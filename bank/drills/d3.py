"""D3 - loops and arrays: read_six_numbers and recurrences."""

from .. import judge
from ..core import Phase, fill

ID = "d3"
TITLE = "반복문과 배열"
TITLE_EN = "loops and arrays"

I32 = judge.to_int32


def _six(line):
    return judge.read_six_numbers(line)


def _seq_phase(slot, variant, template, macros, seq, rule_ok, title,
               walkthrough, hints, **values):
    answer = " ".join(str(v) for v in seq)

    def check(line):
        a = _six(line)
        return a is not None and rule_ok(a)

    return Phase(slot, variant, template, macros, answer=answer, check=check,
                 title=title, answers="`%s` 하나뿐이다." % answer,
                 walkthrough=fill(walkthrough, answer=answer, **values),
                 hints=hints)


def s1_double(r):
    first = r.randint(1, 12)
    seq = [first << k for k in range(6)]
    return _seq_phase(
        "s1", "double", "drills/d3/s1.c", [("D3_S1_FIRST", first)], seq,
        lambda a: a[0] == first and all(a[i] == I32(a[i - 1] * 2)
                                        for i in range(1, 6)),
        "두 배씩 커지는 수열", """\
`read_six_numbers`(스택 배열에 정수 6개)부터 읽는다. 이 함수 안의 `sscanf` 인자를 보면
배열의 각 칸 주소(`lea 0x4(%rsi),%rcx` …)가 차례로 넘어간다. 6번째 이후 인자는
레지스터가 모자라 **스택으로** 넘어간다(`mov %rax,(%rsp)`).

phase 쪽 루프:
```
cmpl   $0x<<fhex>>,(%rsp)         # 첫 값
...
mov    -0x4(%rbx),%eax       # 앞 원소
add    %eax,%eax             # ×2
cmp    %eax,(%rbx)           # 현재 원소와 비교
add    $0x4,%rbx             # 다음 칸 (int = 4바이트)
cmp    %rbp,%rbx             # 끝 포인터
```

컴파일러가 `for (i = 1; i < 6; i++)`를 **포인터 두 개(현재, 끝)**로 바꿨다.
인덱스 변수가 사라지는 것은 -O1의 흔한 모습이다.

**과제에서는**: CMU phase 2가 정확히 이 구조다.

정답: `<<answer>>`
""", ["첫 번째 값은 상수와 바로 비교된다.",
      "루프에서 `-0x4(%rbx)`(앞 원소)로 무엇을 계산하는가?",
      "`add %eax,%eax`는 두 배."], fhex="%x" % first)


def s2_addi(r):
    first = r.randint(0, 20)
    seq = [first]
    for i in range(1, 6):
        seq.append(seq[-1] + i)
    return _seq_phase(
        "s2", "addi", "drills/d3/s2_addi.c", [("D3_S2_FIRST", first)], seq,
        lambda a: a[0] == first and all(a[i] == I32(a[i - 1] + i)
                                        for i in range(1, 6)),
        "인덱스를 더하는 수열", """\
이번 점화식은 `a[i] = a[i-1] + i`다. 앞 단계와 달리 **인덱스 i가 계산에 쓰이므로**
컴파일러가 i를 레지스터에 남겨 둔다.

```
mov    $0x1,%ebx             # i = 1
...
mov    %ebx,%eax
add    -0x4(%rsp,%rbx,4),%eax  # a[i-1] + i   (스케일 4 = int)
cmp    %eax,(%rsp,%rbx,4)      # a[i]
add    $0x1,%rbx
cmp    $0x6,%rbx
```

`(%rsp,%rbx,4)`는 `rsp + rbx*4` — 배열 `a[i]`의 주소다. 스케일(1, 2, 4, 8)이 원소 크기를 알려 준다.

**과제에서는**: 학기마다 phase 2의 점화식이 바뀐다(2배, +i, ×(i+1) …). 루프 본문의 산술만
정확히 읽으면 어느 변형이든 같다.

정답: `<<answer>>`
""", ["첫 값은 상수, 이후는 루프다. 루프 카운터가 계산에 쓰이는가?",
      "`(%rsp,%rbx,4)`는 a[i], `-0x4(%rsp,%rbx,4)`는 a[i-1]이다.",
      "a[i] = a[i-1] + i."])


def s2_fact(r):
    first = r.randint(1, 5)
    seq = [first]
    for i in range(1, 6):
        seq.append(seq[-1] * (i + 1))
    return _seq_phase(
        "s2", "fact", "drills/d3/s2_fact.c", [("D3_S2_FIRST", first)], seq,
        lambda a: a[0] == first and all(a[i] == I32(a[i - 1] * (i + 1))
                                        for i in range(1, 6)),
        "(i+1)을 곱하는 수열", """\
점화식은 `a[i] = a[i-1] * (i+1)`다. 계승(factorial)과 같은 꼴이다.

```
lea    0x1(%rbx),%eax        # i + 1    (lea로 하는 덧셈)
imul   -0x4(%rsp,%rbx,4),%eax  # × a[i-1]
cmp    %eax,(%rsp,%rbx,4)      # a[i]
```

`lea 0x1(%rbx),%eax`는 메모리를 읽지 않는다. 그냥 `eax = rbx + 1`이다.

**과제에서는**: 학기마다 phase 2의 점화식이 바뀐다. `lea`·`imul`·인덱스 레지스터를 식으로
바꾸는 연습이 핵심이다.

정답: `<<answer>>`
""", ["루프 안의 `lea`는 메모리 접근이 아니라 계산이다.",
      "`lea 0x1(%rbx)`는 i+1, 그다음 `imul`의 상대는 a[i-1]이다.",
      "a[i] = a[i-1] × (i+1)."])


