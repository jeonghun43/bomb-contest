#!/usr/bin/env python3
"""
asmdiff.py - Compare functions of two x86-64 ELF binaries instruction by
instruction, ignoring addresses.

    python3 tools/asmdiff.py [--mask-imm] [--data] ORIGINAL BUILT [func ...]

Used for the toolchain calibration and the parity check in
specs/003-practice-bank (AC-05). With no function names, every function
defined in both binaries is compared.

Normalisation (always):
  - a branch inside the function    -> L+<offset>   (--mask-imm: @<index>)
  - a call or jump outside it       -> callee symbol (PLT via .rela.plt)
  - an address that falls in a data symbol, whether rip-relative, an
    absolute immediate or a memory displacement -> that symbol's name
    (compiler-numbered statics such as array.3449 lose the number)
  - any other address >= 0x400000   -> ADDR

--mask-imm  also hides every remaining immediate operand, so two builds of
            the same code with different seeded constants compare equal.
            Branch targets become instruction indices because a different
            constant can change an instruction's encoded length.
--data      also compare the order of data symbols (user objects only).

Dev-machine tool: requires `pip install capstone pyelftools`. The server and
the build pipeline do not depend on it (see tools/elfcheck.py).
"""

import argparse
import re
import sys

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG
from elftools.elf.elffile import ELFFile
from elftools.elf.relocation import RelocationSection

ADDR_MIN = 0x400000
SIZE_NAME = {1: "byte", 2: "word", 4: "dword", 8: "qword", 10: "tbyte",
             16: "xmmword"}
# crt / libc objects that are not part of the bomb's own data layout
CRT_OBJECT = re.compile(r"^(_|completed\.|std(in|out|err)$|.*@)")


class Binary:
    def __init__(self, path):
        self.path = path
        self.elf = ELFFile(open(path, "rb"))
        self.text = self.elf.get_section_by_name(".text")
        self.funcs = {}
        self.by_addr = {}
        self.objects = []
        for s in self.elf.get_section_by_name(".symtab").iter_symbols():
            if not s.name or not s["st_value"]:
                continue
            kind = s["st_info"]["type"]
            if kind == "STT_FUNC":
                self.funcs[s.name] = (s["st_value"], s["st_size"])
                self.by_addr[s["st_value"]] = s.name
            elif kind == "STT_OBJECT":
                self.objects.append((s["st_value"], max(s["st_size"], 1),
                                     s.name.split("@")[0], s["st_size"]))
        # Linker markers such as __TMC_END__ (size 0) can share an address
        # with a real variable (stdout); sort so the real one wins a lookup.
        self.objects.sort(key=lambda o: (o[0], o[3] == 0,
                                         o[2].startswith("__"), o[2]))
        self._plt()
        self.md = Cs(CS_ARCH_X86, CS_MODE_64)
        self.md.detail = True

    def _plt(self):
        plt = self.elf.get_section_by_name(".plt")
        rela = self.elf.get_section_by_name(".rela.plt")
        if plt is None or not isinstance(rela, RelocationSection):
            return
        dynsym = self.elf.get_section(rela["sh_link"])
        for i, r in enumerate(rela.iter_relocations()):
            name = dynsym.get_symbol(r["r_info_sym"]).name
            self.by_addr[plt["sh_addr"] + 16 * (i + 1)] = name + "@plt"

    # ---- data layout ------------------------------------------------------

    def data_name(self, addr):
        """Address -> data symbol(+offset), or None."""
        for start, size, name, _ in self.objects:
            if start <= addr < start + size:
                name = re.sub(r"\.\d+$", "", name)
                return name if addr == start else "%s+%d" % (name,
                                                             addr - start)
        return None

    def data_order(self):
        return [re.sub(r"\.\d+$", "", n) for _, _, n, _ in self.objects
                if not CRT_OBJECT.match(n)]

    # ---- code -------------------------------------------------------------

    def disasm(self, name, mask_imm):
        addr, size = self.funcs[name]
        off = addr - self.text["sh_addr"]
        insns = list(self.md.disasm(self.text.data()[off:off + size], addr))
        index = {ins.address: i for i, ins in enumerate(insns)}
        return [self._norm(ins, addr, size, index, mask_imm) for ins in insns]

    def _addr(self, value):
        name = self.data_name(value)
        if name:
            return name
        if value >= ADDR_MIN:
            return "ADDR"
        return None

    def _norm(self, ins, base, size, index, mask_imm):
        mn = ins.mnemonic
        if (mn.startswith("j") or mn == "call") and len(ins.operands) == 1 \
                and ins.operands[0].type == X86_OP_IMM:
            t = ins.operands[0].imm
            if base <= t < base + size:
                where = ("@%d" % index[t]) if mask_imm else \
                        ("L+%#x" % (t - base))
            else:
                where = self.by_addr.get(t, "?%#x" % t)
            return "%s %s" % (mn, where)

        ops = []
        for op in ins.operands:
            if op.type == X86_OP_REG:
                ops.append(ins.reg_name(op.reg))
            elif op.type == X86_OP_IMM:
                name = self._addr(op.imm & 0xFFFFFFFFFFFFFFFF)
                if name:
                    ops.append(name)
                elif mask_imm:
                    ops.append("IMM")
                else:
                    ops.append(hex(op.imm))
            elif op.type == X86_OP_MEM:
                ops.append(self._mem(ins, op))
        return ("%s %s" % (mn, ", ".join(ops))).strip()

    def _mem(self, ins, op):
        m = op.mem
        seg = ins.reg_name(m.segment) + ":" if m.segment else ""
        size = SIZE_NAME.get(op.size, "%dB" % op.size)
        if m.base and ins.reg_name(m.base) == "rip":
            target = ins.address + ins.size + m.disp
            return "%s ptr %s[%s]" % (size, seg,
                                      self._addr(target) or "?rip")
        parts = []
        if m.base:
            parts.append(ins.reg_name(m.base))
        if m.index:
            parts.append("%s*%d" % (ins.reg_name(m.index), m.scale))
        if m.disp:
            name = self._addr(m.disp & 0xFFFFFFFFFFFFFFFF) \
                if m.disp >= ADDR_MIN else None
            parts.append(name or hex(m.disp))
        return "%s ptr %s[%s]" % (size, seg, " + ".join(parts) or "0")


