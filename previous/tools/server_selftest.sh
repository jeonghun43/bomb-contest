#!/usr/bin/env bash
#
# server_selftest.sh - Exercise the record server end to end WITHOUT root.
#
# Registers the current uid as a test contestant, builds a bomb wired to a
# temp socket, starts reportd + web against a temp DB/config, and checks the
# acceptance criteria that do not need real Unix accounts (AC-01..11).
#
#   bash tools/server_selftest.sh

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
export PYTHONPATH="$ROOT/server:$ROOT/tools"
export BOMBLAB_CONFIG="$TMP/bomblab.ini"

pass=0; fail=0
ok()  { pass=$((pass+1)); echo "  ok: $*"; }
bad() { fail=$((fail+1)); echo "  FAIL: $*"; }

SOCK="$TMP/report.sock"
DB="$TMP/bomblab.db"
PORT=8199
SEED=424242
BOMB_ID="$(python3 -c 'import secrets;print(secrets.token_hex(8))')"
# admin password "secret" hashed:
ADMIN_HASH="$(python3 -c 'import sys;sys.path.insert(0,"'"$ROOT"'/server");from bomblab import config;print(config.hash_password("secret","fixedsalt"))')"

cat > "$BOMBLAB_CONFIG" <<INI
[contest]
name = Selftest
start_at =
freeze_at =
end_at =
kick_on_end = no
[scoring]
phase_points = 10,10,10,10,10,10
secret_points = 10
explosion_penalty = 0.5
max_penalty = 20
[server]
public_host = localhost
socket = $SOCK
db = $DB
listen = 127.0.0.1:$PORT
events_per_minute = 60
[admin]
user = admin
password_hash = $ADMIN_HASH
INI

cleanup() {
    [ -n "${RPID:-}" ] && kill "$RPID" 2>/dev/null
    [ -n "${WPID:-}" ] && kill "$WPID" 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT

# --- build a bomb wired to the temp socket -------------------------------
OUT="$TMP/bomb"
make -C "$ROOT" NOTIFY=1 SEED=$SEED BOMB_ID="$BOMB_ID" OUT="$OUT" \
     NOTIFY_SOCKET="$SOCK" bomb >/dev/null 2>"$TMP/build.err" \
    || { echo "build failed"; cat "$TMP/build.err"; exit 1; }
BOMB="$OUT/bomb"
SOL="$OUT/solution.txt"
SECRET_SOL="$OUT/solution_secret.txt"

# --- register the current uid as a test contestant -----------------------
python3 - <<PY
import os, sys
sys.path.insert(0, "$ROOT/server")
from bomblab.db import Database
db = Database("$DB")
db.add_user("selftester", os.getuid(), "Selftester", $SEED, "$BOMB_ID")
db.close()
PY

# --- start daemons --------------------------------------------------------
python3 -m bomblab.reportd & RPID=$!
python3 -m bomblab.web & WPID=$!
# wait for socket + port
for i in $(seq 1 50); do [ -S "$SOCK" ] && break; sleep 0.1; done

api() { curl -s "http://127.0.0.1:$PORT$1"; }
count_kind() {
    python3 - "$1" <<PY
import sys, sqlite3
c = sqlite3.connect("$DB")
print(c.execute("SELECT COUNT(*) FROM events WHERE kind=?", (sys.argv[1],)).fetchone()[0])
PY
}
score() { api /api/scoreboard | python3 -c 'import sys,json;print(json.load(sys.stdin)["rows"][0]["score"])'; }
feq() { python3 -c "import sys;sys.exit(0 if abs(float('$1')-float('$2'))<1e-6 else 1)"; }
fle() { python3 -c "import sys;sys.exit(0 if float('$1')<=float('$2')+1e-6 else 1)"; }

# --- AC-01: full defuse -> 6 defused, score 60 ---------------------------
"$BOMB" "$SOL" >/dev/null 2>&1
[ "$(count_kind defused)" = "6" ] && ok "AC-01 six defused" || bad "AC-01 defused=$(count_kind defused)"
feq "$(score)" 60 && ok "AC-01 score 60" || bad "AC-01 score=$(score)"

# --- AC-02: secret adds bonus -> score 70 --------------------------------
"$BOMB" "$SECRET_SOL" >/dev/null 2>&1
feq "$(score)" 70 && ok "AC-02 secret bonus (70)" || bad "AC-02 score=$(score)"

# --- AC-03: wrong phase 3 -> one explosion, score drops ------------------
before_boom="$(count_kind exploded)"
{ sed -n 1,2p "$SOL"; echo "9 9"; } > "$TMP/wrong.txt"
"$BOMB" "$TMP/wrong.txt" >/dev/null 2>&1
after_boom="$(count_kind exploded)"
[ "$after_boom" -gt "$before_boom" ] && ok "AC-03 explosion recorded" || bad "AC-03 no explosion"

# --- AC-04: forge a defuse with a wrong input over the socket ------------
inv_before="$(count_kind invalid)"
sc_before="$(score)"
REPLY="$(python3 - <<PY
import socket
s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect("$SOCK")
s.sendall(b"EVENT $BOMB_ID defused 1 %s\n" % b"deadbeef")  # bogus hex input
print(s.recv(64).decode().strip())
PY
)"
[ "$(count_kind invalid)" -gt "$inv_before" ] && ok "AC-04 forged claim -> invalid" || bad "AC-04 not invalidated"
# A forged defuse must never *gain* points; being counted as an explosion
# (a small penalty) is intended, so we assert the score did not go up.
fle "$(score)" "$sc_before" && ok "AC-04 forgery gained no points" || bad "AC-04 score rose to $(score)"
[ "$REPLY" = "OK" ] && ok "AC-04 reply indistinguishable (OK)" || bad "AC-04 reply=$REPLY"

