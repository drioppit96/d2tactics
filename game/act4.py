"""Act 4 built from Diablo 2's own presets.

* World "mesa": the Pandemonium Fortress (Fortress.ds1), its transition FortMesa, the Outer
  Steppes, the Plains of Despair and the City of the Damned - areas of 8x8-tile blocks with
  D2's mesa border presets (Border1-12 a/b/c, the "o" ones where two areas meet) and their own
  fills (Outer / Mid / Chaos + pits), Izual's spot in the Plains and the lava warp in the City.
* World "lava": the River of Flame - a maze of D2's 24x24 lava rooms (the Hellforge rooms, the
  warp back up to the City) - running straight into the Chaos Sanctum: its bridge, entry, the
  four wings and the heart where Diablo waits.
"""
import random

from . import act1, drlg
from .act1 import SUB, MazeKit, _grow, _canon, stamp, Built, make_grid
from .drlg import Canvas, block_area, pick_existing

A4 = "act4\\"
M = A4 + "mesa\\"
MESA_LT = "Act 4 - Mesa"
LAVA_LT = "Act 4 - Lava"
B = 8

MAZES = {
    "lava": dict(folder=A4 + "lava\\", prefix="lava", lvltype=LAVA_LT, variants=("", "2"),
                 roles={"prev": "warpmesa{n}", "forge": "forge{d}"}, role_exits={"prev": "n"}),
}
act1.MAZES.update(MAZES)
DUNGEONS = {}
WORLD_OF = {}


def _mesa_spec(lid, openings):
    kind = {104: "outer", 105: "mid", 106: "chaos"}[lid]
    pit = {104: "outpit", 105: "midpit", 106: None}[lid]

    def var(n, letters="abc"):
        return [M + "border%d%s.ds1" % (n, c) for c in letters]
    border = {"s": var(1), "w": var(2), "n": var(3), "e": var(4),
              ("s", "w"): var(5), ("n", "w"): var(6), ("n", "e"): var(7), ("s", "e"): var(8)}
    open_border = {"s": [M + "border1o.ds1"], "w": [M + "border2o.ds1"], "n": [M + "border3o.ds1"],
                   "e": [M + "border4o.ds1"]}
    T = kind.title()
    fills = []
    for size, w, h in (("24X24", 3, 3), ("16X16", 2, 2), ("16X08", 2, 1), ("08X16", 1, 2), ("08X08", 1, 1)):
        fills.append(([M + "%s%s_%d.ds1" % (T, size, i) for i in range(8)], w, h))
        if pit and size in ("16X16", "08X08"):
            fills.append(([M + "%s%s_%d.ds1" % (pit, size, i) for i in range(4)], w, h))
    specials = []
    if lid == 105:
        specials.append(([M + "mid08x08izual.ds1"], 1, 1, None))
    if lid == 106:
        specials.append(([M + "warplava.ds1", M + "warplava1.ds1"], 1, 1, None))
    return dict(lvltype=MESA_LT, ground="mesa", border=border, open_border=open_border, openings=openings,
                specials=specials, fills=fills, fill_chance=0.7)


