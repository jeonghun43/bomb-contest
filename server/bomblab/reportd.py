"""
reportd.py - Record daemon on the local Unix socket.

The connecting process's uid comes from the kernel (SO_PEERCRED), so a
student can only ever act as themselves. Requests are one line each:

    HELLO <bomb_id>                     -> OK | CLOSED <why> | ERR <why>
    EVENT <bomb_id> <defused|exploded> <phase> [<hexinput>]   -> OK | ERR <why>
    STATUS                              -> OK <json>
    NOTES <bomb_id> <stage>             -> OK <n>\\n<n bytes> | LOCKED <why>
    HINT  <bomb_id> <stage> <k>         -> OK <n>\\n<n bytes> | LOCKED <why>
    NEW   <practice | dN>               -> OK <request id> | ERR <why>
    REQ   <request id>                  -> PENDING | DONE <path> | FAILED <why>

A "defused" claim is re-scored with bank.judge on the bomb's own (kind, seed)
before it counts; a failed claim is recorded as INVALID and counts as an
explosion. EVENT replies never reveal whether a claim was valid. Only the
student's active bombs are accepted. Write-ups and hints (drill and practice
bombs only) are read from the bomb's build directory, which students cannot
read themselves.

Run:  python3 -m bomblab.reportd
"""

import binascii
import collections
import json
import os
import socket
import socketserver
import struct
import sys
import threading

from . import config, layout
from .db import Database

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)
import bank  # noqa: E402

MAX_LINE = 512


class BombCache:
    """bank.build is deterministic, so keep recent Bombs by (kind, seed)."""

    def __init__(self, size=512):
        self.size = size
        self.items = collections.OrderedDict()

    def get(self, kind, seed):
        key = (kind, seed)
        b = self.items.get(key)
        if b is None:
            b = bank.build(kind, seed)
            self.items[key] = b
            if len(self.items) > self.size:
                self.items.popitem(last=False)
        else:
            self.items.move_to_end(key)
        return b


