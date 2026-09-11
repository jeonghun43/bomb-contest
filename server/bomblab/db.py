"""
db.py - SQLite storage for users, events, and operator settings.

All access goes through a Database object. Writers (reportd, bomblabctl) open
read-write; the web server opens read-only (mode=ro).
"""

import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY,
    username   TEXT UNIQUE NOT NULL,
    uid        INTEGER UNIQUE,
    nickname   TEXT NOT NULL,
    seed       INTEGER NOT NULL,
    bomb_id    TEXT UNIQUE NOT NULL,
    locked     INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    bomb_id    TEXT NOT NULL,
    phase      INTEGER NOT NULL,
    kind       TEXT NOT NULL,     -- hello|defused|exploded|invalid|rejected
    input      TEXT,
    peer_pid   INTEGER,
    created_at REAL NOT NULL,
    late       INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(created_at);
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
            self.conn = sqlite3.connect(path, timeout=5,
                                        check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.executescript(SCHEMA)
            self.conn.commit()
        self.conn.row_factory = sqlite3.Row

    # ---- users ----
    def add_user(self, username, uid, nickname, seed, bomb_id):
        self.conn.execute(
            "INSERT INTO users(username, uid, nickname, seed, bomb_id, "
            "locked, created_at) VALUES (?,?,?,?,?,1,?)",
            (username, uid, nickname, seed, bomb_id, time.time()))
        self.conn.commit()

    def user_by_uid(self, uid):
        return self.conn.execute(
            "SELECT * FROM users WHERE uid=?", (uid,)).fetchone()

    def user_by_name(self, username):
        return self.conn.execute(
            "SELECT * FROM users WHERE username=?", (username,)).fetchone()

    def all_users(self):
        return self.conn.execute(
            "SELECT * FROM users ORDER BY username").fetchall()

    def set_locked(self, username, locked):
        self.conn.execute("UPDATE users SET locked=? WHERE username=?",
                          (1 if locked else 0, username))
        self.conn.commit()

    def update_seed(self, username, seed, bomb_id):
        self.conn.execute("UPDATE users SET seed=?, bomb_id=? WHERE username=?",
                          (seed, bomb_id, username))
        self.conn.commit()

    def delete_user(self, username):
        row = self.user_by_name(username)
        if row:
            self.conn.execute("DELETE FROM events WHERE user_id=?", (row["id"],))
            self.conn.execute("DELETE FROM users WHERE id=?", (row["id"],))
            self.conn.commit()

    # ---- events ----
    def add_event(self, user_id, bomb_id, phase, kind, input_text,
                  peer_pid, late=0):
        self.conn.execute(
            "INSERT INTO events(user_id, bomb_id, phase, kind, input, "
            "peer_pid, created_at, late) VALUES (?,?,?,?,?,?,?,?)",
            (user_id, bomb_id, phase, kind, input_text, peer_pid,
             time.time(), 1 if late else 0))
        self.conn.commit()

    def events_since(self, ts):
        return self.conn.execute(
            "SELECT e.*, u.nickname, u.username FROM events e "
            "JOIN users u ON u.id=e.user_id WHERE e.created_at>=? "
            "ORDER BY e.created_at", (ts,)).fetchall()

    def all_events(self):
        return self.conn.execute(
            "SELECT e.*, u.nickname, u.username FROM events e "
            "JOIN users u ON u.id=e.user_id ORDER BY e.created_at").fetchall()

    def count_recent(self, user_id, seconds):
        cutoff = time.time() - seconds
        return self.conn.execute(
            "SELECT COUNT(*) c FROM events WHERE user_id=? AND created_at>=?",
            (user_id, cutoff)).fetchone()["c"]

    # ---- settings ----
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
