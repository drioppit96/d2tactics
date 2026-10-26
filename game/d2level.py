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


def build_cave(kit, seed=None, cols=3, rows=3):
    """Returns (grid, rng, tilemap)."""
    rng = random.Random(seed)
    layout = _maze(cols, rows, rng)
    tw, th = cols * ROOM_TILES + 1, rows * ROOM_TILES + 1
    tm = TileMap(tw, th)
    for (rx, ry), ex in layout.items():
        room = rng.choice(kit.rooms[frozenset(ex)])
        ox, oy = rx * ROOM_TILES, ry * ROOM_TILES
        for y in range(room.height):
            for x in range(room.width):
                pos = (ox + x, oy + y)
                for layer in room.floors:
                    c = layer[y * room.width + x]
                    if c.empty or c.main >= 30:
                        continue
                    t = kit.tiles.pick(0, c.main, c.sub, rng.randrange(1 << 16))
                    if t:
                        tm.floor[pos] = t
                walls = []
                for layer in room.walls:
                    c = layer[y * room.width + x]
                    if c.empty or c.orientation in SKIP_ORIENT or c.orientation == 0 or c.main >= 30:
                        continue
                    orients = [c.orientation, 4] if c.orientation == 3 else [c.orientation]
                    for o in orients:
                        t = kit.tiles.pick(o, c.main, c.sub, rng.randrange(1 << 16))
                        if t:
                            walls.append(t)
                if walls:
                    tm.walls[pos] = walls
                elif pos in tm.walls and room.walls:
                    # the later room's border cell is empty: keep the neighbour's
                    pass

    grid = Grid(tw * SUB, th * SUB, WALL)
    for (tx, ty), (_, tile) in tm.floor.items():
        for sy in range(SUB):
            for sx in range(SUB):
                if not tile.flags[(4 - sy) * SUB + sx] & 1:
                    grid.cells[ty * SUB + sy][tx * SUB + sx] = FLOOR
    for (tx, ty), lst in tm.walls.items():
        for _, tile in lst:
            for sy in range(SUB):
                for sx in range(SUB):
                    if tile.flags[(4 - sy) * SUB + sx] & 1:
                        grid.cells[ty * SUB + sy][tx * SUB + sx] = WALL

    # keep only the largest connected area
    best = set()
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
    used = {(x // SUB, y // SUB) for x, y in best}
    for tx, ty in used:
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                tm.drawn.add((tx + dx, ty + dy))
    return grid, rng, tm
