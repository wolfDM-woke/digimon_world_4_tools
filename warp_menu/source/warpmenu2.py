#!/usr/bin/env python3
"""DW4 (GDJEB2, Digimon World 4 USA) warp menu Gecko code generator + self-test. Version 2.

  Hold Z: D-pad Right/Left = pick a destination, D-pad Up = warp there.

v2 changes: every verified room (from room_names.csv, checked in game 2026-10-18), the entrance number
each room's own scripts use, room labels embedded in the code, and an optional on-screen message
(the game's Lua be:MsgBox) when the selection changes.

How it warps: the same two messages the game's own loading zones send (funcStageChange in the
room scripts), run through the game's Lua (igLuaState::runString):
    be:sd("PLAYERPOINT",nil,-1,"SETGENERATEPOS","I<entrance>")
    be:sd("STAGECTL",nil,-1,"NEXTSTAGE","<stage>")

Hook: 0x8034C4CC in Player_InputHandler, `mr r26,r3` right after PadMgr_GetPad returns the pad
record in r3. It is right after a call, so every volatile register except r3 is dead; and it runs
before Spin2win (0x8034C4D0) and the Lua mailbox (0x8034C4D4), so while Z is held the D-pad bits
are removed from the pad record and those codes never see the menu presses.

Usage:  python warpmenu2.py [--mod 0x200] [--no-msgbox] [--out GDJEB2_warp_menu.txt]
"""
import argparse, csv, struct, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ppcasm import Asm, gecko_c2, Cpu, Mem

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = 0x8034C4CC
ORIGINAL = 0x7C7A1B78          # mr r26,r3 (checked against main.dol below)
OSREPORT = 0x8025DF8C
SPRINTF = 0x80099CA4
RUNSTRING = 0x802726A8         # igLuaState::runString(this=beLuaState, text)
BELUA = 0x808416C8             # beLua object (fixed), vtable 0x804DE70C, +0x18 -> beLuaState
BELUA_VT = 0x804DE70C
ID_LEN, LABEL_LEN = 10, 28     # table entry: stage id (10, NUL padded) + entrance (1) + pad (1) + label offset (2)
ENT = 14
SHORT = [(' floor ', ' F'), ('Main Lobby: ', 'Lobby '), ('Goburimon Fortress - ', 'Fortress '),
         (' (Machine Pit, last boss)', ' (last boss)'), (' (Machine Pit)', ''), (' - ends the session', '')]

# rooms that must not be in the menu: boot/title/save screens (no field to stand in)
SKIP = {'stagis08', 'stagis09', 'stagis10', 'stagis11', 'stagis12'}


def load_dests():
    """(stage id, entrance, label) for every room with a known entrance, in story order."""
    ent = {}
    for r in csv.DictReader(open(os.path.join(HERE, 'entrances.csv'))):
        ent[r['room']] = min(int(x.split('(')[0]) for x in r['entrances (uses)'].split())
    out = []
    names = os.path.join(HERE, 'room_names.csv')
    if not os.path.exists(names): names = os.path.join(HERE, '..', 'room_names.csv')
    for r in csv.DictReader(open(names, encoding='utf-8')):
        k = r['room'].lower()
        if k in SKIP or k not in ent: continue
        label = r['place'] if r['confidence'] == 'VERIFIED' else r['place'] + ' (?)'
        if k == 'stagis20': label = 'Credits - ends the session'
        for a, b in SHORT: label = label.replace(a, b)
        label = label.replace('"', "'").encode('ascii', 'replace').decode()[:LABEL_LEN - 1]
        out.append((r['room'], ent[k], label))
    return out


DESTS = load_dests()
LABELS = False      # --labels: embed place names in the code (bigger; may not fit beside other codes)
LUA_FMT = b'be:sd("PLAYERPOINT",nil,-1,"SETGENERATEPOS","I<%d>") be:sd("STAGECTL",nil,-1,"NEXTSTAGE","%s")\0'
MSG_FMT = b'be:MsgBox("WARP %d/%d: %s",0)\0'
# pad record D-pad bits (mask 0xF0), confirmed in game 2026-10-18
DPAD_UP, DPAD_RIGHT, DPAD_DOWN, DPAD_LEFT = 0x10, 0x20, 0x40, 0x80
BUF = 0x80          # sprintf buffer at r1+0x80 .. +0xFF (frame is 0x100)


