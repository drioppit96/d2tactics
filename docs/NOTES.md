# Developer notes and roadmap

Everything learned so far, so a new session can continue without re-discovering it.

## Status (end of day 2)

Day 2 added: all seven classes (character creation screen, CharStats stats and kits, class
sprites), every class skill from the tables (game/skills.py + game/d2calc.py, turn-based
rules in game/skillcast.py), allies (summons, golems, traps, the Rogue hireling), the whole
of Act 1 (game/act1.py builders, game/actworld.py population), waypoints and all six quests.

Next ideas: save games, D2 sounds (Huffman/ADPCM WAV decompression), real unique/champion packs with D2 names, D2's
automap cells (AutoMap.txt + MaxiMap.dc6), Act 2.

## Day 3: towns, items, missiles

- Vendors: Weapons/Armor/Misc.txt columns `<Npc>Min/Max` (normal) and `<Npc>MagicMin/MagicMax/
  MagicLvl`; ItemTypes.txt StorePage picks the tab (armo/weap/misc). Stock ilvl = clvl+5 (max 30),
  cached per town visit (`player._town_visit`). Potions and scrolls never run out. Sell = price/5.
  Gamble: magic only for now (no rare/unique rolls), price 150 + 60*clvl + 2*cost, bases qlvl <= clvl+2.
- Store art: buysell.dc6 (4 frames, 320x432, 10x10 grid at 15,62 with 29 px cells),
  buyselltabs.dc6 (8 frames 79x31), buysellbtn frame 10 = close, gemsocket.dc6 28x28.
- Sockets: ItemTypes MaxSock1/25/40 by ilvl, capped by the base's gemsockets. Normal items get
  sockets 15% of the time. Gems.txt is not in the samples, so d2items.py has the 1.14d gem / rune
  table built in (used when Gems.txt can't be read). Runes.txt: complete=1 and server=0 only
  (server=1 = ladder). Unsupported props are listed as extra lines on the item (UNSUPPORTED).
- Town portal = world objects "tp" (in the field) and "tp_back" (in camp); `player.portal =
  (level_key, cell, level_id)`. main.portal_to_town / portal_back handle the jump.
- Melee costs `MELEE_AP` (units.py, settings.ini melee_ap = 1); +1 for ranged, +1 for very slow
  weapons (ap >= 5) under 20% IAS. Skill AP costs: skills.ap_cost.
- Missiles: Skills.txt cltmissile / srvmissile -> Missiles.txt CelFile (follow SubMissile /
  CltSubMissile if empty), `data\global\missiles\<cel>.dcc`, Trans = additive blend,
  ExplosionMissile on impact. 32-direction order `_DIR32` in d2assets.py. Novas: 16 missiles
  outward. Overlays: Overlay.txt Filename -> data\global\overlays\<f>.dcc; Skills.txt
  castoverlay on cast, States.txt overlay1-4 for aurastate / auratargetstate.
- Hero select screen: background, heroes and fire use the front-end palette (no palette
  argument); only the buttons use the units palette. Only EXIT shows until a hero is picked.
- Saves now keep sockets, socketed items, runewords, identified, tome charges.

## Day 4: readability, AP rework, big monsters

- DS1 main index is 6 bits (0-63): cottages use main 45 - the old `main >= 30` skip hid every
  house floor and wall (black holes, invisible blocking). Only `border.tg1` editor presets (main 48)
  have no tiles, and they are never placed.
- Monster sprites: MonStats2 BaseW is the weapon class of the COFs (goatman 2hs, corruptrogue 1hs,
  sk_archer / cr_archer bow - the bow is a layer of the bow COFs). Death COFs are hth, which is
  why only corpses showed.
- MonStats2 SizeX 3 -> `unit.radius = 1` (3x3 cells). World.occupied/unit_at cover the footprint,
  World.udist = body distance, World.path_near / attack_path handle big movers and targets,
  actworld.settle_big_monsters moves them where they fit. No knockback for big ones.
- AP: items.speed_tier(Weapons.txt speed) -> 1..5 AP; IAS shifts speed by ias/2. Skill AP from
  mana (skills.ap_cost). Max AP: units.AP_LEVELS, dex/40 above start, FRW/20.
- Aggro: SIGHT 16, ALERT_RADIUS 12, allies look 24 cells for foes.
- Followers: ally moves outside combat don't block the event queue (that made walking stutter
  and could freeze input); teleporting followers emit ("place", unit, cell).
