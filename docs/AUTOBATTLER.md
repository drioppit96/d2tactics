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
| floor_pause | 1 | seconds between stepping through the portal and the next floor; the next floor is built during it |

## Rules

- Diablo II's own odds: the D2 Tactics adjustments in settings.ini (min_hit_chance,
  monster_hit_chance, normal_monster_damage, normal_monster_hit_bonus) are not used. Tactics
  mode is always off.
- Monsters and bosses are D2's own for one player (/players 1) when a hero runs alone: MonStats
  and MonLvl numbers for the difficulty, with none of D2 Tactics' changes (its party life of
  x2.5-x3.5 and damage x1.35, act bosses -40% on Normal, a floor keeper's extra x2.5 life, the
  +50% normal-monster damage and +15% hit bonus). A group of N heroes plays as D2's /players N:
  each monster gets (N + 1) / 2 times the life and experience (`runs.scale_for_players`).
  Monster levels follow the acts (rift.act_level): the ten floors of an act climb from just above
  the previous act boss's level to this act's boss's level (Normal: Act 1 1-12, Act 2 13-22,
  Act 3 23-26, Act 4 27-30, Act 5 31-40; Nightmare and Hell by their MonStats levels), and after
  floor 50 the acts come round again 40 levels higher (at most 99). The act bosses on every tenth
  floor are D2's own.
- A stopped run is picked up again: the next run starts one floor below the deepest he cleared
  (kept on the hero and in his profile); only dying sends him back to floor 1.
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

How a hero fights is worked out from his build; there are no priority settings to fill in.

- Build (Brain.role), worked out again when his level, weapon or skills change:
  - Bow / crossbow: a bow or crossbow in hand. Keeps 5 cells from melee monsters.
  - Thrower: a javelin, throwing knife or axe in hand. Throw is his main attack (scored above the
    normal attack, more so at a distance); his javelin skills are scored as usual. Keeps 4 cells.
  - Summoner: a third or more of his skill points in summons. Keeps 6 cells.
  - Caster: more points in damage spells than in weapon skills. Keeps 5 cells.
  - Melee: everything else. Goes in close.
- Staying alive comes before everything else, at every decision:
  - below 30% life a rejuvenation potion first if he has one, else healing;
  - below his potion_at life (by style) a healing potion;
  - below 25% mana a mana potion, only in a fight (casters and summoners also out of one);
  - below 25% life with no healing or rejuvenation potion left and monsters about: he backs away
    and the run takes him home (Tyrael mends him, the belt is refilled from his gold, nothing is
    sold) and back to the floor 3 seconds later;
  - below 50% life with three or more melee monsters on him: he backs out of the ring.
- Kiting: every build but melee steps away when a melee monster reaches him, at most twice a
  second so he still gets his attacks and spells in; cornered, he fights for a second.
- Mana: damage spells count for less the lower his mana (x0.3 at empty, up to x1 at full), and a
  monster one blow would kill isn't worth a spell; buffs, auras, curses and summons are not cut,
  so mana is kept for them. The normal attack is scored x3 on a monster it kills in one blow.

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
- Summons, golems, traps, walls: cast only while he has fewer of them up than the skill allows
  (Skills.txt petmax at his skill level: one golem of any kind, one Valkyrie, as many skeletons
  as the level gives). A summon that is up is not cast again; when it dies, it is. Each summon is
  tagged with the hero who cast it, so in a group only his own count. Raising needs a corpse
  within 10 cells. When the engine says no anyway, the skill waits 3 seconds.
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

- Each swing or cast plays D2's own animation for it: the skill's Skills.txt anim (TH for the
  javelin skills, A1 for the bow skills, S1-S4, A2, KK, SC for spells), TH for Throw, A1 for a
  weapon skill without one. Its length is that animation's frames at his attack or cast speed. A
  unit without the animation uses its plain attack (render/d2assets.py MODE_MAP).

## Speed

- Floors are built on a background thread, one at a time, so the other runs and the screen keep
  going while a run builds its next floor. Each floor is rolled from a new seed when it is built:
  its place within the act (dungeon or outdoors), its monsters and its map, so the same depth is a
  different floor every time, also after a restart from floor 1.
- A hero decides at most every 6 frames while walking (monsters every 4). Each hero's skill
  numbers (damage, element, radius, duration, cast time) are worked out every 10 seconds, not at
  every decision.
