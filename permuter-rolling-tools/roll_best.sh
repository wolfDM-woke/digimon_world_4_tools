#!/bin/bash
# roll_best.sh - rolling decomp-permuter: run it for SECS, make its best output the new base.c, repeat.
#   bash roll_best.sh <permuter job dir> [rounds=30] [secs=60] [jobs=all cores] [stall=5] [merge_every=5]
# <permuter job dir> = a normal decomp-permuter dir (base.c, target.o, compile.sh, settings.toml), e.g.
#   nonmatchings/my_func. The permuter checkout is found by walking up from it (or set PERMUTER=/path).
# Stops after <rounds>, on a 0 score (exact), after <stall> rounds with no improvement (after one last merge),
# if the new base.c stops compiling (restores the previous one), on a failed checkpoint, or via roll_ctl.sh.
# Ctrl-C stops the permuter and all its workers too.
# Log: <dir>/roll/roll.log.
#
# Env (all optional):
#   NO_INLINE=1          turn off perm_inline and skip outputs with a new inline_fn helper (needed if your compile.sh
#                        only compiles/splices the one function). Outputs are not skipped if base.c already uses one.
#   MERGE_WITHIN=0.02    near-best = within this fraction of the best score, for tie_merge.py
#   MERGE_MIN_NEAR=N     merge only when more than N near-best outputs exist
#   MERGE_LAST=1         merge only outputs from rounds since the last merge (faster on long runs)
#   GUARD=0              turn off the dropped-code guards (below)
#   CHECK_EVERY=10       checkpoint interval in rounds (0 = off); CHECK_MIN_INSTRS_PCT=90
#   STORE_PATTERN=regex  extra store class the guard counts separately (see fn_stats.py)
#   OBJDUMP, CALL_RELOCS, CALL_IGNORE   see fn_stats.py
#   ROLL_CTL=dir         control dir for roll_ctl.sh (default: <this tools dir>/ctl)
D=$(cd "${1:?permuter job dir}" && pwd) || exit 1
ROUNDS=${2:-30}; SECS=${3:-60}; JOBS=${4:-$(sysctl -n hw.ncpu 2>/dev/null || nproc)}; STALL=${5:-5}; MERGE=${6:-5}
FN=$(basename "$D"); TOOLS="$(cd "$(dirname "$0")" && pwd)"; CTL="${ROLL_CTL:-$TOOLS/ctl}"
P=${PERMUTER:-$D}; while [ "$P" != / ] && [ ! -f "$P/permuter.py" ]; do P=$(dirname "$P"); done
[ -f "$P/permuter.py" ] || { echo "permuter.py not found above $D; set PERMUTER=/path/to/decomp-permuter"; exit 1; }
PY="$P/.venv/bin/python"; [ -x "$PY" ] || PY=$(command -v python3 || command -v python)
export PATH="$P/bin:$PATH"
cd "$P" || exit 1
[ -f "$D/base.c" ] || { echo "no base.c in $D"; exit 1; }
mkdir -p "$D/roll"
[ -f "$D/roll/base0.c" ] || cp "$D/base.c" "$D/roll/base0.c"
LOG="$D/roll/roll.log"

# perm_inline makes an "inline_fn" helper outside the function. If base.c already calls one (defined elsewhere in
# your build), every output has it, so skipping them all would mean nothing is ever accepted: skip only new ones.
SKIP_INL=0
if [ "${NO_INLINE:-0}" = 1 ]; then
  grep -q perm_inline "$D/settings.toml" || printf '\n[weight_overrides]\nperm_inline = 0\n' >> "$D/settings.toml"
  grep -q inline_fn "$D/base.c" || SKIP_INL=1
fi
newinl() { [ "$SKIP_INL" = 1 ] && grep -q inline_fn "$1"; }   # true = output has a new permuter-made inline_fn