- Esc menu render/gamemenu.py (font42 + pentspin.dc6), options.ini; loot window d2hud._draw_loot.

## Act 1 world (game/act1.py)

- Outdoors: slots of 8x8 blocks of 8x8 tiles (64x64 tiles = 320x320 cells per area). Snake
  layout from the town's exit side (townN1/E1/S1/W1). Border ring of `Bord1-12` presets:
  edges bord3 N, bord1 S, bord2 W, bord4 E (variants b/c), corners bord6 NW, bord7 NE,
  bord8 SE, bord5 SW. Where two areas meet both sides get the `o` variant (opening) at the same
  block index. Interior: entrances, waypoint, quest presets first, then fills (LvlPrest names).
  If presets don't line up, `_connect` carves a grass trail (A* check per link).
- Monastery Gate (facade1.ds1) must be north of Tamoe (its gate opens south); the Outer Cloister
  (court*.ds1) sits right behind it. The Barracks door = the cloister's far edge (no warp tile).
- Warp tiles: DS1 wall cells with orientation 10 or 11 and main index < 8; main index = Levels.txt
  vis slot (vis0 previous, vis1 next, vis3-6 outdoor entrances, vis4 down). Orientation 8/9 are
  door frames, not warps.
- DS1 objects: type 1 = MonPreset.txt act 1 order (0 gheed, 1 cain1, 2 akara ... 12
  place_bloodraven, 34 Bishibosh ... 46 Corpsefire; place_* = spawn points); type 2 =
  objects: 52/53 waypoint, 7-11 cairn stones, 12 Inifuss tree, 25 moldy tome, 36 Malus, 26 cage.
  Object graphics: Objects.txt token (S1-S5, IT, TT, HM, GI, wp/wn ...), data\global\objects\<tok>.
- Dungeon mazes: room size from the presets (caves 24, crypt 8, barracks 10x14, jail/catacombs 12);
  role rooms: cave{d}pre/next/down/spec/crow, crypt{d}warpprev/warpnext/bonebreak/consol,
  jail{d}warpprev/warpnext/warpcath/way/pitspawn, bar{d}warp/forge + court{d}b, cat{x}up/{d}down/{d}way.
- Monster level = Levels.txt MonLvl1Ex (normal). Rosters: mon1-10 (normal), nmon (NM/Hell).
- Performance: Grid.update_visibility only clears what it lit last time (big maps!), find_path has
  a node limit, make_grid builds rows by slices; the outdoor act builds in about a second.

## Skills (game/skills.py)

- calc language: ln12 = par1 + (lvl-1)*par2, dm12 = diminishing, parN, lvl, blvl (hard points),
  skill('Name'.blvl/.lvl/.parN/.ln34), clc1-4, toht, edmn/edmx (shifted), edns/edxs (<< hitshift),
  min/max, ?:. See game/d2calc.py.
- Damage: value per level brackets (2-8, 9-16, 17-22, 23-28, 29+), shift = v * 2^hitshift / 256
  (blank hitshift = 0). Poison total = shifted * ELen frames. Mana = (mana + lvlmana*(lvl-1)) *
  2^manashift / 256, min minmana.
- SkillDesc descline codes used: 2/4 "text +n tb", 3/5 "text n tb", 6, 7 "n text", 12/31 seconds,
  19/37 yards (x 2/3), 36, 38/43/52 ranges, 51/66 "%d" text, 63 synergy lines (dsc3).
- Durations: frames / 25 / 2 = turns (one round ~ 2 seconds).
- String tables have duplicate keys (Skillname223 twice): the first one wins (parse_tbl).

## Skill data (all classes) - already in the batch 1 samples

Skills.txt has all 210 class skills (30 per class: ama sor nec pal bar dru ass) with:
- damage: `emin/emax` (level 1) + `eminlev1..5 / emaxlev1..5` per level in brackets
  (levels 2-8, 9-16, 17-22, 23-28, 29+); same for physical `mindam/maxdam`, `minlevdam1..5`
- units: value << `hitshift` >> 8 (Fire Bolt: emin 6, hitshift 7 -> 3 damage)
- element `etype` (fire/cold/ltng/pois/mag), length `elen/elevlen1..3` (frames, 25 fps)
- **synergies**: `edmgsympercalc` / `elensympercalc` / `dmgsympercalc`, e.g.
  Fire Bolt: `(skill('Fire Ball'.blvl)+skill('Meteor'.blvl))*par8` -> parse skill('X'.blvl)
  terms and `parN` = Skills.txt `paramN`; result is +% damage
