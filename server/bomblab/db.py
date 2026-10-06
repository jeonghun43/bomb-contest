"""
db.py - SQLite storage for the practice server (schema v2).

    users           one row per student account
    bombs           every bomb ever issued: track (assign|practice|drill),
                    kind (cmu | drill:dN), seed, bomb_id, active flag
    events          every report from a bomb (hello/defused/exploded/
                    invalid/rejected), with the input line
    hint_views      which hints a student has opened (they open in order)
    build_requests  reissue requests the root builder service works through
    settings        operator overrides

Writers (reportd, builder, bomblabctl) open read-write; the web server opens
read-only (mode=ro). A v1 database (contest server: one seed per user) is
upgraded in place; its bombs are kept only as inactive history, because the
v1 bombs were a different design that the bank cannot re-score.
"""

import sqlite3
import time

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY,
    username   TEXT UNIQUE NOT NULL,
    uid        INTEGER UNIQUE,
    nickname   TEXT NOT NULL,
    locked     INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS bombs (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    track      TEXT NOT NULL,             -- assign | practice | drill
    kind       TEXT NOT NULL,             -- cmu | drill:d0 .. drill:d9 | legacy
    seed       INTEGER NOT NULL,
    bomb_id    TEXT UNIQUE NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bombs_user ON bombs(user_id);
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id),
    bomb_id    TEXT NOT NULL,
    phase      INTEGER NOT NULL,
    kind       TEXT NOT NULL,     -- hello|defused|exploded|invalid|rejected
    input      TEXT,
    peer_pid   INTEGER,
    created_at REAL NOT NULL,
    late       INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_events_bomb ON events(bomb_id);
