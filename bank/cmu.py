"""
cmu.py - CMU-structure bombs (Lv.2): the original's six phases and secret
phase, same code shape, constants drawn per seed.

First-pass variant families are the ones measured in the self-study bomb
(specs/003-practice-bank/research.md section 3). Families seen only in other
semesters' bombs are added once their existence is confirmed (T080/T081).

Constants are drawn only where they leave the compiled code shape unchanged
(see the notes in each C template), so every seed still matches the original
instruction for instruction under `asmdiff --mask-imm`.
"""

from . import judge
from .core import BankError, Bomb, Phase, rng

KIND = "cmu"

# --------------------------------------------------------------------------
# phase 1 - string compare
# --------------------------------------------------------------------------

SENTENCES = [
    "Every program starts as a sequence of bits in memory.",
    "The stack grows down and the heap grows up.",
    "A pointer is just an address with a type attached.",
    "Registers are fast, memory is slow, and disks are slower.",
    "Callee-saved registers survive a call, caller-saved ones may not.",
    "Little-endian machines store the low byte first.",
    "Two's complement makes subtraction look like addition.",
    "The return address lives on the stack just above the frame.",
    "Optimizing compilers turn division into multiplication.",
    "Every jump table is an array of addresses in read-only memory.",
    "A segmentation fault is the kernel saying no.",
    "gdb can stop a program at any instruction you choose.",
    "Six phases stand between you and a quiet terminal.",
    "Read the assembly slowly and the answer reads itself.",
    "The first argument arrives in rdi, the second in rsi.",
    "Overflow in signed arithmetic is undefined in C.",
    "Caches reward programs that touch nearby memory.",
    "A linked list is a scavenger hunt through the heap.",
    "Recursion is a function that trusts itself.",
    "The leave instruction undoes what the prologue did.",
    "Objdump shows you the truth, one instruction at a time.",
    "Floating point numbers are approximations with exponents.",
    "Each process believes it owns all of memory.",
    "System calls are how a program asks the kernel for help.",
    "A canary on the stack warns of buffer overflows.",
    "Signed and unsigned comparisons use different jumps.",
    "The condition codes remember what the last arithmetic did.",
    "Every byte has an address, and every address has a byte.",
    "Breakpoints let you pause time inside a running program.",
    "Bits are just bits until you decide what they mean.",
    "Loops in assembly are just jumps that go backwards.",
    "The heap is managed, the stack is automatic.",
    "When in doubt, examine the memory and look again.",
    "A struct is a block of memory with named offsets.",
    "Leaf functions do not need to save the return address.",
    "Arithmetic shifts keep the sign, logical shifts do not.",
    "The linker resolves every symbol before main ever runs.",
    "Virtual memory turns a small machine into a large one.",
    "Assembly code never lies about what the machine does.",
    "Patience and a debugger defuse more bombs than luck.",
]

P1_TITLE = "문자열 비교"


def gen_p1(r):
    s = r.choice(SENTENCES)
    return Phase(
        "p1", "strings", "cmu/p1_strings.c",
        [("P1_STRING", s)],
        answer=s,
        check=lambda line, s=s: not judge.strings_not_equal(line, s),
        title=P1_TITLE,
        answers="정답은 한 줄 전체가 `%s`와 정확히 같을 때 하나뿐이다. "
                "앞뒤 공백도 달라서는 안 된다." % s,
        walkthrough="""\
`phase_1`은 입력 줄(`%%rdi`)과 고정 문자열의 주소(`%%esi`에 들어가는 즉시값)를
`strings_not_equal`에 넘기고, 반환값이 0이 아니면 `explode_bomb`을 부른다.

```
mov    $0x...,%%esi          # 비교할 문자열의 주소
callq  <strings_not_equal>
test   %%eax,%%eax
je     ...                  # 같으면 통과
callq  <explode_bomb>
```

`%%esi`에 들어가는 주소를 gdb에서 `x/s 0x...`로 보면 정답 문장이 그대로 나온다.
`strings_not_equal`은 길이부터 비교하므로 끝에 공백 하나만 더 붙어도 폭발한다.

이 폭탄의 문장: `%s`
""" % s,
        hints=[
            "`phase_1`이 부르는 함수의 이름을 보라. 두 번째 인자는 무엇인가?",
            "`callq <strings_not_equal>` 바로 앞에서 `%esi`에 들어가는 값은 주소다.",
            "gdb에서 `x/s <그 주소>`. 출력된 문장을 그대로 답으로 쓴다.",
        ])


