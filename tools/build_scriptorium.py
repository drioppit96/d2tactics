"""Builds the Kurast Scriptorium (the city quarter west of the Bazaar) and the Forbidden Library (the
dungeon under it) as map-editor maps: assets/maps/kurast_scriptorium.json and forbidden_library.json.

    python tools/build_scriptorium.py <path to your Diablo II folder or extracted files>

The layouts follow the sketches (north up, 1 square = 1 floor tile). Everything in them is Diablo II's
own art: its tiles and its objects (Objects.txt) - no sprites of this game. Once written, the maps
are edited by hand in the map editor; running this again replaces those edits.

The story the rooms tell: when Mephisto's zealots came for the Scriptorium, the scribes tried to save
the books. They barricaded Scribes' Row, burned what they could not carry in the plaza and the
archive, and carried the rest down into the library under the temple. The zealots followed. The
temple guard died on its steps; the scribes who reached the library died among the shelves.
"""
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FIELDSTONE, PLASTER = 20, 24
STAIRS = (31, 7)             # Kurast terrace steps (a floor tile)
BLOODY = (46, 16)            # a blood-stained flagstone (walkable)

# ---- Diablo II's own objects (Objects.txt ids), by what they are here
SHELF = (179, 180)                                  # bookshelves (you can search them)
BENCH, STOOL, BEDS = 10, 256, (247, 248)
CANDLES = (33, 34)
BRAZIER, BRAZIER_TALL, BRAZIER_SMALL, BRAZIER_CELLAR = 102, 286, 287, 283
TORCH, TORCH_TOWN, WALL_TORCH = 328, 370, (296, 297)
FIRE_S, FIRE_M, FIRE_L, BONFIRE = 160, 161, 162, 39
CHESTS = (5, 6, 139, 141, 144, 176, 177, 240, 241)  # wooden chests
RICH_CHESTS = (329, 330, 331, 332, 387, 389, 390, 391)  # Mephisto's / the Arcane Sanctuary's
CASKETS = (1, 3, 50, 51, 53, 365)
CRATE, BOX = 46, 204                                # a crate / a strongbox (searchable)
BASKETS = (208, 209, 362)
URNS = (4, 9, 52, 94, 95)
BARREL, BARREL_X = 7, 11
SARCOPHAGI = (89, 284)
COFFIN = 182
ALTAR = 205
WELL_K, MANA_K = 344, 343                          # Kurast health / mana wells
FOUNTAIN = 31
STANDARDS = (35, 36)                                # banners on poles
WEAPON_RACKS, ARMOR_STANDS = (106, 107), (104, 105)
DEAD_TOWN = (271, 272)                              # dead villagers: the scribes
DEAD_GUARD = (154, 270)                             # Kurast guards
DEAD_HAREM = (314, 315, 316, 317)
DEAD_SEWER = 326
BURNING = (239, 245)                                # bodies still burning
SKELETONS = (158, 171)
IMPALED = (57, 58, 178)                             # on stakes: a warning
HUNG = 363
SKULLS = (225, 126)
BONE_CHEST = 372
BLOOD_POOL = 82                                     # a bubbling pool of blood
RATNEST = 244
COCOONS = (223, 224)
DEATHPOLE = (456, 457)
SWINGING_HEADS = 446


