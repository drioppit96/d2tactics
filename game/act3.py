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
    # D2's Kurast waypoint block (the raised waypoint platform): Lower and Upper Kurast's just inside
    # the gate you come in by (from the docks / from the Bazaar), the Bazaar's anywhere
    specials.append(([K + "burbs08x08_waypoint.ds1"], 1, 1, (4, 6) if k in ("slums", "metro") else None))
    fills = [([K + "%s16x16_%d.ds1" % (k, i) for i in range(5)], 2, 2),
             ([K + "%s16x08_%d.ds1" % (k, i) for i in range(5)], 2, 1),
             ([K + "%s08x16_%d.ds1" % (k, i) for i in range(5)], 1, 2),
             ([K + "%s08x08_%d.ds1" % (k, i) for i in range(6)], 1, 1)]
    return dict(lvltype=KURAST_LT, ground=k, border=border, specials=specials, fills=fills, fill_chance=0.8)


# this game's two extra areas (level ids of the skipped jungle, renamed): built like the area they
# join - the Kurast Armory off Lower Kurast's east side, the Kurast Scriptorium off the Bazaar's west
SIDE_AREAS = {76: dict(name="Kurast Armory", like=80, side="e", own_world=True,
                       roster=["zealot1", "blunderbore1"]),      # Zakarumites and the harem's dark giants
              77: dict(name="Kurast Scriptorium", like=80, side="w",                # the zealots who sacked it,
                       roster=["zealot2", "zealot3", "cantor1", "cantor2", "mummy5"])}  # the scribes risen
SIDE_W = 5                     # blocks (8 tiles) wide
# the Forbidden Library under the Scriptorium (a map-editor map, assets/maps/forbidden_library.json): it
# takes the level id of the Swampy Pit, which this game's Kurast has no way into
LIBRARY = 86
EXTRA_LEVELS = {LIBRARY: dict(name="Forbidden Library", like=80, plus=3,
                              roster=["zealot3", "cantor2", "mummy5", "unraveler3"])}
SCRIPTORIUM_MAP = "kurast_scriptorium"


def _side_spec(lid):
    sa = SIDE_AREAS[lid]
    spec = _kurast_spec(sa["like"])
    spec = dict(spec, specials=[([K + "burbs08x08_waypoint.ds1"], 1, 1, (2, 3))], fill_chance=0.85)
    inner = "w" if sa["side"] == "e" else "e"
    spec["openings"] = {inner: (3, 1)}
    spec["border"] = {k: v for k, v in spec["border"].items() if k != inner and not (isinstance(k, tuple) and inner in k)}
    return spec


