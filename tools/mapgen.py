"""D2 Tactics map generator - random dungeons, start it with "Map Generator.bat".

Pick a theme (any of D2's dungeon tilesets), how many rooms and loops, which monsters (the theme's own
or any you pick), packs / champions / uniques / a super unique boss, and how many shrines, wells,
chests, breakables, bodies, racks, bookshelves and lights. Generate shows the map from above; every
room is checked to be reachable (a layout that fails is thrown away and made again).

Map type switches between dungeons (D2's maze rooms) and open worlds (D2's outdoor areas built block by
block from their border and landmark presets). Save writes maps/<name>.json; the map editor opens it
("Open"). The maps are not put into the game.
"""
import os
import random
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pygame  # noqa: E402

from game import custommap, randmap  # noqa: E402

BG = (14, 12, 10)
PANEL = (28, 24, 20)
LINE = (90, 78, 52)
GOLD = (199, 179, 119)
WHITE = (230, 230, 230)
GREY = (150, 150, 150)
SEL = (70, 58, 30)
RED = (220, 60, 50)
PANEL_W = 430
ROW_H = 25

# (key, label, kind, min, max, step) - kind: num / theme / pick / toggle / text / boss / seed / kind
# rows only for dungeons / only for open worlds
DUNGEON_ONLY = {"rooms", "loops", "theme_rooms", "packs"}
OPEN_ONLY = {"width", "height", "fill", "open_packs"}
ROWS = [("name", "Name", "text"), ("kind", "Map type", "kind"), ("theme", "Theme", "theme"),
        ("rooms", "Rooms", "num", 2, 60, 1),
        ("loops", "Extra links (loops)", "num", 0, 30, 1), ("theme_rooms", "Special rooms %", "num", 0, 100, 10),
        ("width", "Width (8-tile blocks)", "num", 4, 30, 1), ("height", "Height (8-tile blocks)", "num", 4, 30, 1),
        ("fill", "Landmarks / props %", "num", 0, 100, 10),
        ("monsters", "Enemy types", "pick"), ("packs", "Packs per room", "num", 0, 8, 1),
        ("open_packs", "Monster packs", "num", 0, 200, 5),
        ("champions", "Champion packs", "num", 0, 30, 1), ("uniques", "Unique packs", "num", 0, 30, 1),
        ("boss", "Boss (super unique)", "boss"), ("monster_level", "Monster level", "num", 0, 99, 1),
        ("shrines", "Shrines", "num", 0, 30, 1), ("wells", "Wells", "num", 0, 20, 1),
        ("chests", "Chests", "num", 0, 40, 1), ("breakables", "Barrels and urns", "num", 0, 60, 1),
        ("bodies", "Bodies to search", "num", 0, 40, 1), ("racks", "Weapon / armor racks", "num", 0, 20, 1),
        ("bookshelves", "Bookshelves", "num", 0, 20, 1), ("lights", "Torches and braziers", "num", 0, 60, 1),
        ("waypoint", "Waypoint at the start", "toggle"),
        ("room_objects", "Presets' own D2 objects", "toggle"), ("seed", "Seed", "seed")]


