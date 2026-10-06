"""D0 - tools of the trade: find answers with gdb, objdump and strings."""

from .. import judge
from ..core import Phase, fill
from ..words import WORDS

ID = "d0"
TITLE = "도구 기본기"
TITLE_EN = "tools of the trade"


def s1_rodata(r):
    w = r.choice(WORDS)
    return Phase(
        "s1", "rodata", "drills/d0/s1.c", [("D0_S1_WORD", w)],
        answer=w, check=lambda line, w=w: line == w,
        title="`.rodata`에 있는 답",
        answers="`%s` 하나뿐이다." % w,
        walkthrough=fill("""\
`objdump -d bomb`에서 `<phase_1>`을 찾는다. 짧다.

```
mov    $0x...,%esi
callq  <strings_not_equal>
test   %eax,%eax
```

`%esi`(두 번째 인자)로 넘기는 즉시값은 **주소**다. 문자열 상수는 읽기 전용 영역
`.rodata`에 있다. 확인하는 방법은 세 가지다.

- gdb: `x/s 0x...`
- `strings bomb` 출력에서 찾기 (수많은 문자열 중 하나라 오래 걸린다)
- `objdump -s -j .rodata bomb`로 그 주소의 바이트 보기

**과제에서는**: CMU 폭탄 phase 1이 정확히 이 모양이다. 주소 → `x/s` 습관을 들이면
1분 안에 끝난다.

이 폭탄의 답: `<<w>>`
""", w=w),
        hints=["`phase_1`이 부르는 함수에 무엇을 넘기는지 보라.",
               "`mov $0x...,%esi`의 값은 주소다.",
               "gdb에서 `x/s <그 주소>`."])


def s2_register(r):
    tab = [r.randint(2, 40), r.randint(2, 40), r.randint(1, 99), r.randint(1, 99)]
    want = tab[0] * tab[1] + tab[2] - tab[3]

    def check(line, want=want):
        ret, v = judge.sscanf(line, "%d")
        return ret == 1 and v[0] == want

    return Phase(
        "s2", "register", "drills/d0/s2.c", [("D0_S2_TAB", tab)],
        answer=str(want), check=check, title="비교 직전의 레지스터",
        answers="`%d` 하나뿐이다 (뒤에 다른 내용이 붙어도 된다)." % want,
        walkthrough=fill("""\
입력은 `sscanf(input, "%d", ...)`로 읽는 정수 하나다. 비교 대상은 상수가 아니라
전역 배열 `d0_tab`의 값으로 **실행 중에 계산**된다.

```
mov    0x...,%eax        # d0_tab[0]
imul   0x...,%eax        # * d0_tab[1]
add    0x...,%eax        # + d0_tab[2]
sub    0x...,%eax        # - d0_tab[3]
cmp    %eax,0xc(%rsp)    # 입력과 비교
```

계산식을 다 읽지 않아도 된다. gdb에서 비교 명령어에 멈추고 레지스터를 보면 된다.

```
(gdb) break explode_bomb
(gdb) break *<cmp 명령어의 주소>
(gdb) run answers.txt
(gdb) print $eax          # 또는 info registers
```

**과제에서는**: "비교 직전에 멈추고 레지스터를 본다"는 거의 모든 phase에서 쓰는 기술이다.
특히 계산이 길 때 검산용으로 쓴다.

이 폭탄: d0_tab = <<tab>> → <<a>>*<<b>> + <<c>> - <<d>> = **<<want>>**
""", tab=tab, a=tab[0], b=tab[1], c=tab[2], d=tab[3], want=want),
        hints=["비교하는 값이 즉시값으로 보이지 않는다면, 실행 중에 계산된다는 뜻이다.",
               "`cmp` 명령어의 주소에 `break *주소`를 걸어라.",
               "멈춘 뒤 `print $eax`. 그 값이 답이다."])


def s3_stack(r):
    w = r.choice([x for x in WORDS if 6 <= len(x) <= 12])
    key = r.choice([k for k in range(1, 128)
                    if all(ord(c) ^ k not in (0,) for c in w)])
    enc = [ord(c) ^ key for c in w]
    return Phase(
        "s3", "stack", "drills/d0/s3.c",
        [("D0_S3_ENC", enc), ("D0_S3_LEN", len(w)), ("D0_S3_KEY", key)],
        answer=w, check=lambda line, w=w: line == w,
        title="실행 중에 만들어지는 답",
        answers="`%s` 하나뿐이다." % w,
        walkthrough=fill("""\
이번에는 `strings bomb`에 답이 나오지 않는다. 답은 실행 중에 만들어진다.

```
movzbl 0x...(%rax),%edx     # d0_enc[i]
xor    $0x<<keyhex>>,%edx           # 키와 XOR
mov    %dl,0x...(%rax)      # 전역 버퍼 d0_buf[i]에 저장
...
mov    $0x...,%esi          # 두 번째 인자 = d0_buf
callq  <strings_not_equal>
```

XOR를 손으로 풀어도 되지만, 더 빠른 방법은 **비교 함수가 불리는 순간 두 번째 인자를 보는 것**이다.

```
(gdb) break strings_not_equal
(gdb) run answers.txt          # 1, 2번 답을 넣고
(gdb) x/s $rsi
```

**과제에서는**: 비교할 문자열이 실행 중에 만들어지는 경우(phase 5의 변환 결과 등)가 있고,
그때는 보통 스택 버퍼라서 함수 앞뒤에 카나리 코드(`%fs:0x28`)가 붙는다.
`break <비교함수>` + `x/s $rdi`, `x/s $rsi`로 양쪽을 한 번에 본다.

이 폭탄의 답: `<<w>>` (키 0x<<keyhex>>)
""", w=w, keyhex="%x" % key),
        hints=["`strings`로 찾을 수 없다면 답은 실행 중에 만들어진다.",
               "`strings_not_equal`이 불리는 순간 두 인자는 레지스터에 있다.",
               "`break strings_not_equal` 후 `x/s $rsi`."])


STAGES = [
    ("s1", {"rodata": s1_rodata}),
    ("s2", {"register": s2_register}),
    ("s3", {"stack": s3_stack}),
]
