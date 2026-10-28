"""Act 1 built from Diablo 2's own presets.

* One seamless outdoor world: Rogue Encampment, Blood Moor, Cold Plains, Burial Grounds,
  Stony Field, Dark Wood, Black Marsh, Tamoe Highland, Monastery Gate and Outer Cloister.
  Every wilderness area is a 8x8 grid of 8x8-tile blocks like D2's outdoor generator: a ring
  of border presets (Bord1-12, with the "o" opening variants where two areas meet), filled
  with D2's fill presets (stones, fences, ruins, fallen camps, cottages ...), the dungeon
  entrances (DenEnt / CaveDr / Tower / Graveyard), waypoints and quest presets.
* Every dungeon is a separate level, grown room by room from its D2 room presets (caves,
  crypts, barracks, jail, catacombs) or a fixed D2 preset (Forgotten Tower, Countess,
  Tristram, Inner Cloister + Cathedral, Andariel's lair, treasure caves).

Warp tiles: DS1 walls with orientation 10; their "main index" is the Levels.txt vis slot
(vis0 = previous level, vis1 = next, vis3-6 = outdoor entrances, vis4 = down).
DS1 objects: type 1 = monster/NPC presets (MonPreset.txt order), type 2 = objects
(52/53 waypoint, 7-11 cairn stones, 12 Inifuss tree, 25 moldy tome, 36 Horadric Malus, 26 Cain's cage).
"""
import random

from d2.ds1 import DS1
from d2.dt1 import TileSet
from .d2level import TileMap, _dt1_for, SUB, SKIP_ORIENT
from .grid import Grid, FLOOR, WALL

TILES = "data\\global\\tiles\\"
BLOCK = 8                    # tiles per outdoor block
SLOT = 8                     # blocks per outdoor area (64x64 tiles = 320x320 cells)

# MonPreset.txt, act 1 (DS1 type 1 objects)
MONPRESET_A1 = ["gheed", "cain1", "akara", "chicken", "rogue1", "kashya", "cow", "warriv1", "charsi", "andariel",
                "place_fallen", "place_fallenshaman", "place_bloodraven", "cow", "camel", "place_unique_pack",
                "place_npc_pack", "place_nothing", "place_nothing", "place_champion", "navi", "rogue1", "rogue3",
                "gargoyletrap", "place_fallennest", "place_talkingrogue", "place_fallen", "place_fallenshaman",
                "trap-horzmissile", "trap-vertmissile", "place_group25", "place_group50", "place_group75",
                "place_group100", "Bishibosh", "Bonebreak", "Coldcrow", "Rakanishu", "Treehead WoodFist",
                "Griswold", "The Countess", "Pitspawn Fouldog", "Flamespike the Crawler", "Boneash", "The Smith",
                "The Cow King", "Corpsefire"]
TOWN_NPCS = {0: "gheed", 1: "cain1", 2: "akara", 4: "rogue1", 5: "kashya", 7: "warriv1", 8: "charsi", 13: "navi",
             20: "navi"}
QUEST_OBJECTS = {7: "cairn", 8: "cairn", 9: "cairn", 10: "cairn", 11: "cairn", 12: "inifuss", 25: "tome",
                 36: "malus", 26: "cage", 52: "waypoint", 53: "waypoint"}

LEVEL_NAMES = {1: "Rogue Encampment", 2: "Blood Moor", 3: "Cold Plains", 4: "Stony Field", 5: "Dark Wood",
               6: "Black Marsh", 7: "Tamoe Highland", 8: "Den of Evil", 9: "Cave Level 1",
               10: "Underground Passage Level 1", 11: "Hole Level 1", 12: "Pit Level 1", 13: "Cave Level 2",
               14: "Underground Passage Level 2", 15: "Hole Level 2", 16: "Pit Level 2", 17: "Burial Grounds",
               18: "Crypt", 19: "Mausoleum", 20: "Forgotten Tower", 21: "Tower Cellar Level 1",
               22: "Tower Cellar Level 2", 23: "Tower Cellar Level 3", 24: "Tower Cellar Level 4",
               25: "Tower Cellar Level 5", 26: "Monastery Gate", 27: "Outer Cloister", 28: "Barracks",
               29: "Jail Level 1", 30: "Jail Level 2", 31: "Jail Level 3", 32: "Inner Cloister", 33: "Cathedral",
               34: "Catacombs Level 1", 35: "Catacombs Level 2", 36: "Catacombs Level 3", 37: "Catacombs Level 4",
               38: "Tristram"}
OUTDOOR_IDS = (1, 2, 3, 4, 5, 6, 7, 17, 26, 27)
WAYPOINT_LEVELS = [1, 3, 4, 5, 6, 27, 29, 32, 35]         # D2's act 1 waypoint list, in order

