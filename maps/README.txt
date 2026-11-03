The map editor ("Map Editor.bat") edits the game's own hand-made maps - the Kurast Armory now, and the
ones added later. "Open" lists them; nothing else is edited in it.

- Paint floors and walls (Kurast fieldstone, plaster, pillars...), stamp rooms, place D2 objects
  (torches, braziers, chests, racks...), monsters, the game's sprites (Sprite tab) and markers
  (Marker tab - for the armory: the four altars and the smith's spot).
- Save writes <map name>.json here (kurast_armory.json for the armory); the game uses it the next
  time you go there. Delete that file to go back to the map the game comes with.
- A map's size, tileset and place in the game stay fixed. For the armory keep the gate where it is
  (the west side, facing the Bazaar), so it still joins the Bazaar.

Random maps: "Map Generator.bat" makes dungeons (D2's maze rooms: theme, rooms, loops) and open worlds
(D2's outdoor areas: theme, width, height, landmarks), with monsters, packs, champions, uniques, a boss,
shrines, wells, chests, barrels, bodies, racks, bookshelves, lights and a waypoint. Every part is
reachable. Save writes <name>.json here and the map editor opens it; they are not in the game.
