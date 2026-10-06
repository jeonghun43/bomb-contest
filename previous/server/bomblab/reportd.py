"""
reportd.py - Record daemon listening on the local Unix socket.

The connecting process's uid is read from the kernel with SO_PEERCRED, so a
contestant can only ever report as themselves. A "defused" claim is re-scored
with the reference judge before it counts; a failed claim is recorded as
INVALID and counts as an explosion. Replies never reveal whether a claim was
valid.

Run:  python3 -m bomblab.reportd
"""

import binascii
import os
import socket
import socketserver
import struct
import sys
import threading

from . import config
from .db import Database

# Locate the tools/ dir (gen_bomb, bombcheck) relative to the repo root.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "tools"))
import gen_bomb        # noqa: E402
import bombcheck       # noqa: E402

MAX_LINE = 512
NUM_PHASES = 7

_params_cache = {}
_cache_lock = threading.Lock()


def params_for(seed):
    with _cache_lock:
        p = _params_cache.get(seed)
        if p is None:
            p, _ = gen_bomb.build(seed)
            _params_cache[seed] = p
        return p


class Handler(socketserver.StreamRequestHandler):
    timeout = 5

    def _peer_uid(self):
        creds = self.request.getsockopt(
            socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        pid, uid, gid = struct.unpack("3i", creds)
        return pid, uid

    def handle(self):
        server = self.server
        cfg = server.cfg
        db = server.db

        try:
            pid, uid = self._peer_uid()
        except OSError:
            self.wfile.write(b"ERR no peer\n")
            return

        user = db.user_by_uid(uid)
        if user is None:
            self.wfile.write(b"ERR unknown user\n")
            return

        raw = self.rfile.readline(MAX_LINE)
        if not raw:
            self.wfile.write(b"ERR empty\n")
            return
        parts = raw.decode("utf-8", "replace").strip().split()
        if not parts:
            self.wfile.write(b"ERR empty\n")
            return

        override = db.get_setting("override", "auto")
        state = cfg.state(override)

        if parts[0] == "HELLO":
            self._hello(db, cfg, user, pid, parts, state)
        elif parts[0] == "EVENT":
            self._event(db, cfg, user, pid, parts, state)
        else:
            self.wfile.write(b"ERR bad command\n")

    def _hello(self, db, cfg, user, pid, parts, state):
        if len(parts) != 2 or parts[1] != user["bomb_id"]:
            self.wfile.write(b"ERR bad bomb\n")
            return
        db.add_event(user["id"], user["bomb_id"], 0, "hello", None, pid)
        if state in (config.RUNNING, config.FROZEN):
            self.wfile.write(b"OK\n")
        elif state == config.BEFORE:
            self.wfile.write(b"CLOSED the contest has not started\n")
        else:
            self.wfile.write(b"CLOSED the contest has ended\n")

    def _event(self, db, cfg, user, pid, parts, state):
        # EVENT <bomb_id> <defused|exploded> <phase> [<hexinput>]
        if len(parts) < 4 or parts[1] != user["bomb_id"]:
            self.wfile.write(b"ERR bad bomb\n")
            return
        kind = parts[2]
        try:
            phase = int(parts[3])
        except ValueError:
            self.wfile.write(b"ERR bad phase\n")
            return
        if kind not in ("defused", "exploded") or not (1 <= phase <= NUM_PHASES):
            self.wfile.write(b"ERR bad event\n")
            return

        # Rate limit per user.
        if db.count_recent(user["id"], 60) >= cfg.events_per_minute:
            db.add_event(user["id"], user["bomb_id"], phase, "rejected",
                         None, pid)
            self.wfile.write(b"ERR rate limit\n")
            return

        line = ""
        if len(parts) >= 5:
            try:
                line = binascii.unhexlify(parts[4]).decode("utf-8", "replace")
            except (binascii.Error, ValueError):
                line = ""

        late = 1 if state == config.ENDED else 0

        if kind == "defused":
            params = params_for(user["seed"])
            valid = bombcheck.check_line(phase, line, params)
            recorded = "defused" if valid else "invalid"
        else:
            recorded = "exploded"

        db.add_event(user["id"], user["bomb_id"], phase, recorded, line,
                     pid, late)
        # Uniform reply: never reveal validity (AC-04) or lateness.
        self.wfile.write(b"OK\n")


class Server(socketserver.ThreadingUnixStreamServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, cfg, db):
        self.cfg = cfg
        self.db = db
        if os.path.exists(cfg.socket):
            os.unlink(cfg.socket)
        super().__init__(cfg.socket, Handler)
        os.chmod(cfg.socket, 0o666)  # any contestant may connect; uid gates identity


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
