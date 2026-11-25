"""Premade rift floors: a pool of 54 floor layouts kept on the player's own PC.

Building a rift floor from D2's room files is slow. The autobattler keeps a pool of built floor
layouts (maps only: tiles, walls, the walkable grid) in map_cache/ in the game folder, and a new
floor loads one of them; its monsters, portal and boss spot are placed fresh each time.

- The pool is MAP_POOL (54) floors, shared out over the places the rift builds floors from
  (each act's dungeons and outdoors), so every place has its own few layouts.
- Until a place has its share, its floors are built as before and kept. The game also builds the
  missing ones in the background while no run is waiting for a floor.
- The layouts are made on the player's PC from his own D2 files and are never part of the
  repository (map_cache/ is in .gitignore). They hold no art: a tile is kept as the name of its
  D2 tile file and its number in it, read again from the player's MPQs when the floor is loaded.
- Anything that fails (an old file, a tile that can't be found) is skipped and the floor is built
  the old way.
"""
import os
import pickle
import random
import threading
import zlib

MAP_POOL = 204          # 54, then 150 more
ARENA_POOL = 2          # premade arenas for each act's boss (the tenth floors)
ARENA_SIZE = 4          # blocks a side, the border ring included: 2 x 2 blocks of ground inside
VERSION = 1
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(HERE, "map_cache")

FAILED = "(failed)"     # a place whose floors couldn't be kept this session
_LOCK = threading.Lock()
_INDEX = None           # theme key -> [file names]


# ------------------------------------------------------------------ the places and their shares
ARENA = "@arena"


def themes():
    """Every place a BIG rift floor is built from, as (key, act)."""
    from game import rift
    out = [((kit, None), act) for kit, act, _f in rift.PLACES if kit != rift.FIELD]
    out += [((rift.FIELD, theme), act) for theme, act, _f in rift.OPEN_FLOORS]
    return sorted(set(out))


def arenas():
    """The act bosses' arenas, one place per act, as (key, act)."""
    from game import rift
    acts = sorted(set(act for _t, act, _f in rift.OPEN_FLOORS))
    return [((ARENA, str(a)), a) for a in acts]


def theme_of(p):
    from game import rift
    if is_boss_floor(p):
        return (ARENA, str(p.get("act")))
    if p.get("kit") == rift.FIELD:
        return (rift.FIELD, p.get("open"))
    return (p.get("kit"), None)


def is_boss_floor(p):
    from game import rift
    return bool(rift.BIG) and p.get("depth", 1) % rift.BOSS_EVERY == 0


def quota(key):
    """This place's share of the pool."""
    if key[0] == ARENA:
        return ARENA_POOL if key in [k for k, _a in arenas()] else 0
    keys = [k for k, _a in themes()]
    if key not in keys:
        return 0
    n = len(keys)
    return MAP_POOL // n + (1 if keys.index(key) < MAP_POOL % n else 0)


def _slug(key):
    kit, theme = key
    return ("%s_%s" % (kit, theme or "")).replace("@", "").replace("\\", "_").replace("/", "_")


def _tag():
    from game import rift
    return "v%d_a%d" % (VERSION, int(round(rift.AREA * 100)))


def index():
    global _INDEX
    with _LOCK:
        if _INDEX is None:
            _INDEX = {}
            try:
                names = os.listdir(FOLDER)
            except OSError:
                names = []
            tag = _tag()
            for k, _a in themes() + arenas():
                pre = "%s__%s__" % (tag, _slug(k))
                _INDEX[k] = sorted(n for n in names if n.startswith(pre) and n.endswith(".map"))
        return _INDEX


def have(key):
    return len(index().get(key, []))


def missing():
    """Places still short of their share, the emptiest first."""
    out = [(have(k) - quota(k), k, a) for k, a in arenas() + themes() if have(k) < quota(k)]
    out.sort()
    return [(k, a) for _d, k, a in out]


def total():
    return sum(len(v) for v in index().values())


# ------------------------------------------------------------------ saving and loading
def _tile_refs(kit):
    refs = {}
    for name, dt in list(getattr(kit, "dt1_cache", {}).items()):
        if not dt:
            continue
        for i, t in enumerate(dt.tiles):
            refs[id(t)] = (name, i)
    return refs


