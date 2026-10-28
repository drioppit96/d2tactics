"""Shared pieces of the outdoor / dungeon builders of Acts 3-5 (D2's DRLG, simplified):

* Canvas: a Built plus stamping helpers (D2 room presets, plain ground)
* block_area: an area of N x M blocks with D2's border presets around it, specials (entrances,
  gates, waypoints, quest rooms) at chosen spots and D2's fill presets in between
* tree_layout: a random spanning tree over a grid of pieces (the jungle's river, mazes)
* ensure_waypoints / ensure_connected: what every outdoor world needs at the end
"""
import random

from . import act1
from .act1 import Built, stamp, make_grid, SUB, DIRS, OPP


class GroundKit:
    """act1._connect / _carve lay "grass": here the ground of the act."""

    def __init__(self, kit, ds, codes, lvltype):
        self.kit, self._g, self.lt = kit, (ds, codes), lvltype

    def grass(self):
        return self._g

    def tiles_for(self, ds, extra_type=None):
        return self.kit.tiles_for(ds, self.lt)


def ground_codes(kit, name, layer=0, top=1):
    """The most used floor (main, sub) codes of a preset = that area's plain ground."""
    ds = kit.ds1(name)
    if ds is None:
        return None, [(0, 0)]
    count = {}
    for c in ds.floors[layer]:
        if not c.empty and not c.hidden:
            count[(c.main, c.sub)] = count.get((c.main, c.sub), 0) + 1
    best = sorted(count, key=lambda k: -count[k])[:top]
    codes = []
    for k in best:
        codes += [k] * max(1, count[k] // max(1, count[best[0]] // 4))
    return ds, codes or [(0, 0)]


class Canvas:
    def __init__(self, kit, tw, th, act, seed=None):
        self.kit = kit
        self.rng = random.Random(seed)
        self.b = Built(tw + 1, th + 1)
        from .acts import apply_act_tables
        apply_act_tables(self.b, act, kit)
        self.grounds = {}

    def put(self, name, tx, ty, owner, lvltype):
        ds = self.kit.ds1(name)
        if ds is None:
            return None
        stamp(self.b, ds, self.kit.tiles_for(ds, lvltype), tx, ty, self.rng, owner)
        return ds

    def size_of(self, name):
        ds = self.kit.ds1(name)
        return (ds.width - 1, ds.height - 1) if ds is not None else None

    def set_ground(self, key, preset, lvltype):
        ds, codes = ground_codes(self.kit, preset)
        self.grounds[key] = (ds, codes, self.kit.tiles_for(ds, lvltype) if ds is not None else None, lvltype)

    def ground(self, key, tx0, ty0, w, h):
        ds, codes, tiles, _ = self.grounds[key]
        if tiles is None:
            return
        rng = self.rng
        for y in range(h):
            for x in range(w):
                main, sub = rng.choice(codes)
                t = tiles.pick(0, main, sub, rng.randrange(1 << 16))
                if t:
                    self.b.tm.floor[(tx0 + x, ty0 + y)] = t

    def ground_kit(self, key):
        ds, codes, tiles, lt = self.grounds[key]
        return GroundKit(self.kit, ds, codes, lt)

    def finish(self):
        b = self.b
        b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
        return make_grid(b.tm)


def pick_existing(kit, names, rng):
    ok = [n for n in names if kit.ds1(n) is not None]
    return rng.choice(ok) if ok else None


def block_area(cv, lid, x0, y0, bw, bh, B, spec):
    """One outdoor area of bw x bh blocks (B tiles each) at tile (x0, y0).

    spec: lvltype, ground (key for cv.ground), border {"n": [names], "s"..., ("n","w"): [names] ...}
          (missing sides get ground), openings {side: (index, width_in_blocks)},
          specials [(names, wblocks, hblocks, where)] where = None (anywhere inside) / (bx, by),
          fills [(names, wblocks, hblocks)] biggest first, fill_chance
    Returns {special index: (bx, by)} of where each special went.
    """
    rng, kit = cv.rng, cv.kit
    lt = spec["lvltype"]
    border = spec.get("border", {})
    openings = spec.get("openings", {})
    taken = set()
    placed = {}
    cv.b.areas[lid] = (x0 * SUB, y0 * SUB, (x0 + bw * B) * SUB, (y0 + bh * B) * SUB)

    def blk(bx, by):
        return x0 + bx * B, y0 + by * B
    # specials with a fixed spot first (gates, entrances on the border)
    for i, (names, w, h, where) in enumerate(spec.get("specials", [])):
        if where is None:
            continue
        bx, by = where
        name = pick_existing(kit, names, rng)
        if name is None:
            continue
        cv.put(name, *blk(bx, by), lid, lt)
        taken.update((bx + i2, by + j) for i2 in range(w) for j in range(h))
        placed[i] = (bx, by)
    # the border ring
    for bx in range(bw):
        for by in range(bh):
            en, es, ew, ee = by == 0, by == bh - 1, bx == 0, bx == bw - 1
            if not (en or es or ew or ee) or (bx, by) in taken:
                continue
            taken.add((bx, by))
            vert = "n" if en else ("s" if es else None)
            hor = "w" if ew else ("e" if ee else None)
            X, Y = blk(bx, by)
            if vert and hor:
                names = border.get((vert, hor))
            else:
                side = vert or hor
                along = bx if vert else by
                op = openings.get(side)
                if op is not None and abs(along - op[0]) <= op[1]:
                    oname = pick_existing(kit, spec.get("open_border", {}).get(side, []), rng)
                    if oname is None or cv.put(oname, X, Y, lid, lt) is None:
                        cv.ground(spec["ground"], X, Y, B, B)
                    continue
                names = border.get(side)
            name = pick_existing(kit, names or [], rng)
            if name is None or cv.put(name, X, Y, lid, lt) is None:
                cv.ground(spec["ground"], X, Y, B, B)
    inner = [(bx, by) for bx in range(1, bw - 1) for by in range(1, bh - 1)]
    rng.shuffle(inner)
    # plain ground under everything first: a preset that doesn't cover its whole square leaves no hole
    for bx, by in inner:
        if (bx, by) not in taken:
            cv.ground(spec["ground"], *blk(bx, by), B, B)

    def place(names, w, h):
        for bx, by in inner:
            cells = [(bx + i, by + j) for i in range(w) for j in range(h)]
            if all(1 <= c[0] < bw - 1 and 1 <= c[1] < bh - 1 and c not in taken for c in cells):
                name = pick_existing(kit, names, rng)
                if name is None:
                    return None
                cv.put(name, *blk(bx, by), lid, lt)
                taken.update(cells)
                return (bx, by)
        return None
    for i, (names, w, h, where) in enumerate(spec.get("specials", [])):
        if where is None:
            spot = place(names, w, h)
            if spot is not None:
                placed[i] = spot
    chance = spec.get("fill_chance", 0.6)
    for names, w, h in spec.get("fills", []):
        tries = max(1, (bw - 2) * (bh - 2) // max(1, w * h))
        for _ in range(tries):
            if rng.random() < chance:
                place(names, w, h)
    for bx, by in inner:
        if (bx, by) not in taken:
            cv.ground(spec["ground"], *blk(bx, by), B, B)
            taken.add((bx, by))
    return placed


def full_pieces(kit, names, lvltype, min_frac=0.85):
    """Only the presets that cover their whole square (no cliff / ravine edges with void behind)."""
    out = []
    for n in names:
        ds = kit.ds1(n)
        if ds is None:
            continue
        ts = kit.tiles_for(ds, lvltype)
        cells = [c for layer in ds.floors[:2] for c in layer]
        w, h = ds.width - 1, ds.height - 1
        covered = set()
        for li, layer in enumerate(ds.floors[:2]):
            for i, c in enumerate(layer):
                if not c.empty and not c.hidden and ts.pick(0, c.main, c.sub, 1):
                    covered.add(i)
        if len(covered) >= min_frac * ds.width * ds.height:
            out.append(n)
    return out


def tree_layout(cols, rows, rng, extra=0):
    """Every cell of a cols x rows grid joined by a random spanning tree (+ a few extra links).
    -> {(x, y): set of directions}"""
    cells = {(x, y): set() for x in range(cols) for y in range(rows)}
    start = (rng.randrange(cols), rng.randrange(rows))
    seen = {start}
    edges = []
    for d in DIRS:
        nb = (start[0] + DIRS[d][0], start[1] + DIRS[d][1])
        if nb in cells:
            edges.append((start, d))
    while edges:
        a, d = edges.pop(rng.randrange(len(edges)))
        nb = (a[0] + DIRS[d][0], a[1] + DIRS[d][1])
        if nb in seen:
            continue
        seen.add(nb)
        cells[a].add(d)
        cells[nb].add(OPP[d])
        for d2 in DIRS:
            n2 = (nb[0] + DIRS[d2][0], nb[1] + DIRS[d2][1])
            if n2 in cells and n2 not in seen:
                edges.append((nb, d2))
    for _ in range(extra):
        a = rng.choice(list(cells))
        d = rng.choice(list(DIRS))
        nb = (a[0] + DIRS[d][0], a[1] + DIRS[d][1])
        if nb in cells:
            cells[a].add(d)
            cells[nb].add(OPP[d])
    return cells


def near_walkable(grid, c, radius=40):
    if grid.walkable(*c):
        return c
    for r in range(1, radius + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) == r and grid.walkable(c[0] + dx, c[1] + dy):
                    return (c[0] + dx, c[1] + dy)
    return None


def ensure_waypoints(b, grid, act, rooms=None):
    """D2's waypoint in every area of this act's list that doesn't already have one."""
    from .acts import WAYPOINTS
    for lid in WAYPOINTS.get(act, []):
        if lid not in b.areas or any(k == "waypoint" and o == lid for k, _, o, _ in b.objects):
            continue
        rect = (rooms or {}).get(lid)
        if rect is not None:
            x, y, w, h = rect
            c = ((x + w // 2) * SUB, (y + h // 2) * SUB)
        else:
            x0, y0, x1, y1 = b.areas[lid]
            if getattr(b, "town_rect", None) and lid in (75, 103, 109):
                x0, y0, x1, y1 = b.town_rect
            c = ((x0 + x1) // 2, (y0 + y1) // 2)
        c = near_walkable(grid, c, 80)
        if c is not None:
            b.objects.append(("waypoint", c, lid, -1))


def ensure_connected(b, grid, chain, gkit, rng):
    """Every area can be walked into from the one before it (carve a trail where presets don't meet)."""
    b.slot_tiles = getattr(b, "slot_tiles", 64)
    act1._connect(b, grid, None, chain, gkit, rng, {})


def edge_cells(grid, rect, side, x_range=None, depth=3):
    """Walkable cells along one side of a cell rect (seamless exits to another world)."""
    x0, y0, x1, y1 = rect
    out = []
    if side in ("n", "s"):
        xs = range(max(x0, x_range[0] if x_range else x0), min(x1, x_range[1] if x_range else x1))
        ys = range(y0, y0 + 40) if side == "n" else range(y1 - 1, y1 - 41, -1)
        for x in xs:
            for y in ys:
                if grid.walkable(x, y):
                    out += [(x, y + (k if side == "n" else -k)) for k in range(depth)
                            if grid.walkable(x, y + (k if side == "n" else -k))]
                    break
    else:
        ys = range(y0, y1)
        xs = range(x0, x0 + 40) if side == "w" else range(x1 - 1, x1 - 41, -1)
        for y in ys:
            for x in xs:
                if grid.walkable(x, y):
                    out += [(x + (k if side == "w" else -k), y) for k in range(depth)
                            if grid.walkable(x + (k if side == "w" else -k), y)]
                    break
    return out
