"""D8 - binary trees: search depth, fun7 path encoding, path sums."""

from .. import judge
from ..cmu import CHILDREN, IN_ORDER, fun7
from ..core import Phase, fill

ID = "d8"
TITLE = "이진 트리"
TITLE_EN = "binary trees"

NAMES15 = ["n1", "n21", "n22", "n31", "n32", "n33", "n34",
           "n41", "n42", "n43", "n44", "n45", "n46", "n47", "n48"]
IN_ORDER7 = ["b31", "b21", "b32", "b1", "b33", "b22", "b34"]
CHILD7 = {"b1": ("b21", "b22"), "b21": ("b31", "b32"), "b22": ("b33", "b34")}


def _tree15(r, lo=1, hi=1000):
    values = sorted(r.sample(range(lo, hi + 1), 15))
    return dict(zip(IN_ORDER, values))


def s1_depth(r):
    values = sorted(r.sample(range(1, 1000), 7))
    tree = dict(zip(IN_ORDER7, values))
    depth = r.randint(1, 2)

    def find(node, v, d):
        if node is None:
            return -1
        if v == tree[node]:
            return d
        left, right = CHILD7.get(node, (None, None))
        return find(left if v < tree[node] else right, v, d + 1)

    xs = sorted(v for v in values if find("b1", v, 0) == depth)
    macros = [("D8_" + n.upper(), tree[n])
              for n in ["b1", "b21", "b22", "b31", "b32", "b33", "b34"]]
    macros.append(("D8_S1_DEPTH", depth))

    def check(line):
        ret, v = judge.sscanf(line, "%d")
        return ret == 1 and find("b1", v[0], 0) == depth

    return Phase(
        "s1", "depth", "drills/d8/s1.c", macros,
        answer=str(r.choice(xs)), check=check, title="트리에서 값의 깊이",
        answers="깊이 %d인 노드 값 모두 정답: %s." % (depth, ", ".join(map(str, xs))),
        walkthrough=fill("""\
노드는 24바이트다: `int value`(+0), 여백 4바이트, `left`(+8), `right`(+16).

```
(gdb) x/6wx &b1        # value, (여백), left 하위, left 상위, right 하위, right 상위
```

반복문이 루트 `b1`에서 출발해 값을 찾을 때까지 내려가며 깊이 d를 하나씩 늘린다.

```
mov    (%rax),%edx          # t->value
cmp    %ecx,%edx            # 입력과 비교
je     <찾음>
jle    ...
mov    0x8(%rax),%rax       # 작으면 t = t->left
...
mov    0x10(%rax),%rax      # 크면 t = t->right
add    $0x1,%esi            # d++
test   %rax,%rax            # NULL이면 못 찾음
```

`b1`부터 `x/6wx`로 따라가며 트리를 종이에 그리면, 깊이(루트 = 0) <<depth>>인 노드가 보인다.

트리 (중위 순서): <<inorder>>

**과제에서는**: 숨은 단계의 트리가 이 구조(24바이트 노드, left +8, right +16)다. 과제에서는 내려가는 일을
재귀 함수(`fun7`)가 한다 — 그 반환값을 읽는 법은 다음 단계에서 연습한다.
""", depth=depth,
            inorder=", ".join("%s=%d" % (n, tree[n]) for n in IN_ORDER7)),
        hints=["노드 구조체의 크기와 left/right 오프셋을 먼저 알아내라 (`mov 0x8(%rdi)`, `mov 0x10(%rdi)`).",
               "`x/6wx &b1`부터 자식 포인터를 따라가며 트리를 그려라.",
               "루트의 깊이는 0이다. 목표 깊이의 노드 값 중 아무거나."])


