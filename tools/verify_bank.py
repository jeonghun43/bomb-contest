#!/usr/bin/env python3
"""
verify_bank.py - Verify every kind and every variant family of the practice
bank (specs/003-practice-bank T035; AC-01..04, AC-07, NFR-11, NFR-14).

    python3 tools/verify_bank.py [--seeds N] [--kind K ...] [--no-fuzz]

Builds, for every kind:
  - seeds 1..N with the variants their seeds choose, and
  - one extra bomb per (slot, variant) pair the seeds did not cover, so no
    family is left to chance (NFR-11),
all in one container run, every bomb passing elfcheck. Then for each bomb:

  determinism   rendering the same (kind, seed) twice gives identical files
  answers       answers.txt defuses every phase (exit 0); with the secret
                token, answers_secret.txt defuses the secret phase too
  judge         bank.judge accepts every listed answer
  position      for each phase, a wrong line explodes exactly at that phase
                (the answers before it get through, the wrong one goes BOOM)
  fuzz          bank.judge agrees with the binary on boundary inputs
  package       the student package holds only bomb and bomb.c

Exit status 0 when everything passes. `make verify` runs this together with
tools/runtime_check.sh and tools/parity.sh.
"""

import argparse
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import bank  # noqa: E402
import buildbomb  # noqa: E402
import fuzz_bank  # noqa: E402

W = os.path.join(ROOT, "build", "verify")


class Report:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def ok(self, msg):
        self.passed += 1

    def bad(self, msg):
        self.failed += 1
        print("  FAIL " + msg)


def plan(kinds, seeds):
    """[(kind, seed, force)] covering seeds 1..N and every variant."""
    jobs = []
    for kind in kinds:
        seen = set()
        for s in range(1, seeds + 1):
            jobs.append((kind, s, None))
            seen.update(bank.build(kind, s).variants().items())
        extra = 1000
        for slot, names in sorted(bank.variants(kind).items()):
            for name in names:
                if (slot, name) not in seen:
                    extra += 1
                    jobs.append((kind, extra, {slot: name}))
                    seen.add((slot, name))
    return jobs


def dirname(kind, seed):
    return os.path.join(W, "%s-%d" % (kind.replace(":", "-"), seed))


def wrong_line(bomb, number):
    """A line the judge rejects for this phase, preferring near misses."""
    p = bomb.phase(number)
    for c in fuzz_bank.candidates(p.answer, p)[1:]:
        if not bank.judge.check(bomb, number, c):
            return c
    return "this is not the answer"


def check_bomb(rep, kind, seed, force, do_fuzz):
    d = dirname(kind, seed)
    name = os.path.basename(d)
    bomb = bank.build(kind, seed, force=force)

    # determinism: a second render must be byte-identical, file for file
    d2 = d + ".again"
    bank.render.write(bank.build(kind, seed, force=force), d2)
    a, b = bank.render.digest(d), bank.render.digest(d2)
    diffs = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
    bank.render.rmtree(d2)
    (rep.bad("%s: render not deterministic: %s" % (name, diffs))
     if diffs else rep.ok(name))

    # answers
    out, code = fuzz_bank.run_bomb(d, bomb.answer_lines())
    if code == 0 and "Congratulations! You've defused the bomb!" in out \
            and "BOOM" not in out:
        rep.ok(name)
    else:
        rep.bad("%s: answers.txt did not defuse (exit %d)" % (name, code))
    if bomb.has_secret:
        out, code = fuzz_bank.run_bomb(d, bomb.answer_lines(with_secret=True))
        if code == 0 and "Wow! You've defused the secret stage!" in out:
            rep.ok(name)
        else:
            rep.bad("%s: secret answers did not defuse (exit %d)" % (name, code))

    # judge accepts the answers it hands out
    for i, p in enumerate(bomb.phases):
        if bank.judge.check(bomb, i + 1, p.answer):
            rep.ok(name)
        else:
            rep.bad("%s: judge rejects its own answer for phase %d"
                    % (name, i + 1))

    # explosion position
    for i in range(len(bomb.phases)):
        number = i + 1
        pre = fuzz_bank.prefix_for(bomb, number)
        out1, _ = fuzz_bank.run_bomb(d, pre)
        out2, code2 = fuzz_bank.run_bomb(d, pre + [wrong_line(bomb, number)])
        if "BOOM" not in out1 and "BOOM" in out2 and code2 == 8:
            rep.ok(name)
        else:
            rep.bad("%s: phase %d does not explode exactly there"
                    % (name, number))

    if do_fuzz:
        tested, bad = fuzz_bank.fuzz_dir(d, log=lambda m: print(m))
        (rep.bad("%s: %d/%d fuzz mismatches" % (name, bad, tested))
         if bad else rep.ok(name))
        return tested
    return 0


def check_package(rep, d, bomb):
    """
    What a student receives is bomb + bomb.c. bomb.c must not carry an
    answer, the secret token, a generated header, or an unfilled template
    placeholder.
    """
    with open(os.path.join(d, "bomb.c"), encoding="utf-8") as f:
        src = f.read()
    secrets = [p.answer for p in bomb.phases if len(p.answer) >= 4]
    if bomb.secret_word:
        secrets.append(bomb.secret_word)
    leaks = [w for w in ["bombdata.h", "SECRET_WORD", "@DRILL"] + secrets
             if w in src]
    (rep.bad("%s: student bomb.c leaks %s" % (os.path.basename(d), leaks))
     if leaks else rep.ok(d))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify the practice bank.")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--kind", action="append",
                    help="limit to these kinds (default: all)")
    ap.add_argument("--no-fuzz", action="store_true")
    args = ap.parse_args(argv)

    kinds = args.kind or bank.kinds()
    jobs = plan(kinds, args.seeds)
    print("verify: %d bombs across %d kinds" % (len(jobs), len(kinds)))

    bank.render.rmtree(W)
    os.makedirs(W)
    dirs = []
    for kind, seed, force in jobs:
        d = dirname(kind, seed)
        bank.render.write(bank.build(kind, seed, force=force), d)
        dirs.append(d)
    try:
        buildbomb.compile_dirs(dirs)
        buildbomb.check_dirs(dirs)
    except buildbomb.BuildError as e:
        print("verify: build failed: %s" % e)
        return 1
    print("  built and elfchecked %d bombs" % len(dirs))

    rep = Report()
    lines = 0
    for kind, seed, force in jobs:
        lines += check_bomb(rep, kind, seed, force, not args.no_fuzz)
    for (kind, seed, force), d in zip(jobs, dirs):
        check_package(rep, d, bank.build(kind, seed, force=force))

    print("verify: %d checks passed, %d failed%s"
          % (rep.passed, rep.failed,
             "" if args.no_fuzz else ", %d fuzz lines" % lines))
    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