class Handler(socketserver.StreamRequestHandler):
    timeout = 5

    def _peer(self):
        creds = self.request.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, _ = struct.unpack("3i", creds)
        return pid, uid

    def _reply(self, text):
        self.wfile.write(text.encode("utf-8") + b"\n")

    def _reply_body(self, body):
        data = body.encode("utf-8")
        self.wfile.write(b"OK %d\n" % len(data) + data)

    def handle(self):
        srv = self.server
        try:
            pid, uid = self._peer()
        except OSError:
            self._reply("ERR no peer")
            return
        raw = self.rfile.readline(MAX_LINE)
        parts = raw.decode("latin-1").strip().split()
        if not parts:
            self._reply("ERR empty")
            return
        with srv.lock:                 # one SQLite connection, many threads
            user = srv.db.user_by_uid(uid)
            if user is None:
                self._reply("ERR unknown user")
                return
            cmd = parts[0].upper()
            fn = getattr(self, "cmd_" + cmd.lower(), None)
            if fn is None:
                self._reply("ERR bad command")
                return
            fn(user, pid, parts[1:])

    # ---- helpers --------------------------------------------------------

    def _state(self):
        srv = self.server
        return srv.cfg.state(srv.db.get_setting("override", "auto"))

    def _my_bomb(self, user, bomb_id, active=True):
        b = self.server.db.bomb_by_id(bomb_id)
        if b is None or b["user_id"] != user["id"]:
            return None
        if active and not b["active"]:
            return None
        return b

    def _bomb_file(self, bomb_id, *path):
        p = os.path.join(self.server.cfg.bombs_dir, bomb_id, *path)
        with open(p, encoding="utf-8") as f:
            return f.read()

    # ---- bomb reports ---------------------------------------------------

    def cmd_hello(self, user, pid, args):
        db = self.server.db
        b = self._my_bomb(user, args[0]) if len(args) == 1 else None
        if b is None:
            self._reply("ERR bad bomb")
            return
        db.add_event(user["id"], b["bomb_id"], 0, "hello", None, pid)
        if self._state() == config.OPEN:
            self._reply("OK")
        else:
            self._reply("CLOSED the practice server is closed")

    def cmd_event(self, user, pid, args):
        srv = self.server
        db = srv.db
        b = self._my_bomb(user, args[0]) if len(args) >= 3 else None
        if b is None:
            self._reply("ERR bad bomb")
            return
        kind = args[1]
        try:
            phase = int(args[2])
        except ValueError:
            self._reply("ERR bad phase")
            return
        try:
            bomb = srv.bombs.get(b["kind"], b["seed"])
        except bank.BankError:
            self._reply("ERR unknown bomb kind")
            return
        if kind not in ("defused", "exploded") or \
                not 1 <= phase <= len(bomb.phases):
            self._reply("ERR bad event")
            return

        if db.count_recent(user["id"], 60) >= srv.cfg.events_per_minute:
            db.add_event(user["id"], b["bomb_id"], phase, "rejected", None, pid)
            self._reply("ERR rate limit")
            return

        line = ""
        if len(args) >= 4:
            try:
                line = binascii.unhexlify(args[3]).decode("latin-1")
            except (binascii.Error, ValueError):
                line = ""

        late = 0 if self._state() == config.OPEN else 1
        if kind == "defused":
            recorded = "defused" if bank.judge.check(bomb, phase, line) \
                else "invalid"
        else:
            recorded = "exploded"
        db.add_event(user["id"], b["bomb_id"], phase, recorded, line, pid, late)
        self._reply("OK")              # never reveal validity

    # ---- student CLI ----------------------------------------------------

    def cmd_status(self, user, pid, args):
        srv = self.server
        db = srv.db
        out = []
        for b in db.bombs_of(user["id"]):
            if b["kind"] not in bank.kinds():
                continue
            bomb = srv.bombs.get(b["kind"], b["seed"])
            defused = sorted(db.defused_phases(b["bomb_id"]))
            reissuable = b["track"] in layout.REISSUABLE
            out.append({
                "label": layout.label(b["track"], b["kind"]),
                "track": b["track"],
                "kind": b["kind"],
                "title": bomb.title,
                "bomb_id": b["bomb_id"],
                "dir": "~/" + layout.rel_dir(b["track"], b["kind"]),
                "phases": len(bomb.phases),
                "num_phases": bomb.num_phases,
                "defused": defused,
                "explosions": db.explosions(b["bomb_id"]),
                "notes": defused if reissuable else [],
                "hints": {str(s): sorted(db.hints_opened(b["bomb_id"], s))
                          for s in range(1, len(bomb.phases) + 1)}
                if reissuable else {},
            })
        reqs = [{"id": r["id"], "kind": r["kind"], "status": r["status"]}
                for r in db.open_requests(user["id"])]
        self._reply("OK " + json.dumps({"user": user["username"],
                                        "state": self._state(),
                                        "bombs": out, "requests": reqs},
                                       ensure_ascii=False))

    def _stage_args(self, user, args, n):
        if len(args) != n:
            return None, None
        b = self._my_bomb(user, args[0])
        try:
            stage = int(args[1])
        except ValueError:
            return None, None
        return b, stage

    def cmd_notes(self, user, pid, args):
        b, stage = self._stage_args(user, args, 2)
        if b is None:
            self._reply("LOCKED no such bomb")
            return
        if b["track"] not in layout.REISSUABLE:
            self._reply("LOCKED write-ups are not released for the scored bomb")
            return
        if stage not in self.server.db.defused_phases(b["bomb_id"]):
            self._reply("LOCKED defuse this phase first")
            return
        try:
            self._reply_body(self._bomb_file(b["bomb_id"], "notes",
                                             "stage%d.md" % stage))
        except OSError:
            self._reply("LOCKED write-up not found")

    def cmd_hint(self, user, pid, args):
        db = self.server.db
        b, stage = self._stage_args(user, args[:2], 2) if len(args) == 3 \
            else (None, None)
        if b is None:
            self._reply("LOCKED no such bomb")
            return
        if b["track"] not in layout.REISSUABLE:
            self._reply("LOCKED no hints for the scored bomb")
            return
        try:
            k = int(args[2])
        except ValueError:
            k = 0
        if not 1 <= k <= 3:
            self._reply("LOCKED hints are numbered 1 to 3")
            return
        if k > 1 and (k - 1) not in db.hints_opened(b["bomb_id"], stage):
            self._reply("LOCKED open hint %d first" % (k - 1))
            return
        try:
            body = self._bomb_file(b["bomb_id"], "hints",
                                   "stage%d-%d.md" % (stage, k))
        except OSError:
            self._reply("LOCKED no such hint")
            return
        db.open_hint(b["bomb_id"], stage, k)
        self._reply_body(body)

    def cmd_new(self, user, pid, args):
        srv = self.server
        db = srv.db
        parsed = layout.parse_label(args[0]) if len(args) == 1 else None
        if parsed is None:
            self._reply("ERR say: new practice | new d0 .. d9")
            return
        track, kind = parsed
        if track not in layout.REISSUABLE:
            self._reply("ERR the scored bomb is not reissued")
            return
        if self._state() != config.OPEN:
            self._reply("ERR the practice server is closed")
            return
        if db.open_requests(user["id"]):
            self._reply("ERR a request is already being built")
            return
        if db.recent_requests(user["id"], 3600) >= srv.cfg.reissue_per_hour:
            self._reply("ERR too many requests this hour")
            return
        self._reply("OK %d" % db.add_request(user["id"], track, kind))

    def cmd_req(self, user, pid, args):
        db = self.server.db
        try:
            r = db.request(int(args[0])) if len(args) == 1 else None
        except ValueError:
            r = None
        if r is None or r["user_id"] != user["id"]:
            self._reply("FAILED no such request")
        elif r["status"] in ("pending", "building"):
            self._reply("PENDING")
        elif r["status"] == "done":
            self._reply("DONE %s" % r["path"])
        else:
            self._reply("FAILED %s" % (r["error"] or "build failed"))


class Server(socketserver.ThreadingUnixStreamServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        self.lock = threading.Lock()
        self.bombs = BombCache()
        if os.path.exists(cfg.socket):
            os.unlink(cfg.socket)
        super().__init__(cfg.socket, Handler)
        os.chmod(cfg.socket, 0o666)    # anyone may connect; uid gates identity


def main():
    cfg = config.Config()
    db = Database(cfg.db)
    os.makedirs(os.path.dirname(cfg.socket), exist_ok=True)
    server = Server(cfg, db)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
