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
BIG = False                # the autobattler's real-time floors: about twice the area (autobattler/runs.py sets it)
CONTENT = None             # the game's tables, for building outdoor floors (set with BIG)
# outdoor floors (BIG only): randmap's open-world themes, built from each act's own outdoor presets
OPEN_FLOORS = [("wild", 1, "Wild Moors"), ("desert", 2, "Scorched Waste"), ("jungle", 3, "Drowned Jungle"),
               ("slums", 3, "Rotting Slums"), ("burbs", 3, "Ruined Bazaar"), ("metro", 3, "Sunken Streets"),
               ("steppes", 4, "Burning Steppes"), ("plains", 4, "Plains of Ash"), ("damned", 4, "Damned Streets"),
               ("highlands", 5, "Frozen Highlands"), ("plateau", 5, "Windswept Plateau")]
OPEN_SHARE = 0.35          # about a third of the BIG floors are outdoors
#: the BIG floors' area, as a share of their full size (the D2 Autobattler sets 0.5: half as big)
AREA = 1.0


def _side(n, least=1):
    """A BIG floor's side of n (blocks, tiles) for its AREA."""
    return max(least, int(round(n * AREA ** 0.5)))


#: the D2 Autobattler: a floor's monsters take their level from the act, not from the hero
ACT_LEVELS = False
#: the act bosses' own levels on Normal, when MonStats can't be read
BOSS_LEVELS = {"andariel": 12, "duriel": 22, "mephisto": 26, "diablo": 40, "baalcrab": 60}
#: the D2 Autobattler: floors 51-60 are a sixth stretch in Act 5's places, its tenth floor Baal again
SIXTH = False


def _boss_level(act):
    mid = ACT_BOSSES[max(1, min(5, act)) - 1]
    c = CONTENT
    row = (getattr(c, "monstats", None) or {}).get(mid) if c is not None else None
    if row:
        sfx = getattr(c, "sfx", "") or ""
        try:
            v = int((row.get("level" + sfx) or row.get("level") or "").strip())
            if v > 0:
                return v
        except (ValueError, AttributeError):
            pass
    return BOSS_LEVELS[mid]


def _sixth(depth):
    return SIXTH and 51 <= ((max(1, int(depth)) - 1) % 60) + 1 <= 60


