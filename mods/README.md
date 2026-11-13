# Mods (Gecko codes)

**USA (GDJEB2) only.** These codes patch fixed addresses in the USA release of Digimon World 4. They won't work on the European or Japanese disc.

| File | What it does |
|---|---|
| `spin2win_v3.txt` | Spin attack goes in the direction you hold on the D-pad (8-way, camera-relative). |
| `aim_assist.txt` | When you attack, you turn toward the nearest enemy, so your shot leaves already aimed. Two versions: long range (radius 20000) or unlimited range. Use only one. |

## Install (Dolphin)

1. Right-click the game → **Properties** → **Gecko Codes**.
2. Click **Add New Code…**. Put the text after `$` in the Name box and the hex lines in the Code box. For `aim_assist.txt`, pick **one** of the two versions.
3. Tick the code and start the game. Cheats must be enabled (Config → General → Enable Cheats).

## Notes

- Spin2win and aim assist hook different addresses, so you can turn both on together.
- Turn off older versions of the same code first (spin2win v1/v2, the first aim codes). Two codes hooking the same address will break the game.
- Aim assist turns you toward the enemy on any attack, melee too, not only shots.
