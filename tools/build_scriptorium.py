"""Builds the Kurast Scriptorium (the city quarter west of the Bazaar) and the Forbidden Library (the
dungeon under it) as map-editor maps: assets/maps/kurast_scriptorium.json and forbidden_library.json.

    python tools/build_scriptorium.py <path to your Diablo II folder or extracted files>

The layouts follow the sketches (north up, 1 square = 1 floor tile). Once written, the maps are edited
by hand in the map editor; running this again replaces those edits.
"""
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FIELDSTONE, PLASTER = 20, 24
STAIRS = (31, 7)             # Kurast terrace steps (a floor tile)
# Objects.txt ids
BOOKSHELF = (179, 180)
CANDLES = (33, 34)
BRAZIER, TORCH = 102, 328
CHEST, CHEST2, BARREL, URN = 5, 6, 7, 4
WELL_K = 344                 # a Kurast health well
SHRINE_K = 343               # a Kurast mana well
CORPSES = (154, 270, 271, 326)
CASKET = 1


class BP:
    """A blueprint in tile coordinates: floors, wall lines, pillars, objects, sprites, markers."""

    def __init__(self, w, h, seed):
        self.w, self.h = w, h
        self.rng = random.Random(seed)
        self.floor = {}
        self.floor2 = {}
        self.lines = {FIELDSTONE: [], PLASTER: []}
        self.pillars = []
        self.objects = []
        self.decor = []
        self.markers = []
        self.rooms = []
        self.extra = []          # raw tile entries (borrowed tiles)

    # floors
    def fill(self, x0, y0, x1, y1, main, subs=(0,), layer=1):
        dst = self.floor if layer == 1 else self.floor2
        for y in range(int(y0), int(y1)):
            for x in range(int(x0), int(x1)):
                if 0 <= x < self.w and 0 <= y < self.h:
                    dst[(x, y)] = (main, self.rng.choice(subs))

    def scatter(self, x0, y0, x1, y1, main, subs, chance, layer=2):
        dst = self.floor if layer == 1 else self.floor2
        for y in range(int(y0), int(y1)):
            for x in range(int(x0), int(x1)):
                if self.rng.random() < chance:
                    dst[(x, y)] = (main, self.rng.choice(subs))

    # walls: grid-point lines; doors are (side, from, to) gaps
    def line(self, a, b, main=PLASTER):
        self.lines[main].append((a, b))

    def box(self, x0, y0, x1, y1, doors=(), main=PLASTER):
        sides = {"n": ((x0, y0), (x1, y0)), "s": ((x0, y1), (x1, y1)), "w": ((x0, y0), (x0, y1)), "e": ((x1, y0), (x1, y1))}
        for s, ((ax, ay), (bx, by)) in sides.items():
            horiz = ay == by
            cur, end = (ax, bx) if horiz else (ay, by)
            for g0, g1 in sorted((g[1], g[2]) for g in doors if g[0] == s):
                if g0 > cur:
                    self.line((cur, ay) if horiz else (ax, cur), (g0, ay) if horiz else (ax, g0), main)
                cur = max(cur, g1)
            if cur < end:
                self.line((cur, ay) if horiz else (ax, cur), (bx, by), main)

    # things (tile coordinates, fractions allowed)
    @staticmethod
    def cell(x, y):
        return int(round(x * 5 + 2)), int(round(y * 5 + 2))

    def obj(self, oid, x, y):
        self.objects.append(list(self.cell(x, y)) + [oid])

    def spr(self, name, x, y):
        self.decor.append(list(self.cell(x, y)) + [name])

    def mark(self, what, x, y):
        self.markers.append(list(self.cell(x, y)) + [what])

    def pillar(self, x, y):
        self.pillars.append((int(x), int(y)))

    def to_tiles(self):
        from game import act3
        out = []
        for (x, y), (m, s) in sorted(self.floor.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            out.append([x, y, "f", m, s])
        for (x, y), (m, s) in sorted(self.floor2.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            out.append([x, y, "f2", m, s])
        ok = lambda x, y: 0 <= x <= self.w and 0 <= y <= self.h
        for main in (FIELDSTONE, PLASTER):
            for (x, y), (o, m, s) in sorted(act3._wall_tiles(self.lines[main], ok, main).items()):
                out.append([x, y, "w", o, m, s])
        for x, y in self.pillars:
            out.append([x, y, "w", 12, FIELDSTONE, (x * 3 + y) % 3])
        return out + self.extra


def _base(name, w, h, level=0, **kw):
    d = {"version": 1, "name": name, "act": 3, "lvltype": "Act 3 - Kurast", "width": w, "height": h, "level": level,
         "random_monsters": True, "rooms": [], "tiles": [], "objects": [], "monsters": [], "decor": [],
         "markers": [], "start": None, "exits": []}
    d.update(kw)
    return d


# ======================================================================================== the city
def shop(bp, x0, y0, x1, y1, kind, door):
    """A house on Scribes' Row or in the slums: plaster walls, its door, its furniture."""
    bp.fill(x0, y0, x1, y1, 27 if kind in ("home", "hovel") else 20, (0, 1, 2, 3) if kind in ("home", "hovel") else (0, 1, 2))
    cx = (x0 + x1) / 2.0
    dd = {"n": [("n", int(cx) - 1, int(cx) + 1)], "s": [("s", int(cx) - 1, int(cx) + 1)]}[door]
    bp.box(x0, y0, x1, y1, dd, PLASTER)
    r = bp.rng
    back = y0 + 0.6 if door == "s" else y1 - 0.6
    front = y1 - 1.4 if door == "s" else y0 + 1.4
    if kind == "scribe":
        bp.obj(r.choice(BOOKSHELF), x0 + 1.3, back)
        bp.spr("lectern", x1 - 1.0, (y0 + y1) / 2.0)
        bp.spr("table", x0 + 1.6, (y0 + y1) / 2.0 + 0.2)
        if r.random() < 0.5:
            bp.obj(r.choice(CANDLES), x1 - 1.0, back)
    elif kind == "home":
        bp.spr("beds" if r.random() < 0.4 else "bunks", x0 + 1.4, back)
        bp.spr(r.choice(("round_table", "stool", "kegs")), x1 - 1.2, (y0 + y1) / 2.0)
        if r.random() < 0.5:
            bp.obj(r.choice((URN, BARREL)), x1 - 0.8, back)
    elif kind == "store":
        bp.spr(r.choice(("crates", "barrels_stack", "chests_stack")), x0 + 1.3, back)
        bp.spr(r.choice(("sacks", "crate", "pots")), x1 - 1.2, back)
        bp.obj(CHEST, x1 - 1.0, front)
    elif kind == "tavern":
        bp.spr("feast_table", cx, (y0 + y1) / 2.0)
        bp.spr("kegs", x1 - 1.0, back)
        bp.obj(BARREL, x0 + 0.9, back)
    elif kind == "binder":
        bp.spr("bench_table", cx, (y0 + y1) / 2.0)
        bp.obj(r.choice(BOOKSHELF), x1 - 1.2, back)
    elif kind == "hovel":
        bp.spr(r.choice(("bunks", "sacks", "pots", "bucket")), x0 + 1.3, back)
        if r.random() < 0.4:
            bp.obj(r.choice(CORPSES), x1 - 1.3, (y0 + y1) / 2.0)
    elif kind == "ruin":
        bp.scatter(x0, y0, x1, y1, 46, (16,), 0.3)
        bp.spr(r.choice(("rubble", "debris", "ruin_chunk")), cx, (y0 + y1) / 2.0)
        bp.obj(r.choice(CORPSES), x0 + 1.2, front)


def build_city():
    W, H = 80, 64
    bp = BP(W, H, 7701)
    r = bp.rng
    # --- ground by tier: the upper terrace paved, the middle streets cobbled, the lower quarter mud
    bp.fill(0, 0, W, 18, 20, (0, 1, 2))
    bp.fill(0, 18, W, 44, 20, (0, 1, 2))
    bp.fill(0, 44, W, H, 2, tuple(range(0, 19)))
    bp.scatter(0, 44, W, H, 0, tuple(range(0, 20)), 0.35, layer=1)
    bp.scatter(0, 0, W, 44, 21, (0,), 0.04, layer=1)
    # --- the quarter's own wall, open east to the Bazaar
    bp.box(0, 0, 79, 64, [("e", 24, 39)], FIELDSTONE)
    # --- retaining walls between the tiers; stairways in the gaps
    for y, gaps in ((18, [(11, 15), (38, 43), (70, 76)]), (44, [(7, 11), (29, 33), (55, 59)])):
        cur = 0
        for g0, g1 in gaps:
            bp.line((cur, y), (g0, y), FIELDSTONE)
            cur = g1
        bp.line((cur, y), (79, y), FIELDSTONE)
        for g0, g1 in gaps:
            bp.fill(g0, y - 1, g1, y + 1, STAIRS[0], (STAIRS[1],))
            bp.obj(TORCH, g0 - 0.3, y + 0.8)
            bp.obj(TORCH, g1 + 0.3, y + 0.8)

    # ================= UPPER TERRACE
    # Archivists' Cloister: cells round a garden court
    bp.box(1, 1, 22, 16, [("s", 11, 15)], FIELDSTONE)
    for k in range(5):
        x = 1 + 4 * k
        bp.box(x, 1, x + 4, 5, [("s", x + 1, x + 3)], PLASTER)
        bp.fill(x, 1, x + 4, 5, 27, (0, 1, 2, 3))
        bp.spr("bunks", x + 1.2, 1.8)
        bp.obj(BOOKSHELF[k % 2], x + 3.0, 1.6)
    for j in range(2):
        y = 6 + 4 * j
        bp.box(1, y, 5, y + 4, [("e", y + 1, y + 3)], PLASTER)
        bp.fill(1, y, 5, y + 4, 27, (0, 1, 2, 3))
        bp.spr("beds", 2.2, y + 1.4)
        bp.spr("reliquary" if j else "lectern", 3.8, y + 3.0)
    bp.fill(7, 7, 21, 14, 1, tuple(range(3, 20)))                  # the garden
    for x in range(7, 22, 3):
        bp.pillar(x, 7)
        bp.pillar(x, 14)
    bp.obj(WELL_K, 13.5, 10.0)
    for t in ((9, 8.6), (19, 8.6), (9, 12.4), (19, 12.4)):
        bp.spr("dead_tree", *t)
    bp.spr("hooded_statue", 13.5, 8.0)
    bp.spr("brambles", 11, 12.8)
    bp.spr("brambles", 16.5, 8.4)
    bp.obj(BRAZIER, 6.2, 15)
    bp.obj(BRAZIER, 20.8, 15)

    # The Great Scriptorium
    bp.box(24, 1, 57, 16, [("s", 38, 43), ("w", 12, 14), ("e", 12, 14)], FIELDSTONE)
    for x in (31, 50):                                             # side halls, with doorways
        bp.line((x, 1), (x, 6), PLASTER)
        bp.line((x, 9), (x, 12), PLASTER)
        bp.line((x, 14), (x, 16), PLASTER)
    bp.fill(31, 1, 50, 16, 20, (0, 1, 2))
    bp.fill(32, 6, 50, 12, 22, (0,))                               # the nave, rugs down the middle
    for x in (34.5, 41.0, 47.5):
        bp.spr("rug_large", x, 8.6)
    for x in range(33, 50, 4):
        bp.pillar(x, 5)
        bp.pillar(x, 12)
    for x in range(33, 50, 3):
        bp.obj(BOOKSHELF[x % 2], x, 1.6)
    for y in (7.0, 9.0, 11.0):
        for x in (34.5, 38.5, 43.5, 47.5):
            bp.spr("table", x, y)
    bp.spr("lectern", 40.5, 3.4)
    bp.spr("candelabra_great", 38.0, 3.2)
    bp.spr("candelabra_great", 43.0, 3.2)
    bp.obj(BRAZIER, 33, 14.5)
    bp.obj(BRAZIER, 48, 14.5)
    bp.spr("banner_red", 36, 1.5)
    bp.spr("banner_red", 45, 1.5)
    # Hall of Records (west hall): shelf rows
    bp.fill(24, 1, 31, 16, 22, (0,))
    for y in (3.0, 6.0, 9.5, 13.0):
        bp.obj(BOOKSHELF[0], 25.8, y)
        bp.obj(BOOKSHELF[1], 28.6, y)
    bp.spr("bookcase", 30.2, 2.0)
    bp.obj(CASKET, 25.2, 15.2)
    # Illumination Chamber (east hall): painting tables, candles
    bp.fill(50, 1, 57, 16, 22, (0,))
    for y in (3.5, 7.5, 11.0):
        bp.spr("bench_table", 53.5, y)
    bp.obj(CANDLES[0], 51.2, 14.6)
    bp.obj(CANDLES[1], 56.0, 14.6)
    bp.spr("candelabra", 56.0, 1.8)
    bp.spr("bookcase", 51.2, 1.8)

    # North-east: the burned archive and the temple over the Forbidden Library
    bp.box(58, 1, 63, 12, [("s", 59, 62)], FIELDSTONE)
    bp.fill(58, 1, 63, 12, 0, tuple(range(0, 20)))
    bp.scatter(58, 1, 63, 12, 46, (16,), 0.35)
    for y in (3, 6, 9):
        bp.spr(r.choice(("rubble", "debris", "bone_spread")), 60.5, y)
    bp.obj(CORPSES[0], 59.5, 10.5)
    bp.rooms.append([62, 1, "act3\\kurast\\metrotemple2.ds1", "next"])     # its stairs lead down
    bp.fill(58, 13, 79, 18, 20, (0, 1, 2))
    for x in (66.0, 68.5):
        bp.spr("zealot_statue", x, 16.2)
    for x in (78.0,):
        bp.spr("zealot_statue", x, 16.2)
    bp.obj(BRAZIER, 69.5, 17.0)
    bp.obj(BRAZIER, 76.5, 17.0)
    bp.spr("banner_tattered", 59.2, 13.2)
    bp.spr("gibbet", 64.0, 14.2)

    # ================= MIDDLE TIER
    # the Ink Road to the Bazaar gate
    bp.fill(50, 25, 79, 38, 20, (0, 1, 2))
    for x in (55, 63, 71):
        bp.obj(TORCH, x, 25.6)
        bp.obj(TORCH, x, 37.4)
    # Plaza of Quills
    bp.fill(32, 20, 50, 42, 20, (0, 1, 2))
    bp.fill(39, 29, 44, 34, 46, (2,))
    bp.obj(WELL_K, 41.5, 31.5)
    for s in ((37.5, 27.5), (45.5, 27.5), (37.5, 35.5), (45.5, 35.5)):
        bp.spr("zealot_statue" if s[1] < 30 else "hooded_statue", *s)
    bp.objects.append(list(bp.cell(46.5, 39.0)) + ["waypoint"])
    for x in range(33, 49, 3):
        bp.spr(r.choice(("table", "crates", "sacks", "pots")), x + 0.5, 20.8)
        bp.spr(r.choice(("rug_red", "rug_torn", "table", "barrel")), x + 0.5, 41.2)
    for c in ((32.8, 24.0), (49.2, 24.0), (32.8, 38.0), (49.2, 38.0)):
        bp.obj(BRAZIER, *c)
    bp.obj(SHRINE_K, 33.4, 33.5)

    # Scribes' Row: back-to-back rows of shops, a lane between, a lane north-south
    cols = [(1, 6), (6, 11), (11, 16), (18, 23), (23, 28), (28, 31)]
    kinds = ["scribe", "home", "scribe", "store", "binder", "home", "scribe", "tavern", "home", "scribe",
             "store", "scribe", "home", "binder", "scribe", "home", "store", "scribe", "tavern", "home",
             "scribe", "home", "scribe", "store"]
    k = 0
    for y0, y1, door in ((19, 25, "n"), (25, 31, "s"), (34, 38, "n"), (38, 42, "s")):
        for x0, x1 in cols:
            shop(bp, x0, y0, x1, y1, kinds[k % len(kinds)], door)
            k += 1
    bp.fill(1, 31, 31, 34, 20, (0, 1, 2))
    bp.fill(16, 19, 18, 42, 20, (0, 1, 2))
    for x in (4, 13, 21, 27):
        bp.spr(r.choice(("cart", "barrel", "crates", "sacks")), x, 32.5)
    bp.obj(TORCH, 16.0, 32.4)
    bp.spr("lantern_post", 17.0, 27.0)

    # East quarter: Ink Works, Paper Mill, storehouse; Bookbinders' Guild, guard post
    bp.box(51, 19, 60, 25, [("s", 54, 57)], FIELDSTONE)
    bp.fill(51, 19, 60, 25, 22, (0,))
    for x in (52.5, 55.0, 57.5):
        bp.spr("cauldron_big", x, 21.0)
    bp.spr("barrels_stack", 58.8, 23.6)
    bp.obj(BARREL, 52.0, 23.8)
    bp.box(61, 19, 70, 25, [("s", 64, 67)], FIELDSTONE)
    bp.fill(61, 19, 70, 25, 22, (0,))
    for x in (62.5, 64.5, 66.5, 68.5):
        bp.spr("banner_bone" if x > 65 else "banner_grey", x, 20.4)
    bp.spr("washbasin", 62.5, 23.4)
    bp.spr("font", 68.6, 23.4)
    bp.box(71, 19, 78, 25, [("s", 73, 76)], PLASTER)
    bp.fill(71, 19, 78, 25, 27, (0, 1, 2, 3))
    bp.spr("crates", 72.4, 20.4)
    bp.spr("sacks", 76.6, 20.4)
    bp.obj(CHEST2, 76.6, 23.6)
    bp.box(51, 38, 68, 43, [("n", 58, 61)], FIELDSTONE)            # Bookbinders' Guild
    bp.fill(51, 38, 68, 43, 22, (0,))
    bp.line((57, 38), (57, 40), PLASTER)
    bp.line((57, 42), (57, 43), PLASTER)
    bp.line((62, 38), (62, 40), PLASTER)
    bp.line((62, 42), (62, 43), PLASTER)
    for x in (52.8, 55.2):
        bp.spr("bench_table", x, 41.0)
    for x in (63.5, 65.8):
        bp.obj(BOOKSHELF[int(x) % 2], x, 42.3)
    bp.spr("lectern", 59.5, 41.6)
    bp.obj(CHEST, 67.3, 39.0)
    bp.box(70, 38, 78, 43, [("n", 73, 75)], FIELDSTONE)            # guard post
    bp.fill(70, 38, 78, 43, 22, (0,))
    bp.obj(106, 71.5, 42.2)
    bp.obj(107, 74.0, 42.2)
    bp.spr("armorstand", 76.6, 41.8)
    bp.obj(BRAZIER, 77.2, 39.0)
    bp.fill(68, 38, 70, 44, 20, (0, 1))

    # ================= LOWER QUARTER
    for x in range(2, 78, 5):                                       # the canal-side market
        if any(a - 1 <= x <= b for a, b in ((7, 11), (29, 33), (55, 59))):
            continue
        bp.spr(r.choice(("table", "crates", "sacks", "kegs", "cart", "pots")), x + 1.5, 46.4)
    bp.fill(0, 50, 79, 54, 0, tuple(range(0, 20)))                  # the drained canal
    bp.scatter(0, 50, 79, 54, 1, tuple(range(3, 20)), 0.3, layer=1)
    bridges = ((11, 15), (38, 43), (63, 67))
    steps = ((4, 7), (25, 28), (52, 55), (71, 74))                                   # stairs down into the canal bed
    for y, gaps in ((50, sorted(bridges + steps)), (54, bridges)):
        cur = 0
        for g0, g1 in gaps:
            bp.line((cur, y), (g0, y), FIELDSTONE)
            cur = g1
        bp.line((cur, y), (79, y), FIELDSTONE)
    for g0, g1 in bridges:
        bp.line((g0, 50), (g0, 54), FIELDSTONE)
        bp.line((g1, 50), (g1, 54), FIELDSTONE)
        bp.fill(g0, 50, g1, 54, 20, (0, 1, 2))
    for g0, g1 in steps:
        bp.fill(g0, 49, g1, 51, STAIRS[0], (STAIRS[1],))
    for x in (5, 24, 31, 50, 57, 74):
        bp.spr(r.choice(("bone_spread", "rubble", "skeleton", "gore_pile")), x, 52.0)
    # the slums: one row of hovels facing the canal, the dump and graves behind
    x = 1
    i = 0
    while x < 76:
        w = 4 + (i % 2)
        if any(a - 1 < x + w / 2.0 < b + 1 for a, b in ((11, 15), (38, 43), (63, 67))):
            x += 5
            continue
        shop(bp, x, 55, min(x + w, 78), 60, ["hovel", "hovel", "ruin", "hovel", "store", "hovel", "tavern"][i % 7], "n")
        x += w
        i += 1
    for x in range(3, 76, 6):
        bp.spr(r.choice(("gibbet", "spike_tripod", "bone_spread", "skull_heap", "brambles", "cross_monument",
                         "obelisk_small", "rubble")), x + r.random() * 2, 61.8)
    data = _base("Kurast Scriptorium", W, H, scriptorium=True)
    data["tiles"] = bp.to_tiles()
    data["objects"] = bp.objects
    data["decor"] = bp.decor
    data["rooms"] = bp.rooms
    data["links"] = {"next": 86}
    return data


# ===================================================================================== the dungeon
def build_library():
    W, H = 48, 36
    bp = BP(W, H, 8601)
    r = bp.rng
    rooms = {"vest": (1, 26, 9, 35), "cat": (10, 26, 24, 35), "stacks": (1, 1, 24, 24), "copy": (26, 26, 36, 35),
             "burn": (38, 24, 47, 35), "restr": (26, 10, 37, 23), "oss": (26, 1, 36, 8), "sanct": (39, 1, 47, 22)}
    for x0, y0, x1, y1 in rooms.values():
        bp.fill(x0, y0, x1, y1, 20, (0, 1, 2))
    corridors = [(9, 29, 10, 32), (24, 29, 26, 32), (36, 29, 38, 32), (12, 24, 16, 26), (30, 23, 33, 26),
                 (30, 8, 33, 10), (37, 15, 39, 18), (42, 22, 45, 24)]
    for c in corridors:
        bp.fill(*c, 20, (0, 1, 2))
    B = bp.box
    B(*rooms["vest"], [("e", 29, 32)])
    B(*rooms["cat"], [("w", 29, 32), ("e", 29, 32), ("n", 12, 16)])
    B(*rooms["stacks"], [("s", 12, 16)])
    B(*rooms["copy"], [("w", 29, 32), ("e", 29, 32), ("n", 30, 33)])
    B(*rooms["burn"], [("w", 29, 32), ("n", 42, 45)])
    B(*rooms["restr"], [("s", 30, 33), ("n", 30, 33), ("e", 15, 18)])
    B(*rooms["oss"], [("s", 30, 33)])
    B(*rooms["sanct"], [("w", 15, 18), ("s", 42, 45)])
    for (ax, ay), (bx, by) in (((9, 29), (10, 29)), ((9, 32), (10, 32)), ((24, 29), (26, 29)), ((24, 32), (26, 32)),
                               ((36, 29), (38, 29)), ((36, 32), (38, 32)), ((12, 24), (12, 26)), ((16, 24), (16, 26)),
                               ((30, 23), (30, 26)), ((33, 23), (33, 26)), ((30, 8), (30, 10)), ((33, 8), (33, 10)),
                               ((37, 15), (39, 15)), ((37, 18), (39, 18)), ((42, 22), (42, 24)), ((45, 22), (45, 24))):
        bp.line((ax, ay), (bx, by))
    # 1 the vestibule: the Disused Fane's own stairs up (its north-east corner, cut out), statues, braziers
    bp.rooms.append([1, 26, "act3\\temple\\temple3.ds1", "prev", [9, 0, 4, 4]])
    bp.spr("zealot_statue", 7.6, 27.6)
    bp.spr("hooded_statue", 7.6, 34.0)
    bp.obj(BRAZIER, 2.0, 34.2)
    bp.obj(BRAZIER, 5.0, 34.2)
    # 2 the catalogue hall
    for y in (28.0, 30.3, 32.6):
        for x in (12.0, 14.5, 19.0, 21.5):
            bp.obj(BOOKSHELF[int(x) % 2], x, y)
    for x in (12.5, 17.0, 21.5):
        bp.spr("lectern", x, 34.2)
    bp.obj(CANDLES[0], 23.2, 26.8)
    # 3 the stacks: long shelf rows (aisles), reading alcoves, a collapsed aisle, the scroll vault
    for x in range(4, 23, 3):
        for y0, y1 in ((2.0, 10.0), (13.0, 22.5)):
            if x == 10 and y0 > 10:
                continue
            if x == 4 and y0 < 10:
                continue
            y = y0
            while y <= y1:
                bp.obj(BOOKSHELF[(x + int(y)) % 2], x + 0.5, y)
                y += 1.6
    for y in (11.3,):
        x = 9.5
        while x < 23:
            bp.obj(BOOKSHELF[int(x) % 2], x, y)
            x += 1.6
    for y in (15.0, 17.5, 20.0):
        bp.spr("table", 11.0, y)
        bp.obj(CANDLES[1], 12.2, y)
    for _ in range(9):
        bp.spr(r.choice(("rubble", "debris", "rubble_wall")), 20 + r.random() * 3.5, 14 + r.random() * 6)
    bp.box(1, 1, 7, 7, [("e", 5, 6)])
    bp.fill(1, 1, 7, 7, 22, (0,))
    bp.spr("rug_red", 3.6, 4.4)
    for c in ((2.5, 2.4), (4.6, 2.4)):
        bp.obj(CHEST, *c)
    bp.obj(CHEST2, 2.5, 4.8)
    bp.spr("candelabra", 5.8, 2.0)
    bp.obj(SHRINE_K, 22.8, 2.4)
    # 4 the copying room
    for y in (27.6, 29.9, 32.2):
        bp.spr("feast_table", 31.0, y)
    bp.obj(CANDLES[0], 27.2, 34.3)
    bp.obj(CANDLES[1], 34.8, 34.3)
    bp.obj(BARREL, 35.3, 26.8)
    bp.spr("bookcase", 27.0, 26.8)
    # 5 the burned wing
    bp.scatter(38, 24, 47, 35, 46, (16,), 0.45)
    bp.fill(42, 28, 45, 32, 0, tuple(range(0, 20)))
    for _ in range(10):
        bp.spr(r.choice(("rubble", "debris", "bone_spread", "skeleton")), 38.8 + r.random() * 7.5, 24.8 + r.random() * 9.5)
    bp.objects.append(list(bp.cell(43.5, 30.0)) + [160])                      # a fire burning in the ruin
    bp.obj(CORPSES[0], 40.0, 33.5)
    bp.obj(CORPSES[3], 46.0, 26.0)
    # 6 the restricted section: iron gates, chained tomes, a cage
    bp.spr("iron_fence_gate", 31.5, 10.6)
    bp.spr("iron_fence_short", 31.5, 22.6)
    for x in (27.5, 29.5, 34.0, 36.0):
        y = 12.0
        while y <= 21.0:
            bp.obj(BOOKSHELF[int(y) % 2], x, y)
            y += 1.6
    for y in (14.0, 17.0, 20.0):
        bp.spr("lectern", 31.5, y)
    bp.spr("skeleton_cage", 36.2, 11.2)
    # 7 the ossuary of the scribes
    for x in (27.5, 30.0, 32.5, 35.0):
        bp.spr("sarcophagus", x, 2.4)
    for x in (28.7, 31.2, 33.7):
        bp.spr("reliquary", x, 6.0)
    bp.spr("bone_spread", 27.4, 6.6)
    bp.spr("skull_heap", 35.2, 6.6)
    # 8 the sanctum: Ophizek's dais in a ring of candles, blood pools, his study behind
    bp.fill(39, 5, 47, 22, 22, (0,))
    bp.scatter(39, 5, 47, 17, 46, (16,), 0.4)
    bp.spr("rug_large", 43.0, 8.2)
    bp.box(39, 1, 47, 5, [("s", 42, 44)])
    bp.fill(39, 1, 47, 5, 22, (0,))
    bp.obj(BOOKSHELF[0], 40.4, 1.6)
    bp.obj(BOOKSHELF[1], 45.6, 1.6)
    bp.spr("bench_table", 41.0, 3.6)
    bp.obj(CHEST2, 45.2, 3.6)
    bp.spr("ritual_dais", 43.0, 11.5)
    bp.mark("boss", 43.0, 14.5)
    for c in ((40.2, 6.0), (46.4, 6.0), (40.2, 20.6), (46.4, 20.6)):
        bp.spr("candelabra_great", *c)
    pools = [(1, 0, 5), (2, 0, 6), (3, 0, 7), (0, 1, 8), (1, 1, 9), (2, 1, 10), (3, 1, 11), (0, 2, 12), (1, 2, 13)]
    for px, py in ((39, 17),):
        for dx, dy, sub in pools:
            bp.extra.append([px + dx, py + dy, "df", "act1\\catacomb\\andy3.ds1", 1, sub])
    bp.spr("hanged_skeleton", 46.2, 16.8)
    data = _base("Forbidden Library", W, H, level=86, random_monsters=True, links={"prev": 77})
    data["tiles"] = bp.to_tiles()
    data["objects"] = bp.objects
    data["decor"] = bp.decor
    data["rooms"] = bp.rooms
    data["markers"] = bp.markers
    data["start"] = list(bp.cell(5.0, 31.0))
    return data


def main(path):
    out_dir = os.path.join(ROOT, "assets", "maps")
    os.makedirs(out_dir, exist_ok=True)
    for name, data in (("kurast_scriptorium", build_city()), ("forbidden_library", build_library())):
        with open(os.path.join(out_dir, name + ".json"), "w") as f:
            json.dump(data, f, separators=(",", ":"))
        print("wrote", name, len(data["tiles"]), "tiles", len(data["objects"]), "objects", len(data["decor"]), "sprites")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
