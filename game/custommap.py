"""Hand-made areas from the map editor (tools/mapeditor.py, "Map Editor.bat").

A map is a JSON file in the maps folder:

  {"version": 1, "name": "...", "act": 3, "lvltype": "Act 3 - Kurast",
   "width": 48, "height": 48,                 # in D2 floor tiles (5 x 5 cells each)
   "level": 0,                                # a level id it replaces in the game (0 = none)
   "random_monsters": true,                   # also fill it with the level's usual monsters
   "rooms":    [[tx, ty, "act3\\kurast\\slums08x08_0.ds1"], ...],     # whole D2 presets, stamped first
   "tiles":    [[tx, ty, "f", main, sub], [tx, ty, "f2", main, sub],  # floors (f2 = second floor layer)
                [tx, ty, "w", orientation, main, sub],               # walls / roofs / lower walls
                [tx, ty, "x"],                                       # erase everything on that tile
                [tx, ty, "dw", "<preset .ds1>", o, main, sub],       # a tile borrowed from any D2 preset
                [tx, ty, "df", "<preset .ds1>", main, sub]],         # (any act: Act 1's forge, Andariel's blood)
   "objects":  [[cx, cy, objects_txt_id], [cx, cy, "waypoint"], ...],  # cells (sub-tiles)
   "monsters": [[cx, cy, "monstats id or super unique name", "normal|champion|unique|pack|super"], ...],
   "decor":    [[cx, cy, "sprite name (assets/decor)"], ...],
   "markers":  [[cx, cy, "altar" | "smith"], ...],                  # (the Kurast Armory's quest spots)
   "start":    [cx, cy],
   "exits":    [[cx, cy, level_id], ...]}

Tiles are picked the way D2 does (by orientation, main and sub index), with a fixed choice per
position so the editor and the game show the same picture.
"""
import json
import os
import random

from .act1 import Built, stamp, make_grid, SUB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPS = os.path.join(ROOT, "maps")
GAME_MAPS = os.path.join(ROOT, "assets", "maps")     # the hand-made maps the game is built with
_cache = {}


def game_maps():
    """The game's own hand-made maps (assets/maps/<name>.json) - the ones the map editor edits."""
    if not os.path.isdir(GAME_MAPS):
        return []
    return sorted(f[:-5] for f in os.listdir(GAME_MAPS) if f.lower().endswith(".json"))


def game_map_path(name):
    """Your edited copy (maps/<name>.json) if there is one, else the game's own."""
    mine = os.path.join(MAPS, name + ".json")
    return mine if os.path.exists(mine) else os.path.join(GAME_MAPS, name + ".json")


def game_map(name):
    """One of the game's hand-made maps as data (your edited copy first), or None."""
    for path in (os.path.join(MAPS, name + ".json"), os.path.join(GAME_MAPS, name + ".json")):
        if os.path.exists(path):
            try:
                return load(path)
            except Exception:
                continue
    return None


def list_maps():
    if not os.path.isdir(MAPS):
        return []
    return sorted(f for f in os.listdir(MAPS) if f.lower().endswith(".json"))


