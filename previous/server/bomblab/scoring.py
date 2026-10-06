"""
scoring.py - Turn the event log into a ranked scoreboard.

Only DEFUSED and (INVALID + EXPLODED) events with late=0 and created_at within
the cutoff count. The cutoff differs by audience: the public board freezes at
freeze_at while a frozen contest is on; the operator board always uses now.
"""

from . import config


def cutoff_for(cfg, override, public):
    """Timestamp up to which events count for this audience."""
    state = cfg.state(override)
    if public and state == config.FROZEN and cfg.freeze_at:
        return cfg.freeze_at.timestamp()
    return config.now().timestamp()


def score_rows(cfg, users, events, cutoff_ts):
    """
    Compute a list of per-user score dicts, ranked. `events` is every event;
    we filter to scoring events at or before cutoff_ts with late=0.
    """
    by_user = {u["id"]: {
        "username": u["username"],
        "nickname": u["nickname"],
        "defused": {},      # phase -> first defuse timestamp
        "explosions": 0,
    } for u in users}

    for e in events:
        if e["late"]:
            continue
        if e["created_at"] > cutoff_ts:
            continue
        rec = by_user.get(e["user_id"])
        if rec is None:
            continue
        if e["kind"] == "defused":
            ph = e["phase"]
            if ph not in rec["defused"]:
                rec["defused"][ph] = e["created_at"]
        elif e["kind"] in ("exploded", "invalid"):
            rec["explosions"] += 1

    rows = []
    for rec in by_user.values():
        phase_score = 0
        last_gain = 0.0
        for ph, ts in rec["defused"].items():
            if 1 <= ph <= 6:
                phase_score += cfg.phase_points[ph - 1]
            elif ph == 7:
                phase_score += cfg.secret_points
            last_gain = max(last_gain, ts)
        penalty = min(rec["explosions"] * cfg.explosion_penalty,
                      cfg.max_penalty)
        rows.append({
            "username": rec["username"],
            "nickname": rec["nickname"],
            "phases": {ph: rec["defused"][ph] for ph in rec["defused"]},
            "explosions": rec["explosions"],
            "score": round(phase_score - penalty, 2),
            "last_gain": last_gain,
        })

    # Rank: score desc, then earliest last-gain (finished sooner) first.
    rows.sort(key=lambda r: (-r["score"],
                             r["last_gain"] if r["last_gain"] else float("inf")))
    rank = 0
    prev = None
    for i, r in enumerate(rows):
        key = (r["score"], r["last_gain"])
        if key != prev:
            rank = i + 1
            prev = key
        r["rank"] = rank
    return rows
