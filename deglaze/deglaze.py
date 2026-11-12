#!/usr/bin/env python3
"""deGlaze: find "matched" decomp code whose bytes come from assembly instead of real C/C++.

A function written as an `asm` block copied from the disassembly always matches, so it proves nothing. objdiff still
counts it as matched (green). deGlaze lists every such function so you can move it back to unmatched (the "purple"
asm-body state) and keep your progress numbers honest.

Works on any decomp-toolkit (dtk-template) project with an objdiff report:
  python3 deglaze.py --project PATH_TO_DTK_PROJECT [options]

For each unit in the report that has a source file it scans that file (and the local headers it includes) for
  asm fn     a function declared `asm` (MWCC asm function)
  inline     an asm statement inside a C/C++ function (`asm { }`, `asm(...)`, `__asm`, `__asm__`, `asm volatile`)
  asm stmt   a file-level asm statement
and looks the function up in the report to see whether objdiff counts it as matched (100%).
`copied?` marks asm that looks pasted from a disassembler (dtk labels like `L_80xxxxxx`, `.L_80xxxxxx`, `lbl_80xxxxxx`,
`jumptable_80xxxxxx`, address comments `/* 80xxxxxx`, `opword`, raw `.long 0x...` words).

Options
  --project DIR    the dtk project (holds configure.py and build/); default: current directory
  --report FILE    objdiff report.json; default: the first DIR/build/*/report.json
  --own CATS       comma list of progress categories that are YOUR decomp (e.g. game,engine). Any asm in a matched
                   function there is glaze. Default: every category. Other categories (SDK/libraries, where the
                   original source has real asm) only fail the check when the asm looks copied.
  --scan DIR       also scan source drafts outside the build (*.c, *.cpp, *.cp, *.h; repeatable)
  --include DIR    extra include directory for resolving local headers (repeatable)
  --all            also list asm in the non-own categories
  --tsv FILE       write every hit as tab-separated values
Exit status: 1 if any matched function in an own category is asm, or any matched asm anywhere looks copied; else 0.
Read-only. Needs Python 3.6+, no packages. Limits: finds asm by keyword only; code smuggled in some other way (raw bytes
in a data array that gets called, an assembler .s file in the build) is not detected, and `copied?` only catches pastes
that kept their labels. Read the code before deciding.
"""
import glob, json, os, re, sys

ASM_KW = re.compile(r'\b(?:asm|__asm__|__asm)\b')
COPIED = re.compile(r'\.?\bL_8[0-9A-Fa-f]{7}|\blbl_8[0-9A-Fa-f]{7}|\bjumptable_8[0-9A-Fa-f]{7}|/\*\s*8[0-9A-Fa-f]{7}\b'
                    r'|\bopword\b|\.long\s+0x[0-9A-Fa-f]{8}')
INCLUDE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.M)
SRC_EXT = ('.c', '.cpp', '.cp', '.cc', '.h', '.hpp')

def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

def args(name):
    return [sys.argv[i + 1] for i, a in enumerate(sys.argv[:-1]) if a == name]

def strip(src):
    """blank out comments and string/char literals, keeping offsets and newlines"""
    out, i, n = list(src), 0, len(src)
    while i < n:
        c = src[i]
        if src.startswith('//', i):
            j = src.find('\n', i); j = n if j < 0 else j
            for k in range(i, j): out[k] = ' '
            i = j
        elif src.startswith('/*', i):
            j = src.find('*/', i + 2); j = n if j < 0 else j + 2
            for k in range(i, j):
                if src[k] != '\n': out[k] = ' '
            i = j
        elif c in '"\'':
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == '\\' else 1
            for k in range(i + 1, min(j, n)):
                if src[k] != '\n': out[k] = ' '
            i = j + 1
        else:
            i += 1
    return ''.join(out)

def scan(path):
    """[(kind, function name, line, copied?)] for one source file"""
    try: raw = open(path, encoding='utf-8', errors='replace').read()
    except OSError: return []
    code = strip(raw); hits = []
    if not ASM_KW.search(code): return hits
    # depth counts braces inside functions only; extern "C" { } and namespace { } blocks are transparent
    depth, start, last_end, fn, fn_asm, wrap = 0, None, 0, None, False, 0
    for m in re.finditer(r'[{};]', code):
        ch = m.group()
        if ch == '{':
            if depth == 0:
                decl = code[last_end:m.start()]
                if re.search(r'(?:\bextern\s*"\s*"|\bnamespace(?:\s+\w+)?)\s*$', decl):
                    wrap += 1; last_end = m.end(); continue
                name = re.findall(r'([A-Za-z_][\w:~]*)\s*\(', decl)
                fn = name[-1] if name else None
                fn_asm = bool(fn and ASM_KW.search(decl.split('(')[0]))
                start = m.start()
            depth += 1
        elif ch == '}':
            if depth == 0:
                wrap = max(0, wrap - 1); last_end = m.end(); continue
            depth -= 1
            if depth == 0 and start is not None:
                body, rawbody = code[start:m.end()], raw[start:m.end()]
                line = raw.count('\n', 0, start) + 1
                if fn_asm: hits.append(('asm fn', fn, line, bool(COPIED.search(rawbody))))
                elif fn and ASM_KW.search(body): hits.append(('inline', fn, line, bool(COPIED.search(rawbody))))
                start, fn = None, None
            if depth == 0: last_end = m.end()
        elif depth == 0:
            last_end = m.end()
    for m in re.finditer(r'^\s*(?:static\s+)?asm\b[^;{]*;', code, re.M):
        hits.append(('asm stmt', None, raw.count('\n', 0, m.start()) + 1, bool(COPIED.search(m.group()))))
    return hits

