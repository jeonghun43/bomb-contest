"""D2 - arithmetic and comparisons: lea/imul/shifts, signedness, division."""

from .. import judge
from ..core import Phase, fill

ID = "d2"
TITLE = "산술과 비교"
TITLE_EN = "arithmetic and comparisons"


def _one_int(line):
    ret, v = judge.sscanf(line, "%d")
    return v[0] if ret == 1 else None


def s1_lea(r):
    shift = r.randint(1, 4)
    mul = r.choice(range(3, 16, 2))          # odd: 2^shift + mul is odd
    sub = r.randint(1, 999)
    x = r.randint(10, 999)
    target = (x << shift) + x * mul - sub

    def check(line):
        v = _one_int(line)
        return v is not None and \
            judge.to_int32((v << shift) + v * mul - sub) == target

    return Phase(
        "s1", "lea", "drills/d2/s1.c",
        [("D2_S1_SHIFT", shift), ("D2_S1_MUL", mul), ("D2_S1_SUB", sub),
         ("D2_S1_TARGET", target)],
        answer=str(x), check=check, title="lea·imul·시프트로 만든 식",
        answers="`%d` 하나뿐이다. 곱하는 수 %d이 홀수라 32비트에서 역산이 유일하다."
                % (x, (1 << shift) + mul),
        walkthrough=fill("""\
C 코드는 `y = (x << <<shift>>) + x * <<mul>> - <<sub>>;` 이지만, 컴파일러는 이것을
**한 번의 곱셈**으로 합쳐 버린다(`x<<<<shift>>`는 `x*<<p>>`이므로 합쳐서 `x*<<m>>`).

```
imul   $0x<<mhex>>,0xc(%rsp),%eax   # 또는 lea / shl / add 조합
sub    $0x<<subhex>>,%eax
cmp    $0x<<thex>>,%eax
```

컴파일러가 곱셈을 `lea (%rax,%rax,4),%eax`(×5), `shl $n`(×2ⁿ) 같은 조합으로
바꾸기도 한다. 각 명령어가 레지스터에 무엇을 하는지 한 줄씩 적어 식을 복원하라.

식: <<m>>·x - <<sub>> = <<target>> → x = (<<target>> + <<sub>>) / <<m>> = **<<x>>**

**과제에서는**: phase 2·4의 배열 인덱스 계산, `lea`로 하는 산술이 계속 나온다.
`lea`는 메모리를 읽지 않는다 — 주소 계산 회로를 빌려 쓰는 덧셈·곱셈일 뿐이다.
""", shift=shift, mul=mul, sub=sub, p=1 << shift, m=(1 << shift) + mul,
            mhex="%x" % ((1 << shift) + mul), subhex="%x" % sub,
            thex="%x" % (target & 0xFFFFFFFF), target=target, x=x),
        hints=["입력은 정수 하나다. 비교 직전까지 레지스터에 어떤 연산이 가해지는가?",
               "`lea`, `shl`, `imul`을 각각 곱셈·덧셈으로 바꿔 하나의 식으로 합쳐라.",
               "a·x - b = c 꼴이다. x = (c + b) / a."])


