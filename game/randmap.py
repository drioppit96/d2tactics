"""Random dungeon maps for the map generator (tools/mapgen.py, "Map Generator.bat").

A map is laid out the way D2 builds its mazes: a tree of rooms (plus extra links for loops) on a grid,
each room one of the theme's own presets with exactly the doorways it needs - so every room joins its
neighbours. The result is checked by walking it: a map where any room can't be reached is thrown away
and laid out again. Then it is filled: monsters (the theme's own or any you pick, in packs, champions,
uniques, a super unique boss in the farthest room), shrines, wells, chests, breakables, bodies, racks
and lights - on reachable ground, spread over the rooms.

The output is an ordinary custom map (game/custommap.py) that the map editor opens and the game plays
when "level" is set (it replaces that level; its stairs lead where that level's stairs lead).
"""
import math
import random
from collections import deque

from .act1 import MAZES, COMBOS, DIRS, OPP, SUB, _canon, _grow

# theme key -> (shown name, act). Every one is a D2 maze kit (LvlMaze / LvlPrest rooms).
THEMES = [("cave", "Act 1 - Caves", 1), ("crypt", "Act 1 - Crypt", 1), ("barracks", "Act 1 - Barracks", 1),
          ("jail", "Act 1 - Jail", 1), ("catacombs", "Act 1 - Catacombs", 1), ("sewer", "Act 2 - Sewers", 2),
          ("tomb", "Act 2 - Tomb", 2), ("lair", "Act 2 - Maggot Lair", 2), ("a3dung", "Act 3 - Jungle Dungeon", 3),
          ("a3sewer", "Act 3 - Sewers", 3), ("meph", "Act 3 - Durance of Hate", 3),
          ("lava", "Act 4 - River of Flame", 4), ("ice", "Act 5 - Ice Caves", 5),
          ("baal", "Act 5 - Worldstone Keep", 5)]
THEME_NAMES = {k: n for k, n, _a in THEMES}
# the D2 levels each theme comes from (their monsters and monster levels)
THEME_LEVELS = {"cave": (9, 10, 11, 12, 13, 14, 15), "crypt": (16, 17, 18, 19), "barracks": (28,), "jail": (29, 30, 31),
                "catacombs": (34, 35, 36), "sewer": (47, 48, 49), "tomb": (66, 67, 68, 69, 70, 71, 72),
                "lair": (62, 63, 64), "a3dung": (84, 85, 86, 87, 88, 89, 90, 91), "a3sewer": (92, 93),
                "meph": (100, 101), "lava": (107,), "ice": (113, 114, 115, 116, 117, 118),
                "baal": (128, 129, 130)}
THEME_ACT = {k: a for k, _n, a in THEMES}

# open worlds: D2's outdoor areas, built from their border and fill presets block by block
OPEN_THEMES = [("wild", "Act 1 - Wilderness", 1), ("desert", "Act 2 - Desert", 2), ("jungle", "Act 3 - Jungle", 3),
               ("slums", "Act 3 - Kurast Slums", 3), ("burbs", "Act 3 - Kurast Bazaar", 3),
               ("metro", "Act 3 - Upper Kurast", 3), ("steppes", "Act 4 - Outer Steppes", 4),
               ("plains", "Act 4 - Plains of Despair", 4), ("damned", "Act 4 - City of the Damned", 4),
               ("highlands", "Act 5 - Rigid Highlands", 5), ("plateau", "Act 5 - Arreat Plateau", 5)]
OPEN_NAMES = {k: n for k, n, _a in OPEN_THEMES}
OPEN_ACT = {k: a for k, _n, a in OPEN_THEMES}
OPEN_LEVELS = {"wild": (2, 3, 4, 5, 6, 7), "desert": (41, 42, 43, 44), "jungle": (76, 77, 78), "slums": (79,),
               "burbs": (80,), "metro": (81,), "steppes": (104,), "plains": (105,), "damned": (106,),
               "highlands": (111,), "plateau": (112,)}

# what can be scattered: option name -> object kinds (game/objects.py OPERATE_KIND)
OBJECT_OPTIONS = [("shrines", ("shrine",)), ("wells", ("well",)), ("chests", ("chest", "casket")),
                  ("breakables", ("barrel", "urn", "xbarrel")), ("bodies", ("corpse",)),
                  ("racks", ("armor_rack", "weapon_rack")), ("bookshelves", ("bookshelf",))]