- Who stands where is worked out once per frame (the engine's unit_at looks through every
  monster), and so is the list of living monsters. Monsters wake up on a check five times a
  second.
- Within 12 cells of where it is going a unit steps straight at it when a free cell gets it
  closer.
- Monsters after a hero walk down that hero's distance map: one breadth-first search over the
  cells within 24 of him, made again at most every 15 frames while he moves, serves his whole
  pack. A monster with no free cell nearer waits for a gap. Beyond the map's reach it steps
  straight at him, or waits a second. Big monsters (with a radius) still use the path search.
- Full path searches (heroes, big monsters) are limited to 3 per run and 6 for all runs together
  per frame, a different run going first each frame; heroes search 3000 cells at most, monsters
  1500. The rest wait a frame.
- With nothing in sight a hero walks a route to the nearest monster he can reach by walking
  distance: a breadth-first search over the whole floor (walls and the map's edges can't fool
  it, and he no longer turns back and forth between half-searched guesses). A big floor is
  searched over several frames, at most 2000 cells a frame for all runs together; he keeps
  walking his last route meanwhile. Someone standing in the way is stepped round. A complete
  search that finds no monster he can reach marks the floor as done.
- A hero only takes on monsters he can see: within 18 cells with open floor on the straight line
  between them (or within 2 cells). One behind a wall is reached by the route over the floor
  instead, so he doesn't turn back and forth between the two.
- He steps straight at a goal only when the straight line to it is open floor; otherwise he
  follows a searched path, which is searched again only when the goal has moved by more than a
  cell. Routes go round anyone standing in the way.
- A hero who hasn't moved for 3 seconds without fighting drops his path, route and target and
  looks again ("stuck: looking for another way").
- Awake monsters a hero can't get to (no path) or can't see don't keep him from picking things
  up or going to the portal; after the boss he leaves such a monster alone for 10 seconds at a
  time, and he no longer goes looking for more monsters once the boss is dead.
- Measured without Diablo II files, 8 runs for 4 minutes: frames in which a hero stayed within 3
  cells for 4 seconds without fighting went from 8156 / 18917 (two seeds) to 0 / 258.
- Line of sight for the map is only worked out for the run being watched.
- At most 6 game frames are played per screen frame (more at higher speeds): a slow PC slows the
  game down instead of freezing it.
- F3 shows the timings on screen; perf.log in the game folder gets them every 30 seconds.
- Measured without Diablo II files, 8 runs at 25 frames a second: 2.6 ms per game frame on
  average; one frame in 6000 took over 30 ms (the first, when the floors are set up). Before the
  distance maps, 316 in 6000 did.

## Floors, portals and loot

- About a third of the big floors are outdoors: one of eleven terrains from all five acts
  (randmap's open-world builder: wilderness, desert, jungle, three Kurast districts, the Outer
  Steppes, the Plains of Despair, the City of the Damned, highlands, plateau) at 10 x 10 blocks,
  filled with the rift's own monsters and boss. If an outdoor floor can't be built it falls back
  to the open plain.
- When the floor's boss dies a red portal opens where it fell. The heroes pick up what they want
  (at most 25 seconds), then walk to the portal; the first hero stepping next to it takes the run
  to the next floor. The next floor is built while the screen shows "Next: floor N" for
  floor_pause seconds (1 by default); the pause and the building overlap.
- Heroes also pick things up between fights, whenever nothing awake is within 18 cells: the
  nearest item within 30 cells that their pickup rules want. Pickups go through the engine's own
  code (gold to the purse, potions to the belt while it has room, tomes, stacks, the backpack).
  The autobattler has no quests: the engine's quest hook is skipped on pickup. An item that doesn't
  fit is left lying.
- Autobattler heroes have a 10 x 8 backpack, twice D2's 10 x 4 (`qol["inv_rows"] = 8`, read by
  `Player.INV_H`; heroes saved with a 10 x 7 backpack keep their items where they were).
- A full backpack: when a hero finds something he wants and has no room for it, and he carries
  gems, runes, unique or set items, his run goes to town on its own (the floor waits). Every
  return to town, automatic or by the To town button, puts the gems and runes from the backpack on
  their stacks in the stash's gems & runes tab and the unique and set items into the first stash
  tabs with room (autobattler/stash.py). On an automatic trip he also sells every magic (blue)
  and rare (yellow) item in his backpack at D2's sell price (runs.sell_magic_and_rare); what he
  wears is kept, and a trip by the To town button sells nothing. After an automatic trip he goes
  back to the floor by himself 3 seconds later; after To town, Continue run takes him back. With
  nothing in his backpack to stash or sell he stays on the floor and leaves the item lying.
