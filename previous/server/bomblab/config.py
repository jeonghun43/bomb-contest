"""
config.py - Load the contest configuration and compute the current phase.

The effective contest state comes from the configured times, but an operator
override stored in the database (settings table) always wins. That lets
`bomblabctl start/freeze/stop/auto` take effect immediately regardless of the
clock.
"""

import configparser
import datetime
import hashlib
import hmac
import os

DEFAULT_PATH = "/etc/bomblab/bomblab.ini"

# Contest states
BEFORE = "before"   # not started: accounts locked, bombs refuse to run
RUNNING = "running"  # live: events scored
FROZEN = "frozen"   # live, but public board is pinned at freeze time
ENDED = "ended"     # over: new logins blocked, late events not scored


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def _parse_time(s):
    if not s or not s.strip():
        return None
    return datetime.datetime.fromisoformat(s.strip())


class Config:
    def __init__(self, path=None):
        self.path = path or os.environ.get("BOMBLAB_CONFIG", DEFAULT_PATH)
        cp = configparser.ConfigParser()
        if not cp.read(self.path):
            raise FileNotFoundError("config not found: %s" % self.path)
        self._cp = cp

        self.name = cp.get("contest", "name", fallback="Bomb Lab Contest")
        self.start_at = _parse_time(cp.get("contest", "start_at", fallback=""))
        self.freeze_at = _parse_time(cp.get("contest", "freeze_at", fallback=""))
        self.end_at = _parse_time(cp.get("contest", "end_at", fallback=""))
        self.kick_on_end = cp.getboolean("contest", "kick_on_end", fallback=False)

        pts = cp.get("scoring", "phase_points", fallback="10,10,10,10,10,10")
        self.phase_points = [int(x) for x in pts.split(",")]
        self.secret_points = cp.getint("scoring", "secret_points", fallback=10)
        self.explosion_penalty = cp.getfloat("scoring", "explosion_penalty",
                                             fallback=0.5)
        self.max_penalty = cp.getfloat("scoring", "max_penalty", fallback=20)

        self.public_host = cp.get("server", "public_host", fallback="localhost")
        self.socket = cp.get("server", "socket",
                             fallback="/run/bomblab/report.sock")
        self.db = cp.get("server", "db", fallback="/var/lib/bomblab/bomblab.db")
        self.listen = cp.get("server", "listen", fallback="127.0.0.1:8080")
        self.events_per_minute = cp.getint("server", "events_per_minute",
                                           fallback=60)

        self.admin_user = cp.get("admin", "user", fallback="admin")
        self.admin_hash = cp.get("admin", "password_hash", fallback="")

    def listen_addr(self):
        host, _, port = self.listen.partition(":")
        return host, int(port)

    def state(self, override=None, at=None):
        """
        Effective state. `override` is one of BEFORE/RUNNING/FROZEN/ENDED or
        "auto"/None to follow the clock. `at` defaults to now().
        """
        if override and override != "auto":
            return override
        t = at or now()
        if self.start_at and t < self.start_at:
            return BEFORE
        if self.end_at and t >= self.end_at:
            return ENDED
        if self.freeze_at and t >= self.freeze_at:
            return FROZEN
        return RUNNING

    def check_admin_password(self, password):
        """Constant-time check against a stored 'sha256$salt$hex' hash."""
        if not self.admin_hash or self.admin_hash.count("$") != 2:
            return False
        algo, salt, expected = self.admin_hash.split("$")
        if algo != "sha256":
            return False
        got = hashlib.sha256((salt + password).encode()).hexdigest()
        return hmac.compare_digest(got, expected)


def hash_password(password, salt=None):
    """Produce a 'sha256$salt$hex' string for the admin password."""
    import secrets
    salt = salt or secrets.token_hex(8)
    digest = hashlib.sha256((salt + password).encode()).hexdigest()
    return "sha256$%s$%s" % (salt, digest)
