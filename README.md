# D2 Tactics (prototype)

Turn-based, action-point combat in Diablo 2's Act 1. Create a hero (all seven classes, D2's
own character creation screen), start in the Rogue Encampment and play through the whole act.
The game reads the real tiles, room layouts, unit animations, skills and items straight from
your own Diablo II install (set the folder in `settings.ini`). No Blizzard files are included.

**The world:** the outdoors are one seamless map - Rogue Encampment, Blood Moor, Cold Plains,
Burial Grounds, Stony Field, Dark Wood, Black Marsh, Tamoe Highland, Monastery Gate and the
Outer Cloister - built from D2's own outdoor presets (borders, fills, camps, cottages ...).
Every dungeon is entered through its real entrance (Den of Evil, Cave, Underground Passage,
Hole, Pit, Crypt, Mausoleum, Forgotten Tower + 5 cellars, Barracks, Jail 1-3, Inner Cloister,
Cathedral, Catacombs 1-4, Tristram) and generated from D2's room presets; dungeons are built
in the background, so going in or out is (almost) instant. Waypoints work like in D2.

**Quests:** Den of Evil, Sisters' Burial Grounds (Blood Raven - Kashya gives you a Rogue),
The Search for Cain (Tree of Inifuss, Cairn Stones, Tristram), The Forgotten Tower (Countess),
Tools of the Trade (the Smith, Horadric Malus), Sisters to the Slaughter (Andariel).

**Skills:** all 210 class skills from D2's Skills.txt / SkillDesc.txt with their real numbers -
damage per level (D2's level brackets), synergies, mana, durations, radii - and D2's skill
trees, icons and tooltips. Auras, curses, summons, golems, traps, shape shifting and the
Assassin's charge-ups all have turn-based rules.

**Towns and items:** Akara, Charsi and Gheed trade (their stock is D2's own vendor tables and
is rolled again each time you return to camp), Gheed gambles, Cain identifies for free, Kashya
hires a Rogue. Scrolls and tomes of Town Portal and Identify, every potion (healing, mana,
rejuvenation, antidote, thawing, stamina), magic items drop unidentified, gems and runes drop,
sockets, and every non-ladder runeword of 1.14d (Runes.txt).

**Graphics:** projectiles and spells use D2's own missile animations (Missiles.txt) with their
explosions, cast overlays and aura / curse effects (Overlay.txt, States.txt).

Without a D2 path the game falls back to placeholder art (a Barbarian in a generated cave).

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
| Attack (left click a monster) | 1 AP (bows / crossbows +1, very slow weapons +1; `melee_ap` in settings.ini) |
| Right click | your selected right skill (choose it on the right skill button, or F1-F8) |
| Drink potion (keys 1-4) | 2 AP |
| Pick up item | 1 AP (free outside combat) |

**Skills:** one skill point per level, D2's full tree of your class (T). Right click a learned skill in
the tree (or use the right skill button / F1-F8) to put it on the right mouse button. Bolts cost 3 AP,
novas and area spells 4, curses / buffs / summons / warcries 2, skill attacks your attack + 1,
switching auras 1 AP. Choosing an aura turns it on.

**Dying:** you wake up in the Rogue Encampment and lose half your gold (press R).

**Keys:** Space = end turn - I = inventory - C = character - T = skill tree - Q = quest log - Tab = automap
(full / corner / off) - Alt (hold) or L = item names - F = fast animations - F1-F8 = right skill -
mouse wheel = zoom - Esc = close panels / quit

**Walking:** outside combat, click (or hold the left button) to walk; a new click changes direction at once.

**Town:** click an NPC to Talk / Trade / Gamble / Identify / Hire. In a store, left click buys,
right click one of your items sells it. Right click a scroll or tome: Town Portal opens a blue
portal (take it back from the camp), Identify turns the cursor into a scroll - click the item.
Drag a gem or rune onto an item with sockets to insert it; the right runes in the right order
make a runeword.

**Inventory:** D2's 10x4 grid. Click an item to pick it up, click again to place it (or onto an
equipment slot). Right click equips / drinks. Clicking the world while holding an item drops it.

## Project layout

```
game/      pure rules, no graphics (grid, units, items, world/AI)
render/    pygame frontend (isometric renderer, animations, HUD)
render/assets.py    placeholder art  - everything drawn goes through this
render/d2assets.py  real D2 graphics (same interface)
d2/        readers for D2 formats: MPQ, DT1 tiles, DS1 layouts, DCC/COF animations, palettes
game/d2level.py     D2 cave rooms, tile maps
game/act1.py        Act 1: the seamless outdoors and every dungeon, from D2 presets
game/actworld.py    entrances, monsters, super uniques, waypoints, quest objects
game/skills.py      every class skill from D2's tables; game/d2calc.py evaluates D2's formulas
game/skillcast.py   how each kind of skill plays on the grid
game/d2items.py     gems, runes, sockets, runewords, prices
game/itemactions.py vendors, gambling, scrolls / tomes, town portal, identify
render/charcreate.py  D2's character creation screen
tools/extract_samples.py  pulls a small sample set out of your MPQs (for development)
```
