"""Act 5 built from Diablo 2's own presets.

* World "siege": Harrogath (townWest), the Bloody Foothills - D2's siege strips (to town, 13
  strips, to the barricade) - the Rigid (Frigid) Highlands and the Arreat Plateau: areas of
  16x16-tile blocks with the barricade cliff borders, entrance / exit pieces between them, the
  barricades, prisons, waypoints and 8x8 fillers (farms, ruins, lakes) of D2.
* World 117: the Frozen Tundra (snow pieces), between the Glacial Trail and the Ancients' Way.
* Ice caves (Crystalline Passage, Glacial Trail, Ancients' Way) from D2's ice rooms, the Frozen
  River (Anya) and the small caves, Arreat Summit, Nihlathak's Temple and its halls (rings of
  four 40x40 rooms) and Halls of Vaught, the Worldstone Keep (D2's Baal rooms), the Throne of
  Destruction and the Worldstone Chamber.
"""
import random

from . import act1, drlg
from .act1 import SUB, build_maze, Built, stamp, make_grid
from .drlg import Canvas, block_area, pick_existing

X = "expansion\\"
S = X + "siege\\"
BAR_LT = "Act 5 - Barricade"
SIEGE_LT = "Act 5 - Siege"
B = 16

MAZES = {
    "ice": dict(folder=X + "icecave\\", prefix="ice", lvltype="Act 5 - Ice Caves", variants=("01", "02", "03", "04"),
                roles={"prev": "ice{d}back{n}", "next": "ice{d}ahead{n}", "down": "ice{d}down{n}", "way": "ice{d}way"}),
    "baal": dict(folder=X + "baallair\\", prefix="baal", lvltype="Act 5 - Baal", variants=("01", "02", "03"),
                 roles={"prev": "baal{x}up{n}", "next": "baal{d}down{n}", "way": "baal{d}way"}),
}
act1.MAZES.update(MAZES)
ICE = X + "icecave\\"
TEMPLE = X + "wildtemple\\"
DUNGEONS = {
    113: dict(kit="ice", rooms=12, roles=["prev", "next", "down", "way"], act=5),
    114: dict(kit="preset", folder=ICE, files=["riverice%02d.ds1" % i for i in range(1, 9)], lvltype="Act 5 - Ice Caves", act=5),
    115: dict(kit="ice", rooms=12, roles=["prev", "next", "down", "way"], act=5),
    116: dict(kit="preset", folder=ICE, files=["poolroom%02d.ds1" % i for i in range(1, 7)], lvltype="Act 5 - Ice Caves", act=5),
    118: dict(kit="ice", rooms=12, roles=["prev", "next", "down", "way"], act=5),
    119: dict(kit="preset", folder=ICE, files=["poolroom%02da.ds1" % i for i in range(1, 7)], lvltype="Act 5 - Ice Caves", act=5),
    120: dict(kit="preset", folder=X + "mountaintop\\", files=["mtntop.ds1"], lvltype=BAR_LT, act=5),
    121: dict(kit="preset", folder=TEMPLE, files=["tempenter.ds1"], lvltype="Act 5 - Temple", act=5),
    122: dict(kit="temple", act=5),
    123: dict(kit="temple", act=5, waypoint=True),
    124: dict(kit="preset", folder=TEMPLE, files=["nihle.ds1", "nihln.ds1", "nihls.ds1", "nihlw.ds1"], lvltype="Act 5 - Temple", act=5),
    128: dict(kit="baal", rooms=12, roles=["prev", "next"], act=5),
    129: dict(kit="baal", rooms=12, roles=["prev", "next", "way"], act=5),
    130: dict(kit="baal", rooms=12, roles=["prev", "next"], act=5),
    131: dict(kit="preset", folder=X + "baallair\\", files=["wthrone.ds1"], lvltype="Act 5 - Baal", act=5),
    132: dict(kit="preset", folder=X + "baallair\\", files=["wstone01.ds1"], lvltype="Act 5 - Baal", act=5),
}
WORLD_OF = {i: i for i in DUNGEONS}


