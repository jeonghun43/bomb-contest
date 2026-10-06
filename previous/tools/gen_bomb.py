#!/usr/bin/env python3
"""
gen_bomb.py - Generate a seeded variant of the bomb.

    python3 tools/gen_bomb.py --seed 20260215

Outputs:
    build/seed-N/bombdata.h     constants and extern declarations
    build/seed-N/bombdata.c     seeded tables
    build/seed-N/solution.txt   six answer lines
    build/seed-N/solution_secret.txt
                                same, but the phase 4 line carries the hidden
                                token and a seventh line answers the secret
    build/seed-N/SOLUTION.md    author's walkthrough with staged hints

Every phase is sampled, screened for degenerate cases, and checked for a
unique solution before it is accepted. The Python routines here mirror the C
in src/phases.c exactly; tools/verify.sh runs the real binary against these
answers, so any drift between the two implementations shows up at build time.
"""

import argparse
import math
import os
import random
import re
import sys

M32 = 0xFFFFFFFF

P3_STEPS = 6
P5_PATH_LEN = 6
P5_TREE_SIZE = 127

PS_MOD = 65537  # prime, so the congruence in the secret phase has one root


# --------------------------------------------------------------------------
# Bit helpers - mirror src/util.c
# --------------------------------------------------------------------------

def rotl32(v, n):
    n &= 31
    return ((v << n) | (v >> ((32 - n) & 31))) & M32


def rotr32(v, n):
    n &= 31
    return ((v >> n) | (v << ((32 - n) & 31))) & M32


def bit_reverse(v, bits):
    r = 0
    for i in range(bits):
        r = (r << 1) | ((v >> i) & 1)
    return r


def popcount(v):
    return bin(v).count("1")


# --------------------------------------------------------------------------
# Phase 1 - rotate and xor
# --------------------------------------------------------------------------

def check_p1(x, p):
    return rotl32((x & M32) ^ p["P1_KEY"], p["P1_ROT"]) == p["P1_TARGET"]


def gen_p1(rng):
    while True:
        key = rng.getrandbits(32)
        rot = rng.randrange(3, 30)

        if key == 0:
            continue
        if rot % 8 == 0:            # a byte rotate is too easy to eyeball
            continue

        answer = rng.randrange(1000, 1000000)
        params = {
            "P1_KEY": key,
            "P1_ROT": rot,
            "P1_TARGET": rotl32(answer ^ key, rot),
        }

        assert check_p1(answer, params)
        return params, answer


# --------------------------------------------------------------------------
# Phase 2 - 16-bit LFSR
# --------------------------------------------------------------------------

def p2_sequence(seed, poly):
    a = [seed]
    for _ in range(5):
        t = a[-1]
        n = (t << 1) & 0xFFFF
        if t & 0x8000:
            n ^= poly
        a.append(n)
    return a


def gen_p2(rng):
    while True:
        seed = rng.randrange(0x1000, 0x10000)
        poly = rng.randrange(0x1000, 0x10000) | 1
        a = p2_sequence(seed, poly)

        if 0 in a:
            continue
        if len(set(a)) != 6:                    # no repeats to guess from
            continue
        if len({a[i + 1] - a[i] for i in range(5)}) < 4:
            continue                            # must not look arithmetic
        taps = sum(1 for i in range(5) if a[i] & 0x8000)
        if taps < 2 or taps > 4:                # exercise both branches
            continue

        return {"P2_SEED": seed, "P2_POLY": poly}, a


# --------------------------------------------------------------------------
# Phase 3 - walk on a 4x4 torus
# --------------------------------------------------------------------------

P3_DR = (-1, 0, 1, 0)
P3_DC = (0, 1, 0, -1)


def p3_walk(grid, r, c, steps=P3_STEPS):
    total = 0
    seen = []
    for _ in range(steps):
        v = grid[r][c]
        seen.append((r, c))
        d = v & 3
        st = ((v >> 2) & 3) + 1
        total += (v >> 4) & 0xF
        r = (r + P3_DR[d] * st) % 4
        c = (c + P3_DC[d] * st) % 4
    return r, c, total, seen


