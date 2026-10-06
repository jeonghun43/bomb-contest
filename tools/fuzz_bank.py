#!/usr/bin/env python3
"""
fuzz_bank.py - Hold the server's judge (bank.judge) to the real bombs.

    python3 tools/fuzz_bank.py DIR [DIR ...]      rendered + built bomb dirs

For every phase of every bomb, feeds boundary-case lines to BOTH the compiled
bomb (ground truth) and bank.judge.check, and reports any line on which they
disagree about defuse vs explode. A disagreement would record a student as
exploding when the bomb let them through, or the reverse.

The bomb is driven with an answer file: the known answers for the earlier
phases, then the line under test, then nothing (the bomb continues on stdin,
which is empty). The tested phase exploded iff the output has "BOOM!!!".

Lines that never reach a phase are not tested: blank lines (read_line skips
them) and lines of 78 characters or more (read_line explodes on them first).
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bank  # noqa: E402
from bank import judge  # noqa: E402

INT_EDGES = ["0", "-1", "1", "2147483647", "2147483648", "-2147483648",
             "-2147483649", "4294967296", "4294967297",
             "99999999999999999999", "-99999999999999999999"]
NUM = re.compile(r"[+-]?\d+")


def candidates(answer, phase):
    """Boundary lines derived from a valid answer."""
    a = answer
    out = [a, a + " ", " " + a, "\t" + a, a + "  junk", a + " 7",
           a.replace(" ", "\t"), a.replace(" ", "   "), a[:-1], a + "0",
           a + "\r", a.upper(), a.lower(), "x", "-", "+", "+" + a, "-" + a,
           "0x10", a + "\xe9", "\xe9" + a[1:]]

    # every integer token: neighbours, sign flip, overflow edges
    toks = list(NUM.finditer(a))
    for m in toks:
        v = int(m.group())
        for rep in [str(v + 1), str(v - 1), str(-v), "+%d" % v, "0" + str(v),
                    str(v + (1 << 32)), str(v - (1 << 32))] + INT_EDGES:
            out.append(a[:m.start()] + rep + a[m.end():])
    if toks:
        out.append(a[:toks[-1].start()].rstrip())          # one number short
        out.append(" ".join(m.group() for m in toks[:-1]))
    if len(toks) >= 2:                                     # swap two numbers
        t = [m.group() for m in toks]
        t[0], t[1] = t[1], t[0]
        out.append(" ".join(t))

    # characters: change one at a time (phase 5 style), keep nibble or not
    if len(a) <= 12 and not toks:
        for i in range(len(a)):
            for d in (0x10, -0x10, 1):
                c = chr((ord(a[i]) + d) & 0xFF)
                out.append(a[:i] + c + a[i + 1:])

    # extra probes a phase supplies (other valid answers, near misses)
    out += list(getattr(phase, "fuzz", []) or [])

    seen, keep = set(), []
    for c in out:
        if c in seen or "\0" in c or "\n" in c:
            continue
        if not c.strip(judge.WS) or len(c) >= 78:
            continue
        seen.add(c)
        keep.append(c)
    return keep


def run_bomb(d, lines, timeout=10):
    path = os.path.join(d, ".fuzz_in")
    with open(path, "wb") as f:
        f.write(b"".join(l.encode("latin-1") + b"\n" for l in lines))
    r = subprocess.run(["./bomb", ".fuzz_in"], cwd=d, stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=timeout)
    return r.stdout.decode("latin-1"), r.returncode


def defused(output):
    return "BOOM!!!" not in output


def prefix_for(bomb, number):
    """Lines that get the bomb to phase `number` (1-based, secret = N+1)."""
    if bomb.has_secret and number == len(bomb.phases):
        return bomb.answer_lines(with_secret=True)[:-1]
    return bomb.answer_lines()[:number - 1]


def fuzz_dir(d, log=print):
    with open(os.path.join(d, "manifest.json")) as f:
        m = json.load(f)
    bomb = bank.build(m["kind"], m["seed"], force=m["variants"])
    mismatches = tested = 0
    for i, p in enumerate(bomb.phases):
        number = i + 1
        pre = prefix_for(bomb, number)
        for c in candidates(p.answer, p):
            out, _ = run_bomb(d, pre + [c])
            truth = defused(out)
            verdict = judge.check(bomb, number, c)
            tested += 1
            if truth != verdict:
                mismatches += 1
                log("  MISMATCH %s phase %d (%s/%s): %r bomb=%s judge=%s"
                    % (os.path.basename(d), number, p.slot, p.variant, c,
                       "defused" if truth else "exploded",
                       "defused" if verdict else "exploded"))
    try:
        os.unlink(os.path.join(d, ".fuzz_in"))
    except OSError:
        pass
    return tested, mismatches


def main(argv=None):
    ap = argparse.ArgumentParser(description="Judge vs bomb agreement.")
    ap.add_argument("dirs", nargs="+")
    args = ap.parse_args(argv)
    total = bad = 0
    for d in args.dirs:
        t, b = fuzz_dir(d)
        total += t
        bad += b
    print("fuzz: %d lines, %d mismatches" % (total, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
