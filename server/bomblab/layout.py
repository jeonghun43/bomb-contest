"""
layout.py - Where each bomb lives in a student's home, and what students
call it.

    track     kind          label      home directory
    assign    cmu           bomb       ~/bomb        (scored, one per student)
    practice  cmu           practice   ~/practice    (reissued on request)
    drill     drill:dN      dN         ~/drills/dN   (reissued on request)
"""

import os

ASSIGN, PRACTICE, DRILL = "assign", "practice", "drill"
DRILL_KINDS = ["drill:d%d" % i for i in range(10)]
REISSUABLE = {PRACTICE, DRILL}


def label(track, kind):
    if track == ASSIGN:
        return "bomb"
    if track == PRACTICE:
        return "practice"
    return kind.split(":", 1)[1]


def parse_label(text):
    """'bomb' / 'practice' / 'd3' (or 'drill:d3') -> (track, kind), or None."""
    t = text.strip().lower()
    if t in ("bomb", "assign"):
        return ASSIGN, "cmu"
    if t == "practice":
        return PRACTICE, "cmu"
    if t.startswith("drill:"):
        t = t[6:]
    if "drill:" + t in DRILL_KINDS:
        return DRILL, "drill:" + t
    return None


def rel_dir(track, kind):
    """Install directory relative to the home directory."""
    if track == ASSIGN:
        return "bomb"
    if track == PRACTICE:
        return "practice"
    return os.path.join("drills", label(track, kind))


def install_dir(home, track, kind):
    return os.path.join(home, rel_dir(track, kind))


def all_slots():
    """Every (track, kind) a provisioned student gets."""
    return [(ASSIGN, "cmu"), (PRACTICE, "cmu")] + \
        [(DRILL, k) for k in DRILL_KINDS]