CREATE TABLE IF NOT EXISTS hint_views (
    bomb_id    TEXT NOT NULL,
    stage      INTEGER NOT NULL,
    k          INTEGER NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (bomb_id, stage, k)
);
CREATE TABLE IF NOT EXISTS build_requests (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    track       TEXT NOT NULL,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL,     -- pending | building | done | failed
    bomb_id     TEXT,
    path        TEXT,
    error       TEXT,
    created_at  REAL NOT NULL,
    finished_at REAL
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


class Database:
    def __init__(self, path, readonly=False):
        if readonly:
            uri = "file:%s?mode=ro" % path
            self.conn = sqlite3.connect(uri, uri=True, timeout=5,
                                        check_same_thread=False)
        else:
            self.conn = sqlite3.connect(path, timeout=10,
                                        check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self._migrate_v1()
            self.conn.executescript(SCHEMA)
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.execute("PRAGMA user_version=%d" % SCHEMA_VERSION)
            self.conn.commit()
        self.conn.row_factory = sqlite3.Row

    def _migrate_v1(self):
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(users)")]
        if "seed" not in cols:
            return
        c = self.conn
        c.executescript("""
            ALTER TABLE users RENAME TO users_v1;
            CREATE TABLE users (
                id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                uid INTEGER UNIQUE, nickname TEXT NOT NULL,
                locked INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL);
            INSERT INTO users(id, username, uid, nickname, locked, created_at)
                SELECT id, username, uid, nickname, locked, created_at
                FROM users_v1;
        """)
        c.executescript(SCHEMA)
        c.execute("""
            INSERT OR IGNORE INTO bombs(user_id, track, kind, seed, bomb_id,
                                        active, created_at)
            SELECT id, 'assign', 'legacy', seed, bomb_id, 0, created_at
            FROM users_v1""")
        c.execute("DROP TABLE users_v1")
        c.commit()

    # ---- users ----------------------------------------------------------
    def add_user(self, username, uid, nickname):
        cur = self.conn.execute(
            "INSERT INTO users(username, uid, nickname, locked, created_at) "
            "VALUES (?,?,?,0,?)", (username, uid, nickname, time.time()))
        self.conn.commit()
        return cur.lastrowid

    def user_by_uid(self, uid):
        return self.conn.execute(
            "SELECT * FROM users WHERE uid=?", (uid,)).fetchone()

    def user_by_name(self, username):
        return self.conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)).fetchone()

    def user_by_id(self, user_id):
        return self.conn.execute(
            "SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

    def all_users(self):
        return self.conn.execute(
            "SELECT * FROM users ORDER BY username").fetchall()

    def set_locked(self, username, locked):
        self.conn.execute("UPDATE users SET locked=? WHERE username=?",
                          (1 if locked else 0, username))
        self.conn.commit()

    def delete_user(self, username):
        row = self.user_by_name(username)
        if row:
            uid = row["id"]
            ids = [b["bomb_id"] for b in self.bombs_of(uid, active_only=False)]
            for bid in ids:
                self.conn.execute("DELETE FROM hint_views WHERE bomb_id=?", (bid,))
            for t in ("events", "bombs", "build_requests"):
                self.conn.execute("DELETE FROM %s WHERE user_id=?" % t, (uid,))
            self.conn.execute("DELETE FROM users WHERE id=?", (uid,))
            self.conn.commit()

    # ---- bombs ----------------------------------------------------------
    def add_bomb(self, user_id, track, kind, seed, bomb_id, replace=True):
        """Issue a bomb; with replace, the user's previous active bomb of the
        same track and kind stops being accepted."""
        if replace:
            self.conn.execute(
                "UPDATE bombs SET active=0 WHERE user_id=? AND track=? "
                "AND kind=? AND active=1", (user_id, track, kind))
        self.conn.execute(
            "INSERT INTO bombs(user_id, track, kind, seed, bomb_id, active, "
            "created_at) VALUES (?,?,?,?,?,1,?)",
            (user_id, track, kind, seed, bomb_id, time.time()))
        self.conn.commit()

    def bomb_by_id(self, bomb_id):
        return self.conn.execute(
            "SELECT * FROM bombs WHERE bomb_id=?", (bomb_id,)).fetchone()

    def bombs_of(self, user_id, active_only=True):
        q = "SELECT * FROM bombs WHERE user_id=?"
        if active_only:
            q += " AND active=1"
        return self.conn.execute(q + " ORDER BY id", (user_id,)).fetchall()

    def all_bombs(self):
        return self.conn.execute("SELECT * FROM bombs ORDER BY id").fetchall()

    # ---- events ---------------------------------------------------------
    def add_event(self, user_id, bomb_id, phase, kind, input_text,
                  peer_pid, late=0):
        self.conn.execute(
            "INSERT INTO events(user_id, bomb_id, phase, kind, input, "
            "peer_pid, created_at, late) VALUES (?,?,?,?,?,?,?,?)",
            (user_id, bomb_id, phase, kind, input_text, peer_pid,
             time.time(), 1 if late else 0))
        self.conn.commit()

    def all_events(self):
        """Every event with its user and (when known) its bomb's track/kind."""
        return self.conn.execute(
            "SELECT e.*, u.nickname, u.username, b.track, b.kind AS bomb_kind "
            "FROM events e JOIN users u ON u.id=e.user_id "
            "LEFT JOIN bombs b ON b.bomb_id=e.bomb_id "
            "ORDER BY e.created_at, e.id").fetchall()

    def defused_phases(self, bomb_id):
        return {r["phase"] for r in self.conn.execute(
            "SELECT DISTINCT phase FROM events WHERE bomb_id=? "
            "AND kind='defused' AND late=0", (bomb_id,))}

    def explosions(self, bomb_id):
        return self.conn.execute(
            "SELECT COUNT(*) c FROM events WHERE bomb_id=? "
            "AND kind IN ('exploded','invalid') AND late=0",
            (bomb_id,)).fetchone()["c"]

    def count_recent(self, user_id, seconds):
        cutoff = time.time() - seconds
        return self.conn.execute(
            "SELECT COUNT(*) c FROM events WHERE user_id=? AND created_at>=?",
            (user_id, cutoff)).fetchone()["c"]

    # ---- hints ----------------------------------------------------------
    def hints_opened(self, bomb_id, stage):
        return {r["k"] for r in self.conn.execute(
            "SELECT k FROM hint_views WHERE bomb_id=? AND stage=?",
            (bomb_id, stage))}

    def open_hint(self, bomb_id, stage, k):
        self.conn.execute(
            "INSERT OR IGNORE INTO hint_views(bomb_id, stage, k, created_at) "
            "VALUES (?,?,?,?)", (bomb_id, stage, k, time.time()))
        self.conn.commit()

    # ---- build requests -------------------------------------------------
    def add_request(self, user_id, track, kind):
        cur = self.conn.execute(
            "INSERT INTO build_requests(user_id, track, kind, status, "
            "created_at) VALUES (?,?,?,'pending',?)",
            (user_id, track, kind, time.time()))
        self.conn.commit()
        return cur.lastrowid

    def request(self, req_id):
        return self.conn.execute(
            "SELECT * FROM build_requests WHERE id=?", (req_id,)).fetchone()

    def open_requests(self, user_id):
        return self.conn.execute(
            "SELECT * FROM build_requests WHERE user_id=? "
            "AND status IN ('pending','building')", (user_id,)).fetchall()

    def recent_requests(self, user_id, seconds):
        cutoff = time.time() - seconds
        return self.conn.execute(
            "SELECT COUNT(*) c FROM build_requests WHERE user_id=? "
            "AND created_at>=?", (user_id, cutoff)).fetchone()["c"]

    def claim_request(self):
        """Take the oldest pending request (builder). None if there is none."""
        row = self.conn.execute(
            "SELECT * FROM build_requests WHERE status='pending' "
            "ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return None
        cur = self.conn.execute(
            "UPDATE build_requests SET status='building' "
            "WHERE id=? AND status='pending'", (row["id"],))
        self.conn.commit()
        return row if cur.rowcount == 1 else None

    def finish_request(self, req_id, ok, bomb_id=None, path=None, error=None):
        self.conn.execute(
            "UPDATE build_requests SET status=?, bomb_id=?, path=?, error=?, "
            "finished_at=? WHERE id=?",
            ("done" if ok else "failed", bomb_id, path, error, time.time(),
             req_id))
        self.conn.commit()

    # ---- settings -------------------------------------------------------
    def get_setting(self, key, default=None):
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value))
        self.conn.commit()

    def close(self):
        self.conn.close()