def act_level(depth):
    """The monsters' level on a floor: the ten floors of an act climb from just above the last
    act boss's level to this act's boss's level (Normal: Act 1 1-12, Act 2 13-22, Act 3 23-26,
    Act 4 27-30, Act 5 31-40; Nightmare and Hell by their own MonStats levels). After floor 50 the
    acts come round again, 40 levels higher each time round (at most 99)."""
    depth = max(1, int(depth))
    if _sixth(depth):
        # past Baal: from his level, ten more (and 70 more each time round)
        hi = _boss_level(5)
        i = (depth - 1) % 10
        return max(1, min(99, hi + i + 1 + 70 * ((depth - 1) // 60)))
    act = act_of_depth(depth)
    hi = _boss_level(act)
    lo = _boss_level(act - 1) + 1 if act > 1 else max(1, hi - 11)
    i = (depth - 1) % 10
    lvl = lo + (max(lo, hi) - lo) * i / 9.0
    lap = (depth - 1) // (60 if SIXTH else 50)
    return max(1, min(99, int(round(lvl)) + (70 if SIXTH else 40) * lap))


def act_of_depth(depth):
    """BIG floors follow the acts: 1-10 Act 1, 11-20 Act 2, 21-30 Act 3, 31-40 Act 4, 41-50 Act 5,
    then round again (51-60 Act 1 ...). The tenth floor of each is that act's boss."""
    if _sixth(depth):
        return 5
    return ((max(1, int(depth)) - 1) // 10) % (6 if SIXTH else 5) + 1 if not SIXTH else \
        min(5, ((max(1, int(depth)) - 1) % 60) // 10 + 1)

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
#: a floor keeper's life on top of D2's unique monster (the D2 Autobattler sets 1: D2's own)
KEEPER_LIFE = 2.5
_SEED = None               # the seed of the run being played (the hero's, once one is known)
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
def rift_seed(player=None):
    """The seed this run's floors are built from. Plenty of callers (the level's name, its act, its
    monster level) have no player to hand, so the run's seed is remembered here too - without that
    they would all fall back on the same fixed seed and every run would open on the same floor."""
    global _SEED
    if player is not None:
        s = getattr(player, "rift_seed", None)
        if not s:
            s = random.randrange(1, 1 << 30)
            player.rift_seed = s
        _SEED = s
        return s
    if not _SEED:
        _SEED = random.randrange(1, 1 << 30)
    return _SEED


def plan(lid, player=None):
    """What this floor is: deterministic from the hero's rift seed and the depth."""
    p = PLANS.get(lid)
    if p is not None:
        return p
    depth = depth_of(lid)
    seed = rift_seed(player)
    rng = random.Random((seed * 1000003) ^ (depth * 7919))
    kit, act, flavour = rng.choice(PLACES)      # each floor picks its own place, independently
    p = dict(depth=depth, seed=rng.randrange(1 << 30), kit=kit, act=act, flavour=flavour,
             rooms=rng.randint(4, 6), mlvl=None, roster=None, boss=None, start=None, boss_cell=None,
             actboss=rng.choice(ACT_BOSSES) if depth % BOSS_EVERY == 0 else None)
    if BIG:
        # the act of this stretch of ten floors: its own dungeons and outdoors, its own monsters,
        # and on the tenth floor its own boss at D2's own strength
        orng = random.Random(p["seed"] ^ 0x0BE1)
        act = act_of_depth(depth)
        inside = [x for x in PLACES if x[1] == act and x[0] != FIELD]
        outside = [x for x in OPEN_FLOORS if x[1] == act]
        if outside and (not inside or orng.random() < OPEN_SHARE):
            theme, act, flavour = orng.choice(outside)
            p.update(kit=FIELD, act=act, flavour=flavour, open=theme)
        elif inside:
            kit_, act, flavour = orng.choice(inside)
            p.update(kit=kit_, act=act, flavour=flavour, open=None)
        p["actboss"] = ACT_BOSSES[act - 1] if depth % BOSS_EVERY == 0 else None
    PLANS[lid] = p
    return p


def forget(player):
    """A new hero (or a new game): nothing of the old rift is kept."""
    global _SEED
    _SEED = None
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


_ACT_POOLS = {}


def _pool_act(content, kit, act):
    """The monsters of one act's areas (Levels.txt rosters of that act), minus the act bosses."""
    if act in _ACT_POOLS:
        return _ACT_POOLS[act]
    every = set(_pool(content, kit))
    seen = []
    for r in (getattr(kit, "levels", None) or {}).values():
        try:
            if int(r.get("act", -1)) + 1 != act:
                continue
        except (TypeError, ValueError):
            continue
        for pre in ("mon", "nmon"):
            for i in range(1, 11):
                mid = (r.get("%s%d" % (pre, i), "") or "").lower()
                if mid in every and mid not in seen:
                    seen.append(mid)
    _ACT_POOLS[act] = sorted(seen)
    return _ACT_POOLS[act]


def roster(lid, content, kit):
    p = plan(lid)
    if p["roster"] is None:
        pool = _pool(content, kit)
        if BIG:
            pool = _pool_act(content, kit, p["act"]) or pool
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
    if ACT_LEVELS:
        p["mlvl"] = act_level(p["depth"])      # the act's own monster levels (the autobattler)
    elif player is not None:
        p["mlvl"] = max(1, getattr(player, "level", 1))
    rooms = p["rooms"]
    if tactics.ACTIVE:
        rooms = max(3, rooms - 2)               # the shrunken maps of tactics mode
    elif BIG:
        rooms = max(2, int(round(rooms * 2 * AREA)))    # the autobattler: twice the rooms on a wider floor
    seed = p["seed"] if seed is None else seed
    if p["kit"] == FIELD and BIG and p.get("open"):
        try:
            b, grid, rng = _build_open(kit, lid, seed, p["open"])
        except Exception:
            import traceback
            traceback.print_exc()
            b, grid, rng = _build_field(kit, lid, seed, small=False)
            p["act"], p["flavour"], p["open"] = 1, "Open Plain", None
    elif p["kit"] == FIELD:
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
BIG_TILES = 80              # the autobattler's floors: (80/56)^2 = about twice the area


def _fit(kit, name, rooms, small):
    """Rooms and maze bounds that keep a floor inside the shrunken-map size, whatever kit it uses."""
    from . import act1
    try:
        mk = kit.mazes.get(name) or act1.MazeKit(kit, name)
        kit.mazes[name] = mk
        side = max(mk.rw, mk.rh)
    except Exception:
        side = 16
    cap = (SMALL_TILES if small else (_side(BIG_TILES) if BIG else MAX_TILES)) // max(1, side)
    g = max(2, min(6 if BIG and not small else 4, cap))
    return dict(rooms=max(2, min(rooms, g * g - 1)), grid=g)


def _build_open(kit, lid, seed, theme):
    """An outdoor floor of any act (desert, jungle, Kurast, the steppes, the highlands ...), built by
    the map generator's open-world builder (game/randmap.py) at 10 x 10 blocks, without its own
    monsters or objects: the rift fills it like any other floor."""
    from . import custommap, randmap
    o = dict(kind="open", open_theme=theme, width=_side(10, 6), height=_side(10, 6), seed=int(seed) & 0x3FFFFFFF,
             monsters=[], open_packs=0, packs=0, champions=0, uniques=0, boss="", shrines=0, wells=0,
             chests=0, breakables=0, bodies=0, racks=0, bookshelves=0, lights=0, room_objects=False)
    data = randmap.generate(kit, CONTENT, None, o)
    data["monsters"] = []
    data["objects"] = []
    return custommap.compose(kit, data, lid, seed)


def _build_field(kit, lid, seed, small=False):
    """An open plain: Act 1's wilderness ground inside its border ring, with a few fills."""
    from .act1 import BLOCK, SUB, Built, OutdoorKit, stamp, make_grid
    rng = random.Random(seed)
    size = 5 if small else (_side(8, 5) if BIG else 6)    # (8: 6x6 inner blocks instead of 4x4)
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
            boss.rift_boss = True
            if not BIG:
                scale_to_level(world, boss, lvl)
                boss.max_hp = int(boss.max_hp * 1.5)
            # (BIG: the act boss as D2 makes it - its own level, life and damage)
            boss.hp = boss.max_hp
            world.log("%s guards this floor." % boss.name, RED)
            return
    boss = actworld._spawn(world, mid, spot, lvl, taken)
    if boss is None:
        return
    monmods.make_unique(world, boss)
    boss.rift_boss = True
    boss.max_hp = int(boss.max_hp * KEEPER_LIFE)    # a floor's keeper: it takes a fight
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
    """The way into the rift is a pedestal in Sanctuary now (game/act6.py pads), not a portal
    beside Gheed - but the Rogue Encampment still has to forget the last run when you come back
    through it, which is what the rest of this does."""
    p = world.player
    if world.level_id != 1 or not available(p):
        return
    town_only = True
    depth = 1                                   # leaving the rift resets the count: town always opens Rift 1
    if int(getattr(p, "rift_depth", 0) or 0) or getattr(p, "_in_rift", False):
        from . import riftmap                   # back in town: that run is over, the next one is new
        p._in_rift = False
        p.rift_depth = 0
        p.rift_seed = None
        riftmap.clear(p)
        forget(p)
        world.objects[:] = [o for o in world.objects
                            if not (o.get("kind") == "portal" and is_rift(o.get("target")))]
    if town_only:
        return                                   # Sanctuary's pedestal is the only way in now
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
    from . import bounties
    bounties.on_rift_floor(world)                # a Delve contract counts this floor
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
        forget(p)
        world.log("The rift collapses behind you.", RED)