# --------------------------------------------------------------------------
# phase 2 - doubling sequence
# --------------------------------------------------------------------------

def gen_p2(r):
    first = r.randint(1, 9)
    seq = [first << k for k in range(6)]
    answer = " ".join(str(v) for v in seq)

    def check(line, first=first):
        a = judge.read_six_numbers(line)
        if a is None or a[0] != first:
            return False
        return all(a[i] == judge.to_int32(a[i - 1] * 2) for i in range(1, 6))

    return Phase(
        "p2", "double", "cmu/p2_double.c",
        [("P2_FIRST", first)],
        answer=answer, check=check, title="반복문과 배열",
        answers="정답은 `%s` 하나뿐이다. 수 사이 공백 개수는 상관없고, "
                "여섯 번째 수 뒤의 내용은 무시된다." % answer,
        walkthrough="""\
`read_six_numbers`가 정수 여섯 개를 스택의 배열(`%%rsp`부터 4바이트 간격)에 읽는다.
첫 번째 값은 `cmpl $%d,(%%rsp)`로 바로 비교된다.

이어지는 루프는 포인터 두 개로 돈다. `%%rbx`가 현재 원소, `%%rbp`가 배열의 끝이다.

```
mov    -0x4(%%rbx),%%eax      # 앞 원소
add    %%eax,%%eax            # 두 배
cmp    %%eax,(%%rbx)          # 현재 원소와 비교
...
add    $0x4,%%rbx             # 다음 원소
cmp    %%rbp,%%rbx
```

즉 각 원소는 바로 앞 원소의 두 배여야 한다. 첫 값이 %d이므로 정답은 `%s`.
""" % (first, first, answer),
        hints=[
            "입력은 정수 여섯 개다. 첫 번째 값은 상수와 바로 비교된다.",
            "루프 안에서 앞 원소(`-0x4(%rbx)`)로 무엇을 계산해 현재 원소와 비교하는가?",
            "`add %eax,%eax`는 두 배다. 첫 값부터 차례로 두 배씩.",
        ])


# --------------------------------------------------------------------------
# phase 3 - jump table
# --------------------------------------------------------------------------

def gen_p3(r):
    vals = r.sample(range(100, 1000), 8)
    k = r.randrange(8)
    pairs = ", ".join("`%d %d`" % (i, v) for i, v in enumerate(vals))

    def check(line, vals=vals):
        ret, v = judge.sscanf(line, "%d %d")
        if ret < 2:
            return False
        index, val = v[0], v[1]
        return 0 <= index <= 7 and val == vals[index]

    return Phase(
        "p3", "switch_dd", "cmu/p3_switch_dd.c",
        [("P3_V%d" % i, v) for i, v in enumerate(vals)],
        answer="%d %d" % (k, vals[k]), check=check, title="switch와 점프 테이블",
        answers="정답은 여덟 개다: %s." % pairs,
        walkthrough="""\
`sscanf(input, "%%d %%d", ...)`로 두 수를 읽고 개수가 2보다 작으면 폭발한다.
첫 번째 수는 `cmpl $0x7,0x8(%%rsp)` 뒤의 `ja`(부호 없는 비교)로 0~7인지 확인한다.
음수도 부호 없는 수로 보면 아주 크므로 여기서 걸러진다.

그다음이 **점프 테이블**이다.

```
mov    0x8(%%rsp),%%eax
jmpq   *0x...(,%%rax,8)       # 테이블[첫 번째 수]로 점프
```

테이블은 `.rodata`에 있는 8바이트 주소 8개다. gdb에서 `x/8gx 0x...`로 보면
각 case가 시작하는 주소가 나온다. 각 case는 `mov $값,%%eax` 후 공통 지점으로 가서
두 번째 수(`0xc(%%rsp)`)와 비교한다.

이 폭탄의 case 값: %s. 어느 쌍을 넣어도 해제된다.
""" % pairs,
        hints=[
            "첫 번째 수의 범위를 검사하는 `cmp`와 `ja`를 찾아라. 왜 `jg`가 아니라 `ja`일까?",
            "`jmpq *0x...(,%rax,8)`는 주소 표에서 하나를 골라 점프한다. 그 표를 `x/8gx`로 보라.",
            "한 case로 따라가 `%eax`에 들어가는 상수를 읽는다. 첫 번째 수와 그 상수가 답이다.",
        ])


