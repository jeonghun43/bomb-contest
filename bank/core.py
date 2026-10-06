"""
core.py - What a generated bomb is.

A Bomb is fully determined by (kind, seed). Every phase records the C
template that implements it, the macro values that template reads from the
generated bombdata.h, one valid answer, a judge for any input line, and the
write-ups shown to students and operators.
"""

import random
import re

PLACEHOLDER = re.compile(r"<<[a-z_]+>>")


class BankError(Exception):
    pass


class Raw:
    """A macro value emitted verbatim (a C expression such as &item4)."""

    def __init__(self, text):
        self.text = text


def fill(text, **values):
    """
    Replace <<name>> in a write-up with values[name]. Write-ups quote C and
    AT&T assembly, which are full of braces and percent signs, so neither
    str.format nor %-formatting is safe for them.
    """
    for k, v in values.items():
        text = text.replace("<<%s>>" % k, str(v))
    # C's << and >> operators are fine; only <<name>> means a missing value.
    m = PLACEHOLDER.search(text)
    if m:
        raise BankError("unfilled placeholder %s" % m.group())
    return text


def rng(kind, seed, *path):
    """
    Deterministic random stream for one part of one bomb. Each slot draws
    from its own stream, so changing how one phase is generated never shifts
    the constants of another. String seeds are hashed with SHA-512 by
    random.Random, which is stable across Python versions.
    """
    return random.Random("bank/%s/%d/%s" % (kind, seed, "/".join(path)))


class Phase:
    """
    One phase of a bomb.

    slot       'p1'..'p6' / 's1'..'s3' / 'secret'
    variant    family name within the slot, e.g. 'switch_dd'
    template   C source relative to bank/csrc, e.g. 'cmu/p3_switch_dd.c'
    macros     ordered [(NAME, value)] for bombdata.h; value is an int, a str
               (emitted as a C string literal), or a list (an initialiser)
    answer     one input line that defuses the phase
    check      callable(line) -> bool, the C semantics in Python (judge.py)
    canary     True if GCC 4.8 -fstack-protector guards the phase function
               (it has a char array on the stack)
    title      short Korean name of the phase
    answers    Korean description of every valid answer (operators)
    walkthrough Korean explanation of how to read the phase (students, after
               defusal; operators always)
    hints      three Korean hints, vaguest first
    """

    def __init__(self, slot, variant, template, macros, answer, check,
                 canary=False, title="", answers="", walkthrough="",
                 hints=None, extra_canary=()):
        self.slot = slot
        self.variant = variant
        self.template = template
        self.macros = list(macros)
        self.answer = answer
        self.check = check
        self.canary = canary
        self.extra_canary = tuple(extra_canary)
        self.title = title
        self.answers = answers
        self.walkthrough = walkthrough
        self.hints = list(hints or [])
        if len(self.hints) != 3:
            raise BankError("%s/%s: want three hints" % (slot, variant))


class Bomb:
    """
    kind        'cmu' or 'drill:d0' .. 'drill:d9'
    seed        int
    phases      Phase list: phases 1..num_phases, then the secret phase (if
                any) last
    main        'bomb.c' (CMU) or 'drill_main.c'
    secret_line 0-based input line whose extra token opens the secret phase
    secret_word that token
    """

    def __init__(self, kind, seed, phases, main="bomb.c", num_phases=6,
                 has_secret=False, secret_line=3, secret_word="",
                 drill_id="", drill_title="", title=""):
        self.kind = kind
        self.seed = seed
        self.phases = phases
        self.main = main
        self.num_phases = num_phases
        self.has_secret = has_secret
        self.secret_line = secret_line
        self.secret_word = secret_word
        self.drill_id = drill_id
        self.drill_title = drill_title
        self.title = title
        want = num_phases + (1 if has_secret else 0)
        if len(phases) != want:
            raise BankError("%s: %d phases, want %d" % (kind, len(phases), want))

    # ---- phases ------------------------------------------------------------

    def phase(self, number):
        """1-based phase number as reported by the bomb (secret = N+1)."""
        if 1 <= number <= len(self.phases):
            return self.phases[number - 1]
        return None

    @property
    def secret(self):
        return self.phases[-1] if self.has_secret else None

    def variants(self):
        return {p.slot: p.variant for p in self.phases}

    def canary_set(self):
        """Functions GCC 4.8 should guard with a stack canary."""
        out = set()
        for i, p in enumerate(self.phases):
            if p.canary:
                out.add("secret_phase" if p.slot == "secret"
                        else "phase_%d" % (i + 1))
            out.update(p.extra_canary)
        if self.has_secret:
            out.add("phase_defused")      # its char string[80]
        return sorted(out)

    # ---- answers -----------------------------------------------------------

    def answer_lines(self, with_secret=False):
        lines = [p.answer for p in self.phases[:self.num_phases]]
        if with_secret and self.has_secret:
            lines[self.secret_line] += " " + self.secret_word
            lines.append(self.secret.answer)
        return lines
