#!/usr/bin/env python3
"""
buildbomb.py - Generate, compile and check bombs with the original's
toolchain (specs/003-practice-bank plan section 6).

    buildbomb.py --kind cmu --seed 7 --out build/cmu-7
    buildbomb.py --kind drill:d3 --seed 7 --out DIR --force s2=addi
    buildbomb.py --kind cmu --seed 7 --out DIR --notify --bomb-id <hex16>
    buildbomb.py --src DIR [DIR ...]        compile already-rendered dirs

Pipeline:  bank.build(kind, seed) -> bank.render -> DIR
           -> one bomblab-gcc48 container runs Makefile.bomb in every DIR
           -> tools/elfcheck.py on every DIR/bomb

All compilation happens in the container; there is deliberately no host-gcc
path. Several directories are built by a single container run, which matters
for verification (hundreds of bombs). Output files are owned by the invoking
user. Used by the top-level Makefile, bomblabctl and the builder service.

Standard library only (plus docker and binutils on PATH).
"""

import argparse
import json
import os
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CSRC = os.path.join(ROOT, "bank", "csrc")
IMAGE = os.environ.get("BOMBLAB_IMAGE", "bomblab-gcc48")

sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import elfcheck  # noqa: E402


class BuildError(Exception):
    pass


# --------------------------------------------------------------------------
# generate
# --------------------------------------------------------------------------

def render(kind, seed, out, force=None):
    """Write a complete bomb source directory for (kind, seed) into out."""
    try:
        import bank
    except ImportError:
        bank = None
    # bank/ exists from Phase A on (csrc only), so a bare import can succeed
    # as an empty namespace package before the generator is written.
    if not hasattr(bank, "build"):
        raise BuildError("bank generator not available yet "
                         "(specs/003 Phase C); use --src for now")
    bomb = bank.build(kind, seed, force=force)
    bank.render.write(bomb, out)
    return bomb


# --------------------------------------------------------------------------
# compile
# --------------------------------------------------------------------------

def compile_dirs(dirs, notify=None, image=IMAGE):
    """
    Compile every rendered directory in one container run.
    notify: None for offline bombs; dict(bomb_id=..., socket=...) for one
    server-mode setting applied to every dir; or {dir: that dict} to give
    each dir its own bomb id (provisioning many students at once).
    """
    dirs = [os.path.abspath(d) for d in dirs]
    for d in dirs:
        if not os.path.isfile(os.path.join(d, "bomb.c")):
            raise BuildError("%s: no bomb.c (not a rendered bomb dir)" % d)
    root = os.path.commonpath(dirs)
    if len(dirs) == 1:
        root = os.path.dirname(dirs[0])

    def make_args(d):
        n = notify
        if isinstance(notify, dict) and "bomb_id" not in notify:
            n = {os.path.abspath(k): v for k, v in notify.items()}.get(d)
        if not n:
            return ""
        return " ".join(shlex.quote(a) for a in [
            "NOTIFY=1", "BOMB_ID=%s" % n["bomb_id"],
            "NOTIFY_SOCKET=%s" % n["socket"]])

    make = "make -s -f /mk/Makefile.bomb"
    script = " && ".join(
        "%s -C %s clean >/dev/null && %s -C %s %s"
        % (make, shlex.quote("/work/" + os.path.relpath(d, root)),
           make, shlex.quote("/work/" + os.path.relpath(d, root)),
           make_args(d))
        for d in dirs)

    cmd = ["docker", "run", "--rm",
           "--user", "%d:%d" % (os.getuid(), os.getgid()),
           "-v", "%s:/work" % root,
           "-v", "%s:/mk:ro" % CSRC,
           image, "bash", "-c", script]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise BuildError("docker not found on PATH")
    if r.returncode != 0:
        raise BuildError("compile failed:\n%s%s" % (r.stdout, r.stderr))


# --------------------------------------------------------------------------
# check
# --------------------------------------------------------------------------

def expected_canary(d):
    """manifest.json may pin the exact canary set for this bomb."""
    path = os.path.join(d, "manifest.json")
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f).get("canary")
    return None


def check_dirs(dirs):
    bad = []
    for d in dirs:
        fails = elfcheck.check(os.path.join(d, "bomb"), expected_canary(d))
        if fails:
            bad.append((d, fails))
    if bad:
        raise BuildError("elfcheck failed:\n" + "\n".join(
            "  %s\n    %s" % (d, "\n    ".join(f)) for d, f in bad))


# --------------------------------------------------------------------------

def parse_force(items):
    force = {}
    for item in items or []:
        slot, _, variant = item.partition("=")
        if not variant:
            raise BuildError("--force wants slot=variant, got %r" % item)
        force[slot] = variant
    return force


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build bombs with the original CMU toolchain.")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--kind", help="cmu | drill:d0 .. drill:d9")
    src.add_argument("--src", nargs="+", metavar="DIR",
                     help="compile already-rendered bomb directories")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--out", help="output directory (with --kind)")
    ap.add_argument("--force", action="append", metavar="SLOT=VARIANT",
                    help="pin a variant family (verification)")
    ap.add_argument("--notify", action="store_true",
                    help="server-mode bomb that reports to the record daemon")
    ap.add_argument("--bomb-id")
    ap.add_argument("--socket", default="/run/bomblab/report.sock")
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--no-check", action="store_true",
                    help="skip elfcheck (debugging only)")
    args = ap.parse_args(argv)

    notify = None
    if args.notify:
        if not args.bomb_id:
            ap.error("--notify requires --bomb-id")
        notify = {"bomb_id": args.bomb_id, "socket": args.socket}

    try:
        if args.kind:
            if args.seed is None or not args.out:
                ap.error("--kind requires --seed and --out")
            render(args.kind, args.seed, args.out, parse_force(args.force))
            dirs = [args.out]
        else:
            dirs = args.src
        compile_dirs(dirs, notify, args.image)
        if not args.no_check:
            check_dirs(dirs)
    except BuildError as e:
        print("buildbomb: %s" % e, file=sys.stderr)
        return 1

    for d in dirs:
        print(os.path.join(d, "bomb"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