# --------------------------------------------------------------------------
# phase 4 - recursive binary search
# --------------------------------------------------------------------------

def _cdiv(a, b):
    """C integer division (truncates toward zero)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def func4(val, low, high):
    mid = low + _cdiv(high - low, 2)
    if mid > val:
        return func4(val, low, mid - 1) * 2
    if mid < val:
        return func4(val, mid + 1, high) * 2 + 1
    return 0


def gen_p4(r):
    hi = r.randint(10, 30)
    second = r.randint(0, 99)
    xs = [x for x in range(hi + 1) if func4(x, 0, hi) == 0]
    x = r.choice(xs)
    listed = ", ".join("`%d %d`" % (v, second) for v in xs)

    def check(line, hi=hi, second=second):
        ret, v = judge.sscanf(line, "%d %d")
        if ret != 2:
            return False
        if v[0] < 0 or v[0] > hi:
            return False
        return func4(v[0], 0, hi) == 0 and v[1] == second

    return Phase(
        "p4", "func4_bsearch", "cmu/p4_func4_bsearch.c",
        [("P4_HI", hi), ("P4_SECOND", second)],
        answer="%d %d" % (x, second), check=check, title="재귀 (func4)",
        answers="정답은 %d개다: %s. `func4(x, 0, %d)`가 0을 돌려주는 x는 "
                "탐색 경로가 왼쪽으로만 내려가는 값들이다." % (len(xs), listed, hi),
        walkthrough="""\
`sscanf(input, "%%d %%d", ...)`로 두 수를 읽는다. 개수가 2가 아니거나 첫 번째 수가
0~%d 밖이면(`cmpl $0x%x,0x8(%%rsp)` + `jbe`) 폭발한다.

그다음 `func4(x, 0, %d)`를 부른다. 인자는 `%%edi`=x, `%%esi`=0, `%%edx`=%d.
`func4`는 재귀 이진 탐색이다.

```
mid = low + (high - low) / 2      # shr $0x1f / add / sar 로 계산 (음수 나눗셈 보정)
if (mid > x)  return 2 * func4(x, low, mid - 1);
if (mid < x)  return 2 * func4(x, mid + 1, high) + 1;
return 0;
```

반환값이 0이어야 하므로(`test %%eax,%%eax`) 오른쪽으로 한 번도 가지 않는 x만 된다.
두 번째 수는 `cmpl $0x%x,0xc(%%rsp)`로 %d과 비교된다.

