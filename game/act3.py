"""Act 3 built from Diablo 2's own presets.

* World "jungle": Kurast Docks (DockTown3), the jungle's head transition, the Spider Forest,
  the Great Marsh beside it and the Flayer Jungle, each a 2 x 6 grid of D2's 32x32 river pieces
  (Riv<exits> - the river is a random tree through all twelve; the clearings Spid / Bog / Pyg
  carry the cave entrances: Spid = Spider Cave / Cavern, Pyg = Swampy Pit / Flayer Dungeon),
  and the jungle's tail, whose far edge leads on to Lower Kurast.
* World "kurast": Lower Kurast (slums), the Bazaar (burbs) and Upper Kurast (metro) - 10 x 8
  blocks of 8 tiles with D2's border, gate, sewer, temple and filler presets - the Causeway
  bridge and Travincal (its six presets).
* Dungeons: Spider Cave / Cavern (ring of four corner rooms), Swampy Pit / Flayer Dungeon
  (jungle dungeon rooms), the Kurast Sewers, the six temples, the Durance of Hate.
"""
import random

from . import act1, act2, drlg
from .act1 import SUB, build_maze, _canon
from .drlg import Canvas, block_area, tree_layout, pick_existing

A3 = "act3\\"
J = A3 + "jungle\\"
K = A3 + "kurast\\"
JUNGLE_LT = "Act 3 - Jungle"
KURAST_LT = "Act 3 - Kurast"
P = 32                         # jungle piece size (tiles)
CLEAR_COMBOS = {"w", "e", "ew", "s", "sw", "se", "n", "nw", "ne", "ns"}

MAZES = {
    "a3dung": dict(folder=J, prefix="dung", lvltype="Act 3 - Dungeon", variants=("", "2", "3"),
                   roles={"prev": "dexit{d}u{n}", "next": "dexit{d}d{n}"}),
    "a3sewer": dict(folder=A3 + "sewer\\", prefix="sewer", lvltype="Act 3 - Sewer", variants=("", "2"),
                    roles={"up0": "sewer{x}_warp", "up1": "sewer{x}_warp", "up2": "sewer{x}_warp",
                           "up3": "sewer{x}_warp", "next": "sewer{d}drain", "chest": "sewer{d}treas"}),
    "meph": dict(folder=A3 + "travincal\\", prefix="meph", lvltype="Act 3 - Kurast", variants=("", "2"),
                 roles={"prev": "meph{d}warpu", "next": "meph{d}warpd", "way": "meph{d}warp"}),
}
act1.MAZES.update(MAZES)

DUNGEONS = {
    84: dict(kit="ring", folder=A3 + "spider\\", prefix="lair", lvltype="Act 3 - Spider", act=3,
             special={"nw": ["lairnwmage", "lairnw2mage", "lairnw3mage"]}),
    85: dict(kit="ring", folder=A3 + "spider\\", prefix="lair", lvltype="Act 3 - Spider", act=3,
             special={"ne": ["lairnecon", "lairne2con", "lairne3con"]}, quest={"ne": "eye_chest"}),
    86: dict(kit="a3dung", rooms=4, roles=["prev", "next"], act=3),
    87: dict(kit="a3dung", rooms=4, roles=["prev", "next"], act=3),
    88: dict(kit="a3dung", rooms=4, roles=["prev", "next"], act=3),
    89: dict(kit="a3dung", rooms=4, roles=["prev", "next"], act=3),
    90: dict(kit="preset", folder=J, files=["dungrm%da.ds1" % i for i in range(1, 7)], lvltype="Act 3 - Dungeon", act=3),
    91: dict(kit="preset", folder=J, files=["dungrm%db.ds1" % i for i in range(1, 7)], lvltype="Act 3 - Dungeon", act=3),
    92: dict(kit="a3sewer", rooms=32, roles=["up0", "up1", "up2", "up3", "next"], act=3,
             need_warps=({0, 1}, {2, 3})),
    93: dict(kit="preset", folder=A3 + "sewer\\", files=["sewertreasure1.ds1"], lvltype="Act 3 - Sewer", act=3),
    94: dict(kit="preset", folder=A3 + "temple\\", files=["temple0.ds1", "temple1.ds1", "temple2.ds1"], lvltype=KURAST_LT, act=3),
    95: dict(kit="preset", folder=A3 + "temple\\", files=["temple3.ds1", "temple4.ds1"], lvltype=KURAST_LT, act=3),
    96: dict(kit="preset", folder=A3 + "temple\\", files=["temple5.ds1", "temple6.ds1"], lvltype=KURAST_LT, act=3),
    97: dict(kit="preset", folder=A3 + "temple\\", files=["temple7.ds1", "temple8.ds1"], lvltype=KURAST_LT, act=3),
    98: dict(kit="preset", folder=A3 + "temple\\", files=["temple9.ds1", "temple10.ds1"], lvltype=KURAST_LT, act=3),
    99: dict(kit="preset", folder=A3 + "temple\\", files=["temple11.ds1", "temple12.ds1"], lvltype=KURAST_LT, act=3),
    100: dict(kit="meph", rooms=10, roles=["prev", "next"], act=3),
    101: dict(kit="meph", rooms=12, roles=["prev", "next", "way"], act=3),
    102: dict(kit="preset", folder=A3 + "travincal\\", files=["mephcomp.ds1"], lvltype=KURAST_LT, act=3),
}
WORLD_OF = {i: i for i in DUNGEONS}


