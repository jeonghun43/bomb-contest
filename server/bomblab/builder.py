"""
builder.py - Build bombs with the original toolchain and install them into
students' homes. Runs as root.

Used two ways:
  - `python3 -m bomblab.builder` (systemd: bomblab-builder.service) works
    through build_requests that students file with `bomblab new ...`;
  - bomblabctl provision / reissue call build_and_install() directly.

Each bomb is rendered and compiled under bombs_dir/<bomb_id>/ (owned by the
bomblab service account, mode 0700: students cannot read the sources,
answers, write-ups or hints there; reportd serves write-ups and hints from it
when a student has earned them). Only bomb and bomb.c are copied into the
student's home. A failed build leaves the student's previous bomb active.
"""

import os
import pwd
import secrets
import shutil
import sys
import time

from . import config, layout
from .db import Database

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "tools"))
import bank  # noqa: E402
import buildbomb  # noqa: E402

SERVICE_USER = "bomblab"
ASSIGN_DOCS = [("docs/README.md", "README.md"), ("docs/PRIMER.md", "PRIMER.md")]
DRILL_DOCS = [("docs/DRILLS.md", "README.md")]


class Job:
    def __init__(self, cfg, user, track, kind):
        self.user = user
        self.track = track
        self.kind = kind
        self.seed = secrets.randbelow(1 << 31)
        self.bomb_id = secrets.token_hex(8)
        self.out = os.path.join(cfg.bombs_dir, self.bomb_id)
        self.dest = None

    @property
    def rel(self):
        return "~/" + layout.rel_dir(self.track, self.kind)


def _chown_tree(path, uid, gid):
    for dirpath, dirs, files in os.walk(path):
        os.chown(dirpath, uid, gid)
        for name in files:
            os.chown(os.path.join(dirpath, name), uid, gid)


def _install(job, root):
    """Copy bomb + bomb.c (+ docs) into the student's home."""
    pw = pwd.getpwnam(job.user["username"])
    dest = layout.install_dir(pw.pw_dir, job.track, job.kind)
    os.makedirs(dest, exist_ok=True)
    tmp = os.path.join(dest, ".bomb.new")
    shutil.copyfile(os.path.join(job.out, "bomb"), tmp)
    os.chmod(tmp, 0o755)
    os.replace(tmp, os.path.join(dest, "bomb"))     # atomic for a running shell
    shutil.copyfile(os.path.join(job.out, "bomb.c"), os.path.join(dest, "bomb.c"))
    docs = ASSIGN_DOCS if job.track == layout.ASSIGN else \
        DRILL_DOCS if job.track == layout.DRILL else []
    for src, name in docs:
        if os.path.isfile(os.path.join(root, src)):
            shutil.copyfile(os.path.join(root, src), os.path.join(dest, name))
    # Own everything from the home down to the bomb dir by the student.
    d = dest
    while True:
        os.chown(d, pw.pw_uid, pw.pw_gid)
        for name in os.listdir(d):
            p = os.path.join(d, name)
            if os.path.isfile(p):
                os.chown(p, pw.pw_uid, pw.pw_gid)
        if os.path.normpath(d) == os.path.normpath(pw.pw_dir):
            break
        d = os.path.dirname(d)
    os.chmod(pw.pw_dir, 0o700)
    job.dest = dest


def _secure(job):
    """Build dir: service account only."""
    try:
        svc = pwd.getpwnam(SERVICE_USER)
    except KeyError:
        return
    _chown_tree(job.out, svc.pw_uid, svc.pw_gid)
    os.chmod(job.out, 0o700)


def build_and_install(cfg, db, items, install=True, compile=True, log=print):
    """
    items: [(user_row, track, kind)]. Renders, compiles (one container run
    for all), installs and records each bomb. Returns the jobs.
    """
    jobs = [Job(cfg, u, t, k) for u, t, k in items]
    os.makedirs(cfg.bombs_dir, exist_ok=True)
    for j in jobs:
        bank.render.write(bank.build(j.kind, j.seed), j.out)
    if compile:
        buildbomb.compile_dirs(
            [j.out for j in jobs],
            notify={j.out: {"bomb_id": j.bomb_id, "socket": cfg.socket}
                    for j in jobs},
            image=cfg.image)
        buildbomb.check_dirs([j.out for j in jobs])
    for j in jobs:
        if install:
            _install(j, _ROOT)
        db.add_bomb(j.user["id"], j.track, j.kind, j.seed, j.bomb_id,
                    replace=True)
        if os.geteuid() == 0:
            _secure(j)
        log("  %s: %s %s -> %s" % (j.user["username"], j.track, j.kind, j.rel))
    return jobs


def process_one(cfg, db, **kw):
    """Handle the oldest pending request. False if there was none."""
    req = db.claim_request()
    if req is None:
        return False
    user = db.user_by_id(req["user_id"])
    try:
        jobs = build_and_install(cfg, db, [(user, req["track"], req["kind"])],
                                 log=lambda m: None, **kw)
        db.finish_request(req["id"], True, bomb_id=jobs[0].bomb_id,
                          path=jobs[0].rel)
    except Exception as e:                      # keep serving other students
        db.finish_request(req["id"], False,
                          error=str(e).splitlines()[0][:200] if str(e)
                          else e.__class__.__name__)
    return True


def main():
    cfg = config.Config()
    db = Database(cfg.db)
    while True:
        if not process_one(cfg, db):
            time.sleep(1)


if __name__ == "__main__":
    main()
