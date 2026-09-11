"""
web.py - Public scoreboard + operator admin over HTTP.

Binds to 127.0.0.1 (nginx fronts it). The admin views require HTTP Basic auth
checked in-app, because contestants share the host and could otherwise reach
127.0.0.1:PORT directly. The database is opened read-only.

Run:  python3 -m bomblab.web
"""

import base64
import datetime
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import config, scoring
from .db import Database

_HERE = os.path.dirname(os.path.abspath(__file__))
_TPL = os.path.join(_HERE, "templates")


def _template(name):
    with open(os.path.join(_TPL, name), encoding="utf-8") as f:
        return f.read()


def _iso(ts):
    if not ts:
        return None
    return datetime.datetime.fromtimestamp(
        ts, datetime.timezone.utc).astimezone().strftime("%H:%M:%S")


def _asctime(ts):
    # "Sat Aug 29 14:01:31 2026" in the server's local time, matching the
    # classic CMU bomblab scoreboard.
    if not ts:
        return "-"
    return time.strftime("%a %b %e %H:%M:%S %Y", time.localtime(ts))


class Handler(BaseHTTPRequestHandler):
    server_version = "bomblab/1.0"

    def log_message(self, *args):
        pass  # quiet

    # ---- helpers ----
    def _send(self, code, body, ctype="text/html; charset=utf-8", extra=None):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj):
        self._send(200, json.dumps(obj), "application/json")

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

    # ---- data ----
    def _scoreboard(self, public):
        cfg = self.server.cfg
        db = Database(cfg.db, readonly=True)
        try:
            override = db.get_setting("override", "auto")
            state = cfg.state(override)
            cut = scoring.cutoff_for(cfg, override, public=public)
            users = db.all_users()
            events = db.all_events()
            rows = scoring.score_rows(cfg, users, events, cut)
        finally:
            db.close()

        # Per-user last scoring event within the cutoff: its time drives the
        # "Submission date" column and its kind drives Status (valid/invalid).
        last = {}
        for e in events:
            if e["late"] or e["created_at"] > cut:
                continue
            if e["kind"] not in ("defused", "invalid", "exploded"):
                continue
            u = e["username"]
            if u not in last or e["created_at"] > last[u][0]:
                last[u] = (e["created_at"], e["kind"])

        out = []
        summary = {p: 0 for p in range(1, 8)}
        fully = 0
        for r in rows:
            for p in r["phases"]:
                summary[p] += 1
            if all(p in r["phases"] for p in range(1, 7)):
                fully += 1
            lt, lk = last.get(r["username"], (0, ""))
            out.append({
                "rank": r["rank"],
                "nickname": r["nickname"],
                "username": r["username"],   # the "bomb number", e.g. bomb07
                # dict form for the admin per-phase view
                "phases": {str(p): _iso(ts) for p, ts in r["phases"].items()},
                # scalar forms for the CMU-style public board
                "pcount": len(r["phases"]),
                "submission": _asctime(lt),
                "status": "invalid" if lk == "invalid" else "valid",
                "explosions": r["explosions"],
                "score": r["score"],
            })
        return {"state": state, "frozen": state == config.FROZEN,
                "public": public, "contest": cfg.name,
                "updated": _asctime(time.time()),
                "summary": {str(p): summary[p] for p in range(1, 8)},
                "fully": fully, "total": len(users), "rows": out}

    def _feed(self, public, admin):
        cfg = self.server.cfg
        db = Database(cfg.db, readonly=True)
        try:
            override = db.get_setting("override", "auto")
            cut = scoring.cutoff_for(cfg, override, public=public)
            events = db.all_events()
        finally:
            db.close()
        items = []
        for e in reversed(events):
            if e["kind"] not in ("defused", "exploded", "invalid"):
                continue
            if not admin and (e["late"] or e["created_at"] > cut):
                continue
            item = {
                "time": _iso(e["created_at"]),
                "nickname": e["nickname"],
                "phase": e["phase"],
                "kind": e["kind"],
            }
            if admin:
                item["username"] = e["username"]
                item["input"] = e["input"]
                item["late"] = bool(e["late"])
            items.append(item)
            if len(items) >= (2000 if admin else 40):
                break
        return {"events": items}

    # ---- routing ----
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/" or path == "/index.html":
            self._send(200, _template("scoreboard.html"))
        elif path == "/api/scoreboard":
            self._json(self._scoreboard(public=True))
        elif path == "/api/feed":
            self._json(self._feed(public=True, admin=False))
        elif path == "/admin":
            if self._require_admin():
                self._send(200, _template("admin.html"))
        elif path == "/api/admin/scoreboard":
            if self._require_admin():
                self._json(self._scoreboard(public=False))
        elif path == "/api/admin/feed":
            if self._require_admin():
                self._json(self._feed(public=False, admin=True))
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
