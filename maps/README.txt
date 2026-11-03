The map editor ("Map Editor.bat") edits the game's own hand-made maps - the Kurast Armory now, and the
ones added later. "Open" lists them; nothing else is edited in it.

- Paint floors and walls (Kurast fieldstone, plaster, pillars...), stamp rooms, place D2 objects
  (torches, braziers, chests, racks...), monsters, the game's sprites (Sprite tab) and markers
  (Marker tab - for the armory: the four altars and the smith's spot).
- Save writes <map name>.json here (kurast_armory.json for the armory); the game uses it the next
  time you go there. Delete that file to go back to the map the game comes with.
- A map's size, tileset and place in the game stay fixed. For the armory keep the gate where it is
  (the west side, facing the Bazaar), so it still joins the Bazaar.

Random dungeons: "Map Generator.bat" makes them (theme, rooms, loops, monsters, packs, champions,
uniques, a boss, shrines, wells, chests, barrels, bodies, racks, bookshelves, lights, waypoint).
Save writes <name>.json here; set "Replaces level" and the game plays it in place of that level
(its stairs lead where that level's stairs lead). The map editor opens these too.
