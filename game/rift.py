"""Red portals (this game's own - not in D2).

Once Andariel is dead a red portal opens beside Gheed in the Rogue Encampment. It leads into a
rift: one randomly built floor made of the tiles of any act - a cave, a crypt, a jail, a tomb, a
sewer, Baal's halls, an open plain... Every floor holds up to six kinds of monster drawn from the
whole game and a boss somewhere at the far end. Kill the boss and another red portal tears open,
leading one floor deeper. It never ends.

Everything in a rift is at the hero's own level: a Fallen down there is as dangerous as anything
else, and a Pit Lord is no worse, because D2's own MonLvl table gives each monster the life,
damage, attack rating, defense and experience of that level (d2content.monster_template(level=...)).

Floors are level ids 900 and up, one per depth, built from the hero's own rift seed, so the
same hero walking the same depth twice meets the same floor.
"""
import random
from collections import deque

from .grid import chebyshev

BASE = 900                 # level id of rift floor 1
MAX_FLOORS = 666           # Infernal Rift 1 .. 666
KINDS = 6                  # kinds of monster on one floor
BOSS_EVERY = 10            # every tenth floor is guarded by one of D2's act bosses
ACT_BOSSES = ["andariel", "duriel", "mephisto", "diablo", "baalcrab"]
FIELD = "@field"           # the open-plain floor (no maze kit)

# where a floor can be built from: maze kit (act1.MAZES) or FIELD, the act whose palette it wears,
# and what the floor is called. Every act of the game is in here.
PLACES = [
    ("cave", 1, "Fetid Cavern"),
    ("crypt", 1, "Forgotten Crypt"),
    ("jail", 1, "Iron Halls"),
    ("catacombs", 1, "Black Catacomb"),
    ("barracks", 1, "Ruined Barracks"),
    (FIELD, 1, "Open Plain"),
    ("sewer", 2, "Stinking Sewer"),
    ("tomb", 2, "Sunken Tomb"),
    ("lair", 2, "Maggot Lair"),
    ("a3dung", 3, "Drowned Dungeon"),
    ("a3sewer", 3, "Kurast Sewer"),
    ("meph", 3, "Hall of Hate"),
    ("ice", 5, "Glacial Cave"),
    ("baal", 5, "Worldstone Halls"),
]
PLANS = {}                 # level id -> the floor's plan
_POOL = []                 # every monster kind the game spawns, across all acts

YELLOW = (255, 230, 90)
RED = (235, 90, 70)


# ------------------------------------------------------------------ ids
def is_rift(lid):
    return isinstance(lid, int) and BASE <= lid < BASE + MAX_FLOORS


def level_id(depth):
    return BASE + max(0, min(MAX_FLOORS - 1, depth - 1))


def depth_of(lid):
    return lid - BASE + 1


def is_field(lid):
    return is_rift(lid) and plan(lid)["kit"] == FIELD


def act_of(lid):
    return plan(lid)["act"]


def name(lid):
    return "Infernal Rift %d" % plan(lid)["depth"]


# ------------------------------------------------------------------ the plan of one floor
def rift_seed(player):
    s = getattr(player, "rift_seed", None)
    if not s:
        s = random.randrange(1, 1 << 30)
        player.rift_seed = s
    return s


