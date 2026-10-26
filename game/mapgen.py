"""Placeholder dungeon generator: a Den-of-Evil-style cave.

Once the D2 loader exists, this gets replaced (or complemented) by real D2 level
layouts read from .ds1 files.
"""
import random
from collections import deque

from .grid import Grid, FLOOR, WALL, DIRS8
from .units import Monster


def _bfs(grid, start):
    dist = {start: 0}
    q = deque([start])
    while q:
        c = q.popleft()
        for nb in grid.neighbors(*c):
            if nb not in dist:
                dist[nb] = dist[c] + 1
                q.append(nb)
    return dist


def generate_cave(w=64, h=64, seed=None):
    rng = random.Random(seed)
    g = Grid(w, h, WALL)
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            g.cells[y][x] = FLOOR if rng.random() < 0.56 else WALL
    for _ in range(5):
        new = [row[:] for row in g.cells]
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                walls = sum(1 for dx, dy in DIRS8 if g.cells[y + dy][x + dx] == WALL)
                new[y][x] = WALL if walls >= 5 else FLOOR if walls <= 3 else g.cells[y][x]
        g.cells = new
    # keep only the biggest connected cave
    seen, best = set(), set()
    for y in range(h):
        for x in range(w):
            if g.cells[y][x] == FLOOR and (x, y) not in seen:
                region = set(_bfs(g, (x, y)))
                seen |= region
                if len(region) > len(best):
                    best = region
    for y in range(h):
        for x in range(w):
            if (x, y) not in best:
                g.cells[y][x] = WALL
    return g, rng


def populate(g, rng, depth_level=1):
    floor = [(x, y) for y in range(g.h) for x in range(g.w) if g.cells[y][x] == FLOOR]
    # start in the cell furthest from the cave's centre of mass -> feels like an entrance
    cx = sum(c[0] for c in floor) / len(floor)
    cy = sum(c[1] for c in floor) / len(floor)
    start = max(floor, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
    dist = _bfs(g, start)
    maxd = max(dist.values())
    boss_cell = max(dist, key=dist.get)

    monsters = [Monster("corpsefire", *boss_cell, level=depth_level + 2, rng=rng)]
    occupied = {start, boss_cell}

    def free_near(c, radius=3):
        cells = [d for d in dist if d not in occupied and max(abs(d[0] - c[0]), abs(d[1] - c[1])) <= radius]
        rng.shuffle(cells)
        return cells

    # Corpsefire's zombie escort
    for cell in free_near(boss_cell)[:3]:
        monsters.append(Monster("zombie", *cell, level=depth_level + 1, rng=rng))
        occupied.add(cell)

    pack_centres = []
    candidates = [c for c, d in dist.items() if 12 < d < maxd - 8]
    rng.shuffle(candidates)
    max_packs = max(9, min(18, len(dist) // 900))
    for c in candidates:
        if all(max(abs(c[0] - p[0]), abs(c[1] - p[1])) >= 10 for p in pack_centres):
            pack_centres.append(c)
        if len(pack_centres) >= max_packs:
            break

    for c in pack_centres:
        depth = dist[c] / maxd
        lvl = depth_level + (1 if depth > 0.6 else 0)
        kind = rng.choice(["fallen", "fallen", "zombie", "quill"])
        if kind == "fallen":
            members = ["fallen"] * rng.randint(3, 4) + (["shaman"] if rng.random() < 0.7 else [])
        elif kind == "zombie":
            members = ["zombie"] * rng.randint(2, 3)
        else:
            members = ["quill"] * rng.randint(2, 4)
        spots = [c] + free_near(c)
        for m, cell in zip(members, spots):
            if cell in occupied:
                continue
            monsters.append(Monster(m, *cell, level=lvl, rng=rng))
            occupied.add(cell)
    return start, monsters
