# Acts 3-5: what is simplified or missing

Built from the uploaded Act 3 / 4 / 5 map packs (all 1087 room presets of LvlPrest.txt are
there), the monster packs and the tables. Tested headless (no Windows / MPQ run yet).

## Missing in the uploaded files
- Minions of Destruction (minion1/2/6/7, look "XX"): the monster extractor skipped the XX look
  (it is also used by dummy monsters). Fixed in tools/extract_monsters.py; in the game itself the
  animations come straight from your MPQs, so they should show.
- expansion\siege\debris.dt1 is named by the barricade cliff borders but is not in the files
  (probably not in D2 either): a few cliff edge decorations are not drawn.
- No obj.txt (1.14d doesn't ship it): the object numbers of the map pieces come from D2R's
  objpreset table instead (game/objpreset.py).

## Placed by code (D2's real spot unknown)
- Waypoints of the Kurast Docks, the jungle areas, Lower / Upper Kurast, Travincal, the
  Pandemonium Fortress, City of the Damned, River of Flame and Harrogath (near the middle of the
  area / town). Bazaar, Durance 2, ice caves, Worldstone Keep 2 and Halls of Pain use D2's own.
- Khalim's Eye chest (Spider Cavern, NE room), the Gidbinn's altar (Flayer Jungle), Lam Esen's
  lectern (every temple; the tome is in one of them per hero), frozen Anya (Frozen River middle),
  Nihlathak (Halls of Vaught middle), Diablo (the heart of the Chaos Sanctuary), the seal bosses.
- Hratli, Larzuk and Tyrael in Harrogath stand near the middle of town.

## Simplified
- Layout: jungle rivers are a random tree (D2's "o" edge pieces unused); the Great Marsh lies
  beside the Spider Forest / Flayer Jungle; the 13 Bloody Foothills strips are in random order;
  the barricade areas are 8 x 5 blocks (D2 sizes them per game); Act 5 cliff borders use the
  Act 1 border numbering (looks plausible, not verified piece by piece).
- Chaos Sanctuary, Throne of Destruction, Arreat Summit: seals, Baal's five waves and the
  Ancients' altar work (game/bosses.py); timing is per turn, not D2's real-time.
- The Golden Bird: the jade figurine drops from the first boss / unique you kill in the jungle.
- Siege on Harrogath: Larzuk sockets your first unsocketed equipped weapon / armour / helm /
  shield (no item window). Betrayal of Harrogath: Anya gives an item instead of personalizing.
- Rescue on Mount Arreat: break the prisons (D2 object 58) - the freed soldiers don't fight.
- Not spawned yet: Baal's taunt, Malachai, the windows of Harrogath.
- Monster skills: game/monskills.py knows about 80 of D2's monster skills; damage is level
  based (D2 takes it from Missiles.txt per missile), others fall back to the plain attack.
- Doors: D2 picks the door object per tileset by code; here a table (game/objects.DOOR_PAIRS)
  hangs doors in Acts 1-2 dungeons, cottages and tombs (Act 3-5 doorways stay open).
- Random object counts per area follow Levels.txt / ObjGroup.txt chances per 8x8 tile room;
  D2's exact "density" use is unknown.
- Not built: Uber Tristram / Pandemonium (Hell 1-3), Nightmare and Hell difficulty.

## Test-only options (remove later)
Akara "Level 99 (test)", Warriv "Go East (test)", Meshif "Sail East (test)", Cain in the Docks
"To Act 4 (test)", Tyrael "Travel to Harrogath (test)".
