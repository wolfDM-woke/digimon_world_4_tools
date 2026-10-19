# Digimon World 4 warp menu (Gecko code)

Warp to any of 83 rooms in **Digimon World 4 (USA, GDJEB2)**: every field, dungeon floor, boss stage, side-quest dungeon and Terminal Area room.

It uses the game's own room change, the same one its loading zones use. So you get the normal loading screen and the room's title card, and you keep your character, items and progress.

**Tested** on Dolphin (2026-10-18): selection, warping and the overlay all work.

## Controls

Hold **Z**, then:

| Button | Action |
|---|---|
| D-pad Right | next destination |
| D-pad Left | previous destination |
| D-pad Up | warp to the selected destination |

While Z is held, the D-pad is hidden from the game, so the menu doesn't trigger anything else. The selection starts at #1 (Goblin Pass) and is remembered until you reset the game.

**Seeing what's selected:** the game itself has no free on-screen text, so there are two options:
- **On-screen overlay (optional):** if you use [Felk's scripting build of Dolphin](https://github.com/Felk/dolphin), add `warp_overlay.py` (Scripts → Add Script). While you hold Z, it shows `WARP 5/83  dng101b1  Humid Cave F1  [Death Valley]` at the top-left.
- **Plain Dolphin:** open View → Log, tick *OSReport* under Log Types, and the log shows `WARP 5/83 dng101b1 ...` on every change. Or count presses using the table below; the room's title card confirms where you arrived.

## Install (Dolphin)

1. Right-click the game in Dolphin's game list, choose **Properties**, then open the **Gecko Codes** tab.
2. Click **Add New Code…** and paste the whole contents of `GDJEB2_warp_menu.txt`. The name line starting with `$` is optional, and Dolphin fills it in from the Name box.
3. Tick the code, and make sure **Enable Cheats** is on (Config → General).
4. Start, or restart, the game.

If you use the same game on Nintendont or another Gecko loader, the code is a standard `C2` (insert-ASM) code, so it should work there too.

**Two versions:**

| File | Size | Log line shows |
|---|---|---|
| `GDJEB2_warp_menu.txt` (recommended) | about 1.8 KB | the stage ID, e.g. `dng101b1` |
| `GDJEB2_warp_menu_with_names.txt` | about 3.1 KB | the place name too, e.g. `Humid Cave F1` |

Both work the same in game, and the overlay shows names with either one. Gecko code space is limited. If Dolphin says the codes are too large, or the menu does nothing, use the smaller version or turn other codes off.

## Read this first

- **Back up your memory card save.** Warping skips the story's normal order. Going somewhere before the story gets there can leave events unfinished or soft-lock the game. Do a test save first, and don't save in the middle of something you warped into, unless you're sure.
- **#83 is the credits.** It ends the play session.
- Some rooms can't be left the normal way when you arrive. The Numenume River spawn is on a one-way rail section, and two side-quest dungeons (Undead Yard, Forbidden Shrine) have an invisible wall at their entrance. Warp out again with the menu.
- The code hooks address `8034C4CC`. Don't enable another code that patches that same address.
- The selection is also logged to Dolphin's log (View → Log, enable *OSReport*), e.g. `WARP 5/83 dng101b1 ...`.

## Destinations

| # | Place | Area | Stage | Entrance |
|---:|---|---|---|---:|
| 1 | Goblin Pass | Death Valley | `stag0101` | 1 |
| 2 | Abyss of Grief | Death Valley | `stag0102` | 0 |
| 3 | Numenume River | Death Valley | `stag0103` | 0 |
| 4 | Doom Dome | Death Valley | `stag0104` | 1 |
| 5 | Humid Cave F1 | Death Valley | `dng101b1` | 0 |
| 6 | Humid Cave F2 | Death Valley | `dng101b2` | 0 |
| 7 | Cliff Dungeon F1 | Death Valley | `dng102b1` | 0 |
| 8 | Cliff Dungeon F2 | Death Valley | `dng102b2` | 0 |
| 9 | Cliff Dungeon F3 (Mammothmo | Death Valley | `dng102b3` | 0 |
| 10 | Doom Base F1 | Death Valley | `dng103f1` | 0 |
| 11 | Doom Base F2 | Death Valley | `dng103f2` | 0 |
| 12 | Fortress Guard Room | Death Valley | `stagGF01` | 0 |
| 13 | Fortress Rotating Hall | Death Valley | `stagGF02` | 0 |
| 14 | X Digimon Lab | Death Valley | `stagGF03` | 0 |
| 15 | GobGob Room | Death Valley | `stagGF04` | 0 |
| 16 | Apokarimon Space | Bosses | `stagBS01` | 0 |
| 17 | Mummy Desert | Dry Land | `stag0201` | 0 |
| 18 | Grief Wasteland | Dry Land | `stag0202` | 0 |
| 19 | Station X | Dry Land | `stag0204` | 0 |
| 20 | Power Plant | Dry Land | `stag0205` | 1 |
| 21 | Sand Labyrinth F1 | Dry Land | `dng204b1` | 0 |
| 22 | Sand Labyrinth F2 | Dry Land | `dng204b2` | 0 |
| 23 | Ancient Ruins F1 | Dry Land | `dng205b1` | 0 |
| 24 | Ancient Ruins F2 | Dry Land | `dng205b2` | 0 |
| 25 | Ancient Ruins F3 | Dry Land | `dng205b3` | 0 |
| 26 | Virus Lab F1 | Dry Land | `dng206f1` | 0 |
| 27 | Virus Lab F2 | Dry Land | `dng206f2` | 0 |
| 28 | Demon Shift | Bosses | `stagBS02` | 0 |
| 29 | Gekogeko Land | Venom Jungle | `stag0301` | 1 |
| 30 | Mangrove Forest | Venom Jungle | `stag0302` | 0 |
| 31 | Venom Swamp | Venom Jungle | `stag0303` | 0 |
| 32 | Dread Note | Venom Jungle | `stag0304` | 0 |
| 33 | Geko Path F1 | Venom Jungle | `dng307b1` | 0 |
| 34 | Geko Path F2 | Venom Jungle | `dng307b2` | 0 |
| 35 | Vine Tunnel F1 | Venom Jungle | `dng308b1` | 0 |
| 36 | Vine Tunnel F2 | Venom Jungle | `dng308b2` | 0 |
| 37 | Vine Tunnel F3 | Venom Jungle | `dng308b3` | 0 |
| 38 | Vein F1 | Venom Jungle | `dng309b1` | 0 |
| 39 | Vein F2 | Venom Jungle | `dng309b2` | 0 |
| 40 | Vein F3 | Venom Jungle | `dng309b3` | 0 |
| 41 | Vein F4 | Venom Jungle | `dng309b4` | 0 |
| 42 | Dread Bridge 1 | Venom Jungle | `dng310f1` | 0 |
| 43 | Dread Bridge 2 | Venom Jungle | `dng310f2` | 0 |
| 44 | Dread Bridge 3 | Venom Jungle | `dng310f3` | 0 |
| 45 | Hades Obelisk | Bosses | `stagBS03` | 0 |
| 46 | Battle Area | Machine Pit | `stag0401` | 1 |
| 47 | Core Area | Machine Pit | `stag0404` | 0 |
| 48 | Mecha Nest F1 | Machine Pit | `dng411b1` | 0 |
| 49 | Mecha Nest F2 | Machine Pit | `dng411b2` | 0 |
| 50 | Mecha Nest F3 | Machine Pit | `dng411b3` | 0 |
| 51 | Electric Mine F1 | Machine Pit | `dng412b1` | 0 |
| 52 | Electric Mine F2 | Machine Pit | `dng412b2` | 0 |
| 53 | Electric Mine F3 | Machine Pit | `dng412b3` | 0 |
| 54 | Electric Mine F4 | Machine Pit | `dng412b4` | 0 |
| 55 | Zone X 1 | Bosses | `stagBS04` | 0 |
| 56 | Zone X 2 | Bosses | `stagBS05` | 0 |
| 57 | Zone X 3 (last boss) | Bosses | `stagBS06` | 0 |
| 58 | Credits | System | `stagIS20` | 0 |
| 59 | Barbarian Cave | Side quests | `dngq1b1e` | 0 |
| 60 | Undead Yard | Side quests | `dngq2b1e` | 0 |
| 61 | Forbidden Shrine 1 | Side quests | `dngq3b1e` | 0 |
| 62 | Forbidden Shrine 2 | Side quests | `dngq3b2e` | 0 |
| 63 | Captive Dungeon 1 | Side quests | `dngq4b1e` | 0 |
| 64 | Captive Dungeon 1 (alt 1) | Side quests | `dngq4b1h` | 0 |
| 65 | Captive Dungeon 1 (alt 2) | Side quests | `dngq4b1v` | 0 |
| 66 | Captive Dungeon 2 | Side quests | `dngq4b2e` | 0 |
| 67 | Captive Dungeon 2 (alt 1) | Side quests | `dngq4b2h` | 0 |
| 68 | Captive Dungeon 2 (alt 2) | Side quests | `dngq4b2v` | 0 |
| 69 | Trader Hall | Side quests | `dngq5b1e` | 0 |
| 70 | Trader Hall (alt 1) | Side quests | `dngq5b1h` | 0 |
| 71 | Trader Hall (alt 2) | Side quests | `dngq5b1v` | 0 |
| 72 | Dungeon of Doom | Side quests | `dngq6b01` | 0 |
| 73 | Item Road 1 | Side quests | `dngq7b1e` | 0 |
| 74 | Item Road 2 | Side quests | `dngq7b2e` | 0 |
| 75 | Cursed Dungeon 1 | Side quests | `dngq8b1e` | 0 |
| 76 | Cursed Dungeon 2 | Side quests | `dngq8b2e` | 0 |
| 77 | Cursed Dungeon 3 | Side quests | `dngq8b3e` | 0 |
| 78 | Cursed Dungeon 3 (alt 1) | Side quests | `dngq8b3h` | 0 |
| 79 | Cursed Dungeon 3 (alt 2) | Side quests | `dngq8b3v` | 0 |
| 80 | Commander Room (Home Server | Terminal Area | `stagML02` | 0 |
| 81 | Lobby Terminal Area | Terminal Area | `stagML11` | 0 |
| 82 | Lobby Central Area | Terminal Area | `stagML12` | 0 |
| 83 | Lobby Shop Area | Terminal Area | `stagML13` | 0 |

## How it works

The code hooks the player's input handler right after the game reads the pad (`8034C4CC`). When Z is held, it updates the selection. On D-pad Up, it runs this through the game's own Lua interpreter:

```lua
be:sd("PLAYERPOINT",nil,-1,"SETGENERATEPOS","I<entrance>")
be:sd("STAGECTL",nil,-1,"NEXTSTAGE","<stage>")
```

That's the same pair of messages the game's room scripts send when you walk through an exit (`funcStageChange`). The entrance numbers come from the game's own scripts.

`source/` has the generator (`warpmenu2.py`, Python 3). Run `python warpmenu2.py` to rebuild the code. It runs a self-test first: the hook instruction is checked against the game's `main.dol` if you have one, and every path through the code runs in a small PowerPC interpreter. Options:
- `--mod 0x400` uses L instead of Z (`0x800` = R, `0x1000` = Y, `0x2000` = X).
- `--labels` embeds the place names.
- `--msgbox` also calls the game's `be:MsgBox` on every change. The retail game doesn't draw it, so it's for research only.

Room names were checked in game by walking every room and reading its title card.



Author: wolfDM


author:wol
