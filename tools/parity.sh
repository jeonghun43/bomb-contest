#!/usr/bin/env bash
#
# parity.sh - CMU-structure bombs must match the original bomb's code shape
# (specs/003-practice-bank AC-05, T048).
#
#   bash tools/parity.sh [SEEDS]          default: seeds 1..5
#
# For each seed, builds the CMU-structure bomb with the self-study variant
# families pinned (offline build) and compares it with the original
# self-study bomb using `asmdiff --mask-imm --data`: every function must have
# the same instructions apart from immediates, and data symbols must be laid
# out in the same order. Seeded constants are the only thing allowed to
# differ.
#
# Needs ref/cmu-selfstudy/bomb/bomb (dev machine; skipped elsewhere), docker,
# and capstone + pyelftools.

set -u

ROOT=$(cd "$(dirname "$0")/.." && pwd)
REF=$ROOT/ref/cmu-selfstudy/bomb/bomb
SEEDS=${1:-5}
PY=${PYTHON:-python3}
W=$ROOT/build/parity

if [ ! -f "$REF" ]; then
    echo "parity: skipped (ref/cmu-selfstudy/bomb/bomb not present)"
    exit 0
fi

# Self-study families: the variants the original was measured with.
FORCE="p1=strings p2=double p3=switch_dd p4=func4_bsearch p5=charmap p6=list secret=fun7"
FUNCS="main phase_1 phase_2 phase_3 func4 phase_4 phase_5 phase_6 fun7
       secret_phase sig_handler invalid_phase string_length strings_not_equal
       initialize_bomb initialize_bomb_solve blank_line skip explode_bomb
       read_six_numbers read_line phase_defused"

rm -rf "$W" && mkdir -p "$W"
DIRS=""
for s in $(seq 1 "$SEEDS"); do
    ROOT="$ROOT" $PY - "$s" "$W/cmu-$s" $FORCE <<'EOF' || exit 1
import os, sys
sys.path.insert(0, os.environ["ROOT"])
import bank
seed, out = int(sys.argv[1]), sys.argv[2]
force = dict(a.split("=", 1) for a in sys.argv[3:])
bank.render.write(bank.build("cmu", seed, force=force), out)
EOF
    DIRS="$DIRS $W/cmu-$s"
done

( cd "$ROOT" && $PY tools/buildbomb.py --src $DIRS >/dev/null ) || exit 1

bad=0
for s in $(seq 1 "$SEEDS"); do
    if R=$(cd "$ROOT" && $PY tools/asmdiff.py --mask-imm --data "$REF" \
               "$W/cmu-$s/bomb" $FUNCS); then
        echo "ok   seed $s: $(echo "$R" | tail -1)"
    else
        bad=$((bad + 1))
        echo "FAIL seed $s"
        echo "$R" | grep -v ' OK ' | head -60
    fi
done
echo
echo "parity: $((SEEDS - bad))/$SEEDS seeds match the original"
[ $bad = 0 ]
