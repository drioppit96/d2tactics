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

**Act 2:** Lut Gholein (Atma, Drognan, Fara, Elzix, Lysander, Greiz - hires desert guards -,
Cain, Meshif, Jerhyn at the palace door, Warriv), the Rocky Waste, Dry Hills, Far Oasis, Lost
City and Valley of Snakes as one seamless desert, the Canyon of the Magi with the seven tombs
(one is the real Tal Rasha's Tomb, picked per character), and every Act 2 dungeon. Its six
quests: Radament's Lair (Book of Skill), The Horadric Staff (Horadric Cube in the Halls of the
Dead, Staff of Kings in the Maggot Lair, Amulet of the Viper in the Claw Viper Temple), Tainted
Sun (the sky goes dark until you smash the altar), Arcane Sanctuary (Jerhyn opens the palace),
The Summoner (Horazon's Journal opens the portal to the Canyon) and The Seven Tombs (the staff
in the orifice opens Duriel's Lair; Tyrael, Jerhyn, Meshif). Travel: Warriv "Go East" (for now
also "Go East (test)" without killing Andariel).

**Acts 3-5:** built the same way from D2's own presets. Act 3: Kurast Docks, the Spider
Forest, Great Marsh and Flayer Jungle (D2's 32x32 river pieces), Lower Kurast, the Bazaar,
Upper Kurast, the Causeway and Travincal, the spider caves, Swampy Pit, Flayer Dungeon, the
Kurast Sewers, the six temples and the Durance of Hate. Act 4: the Pandemonium Fortress, the
Outer Steppes, Plains of Despair, City of the Damned, the River of Flame (Hellforge) and the
Chaos Sanctuary. Act 5: Harrogath, the Bloody Foothills, Frigid Highlands, Arreat Plateau,
the ice caves, the Frozen River, the Frozen Tundra, Arreat Summit, Nihlathak's Temple and its
halls, the Worldstone Keep, the Throne of Destruction and the Worldstone Chamber. Every act's
NPCs, traders (Ormus, Alkor, Asheara, Hratli, Jamella, Halbu, Larzuk, Malah, Anya), healers,
hirelings (Iron Wolves, barbarians), waypoints and all 18 quests of Acts 3-5 (Golden Bird ...
Eve of Destruction). Travel: Meshif (Act 2 <-> 3), Mephisto's portal (3 -> 4), Tyrael (4 -> 5).
Test-only travel options (remove later): Warriv "Go East (test)", Meshif "Sail East (test)",
Cain in Kurast "To Act 4 (test)", Tyrael "Travel to Harrogath (test)". What is simplified or
still missing: docs/ACTS345_MISSING.md.

**Horadric Cube:** right click it in the backpack (or drop items on it). Every D2 recipe from
CubeMain.txt: gem and rune upgrades, potions, 3 rings -> amulet, rerolls, socketing, prismatic
and garnet rings ..., the Horadric Staff, and Wirt's Leg + a Tome of Town Portal in the Rogue
Encampment opens the Secret Cow Level (Wirt's body lies in Tristram), crafted items (jewel +
rune + perfect gem + a magic item), Stone of Jordan recipes.

**Item qualities:** normal, magic, rare, set and unique, all from D2's tables: every unique
of UniqueItems.txt and every set of SetItems.txt / Sets.txt with their real properties. Set
items give their extra bonuses as you wear more pieces of the set, and the full-set bonus when
you wear them all (the tooltip lights them up, like D2). Sockets: normal items, magic items
with socket affixes (Jeweler's ...), uniques and sets with sockets, the cube's socket recipes.
Gems, runes (runewords) and jewels (magic and rare, D2's jewel affixes) go into them. Item
+skills (+All Skills, +class skills, +skill tab, +single skill) raise your skills (shown blue in
the skill tree); "per character level" properties grow with you; +maximum resistance, damage
reduced by %, life/mana after each kill and extra experience work. Uniques and sets drop
rarely (better with magic find, more from bosses) and can be gambled.

**Objects:** D2's chests, caskets, urns, barrels (some explode), baskets, corpses, rocks, weapon
racks, armor stands and bookshelves - from the map pieces and each area's own random objects
(Levels.txt / ObjGroup.txt) - open or break for loot; some chests are trapped. Shrines (Shrines.txt:
refilling, health, mana, armor, combat, resist, skill, mana recharge, experience, portal, gem,
fire, monster, exploding and poison shrines) and wells. Doors open and close (click them;
monsters can't open them). Torches, braziers and fires burn. Every town has a stash (6x8, plus
gold: left click the gold box to put your gold in, right click to take it).

**More items:** superior and low quality items, ethereal items, durability (weapons wear when
they hit, armor when you are hit, broken items do nothing) and repairs at the smiths (Charsi,
Fara, Hratli, Halbu, Larzuk: "Repair" also recharges charges). Small, large and grand charms work
from the backpack. Item properties that act: chance to cast (on striking, when struck, on attack,
on kill, on level up), skills with charges (they show in your skill list, no mana), auras when
equipped, +skills of other classes, deadly strike, crushing blow, open wounds (bleeding), pierce,
+% to fire / cold / lightning / poison skill damage, -% to enemy resistance, elemental absorb.

**Monsters:** unique and champion packs with D2's modifiers (Extra Strong, Extra Fast, Cursed,
Magic Resistant, Fire / Cold / Lightning Enchanted, Mana Burn, Teleportation, Spectral Hit, Stone
Skin, Multiple Shots, auras; Champion, Berserker, Fanatic, Ghostly) and random unique names;
monsters cast their MonStats skills (bolts, novas, blizzards, curses, teleports, charges, heals,
summons). Traps, fire towers, lightning spires, gargoyle traps, catapults, trapped souls, nests that
hatch monsters, Act 3's water tentacles, regurgitators and the River of Flame's falling meteors.
Bosses: Mephisto keeps to his side of the moat, Diablo comes when all five seals are open (the
seals call his three lieutenants) and fires his lightning hose, Baal sends five waves before he
flees and splits in two in the Worldstone Chamber, the Ancients wake at the altar, Nihlathak
explodes corpses and calls minions.

**Hirelings:** your hireling (Rogue, Desert Guard, Iron Wolf, Barbarian) levels up with your kills
(Hireling.txt), wears a helm, armor, its kind of weapon (and a shield for Iron Wolves) - press O
or click it - uses its skills and aura, and is resurrected for gold by the one who hired it.

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
| Attack (left click a monster) | the weapon's D2 speed: Very Fast 1, Fast 2, Normal 3, Slow 4, Very Slow 5 AP (IAS makes it faster) |
| Right click | your selected right skill (choose it on the right skill button, or F1-F8) |
| Drink potion (keys 1-4) | 2 AP |
| Pick up item | 1 AP (free outside combat) |

**Skills:** one skill point per level, D2's full tree of your class (T). Right click a learned skill in
the tree (or use the right skill button / F1-F8) to put it on the right mouse button. Skill AP comes
from the skill's mana cost: spells 1.5 + square root of the mana (Fire Bolt 3, Frost Nova 5,
Meteor 6, Frozen Orb 7), weapon skills your attack AP + 0.6 x square root of the mana (Bash +1,
Whirlwind +3); switching auras 1 AP. Your maximum AP grows: 8, +1 at levels 10/20/30/45/60/80,
+1 per 40 Dexterity above your class's start, +1 per 20% Faster Run/Walk. Choosing an aura turns it on.

**Dying:** you wake up in the Rogue Encampment and lose half your gold (press R).

**Seeing them coming:** you see about a screen around you; monsters outside your light are shown
dimmed instead of hiding in the dark.

**On the ground:** Fire Wall, Blaze (a fire trail behind you while it lasts), Meteor and Blizzard keep
burning / freezing for a few turns; monsters standing in it or walking through it get hurt.

**Monsters:** the one under the mouse is outlined in red with its tile(s) marked, and its info box
sits to its left. Big monsters (Gargantuan Beasts, crow nests, Andariel ...) fill 3x3 cells.

**Aiming:** with a right-click skill selected, the tiles it will cover light up under the mouse -
missile paths, Teeth / Charged Bolt / Multiple Shot fans, Fire Ball splash, novas, curse and
blast areas; monsters it will hit are marked red (grey = out of range). Fans fly in a cone: the
first missile goes where you aim, each one hits the first monster on its line.

**Heroes:** the game opens on D2's character select screen - your heroes standing in their gear,
two columns of four (mouse wheel / arrows when you have more). Double click or OK plays,
Create New Character opens the creation screen, Delete Character asks first and moves the
save to saves\deleted. *Testing:* Akara has a "Level 99 (test)" option that gives you every
level with all its stat and skill points (will be removed later).

**Esc menu:** Options (light radius, monster / tile highlight, move range, skill area), Save and Exit Game
(back to the hero screen), Return to Game. Options are kept in options.ini.

**Loot window (V):** every item lying on the screen; click one to pick it up (in combat only
items next to you, 1 AP).

**Loading:** decoded sprites are kept in the `cache` folder (a few hundred MB at most; delete it any
time). While you play, a low-priority background process prepares everything the act needs - your
hero, every Act 1 monster, all missiles - so new things appear without a stutter. numpy (installed
automatically by Play D2 Tactics.bat) makes decoding about twice as fast; without it the game still
runs. F11 shows a performance readout (frame time split into logic / world / interface, sprite
decoding, background preparation progress).

**Keys:** Space = end turn - V = loot window - I = inventory - C = character - T = skill tree - Q = quest log - O = hireling - Tab = automap
(full / corner / off) - Alt (hold) or L = item names - F = fast animations - F1-F8 = right skill -
mouse wheel = zoom - F11 = performance readout - Esc = close panels / game menu

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
tools/extract_monsters.py every monster's animations + a report and picture sheets (for checking)
tools/extract_act.py      one act's layouts (DS1), tile libraries (DT1), palette, objects (for building an act)
```
