# D2 Autobattler

A second game on the D2 Tactics engine. Heroes grind rift floors on their own, in real time, and
the player manages them: which heroes go on runs, alone or in groups, and what they wear.

## Setting it up

1. In the D2 Tactics folder, run `Make D2 Autobattler folder.bat`. It creates
   `Diablo 2 Auto battler` next to the D2 Tactics folder (or the folder given as an argument)
   with a copy of the engine, the launchers, and `settings.ini` (so the Diablo II path carries
   over). Running it again refreshes the code and keeps that folder's heroes and settings.
2. In the new folder, start `Play D2 Autobattler.bat`.
3. `Update D2 Autobattler.bat` in that folder updates it from GitHub, the same way the D2
   Tactics updater does. Both folders update from the same repository, so engine fixes reach both.

What the autobattler folder keeps for itself: `saves_auto` (its heroes), `autobattler.ini`
(its settings, written on first start), `errors.log`. Neither file is in the repository, so an
update never overwrites them.

## autobattler.ini

| setting | default | meaning |
| --- | --- | --- |
| max_heroes | 30 | heroes on one account |
| max_active | 8 | heroes on runs at the same time |
| max_group | 4 | heroes on one run together |
| big_maps | yes | rift floors about twice the area of D2 Tactics' |
| speed | 1.0 | game speed; 1 = 25 frames a second |
| move_scale | 1.0 | cells per second per point of D2 velocity |
| floor_pause | 3 | seconds between a boss dying and the next floor |

## Rules

- Diablo II's own odds: the D2 Tactics adjustments in settings.ini (min_hit_chance,
  monster_hit_chance, normal_monster_damage, normal_monster_hit_bonus) are not used. Tactics
  mode is always off.
- The D2R changes in `game/d2r.py` apply as in D2 Tactics.
- Real time at 25 frames a second. Attack, hit recovery and movement follow D2's formulas
  (`autobattler/timing.py`):
  - attack frames = ceil(256 x FPD / floor(speed x (100 + EIAS) / 100)) - 1, EIAS = effective
    IAS - weapon speed modifier, between -85 and 75, effective IAS = floor(120 x IAS / (120 + IAS)).
    FPD and speed come from the unit's COF file in the player's install.
  - hit recovery frames = ceil(256 x base / floor(256 x (50 + EFHR) / 100)) - 1. A hero's base is
    (0% FHR frames + 1) / 2 for his class; this reproduces the published breakpoint tables.
    A hero goes into hit recovery when one blow takes at least 1/12 of his life; a monster at 1/8.
  - movement: heroes run at velocity 9, monsters at their MonStats velocity, raised by Faster
    Run/Walk with effective FRW = floor(150 x FRW / (150 + FRW)).
- Each blow is resolved by the engine's own attack code (`World._resolve_attack`): to-hit,
  block, damage, resistances, life and mana steal, death, experience, drops.
- Monsters wake up when a hero is within 14 cells and wait 8 frames between attacks on top of
  their attack animation.
- Heroes fight the nearest monster within 18 cells, otherwise walk to the floor's boss. Below
  their profile's potion_at they drink a healing or rejuvenation potion from the belt, at most
  once a second. What they do in a fight is up to their brain (below).

## Each hero's brain (autobattler/brain.py)

Every time a hero is free to act, his brain scores every skill he can use right now and does the
best one, or a normal attack, or backs off, or drinks.

- Damage skills: expected damage per second = the skill's own damage (SkillEnv, with synergies
  and the D2R changes) x the monsters it reaches (the pack around the aim point for areas and
  novas, up to four along a line) x what their resistances let through (immune = 0) / the time
  the cast or swing takes. Weapon skills use the weapon's damage with the skill's bonus and the
  chance to hit. A floor boss counts 1.3 times.
- Curses: on a pack of three or more, or a boss, that does not have that curse yet.
- Auras: one is switched on; a defensive one (Prayer, Defiance, the resist auras ...) when life
  is below half.
- Buffs and warcries that buff: cast again when 85% of their duration has passed.
  Offensive warcries (Howl, Taunt, Battle Cry, War Cry): with two or more monsters within 5 cells.
- Summons, golems, traps, walls: cast whenever the engine allows another; raising needs a corpse
  within 10 cells. When the engine says no (full, no corpse), the skill waits 3 seconds.
- Casting delay (Skills.txt delay: Meteor, Blizzard, Frozen Orb ...) is kept as a cooldown.
- Mana: a skill that would leave the hero below his mana reserve scores a quarter.
- Ranged heroes and casters back off a few cells from melee monsters next to them when their life
  is below their style's limit.