def gen_p3(rng):
    while True:
        grid = [[rng.randrange(256) for _ in range(4)] for _ in range(4)]
        sr, sc = rng.randrange(4), rng.randrange(4)
        er, ec, total, seen = p3_walk(grid, sr, sc)

        if (sr, sc) == (0, 0):                  # too guessable a start
            continue
        if len(set(seen)) < 3:                  # no self-loop or 2-cycle
            continue

        hits = [
            (r, c)
            for r in range(4)
            for c in range(4)
            if p3_walk(grid, r, c)[:3] == (er, ec, total)
        ]
        if len(hits) != 1:                      # exhaustive uniqueness check
            continue

        params = {
            "p3_grid": grid,
            "P3_GOAL": er * 4 + ec,
            "P3_SUM": total,
        }
        return params, (sr, sc)


# --------------------------------------------------------------------------
# Phase 4 - modular inverse
# --------------------------------------------------------------------------

P4_PRIMES = [1021, 1031, 1049, 1063, 1091, 1381, 1543, 1789, 2039]


def gen_p4(rng):
    while True:
        mod = rng.choice(P4_PRIMES)
        mul = rng.randrange(2, mod)
        if math.gcd(mul, mod) != 1:
            continue

        x = rng.randrange(100, mod - 1)
        if x in (1, mod - 1) or x == mul:
            continue

        res = (x * mul) % mod
        if res in (0, 1):
            continue

        params = {"P4_MOD": mod, "P4_MUL": mul, "P4_RES": res}
        return params, (x, bit_reverse(x, 11))


# --------------------------------------------------------------------------
# Phase 5 - determined path through a binary tree
# --------------------------------------------------------------------------

def p5_path(tree, init):
    acc = init
    idx = 0
    out = []
    for _ in range(P5_PATH_LEN):
        v = tree[idx]
        want = (acc ^ v) & 1
        out.append("R" if want else "L")
        idx = 2 * idx + 1 + want
        acc = (rotl32(acc, 5) + v) & M32
    return "".join(out), acc


def gen_p5(rng):
    while True:
        tree = [rng.getrandbits(32) for _ in range(P5_TREE_SIZE)]
        init = rng.getrandbits(32)
        path, acc = p5_path(tree, init)

        if path.count("L") < 2 or path.count("R") < 2:
            continue                            # no monotone paths

        params = {"p5_tree": tree, "P5_INIT": init, "P5_TARGET": acc}
        return params, path


# --------------------------------------------------------------------------
# Phase 6 - strictly increasing chain of bit masks
# --------------------------------------------------------------------------

def gen_p6(rng):
    while True:
        bits = list(range(16))
        rng.shuffle(bits)

        incs = [rng.randrange(1, 4) for _ in range(6)]
        if sum(incs) > 16:
            continue
        if len(set(incs)) < 3:                  # growth must not be uniform
            continue

        masks = []
        cur = 0
        k = 0
        for inc in incs:
            for _ in range(inc):
                cur |= 1 << bits[k]
                k += 1
            masks.append(cur)

        ids = list(range(1, 7))
        rng.shuffle(ids)                        # ids[i] labels chain step i
        answer = ids[:]

        slots = list(range(6))
        rng.shuffle(slots)                      # chain step i lives in slot
        if slots == sorted(slots):              # physical order == answer
            continue

        p6_masks = [0] * 6
        p6_ids = [0] * 6
        for i in range(6):
            p6_masks[slots[i]] = masks[i]
            p6_ids[slots[i]] = ids[i]

        chain = list(range(6))
        rng.shuffle(chain)                      # next-pointer traversal order
        if [p6_ids[s] for s in chain] == answer:
            continue                            # chain must not spell the answer

        params = {
            "p6_masks": p6_masks,
            "p6_ids": p6_ids,
            "p6_chain": chain,
            "P6_FULL": masks[-1],
        }
        return params, answer


# --------------------------------------------------------------------------
# Secret phase - reverse bits, then invert modulo 65537
# --------------------------------------------------------------------------

SECRET_WORDS = [
    "quicksilver", "obsidian", "lodestone", "cinnabar", "meridian",
    "alabaster", "wolfram", "peregrine", "vermilion", "tantalum",
]


REV16 = [bit_reverse(v, 16) for v in range(0x10000)]
POP16 = [popcount(v) for v in range(0x10000)]