DEFAULTS = dict(kind="dungeon", name="random_dungeon", theme="catacombs", open_theme="wild",
                town_theme="rogue", buildings=10, roads=True, width=10, height=10,
                fill=60, open_packs=30, rooms=12, loops=2, theme_rooms=20,
                monsters=[], packs=2, champions=2, uniques=1, boss="", monster_level=0,
                shrines=3, wells=1, chests=4, breakables=6, bodies=3, racks=1, bookshelves=0, lights=6,
                waypoint=False, room_objects=True, level=0, seed=None)


def _load_acts():
    from . import act2, act3, act4, act5      # noqa: F401  (their maze kits join MAZES)


def _act_bit(act):
    return 1 << (act - 1)


def _ints(row, k):
    try:
        return int(row.get(k) or 0)
    except ValueError:
        return 0


class Kit:
    """A theme's room presets by doorways, as preset paths (what a custom map's "rooms" hold)."""

    def __init__(self, kit, theme):
        _load_acts()
        from .act1 import MazeKit
        spec = MAZES[theme]
        self.kit, self.theme, self.spec = kit, theme, spec
        mk = kit.mazes.get(theme)
        if mk is None:
            mk = kit.mazes[theme] = MazeKit(kit, theme)
        self.mk = mk
        self.rw, self.rh = mk.rw, mk.rh
        folder, prefix = spec["folder"], spec["prefix"]
        variants = spec.get("variants", ("", "1", "2", "3", "4"))
        good = {id(ds) for lst in mk.rooms.values() for ds in lst}
        self.rooms = {}
        for combo in COMBOS:
            for n in variants:
                path = folder + "%s%s%s.ds1" % (prefix, combo, n)
                ds = kit.ds1(path)
                if ds is not None and id(ds) in good:
                    self.rooms.setdefault(frozenset(combo), []).append(path)
        self.themed = {}
        pat = spec.get("theme")
        if pat:
            for combo in COMBOS:
                path = folder + pat.format(x=combo) + ".ds1"
                if kit.ds1(path) is not None:
                    self.themed.setdefault(frozenset(combo), []).append(path)

    def role(self, role, exits, rng):
        pat = self.spec.get("roles", {}).get(role)
        if not pat:
            return None
        pats = pat if isinstance(pat, (list, tuple)) else [pat]
        cands = []
        for p in pats:
            for n in tuple(self.spec.get("variants", ("", "1", "2", "3", "4"))) + ("",):
                path = self.spec["folder"] + p.format(d=_canon(exits), x=_canon(exits), n=n) + ".ds1"
                if self.kit.ds1(path) is not None and path not in cands:
                    cands.append(path)
        return rng.choice(cands) if cands else None


def _layout(k, n, loops, rng):
    cols = rows = max(3, int(math.ceil(math.sqrt(n * 2.0))))
    for _ in range(80):
        lay = _grow(n, rng, cols, rows)
        cells = list(lay)
        rng.shuffle(cells)
        added = 0
        for c in cells:
            if added >= loops:
                break
            for d in rng.sample(list(DIRS), 4):
                nb = (c[0] + DIRS[d][0], c[1] + DIRS[d][1])
                if nb in lay and d not in lay[c]:
                    a, b_ = frozenset(lay[c] | {d}), frozenset(lay[nb] | {OPP[d]})
                    if a in k.rooms and b_ in k.rooms:
                        lay[c].add(d)
                        lay[nb].add(OPP[d])
                        added += 1
                        break
        if all(frozenset(ex) in k.rooms for ex in lay.values()):
            mx = min(x for x, _ in lay)
            my = min(y for _, y in lay)
            return {(x - mx, y - my): ex for (x, y), ex in lay.items()}
    raise RuntimeError("could not lay out %d rooms of %s" % (n, k.theme))


def level_links(kit, level):
    """Where a level's stairs lead (Levels.txt Vis): the way back (the lower id) and on (a higher one)."""
    r = kit.levels.get(level) if level else None
    if not r:
        return {}
    vis = [_ints(r, "vis%d" % i) for i in range(8)]
    vis = [v for v in vis if v > 0]
    out = {}
    if vis:
        out["prev"] = min(vis)
        nxt = [v for v in vis if v > level]
        if nxt:
            out["next"] = max(nxt)
    return out


