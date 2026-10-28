"""Act 2 built from Diablo 2's own presets.

* One seamless outdoor world: Lut Gholein (LutW / LutN + its desert transition), Rocky Waste,
  Dry Hills, Far Oasis, Lost City and the Valley of Snakes. Each desert area is a 10x10 grid of
  8x8-tile blocks (80x80 tiles, Levels.txt) with D2's desert border presets (edge1-12) around it,
  open passages where two areas meet, entrances (TombEnt, maggot holes, the ruined sewer, the
  viper temple), the Dark Elder's ruin and D2's desert fill presets (berms, mesas, bones,
  wagons, oases, ruins).
* The Canyon of the Magi is its own outdoor world with the seven Tal Rasha tomb entrances
  (TalCor / TalLeft1-3 / TalRght1-3, whose warp numbers are Levels.txt vis1-7 = tombs 66-72).
* Dungeons are grown from their room presets like Act 1's: sewers, tombs, the maggot lair, the
  Arcane Sanctuary; the Harem and Palace Cellars are rings of their four corner rooms; the
  Harem entrance and Duriel's Lair are fixed presets.

Warp tiles work like Act 1 (main index = vis slot). Waypoints come from obj.txt when it is
available, otherwise they are placed here.
"""
import random

from . import act1
from .act1 import Built, stamp, make_grid, SUB, DIRS, OPP, MazeKit, build_maze, _canon
from .acts import apply_act_tables

BLOCK = 8
SLOT = 10                         # blocks per desert area (80 tiles, Levels.txt sizex/sizey)
ST = SLOT * BLOCK
A2 = "act2\\"
DESERT = "Act 2 - Desert"

EDGE = {"n": "edge3", "s": "edge1", "w": "edge2", "e": "edge4"}       # open towards the inside
CORNER = {("s", "w"): "edge9", ("n", "w"): "edge10", ("n", "e"): "edge11", ("s", "e"): "edge12"}
FILLS = {
    "common": ["outdoors\\desert%d.ds1" % i for i in range(1, 11)] +
              ["outdoors\\burm%d.ds1" % i for i in range(1, 8)] +
              ["outdoors\\head1.ds1", "outdoors\\head2.ds1", "outdoors\\bone1.ds1", "outdoors\\bone2.ds1",
               "outdoors\\wagon2.ds1", "outdoors\\mesarm.ds1"],
    "oasis": ["outdoors\\oasis%d.ds1" % i for i in (1, 2, 3, 4)],
    "oasisbig": ["outdoors\\oasis%d.ds1" % i for i in (5, 6, 7, 8, 9, 10, 11, 12)],
    "ruins": ["outdoors\\ruin4.ds1", "outdoors\\ruin5.ds1", "outdoors\\ruin6.ds1"] +
             ["ruin\\ruin%d.ds1" % i for i in range(1, 11)],
    "ruinsbig": ["outdoors\\ruin1.ds1"],
}
SPECIALS = {
    41: [("outdoors\\tombent%d.ds1", (1, 2, 3, 4), 1)],               # Stony Tomb
    42: [("outdoors\\tombent%d.ds1", (1, 2, 3, 4), 1)],               # Halls of the Dead
    43: [("maggot\\%s.ds1", ("hole1", "tight"), 1)],                  # Maggot Lair
    44: [("outdoors\\ruinsewr.ds1", None, 1), ("outdoors\\ruindarkelder.ds1", None, 2)],
    45: [("outdoors\\viper1.ds1", None, 2)],                          # Claw Viper Temple
}
WAYPOINT_AREAS = (40, 42, 43, 44)
WAYPOINT_TOKEN = {40: "WM", 42: "WM", 43: "WM", 44: "WM", 46: "WM", 48: "QM", 52: "W7", 57: "WP", 74: "WP"}