- The belt: each row holds one kind of potion, counted from the bottom (Healing, Mana,
  Rejuvenation or Any; a healing row also takes rejuvenation potions), set per hero on the
  Inventory screen; new heroes have rows 1-2 healing, 3-4 mana (potions.ROW_RULE, from his profile
  through config.apply_d2_rules; D2 Tactics keeps D2's own rule). A belt shows as many rows as D2
  gives it: none 1, Sash / Light Belt 2, Belt / Heavy Belt 3, Plated Belt 4. He drinks a potion of
  the kind he needs from any row (as a right click in D2's open belt), and after each drink the
  stacks are put back in their rows' order. Heroes pick up healing, mana and rejuvenation potions
  on their own whenever a row for that kind has room, whatever their pickup rules say.
  Before each floor, and when he comes back from town, the belt is filled the same way from his
  gold: the best tier the traders sell for the act that he can pay for, down to Minor potions for a
  poor hero. He drinks below his potion_at life, also while picking things up or walking to the
  portal. The Inventory screen shows the belt opened (above the charm inventory), with the kind
  of each row beside it: click to change; the hero card shows how many healing and mana potions he
  has.
- Pickup rules, per hero (Pickup screen): gold, potions, runes, gems, charms, jewelry, unique,
  set, rare and crafted, magic, plain items with sockets, plain items, everything else, and a
  list of words: an item whose name contains one of them is always picked up.

## The manager screen

One 800 x 600 canvas (D2's own resolution), scaled to the window, in Diablo II's own fonts
(font16, font30, fontformal10), the quest panel's carved stone for panels, the front-end's
wide and medium buttons (up and pressed frames), D2's item graphics and description box - all
read from the player's install by the engine's loaders. Without Diablo II files the same layout
is drawn with plain boxes and a system font.

- Heroes: the roster (a red + marks a hero with points to spend); a live view of the selected
  hero's floor (click it to watch full screen); his life, mana, level, style, gold, points to
  spend, what his brain is doing and the run's last events; buttons New hero, Start run, Stop
  run, To town, Watch, Style, Inventory / Loot, Abilities, Pickup, Shop, Stash. A hero not on a
  run is in town (Sanctuary, the Act 6 town). The speed buttons are gone; `speed` in
  autobattler.ini still sets the game speed.
- The hero card shows his build (as his brain sees it) and how he fights with it. While he has summons up, the
  card lists them ("Summons up: Oak Sage"), and each summon he casts goes in the run's log.
- Farm (Rift / Boss / Runes): what the selected heroes farm on their next run (profile "farm"; a
  group farms what its first hero does):
  - Rift: the Infernal Rift, floor after floor, going on below the deepest floor cleared; an act
    boss every tenth floor.
  - Boss: the Black Road (game/arena.py): a small walled room with one of the Great Evils in it,
    chosen at random each time; when it dies a portal opens and the next room follows.
  - Runes: the Forgotten Tower's cellar, Tower Cellar levels 1 to 5 (D2's own maps and monsters).
    Levels 1-4 are done when no more than 35% of their monsters are left; on level 5 the Countess
    ends it (she drops her rune hoard every time). Then it starts again at level 1.
  Dying restarts the farm from its beginning; only the rift keeps the deepest floor.
- To town / Continue run: To town takes the hero (and his group) to town as a town portal would:
  the run waits on its floor, frozen as it is, and he is in Sanctuary, where Tyrael mends him and
  the traders restock; Shop and Stash work. The button then reads Continue run, which takes him
  back to the same floor, where he was, with whatever he changed in town. The hero list shows him
  "in town" in gold while his run waits. Stop run in town ends the run at once; on a floor it
  waits for the end of the floor.
- Shop and Stash (heroes in town only) are two windows, each with D2's inventory panel on the
  right, as on the Inventory screen. The Shop window has four tabs (Tyrael, Hadriel, Izual,
  Gamble); the Stash window has only the stash.
  - Tyrael, Hadriel, Izual: Sanctuary's three traders, with the stock and prices of the game's own
    vendors (game/itemactions.py: Malah's, Gheed's and Halbu's lists). The healing and mana
    potions follow the act of the hero's deepest floor. Click or right click an item to buy it.
    Drop an item on the shelves, or Ctrl + right click it in the backpack, to sell it.
  - Gamble: Hadriel's gambling, with D2's odds.
  - Stash: the account's stash, the same one for every hero (saves_auto/_stash.json): the gems
    and runes tab (one stack per kind; click takes one onto the cursor, right click puts one in the
    backpack, a gem or rune dropped on it goes on its stack) and 29 tabs of 12 x 16. Click picks up
    and puts down (swapping with one item, like D2); right click moves an item to the backpack;
    Ctrl + click in the backpack moves one into the stash; with the stash open, a right click on a
    gem or rune in the backpack puts it on its stack. Gold stays each hero's own.
  - Leaving the screen with an item on the cursor puts it in the backpack, or in the stash when
    the backpack is full.
- No essences: the three account currencies of D2 Tactics (game/essences.py) don't drop in the
  autobattler (essences.DROPS is turned off by config.apply_d2_rules) and aren't shown anywhere.
  D2's own boss essences (the Token of Absolution's) are untouched.
- Inventory / Loot: the loot window on the left, D2's own inventory panel (invchar6) on the right,
  drawn by the game's HUD code, with the equipment slots, the I / II weapon tabs and the backpack
  grown to 8 rows.
  - Charms: a 4 x 8 charm inventory right of the panel, level with the backpack, in the panel's own
    cell art. Only charms go in it, and only the charms in it work (Player._charm_items, through
    qol["charm_grid"]); a charm in the backpack does nothing. Right click moves a charm between the
    backpack and the charm inventory. Charms are never sold on the trip home. The first time, the
    charms a hero carries move into it.
  - Loot: every item on the selected hero's floor laid out like the stash (13 x 10, pages), with
    filters (All, Gold, Potions, Runes, Gems, Charms, Jewelry, Unique, Set, Rare, Magic, Bases) and
    a search field (click it to type) that matches the name and the item's description lines.
    Green items are ones his pickup rules want. Click an item to take it with him (the engine's
    rule: outside a fight, from anywhere on the floor); it goes to the first free place in the
    backpack. Not on a run, the loot window is empty. The item handling is `autobattler/gear.py`, which uses the World's
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
- Abilities: D2's character panel on the left and the skill tree on the right, both drawn by the
  game's HUD code (`autobattler/points.py` does the spending).
  - + beside a stat puts a point in it (Shift + click: all of them). New life and mana are there
    at once, as in D2. Reset Stats gives every spent stat point back, free.
  - Click a skill to learn it (the game's rules: a point left, his level, the skills before it).
  - The skills show D2's own icons (the class's Skillicon.DC6, on the class's skill tree art) and
    D2's tooltip: name, description, required level and skills, the current and next level's
    numbers from SkillDesc / Skills, durations in seconds, and the skills it gets bonuses from
    (points.skill_tooltip). The turn-based game's AP costs and turn counts are left out.
  - If one of the two D2 panels can't be drawn, that panel alone falls back to plain boxes and
    the error goes to errors.log once.
    The tree's tabs change pages; Reset Skills gives every skill point back, free.
  - Points: by hand / by class plan. By hand (the default) the points wait for you; by class plan
    they go by his class's build (brain.BUILDS, brain.STATS) at each level up and before each
    floor. Heroes made before this switch to by hand once.
- Pickup: his pickup rules and words.
- Watch: his floor full screen at 1:1, with each hero's life, mana and decision.

Keys: S start, X stop, W watch, T style, I or L inventory and loot, C abilities, P pickup,
Esc back, Ctrl+click adds heroes to a group. On the Inventory and Sanctuary screens W swaps
weapons; I / L close the Inventory screen, C the Abilities screen.

## Not done yet

- Teleport and Leap are not used to get about yet (heroes walk). Whirlwind and Charge are scored
  as damage on the monsters near their target.
- Monsters that don't cast use their normal attack only; casters act once per 2-second round.
- Reign of the Warlock changes beyond what `game/d2r.py` already has (the Warlock class excluded).

## Tests

`python tools/test_autobattler.py` checks the timing against the published breakpoints, the map
size switch, the roster cap, the run limits, that runs fight and go on to the next floor, and
the Inventory screen's item handling (equip, swap, identify, sell, the 8-row backpack). It
needs no Diablo II files and writes its heroes to a temporary folder.
