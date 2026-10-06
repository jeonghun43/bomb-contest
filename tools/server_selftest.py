#!/usr/bin/env python3
"""
server_selftest.py - Exercise the practice server end to end WITHOUT root
(specs/002-contest-server, revision 2: AC-01..AC-10).

    python3 tools/server_selftest.py

Starts reportd and web against a temporary config, database and bombs
directory, registers the current uid as a student (plus a second, foreign
student), and drives the real Unix socket and HTTP API:

  bomb reports    HELLO / EVENT, own vs foreign vs inactive bombs, re-scoring
                  (valid, invalid), uniform replies
  scoring         70 + 10 for the scored bomb, explosion penalty only there,
                  drill progress kept apart
  write-ups       NOTES only after defusal and never for the scored bomb;
                  HINT in order 1 -> 2 -> 3
  reissue         NEW / REQ with the builder run in-process, old bomb refused
  window          closed server refuses HELLO, records late events unscored
  limits          event rate limit
  web             public board and feed (no input lines), admin auth
  student CLI     server/bin/bomblab against the same socket
  migration       a v1 (contest) database opens as v2

With docker and the bomblab-gcc48 image available, one real server-mode bomb
is compiled and run with its answers against the daemon; otherwise that part
is simulated with EVENT lines.
"""

import base64
import binascii
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "server"), ROOT, HERE):
    sys.path.insert(0, p)

import bank  # noqa: E402
from bomblab import builder, config  # noqa: E402
from bomblab.db import Database  # noqa: E402

PORT = 8199
passed = failed = 0


def ok(msg):
    global passed
    passed += 1
    print("  ok   " + msg)


def bad(msg):
    global failed
    failed += 1
    print("  FAIL " + msg)


def check(cond, msg):
    ok(msg) if cond else bad(msg)


