"""D9 - the hidden stage: how phase_defused() opens the secret phase."""

from .. import judge
from ..core import Phase, fill
from ..words import WORDS

ID = "d9"
TITLE = "숨은 단계"
TITLE_EN = "the hidden stage"

SECRET_LINE = 1              # phase 2's line carries the token
SECRET_WORDS = ["hiddenpath", "trapdoor", "backstage", "undercroft",
                "sidegate", "passkey", "keystone", "loophole"]


def s1_word(r):
    w = r.choice(WORDS)
    return Phase(
        "s1", "word", "drills/d9/s1.c", [("D9_S1_WORD", w)],
        answer=w, check=lambda line, w=w: line == w, title="몸풀기",
        answers="`%s`." % w,
        walkthrough=fill("""\
문자열 비교다(`x/s`로 답 확인). 이 드릴의 진짜 목표는 phase가 아니라
**`phase_defused`** 를 읽는 것이다. 지금 `objdump -d`에서 `<phase_defused>`를 열어 두라.

답: `<<w>>`
""", w=w),
        hints=["D0·D1에서 연습한 그대로다.", "`%esi`의 주소를 `x/s`로.",
               "다 풀었으면 `phase_defused`를 읽어 보라."])


def s2_pair(r):
    a = r.randint(2, 50)
    k = r.randint(2, 9)

    def check(line):
        ret, v = judge.sscanf(line, "%d %d")
        return ret == 2 and v[0] == a and v[1] == judge.to_int32(v[0] * k)

    return Phase(
        "s2", "pair", "drills/d9/s2.c",
        [("D9_S2_A", a), ("D9_S2_K", k)],
        answer="%d %d" % (a, a * k), check=check, title="토큰을 실어 나르는 줄",
        answers="`%d %d` (뒤에 무엇이 붙어도 phase 2는 통과한다)." % (a, a * k),
        walkthrough=fill("""\
`sscanf(input, "%d %d", ...)`는 두 수를 읽은 뒤 **나머지는 무시한다**. 그래서 이 줄 끝에
단어를 하나 더 붙여도 phase 2는 그대로 통과한다. 이것이 숨은 단계의 열쇠다.

답: a = <<a>>, b = a × <<k>> = <<b>>
""", a=a, k=k, b=a * k),
        hints=["두 수의 조건은 상수 비교와 곱셈이다.",
               "`sscanf`는 형식에 없는 뒷부분을 어떻게 처리하는가?",
               "a는 상수, b는 a × 상수."])


def s3_global(r):
    k = r.randint(2, 20)
    c = r.randint(1, 99)
    want = 3 * k + c

    def check(line):
        ret, v = judge.sscanf(line, "%d")
        return ret == 1 and v[0] == want

    return Phase(
        "s3", "global", "drills/d9/s3.c",
        [("D9_S3_K", k), ("D9_S3_C", c)],
        answer=str(want), check=check, title="전역 변수에 달린 답",
        answers="`%d` (= 3 × %d + %d; 3번째 줄을 읽은 시점의 num_input_strings는 3)."
                % (want, k, c),
        walkthrough=fill("""\
비교 대상이 상수가 아니라 **전역 변수** `num_input_strings`로 계산된다.

```
mov    0x...,%eax           # num_input_strings  (전역: 절대 주소 / RIP 상대)
imul   $0x<<khex>>,%eax,%eax
add    $0x<<chex>>,%eax
cmp    %eax,0xc(%rsp)
```

`num_input_strings`는 `read_line`이 입력 줄을 하나 읽을 때마다 1씩 늘린다(빈 줄은 세지 않음).
phase 3를 검사하는 순간 이미 3줄을 읽었으므로 값은 3이다. gdb에서 `x/dw &num_input_strings`로
확인할 수 있다.

답: 3 × <<k>> + <<c>> = **<<want>>**

**과제에서는**: CMU `phase_defused`도 이 변수로 "6번째 줄까지 읽었는가"를 판단한다.
""", k=k, c=c, want=want, khex="%x" % k, chex="%x" % c),
        hints=["비교 대상을 만드는 식에 전역 변수가 들어간다. 그 이름은?",
               "`read_line`이 그 변수를 언제 늘리는가? phase 3 시점의 값은?",
               "값 × 상수 + 상수."])


def secret_key(r):
    key = [r.randint(1, 99), r.randint(2, 30), r.randint(2, 30)]
    want = key[0] + key[1] * key[2]

    def check(line):
        return judge.atoi_int(line) == want

    return Phase(
        "secret", "key", "drills/d9/secret.c", [("D9_SEC_KEY", key)],
        answer=str(want), check=check, title="숨은 단계",
        answers="`%d`." % want,
        walkthrough=fill("""\
**찾기** — `phase_defused`:

```
cmpl   $0x3,num_input_strings     # 마지막(3번째) 줄을 읽은 뒤에만
jne    <끝>
lea    ...,%r8                    # char string[80]
lea    ...,%rcx                   # int b
lea    ...,%rdx                   # int a
mov    $0x...,%esi                # "%d %d %s"
mov    $0x...,%edi                # input_strings + 80  ← 2번째 줄 (줄당 80바이트)
callq  <__isoc99_sscanf@plt>
cmp    $0x3,%eax                  # 세 개 다 읽혔는가
...
mov    $0x...,%esi                # 비밀 단어
callq  <strings_not_equal>
...
callq  <secret_phase>
```

`input_strings`는 80바이트 × 20줄 배열이다. `input_strings + 80`은 두 번째 줄이다.
비밀 단어는 `x/s`로 본다. **2번째 줄 끝에 그 단어를 붙이면** 3단계 뒤에 숨은 단계가 열린다.

**풀기** — `secret_phase`는 `strtol`로 수를 읽어 `d9_key[0] + d9_key[1] * d9_key[2]`와 비교한다.
`x/3dw &d9_key` → <<key>> → **<<want>>**

**과제에서는**: CMU 폭탄도 똑같다. 6번째 줄 뒤에 `phase_defused`가 **4번째 줄**
(`input_strings + 240`)을 `"%d %d %s"`로 다시 읽는다. 어느 줄인지, 어떤 형식인지, 어떤 단어인지
— 이 세 가지만 찾으면 된다.
""", key=key, want=want),
        hints=["숨은 단계는 `phase_defused`가 연다. 어떤 조건에서 `secret_phase`를 부르는가?",
               "`sscanf`의 첫 인자 `input_strings + 80`은 몇 번째 줄인가? 비교하는 단어는 `x/s`로.",
               "2번째 줄 끝에 단어를 붙이고, 숨은 단계에서는 `x/3dw &d9_key`로 식을 계산한다."])


STAGES = [
    ("s1", {"word": s1_word}),
    ("s2", {"pair": s2_pair}),
    ("s3", {"global": s3_global}),
    ("secret", {"key": secret_key}),
]
