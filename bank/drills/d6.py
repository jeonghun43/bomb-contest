"""D6 - characters and tables: nibble indexing, sums, index chains."""

from .. import judge
from ..core import Phase, fill

ID = "d6"
TITLE = "문자 처리와 표"
TITLE_EN = "characters and tables"


def _nibble_char(i):
    return "p" if i == 0 else chr(0x60 + i)


def s1_charmap(r):
    letters = r.sample("abcdefghijklmnopqrstuvwxyz", 16)
    table = "".join(letters)
    target = "".join(r.choice(letters) for _ in range(6))
    answer = "".join(_nibble_char(table.index(c)) for c in target)

    def check(line):
        return len(line) == 6 and \
            "".join(table[ord(c) & 0xF] for c in line) == target

    return Phase(
        "s1", "charmap", "drills/d6/s1.c",
        [("D6_S1_ARRAY", list(letters)), ("D6_S1_TARGET", target)],
        answer=answer, check=check, title="하위 4비트로 고르는 글자",
        answers="하위 4비트가 각각 %s인 여섯 글자면 모두 정답. 예: `%s`."
                % (", ".join(str(table.index(c)) for c in target), answer),
        walkthrough=fill("""\
입력 길이가 6인지 본 뒤, 글자마다 표에서 하나를 골라 목표 문자열의 같은 자리와 비교한다.

```
movsbl (%rbx),%eax             # input[i]
and    $0xf,%eax               # 하위 4비트 (0~15)
movzbl 0x...(%rax),%eax        # d6_letters[하위 4비트]
cmp    0x...(%rdx),%al         # 목표 문자열[i]와 비교
jne    <폭발>
```

`and $0xf`는 글자의 **하위 4비트만 남긴다**. ASCII에서 `a`=0x61, `b`=0x62 …이므로
`a`→1, `b`→2, …, `o`→15, `p`→0. 반대로 말하면 원하는 인덱스 i의 글자를 하나 고르면 된다.

표(`x/s 0x...` 또는 `x/16c`): `<<table>>`, 목표(`x/s`): `<<target>>`.
목표 글자마다 표의 위치를 찾는다.

**과제에서는**: phase 5가 같은 인덱싱을 한다. 과제에서는 고른 글자를 스택 버퍼에 모은 뒤
`strings_not_equal`로 한 번에 비교하므로 버퍼 때문에 카나리 코드(`%fs:0x28`)가 붙고,
표 이름이 `array.NNNN`으로 보인다. 하위 4비트만 맞으면 되니 정답이 여러 개인 것도 같다.

정답 예: `<<answer>>`
""", table=table, target=target, answer=answer),
        hints=["`and $0xf` 뒤에 남는 값의 범위는? 그 값으로 무엇을 읽는가?",
               "표와 목표 문자열을 둘 다 `x/s`로 보라.",
               "목표 글자의 표 위치 i → 하위 4비트가 i인 글자 (`a`=1 … `o`=15, `p`=0)."])