# what the dungeons are made of
DUNGEONS = {
    8: dict(kit="cave", rooms=7, roles=["prev", "spec"]),
    9: dict(kit="cave", rooms=7, roles=["prev", "down", "crow"]),
    13: dict(kit="preset", files=["caves\\caveroom2.ds1"], lvltype="Act 1 - Cave"),
    10: dict(kit="cave", rooms=8, roles=["prev", "next", "down"]),
    14: dict(kit="preset", files=["caves\\caveroom3.ds1"], lvltype="Act 1 - Cave"),
    11: dict(kit="cave", rooms=7, roles=["prev", "down"]),
    15: dict(kit="preset", files=["caves\\caveroom4.ds1"], lvltype="Act 1 - Cave"),
    12: dict(kit="cave", rooms=8, roles=["prev", "down"]),
    16: dict(kit="preset", files=["caves\\caveroom5.ds1"], lvltype="Act 1 - Cave"),
    18: dict(kit="crypt", rooms=14, roles=["prev", "bonebreak"]),
    19: dict(kit="crypt", rooms=12, roles=["prev", "consol"]),
    20: dict(kit="preset", files=["outdoors\\tower2.ds1"], lvltype="Act 1 - Wilderness"),
    21: dict(kit="crypt", rooms=12, roles=["prev", "next"]),
    22: dict(kit="crypt", rooms=12, roles=["prev", "next"]),
    23: dict(kit="crypt", rooms=12, roles=["prev", "next"]),
    24: dict(kit="crypt", rooms=12, roles=["prev", "next"]),
    25: dict(kit="preset", files=["crypt\\cryptcountess1.ds1", "crypt\\cryptcountess2.ds1"], lvltype="Act 1 - Crypt"),
    28: dict(kit="barracks", rooms=12, roles=["prev", "next", "forge"]),
    29: dict(kit="jail", rooms=12, roles=["prev", "next", "way", "pitspawn"]),
    30: dict(kit="jail", rooms=12, roles=["prev", "next"]),
    31: dict(kit="jail", rooms=12, roles=["prev", "cath"]),
    32: dict(kit="cathedral"),
    34: dict(kit="catacombs", rooms=12, roles=["prev", "next"]),
    35: dict(kit="catacombs", rooms=12, roles=["prev", "next", "way"]),
    36: dict(kit="catacombs", rooms=12, roles=["prev", "next"]),
    37: dict(kit="preset", files=["catacomb\\andy3.ds1"], lvltype="Act 1 - Catacombs"),
    38: dict(kit="preset", files=["tristram\\tri_town4.ds1"], lvltype="Act 1 - Tristram"),
}
# which world each level lives in
WORLD_OF = {i: "wild" for i in OUTDOOR_IDS}
WORLD_OF.update({i: i for i in DUNGEONS})
WORLD_OF[33] = 32
WORLD_OF[39] = 39

# maze kits: folder, file prefix, role file patterns (d = the one exit direction)
MAZES = {
    "cave": dict(folder="act1\\caves\\", prefix="cave", lvltype="Act 1 - Cave",
                 roles={"prev": "cave{d}pre{n}", "next": "cave{d}next{n}", "down": "cave{d}down{n}",
                        "spec": "cave{d}spec", "crow": "cave{d}crow"}, theme="cave{x}theme1"),
    "crypt": dict(folder="act1\\crypt\\", prefix="crypt", lvltype="Act 1 - Crypt",
                  roles={"prev": "crypt{d}warpprev", "next": "crypt{d}warpnext", "bonebreak": "crypt{d}bonebreak",
                         "consol": "crypt{d}consol"}, theme="crypt{x}theme"),
    "barracks": dict(folder="act1\\barracks\\", prefix="bar", lvltype="Act 1 - Barracks",
                     roles={"prev": "court{d}b", "next": "bar{d}warp", "forge": "bar{d}forge"}, theme="bar{x}theme1"),
    "jail": dict(folder="act1\\barracks\\", prefix="jail", lvltype="Act 1 - Jail",
                 roles={"prev": "jail{d}warpprev", "next": "jail{d}warpnext", "cath": "jail{d}warpcath",
                        "way": "jail{d}way", "pitspawn": "jail{d}pitspawn"}, theme="jail{x}theme"),
    "catacombs": dict(folder="act1\\catacomb\\", prefix="cat", lvltype="Act 1 - Catacombs",
                      roles={"prev": "cat{x}up{n}", "next": "cat{d}down{n}", "way": "cat{d}way"}, theme="cat{x}theme1"),
}
COMBOS = ["n", "s", "e", "w", "ne", "nw", "ns", "se", "sw", "ew", "nse", "nsw", "new", "sew", "nsew"]
DIRS = {"n": (0, -1), "s": (0, 1), "w": (-1, 0), "e": (1, 0)}
OPP = {"n": "s", "s": "n", "w": "e", "e": "w"}


def _canon(ex):
    return "".join(c for c in "nsew" if c in ex)


def _path(name):
    name = name.replace("/", "\\").lower()
    if name.startswith(("act1\\", "act2\\", "act3\\", "act4\\", "expansion\\")):
        return TILES + name
    return TILES + "act1\\" + name


class Built:
    """Output of a level builder: tiles + what the World needs to know about them."""

    def __init__(self, tw, th):
        self.tm = TileMap(tw, th)
        self.tm.floor2 = {}
        self.warps = []           # (tile (tx, ty), main, level row id of the level owning it)
        self.objects = []         # (kind/id, cell, owner level)
        self.presets = []         # (monpreset name, cell, owner level)
        self.npcs = []
        self.areas = {}           # level id -> (x0, y0, x1, y1) cell rect
        self.edge_exits = []      # (cells, target level) - doors without warp tiles


