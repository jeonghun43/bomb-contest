#!/usr/bin/env python3
"""
fuzz_checker.py - Enforce that bombcheck.py agrees with the real bomb.

For each seed, and each phase, feed boundary-case input lines to BOTH:
  - the compiled offline bomb (ground truth), and
  - tools/bombcheck.check_line (the server's judge),
and fail if they ever disagree on defuse-vs-explode.

    python3 tools/fuzz_checker.py --from 1 --to 20

The offline bomb is driven by building an answer file whose earlier lines are
the known-good solution, so control reaches the phase under test; the tested
line goes in that phase's slot and later lines are the true solution (only the
tested phase's verdict matters for whether we reach "defused" for it).
"""

import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_bomb          # noqa: E402
import bombcheck         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Marker phrases the offline bomb prints right AFTER each phase is defused.
PROGRESS = {
    1: "Phase 1 defused",
    2: "That's number 2",
    3: "Halfway there",
    4: "So you got that one",
    5: "Good work",
    6: "Congratulations",
}


def solution_lines(seed):
    _, ans = gen_bomb.build(seed)
    return [
        str(ans["p1"]),
        " ".join(str(v) for v in ans["p2"]),
        "%d %d" % ans["p3"],
        "%d %d" % ans["p4"],
        ans["p5"],
        " ".join(str(v) for v in ans["p6"]),
    ]


def candidates(phase, sol_line):
    """Boundary inputs likely to expose parsing mismatches."""
    base = [
        sol_line,                       # the true answer
        sol_line + "  ",                # trailing spaces
        sol_line + " 999",              # trailing junk token
        "  " + sol_line,                # leading spaces
        sol_line.replace(" ", "\t"),    # tabs as separators
        "",                             # empty line
        "zzz",                          # non-numeric
    ]
    toks = sol_line.split()
    if phase != 5 and toks and all(t.lstrip("+-").isdigit() for t in toks):
        first = int(toks[0])
        base += [
            " ".join(["+" + t if t[0].isdigit() else t for t in toks]),  # + signs
            sol_line + " ",
            "%d %s" % (first + (1 << 32), " ".join(toks[1:])),  # 2^32 + first
            "%d %s" % (first - (1 << 32), " ".join(toks[1:])),  # -2^32 + first
            " ".join([str(int(t) + 1) for t in toks]),          # all +1
        ]
    if phase == 5:
        base += [sol_line + "X", sol_line[:-1], sol_line + "L",
                 sol_line.lower(), "LLLLLL", "RRRRRR"]
    if phase == 3:
        base += ["-1 0", "4 0", "0 4", "3 3"]
    return base


def bomb_defuses(bomb, seed, phase, line, sol):
    """Run the offline bomb with `line` in the phase slot; True if it passes."""
    answer = sol[:]
    answer[phase - 1] = line
    text = "\n".join(answer) + "\n"
    try:
        out = subprocess.run([bomb], input=text, capture_output=True,
                             text=True, timeout=10,
                             cwd=os.path.dirname(bomb) or ".")
    except subprocess.TimeoutExpired:
        return False
    return PROGRESS[phase] in out.stdout


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", type=int, default=1)
    ap.add_argument("--to", type=int, default=20)
    args = ap.parse_args(argv)

    mismatches = 0
    checked = 0

    for seed in range(args.frm, args.to + 1):
        out = os.path.join(ROOT, "build", "seed-%d" % seed)
        subprocess.run(["make", "-C", ROOT, "SEED=%d" % seed, "OUT=%s" % out,
                        "bomb"], check=True, capture_output=True)
        bomb = os.path.join(out, "bomb")
        params, _ = gen_bomb.build(seed)
        sol = solution_lines(seed)

        for phase in range(1, 7):
            for line in candidates(phase, sol[phase - 1]):
                truth = bomb_defuses(bomb, seed, phase, line, sol)
                judged = bombcheck.check_line(phase, line, params)
                checked += 1
                if truth != judged:
                    mismatches += 1
                    print("MISMATCH seed=%d phase=%d line=%r "
                          "bomb=%s checker=%s"
                          % (seed, phase, line, truth, judged))

    print("checked %d inputs, %d mismatches" % (checked, mismatches))
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
