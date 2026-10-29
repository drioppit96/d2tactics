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
    86: dict(kit="a3dung", rooms=10, roles=["prev", "next"], act=3),
    87: dict(kit="a3dung", rooms=10, roles=["prev", "next"], act=3),
    88: dict(kit="a3dung", rooms=10, roles=["prev", "next"], act=3),
    89: dict(kit="a3dung", rooms=10, roles=["prev", "next"], act=3),
    90: dict(kit="preset", folder=J, files=["dungrm%da.ds1" % i for i in range(1, 7)], lvltype="Act 3 - Dungeon", act=3),
    91: dict(kit="preset", folder=J, files=["dungrm%db.ds1" % i for i in range(1, 7)], lvltype="Act 3 - Dungeon", act=3),
    92: dict(kit="a3sewer", rooms=14, roles=["up0", "up1", "up2", "up3", "next"], act=3,
             need_warps=({0, 1}, {2, 3})),
    93: dict(kit="preset", folder=A3 + "sewer\\", files=["sewertreasure1.ds1"], lvltype="Act 3 - Sewer", act=3),
    94: dict(kit="preset", folder=A3 + "temple\\", files=["temple0.ds1", "temple1.ds1", "temple2.ds1"], lvltype=KURAST_LT, act=3),
    95: dict(kit="preset", folder=A3 + "temple\\", files=["temple3.ds1", "temple4.ds1"], lvltype=KURAST_LT, act=3),
    96: dict(kit="preset", folder=A3 + "temple\\", files=["temple5.ds1", "temple6.ds1"], lvltype=KURAST_LT, act=3),
    97: dict(kit="preset", folder=A3 + "temple\\", files=["temple7.ds1", "temple8.ds1"], lvltype=KURAST_LT, act=3),
    98: dict(kit="preset", folder=A3 + "temple\\", files=["temple9.ds1", "temple10.ds1"], lvltype=KURAST_LT, act=3),
    99: dict(kit="preset", folder=A3 + "temple\\", files=["temple11.ds1", "temple12.ds1"], lvltype=KURAST_LT, act=3),
    100: dict(kit="meph", rooms=12, roles=["prev", "next"], act=3),
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
    W, H = 4 * P, 32 + 6 * P + 6 * P + 32 + 48
    cv = Canvas(kit, W, H, 3, seed)
    rng, b = cv.rng, cv.b
    cv.set_ground("jungle", J + "rivn.ds1", JUNGLE_LT)
    y_tail, y_flay = 0, 32
    y_spid = y_flay + 6 * P
    y_head = y_spid + 6 * P
    y_dock = y_head + 32
    # Kurast Docks
    dock = kit.ds1(A3 + "docktown\\docktown3.ds1")
    if dock is None:
        raise FileNotFoundError("Kurast Docks layout (act3\\docktown\\docktown3.ds1) not found")
    cv.put(A3 + "docktown\\docktown3.ds1", 0, y_dock, 75, "Act 3 - Town")
    dw, dh = dock.width - 1, dock.height - 1
    b.town_rect = (0, y_dock * SUB, dw * SUB, (y_dock + dh) * SUB)
    b.areas[75] = b.town_rect
    # the jungle's head (out of the docks) and tail (towards Kurast)
    head = pick_existing(kit, [J + "transl.ds1", J + "transu.ds1"], rng)
    tail = pick_existing(kit, [J + "travl.ds1", J + "travu.ds1"], rng)
    if head:
        cv.put(head, 0, y_head, 76, JUNGLE_LT)
    if tail:
        cv.put(tail, 0, y_tail, 78, JUNGLE_LT)
    jungle_area(cv, 76, 0, y_spid, {"n": 0, "s": 0}, [("spid", ""), ("spid", "2"), ("spid", "3")])
    jungle_area(cv, 78, 0, y_flay, {"n": 0, "s": 0}, [("pyg", ""), ("pyg", "2"), ("pyg", "3")])
    # the Great Marsh beside them, half along the Spider Forest, half along the Flayer Jungle
    jungle_area(cv, 77, 2 * P, y_flay + 3 * P, {}, [("bog", ""), ("bog", "2"), ("bog", "3")])
    x0, y0, x1, y1 = b.areas[76]
    b.areas[76] = (x0, y0, x1, (y_head + 32) * SUB)           # the head belongs to the Spider Forest
    x0, y0, x1, y1 = b.areas[78]
    b.areas[78] = (x0, 0, x1, y1)                            # ... the tail to the Flayer Jungle
    grid = cv.finish()
    gk = cv.ground_kit("jungle")
    drlg.ensure_connected(b, grid, [(75, 76), (76, 78), (76, 77), (77, 78)], gk, rng)
    drlg.ensure_waypoints(b, grid, 3)
    # the Gidbinn's altar somewhere in the Flayer Jungle
    x0, y0, x1, y1 = b.areas[78]
    c = drlg.near_walkable(grid, (rng.randrange(x0 + 40, x1 - 40), rng.randrange(y0 + 200, y1 - 200)), 80)
    if c:
        b.objects.append(("gidbinn", c, 78, -1))
    # the far edge of the tail: on to Lower Kurast (another world)
    cells = drlg.edge_cells(grid, (0, 0, 2 * P * SUB, 32 * SUB), "n")
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


def build_kurast(kit, seed=None, content=None):
    W, H = 80, 64 + 16 + 64 * 3
    cv = Canvas(kit, W, H, 3, seed)
    rng, b = cv.rng, cv.b
    for lid, k in KINDS.items():
        cv.set_ground(k, K + "%s08x08_0.ds1" % k, KURAST_LT)
    # Travincal (its six presets), the Causeway bridge, then the three city areas going south
    trav = [("travnw", 8, 0), ("travn", 24, 0), ("travne", 56, 0), ("travsw", 8, 32), ("travs", 24, 32), ("travse", 56, 32)]
    for name, x, y in trav:
        cv.put(A3 + "travincal\\%s.ds1" % name, x, y, 83, KURAST_LT)
    b.areas[83] = (8 * SUB, 0, 72 * SUB, 64 * SUB)
    cv.put(K + "bridge.ds1", 16, 64, 82, KURAST_LT)
    b.areas[82] = (0, 64 * SUB, 80 * SUB, 80 * SUB)
    for i, lid in enumerate((81, 80, 79)):
        y0 = 80 + i * 64
        spec = _kurast_spec(lid)
        placed = block_area(cv, lid, 0, y0, 10, 8, 8, spec)
        for k, (names, w, h, where) in enumerate(spec["specials"]):
            if "waypoint" in names[0] and k in placed:
                bx, by = placed[k]
                b.objects.append(("waypoint", ((bx * 8 + 4) * SUB, (y0 + by * 8 + 4) * SUB), lid, -1))
    grid = cv.finish()
    drlg.ensure_connected(b, grid, [(79, 80), (80, 81), (81, 82), (82, 83)], cv.ground_kit("slums"), rng)
    drlg.ensure_waypoints(b, grid, 3)
    # Lower Kurast's south gate: back into the jungle (another world)
    x0, y0, x1, y1 = b.areas[79]
    cells = drlg.edge_cells(grid, b.areas[79], "s", x_range=(24 * SUB, 56 * SUB))
    b.edge_exits = [(cells, 78)]
    return b, grid, rng
