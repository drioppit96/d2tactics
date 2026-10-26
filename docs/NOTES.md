# Developer notes and roadmap

Everything learned so far, so a new session can continue without re-discovering it.

## Status (end of day 1)

Working: MPQ reader (+ disk cache), DT1/DS1/DCC/DC6/COF/palette/font/string-table readers,
Rogue Encampment (4 D2 layouts, NPCs at preset positions), Den of Evil (6-room maze of
D2 cave presets, D2 roster and stats), turn-based combat with AP, D2 items/affixes,
D2 interface (control panel, globes, belt, mini panel, char sheet, 10x4 inventory,
skill tree fallback, quest log), Barbarian skills, Den of Evil quest, automap (own lines),
background prebuild of the Den, step-by-step walking with hold-to-walk.

## Next session - user's list

1. **Character creation** with all 7 classes (Amazon, Sorceress, Necromancer, Paladin,
   Barbarian, Druid, Assassin). Use D2's character-select art (`data\global\ui\FrontEnd\`,
   per-class folders with NU1-3 / FW / BW animations). Needs batch 4 samples.
2. **Every class's skill tree** with icons and **synergies** (Skills.txt `edmgsympercalc`,
   `eLenSymPerCalc`, `aurastat...`; SkillDesc for pages/rows/cols/icons; icons in
   `data\global\ui\SPELLS\<Xx>Skillicon.DC6`, trees `skltree_<x>_back.DC6`).
   Generalise game/skills.py: data-driven tree for any class; behaviour per skill
   "type" (melee attack, missile, nova, aura, summon, curse, warcry, passive...).
3. **Act 1 complete**: Blood Moor, Cold Plains, Stony Field, Dark Wood, Black Marsh,
   Tamoe Highland, Monastery Gate, Outer Cloister, Barracks, Jail 1-3, Inner Cloister,
   Cathedral, Catacombs 1-4 + all caves/crypts/tower. Outdoors seamless (one continuous
   world built from the wilderness DS1 presets); dungeons entered through their real
   entrance tiles (Levels.txt Vis0-7 / Warp0-7, LvlWarp.txt). Quests: Den of Evil (done),
   Blood Raven, Cain/Tristram (Cairn Stones), Forgotten Tower (Countess), Horadric Malus
   (Charsi / Barracks), Andariel. Waypoints. Needs batch 3 samples (outdoor DS1s).

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

`tools/extract_samples.py --batch1..4` pulls small sets of files for development
(never committed; .gitignore blocks D2 formats). Batch 3 = skill icons, skill trees,
automap files, string tables, Act 1 layouts. Batch 4 = all classes + front-end screens.

## Testing without a display

A PIL-backed pygame stand-in was used for headless screenshots (not part of the repo):
it supports Surface/Rect/draw/font/blend modes used by the game. Logic tests run bots
through whole caves (`World` + simple attack/move loop) to check balance.