# --- dropped-code guards ---
# The permuter can lower the score by deleting code: a return hoisted above calls, a statement dropped, stores
# chained away. Seen in practice: a function that lost 12 of 1381 calls, and one that kept every call but lost
# half its stores (355 of 680 hardware FIFO writes) over 37 rounds. So a new best is only accepted if it is no
# worse than the current base on any of: call list vs the target, store deficit, pattern-store deficit.
# guard 0: the target must contain the function at all, or the permuter is rewarded for deleting everything.
stats() {  # stats <file.o>: fn_stats.py output
  "$PY" "$TOOLS/fn_stats.py" "$D" "$1"
}
GUARD=${GUARD:-1}; TS=0; TP=0; NT=0
if [ "$GUARD" = 1 ]; then
  TS0=$(stats "$D/target.o"); rc=$?
  [ $rc = 2 ] && { echo "guards need objdump for this architecture: set OBJDUMP=... (or GUARD=0 to roll without guards)"; exit 1; }
  NT=$(sed -n 's/^instrs //p' <<< "$TS0")
  [ "${NT:-0}" -gt 0 ] || { echo "BAD TARGET: $D/target.o has no function $(sed -n 's/^func_name *= *"\(.*\)"/\1/p' "$D/settings.toml") - not rolled"; exit 3; }
  grep '^call ' <<< "$TS0" | sort | uniq -c > "$D/roll/target.calls"
  read TS TP <<< "$(sed -n 's/^stores //p' <<< "$TS0")"
fi
# calldiff <source.c>: compile it, print "calls,pattern,stores": differing callee-count lines vs the target,
# pattern-store deficit, store deficit (target - count, floor 0). "999999,999999,999999" if it does not compile.
calldiff() {
  [ "$GUARD" = 1 ] || { echo 0,0,0; return; }
  local o="$D/roll/calls_check.o" st c s p; rm -f "$o"
  bash "$D/compile.sh" "$1" -o "$o" >/dev/null 2>&1 && [ -s "$o" ] || { echo 999999,999999,999999; return; }
  st=$(stats "$o"); rm -f "$o"
  c=$(grep '^call ' <<< "$st" | sort | uniq -c | diff "$D/roll/target.calls" - | grep -c '^[<>]')
  read s p <<< "$(sed -n 's/^stores //p' <<< "$st")"
  p=$((TP - p)); s=$((TS - s)); echo "$c,$((p > 0 ? p : 0)),$((s > 0 ? s : 0))"
}
instrs() {  # instruction count of the function compiled from <source.c> (0 = does not compile)
  local o="$D/roll/instrs_check.o" n; rm -f "$o"
  bash "$D/compile.sh" "$1" -o "$o" >/dev/null 2>&1 && [ -s "$o" ] || { echo 0; return; }
  n=$(stats "$o" | sed -n 's/^instrs //p'); rm -f "$o"; echo "${n:-0}"
}
worse() {  # worse <a> <b>: true if any component of a ("calls,pattern,stores") is greater than b's
  local a b; IFS=, read -a a <<< "$1"; IFS=, read -a b <<< "$2"
  [ "${a[0]}" -gt "${b[0]}" ] || [ "${a[1]:-0}" -gt "${b[1]:-0}" ] || [ "${a[2]:-0}" -gt "${b[2]:-0}" ]
}