이 폭탄의 정답: %s.
""" % (hi, hi, hi, hi, second, second, listed),
        hints=[
            "첫 번째 수의 범위와, `func4`에 넘기는 세 인자(`%edi`, `%esi`, `%edx`)를 확인하라.",
            "`func4`는 자기 자신을 부른다. 반환값이 `2*f`, `2*f+1`, `0` 중 무엇인지 경우를 나눠 보라.",
            "반환값 0 = 오른쪽으로 한 번도 가지 않음. mid를 직접 계산하며 내려가 보라. 두 번째 수는 상수 비교다.",
        ])


# --------------------------------------------------------------------------
# phase 5 - character table
# --------------------------------------------------------------------------

def _nibble_char(i):
    """A typeable character whose low four bits are i."""
    return "p" if i == 0 else chr(0x60 + i)


def gen_p5(r):
    letters = r.sample("abcdefghijklmnopqrstuvwxyz", 16)
    target = "".join(r.choice(letters) for _ in range(6))
    answer = "".join(_nibble_char(letters.index(c)) for c in target)
    table = "".join(letters)

    def check(line, table=table, target=target):
        if judge.string_length(line) != 6:
            return False
        return "".join(table[ord(c) & 0xF] for c in line) == target

    idx = ", ".join("`%s`→%d" % (c, table.index(c)) for c in target)
    return Phase(
        "p5", "charmap", "cmu/p5_charmap.c",
        [("P5_ARRAY", list(letters)), ("P5_TARGET", target)],
        answer=answer, check=check, canary=True, title="문자 처리와 표 인덱싱",
        answers="하위 4비트가 각각 %s인 여섯 글자면 모두 정답이다. 예: `%s`."
                % (", ".join(str(table.index(c)) for c in target), answer),
        walkthrough="""\
먼저 `string_length(input) == 6`인지 본다. 함수 앞뒤의 `mov %%fs:0x28,%%rax` /
`xor %%fs:0x28,%%rax`는 **스택 카나리**다. 스택에 문자 배열이 있어서 컴파일러가 넣었고,
문제 풀이와는 상관없다.

루프는 글자마다 이렇게 한다.

```
movzbl (%%rbx,%%rax,1),%%ecx   # input[i]
...
and    $0xf,%%edx             # 하위 4비트
movzbl 0x...(%%rdx),%%edx     # array[하위 4비트]
mov    %%dl,0x10(%%rsp,%%rax,1) # 스택의 버퍼에 저장
```

`0x...`는 16바이트 표(심볼 `array.NNNN`)다. `x/s 0x...` 또는 `x/16c 0x...`로 본다.
만들어진 6글자를 `strings_not_equal`로 목표 문자열과 비교한다(`x/s`로 확인).

이 폭탄의 표: `%s`, 목표: `%s`.
목표의 각 글자가 표의 몇 번째인지 찾으면 %s. 하위 4비트가 그 값인 글자를 고르면 된다
(예: 1은 `a`, 2는 `b`, …, 15는 `o`, 0은 `p`). 정답 예: `%s`.
""" % (table, target, idx, answer),
        hints=[
            "입력 길이는 몇이어야 하는가? 그리고 루프 안의 `and $0xf`는 무엇을 남기는가?",
            "`movzbl 0x...(%rdx),%edx`의 `0x...`가 표의 주소다. 표와, 마지막에 비교하는 목표 문자열을 둘 다 `x/s`로 보라.",
            "목표 글자마다 표에서의 위치(0~15)를 찾고, 하위 4비트가 그 위치인 글자를 고른다. `man ascii`가 도움이 된다.",
        ])


# --------------------------------------------------------------------------
# phase 6 - linked list
# --------------------------------------------------------------------------

def gen_p6(r):
    while True:
        values = r.sample(range(100, 1000), 6)
        order = sorted(range(1, 7), key=lambda j: -values[j - 1])
        xs = [7 - j for j in order]
        if xs not in ([1, 2, 3, 4, 5, 6], [6, 5, 4, 3, 2, 1]):
            break
    answer = " ".join(str(x) for x in xs)

    def check(line, values=values):
        a = judge.read_six_numbers(line)
        if a is None:
            return False
        for i in range(6):
            if a[i] < 1 or a[i] > 6:
                return False
            if a[i] in a[i + 1:]:
                return False
        vs = [values[7 - x - 1] for x in a]
        return all(vs[i] >= vs[i + 1] for i in range(5))

    table = ", ".join("node%d=%d" % (j, values[j - 1]) for j in range(1, 7))
    return Phase(
        "p6", "list", "cmu/p6_list.c",
        [("P6_V%d" % j, values[j - 1]) for j in range(1, 7)],
        answer=answer, check=check, title="구조체와 연결 리스트",
        answers="정답은 `%s` 하나뿐이다 (%s)." % (answer, table),
        walkthrough="""\
