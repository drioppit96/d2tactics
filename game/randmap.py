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

# what can be scattered: option name -> object kinds (game/objects.py OPERATE_KIND)
OBJECT_OPTIONS = [("shrines", ("shrine",)), ("wells", ("well",)), ("chests", ("chest", "casket")),
                  ("breakables", ("barrel", "urn", "xbarrel")), ("bodies", ("corpse",)),
                  ("racks", ("armor_rack", "weapon_rack")), ("bookshelves", ("bookshelf",))]

DEFAULTS = dict(name="random_dungeon", theme="catacombs", rooms=12, loops=2, theme_rooms=20,
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


def theme_monsters(kit, content, theme):
    """The monsters D2 puts in the theme's own levels."""
    out = []
    for lid in THEME_LEVELS.get(theme, ()):
        r = kit.levels.get(lid) or {}
        for i in range(1, 11):
            m = (r.get("mon%d" % i) or "").lower()
            if m and (content is None or m in content.monstats) and m not in out:
                out.append(m)
    return out


def theme_level(kit, theme):
    """The theme's monster level (normal difficulty): its deepest D2 level's."""
    best = 1
    for lid in THEME_LEVELS.get(theme, ()):
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
    """A random dungeon as a custom map (dict). opts: see DEFAULTS."""
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
    mons = [m for m in (o["monsters"] or theme_monsters(kit, content, theme))
            if content is None or m in content.monstats]
    if mons:
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
    data["boss_room"] = list(far)
    data["room_size"] = [k.rw, k.rh]
    return data
