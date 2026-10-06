"""
scoring.py - Turn the event log into the scoreboard.

Only the scored bomb (track 'assign') earns points and loses them for
explosions, exactly like the original assignment: phases 1-6 and the secret
phase score per the config, each explosion (or invalid defusal claim) costs
the penalty, capped. Events recorded while the server was closed (late=1)
never count. If an operator reissued someone's scored bomb, phases defused on
the earlier one still count.

Drill and practice bombs never touch the score; drill_progress() and
practice_counts() summarise them for the separate tables.
"""

from . import layout

SECRET = 7


def score_rows(cfg, users, events):
    by_user = {u["id"]: {
        "username": u["username"],
        "nickname": u["nickname"],
        "defused": {},          # phase -> first defuse timestamp
        "explosions": 0,
        "last": (0.0, ""),      # last scoring event (time, kind)
    } for u in users}

    for e in events:
        if e["late"] or e["track"] != layout.ASSIGN:
            continue
        rec = by_user.get(e["user_id"])
        if rec is None:
            continue
        if e["kind"] == "defused":
            rec["defused"].setdefault(e["phase"], e["created_at"])
        elif e["kind"] in ("exploded", "invalid"):
            rec["explosions"] += 1
        if e["kind"] in ("defused", "exploded", "invalid"):
            rec["last"] = (e["created_at"], e["kind"])

    rows = []
    for rec in by_user.values():
        pts = 0
        last_gain = 0.0
        for ph, ts in rec["defused"].items():
            if 1 <= ph <= 6:
                pts += cfg.phase_points[ph - 1]
            elif ph == SECRET:
                pts += cfg.secret_points
            last_gain = max(last_gain, ts)
        penalty = min(rec["explosions"] * cfg.explosion_penalty,
                      cfg.max_penalty)
        rows.append({
            "username": rec["username"],
            "nickname": rec["nickname"],
            "phases": dict(rec["defused"]),
            "explosions": rec["explosions"],
            "score": round(pts - penalty, 2),
            "last_gain": last_gain,
            "last_event": rec["last"],
        })

    # Rank: score desc, then whoever reached it first.
    rows.sort(key=lambda r: (-r["score"],
                             r["last_gain"] if r["last_gain"] else float("inf"),
                             r["username"]))
    rank, prev = 0, None
    for i, r in enumerate(rows):
        key = (r["score"], r["last_gain"])
        if key != prev:
            rank, prev = i + 1, key
        r["rank"] = rank
    return rows


def drill_progress(users, events):
    """{username: {'d0': [stages defused], ...}} over every drill bomb."""
    out = {u["username"]: {} for u in users}
    for e in events:
        if e["late"] or e["track"] != layout.DRILL or e["kind"] != "defused":
            continue
        d = layout.label(e["track"], e["bomb_kind"])
        stages = out.setdefault(e["username"], {}).setdefault(d, [])
        if e["phase"] not in stages:
            stages.append(e["phase"])
    for per in out.values():
        for s in per.values():
            s.sort()
    return out


def practice_counts(users, events):
    """{username: practice bombs fully defused (all six phases)}."""
    per_bomb = {}
    owner = {}
    for e in events:
        if e["late"] or e["track"] != layout.PRACTICE or e["kind"] != "defused":
            continue
        per_bomb.setdefault(e["bomb_id"], set()).add(e["phase"])
        owner[e["bomb_id"]] = e["username"]
    out = {u["username"]: 0 for u in users}
    for bid, phases in per_bomb.items():
        if all(p in phases for p in range(1, 7)):
            out[owner[bid]] = out.get(owner[bid], 0) + 1
    return out
