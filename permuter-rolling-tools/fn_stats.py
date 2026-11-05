"""Facts about one function in an object file, for roll_best.sh's guards.

  python3 fn_stats.py <permuter job dir> <file.o>

Prints, one per line:
  instrs N          instructions in the function (0 = function not in the file)
  stores S P        stores not to the stack, and stores whose line matches $STORE_PATTERN (0 if unset)
  call <name>       one line per call relocation (repeat = called more than once)

Function name: func_name in <job dir>/settings.toml, else the job dir's name.
objdump: $OBJDUMP if set (a command, may include flags), else picked from the object's ELF machine
(same candidates decomp-permuter uses). Exit 2 = no objdump found.

Env (all optional):
  CALL_RELOCS    regex of relocation types that are calls (default: per architecture, below)
  CALL_IGNORE    regex of callee names to ignore (default: MWCC _savegpr_/_restgpr_ helpers, which follow
                 register allocation, not the code)
  STORE_PATTERN  regex; stores whose disassembly line matches it are counted separately - e.g. '-32768\\('
                 for GameCube GX FIFO writes (stw rN,-32768(rM) to 0xCC008000)
"""
import os, re, shlex, shutil, subprocess, sys

# ELF e_machine -> (objdump candidates, extra args, call relocs, store mnemonics, stack-base regex)
ARCHES = {
    3:   (['objdump'], ['--no-show-raw-insn'], r'R_386_(PC32|PLT32)$', None, None),          # x86: stores not tracked
    62:  (['objdump'], ['--no-show-raw-insn'], r'R_X86_64_(PLT32|PC32)$', None, None),
    8:   (['mips-linux-gnu-objdump', 'mips64-linux-gnu-objdump', 'mips64-elf-objdump'], ['-z', '-m', 'mips:4300'],
          r'R_MIPS_(26|PC26_S2)$', r'(sb|sh|sw|sd|swl|swr|sdl|sdr|swc1|sdc1|sc|scd|sq)$', r'\(\$?(sp|s8|fp)\)'),
    20:  (['powerpc-eabi-objdump'], ['-EB', '-mpowerpc', '-M', 'broadway'],
          r'R_PPC_(REL24|PLTREL24|LOCAL24PC)$', r'(st[a-z]*|psq_st[a-z]*)$', r'\(r1\)'),
    40:  (['arm-none-eabi-objdump'], ['-z'], r'R_ARM_(CALL|THM_CALL|PC24|JUMP24|THM_JUMP24|PLT32)$',
          r'(str|stm|vstr|vstm)[a-z0-9.]*$', r'\[sp|\bsp!?,'),
    183: (['aarch64-linux-gnu-objdump', 'aarch64-none-elf-objdump', 'objdump'], [], r'R_AARCH64_(CALL26|JUMP26)$',
          r'(st[rpu][a-z]*|stl[a-z]*)$', r'\[sp'),
}

def machine(path):
    with open(path, 'rb') as f:
        h = f.read(20)
    if h[:4] != b'\x7fELF': sys.exit('%s: not an ELF object' % path)
    return h[18] | (h[19] << 8) if h[5] == 1 else (h[18] << 8) | h[19]

def func_name(d):
    try:
        m = re.search(r'^\s*func_name\s*=\s*"([^"]+)"', open(os.path.join(d, 'settings.toml')).read(), re.M)
        if m: return m.group(1)
    except OSError: pass
    return os.path.basename(os.path.abspath(d))

def main():
    d, obj = sys.argv[1], sys.argv[2]
    fn = func_name(d)
    exe, args, call_re, store_re, stack_re = ARCHES.get(machine(obj), (['objdump'], [], r'CALL|PLT|REL24|_26$', None, None))
    if os.environ.get('OBJDUMP'):
        cmd = shlex.split(os.environ['OBJDUMP'])
    else:
        found = next((e for e in exe if shutil.which(e)), None)
        if not found: print('no objdump found (tried %s); set OBJDUMP=' % ', '.join(exe), file=sys.stderr); sys.exit(2)
        cmd = [found] + args
    out = subprocess.run(cmd + ['-dr', obj], capture_output=True, text=True, errors='replace').stdout
    call_re = re.compile(os.environ.get('CALL_RELOCS') or call_re)
    ignore = re.compile(os.environ.get('CALL_IGNORE', r'^_(save|rest)[gf]pr_'))
    pat = os.environ.get('STORE_PATTERN'); pat = re.compile(pat) if pat else None
    store_re = re.compile(store_re) if store_re else None
    stack_re = re.compile(stack_re) if stack_re else None
    head = re.compile(r'^[0-9a-f]+ <(.+)>:$')
    insn = re.compile(r'^\s+[0-9a-f]+:\s')
    reloc = re.compile(r'^\s+[0-9a-f]+:\s+(R_\S+)\s+(\S+)')
    inside, n, s, p, calls = False, 0, 0, 0, []
    for line in out.splitlines():
        h = head.match(line)
        if h: inside = h.group(1) == fn; continue
        if not inside: continue
        r = reloc.match(line)
        if r:
            name = re.sub(r'[+-]0x[0-9a-f]+$', '', r.group(2))
            if call_re.search(r.group(1)) and not ignore.search(name): calls.append(name)
            continue
        if not insn.match(line): continue
        n += 1
        text = line.split('\t')[-1].strip()
        mn = text.split()[0] if text else ''
        if store_re and store_re.match(mn) and not (stack_re and stack_re.search(text)):
            s += 1
            if pat and pat.search(text): p += 1
    print('instrs', n); print('stores', s, p)
    for c in calls: print('call', c)

if __name__ == '__main__':
    main()