def build_mesa(kit, seed=None, content=None):
    # tile layout: Fortress + FortMesa (west), Outer Steppes east of them, Plains north of the Steppes,
    # the City of the Damned north of the Plains
    xs, ys = 40, 144             # Outer Steppes (10 x 8 blocks)
    xp, yp = 48, 64              # Plains of Despair (8 x 10)
    xc, yc = 40, 0               # City of the Damned (10 x 8)
    fort_y = ys + 16
    W, H = xs + 80, ys + 64
    cv = Canvas(kit, W, H, 4, seed)
    rng, b = cv.rng, cv.b
    cv.set_ground("mesa", M + "outer08x08_0.ds1", MESA_LT)
    fort = kit.ds1(A4 + "fort\\fortress.ds1")
    if fort is None:
        raise FileNotFoundError("Pandemonium Fortress layout (act4\\fort\\fortress.ds1) not found")
    cv.put(A4 + "fort\\fortress.ds1", 0, fort_y, 103, "Act 4 - Town")
    b.town_rect = (0, fort_y * SUB, 32 * SUB, (fort_y + 24) * SUB)
    b.areas[103] = b.town_rect
    cv.put(M + "fortmesa.ds1", 32, fort_y, 104, MESA_LT)
    pass_sp = 88                 # absolute tile x of the Steppes <-> Plains passage
    pass_pc = 80                 # ... of the Plains <-> City passage
    block_area(cv, 104, xs, ys, 10, 8, B, _mesa_spec(104, {"w": (3, 1), "n": ((pass_sp - xs) // B, 0)}))
    block_area(cv, 105, xp, yp, 8, 10, B, _mesa_spec(105, {"s": ((pass_sp - xp) // B, 0),
                                                       "n": ((pass_pc - xp) // B, 0)}))
    block_area(cv, 106, xc, yc, 10, 8, B, _mesa_spec(106, {"s": ((pass_pc - xc) // B, 0)}))
    x0, y0, x1, y1 = b.areas[104]
    b.areas[104] = (32 * SUB, y0, x1, y1)        # the transition belongs to the Steppes
    grid = cv.finish()
    drlg.ensure_connected(b, grid, [(103, 104), (104, 105), (105, 106)], cv.ground_kit("mesa"), rng)
    drlg.ensure_waypoints(b, grid, 4)
    return b, grid, rng


# ---------------------------------------------------------------- the River of Flame + the Chaos Sanctum
R = 24          # lava / sanctum room size
SANCTUM = [((2, 0), ["wingn1", "wingn2"]), ((1, 1), ["wingw1", "wingw2"]), ((2, 1), ["heart"]),
           ((3, 1), ["winge1", "winge2"]), ((2, 2), ["wings1", "wings2"]), ((2, 3), ["entry1"]),
           ((2, 4), ["bridge1", "bridge2", "bridge3", "bridge4"]), ((2, 5), ["bridgelava"])]
SANCTUM_ROWS = 6


def build_lava(kit, seed=None, content=None):
    rng = random.Random(seed)
    mk = kit.mazes.get("lava")
    if mk is None:
        mk = kit.mazes["lava"] = MazeKit(kit, "lava")
    # the river: a maze of 13 rooms whose top middle room opens north into the sanctum's bridge
    for attempt in range(400):
        layout = _grow(13, rng, 5, 5)
        if (2, 0) not in layout:
            continue
        leaves = [c for c, ex in layout.items() if len(ex) == 1 and c != (2, 0)]
        rng.shuffle(leaves)
        assign = {}
        for role in ("prev", "forge"):
            cand = [c for c in leaves if c not in assign and mk.role_room(role, layout[c], rng) is not None]
            if cand:
                assign[cand[0]] = role
        if len(assign) == 2:
            break
    layout[(2, 0)] = set(layout[(2, 0)]) | {"n"}
    W, H = 5 * R, (SANCTUM_ROWS + 5) * R
    b = Built(W + 1, H + 1)
    from .acts import apply_act_tables
    apply_act_tables(b, 4, kit)
    oy = SANCTUM_ROWS * R
    rooms = {}
    for (rx, ry), ex in layout.items():
        role = assign.get((rx, ry))
        ds = mk.role_room(role, ex, rng) if role else None
        if ds is None:
            ds = rng.choice(mk.rooms[frozenset(_canon(ex))])
        stamp(b, ds, kit.tiles_for(ds, LAVA_LT), rx * R, oy + ry * R, rng, 107)
        if role:
            rooms[role] = (rx * R, oy + ry * R, R, R)
    for (cx, cy), names in SANCTUM:
        name = pick_existing(kit, [A4 + "diab\\%s.ds1" % n for n in names], rng)
        if name:
            ds = kit.ds1(name)
            stamp(b, ds, kit.tiles_for(ds, LAVA_LT), cx * R, cy * R, rng, 108)
    b.areas[108] = (R * SUB, 0, 4 * R * SUB, oy * SUB)
    b.areas[107] = (0, oy * SUB, W * SUB, H * SUB)
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    # Diablo waits at the heart; the three seal bosses in the wings
    heart = drlg.near_walkable(grid, ((2 * R + R // 2) * SUB, (R + R // 2) * SUB), 60)
    if heart:
        b.presets.append(("diablo", heart, 108))
    for (cx, cy), boss in (((1, 1), "Grand Vizier of Chaos"), ((2, 0), "Lord De Seis"), ((3, 1), "Infector of Souls")):
        c = drlg.near_walkable(grid, ((cx * R + R // 2) * SUB, (cy * R + R // 2) * SUB), 60)
        if c:
            b.presets.append((boss, c, 108))
    gds, gcodes = drlg.ground_codes(kit, A4 + "lava\\lavans.ds1")
    gk = drlg.GroundKit(kit, gds, gcodes, LAVA_LT)
    drlg.ensure_connected(b, grid, [(107, 108)], gk, rng)
    drlg.ensure_waypoints(b, grid, 4)
    b.role_rooms = rooms
    return b, grid, rng
