"""
drills - concept drills (Lv.1): small three-phase bombs, one idea each.

Each drill module defines ID ('d0'..'d9'), TITLE, STAGES = [(slot,
{variant: generator})] for s1, s2, s3 (and 'secret' for D9), and optionally
SECRET_LINE / SECRET_WORDS. build() here turns that into a Bomb.
See specs/003-practice-bank spec section 9.
"""

import importlib

from ..core import BankError, Bomb, rng

DRILL_IDS = ["d0", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9"]
BUILDERS = {}
_MODULES = {}


def _register(mod):
    kind = "drill:" + mod.ID
    _MODULES[kind] = mod

    def builder(seed, force=None, mod=mod, kind=kind):
        return build(mod, kind, seed, force)

    BUILDERS[kind] = builder


def build(mod, kind, seed, force=None):
    force = dict(force or {})
    phases = []
    for slot, families in mod.STAGES:
        names = sorted(families)
        if slot in force:
            name = force.pop(slot)
            if name not in families:
                raise BankError("%s %s: no variant %r" % (kind, slot, name))
        else:
            name = rng(kind, seed, slot, "variant").choice(names)
        phases.append(families[name](rng(kind, seed, slot, name)))
    if force:
        raise BankError("%s: unknown slot(s) %s" % (kind, ", ".join(sorted(force))))

    has_secret = len(phases) == 4
    word = ""
    if has_secret:
        word = rng(kind, seed, "secret-word").choice(mod.SECRET_WORDS)
    return Bomb(kind, seed, phases, main="drill_main.c", num_phases=3,
                has_secret=has_secret,
                secret_line=getattr(mod, "SECRET_LINE", 1),
                secret_word=word, drill_id=mod.ID.upper(),
                drill_title=mod.TITLE_EN, title="개념 드릴 %s: %s"
                % (mod.ID.upper(), mod.TITLE))


def variants(kind):
    mod = _MODULES.get(kind)
    if mod is None:
        raise BankError("unknown kind %r" % kind)
    return {slot: sorted(fams) for slot, fams in mod.STAGES}


for _id in DRILL_IDS:
    _register(importlib.import_module("." + _id, __name__))
