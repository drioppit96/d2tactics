# D2 Tactics (prototype)

Turn-based, action-point combat in Diablo 2's Act 1. You start in the Rogue Encampment
(talk to Akara to heal) and leave the camp for the Den of Evil. The game reads the real
tiles, room layouts and unit animations straight from your own Diablo II install
(set the folder in `settings.ini`). No Blizzard files are included in this project.

Each cave is generated like D2 does it: a random maze of D2's own cave room presets,
with walkable areas taken from the tiles' collision flags. Without a D2 path the game
falls back to placeholder art.

## Run it (Windows)

1. Python 3.7 or newer (Windows 7: Python 3.8 is the last official version and works fine).
   Check with `python --version`.
2. Unzip this folder, open a terminal in it and run:
   ```
   pip install -r requirements.txt
   python main.py
   ```

## How to play

You start in the Rogue Encampment (talk to Akara to heal) and leave the camp for the Den
of Evil. You explore freely until monsters spot you, then combat switches to turns (like
Fallout). Each turn you get **Action Points** (the stamina bar shows them).

| Action | Cost |
|---|---|
| Move one cell | 1 AP |
| Attack (left click a monster) | weapon speed, e.g. Hand Axe 3 AP, Scimitar 2 AP |
| Right click | your selected right skill (choose it on the right skill button, or F1-F8) |
| Drink potion (keys 1-4) | 2 AP |
| Pick up item | 1 AP (free outside combat) |

**Skills:** one skill point per level, D2's full Barbarian tree (T). Combat skills (Bash, Stun,
Double Swing, Frenzy, Leap Attack, Whirlwind, Berserk...), warcries (Howl, Shout, Battle
Orders, Battle Cry, War Cry...) and passives (masteries, Iron Skin, Increased Speed...).

**Keys:** Space = end turn - I = inventory - C = character - T = skill tree - Tab = automap
(full / corner / off) - Alt (hold) or L = item names - F = fast animations - F1-F8 = right skill -
mouse wheel = zoom - Esc = close panels / quit

**Inventory:** D2's 10x4 grid. Click an item to pick it up, click again to place it (or onto an
equipment slot). Right click equips / drinks. Clicking the world while holding an item drops it.

## Project layout

```
game/      pure rules, no graphics (grid, units, items, world/AI)
render/    pygame frontend (isometric renderer, animations, HUD)
render/assets.py    placeholder art  - everything drawn goes through this
render/d2assets.py  real D2 graphics (same interface)
d2/        readers for D2 formats: MPQ, DT1 tiles, DS1 layouts, DCC/COF animations, palettes
game/d2level.py     builds a cave from D2 room presets
tools/extract_samples.py  pulls a small sample set out of your MPQs (for development)
```