- `reqskill1-3`, `reqlevel`, `mana`, `lvlmana`, `minmana`, `manashift`, `tohit/levtohit`,
  `passivestat1-5 / passivecalc1-5` (passives), `aurastat1-6 / aurastatcalc1-6` (auras),
  `sumsk1-5` (summon skills), `srvmissile*` (Missiles.txt for projectiles)
- SkillDesc.txt: page/row/column/icon cell for the tree; `descline*` describe the tooltip.
Combat in this game: player hit chance is D2's formula mapped onto 60-95%
(`[game] min_hit_chance` in settings.ini; 5 = original D2).

## Hard-won format facts

- **DT1** tile header: subtile flags are at offset **+40** of the 96-byte tile record
  (25 bytes); flag bit 0 = blocks walking; subtile rows are stored **bottom-up**:
  index = `(4 - sy) * 5 + sx`.
- **DT1** block format 1 = 32x15 iso block (row widths 4..32..4), else RLE (x-skip, count).
- **DCC**: the "encoding type" bit is read **once per 4x4 cell**, not per pixel.
  Verified: all 5760 directions in the samples consume every bitstream exactly.
- **DCC directions** (16-dir sprites): screen direction (clockwise from south, 22.5 deg
  steps) -> sprite index `[4, 8, 0, 9, 5, 10, 1, 11, 6, 12, 2, 13, 7, 14, 3, 15]`;
  8-dir sprites use every second entry.
- **COF**: header 28 bytes, then 9 bytes per layer (component, shadow, selectable,
  transparent, draw effect, weapon class[4]), then keyframes, then draw order
  `[dir][frame][layer]`.
- **DS1** v18: objects after the layers; type 1 = NPC preset (Act 1 town ids:
  0 Gheed, 1 Cain, 2 Akara, 3 chicken, 4 rogue, 5 Kashya, 7 Warriv, 8 Charsi, 13 Flavie).
- **Fonts**: `.tbl` = "Woo!" + 8 bytes, then 14-byte entries
  `<HBBBBHHI>` = char, ?, width, height, ?, ?, frame, ?.
- **Explode** (PKWARE): table-driven version in d2/explode.py, reference kept as
  `explode_reference` for tests.

## Interface coordinates (D2 800x600 logical space, measured from the art)

- Control panel `800ctrlpnl7.dc6`: frames 0-5, widths 117,128,128,128,86,117 = 704 px,
  centred; frames 1-4 are 55 px tall, bottom-aligned.
- Globes `hlthmana.dc6` (80x80): left at holder +30, right at +594, **y = panel top + 12**;
  glass `overlap.dc6` at (-1, -1) from the globe. Draw holders first, then globes, then glass.
- Skill boxes: (153, 65) and (510, 65), 36x36. Belt: x = 375 + i*31, y = 66, 29x29.
  Thin XP bar (210, 64, 118x3); stamina/AP bar (226, 76, 102x17); run button (208, 75).
  Mini panel 176x26 at (262, 22) relative to the panel top-left; buttons 20x20 every 21 px.
- Inventory panel (`invchar6.dc6` frames 4-7, 320x432): helm (132,2,60,60),
  amulet (205,30,30,31), weapon (17,45,60,116), shield (248,45,60,117),
  armor (132,73,60,89), gloves (17,175,60,61), rings (91,175) and (205,175) 30x31,
  belt (133,175,60,31), boots (248,175,60,61), grid origin (18,255), 29 px cells, 10x4.
- Character panel (`invchar6.dc6` frames 0-3): see render/d2hud.py `_draw_char`.

## Samples

`tools/extract_samples.py --batch1..5` pulls small sets of files for development
(never committed; .gitignore blocks D2 formats). Batch 3 = skill icons, skill trees,
automap files, string tables, Act 1 layouts. Batch 4 = all classes + front-end screens.
Batch 5 = every palette, all seven heroes of the character creation screen, quest object
and waypoint graphics.

## Testing without a display

A PIL-backed pygame stand-in was used for headless screenshots (not part of the repo):
it supports Surface/Rect/draw/font/blend modes used by the game. Logic tests run bots
through whole caves (`World` + simple attack/move loop) to check balance.
