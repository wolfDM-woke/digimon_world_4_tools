"""Tiny two-pass PowerPC assembler (only what DW4 Gecko caves need) + a matching interpreter for tests.

Encodings follow the PowerPC 750 (Gekko) manual; the commonly used ones are cross-checked
against main.dol in warpmenu.py's self-test.
"""
import struct

def _d(op, a, b, imm): return ((op << 26) | (a << 21) | (b << 16) | (imm & 0xFFFF)) & 0xFFFFFFFF
def _x(rs, ra, rb, xo, rc=0): return (31 << 26) | (rs << 21) | (ra << 16) | (rb << 11) | (xo << 1) | rc

class Asm:
    def __init__(self, base):
        self.base = base          # address of the first emitted word (inside the code cave)
        self.items = []           # ("w", word) | ("br", kind, label, extra) | ("data", bytes) | ("label", name)
        self.labels = {}

    # -- layout ---------------------------------------------------------------------------
    def label(self, name): self.items.append(("label", name))
    def word(self, w): self.items.append(("w", w & 0xFFFFFFFF))
    def data(self, b):
        b = bytes(b)
        b += b"\0" * (-len(b) % 4)
        self.items.append(("data", b))
    def align(self): pass  # data() pads to 4 already

    # -- D-form -----------------------------------------------------------------------------
    def lwz(self, rt, d, ra):  self.word(_d(32, rt, ra, d))
    def lbz(self, rt, d, ra):  self.word(_d(34, rt, ra, d))
    def lhz(self, rt, d, ra):  self.word(_d(40, rt, ra, d))
    def stw(self, rs, d, ra):  self.word(_d(36, rs, ra, d))
    def stwu(self, rs, d, ra): self.word(_d(37, rs, ra, d))
    def lmw(self, rt, d, ra):  self.word(_d(46, rt, ra, d))
    def stmw(self, rs, d, ra): self.word(_d(47, rs, ra, d))
    def addi(self, rt, ra, i): self.word(_d(14, rt, ra, i))
    def li(self, rt, i):       self.addi(rt, 0, i)
    def lis(self, rt, i):      self.word(_d(15, rt, 0, i))
    def ori(self, ra, rs, i):  self.word(_d(24, rs, ra, i))
    def andi_(self, ra, rs, i): self.word(_d(28, rs, ra, i))
    def mulli(self, rt, ra, i): self.word(_d(7, rt, ra, i))
    def cmpwi(self, ra, i, cr=0): self.word(_d(11, cr << 2, ra, i))
    def li32(self, r, v):
        self.lis(r, (v >> 16) & 0xFFFF); self.ori(r, r, v & 0xFFFF)

    # -- X-form -----------------------------------------------------------------------------
    def or_(self, ra, rs, rb): self.word(_x(rs, ra, rb, 444))
    def mr(self, ra, rs):      self.or_(ra, rs, rs)
    def and_(self, ra, rs, rb): self.word(_x(rs, ra, rb, 28))
    def andc(self, ra, rs, rb): self.word(_x(rs, ra, rb, 60))
    def add(self, rt, ra, rb): self.word(_x(rt, ra, rb, 266))
    def cmpw(self, ra, rb, cr=0): self.word(_x(cr << 2, ra, rb, 0))
    def mflr(self, rt):  self.word(0x7C0802A6 | (rt << 21))
    def mtlr(self, rs):  self.word(0x7C0803A6 | (rs << 21))
    def mtctr(self, rs): self.word(0x7C0903A6 | (rs << 21))
    def bctrl(self):     self.word(0x4E800421)
    def crclr6(self):    self.word(0x4CC63182)
    def nop(self):       self.word(0x60000000)

    def call(self, addr, scratch=12):
        """Absolute call through CTR (clobbers r12, CTR, LR)."""
        self.li32(scratch, addr); self.mtctr(scratch); self.bctrl()

    # -- branches to labels -------------------------------------------------------------------
    def b(self, lbl):   self.items.append(("br", "b", lbl, 0))
    def bl(self, lbl):  self.items.append(("br", "bl", lbl, 0))
    def beq(self, lbl): self.items.append(("br", "bc", lbl, (12, 2)))
    def bne(self, lbl): self.items.append(("br", "bc", lbl, (4, 2)))
    def blt(self, lbl): self.items.append(("br", "bc", lbl, (12, 0)))
    def bge(self, lbl): self.items.append(("br", "bc", lbl, (4, 0)))

    # -- assemble -----------------------------------------------------------------------------
    def assemble(self):
        pc = self.base
        for it in self.items:
            if it[0] == "label": self.labels[it[1]] = pc
            elif it[0] == "data": pc += len(it[1])
            else: pc += 4
        out = bytearray(); pc = self.base
        for it in self.items:
            if it[0] == "label": continue
            if it[0] == "data": out += it[1]; pc += len(it[1]); continue
            if it[0] == "w": w = it[1]
            else:
                _, kind, lbl, extra = it
                off = self.labels[lbl] - pc
                if kind in ("b", "bl"):
                    assert -0x2000000 <= off < 0x2000000
                    w = 0x48000000 | (off & 0x03FFFFFC) | (1 if kind == "bl" else 0)
                else:
                    assert -0x8000 <= off < 0x8000, "bc out of range"
                    bo, bi = extra
                    w = (16 << 26) | (bo << 21) | (bi << 16) | (off & 0xFFFC)
            out += struct.pack(">I", w); pc += 4
        return bytes(out)


