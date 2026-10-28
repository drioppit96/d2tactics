"""DS1 object numbers -> what they are.

D2 maps the object numbers in a DS1 (per act) to Objects.txt rows with an internal table (the
community's "obj.txt" is a dump of it; 1.14d's MPQs don't ship it). Act 1's numbers were
hand-checked earlier; Act 2's are read off D2's own room presets - e.g. number 115 is in all
four "Sewer Waypoint" rooms and nowhere else, 126 in all four "Tomb Talrasha" rooms (the orifice),
109 in the four "Tomb Cube" rooms (the Horadric Cube chest).
If an obj.txt is present anyway (a modded install), it is used.
"""
_cache = {}

# Act 2 (checked against LvlPrest's room names)
ACT2 = {
    10: "waypoint",        # Lut Gholein + the tomb waypoint rooms
    115: "waypoint",       # sewer waypoint rooms
    88: "waypoint",        # palace cellar waypoint rooms
    134: "waypoint",       # Canyon (KingWarp) + the Arcane Sanctuary's middle
    89: "arcane_portal",   # cellar 3 <-> Arcane Sanctuary
    126: "orifice",        # Tal Rasha's chamber: where the Horadric Staff goes
    109: "cube_chest",     # Halls of the Dead 3
    121: "staff_chest",    # Maggot Lair 3 (Coldworm's room)
    23: "viper_altar",     # Claw Viper Temple 2 (Serpent1)
    120: "scroll_chest",   # Radament's lair
    14: "journal",         # the Summoner's room: Horazon's journal
}
# Acts 3-5, read off their room presets the same way
ACT3 = {84: "waypoint", 115: "brain_chest", 113: "heart_chest"}   # 112 = a plain chest, 54 not only waypoints
ACT4 = {42: "hellforge"}
ACT5 = {101: "waypoint", 103: "waypoint", 118: "waypoint", 119: "waypoint", 120: "waypoint", 58: "prison"}
BY_ACT = {2: ACT2, 3: ACT3, 4: ACT4, 5: ACT5}

# Objects.txt names (lower case, substring) -> our object kinds, for obj.txt
KINDS = [("waypoint", "waypoint"), ("orifice", "orifice"), ("holder for horadric staff", "orifice"),
         ("arcane sanctuary portal", "arcane_portal"), ("horadric cube chest", "cube_chest"),
         ("staff of kings chest", "staff_chest"), ("horadric scroll chest", "scroll_chest"),
         ("tainted sun altar", "viper_altar"), ("yet another tome", "journal")]


def _rows(kit, name):
    from d2.source import read_table
    try:
        return read_table(kit.src, name)
    except Exception:
        return []


def quest_objects(kit, act):
    key = (id(kit.src), act)
    if key in _cache:
        return _cache[key]
    out = dict(BY_ACT.get(act, {}))
    obj = [r for r in _rows(kit, "Obj") if (r.get("act") or "").strip() == str(act)]
    if obj:
        objects = _rows(kit, "Objects")
        by_id = {}
        for i, r in enumerate(objects):
            try:
                by_id[int(r.get("id") or i)] = r
            except ValueError:
                by_id[i] = r
        found = {}
        for r in obj:
            try:
                ds1_id = int(r.get("id"))
                oid = int(r.get("objectid"))
            except (TypeError, ValueError):
                continue
            orow = by_id.get(oid, {})
            text = ((r.get("description") or "") + " " + (orow.get("name") or "") + " " +
                    (orow.get("description - not loaded") or "")).lower()
            for needle, kind in KINDS:
                if needle in text:
                    found[ds1_id] = kind
                    break
        if found:
            out = found
    _cache[key] = out
    return out