def load(name):
    path = name if os.path.isabs(name) else os.path.join(MAPS, name)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(data, name):
    os.makedirs(MAPS, exist_ok=True)
    path = os.path.join(MAPS, name if name.lower().endswith(".json") else name + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    return path


def for_level(level_id):
    """The custom map that replaces this level, if there is one."""
    if not isinstance(level_id, int) or level_id <= 0:
        return None
    for fn in list_maps():
        path = os.path.join(MAPS, fn)
        try:
            mt = os.path.getmtime(path)
            ent = _cache.get(path)
            if ent is None or ent[0] != mt:
                ent = _cache[path] = (mt, load(path))
            if int(ent[1].get("level") or 0) == level_id:
                return ent[1]
        except Exception:
            continue
    return None


def tileset(kit, lvltype):
    """All the DT1 tiles of one level type (LvlTypes.txt)."""
    from .d2level import _dt1_for
    from d2.dt1 import TileSet
    key = ("lvltype", lvltype)
    if key not in kit.tileset_cache:
        files = ["\\d2\\data\\global\\tiles\\" + f.replace("/", "\\") for f in kit.lvltypes.get(lvltype, [])]
        kit.tileset_cache[key] = TileSet(_dt1_for(kit.src, files, kit.dt1_cache))
    return kit.tileset_cache[key]


def _rnd(x, y, k=0):
    return (x * 73856093 ^ y * 19349663 ^ k * 83492791) & 0xFFFF


def lay_tiles(kit, b, data, ox, oy, owner):
    """The map's rooms and tiles into a Built, its tile (0, 0) at tile (ox, oy). Several wall entries
    of one orientation on a tile all stay (layered walls); a later paint replaces the room's."""
    lt = data.get("lvltype", "")
    for tx, ty, path in data.get("rooms", []):
        ds = kit.ds1(path)
        if ds is not None:
            stamp(b, ds, kit.tiles_for(ds, lt), int(tx) + ox, int(ty) + oy, random.Random(_rnd(tx, ty)), owner,
                  keep_edges=False)
    ts = tileset(kit, lt)
    tm = b.tm
    mine = set()
    foreign = {}
    for t in data.get("tiles", []):
        tx, ty, layer = int(t[0]), int(t[1]), t[2]
        pos = (tx + ox, ty + oy)
        if layer in ("dw", "df", "df2"):
            path = t[3]
            if path not in foreign:
                ds = kit.ds1(path)
                foreign[path] = kit.tiles_for(ds) if ds is not None else None
            fts = foreign[path]
            if fts is None:
                continue
            if layer == "dw":
                ref = fts.pick(int(t[4]), int(t[5]), int(t[6]), _rnd(tx, ty, int(t[4])))
                if ref:
                    tm.walls.setdefault(pos, []).append(ref)
            else:
                ref = fts.pick(0, int(t[4]), int(t[5]), _rnd(tx, ty))
                if ref:
                    (tm.floor if layer == "df" else tm.floor2)[pos] = ref
            continue
        if layer == "x":
            tm.floor.pop(pos, None)
            tm.floor2.pop(pos, None)
            tm.walls.pop(pos, None)
            continue
        if layer in ("f", "f2"):
            ref = ts.pick(0, int(t[3]), int(t[4]), _rnd(tx, ty))
            if ref:
                (tm.floor if layer == "f" else tm.floor2)[pos] = ref
        elif layer == "w":
            o, main, sub = int(t[3]), int(t[4]), int(t[5])
            keep = (pos, o) in mine
            lst = [r for r in tm.walls.get(pos, []) if keep or getattr(r[1], "orientation", -1) not in (o, 4 if o == 3 else -9)]
            for oo in ([o, 4] if o == 3 else [o]):
                ref = ts.pick(oo, main, sub, _rnd(tx, ty, oo))
                if ref:
                    lst.append(ref)
            tm.walls[pos] = lst
            mine.add((pos, o))


def lay_things(b, data, ox, oy, owner):
    """The map's objects, sprites and markers (cells shifted by the tile offset)."""
    dx, dy = ox * SUB, oy * SUB
    for o in data.get("objects", []):
        cx, cy, what = int(o[0]) + dx, int(o[1]) + dy, o[2]
        if what in ("waypoint", "portal"):
            b.objects.append((what, (cx, cy), owner, -1))
        else:
            b.gen_objects.append((("id", int(what)), (cx, cy), owner))
    decor = b.__dict__.setdefault("decor", [])
    for cx, cy, name in data.get("decor", []):
        decor.append((name, (int(cx) + dx, int(cy) + dy)))
    b.__dict__.setdefault("markers", [])
    for cx, cy, what in data.get("markers", []):
        b.markers.append((what, (int(cx) + dx, int(cy) + dy)))


def compose(kit, data, level_id=0, seed=None, with_grid=True):
    """The map as a Built (tiles, objects, monsters, exits) - used by the editor and the game."""
    from .acts import apply_act_tables
    tw, th = int(data.get("width", 32)), int(data.get("height", 32))
    b = Built(tw + 1, th + 1)
    act = int(data.get("act", 1) or 1)
    apply_act_tables(b, act, kit)
    rng = random.Random(seed if seed is not None else 12345)
    lt = data.get("lvltype", "")
    owner = level_id or 0
    lay_tiles(kit, b, data, 0, 0, owner)
    tm = b.tm
    b.areas[owner] = (0, 0, tw * SUB, th * SUB)
    tm.drawn = set(tm.floor) | set(tm.walls) | set(tm.floor2)
    grid = make_grid(tm) if with_grid else None
    lay_things(b, data, 0, 0, owner)
    if grid is not None:
        from .act3 import _block_decor
        _block_decor(b, grid)
    b.custom_monsters = [((int(m[0]), int(m[1])), m[2], (m[3] if len(m) > 3 else "normal"))
                         for m in data.get("monsters", [])]
    st = data.get("start")
    b.custom_start = (int(st[0]), int(st[1])) if st else None
    b.edge_exits = []
    for cx, cy, target in data.get("exits", []):
        cells = [(cx + dx, cy + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
        b.edge_exits.append((cells, int(target)))
    b.random_monsters = bool(data.get("random_monsters", True))
    return b, grid, rng


def spawn_monsters(world, built, taken, info):
    """The monsters the designer placed."""
    from . import actworld
    for cell, what, kind in getattr(built, "custom_monsters", []) or []:
        owner = world.area_at(cell) or world.level_id
        lvl = info.monster_level(owner) if info else 10
        if kind == "super":
            actworld._spawn_preset(world, what, cell, owner, taken, info)
            continue
        if world.content is None or what not in world.content.monstats:
            continue
        c = actworld._free_near(world.grid, cell, 4)
        if kind == "pack":
            actworld._pack(world, c, what, lvl, taken)
        elif kind == "unique":
            actworld._pack(world, c, what, lvl, taken, unique=True)
        elif kind == "champion":
            actworld._pack(world, c, what, lvl, taken, champion=True)
        else:
            actworld._spawn(world, what, c, lvl, taken)
