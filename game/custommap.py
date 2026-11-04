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
   "links":    {"prev": level_id, "next": level_id},  # where rooms [tx, ty, path, "prev"/"next"] stairs lead
   "monster_level": 0,                        # 0: the level's own
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
    """The maps the map editor edits: the game's own (assets/maps) and the map generator's (maps)."""
    out = set()
    for d in (GAME_MAPS, MAPS):
        if os.path.isdir(d):
            out |= {f[:-5] for f in os.listdir(d) if f.lower().endswith(".json")}
    return sorted(out)


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
    """The custom map that replaces this level, if there is one (yours first, then the game's own)."""
    if not isinstance(level_id, int) or level_id <= 0:
        return None
    paths = [os.path.join(MAPS, fn) for fn in list_maps()]
    if os.path.isdir(GAME_MAPS):
        mine = set(list_maps())
        paths += [os.path.join(GAME_MAPS, f) for f in sorted(os.listdir(GAME_MAPS))
                  if f.lower().endswith(".json") and f not in mine]
    for path in paths:
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
    links = data.get("links") or {}
    # an open world's plain ground: [preset it comes from, [[tx, ty, main, sub], ...]]
    for src, cells in data.get("ground", []):
        gds = kit.ds1(src)
        if gds is None:
            continue
        gts = kit.tiles_for(gds, lt)
        for tx, ty, main, sub in cells:
            ref = gts.pick(0, int(main), int(sub), _rnd(tx, ty))
            if ref:
                b.tm.floor[(int(tx) + ox, int(ty) + oy)] = ref
    keep = bool(data.get("keep_edges", False))
    for room in data.get("rooms", []):
        tx, ty, path = room[0], room[1], room[2]
        ds = kit.ds1(path)
        if ds is not None and len(room) > 4 and room[4]:
            from .act3 import _Sub                  # [tx, ty, path, role, [sx, sy, w, h]]: a piece of it
            sx, sy, sw, sh = room[4]
            src_ds = ds
            ds = _Sub(src_ds, int(sx), int(sy), int(sw), int(sh))
            ds.files = src_ds.files
        if ds is not None:
            n0 = len(b.warps)
            no, ng = len(b.objects), len(b.gen_objects)
            stamp(b, ds, kit.tiles_for(src_ds if len(room) > 4 and room[4] else ds, lt), int(tx) + ox, int(ty) + oy, random.Random(_rnd(tx, ty)), owner,
                  keep_edges=keep)
            if not data.get("room_objects", True):        # (the generator's "rooms' own objects: off")
                del b.gen_objects[ng:]
                b.objects[no:] = [o for o in b.objects[no:] if o[0] in ("waypoint", "portal")]
            # a room with a role ("prev" / "next" stairs): its stairs lead where the map says
            wt = b.__dict__.setdefault("warp_targets", {})
            role = room[3] if len(room) > 3 and room[3] else None
            for _t, main, ow in b.warps[n0:]:
                wt[(ow, main)] = links.get(role) if role else wt.get((ow, main))
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


def block_walls(data, grid, ox, oy):
    """Solid Kurast fieldstone / plaster walls block all along their edges, pillars round them (their
    tiles alone leave gaps). ox, oy: the map's tile offset in the grid."""
    from .grid import WALL

    def block(x0, y0, x1, y1):
        for y in range(y0, y1):
            for x in range(x0, x1):
                if grid.in_bounds(x, y):
                    grid.cells[y][x] = WALL
    for t in data.get("tiles", []):
        if t[2] != "w":
            continue
        o, main = int(t[3]), int(t[4])
        X, Y = (int(t[0]) + ox) * SUB, (int(t[1]) + oy) * SUB
        if o == 12:
            block(X - 1, Y - 1, X + 2, Y + 2)
            continue
        if main not in (20, 24):
            continue
        block(X - 1, Y - 1, X + 1, Y + 1)
        if o in (2, 3, 6):
            block(X, Y - 1, X + SUB + 1, Y + 1)
        if o in (1, 3, 5):
            block(X - 1, Y, X + 1, Y + SUB + 1)


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
        block_walls(data, grid, 0, 0)
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
    b.monster_level = int(data.get("monster_level") or 0)
    b.random_objects = bool(data.get("random_objects", True))
    return b, grid, rng


def spawn_monsters(world, built, taken, info):
    """The monsters the designer placed."""
    from . import actworld
    for cell, what, kind in getattr(built, "custom_monsters", []) or []:
        owner = world.area_at(cell) or world.level_id
        lvl = getattr(built, "monster_level", 0) or (info.monster_level(owner) if info else 10)
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