def gen_secret(rng):
    while True:
        mul = rng.randrange(2, PS_MOD)
        x = rng.randrange(1, 0x10000)
        pop = POP16[x]
        if pop < 4 or pop > 12:
            continue

        res = (REV16[x] * mul) % PS_MOD

        sols = [
            v
            for v in range(1, 0x10000)
            if (REV16[v] * mul) % PS_MOD == res and POP16[v] == pop
        ]
        if len(sols) != 1:                      # exhaustive uniqueness check
            continue

        params = {
            "PS_MUL": mul,
            "PS_RES": res,
            "PS_POP": pop,
            "PS_WORD": rng.choice(SECRET_WORDS),
        }
        return params, sols[0]


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_header(seed, p, bomb_id=None):
    # A server-mode bomb carries an opaque id instead of its seed: the seed
    # plus this generator reproduces every answer.
    if bomb_id is None:
        identity = ["#define BOMB_SEED %d" % seed]
    else:
        identity = ['#define BOMB_ID "%s"' % bomb_id]

    lines = [
        "/* Generated by tools/gen_bomb.py - do not edit, do not distribute. */",
        "#ifndef BOMBDATA_H",
        "#define BOMBDATA_H",
        "",
    ] + identity + [
        "",
        "/* phase 1 */",
        "#define P1_KEY      0x%08Xu" % p["P1_KEY"],
        "#define P1_ROT      %d" % p["P1_ROT"],
        "#define P1_TARGET   0x%08Xu" % p["P1_TARGET"],
        "",
        "/* phase 2 */",
        "#define P2_SEED     %d" % p["P2_SEED"],
        "#define P2_POLY     0x%04Xu" % p["P2_POLY"],
        "",
        "/* phase 3 */",
        "#define P3_STEPS    %d" % P3_STEPS,
        "#define P3_GOAL     %d" % p["P3_GOAL"],
        "#define P3_SUM      %d" % p["P3_SUM"],
        "extern const unsigned char p3_grid[4][4];",
        "",
        "/* phase 4 */",
        "#define P4_MOD      %d" % p["P4_MOD"],
        "#define P4_MUL      %d" % p["P4_MUL"],
        "#define P4_RES      %d" % p["P4_RES"],
        "",
        "/* phase 5 */",
        "#define P5_INIT     0x%08Xu" % p["P5_INIT"],
        "#define P5_TARGET   0x%08Xu" % p["P5_TARGET"],
        "extern const unsigned p5_tree[%d];" % P5_TREE_SIZE,
        "",
        "/* phase 6 */",
        "#define P6_FULL     0x%08Xu" % p["P6_FULL"],
        "extern const unsigned p6_masks[6];",
        "extern const int      p6_ids[6];",
        "extern const int      p6_chain[6];",
        "",
        "/* secret phase */",
        "#define PS_MOD      %d" % PS_MOD,
        "#define PS_MUL      %du" % p["PS_MUL"],
        "#define PS_RES      %du" % p["PS_RES"],
        "#define PS_POP      %d" % p["PS_POP"],
        '#define PS_WORD     "%s"' % p["PS_WORD"],
        "",
        "#endif /* BOMBDATA_H */",
        "",
    ]
    return "\n".join(lines)


def render_source(p):
    out = [
        "/* Generated by tools/gen_bomb.py - do not edit, do not distribute. */",
        '#include "bombdata.h"',
        "",
        "const unsigned char p3_grid[4][4] = {",
    ]
    for row in p["p3_grid"]:
        out.append("    { " + ", ".join("0x%02X" % v for v in row) + " },")
    out += ["};", "", "const unsigned p5_tree[%d] = {" % P5_TREE_SIZE]
    tree = p["p5_tree"]
    for i in range(0, P5_TREE_SIZE, 4):
        chunk = tree[i:i + 4]
        out.append("    " + ", ".join("0x%08Xu" % v for v in chunk) + ",")
    out += [
        "};",
        "",
        "const unsigned p6_masks[6] = { "
        + ", ".join("0x%08Xu" % v for v in p["p6_masks"]) + " };",
        "const int p6_ids[6] = { "
        + ", ".join(str(v) for v in p["p6_ids"]) + " };",
        "const int p6_chain[6] = { "
        + ", ".join(str(v) for v in p["p6_chain"]) + " };",
        "",
    ]
    return "\n".join(out)


