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

You explore freely until monsters spot you, then combat switches to turns (like Fallout).
Each turn you get **8 Action Points**.

| Action | Cost |
|---|---|
| Move one cell | 1 AP |
| Attack (left click a monster) | weapon speed, e.g. Hand Axe 3 AP, Scimitar 2 AP |
| Bash (right click) | attack + 1 AP, 2 mana: +50% damage, knockback |
| Drink potion (keys 1-4) | 2 AP |
| Pick up item | 1 AP (free outside combat) |

Hit chance uses D2's real to-hit formula (attack rating vs. defense, level difference).
Hover a monster to see hit chance and AP cost before you commit.

**Keys:** Space = end turn · I = inventory · C = character / stat points · Tab = automap · Alt (hold) or L = item names ·
G = grid · F = fast animations · mouse wheel = zoom · R = new cave after death · Esc = close / quit

**Monsters:** Zombies (slow, hit hard), Fallen (fast, scatter when a pack mate dies),
Fallen Shamans (fireballs, raise dead Fallen - kill them first), Quill Rats (ranged spikes),
and **Corpsefire** at the bottom of the Den of Evil.

**Loot:** gold, healing potions, white and magic (blue) items with D2 affixes such as
Jagged, Bronze, Sturdy, of the Fox, of Strength... Boots "of Haste" give +1 AP.

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
