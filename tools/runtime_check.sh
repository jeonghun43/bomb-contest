#!/usr/bin/env bash
#
# runtime_check.sh - verify the shared bomb runtime (specs/003-practice-bank
# Phase B: T020-T023, AC-06).
#
#   bash tools/runtime_check.sh
#
# Builds small test bombs from bank/csrc/common plus trivial test phases
# (bank/csrc/test/phases_rt.c) with the original toolchain, then checks:
#
#   offline   input handling: blank lines, answer file -> stdin, EOF errors,
#             GRADE_BOMB, 78-character limit, Ctrl-C, secret phase entry
#   drill     the three-phase drill main
#   parity    (dev machine, needs ref/) our bomb.c + support.c with the
#             calibration phases match the original instruction for
#             instruction, and both binaries behave identically - same output,
#             same exit status - on every input-handling scenario
#   notify    server builds against a mock record daemon: HELLO, EVENT lines
#             with phase numbers and hex input, refusal, unreachable daemon,
#             lost defusal report
#
# Needs docker (bomblab-gcc48 image) and python3; the parity part also needs
# capstone + pyelftools. Exit status 0 when everything passes.

set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
COMMON=$ROOT/bank/csrc/common
TEST=$ROOT/bank/csrc/test
W=$ROOT/build/rt
REF=$ROOT/ref/cmu-selfstudy/bomb/bomb
CALIB=$ROOT/ref/calib/phases.c
SOCK=/tmp/bomblab-rt.sock
BOMB_ID=0011223344556677
PY=${PYTHON:-python3}

pass=0
fail=0
ok()  { echo "  ok   $*"; pass=$((pass + 1)); }
bad() { echo "  FAIL $*"; fail=$((fail + 1)); }

# assemble NAME MAIN PHASES CANARY_JSON   (bombdata.h on stdin)
assemble() {
    local d=$W/$1
    rm -rf "$d" && mkdir -p "$d"
    cp "$COMMON"/support.c "$COMMON"/support.h "$COMMON"/phases.h \
       "$COMMON"/driverlib.c "$COMMON"/driverlib.h "$d"/
    sed -e 's/@DRILL_ID@/D0/g' -e 's/@DRILL_TITLE@/runtime test/g' \
        "$2" > "$d/bomb.c"
    cp "$3" "$d/phases.c"
    cat > "$d/bombdata.h"
    echo "{\"canary\": $4}" > "$d/manifest.json"
}

# run DIR INPUT_FILE [args...]   -> OUT, CODE   (cwd = DIR, argv[0] = ./bomb)
run() {
    local d=$1 in=$2
    shift 2
    OUT=$(cd "$d" && timeout 15 ./bomb "$@" < "$in" 2>&1)
    CODE=$?
}

# expect NAME CODE [needle ...]   -- checks the last run()
expect() {
    local name=$1 code=$2 n
    shift 2
    if [ "$CODE" != "$code" ]; then
        bad "$name: exit $CODE, want $code"
        return
    fi
    for n in "$@"; do
        case "$OUT" in
            *"$n"*) ;;
            *) bad "$name: output lacks '$n'"; return ;;
        esac
    done
    ok "$name"
}

lines() { printf '%s\n' "$@"; }

echo "== build"
mkdir -p "$W/in"

assemble off "$COMMON/bomb.c" "$TEST/phases_rt.c" '["phase_defused"]' <<'EOF'
#define NUM_PHASES  6
#define HAS_SECRET  1
#define SECRET_LINE 3
#define SECRET_WORD "token"
EOF

assemble drill "$COMMON/drill_main.c" "$TEST/phases_rt.c" '[]' <<'EOF'
#define RT_DRILL
#define NUM_PHASES  3
#define HAS_SECRET  0
EOF

assemble notify "$COMMON/bomb.c" "$TEST/phases_rt.c" '["phase_defused"]' <<'EOF'
#define NUM_PHASES  6
#define HAS_SECRET  1
#define SECRET_LINE 3
#define SECRET_WORD "token"
EOF

DIRS="$W/off $W/drill"
HAVE_REF=0
if [ -f "$REF" ] && [ -f "$CALIB" ]; then
    HAVE_REF=1
    # The calibration phases are the original's; the secret word below is a
    # stand-in (only its address reaches the code, and addresses are ignored).
    assemble parity "$COMMON/bomb.c" "$CALIB" '["phase_5", "phase_defused"]' <<'EOF'
#define NUM_PHASES  6
#define HAS_SECRET  1
#define SECRET_LINE 3
#define SECRET_WORD "standin"
EOF
    DIRS="$DIRS $W/parity"
fi

if $PY "$ROOT/tools/buildbomb.py" --src $DIRS >/dev/null &&
   $PY "$ROOT/tools/buildbomb.py" --src "$W/notify" --notify \
       --bomb-id "$BOMB_ID" --socket "$SOCK" >/dev/null; then
    ok "build + elfcheck ($(echo $DIRS | wc -w) offline, 1 server)"