def gecko_c2(hook_addr, body_words, original):
    """Builds C2 lines: body + original instruction + terminator per the Gecko spec."""
    w = list(body_words) + [original]
    if len(w) % 2 == 0: w.append(0x60000000)
    w.append(0)
    lines = ["%08X %08X" % (0xC2000000 | (hook_addr & 0x01FFFFFF), len(w) // 2)]
    lines += ["%08X %08X" % (w[i], w[i + 1]) for i in range(0, len(w), 2)]
    return lines


class Cpu:
    """Interpreter for exactly the instructions Asm emits. Calls to hooked addresses run Python stubs."""
    def __init__(self, mem, stubs):
        self.r = [0] * 32; self.lr = 0; self.ctr = 0; self.cr = [0] * 8  # each cr field: (lt,gt,eq) bits as int 0b100/010/001
        self.mem = mem; self.stubs = stubs

    def r32(self, a): return struct.unpack(">I", self.mem.read(a, 4))[0]
    def w32(self, a, v): self.mem.write(a, struct.pack(">I", v & 0xFFFFFFFF))

    def _cmp(self, cr, a, b):
        a = a - (1 << 32) if a & 0x80000000 else a
        b = b - (1 << 32) if b & 0x80000000 else b
        self.cr[cr] = 0b100 if a < b else (0b010 if a > b else 0b001)

    def run(self, pc, stop, max_steps=10000):
        s16 = lambda x: x - 0x10000 if x & 0x8000 else x
        for _ in range(max_steps):
            if pc == stop: return
            w = self.r32(pc); op = w >> 26; rt = (w >> 21) & 31; ra = (w >> 16) & 31; imm = w & 0xFFFF
            ea = lambda: ((self.r[ra] if ra else 0) + s16(imm)) & 0xFFFFFFFF
            npc = pc + 4
            if op == 32: self.r[rt] = self.r32(ea())
            elif op == 34: self.r[rt] = self.mem.read(ea(), 1)[0]
            elif op == 40: self.r[rt] = int.from_bytes(self.mem.read(ea(), 2), 'big')
            elif op == 36: self.w32(ea(), self.r[rt])
            elif op == 37: a = ea(); self.w32(a, self.r[rt]); self.r[ra] = a
            elif op == 46:
                a = ea()
                for k in range(rt, 32): self.r[k] = self.r32(a); a += 4
            elif op == 47:
                a = ea()
                for k in range(rt, 32): self.w32(a, self.r[k]); a += 4
            elif op == 14: self.r[rt] = ((self.r[ra] if ra else 0) + s16(imm)) & 0xFFFFFFFF
            elif op == 15: self.r[rt] = (imm << 16) & 0xFFFFFFFF
            elif op == 24: self.r[ra] = self.r[rt] | imm
            elif op == 28: self.r[ra] = self.r[rt] & imm; self._cmp(0, self.r[ra], 0)
            elif op == 25: self.r[ra] = self.r[rt] | (imm << 16)
            elif op == 21:
                sh = (w >> 11) & 31; mb = (w >> 6) & 31; me = (w >> 1) & 31
                v = self.r[rt]; v = ((v << sh) | (v >> (32 - sh))) & 0xFFFFFFFF if sh else v
                m = 0
                for b in range(32):
                    inr = (mb <= b <= me) if mb <= me else (b >= mb or b <= me)
                    if inr: m |= 1 << (31 - b)
                self.r[ra] = v & m
                if w & 1: self._cmp(0, self.r[ra], 0)
            elif op == 7: self.r[rt] = (self.r[ra] * s16(imm)) & 0xFFFFFFFF
            elif op == 11: self._cmp(rt >> 2, self.r[ra], s16(imm) & 0xFFFFFFFF)
            elif op == 18:
                off = w & 0x03FFFFFC; off = off - 0x4000000 if off & 0x2000000 else off
                if w & 1: self.lr = npc
                npc = (pc + off) & 0xFFFFFFFF
            elif op == 16:
                bo = rt; bi = ra; off = s16(w & 0xFFFC)
                bit = (self.cr[bi >> 2] >> (2 - (bi & 3))) & 1
                take = bit == 1 if bo == 12 else bit == 0
                if take: npc = pc + off
            elif op == 19:
                if w == 0x4E800421:
                    self.lr = npc
                    self.stubs[self.ctr](self)          # stub returns to lr
                elif w == 0x4CC63182: pass
                else: raise RuntimeError("op19 %08x" % w)
            elif op == 31:
                xo = (w >> 1) & 0x3FF; rb = (w >> 11) & 31
                if xo == 444: self.r[ra] = self.r[rt] | self.r[rb]
                elif xo == 28: self.r[ra] = self.r[rt] & self.r[rb]
                elif xo == 60: self.r[ra] = self.r[rt] & ~self.r[rb] & 0xFFFFFFFF
                elif xo == 266: self.r[rt] = (self.r[ra] + self.r[rb]) & 0xFFFFFFFF
                elif xo == 0: self._cmp(rt >> 2, self.r[ra], self.r[rb])
                elif w & 0xFC1FFFFF == 0x7C0802A6: self.r[rt] = self.lr
                elif w & 0xFC1FFFFF == 0x7C0803A6: self.lr = self.r[rt]
                elif w & 0xFC1FFFFF == 0x7C0903A6: self.ctr = self.r[rt]
                else: raise RuntimeError("x-form %08x" % w)
            elif w == 0x60000000: pass
            else: raise RuntimeError("unhandled %08x at %08x" % (w, pc))
            pc = npc
        raise RuntimeError("did not finish")


class Mem:
    def __init__(self): self.pages = {}
    def read(self, a, n): return bytes(self.pages.get(a + i, 0) for i in range(n))
    def write(self, a, b):
        for i, x in enumerate(b): self.pages[a + i] = x
    def cstr(self, a):
        s = bytearray()
        while self.pages.get(a, 0): s.append(self.pages[a]); a += 1
        return s.decode("latin-1")