class _Saver(pickle.Pickler):
    def __init__(self, f, kit):
        pickle.Pickler.__init__(self, f, protocol=4)
        from d2.dt1 import DT1, Tile
        self.kit, self.DT1, self.Tile = kit, DT1, Tile
        self.refs = _tile_refs(kit)
        self.names = {id(dt): name for name, dt in getattr(kit, "dt1_cache", {}).items() if dt}

    def persistent_id(self, obj):
        if obj is self.kit:
            return ("kit",)
        if isinstance(obj, self.DT1):
            name = self.names.get(id(obj)) or getattr(obj, "name", None)
            if not name:
                raise pickle.PicklingError("a tile file without a name")
            return ("dt1", name)
        if isinstance(obj, self.Tile):
            r = self.refs.get(id(obj))
            if r is None:
                raise pickle.PicklingError("a tile that is not in a D2 tile file")
            return ("tile",) + r
        if type(obj).__module__.startswith("pygame"):
            raise pickle.PicklingError("a picture in the floor")
        return None


class _Loader(pickle.Unpickler):
    def __init__(self, f, kit):
        pickle.Unpickler.__init__(self, f)
        self.kit = kit

    def _dt1(self, name):
        cache = self.kit.dt1_cache
        dt = cache.get(name)
        if dt is None:
            from d2.dt1 import DT1
            dt = DT1(self.kit.src.read(name), name)
            cache[name] = dt
        return dt

    def persistent_load(self, pid):
        if pid[0] == "kit":
            return self.kit
        if pid[0] == "dt1":
            return self._dt1(pid[1])
        if pid[0] == "tile":
            return self._dt1(pid[1]).tiles[pid[2]]
        raise pickle.UnpicklingError("unknown reference %r" % (pid,))


def save(key, b, grid, lid, kit):
    """Keep a just-built floor (if its place is short of its share)."""
    if have(key) >= quota(key):
        return False
    import io
    try:
        buf = io.BytesIO()
        _Saver(buf, kit).dump({"b": b, "grid": grid, "lid": lid})
        data = zlib.compress(buf.getvalue(), 6)
        os.makedirs(FOLDER, exist_ok=True)
        with _LOCK:
            names = _INDEX.setdefault(key, []) if _INDEX is not None else []
            n = 0
            while True:
                fn = "%s__%s__%03d.map" % (_tag(), _slug(key), n)
                if fn not in names and not os.path.exists(os.path.join(FOLDER, fn)):
                    break
                n += 1
            tmp = os.path.join(FOLDER, fn + ".tmp")
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, os.path.join(FOLDER, fn))
            names.append(fn)
        return True
    except Exception:
        _log("could not keep a %s floor" % (key,))
        with _LOCK:
            # (this session the place is counted as full: no retrying on every floor)
            index().setdefault(key, []).extend([FAILED] * max(0, quota(key) - have(key)))
        return False


def load(key, kit, rng=random):
    """A kept floor of this place: (Built, Grid, its old level id), or None."""
    names = [n for n in index().get(key, []) if n != FAILED]
    if not names:
        return None
    fn = rng.choice(names)
    import io
    try:
        with open(os.path.join(FOLDER, fn), "rb") as f:
            data = zlib.decompress(f.read())
        d = _Loader(io.BytesIO(data), kit).load()
        return d["b"], d["grid"], d.get("lid")
    except Exception:
        _log("could not load %s - it is dropped" % fn)
        try:
            os.remove(os.path.join(FOLDER, fn))
        except OSError:
            pass
        with _LOCK:
            if fn in index().get(key, []):
                index()[key].remove(fn)
        return None


def _log(what):
    import traceback
    try:
        from main import log_error
        log_error("map cache: %s\n%s" % (what, traceback.format_exc()))
    except Exception:
        traceback.print_exc()


# ------------------------------------------------------------------ the rift's build_level, cached
_ORIGINAL = None


def _relabel(b, old, new):
    """Everything in a kept floor that belongs to its old level id now belongs to the new one."""
    if old is None or old == new:
        return
    b.warps = [(c, m, new if o == old else o) for c, m, o in getattr(b, "warps", [])]
    b.gen_objects = [(i, c, new if o == old else o) for i, c, o in getattr(b, "gen_objects", [])]
    b.edge_exits = [(c, new if t == old else t) for c, t in getattr(b, "edge_exits", [])]