def theme_monsters(kit, content, theme, table=None):
    """The monsters D2 puts in the theme's own levels."""
    out = []
    for lid in (table or THEME_LEVELS).get(theme, ()):
        r = kit.levels.get(lid) or {}
        for i in range(1, 11):
            m = (r.get("mon%d" % i) or "").lower()
            if m and (content is None or m in content.monstats) and m not in out:
                out.append(m)
    return out


def theme_level(kit, theme, table=None):
    """The theme's monster level (normal difficulty): its deepest D2 level's."""
    best = 1
    for lid in (table or THEME_LEVELS).get(theme, ()):
        r = kit.levels.get(lid) or {}
        best = max(best, _ints(r, "monlvl1ex") or _ints(r, "monlvl1"))
    return best


def _level_is(kit, lid, lvltype):
    r = kit.levels.get(lid) or {}
    t = r.get("leveltype")
    names = getattr(kit, "lvltype_names", None)
    if names is None:
        names = kit.lvltype_names = {}
        try:
            from d2.source import read_table
            for row in read_table(kit.src, "LvlTypes"):
                try:
                    names[int(row.get("id") or -1)] = row.get("name", "")
                except ValueError:
                    pass
        except Exception:
            pass
    try:
        return names.get(int(t or -1), "") == lvltype
    except ValueError:
        return False


def object_choices(objdata, act):
    """Objects.txt ids by kind that belong to this act (Objects.txt Act is a bit mask)."""
    out = {}
    for oid, r in objdata.rows.items():
        try:
            kind = objdata.kind(oid)
        except Exception:
            kind = None
        if kind is None:
            continue
        if not (_ints(r, "act") & _act_bit(act)):
            continue
        out.setdefault(kind, []).append(oid)
    # (the light sources: torches, braziers, fires that are only drawn)
    lights = []
    for oid, r in objdata.rows.items():
        name = ((r.get("description - not loaded") or "") + " " + (r.get("name") or "")).lower()
        if (_ints(r, "act") & _act_bit(act)) and any(w in name for w in ("torch", "brazier", "candle")):
            try:
                if objdata.kind(oid) == "decor":
                    lights.append(oid)
            except Exception:
                pass
    out["light"] = lights
    return out


def _flood(grid, start):
    seen = {start}
    q = deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c = (x + dx, y + dy)
            if c not in seen and grid.in_bounds(*c) and grid.walkable(*c):
                seen.add(c)
                q.append(c)
    return seen


def _near_walkable(grid, c, r=10):
    for k in range(r):
        for dx in range(-k, k + 1):
            for dy in range(-k, k + 1):
                p = (c[0] + dx, c[1] + dy)
                if grid.in_bounds(*p) and grid.walkable(*p):
                    return p
    return None


def generate(kit, content, objdata, opts, log=None):
    """A random map as a custom map (dict): a dungeon, an open world (opts["kind"] == "open") or a
    town built from D2's own town buildings (opts["kind"] == "town", see game/townmap.py)."""
    o = dict(DEFAULTS)
    o.update(opts or {})
    if o.get("kind") == "town":
        from . import townmap
        doc = townmap.generate(kit, o)
        doc.pop("_placed", None)
        return doc
    if o.get("kind") == "open":
        return _generate_open(kit, content, objdata, o, log)
    return _generate_dungeon(kit, content, objdata, o, log)