# ---------------------------------------------------------------- dungeons
MAZES = {
    "sewer": dict(folder="act2\\sewer\\", prefix="sew", lvltype="Act 2 - Sewer",
                  roles={"prev": "sew{d}up", "dock": "sew{x}dock{n}", "next": "sew{d}down", "way": "sew{d}waypoint",
                         "rad": "sew{d}rad", "chest": "sew{d}con"}),
    "tomb": dict(folder="act2\\tomb\\", prefix="tomb", lvltype="Act 2 - Tomb",
                 roles={"prev": "tomb{x}warpprev{n}", "next": "tomb{d}warpnext{n}", "treasure": "tomb{d}treasure",
                        "cube": "tombcube{d}", "talrasha": "tomb{d}talrasha", "way": "tomb{d}waypoint",
                        "kaa": "tomb{d}kaa", "leather": "tomb{d}leatherarm", "chest": "tomb{d}consol",
                        "serpent": "serpent1"}),
    "lair": dict(folder="act2\\maggot\\", prefix="mag", lvltype="Act 2 - Lair",
                 roles={"prev": "mag{d}warpprev", "next": "mag{d}warpnext", "queen": "magqueen"},
                 role_exits={"queen": "s"}),
    "arcane": dict(folder="act2\\arcane\\", prefix="sanct", lvltype="Act 2 - Arcane",
                   roles={"summoner": "summ{d}"}),
}
act1.MAZES.update(MAZES)

DUNGEONS = {
    47: dict(kit="sewer", rooms=10, roles=["prev", "next"], act=2),
    48: dict(kit="sewer", rooms=11, roles=["prev", "next", "way"], act=2),
    49: dict(kit="sewer", rooms=10, roles=["prev", "rad"], act=2),
    50: dict(kit="preset", folder=A2, files=["palace\\harem2.ds1"], lvltype="Act 2 - Harem", act=2),
    51: dict(kit="ring", prefix="palace\\sub", lvltype="Act 2 - Harem", act=2),
    52: dict(kit="ring", prefix="palace\\cel", lvltype="Act 2 - Basement", act=2, waypoint=True),
    53: dict(kit="ring", prefix="palace\\cel", lvltype="Act 2 - Basement", act=2),
    54: dict(kit="ring", prefix="palace\\cel", lvltype="Act 2 - Basement", act=2, arcane=True),
    55: dict(kit="tomb", rooms=10, roles=["prev", "next"], act=2),
    59: dict(kit="tomb", rooms=10, roles=["prev", "chest"], act=2),
    56: dict(kit="tomb", rooms=10, roles=["prev", "next"], act=2),
    57: dict(kit="tomb", rooms=11, roles=["prev", "next", "way"], act=2),
    60: dict(kit="tomb", rooms=10, roles=["prev", "cube"], act=2),
    58: dict(kit="tomb", rooms=10, roles=["prev", "next"], act=2),
    61: dict(kit="tomb", rooms=10, roles=["prev", "serpent"], act=2),
    62: dict(kit="lair", rooms=10, roles=["prev", "next"], act=2),
    63: dict(kit="lair", rooms=10, roles=["prev", "next"], act=2),
    64: dict(kit="lair", rooms=10, roles=["prev", "queen"], act=2),
    65: dict(kit="sewer", rooms=11, roles=["prev", "chest"], act=2),
    73: dict(kit="preset", folder=A2, files=["tomb\\duriel.ds1"], lvltype="Act 2 - Tomb", act=2),
    74: dict(kit="arcane", rooms=16, roles=["summoner"], act=2, waypoint_centre=True),
}
for _lid in range(66, 73):
    DUNGEONS[_lid] = dict(kit="tomb", rooms=11, roles=["prev", "chest"], act=2, tal=True)

WORLD_OF = {i: "desert" for i in (40, 41, 42, 43, 44, 45)}
WORLD_OF[46] = 46
WORLD_OF.update({i: i for i in DUNGEONS})


# MazeKit.role_room with an exit restriction (the queen's room only exists facing south)
_orig_role_room = MazeKit.role_room


def _role_room(self, role, exits, rng):
    need = self.spec.get("role_exits", {}).get(role)
    if need is not None and _canon(exits) != need:
        return None
    return _orig_role_room(self, role, exits, rng)