def build_level(kit, lid, seed=None, player=None):
    """rift.build_level, from the pool when this floor's place has its share of kept floors."""
    from game import rift
    p = rift.plan(lid, player)
    key = theme_of(p)
    rng = random.Random(p["seed"] if seed is None else seed)
    if quota(key) and have(key) >= quota(key):
        got = load(key, kit, rng)
        if got is not None:
            b, grid, old = got
            if rift.ACT_LEVELS:
                p["mlvl"] = rift.act_level(p["depth"])
            elif player is not None:
                p["mlvl"] = max(1, getattr(player, "level", 1))
            _relabel(b, old, lid)
            b.npcs, b.objects, b.presets = [], [], []
            b.areas = {lid: (0, 0, b.tm.tw * 5, b.tm.th * 5)}
            ends = getattr(b, "_ends", None)
            if ends and all(e is not None and grid.walkable(*e) for e in ends):
                # the floor's two far ends, found when it was built (three searches over the
                # whole floor: most of a premade floor's loading time); either way round
                a, z = ends if rng.random() < 0.5 else (ends[1], ends[0])
                p["start"], p["boss_cell"] = a, z
            else:
                rift._pick_ends(b, grid, p, rng)
            b.custom_start = p["start"]
            return b, grid, rng
    if key[0] == ARENA:
        b, grid, rng = build_arena(kit, lid, rng.randrange(1 << 30), int(key[1]))
        if rift.ACT_LEVELS:
            p["mlvl"] = rift.act_level(p["depth"])
        rift._pick_ends(b, grid, p, rng)
        b.custom_start = p["start"]
        b._ends = (p.get("start"), p.get("boss_cell"))
        save(key, b, grid, lid, kit)
        return b, grid, rng
    b, grid, rng = _ORIGINAL(kit, lid, seed, player)
    if quota(key) and theme_of(p) == key:           # (not if it fell back to an open plain)
        b._ends = (p.get("start"), p.get("boss_cell"))
        save(key, b, grid, lid, kit)
    return b, grid, rng


def build_arena(kit, lid, seed, act):
    """An act boss's arena: a small walled stretch of his own act's outdoors (2 x 2 blocks of
    ground inside its border), nothing else in it. Falls back on the Black Road's arena (Act 1's
    wilderness) if the act's outdoors can't be built that small."""
    from game import arena, rift
    rng = random.Random(seed)
    themes_ = [t for t, a, _f in rift.OPEN_FLOORS if a == act]
    rng.shuffle(themes_)
    for theme in themes_:
        for size in (ARENA_SIZE, ARENA_SIZE + 1):
            try:
                b, grid, _r = rift._build_open(kit, lid, seed, theme, size=size)
                if sum(1 for y in range(grid.h) for x in range(grid.w) if grid.walkable(x, y)) > 200:
                    b.npcs, b.objects, b.presets = [], [], []
                    b.areas = {lid: (0, 0, b.tm.tw * 5, b.tm.th * 5)}
                    return b, grid, random.Random(seed)
            except Exception:
                _log("an Act %d arena (%s, %d blocks)" % (act, theme, size))
    b, grid, _r = arena.build(kit, lid, seed, rift.CONTENT)
    b.areas = {lid: (0, 0, b.tm.tw * 5, b.tm.th * 5)}
    return b, grid, random.Random(seed)


def install():
    """The autobattler's rift floors come from the pool from now on."""
    global _ORIGINAL
    from game import rift
    if _ORIGINAL is None:
        _ORIGINAL = rift.build_level
        rift.build_level = build_level


def build_missing_one(kit):
    """Build one floor for the place shortest of its share and keep it (the background filler).
    Returns False when the pool is full."""
    from game import act1, rift
    todo = missing()
    if not todo:
        return False
    key, act = todo[0]
    kit_name, theme = key
    seed = random.randrange(1 << 30)
    lid = rift.level_id(rift.MAX_FLOORS)               # (a level id of the rift's, for the tiles' owner)
    if kit_name == ARENA:
        b, grid, _r = build_arena(kit, lid, seed, act)
    elif kit_name == rift.FIELD:
        b, grid, _r = rift._build_open(kit, lid, seed, theme)
    else:
        spec = dict(kit=kit_name, roles=[], act=act, **rift._fit(kit, kit_name, max(2, int(round(10 * rift.AREA))), False))
        b, grid, _r = act1.build_maze(kit, lid, spec, seed)
    b.npcs, b.objects, b.presets = [], [], []
    p = {}
    rift._pick_ends(b, grid, p, random.Random(seed))
    b._ends = (p.get("start"), p.get("boss_cell"))
    save(key, b, grid, lid, kit)       # (one that can't be kept counts the place as full)
    return True