def answer_lines(ans, params, with_secret):
    p4 = "%d %d" % ans["p4"]
    if with_secret:
        p4 += " " + params["PS_WORD"]

    lines = [
        str(ans["p1"]),
        " ".join(str(v) for v in ans["p2"]),
        "%d %d" % ans["p3"],
        p4,
        ans["p5"],
        " ".join(str(v) for v in ans["p6"]),
    ]
    if with_secret:
        lines.append(str(ans["secret"]))
    return "\n".join(lines) + "\n"


def render_solution_md(seed, p, ans):
    grid = p["p3_grid"]
    grid_rows = "\n".join(
        "| %d | " % r + " | ".join("0x%02X" % grid[r][c] for c in range(4)) + " |"
        for r in range(4)
    )

    chain_order = [p["p6_ids"][s] for s in p["p6_chain"]]
    masks_by_id = {p["p6_ids"][i]: p["p6_masks"][i] for i in range(6)}
    mask_rows = "\n".join(
        "| %d | 0x%04X | `%s` | %d |"
        % (i, masks_by_id[i], format(masks_by_id[i], "016b"),
           popcount(masks_by_id[i]))
        for i in sorted(masks_by_id)
    )

    inv4 = pow(p["P4_MUL"], -1, p["P4_MOD"])
    inv_s = pow(p["PS_MUL"], -1, PS_MOD)
    secret_rev = bit_reverse(ans["secret"], 16)

    return f"""# SOLUTION - seed {seed}

**출제자 전용. 참가자에게 배포 금지.**

## 정답 요약

| phase | 정답 |
|---|---|
| 1 | `{ans['p1']}` |
| 2 | `{' '.join(str(v) for v in ans['p2'])}` |
| 3 | `{ans['p3'][0]} {ans['p3'][1]}` |
| 4 | `{ans['p4'][0]} {ans['p4'][1]}` |
| 5 | `{ans['p5']}` |
| 6 | `{' '.join(str(v) for v in ans['p6'])}` |
| secret | `{ans['secret']}` |

secret 진입: phase 4 줄을 `{ans['p4'][0]} {ans['p4'][1]} {p['PS_WORD']}` 로 적는다.

---

## Phase 1 — 회전 + XOR (쉬움, 목표 10~20분)

**의도**: objdump만으로 풀리는 워밍업. 전단사 연산의 역산 개념.

- 상수: `P1_KEY = 0x{p['P1_KEY']:08X}`, `P1_ROT = {p['P1_ROT']}`, `P1_TARGET = 0x{p['P1_TARGET']:08X}`
- 역산: `x = rotr32(0x{p['P1_TARGET']:08X}, {p['P1_ROT']}) ^ 0x{p['P1_KEY']:08X}` = **{ans['p1']}**

**힌트 1** — 이 phase가 하는 일은 딱 두 가지 연산이다. 둘 다 되돌릴 수 있다.
**힌트 2** — `rol` 명령이 무엇을 하는지, 그리고 그 반대 명령이 무엇인지 확인해라.
**힌트 3** — `cmp`의 상수에서 시작해 거꾸로 `ror {p['P1_ROT']}`, 그다음 `xor 0x{p['P1_KEY']:08X}`.

## Phase 2 — 16비트 LFSR (쉬움, 목표 20~30분)

**의도**: 시프트와 조건부 XOR로 이어지는 점화식. 첫 값만 알면 나머지가 결정된다.

- 상수: `P2_SEED = {p['P2_SEED']}`, `P2_POLY = 0x{p['P2_POLY']:04X}`
- 수열: {' -> '.join(str(v) for v in ans['p2'])}

**힌트 1** — 여섯 개 값이 서로 독립이 아니다. 하나가 정해지면 나머지는 따라온다.
**힌트 2** — 첫 값은 코드에 그대로 들어 있다. 루프가 앞 값에서 뒤 값을 어떻게 만드는지 보라.
**힌트 3** — 왼쪽으로 1비트 밀고, 밀려나간 최상위 비트가 1이었으면 0x{p['P2_POLY']:04X}와 XOR 한다. 16비트로 자른다.

## Phase 3 — 4×4 격자 순회 (중간, 목표 40~60분)

**의도**: 바이트 하나에 방향·보폭·가중치가 패킹되어 있음을 읽어내고, 격자를 그려 역추적.

격자 `p3_grid` (행 r, 열 c):

|  | c=0 | c=1 | c=2 | c=3 |
|---|---|---|---|---|
{grid_rows}

- 인코딩: `dir = v & 3` (0=상 1=우 2=하 3=좌), `step = ((v>>2)&3)+1`, `weight = (v>>4)&0xF`
- 목표: {P3_STEPS}스텝 후 `r*4+c == {p['P3_GOAL']}` (r={p['P3_GOAL'] // 4}, c={p['P3_GOAL'] % 4}), 가중치 합 = {p['P3_SUM']}
- 정답 시작점: **{ans['p3'][0]} {ans['p3'][1]}** (16개 시작점 중 유일)

**힌트 1** — 입력 두 개는 좌표다. 격자 위에서 정해진 횟수만큼 움직인다.
**힌트 2** — 셀 값 한 바이트를 비트로 쪼개 보라. 하위 2비트, 그다음 2비트, 상위 4비트가 각각 다른 역할을 한다.
**힌트 3** — 16칸에 각각 화살표를 그리면 시작점 16개의 종착지가 한눈에 보인다. 조건을 만족하는 건 하나뿐이다.

## Phase 4 — 모듈러 역산 (중간, 목표 50~70분)

**의도**: 컴파일러가 상수 나눗셈을 곱셈+시프트로 바꾼다는 사실을 발견하는 것이 핵심. 그 뒤는 확장 유클리드.

- 조건: `({p['P4_MUL']} * x) mod {p['P4_MOD']} == {p['P4_RES']}`, `y = reverse_bits(x, 11)`
- `{p['P4_MUL']}`의 역원 mod {p['P4_MOD']} = {inv4}
- `x = {p['P4_RES']} * {inv4} mod {p['P4_MOD']}` = **{ans['p4'][0]}**
- `y = reverse_bits({ans['p4'][0]}, 11)` = **{ans['p4'][1]}** (`{format(ans['p4'][0], '011b')}` → `{format(ans['p4'][1], '011b')}`)

**힌트 1** — 첫 번째 조건은 나머지 연산이다. 두 번째 값은 첫 번째 값에서 계산된다.
**힌트 2** — 어셈블리에 나눗셈 명령이 없다고 나눗셈이 없는 게 아니다. 큰 상수와의 `imul` 뒤에 오는 `shr`/`sar` 조합을 보라.
**힌트 3** — `{p['P4_MOD']}`은 소수다. `{p['P4_MUL']}`의 곱셈 역원을 확장 유클리드로 구하면 x가 한 번에 나온다. y는 x의 하위 11비트를 뒤집은 값.

## Phase 5 — 이진 트리 경로 (어려움, 목표 60~80분)

**의도**: 경로를 탐색하는 문제로 착각하기 쉽지만, 매 스텝의 방향이 누산기에서 결정된다. 64가지를 시도할 필요가 없다.

- 시작: `acc = 0x{p['P5_INIT']:08X}`, `idx = 0`
- 각 스텝: `want = (acc ^ tree[idx]) & 1`, `idx = 2*idx + 1 + want`, `acc = rotl32(acc,5) + tree[idx_before]`
- 정답 경로: **{ans['p5']}**
- 최종 검산값: `P5_TARGET = 0x{p['P5_TARGET']:08X}`

방문 노드:

| 스텝 | idx | tree[idx] | want |
|---|---|---|---|
""" + "\n".join(
        _p5_trace_rows(p["p5_tree"], p["P5_INIT"])
    ) + f"""

**힌트 1** — 64가지를 전부 시도하지 마라. 입력이 방향을 정하는 게 아니라, 프로그램이 방향을 정하고 입력이 맞는지만 본다.
**힌트 2** — `idx = 2*idx + 1 + ...` 는 배열로 표현한 완전이진트리의 자식 인덱스 공식이다. 루트는 0.
**힌트 3** — 0번 노드부터 시작해 `(acc ^ 노드값) & 1`을 계산하면 이번 글자가 L인지 R인지 나온다. 그 값으로 다음 인덱스를 구하고 acc를 갱신하며 6번 반복.

## Phase 6 — 비트마스크 포함 사슬 (어려움, 목표 50~70분)

**의도**: 정렬처럼 보이지만 기준이 집합 포함관계. 마스크를 비트로 적어놓으면 순서가 눈에 보인다. 720가지 순열 탐색 불필요.

| id | mask | 비트 | popcount |
|---|---|---|---|
{mask_rows}

- 연결리스트 순회 순서 (물리 슬롯 `p6_chain` 기준 id): {' -> '.join(str(v) for v in chain_order)}
- 조건: 앞 마스크가 뒤 마스크의 부분집합, 마지막이 `P6_FULL = 0x{p['P6_FULL']:04X}`
- 정답: **{' '.join(str(v) for v in ans['p6'])}**

**힌트 1** — 입력은 1~6의 순열이다. 노드 6개에 각각 마스크가 하나씩 있다.
**힌트 2** — 조건 `(prev & mask) == prev` 가 뜻하는 것을 집합으로 옮겨 생각해 보라.
**힌트 3** — 여섯 마스크를 2진수로 나란히 적으면 1비트가 계속 추가되기만 하는 사슬이다. popcount가 작은 것부터 나열하면 끝.

## Secret Phase — 비트 역순 + 모듈러 역산 (동점자용)

**진입**: phase 4 정답 줄 끝에 `{p['PS_WORD']}` 를 덧붙인다. (`phase_defused`가 그 줄을 `"%d %d %s"` 로 다시 읽는다.)

- 조건: `reverse_bits(x,16) * {p['PS_MUL']} mod 65537 == {p['PS_RES']}`, `popcount(x) == {p['PS_POP']}`
- `{p['PS_MUL']}`의 역원 mod 65537 = {inv_s}
- `reverse_bits(x,16) = {p['PS_RES']} * {inv_s} mod 65537` = {secret_rev}
- `x = reverse_bits({secret_rev}, 16)` = **{ans['secret']}** (`{format(ans['secret'], '016b')}`, popcount {p['PS_POP']})

**힌트 1** — 진입 조건은 코드 어딘가에서 답 줄을 한 번 더 읽는 곳에 있다.
**힌트 2** — 65537은 소수다. phase 4에서 쓴 방법이 그대로 통한다.
**힌트 3** — 역원으로 역순 비트열을 먼저 구하고, 그걸 다시 뒤집으면 x다. popcount는 검산용.

---

## 운영 메모

- 폭발 시 프로세스가 종료된다. 참가자에게 gdb 안에서 먼저 시험하도록 안내할 것.
- `bomb.log`에 START / DEFUSED / EXPLODED가 기록된다. 순위 집계에 사용.
- 힌트는 1 → 2 → 3 순서로만 지급한다.
"""