def build(mod_mask, cave=0x80001800, msgbox=True, labels_in_code=False):
    n = len(DESTS)
    for s, e, l in DESTS:
        assert len(s) < ID_LEN and 0 <= e < 256 and len(l) < LABEL_LEN
    a = Asm(cave)
    # prologue
    a.stwu(1, -0x100, 1); a.mflr(0); a.stw(0, 0x104, 1); a.stmw(3, 0x08, 1)
    a.mr(31, 3)                                   # r31 = pad record
    a.bl("code")                                  # LR = data
    a.label("data")
    a.word(0)                                     # +0 D-pad bits held last frame (own edge detection)
    a.word(0)                                     # +4 selected index (warp_overlay.py reads it: just before fmt_sel)
    a.label("fmt_sel"); a.data(b"WARP %d/%d %s %s\n\0")
    a.label("fmt_go"); a.data(b"WARP go %s entrance %d result=%d\n\0")
    a.label("fmt_nolua"); a.data(b"WARP no Lua state\n\0")
    a.label("fmt_lua"); a.data(LUA_FMT)
    a.label("fmt_msg"); a.data(MSG_FMT)            # data() pads every string to 4 bytes
    a.label("fmt_msgres"); a.data(b"WARP msg result=%d\n\0")
    # labels packed one after another; the table stores each one's offset from "data"
    head = 8 + sum(len(x) + (-len(x) % 4) for x in (b"WARP %d/%d %s %s\n\0", b"WARP go %s entrance %d result=%d\n\0",
                                                    b"WARP no Lua state\n\0", LUA_FMT, MSG_FMT,
                                                    b"WARP msg result=%d\n\0"))
    tsize = ENT * len(DESTS); tsize += -tsize % 4
    pool, offs = b"", []
    for i, (_, _, l) in enumerate(DESTS):
        if labels_in_code: offs.append(head + tsize + len(pool)); pool += l.encode() + b"\0"
        else: offs.append(head + i * ENT)         # compact: the "label" is the stage id itself
    a.label("table")
    a.data(b"".join(s.encode().ljust(ID_LEN, b"\0") + bytes([e, 0]) + struct.pack(">H", o)
                    for (s, e, _), o in zip(DESTS, offs)))
    a.label("labels")
    if pool: a.data(pool)
    a.label("code")
    a.mflr(30)                                    # r30 = data
    a.lwz(4, 0x44, 31)                            # held
    # the pad record's "pressed" bits repeat while a button is held, so detect presses ourselves
    a.andi_(27, 4, 0xF0)                          # r27 = D-pad held now
    a.lwz(9, 0, 30); a.stw(27, 0, 30)             # r9 = held last frame; remember this frame
    a.andi_(0, 4, mod_mask)
    a.beq("exit")
    a.andc(27, 27, 9)                             # r27 = D-pad pressed this frame (kept across calls)
    a.li32(6, 0xFFFFFF0F)                         # hide the D-pad from the game/other codes
    a.and_(7, 4, 6); a.stw(7, 0x44, 31)
    a.lwz(7, 0x48, 31); a.and_(7, 7, 6); a.stw(7, 0x48, 31)
    a.lwz(8, 4, 30); a.li(29, 0)
    a.andi_(0, 27, DPAD_RIGHT); a.beq("no_r")
    a.addi(8, 8, 1); a.cmpwi(8, n); a.blt("r_ok"); a.li(8, 0)
    a.label("r_ok"); a.li(29, 1)
    a.label("no_r")
    a.andi_(0, 27, DPAD_LEFT); a.beq("no_l")
    a.addi(8, 8, -1); a.cmpwi(8, 0); a.bge("l_ok"); a.li(8, n - 1)
    a.label("l_ok"); a.li(29, 1)
    a.label("no_l")
    a.cmpwi(8, 0); a.blt("fix"); a.cmpwi(8, n); a.blt("in_range")   # guard against a corrupt index
    a.label("fix"); a.li(8, 0)
    a.label("in_range")
    a.stw(8, 4, 30)
    a.mr(25, 8)                                   # r25 = index (kept across calls)
    a.mulli(28, 8, ENT); a.add(28, 28, 30)
    a.items.append(("tableoff",))                 # r28 += table - data  -> r28 = entry
    a.cmpwi(29, 0); a.beq("no_sel")
    a.lhz(24, ID_LEN + 2, 28); a.add(24, 24, 30)  # r24 = label (kept across calls)
    a.items.append(("dataoff", 3, "fmt_sel")); a.addi(4, 25, 1); a.li(5, n); a.mr(6, 28); a.mr(7, 24)
    a.crclr6(); a.call(OSREPORT)
    if msgbox:                                    # show the selection in game
        a.addi(3, 1, BUF); a.items.append(("dataoff", 4, "fmt_msg")); a.addi(5, 25, 1); a.li(6, n); a.mr(7, 24)
        a.crclr6(); a.call(SPRINTF)
        lua_state(a, "m_nolua")
        a.addi(4, 1, BUF); a.call(RUNSTRING)
        a.mr(4, 3); a.items.append(("dataoff", 3, "fmt_msgres")); a.crclr6(); a.call(OSREPORT)
        a.b("no_sel")
        a.label("m_nolua")
        a.items.append(("dataoff", 3, "fmt_nolua")); a.crclr6(); a.call(OSREPORT)
    a.label("no_sel")
    a.andi_(0, 27, DPAD_UP); a.beq("exit")
    a.addi(3, 1, BUF); a.items.append(("dataoff", 4, "fmt_lua")); a.lbz(5, ID_LEN, 28); a.mr(6, 28)
    a.crclr6(); a.call(SPRINTF)
    lua_state(a, "no_lua")
    a.addi(4, 1, BUF); a.call(RUNSTRING); a.mr(26, 3)
    a.items.append(("dataoff", 3, "fmt_go")); a.mr(4, 28); a.lbz(5, ID_LEN, 28); a.mr(6, 26)
    a.crclr6(); a.call(OSREPORT)
    a.b("exit")
    a.label("no_lua")
    a.items.append(("dataoff", 3, "fmt_nolua")); a.crclr6(); a.call(OSREPORT)
    a.label("exit")
    a.lmw(3, 0x08, 1); a.lwz(0, 0x104, 1); a.mtlr(0); a.addi(1, 1, 0x100)

    # resolve data-relative addi placeholders (offsets from the "data" label) in a pre-pass
    pc = cave; labels = {}
    for it in a.items:
        if it[0] == "label": labels[it[1]] = pc
        elif it[0] == "data": pc += len(it[1])
        elif it[0] == "align": pc = (pc + it[1] - 1) // it[1] * it[1]
        else: pc += 4
    fixed = []
    for it in a.items:
        if it[0] == "tableoff":
            fixed.append(("w", (14 << 26) | (28 << 21) | (28 << 16) | ((labels["table"] - labels["data"]) & 0xFFFF)))
        elif it[0] == "dataoff":
            _, rt, lbl = it
            fixed.append(("w", (14 << 26) | (rt << 21) | (30 << 16) | ((labels[lbl] - labels["data"]) & 0xFFFF)))
        else:
            fixed.append(it)
    assert labels["code"] - labels["data"] < 0x8000, "table too big for 16-bit offsets"
    assert labels["labels"] - labels["data"] == head + tsize, "label offsets do not match the layout"
    a.items = fixed
    code = a.assemble()
    assert len(code) % 4 == 0
    return code, a.labels