가장 긴 phase다. 덩어리별로 나눠 읽는다.

1. `read_six_numbers` → 스택의 배열.
2. **이중 루프**: 각 수가 1~6인지(`sub $0x1` 후 `cmp $0x5` + `jbe`), 그리고 뒤의 수들과
   겹치지 않는지 확인한다. 즉 입력은 1~6의 순열이다.
3. **7-x 변환**: `mov $0x7,%%ecx` / `sub (%%rax),%%edx` 루프가 배열의 각 수를 `7-x`로 바꾼다.
4. **노드 고르기**: `mov $0x...,%%edx`의 `0x...`가 `node1`이다. 각 수 k에 대해
   `mov 0x8(%%rdx),%%rdx`(next)를 k-1번 따라가 k번째 노드의 주소를 스택의 포인터 배열
   (`0x20(%%rsp)`부터 8바이트 간격)에 저장한다.
5. **재연결**: 포인터 배열 순서대로 `next`를 다시 이어 붙인다.
6. **검사**: 이어진 리스트를 따라가며 `mov (%%rax),%%eax` / `cmp %%eax,(%%rbx)` / `jge` —
   각 노드 값이 다음 노드 값보다 크거나 같아야 한다. 즉 **내림차순**.

노드는 16바이트(`int value; int index; struct node *next;`)다.
gdb에서 `x/24wx 0x...`(node1 주소)로 여섯 노드를 한 번에 볼 수 있다.

이 폭탄의 노드: %s.
값이 큰 순서의 노드 번호를 구하고, 각 번호 j를 `7-j`로 바꾸면 정답 `%s`.
""" % (table, answer),
        hints=[
            "첫 이중 루프는 입력에 어떤 조건을 거는가? 그다음 `mov $0x7,...` 루프는 각 수를 무엇으로 바꾸는가?",
            "`mov $0x...,%edx`의 주소를 `x/24wx`로 보라. 16바이트짜리 구조체 여섯 개가 next로 이어져 있다.",
            "마지막 검사는 리스트가 내림차순인지 본다. 값이 큰 순서의 노드 번호 j를 구해 각각 7-j로 바꾼다.",
        ])


# --------------------------------------------------------------------------
# secret phase - binary search tree
# --------------------------------------------------------------------------

# In-order positions of the complete 15-node tree (n1 root, n2x level 2 ...).
IN_ORDER = ["n41", "n31", "n42", "n21", "n43", "n32", "n44", "n1",
            "n45", "n33", "n46", "n22", "n47", "n34", "n48"]
CHILDREN = {"n1": ("n21", "n22"), "n21": ("n31", "n32"),
            "n22": ("n33", "n34"), "n31": ("n41", "n42"),
            "n32": ("n43", "n44"), "n33": ("n45", "n46"),
            "n34": ("n47", "n48")}
SECRET_WORDS = ["lodestone", "quicksilver", "cinnabar", "obsidian",
                "meridian", "alabaster", "wolfram", "peregrine", "vermilion",
                "tantalum", "basilisk", "chimera", "nightjar", "kestrel",
                "foxglove", "nightshade", "halcyon", "zephyr"]


def fun7(tree, node, val):
    if node is None:
        return -1
    v = tree[node]
    left, right = CHILDREN.get(node, (None, None))
    if val < v:
        return fun7(tree, left, val) * 2
    if val == v:
        return 0
    return fun7(tree, right, val) * 2 + 1


def gen_secret(r):
    values = sorted(r.sample(range(1, 1001), 15))
    tree = dict(zip(IN_ORDER, values))
    target = r.randint(1, 7)
    xs = sorted(v for v in values if fun7(tree, "n1", v) == target)
    x = r.choice(xs)

    def check(line, tree=tree, target=target):
        t = judge.atoi_int(line)
        if t < 1 or t > 1001:
            return False
        return fun7(tree, "n1", t) == target

    names = ["n1", "n21", "n22", "n31", "n32", "n33", "n34",
             "n41", "n42", "n43", "n44", "n45", "n46", "n47", "n48"]
    macros = [("T_" + n.upper(), tree[n]) for n in names]
    macros.append(("SECRET_TARGET", target))
    path = bin(target)[2:][::-1]
    steps = " → ".join("오른쪽" if b == "1" else "왼쪽" for b in path)
    return Phase(
        "secret", "fun7", "cmu/secret_fun7.c", macros,
        answer=str(x), check=check, title="이진 탐색 트리 (fun7)",
        answers="정답: %s. `fun7`이 %d를 돌려주는 노드 값들이다."
                % (", ".join("`%d`" % v for v in xs), target),
        walkthrough="""\
