"""
config.py - Load the practice-server configuration.

The server is OPEN during its operating window (by default the two weeks
between the Bomb Lab lecture and the course assignment) and CLOSED outside
it. With no window configured it is always open. An operator override stored
in the database (`bomblabctl open|close|auto`) always wins.
"""

import configparser
import datetime
import hashlib
import hmac
import os

DEFAULT_PATH = "/etc/bomblab/bomblab.ini"

OPEN = "open"
CLOSED = "closed"


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
        if not cp.read(self.path, encoding="utf-8"):
            raise FileNotFoundError("config not found: %s" % self.path)
        self._cp = cp

        self.name = cp.get("site", "name", fallback="Bomb Lab Practice")
        self.start_at = _parse_time(cp.get("window", "start_at", fallback=""))
        self.end_at = _parse_time(cp.get("window", "end_at", fallback=""))

        # Original CMU assignment: phases 1-4 ten points, 5-6 fifteen.
        pts = cp.get("scoring", "phase_points", fallback="10,10,10,10,15,15")
        self.phase_points = [int(x) for x in pts.split(",")]
        self.secret_points = cp.getint("scoring", "secret_points", fallback=10)
        self.explosion_penalty = cp.getfloat("scoring", "explosion_penalty",
                                             fallback=0.5)
        self.max_penalty = cp.getfloat("scoring", "max_penalty", fallback=20)

        self.public_host = cp.get("server", "public_host", fallback="localhost")
        self.socket = cp.get("server", "socket",
                             fallback="/run/bomblab/report.sock")
        self.db = cp.get("server", "db", fallback="/var/lib/bomblab/bomblab.db")
        self.bombs_dir = cp.get("server", "bombs_dir",
                                fallback="/var/lib/bomblab/bombs")
        self.listen = cp.get("server", "listen", fallback="127.0.0.1:8080")
        self.events_per_minute = cp.getint("server", "events_per_minute",
                                           fallback=60)

        self.reissue_per_hour = cp.getint("practice", "reissue_per_hour",
                                          fallback=30)
        self.image = cp.get("practice", "image", fallback="bomblab-gcc48")

        self.admin_user = cp.get("admin", "user", fallback="admin")
        self.admin_hash = cp.get("admin", "password_hash", fallback="")

    def listen_addr(self):
        host, _, port = self.listen.partition(":")
        return host, int(port)

    def has_window(self):
        return bool(self.start_at or self.end_at)

    def state(self, override=None, at=None):
        """OPEN or CLOSED. `override` is OPEN/CLOSED, or 'auto'/None."""
        if override in (OPEN, CLOSED):
            return override
        t = at or now()
        if self.start_at and t < self.start_at:
            return CLOSED
        if self.end_at and t >= self.end_at:
            return CLOSED
        return OPEN

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