def lua_state(a, fail):
    """r3 = beLuaState if the game's Lua is up, else branch to `fail`"""
    a.li32(9, BELUA); a.lwz(10, 0, 9); a.li32(11, BELUA_VT); a.cmpw(10, 11); a.bne(fail)
    a.lwz(3, 0x18, 9); a.cmpwi(3, 0); a.beq(fail)
    a.lwz(10, 0x0C, 3); a.cmpwi(10, 0); a.beq(fail)


def words(b): return list(struct.unpack(">%dI" % (len(b) // 4), b))


# ------------------------------------------------------------------------------------------
def selftest(mod, msgbox):
    ok = True
    def check(what, cond):
        nonlocal ok
        print(("  ok    " if cond else "  FAIL  ") + what); ok &= bool(cond)

    # 1. main.dol: the hook's original instruction and a few encodings the game also uses.
    # main.dol (extracted from your own disc) next to this script, or set DW4_DOL=<path>
    dol = os.environ.get("DW4_DOL") or next((p for p in (os.path.join(HERE, "main.dol"),
                                             os.path.join(HERE, "..", "dw4-workbench", "data", "main.dol")) if os.path.exists(p)), "")
    if os.path.exists(dol):
        d = open(dol, "rb").read()
        off = struct.unpack(">18I", d[0:72]); ad = struct.unpack(">18I", d[72:144]); sz = struct.unpack(">18I", d[144:216])
        def word(x):
            for i in range(18):
                if sz[i] and ad[i] <= x < ad[i] + sz[i]: return struct.unpack(">I", d[off[i] + x - ad[i]:off[i] + x - ad[i] + 4])[0]
        check("original at 8034c4cc is mr r26,r3", word(HOOK) == ORIGINAL)
        check("PadMgr_GetPad call right before the hook", word(HOOK - 4) == 0x4BFC5C71)
        check("OSReport starts with mflr r0", word(OSREPORT) == 0x7C0802A6)
    else:
        print("  (main.dol not found; skipping DOL checks)")
    # encodings worked out by hand from the PowerPC instruction formats
    a = Asm(0); a.and_(7, 4, 6); a.lbz(5, 11, 28); a.add(28, 28, 30); a.cmpw(10, 11); a.andi_(0, 4, 0x10); a.mulli(28, 8, 48)
    want = [0x7C873038, 0x88BC000B, 0x7F9CF214, 0x7C0A5800, 0x70800010, 0x1F880030]
    for got, w in zip(words(a.assemble()), want):
        check("encoding %08x (want %08x)" % (got, w), got == w)

    # 2. Run the cave in the interpreter.
    cave = 0x80001800
    code, labels = build(mod, cave, msgbox, LABELS)
    stop = cave + len(code)                       # where the handler would run the original instruction

    def scenario(held, pressed, sel=0, lua_ok=True, prev=0):
        m = Mem(); m.write(cave, code)
        PAD = 0x80500000; m.write(PAD + 0x44, struct.pack(">II", held, pressed))
        m.write(labels["data"], struct.pack(">II", prev, sel))
        if lua_ok:
            m.write(BELUA, struct.pack(">I", BELUA_VT)); m.write(BELUA + 0x18, struct.pack(">I", 0x80600000))
            m.write(0x80600000 + 0x0C, struct.pack(">I", 0x80700000))
        log = []; lua = []
        def fmt(c, fa, args):
            s = m.cstr(fa); out = ""; i = 0; k = 0
            while i < len(s):
                if s[i] == "%":
                    t = s[i + 1]; v = args[k]; k += 1; i += 2
                    out += str(v - (1 << 32) if v & 0x80000000 else v) if t == "d" else m.cstr(v)
                else: out += s[i]; i += 1
            return out
        def osreport(c): log.append(fmt(c, c.r[3], c.r[4:11]))
        def sprintf(c): m.write(c.r[3], fmt(c, c.r[4], c.r[5:11]).encode() + b"\0"); c.r[3] = 1
        def runstring(c): lua.append((c.r[3], m.cstr(c.r[4]))); c.r[3] = 0
        def ret(fn):
            def f(c): fn(c); c.r[0] = 0xDEADBEEF; c.r[12] = 0xDEADBEEF   # clobber volatiles like a real call
            return f
        cpu = Cpu(m, {OSREPORT: ret(osreport), SPRINTF: ret(sprintf), RUNSTRING: ret(runstring)})
        for k in range(32): cpu.r[k] = 0x1000 + k
        cpu.r[1] = 0x80400000; cpu.r[3] = PAD
        before = list(cpu.r)
        cpu.run(cave, stop)
        regs_ok = all(cpu.r[k] == before[k] for k in range(1, 32))
        h, p = struct.unpack(">II", m.read(PAD + 0x44, 8))
        sel_after = struct.unpack(">I", m.read(labels["data"] + 4, 4))[0]
        return dict(log=log, lua=lua, regs_ok=regs_ok, held=h, pressed=p, sel=sel_after)

    n = len(DESTS)
    shown = lambda k: DESTS[k][2] if LABELS else DESTS[k][0]
    msg = lambda k: 'be:MsgBox("WARP %d/%d: %s",0)' % (k + 1, n, shown(k))
    r = scenario(held=0x4000 | DPAD_RIGHT, pressed=DPAD_RIGHT)
    check("no Z: nothing happens, pad untouched", not r["log"] and not r["lua"] and r["held"] == 0x4000 | DPAD_RIGHT and r["pressed"] == DPAD_RIGHT and r["regs_ok"])
    r = scenario(held=mod | DPAD_RIGHT, pressed=DPAD_RIGHT)
    check("Z+Right: selects #2 and logs it", r["sel"] == 1 and r["log"] == ["WARP 2/%d %s %s\n" % (n, DESTS[1][0], shown(1))]
          + (["WARP msg result=0\n"] if msgbox else []))
    check("Z+Right: on-screen message" if msgbox else "Z+Right: no Lua when msgbox is off",
          r["lua"] == ([(0x80600000, msg(1))] if msgbox else []))
    check("Z+Right: D-pad hidden from the game", r["held"] == mod and r["pressed"] == 0)
    check("registers r1..r31 restored", r["regs_ok"])
    r = scenario(held=mod | DPAD_RIGHT, pressed=DPAD_RIGHT, prev=DPAD_RIGHT)
    check("Right still held from last frame: no repeat", r["sel"] == 0 and not r["log"] and not r["lua"])
    r = scenario(held=mod | DPAD_UP, pressed=DPAD_UP, prev=DPAD_UP)
    check("Up still held from last frame: no second warp", not r["lua"])
    r = scenario(held=DPAD_RIGHT, pressed=DPAD_RIGHT)
    check("no Z: D-pad state is still remembered", r["sel"] == 0 and not r["log"])
    r = scenario(held=mod | DPAD_LEFT, pressed=DPAD_LEFT, sel=0)
    check("Z+Left from first wraps to last", r["sel"] == n - 1 and DESTS[-1][0] in r["log"][0])
    r = scenario(held=mod | DPAD_RIGHT, pressed=DPAD_RIGHT, sel=n - 1)
    check("Z+Right from last wraps to first", r["sel"] == 0)
    r = scenario(held=mod, pressed=0, sel=0x7FFF)
    check("corrupt index is reset to 0", r["sel"] == 0 and not r["log"] and not r["lua"])
    for k in (5, n - 1):
        r = scenario(held=mod | DPAD_UP, pressed=DPAD_UP, sel=k)
        s, e, _ = DESTS[k]
        want = 'be:sd("PLAYERPOINT",nil,-1,"SETGENERATEPOS","I<%d>") be:sd("STAGECTL",nil,-1,"NEXTSTAGE","%s")' % (e, s)
        check("Z+Up on #%d: runs the warp Lua on beLuaState" % (k + 1), r["lua"] == [(0x80600000, want)])
        check("Z+Up on #%d: logs the warp" % (k + 1), r["log"] == ["WARP go %s entrance %d result=0\n" % (s, e)])
        check("Z+Up on #%d: registers restored" % (k + 1), r["regs_ok"])
    r = scenario(held=mod | DPAD_UP, pressed=DPAD_UP, sel=0, lua_ok=False)
    check("no Lua state: logs and skips", r["lua"] == [] and r["log"] == ["WARP no Lua state\n"])
    r = scenario(held=mod | DPAD_RIGHT, pressed=DPAD_RIGHT, sel=0, lua_ok=False)
    check("no Lua state: selecting still works, no message", r["sel"] == 1 and r["lua"] == [])
    return ok, code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mod", default="0x200", help="modifier button mask in pad+0x44 (default Z = 0x200)")
    ap.add_argument("--msgbox", action="store_true", help="also try the game's be:MsgBox on selection (not drawn by the retail game)")
    ap.add_argument("--labels", action="store_true", help="embed place names (about 1.2 KB more)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    global LABELS
    LABELS = args.labels
    mod = int(args.mod, 0); msgbox = args.msgbox
    ok, code = selftest(mod, msgbox)
    if not ok:
        sys.exit("selftest FAILED; not writing a code")
    lines = gecko_c2(HOOK, words(code), ORIGINAL)
    names = {0x200: "Z", 0x400: "L", 0x800: "R", 0x1000: "Y", 0x2000: "X", 0x8000: "B", 0x8: "Start"}
    btn = names.get(mod, "0x%X" % mod)
    hdr = ["$Warp menu v2 (hold %s: D-pad Left/Right = pick, Up = warp)" % btn]
    text = "\n".join(hdr + lines) + "\n"
    notes = ["", "# Destinations (number: stage, entrance - place)"] + \
            ["#  %2d: %-9s %d - %s" % (i + 1, s, e, l) for i, (s, e, l) in enumerate(DESTS)]
    notes += ["# Hook 0x8034C4CC (after PadMgr_GetPad). Safe alongside Spin2win (0x8034C4D0) and the Lua mailbox (0x8034C4D4).",
              "# Selection and warps are also logged via OSReport (Dolphin: View > Log, enable OSReport).",
              "# %d destinations, %d bytes of code+data." % (len(DESTS), len(code))]
    if args.out:
        open(args.out, "w").write(text + "\n".join(notes) + "\n")
        print("wrote", args.out, "-", len(DESTS), "destinations,", len(code), "bytes")
    else:
        print(text + "\n".join(notes))


if __name__ == "__main__":
    main()
