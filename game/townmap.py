"""Town maps for the map generator - a plot of town ground with real D2 buildings standing on it.

A town is not built like a dungeon. D2's dungeons are kits of interchangeable rooms, each cut to
join its neighbours, so a generator can lay them out like dominoes. The five towns are not: each
one is a single hand-made picture, and its tileset is a box of parts that only ever fitted
together that one way.

So this takes the towns apart instead. It reads each town's own DS1, finds every connected run of
wall - a house, a tower, a gate, a wall of the camp - and lifts it out whole, with the ground it
stands on, as a piece that can be put down anywhere. The pieces keep their original tiles, so a
house generated here is the same house, down to the tile, as the one in Diablo.

    themes()                  the five towns
    pieces(kit, theme)        every building and wall run lifted out of that town
    generate(kit, opts)       a custom map (game/custommap.py) ready for the editor and the game

What comes out is an ordinary custom map, so the map editor opens it and every piece in it can be
moved, deleted or built on by hand afterwards.
"""
import random
from collections import Counter

# key -> (shown name, act, LvlTypes name, the town's own DS1s)
TOWNS = [
    ("rogue", "Act 1 - Rogue Encampment", 1, "Act 1 - Town",
     ["act1\\town\\townn1.ds1", "act1\\town\\towne1.ds1", "act1\\town\\towns1.ds1", "act1\\town\\townw1.ds1"]),
    ("lut", "Act 2 - Lut Gholein", 2, "Act 2 - Town",
     ["act2\\town\\lutw.ds1", "act2\\town\\lutn.ds1"]),
    ("docks", "Act 3 - Kurast Docks", 3, "Act 3 - Town",
     ["act3\\docktown\\docktown3.ds1"]),
    ("fortress", "Act 4 - Pandemonium Fortress", 4, "Act 4 - Town",
     ["act4\\fort\\fortress.ds1"]),
    ("harrogath", "Act 5 - Harrogath", 5, "Act 5 - Town",
     ["expansion\\town\\townwest.ds1"]),
]
TOWN_NAMES = {k: n for k, n, _a, _t, _f in TOWNS}
TOWN_ACT = {k: a for k, _n, a, _t, _f in TOWNS}
TOWN_TYPE = {k: t for k, _n, _a, t, _f in TOWNS}
TOWN_FILES = {k: f for k, _n, _a, _t, f in TOWNS}

MAX_PIECE = 24            # tiles: bigger than this is a whole quarter of the town, not a building
MIN_WALL = 2              # tiles of wall: fewer is a stray post, not a structure
_cache = {}


def themes():
    return [(k, n, a) for k, n, a, _t, _f in TOWNS]


def _cells(ds, layers, x, y):
    w = ds.width
    for layer in layers:
        c = layer[y * w + x]
        if not c.empty and not c.hidden:
            yield c


def _read(kit, path):
    """One town DS1 -> (walls by tile, floors by tile, size). Warps and doors are left behind."""
    ds = kit.ds1(path)
    if ds is None:
        return None
    walls, floors = {}, {}
    for y in range(ds.height):
        for x in range(ds.width):
            ws = [(c.orientation, c.main, c.sub) for c in _cells(ds, ds.walls, x, y)
                  if c.orientation not in (10, 11)]
            if ws:
                walls[(x, y)] = ws
            fs = []
            for li, layer in enumerate(ds.floors):
                c = layer[y * ds.width + x]
                if not c.empty and not c.hidden:
                    fs.append((li, c.main, c.sub))
            if fs:
                floors[(x, y)] = fs
    return walls, floors, (ds.width, ds.height)


def _clusters(walls):
    """Connected runs of wall, 8-connected over tiles."""
    seen, out = set(), []
    for start in walls:
        if start in seen:
            continue
        stack, group = [start], []
        seen.add(start)
        while stack:
            t = stack.pop()
            group.append(t)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (t[0] + dx, t[1] + dy)
                    if n in walls and n not in seen:
                        seen.add(n)
                        stack.append(n)
        out.append(group)
    return out