def build_kurast(kit, seed=None, content=None):
    from . import custommap
    city = custommap.game_map(SCRIPTORIUM_MAP)          # the Kurast Scriptorium, hand-made (80 x 64)
    SW = int(city["width"]) if city else SIDE_W * 8
    dock = kit.ds1(A3 + "docktown\\docktown3.ds1")
    if dock is None:
        raise FileNotFoundError("Kurast Docks layout (act3\\docktown\\docktown3.ds1) not found")
    dw, dh = dock.width - 1, dock.height - 1
    W, H = SW + 80 + ARMORY_ROAD + ARMORY + 4, 64 + 16 + 64 * 3 + dh
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
            spec = dict(spec, openings={"w": (3, 1), "e": (2, 0)})
        placed = block_area(cv, lid, X, y0, 10, 8, 8, spec)
        # (the waypoint block carries D2's waypoint object itself)
    # the Kurast Docks right below Lower Kurast: walk out of town and you are in the city
    # (this game skips the jungle); the docks' road north lines up with Lower Kurast's south gate
    yd = 80 + 64 * 3
    xd = X + 40 - 29
    cv.put(A3 + "docktown\\docktown3.ds1", xd, yd, 75, "Act 3 - Town")
    b.town_rect = (xd * SUB, yd * SUB, (xd + dw) * SUB, (yd + dh) * SUB)
    b.stormtree_spot = ((xd + 29) * SUB, (yd - 13) * SUB)      # just inside Lower Kurast's south gate
    b.areas[75] = b.town_rect
    # the Kurast Armory beside the Bazaar: a road runs east from the Bazaar to its north gate
    # its gate (in the west wall) lines up with the opening in the Bazaar's east side, a short
    # walled road between them
    ax, ay = X + 80 + ARMORY_ROAD - 1, rows[80] + 16 - 1 - ARMORY_GATE[0]
    stamp_armory(kit, b, ax, ay)
    # the side areas
    for lid, sa in SIDE_AREAS.items():
        if sa.get("own_world"):
            continue
        if lid == 77 and city:
            # its east gate meets the Bazaar's west opening; the temple in its north-east corner holds
            # the stairs down to the Forbidden Library
            cy = rows[sa["like"]]
            custommap.lay_tiles(kit, b, city, 0, cy, 77)
            custommap.lay_things(b, city, 0, cy, 77)
            b.areas[77] = (0, cy * SUB, int(city["width"]) * SUB, (cy + int(city["height"])) * SUB)
            b.scriptorium_json = (city, 0, cy)
            continue
        y0 = rows[sa["like"]]
        x0 = X + 80 if sa["side"] == "e" else 0
        block_area(cv, lid, x0, y0, SIDE_W, 8, 8, _side_spec(lid))
    grid = cv.finish()
    if getattr(b, "scriptorium_json", None):
        custommap.block_walls(*b.scriptorium_json[:1], grid, *b.scriptorium_json[1:])
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
    (LIBRARY, "cantor2", "Scribe Ophizek the Hollow", "scribe", ("MANAHIT", "TELEPORT"), ("zealot3", 4)),
    # the Scriptorium's crypt garden: a giant winged Venom Lord among the tombs and sigils, with the
    # sewers' walking dead around him; he drops exactly what Nihlathak drops
    (77, "megademon3", "Morvane the Unburied", "crypt", ("STRONG", "STONESKIN"), ("mummy4", 5)),
]
GIANTS = {"crypt": 2.0}         # boss tag -> drawn this many times its normal size
LOOT_LIKE = {"crypt": ("nihlathakboss", 124)}   # boss tag -> (boss whose loot he drops, that boss's area)


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
    for m in world.monsters:                 # the armory's giants are soot-dark, like the harem's
        if getattr(m, "d2id", None) == "blunderbore1" and not getattr(m, "color_shift", 0) \
                and world.area_at((m.x, m.y)) == 76:
            m.color_shift = "dark"
    for lid, mid, name, tag, mods, (minion, n) in SIDE_BOSSES:
        rect = world.areas.get(lid)
        if rect is None or world.content is None or mid not in world.content.monstats:
            continue
        if any(getattr(m, "boss", None) == tag for m in world.monsters):
            continue
        x0, y0, x1, y1 = rect
        cell = None
        nest = getattr(world, "armory_spider", None) if tag == "silkmother" else None
        if tag in ("scribe", "crypt"):       # they wait at their map's boss spot (dais, crypt garden)
            nest = next((c for w, c in getattr(world, "markers", []) if w == "boss"
                         and world.area_at(c) == lid), None)
        if nest is not None:                 # the Silkmother waits in her nest by the armory's gate
            cell = actworld._free_near(world.grid, nest, 8)
            if cell in taken or not world.grid.walkable(*cell):
                cell = None
        for _ in range(0 if cell else 200):
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
        if tag in GIANTS:
            m.giant = GIANTS[tag]
        if tag in LOOT_LIKE:                 # the same treasure classes, rolled at that boss's own level
            other, area = LOOT_LIKE[tag]
            at = actworld._template(world, other, info.monster_level(area) + 2, unique=True)
            if at is not None:
                m.tc, m.tc_quest = at.get("tc"), at.get("tc_quest")
                m.drop_level = at.get("level")
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