def compare_funcs(a, b, funcs, mask_imm, out):
    bad = 0
    for f in funcs:
        if f not in a.funcs or f not in b.funcs:
            out("%-22s MISSING" % f)
            bad += 1
            continue
        x, y = a.disasm(f, mask_imm), b.disasm(f, mask_imm)
        if x == y:
            out("%-22s OK    (%d insns)" % (f, len(x)))
            continue
        bad += 1
        out("%-22s DIFF  (%d vs %d insns)" % (f, len(x), len(y)))
        for i in range(max(len(x), len(y))):
            l = x[i] if i < len(x) else ""
            r = y[i] if i < len(y) else ""
            out("    %s %-46s | %s" % ("  " if l == r else "!!", l, r))
    return bad


def compare_data(a, b, out):
    x, y = a.data_order(), b.data_order()
    common = [n for n in x if n in y]
    xo = [n for n in x if n in common]
    yo = [n for n in y if n in common]
    if xo == yo:
        out("data order             OK    (%d symbols)" % len(common))
        return 0
    out("data order             DIFF")
    out("    original: %s" % " ".join(xo))
    out("    built:    %s" % " ".join(yo))
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mask-imm", action="store_true")
    ap.add_argument("--data", action="store_true")
    ap.add_argument("original")
    ap.add_argument("built")
    ap.add_argument("funcs", nargs="*")
    args = ap.parse_args(argv)

    a, b = Binary(args.original), Binary(args.built)
    funcs = args.funcs or sorted(set(a.funcs) & set(b.funcs))
    bad = compare_funcs(a, b, funcs, args.mask_imm, print)
    total = len(funcs)
    if args.data:
        bad += compare_data(a, b, print)
        total += 1
    print("\n%d/%d checks differ" % (bad, total))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
