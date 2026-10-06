#!/usr/bin/env python3
"""
check_secret_unique.py - Re-verify that the secret phase answer is unique.

    python3 tools/check_secret_unique.py --seed 20260215

The generator already screens for this, but the check is cheap and this
script is what tools/verify.sh calls, so the property is re-established from
scratch for every seed rather than trusted.

Exits 0 when exactly one integer in 1..0xFFFF satisfies the phase.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gen_bomb  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    args = ap.parse_args(argv)

    params, ans = gen_bomb.build(args.seed)

    mul = params["PS_MUL"]
    res = params["PS_RES"]
    pop = params["PS_POP"]
    mod = gen_bomb.PS_MOD

    sols = [
        x
        for x in range(1, 0x10000)
        if (gen_bomb.REV16[x] * mul) % mod == res and gen_bomb.POP16[x] == pop
    ]

    if len(sols) != 1:
        print("seed %d: %d solutions %s" % (args.seed, len(sols), sols[:8]))
        return 1
    if sols[0] != ans["secret"]:
        print("seed %d: generator answer %d, exhaustive answer %d"
              % (args.seed, ans["secret"], sols[0]))
        return 1

    print("seed %d: secret answer %d is unique" % (args.seed, sols[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