ARMORY = 43                    # the compound in tiles (the area is one tile bigger all round)
ARMORY_GATE = (17, 26)         # the gate in the west wall (y range), facing the Bazaar
ARMORY_ROAD = 11               # tiles of walled forecourt between the Bazaar's east edge and the gate
ARMORY_FORECOURT = (11, 32)    # its north and south walls (y)
FIELDSTONE = 20                # D2 Kurast wall styles (main index): solid fieldstone ...
PLASTER = 24                   # ... and plastered, bloodied room walls
# the blueprint (north up, gate west): solid fieldstone walls, (x0, y0) - (x1, y1)
ARMORY_WALLS = [((0, 0), (43, 0)), ((43, 0), (43, 43)), ((0, 43), (43, 43)), ((0, 0), (0, 17)), ((0, 26), (0, 43)),
                ((0, 16), (8, 16)), ((0, 28), (8, 28)),                       # the gate hall
                ((12, 0), (12, 16)), ((12, 28), (12, 43)),                    # ... and the muster court
                ((17, 4), (17, 16)), ((17, 4), (31, 4)), ((31, 4), (31, 12)), ((31, 12), (43, 12)),   # the keep
                ((17, 26), (17, 37)), ((17, 37), (33, 37)), ((33, 31), (33, 37)), ((33, 31), (43, 31)),
                # the forecourt before the gate, open to the Bazaar between its chapel and guardhouse
                ((-11, 11), (0, 11)), ((-11, 32), (0, 32)), ((-11, 11), (-11, 17)), ((-11, 26), (-11, 32)),
                # the two gate towers
                ((-2, 17), (0, 17)), ((-2, 17), (-2, 19)), ((-2, 19), (0, 19)),
                ((-2, 24), (0, 24)), ((-2, 24), (-2, 26)), ((-2, 26), (0, 26))]
# rooms inside: plastered walls, with doorways left open
ARMORY_INNER = [((0, 8), (8, 8)),                                            # barracks | mess hall
                ((4, 0), (4, 3)), ((4, 5), (4, 8)),                          # officers' corner in the barracks
                ((0, 35), (7, 35)), ((6, 28), (6, 31)), ((6, 33), (6, 35)),  # crypt | ossuary, the crypt's vault
                ((17, 26), (26, 26)), ((29, 26), (34, 26)), ((26, 26), (26, 29)),   # hall of arms | the vaults
                ((17, 31), (23, 31)), ((25, 31), (33, 31)),                  # the vaults | grindstone hall
                ((14, 38), (14, 42)), ((14, 42), (17, 42)), ((17, 38), (17, 42)),   # smithy row: three forge sheds
                ((20, 38), (20, 42)), ((20, 42), (23, 42)), ((23, 38), (23, 42)),
                ((26, 38), (26, 42)), ((26, 42), (29, 42)), ((29, 38), (29, 42)),
                ((33, 37), (38, 37)), ((38, 37), (38, 40)),                  # the quartermaster's counter
                ((34, 15), (36, 15)), ((41, 15), (43, 15))]                  # the forge court's inner gate
ARMORY_ALTARS = [(2.5, 2.5), (40.5, 2.5), (2.5, 40.5), (40.5, 40.5)]
ARMORY_BOSS = (38.5, 28.5)
ARMORY_SPIDER = (-6.8, 27.0)    # the spider queen's nest, by the guardhouse in the forecourt
# Travincal buildings: (preset, source x, y, w, h, where in the blueprint)
ARMORY_BUILDINGS = [("travnw", 10, 12, 7, 7, (20, 5)),           # the weapon vault (a Travincal hall)
                    ("travs", 12, 3, 7, 7, (35, 19)),            # the council dais: the smith's forge court
                    ("travs", 2, 16, 7, 5, (-10, 12)),           # forecourt: the gatehouse chapel
                    ("travs", 21, 16, 7, 5, (-10, 26))]          # ... and the guardhouse
ARMORY_WAYPOINT = (1, 18)                                        # the waypoint block, in the gate hall
ARMORY_ROOMS = []               # (no random scatter: every room is laid out by hand below)
# stone pillars (D2's Kurast pillar pieces): tiles
ARMORY_PILLARS = ([(x, y) for x in (20, 24, 28, 32) for y in (19, 24)] +   # hall of arms
                  [(10, 18), (10, 26)] +                                  # gate hall
                  [(-8, 18), (-5, 18), (-8, 25), (-5, 25)] +              # forecourt colonnade
                  [(18, 13), (30, 13)])                                   # before the weapon vault