def s2_fun7(r):
    tree = _tree15(r)
    target = r.randint(1, 7)
    xs = sorted(v for v in tree.values() if fun7(tree, "n1", v) == target)
    macros = [("D8_" + n.upper(), tree[n]) for n in NAMES15]
    macros.append(("D8_S2_TARGET", target))

    def check(line):
        return fun7(tree, "n1", judge.atoi_int(line)) == target

    bits = bin(target)[2:][::-1]
    return Phase(
        "s2", "fun7", "drills/d8/s2.c", macros,
        answer=str(r.choice(xs)), check=check, title="fun7 경로 인코딩",
        answers="`fun7`이 %d를 돌려주는 값: %s." % (target, ", ".join(map(str, xs))),
        walkthrough=fill("""\
입력은 `strtol`로 읽는다(`sscanf`가 아님 — 앞에 공백, 뒤에 글자가 붙어도 숫자 부분만 쓴다).

`fun7(node, x)`:
- `node == NULL` → -1
- `x < value` → `2 * fun7(left, x)`     (`add %eax,%eax`)
- `x == value` → 0
- `x > value` → `2 * fun7(right, x) + 1` (`lea 0x1(%rax,%rax,1),%eax`)

돌아오면서 2를 곱하므로, 반환값의 **가장 아래 비트가 루트에서의 첫 걸음**이다.
목표 <<target>> = 2진수로 아래 비트부터 <<bits>> (1 = 오른쪽, 0 = 왼쪽).
경로 끝 노드에서 왼쪽으로만 더 내려간 노드도 같은 값을 돌려주므로 정답이 여러 개일 수 있다.

**과제에서는**: 숨은 단계가 이 `fun7`을 쓴다. 과제에서는 입력이 1~1001인지 보는 범위 검사
(`lea -0x1(%rax),%eax` / `cmp $0x3e8,%eax` / `jbe`)가 앞에 하나 더 붙는다.
남은 일은 `phase_defused`에서 진입 방법을 찾는 것뿐이다(D9).

정답: <<xs>>
""", target=target, bits=bits, xs=", ".join(map(str, xs))),
        hints=["`fun7`의 세 갈래가 반환값을 어떻게 만드는지 적어라.",
               "반환값을 2진수로 쓰고 아래 비트부터 읽으면 경로다.",
               "1=오른쪽, 0=왼쪽으로 루트부터 내려간 노드의 값."])


def s3_pathsum(r):
    tree = _tree15(r, 1, 500)
    names = ["m" + n[1:] for n in NAMES15]
    mtree = {"m" + k[1:]: v for k, v in tree.items()}
    leaf = r.choice([n for n in IN_ORDER if n.startswith("n4")])

    def path_sum(v):
        node, total = "n1", 0
        while node is not None:
            nv = tree[node]
            total += nv
            if v == nv:
                return total
            left, right = CHILDREN.get(node, (None, None))
            node = left if v < nv else right
        return total

    target = path_sum(tree[leaf])
    macros = [("D8_" + n.upper(), mtree[n]) for n in names]
    macros.append(("D8_S3_T", target))

    def check(line):
        ret, v = judge.sscanf(line, "%d")
        return ret == 1 and judge.to_int32(path_sum(v[0])) == target

    return Phase(
        "s3", "pathsum", "drills/d8/s3.c", macros,
        answer=str(tree[leaf]), check=check, title="경로의 값 합",
        answers="탐색 경로의 값 합이 %d이 되는 수. 예: `%d` (잎 노드 m%s). "
                "그 잎으로 내려가는 트리에 없는 값들도 같은 합을 낸다."
                % (target, tree[leaf], leaf[1:]),
        walkthrough=fill("""\
반복문이 `m1`에서 출발해 x를 찾아 내려가며, 지나는 노드의 값을 모두 더한다.

```
mov    (%rax),%edx          # t->value
add    %edx,%ecx            # sum += t->value
cmp    %esi,%edx
je     <끝>                 # 찾으면 멈춤
mov    0x8(%rax),%rax       # 작으면 왼쪽
...
mov    0x10(%rax),%rax      # 크면 오른쪽
test   %rax,%rax
jne    <반복>
cmp    $0x...,%ecx          # 합 == 목표 ?
```

트리를 `m1`부터 `x/6wx`로 덤프해 그린 뒤, 합이 <<target>>이 되는 경로를 찾는다.
x가 트리에 없으면 NULL에 닿을 때까지 내려가므로, 마지막 노드까지의 합이 된다.
그래서 **그 잎 노드로 내려가는 모든 값**이 같은 합을 낸다.

**과제에서는**: 숨은 단계를 풀 때 하는 일이 바로 이것 — 메모리의 트리를 덤프해 그리고, 원하는 결과가
나오는 경로를 찾아 그 끝 노드의 값을 넣는 것이다.

정답 예: <<ans>>
""", target=target, ans=tree[leaf]),
        hints=["반복문이 한 바퀴마다 무엇을 더하고, 언제 멈추는가?",
               "`m1`부터 트리를 덤프해 그리고, 경로별 합을 적어라.",
               "합이 목표인 경로의 끝 노드 값을 넣는다."])


STAGES = [
    ("s1", {"depth": s1_depth}),
    ("s2", {"fun7": s2_fun7}),
    ("s3", {"pathsum": s3_pathsum}),
]