def s3_fib(r):
    a, b = r.randint(1, 9), r.randint(1, 9)
    seq = [a, b]
    for _ in range(4):
        seq.append(seq[-1] + seq[-2])
    answer = " ".join(str(v) for v in seq)

    def check(line):
        x = _six(line)
        return x is not None and x[0] == a and all(
            x[i] == I32(x[i - 1] + x[i - 2]) for i in range(2, 6))

    return Phase(
        "s3", "fib", "drills/d3/s3_fib.c", [("D3_S3_A", a)],
        answer=answer, check=check, title="앞의 두 값을 쓰는 수열",
        answers="첫 값이 %d이고 셋째부터 앞의 두 값의 합이면 모두 정답 (두 번째 값은 자유). 예: `%s`."
                % (a, answer),
        walkthrough=fill("""\
첫 값만 상수(<<a>>)와 비교되고, 루프는 **i=2부터** `a[i] = a[i-1] + a[i-2]`를 검사한다.

```
cmpl   $0x<<ahex>>,(%rsp)          # a[0]
...
mov    -0x4(%rbx),%eax       # a[i-1]
add    -0x8(%rbx),%eax       # + a[i-2]
cmp    %eax,(%rbx)           # a[i]
```

`-0x4`, `-0x8`처럼 **음수 오프셋이 둘** 보이면 앞의 원소 두 개를 쓴다는 신호다.
루프가 a[2]부터 시작하므로 a[1]은 아무 값이나 된다. 두 번째 값을 정하고 나머지를 계산하라.

**과제에서는**: 루프가 몇 번째 원소부터 시작하는지, 앞의 원소를 몇 개 쓰는지부터 확인하라.
검사하지 않는 원소가 있으면 그 자리는 자유다.

정답 예: `<<answer>>`
""", a=a, ahex="%x" % a, answer=answer),
        hints=["상수와 비교되는 것은 몇 번째 값인가? 루프는 몇 번째부터 시작하는가?",
               "루프가 참조하는 오프셋 `-0x4`, `-0x8`은 각각 몇 번째 앞 원소인가?",
               "첫 값은 상수, 둘째는 아무 값, 셋째부터는 앞의 두 값의 합."])


def s3_collatz(r):
    while True:
        first = r.randint(7, 99)
        seq = [first]
        for _ in range(5):
            p = seq[-1]
            seq.append(3 * p + 1 if p & 1 else p // 2)
        if min(seq) > 1 and len(set(seq)) == 6:
            break

    def rule(a):
        if a[0] != first:
            return False
        for i in range(1, 6):
            p = a[i - 1]
            want = I32(3 * p + 1) if p & 1 else (abs(p) // 2) * (1 if p >= 0 else -1)
            if a[i] != want:
                return False
        return True

    return _seq_phase(
        "s3", "collatz", "drills/d3/s3_collatz.c", [("D3_S3_FIRST", first)],
        seq, rule, "조건에 따라 달라지는 수열", """\
다음 값이 앞 값의 **홀짝**에 따라 달라진다. 컴파일러는 이것을 분기 없이 쓰기도 한다.

```
test   $0x1,%al              # 홀수인가
je     <짝수>
lea    0x1(%rax,%rax,2),%eax # 3n + 1      (rax + rax*2 + 1)
...
<짝수>:
mov    %eax,%edx
shr    $0x1f,%edx            # 부호 비트
add    %edx,%eax             # 음수면 +1 (0 쪽으로 반올림)
sar    %eax                  # n / 2
```

`lea 0x1(%rax,%rax,2)`는 `3n+1`, `shr $0x1f` / `add` / `sar`는 **부호 있는 나눗셈 /2**다.

**과제에서는**: 조건 분기 + `lea` 산술 + 부호 있는 나눗셈 보정이 한 루프에 모였다.
CMU phase 4의 `func4`도 같은 나눗셈 보정을 쓴다.

정답: `<<answer>>`
""", ["`test $0x1`은 무엇을 검사하는가?",
      "`lea 0x1(%rax,%rax,2)`를 식으로 쓰면? `sar` 앞의 `shr $0x1f`/`add`는 무엇을 보정하는가?",
      "홀수면 3n+1, 짝수면 n/2 (콜라츠 수열)."])


STAGES = [
    ("s1", {"double": s1_double}),
    ("s2", {"addi": s2_addi, "fact": s2_fact}),
    ("s3", {"fib": s3_fib, "collatz": s3_collatz}),
]
