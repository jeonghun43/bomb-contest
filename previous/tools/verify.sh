#!/usr/bin/env bash
#
# verify.sh - Automated acceptance checks for seeded bomb variants.
#
#   bash tools/verify.sh [FROM] [TO]
#
# Covers AC-01..AC-07 from specs/001-new-bomb/spec.md. Exits non-zero on the
# first failure so that a broken variant can never reach a contestant.

set -u

FROM="${1:-1}"
TO="${2:-20}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT

pass=0
fail=0

ok()   { pass=$((pass + 1)); }
bad()  { fail=$((fail + 1)); echo "  FAIL: $*"; }

# run <answer-file> -> sets RC and OUT, log left in $SCRATCH/bomb.log
run() {
    rm -f "$SCRATCH/bomb.log"
    OUT="$(cd "$SCRATCH" && "$ROOT/bomb" "$1" 2>&1)"
    RC=$?
}

# Replace line N of a file with the given text.
sub_line() {
    awk -v n="$2" -v repl="$3" 'NR==n {print repl; next} {print}' "$1"
}

# Nudge the last integer of a line by one; for phase 5 flip the last letter.
near_miss() {
    python3 - "$1" <<'PY'
import re, sys
line = sys.argv[1]
if re.fullmatch(r"[LR]+", line.strip()):
    s = line.strip()
    print(s[:-1] + ("L" if s[-1] == "R" else "R"))
else:
    toks = line.split()
    toks[-1] = str(int(toks[-1]) + 1)
    print(" ".join(toks))
PY
}

echo "verify: seeds $FROM..$TO"

for seed in $(seq "$FROM" "$TO"); do
    echo "seed $seed"

    if ! make -C "$ROOT" SEED="$seed" bomb >/dev/null 2>"$SCRATCH/build.err"; then
        bad "build failed"
        sed 's/^/    /' "$SCRATCH/build.err"
        continue
    fi
    ok

    SOL="$ROOT/build/seed-$seed/solution.txt"
    SECRET="$ROOT/build/seed-$seed/solution_secret.txt"

    # ---- AC-01: the published answers defuse all six phases -------------
    run "$SOL"
    if [ "$RC" -eq 0 ] && [[ "$OUT" == *"Congratulations"* ]]; then ok
    else bad "AC-01 answers rejected (rc=$RC)"; echo "$OUT" | sed 's/^/    /'; fi

    # ---- AC-07: defusals are logged -------------------------------------
    if [ "$(grep -c 'DEFUSED' "$SCRATCH/bomb.log" 2>/dev/null)" -ge 6 ]; then ok
    else bad "AC-07 log missing defusal records"; fi

    # ---- AC-02: the hidden stage opens and can be solved -----------------
    run "$SECRET"
    if [ "$RC" -eq 0 ] && [[ "$OUT" == *"hidden stage"* ]] \
       && [[ "$OUT" == *"Congratulations"* ]]; then ok
    else bad "AC-02 secret phase not defused (rc=$RC)"; echo "$OUT" | sed 's/^/    /'; fi

    # The hidden stage must stay closed without the token.
    run "$SOL"
    if [[ "$OUT" != *"hidden stage"* ]]; then ok
    else bad "AC-02 secret phase opened without the token"; fi

    # ---- AC-03: each phase explodes on wrong input ----------------------
    for n in 1 2 3 4 5 6; do
        good_line="$(sed -n "${n}p" "$SOL")"
        for wrong in "0 0 0 0 0 0" "zzz" "$(near_miss "$good_line")"; do
            sub_line "$SOL" "$n" "$wrong" > "$SCRATCH/wrong.txt"
            run "$SCRATCH/wrong.txt"
            if [ "$RC" -ne 0 ] && [[ "$OUT" == *"BOOM"* ]] \
               && grep -q "phase=$n | EXPLODED" "$SCRATCH/bomb.log"; then ok
            else bad "AC-03 phase $n did not explode on '$wrong' (rc=$RC)"; fi
        done
    done

    # ---- AC-04: phase 3 has exactly one starting square ------------------
    hits=0
    for r in 0 1 2 3; do
        for c in 0 1 2 3; do
            head -2 "$SOL" > "$SCRATCH/p3.txt"
            echo "$r $c" >> "$SCRATCH/p3.txt"
            run "$SCRATCH/p3.txt"
            [[ "$OUT" == *"Halfway there"* ]] && hits=$((hits + 1))
        done
    done
    if [ "$hits" -eq 1 ]; then ok
    else bad "AC-04 phase 3 has $hits solutions, expected 1"; fi

    # ---- AC-04: the secret answer is unique over the whole input range ---
    if python3 "$ROOT/tools/check_secret_unique.py" \
           --seed "$seed" >/dev/null 2>&1; then ok
    else bad "AC-04 secret phase answer is not unique"; fi
done

# ---- AC-06: the package leaks nothing --------------------------------------
if make -C "$ROOT" SEED="$TO" dist >/dev/null 2>&1; then
    leak=0
    for f in phases.c support.c util.c notify.c bombdata.h bombdata.c \
             solution.txt solution_secret.txt SOLUTION.md; do
        [ -e "$ROOT/dist/bomb-$TO/$f" ] && { bad "AC-06 leaked $f"; leak=1; }
    done
    [ "$leak" -eq 0 ] && ok
else
    bad "AC-06 dist target failed"
fi

# ---- AC-11: the server judge matches the compiled bomb ---------------------
if python3 "$ROOT/tools/fuzz_checker.py" --from "$FROM" --to "$TO" \
       > "$SCRATCH/fuzz.out" 2>&1 && grep -q "0 mismatches" "$SCRATCH/fuzz.out"; then
    ok
    tail -1 "$SCRATCH/fuzz.out" | sed 's/^/  /'
else
    bad "AC-11 checker disagrees with the bomb"
    tail -5 "$SCRATCH/fuzz.out" | sed 's/^/    /'
fi

echo
echo "passed: $pass   failed: $fail"
[ "$fail" -eq 0 ] || exit 1