def plan(lid, player=None):
    """What this floor is: deterministic from the hero's rift seed and the depth."""
    p = PLANS.get(lid)
    if p is not None:
        return p
    depth = depth_of(lid)
    seed = rift_seed(player) if player is not None else 1
    rng = random.Random((seed * 1000003) ^ (depth * 7919))
    # every kind of place is seen once before any of them comes round again
    order = list(PLACES)
    random.Random(seed ^ ((depth - 1) // len(PLACES))).shuffle(order)
    kit, act, flavour = order[(depth - 1) % len(PLACES)]
    p = dict(depth=depth, seed=rng.randrange(1 << 30), kit=kit, act=act, flavour=flavour,
             rooms=rng.randint(4, 6), mlvl=None, roster=None, boss=None, start=None, boss_cell=None,
             actboss=rng.choice(ACT_BOSSES) if depth % BOSS_EVERY == 0 else None)
    PLANS[lid] = p
    return p


def forget(player):
    """A new hero (or a new game): nothing of the old rift is kept."""
    PLANS.clear()


# ------------------------------------------------------------------ who lives there
def _pool(content, kit):
    """Every monster the game spawns anywhere, across all five acts (Levels.txt rosters), minus the
    act bosses - their stats are fixed in D2 and would not follow the hero's level."""
    if _POOL:
        return _POOL
    if content is None or kit is None:
        return []
    seen = []
    for r in (kit.levels or {}).values():
        for pre in ("mon", "nmon"):
            for i in range(1, 11):
                mid = (r.get("%s%d" % (pre, i), "") or "").lower()
                if mid and mid in content.monstats and mid not in seen:
                    row = content.monstats[mid]
                    if row.get("boss") == "1" or row.get("npc") == "1" or row.get("killable") != "1":
                        continue
                    if row.get("interact") == "1" or not (row.get("code") or "").strip():
                        continue
                    seen.append(mid)
    _POOL.extend(sorted(seen))
    return _POOL


def roster(lid, content, kit):
    p = plan(lid)
    if p["roster"] is None:
        pool = _pool(content, kit)
        if not pool:
            return []
        rng = random.Random(p["seed"] ^ 0x51ED)
        p["roster"] = rng.sample(pool, min(KINDS, len(pool)))
        p["boss"] = rng.choice(p["roster"])
    return list(p["roster"])


def monster_level(lid):
    """Every monster in a rift is the hero's own level."""
    return max(1, plan(lid)["mlvl"] or 1)


# ------------------------------------------------------------------ building a floor
def build_level(kit, lid, seed=None, player=None):
    from . import act1, tactics
    p = plan(lid, player)
    if player is not None:
        p["mlvl"] = max(1, getattr(player, "level", 1))
    rooms = p["rooms"]
    if tactics.ACTIVE:
        rooms = max(3, rooms - 2)               # the shrunken maps of tactics mode
    seed = p["seed"] if seed is None else seed
    if p["kit"] == FIELD:
        b, grid, rng = _build_field(kit, lid, seed, small=tactics.ACTIVE)
    else:
        spec = dict(kit=p["kit"], roles=[], act=p["act"], **_fit(kit, p["kit"], rooms, tactics.ACTIVE))
        try:
            b, grid, rng = act1.build_maze(kit, lid, spec, seed)
        except Exception:
            b, grid, rng = _build_field(kit, lid, seed, small=tactics.ACTIVE)
            p["kit"], p["act"], p["flavour"] = FIELD, 1, "Open Plain"
    b.npcs = []
    b.objects = []
    b.presets = []                              # no D2 set pieces: a rift has its own monsters
    b.gen_objects = [o for o in getattr(b, "gen_objects", [])]
    b.areas = {lid: (0, 0, b.tm.tw * 5, b.tm.th * 5)}
    _pick_ends(b, grid, p, rng)
    b.custom_start = p["start"]
    return b, grid, rng


# the shrunken-map rule: a floor is never wider than this many tiles (Act 1's small slot is 7
# blocks of 8 tiles; Act 2's is 8), whatever the size of one room of its kit
MAX_TILES = 56
SMALL_TILES = 44


def _fit(kit, name, rooms, small):
    """Rooms and maze bounds that keep a floor inside the shrunken-map size, whatever kit it uses."""
    from . import act1
    try:
        mk = kit.mazes.get(name) or act1.MazeKit(kit, name)
        kit.mazes[name] = mk
        side = max(mk.rw, mk.rh)
    except Exception:
        side = 16
    cap = (SMALL_TILES if small else MAX_TILES) // max(1, side)
    g = max(2, min(4, cap))
    return dict(rooms=max(2, min(rooms, g * g - 1)), grid=g)


def _build_field(kit, lid, seed, small=False):
    """An open plain: Act 1's wilderness ground inside its border ring, with a few fills."""
    from .act1 import BLOCK, SUB, Built, OutdoorKit, stamp, make_grid
    rng = random.Random(seed)
    size = 5 if small else 6
    b = Built(size * BLOCK + 1, size * BLOCK + 1)
    from .acts import apply_act_tables
    apply_act_tables(b, 1, kit)
    gds, gcodes = kit.grass()
    gtiles = kit.tiles_for(gds, "Act 1 - Wilderness")

    def put(nm, tx0, ty0):
        ds = kit.ds1(nm)
        if ds is None:
            return None
        stamp(b, ds, kit.tiles_for(ds, "Act 1 - Wilderness"), tx0, ty0, rng, lid)
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
            if put("Act1/Outdoors/%s%s.ds1" % (OutdoorKit.EDGE[side], rng.choice(["", "", "b", "c"])),
                   bx * BLOCK, by * BLOCK) is None:
                put("Act1/Outdoors/%s.ds1" % OutdoorKit.EDGE[side], bx * BLOCK, by * BLOCK)
    inner = [(bx, by) for bx in range(1, size - 1) for by in range(1, size - 1)]
    rng.shuffle(inner)
    fills = [f for f in OutdoorKit.FILLS["common"] if "FallCmp" not in f and "Camp" not in f]
    for bx, by in list(inner):
        if (bx, by) not in taken and rng.random() < 0.35:
            if put(rng.choice(fills), bx * BLOCK, by * BLOCK) is not None:
                taken.add((bx, by))
    for bx, by in inner:
        if (bx, by) in taken:
            continue
        for y in range(BLOCK):
            for x in range(BLOCK):
                main, sub = rng.choice(gcodes)
                t = gtiles.pick(0, main, sub, rng.randrange(1 << 16))
                if t:
                    b.tm.floor[(bx * BLOCK + x, by * BLOCK + y)] = t
        taken.add((bx, by))
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    return b, grid, rng


def _pick_ends(b, grid, p, rng):
    """Where you arrive and where the boss waits: the two ends of the floor."""
    cells = []
    for _ in range(4000):
        c = (rng.randrange(0, grid.w), rng.randrange(0, grid.h))
        if grid.walkable(*c):
            cells.append(c)
            if len(cells) >= 60:
                break
    if not cells:
        p["start"] = p["boss_cell"] = None
        return
    start = cells[0]
    far, _ = _bfs_far(grid, start)
    start, _ = _bfs_far(grid, far or start)     # the two ends of the longest walk
    boss, _ = _bfs_far(grid, start)
    # a few steps in from the very corner, so you arrive inside the floor and not on its wall
    p["start"] = _step_in(grid, start, 7)
    p["boss_cell"] = _step_in(grid, boss or far or start, 5)


def _step_in(grid, start, steps):
    """A walkable cell `steps` away from `start` (away from the map's edge)."""
    seen = {start}
    q = deque([(start, 0)])
    out = start
    while q:
        c, d = q.popleft()
        out = c
        if d >= steps:
            return c
        for nb in grid.neighbors(*c):
            if nb not in seen:
                seen.add(nb)
                q.append((nb, d + 1))
    return out


def _bfs_far(grid, start, cap=120000):
    """The walkable cell farthest from `start` (and how many cells were reached)."""
    seen = {start}
    q = deque([start])
    last = start
    while q and len(seen) < cap:
        c = q.popleft()
        last = c
        for nb in grid.neighbors(*c):
            if nb not in seen:
                seen.add(nb)
                q.append(nb)
    return last, len(seen)


# ------------------------------------------------------------------ the floor's boss
def after_build(world):
    """Called once a rift floor's World is built: its boss waits at the far end."""
    lid = world.level_id
    if not is_rift(lid):
        return
    from . import actworld, monmods
    p = plan(lid)
    roster(lid, world.content, getattr(world.info, "kit", None))
    mid = p.get("boss")
    cell = p.get("boss_cell")
    if not mid or cell is None:
        return
    taken = {m.pos for m in world.monsters}
    lvl = monster_level(lid)
    # nothing stands on top of the arrival spot
    start = p.get("start")
    if start:
        for m in list(world.monsters):
            if not getattr(m, "ally", False) and m.ai != "npc" and chebyshev(m.pos, start) < 14:
                world.monsters.remove(m)
    spot = world._free_cell_near(cell, 8) or cell
    if p.get("actboss"):
        # every tenth floor: one of D2's act bosses, brought down (or up) to the hero's own level
        boss = actworld._spawn(world, p["actboss"], spot, lvl, taken)
        if boss is not None:
            scale_to_level(world, boss, lvl)
            boss.rift_boss = True
            boss.max_hp = int(boss.max_hp * 1.5)
            boss.hp = boss.max_hp
            world.log("%s guards this floor." % boss.name, RED)
            return
    boss = actworld._spawn(world, mid, spot, lvl, taken)
    if boss is None:
        return
    monmods.make_unique(world, boss)
    boss.rift_boss = True
    boss.max_hp = int(boss.max_hp * 2.5)        # a floor's keeper: it takes a fight
    boss.hp = boss.max_hp
    boss.name = "%s, Keeper of the Rift" % boss.name
    for c in actworld._spots(world, spot, 5, taken, radius=5):
        u = actworld._spawn(world, mid, c, lvl, taken)
        if u is not None:
            u.minion_of = boss
            u.color_shift = getattr(boss, "color_shift", 0)
            monmods.pass_aura(boss, u)


def _mlval(content, lvl, col):
    """One column of D2's MonLvl table at `lvl` (the difficulty's own column)."""
    row = content.monlvl.get(max(1, int(lvl))) or content.monlvl.get(1) or {}
    sfx = getattr(content, "sfx", "") or ""
    try:
        return max(1, int((row.get(col + sfx) or row.get(col) or "1").strip() or 1))
    except (ValueError, AttributeError):
        return 1


def scale_to_level(world, u, target):
    """D2 pins an act boss's stats to its own level; in a rift it follows the hero's level instead,
    by the same MonLvl ratios every other monster is built from."""
    c = world.content
    native = max(1, getattr(u, "level", 1))
    if c is None or native == int(target):
        return
    def ratio(col):
        return _mlval(c, target, col) / float(_mlval(c, native, col))
    hp, dm, th, ac, xp = (ratio(k) for k in ("hp", "dm", "th", "ac", "xp"))
    u.max_hp = max(1, int(u.max_hp * hp))
    u.hp = u.max_hp
    lo, hi = u.dmg
    u.dmg = (max(1, int(lo * dm)), max(2, int(hi * dm)))
    u.ar = max(5, int(u.ar * th))
    u.defense = max(0, int(getattr(u, "defense", 0) * ac))
    u.xp_value = max(1, int(getattr(u, "xp_value", 1) * xp))
    u.level = int(target)
    u.drop_level = int(target)


# ------------------------------------------------------------------ the portals
def available(player):
    """Andariel is dead: the red portal can open."""
    q = getattr(player, "quests", None) or {}
    return q.get("andariel") in ("cleared", "done")


def ensure_portal(world):
    """The red portal stands beside Gheed in the Rogue Encampment once Andariel has fallen."""
    p = world.player
    if world.level_id != 1 or not available(p):
        return
    depth = 1                                   # leaving the rift resets the count: town always opens Rift 1
    if int(getattr(p, "rift_depth", 0) or 0) or getattr(p, "_in_rift", False):
        from . import riftmap                   # back in town: that run is over, the next one is new
        p._in_rift = False
        p.rift_depth = 0
        p.rift_seed = None
        riftmap.clear(p)
        PLANS.clear()
        world.objects[:] = [o for o in world.objects
                            if not (o.get("kind") == "portal" and is_rift(o.get("target")))]
    if any(o.get("kind") == "portal" and is_rift(o.get("target")) for o in world.objects):
        return
    plan(level_id(depth), p)                    # (the floor is the hero's own, from his rift seed)
    gheed = next((n for n in world.npcs if getattr(n, "npc", "") == "gheed"), None)
    # down-screen is +x +y: two portal heights clear of Gheed, so it no longer covers him
    near = (gheed.x + 7, gheed.y + 6) if gheed is not None else (p.x + 7, p.y + 6)
    cell = world._free_cell_near(near, 4) or world._free_cell_near(near, 8)
    if cell is None:
        return
    world.objects.append(dict(kind="portal", cell=cell, level=1, oid=0, used=False,
                              target=level_id(depth)))


def on_killed(world, unit):
    """The floor's keeper is dead: a red portal opens, one floor deeper."""
    if unit is None or not getattr(unit, "rift_boss", False) or not is_rift(world.level_id):
        return
    if any(getattr(m, "rift_boss", False) and m.alive for m in world.monsters):
        return                                   # (Crowned: the keeper has a twin - both must fall)
    p = world.player
    depth = depth_of(world.level_id) + 1
    if depth > MAX_FLOORS:
        world.log("Infernal Rift %d was the last. Nothing deeper answers." % MAX_FLOORS, RED)
        return
    p.rift_depth = depth - 1                     # (the deepest floor beaten)
    if any(o.get("kind") == "portal" and is_rift(o.get("target")) for o in world.objects):
        return
    cell = world._free_cell_near(unit.pos, 8) or world._free_cell_near(p.pos, 6)
    if cell is None:
        return
    plan(level_id(depth), p)
    world.objects.append(dict(kind="portal", cell=cell, level=world.level_id, oid=0, used=False,
                              target=level_id(depth)))
    world.emit("nova", p, cell, 3, "fire")
    world.log("A red portal tears open. Infernal Rift %d awaits." % depth, RED)


def on_enter(world, lid):
    """A rift floor starts clean, and leaving the rift ends the run: the count starts at 1 again."""
    from . import riftmap
    p = world.player
    if is_rift(lid):
        p._in_rift = True
        world._rift_fought = False
        if getattr(p, "rift_map_depth", None) != depth_of(lid):
            riftmap.clear(p)                     # a new floor carries no modifiers of its own
        world.log("%s: everything here is your equal." % name(lid), YELLOW)
        if plan(lid).get("actboss"):
            world.log("Something out of the old world waits at the far end.", RED)
        return
    if getattr(p, "_in_rift", False):
        p._in_rift = False
        p.rift_depth = 0                         # left the rift: the next red portal is Infernal Rift 1
        p.rift_seed = None                       # and a new run is built from a new seed
        riftmap.clear(p)
        PLANS.clear()
        world.log("The rift collapses behind you.", RED)