**찾기**: `phase_defused`는 여섯 번째 줄을 읽은 뒤(`cmpl $0x6,num_input_strings`)
네 번째 줄을 `sscanf(..., "%%d %%d %%s", ...)`로 다시 읽어 세 번째 토큰을 문자열과
비교한다(`x/s`로 확인). 그 단어를 phase 4 답 뒤에 붙이면 `secret_phase`가 열린다.

**풀기**: `secret_phase`는 줄을 `strtol`로 읽고 1~1001인지 확인한 뒤
`fun7(&n1, x)`의 반환값을 %d과 비교한다.

```
fun7(node, x):
    node == NULL  → -1
    x < value     → 2 * fun7(left, x)
    x == value    → 0
    x > value     → 2 * fun7(right, x) + 1
```

노드는 24바이트(`int value; node *left; node *right;`, 값 뒤 4바이트는 정렬 여백)다.
`x/60wx 0x...`(n1 주소) 또는 `n1`, `n21`, … 심볼마다 `x/6wx`로 트리를 그린다.

반환값 %d을 2진수로 쓰고 **아래 비트부터** 읽으면 루트에서의 경로다(1=오른쪽, 0=왼쪽):
%s. 그 경로 끝 노드(와, 거기서 왼쪽으로만 더 내려간 노드) 값이 답이다: %s.
""" % (target, target, steps, ", ".join(str(v) for v in xs)),
        hints=[
            "`phase_defused`에서 몇 번째 줄을 어떤 형식으로 다시 읽는지 보라. 비교하는 문자열은 `x/s`로.",
            "`fun7`의 세 갈래(작다/같다/크다)가 반환값을 어떻게 만드는지 적어 보라. 노드는 `n1`부터 24바이트 구조체다.",
            "목표 반환값을 2진수로 쓰고 아래 비트부터: 0이면 왼쪽, 1이면 오른쪽. 그 경로 끝 노드의 값이 답이다.",
        ])


# --------------------------------------------------------------------------

SLOTS = [
    ("p1", {"strings": gen_p1}),
    ("p2", {"double": gen_p2}),
    ("p3", {"switch_dd": gen_p3}),
    ("p4", {"func4_bsearch": gen_p4}),
    ("p5", {"charmap": gen_p5}),
    ("p6", {"list": gen_p6}),
    ("secret", {"fun7": gen_secret}),
]


def variants():
    return {slot: sorted(fams) for slot, fams in SLOTS}


def build(seed, force=None):
    force = dict(force or {})
    phases = []
    for slot, families in SLOTS:
        names = sorted(families)
        if slot in force:
            name = force.pop(slot)
            if name not in families:
                raise BankError("cmu %s: no variant %r (have %s)"
                                % (slot, name, ", ".join(names)))
        else:
            name = rng(KIND, seed, slot, "variant").choice(names)
        phases.append(families[name](rng(KIND, seed, slot, name)))
    if force:
        raise BankError("cmu: unknown slot(s) %s" % ", ".join(sorted(force)))

    word = rng(KIND, seed, "secret-word").choice(SECRET_WORDS)
    return Bomb(KIND, seed, phases, main="bomb.c", num_phases=6,
                has_secret=True, secret_line=3, secret_word=word,
                title="CMU 구조 폭탄")
