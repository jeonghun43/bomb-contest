"""D4 - switch statements: jump tables, offsets, sparse compares."""

from .. import judge
from ..core import Phase, fill

ID = "d4"
TITLE = "switch와 점프 테이블"
TITLE_EN = "switch and jump tables"


def s1_dense(r):
    vals = r.sample(range(100, 1000), 5)
    k = r.randrange(5)
    pairs = ", ".join("`%d %d`" % (i, v) for i, v in enumerate(vals))

    def check(line):
        ret, v = judge.sscanf(line, "%d %d")
        return ret >= 2 and 0 <= v[0] <= 4 and v[1] == vals[v[0]]

    return Phase(
        "s1", "dense", "drills/d4/s1.c",
        [("D4_S1_V%d" % i, v) for i, v in enumerate(vals)],
        answer="%d %d" % (k, vals[k]), check=check, title="밀집 switch",
        answers="다섯 쌍 모두 정답이다: %s." % pairs,
        walkthrough=fill("""\
case가 0, 1, 2, 3, 4 처럼 촘촘하면 컴파일러는 비교를 늘어놓지 않고 **점프 테이블**을 만든다.

```
cmpl   $0x4,0x8(%rsp)          # 0~4인가 (ja: 부호 없는 비교, 음수도 걸러짐)
ja     <default>
mov    0x8(%rsp),%eax
jmpq   *0x...(,%rax,8)         # 테이블[index]로 간접 점프
```

테이블은 `.rodata`에 있는 8바이트 주소 배열이다.

```
(gdb) x/5gx 0x...              # case 0..4의 시작 주소
```

각 주소로 가 보면 `mov $값,%eax` 후 공통 지점으로 점프한다. 공통 지점에서 두 번째 입력과 비교한다.

**과제에서는**: phase 3이 이것이다. case가 0~7로 여덟 개라 테이블이 `x/8gx`일 뿐, 읽는 법은 같다.

이 폭탄: <<pairs>>
""", pairs=pairs),
        hints=["`ja` 앞의 `cmp`가 첫 번째 수의 범위를 알려 준다.",
               "`jmpq *0x...(,%rax,8)`의 `0x...`를 `x/5gx`로 보라.",
               "테이블의 주소 하나로 가서 `%eax`에 넣는 상수를 읽는다."])


def s2_offset(r):
    base = r.randint(100, 900)
    chars = r.sample("abcdefghijklmnopqrstuvwxyz", 5)
    k = r.randrange(5)
    macros = [("D4_S2_BASE", base)]
    macros += [("D4_S2_C%d" % i, ord(c)) for i, c in enumerate(chars)]
    pairs = ", ".join("`%d %s`" % (base + i, chars[i]) for i in range(5))

    def check(line):
        ret, v = judge.sscanf(line, "%d %c")
        if ret < 2:
            return False
        i = v[0] - base
        return 0 <= i <= 4 and v[1] == chars[i]

    return Phase(
        "s2", "offset", "drills/d4/s2.c", macros,
        answer="%d %s" % (base + k, chars[k]), check=check,
        title="`%d %c`와 case 오프셋",
        answers="다섯 쌍 모두 정답이다: %s." % pairs,
        walkthrough=fill("""\
입력 형식이 `"%d %c"`(수, 문자)다. 형식 문자열은 `sscanf`의 두 번째 인자(`%esi`) 주소를
`x/s`로 보면 확인된다.

case가 0이 아니라 <<base>>부터 시작한다. 컴파일러는 **먼저 빼고** 범위를 검사한다.

```
mov    0x..(%rsp),%eax
sub    $0x<<basehex>>,%eax              # index - <<base>>
cmp    $0x4,%eax
ja     <default>
jmpq   *0x...(,%rax,8)
```

각 case는 기대하는 문자 하나를 정한다(`mov $0x..,%eax`). 문자는 ASCII 코드로 보이니
`man ascii`나 gdb의 `print/c 0x6b`로 바꾼다.

**과제에서는**: 예전 학기의 phase 3은 `"%d %c %d"`로, 각 case가 문자와 수를 하나씩 정했다.
`sub` + `cmp` + `ja`는 "case 범위가 0부터가 아니다"라는 신호다.

이 폭탄: <<pairs>>
""", base=base, basehex="%x" % base, pairs=pairs),
        hints=["`sscanf`의 형식 문자열부터 `x/s`로 확인하라. 입력은 두 개다.",
               "`sub $0x...` 다음의 `cmp $0x4`는 index - 오프셋이 0~4인지 본다.",
               "한 case에서 문자 코드를 읽는다. 수 = 오프셋 + case 번호."])


def s3_sparse(r):
    keys = sorted(r.sample(range(1, 5000), 4))
    while any(b - a < 300 for a, b in zip(keys, keys[1:])):
        keys = sorted(r.sample(range(1, 5000), 4))
    keys = r.sample(keys, 4)               # case order in the source
    adds = [r.randint(10, 400) for _ in range(4)]
    result = {
        keys[0]: adds[0] + adds[1],
        keys[1]: adds[1],
        keys[2]: adds[2] + adds[3],
        keys[3]: adds[3],
    }
    pick = r.choice(keys)
    pairs = ", ".join("`%d %d`" % (k, result[k]) for k in sorted(result))
    macros = [("D4_S3_K%d" % i, k) for i, k in enumerate(keys)]
    macros += [("D4_S3_A%d" % i, a) for i, a in enumerate(adds)]

    def check(line):
        ret, v = judge.sscanf(line, "%d %d")
        return ret == 2 and v[0] in result and v[1] == result[v[0]]

    return Phase(
        "s3", "sparse", "drills/d4/s3.c", macros,
        answer="%d %d" % (pick, result[pick]), check=check,
        title="희소 switch와 fall-through",
        answers="네 쌍 모두 정답이다: %s." % pairs,
        walkthrough=fill("""\
case 값이 띄엄띄엄(<<keys>>)이면 테이블이 너무 커지므로, 컴파일러는 **비교**를 늘어놓는다.

```
cmp    $0x...,%eax
je     <case A>
jg     <오른쪽 절반>         # 범위를 반씩 나누기도 한다
cmp    $0x...,%eax
je     <case B>
...
```

`je` 대상들을 따라가 각 case의 코드를 읽는다. 두 case는 `break`가 없어 **다음 case로 흘러간다**
(fall-through). 어셈블리에서는 한 case의 코드 끝에 점프 없이 다음 case 코드가 바로 이어진다.

```
case K0: x += A0;   // break 없음 → 아래로
case K1: x += A1; break;
```

각 키에 대해 실제로 실행되는 덧셈을 모두 더하면 그 키의 기대값이다.

**과제에서는**: switch가 항상 점프 테이블이 되지는 않는다. `cmp`/`je`가 줄줄이 나오면 희소 switch다.

이 폭탄: <<pairs>>
""", keys=", ".join(str(k) for k in sorted(keys)), pairs=pairs),
        hints=["점프 테이블이 없다. 대신 상수와의 `cmp`/`je`가 여러 번 나온다. 그 상수들이 case 값이다.",
               "한 case로 가서, `jmp`가 나올 때까지 실행되는 덧셈을 모두 따라가라 (fall-through).",
               "키 하나를 고르고, 그 키에서 실행되는 덧셈의 합이 두 번째 수다."])


STAGES = [
    ("s1", {"dense": s1_dense}),
    ("s2", {"offset": s2_offset}),
    ("s3", {"sparse": s3_sparse}),
]
