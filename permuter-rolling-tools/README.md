# permuter rolling tools

Two add-ons for [decomp-permuter](https://github.com/simonlindholm/decomp-permuter). They don't change the permuter;
they drive it. Bash + Python 3, macOS/Linux (Windows: WSL or Git Bash, untested).

## roll_best.sh - restart from the best every round

A normal permuter run keeps randomizing from the *original* base.c (60% of the time it continues the last
candidate, otherwise it resets), so gains don't stack. This runs it in short rounds and makes each round's best
output the next round's base.c.

```
bash roll_best.sh <permuter job dir> [rounds=30] [secs=60] [jobs=all cores] [stall=5] [merge_every=5]
bash roll_best.sh nonmatchings/my_func 90 40
```

- Stops after `rounds`, on score 0, after `stall` rounds without improvement, or if a new base.c fails to
  compile (it restores the previous one). Ctrl-C stops the permuter too.
- Every round's outputs are kept in `<dir>/roll/rN/`; the original base is `<dir>/roll/base0.c`;
  log `<dir>/roll/roll.log`. Leftover `output-*` dirs from an earlier normal run are used as the start.
- `NO_INLINE=1 bash roll_best.sh ...` turns off `perm_inline` and skips outputs with its `inline_fn`
  helper - use it if your compile.sh only compiles/splices the one function (the helper gets lost).
- The permuter checkout is found by walking up from the job dir (or `PERMUTER=/path/to/decomp-permuter`);
  uses its `.venv/bin/python` if there is one.

### Guards against dropped code (on by default)

The permuter can lower the score by *deleting* code (a return hoisted above calls, stores chained away).
A new best or merge is only accepted if it is no worse than the current base on: call list vs target.o,
non-stack store count, and an optional `STORE_PATTERN` store class (e.g. `STORE_PATTERN='-32768\('` for GameCube
GX FIFO writes). It also refuses to roll if target.o doesn't contain the function (exit 3), and every
`CHECK_EVERY` rounds (default 10) checks the best against the start; if it drifted (guard worse or under
`CHECK_MIN_INSTRS_PCT`=90% of the instructions) base.c goes back to the last checkpoint and the roll stops.
Uses `fn_stats.py` (objdump picked from the ELF machine like the permuter does; `OBJDUMP=...` to override,
`GUARD=0` to turn it all off).

Other env: `MERGE_WITHIN` (0.02), `MERGE_MIN_NEAR`, `MERGE_LAST=1` (merge only rounds since the last merge).
A last merge runs before stopping on a stall. `bash roll_ctl.sh pause|resume|stop|status` controls running
rolls at the next round boundary. The permuter runs in its own process group so no workers are orphaned.

## tie_merge.py - stack changes from near-best outputs

Tied and near-tied outputs are usually wrong in *different* places. This takes every small hunk (<= 12 lines)
that an output within 1% of base.c changed, scores each one alone on top of base.c, then stacks the ones that
help (greedy, re-scoring each time). roll_best.sh calls it every `merge_every` rounds; it also runs alone:

```
python3 tie_merge.py <permuter job dir> [--within 0.01] [--max-hunk 12] [--jobs N] [--min-near N] [--min-round N] [--apply] [--no-inline]
```

Writes `<dir>/merge/best.c` and `merge.log`; `--apply` copies best.c to base.c (old one saved as
`merge/base_before_merge.c`). Hunks over `--max-hunk` lines are skipped on purpose (big structural rewrites
like `switch` -> `if (1)` can tie on score while drifting away from the real source).

## Example (GameCube, MWCC, 15.7 KB function, 12 jobs on an M3 Pro)

| | score |
|---|---|
| start | 497,540 |
| one plain 10 min run | 476,590 |
| 60 x 1 min rolling | 344,430 |
| + one tie_merge (14 hunks, < 1 min) | 342,755 |
| + 40 s rounds, merge every 5 | ~334,000 after ~20 more min |

Nowhere near matching for a function that size, but it shows the shape: rolling beats one long run on far-off
functions, and merging finds gains the permuter misses. For near-misses (a few lines off) a longer single run
from a good base is often better, since resetting keeps the search wide.
