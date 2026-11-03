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
SIDE_AREAS = {76: dict(name="Kurast Armory", like=80, side="e", own_world=True,
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
    dock = kit.ds1(A3 + "docktown\\docktown3.ds1")
    if dock is None:
        raise FileNotFoundError("Kurast Docks layout (act3\\docktown\\docktown3.ds1) not found")
    dw, dh = dock.width - 1, dock.height - 1
    W, H = SW + 80 + 4 + ARMORY + 4, 64 + 16 + 64 * 3 + dh
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
        if lid == 80:
            # the Bazaar opens west into the Scriptorium and, at its north-east, onto the armory road
            spec = dict(spec, openings={"w": (3, 1), "e": (1, 1)})
        placed = block_area(cv, lid, X, y0, 10, 8, 8, spec)
        for k, (names, w, h, where) in enumerate(spec["specials"]):
            if "waypoint" in names[0] and k in placed:
                bx, by = placed[k]
                b.objects.append(("waypoint", ((X + bx * 8 + 4) * SUB, (y0 + by * 8 + 4) * SUB), lid, -1))
    # the Kurast Docks right below Lower Kurast: walk out of town and you are in the city
    # (this game skips the jungle); the docks' road north lines up with Lower Kurast's south gate
    yd = 80 + 64 * 3
    xd = X + 40 - 29
    cv.put(A3 + "docktown\\docktown3.ds1", xd, yd, 75, "Act 3 - Town")
    b.town_rect = (xd * SUB, yd * SUB, (xd + dw) * SUB, (yd + dh) * SUB)
    b.stormtree_spot = ((xd + 29) * SUB, (yd - 13) * SUB)      # just inside Lower Kurast's south gate
    b.areas[75] = b.town_rect
    # the Kurast Armory beside the Bazaar: a road runs east from the Bazaar to its north gate
    ax, ay = X + 80 + 4, rows[80] + 26
    cv.ground("burbs", X + 80, rows[80] + 6, ax + 52 - (X + 80), 21)
    stamp_armory(kit, b, ax, ay)
    # the side areas
    for lid, sa in SIDE_AREAS.items():
        if sa.get("own_world"):
            continue
        y0 = rows[sa["like"]]
        x0 = X + 80 if sa["side"] == "e" else 0
        block_area(cv, lid, x0, y0, SIDE_W, 8, 8, _side_spec(lid))
    grid = cv.finish()
    armory_after_grid(b, grid, ax, ay)
    drlg.ensure_connected(b, grid, [(75, 79), (79, 80), (80, 81), (81, 82), (82, 83), (80, 77), (80, 76)],
                          cv.ground_kit("burbs"), rng)
    drlg.ensure_waypoints(b, grid, 3)
    b.edge_exits = []
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
    spot = getattr(world, "stormtree_spot", None)
    if spot and not any("stormtree" in (m.name or "").lower() for m in world.monsters):
        # out of the docks, the first thing you meet in Lower Kurast is Stormtree
        c = drlg.near_walkable(world.grid, spot, 30)
        if c is not None:
            actworld._spawn_preset(world, "Stormtree", c, 79, taken, info)
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
# The Zakarum smiths forged the Travincal guard's arms here. When Mephisto's corruption took the
# city, Kalvhar, the master smith, walled himself into the forge court; the old faith's four altars
# in the corners still hold him. The yard tells the rest: the storerooms half looted, the training
# yard abandoned mid-drill, the guards' last stand at the keep gate, the dead heaped in the ossuary.
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


ARMORY = 72                    # blueprint size in tiles (the area is one tile bigger all round)
# the designer's blueprint: crenellated walls between grid points (x0, y0) - (x1, y1)
ARMORY_WALLS = [((0, 0), (28, 0)), ((47, 0), (72, 0)), ((0, 0), (0, 72)), ((72, 0), (72, 72)), ((0, 72), (72, 72)),
                ((28, 0), (28, 14)), ((47, 0), (47, 14)),
                ((0, 20), (28, 20)), ((47, 20), (72, 20)),
                ((12, 29), (30, 29)), ((45, 29), (65, 29)),
                ((12, 29), (12, 55)), ((12, 55), (22, 55)), ((22, 55), (22, 72)),
                ((65, 29), (65, 51)), ((52, 51), (65, 51)), ((52, 51), (52, 72))]
ARMORY_ALTARS = [(5, 5), (66, 5), (6, 67), (66, 67)]
ARMORY_BOSS = (37, 64)
# Travincal buildings: (preset, source x, y, w, h, where in the blueprint)
ARMORY_BUILDINGS = [("travn", 7, 14, 21, 12, (28, 33)),          # the great hall in the keep
                    ("travs", 10, 2, 12, 9, (31, 58)),           # the council dais: the smith's forge court
                    ("travs", 0, 13, 9, 8, (10, 58)),            # the ossuary chapel (bottom left)
                    ("travs", 21, 15, 10, 8, (56, 58)),          # the quartermaster's house (bottom right)
                    ("travn", 15, 26, 8, 6, (2, 37)),            # a sunken cistern in the west lane
                    ("travnw", 10, 12, 7, 7, (17, 9))]           # the quartermaster's store (north-west)
# this game's own sprites (assets/decor) and D2's objects: (what, x, y) in blueprint tiles
ARMORY_DECOR = [
    # the gate: banners of Zakarum, and the guards' last stand
    ("banner", 29.6, 2.0), ("banner", 46.0, 2.0), ("blood", 37.0, 7.0), ("debris", 34.5, 10.0),
    ("debris", 41.0, 12.5), ("blood", 39.0, 16.0),
    # storeroom (north-west): crates, barrels, an ore cart, arrows, the quartermaster's dropped load
    ("crates", 3.5, 13.0), ("crates", 21.5, 3.0), ("cart", 11.0, 15.5),
    ("arrows", 9.5, 3.0), ("arrows", 17.0, 9.0), ("debris", 12.0, 9.0),
    # training yard (north-east): dummies in a row, racks, baskets of arrows
    ("dummy", 53.0, 9.0), ("dummy", 57.0, 9.0), ("dummy", 61.0, 9.0), ("dummy", 57.0, 14.0),
    ("weaponrack", 52.0, 3.0), ("weaponrack", 59.0, 3.0), ("arrows", 69.0, 12.0), ("arrows", 50.5, 16.0),
    ("armorstand", 69.5, 16.0), ("blood", 61.0, 16.0),
    # the parade ground between the halls
    ("banner", 14.0, 22.0), ("banner", 61.0, 22.0), ("cart", 6.0, 24.5), ("crates", 68.0, 24.0),
    ("debris", 32.0, 25.0), ("debris", 44.0, 23.0), ("blood", 38.0, 26.0), ("bones", 22.0, 25.5),
    # the keep: armour on parade before the great hall, forges in its wings
    ("armorstand", 20.0, 32.0), ("armorstand", 24.0, 32.0), ("armorstand", 52.0, 32.0), ("armorstand", 56.0, 32.0),
    ("banner", 30.5, 31.0), ("banner", 45.0, 31.0),
    ("forge", 17.0, 40.0), ("anvil", 22.5, 44.0), ("crates", 16.0, 50.0),
    ("forge", 59.0, 40.0), ("anvil", 54.0, 44.0), ("cart", 58.0, 48.5),
    ("weaponrack", 33.0, 49.0), ("weaponrack", 41.0, 49.0), ("blood", 37.0, 51.0),
    # the lanes
    ("armorstand", 4.0, 31.0), ("armorstand", 8.0, 31.0), ("crates", 5.0, 47.0), ("arrows", 9.0, 51.0),
    ("weaponrack", 66.0, 31.0), ("crates", 68.5, 40.0), ("debris", 68.0, 47.0),
    # the ossuary (south-west): the dead of the fall, heaped with candles
    ("bones", 4.0, 59.0), ("bones", 15.0, 69.0), ("blood", 10.0, 66.0), ("debris", 18.0, 62.0),
    # the quartermaster's (south-east)
    ("crates", 57.0, 69.0), ("cart", 69.0, 58.0), ("arrows", 62.0, 70.0),
    # the forge court: the smith's forges and anvils around the dais
    ("forge", 25.5, 58.5), ("forge", 48.5, 58.5), ("anvil", 27.0, 66.0), ("anvil", 47.0, 66.0),
    ("debris", 33.0, 70.0), ("blood", 41.0, 70.0), ("banner", 24.0, 70.5), ("banner", 50.5, 70.5),
]
# D2's own objects: (Objects.txt id, x, y) - torches, racks and stands to loot, fallen guards, barrels
ARMORY_OBJECTS = [(328, 27.0, 1.5), (328, 48.0, 1.5), (328, 11.0, 28.0), (328, 64.0, 28.0),
                  (328, 29.0, 30.0), (328, 46.0, 30.0), (328, 21.0, 56.0), (328, 51.0, 56.0),
                  (102, 16.0, 23.5), (102, 24.0, 23.5), (102, 51.0, 23.5), (102, 59.0, 23.5),
                  (106, 2.0, 8.0), (107, 26.0, 8.0), (548, 70.0, 6.0), (549, 49.0, 12.0),
                  (104, 36.0, 47.0), (105, 40.0, 47.0), (550, 14.0, 44.0), (551, 62.0, 44.0),
                  (154, 36.0, 12.0), (270, 39.0, 21.0), (154, 25.0, 27.0), (270, 49.0, 26.0),
                  (154, 8.0, 63.0), (270, 44.0, 62.0),
                  (7, 2.5, 17.0), (7, 3.5, 18.0), (11, 26.0, 17.5), (7, 70.0, 18.5), (11, 9.0, 55.0),
                  (7, 69.0, 66.0), (7, 54.5, 66.0)]
# themed corners of the yard, filled with more of the same (deterministic): (x0, y0, x1, y1, props, count)
ARMORY_THEMES = [
    (1, 1, 27, 19, ["crates", "arrows", "cart", "debris", "crates"], 14),                   # storeroom
    (48, 1, 71, 19, ["dummy", "weaponrack", "arrows", "armorstand", "dummy"], 14),          # training yard
    (29, 2, 46, 13, ["debris", "blood", "blood"], 7),                                      # the gate fight
    (1, 21, 71, 28, ["banner", "armorstand", "cart", "crates", "debris", "blood", "bones", "weaponrack"], 25),
    (1, 30, 11, 54, ["crates", "arrows", "debris", "blood"], 7),                           # west lane
    (66, 30, 71, 50, ["crates", "arrows", "blood"], 5),                                    # east lane
    (13, 30, 27, 54, ["anvil", "weaponrack", "crates", "armorstand", "blood", "debris"], 10),  # keep, west wing
    (50, 30, 64, 50, ["anvil", "weaponrack", "crates", "armorstand", "blood", "debris"], 10),  # keep, east wing
    (28, 46, 49, 54, ["weaponrack", "debris", "blood", "banner"], 7),                      # behind the hall
    (1, 56, 21, 71, ["bones", "blood", "debris", "bones", "blood"], 12),                    # the ossuary
    (53, 52, 71, 71, ["crates", "cart", "arrows", "crates"], 10),                           # quartermaster's
    (23, 56, 51, 71, ["anvil", "debris", "blood", "banner", "forge"], 10),                  # forge court
]
ARMORY_KEEP_CLEAR = [(31, 57, 44, 68), (27, 32, 50, 46)]          # the dais and the great hall
# Travincal's low-walled planters (sunken dark-green beds): (x, y, w, h) in blueprint tiles
ARMORY_PLANTERS = [(4, 22, 5, 4), (17, 22, 5, 4), (51, 22, 5, 4), (63, 22, 5, 4),
                   (14, 47, 4, 4), (59, 51, 4, 3), (2, 44, 4, 3), (33, 15, 3, 3), (40, 15, 3, 3)]
ARMORY_FLOOR_DECALS = [(49, 7), (49, 4), (49, 12), (49, 0), (49, 10)]
# how many cells around its spot each sprite blocks (0: you walk over it)
DECOR_BLOCK = {"anvil": 3, "forge": 7, "weaponrack": 4, "armorstand": 2, "crates": 6, "arrows": 3, "dummy": 1,
               "banner": 1, "cart": 6, "bones": 4, "debris": 0, "blood": 0}


def _wall_tiles(lines, n_ok):
    """Grid-point wall lines -> D2 wall tiles (orientation, main, sub), the way D2's own Travincal
    walls are laid: along a tile's north (2) and west (1) edges, with north (3), east-end (5),
    west-end (6) and south (7) corner pieces. Every piece is the full wall (body + battlements)."""
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
        if not n_ok(x, y):
            continue
        t = []
        if "E" in ds and "S" in ds:
            t = [(3, 32, 0), (3, 31, 0)]
        elif "E" in ds and "N" in ds and "W" not in ds:
            t = [(6, 32, 0), (6, 31, 0)]
        elif "E" in ds:
            t = [(2, 31, 0), (2, 32, 4 + x % 4)]
        elif "S" in ds and "W" in ds and "N" not in ds:
            t = [(5, 32, 0), (5, 31, 0)]
        elif "S" in ds:
            t = [(1, 31, 0), (1, 32, y % 4)]
        elif "N" in ds and "W" in ds:
            t = [(7, 32, 0), (7, 31, 0)]
        if t:
            out[(x, y)] = t
    return out


def _acell(ax, ay, x, y):
    return (int(round((ax + 1 + x) * SUB + 2)), int(round((ay + 1 + y) * SUB + 2)))


def stamp_armory(kit, b, ax, ay):
    """The Kurast Armory into a Built at tile (ax, ay): paving, Travincal's buildings, the walls of
    the blueprint, altars, the smith's spot, D2 objects and this game's decoration sprites."""
    from .act1 import stamp
    from . import custommap
    n = ARMORY + 2
    off = 1
    ts = custommap.tileset(kit, KURAST_LT)
    tm = b.tm
    R = custommap._rnd
    for y in range(off, off + ARMORY):
        for x in range(off, off + ARMORY):
            ref = ts.pick(0, 20, 0, R(ax + x, ay + y))
            if ref:
                tm.floor[(ax + x, ay + y)] = ref
            tm.walls.pop((ax + x, ay + y), None)
    for name, sx, sy, w, h, (bx, by) in ARMORY_BUILDINGS:
        ds = kit.ds1(A3 + "travincal\\%s.ds1" % name)
        if ds is None:
            continue
        nwarps = len(b.warps)
        stamp(b, _Sub(ds, sx, sy, w, h), kit.tiles_for(ds, KURAST_LT), ax + bx + off, ay + by + off,
              random.Random(R(bx, by)), 76, keep_edges=False)
        del b.warps[nwarps:]                 # (the chunks' own stairs lead nowhere here)
    walls = _wall_tiles(ARMORY_WALLS, lambda x, y: 0 <= x + off < n and 0 <= y + off < n)
    for (x, y), keys in walls.items():
        pos = (ax + x + off, ay + y + off)
        lst = []
        for o, m, s_ in keys:
            for oo in ([o, 4] if o == 3 else [o]):
                ref = ts.pick(oo, m, s_, R(pos[0], pos[1], oo))
                if ref:
                    lst.append(ref)
        if lst:
            tm.walls[pos] = lst
    b.areas[76] = ((ax + off) * SUB, (ay + off) * SUB, (ax + off + ARMORY) * SUB, (ay + off + ARMORY) * SUB)
    b.armory_at = (ax, ay)
    for oid, x, y in ARMORY_OBJECTS:
        b.gen_objects.append((("id", oid), _acell(ax, ay, x, y), 76))
    decor = getattr(b, "decor", None)
    if decor is None:
        decor = b.decor = []
    rng = random.Random(7676)
    placed = [(x, y) for _, x, y in ARMORY_DECOR]
    for name, x, y in ARMORY_DECOR:
        decor.append((name, _acell(ax, ay, x, y)))
    # fill the themed corners of the yard
    blocked = [(bx - 1, by - 1, bx + w + 1, by + h + 1) for _n, _sx, _sy, w, h, (bx, by) in ARMORY_BUILDINGS]
    blocked += ARMORY_KEEP_CLEAR + [(px_ - 1, py_ - 1, px_ + pw + 1, py_ + ph + 1) for px_, py_, pw, ph in ARMORY_PLANTERS]
    lines = ARMORY_WALLS

    def near_wall(x, y):
        for (x0, y0), (x1, y1) in lines:
            if y0 == y1 and min(x0, x1) - 1 <= x <= max(x0, x1) + 1 and abs(y - y0) < 1.6:
                return True
            if x0 == x1 and min(y0, y1) - 1 <= y <= max(y0, y1) + 1 and abs(x - x0) < 1.6:
                return True
        return False
    for x0, y0, x1, y1, props, count in ARMORY_THEMES:
        done = 0
        for _ in range(count * 40):
            if done >= count:
                break
            x, y = rng.uniform(x0 + 1, x1 - 1), rng.uniform(y0 + 1, y1 - 1)
            if any(bx0 <= x <= bx1 and by0 <= y <= by1 for bx0, by0, bx1, by1 in blocked):
                continue
            if near_wall(x, y) or any(abs(x - px) + abs(y - py) < 4.5 for px, py in placed):
                continue
            if any(abs(x - a) + abs(y - b_) < 5 for a, b_ in ARMORY_ALTARS + [ARMORY_BOSS]):
                continue
            name = props[done % len(props)]
            decor.append((name, _acell(ax, ay, x, y)))
            placed.append((x, y))
            done += 1
    # the planters
    for px_, py_, pw, ph in ARMORY_PLANTERS:
        x0, y0, x1, y1 = ax + off + px_, ay + off + py_, ax + off + px_ + pw, ay + off + py_ + ph
        for y in range(y0, y1):
            for x in range(x0, x1):
                ref = ts.pick(0, 29, 12, R(x, y))
                if ref:
                    tm.floor[(x, y)] = ref
        pieces = {}
        for x in range(x0, x1 + 1):
            pieces[(x, y0)] = 2
            pieces[(x, y1)] = 2
        for y in range(y0, y1 + 1):
            pieces[(x0, y)] = 1
            pieces[(x1, y)] = 1
        pieces[(x0, y0)], pieces[(x1, y0)], pieces[(x0, y1)], pieces[(x1, y1)] = 3, 5, 6, 7
        for pos, o in pieces.items():
            lst = []
            for oo in ([o, 4] if o == 3 else [o]):
                ref = ts.pick(oo, 31, 0, R(pos[0], pos[1], oo))
                if ref:
                    lst.append(ref)
            if lst:
                tm.walls[pos] = lst
    # torches along the walls, a little in from them
    for (x0, y0), (x1, y1) in lines:
        if y0 == y1:
            for x in range(min(x0, x1) + 3, max(x0, x1) - 2, 9):
                for dy in (0.9, -0.9):
                    if 0.5 < y0 + dy < ARMORY - 0.5:
                        b.gen_objects.append((("id", 328), _acell(ax, ay, x, y0 + dy), 76))
                        break
        else:
            for y in range(min(y0, y1) + 3, max(y0, y1) - 2, 9):
                for dx in (0.9, -0.9):
                    if 0.5 < x0 + dx < ARMORY - 0.5:
                        b.gen_objects.append((("id", 328), _acell(ax, ay, x0 + dx, y), 76))
                        break
    # wear on the paving: stains, cracks and grime (Travincal's second floor layer)
    for y in range(off, off + ARMORY):
        for x in range(off, off + ARMORY):
            if rng.random() < 0.12 and (ax + x, ay + y) not in tm.floor2:
                m_, s_ = rng.choice(ARMORY_FLOOR_DECALS)
                ref = ts.pick(0, m_, s_, R(ax + x, ay + y, 3))
                if ref:
                    tm.floor2[(ax + x, ay + y)] = ref


def armory_after_grid(b, grid, ax, ay):
    """Once the grid exists: the walls block all along, the sprites block what they cover, and the
    altars and the smith's spot are found on walkable ground."""
    from .grid import WALL
    off = 1
    for (x0, y0), (x1, y1) in ARMORY_WALLS:
        if y0 == y1:
            Y = (ay + y0 + off) * SUB
            for X in range((ax + min(x0, x1) + off) * SUB, (ax + max(x0, x1) + off) * SUB + 1):
                for yy in (Y - 1, Y):
                    if grid.in_bounds(X, yy):
                        grid.cells[yy][X] = WALL
        else:
            X = (ax + x0 + off) * SUB
            for Y in range((ay + min(y0, y1) + off) * SUB, (ay + max(y0, y1) + off) * SUB + 1):
                for xx in (X - 1, X):
                    if grid.in_bounds(xx, Y):
                        grid.cells[Y][xx] = WALL
    for name, (cx, cy) in getattr(b, "decor", []):
        r = DECOR_BLOCK.get(name, 0)
        if r <= 0:
            continue
        for y in range(cy - r // 2 - 1, cy + (r + 1) // 2):
            for x in range(cx - r + 1, cx + r):
                if grid.in_bounds(x, y) and abs(x - cx) / float(r) + abs(y - cy) / float(max(1, r * 0.8)) <= 1.2:
                    grid.cells[y][x] = WALL
    for a in ARMORY_ALTARS:
        c = drlg.near_walkable(grid, _acell(ax, ay, *a), 12)
        if c:
            b.objects.append(("armory_altar", c, 76, -1))
    b.armory_boss = drlg.near_walkable(grid, _acell(ax, ay, *ARMORY_BOSS), 12)


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