def s2_sum(r):
    vals = [r.randint(1, 20) for _ in range(16)]
    length = r.randint(4, 6)
    picks = [r.randrange(16) for _ in range(length)]
    total = sum(vals[i] for i in picks)
    answer = "".join(_nibble_char(i) for i in picks)

    def check(line):
        return len(line) == length and \
            sum(vals[ord(c) & 0xF] for c in line) == total

    return Phase(
        "s2", "sum", "drills/d6/s2.c",
        [("D6_S2_VALS", vals), ("D6_S2_LEN", length), ("D6_S2_SUM", total)],
        answer=answer, check=check, title="표 값의 합",
        answers="길이 %d이고 표 값의 합이 %d인 글자열이면 모두 정답. 예: `%s`."
                % (length, total, answer),
        walkthrough=fill("""\
이번 표는 **int 배열**이다. 인덱싱에 스케일 4가 붙는다.

```
movsbl (%rdi,%rax,1),%edx      # input[i] (부호 확장)
and    $0xf,%edx
add    0x...(,%rdx,4),%ecx     # sum += d6_vals[하위 4비트]   ← 4바이트 칸
```

`x/16dw 0x...`로 표를 정수로 본다(`w` = 4바이트, `d` = 10진수).
길이 <<len>>, 합 <<sum>>이 되도록 인덱스를 고르고, 각 인덱스를 하위 4비트로 갖는 글자로 바꾼다.

표: <<vals>>

**과제에서는**: 예전 학기의 CMU phase 5 중에는 이렇게 **합**을 검사하는 변형이 있었다.
`x/..c`(문자)와 `x/..dw`(int) 중 무엇으로 볼지는 인덱싱의 스케일(1 또는 4)로 정한다.

정답 예: `<<answer>>`
""", len=length, sum=total, vals=vals, answer=answer),
        hints=["`(,%rdx,4)`의 스케일 4는 원소 크기다. 표를 어떤 단위로 봐야 하는가?",
               "`x/16dw <표 주소>`로 값을 읽는다. 길이와 목표 합도 상수로 보인다.",
               "합이 맞는 인덱스 조합을 고르고, 하위 4비트로 글자를 만든다."])


def s3_cycle(r):
    order = list(range(15))
    r.shuffle(order)
    cycle = order + [15]                    # one 16-cycle ending at 15
    nxt = [0] * 16
    for i in range(16):
        nxt[cycle[i]] = cycle[(i + 1) % 16]
    steps = r.randint(6, 10)
    start = cycle[15 - steps]
    a, count = start, 0
    while a != 15:
        a = nxt[a]
        count += 1
    assert count == steps

    def check(line):
        ret, v = judge.sscanf(line, "%d")
        if ret != 1:
            return False
        x, c = v[0] & 0xF, 0
        while x != 15:
            x = nxt[x]
            c += 1
        return c == steps

    return Phase(
        "s3", "cycle", "drills/d6/s3.c",
        [("D6_S3_NEXT", nxt), ("D6_S3_STEPS", steps)],
        answer=str(start), check=check, title="인덱스를 따라가는 배열",
        answers="하위 4비트가 %d인 수면 정답 (예: `%d`)." % (start, start),
        walkthrough=fill("""\
`a = a & 0xf`로 시작 칸을 정하고, **15에 도착할 때까지** `a = next[a]`를 반복하며 횟수를 센다.

```
and    $0xf,%eax
cmp    $0xf,%eax
je     <끝>
loop:
cltq
mov    0x...(,%rax,4),%eax     # a = d6_next[a]
add    $0x1,%edx               # count++
cmp    $0xf,%eax
jne    loop
cmp    $0x<<shex>>,%edx              # 횟수 == <<steps>> ?
```

표(`x/16dw`): <<nxt>>

**거꾸로** 푸는 것이 빠르다. 15에 도착하기 직전 칸은 `next[j] == 15`인 j, 그 전은
`next[k] == j`인 k … 이렇게 <<steps>>번 거슬러 올라가면 시작 칸 <<start>>이 나온다.

**과제에서는**: 예전 학기 phase 5의 "배열 순환" 변형이 이 모양이다. 거기서는 횟수가 15로 정해져 있고,
지나간 값의 합을 두 번째 수로 하나 더 입력한다. 반복문의 종료 조건부터 보고, 목표에서 거꾸로 추적하라.
""", steps=steps, shex="%x" % steps, nxt=nxt, start=start),
        hints=["반복문은 언제 끝나는가? 무엇을 세는가?",
               "`x/16dw`로 표를 보고, 15로 가는 칸부터 거꾸로 추적하라.",
               "정해진 횟수만큼 거슬러 올라간 칸이 시작점이다."])


STAGES = [
    ("s1", {"charmap": s1_charmap}),
    ("s2", {"sum": s2_sum}),
    ("s3", {"cycle": s3_cycle}),
]