def _row(name, x0, x1, y, step):
    out, x = [], x0
    while x <= x1 + 1e-6:
        out.append((name, x, y))
        x += step
    return out


def _col(name, x, y0, y1, step):
    out, y = [], y0
    while y <= y1 + 1e-6:
        out.append((name, x, y))
        y += step
    return out


ARMORY_DECOR = (
    # the forecourt: supplies left by the chapel and the guardhouse, banners on the gate towers,
    # blood on the road
    [("crates", -1.5, 13.4), ("sacks", -2.0, 15.6), ("cart", -1.8, 29.6), ("kegs", -1.4, 27.4),
     ("banner", -1.2, 18.6), ("banner", -1.2, 25.0), ("gibbet", -10.2, 22.0), ("blood", -5.0, 21.5)] +
    # the gate hall: stone zealots keep watch around the waypoint
    [("statue", 1.2, 17.0), ("statue", 1.2, 27.0), ("statue", 8.6, 17.0), ("statue", 8.6, 27.0),
     ("banner", 4.6, 16.6), ("banner", 4.6, 27.6)] +
    # barracks: bunks along both walls, the guards' armour by the door; the officers' corner has a
    # table and kegs (and the first altar)
    _row("bunks", 5.6, 9.6, 1.2, 2.0) + _row("bunks", 5.6, 9.6, 6.9, 2.0) +
    [("armorstand", 11.3, 3.4), ("armorstand", 11.3, 5.0), ("table", 2.0, 5.6), ("kegs", 3.2, 7.2)] +
    # mess hall: two rows of long tables, the kitchen's cauldron, kegs along the west wall
    [("table", x, y) for x in (2.6, 6.2, 9.8) for y in (10.2, 13.4)] +
    [("cauldron", 11.0, 9.2), ("sacks", 11.2, 11.4), ("kegs", 0.9, 9.6), ("kegs", 0.9, 12.2)] +
    # muster court: armour on parade
    _row("armorstand", 13.0, 16.0, 17.2, 1.5) + _row("armorstand", 13.0, 16.0, 26.8, 1.5) +
    # crypt: the dead along the walls, its vault behind; the ossuary's heaped bones
    _col("bones", 11.0, 29.6, 33.6, 2.0) + [("bones", 1.0, 29.8), ("bones", 1.0, 32.6), ("statue", 8.8, 28.7),
                                           ("chest", 7.2, 34.2)] +
    _row("bones", 5.0, 11.0, 42.2, 3.0) + _col("spikes", 11.2, 36.6, 40.6, 2.0) +
    [("statue", 5.6, 36.4), ("blood", 5.6, 39.2)] +
    # supply lane: carts parked along the north wall with their loads, more stacked by the keep
    [("cart", 14.2, 1.3), ("crates", 17.2, 1.1), ("sacks", 19.2, 1.2), ("cart", 21.8, 1.3), ("kegs", 24.6, 1.2),
     ("cart", 28.0, 1.3)] + _col("crates", 13.0, 6.0, 12.0, 3.0) + [("sacks", 16.2, 7.0), ("sacks", 16.2, 11.0)] +
    # training yard: dummies, the archery butts on the east wall, arrow baskets, racks on the south wall
    _row("dummy", 32.6, 37.6, 3.6, 2.5) + _col("target", 42.3, 5.0, 10.0, 2.5) +
    [("arrows", 36.4, 6.8), ("arrows", 36.4, 9.2), ("armorstand", 32.4, 1.2)] +
    _row("weaponrack", 33.0, 39.0, 11.1, 3.0) +
    # before the weapon vault
    [("banner", 19.4, 13.4), ("banner", 28.6, 13.4)] +
    # hall of arms: racks along the north wall, armour along the south, pillars down the aisle
    _row("weaponrack", 18.6, 30.6, 17.4, 4.0) + _row("armorstand", 18.6, 30.6, 25.2, 4.0) +
    # armour vault and the helm-and-shield room
    _row("armorstand", 18.4, 24.4, 27.5, 2.0) + [("chest", 25.0, 30.2), ("shieldrack", 28.2, 30.2),
                                                ("shieldrack", 31.6, 30.2), ("chest", 32.2, 27.4)] +
    # grindstone hall: wheels, crates of blades waiting along the south wall
    [("grindstone", 19.4, 33.2), ("grindstone", 27.6, 33.2), ("grindstone", 31.2, 33.2)] +
    _row("crates", 19.0, 31.0, 36.2, 4.0) +
    # smithy row: a forge at the back of each shed, its anvil in front
    [("forge", 15.5, 41.0), ("anvil", 15.5, 38.8), ("forge", 21.5, 41.0), ("anvil", 21.5, 38.8),
     ("forge", 27.5, 41.0), ("anvil", 27.5, 38.8), ("crates", 31.2, 38.6), ("sacks", 31.6, 42.2)] +
    # quartermaster's: crates along the east wall, sacks, the counter's strongboxes
    _col("crates", 42.2, 32.2, 37.2, 2.5) + [("sacks", 40.0, 33.0), ("sacks", 40.0, 36.0), ("cart", 35.2, 33.2),
                                            ("chest", 34.6, 38.6), ("chest", 36.8, 38.6), ("kegs", 34.4, 42.0)] +
    # the forge court: two great forges at the north wall with their anvils and the smith's cauldron;
    # where he waits, the bodies of those who came for the Gidbinn
    [("forge", 35.6, 13.3), ("forge", 41.4, 13.3), ("anvil", 35.6, 16.4), ("anvil", 41.4, 16.4),
     ("cauldron", 38.5, 13.6), ("gibbet", 34.6, 29.8), ("gibbet", 42.3, 29.8), ("bones", 36.6, 29.8),
     ("blood", 38.5, 28.6), ("bones", 40.4, 29.8), ("debris", 37.2, 26.8)] +
    # a fight at the gate: the last guards died here
    [("blood", 9.4, 21.6), ("debris", 10.8, 23.2)]
)