class Env:
    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="bomblab-selftest-")
        self.sock = os.path.join(self.tmp, "report.sock")
        self.db_path = os.path.join(self.tmp, "bomblab.db")
        self.ini = os.path.join(self.tmp, "bomblab.ini")
        self.bombs = os.path.join(self.tmp, "bombs")
        self.write_ini(events_per_minute=1000)
        self.procs = []

    def write_ini(self, events_per_minute):
        h = config.hash_password("secret", "fixedsalt")
        with open(self.ini, "w") as f:
            f.write("""[site]
name = Selftest
[window]
start_at =
end_at =
[scoring]
phase_points = 10,10,10,10,15,15
secret_points = 10
explosion_penalty = 0.5
max_penalty = 20
[practice]
reissue_per_hour = 30
image = bomblab-gcc48
[server]
public_host = localhost
socket = %s
db = %s
bombs_dir = %s
listen = 127.0.0.1:%d
events_per_minute = %d
[admin]
user = admin
password_hash = %s
""" % (self.sock, self.db_path, self.bombs, PORT, events_per_minute, h))

    def start(self):
        env = dict(os.environ, BOMBLAB_CONFIG=self.ini,
                   PYTHONPATH=os.pathsep.join([os.path.join(ROOT, "server"),
                                               ROOT, HERE]))
        for mod in ("bomblab.reportd", "bomblab.web"):
            self.procs.append(subprocess.Popen(
                [sys.executable, "-m", mod], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for _ in range(100):
            try:
                s = socket.socket(socket.AF_UNIX)
                s.connect(self.sock)
                s.close()
                urllib.request.urlopen("http://127.0.0.1:%d/" % PORT,
                                       timeout=1)
                return
            except OSError:
                time.sleep(0.1)
        raise SystemExit("daemons did not start")

    def stop(self):
        for p in self.procs:
            p.terminate()
            p.wait()
        self.procs = []
        if os.path.exists(self.sock):     # a stale socket would look alive
            os.unlink(self.sock)

    def cleanup(self):
        self.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


def send(env, line):
    s = socket.socket(socket.AF_UNIX)
    s.connect(env.sock)
    s.sendall(line.encode("latin-1") + b"\n")
    data = b""
    while True:
        c = s.recv(65536)
        if not c:
            break
        data += c
    s.close()
    head, _, rest = data.partition(b"\n")
    return head.decode(), rest.decode("utf-8", "replace")


def hexl(s):
    return binascii.hexlify(s.encode("latin-1")).decode()


def api(path, auth=None):
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (PORT, path))
    if auth:
        req.add_header("Authorization", "Basic " +
                       base64.b64encode(auth.encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, ""


def board(env):
    return json.loads(api("/api/scoreboard")[1])


def my_row(env):
    for r in board(env)["rows"]:
        if r["username"] == "selftester":
            return r
    return None


def docker_ok():
    try:
        r = subprocess.run(["docker", "image", "inspect", "bomblab-gcc48"],
                           capture_output=True)
        return r.returncode == 0
    except FileNotFoundError:
        return False


def main():
    env = Env()
    try:
        run(env)
    finally:
        env.cleanup()
    print("\nselftest: passed %d, failed %d" % (passed, failed))
    return 1 if failed else 0


def run(env):
    cfg = config.Config(env.ini)
    db = Database(env.db_path)
    me = db.user_by_id(db.add_user("selftester", os.getuid(), "Selftester"))
    other = db.user_by_id(db.add_user("other", 4000000, "Other"))
    real = docker_ok()

    print("== setup (%s)" % ("real server-mode bomb" if real
                             else "no docker: simulated reports"))
    jobs = builder.build_and_install(
        cfg, db, [(me, "assign", "cmu")], install=False, compile=real,
        log=lambda m: None)
    jobs += builder.build_and_install(
        cfg, db, [(me, "practice", "cmu"), (me, "drill", "drill:d0"),
                  (other, "assign", "cmu")],
        install=False, compile=False, log=lambda m: None)
    assign, practice, drill, foreign = jobs
    env.start()

    A = bank.build("cmu", assign.seed)
    D = bank.build("drill:d0", drill.seed)

    print("== bomb reports")
    check(send(env, "HELLO " + assign.bomb_id)[0] == "OK", "HELLO own bomb")
    check(send(env, "HELLO " + foreign.bomb_id)[0].startswith("ERR"),
          "HELLO someone else's bomb -> ERR")

    if real:
        lines = A.answer_lines(with_secret=True)
        path = os.path.join(env.tmp, "answers.txt")
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        r = subprocess.run([os.path.join(assign.out, "bomb"), path],
                           stdin=subprocess.DEVNULL, capture_output=True,
                           text=True, timeout=30)
        check(r.returncode == 0 and "Wow!" in r.stdout,
              "real bomb defused all 7 against the daemon")
    else:
        for n, line in enumerate(A.answer_lines(with_secret=True), 1):
            send(env, "EVENT %s defused %d %s" % (assign.bomb_id, n, hexl(line)))
    kinds = [r[0] for r in sqlite3.connect(env.db_path).execute(
        "SELECT kind FROM events WHERE bomb_id=? AND kind!='hello'",
        (assign.bomb_id,))]
    check(kinds == ["defused"] * 7, "7 defusals recorded and re-scored valid")

    r = my_row(env)
    check(r and r["score"] == 80, "AC-01 score 70 + hidden 10 = 80 (got %s)"
          % (r and r["score"]))

    print("== scoring")
    send(env, "EVENT %s exploded 2 %s" % (assign.bomb_id, hexl("nope")))
    check(my_row(env)["score"] == 79.5, "AC-02 scored-bomb explosion -0.5")
    send(env, "EVENT %s exploded 1 %s" % (drill.bomb_id, hexl("nope")))
    check(my_row(env)["score"] == 79.5, "AC-02 drill explosion: no penalty")
    rep = send(env, "EVENT %s defused 1 %s" % (assign.bomb_id, hexl("wrong")))
    check(rep[0] == "OK", "AC-03 invalid claim gets the same OK reply")
    check(my_row(env)["score"] == 79.0, "AC-03 invalid claim counts as explosion")
    send(env, "EVENT %s defused 1 %s" % (drill.bomb_id, hexl(D.phases[0].answer)))
    rows = {x["username"]: x for x in board(env)["drill_rows"]}
    check(rows["selftester"]["drills"]["d0"] == [1] and
          my_row(env)["score"] == 79.0,
          "AC-07 drill progress tracked apart from the score")
    check(send(env, "EVENT %s defused 1 %s" % (foreign.bomb_id, hexl("x")))[0]
          .startswith("ERR"), "AC-04 report on someone else's bomb -> ERR")

    print("== write-ups and hints")
    h, body = send(env, "NOTES %s 1" % drill.bomb_id)
    check(h.startswith("OK") and "Phase 1" in body, "AC-06 notes after defusal")
    check(send(env, "NOTES %s 2" % drill.bomb_id)[0].startswith("LOCKED"),
          "AC-06 notes locked before defusal")
    check(send(env, "NOTES %s 1" % assign.bomb_id)[0].startswith("LOCKED"),
          "scored bomb: no write-ups")
    check(send(env, "HINT %s 1 1" % assign.bomb_id)[0].startswith("LOCKED"),
          "scored bomb: no hints")
    check(send(env, "HINT %s 2 2" % drill.bomb_id)[0].startswith("LOCKED"),
          "hint 2 before hint 1 -> LOCKED")
    check(send(env, "HINT %s 2 1" % drill.bomb_id)[0].startswith("OK") and
          send(env, "HINT %s 2 2" % drill.bomb_id)[0].startswith("OK"),
          "hints open in order, no waiting")

    print("== reissue")
    check(send(env, "NEW bomb")[0].startswith("ERR"),
          "AC-05 scored bomb is not reissued on request")
    h, _ = send(env, "NEW d0")
    check(h.startswith("OK "), "NEW d0 accepted")
    req = h[3:]
    check(send(env, "NEW practice")[0].startswith("ERR"),
          "one request at a time")
    check(send(env, "REQ " + req)[0] == "PENDING", "REQ pending")
    builder.process_one(cfg, Database(env.db_path), install=False,
                        compile=False)
    h, _ = send(env, "REQ " + req)
    check(h == "DONE ~/drills/d0", "AC-05 builder finished: %s" % h)
    check(send(env, "EVENT %s exploded 1 %s" % (drill.bomb_id, hexl("x")))[0]
          .startswith("ERR"), "AC-04 replaced bomb is refused")
    st = json.loads(send(env, "STATUS")[0][3:])
    labels = {b["label"]: b for b in st["bombs"]}
    check(set(labels) == {"bomb", "practice", "d0"} and
          labels["d0"]["bomb_id"] != drill.bomb_id,
          "STATUS lists the new d0 bomb")

    print("== student CLI")
    cli = os.path.join(ROOT, "server", "bin", "bomblab")
    cenv = dict(os.environ, BOMBLAB_SOCKET=env.sock)
    r = subprocess.run([sys.executable, cli], env=cenv, capture_output=True,
                       text=True)
    check(r.returncode == 0 and "~/drills/d0" in r.stdout, "bomblab status")
    r = subprocess.run([sys.executable, cli, "new", "bomb"], env=cenv,
                       capture_output=True, text=True)
    check(r.returncode == 1 and "과제형" in r.stderr,
          "bomblab new bomb is refused with a message")
    r = subprocess.run([sys.executable, cli, "hint", "practice", "1"],
                       env=cenv, capture_output=True, text=True)
    check(r.returncode == 0 and "힌트 1/3" in r.stdout, "bomblab hint")

    print("== operator lookup")
    ctl = os.path.join(ROOT, "server", "bin", "bomblabctl")
    r = subprocess.run([sys.executable, ctl, "--config", env.ini, "solution",
                        "selftester", "practice"], capture_output=True,
                       text=True)
    check(r.returncode == 0 and "# SOLUTION" in r.stdout and
          "1단계 1" in r.stdout,
          "bomblabctl solution shows the answers and the hints opened")
    r = subprocess.run([sys.executable, ctl, "--config", env.ini, "solution",
                        "selftester", "d9"], capture_output=True, text=True)
    check(r.returncode != 0, "bomblabctl solution: no such bomb -> error")

    print("== window")
    Database(env.db_path).set_setting("override", config.CLOSED)
    check(send(env, "HELLO " + assign.bomb_id)[0].startswith("CLOSED"),
          "AC-08 closed server refuses HELLO")
    send(env, "EVENT %s exploded 3 %s" % (assign.bomb_id, hexl("late")))
    check(my_row(env)["score"] == 79.0, "late event recorded but not scored")
    check(send(env, "NEW practice")[0].startswith("ERR"),
          "no reissue while closed")
    Database(env.db_path).set_setting("override", "auto")

    print("== web")
    check(api("/admin")[0] == 401, "AC-10 admin without auth -> 401")
    check(api("/admin", "admin:secret")[0] == 200, "admin with auth -> 200")
    feed = json.loads(api("/api/feed")[1])["events"]
    check(feed and all("input" not in e for e in feed),
          "public feed has no input lines")
    afeed = json.loads(api("/api/admin/feed", "admin:secret")[1])["events"]
    check(any(e.get("input") == "wrong" for e in afeed),
          "admin feed shows input lines")

    print("== limits")
    env.stop()
    env.write_ini(events_per_minute=5)
    env.start()
    replies = [send(env, "EVENT %s exploded 1 %s" %
                    (practice.bomb_id, hexl("x")))[0] for _ in range(8)]
    check("ERR rate limit" in replies, "AC-09 rate limit")

    print("== migration")
    v1 = os.path.join(env.tmp, "v1.db")
    c = sqlite3.connect(v1)
    c.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL,
            uid INTEGER UNIQUE, nickname TEXT NOT NULL, seed INTEGER NOT NULL,
            bomb_id TEXT UNIQUE NOT NULL, locked INTEGER NOT NULL DEFAULT 1,
            created_at REAL NOT NULL);
        INSERT INTO users VALUES (1, 'bomb01', 1234, 'Kim', 99, 'aaaabbbbccccdddd', 1, 0);
    """)
    c.commit()
    c.close()
    m = Database(v1)
    u = m.user_by_name("bomb01")
    b = m.bomb_by_id("aaaabbbbccccdddd")
    check(u is not None and b is not None and b["active"] == 0 and
          b["kind"] == "legacy", "v1 database upgraded; v1 bomb kept inactive")


if __name__ == "__main__":
    sys.exit(main())
