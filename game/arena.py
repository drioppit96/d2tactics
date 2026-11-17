"""The arenas behind two of Sanctuary's pedestals.

Neither is a place in Diablo: they are rooms the Tree opens, a walled patch of ground with one
thing standing in it and no way out but the way you came. Both are built fresh every time, from
the hero's own roll, so the fills and the ground are never quite the same twice.

    BOSS_LEVEL   one of the Great Evils, alone
    UBER_LEVEL   a key holder and the ten champions that keep it

    build(kit, level_key, seed, content)   the map
    populate(world)                        what stands in it
"""
import random

from .grid import chebyshev

BOSS_LEVEL = 138
UBER_LEVEL = 139
LEVELS = (BOSS_LEVEL, UBER_LEVEL)

NAMES = {BOSS_LEVEL: "The Black Road", UBER_LEVEL: "The Warded Vault"}

#: the Great Evils, by the boss tag game/actworld.py gives them
BOSSES = ("andariel", "duriel", "mephisto", "diablo", "baal")

#: the three that hold a key in D2: who they are, what they are, and where they normally stand -
#: the guard is drawn from that level's own roster, so it is the company they usually keep
KEEPERS = [("The Countess", "countess", 25),
           ("Nihlathak", "nihlathakboss", 124),
           ("The Summoner", "summoner", 74)]

#: what stands around a key holder
GUARDS = 10

COLOR = (199, 179, 119)


def is_arena(lid):
    return lid in LEVELS


def name(lid):
    return NAMES.get(lid)


# ---------------------------------------------------------------- the room
def build(kit, level_key, seed=None, content=None):
    """A small walled patch of Act 1 wilderness - four blocks across, a border ring and no exit.

    It is the Moo Moo Farm's shape at a quarter of the size: D2's own edge and corner pieces
    round the outside, its fills scattered inside, and plain grass under everything else.
    """
    from .act1 import OutdoorKit, Built, stamp, make_grid, BLOCK
    from .d2level import SUB
    rng = random.Random(seed)
    size = 4                                     # 2x2 of room inside a ring of border blocks
    b = Built(size * BLOCK + 1, size * BLOCK + 1)
    b.areas[level_key] = (0, 0, size * BLOCK * SUB, size * BLOCK * SUB)
    gds, gcodes = kit.grass()
    gtiles = kit.tiles_for(gds, "Act 1 - Wilderness")

    def grass_block(tx0, ty0):
        for y in range(BLOCK):
            for x in range(BLOCK):
                main, sub = rng.choice(gcodes)
                t = gtiles.pick(0, main, sub, rng.randrange(1 << 16))
                if t:
                    b.tm.floor[(tx0 + x, ty0 + y)] = t

    def put(nm, tx0, ty0):
        ds = kit.ds1(nm)
        if ds is None:
            return None
        stamp(b, ds, kit.tiles_for(ds, "Act 1 - Wilderness"), tx0, ty0, rng, level_key)
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
            if vert and hor:
                put("Act1/Outdoors/%s.ds1" % OutdoorKit.CORNER[(vert, hor)], bx * BLOCK, by * BLOCK)
                continue
            side = vert or hor
            v = rng.choice(["", "", "b", "c"])
            if put("Act1/Outdoors/%s%s.ds1" % (OutdoorKit.EDGE[side], v), bx * BLOCK, by * BLOCK) is None:
                put("Act1/Outdoors/%s.ds1" % OutdoorKit.EDGE[side], bx * BLOCK, by * BLOCK)

    inner = [(bx, by) for bx in range(1, size - 1) for by in range(1, size - 1)]
    rng.shuffle(inner)
    fills = [f for f in OutdoorKit.FILLS["common"] if "FallCmp" not in f and "Camp" not in f]
    for bx, by in list(inner):
        # one block in three carries something, so no two visits look alike
        if (bx, by) not in taken and rng.random() < 0.34 and fills:
            if put(rng.choice(fills), bx * BLOCK, by * BLOCK) is not None:
                taken.add((bx, by))
    for bx, by in inner:
        if (bx, by) not in taken:
            grass_block(bx * BLOCK, by * BLOCK)
            taken.add((bx, by))

    b.presets = []                               # nothing the fills brought with them
    b.npcs = []
    b.objects = []
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    return b, grid, rng


# ---------------------------------------------------------------- what stands in it
def populate(world):
    """Put the arena's occupant in it, once, when the room is first entered."""
    lid = getattr(world, "level_id", None)
    if not is_arena(lid) or getattr(world, "_arena_done", False):
        return
    world._arena_done = True
    from . import actworld
    p = world.player
    rng = getattr(world, "rng", None) or random
    lvl = max(1, getattr(p, "level", 1))
    far = _far_cell(world, p.pos)
    taken = set(world.occupied())
    if lid == BOSS_LEVEL:
        tag = rng.choice(BOSSES)
        m = _spawn_boss(world, tag, far, lvl, taken)
        if m is not None:
            world.log("%s is here, and nothing else." % m.name, COLOR)
        return
    who, mid, home = rng.choice(KEEPERS)
    c = world.content
    shown = who
    try:
        row = (c.superuniques or {}).get(who.lower())
        if row:
            mid = row.get("class") or mid
            shown = (c.strings or {}).get(row.get("name") or who, who)
    except Exception:
        pass
    boss = actworld._spawn(world, mid, far, lvl + 3, taken, unique=True, name=shown)
    if boss is None:
        return
    boss.aware = True
    world.emit("place", boss, boss.pos)
    roster = []
    try:
        roster = [m for m in (world.info.roster(home) or []) if m] if world.info else []
    except Exception:
        roster = []
    roster = roster or [mid]
    kept = 0
    for radius in (7, 10, 14, 18):
        if kept >= GUARDS:
            break
        for spot in actworld._spots(world, boss.pos, GUARDS - kept, world.occupied(), radius=radius):
            g = actworld._spawn(world, rng.choice(roster), spot, lvl + 2,
                                set(world.occupied()), champion=True)
            if g is None:
                continue
            g.aware = True
            world.emit("place", g, g.pos)
            kept += 1
            if kept >= GUARDS:
                break
    world.log("%s, and %d of its own around it." % (shown, kept), COLOR)


def _spawn_boss(world, tag, cell, lvl, taken):
    from . import actworld
    mid = {"andariel": "andariel", "duriel": "duriel", "mephisto": "mephisto",
           "diablo": "diablo", "baal": "baalcrab"}.get(tag, tag)
    c = world.content
    if c is not None and mid not in (c.monstats or {}):
        mid = tag
    shown = mid
    try:
        row = (c.monstats or {}).get(mid) or {}
        key = row.get("namestr") or mid
        shown = (c.strings or {}).get(key, key)
    except Exception:
        pass
    m = actworld._spawn(world, mid, cell, lvl + 5, taken, unique=True, name=shown)
    if m is None:
        return None
    m.boss = tag
    m.aware = True
    world.emit("place", m, m.pos)
    return m


def _far_cell(world, from_cell):
    """Across the room from the way in, so the fight does not start on the doorstep."""
    best, far = None, -1
    g = world.grid
    for _ in range(400):
        c = (random.randrange(g.w), random.randrange(g.h))
        if not g.walkable(*c):
            continue
        d = chebyshev(c, from_cell)
        if d > far:
            best, far = c, d
    return best or world._free_cell_near(from_cell, 10) or from_cell