# ---------------------------------------------------------------- dungeons
def build_level(kit, level_id, seed=None):
    spec = dict(DUNGEONS[level_id])
    if spec["kit"] == "ring":
        return build_ring(kit, level_id, spec, seed)
    if spec["kit"] == "preset":
        b, grid, rng = act1.build_preset(kit, level_id, spec, seed)
    else:
        need = spec.get("need_warps")
        for k in range(12):
            b, grid, rng = build_maze(kit, level_id, spec, None if seed is None else seed + k * 7919)
            mains = {m for _, m, _ in b.warps}
            if not need or all(mains & n for n in need):
                break
    drlg.ensure_waypoints(b, grid, 3, {level_id: getattr(b, "role_rooms", {}).get("way")}
                          if "way" in spec.get("roles", []) else None)
    if 94 <= level_id <= 99:
        # Lam Esen's Tome lies on a lectern in one of the six temples (which one is fixed per hero)
        w, h = b.tm.tw * SUB, b.tm.th * SUB
        c = drlg.near_walkable(grid, (w // 2, h // 2), 60)
        if c:
            b.objects.append(("lamtome", c, level_id, -1))
    return b, grid, rng


def build_ring(kit, level_id, spec, seed=None):
    """Four corner rooms around a middle (the spider caves; D2 builds the Harem the same way)."""
    from .act1 import Built, stamp, make_grid
    from .acts import apply_act_tables
    rng = random.Random(seed)
    layout = {(0, 0): "se", (1, 0): "sw", (0, 1): "ne", (1, 1): "nw"}
    folder, prefix = spec["folder"], spec["prefix"]
    sample = kit.ds1(folder + prefix + "ne.ds1")
    if sample is None:
        raise FileNotFoundError(prefix + "ne.ds1")
    rw, rh = sample.width - 1, sample.height - 1
    b = Built(2 * rw + 1, 2 * rh + 1)
    apply_act_tables(b, spec.get("act", 3), kit)
    for (rx, ry), combo in layout.items():
        names = spec.get("special", {}).get(combo) or [prefix + combo + n for n in ("", "2", "3")]
        cands = [kit.ds1(folder + n + ".ds1") for n in names]
        cands = [d for d in cands if d is not None] or [sample]
        ds = rng.choice(cands)
        stamp(b, ds, kit.tiles_for(ds, spec["lvltype"]), rx * rw, ry * rh, rng, level_id, keep_edges=False)
    b.areas[level_id] = (0, 0, b.tm.tw * SUB, b.tm.th * SUB)
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    for combo, kind in spec.get("quest", {}).items():
        (rx, ry) = next(k for k, v in layout.items() if v == combo)
        c = drlg.near_walkable(grid, ((rx * rw + rw // 2) * SUB, (ry * rh + rh // 2) * SUB), 40)
        if c is not None:
            b.objects.append((kind, c, level_id, -1))
    return b, grid, rng


# ---------------------------------------------------------------- the jungle
def _riv(kit, combo, rng, prefix="riv", variants=("", "2", "3", "4", "5")):
    names = [J + "%s%s%s.ds1" % (prefix, combo, v) for v in variants]
    return pick_existing(kit, names, rng)


def jungle_area(cv, lid, x0, y0, links, clearings):
    """2 x 6 river pieces. links: {"n": col, "s": col} rivers flowing on into the next area.
    clearings: [(prefix, variant)] - D2's clearings (some hold cave entrances)."""
    rng, kit = cv.rng, cv.kit
    lay = tree_layout(2, 6, rng, extra=1)
    if "n" in links:
        lay[(links["n"], 0)].add("n")
    if "s" in links:
        lay[(links["s"], 5)].add("s")
    cells = list(lay)
    rng.shuffle(cells)
    special = {}
    for prefix, variant in clearings:
        for c in cells:
            if c not in special and _canon(lay[c]) in CLEAR_COMBOS:
                special[c] = (prefix, variant)
                break
    for (cx, cy), ex in lay.items():
        combo = _canon(ex)
        name = None
        if (cx, cy) in special:
            prefix, variant = special[(cx, cy)]
            name = pick_existing(kit, [J + "%s%s%s.ds1" % (prefix, combo, variant)], rng)
        name = name or _riv(kit, combo, rng)
        if name:
            cv.put(name, x0 + cx * P, y0 + cy * P, lid, JUNGLE_LT)
    cv.b.areas[lid] = (x0 * SUB, y0 * SUB, (x0 + 2 * P) * SUB, (y0 + 6 * P) * SUB)


def build_jungle(kit, seed=None, content=None):
    """The Kurast Docks alone: this game skips the jungle (Spider Forest, Great Marsh, Flayer Jungle) -
    the docks' north road leads straight into Lower Kurast."""
    dock = kit.ds1(A3 + "docktown\\docktown3.ds1")
    if dock is None:
        raise FileNotFoundError("Kurast Docks layout (act3\\docktown\\docktown3.ds1) not found")
    dw, dh = dock.width - 1, dock.height - 1
    road = 32                                          # D2's jungle head piece: the road out of the docks
    cv = Canvas(kit, dw, dh + road, 3, seed)
    rng, b = cv.rng, cv.b
    cv.set_ground("jungle", J + "rivn.ds1", JUNGLE_LT)
    head = pick_existing(kit, [J + "transl.ds1", J + "transu.ds1"], rng)
    if head:
        cv.put(head, 0, 0, 75, JUNGLE_LT)
    cv.put(A3 + "docktown\\docktown3.ds1", 0, road, 75, "Act 3 - Town")
    b.town_rect = (0, road * SUB, dw * SUB, (road + dh) * SUB)
    b.areas[75] = (0, 0, dw * SUB, (road + dh) * SUB)
    grid = cv.finish()
    drlg.ensure_waypoints(b, grid, 3)
    # the road's far (north) edge: on to Lower Kurast (another world)
    cells = drlg.edge_cells(grid, (0, 0, dw * SUB, (road + dh) * SUB), "n")
    b.edge_exits = [(cells, 79)]
    return b, grid, rng


# ---------------------------------------------------------------- Kurast
KINDS = {79: "slums", 80: "burbs", 81: "metro"}


def _kurast_spec(lid):
    k = KINDS[lid]
    T = k.title()
    border = {"n": [K + "border%sn%d.ds1" % (k, i) for i in (1, 2)], "s": [K + "border%ss%d.ds1" % (k, i) for i in (1, 2, 3)],
              "e": [K + "border%se%d.ds1" % (k, i) for i in (1, 2)], "w": [K + "border%sw%d.ds1" % (k, i) for i in (1, 2)],
              ("n", "e"): [K + "border%sne.ds1" % k], ("n", "w"): [K + "border%snw.ds1" % k],
              ("s", "e"): [K + "border%sse.ds1" % k], ("s", "w"): [K + "border%ssw.ds1" % k]}
    gate_n = (K + "%sgaten.ds1" % k, 2 if k == "metro" else 1, 2 if k == "metro" else 1)
    gate_s = (K + "%sgates.ds1" % k, 2 if k == "slums" else 1, 1)
    specials = [([gate_n[0]], gate_n[1], gate_n[2], (4, 0)), ([gate_s[0]], gate_s[1], gate_s[2], (4, 7))]
    if k != "slums":
        specials += [([K + "%ssewer0.ds1" % k], 1, 1, None), ([K + "%ssewer1.ds1" % k], 1, 1, None),
                     ([K + "%stemple2.ds1" % k], 2, 2, None), ([K + "%stemple3.ds1" % k], 2, 2, None)]
    if k == "burbs":
        specials.append(([K + "burbs08x08_waypoint.ds1"], 1, 1, None))
    fills = [([K + "%s16x16_%d.ds1" % (k, i) for i in range(5)], 2, 2),
             ([K + "%s16x08_%d.ds1" % (k, i) for i in range(5)], 2, 1),
             ([K + "%s08x16_%d.ds1" % (k, i) for i in range(5)], 1, 2),
             ([K + "%s08x08_%d.ds1" % (k, i) for i in range(6)], 1, 1)]
    return dict(lvltype=KURAST_LT, ground=k, border=border, specials=specials, fills=fills, fill_chance=0.8)


# this game's two extra areas (level ids of the skipped jungle, renamed): built like the area they
# join - the Kurast Armory off Lower Kurast's east side, the Kurast Scriptorium off the Bazaar's west
SIDE_AREAS = {76: dict(name="Kurast Armory", like=79, side="e", own_world=True,
                       extra=["fetish5", "fetishshaman5", "arach4"]),
              77: dict(name="Kurast Scriptorium", like=80, side="w", extra=["cantor2", "zealot3", "mummy5"])}
SIDE_W = 5                     # blocks (8 tiles) wide


def _side_spec(lid):
    sa = SIDE_AREAS[lid]
    spec = _kurast_spec(sa["like"])
    spec = dict(spec, specials=[], fill_chance=0.85)
    inner = "w" if sa["side"] == "e" else "e"
    spec["openings"] = {inner: (3, 1)}
    spec["border"] = {k: v for k, v in spec["border"].items() if k != inner and not (isinstance(k, tuple) and inner in k)}
    return spec


def build_kurast(kit, seed=None, content=None):
    SW = SIDE_W * 8
    W, H = 80 + 2 * SW, 64 + 16 + 64 * 3
    X = SW                                 # the main column (Travincal ... Lower Kurast) starts here
    cv = Canvas(kit, W, H, 3, seed)
    rng, b = cv.rng, cv.b
    for lid, k in KINDS.items():
        cv.set_ground(k, K + "%s08x08_0.ds1" % k, KURAST_LT)
    # Travincal (its six presets), the Causeway bridge, then the three city areas going south
    trav = [("travnw", 8, 0), ("travn", 24, 0), ("travne", 56, 0), ("travsw", 8, 32), ("travs", 24, 32), ("travse", 56, 32)]
    for name, x, y in trav:
        cv.put(A3 + "travincal\\%s.ds1" % name, X + x, y, 83, KURAST_LT)
    b.areas[83] = ((X + 8) * SUB, 0, (X + 72) * SUB, 64 * SUB)
    cv.put(K + "bridge.ds1", X + 16, 64, 82, KURAST_LT)
    b.areas[82] = (X * SUB, 64 * SUB, (X + 80) * SUB, 80 * SUB)
    rows = {}
    for i, lid in enumerate((81, 80, 79)):
        y0 = 80 + i * 64
        rows[lid] = y0
        spec = _kurast_spec(lid)
        side = next((s_ for l_, s_ in ((76, "e"), (77, "w")) if SIDE_AREAS[l_]["like"] == lid), None)
        if side:
            spec = dict(spec, openings={side: (3, 1)})
        placed = block_area(cv, lid, X, y0, 10, 8, 8, spec)
        for k, (names, w, h, where) in enumerate(spec["specials"]):
            if "waypoint" in names[0] and k in placed:
                bx, by = placed[k]
                b.objects.append(("waypoint", ((X + bx * 8 + 4) * SUB, (y0 + by * 8 + 4) * SUB), lid, -1))
    # the side areas
    for lid, sa in SIDE_AREAS.items():
        if sa.get("own_world"):
            continue
        y0 = rows[sa["like"]]
        x0 = X + 80 if sa["side"] == "e" else 0
        block_area(cv, lid, x0, y0, SIDE_W, 8, 8, _side_spec(lid))
    grid = cv.finish()
    drlg.ensure_connected(b, grid, [(79, 80), (80, 81), (81, 82), (82, 83), (80, 77)],
                          cv.ground_kit("slums"), rng)
    drlg.ensure_waypoints(b, grid, 3)
    # Lower Kurast's south gate: back to the Kurast Docks (another world)
    cells = drlg.edge_cells(grid, b.areas[79], "s", x_range=((X + 24) * SUB, (X + 56) * SUB))
    b.edge_exits = [(cells, 75)]
    # Lower Kurast's east gate: into the Kurast Armory (its own map)
    x0, y0, x1, y1 = b.areas[79]
    gate = drlg.edge_cells(grid, (x0, y0 + 24 * SUB, x1, y0 + 40 * SUB), "e")
    if gate:
        b.edge_exits.append((gate, 76))
    return b, grid, rng


# this game's named uniques of the two extra areas, who carry quest items
SIDE_BOSSES = [
    # (area, monster, name, boss tag, mods, minions)
    (76, "arach4", "Silkmother Vashra", "silkmother", ("STRONG", "CURSE"), ("arach4", 3)),
    (77, "cantor2", "Scribe Ophizek the Hollow", "scribe", ("MANAHIT", "TELEPORT"), ("zealot3", 4)),
]


def spawn_side_bosses(world, taken, info):
    """The Armory's doll (the Gidbinn) and spider queen (Khalim's Eye), the Scriptorium's scribe
    (Khalim's Brain): one each, deep inside their area."""
    from . import actworld, monmods
    import zlib
    rng = world.rng
    for lid, mid, name, tag, mods, (minion, n) in SIDE_BOSSES:
        rect = world.areas.get(lid)
        if rect is None or world.content is None or mid not in world.content.monstats:
            continue
        if any(getattr(m, "boss", None) == tag for m in world.monsters):
            continue
        x0, y0, x1, y1 = rect
        cell = None
        for _ in range(200):
            c = (rng.randrange(x0 + 30, x1 - 30), rng.randrange(y0 + 30, y1 - 30))
            if world.grid.walkable(*c) and c not in taken and actworld._reachable(world, c):
                cell = c
                break
        if cell is None:
            continue
        lvl = info.monster_level(lid)
        m = actworld._spawn(world, mid, cell, lvl + 3, taken, unique=True, name=name)
        if m is None:
            continue
        m.boss = tag
        monmods.apply(world, m, [getattr(monmods, k) for k in mods])
        m.color_shift = 1 + zlib.crc32(name.encode()) % 7
        for c in actworld._scatter(world, cell, n, taken):
            mm = actworld._spawn(world, minion, c, lvl + 1, taken)
            if mm is not None:
                monmods.pass_aura(m, mm)


# ---------------------------------------------------------------- the Kurast Armory
class _Sub:
    """A rectangle cut out of a DS1 (a Travincal building), stamped like a whole preset."""

    def __init__(self, ds, sx, sy, w, h):
        self.width, self.height = w + 1, h + 1
        self.files = ds.files
        W = ds.width
        pick = lambda layer: [layer[(sy + y) * W + sx + x] if sx + x < ds.width and sy + y < ds.height else None
                              for y in range(self.height) for x in range(self.width)]
        from d2.ds1 import Cell
        empty = Cell(0)
        self.floors = [[c or empty for c in pick(L)] for L in ds.floors]
        self.walls = [[c or empty for c in pick(L)] for L in ds.walls]
        self.objects = [(t, o, x - sx * 5, y - sy * 5) for t, o, x, y in ds.objects
                        if t == 2 and sx * 5 <= x < (sx + w) * 5 and sy * 5 <= y < (sy + h) * 5]


ARMORY = 72                    # blueprint size in tiles (the map is one tile bigger all round)
# the designer's blueprint: crenellated walls between grid points (x0, y0) - (x1, y1)
ARMORY_WALLS = [((0, 0), (28, 0)), ((47, 0), (72, 0)), ((0, 0), (0, 72)), ((72, 0), (72, 72)), ((0, 72), (72, 72)),
                ((28, 0), (28, 14)), ((47, 0), (47, 14)),
                ((0, 20), (28, 20)), ((47, 20), (72, 20)),
                ((12, 29), (30, 29)), ((45, 29), (65, 29)),
                ((12, 29), (12, 55)), ((12, 55), (22, 55)), ((22, 55), (22, 72)),
                ((65, 29), (65, 51)), ((52, 51), (65, 51)), ((52, 51), (52, 72))]
ARMORY_ALTARS = [(5, 5), (66, 5), (6, 67), (66, 67)]
ARMORY_BOSS = (37, 64)
ARMORY_ENTRY = (37, 1)
# Travincal buildings: (preset, source x, y, w, h, where in the blueprint)
ARMORY_BUILDINGS = [("travn", 7, 14, 21, 12, (28, 33)),          # the great hall in the keep
                    ("travs", 10, 2, 12, 9, (31, 58)),           # the council dais: the smith's forge court
                    ("travs", 0, 13, 9, 8, (9, 58)),             # small temples in the bottom rooms
                    ("travs", 21, 15, 10, 8, (55, 58)),
                    ("travn", 15, 26, 8, 6, (10, 6)),            # sunken gardens in the top rooms
                    ("travn", 15, 26, 8, 6, (55, 6)),
                    ]


def _wall_tiles(lines, off, n):
    """Grid-point wall lines -> D2 wall tiles (orientation, main, sub) on each tile, the way D2's own
    Travincal walls are laid: walls run along a tile's north (2) and west (1) edges, with north (3),
    east-end (5), west-end (6) and south (7) corner pieces."""
    pts = {}
    def link(a, b_, d1, d2):
        pts.setdefault(a, set()).add(d1)
        pts.setdefault(b_, set()).add(d2)
    for (x0, y0), (x1, y1) in lines:
        if y0 == y1:
            for x in range(min(x0, x1), max(x0, x1)):
                link((x, y0), (x + 1, y0), "E", "W")
        else:
            for y in range(min(y0, y1), max(y0, y1)):
                link((x0, y), (x0, y + 1), "S", "N")
    out = {}
    for (x, y), ds in pts.items():
        X, Y = x + off, y + off
        if not (0 <= X < n and 0 <= Y < n):
            continue
        t = []
        if "E" in ds and "S" in ds:
            t = [(3, 32, 0)]
        elif "E" in ds and "N" in ds and "W" not in ds:
            t = [(6, 32, 0)]
        elif "E" in ds:
            t = [(2, 32, 4 + x % 4)]
        elif "S" in ds and "W" in ds and "N" not in ds:
            t = [(5, 32, 0)]
        elif "S" in ds:
            t = [(1, 32, y % 4)]
        elif "N" in ds and "W" in ds:
            t = [(7, 32, 0)]
        if t:
            out[(X, Y)] = t
    return out


def build_armory(kit, seed=None, content=None):
    """The Kurast Armory: a walled Travincal-style compound (the designer's blueprint). Four altars
    in its corners; lighting all of them calls out the smith in the forge court."""
    from .act1 import Built, stamp, make_grid
    from .acts import apply_act_tables
    from . import custommap
    rng = random.Random(7919 * 76 + 17)
    n = ARMORY + 2
    off = 1
    b = Built(n, n)
    apply_act_tables(b, 3, kit)
    ts = custommap.tileset(kit, KURAST_LT)
    tm = b.tm
    R = lambda *k: custommap._rnd(*k)
    # Travincal's paving everywhere
    for y in range(off, off + ARMORY):
        for x in range(off, off + ARMORY):
            key = (20, 0)
            ref = ts.pick(0, key[0], key[1], R(x, y))
            if ref:
                tm.floor[(x, y)] = ref
    # the buildings (whole chunks of Travincal)
    for name, sx, sy, w, h, (bx, by) in ARMORY_BUILDINGS:
        ds = kit.ds1(A3 + "travincal\\%s.ds1" % name)
        if ds is None:
            continue
        sub = _Sub(ds, sx, sy, w, h)
        stamp(b, sub, kit.tiles_for(ds, KURAST_LT), bx + off, by + off, random.Random(R(bx, by)), 76, keep_edges=False)
    # the crenellated walls
    for pos, keys in _wall_tiles(ARMORY_WALLS, off, n).items():
        lst = []
        for o, m, s_ in keys:
            for oo in ([o, 4] if o == 3 else [o]):
                ref = ts.pick(oo, m, s_, R(pos[0], pos[1], oo))
                if ref:
                    lst.append(ref)
        if lst:
            tm.walls[pos] = lst
    b.warps = []                   # (the building chunks' own stairs lead nowhere here)
    b.areas[76] = (0, 0, n * SUB, n * SUB)
    tm.drawn = set(tm.floor) | set(tm.walls) | set(tm.floor2)
    grid = make_grid(tm)
    # the crenellated walls block the way all along (their pieces alone leave gaps)
    from .grid import WALL
    for (x0, y0), (x1, y1) in ARMORY_WALLS:
        if y0 == y1:
            Y = (y0 + off) * SUB
            for X in range((min(x0, x1) + off) * SUB, (max(x0, x1) + off) * SUB + 1):
                for yy in (Y - 1, Y):
                    if grid.in_bounds(X, yy):
                        grid.cells[yy][X] = WALL
        else:
            X = (x0 + off) * SUB
            for Y in range((min(y0, y1) + off) * SUB, (max(y0, y1) + off) * SUB + 1):
                for xx in (X - 1, X):
                    if grid.in_bounds(xx, Y):
                        grid.cells[Y][xx] = WALL
    C = lambda t: ((t[0] + off) * SUB + 2, (t[1] + off) * SUB + 2)
    for a in ARMORY_ALTARS:
        c = drlg.near_walkable(grid, C(a), 12)
        if c:
            b.objects.append(("armory_altar", c, 76, -1))
    b.armory_boss = drlg.near_walkable(grid, C(ARMORY_BOSS), 12)
    # braziers along the middle band and the keep's gate
    for t in [(16, 23), (24, 23), (51, 23), (59, 23), (29, 27), (46, 27), (6, 30), (68, 30), (6, 48), (68, 48)]:
        b.gen_objects.append((("id", 102), C(t), 76))
    # the gate in the north wall: back to Lower Kurast
    cells = [((x + off) * SUB + dx, off * SUB + dy) for x in range(29, 47) for dx in range(SUB) for dy in range(0, 3)]
    b.edge_exits = [([c for c in cells if grid.walkable(*c)], 79)]
    b.custom_start = drlg.near_walkable(grid, C(ARMORY_ENTRY), 10)
    return b, grid, rng


SMITH_NAME = "Kalvhar the Pale Anvil"


def summon_smith(world):
    """All four altars burn: the armory's smith steps out in the forge court."""
    from . import actworld, monmods
    if any(getattr(m, "boss", None) == "armory_smith" for m in world.monsters):
        return None
    spot = getattr(world, "armory_boss", None) or world.player.pos
    taken = {m.pos for m in world.monsters if m.alive}
    lvl = world.info.monster_level(76) if getattr(world, "info", None) else 30
    cell = actworld._free_near(world.grid, spot, 8)
    m = actworld._spawn(world, "smith", cell, lvl + 4, taken, unique=True, name=SMITH_NAME)
    if m is None:
        return None
    m.boss = "armory_smith"
    world.player.armory_lit = True
    monmods.apply(world, m, [monmods.STRONG, monmods.COLD])
    m.color_shift = "paleblue"
    m.aware = True
    for c in actworld._scatter(world, m.pos, 4, taken):
        g = actworld._spawn(world, "zealot3", c, lvl + 1, taken)
        if g is not None:
            g.aware = True
    world.emit("place", m, m.pos)
    return m