def s2_signed(r):
    n = r.randint(20, 200)                  # unsigned bound: 2^32 - n
    m = r.randint(2, n - 3)                 # signed bound: x <= -m
    umin = (1 << 32) - n
    lo, hi = -n, -m
    x = r.randint(lo, hi)

    def check(line):
        v = _one_int(line)
        return v is not None and judge.to_uint32(v) >= umin and v <= hi

    return Phase(
        "s2", "signed", "drills/d2/s2.c",
        [("D2_S2_UMIN", umin), ("D2_S2_HIGH", hi)],
        answer=str(x), check=check, title="부호 있는 비교와 없는 비교",
        answers="%d 이상 %d 이하의 정수면 모두 정답." % (lo, hi),
        walkthrough=fill("""\
정수 하나를 **두 번** 비교한다. 한 번은 부호 없는 수로, 한 번은 부호 있는 수로.

```
cmpl   $0x<<uhex>>,0xc(%rsp)
jb     <폭발>              # 부호 없는 비교: x < 0x<<uhex>> 이면 폭발
cmpl   $0x<<hhex>>,0xc(%rsp)
jg     <폭발>              # 부호 있는 비교: x > <<hi>> 이면 폭발
```

| 명령어 | 비교 방식 |
|---|---|
| `ja` / `jb` / `jae` / `jbe` | 부호 없는 (above / below) |
| `jg` / `jl` / `jge` / `jle` | 부호 있는 (greater / less) |

같은 비트 패턴 `0x<<uhex>>`이 부호 없는 수로는 <<umin>>(아주 큰 수), 부호 있는 수로는 <<lo>>이다.
첫 비교는 "x를 부호 없는 수로 볼 때 0x<<uhex>> 이상" = **x는 <<lo>>~-1의 음수**라는 뜻이고,
둘째 비교는 x ≤ <<hi>>. 합치면 <<lo>> ≤ x ≤ <<hi>>.

**과제에서는**: phase 3의 `cmpl $0x7` + `ja`(0~7인지), phase 6의 `sub $0x1` + `cmp $0x5` + `jbe`(1~6인지)가
"음수까지 한 번에 거르는 부호 없는 비교"다. `ja`/`jb`인지 `jg`/`jl`인지부터 확인하는 습관을 들이자.
""", uhex="%x" % umin, umin=umin, lo=lo, hi=hi,
            hhex="%x" % (hi & 0xFFFFFFFF)),
        hints=["두 비교의 점프 명령어가 각각 부호 있는 것인지 없는 것인지 확인하라.",
               "0xffffff..처럼 큰 상수는 부호 있는 수로 보면 작은 음수다. `p (int)0x...`로 확인할 수 있다.",
               "첫 비교는 음수 범위를, 둘째 비교는 상한을 정한다. 둘 다 만족하는 음수."])


DIVISORS = [23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97]


def s3_magic(r):
    div = r.choice(DIVISORS)
    q = r.randint(10, 999)
    rem = r.randint(1, div - 1)
    x = q * div + rem

    def check(line):
        v = _one_int(line)
        if v is None:
            return False
        u = judge.to_uint32(v)
        return u // div == q and u % div == rem

    return Phase(
        "s3", "magic", "drills/d2/s3.c",
        [("D2_S3_DIV", div), ("D2_S3_Q", q), ("D2_S3_R", rem)],
        answer=str(x), check=check, title="상수 나눗셈 (매직 넘버)",
        answers="`%d` 하나뿐이다 (= %d × %d + %d)." % (x, q, div, rem),
        walkthrough=fill("""\
어셈블리에 `div`가 없다. 컴파일러는 상수 나눗셈을 **곱셈 + 시프트**로 바꾼다.

```
mov    $0x........,%edx    # 큰 "매직 넘버"
mov    %ecx,%eax
mul    %edx                # 64비트 곱: 상위 32비트가 %edx로
shr    $0x?,%edx           # → 몫
...
imul   $0x<<divhex>>,%edx,%eax      # 몫 × 나누는 수
sub    %eax,%ecx           # 원래 값 - 몫×나누는 수 = 나머지
```

매직 넘버에서 나누는 수를 역산할 필요는 없다. 나머지를 구하려면 **몫 × 나누는 수**를
빼야 하므로, 그 `imul $0x<<divhex>>`에 나누는 수가 그대로 보인다.

조건: x / <<div>> == <<q>>, x % <<div>> == <<r>> → x = <<q>>·<<div>> + <<r>> = **<<x>>**

**과제에서는**: 부호 있는(`int`) 나눗셈이면 여기에 음수 보정(`sar $0x1f` / `sub`)이 더 붙는다.
phase 4의 `func4`가 `(high-low)/2`를 `shr $0x1f` / `add` / `sar`로 계산하는 것이 그 예다.
""", divhex="%x" % div, div=div, q=q, r=rem, x=x),
        hints=["나눗셈 명령어가 없다. 대신 무엇이 보이는가?",
               "나머지를 구하려면 몫 × 나누는 수를 빼야 한다. 그 `imul`의 상수가 나누는 수다.",
               "x = 몫 × 나누는 수 + 나머지."])


STAGES = [
    ("s1", {"lea": s1_lea}),
    ("s2", {"signed": s2_signed}),
    ("s3", {"magic": s3_magic}),
]
