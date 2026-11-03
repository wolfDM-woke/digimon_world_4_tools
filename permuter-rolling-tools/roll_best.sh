#!/bin/bash
# roll_best.sh - rolling decomp-permuter: run it for SECS, make its best output the new base.c, repeat.
#   bash roll_best.sh <permuter job dir> [rounds=30] [secs=60] [jobs=all cores] [stall=5] [merge_every=5]
# <permuter job dir> = a normal decomp-permuter dir (base.c, target.o, compile.sh, settings.toml), e.g.
#   nonmatchings/my_func. The permuter checkout is found by walking up from it (or set PERMUTER=/path).
# Every <merge_every> rounds (0 = never) tie_merge.py stacks small hunks from near-best outputs onto base.c.
# Stops after <rounds>, on a 0 score (exact), after <stall> rounds with no improvement, or if the new
# base.c stops compiling (restores the previous one). Ctrl-C stops the permuter too.
# Each round's outputs are moved to <dir>/roll/rN/; the original base is kept as <dir>/roll/base0.c.
# Log: <dir>/roll/roll.log. NO_INLINE=1 turns off perm_inline and skips outputs with an inline_fn helper
# (needed if your compile.sh only compiles/splices the one function).
D=$(cd "${1:?permuter job dir}" && pwd) || exit 1
ROUNDS=${2:-30}; SECS=${3:-60}; JOBS=${4:-$(sysctl -n hw.ncpu 2>/dev/null || nproc)}; STALL=${5:-5}; MERGE=${6:-5}
FN=$(basename "$D"); TOOLS="$(cd "$(dirname "$0")" && pwd)"
P=${PERMUTER:-$D}; while [ "$P" != / ] && [ ! -f "$P/permuter.py" ]; do P=$(dirname "$P"); done
[ -f "$P/permuter.py" ] || { echo "permuter.py not found above $D; set PERMUTER=/path/to/decomp-permuter"; exit 1; }
PY="$P/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3 || command -v python)
cd "$P" || exit 1
[ -f "$D/base.c" ] || { echo "no base.c in $D"; exit 1; }
mkdir -p "$D/roll"
[ -f "$D/roll/base0.c" ] || cp "$D/base.c" "$D/roll/base0.c"
LOG="$D/roll/roll.log"
if [ "${NO_INLINE:-0}" = 1 ]; then
  grep -q perm_inline "$D/settings.toml" || printf '\n[weight_overrides]\nperm_inline = 0\n' >> "$D/settings.toml"
fi

best_out() {  # lowest-score output-* dir in $D (skipping inline_fn ones with NO_INLINE=1), or nothing
  for o in $(ls -d "$D"/output-* 2>/dev/null | sed 's/.*output-\([0-9]*\)-\(.*\)/\1:\2/' | sort -n); do
    o="$D/output-${o/:/-}"
    [ "${NO_INLINE:-0}" = 1 ] && grep -q inline_fn "$o/source.c" && continue
    echo "$(basename "$o" | cut -d- -f2) $o"; return
  done
}

# fold in outputs left over from an earlier plain run
read SC OUT <<< "$(best_out)"
if [ -n "$OUT" ]; then
  cp "$OUT/source.c" "$D/base.c"; mkdir -p "$D/roll/r0"; mv "$D"/output-* "$D/roll/r0/"
  BEST=$SC; echo "round 0: start from earlier best $SC" | tee -a "$LOG"
else
  BEST=999999999
fi

# Ctrl-C / closing the window: stop the permuter too (it runs in the background), then exit
trap 'kill -TERM $PID $T 2>/dev/null; sleep 2; kill -KILL $PID 2>/dev/null; echo "interrupted" | tee -a "$LOG"; exit 130' INT TERM HUP
stall=0
for r in $(seq 1 "$ROUNDS"); do
  echo; echo "=== $FN round $r/$ROUNDS  best so far $BEST  ($SECS s, $JOBS jobs) ==="
  cp "$D/base.c" "$D/roll/prev_base.c"; T0=$(date +%s)
  "$PY" permuter.py "$D" -j "$JOBS" --best-only --stop-on-zero &
  PID=$!
  ( sleep "$SECS"; kill -TERM $PID 2>/dev/null; sleep 10; kill -KILL $PID 2>/dev/null; pkill -KILL -P $PID 2>/dev/null ) &
  T=$!
  wait $PID 2>/dev/null; kill $T 2>/dev/null
  if [ $(( $(date +%s) - T0 )) -lt 10 ]; then   # permuter quit at once: base.c broke
    cp "$D/roll/prev_base.c" "$D/base.c"; echo "round $r: permuter exited at once (base does not compile?) - stopped" | tee -a "$LOG"; break
  fi
  read SC OUT <<< "$(best_out)"
  if [ -n "$OUT" ] && [ "$SC" -lt "$BEST" ]; then
    cp "$OUT/source.c" "$D/base.c"; BEST=$SC; stall=0
    echo "round $r: new best $SC $(date +%T)" | tee -a "$LOG"
  else
    stall=$((stall+1)); echo "round $r: no improvement ($stall/$STALL) $(date +%T)" | tee -a "$LOG"
  fi
  mkdir -p "$D/roll/r$r"; mv "$D"/output-* "$D/roll/r$r/" 2>/dev/null
  if [ "$MERGE" -gt 0 ] && [ $((r % MERGE)) = 0 ] && [ "$BEST" != 0 ]; then
    echo "--- merging near-best outputs (tie_merge.py) ---"
    M=$("$PY" "$TOOLS/tie_merge.py" "$D" --jobs "$JOBS" --apply $([ "${NO_INLINE:-0}" = 1 ] && echo --no-inline) | tee /dev/stderr | sed -n 's/^result: [0-9]* -> \([0-9]*\) .*/\1/p')
    if [ -n "$M" ] && [ "$M" -lt "$BEST" ]; then
      BEST=$M; stall=0; echo "round $r: merge -> $M $(date +%T)" | tee -a "$LOG"
    else
      echo "round $r: merge found nothing $(date +%T)" | tee -a "$LOG"
    fi
  fi
  [ "$BEST" = 0 ] && { echo "EXACT"; break; }
  [ "$stall" -ge "$STALL" ] && { echo "stalled"; break; }
done
echo; echo "done: best $BEST, base.c = best source. Log $LOG"