def pieces(kit, theme):
    """Every building and wall run of one town, ready to put down somewhere else."""
    key = ("pieces", theme)
    if key in _cache:
        return _cache[key]
    out = []
    for path in TOWN_FILES.get(theme, []):
        got = _read(kit, path)
        if not got:
            continue
        walls, floors, _size = got
        # a floor tile the tileset has no art for would punch a hole through the ground the piece
        # is standing on, so those are left out and the plot's own ground shows instead
        ts = kit.tiles_for(kit.ds1(path), TOWN_TYPE.get(theme, ""))
        def ok(main, sub):
            return ts is None or ts.pick(0, main, sub, 0) is not None
        for group in _clusters(walls):
            if len(group) < MIN_WALL:
                continue
            xs = [t[0] for t in group]
            ys = [t[1] for t in group]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            # Act 4's fortress and Harrogath are one connected mass of wall, so a whole town would
            # come out as a single piece. Anything oversized is cut into blocks instead, and each
            # block that still holds enough wall becomes a piece of its own.
            for bx in range(x0, x1 + 1, MAX_PIECE):
                for by in range(y0, y1 + 1, MAX_PIECE):
                    sx1, sy1 = min(bx + MAX_PIECE - 1, x1), min(by + MAX_PIECE - 1, y1)
                    part = [t for t in group if bx <= t[0] <= sx1 and by <= t[1] <= sy1]
                    if len(part) < MIN_WALL:
                        continue
                    px0, py0 = min(t[0] for t in part), min(t[1] for t in part)
                    px1, py1 = max(t[0] for t in part), max(t[1] for t in part)
                    w, h = px1 - px0 + 1, py1 - py0 + 1
                    tiles = []
                    for (tx, ty) in sorted(part):
                        for o, main, sub in walls[(tx, ty)]:
                            tiles.append([tx - px0, ty - py0, "dw", path, o, main, sub])
                    for ty in range(py0, py1 + 1):     # the ground it stands on, and its doorstep
                        for tx in range(px0, px1 + 1):
                            for li, main, sub in floors.get((tx, ty), ()):
                                if li == 0 and not ok(main, sub):
                                    continue
                                tiles.append([tx - px0, ty - py0, "df" if li == 0 else "df2", path, main, sub])
                    out.append({"name": "%s %d.%d %dx%d" % (path.rsplit("\\", 1)[-1][:-4], px0, py0, w, h),
                                "w": w, "h": h, "walls": len(part), "src": path, "tiles": tiles})
    out.sort(key=lambda p: (-p["walls"], p["name"]))
    _cache[key] = out
    return out


def ground(kit, theme):
    """The town's ordinary ground: its commonest open floor tiles, and its commonest paving."""
    key = ("ground", theme)
    if key in _cache:
        return _cache[key]
    base, road, src = Counter(), Counter(), None
    for path in TOWN_FILES.get(theme, []):
        got = _read(kit, path)
        if not got:
            continue
        walls, floors, _size = got
        src = src or path
        for t, fs in floors.items():
            # every floor tile counts, including the ones under buildings: in Harrogath almost the
            # whole town stands on something, and the open squares alone are too thin a sample
            for li, main, sub in fs:
                (base if li == 0 else road)[(main, sub)] += 1
    # Keep one ground, not a patchwork. D2 lays a field from a single main index and varies only
    # the sub, which is why its ground reads as one surface; the other mains are a garden patch or
    # a shoreline made for one spot, and sprinkled at random they turn the plot into a chessboard.
    # Anything that does not resolve to a tile is dropped too, or it leaves a hole in the ground.
    best = Counter()
    for (main, _sub), n in base.items():
        best[main] += n
    keep = []
    if best:
        main0 = best.most_common(1)[0][0]
        ts = kit.tiles_for(kit.ds1(src), TOWN_TYPE.get(theme, "")) if src else None
        for (main, sub), n in base.most_common():
            if main != main0:
                continue
            if ts is not None and ts.pick(0, main, sub, 0) is None:
                continue
            keep.append(((main, sub), n))
            if len(keep) >= 6:        # the common variants of that ground; the rest are specials
                break
    out = (src, keep or base.most_common(4), [t for t, _n in road.most_common(8)])
    _cache[key] = out
    return out


