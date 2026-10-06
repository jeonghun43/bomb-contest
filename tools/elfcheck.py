#!/usr/bin/env python3
"""
elfcheck.py - Check that a built bomb has the original CMU bomb's binary
properties (specs/003-practice-bank AC-05b, research.md section 1).

    python3 tools/elfcheck.py [--canary f1,f2,...] BOMB [BOMB ...]

Checks:
  exec        ELF64 ET_EXEC (non-PIE)
  symtab      not stripped (.symtab present)
  toolchain   .comment names GCC (Ubuntu 4.8.1-2ubuntu1~12.04) 4.8.1
  dwarf       exactly one compile unit, bomb.c, with the original producer
              string (-ggdb -O1 -fstack-protector ...)
  endbr64     no endbr64 anywhere in the code
  canary      with --canary (or a bomb's manifest.json), the set of functions
              that carry a stack canary must equal that list exactly; without
              one, phase_defused must have a canary, which proves
              -fstack-protector for any bomb with a CMU-style secret check.
              Reporting code is left out of the comparison: driverlib.c (the
              original's driverlib has canaries in init_driver and submitr,
              ours is a different implementation behind the same API), and in
              server builds send_msg / initialize_bomb, whose report buffers
              exist only there.

Not checked: the optimisation level of code without debug info cannot be read
from the binary. tools/parity.sh (instruction-shape comparison against the
original) covers that.

Standard library plus binutils (readelf, objdump) only, so the server can run
it before installing a bomb. Exit status 0 when every bomb passes.
"""

import argparse
import re
import struct
import subprocess
import sys

TOOLCHAIN = b"GCC: (Ubuntu 4.8.1-2ubuntu1~12.04) 4.8.1"
PRODUCER = "GNU C 4.8.1 -mtune=generic -march=x86-64 -ggdb -O1 -fstack-protector"
ET_EXEC = 2

# driverlib.c: the original's reporting library, and ours behind the same API.
DRIVERLIB = {"init_driver", "driver_post", "submitr", "rio_readlineb",
             "init_timeout", "sigalrm_handler", "notify_request", "chomp"}
# Server builds (-DNOTIFY) give these support.c functions reporting buffers,
# hence canaries; send_msg exists only in server builds.
NOTIFY_ONLY = {"send_msg", "initialize_bomb"}

FUNC_HDR = re.compile(r"^[0-9a-f]+ <([^>]+)>:$")
ATTR = re.compile(r"DW_AT_(name|producer)\s*:\s*(?:\(indirect[^)]*\):\s*)?(.*)$")


def sections(data):
    """name -> (offset, size) for every section of an ELF64 file."""
    shoff, = struct.unpack_from("<Q", data, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3A)
    hdrs = []
    for i in range(shnum):
        name, _, _, _, off, size = struct.unpack_from(
            "<IIQQQQ", data, shoff + i * shentsize)
        hdrs.append((name, off, size))
    stroff = hdrs[shstrndx][1]
    out = {}
    for name, off, size in hdrs:
        end = data.index(b"\0", stroff + name)
        out[data[stroff + name:end].decode()] = (off, size)
    return out


def compile_units(path):
    """[(name, producer)] from readelf's DWARF dump."""
    txt = subprocess.run(["readelf", "--debug-dump=info", path],
                         capture_output=True, text=True).stdout
    units = []
    cur = None
    for line in txt.splitlines():
        if "DW_TAG_compile_unit" in line:
            cur = {}
            units.append(cur)
            continue
        if "Abbrev Number" in line:
            cur = None                      # left the CU's own attributes
            continue
        if cur is not None:
            m = ATTR.search(line)
            if m:
                cur[m.group(1)] = m.group(2).strip()
    return [(u.get("name"), u.get("producer")) for u in units]


def code_facts(path):
    """(functions with a stack canary, functions containing endbr64,
    every function seen)."""
    txt = subprocess.run(["objdump", "-d", "--no-show-raw-insn", path],
                         capture_output=True, text=True).stdout
    canary, endbr, funcs = set(), set(), set()
    func = None
    for line in txt.splitlines():
        m = FUNC_HDR.match(line)
        if m:
            func = m.group(1)
            funcs.add(func)
            continue
        if func is None:
            continue
        if "%fs:0x28" in line:
            canary.add(func)
        if "endbr64" in line:
            endbr.add(func)
    return canary, endbr, funcs


def check(path, expect_canary=None):
    """Return a list of failure strings (empty when the bomb passes)."""
    fails = []
    with open(path, "rb") as f:
        data = f.read()

    if data[:4] != b"\x7fELF" or data[4] != 2:
        return ["exec: not an ELF64 file"]
    e_type, = struct.unpack_from("<H", data, 16)
    if e_type != ET_EXEC:
        fails.append("exec: e_type=%d, want ET_EXEC (non-PIE)" % e_type)

    secs = sections(data)
    if ".symtab" not in secs:
        fails.append("symtab: binary is stripped")

    off, size = secs.get(".comment", (0, 0))
    if TOOLCHAIN not in data[off:off + size]:
        fails.append("toolchain: .comment lacks %s" % TOOLCHAIN.decode())

    units = compile_units(path)
    if [u[0] for u in units] != ["bomb.c"]:
        fails.append("dwarf: compile units %s, want ['bomb.c']"
                     % [u[0] for u in units])
    elif units[0][1] != PRODUCER:
        fails.append("dwarf: producer %r, want %r" % (units[0][1], PRODUCER))

    canary, endbr, funcs = code_facts(path)
    canary -= DRIVERLIB
    if "send_msg" in funcs:
        canary -= NOTIFY_ONLY
    if endbr:
        fails.append("endbr64: found in %s" % ", ".join(sorted(endbr)))
    if expect_canary is None and "phase_defused" not in canary:
        # Without an explicit expectation, a CMU-style phase_defused (with its
        # secret-token buffer) is the proof that -fstack-protector was on.
        fails.append("canary: phase_defused has none (-fstack-protector off?)")
    if expect_canary is not None and canary != set(expect_canary):
        fails.append("canary: functions %s, want %s"
                     % (sorted(canary), sorted(expect_canary)))
    return fails


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check bomb binary properties.")
    ap.add_argument("--canary", help="exact comma-separated list of functions "
                    "that must carry a stack canary")
    ap.add_argument("bombs", nargs="+")
    args = ap.parse_args(argv)
    expect = args.canary.split(",") if args.canary else None

    bad = 0
    for b in args.bombs:
        fails = check(b, expect)
        if fails:
            bad += 1
            print("FAIL %s" % b)
            for f in fails:
                print("     %s" % f)
        else:
            print("ok   %s" % b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