class BP:
    """A blueprint in tile coordinates: floors, wall lines, pillars, objects, markers."""

    def __init__(self, w, h, seed):
        self.w, self.h = w, h
        self.rng = random.Random(seed)
        self.floor = {}
        self.floor2 = {}
        self.lines = {FIELDSTONE: [], PLASTER: []}
        self.pillars = []
        self.objects = []
        self.markers = []
        self.rooms = []
        self.extra = []
        self.used = []

    def fill(self, x0, y0, x1, y1, main, subs=(0,), layer=1):
        dst = self.floor if layer == 1 else self.floor2
        for y in range(int(y0), int(y1)):
            for x in range(int(x0), int(x1)):
                if 0 <= x < self.w and 0 <= y < self.h:
                    dst[(x, y)] = (main, self.rng.choice(subs))

    def scatter(self, x0, y0, x1, y1, main, subs, chance, layer=1):
        dst = self.floor if layer == 1 else self.floor2
        for y in range(int(y0), int(y1)):
            for x in range(int(x0), int(x1)):
                if self.rng.random() < chance:
                    dst[(x, y)] = (main, self.rng.choice(subs))

    def blood(self, x0, y0, x1, y1, chance=0.35):
        self.scatter(x0, y0, x1, y1, BLOODY[0], (BLOODY[1],), chance)

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

    @staticmethod
    def cell(x, y):
        return int(round(x * 5 + 2)), int(round(y * 5 + 2))

    def obj(self, oid, x, y):
        """An object at tile (x, y); a choice when oid is a tuple. Two things never share a spot."""
        if isinstance(oid, (tuple, list)):
            oid = self.rng.choice(oid)
        c = self.cell(x, y)
        if any(abs(c[0] - u[0]) + abs(c[1] - u[1]) < 4 for u in self.used):
            return
        self.used.append(c)
        self.objects.append([c[0], c[1], oid])

    def row(self, oid, x0, x1, y, step):
        x = x0
        while x <= x1 + 1e-6:
            self.obj(oid, x, y)
            x += step

    def col(self, oid, x, y0, y1, step):
        y = y0
        while y <= y1 + 1e-6:
            self.obj(oid, x, y)
            y += step

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
    d = {"version": 1, "revision": 2, "name": name, "act": 3, "lvltype": "Act 3 - Kurast", "width": w, "height": h,
         "level": level, "random_monsters": True, "rooms": [], "tiles": [], "objects": [], "monsters": [],
         "decor": [], "markers": [], "start": None, "exits": []}
    d.update(kw)
    return d


# ======================================================================================== the city
def house(bp, x0, y0, x1, y1, kind, door):
    """A house on Scribes' Row or in the slums, furnished with D2's own objects."""
    hut = kind in ("home", "hovel")
    bp.fill(x0, y0, x1, y1, 27 if hut else 20, (0, 1, 2, 3) if hut else (0, 1, 2))
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    bp.box(x0, y0, x1, y1, [(door, int(cx) - 1, int(cx) + 1)], PLASTER)
    r = bp.rng
    back = y0 + 0.7 if door == "s" else y1 - 0.7
    front = y1 - 1.3 if door == "s" else y0 + 1.3
    if kind == "scribe":         # a copyist's shop: shelves at the back, his bench, a candle; often he lies dead
        bp.obj(SHELF, x0 + 1.2, back)
        bp.obj(SHELF, x1 - 1.4, back)
        bp.obj(BENCH, cx, cy)
        bp.obj(CANDLES, x1 - 0.9, cy)
        if r.random() < 0.6:
            bp.obj(DEAD_TOWN, x0 + 1.0, front)
            bp.blood(x0, y0, x1, y1, 0.25)
        else:
            bp.obj(CASKETS, x0 + 1.0, front)
    elif kind == "home":         # beds, a stool, the family's chest and pots
        bp.obj(BEDS, x0 + 1.2, back)
        bp.obj(STOOL, x1 - 1.2, cy)
        bp.obj(CHESTS, x1 - 1.0, back)
        if r.random() < 0.5:
            bp.obj(URNS, x0 + 0.9, front)
    elif kind == "store":        # a paper-and-ink store: crates, baskets, the strongbox
        bp.obj(CRATE, x0 + 1.0, back)
        bp.obj(CRATE, x0 + 2.2, back)
        bp.obj(BASKETS, x1 - 1.0, back)
        bp.obj(BOX, x1 - 1.0, front)
        bp.obj(BARREL, x0 + 1.0, front)
    elif kind == "tavern":
        bp.obj(BENCH, cx - 1.0, cy)
        bp.obj(BENCH, cx + 1.2, cy)
        bp.obj(BARREL, x1 - 0.8, back)
        bp.obj(BARREL, x1 - 1.8, back)
        bp.obj(BARREL_X, x0 + 0.9, back)
        bp.obj(DEAD_TOWN, cx, front)
    elif kind == "binder":       # the bookbinder's: half-bound books on the shelves, a bench, crates
        bp.obj(SHELF, x1 - 1.2, back)
        bp.obj(BENCH, x0 + 1.4, cy)
        bp.obj(CRATE, x0 + 1.0, back)
    elif kind == "barricade":    # the scribes' barricade: crates, barrels, and the dead behind it
        bp.obj(CRATE, x0 + 1.0, cy)
        bp.obj(CRATE, x0 + 2.2, cy)
        bp.obj(BARREL, x1 - 1.0, cy)
        bp.obj(DEAD_TOWN, cx, back)
        bp.blood(x0, y0, x1, y1, 0.4)
    elif kind == "hovel":
        bp.obj(BEDS if r.random() < 0.5 else BASKETS, x0 + 1.2, back)
        bp.obj(URNS, x1 - 1.0, back)
        if r.random() < 0.4:
            bp.obj((DEAD_SEWER,) + DEAD_TOWN, cx, front)
        elif r.random() < 0.4:
            bp.obj(RATNEST, x1 - 1.0, front)
    elif kind == "ruin":         # burnt out: bodies still smouldering
        bp.blood(x0, y0, x1, y1, 0.3)
        bp.obj(BURNING, cx, cy)
        bp.obj(FIRE_S, x0 + 1.0, back)
        bp.obj(SKELETONS, x1 - 1.0, front)


