"""Combine permuter outputs: take the hunks other near-best outputs changed vs the current base.c, try each one
on top of base.c, then stack the ones that lower the score (greedy, re-checking each on the stacked source).

  python3 tie_merge.py <permuter job dir> [--within 0.01] [--max-hunk 12] [--jobs N] [--apply]

The permuter checkout is found by walking up from the job dir (or set PERMUTER=/path/to/decomp-permuter).
Sources: every output-*/source.c under the job dir (and roll/r*/ from roll_best.sh) scoring within
--within (fraction) of the best. Hunks longer than --max-hunk lines are skipped (structural rewrites, e.g.
switch -> if (1)). --no-inline skips sources with a perm_inline "inline_fn" helper.
Writes <dir>/merge/best.c + merge.log; --apply copies best.c to base.c if it scored lower.
"""
import difflib, glob, os, re, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

def arg(k, d):
    return sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d

D = os.path.abspath(sys.argv[1]); FN = os.path.basename(D)
WITHIN, MAXH, JOBS = float(arg('--within', '0.01')), int(arg('--max-hunk', '12')), int(arg('--jobs', str(os.cpu_count())))
PERM = os.environ.get('PERMUTER') or D
while PERM != os.path.dirname(PERM) and not os.path.exists(os.path.join(PERM, 'permuter.py')): PERM = os.path.dirname(PERM)
if not os.path.exists(os.path.join(PERM, 'permuter.py')): sys.exit('permuter.py not found; set PERMUTER=/path/to/decomp-permuter')
ENV = dict(os.environ, PATH=os.path.join(PERM, 'bin') + os.pathsep + os.environ['PATH'])
PY = os.path.join(PERM, '.venv', 'bin', 'python')
if not os.path.exists(PY): PY = sys.executable
SKIP = ('output-', 'roll', 'merge', 'debug_source')
OUT = os.path.join(D, 'merge'); os.makedirs(OUT, exist_ok=True)
LOG = open(os.path.join(OUT, 'merge.log'), 'a')
def say(s):
    print(s, flush=True); LOG.write(s + '\n'); LOG.flush()

TMP = tempfile.mkdtemp(prefix='tiemerge_')
def score(lines):
    """compile lines as base.c in a scratch copy of the permuter dir; returns score or None"""
    w = tempfile.mkdtemp(dir=TMP)
    for f in os.listdir(D):                      # copy the job dir (compile.sh, target.o, settings, extras)
        if f.startswith(SKIP) or f == 'base.c': continue
        src = os.path.join(D, f)
        (shutil.copytree if os.path.isdir(src) else shutil.copy)(src, os.path.join(w, f))
    open(os.path.join(w, 'base.c'), 'w').write('\n'.join(lines) + '\n')
    r = subprocess.run([PY, os.path.join(PERM, 'permuter.py'), w, '--debug'], cwd=w, env=ENV, capture_output=True, text=True)
    m = re.search(r'base score = (\d+)', r.stdout)
    shutil.rmtree(w, ignore_errors=True)
    return int(m.group(1)) if m else None

base = open(os.path.join(D, 'base.c')).read().splitlines()
outs = []
for o in glob.glob(os.path.join(D, 'output-*')) + glob.glob(os.path.join(D, 'roll', 'r*', 'output-*')):
    m = re.search(r'output-(\d+)-\d+$', o)
    src = open(os.path.join(o, 'source.c')).read()
    if '--no-inline' not in sys.argv or 'inline_fn' not in src: outs.append((int(m.group(1)), o, src.splitlines()))
outs.sort(key=lambda x: x[0])
b0 = score(base)
say('== %s: base.c scores %s; %d outputs' % (FN, b0, len(outs)))
if b0 is None: sys.exit('base.c does not compile')
near = [x for x in outs if x[0] <= b0 * (1 + WITHIN)]

# hunks vs base: (i1, i2, replacement lines); dedupe identical ones
hunks, seen = [], set()
for sc, o, src in near:
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, base, src, autojunk=False).get_opcodes():
        if tag == 'equal' or max(i2 - i1, j2 - j1) > MAXH: continue
        key = (i1, i2, tuple(src[j1:j2]))
        if key not in seen: seen.add(key); hunks.append(key)
say('%d near-best sources (within %.1f%%), %d distinct hunks of <= %d lines' % (len(near), WITHIN * 100, len(hunks), MAXH))

def apply(lines, hs):
    out, pos = [], 0
    for i1, i2, rep in sorted(hs):
        if i1 < pos: return None              # overlapping hunks
        out += lines[pos:i1] + list(rep); pos = i2
    return out + lines[pos:]

# 1) each hunk alone
with ThreadPoolExecutor(JOBS) as ex:
    single = list(ex.map(lambda h: score(apply(base, [h])), hunks))
good = sorted([(s, h) for s, h in zip(single, hunks) if s is not None and s < b0], key=lambda x: x[0])
say('singles: %d lower than base, %d same/worse, %d did not compile' %
    (len(good), sum(s is not None and s >= b0 for s in single), sum(s is None for s in single)))

# 2) greedy stack, best single first; keep a hunk only if it still lowers the stacked score
chosen, cur = [], b0
for s1, h in good:
    trial = apply(base, chosen + [h])
    if trial is None: continue
    s = score(trial)
    if s is not None and s < cur:
        chosen.append(h); cur = s; say('  + hunk at line %d (alone %d) -> %d' % (h[0] + 1, s1, s))
best = apply(base, chosen)
open(os.path.join(OUT, 'best.c'), 'w').write('\n'.join(best) + '\n')
say('result: %s -> %s with %d hunks stacked (best single was %s)' % (b0, cur, len(chosen), good[0][0] if good else None))
if '--apply' in sys.argv and cur < b0:
    shutil.copy(os.path.join(D, 'base.c'), os.path.join(OUT, 'base_before_merge.c'))
    shutil.copy(os.path.join(OUT, 'best.c'), os.path.join(D, 'base.c')); say('applied to base.c')
shutil.rmtree(TMP, ignore_errors=True)
