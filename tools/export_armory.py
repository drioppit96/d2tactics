"""Writes the Kurast Armory, as the code builds it, to assets/maps/kurast_armory.json - the map the
map editor opens and the game loads (your edits are saved to maps/kurast_armory.json instead):

    python tools/export_armory.py <path to your Diablo II folder or extracted files>
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def export(kit):
    from game import act3
    from game.act1 import Built
    from game.acts import apply_act_tables
    from game.objpreset import object_id
    R, A = act3.ARMORY_ROAD, act3.ARMORY
    W, H = R + A + 3, A + 3
    b = Built(W + 1, H + 1)
    apply_act_tables(b, 3, kit)
    act3.stamp_armory(kit, b, R, 0, procedural=True)
    tm = b.tm
    tiles = []
    for (x, y), ref in sorted(tm.floor.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        tiles.append([x, y, "f", ref[1].main, ref[1].sub])
    for (x, y), ref in sorted(tm.floor2.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        tiles.append([x, y, "f2", ref[1].main, ref[1].sub])
    for (x, y), refs in sorted(tm.walls.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        for ref in refs:
            o = ref[1].orientation
            if o == 4:
                continue                     # (drawn with its corner piece 3)
            tiles.append([x, y, "w", o, ref[1].main, ref[1].sub])
    objects = []
    for n, c, _o in b.gen_objects:
        oid = n[1] if isinstance(n, tuple) else object_id(3, n)
        if oid is not None:
            objects.append([c[0], c[1], int(oid)])
    for k, c, _o, _i in b.objects:
        if k == "waypoint":
            objects.append([c[0], c[1], "waypoint"])
    markers = [list(act3._acell(R, 0, *a)) + ["altar"] for a in act3.ARMORY_ALTARS]
    markers.append(list(act3._acell(R, 0, *act3.ARMORY_BOSS)) + ["smith"])
    return {"version": 1, "name": "Kurast Armory", "act": 3, "lvltype": "Act 3 - Kurast", "width": W, "height": H,
            "level": 0, "armory": True, "random_monsters": True, "rooms": [], "tiles": tiles, "objects": objects,
            "monsters": [], "decor": [[c[0], c[1], n] for n, c in b.decor], "markers": markers,
            "start": None, "exits": []}


def main(path):
    from d2.source import open_source, read_table
    from game.act1 import OutdoorKit
    src = open_source(path)
    kit = OutdoorKit(src, read_table(src, "Levels"), read_table(src, "LvlTypes"))
    data = export(kit)
    out = os.path.join(ROOT, "assets", "maps", "kurast_armory.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print("wrote", out, len(data["tiles"]), "tiles", len(data["decor"]), "sprites", len(data["objects"]), "objects")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