else
    bad "build"
    echo "passed: $pass   failed: $fail"
    exit 1
fi

# ---------------------------------------------------------------------------
echo "== offline runtime"

lines one two three "4 4" five six            > "$W/in/all"
lines one two three "4 4 token" five six seven > "$W/in/secret"
lines one two three "4 4 nottoken" five six    > "$W/in/badtoken"
lines one two three                           > "$W/in/first3"
lines "4 4" five six                          > "$W/in/rest3"
printf 'one\n\n   \ntwo\n\t\nthree\n\n4 4\nfive\nsix\n' > "$W/in/blanks"
printf '%085d\n' 0                            > "$W/in/long"
: > "$W/in/empty"

run "$W/off" "$W/in/all";        expect "all six answers" 0 "Congratulations! You've defused the bomb!"
run "$W/off" "$W/in/secret";     expect "secret token opens the secret phase" 0 \
    "Curses, you've found the secret phase!" "Wow! You've defused the secret stage!"
run "$W/off" "$W/in/badtoken"
case "$OUT" in *Curses*) bad "wrong token must not open the secret phase" ;;
               *) expect "wrong token: no secret phase" 0 "Congratulations" ;; esac
run "$W/off" "$W/in/rest3" "$W/in/first3"
                                 expect "answer file runs out -> continue on stdin" 0 "Congratulations"
run "$W/off" "$W/in/blanks";     expect "blank lines are skipped" 0 "Congratulations"
run "$W/off" "$W/in/long";       expect "line over 78 chars explodes" 8 "Error: Input line too long" "BOOM!!!"
run "$W/off" "$W/in/empty" "$W/in/first3"
                                 expect "file then empty stdin -> Premature EOF, exit 0" 0 "Error: Premature EOF on stdin"
run "$W/off" "$W/in/first3";     expect "stdin EOF -> Premature EOF, exit 8" 8 "Error: Premature EOF on stdin"
OUT=$(cd "$W/off" && GRADE_BOMB=1 timeout 15 ./bomb "$W/in/first3" < "$W/in/empty" 2>&1); CODE=$?
case "$OUT" in *Premature*) bad "GRADE_BOMB must exit quietly" ;;
               *) expect "GRADE_BOMB: quiet exit 0 at end of file" 0 ;; esac

sigint() {   # sigint DIR -> OUT, CODE
    local f=$W/sigint.out
    ( cd "$1" && sleep 10 | ./bomb > "$f" 2>&1 ) &
    sleep 0.5
    pkill -INT -f "^./bomb$" 2>/dev/null
    wait $!
    CODE=$?
    OUT=$(cat "$f")
}
sigint "$W/off"
case "$CODE" in 16) ;; *) CODE=$CODE ;; esac
expect "Ctrl-C handler" 16 "So you think you can stop the bomb with ctrl-c, do you?" "Well...OK. :-)"

# ---------------------------------------------------------------------------
echo "== drill main"

lines one two three > "$W/in/drill"
run "$W/drill" "$W/in/drill"
expect "three phases, then defused" 0 "Welcome to drill D0: runtime test." \
    "That's number 2.  Keep going!" "Congratulations! You've defused the bomb!"
lines one two > "$W/in/drill2"
run "$W/drill" "$W/in/drill2"; expect "stops for phase 3 input" 8 "Premature EOF"

# ---------------------------------------------------------------------------
if [ $HAVE_REF = 1 ]; then
    echo "== parity with the original (ref/)"

    FUNCS="main phase_1 phase_2 phase_3 func4 phase_4 phase_5 phase_6 fun7
           secret_phase sig_handler invalid_phase string_length
           strings_not_equal initialize_bomb initialize_bomb_solve blank_line
           skip explode_bomb read_six_numbers read_line phase_defused"
    if R=$($PY "$ROOT/tools/asmdiff.py" --data "$REF" "$W/parity/bomb" $FUNCS); then
        ok "asmdiff: $(echo "$R" | tail -1)"
    else
        bad "asmdiff"
        echo "$R" | grep -v ' OK ' | head -40
    fi

    O=$W/orig
    rm -rf "$O" && mkdir -p "$O" && cp "$REF" "$O/bomb"

    lines wrong                       > "$W/in/wrong"
    printf '\n\n  \nwrong\n'          > "$W/in/blankwrong"
    printf '%077d\n' 0                > "$W/in/len77"
    printf '%078d\n' 0                > "$W/in/len78"
    printf 'no newline at end'        > "$W/in/nonl"

    same() {   # same NAME STDIN [args...]
        local name=$1 in=$2 o1 c1
        shift 2
        run "$O" "$in" "$@";        o1=$OUT; c1=$CODE
        run "$W/parity" "$in" "$@"
        if [ "$o1" = "$OUT" ] && [ "$c1" = "$CODE" ]; then
            ok "same behaviour: $name (exit $CODE)"
        else
            bad "behaviour differs: $name (exit $c1 vs $CODE)"
            diff <(echo "$o1") <(echo "$OUT") | head -10
        fi
    }
    same "wrong answer"                 "$W/in/wrong"
    same "blank lines before an answer" "$W/in/blankwrong"
    same "answer file -> stdin"         "$W/in/wrong" "$W/in/empty"
    same "file then empty stdin"        "$W/in/empty" "$W/in/empty"
    same "stdin EOF"                    "$W/in/empty"
    same "77-character line"            "$W/in/len77"
    same "78-character line"            "$W/in/len78"
    same "85-character line"            "$W/in/long"
    same "last line without newline"    "$W/in/nonl"
    same "missing answer file"          "$W/in/empty" /nonexistent/answers
    same "too many arguments"           "$W/in/empty" a b
    o1=$(GRADE_BOMB=1; export GRADE_BOMB; run "$O" "$W/in/empty" "$W/in/empty"; echo "$CODE:$OUT")
    o2=$(GRADE_BOMB=1; export GRADE_BOMB; run "$W/parity" "$W/in/empty" "$W/in/empty"; echo "$CODE:$OUT")
    [ "$o1" = "$o2" ] && ok "same behaviour: GRADE_BOMB" || bad "behaviour differs: GRADE_BOMB"
    sigint "$O";        o1="$CODE:$OUT"
    sigint "$W/parity"; o2="$CODE:$OUT"
    [ "$o1" = "$o2" ] && ok "same behaviour: Ctrl-C" || bad "behaviour differs: Ctrl-C"
