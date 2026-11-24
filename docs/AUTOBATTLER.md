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
- Heroes fight the nearest monster within 18 cells, otherwise walk to the floor's boss. Below 45%
  life they drink a healing or rejuvenation potion from the belt, at most once a second.

## Runs

- A run is one hero or a group. It starts at the floor after the deepest one its heroes have
  cleared and goes down one floor each time the floor's boss dies.
- Floors are the Infernal Rift's (`game/rift.py`): any act's tiles, monsters at the hero's level,
  a boss at the far end. With big_maps the floor has twice the rooms on a maze up to 80 tiles
  across (instead of 56), open plains are 8 x 8 blocks (instead of 6 x 6), and up to 32 packs
  (instead of 16) are placed.
- Heroes are healed between floors, as if they had been to town.
- A run ends when every hero on it is dead, or after the current floor when it is stopped.
  Heroes are saved after every floor and when the run ends.
- In a group, experience from kills goes to the first hero by the engine's rules, and every other
  living hero in the group gets the same amount.
- Without Diablo II files, a run plays on the engine's generated cave with placeholder monsters.
  Those monsters' numbers were made for turn-based play and hit far too often in real time; it is
  only for testing.

## Screen (temporary)

The first screen is a working placeholder until the manager screen is designed: the roster on
the left (click selects a hero, Ctrl+click adds heroes for a group), the runs on the right (click
one to watch it), and buttons for a new hero, start, stop and watch. Keys: S start, X stop,
W watch, + / - game speed, Esc back. The watch view uses the engine's renderer with Diablo II
files, and a top-down view without them.

## Not done yet

- Skills: heroes only use their normal attack. Skills, auras, curses and summons come next, a
  class at a time.
- Picking up items, and managing gear from the manager screen.
- The manager screen itself.
- Reign of the Warlock changes beyond what `game/d2r.py` already has (the Warlock class excluded).
- Floor building happens on the main thread, so the game may pause briefly when several runs
  start a new floor at once.

## Tests

`python tools/test_autobattler.py` checks the timing against the published breakpoints, the map
size switch, the roster cap, the run limits, and that runs fight and go on to the next floor. It
needs no Diablo II files and writes its heroes to a temporary folder.