- Cast time: spells use the cast formula with the class's frames at 0% FCR (Amazon 19,
  Assassin 16, Barbarian 13, Druid 18, Necromancer 15, Paladin 15, Sorceress 13) as base + 1,
  which reproduces the published FCR breakpoints; skills that swing use the attack formula.
  The skill takes effect half way through.

Profile, saved with the hero (mode_state["autobattler"]):

| field | meaning |
| --- | --- |
| style | balanced (drink at 45%, keep 15% mana, back off below 70% life), aggressive (30%, 5%, never), careful (60%, 25%, below 95%) |
| potion_at, mana_reserve | override the style's numbers |
| keep_distance | auto, yes, no |
| favourite | a skill scored 25% higher |
| never | skills not used |
| auto_points | spend skill and stat points by the class plan |

Points: with auto_points on, skill points go by the class's plan in BUILDS (prerequisites first;
anything the plan can't take yet is kept) and stat points by STATS (strength and dexterity up to
a cap, the rest vitality). Plans: Sorceress cold, Necromancer bone, Paladin Blessed Hammer,
Barbarian Frenzy and Battle Orders, Amazon lightning javelin, Druid fire, Assassin lightning traps.
Every skill a hero has points in is used, whatever the plan.

The turn-based upkeep: the engine counts a turn as two seconds of D2 time, so every 50 frames
auras, buffs and curses tick, mana regenerates, poison and lingering spells do their damage,
summons, golems, traps and hirelings act, frozen and stunned monsters lose that round, and
monsters that cast spells take a turn (their own spells, through the engine's monster code).

## Runs

- A run is one hero or a group. It starts at the floor after the deepest one its heroes have
  cleared and goes down one floor each time the floor's boss dies.
- Floors are the Infernal Rift's (`game/rift.py`): any act's tiles, monsters at the hero's level,
  a boss at the far end. With big_maps the floor has twice the rooms on a maze up to 80 tiles
  across (instead of 56), open plains are 8 x 8 blocks (instead of 6 x 6), and up to 32 packs
  (instead of 16) are placed.
- Heroes are healed between floors, as if they had been to town.
- A run ends after the current floor when it is stopped. Heroes are saved after every floor and
  when the run ends.
- In a group, experience from kills goes to the first hero by the engine's rules, and every other
  living hero in the group gets the same amount.
- Without Diablo II files, a run plays on the engine's generated cave with placeholder monsters.
  Those monsters' numbers were made for turn-based play and hit far too often in real time; it is
  only for testing.

## The watch view (autobattler/liveview.py)

The engine's Scene plays events one after another, the way turns play out; real time doesn't go
through that queue. Every frame each unit's picture is set from the real-time state: its position
glides between its cell and the next one by how far into that step it is, and its animation is
WL while walking, A1 while swinging, SC while casting, GH in hit recovery and DD when it dies, each
played over exactly the frames the real-time code gives it (IAS / FCR / FHR). Missiles,
explosions, overlays, damage numbers and deaths still go through the Scene's own code.

## Speed

- Floors are built on a background thread, one at a time, so the other runs and the screen keep
  going while a run builds its next floor. All runs of a session share one rift seed, so two runs
  on the same depth agree on what that floor is (act, place, monsters); their maps still come from
  their own seeds.
- A hero decides at most every 6 frames while walking (monsters every 4). Each hero's skill
  numbers (damage, element, radius, duration, cast time) are worked out every 10 seconds, not at
  every decision.
- Who stands where is worked out once per frame (the engine's unit_at looks through every
  monster), and so is the list of living monsters. Monsters wake up on a check five times a
  second.
- Within 12 cells of where it is going a unit steps straight at it when a free cell gets it
  closer. A monster within 3 cells of its target whose way in is blocked by its own pack waits for
  a gap instead of searching a path. Full path searches are limited to 3 per run per frame (monsters
  search 1500 cells at most, heroes 6000); the rest wait a frame.
- With nothing in sight a hero heads for the nearest monster he can walk to (searched over at most
  12000 cells, once every two seconds); if the search is cut short he heads for the nearest one in
  a straight line. Only a search that wasn't cut short can decide that the monsters left are out
  of reach (the floor then counts as done).
- At most 6 game frames are played per screen frame (more at higher speeds): a slow PC slows the
  game down instead of freezing it.
- F3 shows the timings on screen; perf.log in the game folder gets them every 30 seconds.
- Measured without Diablo II files, 8 runs at 25 frames a second: 3 ms per game frame on average,
  under 10 ms for 99% of frames (D2's frame is 40 ms).

## Floors, portals and loot

- About a third of the big floors are outdoors: one of eleven terrains from all five acts
  (randmap's open-world builder: wilderness, desert, jungle, three Kurast districts, the Outer
  Steppes, the Plains of Despair, the City of the Damned, highlands, plateau) at 10 x 10 blocks,
  filled with the rift's own monsters and boss. If an outdoor floor can't be built it falls back
  to the open plain.
- When the floor's boss dies a red portal opens where it fell. The heroes pick up what they want
  (at most 25 seconds), then walk to the portal; the first hero stepping next to it takes the run
  to the next floor.
- Heroes also pick things up between fights, whenever nothing awake is within 18 cells: the
  nearest item within 30 cells that their pickup rules want. Pickups go through the engine's own
  code (gold to the purse, potions to the belt while it has room, tomes, stacks, the backpack).
  The autobattler has no quests: the engine's quest hook is skipped on pickup. An item that doesn't
  fit is left lying.
- Autobattler heroes have a 10 x 8 backpack, twice D2's 10 x 4 (`qol["inv_rows"] = 8`, read by
  `Player.INV_H`; heroes saved with a 10 x 7 backpack keep their items where they were).
- Pickup rules, per hero (Pickup screen): gold, potions, runes, gems, charms, jewelry, unique,
  set, rare and crafted, magic, plain items with sockets, plain items, everything else, and a
  list of words: an item whose name contains one of them is always picked up.

## The manager screen

One 800 x 600 canvas (D2's own resolution), scaled to the window, in Diablo II's own fonts
(font16, font30, fontformal10), the quest panel's carved stone for panels, the front-end's
wide and medium buttons (up and pressed frames), D2's item graphics and description box - all
read from the player's install by the engine's loaders. Without Diablo II files the same layout
is drawn with plain boxes and a system font.

- Heroes: the roster; a live view of the selected hero's floor (click it to watch full screen);
  his life, mana, level, style, gold, what his brain is doing and the run's last events; buttons
  New hero, Start run, Stop run, Watch, Style, Loot, Inventory, Pickup, Speed - / +.
- Loot: every item on the selected hero's floor laid out like the stash (12 x 14, pages), with
  filters (All, Gold, Potions, Runes, Gems, Charms, Jewelry, Unique, Set, Rare, Magic, Bases) and a
  search field that matches the name and the item's description lines. Green items are ones his
  pickup rules want. Click an item to take it with him (the engine's rule: outside a fight, from
  anywhere on the floor). His backpack is shown beside it.
- Inventory: D2's own inventory panel (invchar6), drawn by the game's HUD code, with the
  equipment slots, the I / II weapon tabs and the backpack grown to 8 rows. Beside it: his stats,
  his belt, and the buttons. The item handling is `autobattler/gear.py`, which uses the World's
  own item methods, so the game's rules apply (requirements, two-handed weapons and shields, rings,
  off-hand weapons for Barbarians and Assassins).
  - Click: pick an item up onto the cursor, put it down in the backpack (swapping with one item
    under it, like D2), or wear it in a slot (what was there comes onto the cursor).
  - Right click on a backpack item: wear it; a potion goes to the belt; a Scroll or Tome of
    Identify picks a target, then click the item to identify. Right click on a worn item takes it
    off into the backpack. Ctrl + right click sells an item.
  - Identify all: identifies everything he carries and wears, free.
  - Swap weapons (W, or the I / II tabs).
  - Sell box: drop the cursor item on it to sell it for D2's sell price.
  - Floor box: items put down outside the panel, or pushed out of a slot with no room. Click one
    to pick it up again.
  - Leaving the screen puts the cursor item and the floor back in the backpack. What still does
    not fit is sold, and the screen says so.
  - A hero who is not on a run is saved after each change; one on a run is saved by the run at
    the end of the floor.
- Pickup: his pickup rules and words.
- Watch: his floor full screen at 1:1, with each hero's life, mana and decision.

Keys: S start, X stop, W watch, T style, L loot, I inventory, P pickup, + / - speed, Esc back,
Ctrl+click adds heroes to a group. On the Inventory screen W swaps weapons.

## Not done yet

- Teleport and Leap are not used to get about yet (heroes walk). Whirlwind and Charge are scored
  as damage on the monsters near their target.
- Monsters that don't cast use their normal attack only; casters act once per 2-second round.
- Reign of the Warlock changes beyond what `game/d2r.py` already has (the Warlock class excluded).
- Floor building happens on the main thread, so the game may pause briefly when several runs
  start a new floor at once.

## Tests

`python tools/test_autobattler.py` checks the timing against the published breakpoints, the map
size switch, the roster cap, the run limits, that runs fight and go on to the next floor, and
the Inventory screen's item handling (equip, swap, identify, sell, the 8-row backpack). It
needs no Diablo II files and writes its heroes to a temporary folder.
