"""
bank - the Bomb Lab practice bank: generator and judge.

    import bank
    bomb = bank.build("cmu", 7)              # or "drill:d3"
    bank.render.write(bomb, "build/cmu-7")   # sources for tools/buildbomb.py
    bank.judge.check(bomb, 3, "0 207")       # what the server re-scores with

A bomb is a pure function of (kind, seed): the server stores only those two
and rebuilds the Bomb to re-score a reported input line.
See specs/003-practice-bank.
"""

from . import core, judge, render          # noqa: F401
from .core import BankError, Bomb, Phase   # noqa: F401
from . import cmu
from . import drills

_BUILDERS = {cmu.KIND: cmu.build}
_BUILDERS.update(drills.BUILDERS)


def kinds():
    """Every kind this bank can build, in a stable order."""
    return sorted(_BUILDERS, key=lambda k: (k != "cmu", k))


def build(kind, seed, force=None):
    """Bomb for (kind, seed). force pins variant families: {slot: variant}."""
    try:
        builder = _BUILDERS[kind]
    except KeyError:
        raise BankError("unknown kind %r (have %s)" % (kind, ", ".join(kinds())))
    if not isinstance(seed, int) or seed < 0:
        raise BankError("seed must be a non-negative int")
    return builder(seed, force)


def variants(kind):
    """{slot: [variant, ...]} for a kind (verification uses this)."""
    if kind == cmu.KIND:
        return cmu.variants()
    return drills.variants(kind)