# D2's own objects: (Objects.txt id, x, y) - braziers, torches, racks and stands to loot, the fallen, barrels, chests
ARMORY_OBJECTS = [(102, -6.5, 18.6), (102, -6.5, 25.4), (102, -1.0, 19.8), (102, -1.0, 23.8),
                  (102, 8.6, 18.6), (102, 8.6, 25.4), (102, 33.2, 21.5), (102, 38.5, 17.2),
                  (106, 13.0, 18.8), (107, 13.0, 25.4), (548, 40.2, 10.8), (549, 32.6, 6.2),
                  (104, 25.0, 28.4), (105, 18.6, 29.8), (550, 27.6, 28.0), (551, 30.2, 28.2),
                  (154, 10.0, 20.0), (270, 15.0, 21.6), (154, 24.0, 14.0), (270, 36.6, 30.4),
                  (154, 5.0, 40.0), (5, 10.8, 30.4), (7, 12.8, 3.2), (11, 30.2, 1.2), (11, 15.6, 30.2),
                  (7, 41.0, 42.2)]
ARMORY_FLOOR_DECALS = [(49, 7), (49, 4), (49, 12), (49, 0), (49, 10)]
# how many cells around its spot each sprite blocks (0: you walk over it)
DECOR_BLOCK = {"anvil": 2, "forge": 4, "weaponrack": 3, "armorstand": 1, "crates": 3, "arrows": 2, "dummy": 1,
               "banner": 1, "cart": 3, "bones": 2, "debris": 0, "blood": 0, "statue": 2, "bunks": 3, "table": 3,
               "kegs": 2, "grindstone": 2, "target": 1, "shieldrack": 3, "chest": 2, "cauldron": 2, "gibbet": 1,
               "spikes": 2, "sacks": 2}


_BLOCKS = None


def decor_block(name):
    """How many cells around its spot a sprite blocks: the list above, else what the sprite importer
    worked out from its size (assets/decor/blocks.json)."""
    global _BLOCKS
    if name in DECOR_BLOCK:
        return DECOR_BLOCK[name]
    if _BLOCKS is None:
        import json
        import os
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "decor", "blocks.json")
        try:
            with open(path) as f:
                _BLOCKS = json.load(f)
        except Exception:
            _BLOCKS = {}
    return int(_BLOCKS.get(name, 0))