def _p5_trace_rows(tree, init):
    acc = init
    idx = 0
    rows = []
    for step in range(P5_PATH_LEN):
        v = tree[idx]
        want = (acc ^ v) & 1
        rows.append("| %d | %d | 0x%08X | %s |"
                    % (step + 1, idx, v, "R" if want else "L"))
        idx = 2 * idx + 1 + want
        acc = (rotl32(acc, 5) + v) & M32
    return rows


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def build(seed):
    rng = random.Random(seed)
    params = {}
    ans = {}

    for key, fn in (("p1", gen_p1), ("p2", gen_p2), ("p3", gen_p3),
                    ("p4", gen_p4), ("p5", gen_p5), ("p6", gen_p6),
                    ("secret", gen_secret)):
        p, a = fn(rng)
        params.update(p)
        ans[key] = a

    return params, ans


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate a seeded bomb variant.")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", help="output directory (default: build/seed-N)")
    ap.add_argument("--bomb-id",
                    help="server mode: embed this hex id instead of the seed")
    args = ap.parse_args(argv)

    if args.bomb_id is not None and not re.fullmatch(r"[0-9a-f]{16}", args.bomb_id):
        ap.error("--bomb-id must be 16 lowercase hex digits")

    params, ans = build(args.seed)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = args.out or os.path.join(root, "build", "seed-%d" % args.seed)
    os.makedirs(out, exist_ok=True)

    with open(os.path.join(out, "bombdata.h"), "w") as f:
        f.write(render_header(args.seed, params, args.bomb_id))
    with open(os.path.join(out, "bombdata.c"), "w") as f:
        f.write(render_source(params))
    with open(os.path.join(out, "solution.txt"), "w") as f:
        f.write(answer_lines(ans, params, with_secret=False))
    with open(os.path.join(out, "solution_secret.txt"), "w") as f:
        f.write(answer_lines(ans, params, with_secret=True))
    with open(os.path.join(out, "SOLUTION.md"), "w", encoding="utf-8") as f:
        f.write(render_solution_md(args.seed, params, ans))

    print("seed %d -> %s" % (args.seed, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
