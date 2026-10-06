"""D5 - calls and recursion: argument registers, func4, double recursion."""

from .. import judge
from ..cmu import func4
from ..core import Phase, fill

ID = "d5"
TITLE = "함수 호출과 재귀"
TITLE_EN = "calls and recursion"


def s1_args(r):
    m = r.randint(3, 19)
    s = r.randint(1, 4)
    a = r.randint(2, 99)
    c = r.randint(1, 50)
    x = r.randint(1, 999)
    t = a * m - x + (c << s)

    def check(line):
        ret, v = judge.sscanf(line, "%d")
        return ret == 1 and judge.to_int32(a * m - v[0] + (c << s)) == t

    return Phase(
        "s1", "args", "drills/d5/s1.c",
        [("D5_S1_M", m), ("D5_S1_S", s), ("D5_S1_A", a), ("D5_S1_C", c),
         ("D5_S1_T", t)],
        answer=str(x), check=check, title="인자 세 개짜리 함수",
        answers="`%d` 하나뿐이다." % x,
        walkthrough=fill("""\
`phase_1`은 `mix3`를 부르기 직전에 인자 레지스터를 채운다. x86-64 System V 호출 규약에서
정수 인자는 `%rdi`, `%rsi`, `%rdx`, `%rcx`, `%r8`, `%r9` 순서다.

```
mov    $0x<<chex>>,%edx           # 세 번째 인자 c = <<c>>
mov    0xc(%rsp),%esi        # 두 번째 인자 = 입력 x
mov    $0x<<ahex>>,%edi           # 첫 번째 인자 a = <<a>>
callq  <mix3>
cmp    $0x<<thex>>,%eax           # 반환값은 %eax
```

`mix3`(a, b, c) 본문은 `a*<<m>> - b + (c << <<s>>)`를 계산한다(`imul`, `sub`, `shl`).
입력이 **두 번째 인자 b**로 들어간다는 점이 함정이다.

<<a>>·<<m>> - x + <<c>>·<<p>> = <<t>> → x = <<x>>

**과제에서는**: CMU phase 4에서 `func4(x, 0, 14)`의 세 인자를 `%edi`, `%esi`, `%edx`에서 읽어야 한다.
"어느 레지스터가 몇 번째 인자인가"는 모든 phase의 기본이다.
""", a=a, ahex="%x" % a, c=c, chex="%x" % c, m=m, s=s, p=1 << s, t=t,
            thex="%x" % (t & 0xFFFFFFFF), x=x),
        hints=["`callq <mix3>` 직전에 `%edi`, `%esi`, `%edx`에 무엇이 들어가는가?",
               "입력은 몇 번째 인자로 넘어가는가? `mix3` 본문을 식으로 적어라.",
               "a·M - x + (c << S) = T를 x에 대해 푼다."])


def s2_func4(r):
    hi = r.randint(10, 30)
    xs = [x for x in range(hi + 1) if func4(x, 0, hi) == 0]
    x = r.choice(xs)
    listed = ", ".join("`%d`" % v for v in xs)

    def check(line):
        ret, v = judge.sscanf(line, "%d")
        return ret == 1 and 0 <= v[0] <= hi and func4(v[0], 0, hi) == 0

    return Phase(
        "s2", "func4", "drills/d5/s2.c", [("D5_S2_HI", hi)],
        answer=str(x), check=check, title="재귀 이진 탐색 (func4)",
        answers="정답 %d개: %s." % (len(xs), listed),
        walkthrough=fill("""\
`func4(x, 0, <<hi>>)`는 자기 자신을 부르는 이진 탐색이다. 재귀 함수는 이렇게 읽는다.

1. **종료 조건**을 찾는다: `mid == x`이면 0을 돌려준다.
2. **재귀 호출의 인자**를 본다: 왼쪽은 `(x, low, mid-1)`, 오른쪽은 `(x, mid+1, high)`.
3. **돌아온 값을 어떻게 쓰는지** 본다: 왼쪽은 `add %eax,%eax`(×2), 오른쪽은
   `lea 0x1(%rax,%rax,1),%eax`(×2+1).

```
mov    %edx,%eax
sub    %esi,%eax             # high - low
mov    %eax,%ecx
shr    $0x1f,%ecx            # 음수면 1
add    %ecx,%eax             # 0 쪽으로 반올림 보정
sar    %eax                  # / 2
lea    (%rax,%rsi,1),%ecx    # mid = low + ...
```

반환값이 0이 되려면 오른쪽으로 한 번도 가면 안 된다. mid를 직접 따라가 보라:
0~<<hi>>에서 x = mid이거나, x < mid라서 왼쪽 구간에서 다시 mid이거나…

gdb의 `finish`는 현재 함수가 돌아올 때까지 실행하고 반환값(`$rax`)을 보여 준다.
재귀가 헷갈리면 `break func4`를 걸고 `info registers rdi rsi rdx`를 매번 보라.

**과제에서는**: phase 4와 같은 `func4`다. 과제에서는 입력이 `"%d %d"`이고 두 번째 수를
상수와 비교하는 검사가 하나 더 붙는다(`cmpl $0x0,0xc(%rsp)` 같은 모양). 상한(14)도 다를 수 있다.

이 폭탄의 정답: <<listed>>
""", hi=hi, listed=listed),
        hints=["`func4`의 종료 조건과 두 갈래의 재귀 호출 인자를 적어라.",
               "반환값이 0이려면 어느 쪽으로만 내려가야 하는가?",
               "mid = low + (high-low)/2를 직접 계산하며 내려간다. 왼쪽으로만 가다 mid와 같아지는 수."])