class LevelKit:
    """DS1/DT1 cache shared by all builders."""

    def __init__(self, src, levels_rows=None, lvltypes=None):
        self.src = src
        self.dt1_cache = {}
        self.ds1_cache = {}
        self.tileset_cache = {}
        self.levels = {int(r["id"]): r for r in (levels_rows or []) if r.get("id", "").isdigit()}
        self.lvltypes = {}
        for r in lvltypes or []:
            files = [v for k, v in r.items() if k.startswith("file") and v and v != "0"]
            self.lvltypes[r.get("name", "")] = files
        self._grass = None
        self.mazes = {}

    def ds1(self, name):
        p = _path(name) if not name.lower().startswith("data\\") else name.lower()
        if p not in self.ds1_cache:
            self.ds1_cache[p] = DS1(self.src.read(p), p.rsplit("\\", 1)[-1]) if self.src.has(p) else None
        return self.ds1_cache[p]

    def tiles_for(self, ds, extra_type=None):
        files = list(ds.files)
        if extra_type and extra_type in self.lvltypes:
            files += ["\\d2\\data\\global\\tiles\\" + f.replace("/", "\\") for f in self.lvltypes[extra_type]]
        key = tuple(sorted(set(f.lower() for f in files)))
        if key not in self.tileset_cache:
            self.tileset_cache[key] = TileSet(_dt1_for(self.src, files, self.dt1_cache))
        return self.tileset_cache[key]

    def vis(self, level_id, main):
        r = self.levels.get(level_id)
        if not r:
            return None
        try:
            v = int(r.get("vis%d" % main) or 0)
        except ValueError:
            v = 0
        return v or None


def stamp(b, ds, tiles, ox, oy, rng, owner, skip_npc_objects=False):
    """Copy a DS1 into the level: floors, walls, warp markers, monster presets, objects."""
    tm = b.tm
    w, h = ds.width, ds.height
    for y in range(h):
        for x in range(w):
            pos = (ox + x, oy + y)
            for li, layer in enumerate(ds.floors):
                c = layer[y * w + x]
                if c.empty or c.hidden:
                    continue            # hidden = editor markers D2 never draws
                t = tiles.pick(0, c.main, c.sub, rng.randrange(1 << 16))
                if t:
                    if li == 0:
                        tm.floor[pos] = t
                    else:
                        tm.floor2[pos] = t
            walls = []
            for layer in ds.walls:
                c = layer[y * w + x]
                if c.empty:
                    continue
                if c.orientation in (10, 11) and c.main < 8:
                    b.warps.append((pos, c.main, owner))
                    continue
                if c.hidden:
                    continue
                if c.orientation in SKIP_ORIENT or c.orientation == 0:
                    continue
                orients = [c.orientation, 4] if c.orientation == 3 else [c.orientation]
                for o in orients:
                    t = tiles.pick(o, c.main, c.sub, rng.randrange(1 << 16))
                    if t:
                        walls.append(t)
            if walls:
                tm.walls[pos] = walls
            elif pos in tm.walls:
                del tm.walls[pos]
    # what the DS1's object numbers mean depends on the act (Built carries the act's tables)
    monpreset = getattr(b, "monpreset", MONPRESET_A1)
    town_npcs = getattr(b, "town_npcs", TOWN_NPCS)
    quest_objects = getattr(b, "quest_objects", QUEST_OBJECTS)
    town_id = getattr(b, "town_id", 1)
    for typ, oid, x, y in ds.objects:
        cell = (ox * SUB + x, oy * SUB + y)
        if typ == 1:
            name = monpreset[oid] if oid < len(monpreset) else ""
            if oid in town_npcs and owner == town_id:
                b.npcs.append((town_npcs[oid], cell))
            elif name and not name.startswith("place_nothing"):
                b.presets.append((name, cell, owner))
        elif typ == 2 and oid in quest_objects:
            b.objects.append((quest_objects[oid], cell, owner, oid))


# ---------------------------------------------------------------- fast walkability
_MASKS = {}


def _mask(tile, blocked_value):
    k = (id(tile), blocked_value)
    m = _MASKS.get(k)
    if m is None:
        f = tile.flags
        m = tuple(tuple(i for i in range(SUB) if f[(4 - sy) * SUB + i] & 1) for sy in range(SUB))
        _MASKS[k] = m
    return m


def make_grid(tm):
    W, H = tm.tw * SUB, tm.th * SUB
    cells = [[WALL] * W for _ in range(H)]
    for (tx, ty), (_, tile) in tm.floor.items():
        bl = _mask(tile, 1)
        x0 = tx * SUB
        for sy in range(SUB):
            y = ty * SUB + sy
            if y >= H:
                break
            row = cells[y]
            row[x0:x0 + SUB] = [FLOOR] * SUB
            for i in bl[sy]:
                row[x0 + i] = WALL
    for src in (getattr(tm, "floor2", {}), None):
        if src is None:
            break
        for (tx, ty), (_, tile) in src.items():
            bl = _mask(tile, 1)
            alone = (tx, ty) not in tm.floor          # a second-layer floor with nothing under it is the floor
            for sy in range(SUB):
                y = ty * SUB + sy
                if y >= H:
                    break
                row = cells[y]
                if alone:
                    row[tx * SUB:tx * SUB + SUB] = [FLOOR] * SUB
                if not bl[sy]:
                    continue
                for i in bl[sy]:
                    if tx * SUB + i < W:
                        row[tx * SUB + i] = WALL
    for (tx, ty), lst in tm.walls.items():
        for _, tile in lst:
            bl = _mask(tile, 1)
            for sy in range(SUB):
                y = ty * SUB + sy
                if y >= H or not bl[sy]:
                    continue
                row = cells[y]
                for i in bl[sy]:
                    if tx * SUB + i < W:
                        row[tx * SUB + i] = WALL
    g = Grid(1, 1, WALL)
    g.w, g.h = W, H
    g.cells = cells
    g.explored = [[False] * W for _ in range(H)]
    g.visible = [[False] * W for _ in range(H)]
    g.explored_cells = []
    return g