class Generator:
    def __init__(self, assets, size):
        self.a = assets
        self.kit = assets.act_kit
        self.content = assets.content
        from game.objects import data_for
        from game.actworld import ActInfo
        self.objdata = data_for(self.content)
        self.info = ActInfo(self.kit, self.content)
        self.W, self.H = size
        self.font = pygame.font.SysFont("arial", 15)
        self.small = pygame.font.SysFont("arial", 12)
        self.big = pygame.font.SysFont("arial", 19, bold=True)
        self.opts = dict(randmap.DEFAULTS)
        self.opts["seed"] = random.randrange(1 << 30)
        self.data = None
        self.grid = None
        self.msg = "Set the options, then Generate."
        self.mouse = (0, 0)
        self.picker = None          # dict(title, items [(label, value)], multi, key, search, scroll)
        self.prompt = None          # (question, text, callback)
        self.preview = None
        self.generate()

    # ------------------------------------------------------------------ data
    def strings(self):
        return getattr(self.content, "strings", None)

    def mon_name(self, mid):
        r = self.content.monstats.get(mid, {}) if self.content else {}
        nm = r.get("namestr") or mid
        st = self.strings()
        return st.get(nm, nm) if st is not None else nm

    def monster_items(self):
        out = []
        for mid, r in sorted((self.content.monstats or {}).items()):
            if str(r.get("enabled", "1")) != "1" or str(r.get("killable", "1")) != "1" or str(r.get("npc", "0")) == "1":
                continue
            lvl = r.get("level") or ""
            out.append(("%s  (%s, lvl %s)" % (self.mon_name(mid), mid, lvl), mid))
        out.sort(key=lambda e: e[0].lower())
        return out

    def boss_items(self):
        out = []
        st = self.strings()
        for k, r in sorted((getattr(self.content, "superuniques", {}) or {}).items()):
            nm = r.get("name") or k
            if st is not None:
                nm = st.get(nm, nm)
            out.append(("%s  (%s)" % (nm, r.get("class", "")), k))
        out.sort(key=lambda e: e[0].lower())
        return out

    def level_items(self):
        from game import act1, act2, act3, act5
        ids = sorted(set(act1.DUNGEONS) | set(act2.DUNGEONS) | set(act3.DUNGEONS) | set(act5.DUNGEONS))
        return [("%s  (#%d)" % (self.info.name(i), i), i) for i in ids if isinstance(i, int)]

    def value_text(self, key):
        v = self.opts.get(key)
        if key == "theme":
            if self.opts.get("kind") == "open":
                return randmap.OPEN_NAMES.get(self.opts["open_theme"], self.opts["open_theme"])
            return randmap.THEME_NAMES.get(v, v)
        if key == "kind":
            return "Open world" if v == "open" else "Dungeon"
        if key == "monsters":
            if not v:
                return "the theme's own"
            names = [self.mon_name(m) for m in v]
            t = ", ".join(names)
            return t if len(t) < 34 else "%d types: %s..." % (len(v), t[:22])
        if key == "boss":
            if not v:
                return "none"
            r = (getattr(self.content, "superuniques", {}) or {}).get(v, {})
            nm = r.get("name") or v
            st = self.strings()
            return st.get(nm, nm) if st is not None else nm
        if key == "level":
            return "none (editor only)" if not v else "%s (#%d)" % (self.info.name(v), v)
        if key in ("waypoint", "room_objects"):
            return "yes" if v else "no"
        if key == "monster_level" and not v:
            return "auto"
        return str(v)

    # ------------------------------------------------------------------ actions
    def generate(self, new_seed=False):
        if new_seed:
            self.opts["seed"] = random.randrange(1 << 30)
        try:
            self.data = randmap.generate(self.kit, self.content, self.objdata, self.opts)
            self.data["name"] = self.opts["name"]
            self.build_preview()
            d = self.data
            if d.get("ground") is not None and "reachable" in d:
                self.msg = "Open world %d x %d tiles, %d presets, %d monster groups, %d objects - %d%% of the ground reachable (the rest is walled-in pockets, left empty)." % (
                    d["width"], d["height"], len(d["rooms"]), len(d["monsters"]), len(d["objects"]), d["reachable"])
            else:
                self.msg = "%d rooms, %d x %d tiles, %d monster groups, %d objects - every room reachable." % (
                    len(d["rooms"]), d["width"], d["height"], len(d["monsters"]), len(d["objects"]))
        except Exception as e:
            self.msg = "Could not generate: %s" % e

    def build_preview(self):
        b, grid, _ = custommap.compose(self.kit, self.data, self.data.get("level") or 0, 1)
        self.grid = grid
        w, h = grid.w, grid.h
        surf = pygame.Surface((w, h))
        surf.fill((8, 7, 6))
        rw, rh = self.data.get("room_size", [8, 8])
        for y in range(h):
            for x in range(w):
                if grid.walkable(x, y):
                    rx, ry = x // (rw * 5), y // (rh * 5)
                    surf.set_at((x, y), (78, 70, 58) if (rx + ry) % 2 else (64, 58, 48))
        self.preview = (surf, b)

    def save(self):
        if not self.data:
            return
        self.data["name"] = self.opts["name"]
        name = custommap.save(self.data, self.opts["name"])
        self.msg = "Saved %s - open it in the Map Editor (Open)." % name

    def open_in_editor(self):
        if not self.data:
            return
        self.save()
        try:
            subprocess.Popen([sys.executable, os.path.join(ROOT, "tools", "mapeditor.py"), self.opts["name"]])
            self.msg = "Opening %s in the Map Editor..." % self.opts["name"]
        except Exception as e:
            self.msg = "Could not start the editor: %s" % e

    def change(self, key, d):
        row = next(r for r in ROWS if r[0] == key)
        kind = row[2]
        if kind == "num":
            lo, hi, step = row[3], row[4], row[5]
            self.opts[key] = max(lo, min(hi, int(self.opts.get(key) or 0) + d * step))
        elif kind == "theme":
            opn = self.opts.get("kind") == "open"
            key = "open_theme" if opn else "theme"
            keys = [k for k, _n, _a in (randmap.OPEN_THEMES if opn else randmap.THEMES)]
            i = keys.index(self.opts[key]) if self.opts[key] in keys else 0
            self.opts[key] = keys[(i + d) % len(keys)]
            self.opts["monsters"] = []
        elif kind == "kind":
            self.opts["kind"] = "dungeon" if self.opts.get("kind") == "open" else "open"
            self.opts["monsters"] = []
            if self.opts["name"] in ("random_dungeon", "random_world"):
                self.opts["name"] = "random_world" if self.opts["kind"] == "open" else "random_dungeon"
        elif kind == "toggle":
            self.opts[key] = not self.opts.get(key)
        elif kind == "seed":
            self.opts["seed"] = random.randrange(1 << 30)
        elif kind in ("pick", "boss", "level"):
            if d < 0:
                self.opts[key] = [] if kind == "pick" else ("" if kind == "boss" else 0)
            else:
                self.open_picker(key)
        elif kind == "text":
            self.prompt = ("Map name (letters, digits, _):", self.opts["name"], self._set_name)

    def _set_name(self, text):
        import re
        t = re.sub(r"[^A-Za-z0-9_\-]+", "_", text).strip("_")
        if t:
            self.opts["name"] = t

    def open_picker(self, key):
        if key == "monsters":
            self.picker = dict(title="Enemy types (click to add / remove; Esc closes)", items=self.monster_items(),
                               multi=True, key=key, search="", scroll=0)
        elif key == "boss":
            self.picker = dict(title="Boss: a super unique (Esc closes)", items=self.boss_items(), multi=False,
                               key=key, search="", scroll=0)
        else:
            self.picker = dict(title="Replaces level - the game plays this map there (Esc closes)",
                               items=self.level_items(), multi=False, key=key, search="", scroll=0)

    # ------------------------------------------------------------------ layout
    def rows(self):
        skip = DUNGEON_ONLY if self.opts.get("kind") == "open" else OPEN_ONLY
        return [r for r in ROWS if r[0] not in skip]

    def row_rects(self):
        out = []
        y = 52
        for row in self.rows():
            out.append((row, pygame.Rect(10, y, PANEL_W - 20, ROW_H - 3)))
            y += ROW_H
        return out

    def buttons(self):
        y = 52 + ROW_H * len(self.rows()) + 12
        out = []
        x = 10
        for label, act in (("Generate", "gen"), ("Same seed", "again"), ("Save", "save"),
                           ("Open in Map Editor", "edit")):
            w = self.font.size(label)[0] + 18
            if x + w > PANEL_W - 6:
                x, y = 10, y + 32
            out.append((pygame.Rect(x, y, w, 26), label, act))
            x += w + 6
        return out

    def picker_items(self):
        p = self.picker
        s = p["search"].lower()
        return [e for e in p["items"] if not s or s in e[0].lower()]

    def picker_rects(self):
        box = pygame.Rect(self.W // 2 - 330, 50, 660, self.H - 100)
        out = []
        items = self.picker_items()
        n = (box.h - 80) // 22
        for i, e in enumerate(items[self.picker["scroll"]:self.picker["scroll"] + n]):
            out.append((pygame.Rect(box.x + 10, box.y + 70 + i * 22, box.w - 20, 20), e))
        return box, out

    # ------------------------------------------------------------------ events
    def handle(self, e):
        if e.type == pygame.QUIT:
            return "quit"
        if e.type == pygame.MOUSEMOTION:
            self.mouse = e.pos
            return None
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
            p = self.picker
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.picker = None
                elif e.key == pygame.K_BACKSPACE:
                    p["search"] = p["search"][:-1]
                    p["scroll"] = 0
                elif getattr(e, "unicode", "") and e.unicode.isprintable():
                    p["search"] += e.unicode
                    p["scroll"] = 0
            elif e.type == getattr(pygame, "MOUSEWHEEL", -1):
                p["scroll"] = max(0, min(len(self.picker_items()) - 5, p["scroll"] - e.y * 3))
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                box, rects = self.picker_rects()
                if not box.collidepoint(e.pos):
                    self.picker = None
                    return None
                for r, (label, value) in rects:
                    if r.collidepoint(e.pos):
                        if p["multi"]:
                            lst = list(self.opts.get(p["key"]) or [])
                            if value in lst:
                                lst.remove(value)
                            else:
                                lst.append(value)
                            self.opts[p["key"]] = lst
                        else:
                            self.opts[p["key"]] = value
                            if p["key"] == "level" and value and not self.opts.get("monster_level"):
                                pass
                            self.picker = None
                        break
            return None
        if e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
            for row, r in self.row_rects():
                if r.collidepoint(e.pos):
                    minus = pygame.Rect(r.right - 62, r.y, 28, r.h)
                    if e.button == 3 or minus.collidepoint(e.pos):
                        self.change(row[0], -1)
                    else:
                        self.change(row[0], 1)
                    return None
            for r, label, act in self.buttons():
                if r.collidepoint(e.pos):
                    if act == "gen":
                        self.generate(True)
                    elif act == "again":
                        self.generate(False)
                    elif act == "save":
                        self.save()
                    elif act == "edit":
                        self.open_in_editor()
                    return None
        if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
            self.generate(True)
        return None

    # ------------------------------------------------------------------ drawing
    def text(self, surf, s, pos, col=WHITE, font=None):
        img = (font or self.font).render(str(s), True, col)
        surf.blit(img, pos)
        return img.get_width()

    def draw(self, surf):
        surf.fill(BG)
        pygame.draw.rect(surf, PANEL, (0, 0, PANEL_W, self.H))
        pygame.draw.line(surf, LINE, (PANEL_W - 1, 0), (PANEL_W - 1, self.H))
        self.text(surf, "Random Map Generator", (12, 12), GOLD, self.big)
        for row, r in self.row_rects():
            hot = r.collidepoint(self.mouse)
            pygame.draw.rect(surf, (52, 44, 30) if hot else (36, 31, 25), r)
            self.text(surf, row[1], (r.x + 6, r.y + 3), GREY)
            self.text(surf, self.value_text(row[0]), (r.x + 190, r.y + 3), WHITE)
            for i, sym in enumerate("-+"):
                br = pygame.Rect(r.right - 62 + i * 31, r.y + 1, 28, r.h - 2)
                pygame.draw.rect(surf, (60, 50, 32), br)
                pygame.draw.rect(surf, LINE, br, 1)
                lab = sym
                if row[2] in ("pick", "boss", "level"):
                    lab = "x" if sym == "-" else "..."
                elif row[2] in ("theme",):
                    lab = "<" if sym == "-" else ">"
                elif row[2] in ("toggle", "seed", "text", "kind"):
                    lab = "" if sym == "-" else "*"
                self.text(surf, lab, (br.x + (br.w - self.font.size(lab)[0]) // 2, br.y + 2), GOLD)
        for r, label, act in self.buttons():
            hot = r.collidepoint(self.mouse)
            pygame.draw.rect(surf, (88, 72, 36) if hot else (44, 38, 30), r)
            pygame.draw.rect(surf, GOLD if hot else LINE, r, 1)
            self.text(surf, label, (r.x + 9, r.y + 4), GOLD if hot else WHITE)
        self.text(surf, "click a row (or +) to change it, right click (or -) to go back", (12, self.H - 46), GREY, self.small)
        self.text(surf, self.msg, (12, self.H - 26), GOLD, self.small)
        self.draw_preview(surf)
        if self.picker is not None:
            self.draw_picker(surf)
        if self.prompt is not None:
            q, text, _ = self.prompt
            box = pygame.Rect(self.W // 2 - 260, self.H // 2 - 50, 520, 100)
            pygame.draw.rect(surf, PANEL, box)
            pygame.draw.rect(surf, GOLD, box, 1)
            self.text(surf, q, (box.x + 14, box.y + 14), GOLD)
            pygame.draw.rect(surf, (10, 9, 8), (box.x + 14, box.y + 44, box.w - 28, 26))
            self.text(surf, text + "_", (box.x + 20, box.y + 48))
            self.text(surf, "Enter: OK   Esc: cancel", (box.x + 14, box.y + 76), GREY, self.small)

    def draw_preview(self, surf):
        area = pygame.Rect(PANEL_W + 10, 10, self.W - PANEL_W - 20, self.H - 20)
        if not self.preview or not self.data:
            return
        img, b = self.preview
        w, h = img.get_size()
        k = min(area.w / float(w), area.h / float(h))
        sw, sh = max(1, int(w * k)), max(1, int(h * k))
        ox, oy = area.x + (area.w - sw) // 2, area.y + (area.h - sh) // 2
        surf.blit(pygame.transform.scale(img, (sw, sh)), (ox, oy))
        P = lambda c: (int(ox + c[0] * k), int(oy + c[1] * k))
        r = max(2, int(k * 1.6))
        # stairs
        for (tx, ty), _m, _o in b.warps:
            pygame.draw.rect(surf, (90, 150, 255), (*P((tx * 5, ty * 5)), max(3, int(5 * k)), max(3, int(5 * k))))
        colours = {"shrine": (90, 200, 255), "well": (60, 120, 230), "chest": (230, 200, 60), "casket": (230, 200, 60),
                   "barrel": (170, 120, 60), "urn": (170, 120, 60), "xbarrel": (210, 110, 40), "corpse": (160, 160, 160),
                   "armor_rack": (200, 200, 220), "weapon_rack": (200, 200, 220), "bookshelf": (150, 100, 60)}
        for cx, cy, what in self.data["objects"]:
            if what == "waypoint":
                pygame.draw.circle(surf, (80, 230, 120), P((cx, cy)), r + 3, 2)
                continue
            kind = self.objdata.kind(int(what)) if self.objdata else None
            col = colours.get(kind, (255, 150, 40))
            pygame.draw.rect(surf, col, (P((cx, cy))[0] - r, P((cx, cy))[1] - r, 2 * r, 2 * r))
        for cx, cy, mid, kind in self.data["monsters"]:
            col = {"pack": RED, "champion": (80, 140, 255), "unique": (230, 200, 60), "super": (255, 120, 0)}.get(kind, RED)
            pygame.draw.circle(surf, col, P((cx, cy)), r + (5 if kind == "super" else 1))
        st = self.data.get("start")
        if st:
            pygame.draw.circle(surf, (60, 230, 90), P(st), r + 4, 2)
            self.text(surf, "START", (P(st)[0] + 8, P(st)[1] - 8), (60, 230, 90), self.small)
        # legend
        lx, ly = area.x + 6, area.y + 4
        for i, (col, lab) in enumerate([(RED, "monster pack"), ((80, 140, 255), "champions"), ((230, 200, 60), "unique / chest"),
                                        ((255, 120, 0), "boss"), ((90, 200, 255), "shrine"), ((60, 120, 230), "well"),
                                        ((90, 150, 255), "stairs"), ((255, 150, 40), "lights / other")]):
            pygame.draw.rect(surf, col, (lx, ly + i * 14 + 3, 9, 9))
            self.text(surf, lab, (lx + 14, ly + i * 14), GREY, self.small)

    def draw_picker(self, surf):
        p = self.picker
        box, rects = self.picker_rects()
        pygame.draw.rect(surf, PANEL, box)
        pygame.draw.rect(surf, GOLD, box, 1)
        self.text(surf, p["title"], (box.x + 12, box.y + 10), GOLD, self.big)
        pygame.draw.rect(surf, (10, 9, 8), (box.x + 10, box.y + 40, box.w - 20, 24))
        self.text(surf, "search: " + (p["search"] or "(type to filter)"), (box.x + 16, box.y + 43),
                  WHITE if p["search"] else GREY)
        chosen = self.opts.get(p["key"])
        for r, (label, value) in rects:
            on = (value in chosen) if p["multi"] else value == chosen
            pygame.draw.rect(surf, SEL if on or r.collidepoint(self.mouse) else (40, 34, 26), r)
            self.text(surf, ("[x] " if on else "[ ] ") + label if p["multi"] else label, (r.x + 6, r.y + 2),
                      GOLD if on else WHITE, self.small)


def main():
    from main import load_settings
    cfg = load_settings()
    path = cfg.get("diablo2", "path").strip()
    pygame.init()
    screen = pygame.display.set_mode((1280, 760), getattr(pygame, "RESIZABLE", 0))
    pygame.display.set_caption("D2 Tactics - Map Generator")
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
    gen = Generator(assets, screen.get_size())
    clock = pygame.time.Clock()
    while True:
        for e in pygame.event.get():
            if e.type == getattr(pygame, "VIDEORESIZE", -1):
                gen.W, gen.H = e.w, e.h
                screen = pygame.display.set_mode((e.w, e.h), getattr(pygame, "RESIZABLE", 0))
                continue
            if gen.handle(e) == "quit":
                pygame.quit()
                return 0
        gen.draw(screen)
        pygame.display.flip()
        clock.tick(30)


if __name__ == "__main__":
    sys.exit(main() or 0)