def _fits(taken, x, y, w, h, W, H, gap=1):
    if x < 1 or y < 1 or x + w > W - 1 or y + h > H - 1:
        return False
    for ty in range(y - gap, y + h + gap):
        for tx in range(x - gap, x + w + gap):
            if (tx, ty) in taken:
                return False
    return True


def generate(kit, opts):
    """A town as a custom map. opts: theme, width, height, buildings, roads, seed, name, level."""
    theme = opts.get("town_theme") or "rogue"
    W = max(8, int(opts.get("width", 24)))
    H = max(8, int(opts.get("height", 24)))
    rng = random.Random(opts.get("seed"))
    src, base, road = ground(kit, theme)
    all_pieces = pieces(kit, theme)
    tiles = []
    # the open ground of the whole plot
    picks = [t for t, _n in base]
    weights = [n for _t, n in base]
    for ty in range(H):
        for tx in range(W):
            if picks:
                main, sub = rng.choices(picks, weights=weights)[0]
                tiles.append([tx, ty, "df", src, main, sub])
    taken = set()
    placed = []
    want = int(opts.get("buildings", 10))
    # pieces that leave room for a street: a 24x24 quarter on a 26x26 plot fills the whole town
    lim = max(4, min(W, H) // 2)
    big = [p for p in all_pieces if 3 <= p["w"] <= lim and 3 <= p["h"] <= lim]
    big = big or [p for p in all_pieces if p["w"] < W - 2 and p["h"] < H - 2] or all_pieces
    tries = 0
    while len(placed) < want and big and tries < want * 60:
        tries += 1
        p = big[rng.randrange(len(big))]
        x, y = rng.randrange(1, max(2, W - p["w"])), rng.randrange(1, max(2, H - p["h"]))
        if not _fits(taken, x, y, p["w"], p["h"], W, H):
            continue
        for ty in range(y, y + p["h"]):
            for tx in range(x, x + p["w"]):
                taken.add((tx, ty))
        for t in p["tiles"]:
            dx, dy, kind, path = t[0], t[1], t[2], t[3]
            if kind == "dw":
                tiles.append([x + dx, y + dy, "dw", path, t[4], t[5], t[6]])
            else:
                tiles.append([x + dx, y + dy, "df" if kind == "df" else "df2", path, t[4], t[5]])
        placed.append((p["name"], x, y))
    # paving between the buildings: lanes of the town's own road tiles down the open ground
    if road and opts.get("roads", True):
        for ty in range(H):
            for tx in range(W):
                if (tx, ty) in taken:
                    continue
                if tx % 6 == 3 or ty % 6 == 3:
                    main, sub = road[rng.randrange(len(road))]
                    tiles.append([tx, ty, "df2", src, main, sub])
    start = None
    for ty in range(H // 2, H):
        for tx in range(W // 2, W):
            if (tx, ty) not in taken:
                start = [tx * 5 + 2, ty * 5 + 2]
                break
        if start:
            break
    doc = {"version": 1, "name": opts.get("name") or ("town_" + theme), "act": TOWN_ACT[theme],
           "lvltype": TOWN_TYPE[theme], "width": W, "height": H, "level": int(opts.get("level") or 0),
           "random_monsters": False, "rooms": [], "tiles": tiles, "objects": [], "monsters": [],
           "decor": [], "markers": [], "start": start or [W * 5 // 2, H * 5 // 2]}
    if opts.get("waypoint", True) and start:
        doc["objects"].append([start[0], max(1, start[1] - 6), "waypoint"])
    doc["_placed"] = placed
    return doc