def build_city():
    W, H = 80, 64
    bp = BP(W, H, 7702)
    r = bp.rng
    # ground by tier: the upper terrace and middle streets paved, the lower quarter mud
    bp.fill(0, 0, W, 44, 20, (0, 1, 2))
    bp.fill(0, 44, W, H, 2, tuple(range(0, 19)))
    bp.scatter(0, 44, W, H, 0, tuple(range(0, 20)), 0.35)
    bp.scatter(0, 0, W, 44, 21, (0,), 0.04)
    bp.box(0, 0, 79, 64, [("e", 24, 39)], FIELDSTONE)                # open east, to the Bazaar
    for y, gaps in ((18, [(11, 15), (38, 43), (70, 76)]), (44, [(7, 11), (29, 33), (55, 59)])):
        cur = 0
        for g0, g1 in gaps:
            bp.line((cur, y), (g0, y), FIELDSTONE)
            cur = g1
        bp.line((cur, y), (79, y), FIELDSTONE)
        for g0, g1 in gaps:
            bp.fill(g0, y - 1, g1, y + 1, STAIRS[0], (STAIRS[1],))
            bp.obj(TORCH, g0 - 0.4, y + 0.9)
            bp.obj(TORCH, g1 + 0.4, y + 0.9)

    # ================= UPPER TERRACE
    # Archivists' Cloister: the monks died in their cells; the garden court is a graveyard of books
    bp.box(1, 1, 22, 16, [("s", 11, 15)], FIELDSTONE)
    for k in range(5):
        x = 1 + 4 * k
        bp.box(x, 1, x + 4, 5, [("s", x + 1, x + 3)], PLASTER)
        bp.fill(x, 1, x + 4, 5, 27, (0, 1, 2, 3))
        bp.obj(BEDS, x + 1.0, 1.8)
        bp.obj(SHELF, x + 3.0, 1.6)
        bp.obj(DEAD_TOWN if k % 2 == 0 else CASKETS, x + 2.2, 3.8)
    for j in range(2):
        y = 6 + 4 * j
        bp.box(1, y, 5, y + 4, [("e", y + 1, y + 3)], PLASTER)
        bp.fill(1, y, 5, y + 4, 27, (0, 1, 2, 3))
        bp.obj(BEDS, 1.9, y + 1.2)
        bp.obj(CHESTS, 3.9, y + 3.2)
    bp.fill(7, 7, 21, 14, 1, tuple(range(3, 20)))                    # the garden court
    for x in range(7, 22, 3):
        bp.pillar(x, 7)
        bp.pillar(x, 14)
    bp.obj(WELL_K, 13.5, 10.5)
    bp.obj(BONFIRE, 10.0, 9.0)                                       # books burned in the garden
    bp.obj(SHELF, 9.0, 11.6)
    bp.obj(DEAD_TOWN, 17.5, 9.0)
    bp.obj(HUNG, 18.5, 12.5)
    bp.obj(BRAZIER, 6.2, 15.2)
    bp.obj(BRAZIER, 20.8, 15.2)

    # The Great Scriptorium: the desks overturned, the scribes cut down at their work
    bp.box(24, 1, 57, 16, [("s", 38, 43), ("w", 12, 14), ("e", 12, 14)], FIELDSTONE)
    for x in (31, 50):
        bp.line((x, 1), (x, 6), PLASTER)
        bp.line((x, 9), (x, 12), PLASTER)
        bp.line((x, 14), (x, 16), PLASTER)
    bp.fill(31, 1, 50, 16, 22, (0,))
    for x in range(33, 50, 4):
        bp.pillar(x, 5)
        bp.pillar(x, 12)
    bp.row(SHELF, 32.5, 49.0, 1.6, 2.0)                              # the shelf wall behind the altar
    for y in (7.0, 9.0, 11.0):                                       # rows of copyists' benches
        for x in (34.5, 37.5, 43.5, 46.5):
            bp.obj(BENCH, x, y)
    bp.obj(ALTAR, 40.5, 3.4)                                         # the great lectern
    bp.obj(CANDLES[0], 38.6, 3.4)
    bp.obj(CANDLES[1], 42.4, 3.4)
    for c in ((35.5, 8.0), (44.8, 10.0), (40.5, 12.2), (47.8, 7.6)):
        bp.obj(DEAD_TOWN, *c)
    bp.obj(DEAD_GUARD, 40.5, 14.8)
    bp.blood(32, 6, 50, 14, 0.3)
    bp.obj(BRAZIER_TALL, 32.6, 14.6)
    bp.obj(BRAZIER_TALL, 48.4, 14.6)
    bp.obj(STANDARDS, 36.0, 2.2)
    bp.obj(STANDARDS, 45.0, 2.2)
    # Hall of Records: shelf rows, the caskets of the old charters
    bp.fill(24, 1, 31, 16, 22, (0,))
    for y in (2.6, 5.6, 9.4, 13.0):
        bp.row(SHELF, 25.6, 29.6, y, 2.0)
    bp.obj(CASKETS, 25.2, 15.2)
    bp.obj(CASKETS, 29.8, 15.2)
    bp.obj(DEAD_TOWN, 27.5, 7.4)
    # Illumination Chamber: benches, candles, the illuminators' chests of pigment and gold leaf
    bp.fill(50, 1, 57, 16, 22, (0,))
    for y in (3.5, 7.5, 11.0):
        bp.obj(BENCH, 53.5, y)
        bp.obj(CANDLES, 55.6, y)
    bp.obj(RICH_CHESTS, 51.2, 1.8)
    bp.obj(CHESTS, 56.0, 1.8)
    bp.obj(SHELF, 51.4, 14.8)

    # The burned archive: the scribes burned what they could not carry
    bp.box(58, 1, 63, 12, [("s", 59, 62)], FIELDSTONE)
    bp.fill(58, 1, 63, 12, 0, tuple(range(0, 20)))
    bp.blood(58, 1, 63, 12, 0.3)
    bp.obj(FIRE_L, 60.5, 4.0)
    bp.obj(FIRE_M, 61.0, 8.0)
    bp.obj(BURNING, 59.4, 6.0)
    bp.obj(SKELETONS, 61.8, 10.4)
    bp.obj(SHELF, 59.4, 2.0)
    # The temple over the Forbidden Library: its guard died on the steps
    bp.rooms.append([62, 1, "act3\\kurast\\metrotemple2.ds1", "next"])
    bp.fill(58, 13, 79, 18, 20, (0, 1, 2))
    bp.blood(63, 13, 79, 18, 0.25)
    for c in ((66.0, 15.5), (71.0, 14.0), (74.5, 16.2), (77.5, 13.6)):
        bp.obj(DEAD_GUARD, *c)
    bp.obj(DEAD_HAREM, 68.5, 16.8)
    bp.obj(IMPALED, 64.0, 13.6)
    bp.obj(IMPALED, 78.0, 16.8)
    bp.obj(BRAZIER_TALL, 69.4, 17.2)
    bp.obj(BRAZIER_TALL, 76.6, 17.2)
    bp.obj(WEAPON_RACKS, 59.4, 13.8)

    # ================= MIDDLE TIER
    # the Ink Road to the Bazaar gate: lit by town torches, a cart overturned
    bp.fill(50, 25, 79, 38, 20, (0, 1, 2))
    for x in (55, 63, 71):
        bp.obj(TORCH_TOWN, x, 25.8)
        bp.obj(TORCH_TOWN, x, 37.2)
    bp.obj(CRATE, 66.5, 29.5)
    bp.obj(CRATE, 67.6, 30.3)
    bp.obj(BARREL, 65.6, 30.6)
    bp.obj(DEAD_GUARD, 74.0, 33.0)
    # Plaza of Quills: the zealots' book burning, the heretics on stakes, the stalls abandoned
    bp.fill(32, 20, 50, 42, 20, (0, 1, 2))
    bp.fill(39, 29, 44, 34, 46, (2,))
    bp.obj(FOUNTAIN, 41.5, 31.5)
    bp.obj(BONFIRE, 37.0, 26.5)
    bp.obj(FIRE_M, 38.6, 27.6)
    bp.obj(SHELF, 35.6, 25.4)
    for c in ((36.0, 36.0), (46.5, 26.0), (47.0, 35.0)):
        bp.obj(IMPALED, *c)
    bp.obj(SWINGING_HEADS, 44.0, 23.0)
    bp.objects.append(list(bp.cell(46.5, 39.0)) + ["waypoint"])
    for x in range(33, 49, 3):
        bp.obj((CRATE,) + BASKETS + URNS, x + 0.5, 20.8)
        bp.obj(BASKETS + URNS + (BARREL,), x + 0.5, 41.2)
    for c in ((32.8, 24.0), (49.2, 24.0), (32.8, 38.0), (49.2, 38.0)):
        bp.obj(BRAZIER, *c)
    bp.obj(MANA_K, 33.4, 33.5)
    bp.blood(34, 22, 48, 40, 0.12)
    bp.obj(DEAD_TOWN, 40.0, 35.0)
    bp.obj(DEAD_TOWN, 44.5, 29.0)

    # Scribes' Row
    cols = [(1, 6), (6, 11), (11, 16), (18, 23), (23, 28), (28, 31)]
    kinds = ["scribe", "home", "scribe", "store", "binder", "home", "scribe", "tavern", "home", "scribe",
             "store", "scribe", "home", "binder", "scribe", "home", "store", "scribe", "ruin", "home",
             "scribe", "home", "scribe", "store"]
    k = 0
    for y0, y1, door in ((19, 25, "n"), (25, 31, "s"), (34, 38, "n"), (38, 42, "s")):
        for x0, x1 in cols:
            house(bp, x0, y0, x1, y1, kinds[k % len(kinds)], door)
            k += 1
    bp.fill(1, 31, 31, 34, 20, (0, 1, 2))
    bp.fill(16, 19, 18, 42, 20, (0, 1, 2))
    # the barricade across the lane of the copyists, and the dead on both sides of it
    for x in (19.0, 20.2, 21.4):
        bp.obj(CRATE, x, 32.0)
    bp.obj(BARREL, 22.6, 32.6)
    bp.obj(BARREL_X, 18.0, 32.8)
    bp.obj(DEAD_TOWN, 20.5, 33.3)
    bp.obj(DEAD_GUARD, 24.5, 32.0)
    bp.blood(17, 31, 26, 34, 0.4)
    bp.obj(TORCH, 16.0, 32.4)
    for x in (4.0, 9.0, 13.5, 28.0):
        bp.obj((CRATE,) + BASKETS, x, 32.4)

    # East quarter: Ink Works (vats = great urns), Paper Mill, storehouse; Bookbinders' Guild, guard post
    bp.box(51, 19, 60, 25, [("s", 54, 57)], FIELDSTONE)
    bp.fill(51, 19, 60, 25, 22, (0,))
    for x in (52.4, 54.6, 56.8):
        bp.obj((4, 94, 95), x, 20.6)
    bp.row(BARREL, 52.0, 54.0, 23.8, 1.0)
    bp.obj(DEAD_SEWER, 58.5, 23.0)
    bp.box(61, 19, 70, 25, [("s", 64, 67)], FIELDSTONE)
    bp.fill(61, 19, 70, 25, 22, (0,))
    bp.row(BASKETS, 62.0, 69.0, 20.4, 1.4)
    bp.obj(CRATE, 62.4, 23.6)
    bp.obj(CRATE, 68.8, 23.6)
    bp.box(71, 19, 78, 25, [("s", 73, 76)], PLASTER)
    bp.fill(71, 19, 78, 25, 27, (0, 1, 2, 3))
    bp.row(CRATE, 72.0, 77.0, 20.2, 1.2)
    bp.obj(BOX, 72.2, 23.6)
    bp.obj(CHESTS, 77.0, 23.6)
    bp.box(51, 38, 68, 43, [("n", 58, 61)], FIELDSTONE)            # Bookbinders' Guild
    bp.fill(51, 38, 68, 43, 22, (0,))
    bp.line((57, 38), (57, 40), PLASTER)
    bp.line((57, 42), (57, 43), PLASTER)
    bp.line((62, 38), (62, 40), PLASTER)
    bp.line((62, 42), (62, 43), PLASTER)
    bp.obj(BENCH, 53.0, 40.5)
    bp.obj(BENCH, 55.4, 40.5)
    bp.row(SHELF, 63.4, 66.8, 42.2, 1.7)
    bp.obj(ALTAR, 59.5, 41.6)
    bp.obj(RICH_CHESTS, 67.2, 39.0)
    bp.obj(CRATE, 52.0, 42.2)
    bp.obj(DEAD_TOWN, 60.0, 39.4)
    bp.box(70, 38, 78, 43, [("n", 73, 75)], FIELDSTONE)            # the guard post, emptied for the temple
    bp.fill(70, 38, 78, 43, 22, (0,))
    bp.obj(WEAPON_RACKS[0], 71.4, 42.2)
    bp.obj(WEAPON_RACKS[1], 73.8, 42.2)
    bp.obj(ARMOR_STANDS, 76.6, 41.8)
    bp.obj(BRAZIER_SMALL, 77.2, 39.0)
    bp.obj(CHESTS, 70.8, 39.0)
    bp.fill(68, 38, 70, 44, 20, (0, 1))

    # ================= LOWER QUARTER
    for x in range(2, 78, 5):                                       # the canal-side market, abandoned
        if any(a - 1 <= x <= b for a, b in ((7, 11), (29, 33), (55, 59))):
            continue
        bp.obj((CRATE, BARREL) + BASKETS + URNS, x + 1.0, 46.4)
        bp.obj(BASKETS + URNS, x + 2.6, 47.2)
    bp.fill(0, 50, 79, 54, 0, tuple(range(0, 20)))                  # the drained canal
    bp.scatter(0, 50, 79, 54, 1, tuple(range(3, 20)), 0.3)
    bridges = ((11, 15), (38, 43), (63, 67))
    steps = ((4, 7), (25, 28), (52, 55), (71, 74))                   # stairs down into the canal bed
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
    # the canal bed: where the dead were thrown
    for x in (2.0, 9.0, 19.0, 22.0, 33.0, 47.0, 58.0, 61.0, 70.0, 77.0):
        bp.obj(SKELETONS + SKULLS + (DEAD_SEWER, RATNEST), x, 52.0 + r.random() * 1.2)
    bp.obj(BONE_CHEST, 35.0, 52.4)
    bp.obj(BLOOD_POOL, 48.5, 51.6)
    # the slums: one row of hovels facing the canal, the graves behind
    x = 1
    i = 0
    while x < 76:
        w = 4 + (i % 2)
        if any(a - 1 < x + w / 2.0 < b + 1 for a, b in bridges):
            x += 5
            continue
        house(bp, x, 55, min(x + w, 78), 60, ["hovel", "hovel", "ruin", "hovel", "store", "hovel", "tavern"][i % 7], "n")
        x += w
        i += 1
    for x in range(3, 76, 6):
        bp.obj((COFFIN,) + SKULLS + DEATHPOLE + (HUNG,) + IMPALED, x + r.random() * 2, 61.8)
    data = _base("Kurast Scriptorium", W, H, scriptorium=True)
    data["tiles"] = bp.to_tiles()
    data["objects"] = bp.objects
    data["rooms"] = bp.rooms
    data["links"] = {"next": 86}
    return data


