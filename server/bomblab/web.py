"""
web.py - Public scoreboard + operator admin over HTTP.

Binds to 127.0.0.1 (nginx fronts it). The admin views require HTTP Basic auth
checked in-app, because students share the host and could otherwise reach
127.0.0.1:PORT directly. The database is opened read-only.

The public board has the scored-bomb table (the original assignment's
scoreboard), a separate drill-progress table that never affects rank, and a
feed without input lines.

Run:  python3 -m bomblab.web
"""

import base64
import datetime
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import config, layout, scoring
from .db import Database

_HERE = os.path.dirname(os.path.abspath(__file__))
_TPL = os.path.join(_HERE, "templates")
DRILLS = [k.split(":")[1] for k in layout.DRILL_KINDS]
DRILL_STAGES = {d: 4 if d == "d9" else 3 for d in DRILLS}


def _template(name):
    with open(os.path.join(_TPL, name), encoding="utf-8") as f:
        return f.read()


def _hms(ts):
    if not ts:
        return None
    return datetime.datetime.fromtimestamp(
        ts, datetime.timezone.utc).astimezone().strftime("%m-%d %H:%M:%S")


def _asctime(ts):
    # "Sat Aug 29 14:01:31 2026", as on the classic CMU scoreboard.
    if not ts:
        return "-"
    return time.strftime("%a %b %e %H:%M:%S %Y", time.localtime(ts))


class Handler(BaseHTTPRequestHandler):
    server_version = "bomblab/2.0"

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj):
        self._send(200, json.dumps(obj, ensure_ascii=False),
                   "application/json; charset=utf-8")

    def _require_admin(self):
        cfg = self.server.cfg
        hdr = self.headers.get("Authorization", "")
        if hdr.startswith("Basic "):
            try:
                user, _, pw = base64.b64decode(hdr[6:]).decode().partition(":")
            except Exception:
                user, pw = "", ""
            if user == cfg.admin_user and cfg.check_admin_password(pw):
                return True
        self._send(401, "Authentication required",
                   extra={"WWW-Authenticate": 'Basic realm="bomblab admin"'})
        return False

    def _load(self):
        cfg = self.server.cfg
        db = Database(cfg.db, readonly=True)
        try:
            state = cfg.state(db.get_setting("override", "auto"))
            return state, db.all_users(), db.all_events()
        finally:
            db.close()

    # ---- data -----------------------------------------------------------

    def _scoreboard(self, admin):
        cfg = self.server.cfg
        state, users, events = self._load()
        rows = scoring.score_rows(cfg, users, events)
        drills = scoring.drill_progress(users, events)
        practice = scoring.practice_counts(users, events)

        summary = {p: 0 for p in range(1, 8)}
        fully = 0
        out = []
        for r in rows:
            for p in r["phases"]:
                if p in summary:
                    summary[p] += 1
            if all(p in r["phases"] for p in range(1, 7)):
                fully += 1
            lt, lk = r["last_event"]
            out.append({
                "rank": r["rank"],
                "nickname": r["nickname"],
                "username": r["username"],
                "phases": {str(p): _hms(ts) for p, ts in r["phases"].items()},
                "pcount": len([p for p in r["phases"] if 1 <= p <= 6]),
                "secret": scoring.SECRET in r["phases"],
                "submission": _asctime(lt),
                "status": "invalid" if lk == "invalid" else "valid",
                "explosions": r["explosions"],
                "score": r["score"],
            })
        drill_rows = [{
            "username": u["username"],
            "nickname": u["nickname"],
            "drills": {d: drills.get(u["username"], {}).get(d, [])
                       for d in DRILLS},
            "done": sum(1 for d in DRILLS
                        if len(drills.get(u["username"], {}).get(d, []))
                        >= DRILL_STAGES[d]),
            "practice": practice.get(u["username"], 0),
        } for u in users]
        return {"site": cfg.name, "state": state,
                "window": {"start": cfg.start_at.isoformat() if cfg.start_at
                           else None,
                           "end": cfg.end_at.isoformat() if cfg.end_at
                           else None},
                "updated": _asctime(time.time()),
                "summary": {str(p): summary[p] for p in range(1, 8)},
                "fully": fully, "total": len(users), "rows": out,
                "drill_stages": DRILL_STAGES, "drill_rows": drill_rows,
                "admin": admin}

    def _feed(self, admin, track=None):
        _, _, events = self._load()
        items = []
        for e in reversed(events):
            if e["kind"] not in ("defused", "exploded", "invalid"):
                continue
            if not admin and e["late"]:
                continue
            if track and e["track"] != track:
                continue
            item = {
                "time": _hms(e["created_at"]),
                "nickname": e["nickname"],
                "track": e["track"] or "legacy",
                "bomb": layout.label(e["track"], e["bomb_kind"])
                if e["track"] else "-",
                "phase": e["phase"],
                "kind": e["kind"],
            }
            if admin:
                item["username"] = e["username"]
                item["input"] = e["input"]
                item["late"] = bool(e["late"])
            items.append(item)
            if len(items) >= (3000 if admin else 40):
                break
        return {"events": items}

    # ---- routing --------------------------------------------------------

    def do_GET(self):
        url = urlparse(self.path)
        path = url.path
        q = parse_qs(url.query)
        track = (q.get("track") or [None])[0]
        if path in ("/", "/index.html"):
            self._send(200, _template("scoreboard.html"))
        elif path == "/api/scoreboard":
            self._json(self._scoreboard(admin=False))
        elif path == "/api/feed":
            self._json(self._feed(admin=False))
        elif path == "/admin":
            if self._require_admin():
                self._send(200, _template("admin.html"))
        elif path == "/api/admin/scoreboard":
            if self._require_admin():
                self._json(self._scoreboard(admin=True))
        elif path == "/api/admin/feed":
            if self._require_admin():
                self._json(self._feed(admin=True, track=track))
        else:
            self._send(404, "not found")


class WebServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, cfg):
        self.cfg = cfg
        super().__init__(cfg.listen_addr(), Handler)


def main():
    cfg = config.Config()
    WebServer(cfg).serve_forever()


if __name__ == "__main__":
    main()
