"""D1 - strings: string_length / strings_not_equal and where strings live."""

from ..core import Phase, fill
from ..words import PHRASES, WORDS

ID = "d1"
TITLE = "문자열"
TITLE_EN = "strings"

LETTERS = "abcdefghijklmnopqrstuvwxyz"


def s1_global(r):
    t = r.choice(PHRASES)
    return Phase(
        "s1", "global", "drills/d1/s1.c", [("D1_S1_TEXT", t)],
        answer=t, check=lambda line, t=t: line == t, title="전역 문자열과 비교",
        answers="`%s` 한 줄 전체. 공백 하나라도 다르면 폭발한다." % t,
        walkthrough=fill("""\
`phase_1` 자체는 D0 1단계와 같다. 이번 단계의 목표는 **비교 함수 자체를 읽는 것**이다.
`objdump -d`에서 `<strings_not_equal>`과 `<string_length>`를 찾아 보라.

`string_length`:
```
cmpb   $0x0,(%rdi)          # 첫 글자가 0이면 길이 0
je     ...
mov    %rdi,%rdx
add    $0x1,%rdx            # 포인터를 한 칸씩
mov    %edx,%eax
sub    %edi,%eax            # 길이 = 현재 포인터 - 시작
cmpb   $0x0,(%rdx)
jne    ...
```

`strings_not_equal`은 두 문자열의 `string_length`를 먼저 비교하고(다르면 1),
같으면 `movzbl (%rbx),%eax` / `cmp (%rbp),%al`로 한 글자씩 비교한다.
그래서 **길이가 다르면 내용은 보지도 않는다** — 끝에 공백 하나만 있어도 실패한다.

**과제에서는**: 이 두 함수는 CMU 폭탄에 그대로 있고 여러 phase가 쓴다.
한 번 읽어 두면 다음부터는 "문자열 같으면 0"으로 넘어갈 수 있다.

이 폭탄의 답: `<<t>>`
""", t=t),
        hints=["`strings_not_equal`은 0을 돌려줄 때 같다는 뜻이다.",
               "비교 대상 주소는 `%esi`로 넘어간다.",
               "`x/s <주소>`로 문장 전체를 읽는다. 공백까지 그대로."])


def s2_stack(r):
    w = "".join(r.choice(LETTERS) for _ in range(r.randint(9, 15)))
    return Phase(
        "s2", "stack", "drills/d1/s2.c",
        [("D1_S2_WORD", w), ("D1_S2_LEN", len(w))],
        answer=w, check=lambda line, w=w: line == w, canary=True,
        title="스택에 조립되는 문자열",
        answers="`%s` 하나뿐이다." % w,
        walkthrough=fill("""\
지역 배열 `char key[] = "...";`는 `.rodata`에서 복사되지 않고, 컴파일러가
**8바이트 즉시값**으로 스택에 직접 써 넣는다.

```
movabs $0x...,%rax
mov    %rax,(%rsp)           # key[0..7]
movl   $0x...,0x8(%rsp)      # key[8..11]
...
```

x86-64는 **리틀 엔디언**이라 즉시값의 **낮은 바이트가 먼저(낮은 주소)** 온다.
예: `movabs $0x6766656463626261,%rax`는 메모리에 `61 62 62 63 64 65 66 67` = `"abbcdefg"`.

손으로 뒤집어도 되고, `string_length` 비교를 통과한 뒤 `strings_not_equal`에서 멈춰
`x/s $rsi`로 봐도 된다. 길이 검사(`cmp $0x<<lenhex>>,%eax`)가 먼저라서 엉뚱한 길이를 넣으면
비교 함수까지 가지도 못한다.

**과제에서는**: 지역 문자열·배열 초기화, 그리고 숫자를 바이트로 볼 때 리틀 엔디언을
늘 의식해야 한다. `x/8xb`와 `x/2gx`의 출력 순서가 다른 이유도 이것이다.

이 폭탄의 답: `<<w>>` (길이 <<len>>)
""", w=w, len=len(w), lenhex="%x" % len(w)),
        hints=["입력 길이가 먼저 검사된다. 몇 글자여야 하는가?",
               "`movabs`의 즉시값을 바이트로 쪼개 낮은 바이트부터 읽어라.",
               "또는 `break strings_not_equal` 후 `x/s $rsi`."])


def s3_bylen(r):
    k = r.randrange(8)
    words = []
    for i in range(8):
        if i == k:
            words.append("".join(r.choice(LETTERS) for _ in range(i + 2)))
        else:
            cands = [w for w in WORDS if len(w) != i + 2]
            words.append(r.choice(cands))
    ans = words[k]

    def check(line, words=words):
        n = len(line)
        return 2 <= n <= 9 and line == words[n - 2]

    return Phase(
        "s3", "bylen", "drills/d1/s3.c", [("D1_S3_WORDS", words)],
        answer=ans, check=check, title="길이로 고르는 문자열",
        answers="`%s` 하나뿐이다 (길이 %d → 표의 %d번 칸)." % (ans, k + 2, k),
        walkthrough=fill("""\
입력 길이 n이 2~9가 아니면 폭발하고, 그다음 `d1_words[n-2]`와 비교한다.

```
callq  <string_length>
lea    -0x2(%rax),%edx
cmp    $0x7,%edx                 # n-2가 0~7인가 (부호 없는 비교)
ja     <explode>
cltq                             # n을 64비트로 부호 확장
mov    0x...(,%rax,8),%rsi       # d1_words[n-2]: 8바이트 포인터 배열
callq  <strings_not_equal>
```

`d1_words`는 **포인터 8개의 배열**이다. `x/8gx 0x...`로 포인터를 보고,
각 포인터를 `x/s`로 따라가면 문자열이 나온다(`x/8s`로는 안 된다는 점에 주의).
칸 i의 문자열 길이가 i+2와 같은 칸이 하나뿐이고, 그것이 답이다.

**과제에서는**: "배열에 든 것이 값인가, 포인터인가"를 구분하는 습관.
CMU phase 3의 점프 테이블, phase 6의 노드 포인터 배열도 같은 패턴이다.

이 폭탄: d1_words = <<words>> → 답 `<<ans>>`
""", words=words, ans=ans),
        hints=["허용되는 길이 범위와, 그 길이로 무엇을 고르는지 보라.",
               "`0x...(,%rax,8)`는 8바이트 칸의 배열 = 포인터 배열이다. `x/8gx`로 보라.",
               "포인터마다 `x/s`. 길이가 (칸 번호 + 2)인 문자열이 답이다."])


STAGES = [
    ("s1", {"global": s1_global}),
    ("s2", {"stack": s2_stack}),
    ("s3", {"bylen": s3_bylen}),
]