# ===================================================================================== the dungeon
def build_library():
    W, H = 48, 36
    bp = BP(W, H, 8602)
    r = bp.rng
    rooms = {"vest": (1, 26, 9, 35), "cat": (10, 26, 24, 35), "stacks": (1, 1, 24, 24), "copy": (26, 26, 36, 35),
             "burn": (38, 24, 47, 35), "restr": (26, 10, 37, 23), "oss": (26, 1, 36, 8), "sanct": (39, 1, 47, 22)}
    for x0, y0, x1, y1 in rooms.values():
        bp.fill(x0, y0, x1, y1, 20, (0, 1, 2))
    for c in ((9, 29, 10, 32), (24, 29, 26, 32), (36, 29, 38, 32), (12, 24, 16, 26), (30, 23, 33, 26),
              (30, 8, 33, 10), (37, 15, 39, 18), (42, 22, 45, 24)):
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
    # 1 the vestibule: the Disused Fane's own stairs up; the books the scribes dragged down, left here
    bp.rooms.append([1, 26, "act3\\temple\\temple3.ds1", "prev", [9, 0, 4, 4]])
    bp.obj(BRAZIER_CELLAR, 2.0, 34.2)
    bp.obj(BRAZIER_CELLAR, 8.0, 34.2)
    bp.obj(CRATE, 7.6, 27.4)
    bp.obj(CRATE, 6.4, 27.4)
    bp.obj(BASKETS, 7.8, 28.8)
    bp.obj(DEAD_TOWN, 5.6, 33.0)
    bp.blood(1, 30, 9, 35, 0.3)
    # 2 the catalogue hall: card shelves; a scribe killed while hiding the index
    for y in (28.0, 30.4, 32.8):
        bp.row(SHELF, 11.6, 15.6, y, 2.0)
        bp.row(SHELF, 18.4, 22.4, y, 2.0)
    bp.obj(CASKETS, 17.0, 34.2)
    bp.obj(DEAD_TOWN, 17.0, 31.4)
    bp.obj(CANDLES, 23.2, 26.8)
    bp.obj(CANDLES, 10.8, 26.8)
    # 3 the stacks: long shelf rows, reading benches, a collapsed aisle, the scroll vault
    for x in range(4, 23, 3):
        for y0, y1 in ((2.0, 10.0), (13.0, 22.5)):
            if (x == 10 and y0 > 10) or (x == 4 and y0 < 10):
                continue
            bp.col(SHELF, x + 0.5, y0, y1, 1.7)
    bp.row(SHELF, 9.5, 23.0, 11.3, 1.7)
    for y in (15.0, 17.5, 20.0):
        bp.obj(BENCH, 11.0, y)
    bp.obj(CANDLES, 12.0, 21.6)
    bp.obj(DEAD_TOWN, 12.0, 16.2)
    bp.obj(SKELETONS, 7.0, 18.4)
    for c in ((20.6, 15.0), (21.8, 17.2), (20.6, 19.4)):           # the collapsed aisle
        bp.obj(SKULLS, *c)
    bp.obj(COCOONS, 22.8, 21.6)
    bp.obj(COCOONS, 2.2, 22.6)
    bp.box(1, 1, 7, 7, [("e", 5, 6)])                               # the scroll vault
    bp.fill(1, 1, 7, 7, 22, (0,))
    bp.obj(RICH_CHESTS[0], 2.4, 2.4)
    bp.obj(RICH_CHESTS[5], 4.6, 2.4)
    bp.obj(CASKETS, 2.4, 5.0)
    bp.obj(BOX, 5.8, 2.2)
    bp.obj(CANDLES, 5.8, 5.6)
    bp.obj(MANA_K, 22.8, 2.4)
    # 4 the copying room: the copyists' benches, ink barrels, their last copies in the chests
    for y in (27.6, 29.9, 32.2):
        bp.obj(BENCH, 28.6, y)
        bp.obj(BENCH, 33.4, y)
    bp.obj(CANDLES, 27.2, 34.3)
    bp.obj(CANDLES, 34.8, 34.3)
    bp.obj(BARREL, 35.3, 26.8)
    bp.obj(BARREL, 34.2, 26.8)
    bp.obj(CHESTS, 27.0, 26.8)
    bp.obj(DEAD_TOWN, 31.0, 31.0)
    # 5 the burned wing: the fire that took the restricted copies still burns
    bp.blood(38, 24, 47, 35, 0.45)
    bp.fill(42, 28, 45, 32, 0, tuple(range(0, 20)))
    bp.obj(FIRE_L, 43.5, 30.0)
    bp.obj(FIRE_S, 40.0, 26.0)
    bp.obj(FIRE_S, 46.0, 33.6)
    for c in ((39.6, 33.4), (45.8, 26.2), (41.0, 30.6)):
        bp.obj(BURNING, *c)
    bp.obj(SKELETONS, 44.6, 33.8)
    bp.obj(SHELF, 39.4, 24.8)
    # 6 the restricted section: shelves of forbidden books, a scribe hanged among them
    for x in (27.5, 29.5, 34.0, 36.0):
        bp.col(SHELF, x, 12.0, 21.0, 1.7)
    bp.obj(HUNG, 31.5, 13.6)
    bp.obj(SARCOPHAGI, 31.5, 17.0)
    bp.obj(CASKETS, 31.5, 20.4)
    bp.obj(BOX, 36.2, 11.2)
    bp.obj(WALL_TORCH, 30.6, 10.8)
    # 7 the ossuary of the scribes: sarcophagi, coffins, the bones of every scribe who served
    for x in (27.5, 30.0, 32.5, 35.0):
        bp.obj(SARCOPHAGI, x, 2.4)
    for x in (28.6, 31.2, 33.8):
        bp.obj(COFFIN, x, 6.0)
    bp.obj(BONE_CHEST, 27.2, 6.8)
    bp.obj(SKULLS, 35.2, 6.6)
    bp.obj(CANDLES, 31.2, 4.4)
    # 8 the sanctum: Ophizek's altar in a ring of hellfire and candles, the blood pools, his study
    bp.fill(39, 5, 47, 22, 22, (0,))
    bp.blood(39, 5, 47, 17, 0.45)
    bp.box(39, 1, 47, 5, [("s", 42, 44)])
    bp.fill(39, 1, 47, 5, 22, (0,))
    bp.obj(SHELF, 40.4, 1.6)
    bp.obj(SHELF, 45.6, 1.6)
    bp.obj(BENCH, 41.0, 3.6)
    bp.obj(RICH_CHESTS[1], 45.2, 3.6)
    bp.obj(ALTAR, 43.0, 10.5)
    bp.mark("boss", 43.0, 13.5)
    for c in ((40.4, 8.4), (45.6, 8.4), (40.4, 12.8), (45.6, 12.8)):
        bp.obj((345, 346, 347), *c)                                  # hellfire round the altar
    for c in ((40.2, 6.0), (46.4, 6.0), (40.2, 20.6), (46.4, 20.6)):
        bp.obj(BRAZIER_TALL, *c)
    bp.obj(CANDLES, 43.0, 6.4)
    bp.obj(DEAD_TOWN, 41.6, 15.6)
    bp.obj(HUNG, 46.2, 16.8)
    pools = [(1, 0, 5), (2, 0, 6), (3, 0, 7), (0, 1, 8), (1, 1, 9), (2, 1, 10), (3, 1, 11), (0, 2, 12), (1, 2, 13)]
    for dx, dy, sub in pools:
        bp.extra.append([39 + dx, 17 + dy, "df", "act1\\catacomb\\andy3.ds1", 1, sub])
    data = _base("Forbidden Library", W, H, level=86, links={"prev": 77})
    data["tiles"] = bp.to_tiles()
    data["objects"] = bp.objects
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
        print("wrote", name, len(data["tiles"]), "tiles", len(data["objects"]), "objects")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