def warp_cells(grid, tile, radius=2):
    """Walkable cells at a warp tile: walking onto them uses the entrance."""
    tx, ty = tile
    out = []
    for r in (radius, radius + 2, radius + 4):
        for y in range(ty * SUB - r, ty * SUB + SUB + r):
            for x in range(tx * SUB - r, tx * SUB + SUB + r):
                if grid.walkable(x, y):
                    out.append((x, y))
        if out:
            break
    return out


def arrival_cell(grid, exit_cells, avoid, rng=None, dist=4):
    """A walkable spot a few steps away from an entrance (you arrive next to it, like D2)."""
    from collections import deque
    ex = set(exit_cells)
    q = deque((c, 0) for c in exit_cells)
    seen = set(exit_cells)
    best = None
    while q:
        c, d = q.popleft()
        if d >= dist and c not in avoid:
            return c
        if d > dist + 6:
            break
        for nb in grid.neighbors(*c):
            if nb not in seen:
                seen.add(nb)
                q.append((nb, d + 1))
                if nb not in ex and nb not in avoid:
                    best = nb
    return best or (exit_cells[0] if exit_cells else None)


# ---------------------------------------------------------------- the outdoor world
class OutdoorKit(LevelKit):
    FILLS = {
        "common": ["Act1/Outdoors/Circle.ds1", "Act1/Outdoors/XRock.ds1", "Act1/Outdoors/6Rock.ds1",
                   "Act1/Outdoors/Clover.ds1", "Act1/Outdoors/Arrow.ds1", "Act1/Outdoors/4Rock.ds1",
                   "Act1/Outdoors/Corral1.ds1", "Act1/Outdoors/Corral2.ds1", "Act1/Outdoors/Wild5.ds1",
                   "Act1/Outdoors/FallCmp.ds1", "Act1/Outdoors/FallCmp2.ds1", "Act1/Outdoors/FallCmp3.ds1",
                   "Act1/Outdoors/FallCmp4.ds1", "Act1/Outdoors/FallCmp5.ds1", "Act1/Outdoors/FallCmp6.ds1",
                   "Act1/Outdoors/Camp.ds1", "Act1/Outdoors/Pond1.ds1", "Act1/Outdoors/Cott1.ds1",
                   "Act1/Outdoors/Cott2.ds1", "Act1/Outdoors/Cott3.ds1", "Act1/Outdoors/Cott4.ds1",
                   "Act1/Outdoors/Cott5.ds1", "Act1/Outdoors/Cott6.ds1", "Act1/Outdoors/Cott1A.ds1",
                   "Act1/Outdoors/Cott3A.ds1", "Act1/Outdoors/Cott7.ds1"],
        "big": ["Act1/Outdoors/Wild1.ds1", "Act1/Outdoors/Wild2.ds1", "Act1/Outdoors/Wild3.ds1",
                "Act1/Outdoors/Wild4.ds1", "Act1/Outdoors/Trees2.ds1", "Act1/Outdoors/Trees3.ds1",
                "Act1/Outdoors/Ruin2.ds1", "Act1/Outdoors/Bivouac.ds1"],
        "swamp": ["Act1/Outdoors/Swamp3.ds1", "Act1/Outdoors/Swamp4.ds1"],
        "swampbig": ["Act1/Outdoors/Swamp5.ds1"],
    }
    EDGE = {"n": "bord3", "s": "bord1", "w": "bord2", "e": "bord4"}
    CORNER = {("n", "w"): "bord6", ("n", "e"): "bord7", ("s", "e"): "bord8", ("s", "w"): "bord5"}

    def __init__(self, src, levels_rows=None, lvltypes=None):
        super().__init__(src, levels_rows, lvltypes)
        self.towns = []
        for n in ("townn1", "towne1", "towns1", "townw1"):
            ds = self.ds1("act1\\town\\%s.ds1" % n)
            if ds is not None:
                self.towns.append((n, ds))
        if not self.towns:
            raise FileNotFoundError("Rogue Encampment layouts not found")
        if self.ds1("Act1/Outdoors/Bord1.ds1") is None:
            raise FileNotFoundError("outdoor border presets (bord1.ds1) not found")

    def grass(self):
        """Plain grass (floor main/sub codes) taken from an outdoor preset."""
        if self._grass is None:
            ds = self.ds1("Act1/Outdoors/Bord1.ds1")
            codes = []
            for y in range(0, 3):
                for x in range(ds.width):
                    c = ds.floors[0][y * ds.width + x]
                    if not c.empty:
                        codes.append((c.main, c.sub))
            self._grass = (ds, codes or [(0, 0)])
        return self._grass


def _town_exit_dir(name):
    return {"townn1": "n", "towne1": "e", "towns1": "s", "townw1": "w"}[name]