best_out() {  # lowest-score output-* dir in $D (skipping new inline_fn ones), or nothing
  for o in $(ls -d "$D"/output-* 2>/dev/null | sed 's/.*output-\([0-9]*\)-\(.*\)/\1:\2/' | sort -n); do
    o="$D/output-${o/:/-}"; newinl "$o/source.c" || { echo "$(basename "$o" | cut -d- -f2) $o"; return; }
  done
}
good_out() {  # best_out among outputs scoring below $BEST that pass the guard vs $CD; tries the 4 lowest. "score dir guard"
  local n=0 o sc c
  for o in $(ls -d "$D"/output-* 2>/dev/null | sed 's/.*output-\([0-9]*\)-\(.*\)/\1:\2/' | sort -n); do
    o="$D/output-${o/:/-}"; sc=$(basename "$o" | cut -d- -f2)
    [ "$sc" -lt "$BEST" ] || return; newinl "$o/source.c" && continue
    c=$(calldiff "$o/source.c"); worse "$c" "$CD" || { echo "$sc $o $c"; return; }
    echo "  output $sc rejected: guard $c worse than $CD (calls,pattern,stores: code dropped)" | tee -a "$LOG" >&2
    n=$((n+1)); [ $n -ge 4 ] && return
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
CD=$(calldiff "$D/base.c")
[ "$GUARD" = 1 ] && echo "guard (calls,pattern,stores) base vs target: $CD; target has $TS non-stack stores, $TP pattern stores" | tee -a "$LOG"

# checkpoint: every CHECK_EVERY rounds the current best is checked against the START (not the previous base, so
# slow drift shows too): guard no worse than at round 0, and at least CHECK_MIN_INSTRS_PCT % of min(start, target)
# instructions. Pass -> roll/checkpoint.c (+ checkpoint_rN.c). Fail -> base.c goes back to the last checkpoint and
# the roll stops ("butchered").
CHECK=${CHECK_EVERY:-10}; [ "$GUARD" = 1 ] || CHECK=0   # checkpoints use the same objdump stats
G0=$CD; N0=0; [ "$CHECK" -gt 0 ] && N0=$(instrs "$D/base.c"); NMIN=$(( (N0 < NT ? N0 : NT) * ${CHECK_MIN_INSTRS_PCT:-90} / 100 ))
cp "$D/base.c" "$D/roll/checkpoint.c"; CKR=0; CKBEST=$BEST
[ "$CHECK" -gt 0 ] && echo "checkpoint every $CHECK rounds: guard <= $G0, instrs >= $NMIN (start $N0, target $NT)" | tee -a "$LOG"

# The permuter runs in its own process group (set -m), so killing -$PID also ends its multiprocessing workers;
# killing only $PID leaves them behind as idle orphans (hundreds, many GB, after a night of rounds).
set -m
trap 'kill -TERM -- -$PID 2>/dev/null; kill $T 2>/dev/null; sleep 2; kill -KILL -- -$PID 2>/dev/null; echo "interrupted" | tee -a "$LOG"; exit 130' INT TERM HUP

# tie_merge.py over near-best outputs; kept only if it scores lower and passes the guard. $1 = log label.
merge_now() {
  echo "--- merging near-best outputs (tie_merge.py)$1 ---"
  cp "$D/base.c" "$D/roll/pre_merge.c"
  M=$(PERMUTER="$P" "$PY" "$TOOLS/tie_merge.py" "$D" --within "${MERGE_WITHIN:-0.02}" --jobs "$JOBS" \
        --min-near "${MERGE_MIN_NEAR:-0}" ${MERGE_LAST:+--min-round $((LASTM + 1))} \
        $([ "${NO_INLINE:-0}" = 1 ] && echo --no-inline) --apply \
      | tee /dev/stderr | sed -n 's/^result: [0-9]* -> \([0-9]*\) .*/\1/p')
  LASTM=$r
  if [ -n "$M" ] && [ "$M" -lt "$BEST" ] && C=$(calldiff "$D/base.c") && worse "$C" "$CD"; then
    cp "$D/roll/pre_merge.c" "$D/base.c"; echo "round $r:$1 merge -> $M rejected: guard $C worse than $CD $(date +%T)" | tee -a "$LOG"
  elif [ -n "$M" ] && [ "$M" -lt "$BEST" ]; then
    BEST=$M; CD=$C; stall=0; echo "round $r:$1 merge -> $M (guard $C) $(date +%T)" | tee -a "$LOG"
  else
    cp "$D/roll/pre_merge.c" "$D/base.c"
    echo "round $r:$1 merge found nothing or skipped (near-best <= ${MERGE_MIN_NEAR:-0}) $(date +%T)" | tee -a "$LOG"
  fi
}

stall=0; LASTM=0
for r in $(seq 1 "$ROUNDS"); do
  # round-boundary control (roll_ctl.sh): $CTL/stop ends the roll (one-shot), $CTL/pause holds until removed
  if [ -e "$CTL/stop" ]; then rm -f "$CTL/stop"; echo "round $r: stopped by roll_ctl $(date +%T)" | tee -a "$LOG"; break; fi
  if [ -e "$CTL/pause" ]; then echo "round $r: paused by roll_ctl $(date +%T)" | tee -a "$LOG"
    while [ -e "$CTL/pause" ]; do sleep 5; done; echo "round $r: resumed $(date +%T)" | tee -a "$LOG"; fi
  echo; echo "=== $FN round $r/$ROUNDS  best so far $BEST  ($SECS s, $JOBS jobs) ==="
  cp "$D/base.c" "$D/roll/prev_base.c"; T0=$(date +%s)
  "$PY" permuter.py "$D" -j "$JOBS" --best-only --stop-on-zero &
  PID=$!
  ( sleep "$SECS"; kill -TERM -- -$PID 2>/dev/null; sleep 10; kill -KILL -- -$PID 2>/dev/null ) &
  T=$!
  wait $PID 2>/dev/null; kill $T 2>/dev/null; kill -KILL -- -$PID 2>/dev/null   # workers that outlived the permuter
  if [ $(( $(date +%s) - T0 )) -lt 10 ]; then   # permuter quit at once: base.c broke
    cp "$D/roll/prev_base.c" "$D/base.c"; echo "round $r: permuter exited at once (base does not compile?) - stopped" | tee -a "$LOG"; break
  fi
  read SC OUT C <<< "$(good_out)"
  if [ -n "$OUT" ] && [ "$SC" -lt "$BEST" ]; then
    cp "$OUT/source.c" "$D/base.c"; BEST=$SC; CD=$C; stall=0
    echo "round $r: new best $SC (guard $C) $(date +%T)" | tee -a "$LOG"
  else
    stall=$((stall+1)); echo "round $r: no improvement ($stall/$STALL) $(date +%T)" | tee -a "$LOG"
  fi
  mkdir -p "$D/roll/r$r"; mv "$D"/output-* "$D/roll/r$r/" 2>/dev/null
  [ "$MERGE" -gt 0 ] && [ $((r % MERGE)) = 0 ] && [ "$BEST" != 0 ] && merge_now ""
  if [ "$CHECK" -gt 0 ] && [ $((r % CHECK)) = 0 ] && ! cmp -s "$D/base.c" "$D/roll/checkpoint.c"; then
    KG=$(calldiff "$D/base.c"); KN=$(instrs "$D/base.c")
    if worse "$KG" "$G0" || [ "$KN" -lt "$NMIN" ]; then
      cp "$D/roll/checkpoint.c" "$D/base.c"; BEST=$CKBEST
      echo "round $r: CHECKPOINT FAILED - butchered (guard $KG vs start $G0, instrs $KN vs min $NMIN); base.c back to round $CKR checkpoint ($CKBEST) - stopped $(date +%T)" | tee -a "$LOG"
      echo "butchered"; break
    fi
    cp "$D/base.c" "$D/roll/checkpoint.c"; cp "$D/base.c" "$D/roll/checkpoint_r$r.c"; CKR=$r; CKBEST=$BEST
    echo "round $r: checkpoint ok (guard $KG, instrs $KN) $(date +%T)" | tee -a "$LOG"
  fi
  [ "$BEST" = 0 ] && { echo "EXACT"; break; }
  # final merge: about to stop on a stall, but outputs from rounds since the last merge were never merged
  if [ "$stall" -ge "$STALL" ] && [ "$MERGE" -gt 0 ] && [ "$LASTM" -lt "$r" ]; then
    merge_now " final"; [ "$stall" = 0 ] && echo "round $r: final merge improved - rolling on" | tee -a "$LOG"
  fi
  [ "$stall" -ge "$STALL" ] && { echo "stalled"; break; }
done
[ "$BEST" = 999999999 ] && BEST="unchanged (never beat the base)"
echo; echo "done: best $BEST, base.c = best source. Log $LOG"
