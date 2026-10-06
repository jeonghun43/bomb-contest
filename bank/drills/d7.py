"""D7 - structs and linked lists: node layout, pointer chasing, ordering."""

from .. import judge
from ..core import Phase, Raw, fill

ID = "d7"
TITLE = "구조체와 연결 리스트"
TITLE_EN = "structs and linked lists"


def _pick_check(values, transform, descending):
    """Each number picks node transform(x); picked values must strictly
    increase (or decrease). Mirrors the C loop: range check, walk, compare."""
    def check(line):
        a = judge.read_six_numbers(line)
        if a is None:
            return False
        prev = 0x7FFFFFFF if descending else 0
        for x in a:
            if x < 1 or x > 6:
                return False
            v = values[transform(x) - 1]
            if (v >= prev) if descending else (v <= prev):
                return False
            prev = v
        return True
    return check


def s1_walk(r):
    values = r.sample(range(100, 1000), 6)
    order = [1] + r.sample(range(2, 7), 5)        # chain from item1
    nxt = {}
    for i in range(6):
        nxt[order[i]] = order[i + 1] if i < 5 else None
    steps = r.randint(2, 5)
    target = order[steps]
    want = values[target - 1]
    macros = [("D7_S1_V%d" % j, values[j - 1]) for j in range(1, 7)]
    macros += [("D7_S1_N%d" % j, Raw("&item%d" % nxt[j] if nxt[j] else "NULL"))
               for j in range(1, 7)]
    macros.append(("D7_S1_STEPS", steps))
    chain = " → ".join("item%d(%d)" % (j, values[j - 1]) for j in order)

    def check(line):
        ret, v = judge.sscanf(line, "%d")
        return ret == 1 and v[0] == want

    return Phase(
        "s1", "walk", "drills/d7/s1.c", macros,
        answer=str(want), check=check, title="노드 따라가기",
        answers="`%d` 하나뿐이다 (item1에서 %d번 이동한 노드)." % (want, steps),
        walkthrough=fill("""\
노드 구조체는 16바이트다.

```
struct item { int value;   /* +0 */
              int index;   /* +4 */
              struct item *next; /* +8 */ };
```

루프는 `mov 0x8(%rax),%rax`(p = p->next)를 <<steps>>번 실행하고, 마지막에
`cmp (%rax),%edx`로 그 노드의 value(+0)를 입력과 비교한다.

노드는 `item1`~`item6`이라는 전역 심볼이다. 메모리에서는 이어져 있지만 **연결 순서는 다르다**.

```
(gdb) x/24wx &item1          # 6개 × 4워드: value, index, next(하위), next(상위)
(gdb) p item1                # 디버그 정보가 없으므로 이건 안 된다 → x/4wx 를 쓴다
```

next 필드(+8)의 주소가 어느 item인지 맞춰 가며 따라간다.

연결 순서: <<chain>> → <<steps>>번 이동하면 value = **<<want>>**

**과제에서는**: CMU phase 6의 `node1`~`node6`, secret의 트리 노드가 모두 이런 전역 구조체다.
`x/Nwx`로 덤프하고 오프셋별로 해석하는 연습이 핵심이다.
""", steps=steps, chain=chain, want=want),
        hints=["루프 안의 `mov 0x8(%rax),%rax`는 구조체의 어느 필드를 읽는가?",
               "`x/24wx &item1`로 노드 여섯 개를 한 번에 본다. +8 위치가 next 포인터다.",
               "item1에서 next를 정해진 횟수만큼 따라간 노드의 첫 필드(value)가 답이다."])


def _distinct_order(r, key):
    while True:
        values = r.sample(range(100, 1000), 6)
        xs = key(values)
        if xs not in ([1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]):
            return values, xs


