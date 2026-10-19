# Digimon World 4 warp menu - on-screen overlay (optional)
# For Felk's scripting build of Dolphin (https://github.com/Felk/dolphin). Plain Dolphin cannot run it;
# the Gecko code works without it.
#
# Shows the warp menu's current selection at the top-left while you hold Z (and for a few seconds
# after it changes):   WARP 5/83  dng101b1  Humid Cave F1  [Death Valley]
# It only reads memory: it finds the running warp code by its log string and reads its selection.
#
# Use: enable the warp menu Gecko code, start the game, then Scripts > Add Script > this file.

import importlib

def _mod(name):
    try: return importlib.import_module('dolphin.' + name)
    except Exception: return getattr(importlib.import_module('dolphin'), name)
event, gui, memory, controller = (_mod(n) for n in ('event', 'gui', 'memory', 'controller'))

# (stage, entrance, place, area) in menu order - generated together with the Gecko code
DESTS = [
    ('stag0101', 1, 'Goblin Pass', 'Death Valley'),
    ('stag0102', 0, 'Abyss of Grief', 'Death Valley'),
    ('stag0103', 0, 'Numenume River', 'Death Valley'),
    ('stag0104', 1, 'Doom Dome', 'Death Valley'),
    ('dng101b1', 0, 'Humid Cave floor 1', 'Death Valley'),
    ('dng101b2', 0, 'Humid Cave floor 2', 'Death Valley'),
    ('dng102b1', 0, 'Cliff Dungeon floor 1', 'Death Valley'),
    ('dng102b2', 0, 'Cliff Dungeon floor 2', 'Death Valley'),
    ('dng102b3', 0, 'Cliff Dungeon floor 3 (Mammothmon)', 'Death Valley'),
    ('dng103f1', 0, 'Doom Base floor 1', 'Death Valley'),
    ('dng103f2', 0, 'Doom Base floor 2', 'Death Valley'),
    ('stagGF01', 0, 'Goburimon Fortress - Guard Room', 'Death Valley'),
    ('stagGF02', 0, 'Goburimon Fortress - Rotating Hall', 'Death Valley'),
    ('stagGF03', 0, 'X Digimon Lab', 'Death Valley'),
    ('stagGF04', 0, 'GobGob Room', 'Death Valley'),
    ('stagBS01', 0, 'Apokarimon Space', 'Bosses'),
    ('stag0201', 0, 'Mummy Desert', 'Dry Land'),
    ('stag0202', 0, 'Grief Wasteland', 'Dry Land'),
    ('stag0204', 0, 'Station X', 'Dry Land'),
    ('stag0205', 1, 'Power Plant', 'Dry Land'),
    ('dng204b1', 0, 'Sand Labyrinth floor 1', 'Dry Land'),
    ('dng204b2', 0, 'Sand Labyrinth floor 2', 'Dry Land'),
    ('dng205b1', 0, 'Ancient Ruins floor 1', 'Dry Land'),
    ('dng205b2', 0, 'Ancient Ruins floor 2', 'Dry Land'),
    ('dng205b3', 0, 'Ancient Ruins floor 3', 'Dry Land'),
    ('dng206f1', 0, 'Virus Lab floor 1', 'Dry Land'),
    ('dng206f2', 0, 'Virus Lab floor 2', 'Dry Land'),
    ('stagBS02', 0, 'Demon Shift', 'Bosses'),
    ('stag0301', 1, 'Gekogeko Land', 'Venom Jungle'),
    ('stag0302', 0, 'Mangrove Forest', 'Venom Jungle'),
    ('stag0303', 0, 'Venom Swamp', 'Venom Jungle'),
    ('stag0304', 0, 'Dread Note', 'Venom Jungle'),
    ('dng307b1', 0, 'Geko Path floor 1', 'Venom Jungle'),
    ('dng307b2', 0, 'Geko Path floor 2', 'Venom Jungle'),
    ('dng308b1', 0, 'Vine Tunnel floor 1', 'Venom Jungle'),
    ('dng308b2', 0, 'Vine Tunnel floor 2', 'Venom Jungle'),
    ('dng308b3', 0, 'Vine Tunnel floor 3', 'Venom Jungle'),
    ('dng309b1', 0, 'Vein floor 1', 'Venom Jungle'),
    ('dng309b2', 0, 'Vein floor 2', 'Venom Jungle'),
    ('dng309b3', 0, 'Vein floor 3', 'Venom Jungle'),
    ('dng309b4', 0, 'Vein floor 4', 'Venom Jungle'),
    ('dng310f1', 0, 'Dread Bridge 1', 'Venom Jungle'),
    ('dng310f2', 0, 'Dread Bridge 2', 'Venom Jungle'),
    ('dng310f3', 0, 'Dread Bridge 3', 'Venom Jungle'),
    ('stagBS03', 0, 'Hades Obelisk', 'Bosses'),
    ('stag0401', 1, 'Battle Area', 'Machine Pit'),
    ('stag0404', 0, 'Core Area', 'Machine Pit'),
    ('dng411b1', 0, 'Mecha Nest floor 1', 'Machine Pit'),
    ('dng411b2', 0, 'Mecha Nest floor 2', 'Machine Pit'),
    ('dng411b3', 0, 'Mecha Nest floor 3', 'Machine Pit'),
    ('dng412b1', 0, 'Electric Mine floor 1', 'Machine Pit'),
    ('dng412b2', 0, 'Electric Mine floor 2', 'Machine Pit'),
    ('dng412b3', 0, 'Electric Mine floor 3', 'Machine Pit'),
    ('dng412b4', 0, 'Electric Mine floor 4', 'Machine Pit'),
    ('stagBS04', 0, 'Zone X 1 (Machine Pit)', 'Bosses'),
    ('stagBS05', 0, 'Zone X 2 (Machine Pit)', 'Bosses'),
    ('stagBS06', 0, 'Zone X 3 (Machine Pit, last boss)', 'Bosses'),
    ('stagIS20', 0, 'Credits', 'System'),
    ('dngq1b1e', 0, 'Barbarian Cave', 'Side quests'),
    ('dngq2b1e', 0, 'Undead Yard', 'Side quests'),
    ('dngq3b1e', 0, 'Forbidden Shrine 1', 'Side quests'),
    ('dngq3b2e', 0, 'Forbidden Shrine 2', 'Side quests'),
    ('dngq4b1e', 0, 'Captive Dungeon 1', 'Side quests'),
    ('dngq4b1h', 0, 'Captive Dungeon 1 (alt 1)', 'Side quests'),
    ('dngq4b1v', 0, 'Captive Dungeon 1 (alt 2)', 'Side quests'),
    ('dngq4b2e', 0, 'Captive Dungeon 2', 'Side quests'),
    ('dngq4b2h', 0, 'Captive Dungeon 2 (alt 1)', 'Side quests'),
    ('dngq4b2v', 0, 'Captive Dungeon 2 (alt 2)', 'Side quests'),
    ('dngq5b1e', 0, 'Trader Hall', 'Side quests'),
    ('dngq5b1h', 0, 'Trader Hall (alt 1)', 'Side quests'),
    ('dngq5b1v', 0, 'Trader Hall (alt 2)', 'Side quests'),
    ('dngq6b01', 0, 'Dungeon of Doom', 'Side quests'),
    ('dngq7b1e', 0, 'Item Road 1', 'Side quests'),
    ('dngq7b2e', 0, 'Item Road 2', 'Side quests'),
    ('dngq8b1e', 0, 'Cursed Dungeon 1', 'Side quests'),
    ('dngq8b2e', 0, 'Cursed Dungeon 2', 'Side quests'),
    ('dngq8b3e', 0, 'Cursed Dungeon 3', 'Side quests'),
    ('dngq8b3h', 0, 'Cursed Dungeon 3 (alt 1)', 'Side quests'),
    ('dngq8b3v', 0, 'Cursed Dungeon 3 (alt 2)', 'Side quests'),
    ('stagML02', 0, 'Commander Room (Home Server)', 'Terminal Area'),
    ('stagML11', 0, 'Main Lobby: Terminal Area', 'Terminal Area'),
    ('stagML12', 0, 'Main Lobby: Central Area', 'Terminal Area'),
    ('stagML13', 0, 'Main Lobby: Shop Area', 'Terminal Area'),
]
MARK = b'WARP %d/%d %s %s\n'
SHOW_FRAMES = 240                     # keep the label up this long after a change (60 = 1 s)
COLOR = 0xFFFFFF40                    # ARGB


