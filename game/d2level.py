"""Build a Den-of-Evil-style cave from Diablo 2's own room presets.

Like the real game, the level is a maze on a grid of rooms. Every room slot gets a
DS1 preset with exactly the exits it needs (caven.ds1, cavense.ds1, ...), rooms are
stitched together, and walkability comes from each tile's subtile flags.
"""
import random
from collections import deque

from d2.ds1 import DS1
from d2.dt1 import DT1, TileSet
from .grid import Grid, FLOOR, WALL

CAVE_DIR = "data\\global\\tiles\\act1\\caves\\"
CAVE_DT1 = ["cave.dt1", "cavedr.dt1"]
ROOM_TILES = 24          # room presets are 24x24 tiles (+1 shared border row/column)
SUB = 5                  # cells (subtiles) per tile side
SKIP_ORIENT = {10, 11, 13}   # special markers and shadows: not drawn as walls, no collision

DIRS = {"n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0)}
OPP = {"n": "s", "s": "n", "w": "e", "e": "w"}


class TileMap:
    """What the renderer draws: floor tiles and wall/prop tiles per tile position."""

    def __init__(self, tw, th):
        self.tw, self.th = tw, th
        self.floor = {}     # (tx, ty) -> (dt1, tile)
        self.walls = {}     # (tx, ty) -> [(dt1, tile)]
        self.drawn = set()  # tile positions worth drawing (near walkable space)


def _room_exits(name):
    """'cavensew2.ds1' -> {'n','s','e','w'}; None for non-maze rooms."""
    stem = name.lower().replace(".ds1", "")
    if not stem.startswith("cave"):
        return None
    body = stem[4:].rstrip("0123456789")
    if not body or any(c not in "nsew" for c in body):
        return None
    return frozenset(body)


class CaveKit:
    def __init__(self, src):
        self.src = src
        dt1s = []
        for n in CAVE_DT1:
            if src.has(CAVE_DIR + n):
                dt1s.append(DT1(src.read(CAVE_DIR + n), n))
        if not dt1s:
            raise FileNotFoundError("cave tiles (cave.dt1) not found")
        self.tiles = TileSet(dt1s)
        self.rooms = {}
        combos = ["n", "s", "e", "w", "ne", "nw", "ns", "se", "sw", "ew",
                  "nse", "nsw", "new", "sew", "nsew"]
        for c in combos:
            for suffix in ("", "2", "3"):
                name = "cave%s%s.ds1" % (c, suffix)
                if src.has(CAVE_DIR + name):
                    ex = _room_exits(name)
                    self.rooms.setdefault(ex, []).append(DS1(src.read(CAVE_DIR + name), name))
        if len(self.rooms) < 15:
            missing = 15 - len(self.rooms)
            raise FileNotFoundError("%d cave room types missing" % missing)


def _maze(cols, rows, rng, extra_links=1):
    """Random spanning tree over the room grid (plus a few loops) -> {(x, y): set(exits)}."""
    exits = {(x, y): set() for x in range(cols) for y in range(rows)}
    start = (rng.randrange(cols), rng.randrange(rows))
    stack, seen = [start], {start}
    while stack:
        cur = stack[-1]
        opts = []
        for d, (dx, dy) in DIRS.items():
            nb = (cur[0] + dx, cur[1] + dy)
            if nb in exits and nb not in seen:
                opts.append((d, nb))
        if not opts:
            stack.pop()
            continue
        d, nb = rng.choice(opts)
        exits[cur].add(d)
        exits[nb].add(OPP[d])
        seen.add(nb)
        stack.append(nb)
    for _ in range(extra_links):
        x, y = rng.randrange(cols), rng.randrange(rows)
        d = rng.choice(list(DIRS))
        nb = (x + DIRS[d][0], y + DIRS[d][1])
        if nb in exits:
            exits[(x, y)].add(d)
            exits[nb].add(OPP[d])
    return exits


def stamp(tm, room, tiles, ox, oy, rng):
    """Copy one DS1 preset's floors and walls into the tile map at tile offset (ox, oy)."""
    for y in range(room.height):
        for x in range(room.width):
            pos = (ox + x, oy + y)
            for layer in room.floors:
                c = layer[y * room.width + x]
                if c.empty or c.main >= 30:
                    continue
                t = tiles.pick(0, c.main, c.sub, rng.randrange(1 << 16))
                if t:
                    tm.floor[pos] = t
            walls = []
            for layer in room.walls:
                c = layer[y * room.width + x]
                if c.empty or c.orientation in SKIP_ORIENT or c.orientation == 0 or c.main >= 30:
                    continue
                orients = [c.orientation, 4] if c.orientation == 3 else [c.orientation]
                for o in orients:
                    t = tiles.pick(o, c.main, c.sub, rng.randrange(1 << 16))
                    if t:
                        walls.append(t)
            if walls:
                tm.walls[pos] = walls


def grid_from_tilemap(tm, keep_largest=True):
    """Walkable cells from the tiles' subtile flags (bit 0 = blocks walking)."""
    grid = Grid(tm.tw * SUB, tm.th * SUB, WALL)
    for (tx, ty), (_, tile) in tm.floor.items():
        for sy in range(SUB):
            row = grid.cells[ty * SUB + sy]
            for sx in range(SUB):
                if not tile.flags[(4 - sy) * SUB + sx] & 1:
                    row[tx * SUB + sx] = FLOOR
    for (tx, ty), lst in tm.walls.items():
        for _, tile in lst:
            for sy in range(SUB):
                row = grid.cells[ty * SUB + sy]
                for sx in range(SUB):
                    if tile.flags[(4 - sy) * SUB + sx] & 1:
                        row[tx * SUB + sx] = WALL
    best = set()
    if keep_largest:
        seen = set()
        for y in range(grid.h):
            row = grid.cells[y]
            for x in range(grid.w):
                if row[x] == FLOOR and (x, y) not in seen:
                    region = {(x, y)}
                    q = deque([(x, y)])
                    while q:
                        c = q.popleft()
                        for nb in grid.neighbors(*c):
                            if nb not in region:
                                region.add(nb)
                                q.append(nb)
                    seen |= region
                    if len(region) > len(best):
                        best = region
        for y in range(grid.h):
            for x in range(grid.w):
                if grid.cells[y][x] == FLOOR and (x, y) not in best:
                    grid.cells[y][x] = WALL
    return grid, best


def build_cave(kit, seed=None, cols=3, rows=3):
    """Returns (grid, rng, tilemap)."""
    rng = random.Random(seed)
    layout = _maze(cols, rows, rng)
    tm = TileMap(cols * ROOM_TILES + 1, rows * ROOM_TILES + 1)
    for (rx, ry), ex in layout.items():
        room = rng.choice(kit.rooms[frozenset(ex)])
        stamp(tm, room, kit.tiles, rx * ROOM_TILES, ry * ROOM_TILES, rng)
    grid, best = grid_from_tilemap(tm)
    used = {(x // SUB, y // SUB) for x, y in best}
    for tx, ty in used:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                tm.drawn.add((tx + dx, ty + dy))
    tm.entry = None
    return grid, rng, tm


# ---------------------------------------------------------------- Rogue Encampment
TOWN_DIR = "data\\global\\tiles\\act1\\town\\"
# D2's Act 1 NPC presets referenced by town layouts (type 1 objects)
ACT1_NPC_PRESETS = {0: "gheed", 1: "cain1", 2: "akara", 3: "chicken", 4: "rogue1", 5: "kashya",
                    7: "warriv1", 8: "charsi", 13: "navi"}


def _dt1_for(src, ds1_files, cache):
    """DT1 tile libraries a DS1 refers to (its list holds .tg1 names; the files are .dt1)."""
    out = []
    for f in ds1_files:
        name = f.lower().replace("/", "\\").lstrip("\\")
        if name.startswith("d2\\"):
            name = name[3:]
        name = name.rsplit(".", 1)[0] + ".dt1"
        if name in cache:
            if cache[name]:
                out.append(cache[name])
            continue
        dt = None
        if src.has(name):
            try:
                dt = DT1(src.read(name), name)
            except Exception:
                dt = None
        cache[name] = dt
        if dt:
            out.append(dt)
    return out


class TownKit:
    def __init__(self, src):
        self.src = src
        self.layouts = []
        self.dt1_cache = {}
        for n in ("townn1", "towne1", "towns1", "townw1"):
            path = TOWN_DIR + n + ".ds1"
            if src.has(path):
                self.layouts.append((n, DS1(src.read(path), n)))
        if not self.layouts:
            raise FileNotFoundError("Rogue Encampment layouts (townn1.ds1...) not found")


def build_town(kit, seed=None):
    """Returns (grid, rng, tilemap); tilemap.npcs = [(monstats id, (x, y))], tilemap.exits = cells."""
    rng = random.Random(seed)
    name, ds1 = rng.choice(kit.layouts)
    tiles = TileSet(_dt1_for(kit.src, ds1.files, kit.dt1_cache))
    tm = TileMap(ds1.width, ds1.height)
    stamp(tm, ds1, tiles, 0, 0, rng)
    grid, best = grid_from_tilemap(tm)
    tm.drawn = set(tm.floor) | set(tm.walls)
    tm.npcs = []
    for t, oid, x, y in ds1.objects:
        if t == 1 and oid in ACT1_NPC_PRESETS and grid.walkable(x, y):
            tm.npcs.append((ACT1_NPC_PRESETS[oid], (x, y)))
    # the way out: walkable cells on the map border (towards the Blood Moor)
    tm.exits = {c for c in best if c[0] <= 1 or c[1] <= 1 or c[0] >= grid.w - 2 or c[1] >= grid.h - 2}
    # start near Warriv, like arriving in the camp
    warriv = [p for n, p in tm.npcs if n == "warriv1"]
    tm.entry = None
    if warriv:
        taken = {p for _, p in tm.npcs}
        wx, wy = warriv[0]
        free = [c for c in best if c not in taken and c not in tm.exits and 2 <= max(abs(c[0] - wx), abs(c[1] - wy)) <= 4]
        tm.entry = min(free, key=lambda c: abs(c[0] - wx) + abs(c[1] - wy)) if free else None
    tm.layout = name
    return grid, rng, tm
