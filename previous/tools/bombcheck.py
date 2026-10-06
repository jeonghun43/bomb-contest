#!/usr/bin/env python3
"""
bombcheck.py - Reference judge used by the record server.

The server does not trust a bomb's "defused" claim: it re-scores the submitted
input line with this module, using the contestant's own seed. A claim only
counts as a defusal when check_line returns True.

check_line(phase, line, params) mirrors the C in src/phases.c *exactly*,
including sscanf parsing quirks. tools/fuzz_checker.py enforces that agreement
against the compiled bomb over boundary inputs; do not "fix" a discrepancy here
without re-running that fuzzer.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_bomb  # noqa: E402  (rotl32, p2_sequence, p3_walk, bit_reverse, ...)

M32 = 0xFFFFFFFF
LONG_MIN = -(2 ** 63)
LONG_MAX = 2 ** 63 - 1
WS = " \t\n\v\f\r"


def _to_int32(v):
    v &= M32
    return v - (1 << 32) if v & 0x80000000 else v


def scan_d(s, i):
    """
    Emulate one %d of glibc sscanf starting at s[i].
    Returns (value_as_int, next_index) or (None, i) if no conversion.
    Overflow follows glibc: clamp to long, then assign to int (truncate).
    """
    n = len(s)
    while i < n and s[i] in WS:
        i += 1
    j = i
    if j < n and s[j] in "+-":
        j += 1
    k = j
    while k < n and s[k].isdigit():
        k += 1
    if k == j:                       # no digits
        return None, i
    val = int(s[i:k])                # includes sign
    if val > LONG_MAX:
        val = LONG_MAX
    elif val < LONG_MIN:
        val = LONG_MIN
    return _to_int32(val), k


def scan_ints(s, count):
    """Sequential %d x count, as read_six_numbers / phase parsers do."""
    i = 0
    out = []
    for _ in range(count):
        v, i = scan_d(s, i)
        if v is None:
            return None
        out.append(v)
    return out


def scan_s(s, width):
    """Emulate %<width>s: skip leading ws, take up to `width` non-ws chars."""
    i = 0
    n = len(s)
    while i < n and s[i] in WS:
        i += 1
    j = i
    while j < n and s[j] not in WS and (j - i) < width:
        j += 1
    if j == i:
        return None
    return s[i:j]


# --- per-phase judges ------------------------------------------------------

def _p1(line, p):
    got = scan_ints(line, 1)
    if got is None:
        return False
    x = got[0]
    return gen_bomb.rotl32((x & M32) ^ p["P1_KEY"], p["P1_ROT"]) == p["P1_TARGET"]


def _p2(line, p):
    a = scan_ints(line, 6)
    if a is None:
        return False
    if a[0] != p["P2_SEED"]:                 # int == int in C
        return False
    seq = gen_bomb.p2_sequence(p["P2_SEED"], p["P2_POLY"])
    for i in range(1, 6):
        if (a[i] & M32) != (seq[i] & M32):   # (unsigned)a[i] == n in C
            return False
    return True


def _p3(line, p):
    got = scan_ints(line, 2)
    if got is None:
        return False
    r, c = got
    if r < 0 or r > 3 or c < 0 or c > 3:
        return False
    er, ec, total, _ = gen_bomb.p3_walk(p["p3_grid"], r, c)
    return er * 4 + ec == p["P3_GOAL"] and total == p["P3_SUM"]


def _p4(line, p):
    got = scan_ints(line, 2)
    if got is None:
        return False
    x, y = got
    if x < 1 or x >= p["P4_MOD"]:
        return False
    if (x * p["P4_MUL"]) % p["P4_MOD"] != p["P4_RES"]:
        return False
    return (y & M32) == gen_bomb.bit_reverse(x & M32, 11)


def _p5(line, p):
    tok = scan_s(line, 63)
    if tok is None or len(tok) != 6:
        return False
    acc = p["P5_INIT"]
    idx = 0
    for ch in tok:
        if ch not in "LR":
            return False
        v = p["p5_tree"][idx]
        want = (acc ^ v) & 1
        got = 1 if ch == "R" else 0
        if got != want:
            return False
        idx = 2 * idx + 1 + want
        acc = (gen_bomb.rotl32(acc, 5) + v) & M32
    return acc == p["P5_TARGET"]


def _p6(line, p):
    a = scan_ints(line, 6)
    if a is None:
        return False
    for i in range(6):
        if a[i] < 1 or a[i] > 6:
            return False
        for j in range(i):
            if a[i] == a[j]:
                return False
    mask_by_id = {p["p6_ids"][k]: p["p6_masks"][k] for k in range(6)}
    prev = 0
    for aid in a:
        m = mask_by_id[aid]
        if (prev & m) != prev:
            return False
        prev = m
    return prev == p["P6_FULL"]


def _secret(line, p):
    got = scan_ints(line, 1)
    if got is None:
        return False
    x = got[0]
    if x < 1 or x > 0xFFFF:
        return False
    r = gen_bomb.bit_reverse(x & M32, 16)
    if (r * p["PS_MUL"]) % gen_bomb.PS_MOD != p["PS_RES"]:
        return False
    return gen_bomb.popcount(x & 0xFFFF) == p["PS_POP"]


_JUDGES = {1: _p1, 2: _p2, 3: _p3, 4: _p4, 5: _p5, 6: _p6, 7: _secret}


def check_line(phase, line, params):
    """True iff `line` defuses `phase` for the bomb described by `params`."""
    judge = _JUDGES.get(phase)
    if judge is None:
        return False
    return judge(line, params)