def read_bytes(a, n):
    rb = getattr(memory, 'read_bytes', None)
    if rb: return bytes(rb(a, n))
    ru = memory.read_u8
    return bytes(ru(a + i) for i in range(n))


def find_index_addr():
    """the warp code's selection word sits 4 bytes before its log string, inside the Gecko code area"""
    blob = read_bytes(0x80001800, 0x1800)
    i = blob.find(MARK)
    return None if i < 4 else 0x80001800 + i - 4


addr, last, shown, wait = None, None, 0, 0
while True:
    await event.frameadvance()
    if addr is None:
        if wait > 0: wait -= 1; continue
        addr = find_index_addr()
        if addr is None:
            wait = 300                # code not running yet: look again in 5 s
            continue
    i = memory.read_u32(addr)
    if not 0 <= i < len(DESTS):
        addr = None; continue         # memory changed under us (game reset): find the code again
    if i != last: last, shown = i, SHOW_FRAMES
    try: z = controller.get_gc_buttons(0).get('Z')
    except Exception: z = False
    if shown > 0: shown -= 1
    if z or shown:
        s, e, place, area = DESTS[i]
        gui.draw_text((12, 12), COLOR, 'WARP %d/%d  %s  %s  [%s]   Z + D-pad Up = warp' % (i + 1, len(DESTS), s, place, area))