def s2_ascending(r):
    values, xs = _distinct_order(
        r, lambda v: sorted(range(1, 7), key=lambda j: v[j - 1]))
    answer = " ".join(str(x) for x in xs)
    table = ", ".join("elem%d=%d" % (j, values[j - 1]) for j in range(1, 7))
    return Phase(
        "s2", "ascending", "drills/d7/s2.c",
        [("D7_S2_V%d" % j, values[j - 1]) for j in range(1, 7)],
        answer=answer, check=_pick_check(values, lambda x: x, False),
        title="번호로 고른 노드의 오름차순",
        answers="`%s` 하나뿐이다 (%s)." % (answer, table),
        walkthrough=fill("""\
여섯 수를 읽고, 수마다 이렇게 한다.

```
mov    (%r12),%eax           # a[i]
lea    -0x1(%rax),%edx
cmp    $0x5,%edx
ja     <폭발>                # 1~6인가
mov    $0x...,%edx           # p = &elem1
...
mov    0x8(%rdx),%rdx        # p = p->next  (a[i]-1번)
...
mov    (%rdx),%eax           # p->value
cmp    %ebx,%eax             # 앞에서 고른 값(prev)과 비교
jle    <폭발>                # 커지지 않으면 폭발
mov    %eax,%ebx             # prev = p->value
```

즉 수 k는 "`elem1`에서 k번째 노드"를 고르고, 고른 노드의 값이 **계속 커져야** 한다.
값이 같으면 실패하니 같은 번호를 두 번 쓸 수도 없다.

노드 값(`x/24wx &elem1`): <<table>>
값이 작은 순서대로 노드 번호를 나열하면 정답: `<<answer>>`

**과제에서는**: phase 6은 같은 "번호로 노드 고르기"에 덩어리가 더 붙는다 — 1~6 범위·**중복 검사 이중 루프**,
고른 노드를 스택의 포인터 배열에 모았다가 **next를 다시 이어 붙이는 재연결**, 그리고 이어진 리스트를 따라가는
정렬 검사. 재연결은 정답에 영향을 주지 않는다. 정답을 정하는 것은 "어떤 번호가 어떤 노드인가"와 "비교 방향"뿐이다.
""", table=table, answer=answer),
        hints=["각 수로 무엇을 하는가? `mov 0x8(%rdx),%rdx`를 몇 번 반복하는가?",
               "노드 값을 `x/24wx &elem1`로 읽어라. 고른 값끼리 어떤 관계여야 하는가(`jle`)?",
               "값이 작은 노드부터 그 번호를 나열한다."])


def s3_core(r):
    values, xs = _distinct_order(
        r, lambda v: [7 - j for j in sorted(range(1, 7), key=lambda j: -v[j - 1])])
    answer = " ".join(str(x) for x in xs)
    table = ", ".join("node%d=%d" % (j, values[j - 1]) for j in range(1, 7))
    return Phase(
        "s3", "core", "drills/d7/s3.c",
        [("D7_S3_V%d" % j, values[j - 1]) for j in range(1, 7)],
        answer=answer, check=_pick_check(values, lambda x: 7 - x, True),
        title="phase 6의 핵심: 7-x와 내림차순",
        answers="`%s` 하나뿐이다 (%s)." % (answer, table),
        walkthrough=fill("""\
2단계와 같은 모양에 두 가지가 바뀌었다.

- **7-x 변환**: 노드를 따라가는 횟수가 `a[i]-1`이 아니라 `7-a[i]-1`이다.
  `mov $0x7,%eax` / `sub (%r12),%eax` 같은 계산이 보인다. 그래서 입력 x는 노드 `7-x`를 고른다.
- **내림차순**: 비교가 `jge <폭발>`로 바뀌었다. 고른 값이 계속 **작아져야** 한다.

풀이 순서: 값이 큰 순서로 노드 번호 j를 나열 → 각각 `7-j`로 바꾼다.

노드: <<table>> → 정답 `<<answer>>`

**과제에서는**: 이것이 phase 6의 정답을 정하는 논리 전부다. 과제의 phase 6은 여기에
범위·중복 검사 이중 루프, 7-x를 배열에 미리 써 두는 별도 루프, 포인터 배열, 재연결이 붙어
명령어가 90개쯤 된다. 덩어리별로 끊어 읽고, 마지막 비교 방향(`jge`/`jle`)과 7-x 유무만 확인하면
답은 이 단계와 똑같이 구한다. 전체 모양은 연습 폭탄(`~/practice`)에서 그대로 볼 수 있다.
""", table=table, answer=answer),
        hints=["2단계와 비교해 무엇이 달라졌는지 찾아라: 따라가는 횟수, 비교 방향.",
               "`mov $0x7` 다음의 `sub`는 각 수를 무엇으로 바꾸는가? 비교는 `jge`인가 `jle`인가?",
               "값이 큰 순서의 노드 번호 j를 구해 각각 7-j로 바꾼다."])


STAGES = [
    ("s1", {"walk": s1_walk}),
    ("s2", {"ascending": s2_ascending}),
    ("s3", {"core": s3_core}),
]