def plan_slots(exit_dir, rng):
    """Positions of the areas on a grid of 64x64-tile slots (a self-avoiding snake like D2's act 1)."""
    d = DIRS[exit_dir]
    perp = [(d[1], d[0]), (-d[1], -d[0])]
    rng.shuffle(perp)
    for turn in perp:
        pos = {1: (0, 0)}
        add = lambda a, b: (a[0] + b[0], a[1] + b[1])
        pos[2] = add(pos[1], d)
        pos[3] = add(pos[2], d)
        pos[4] = add(pos[3], turn)
        pos[5] = add(pos[4], turn)
        back = (-d[0], -d[1])
        pos[6] = add(pos[5], back)
        pos[7] = add(pos[6], back)
        pos[17] = add(pos[3], (-turn[0], -turn[1]))
        # the Monastery gate opens to the south, so it has to sit north of Tamoe Highland
        mg = add(pos[7], (0, -1))
        if mg not in pos.values():
            pos[26] = mg
        elif add(pos[6], (0, -1)) not in pos.values():
            pos[26] = add(pos[6], (0, -1))
            pos["mg_from"] = 6
        if len(set(v for k, v in pos.items() if k != "mg_from")) == len([k for k in pos if k != "mg_from"]):
            return pos
    return pos


def build_outdoors(kit, seed=None, content=None):
    rng = random.Random(seed)
    tname, town = rng.choice(kit.towns)
    exit_dir = _town_exit_dir(tname)
    pos = plan_slots(exit_dir, rng)
    mg_from = pos.pop("mg_from", 7)
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    mnx, mny = min(xs), min(ys)
    pos = {k: (v[0] - mnx, v[1] - mny) for k, v in pos.items()}
    cols, rows = max(p[0] for p in pos.values()) + 1, max(p[1] for p in pos.values()) + 1
    ST = SLOT * BLOCK                                   # tiles per slot side
    b = Built(cols * ST + 1, rows * ST + 1)
    b.slot_of = {v: k for k, v in pos.items()}
    b.slot_tiles = ST
    for lid, (sx, sy) in pos.items():
        b.areas[lid] = (sx * ST * SUB, sy * ST * SUB, (sx + 1) * ST * SUB, (sy + 1) * ST * SUB)
    gds, gcodes = kit.grass()
    gtiles = kit.tiles_for(gds, "Act 1 - Wilderness")

    links = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (3, 17)]
    if 26 in pos:
        links.append((mg_from, 26))
    neighbours = {}
    for a, c in links:
        da = (pos[c][0] - pos[a][0], pos[c][1] - pos[a][1])
        dname = next(k for k, v in DIRS.items() if v == da)
        neighbours.setdefault(a, {})[dname] = c
        neighbours.setdefault(c, {})[OPP[dname]] = a
    # opening block index along each shared edge (same index on both sides lines them up)
    openings = {}
    for a, c in links:
        idx = rng.randrange(2, SLOT - 2)
        openings[(a, c)] = openings[(c, a)] = idx

    def grass_block(tx0, ty0, w=BLOCK, h=BLOCK):
        for y in range(h):
            for x in range(w):
                main, sub = rng.choice(gcodes)
                t = gtiles.pick(0, main, sub, rng.randrange(1 << 16))
                if t:
                    b.tm.floor[(tx0 + x, ty0 + y)] = t

    def put(name, tx0, ty0, owner, extra_type="Act 1 - Wilderness"):
        ds = kit.ds1(name)
        if ds is None:
            return None
        stamp(b, ds, kit.tiles_for(ds, extra_type), tx0, ty0, rng, owner)
        return ds

    # ---- the camp
    tsx, tsy = pos[1]
    tw, th = town.width - 1, town.height - 1
    ox = tsx * ST + {"e": ST - tw, "w": 0}.get(exit_dir, (ST - tw) // 2)
    oy = tsy * ST + {"s": ST - th, "n": 0}.get(exit_dir, (ST - th) // 2)
    stamp(b, town, kit.tiles_for(town, "Act 1 - Town"), ox, oy, rng, 1)
    b.town_rect = (ox * SUB, oy * SUB, (ox + tw) * SUB, (oy + th) * SUB)

    # ---- wilderness areas
    for lid in (2, 3, 4, 5, 6, 7, 17):
        sx, sy = pos[lid]
        tx0, ty0 = sx * ST, sy * ST
        nb = neighbours.get(lid, {})
        taken = set()
        for bx in range(SLOT):
            for by in range(SLOT):
                edge_n, edge_s, edge_w, edge_e = by == 0, by == SLOT - 1, bx == 0, bx == SLOT - 1
                if not (edge_n or edge_s or edge_w or edge_e):
                    continue
                taken.add((bx, by))
                X, Y = tx0 + bx * BLOCK, ty0 + by * BLOCK
                vert = "n" if edge_n else ("s" if edge_s else None)
                hor = "w" if edge_w else ("e" if edge_e else None)
                if vert and hor:
                    put("Act1/Outdoors/%s.ds1" % OutdoorKit.CORNER[(vert, hor)], X, Y, lid)
                    continue
                side = vert or hor
                along = bx if vert else by
                other = nb.get(side)
                if other is not None and openings.get((lid, other)) == along:
                    if other == 1:
                        grass_block(X, Y)          # the camp's own fence closes this side
                    else:
                        put("Act1/Outdoors/%so.ds1" % OutdoorKit.EDGE[side], X, Y, lid)
                elif other == 1:
                    grass_block(X, Y)
                else:
                    v = rng.choice(["", "", "b", "c"]) if side in "nsew" else ""
                    name = "Act1/Outdoors/%s%s.ds1" % (OutdoorKit.EDGE[side], v)
                    if put(name, X, Y, lid) is None:
                        put("Act1/Outdoors/%s.ds1" % OutdoorKit.EDGE[side], X, Y, lid)
        inner = [(bx, by) for bx in range(1, SLOT - 1) for by in range(1, SLOT - 1)]
        rng.shuffle(inner)

        def place(name, w=1, h=1, owner=lid):
            for bx, by in inner:
                cells = [(bx + i, by + j) for i in range(w) for j in range(h)]
                if all(1 <= c[0] < SLOT - 1 and 1 <= c[1] < SLOT - 1 and c not in taken for c in cells):
                    if put(name, tx0 + bx * BLOCK, ty0 + by * BLOCK, owner) is None:
                        return False
                    taken.update(cells)
                    return True
            return False
        # entrances, waypoints, quest spots first
        specials = {
            2: ["Act1/Caves/DenEnt.ds1" if rng.random() < 0.5 else "Act1/Caves/DenEnt2.ds1"],
            3: ["Act1/Caves/CaveDr1.ds1", "Act1/Outdoors/Waypoint.ds1", "Act1/Outdoors/FallCmpBish.ds1"],
            4: ["Act1/Caves/CaveDr2.ds1", "Act1/Outdoors/Waypoint.ds1", "Act1/Outdoors/cairn2.ds1",
                "Act1/Outdoors/tome.ds1"],
            5: ["Act1/Caves/CaveDr1.ds1", "Act1/Outdoors/Waypoint.ds1", "Act1/Outdoors/funktree.ds1"],
            6: ["Act1/Caves/CaveDr2.ds1", "Act1/Outdoors/Waypoint.ds1", "Act1/Outdoors/Tower1.ds1"],
            7: ["Act1/Caves/CaveDr1.ds1"],
        }.get(lid, [])
        if lid == 17:
            place("act1\\graveyard\\gravey.ds1", 3, 4)
        for sp in specials:
            place(sp)
        fill_names = kit.FILLS["swamp"] + kit.FILLS["common"][:6] if lid == 6 else kit.FILLS["common"]
        for _ in range(3):
            place(rng.choice(kit.FILLS["swampbig"] if lid == 6 else kit.FILLS["big"]), 2, 2)
        for bx, by in list(inner):
            if (bx, by) in taken:
                continue
            if rng.random() < 0.33:
                place(rng.choice(fill_names))
        for bx, by in inner:
            if (bx, by) not in taken:
                grass_block(tx0 + bx * BLOCK, ty0 + by * BLOCK)
                taken.add((bx, by))

    # ---- Monastery Gate + Outer Cloister (D2: the cloister sits right behind the gate)
    if 26 in pos:
        sx, sy = pos[26]
        tx0, ty0 = sx * ST, sy * ST
        facade = kit.ds1("act1\\monastry\\facade1.ds1")
        court = None
        for nm in ("act1\\court\\courtn.ds1", "act1\\court\\courtw.ds1", "act1\\court\\courte.ds1"):
            if kit.ds1(nm) is not None:
                court = kit.ds1(nm) if court is None or rng.random() < 0.4 else court
        if facade is not None:
            fw, fh = facade.width - 1, facade.height - 1
            fy = ty0 + ST - fh
            stamp(b, facade, kit.tiles_for(facade, "Act 1 - Monestary"), tx0 + (ST - fw) // 2, fy, rng, 26)
            b.areas[26] = ((tx0) * SUB, fy * SUB, (tx0 + ST) * SUB, (ty0 + ST) * SUB)
            if court is not None:
                cw, ch = court.width - 1, court.height - 1
                cx, cy = tx0 + (ST - cw) // 2, fy - ch
                stamp(b, court, kit.tiles_for(court, "Act 1 - Courtyard"), cx, cy, rng, 27)
                b.areas[27] = (tx0 * SUB, ty0 * SUB, (tx0 + ST) * SUB, fy * SUB)
                b.court_rect = (cx, cy, cw, ch)
        b.mg_from = mg_from
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    _connect(b, grid, pos, links, kit, rng, openings)
    return b, grid, rng


def build_cow(kit, seed=None, content=None):
    """The Moo Moo Farm (level 39): one Act 1 wilderness area of 80x80 tiles, D2's border ring
    and wilderness fills, no exits (you leave through the red portal)."""
    rng = random.Random(seed)
    size = 10
    b = Built(size * BLOCK + 1, size * BLOCK + 1)
    b.areas[39] = (0, 0, size * BLOCK * SUB, size * BLOCK * SUB)
    gds, gcodes = kit.grass()
    gtiles = kit.tiles_for(gds, "Act 1 - Wilderness")

    def grass_block(tx0, ty0):
        for y in range(BLOCK):
            for x in range(BLOCK):
                main, sub = rng.choice(gcodes)
                t = gtiles.pick(0, main, sub, rng.randrange(1 << 16))
                if t:
                    b.tm.floor[(tx0 + x, ty0 + y)] = t

    def put(name, tx0, ty0):
        ds = kit.ds1(name)
        if ds is None:
            return None
        stamp(b, ds, kit.tiles_for(ds, "Act 1 - Wilderness"), tx0, ty0, rng, 39)
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
            v = rng.choice(["", "", "b", "c"])
            if put("Act1/Outdoors/%s%s.ds1" % (OutdoorKit.EDGE[side], v), bx * BLOCK, by * BLOCK) is None:
                put("Act1/Outdoors/%s.ds1" % OutdoorKit.EDGE[side], bx * BLOCK, by * BLOCK)
    inner = [(bx, by) for bx in range(1, size - 1) for by in range(1, size - 1)]
    rng.shuffle(inner)

    def place(name, w=1, h=1):
        for bx, by in inner:
            cells = [(bx + i, by + j) for i in range(w) for j in range(h)]
            if all(1 <= c[0] < size - 1 and 1 <= c[1] < size - 1 and c not in taken for c in cells):
                if put(name, bx * BLOCK, by * BLOCK) is None:
                    return False
                taken.update(cells)
                return True
        return False
    for _ in range(3):
        place(rng.choice(OutdoorKit.FILLS["big"]), 2, 2)
    fills = [f for f in OutdoorKit.FILLS["common"] if "FallCmp" not in f and "Camp" not in f]
    for bx, by in list(inner):
        if (bx, by) not in taken and rng.random() < 0.3:
            place(rng.choice(fills))
    for bx, by in inner:
        if (bx, by) not in taken:
            grass_block(bx * BLOCK, by * BLOCK)
            taken.add((bx, by))
    # D2's markers in the fills are the wilderness' own (fallen camps ...): the farm only has cows
    b.presets = [p for p in b.presets if p[0] == "The Cow King"]
    b.npcs = []
    b.objects = []
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    if not b.presets:
        for _ in range(200):
            c = (rng.randrange(3 * BLOCK, 7 * BLOCK) * SUB, rng.randrange(3 * BLOCK, 7 * BLOCK) * SUB)
            if grid.walkable(*c):
                b.presets.append(("The Cow King", c, 39))
                break
    return b, grid, rng


def _connect(b, grid, pos, links, kit, rng, openings):
    """Make sure every area can be walked into from the previous one (carve a path if presets
    don't line up exactly - e.g. the camp's exit or the Monastery gate)."""
    ST = b.slot_tiles
    for a, c in links:
        ra, rc = b.areas.get(a), b.areas.get(c)
        if not ra or not rc:
            continue
        ca = _walk_centre(grid, ra, b, a)
        cc = _walk_centre(grid, rc, b, c)
        if ca is None or cc is None:
            continue
        if grid.find_path(ca, cc, limit=400000) is not None:
            continue
        _carve(b, grid, ca, cc, kit, rng)


def _walk_centre(grid, rect, b, lid):
    x0, y0, x1, y1 = rect
    if lid == 1 and hasattr(b, "town_rect"):
        x0, y0, x1, y1 = b.town_rect
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    for r in range(0, max(x1 - x0, y1 - y0) // 2, 3):
        for dy in range(-r, r + 1, 3):
            for dx in range(-r, r + 1, 3):
                if grid.walkable(cx + dx, cy + dy):
                    return (cx + dx, cy + dy)
    return None


def _carve(b, grid, a, c, kit, rng):
    """Straight-ish 3-tile-wide trail between two cells: walls removed, grass laid."""
    gds, gcodes = kit.grass()
    gtiles = kit.tiles_for(gds, "Act 1 - Wilderness")
    x, y = a[0] // SUB, a[1] // SUB
    ex, ey = c[0] // SUB, c[1] // SUB
    tm = b.tm
    while (x, y) != (ex, ey):
        if abs(ex - x) > abs(ey - y):
            x += 1 if ex > x else -1
        else:
            y += 1 if ey > y else -1
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                p = (x + dx, y + dy)
                tm.walls.pop(p, None)
                tm.floor2.pop(p, None)
                main, sub = rng.choice(gcodes)
                t = gtiles.pick(0, main, sub, rng.randrange(1 << 16))
                if t:
                    tm.floor[p] = t
                tm.drawn.add(p)
                for sy in range(SUB):
                    for sx in range(SUB):
                        cx, cy = p[0] * SUB + sx, p[1] * SUB + sy
                        if grid.in_bounds(cx, cy):
                            grid.cells[cy][cx] = FLOOR


# ---------------------------------------------------------------- dungeons
class MazeKit:
    def __init__(self, kit, name):
        spec = MAZES[name]
        self.kit, self.spec = kit, spec
        self.rooms = {}
        folder, prefix = spec["folder"], spec["prefix"]
        self.variants = spec.get("variants", ("", "1", "2", "3", "4"))
        for combo in COMBOS:
            for n in self.variants:
                ds = kit.ds1(folder + "%s%s%s.ds1" % (prefix, combo, n))
                if ds is not None:
                    self.rooms.setdefault(frozenset(combo), []).append(ds)
        if len(self.rooms) < spec.get("min_kinds", 15):
            raise FileNotFoundError("%s rooms missing (%d of 15 kinds)" % (name, len(self.rooms)))
        any_room = next(iter(self.rooms.values()))[0]
        self.rw, self.rh = any_room.width - 1, any_room.height - 1

    def role_room(self, role, exits, rng):
        pat = self.spec["roles"].get(role)
        if not pat:
            return None
        cands = []
        pats = pat if isinstance(pat, (list, tuple)) else [pat]
        for p, n in [(p, n) for p in pats for n in tuple(self.variants) + ("",)]:
            nm = p.format(d=_canon(exits), x=_canon(exits), n=n)
            ds = self.kit.ds1(self.spec["folder"] + nm + ".ds1")
            if ds is not None and ds not in cands:
                cands.append(ds)
        return rng.choice(cands) if cands else None


def _grow(n, rng, cols, rows):
    start = (rng.randrange(cols), rng.randrange(rows))
    rooms = {start: set()}
    guard = 0
    while len(rooms) < n and guard < 5000:
        guard += 1
        frm = rng.choice(list(rooms))
        d = rng.choice(list(DIRS))
        nb = (frm[0] + DIRS[d][0], frm[1] + DIRS[d][1])
        if not (0 <= nb[0] < cols and 0 <= nb[1] < rows) or nb in rooms:
            continue
        rooms[frm].add(d)
        rooms[nb] = {OPP[d]}
    return rooms


def build_maze(kit, level_id, spec, seed=None):
    mk = kit.mazes.get(spec["kit"])
    if mk is None:
        mk = kit.mazes[spec["kit"]] = MazeKit(kit, spec["kit"])
    rng = random.Random(seed)
    roles = spec.get("roles", [])
    cols = rows = spec.get("grid", 5 if spec["rooms"] > 9 else 4)
    for attempt in range(60):
        layout = _grow(spec["rooms"], rng, cols, rows)
        assign = {}
        leaves = [c for c, ex in layout.items() if len(ex) == 1]
        rng.shuffle(leaves)
        ok = True
        for role in roles:
            rp = mk.spec["roles"].get(role, "")
            if "{x}" in (rp if isinstance(rp, str) else " ".join(rp)):
                cand = [c for c, ex in layout.items() if c not in assign and mk.role_room(role, ex, rng) is not None]
            else:
                cand = [c for c in leaves if c not in assign and mk.role_room(role, layout[c], rng) is not None]
            if not cand:
                ok = False
                break
            assign[cand[0]] = role
        if ok:
            break
    mx = min(x for x, _ in layout)
    my = min(y for _, y in layout)
    layout = {(x - mx, y - my): ex for (x, y), ex in layout.items()}
    assign = {(x - mx, y - my): r for (x, y), r in assign.items()}
    cw = max(x for x, _ in layout) + 1
    ch = max(y for _, y in layout) + 1
    b = Built(cw * mk.rw + 1, ch * mk.rh + 1)
    act_tables(b, spec.get("act", 1), kit)
    lt = mk.spec["lvltype"]
    for (rx, ry), ex in layout.items():
        role = assign.get((rx, ry))
        ds = mk.role_room(role, ex, rng) if role else None
        if ds is None:
            ds = rng.choice(mk.rooms[frozenset(ex)])
        stamp(b, ds, kit.tiles_for(ds, lt), rx * mk.rw, ry * mk.rh, rng, level_id)
        if role:
            b.__dict__.setdefault("role_rooms", {})[role] = (rx * mk.rw, ry * mk.rh, mk.rw, mk.rh)
        if role == "prev" and spec["kit"] == "barracks":
            # the court connection has no warp tile: its open side leads back to the cloister
            b.court_room = (rx * mk.rw, ry * mk.rh, mk.rw, mk.rh)
    b.areas[level_id] = (0, 0, b.tm.tw * SUB, b.tm.th * SUB)
    grid = make_grid(b.tm)
    used = set()
    for (tx, ty) in b.tm.floor:
        used.add((tx, ty))
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    return b, grid, rng


def build_preset(kit, level_id, spec, seed=None):
    rng = random.Random(seed)
    if spec["kit"] == "cathedral":
        court = kit.ds1("act1\\court\\cat_court.ds1")
        cath = kit.ds1("act1\\cathedrl\\cathy3.ds1")
        cw, chh = court.width - 1, court.height - 1
        tw, th = cath.width - 1, cath.height - 1
        # Levels.txt: the Cathedral sits at offset (-4, -34) from the Inner Cloister
        ox, oy = 4, th
        W, H = max(ox + cw, tw) + 1, oy + chh + 1
        b = Built(W, H)
        stamp(b, cath, kit.tiles_for(cath, "Act 1 - Cathedral"), 0, 0, rng, 33)
        stamp(b, court, kit.tiles_for(court, "Act 1 - Courtyard"), ox, oy, rng, 32)
        b.areas[33] = (0, 0, W * SUB, oy * SUB)
        b.areas[32] = (0, oy * SUB, W * SUB, H * SUB)
    else:
        folder = spec.get("folder", "act1\\")
        name = rng.choice([f for f in spec["files"] if kit.ds1(folder + f) is not None] or spec["files"])
        ds = kit.ds1(folder + name)
        if ds is None:
            raise FileNotFoundError(name)
        b = Built(ds.width, ds.height)
        act_tables(b, spec.get("act", 1), kit)
        stamp(b, ds, kit.tiles_for(ds, spec.get("lvltype")), 0, 0, rng, level_id)
        b.areas[level_id] = (0, 0, ds.width * SUB, ds.height * SUB)
    b.tm.drawn = set(b.tm.floor) | set(b.tm.walls) | set(b.tm.floor2)
    grid = make_grid(b.tm)
    return b, grid, rng


def act_tables(b, act, kit):
    """Give a Built the object / monster number tables of its act (Act 1 is the default)."""
    if act and act != 1:
        from .acts import apply_act_tables
        apply_act_tables(b, act, kit)


def build_level(kit, level_id, seed=None):
    if level_id not in DUNGEONS:
        from . import act2
        return act2.build_level(kit, level_id, seed)
    spec = DUNGEONS[level_id]
    if spec["kit"] in MAZES:
        return build_maze(kit, level_id, spec, seed)
    return build_preset(kit, level_id, spec, seed)