def _wall_tiles(lines, n_ok, main):
    """Grid-point wall lines -> D2 wall tiles (orientation, main, sub), the way D2 lays them: along a
    tile's north (2) and west (1) edges, with north (3), east-end (5), west-end (6) and south (7)
    corner pieces. `main` picks the wall (solid fieldstone or plaster)."""
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
    nsub = {FIELDSTONE: {1: 3, 2: 3}, PLASTER: {1: 5, 2: 5}}[main]
    out = {}
    for (x, y), ds in pts.items():
        if not n_ok(x, y):
            continue
        h = (x * 7 + y * 13) & 0xFFFF
        if "E" in ds and "S" in ds:
            t = (3, main, 0)
        elif "E" in ds and "N" in ds and "W" not in ds:
            t = (6, main, 0)
        elif "E" in ds:
            t = (2, main, h % nsub[2])
        elif "S" in ds and "W" in ds and "N" not in ds:
            t = (5, main, 0)
        elif "S" in ds:
            t = (1, main, h % nsub[1])
        elif "N" in ds and "W" in ds:
            t = (7, main, 0)
        else:
            continue
        out[(x, y)] = t
    return out


def _acell(ax, ay, x, y):
    return (int(round((ax + 1 + x) * SUB + 2)), int(round((ay + 1 + y) * SUB + 2)))


ARMORY_MAP_NAME = "kurast_armory.json"


def armory_map():
    """The armory as a map-editor map: your edited copy (maps/kurast_armory.json) if there is one,
    otherwise the one that comes with the game (assets/maps). None: build it from the code below."""
    from . import custommap
    return custommap.game_map(ARMORY_MAP_NAME[:-5])


def stamp_armory(kit, b, ax, ay, procedural=False):
    """The Kurast Armory into the Kurast world: from its map-editor map when there is one."""
    data = None if procedural else armory_map()
    if data is not None:
        from . import custommap
        ox, oy = ax - ARMORY_ROAD, ay
        custommap.lay_tiles(kit, b, data, ox, oy, 76)
        custommap.lay_things(b, data, ox, oy, 76)
        b.armory_json = (data, ox, oy)
        b.areas[76] = ((ox + 1) * SUB, (oy + 1) * SUB, (ax + 1 + ARMORY) * SUB, (ay + 1 + ARMORY) * SUB)
        b.armory_at = (ax, ay)
        return
    _stamp_armory_code(kit, b, ax, ay)


def _armory_after_grid_json(b, grid):
    """Blocking for a map-editor armory: its fieldstone and plaster walls all along their edges, the
    pillars, the sprites; the altars and the smith's spot from its markers."""
    from .grid import WALL
    data, ox, oy = b.armory_json

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
        if main not in (FIELDSTONE, PLASTER):
            continue
        block(X - 1, Y - 1, X + 1, Y + 1)
        if o in (2, 3, 6):
            block(X, Y - 1, X + SUB + 1, Y + 1)
        if o in (1, 3, 5):
            block(X - 1, Y, X + 1, Y + SUB + 1)
    _block_decor(b, grid)
    altars = [c for w, c in getattr(b, "markers", []) if w == "altar"]
    for i, c in enumerate(altars):           # Diablo's seals from the Chaos Sanctuary, one of each kind
        c2 = drlg.near_walkable(grid, c, 12)
        if c2:
            b.objects.append(("armory_altar", c2, 76, i % 5))
    smith = [c for w, c in getattr(b, "markers", []) if w == "smith"]
    b.armory_boss = drlg.near_walkable(grid, smith[0], 12) if smith else None
    spider = [c for w, c in getattr(b, "markers", []) if w == "spider"]
    c = spider[0] if spider else _acell(ox + ARMORY_ROAD, oy, *ARMORY_SPIDER)
    b.armory_spider = drlg.near_walkable(grid, c, 12)