MazeKit.role_room = _role_room


CURRENT_REAL = None        # set when a hero enters the game (background builders use it too)


def real_tomb(seed_text):
    """Which of the seven tombs is Tal Rasha's (fixed per hero, like D2 fixes it per game)."""
    h = 0
    for ch in str(seed_text or ""):
        h = (h * 131 + ord(ch)) & 0xFFFFFF
    return 66 + h % 7


def build_level(kit, level_id, seed=None, real=None):
    spec = dict(DUNGEONS[level_id])
    if spec.get("tal"):
        spec["roles"] = ["prev", "talrasha"] if level_id == (real or 66) else ["prev", "treasure"]
    if spec["kit"] == "ring":
        return build_ring(kit, level_id, spec, seed)
    if spec["kit"] in act1.MAZES:
        b, grid, rng = build_maze(kit, level_id, spec, seed)
    else:
        b, grid, rng = act1.build_preset(kit, level_id, spec, seed)
    _ensure_waypoint(b, grid, level_id, spec)
    rooms = getattr(b, "role_rooms", {})
    whole = (0, 0, b.tm.tw, b.tm.th)

    def portal_in(rect, target, kind="portal"):
        x, y, w, h = rect
        c = _near_walkable(grid, ((x + w // 2) * SUB, (y + h // 2) * SUB), 50)
        if c is not None:
            b.objects.append((kind, c, level_id, target))
    # the quest objects (D2's own when the room preset has them, else placed in their room)
    for role, kind in QUEST_ROLES.get(level_id, []):
        _ensure_object(b, grid, kind, rooms.get(role), level_id)
    if "talrasha" in rooms:
        _ensure_object(b, grid, "orifice", rooms["talrasha"], level_id)
    if level_id == 74:
        if not any(k == "arcane_portal" for k, _, _, _ in b.objects):
            portal_in(whole, 54, "arcane_portal")             # back to the Palace Cellar
        for i, (k, c, o, t) in enumerate(b.objects):
            if k == "arcane_portal":
                b.objects[i] = (k, c, o, 54)
        _ensure_object(b, grid, "journal", rooms.get("summoner"), level_id)
    elif level_id == 73:
        portal_in(whole, real or 66)
    return b, grid, rng


# role room -> quest object that belongs in it
QUEST_ROLES = {49: [("rad", "scroll_chest")], 60: [("cube", "cube_chest")], 61: [("serpent", "viper_altar")],
               64: [("queen", "staff_chest")]}


def _ensure_object(b, grid, kind, rect, level_id):
    if rect is None or any(k == kind for k, _, _, _ in b.objects):
        return
    x, y, w, h = rect
    c = _near_walkable(grid, ((x + w // 2) * SUB, (y + h // 2) * SUB), 40)
    if c is not None:
        b.objects.append((kind, c, level_id, -1))


def _ensure_waypoint(b, grid, level_id, spec):
    """Without obj.txt the DS1 waypoint objects can't be recognised: place one in the waypoint room."""
    from .acts import WAYPOINTS
    if level_id not in WAYPOINTS[2] or any(k == "waypoint" for k, _, _, _ in b.objects):
        return
    rect = getattr(b, "role_rooms", {}).get("way")
    if rect is None:
        if not spec.get("waypoint_centre"):
            return
        rect = (0, 0, b.tm.tw, b.tm.th)
    x, y, w, h = rect
    c = ((x + w // 2) * SUB, (y + h // 2) * SUB)
    c = _near_walkable(grid, c, 40)
    if c is not None:
        b.objects.append(("waypoint", c, level_id, -1))


def _near_walkable(grid, c, radius):
    if grid.walkable(*c):
        return c
    for r in range(1, radius + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) == r and grid.walkable(c[0] + dx, c[1] + dy):
                    return (c[0] + dx, c[1] + dy)
    return None


def build_ring(kit, level_id, spec, seed=None):
    """Harem 2 and the Palace Cellars: D2 builds them from four corner rooms in a ring."""
    rng = random.Random(seed)
    layout = {(0, 0): "se", (1, 0): "sw", (0, 1): "ne", (1, 1): "nw"}
    sample = kit.ds1(A2 + spec["prefix"] + "ne.ds1")
    if sample is None:
        raise FileNotFoundError(spec["prefix"] + "ne.ds1")
    rw, rh = sample.width - 1, sample.height - 1
    b = Built(2 * rw + 1, 2 * rh + 1)
    apply_act_tables(b, 2, kit)
    way = rng.choice(list(layout)) if spec.get("waypoint") else None
    for (rx, ry), combo in layout.items():
        names = [spec["prefix"] + combo + n + ".ds1" for n in ("", "2")]
        if (rx, ry) == way:
            names = [spec["prefix"] + combo + "waypoint.ds1"] or names
        cands = [kit.ds1(A2 + n) for n in names]
        cands = [d for d in cands if d is not None] or [sample]
        ds = rng.choice(cands)
        stamp(b, ds, kit.tiles_for(ds, spec["lvltype"]), rx * rw, ry * rh, rng, level_id)
        if (rx, ry) == way:
            b.role_rooms = {"way": (rx * rw, ry * rh, rw, rh)}
    b.areas[level_id] = (0, 0, b.tm.tw * SUB, b.tm.th * SUB)
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    if spec.get("waypoint"):
        _ensure_waypoint(b, grid, level_id, dict(spec, waypoint_centre=False))
    if spec.get("arcane") and not any(k == "arcane_portal" for k, _, _, _ in b.objects):
        # the portal to the Arcane Sanctuary waits in the last cellar
        c = _near_walkable(grid, (rw * SUB, rh * SUB), 40)
        if c is not None:
            b.objects.append(("arcane_portal", c, level_id, 74))
    for i, (k, c, o, t) in enumerate(b.objects):
        if k == "arcane_portal":
            b.objects[i] = (k, c, o, 74)
    return b, grid, rng


# ---------------------------------------------------------------- the desert
def _plan(exit_dir, rng):
    """Lut Gholein, then four desert areas in a bending line, the Valley of Snakes off the Lost City."""
    d = DIRS[exit_dir]
    perp = [(d[1], d[0]), (-d[1], -d[0])]
    rng.shuffle(perp)
    add = lambda a, b: (a[0] + b[0], a[1] + b[1])
    for turn in perp:
        pos = {40: (0, 0)}
        pos[41] = add(pos[40], d)
        pos[42] = add(pos[41], d)
        pos[43] = add(pos[42], turn)
        pos[44] = add(pos[43], turn)
        for step in (d, turn, (-d[0], -d[1])):
            c = add(pos[44], step)
            if c not in pos.values():
                pos[45] = c
                break
        if len(set(pos.values())) == len(pos):
            return pos
    return pos


def sand_codes(kit):
    """Plain sand (floor main/sub codes) taken from a desert fill preset."""
    ds = kit.ds1(A2 + "outdoors\\desert1.ds1")
    codes = []
    if ds is not None:
        for y in range(ds.height):
            for x in range(ds.width):
                c = ds.floors[0][y * ds.width + x]
                if not c.empty:
                    codes.append((c.main, c.sub))
    return ds, codes or [(0, 0)]


def build_desert(kit, seed=None, content=None):
    rng = random.Random(seed)
    towns = [(n, kit.ds1(A2 + "town\\%s.ds1" % n)) for n in ("lutw", "lutn")]
    towns = [(n, t) for n, t in towns if t is not None]
    if not towns:
        raise FileNotFoundError("Lut Gholein layouts (act2\\town\\lutw.ds1) not found")
    tname, town = rng.choice(towns)
    exit_dir = "w" if tname == "lutw" else "n"
    pos = _plan(exit_dir, rng)
    mnx = min(p[0] for p in pos.values())
    mny = min(p[1] for p in pos.values())
    pos = {k: (v[0] - mnx, v[1] - mny) for k, v in pos.items()}
    cols, rows = max(p[0] for p in pos.values()) + 1, max(p[1] for p in pos.values()) + 1
    b = Built(cols * ST + 1, rows * ST + 1)
    apply_act_tables(b, 2, kit)
    b.slot_tiles = ST
    for lid, (sx, sy) in pos.items():
        b.areas[lid] = (sx * ST * SUB, sy * ST * SUB, (sx + 1) * ST * SUB, (sy + 1) * ST * SUB)
    sds, scodes = sand_codes(kit)
    stiles = kit.tiles_for(sds, DESERT) if sds is not None else None
    links = [(40, 41), (41, 42), (42, 43), (43, 44), (44, 45)]
    nbr = {}
    for a, c in links:
        da = (pos[c][0] - pos[a][0], pos[c][1] - pos[a][1])
        dn = next(k for k, v in DIRS.items() if v == da)
        nbr.setdefault(a, {})[dn] = c
        nbr.setdefault(c, {})[OPP[dn]] = a
    openings = {}
    for a, c in links:
        if 45 in (a, c):
            idx = rng.randrange(4, 6)
        elif 40 in (a, c):
            idx = SLOT // 2
        else:
            idx = rng.randrange(2, SLOT - 2)
        openings[(a, c)] = openings[(c, a)] = idx

    def sand(tx0, ty0, w=BLOCK, h=BLOCK):
        if stiles is None:
            return
        for y in range(h):
            for x in range(w):
                main, sub = rng.choice(scodes)
                t = stiles.pick(0, main, sub, rng.randrange(1 << 16))
                if t:
                    b.tm.floor[(tx0 + x, ty0 + y)] = t

    def put(name, tx0, ty0, owner, lt=DESERT):
        ds = kit.ds1(A2 + name)
        if ds is None:
            return None
        stamp(b, ds, kit.tiles_for(ds, lt), tx0, ty0, rng, owner)
        return ds

    # ---- Lut Gholein + its desert transition, flush against the side that leads into the desert
    sx, sy = pos[40]
    tx0, ty0 = sx * ST, sy * ST
    tw, th = town.width - 1, town.height - 1
    trans = kit.ds1(A2 + ("town\\transw2.ds1" if exit_dir == "w" else "town\\transn1.ds1"))
    trw = (trans.width - 1) if trans is not None else 0
    trh = (trans.height - 1) if trans is not None else 0
    toward = DIRS[exit_dir]
    if exit_dir == "w":
        # the desert lies to the west of the town: transition on the slot's west edge, town east of it
        town_x, town_y = tx0 + trw, ty0 + (ST - th) // 2
        tr_x, tr_y = tx0, town_y
    else:
        town_x, town_y = tx0 + (ST - tw) // 2, ty0 + trh
        tr_x, tr_y = town_x, ty0
    # the town slot was planned with the desert in direction `toward`; flip it if the town slot lies
    # on the other side (positions are normalised), so the transition always faces area 41
    if (pos[41][0] - pos[40][0], pos[41][1] - pos[40][1]) != toward:
        raise RuntimeError("desert plan mismatch")
    stamp(b, town, kit.tiles_for(town, "Act 2 - Town"), town_x, town_y, rng, 40)
    if trans is not None:
        stamp(b, trans, kit.tiles_for(trans, "Act 2 - Town"), tr_x, tr_y, rng, 40)
    b.town_rect = (town_x * SUB, town_y * SUB, (town_x + tw) * SUB, (town_y + th) * SUB)
    # the town's area is the town itself (so the desert starts right at the transition)
    b.areas[40] = (min(town_x, tr_x) * SUB, min(town_y, tr_y) * SUB, (town_x + tw) * SUB, (town_y + th) * SUB)

    # ---- the desert areas
    for lid in (41, 42, 43, 44, 45):
        sx, sy = pos[lid]
        size = 4 if lid == 45 else SLOT
        # the small Valley of Snakes sits against the Lost City side of its slot
        off = [0, 0]
        if lid == 45:
            back = nbr[45]
            side = next(iter(back))           # direction from the valley towards the Lost City
            off = {"w": [0, (SLOT - size) // 2], "e": [SLOT - size, (SLOT - size) // 2],
                   "n": [(SLOT - size) // 2, 0], "s": [(SLOT - size) // 2, SLOT - size]}[side]
        bx0, by0 = sx * ST + off[0] * BLOCK, sy * ST + off[1] * BLOCK
        b.areas[lid] = (bx0 * SUB, by0 * SUB, (bx0 + size * BLOCK) * SUB, (by0 + size * BLOCK) * SUB)
        nb = nbr.get(lid, {})
        taken = set()
        for bx in range(size):
            for by in range(size):
                en, es, ew, ee = by == 0, by == size - 1, bx == 0, bx == size - 1
                if not (en or es or ew or ee):
                    continue
                taken.add((bx, by))
                X, Y = bx0 + bx * BLOCK, by0 + by * BLOCK
                vert = "n" if en else ("s" if es else None)
                hor = "w" if ew else ("e" if ee else None)
                if vert and hor:
                    put("outdoors\\%s.ds1" % CORNER[(vert, hor)], X, Y, lid)
                    continue
                side = vert or hor
                # position along the edge counted in whole-slot blocks (the valley is offset in its slot)
                along = (bx + off[0]) if vert else (by + off[1])
                other = nb.get(side)
                if other is not None:
                    idx = openings[(lid, other)]
                    wide = 3 if other == 40 else 1
                    if abs(along - idx) <= wide:
                        sand(X, Y)              # open passage into the neighbouring area
                        continue
                put("outdoors\\%s.ds1" % EDGE[side], X, Y, lid)
        inner = [(bx, by) for bx in range(1, size - 1) for by in range(1, size - 1)]
        rng.shuffle(inner)

        def place(name, w=1, h=1, owner=lid):
            for bx, by in inner:
                cells = [(bx + i, by + j) for i in range(w) for j in range(h)]
                if all(1 <= c[0] < size - 1 and 1 <= c[1] < size - 1 and c not in taken for c in cells):
                    if put(name, bx0 + bx * BLOCK, by0 + by * BLOCK, owner) is None:
                        return None
                    taken.update(cells)
                    return (bx, by)
            return None
        for pattern, choices, blocks in SPECIALS.get(lid, []):
            name = pattern % rng.choice(choices) if choices else pattern
            place(name, blocks, blocks)
        if lid in WAYPOINT_AREAS:
            spot = next(((bx, by) for bx, by in inner if (bx, by) not in taken), None)
            if spot is not None:
                taken.add(spot)
                sand(bx0 + spot[0] * BLOCK, by0 + spot[1] * BLOCK)
                cell = ((bx0 + spot[0] * BLOCK + 4) * SUB, (by0 + spot[1] * BLOCK + 4) * SUB)
                b.objects.append(("waypoint", cell, lid, -1))
        if lid == 43:
            for _ in range(2):
                place(rng.choice(FILLS["oasisbig"]), 2, 2)
            fills = FILLS["oasis"] + FILLS["common"]
        elif lid == 44:
            place(rng.choice(FILLS["ruinsbig"]), 2, 2)
            fills = FILLS["ruins"] * 2 + FILLS["common"]
        else:
            fills = FILLS["common"]
        for bx, by in list(inner):
            if (bx, by) not in taken and rng.random() < 0.3:
                place(rng.choice(fills))
        for bx, by in inner:
            if (bx, by) not in taken:
                sand(bx0 + bx * BLOCK, by0 + by * BLOCK)
                taken.add((bx, by))
    # Lut Gholein's waypoint (obj.txt would also find the DS1's own)
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    if not any(k == "waypoint" and o == 40 for k, _, o, _ in b.objects):
        x0, y0, x1, y1 = b.town_rect
        c = _near_walkable(grid, ((x0 + x1) // 2, (y0 + y1) // 2 + 10), 60)
        if c is not None:
            b.objects.append(("waypoint", c, 40, -1))
    act1._connect(b, grid, pos, links, _SandKit(kit, sds, scodes), rng, openings)
    return b, grid, rng


class _SandKit:
    """act1._connect carves with 'grass' - in the desert that is sand."""

    def __init__(self, kit, sds, scodes):
        self.kit, self._g = kit, (sds, scodes)

    def grass(self):
        return self._g

    def tiles_for(self, ds, extra_type=None):
        return self.kit.tiles_for(ds, DESERT)


# ---------------------------------------------------------------- Canyon of the Magi
def build_canyon(kit, seed=None, content=None):
    rng = random.Random(seed)
    size = SLOT
    b = Built(ST + 1, ST + 1)
    apply_act_tables(b, 2, kit)
    b.areas[46] = (0, 0, ST * SUB, ST * SUB)
    sds, scodes = sand_codes(kit)
    stiles = kit.tiles_for(sds, DESERT) if sds is not None else None

    def sand(tx0, ty0, w=BLOCK, h=BLOCK):
        if stiles is None:
            return
        for y in range(h):
            for x in range(w):
                main, sub = rng.choice(scodes)
                t = stiles.pick(0, main, sub, rng.randrange(1 << 16))
                if t:
                    b.tm.floor[(tx0 + x, ty0 + y)] = t

    def put(name, tx0, ty0):
        ds = kit.ds1(A2 + name)
        if ds is None:
            return None
        stamp(b, ds, kit.tiles_for(ds, DESERT), tx0, ty0, rng, 46)
        return ds
    taken = set()
    for bx in range(size):
        for by in range(size):
            en, es, ew, ee = by == 0, by == size - 1, bx == 0, bx == size - 1
            if not (en or es or ew or ee):
                continue
            taken.add((bx, by))
            vert = "n" if en else ("s" if es else None)
            hor = "w" if ew else ("e" if ee else None)
            name = CORNER[(vert, hor)] if vert and hor else EDGE[vert or hor]
            put("outdoors\\%s.ds1" % name, bx * BLOCK, by * BLOCK)
    inner = [(bx, by) for bx in range(1, size - 1) for by in range(1, size - 1)]
    rng.shuffle(inner)

    def place(name, w, h):
        for bx, by in inner:
            cells = [(bx + i, by + j) for i in range(w) for j in range(h)]
            if all(1 <= c[0] < size - 1 and 1 <= c[1] < size - 1 and c not in taken for c in cells):
                # keep a free ring around each tomb so every entrance can be reached
                ring = [(bx + i, by + j) for i in range(-1, w + 1) for j in range(-1, h + 1)]
                if any(c in taken and 1 <= c[0] < size - 1 and 1 <= c[1] < size - 1 for c in ring):
                    continue
                if put(name, bx * BLOCK, by * BLOCK) is None:
                    return False
                taken.update(cells)
                return True
        return False
    # the seven tombs: their warp number (1-7) is the tomb they lead to (Levels.txt vis1-7)
    tombs = [("bigcliff\\talcor.ds1", 2, 2)] + [("bigcliff\\talleft%d.ds1" % i, 1, 2) for i in (1, 2, 3)] + \
            [("bigcliff\\talrght%d.ds1" % i, 2, 1) for i in (1, 2, 3)]
    for name, w, h in tombs:
        place(name, w, h)
    spot = next(((bx, by) for bx, by in inner if (bx, by) not in taken), None)
    if spot is not None:
        taken.add(spot)
        sand(spot[0] * BLOCK, spot[1] * BLOCK)
        b.objects.append(("waypoint", ((spot[0] * BLOCK + 4) * SUB, (spot[1] * BLOCK + 4) * SUB), 46, -1))
        b.objects.append(("portal", ((spot[0] * BLOCK + 4) * SUB + 8, (spot[1] * BLOCK + 4) * SUB + 4), 46, 74))
    for bx, by in list(inner):
        if (bx, by) not in taken and rng.random() < 0.25:
            if put(rng.choice(FILLS["common"]), bx * BLOCK, by * BLOCK) is not None:
                taken.add((bx, by))
    for bx, by in inner:
        if (bx, by) not in taken:
            sand(bx * BLOCK, by * BLOCK)
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    return b, grid, rng