def _generate_dungeon(kit, content, objdata, opts, log=None):
    from . import custommap
    o = dict(DEFAULTS)
    o.update(opts or {})
    seed = o["seed"] if o["seed"] is not None else random.randrange(1 << 30)
    rng = random.Random(seed)
    theme = o["theme"]
    k = Kit(kit, theme)
    act = THEME_ACT.get(theme, 1)
    lt = k.spec["lvltype"]
    links = level_links(kit, int(o["level"] or 0))
    n = max(2, int(o["rooms"]))
    for attempt in range(40):
        lay = _layout(k, n, int(o["loops"]), rng)
        leaves = [c for c, ex in lay.items() if len(ex) == 1]
        rng.shuffle(leaves)
        roles = {}
        # the first room: the stairs back (when the theme has them), the last: the stairs on
        for role in ("prev", "next"):
            if role == "next" and not links.get("next"):
                continue
            for c in leaves:
                if c in roles.values():
                    continue
                path = k.role(role, lay[c], rng)
                if path:
                    roles[role] = (c, path)
                    break
        start_room = roles["prev"][0] if "prev" in roles else (leaves[0] if leaves else next(iter(lay)))
        if "next" in roles and roles["next"][0] == start_room:
            del roles["next"]
        rooms = []
        role_at = {c: (r, p) for r, (c, p) in roles.items()}
        for (rx, ry), ex in sorted(lay.items()):
            key = frozenset(ex)
            if (rx, ry) in role_at:
                role, path = role_at[(rx, ry)]
                rooms.append([rx * k.rw, ry * k.rh, path, role])
                continue
            if k.themed.get(key) and rng.random() * 100 < int(o["theme_rooms"]) and (rx, ry) != start_room:
                path = rng.choice(k.themed[key])
            else:
                path = rng.choice(k.rooms[key])
            rooms.append([rx * k.rw, ry * k.rh, path])
        cw = max(x for x, _ in lay) + 1
        ch = max(y for _, y in lay) + 1
        data = {"version": 1, "name": o["name"], "act": act, "lvltype": lt, "width": cw * k.rw, "height": ch * k.rh,
                "level": int(o["level"] or 0), "random_monsters": False, "random_objects": False, "rooms": rooms, "tiles": [],
                "objects": [], "monsters": [], "decor": [], "markers": [], "start": None, "exits": [],
                "links": {r: links[r] for r in ("prev", "next") if links.get(r)},
                "room_objects": bool(o.get("room_objects", True)),
                "monster_level": int(o["monster_level"] or 0) or (0 if o["level"] else theme_level(kit, theme)),
                "generated": dict(o, seed=seed)}
        b, grid, _r = custommap.compose(kit, data, data["level"], seed)
        # walk it: every room must be reachable from the first
        sx, sy = start_room
        rect = lambda c: (c[0] * k.rw * SUB, c[1] * k.rh * SUB, (c[0] + 1) * k.rw * SUB, (c[1] + 1) * k.rh * SUB)
        x0, y0, x1, y1 = rect(start_room)
        start = _near_walkable(grid, ((x0 + x1) // 2, (y0 + y1) // 2), 30)
        if start is None:
            continue
        seen = _flood(grid, start)
        cells_of = {}
        for c in seen:
            rc = (c[0] // (k.rw * SUB), c[1] // (k.rh * SUB))
            cells_of.setdefault(rc, []).append(c)
        if any(len(cells_of.get(c, [])) < 40 for c in lay):
            if log:
                log("layout %d: a room can't be reached - laying out again" % attempt)
            continue
        break
    else:
        raise RuntimeError("no fully connected layout found - try fewer rooms or another theme")
    # the stairs (warp tiles) and the cells right by them stay clear
    warp_cells = set()
    for (tx, ty), _m, _ow in b.warps:
        for dx in range(-3, SUB + 3):
            for dy in range(-3, SUB + 3):
                warp_cells.add((tx * SUB + dx, ty * SUB + dy))
    data["start"] = list(start)
    # rooms by their distance from the first (the boss waits in the farthest)
    dist = {start_room: 0}
    q = deque([start_room])
    while q:
        c = q.popleft()
        for d in lay[c]:
            nb = (c[0] + DIRS[d][0], c[1] + DIRS[d][1])
            if nb in lay and nb not in dist:
                dist[nb] = dist[c] + 1
                q.append(nb)
    order = sorted(lay, key=lambda c: dist.get(c, 0))
    far = order[-1]
    _fill(data, o, rng, grid, start, start_room, cells_of, order, far, warp_cells, kit, content, objdata, theme, act)
    data["boss_room"] = list(far)
    data["room_size"] = [k.rw, k.rh]
    return data


def _fill(data, o, rng, grid, start, start_room, cells_of, order, far, warp_cells, kit, content, objdata, theme, act):
    """Monsters and objects on reachable ground, spread over the rooms (or open-world blocks)."""
    used = []

    def clear(c, r):
        return all(abs(c[0] - u[0]) + abs(c[1] - u[1]) >= r for u in used)

    def pick(room, near_wall=False, r=8):
        cells = cells_of.get(room, [])
        cand = [c for c in cells if c not in warp_cells and abs(c[0] - start[0]) + abs(c[1] - start[1]) > 6]
        rng.shuffle(cand)
        for c in cand[:400]:
            if not clear(c, r):
                continue
            if near_wall:
                ok = all(grid.walkable(c[0] + dx, c[1] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
                wall = any(not grid.walkable(c[0] + dx, c[1] + dy) for dx in (-3, 0, 3) for dy in (-3, 0, 3)
                           if grid.in_bounds(c[0] + dx, c[1] + dy))
                if not (ok and wall):
                    continue
            used.append(c)
            return c
        return None
    others = [c for c in order if c != start_room] or [start_room]

    def spread(count):
        rooms_ = others[:]
        rng.shuffle(rooms_)
        return [rooms_[i % len(rooms_)] for i in range(count)]
    # objects
    choices = object_choices(objdata, act) if objdata is not None else {}
    if o.get("waypoint"):
        c = pick(start_room, False, 10) or _near_walkable(grid, (start[0] + 6, start[1]), 10)
        if c:
            data["objects"].append([c[0], c[1], "waypoint"])
    for opt, kinds in OBJECT_OPTIONS + [("lights", ("light",))]:
        ids = [i for kd in kinds for i in choices.get(kd, [])]
        if not ids:
            continue
        for room in spread(int(o.get(opt, 0) or 0)):
            c = pick(room, True, 7 if opt != "lights" else 5)
            if c:
                data["objects"].append([c[0], c[1], rng.choice(ids)])
    # monsters
    mons = [m for m in (o["monsters"] or theme_monsters(kit, content, theme, OPEN_LEVELS if theme in OPEN_LEVELS else None))
            if content is None or m in content.monstats]
    if mons:
        if o.get("kind") == "open":            # an open world: a number of packs over the whole map
            for room in spread(int(o.get("open_packs", 30))):
                c = pick(room, False, 12)
                if c:
                    data["monsters"].append([c[0], c[1], rng.choice(mons), "pack"])
        else:
            for room in others:
                for _ in range(int(o["packs"])):
                    c = pick(room, False, 10)
                    if c:
                        data["monsters"].append([c[0], c[1], rng.choice(mons), "pack"])
        for count, kind in ((int(o["champions"]), "champion"), (int(o["uniques"]), "unique")):
            for room in spread(count):
                c = pick(room, False, 10)
                if c:
                    data["monsters"].append([c[0], c[1], rng.choice(mons), kind])
    if o.get("boss"):
        c = pick(far, False, 6)
        if c:
            data["monsters"].append([c[0], c[1], o["boss"], "super"])


# ---------------------------------------------------------------- open worlds
class _RecCanvas:
    """A drlg Canvas that also writes down what it lays: presets (-> "rooms") and plain ground."""

    def __init__(self, kit, tw, th, act, seed):
        from .drlg import Canvas
        self.cv = Canvas(kit, tw, th, act, seed)
        self.puts = []
        self.ground_refs = {}            # pos -> (ref, preset path, main, sub)
        self.ground_src = {}

    def __getattr__(self, k):
        return getattr(self.cv, k)

    def put(self, name, tx, ty, owner, lvltype):
        ds = self.cv.put(name, tx, ty, owner, lvltype)
        if ds is not None:
            self.puts.append([tx, ty, name])
        return ds

    def set_ground(self, key, preset, lvltype, codes=None):
        self.cv.set_ground(key, preset, lvltype)
        if codes is not None:
            ds, _c, tiles, lt = self.cv.grounds[key]
            self.cv.grounds[key] = (ds, codes, tiles, lt)
        self.ground_src[key] = preset

    def ground(self, key, tx0, ty0, w, h):
        ds, codes, tiles, _lt = self.cv.grounds[key]
        if tiles is None:
            return
        rng = self.cv.rng
        for y in range(h):
            for x in range(w):
                main, sub = rng.choice(codes)
                t = tiles.pick(0, main, sub, rng.randrange(1 << 16))
                if t:
                    self.cv.b.tm.floor[(tx0 + x, ty0 + y)] = t
                    self.ground_refs[(tx0 + x, ty0 + y)] = (t, self.ground_src[key], main, sub)


def _block_names(kit, names):
    return [n for n in names if kit.ds1(n) is not None]


def _fills_by_size(kit, names, B):
    """Fill presets grouped by how many blocks they cover."""
    out = {}
    for n in _block_names(kit, names):
        ds = kit.ds1(n)
        w, h = max(1, (ds.width - 1) // B), max(1, (ds.height - 1) // B)
        out.setdefault((w, h), []).append(n)
    return [(lst, w, h) for (w, h), lst in sorted(out.items(), key=lambda kv: -kv[0][0] * kv[0][1])]


def _open_spec(kit, cv, theme, fill):
    """(spec for drlg.block_area, block size, lvltype) of an open-world theme; sets the canvas' ground."""
    from . import act1, act2, act3, act4, act5
    f = max(0.0, min(1.0, fill / 100.0))
    if theme == "wild":
        lt = "Act 1 - Wilderness"
        ds, codes = kit.grass()
        cv.set_ground("grass", "Act1/Outdoors/Bord1.ds1", lt, codes)
        E, C = act1.OutdoorKit.EDGE, act1.OutdoorKit.CORNER
        var = lambda b: _block_names(kit, ["Act1/Outdoors/%s%s.ds1" % (b, v) for v in ("", "b", "c")])
        border = {s: var(E[s]) for s in E}
        border.update({k: var(v) for k, v in C.items()})
        fills = _fills_by_size(kit, act1.OutdoorKit.FILLS["big"] + act1.OutdoorKit.FILLS["common"] +
                               act1.OutdoorKit.FILLS["swamp"], 8)
        return dict(lvltype=lt, ground="grass", border=border, fills=fills, fill_chance=f), 8, lt
    if theme == "desert":
        lt = act2.DESERT
        ds, codes = act2.sand_codes(kit)
        cv.set_ground("sand", act2.A2 + "outdoors\\desert1.ds1", lt, codes)
        border = {s: [act2.A2 + "outdoors\\%s.ds1" % n] for s, n in act2.EDGE.items()}
        border.update({k: [act2.A2 + "outdoors\\%s.ds1" % n] for k, n in act2.CORNER.items()})
        names = [act2.A2 + n for k in ("oasisbig", "ruinsbig", "oasis", "ruins", "common") for n in act2.FILLS[k]]
        return dict(lvltype=lt, ground="sand", border=border, fills=_fills_by_size(kit, names, 8), fill_chance=f), 8, lt
    if theme in ("slums", "burbs", "metro"):
        lid = {"slums": 79, "burbs": 80, "metro": 81}[theme]
        spec = act3._kurast_spec(lid)
        cv.set_ground(theme, act3.K + "%s08x08_0.ds1" % theme, act3.KURAST_LT)
        # (no gates, sewers or waypoint blocks: they lead nowhere here; the temples stay)
        spec = dict(spec, specials=[s for s in spec["specials"] if s[3] is None and "waypoint" not in s[0][0]
                                    and "sewer" not in s[0][0]], fill_chance=f)
        return spec, 8, act3.KURAST_LT
    if theme in ("steppes", "plains", "damned"):
        lid = {"steppes": 104, "plains": 105, "damned": 106}[theme]
        cv.set_ground("mesa", act4.M + "outer08x08_0.ds1", act4.MESA_LT)
        spec = act4._mesa_spec(lid, {})
        spec = dict(spec, specials=[], fill_chance=f)
        return spec, act4.B, act4.MESA_LT
    if theme in ("highlands", "plateau"):
        snow = theme == "plateau"
        act5._KIT[:] = [kit]
        cv.set_ground("dirt", act5.S + "newbarrAA1.ds1", act5.BAR_LT)
        cv.set_ground("snow", act5.S + "snowbarrAA1.ds1", act5.BAR_LT)
        spec = act5._barricade_spec(111 if not snow else 112, snow, [])
        spec = dict(spec, fill_chance=f)
        return spec, act5.B, act5.BAR_LT
    raise ValueError(theme)


def _build_jungle(kit, cv, cols, rows, loops, rng, fill):
    """The jungle: D2's river pieces (32 x 32 tiles) joined as a tree, clearings among them."""
    from . import act3
    from .drlg import tree_layout, pick_existing
    lay = tree_layout(cols, rows, rng, extra=loops)
    for (cx, cy), ex in lay.items():
        combo = _canon(ex)
        name = None
        if combo in act3.CLEAR_COMBOS and rng.random() * 100 < fill:
            name = pick_existing(kit, [act3.J + "%s%s%s.ds1" % (p, combo, v) for p in ("clear", "cave")
                                       for v in ("", "1", "2", "3")], rng)
        name = name or act3._riv(kit, combo, rng)
        if name:
            cv.put(name, cx * act3.P, cy * act3.P, 0, act3.JUNGLE_LT)
    return act3.JUNGLE_LT


def _generate_open(kit, content, objdata, o, log=None):
    """An open world: one outdoor area of width x height blocks, ringed by the theme's borders."""
    from . import custommap
    from .drlg import block_area
    _load_acts()
    seed = o["seed"] if o["seed"] is not None else random.randrange(1 << 30)
    rng = random.Random(seed)
    theme = o.get("open_theme", "wild")
    act = OPEN_ACT.get(theme, 1)
    bw, bh = max(4, int(o["width"])), max(4, int(o["height"]))
    best = None
    for attempt in range(8):
        aseed = rng.randrange(1 << 30)
        if theme == "jungle":
            from . import act3
            cols, rows = max(2, bw // 4), max(2, bh // 4)
            cv = _RecCanvas(kit, cols * act3.P, rows * act3.P, act, aseed)
            lt = _build_jungle(kit, cv, cols, rows, int(o.get("loops", 1)), random.Random(aseed), int(o.get("fill", 60)))
            tw, th, B = cols * act3.P, rows * act3.P, act3.P // 4
        else:
            probe = _RecCanvas(kit, 8, 8, act, aseed)
            spec, B, lt = _open_spec(kit, probe, theme, int(o.get("fill", 60)))
            if B > 8:                            # (width and height count 8-tile blocks)
                bw, bh = max(4, bw * 8 // B), max(4, bh * 8 // B)
            tw, th = bw * B, bh * B
            cv = _RecCanvas(kit, tw, th, act, aseed)
            spec, B, lt = _open_spec(kit, cv, theme, int(o.get("fill", 60)))
            block_area(cv, 0, 0, 0, bw, bh, B, spec)
            if theme in ("highlands", "plateau"):
                from . import act5
                act5._sprinkle(cv, 0, 0, 0, bw, bh, "snow" if theme == "plateau" else "dirt")
        b = cv.b
        tm = b.tm
        # the plain ground the presets left showing: one compact list (preset it comes from + codes)
        ground = {}
        for pos, (ref, src, main, sub) in cv.ground_refs.items():
            if tm.floor.get(pos) is ref:
                ground.setdefault(src, []).append([pos[0], pos[1], main, sub])
        data = {"version": 1, "name": o["name"], "act": act, "lvltype": lt, "width": tw, "height": th,
                "level": 0, "random_monsters": False, "random_objects": False, "keep_edges": True,
                "ground": [[src, cells] for src, cells in ground.items()], "rooms": cv.puts, "tiles": [],
                "objects": [], "monsters": [], "decor": [], "markers": [], "start": None, "exits": [],
                "room_objects": bool(o.get("room_objects", True)),
                "monster_level": int(o["monster_level"] or 0) or theme_level(kit, theme, OPEN_LEVELS),
                "generated": dict(o, seed=seed)}
        b2, grid, _r = custommap.compose(kit, data, 0, seed)
        # (the ring of border pieces is scenery: cliffs, forest, walls - the map is what lies inside it)
        m = B * SUB if theme != "jungle" else 0
        inside = lambda c: m <= c[0] < grid.w - m - SUB and m <= c[1] < grid.h - m - SUB
        walk = [(x, y) for y in range(grid.h) for x in range(grid.w) if grid.walkable(x, y) and inside((x, y))]
        if not walk:
            continue
        cx, cy = grid.w // 2, grid.h // 2
        start = _near_walkable(grid, (cx, cy), 60)
        seen = {c for c in _flood(grid, start) if inside(c)} if start else set()
        frac = len(seen) / float(len(walk))
        if best is None or frac > best[0]:
            best = (frac, data, grid, start, seen, b2, B)
        if frac >= 0.9:
            break
        if log:
            log("open world %d: %d%% of the ground reachable - building again" % (attempt, int(frac * 100)))
    frac, data, grid, start, seen, b, B = best
    # the pockets nobody can walk into (behind cliffs, inside walls) get nothing
    cell_b = B * SUB
    cells_of = {}
    for c in seen:
        cells_of.setdefault((c[0] // cell_b, c[1] // cell_b), []).append(c)
    start_room = (start[0] // cell_b, start[1] // cell_b)
    order = sorted(cells_of, key=lambda c: abs(c[0] - start_room[0]) + abs(c[1] - start_room[1]))
    order = [c for c in order if len(cells_of[c]) >= 30] or order
    far = order[-1]
    data["start"] = list(start)
    data["reachable"] = int(frac * 100)
    _fill(data, o, rng, grid, start, start_room, cells_of, order, far, set(), kit, content, objdata, theme, act)
    data["boss_room"] = list(far)
    data["room_size"] = [B, B]
    return data
