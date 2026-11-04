"""D2 Tactics map editor - for the game's own hand-made maps (assets/maps: the Kurast Armory, and the
ones added later): D2 tiles, walls, pillars, rooms, objects, monsters, the game's decoration sprites and
markers (the armory's altars and smith spot). Open lists those maps; nothing else is edited here.
Save writes your copy to maps/<name>.json, which the game then uses instead of its own.

Start it with "Map Editor.bat" (it reads your Diablo II files like the game does).
Maps are saved as JSON in the maps folder (see game/custommap.py for the format). A map whose
"level" is set to a level id replaces that level in the game (entered through an entrance,
e.g. a cave or a tomb).

  Left panel     Floor / Wall / Room / Object / Monster / Marker / Sprite palettes (Tab or click a tab)
                 Object: every placeable thing - D2 objects and the game's sprites - in folders
                 (Furniture, Light & fire, Chests...); click a folder to open it
                 type to search, Backspace / Esc clears the search, mouse wheel scrolls
  Map            left click / drag: place     right click / drag: remove     middle drag or arrows: pan
                 mouse wheel: zoom
  Toolbar buttons (top) do everything below; the Ctrl shortcuts still work:
  Ctrl+S save    Ctrl+O open    Ctrl+N new map    Ctrl+Z undo    Ctrl+G grid on/off
  Ctrl+R rename  Ctrl+L level it replaces    Ctrl+M random monsters on/off
  Ctrl+F floor layer 1 / 2 (layer 2 lies on top: roads, rugs, decals)
  Ctrl+K monster placement: normal / pack / champion / unique
  Ctrl+[ / Ctrl+]  tileset (level type)      PageUp / PageDown  act
  Ctrl+Arrows    map size (4 tiles a step)
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from render.iso import cell_to_world, Camera  # noqa: E402
from game import custommap  # noqa: E402

PANEL_W = 290
TOP_H = 92                     # info line + two rows of buttons
BOT_H = 24
TABS = ["Floor", "Wall", "Room", "Object", "Monster", "Marker", "Sprite"]
DECOR_DIR = os.path.join(ROOT, "assets", "decor")
BG = (14, 12, 10)
PANEL = (28, 24, 20)
LINE = (90, 78, 52)
GOLD = (199, 179, 119)
WHITE = (230, 230, 230)
GREY = (150, 150, 150)
SEL = (70, 58, 30)
ZOOMS = [1.0, 0.75, 0.5, 0.35, 0.25]
KINDS = ["normal", "pack", "champion", "unique"]
ORIENT = {1: "left wall", 2: "right wall", 3: "corner", 5: "end", 6: "end", 7: "corner", 8: "door", 9: "door",
          12: "pillar", 14: "tree / prop", 15: "roof", 16: "lower wall", 17: "lower wall", 18: "lower wall",
          19: "lower wall"}


def _act_of(lvltype):
    m = re.match(r"\s*act\s*(\d)", lvltype, re.I)
    return int(m.group(1)) if m else 1


# the Object tab: D2's objects and this game's sprites together, sorted into folders
CATEGORIES = ["Buildings", "Waypoints & portals", "Doors & gates", "Chests & containers", "Light & fire",
              "Furniture", "Forge & weapon racks", "Statues & pillars", "Banners & signs",
              "Shrines, wells & fountains", "Pottery & urns", "Torture & executions", "Corpses & remains",
              "Fences, walls & ruins", "Floors & rugs", "Nature", "Quest & special", "Other D2 objects",
              "Invisible (no picture)"]
_OBJ_RULES = [("Waypoints & portals", ("waypoint", "portal")),
              ("Doors & gates", ("door", "gate", "portcullis")),
              ("Shrines, wells & fountains", ("shrine", "well", "healthwell", "manawell", "fountain", "pool")),
              ("Quest & special", ("seal", "orifice", "quest", "horadric", "hellforge", "altar", "tome",
                                   "cairn", "trap", "stone theta", "stonetheta", "inifuss", "sanctuary")),
              ("Light & fire", ("torch", "brazier", "fire", "candle", "lamp", "lantern", "light", "flame", "pyre",
                                "burning")),
              ("Forge & weapon racks", ("rack", "armor stand", "weapon stand", "anvil")),
              ("Chests & containers", ("chest", "casket", "coffin", "sarcophag", "stash", "box", "basket", "jar",
                                       "barrel", "crate", "bag", "sack", "cabinet", "armoir", "bookshel",
                                       "bookcase", "wardrobe", "loose", "pile")),
              ("Pottery & urns", ("urn", "vase", "pot", "amphora")),
              ("Furniture", ("bench", "table", "chair", "bed", "throne", "stool", "desk", "shelf")),
              ("Banners & signs", ("banner", "sign", "flag", "pennant")),
              ("Torture & executions", ("gibbet", "stake", "pike", "cage", "gallow", "rack", "impale", "hung",
                                        "hanging", "heads")),
              ("Corpses & remains", ("corpse", "body", "skeleton", "bone", "skull", "dead", "guy", "carcass",
                                     "rotting", "remains", "blood", "gore")),
              ("Statues & pillars", ("statue", "pillar", "obelisk", "column", "gargoyle", "totem", "idol",
                                     "stone", "pedestal")),
              ("Nature", ("tree", "bush", "plant", "log", "stump", "rock", "grass", "flower", "reed", "tumbleweed",
                          "cactus", "mushroom", "boulder", "weed", "vine", "fungus")),
              ("Fences, walls & ruins", ("fence", "wall", "ruin", "rubble", "arch"))]
_SPRITE_CATS = {
    "Buildings": "cathedral demon_shrine fortress blood_spire_shrine banner_gate watchtower ruined_arch altar_pyramid "
                 "ritual_dais arch_colonnade lava_cave shrine_gate",
    "Furniture": "bunks table bookcase wardrobe cabinet throne beds stool round_table low_bench bench_table feast_table "
                 "lectern",
    "Forge & weapon racks": "anvil forge grindstone weaponrack armorstand shieldrack arrows dummy target spear_rack",
    "Chests & containers": "chest crates kegs sacks barrels_stack chests_stack trunk open_crate crate barrel bucket "
                           "stone_chest cart bone_cart reliquary sarcophagus",
    "Light & fire": "candles candle candelabra candelabra_great torch_stand goblet_brazier lantern_post cauldron "
                    "cauldron_tripod cauldron_big",
    "Statues & pillars": "statue zealot_statue hooded_statue hooded_statue_small gargoyle obelisk obelisk_small "
                         "cross_monument post post_short spire spire_small pedestal stone_block",
    "Shrines, wells & fountains": "well washbasin font chalice_font",
    "Pottery & urns": "vase vase_small amphora urn urn_stone jug pots pot",
    "Torture & executions": "gibbet spikes skeleton_cage gallows_double hanging_cage pillory iron_chair breaking_wheel "
                            "chopping_block bloody_table meat_rack hanged_skeleton hook_gallows spike_tripod "
                            "torture_ladder rack_frame stake",
    "Corpses & remains": "bones blood debris skull skull_small skulls skulls_small skull_heap skull_heap2 bone "
                         "bone_heap bone_scatter bone_spread skeleton skeletons gore_pile",
    "Fences, walls & ruins": "fence_wall_ruin ruin_arch_wall rubble_wall wall_ruin stone_arch ruin_chunk candle_arch "
                             "rubble",
    "Floors & rugs": "blood_tile dirt_patch gravel_patch web_patch",
    "Nature": "dead_tree brambles rock_pile stone_pile firewood"}
_SPRITE_CAT = {n: c for c, names in _SPRITE_CATS.items() for n in names.split()}


def sprite_category(name):
    if name in _SPRITE_CAT:
        return _SPRITE_CAT[name]
    if name.startswith(("floor_", "tile_", "rug_", "grate")):
        return "Floors & rugs"
    if name.startswith("brazier"):
        return "Light & fire"
    if name.startswith("pillar"):
        return "Statues & pillars"
    if name.startswith("banner"):
        return "Banners & signs"
    if name.startswith("iron_fence"):
        return "Fences, walls & ruins"
    return "Other D2 objects"


def object_category(row, label):
    try:
        if int(row.get("draw") or 0) == 0:
            return "Invisible (no picture)"
    except ValueError:
        pass
    text = " " + label.lower() + " " + (row.get("token") or "").lower() + " "
    for cat, words in _OBJ_RULES:
        if any(re.search(r"\b" + re.escape(w), text) for w in words):
            return cat
    return "Other D2 objects"


def new_doc(lvltype="Act 1 - Wilderness", w=32, h=32):
    return {"version": 1, "name": "new_area", "act": _act_of(lvltype), "lvltype": lvltype, "width": w,
            "height": h, "level": 0, "random_monsters": True, "rooms": [], "tiles": [], "objects": [],
            "monsters": [], "start": None, "exits": []}


class Editor:
    def __init__(self, assets, screen_size=(1280, 760)):
        self.a = assets
        self.kit = assets.act_kit
        self.content = assets.content
        from game.objects import data_for
        self.objdata = data_for(self.content)
        self.W, self.H = screen_size
        self.font = pygame.font.SysFont("arial", 14)
        self.small = pygame.font.SysFont("arial", 12)
        self.big = pygame.font.SysFont("arial", 18, bold=True)
        self.lvltypes = sorted(t for t in self.kit.lvltypes if self.kit.lvltypes[t] and re.match(r"\s*act", t, re.I))
        self.doc = new_doc(self.lvltypes[0] if self.lvltypes else "Act 1 - Wilderness")
        self.tab = 0
        self.search = ""
        self.scroll = 0
        self.sel = {}                 # tab -> selected entry
        self.open_cats = set()        # the Object tab's open folders
        self.kind = 0
        self.layer2 = False
        self.grid_on = True
        self.zoom = 0
        self.wx, self.wy = 0.0, 0.0
        self.undo = []
        self.prompt = None            # (question, text, callback)
        self.picker = None            # list of the game's maps for Ctrl+O
        self.map_key = None           # which of them is open (saved as maps/<map_key>.json)
        self.msg = "Welcome! Pick a tileset with Ctrl+[ and Ctrl+], then paint. Ctrl+S saves."
        self.dirty_drag = False
        self.drag = None              # "paint" / "erase" / "pan"
        self.last_cell = None
        self.mouse = (0, 0)
        self.thumbs = {}
        self._lists = {}
        self.b = None
        self.recompose()
        self.centre()

    # ---------------------------------------------------------------- data
    def act(self):
        return int(self.doc.get("act", 1) or 1)

    def tileset(self):
        return custommap.tileset(self.kit, self.doc["lvltype"])

    def entries(self):
        """The current tab's palette: [(label, value)]."""
        key = (self.tab, self.doc["lvltype"], self.search.lower())
        if key in self._lists:
            return self._lists[key]
        s = self.search.lower()
        out = []
        if self.tab in (0, 1):
            ts = self.tileset()
            keys = sorted(ts.by_key)
            for o, main, sub in keys:
                if self.tab == 0 and o == 0:
                    out.append(("floor %d.%d" % (main, sub), (o, main, sub)))
                elif self.tab == 1 and o not in (0, 4, 10, 11, 13):
                    out.append(("%s %d.%d.%d" % (ORIENT.get(o, "o%d" % o), o, main, sub), (o, main, sub)))
        elif self.tab == 2:
            for r in self._prest():
                for i in range(1, 7):
                    f = r.get("file%d" % i, "0")
                    if f and f != "0":
                        out.append(("%s  [%s]" % (r["name"], f.rsplit("/", 1)[-1]), f))
        elif self.tab == 3:
            groups = {c: [] for c in CATEGORIES}
            groups["Waypoints & portals"].append(("Waypoint", "waypoint"))
            d = self.objdata
            if d is not None:
                strings = getattr(self.content, "strings", None)
                for oid in sorted(d.rows):
                    try:
                        if d.kind(oid) is None:
                            continue
                    except Exception:
                        continue
                    r = d.rows[oid]
                    desc = (r.get("description - not loaded") or r.get("name", "")).strip('" ')[:28]
                    base = d.name(oid, strings)
                    nm = ("%s #%d" % (desc, oid)) if base.lower() == "an evil force" else "%s (%s) #%d" % (base, desc, oid)
                    groups[object_category(r, nm)].append((nm, oid))
            names = sorted(f[:-4] for f in os.listdir(DECOR_DIR) if f.endswith(".png")) if os.path.isdir(DECOR_DIR) else []
            for n in names:
                groups[sprite_category(n)].append((n.replace("_", " "), ("sprite", n)))
            for c in CATEGORIES:
                items = [e for e in sorted(groups[c], key=lambda e: e[0].lower()) if not s or s in e[0].lower()]
                if not items:
                    continue
                opened = bool(s) or c in self.open_cats
                out.append(("%s %s  (%d)" % ("-" if opened else "+", c, len(items)), ("cat", c)))
                if opened:
                    out += items
            self._lists[key] = out
            return out
        elif self.tab == 4:
            ms = getattr(self.content, "monstats", {}) or {}
            strings = getattr(self.content, "strings", None)
            for mid in sorted(ms):
                r = ms[mid]
                name = r.get("namestr", "") or mid
                if strings is not None:
                    name = strings.get(name, name)
                out.append(("%s (%s)" % (name, mid), ("mon", mid)))
            for k, r in sorted((getattr(self.content, "superuniques", {}) or {}).items()):
                nm = r.get("name") or k
                if strings is not None:
                    nm = strings.get(nm, nm)
                out.append(("* %s (super unique)" % nm, ("super", k)))
        elif self.tab == 6:
            names = sorted(f[:-4] for f in os.listdir(DECOR_DIR) if f.endswith(".png")) if os.path.isdir(DECOR_DIR) else []
            out = [(n, ("sprite", n)) for n in names]
        else:
            out = [("Start (where you arrive)", "start"), ("Exit to a level...", "exit"),
                   ("Erase a tile completely (even a room's)", "x")]
            if any(m[2] == "boss" for m in self.doc.get("markers", [])) or int(self.doc.get("level") or 0):
                out = [("The boss's spot", "boss")] + out
            if self.doc.get("armory"):
                out = [("Seal (open all four to call the smith)", "altar"), ("The smith's spot", "smith"),
                       ("The spider queen's nest (Silkmother)", "spider"),
                       ("Erase a tile completely (even a room's)", "x")]
        if s:
            out = [e for e in out if s in e[0].lower()]
        self._lists[key] = out
        return out

    def _prest(self):
        if not hasattr(self, "_prest_rows"):
            from d2.source import read_table
            try:
                self._prest_rows = [r for r in read_table(self.kit.src, "LvlPrest") if r.get("name")]
            except Exception:
                self._prest_rows = []
        a = self.act()
        pre = "act %d" % a
        return [r for r in self._prest_rows if r["name"].lower().startswith(pre) or
                (a == 5 and r["name"].lower().startswith("expansion"))]

    def selected(self):
        return self.sel.get(self.tab)

    # ---------------------------------------------------------------- document
    def snapshot(self):
        self.undo.append(json.dumps(self.doc))
        if len(self.undo) > 60:
            self.undo.pop(0)

    def recompose(self):
        try:
            self.a.set_act(self.act())
        except Exception:
            pass
        try:
            self.b, _, _ = custommap.compose(self.kit, self.doc, 0, with_grid=False)
        except Exception as e:
            self.msg = "Could not build the map: %s" % e
        self.thumbs = {k: v for k, v in self.thumbs.items() if k[0] == "obj"}

    def centre(self):
        tw, th = self.doc["width"], self.doc["height"]
        self.wx, self.wy = cell_to_world(tw * 5 / 2.0, th * 5 / 2.0)

    def _set_tile(self, entry):
        """Add a tile entry (replacing what the same layer had on that tile)."""
        tx, ty, layer = entry[0], entry[1], entry[2]
        def same(t):
            if t[0] != tx or t[1] != ty:
                return False
            if layer == "w":
                return t[2] == "w" and t[3] == entry[3]
            return t[2] == layer
        tiles = [t for t in self.doc["tiles"] if not same(t)]
        if layer == "x":
            tiles = [t for t in tiles if not (t[0] == tx and t[1] == ty)]
        tiles.append(list(entry))
        self.doc["tiles"] = tiles

    def place(self, cell, first):
        tw, th = self.doc["width"], self.doc["height"]
        tx, ty = cell[0] // 5, cell[1] // 5
        inside = 0 <= tx < tw and 0 <= ty < th
        v = self.selected()
        if v is None and self.tab != 5:
            self.msg = "Pick something in the palette first."
            return False
        if first:
            self.snapshot()
        if self.tab == 0 and inside:
            self._set_tile([tx, ty, "f2" if self.layer2 else "f", v[1], v[2]])
            return "tile"
        if self.tab == 1 and inside:
            self._set_tile([tx, ty, "w", v[0], v[1], v[2]])
            return "tile"
        if self.tab == 2 and first:
            self.doc["rooms"].append([tx, ty, v.replace("/", "\\").lower()])
            return "room"
        if self.tab == 3 and first and isinstance(v, tuple) and v[0] == "sprite":
            self.doc.setdefault("decor", []).append([cell[0], cell[1], v[1]])
            return "obj"
        if self.tab == 3 and first:
            self.doc["objects"] = [o for o in self.doc["objects"] if (o[0], o[1]) != cell] + [[cell[0], cell[1], v]]
            return "obj"
        if self.tab == 4 and first:
            what = v[1]
            kind = "super" if v[0] == "super" else KINDS[self.kind]
            self.doc["monsters"] = [m for m in self.doc["monsters"] if (m[0], m[1]) != cell] + [[cell[0], cell[1], what, kind]]
            return "obj"
        if self.tab == 6 and first:
            self.doc.setdefault("decor", []).append([cell[0], cell[1], v[1]])
            return "obj"
        if self.tab == 5 and v in ("altar", "smith", "spider", "boss") and first:
            mk = self.doc.setdefault("markers", [])
            if v in ("smith", "spider", "boss"):
                mk[:] = [m for m in mk if m[2] != v]
            mk.append([cell[0], cell[1], v])
            return "obj"
        if self.tab == 5:
            if v == "x" and inside:
                self._set_tile([tx, ty, "x"])
                return "tile"
            if v == "start" and first:
                self.doc["start"] = [cell[0], cell[1]]
                return "obj"
            if v == "exit" and first:
                def done(text, c=cell):
                    if text.strip().isdigit():
                        self.snapshot()
                        self.doc["exits"] = [e for e in self.doc["exits"] if (e[0], e[1]) != c] + [[c[0], c[1], int(text)]]
                        self.msg = "Exit to level %s placed." % text
                self.prompt = ("Exit leads to level id (e.g. 79 = Lower Kurast):", "", done)
                return False
        return False

    def erase(self, cell, first):
        tx, ty = cell[0] // 5, cell[1] // 5
        if first:
            self.snapshot()
        d = self.doc
        if self.tab in (0, 1, 5):
            lay = {0: ("f2", "df2") if self.layer2 else ("f", "df"), 1: ("w", "dw"), 5: ("x",)}[self.tab]
            n = len(d["tiles"])
            d["tiles"] = [t for t in d["tiles"] if not (t[0] == tx and t[1] == ty and t[2] in lay)]
            if self.tab == 5:
                mk = d.get("markers", [])
                n3 = len(mk)
                d["markers"] = [m for m in mk if max(abs(m[0] - cell[0]), abs(m[1] - cell[1])) > 2]
                if n3 != len(d["markers"]):
                    return "obj"
                n2 = len(d["exits"])
                d["exits"] = [e for e in d["exits"] if max(abs(e[0] - cell[0]), abs(e[1] - cell[1])) > 2]
                if d["start"] and max(abs(d["start"][0] - cell[0]), abs(d["start"][1] - cell[1])) <= 2:
                    d["start"] = None
                    return "obj"
                if n2 != len(d["exits"]):
                    return "obj"
            return "tile" if n != len(d["tiles"]) else False
        if self.tab == 2 and first:
            for i in range(len(d["rooms"]) - 1, -1, -1):
                rx, ry, path = d["rooms"][i][:3]
                ds = self.kit.ds1(path)
                if ds is not None and rx <= tx < rx + ds.width - 1 and ry <= ty < ry + ds.height - 1:
                    d["rooms"].pop(i)
                    return "room"
            return False
        if self.tab in (3, 4, 6) and first:
            keys = {3: ("objects", "decor"), 4: ("monsters",), 6: ("decor",)}[self.tab]
            gone = False
            for key in keys:
                d.setdefault(key, [])
                n = len(d[key])
                d[key] = [o for o in d[key] if max(abs(o[0] - cell[0]), abs(o[1] - cell[1])) > 1]
                gone = gone or n != len(d[key])
            return "obj" if gone else False
        return False

    # ---------------------------------------------------------------- files
    def filename(self):
        return re.sub(r"[^A-Za-z0-9_\-]+", "_", self.doc.get("name") or "area").strip("_") or "area"

    def save(self):
        path = custommap.save(self.doc, self.map_key or self.filename())
        self.msg = "Saved %s" % path
        return path

    def open(self, fn):
        try:
            self.doc = custommap.load(fn)
            for k, v in new_doc().items():
                self.doc.setdefault(k, v)
            self.undo = []
            self._lists.clear()
            self.recompose()
            self.centre()
            self.msg = "Opened %s" % fn
        except Exception as e:
            self.msg = "Could not open %s: %s" % (fn, e)

    # ---------------------------------------------------------------- view
    def zoomf(self):
        return ZOOMS[self.zoom]

    def view_rect(self):
        return pygame.Rect(PANEL_W, TOP_H, self.W - PANEL_W, self.H - TOP_H - BOT_H)

    def cam(self):
        vr = self.view_rect()
        z = self.zoomf()
        c = Camera(int(vr.w / z), int(vr.h / z), scale=1.0)
        c.snap(self.wx, self.wy)
        return c

    def screen_to_cell(self, pos):
        vr = self.view_rect()
        z = self.zoomf()
        c = self.cam()
        return c.screen_to_cell((pos[0] - vr.x) / z, (pos[1] - vr.y) / z)

    # ---------------------------------------------------------------- input
    def handle(self, e):
        if e.type == pygame.QUIT:
            return "quit"
        if self.prompt is not None:
            if e.type == pygame.KEYDOWN:
                q, text, cb = self.prompt
                if e.key == pygame.K_RETURN:
                    self.prompt = None
                    cb(text)
                elif e.key == pygame.K_ESCAPE:
                    self.prompt = None
                elif e.key == pygame.K_BACKSPACE:
                    self.prompt = (q, text[:-1], cb)
                elif getattr(e, "unicode", "") and e.unicode.isprintable():
                    self.prompt = (q, text + e.unicode, cb)
            return None
        if self.picker is not None:
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.picker = None
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                for r, fn in self._picker_rects():
                    if r.collidepoint(e.pos):
                        self.picker = None
                        open_game_map(self, fn)
                        break
            return None
        if e.type == pygame.KEYDOWN:
            return self.key(e)
        if e.type == pygame.MOUSEMOTION:
            self.mouse = e.pos
            self.motion(e)
        elif e.type == pygame.MOUSEBUTTONDOWN:
            self.mouse = e.pos
            self.click(e)
        elif e.type == pygame.MOUSEBUTTONUP:
            if self.drag in ("paint", "erase") and self.dirty_drag:
                self.recompose()
            self.drag = None
            self.dirty_drag = False
            self.last_cell = None
        elif e.type == getattr(pygame, "MOUSEWHEEL", -1):
            if self.mouse[0] < PANEL_W:
                self.scroll = max(0, self.scroll - e.y * 3)
            else:
                self.zoom = max(0, min(len(ZOOMS) - 1, self.zoom - e.y))
        return None

    def key(self, e):
        ctrl = bool(e.mod & pygame.KMOD_CTRL)
        k = e.key
        if ctrl:
            act = {pygame.K_s: "save", pygame.K_o: "open", pygame.K_n: "new", pygame.K_z: "undo",
                   pygame.K_g: "grid", pygame.K_f: "layer", pygame.K_k: "kind", pygame.K_m: "random",
                   pygame.K_r: "rename", pygame.K_l: "level", pygame.K_LEFTBRACKET: "ts-", pygame.K_RIGHTBRACKET: "ts+",
                   pygame.K_LEFT: "w-", pygame.K_RIGHT: "w+", pygame.K_UP: "h-", pygame.K_DOWN: "h+"}.get(k)
            if act:
                self.do(act)
            return None
        if k == pygame.K_TAB:
            self.set_tab((self.tab + 1) % len(TABS))
        elif k in (pygame.K_PAGEUP, pygame.K_PAGEDOWN) and not self.map_key:
            self.cycle_act(1 if k == pygame.K_PAGEDOWN else -1)
        elif k in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            step = 160 / self.zoomf()
            dx, dy = {pygame.K_LEFT: (-step, 0), pygame.K_RIGHT: (step, 0), pygame.K_UP: (0, -step / 2),
                      pygame.K_DOWN: (0, step / 2)}[k]
            self.wx += dx
            self.wy += dy
        elif k == pygame.K_BACKSPACE:
            self.search = self.search[:-1]
            self.scroll = 0
        elif k == pygame.K_ESCAPE:
            self.search = ""
            self.scroll = 0
        elif getattr(e, "unicode", "") and e.unicode.isprintable():
            self.search += e.unicode
            self.scroll = 0
        return None

    def do(self, act):
        """A toolbar button (or its Ctrl shortcut)."""
        if self.map_key and act in ("new", "rename", "level", "random", "ts-", "ts+", "act-", "act+",
                                    "w-", "w+", "h-", "h+"):
            return                  # (a game map keeps its size, tileset and place in the game)
        if act == "save":
            self.save()
        elif act == "open":
            self.picker = custommap.game_maps()
            if not self.picker:
                self.picker = None
                self.msg = "The game has no hand-made maps (assets/maps is empty)."
        elif act == "new":
            self.snapshot()
            self.doc = new_doc(self.doc["lvltype"], self.doc["width"], self.doc["height"])
            self.recompose()
            self.centre()
            self.msg = "New map (Undo brings the old one back)."
        elif act == "undo":
            if self.undo:
                self.doc = json.loads(self.undo.pop())
                self.recompose()
                self.msg = "Undone."
            else:
                self.msg = "Nothing to undo."
        elif act == "grid":
            self.grid_on = not self.grid_on
        elif act == "layer":
            self.layer2 = not self.layer2
            self.msg = "Painting floor layer %d." % (2 if self.layer2 else 1)
        elif act == "kind":
            self.kind = (self.kind + 1) % len(KINDS)
            self.msg = "Monsters are placed as: %s." % KINDS[self.kind]
        elif act == "random":
            self.doc["random_monsters"] = not self.doc.get("random_monsters", True)
            self.msg = "Random monsters: %s." % ("on" if self.doc["random_monsters"] else "off")
        elif act == "rename":
            def done(text):
                if text.strip():
                    self.doc["name"] = text.strip()
            self.prompt = ("Map name:", self.doc.get("name", ""), done)
        elif act == "level":
            def done(text):
                t = text.strip()
                self.doc["level"] = int(t) if t.isdigit() else 0
                self.msg = "This map replaces level %s." % (self.doc["level"] or "nothing")
            self.prompt = ("Level id this map replaces in the game (0 = none):", str(self.doc.get("level", 0)), done)
        elif act in ("ts-", "ts+"):
            self.cycle_tileset(1 if act == "ts+" else -1)
        elif act in ("act-", "act+"):
            self.cycle_act(1 if act == "act+" else -1)
        elif act in ("w-", "w+", "h-", "h+"):
            self.snapshot()
            d = 4 if act.endswith("+") else -4
            key = "width" if act[0] == "w" else "height"
            self.doc[key] = max(8, min(256, self.doc[key] + d))
            self.recompose()
            self.centre()
            self.msg = "Map size %d x %d tiles." % (self.doc["width"], self.doc["height"])
        elif act in ("z-", "z+"):
            self.zoom = max(0, min(len(ZOOMS) - 1, self.zoom + (1 if act == "z-" else -1)))
        elif act == "centre":
            self.centre()

    def _buttons(self):
        """[(rect, label, action, on)] of the two toolbar rows."""
        d = self.doc
        out = []
        x, y = PANEL_W + 8, 32
        row1 = [("New", "new", False), ("Open", "open", False), ("Save", "save", False), ("Undo", "undo", False),
                ("Rename", "rename", False), ("Replaces level: %s" % (d.get("level") or "-"), "level", bool(d.get("level"))),
                ("Random monsters: %s" % ("on" if d.get("random_monsters", True) else "off"), "random",
                 d.get("random_monsters", True)),
                ("Grid: %s" % ("on" if self.grid_on else "off"), "grid", self.grid_on),
                ("Floor layer %d" % (2 if self.layer2 else 1), "layer", self.layer2),
                ("Monsters: %s" % KINDS[self.kind], "kind", self.kind > 0)]
        if self.map_key:                        # a game map: its size, tileset and place are fixed
            row1 = [r for r in row1 if r[1] not in ("new", "rename", "level", "random")]
        for label, act, on in row1:
            w = self.font.size(label)[0] + 18
            out.append((pygame.Rect(x, y, w, 24), label, act, on))
            x += w + 6
        x, y = PANEL_W + 8, 62
        groups = [("Act %d" % self.act(), "act"), (d.get("lvltype", ""), "ts"),
                  ("Width %d" % d["width"], "w"), ("Height %d" % d["height"], "h"),
                  ("Zoom %d%%" % int(self.zoomf() * 100), "z")]
        if self.map_key:
            groups = [g for g in groups if g[1] == "z"]
        for label, key in groups:
            out.append((pygame.Rect(x, y, 24, 24), "<" if key in ("act", "ts") else "-", key + "-", False))
            x += 28
            w = max(60, self.font.size(label)[0] + 12)
            out.append((pygame.Rect(x, y, w, 24), label, None, False))
            x += w + 4
            out.append((pygame.Rect(x, y, 24, 24), ">" if key in ("act", "ts") else "+", key + "+", False))
            x += 38
        w = self.font.size("Centre view")[0] + 18
        out.append((pygame.Rect(x, y, w, 24), "Centre view", "centre", False))
        return out

    def set_tab(self, t):
        self.tab = t
        self.search = ""
        self.scroll = 0

    def cycle_tileset(self, d):
        if not self.lvltypes:
            return
        i = self.lvltypes.index(self.doc["lvltype"]) if self.doc["lvltype"] in self.lvltypes else 0
        self.doc["lvltype"] = self.lvltypes[(i + d) % len(self.lvltypes)]
        self.doc["act"] = _act_of(self.doc["lvltype"])
        self._lists.clear()
        self.recompose()
        self.msg = "Tileset: %s" % self.doc["lvltype"]

    def cycle_act(self, d):
        a = (self.act() - 1 + d) % 5 + 1
        first = next((t for t in self.lvltypes if _act_of(t) == a), None)
        if first:
            self.doc["lvltype"], self.doc["act"] = first, a
            self._lists.clear()
            self.recompose()
            self.msg = "Act %d - tileset %s" % (a, first)

    def click(self, e):
        if e.pos[0] >= PANEL_W and e.pos[1] < TOP_H:
            if e.button == 1:
                for r, label, act, on in self._buttons():
                    if act and r.collidepoint(e.pos):
                        self.do(act)
                        return
            return
        if e.pos[0] < PANEL_W:
            if e.button == 1:
                for r, t in self._tab_rects():
                    if r.collidepoint(e.pos):
                        self.set_tab(t)
                        return
                for r, i in self._entry_rects():
                    if r.collidepoint(e.pos):
                        v = self.entries()[i][1]
                        if isinstance(v, tuple) and v[0] == "cat":
                            self.open_cats ^= {v[1]}
                            self._lists.clear()
                        else:
                            self.sel[self.tab] = v
                        return
            return
        if e.button == 2:
            self.drag = "pan"
            self._pan0 = (e.pos, self.wx, self.wy)
            return
        if e.button not in (1, 3) or not self.view_rect().collidepoint(e.pos):
            return
        cell = self.screen_to_cell(e.pos)
        self.drag = "paint" if e.button == 1 else "erase"
        self.last_cell = cell
        r = self.place(cell, True) if e.button == 1 else self.erase(cell, True)
        self._after(r)

    def motion(self, e):
        if self.drag == "pan":
            (p0, wx, wy) = self._pan0
            z = self.zoomf()
            self.wx = wx - (e.pos[0] - p0[0]) / z
            self.wy = wy - (e.pos[1] - p0[1]) / z
            return
        if self.drag in ("paint", "erase"):
            cell = self.screen_to_cell(e.pos)
            if self.last_cell is not None and (cell[0] // 5, cell[1] // 5) == (self.last_cell[0] // 5, self.last_cell[1] // 5):
                return
            self.last_cell = cell
            r = self.place(cell, False) if self.drag == "paint" else self.erase(cell, False)
            self._after(r)

    def _after(self, r):
        if r == "tile":
            self.dirty_drag = True
            self.recompose()
        elif r in ("room", "obj"):
            self.recompose()

    # ---------------------------------------------------------------- drawing
    def text(self, surf, s, pos, col=WHITE, font=None):
        img = (font or self.font).render(str(s), True, col)
        surf.blit(img, pos)
        return img.get_width()

    def _tab_rects(self):
        out = []
        w = (PANEL_W - 8) // 3
        for i, t in enumerate(TABS):
            out.append((pygame.Rect(4 + (i % 3) * w, 4 + (i // 3) * 26, w - 4, 22), i))
        return out

    def _entry_geom(self):
        tiles = self.tab in (0, 1, 6)
        return (2, 128, 78) if tiles else (1, PANEL_W - 12, 20)

    def _entry_rects(self):
        if self.tab == 3:
            return self._object_rects()
        cols, ew, eh = self._entry_geom()
        y0 = 112
        out = []
        ents = self.entries()
        maxrows = (self.H - y0 - 80) // (eh + 4)
        start = self.scroll * cols
        for k, i in enumerate(range(start, min(len(ents), start + maxrows * cols))):
            r = pygame.Rect(6 + (k % cols) * (ew + 6), y0 + (k // cols) * (eh + 4), ew, eh)
            out.append((r, i))
        return out

    def _object_rects(self):
        """The Object tab: a bar per folder, its pictures two to a row underneath when it is open.
        (The wheel scrolls three bars or one row of pictures a step.)"""
        y0, bottom = 112, self.H - 80
        ents = self.entries()
        out, y, col, skip = [], y0, 0, self.scroll * 30
        for i, (label, value) in enumerate(ents):
            if isinstance(value, tuple) and value[0] == "cat":
                if col:
                    y += 82
                    col = 0
                r = pygame.Rect(6, y - skip, PANEL_W - 14, 24)
                y += 28
            else:
                r = pygame.Rect(6 + col * 134, y - skip, 128, 78)
                col = (col + 1) % 2
                if col == 0:
                    y += 82
            if r.y >= y0 and r.bottom <= bottom:
                out.append((r, i))
        return out

    def _thumb(self, value, w, h):
        key = (self.tab, self.doc["lvltype"], value, w, h)
        if key in self.thumbs:
            return self.thumbs[key]
        img = None
        try:
            if isinstance(value, tuple) and value[0] == "sprite":
                img = pygame.image.load(os.path.join(DECOR_DIR, value[1] + ".png")).convert_alpha()
            elif self.tab == 3:
                img = self._object_picture(value)
            elif self.tab in (0, 1):
                ref = self.tileset().pick(value[0], value[1], value[2], 0)
                ts = self.a.tile_surface(ref) if ref else None
                if ts:
                    img = ts[0]
        except Exception:
            img = None
        if img is not None:
            iw, ih = img.get_size()
            f = min(w / float(max(1, iw)), h / float(max(1, ih)), 1.0)
            img = pygame.transform.smoothscale(img, (max(1, int(iw * f)), max(1, int(ih * f))))
        self.thumbs[key] = img
        return img

    def _object_picture(self, value):
        """A D2 object's first frame (as the map shows it) for the palette."""
        if value == "waypoint":
            tmp = pygame.Surface((220, 220), pygame.SRCALPHA)
            self.a.draw_object(tmp, "waypoint", -1, (110, 170), 1.0, 0.0, False)
            r = tmp.get_bounding_rect() if hasattr(tmp, "get_bounding_rect") else tmp.get_rect()
            return tmp.subsurface(r).copy() if r.w and r.h else None
        d = self.objdata
        r = d.rows.get(int(value)) if d is not None else None
        if r is None:
            return None

        def iv(k):
            try:
                return int(r.get(k) or 0)
            except ValueError:
                return 0
        tok = r["token"].strip().upper()
        mode = "ON" if iv("framecnt0") <= 1 and iv("framecnt2") > 1 else "NU"
        fr = self.a._obj_frames(tok, mode) or self.a._obj_frames(tok, "NU") or self.a._obj_frames(tok, "ON")
        return fr[0][0] if fr else None

    def draw_panel(self, surf):
        pygame.draw.rect(surf, PANEL, (0, 0, PANEL_W, self.H))
        pygame.draw.line(surf, LINE, (PANEL_W - 1, 0), (PANEL_W - 1, self.H))
        for r, i in self._tab_rects():
            pygame.draw.rect(surf, SEL if i == self.tab else (40, 34, 26), r)
            pygame.draw.rect(surf, LINE, r, 1)
            self.text(surf, TABS[i], (r.x + 8, r.y + 3), GOLD if i == self.tab else GREY)
        pygame.draw.rect(surf, (10, 9, 8), (4, 84, PANEL_W - 10, 22))
        self.text(surf, "search: " + (self.search or "(type to filter)"), (8, 87), WHITE if self.search else GREY)
        ents = self.entries()
        cols, ew, eh = self._entry_geom()
        sel = self.selected()
        for r, i in self._entry_rects():
            label, value = ents[i]
            on = value == sel
            pygame.draw.rect(surf, SEL if on else (36, 31, 25), r)
            if on:
                pygame.draw.rect(surf, GOLD, r, 1)
            if isinstance(value, tuple) and value[0] == "cat":
                pygame.draw.rect(surf, (58, 48, 30), r)
                pygame.draw.rect(surf, LINE, r, 1)
                self.text(surf, label, (r.x + 6, r.y + 4), GOLD)
                continue
            if self.tab in (0, 1, 3, 6):
                ew, eh = r.w, r.h
                img = self._thumb(value, ew - 4, eh - 16)
                if img is not None:
                    surf.blit(img, (r.x + (ew - img.get_width()) // 2, r.y + 2))
                self.text(surf, label[:20] if self.tab == 3 else label[-18:], (r.x + 3, r.bottom - 14), GREY, self.small)
            else:
                self.text(surf, label[:44], (r.x + 4, r.y + 3), GOLD if on else WHITE, self.small)
        if self.tab == 3:
            n = sum(1 for _l, v in ents if not (isinstance(v, tuple) and v[0] == "cat"))
            self.text(surf, "click a folder to open it - wheel scrolls", (8, self.H - 70), GREY, self.small)
            if sel is not None:
                lab = next((l for l, v in ents if v == sel), None)
                if lab:
                    self.text(surf, "placing: " + lab[:40], (8, self.H - 52), GOLD, self.small)
        else:
            self.text(surf, "%d entries - wheel scrolls" % len(ents), (8, self.H - 70), GREY, self.small)
        info = {4: "placed as: %s (Monsters button)" % KINDS[self.kind],
                0: "painting floor layer %d (Floor layer button)" % (2 if self.layer2 else 1)}
        if self.tab in info:
            self.text(surf, info[self.tab], (8, self.H - 52), GOLD, self.small)

    def draw_map(self, surf):
        vr = self.view_rect()
        z = self.zoomf()
        cam = self.cam()
        off = pygame.Surface((cam.sw, cam.sh))
        off.fill(BG)
        b = self.b
        tw, th = self.doc["width"], self.doc["height"]
        a = self.a
        if b is not None:
            tm = b.tm
            c0 = cam.screen_to_cell(0, 0)
            c1 = cam.screen_to_cell(cam.sw, 0)
            c2 = cam.screen_to_cell(0, cam.sh)
            c3 = cam.screen_to_cell(cam.sw, cam.sh)
            xs = [c[0] for c in (c0, c1, c2, c3)]
            ys = [c[1] for c in (c0, c1, c2, c3)]
            tx0, tx1 = max(0, min(xs) // 5 - 2), min(tm.tw - 1, max(xs) // 5 + 2)
            ty0, ty1 = max(0, min(ys) // 5 - 2), min(tm.th - 1, max(ys) // 5 + 4)
            rng_t = [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]
            for tx, ty in rng_t:
                for w in tm.walls.get((tx, ty), ()):
                    if getattr(w[1], "orientation", 0) >= 16:
                        a.draw_tile(off, w, tx, ty, cam)
            for tx, ty in rng_t:
                f = tm.floor.get((tx, ty))
                if f:
                    a.draw_tile(off, f, tx, ty, cam)
                f2 = tm.floor2.get((tx, ty))
                if f2:
                    a.draw_tile(off, f2, tx, ty, cam)
            if self.grid_on:
                self._grid(off, cam, tx0, ty0, tx1, ty1, tw, th)
            draws = []
            roofs = []
            for tx, ty in rng_t:
                for w in tm.walls.get((tx, ty), ()):
                    o = getattr(w[1], "orientation", 0)
                    if o >= 16:
                        continue
                    if o == 15:
                        roofs.append((tx + ty, w, tx, ty))
                    else:
                        draws.append((tx * 5 + ty * 5 + 1, 0, "tile", (w, tx, ty)))
                for t_, lt in (getattr(tm, "warp_tiles", {}) or {}).get((tx, ty), ()):
                    draws.append((tx * 5 + ty * 5 + 1, 0, "tile", (t_, tx, ty)))
            for o in self.doc["objects"]:
                draws.append((o[0] + o[1], 1, "obj", o))
            for m in self.doc["monsters"]:
                draws.append((m[0] + m[1], 2, "mon", m))
            for k, c, own, oid in b.objects:
                draws.append((c[0] + c[1], 1, "qobj", (k, c)))
            for name, c in getattr(b, "decor", ()) or ():
                draws.append((c[0] + c[1], 1, "decor", (name, c)))
            draws.sort(key=lambda d: (d[0], d[1]))
            for _, _, kind, obj in draws:
                if kind == "tile":
                    a.draw_tile(off, obj[0], obj[1], obj[2], cam)
                elif kind == "obj":
                    self._draw_object(off, cam, obj)
                elif kind == "qobj":
                    k, c = obj
                    if hasattr(a, "draw_object"):
                        a.draw_object(off, k, -1, cam.cell_to_screen(*c), 1.0, 0.0, False)
                elif kind == "decor":
                    if hasattr(a, "draw_decor"):
                        a.draw_decor(off, obj[0], cam.cell_to_screen(*obj[1]))
                elif kind == "mon":
                    self._marker(off, cam, (obj[0], obj[1]), (220, 60, 50), "%s%s" % (obj[2], "" if obj[3] == "normal" else " [%s]" % obj[3]))
            for _, w, tx, ty in sorted(roofs, key=lambda r: r[0]):
                a.draw_tile(off, w, tx, ty, cam)
        # bounds, start, exits
        corners = [cam.cell_to_screen(0, 0), cam.cell_to_screen(tw * 5, 0), cam.cell_to_screen(tw * 5, th * 5),
                   cam.cell_to_screen(0, th * 5)]
        pygame.draw.lines(off, GOLD, True, [(int(x), int(y)) for x, y in corners], 2)
        if self.doc.get("start"):
            self._marker(off, cam, tuple(self.doc["start"]), (60, 220, 90), "START")
        for mx_, my_, what in self.doc.get("markers", []):
            col, lab = {"altar": ((80, 170, 255), "SEAL"), "smith": ((230, 50, 50), "SMITH"),
                        "spider": ((200, 90, 230), "SPIDER QUEEN"), "boss": ((230, 50, 50), "BOSS")}.get(what, ((200, 200, 200), what.upper()))
            self._marker(off, cam, (mx_, my_), col, lab)
        for e in self.doc.get("exits", []):
            self._marker(off, cam, (e[0], e[1]), (170, 90, 230), "EXIT -> %s" % e[2])
        # cursor
        if vr.collidepoint(self.mouse) and self.picker is None:
            cell = self.screen_to_cell(self.mouse)
            if self.tab in (0, 1, 2) or (self.tab == 5 and self.selected() == "x"):
                tx, ty = cell[0] // 5, cell[1] // 5
                w_, h_ = 1, 1
                if self.tab == 2 and self.selected():
                    ds = self.kit.ds1(self.selected().replace("/", "\\").lower())
                    if ds is not None:
                        w_, h_ = ds.width - 1, ds.height - 1
                pts = [cam.cell_to_screen(tx * 5, ty * 5), cam.cell_to_screen((tx + w_) * 5, ty * 5),
                       cam.cell_to_screen((tx + w_) * 5, (ty + h_) * 5), cam.cell_to_screen(tx * 5, (ty + h_) * 5)]
                pygame.draw.lines(off, WHITE, True, [(int(x), int(y)) for x, y in pts], 2)
            else:
                x, y = cam.cell_to_screen(*cell)
                pygame.draw.circle(off, WHITE, (int(x), int(y)), 6, 2)
        if z != 1.0:
            off = pygame.transform.smoothscale(off, (vr.w, vr.h))
        surf.blit(off, vr.topleft)

    def _grid(self, off, cam, tx0, ty0, tx1, ty1, tw, th):
        g = pygame.Surface(off.get_size(), pygame.SRCALPHA)
        col = (255, 255, 255, 28)
        for tx in range(max(0, tx0), min(tw, tx1 + 1) + 1):
            a_ = cam.cell_to_screen(tx * 5, max(0, ty0) * 5)
            b_ = cam.cell_to_screen(tx * 5, min(th, ty1 + 1) * 5)
            pygame.draw.line(g, col, (int(a_[0]), int(a_[1])), (int(b_[0]), int(b_[1])))
        for ty in range(max(0, ty0), min(th, ty1 + 1) + 1):
            a_ = cam.cell_to_screen(max(0, tx0) * 5, ty * 5)
            b_ = cam.cell_to_screen(min(tw, tx1 + 1) * 5, ty * 5)
            pygame.draw.line(g, col, (int(a_[0]), int(a_[1])), (int(b_[0]), int(b_[1])))
        off.blit(g, (0, 0))

    def _draw_object(self, off, cam, o):
        cx, cy, what = o
        pos = cam.cell_to_screen(cx, cy)
        if what in ("waypoint", "portal"):
            self.a.draw_object(off, what, -1, pos, 1.0, 0.0, False)
            return
        d = self.objdata
        r = d.rows.get(int(what)) if d is not None else None
        drawn = None
        if r is not None:
            try:
                def iv(k):
                    try:
                        return int(r.get(k) or 0)
                    except ValueError:
                        return 0
                fc = (iv("framecnt0"), iv("framecnt1"), iv("framecnt2"))
                od = dict(token=r["token"].strip().upper(), mode="ON" if fc[0] <= 1 and fc[2] > 1 else "NU",
                          fcnt=fc, op_t=None, cycle=False, cycle_on=False, kind="decor")
                drawn = self.a.draw_gen_object(off, od, pos, 1.0, 0.0)
            except Exception:
                drawn = None
        if drawn is None:
            self._marker(off, cam, (cx, cy), (230, 200, 90), "object %s" % what)

    def _marker(self, off, cam, cell, col, label):
        x, y = cam.cell_to_screen(*cell)
        pts = [(x, y - 8), (x + 16, y), (x, y + 8), (x - 16, y)]
        pygame.draw.polygon(off, col, [(int(a), int(b)) for a, b in pts], 2)
        img = self.small.render(label, True, col)
        off.blit(img, (int(x - img.get_width() / 2), int(y - 26)))

    def _picker_rects(self):
        out = []
        for i, fn in enumerate(self.picker or []):
            out.append((pygame.Rect(self.W // 2 - 200, 120 + i * 26, 400, 22), fn))
        return out

    def draw(self, surf):
        surf.fill(BG)
        self.draw_map(surf)
        self.draw_panel(surf)
        # top bar
        pygame.draw.rect(surf, PANEL, (PANEL_W, 0, self.W - PANEL_W, TOP_H))
        d = self.doc
        self.text(surf, "Map: %s" % d.get("name"), (PANEL_W + 10, 7), GOLD, self.big)
        pygame.draw.line(surf, LINE, (PANEL_W, TOP_H - 1), (self.W, TOP_H - 1))
        for r, label, act, on in self._buttons():
            if act is None:
                self.text(surf, label, (r.x + 6, r.y + 4), WHITE)
                continue
            hot = r.collidepoint(self.mouse)
            pygame.draw.rect(surf, (88, 72, 36) if hot else (SEL if on else (44, 38, 30)), r)
            pygame.draw.rect(surf, GOLD if hot else LINE, r, 1)
            self.text(surf, label, (r.x + (r.w - self.font.size(label)[0]) // 2, r.y + 4), GOLD if on or hot else WHITE)
        # status
        pygame.draw.rect(surf, PANEL, (PANEL_W, self.H - BOT_H, self.W - PANEL_W, BOT_H))
        cell = self.screen_to_cell(self.mouse) if self.view_rect().collidepoint(self.mouse) else None
        where = "  tile %d,%d  cell %d,%d" % (cell[0] // 5, cell[1] // 5, cell[0], cell[1]) if cell else ""
        self.text(surf, self.msg + where, (PANEL_W + 10, self.H - BOT_H + 4), WHITE, self.small)
        if self.picker is not None:
            box = pygame.Rect(self.W // 2 - 220, 80, 440, 60 + 26 * len(self.picker))
            pygame.draw.rect(surf, PANEL, box)
            pygame.draw.rect(surf, GOLD, box, 1)
            self.text(surf, "Open a map: the game's own and the generator's (Esc closes)", (box.x + 12, box.y + 10), GOLD, self.big)
            for r, fn in self._picker_rects():
                hot = r.collidepoint(self.mouse)
                pygame.draw.rect(surf, SEL if hot else (40, 34, 26), r)
                self.text(surf, fn, (r.x + 8, r.y + 3))
        if self.prompt is not None:
            q, text, _ = self.prompt
            box = pygame.Rect(self.W // 2 - 260, self.H // 2 - 50, 520, 100)
            pygame.draw.rect(surf, PANEL, box)
            pygame.draw.rect(surf, GOLD, box, 1)
            self.text(surf, q, (box.x + 14, box.y + 14), GOLD)
            pygame.draw.rect(surf, (10, 9, 8), (box.x + 14, box.y + 44, box.w - 28, 26))
            self.text(surf, text + "_", (box.x + 20, box.y + 48))
            self.text(surf, "Enter: OK   Esc: cancel", (box.x + 14, box.y + 76), GREY, self.small)


def map_title(name):
    return name.replace("_", " ").title()


def open_game_map(ed, name):
    """Opens one of the game's maps (your edited copy if you saved one). Save writes maps/<name>.json,
    which the game then builds that place from."""
    path = custommap.game_map_path(name)
    ed.open(path)
    ed.map_key = name
    try:                                          # (the editor opens this map again next time)
        os.makedirs(custommap.MAPS, exist_ok=True)
        with open(os.path.join(custommap.MAPS, ".editor_last"), "w") as f:
            f.write(name)
    except OSError:
        pass
    mine = path.startswith(custommap.MAPS)
    in_game = os.path.exists(os.path.join(custommap.GAME_MAPS, name + ".json")) or int(ed.doc.get("level") or 0)
    ed.msg = "%s (%s). Save writes maps/%s.json%s" % (
        map_title(name), "your copy" if mine else "the game's own", name, " - the game uses it." if in_game else ".")


def open_armory(ed):
    open_game_map(ed, "kurast_armory")


def main():
    from main import load_settings
    cfg = load_settings()
    path = cfg.get("diablo2", "path").strip()
    pygame.init()
    screen = pygame.display.set_mode((1280, 760), getattr(pygame, "RESIZABLE", 0))
    pygame.display.set_caption("D2 Tactics - Map Editor")
    font = pygame.font.SysFont("arial", 18)

    def say(msg):
        screen.fill(BG)
        screen.blit(font.render("Loading Diablo II files: " + str(msg), True, GOLD), (40, 360))
        pygame.display.flip()
        pygame.event.pump()
    if not path:
        print("Set your Diablo II folder in settings.ini ([diablo2] path = ...) first.")
        return 1
    from render.d2assets import D2Assets
    assets = D2Assets(path, "normal", say)
    if assets.act_kit is None:
        print("Could not read the level files.")
        return 1
    ed = Editor(assets, screen.get_size())
    maps = custommap.game_maps()
    want = sys.argv[1] if len(sys.argv) > 1 else None          # (the map generator opens its map here)
    if not want:
        try:
            with open(os.path.join(custommap.MAPS, ".editor_last")) as f:
                want = f.read().strip()
        except OSError:
            want = None
    if want and want in maps:
        open_game_map(ed, want)
    elif maps:
        open_game_map(ed, "kurast_armory" if "kurast_armory" in maps else maps[0])
    clock = pygame.time.Clock()
    while True:
        for e in pygame.event.get():
            if e.type == getattr(pygame, "VIDEORESIZE", -1):
                ed.W, ed.H = e.w, e.h
                screen = pygame.display.set_mode((e.w, e.h), getattr(pygame, "RESIZABLE", 0))
                continue
            if ed.handle(e) == "quit":
                pygame.quit()
                return 0
        ed.draw(screen)
        pygame.display.flip()
        clock.tick(30)


if __name__ == "__main__":
    sys.exit(main() or 0)