def build_level(kit, level_id, seed=None):
    spec = dict(DUNGEONS[level_id])
    if spec["kit"] == "temple":
        return build_temple(kit, level_id, spec, seed)
    if spec["kit"] == "preset":
        b, grid, rng = act1.build_preset(kit, level_id, spec, seed)
    else:
        b, grid, rng = build_maze(kit, level_id, spec, seed)
    rooms = getattr(b, "role_rooms", {})
    drlg.ensure_waypoints(b, grid, 5, {level_id: rooms.get("way")})
    whole = (0, 0, b.tm.tw * SUB, b.tm.th * SUB)
    centre = drlg.near_walkable(grid, ((whole[0] + whole[2]) // 2, (whole[1] + whole[3]) // 2), 80)
    if level_id == 114 and centre:
        b.objects.append(("anya", centre, 114, -1))            # Anya, frozen in the river
    if level_id == 124 and centre:
        b.presets.append(("nihlathakboss", centre, 124))       # D2 puts Nihlathak here by code
    if level_id == 131 and centre:
        b.objects.append(("portal", centre, 131, 132))         # Baal's portal: open once the throne is cleared
    if level_id == 132:
        c = drlg.near_walkable(grid, (whole[2] // 2, whole[3] - 40), 80)
        if c:
            b.objects.append(("portal", c, 132, 131))          # back to the Throne (you arrive next to it)
    return b, grid, rng


def build_temple(kit, level_id, spec, seed=None):
    """Nihlathak's halls: four 40x40 rooms around the middle; the way up is always the SE room."""
    rng = random.Random(seed)
    corners = {(0, 0): "nw", (1, 0): "ne", (0, 1): "sw", (1, 1): "se"}
    down = rng.choice(["ne", "nw", "sw"])
    way = rng.choice([c for c in ("ne", "nw", "sw") if c != down]) if spec.get("waypoint") else None
    b = Built(81, 81)
    from .acts import apply_act_tables
    apply_act_tables(b, 5, kit)
    for (rx, ry), c in corners.items():
        if c == "se":
            names = ["tempse01", "tempse02"]
        elif c == down:
            names = ["temp%sdown" % c]
        elif c == way:
            names = ["temp%sway" % c]
        else:
            names = ["temp%s01" % c, "temp%s02" % c]
        name = pick_existing(kit, [TEMPLE + n + ".ds1" for n in names], rng)
        if name:
            ds = kit.ds1(name)
            stamp(b, ds, kit.tiles_for(ds, "Act 5 - Temple"), rx * 40, ry * 40, rng, level_id, keep_edges=False)
    b.areas[level_id] = (0, 0, 80 * SUB, 80 * SUB)
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    drlg.ensure_waypoints(b, grid, 5)
    return b, grid, rng


# ---------------------------------------------------------------- outdoors
def _barricade_spec(lid, snow, specials, openings=None):
    brd = (S + "brdr_snow%02dc.ds1") if snow else (S + "brdr%02dc.ds1")
    rav = (S + "brdr_snow%02dr.ds1") if snow else (S + "brdr%02dr.ds1")
    side = lambda n: [brd % n, rav % n]
    border = {"s": side(1), "w": side(2), "n": side(3), "e": side(4),
              ("s", "w"): side(5), ("n", "w"): side(6), ("n", "e"): side(7), ("s", "e"): side(8)}
    pre = "snowbarr" if snow else "newbarr"
    barr = [S + "%s%s%d.ds1" % (pre, k, i) for k in ("AA", "BB", "CC", "DD", "AB", "BA", "CD", "DC", "BR", "AR",
                                                       "FB", "FA", "CR", "DR", "FC", "FD") for i in (1, 2)]
    barr = drlg.full_pieces(_KIT[0], barr, BAR_LT) if _KIT else barr
    return dict(lvltype=BAR_LT, ground="snow" if snow else "dirt", border=border, specials=specials,
                fills=[(barr, 1, 1)], fill_chance=0.45, openings=openings or {})


_KIT = []


FILLERS = {"dirt": [S + "farm%d.ds1" % i for i in range(1, 9)] + [S + "farm%da.ds1" % i for i in range(1, 9)] +
           [X + "ruins\\northhouse%d.ds1" % i for i in range(1, 9)] + [X + "ruins\\westhouse%d.ds1" % i for i in range(1, 9)],
           "snow": [S + "lake%d.ds1" % i for i in range(1, 9)]}


def _sprinkle(cv, lid, x0, y0, bw, bh, kind):
    """D2's 8x8 fillers (farms, ruins, lakes) on some of the plain blocks."""
    rng = cv.rng
    for by in range(1, bh - 1):
        for bx in range(1, bw - 1):
            tx, ty = x0 + bx * B, y0 + by * B
            if rng.random() < 0.35 and all((tx + i, ty + j) not in cv.b.tm.walls for i in range(B) for j in range(B)):
                name = pick_existing(cv.kit, FILLERS[kind], rng)
                if name:
                    cv.put(name, tx + rng.choice((0, 8)), ty + rng.choice((0, 8)), lid, BAR_LT)


def build_siege(kit, seed=None, content=None):
    _KIT[:] = [kit]
    strips = [S + "striptownsiege.ds1"] + [S + "strip%02d.ds1" % i for i in range(1, 14)] + [S + "stripseigebar.ds1"]
    x_hi = 40 + 16 * len(strips)                  # the Rigid Highlands start here
    x_pl = x_hi + 8 * B                            # ... the Arreat Plateau here
    W, H = x_pl + 8 * B, 5 * B
    cv = Canvas(kit, W, H, 5, seed)
    rng, b = cv.rng, cv.b
    cv.set_ground("dirt", S + "newbarrAA1.ds1", BAR_LT)
    cv.set_ground("snow", S + "snowbarrAA1.ds1", BAR_LT)
    town = kit.ds1(X + "town\\townwest.ds1")
    if town is None:
        raise FileNotFoundError("Harrogath layout (expansion\\town\\townwest.ds1) not found")
    cv.put(X + "town\\townwest.ds1", 0, 20, 109, "Act 5 - Town")
    b.town_rect = (0, 20 * SUB, 40 * SUB, 60 * SUB)
    b.areas[109] = b.town_rect
    # the Bloody Foothills: D2's siege strips side by side
    for i, name in enumerate(strips):
        cv.put(name, 40 + i * 16, 16, 110, SIEGE_LT)
    b.areas[110] = (40 * SUB, 0, x_hi * SUB, H * SUB)
    # the Rigid Highlands: from the siege (west) to the Plateau (east)
    hi_specials = [([S + "siege2barricade.ds1"], 1, 2, (0, 1)), ([S + "brdr16x32top.ds1"], 1, 2, (7, 1)),
                   ([S + "siegewaypoint1.ds1", S + "siegewaypoint2.ds1"], 1, 1, None)] + \
                  [([S + "sharptooth%s.ds1" % k for k in ("aa", "bb", "cc", "dd", "ab", "ba", "cd", "dc")], 1, 1, None)] * 3
    block_area(cv, 111, x_hi, 0, 8, 5, B, _barricade_spec(111, False, hi_specials))
    _sprinkle(cv, 111, x_hi, 0, 8, 5, "dirt")
    # the Arreat Plateau: from the Highlands (west) to the Crystalline Passage
    pl_specials = [([S + "brdr16x32btm.ds1"], 1, 2, (0, 1)), ([ICE + "westentrance_snow.ds1", ICE + "westentrance_dirt.ds1"], 1, 2, (7, 2)),
                   ([S + "snowwaypoint1.ds1", S + "snowwaypoint2.ds1"], 1, 1, None)]
    block_area(cv, 112, x_pl, 0, 8, 5, B, _barricade_spec(112, True, pl_specials))
    _sprinkle(cv, 112, x_pl, 0, 8, 5, "snow")
    grid = cv.finish()
    drlg.ensure_connected(b, grid, [(109, 110), (110, 111), (111, 112)], cv.ground_kit("dirt"), rng)
    drlg.ensure_waypoints(b, grid, 5)
    return b, grid, rng


def build_tundra(kit, seed=None, content=None):
    _KIT[:] = [kit]
    cv = Canvas(kit, 8 * B, 5 * B, 5, seed)
    rng, b = cv.rng, cv.b
    cv.set_ground("snow", S + "snowbarrAA1.ds1", BAR_LT)
    specials = [([ICE + "northexit_snow.ds1"], 2, 1, (2, 0)), ([ICE + "northentrance_snow.ds1"], 2, 1, (5, 4)),
                ([S + "snowwaypoint1.ds1", S + "snowwaypoint2.ds1"], 1, 1, None)]
    block_area(cv, 117, 0, 0, 8, 5, B, _barricade_spec(117, True, specials))
    _sprinkle(cv, 117, 0, 0, 8, 5, "snow")
    grid = cv.finish()
    drlg.ensure_waypoints(b, grid, 5)
    return b, grid, rng