def _block_decor(b, grid):
    from .grid import WALL
    for name, (cx, cy) in getattr(b, "decor", []):
        r = decor_block(name)
        if r <= 0:
            continue
        for y in range(cy - r // 2 - 1, cy + (r + 1) // 2):
            for x in range(cx - r + 1, cx + r):
                if grid.in_bounds(x, y) and abs(x - cx) / float(r) + abs(y - cy) / float(max(1, r * 0.8)) <= 1.2:
                    grid.cells[y][x] = WALL


def _stamp_armory_code(kit, b, ax, ay):
    """The Kurast Armory into a Built at tile (ax, ay), its gate road reaching west to the Bazaar:
    paving, the waypoint block, Travincal's buildings, solid and plastered walls, rooms filled with
    sprites and D2 objects, the altars and the smith's spot."""
    from .act1 import stamp
    from . import custommap
    off = 1
    ts = custommap.tileset(kit, KURAST_LT)
    tm = b.tm
    R = custommap._rnd
    g0, g1 = ARMORY_GATE

    def pave(x0, y0, x1, y1):
        for y in range(y0, y1):
            for x in range(x0, x1):
                ref = ts.pick(0, 20, 0, R(ax + off + x, ay + off + y))
                if ref:
                    tm.floor[(ax + off + x, ay + off + y)] = ref
                tm.walls.pop((ax + off + x, ay + off + y), None)
    pave(0, 0, ARMORY, ARMORY)
    pave(-ARMORY_ROAD, ARMORY_FORECOURT[0], 0, ARMORY_FORECOURT[1])     # the forecourt
    pave(-ARMORY_ROAD - 1, g0, 0, g1)                      # the gate road (meets the Bazaar's paving)
    wpds = kit.ds1(K + "burbs08x08_waypoint.ds1")
    if wpds is not None:
        wx, wy = ARMORY_WAYPOINT
        stamp(b, wpds, kit.tiles_for(wpds, KURAST_LT), ax + off + wx, ay + off + wy, random.Random(76), 76,
              keep_edges=False)
    for name, sx, sy, w, h, (bx, by) in ARMORY_BUILDINGS:
        ds = kit.ds1(A3 + "travincal\\%s.ds1" % name)
        if ds is None:
            continue
        nwarps = len(b.warps)
        stamp(b, _Sub(ds, sx, sy, w, h), kit.tiles_for(ds, KURAST_LT), ax + bx + off, ay + by + off,
              random.Random(R(bx, by)), 76, keep_edges=False)
        del b.warps[nwarps:]                 # (the chunks' own stairs lead nowhere here)
    ok = lambda x, y: -ARMORY_ROAD - 2 <= x <= ARMORY + 1 and -1 <= y <= ARMORY + 1
    for lines, main in ((ARMORY_WALLS, FIELDSTONE), (ARMORY_INNER, PLASTER)):
        for (x, y), (o, m, s_) in _wall_tiles(lines, ok, main).items():
            pos = (ax + x + off, ay + y + off)
            lst = [r for r in tm.walls.get(pos, []) if main == PLASTER and getattr(r[1], "orientation", 0) != o]
            for oo in ([o, 4] if o == 3 else [o]):
                ref = ts.pick(oo, m, s_, R(pos[0], pos[1], oo)) or ts.pick(oo, m, 0, 0)
                if ref:
                    lst.append(ref)
            if lst:
                tm.walls[pos] = lst
    for x, y in ARMORY_PILLARS:
        pos = (ax + off + x, ay + off + y)
        ref = ts.pick(12, FIELDSTONE, (x * 3 + y) % 3, 0) or ts.pick(12, PLASTER, 0, 0)
        if ref:
            tm.walls.setdefault(pos, []).append(ref)
    b.areas[76] = ((ax + off - ARMORY_ROAD) * SUB, (ay + off) * SUB, (ax + off + ARMORY) * SUB, (ay + off + ARMORY) * SUB)
    b.armory_at = (ax, ay)
    for oid, x, y in ARMORY_OBJECTS:
        b.gen_objects.append((("id", oid), _acell(ax, ay, x, y), 76))
    decor = getattr(b, "decor", None)
    if decor is None:
        decor = b.decor = []
    placed = [(x, y) for _, x, y in ARMORY_DECOR] + [(x, y) for _, x, y in ARMORY_OBJECTS]
    for name, x, y in ARMORY_DECOR:
        decor.append((name, _acell(ax, ay, x, y)))
    # fill each room with its own things
    rng = random.Random(7676)
    blocked = [(bx - 1, by - 1, bx + w + 1, by + h + 1) for _n, _sx, _sy, w, h, (bx, by) in ARMORY_BUILDINGS]
    wx, wy = ARMORY_WAYPOINT
    blocked.append((wx - 1, wy - 1, wx + 9, wy + 9))
    blocked.append((-1, g0 + 2, 10, g1 - 2))                        # the way in stays clear
    lines = ARMORY_WALLS + ARMORY_INNER

    def near_wall(x, y):
        for (x0, y0), (x1, y1) in lines:
            if y0 == y1 and min(x0, x1) - 1 <= x <= max(x0, x1) + 1 and abs(y - y0) < 1.4:
                return True
            if x0 == x1 and min(y0, y1) - 1 <= y <= max(y0, y1) + 1 and abs(x - x0) < 1.4:
                return True
        return False
    for x0, y0, x1, y1, props, count in ARMORY_ROOMS:
        done = 0
        for _ in range(count * 80):
            if done >= count:
                break
            x, y = rng.uniform(x0 + 0.8, x1 - 0.8), rng.uniform(y0 + 0.8, y1 - 0.8)
            if any(bx0 <= x <= bx1 and by0 <= y <= by1 for bx0, by0, bx1, by1 in blocked):
                continue
            if near_wall(x, y) or any(abs(x - px) + abs(y - py) < 2.4 for px, py in placed):
                continue
            if any(abs(x - a) + abs(y - b_) < 4 for a, b_ in ARMORY_ALTARS + [ARMORY_BOSS]):
                continue
            decor.append((props[done % len(props)], _acell(ax, ay, x, y)))
            placed.append((x, y))
            done += 1
    # torches along the walls, a little in from them
    for (x0, y0), (x1, y1) in ARMORY_WALLS:
        if y0 == y1:
            for x in range(min(x0, x1) + 3, max(x0, x1) - 2, 8):
                for dy in (0.9, -0.9):
                    if 0.5 < y0 + dy < ARMORY - 0.5 and not near_wall(x, y0 + dy * 2.2):
                        b.gen_objects.append((("id", 328), _acell(ax, ay, x, y0 + dy), 76))
                        break
        else:
            for y in range(min(y0, y1) + 3, max(y0, y1) - 2, 8):
                for dx in (0.9, -0.9):
                    if 0.5 < x0 + dx < ARMORY - 0.5 and not near_wall(x0 + dx * 2.2, y):
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
    if getattr(b, "armory_json", None):
        return _armory_after_grid_json(b, grid)
    off = 1
    for (x0, y0), (x1, y1) in ARMORY_WALLS + ARMORY_INNER:
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
    for x, y in ARMORY_PILLARS:
        X, Y = (ax + off + x) * SUB, (ay + off + y) * SUB
        for yy in range(Y - 1, Y + 2):
            for xx in range(X - 1, X + 2):
                if grid.in_bounds(xx, yy):
                    grid.cells[yy][xx] = WALL
    for name, (cx, cy) in getattr(b, "decor", []):
        r = decor_block(name)
        if r <= 0:
            continue
        for y in range(cy - r // 2 - 1, cy + (r + 1) // 2):
            for x in range(cx - r + 1, cx + r):
                if grid.in_bounds(x, y) and abs(x - cx) / float(r) + abs(y - cy) / float(max(1, r * 0.8)) <= 1.2:
                    grid.cells[y][x] = WALL
    for a in ARMORY_ALTARS:
        c = drlg.near_walkable(grid, _acell(ax, ay, *a), 12)
        if c:
            b.objects.append(("armory_altar", c, 76, len([o for o in b.objects if o[0] == "armory_altar"]) % 5))
    b.armory_boss = drlg.near_walkable(grid, _acell(ax, ay, *ARMORY_BOSS), 12)
    b.armory_spider = drlg.near_walkable(grid, _acell(ax, ay, *ARMORY_SPIDER), 12)


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
    # his loot: Andariel's treasure class (for this difficulty), rolled at his own level
    at = actworld._template(world, "andariel", lvl + 4)
    if at is not None:
        m.tc, m.tc_quest = at.get("tc"), at.get("tc_quest")
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