def headers(path, dirs, seen):
    """local headers a file includes, recursively"""
    try: txt = open(path, encoding='utf-8', errors='replace').read()
    except OSError: return
    for inc in INCLUDE.findall(txt):
        for base in [os.path.dirname(path)] + dirs:
            p = os.path.normpath(os.path.join(base, inc))
            if os.path.isfile(p):
                if p not in seen: seen.add(p); headers(p, dirs, seen)
                break

def key(name):
    return re.sub(r'\W+', '_', name.replace('::', '__')).lower()

def report_fn(src_name, funcs):
    """the report's function for a source name: exact, else Class::method -> Class__method[_suffix] if unique"""
    if not src_name: return None
    if src_name in funcs: return src_name
    k = key(src_name)
    c = [f for f in funcs if key(f) == k or key(f).startswith(k + '_')]
    return c[0] if len(c) == 1 else None

def main():
    if '-h' in sys.argv or '--help' in sys.argv: print(__doc__); return 0
    proj = os.path.abspath(arg('--project', '.'))
    rp = arg('--report') or next(iter(sorted(glob.glob(os.path.join(proj, 'build', '*', 'report.json')))), None)
    if not rp or not os.path.isfile(rp):
        sys.exit('no report.json (build the project, or pass --report FILE)')
    own = set(c for c in (arg('--own') or '').split(',') if c) or None
    inc = [os.path.join(proj, 'src'), os.path.join(proj, 'include')] + [os.path.abspath(d) for d in args('--include')]
    rep = json.load(open(rp))
    rows, cache = [], {}
    def is_own(cat): return own is None or any(c in own for c in cat.split(','))
    for u in rep.get('units', []):
        md = u.get('metadata', {}); sp = md.get('source_path')
        if not sp: continue
        src = os.path.join(proj, sp)
        if not os.path.isfile(src): continue
        cat = ','.join(md.get('progress_categories') or ['-'])
        funcs = {f['name']: f for f in u.get('functions', [])}
        seen = set(); headers(src, inc, seen)
        for f in [src] + sorted(seen):
            if f not in cache: cache[f] = scan(f)
            for kind, name, line, copied in cache[f]:
                rf = report_fn(name, funcs)
                if f != src and not rf: continue      # header asm this unit doesn't emit as its own function
                fz = funcs[rf].get('fuzzy_match_percent') if rf else None
                rows.append(dict(cat=cat, own=is_own(cat), unit=u['name'], file=os.path.relpath(f, proj), line=line,
                                 kind=kind, fn=rf or name or '-', matched=fz == 100,
                                 size=int(funcs[rf].get('size') or 0) if rf else 0, copied=copied))
    for d in args('--scan'):
        for f in sorted(p for p in glob.glob(os.path.join(d, '**', '*'), recursive=True) if p.endswith(SRC_EXT)):
            for kind, name, line, copied in scan(f):
                rows.append(dict(cat='draft', own=True, unit='-', file=os.path.relpath(f), line=line, kind=kind,
                                 fn=name or '-', matched=None, size=0, copied=copied))
    mine = [r for r in rows if r['own']]; lib = [r for r in rows if not r['own']]
    def show(title, rs):
        print('%s: %d hits, %d in matched fns (%d B), %d look copied from disassembly' % (title, len(rs),
              sum(1 for r in rs if r['matched']), sum(r['size'] for r in rs if r['matched']), sum(1 for r in rs if r['copied'])))
        for r in sorted(rs, key=lambda r: (r['matched'] is not True, r['cat'], r['file'], r['line'])):
            st = 'MATCHED' if r['matched'] else 'draft' if r['matched'] is None else 'not matched'
            print('  %-10s %-11s %-8s %-42s %s:%d%s' % (r['cat'][:10], st, r['kind'], r['fn'][:42], r['file'], r['line'],
                                                       '  copied?' if r['copied'] else ''))
    show('Own code (%s; should be 0)' % (','.join(sorted(own)) if own else 'all categories'), mine)
    if own:
        if '--all' in sys.argv: show('Other categories (libraries; original asm is normal there)', lib)
        else: print('Other categories: %d hits (%d look copied); --all lists them' % (len(lib), sum(1 for r in lib if r['copied'])))
    tot = rep.get('measures', {})
    bad = [r for r in rows if r['matched'] and (r['own'] or r['copied'])]
    if tot.get('total_code') and bad:
        b = sum(r['size'] for r in bad); mc, tc = int(tot.get('matched_code', 0)), int(tot['total_code'])
        print('Matched code without them: %.2f%% (report: %.2f%%), %d fns, %d B' % (100 * (mc - b) / tc, 100 * mc / tc, len(bad), b))
    tsv = arg('--tsv')
    if tsv:
        with open(tsv, 'w') as f:
            ks = ('cat', 'matched', 'kind', 'fn', 'size', 'copied', 'file', 'line', 'unit')
            f.write('\t'.join(ks) + '\n')
            for r in rows: f.write('\t'.join(str(r[k]) for k in ks) + '\n')
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