def s3_double(r):
    base = r.randint(1, 9)

    def f(n, memo={}):
        if n < 2:
            return n + base
        key = (n, base)
        if key not in memo:
            memo[key] = f(n - 1) + f(n - 2)
        return memo[key]

    vals = [f(n) for n in range(21)]
    n0 = r.randint(8, 20)
    t = vals[n0]

    def check(line):
        ret, v = judge.sscanf(line, "%d")
        return ret == 1 and 0 <= v[0] <= 20 and vals[v[0]] == t

    return Phase(
        "s3", "double", "drills/d5/s3.c",
        [("D5_S3_BASE", base), ("D5_S3_T", t)],
        answer=str(n0), check=check, title="두 번 부르는 재귀",
        answers="`%d` 하나뿐이다 (func5(%d) = %d)." % (n0, n0, t),
        walkthrough=fill("""\
`func5(n)`은 자기 자신을 **두 번** 부른다.

```
cmp    $0x1,%edi
jg     <recurse>
lea    0x<<bhex>>(%rdi),%eax          # n < 2: n + <<base>>
retq
<recurse>:
push   %rbp
push   %rbx
mov    %edi,%ebx             # n을 callee-saved 레지스터에 보관
lea    -0x1(%rdi),%edi
callq  <func5>               # func5(n-1)
mov    %eax,%ebp             # 결과를 callee-saved 레지스터에 보관
lea    -0x2(%rbx),%edi
callq  <func5>               # func5(n-2)
add    %ebp,%eax
```

첫 호출의 결과를 `%ebp`에 담아 두는 이유: 두 번째 호출이 `%eax`를 덮어쓰기 때문이다.
`%rbx`, `%rbp`는 **callee-saved**라서 함수가 쓰기 전에 `push`하고 끝나면 `pop`한다.

f(0)=<<base>>, f(1)=<<base1>>, f(n)=f(n-1)+f(n-2) — 피보나치처럼 커진다. 표를 만들어
<<t>>이 되는 n을 찾는다: **<<n>>**. 입력 범위(0~20)는 `cmp $0x14` + `ja`로 검사한다.

**과제에서는**: 재귀 함수에서 "어떤 값이 호출을 가로질러 보존되어야 하는가"를 callee-saved
레지스터의 `push`/`pop`으로 알아보는 습관.
""", base=base, base1=base + 1, bhex="%x" % base, t=t, n=n0),
        hints=["`func5`의 종료 조건(n < 2)에서 무엇을 돌려주는가?",
               "재귀 호출이 두 번이다. 첫 결과를 어디에 보관했다가 무엇과 더하는가?",
               "f(0), f(1)부터 표를 만들어 목표값이 되는 n을 찾는다."])


STAGES = [
    ("s1", {"args": s1_args}),
    ("s2", {"func4": s2_func4}),
    ("s3", {"double": s3_double}),
]