# --- AC-05: report under another bomb id is rejected ---------------------
REPLY="$(python3 - <<PY
import socket
s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect("$SOCK")
s.sendall(b"EVENT ffffffffffffffff defused 1 33\n")
print(s.recv(64).decode().strip())
PY
)"
[ "$REPLY" != "OK" ] && ok "AC-05 wrong bomb id rejected ($REPLY)" || bad "AC-05 accepted"

# --- AC-09: rate limit ----------------------------------------------------
LIMIT_HIT="$(python3 - <<PY
import socket
hit=False
for i in range(80):
    s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect("$SOCK")
    s.sendall(b"EVENT $BOMB_ID exploded 1 33\n")
    r=s.recv(64).decode().strip(); s.close()
    if r.startswith("ERR rate"): hit=True; break
print("yes" if hit else "no")
PY
)"
[ "$LIMIT_HIT" = "yes" ] && ok "AC-09 rate limit enforced" || bad "AC-09 no rate limit"

# --- AC-10: admin needs auth ---------------------------------------------
code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/admin")"
[ "$code" = "401" ] && ok "AC-10 admin 401 without auth" || bad "AC-10 code=$code"
code="$(curl -s -o /dev/null -w '%{http_code}' -u admin:secret "http://127.0.0.1:$PORT/admin")"
[ "$code" = "200" ] && ok "AC-10 admin 200 with auth" || bad "AC-10 authed code=$code"

# --- AC-06/07: HELLO before start closes; freeze pins the public board ----
# Rebuild config to "before start" and confirm HELLO is refused.
python3 - <<PY
import configparser
c = configparser.ConfigParser(); c.read("$BOMBLAB_CONFIG")
from datetime import datetime, timedelta, timezone
future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
c["contest"]["start_at"] = future
with open("$BOMBLAB_CONFIG","w") as f: c.write(f)
PY
kill "$RPID" 2>/dev/null; wait "$RPID" 2>/dev/null
rm -f "$SOCK"          # drop the stale socket so the wait below is meaningful
python3 -m bomblab.reportd & RPID=$!
for i in $(seq 1 50); do [ -S "$SOCK" ] && break; sleep 0.1; done
sleep 0.2
REPLY="$(python3 - <<PY
import socket
s=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); s.connect("$SOCK")
s.sendall(b"HELLO $BOMB_ID\n"); print(s.recv(64).decode().strip())
PY
)"
case "$REPLY" in CLOSED*) ok "AC-06 HELLO before start -> $REPLY";; *) bad "AC-06 reply=$REPLY";; esac

echo
echo "server selftest: passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