else
    echo "== parity with the original: skipped (ref/ not present)"
fi

# ---------------------------------------------------------------------------
echo "== server reporting (mock daemon)"

cat > "$W/mock.py" <<'EOF'
import os, socket, sys
path, mode, log = sys.argv[1:4]
if os.path.exists(path):
    os.unlink(path)
s = socket.socket(socket.AF_UNIX)
s.bind(path)
s.listen(16)
with open(log, "w") as lf:
    while True:
        c, _ = s.accept()
        data = b""
        while not data.endswith(b"\n"):
            chunk = c.recv(4096)
            if not chunk:
                break
            data += chunk
        line = data.decode().strip()
        if line == "QUIT":
            break
        lf.write(line + "\n")
        lf.flush()
        if line.startswith("HELLO"):
            c.sendall(b"CLOSED not open yet\n" if mode == "closed" else b"OK\n")
        elif mode == "drop-defused" and " defused " in line:
            pass                        # hang up without a reply
        else:
            c.sendall(b"OK\n")
        c.close()
s.close()
os.unlink(path)
EOF

with_mock() {   # with_mock MODE INPUT -> OUT, CODE, LOG
    $PY "$W/mock.py" "$SOCK" "$1" "$W/mock.log" &
    local pid=$! i
    for i in $(seq 50); do [ -S "$SOCK" ] && break; sleep 0.1; done
    run "$W/notify" "$2"
    $PY -c "import socket,sys; s=socket.socket(socket.AF_UNIX); s.connect(sys.argv[1]); s.sendall(b'QUIT\n')" "$SOCK"
    wait $pid
    LOG=$(cat "$W/mock.log")
}

hex() { printf '%s' "$1" | od -An -tx1 | tr -d ' \n'; }

printf 'one\n\ntwo\nthree\nwrong\n' > "$W/in/n1"
with_mock ok "$W/in/n1"
WANT="HELLO $BOMB_ID
EVENT $BOMB_ID defused 1 $(hex one)
EVENT $BOMB_ID defused 2 $(hex two)
EVENT $BOMB_ID defused 3 $(hex three)
EVENT $BOMB_ID exploded 4 $(hex wrong)"
if [ "$LOG" = "$WANT" ] && [ "$CODE" = 8 ]; then
    ok "HELLO + EVENTs: phase = non-blank line count, input in hex"
else
    bad "event stream (exit $CODE)"
    diff <(echo "$WANT") <(echo "$LOG")
fi

with_mock ok "$W/in/secret"
case "$(echo "$LOG" | tail -1)" in
    "EVENT $BOMB_ID defused 7 $(hex seven)") ok "secret phase reports as phase 7" ;;
    *) bad "secret phase event: $(echo "$LOG" | tail -1)" ;;
esac

with_mock closed "$W/in/all"
case "$OUT" in *Welcome*) bad "refused bomb must not start" ;;
    *) expect "daemon refuses -> reason shown, exit 9" 9 \
           "This bomb is not active right now: CLOSED not open yet" ;; esac

rm -f "$SOCK"
run "$W/notify" "$W/in/all"
expect "daemon unreachable -> exit 9" 9 "Could not reach the record server. Ask a proctor for help."

with_mock drop-defused "$W/in/all"
expect "lost defusal report -> stop, ask for a re-run" 9 "Nothing was lost - please run the bomb again."

echo
echo "passed: $pass   failed: $fail"
[ $fail = 0 ]
