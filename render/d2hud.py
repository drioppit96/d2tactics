"""Diablo 2's own interface, drawn from the game's UI files.

Everything is laid out in D2's 800x600 coordinates and scaled to the window height,
so the control panel, globes, belt, character sheet, inventory and skill tree sit
exactly where they do in the original.
"""
import pygame

from d2.dc6 import DC6
from d2.font import FontTable
from game.items import SLOTS

PANEL = "data\\global\\ui\\PANEL\\"
FONTS = "data\\local\\font\\latin\\"
SPELLS = "data\\global\\ui\\SPELLS\\"

WHITE = (255, 255, 255)
GREY = (150, 150, 150)
GOLD = (199, 179, 119)
GREEN = (0, 220, 0)
RED = (255, 80, 80)
BLUE = (105, 105, 255)
YELLOW = (255, 255, 100)

# exact boxes measured from the panel art (panel-local 320x432 coordinates)
INV_SLOTS = {"helm": (132, 2, 60, 60), "amulet": (205, 30, 30, 31), "weapon": (17, 45, 60, 116),
             "shield": (248, 45, 60, 117), "armor": (132, 73, 60, 89), "gloves": (17, 175, 60, 61),
             "ring1": (91, 175, 30, 31), "belt": (133, 175, 60, 31), "ring2": (205, 175, 30, 31),
             "boots": (248, 175, 60, 61)}
GRID_X, GRID_Y, CELL = 18, 255, 29
GOLD_BOX = (107, 392, 90, 18)
INV_CLOSE = (18, 385, 32, 32)
CHAR_CLOSE = (128, 389, 32, 32)
SKILL_TREE_X, SKILL_TREE_DX, SKILL_TREE_Y, SKILL_TREE_DY = 15, 69, 59, 63


def _num(v):
    if isinstance(v, float) and v != int(v):
        return ("%.1f" % v).rstrip("0").rstrip(".")
    return str(int(v))


def _wrap(text, width):
    out, line = [], ""
    for wd in text.split():
        trial = (line + " " + wd).strip()
        if len(trial) > width and line:
            out.append(line)
            line = wd
        else:
            line = trial
    if line:
        out.append(line)
    return out


class D2Font:
    def __init__(self, src, name):
        self.t = FontTable(src.read(FONTS + name + ".tbl"), src.read(FONTS + name + ".dc6"))
        self.cache = {}
        self.glyph_surf = {}
        self.palette = None

    def height(self):
        return self.t.line_height + 4

    def width(self, text):
        return self.t.measure(text)

    def render(self, text, color, indexed):
        key = (text, color)
        s = self.cache.get(key)
        if s is not None:
            return s
        w = max(1, self.t.measure(text))
        h = max(1, max((g[1].height for g in (self.t.glyph(c) for c in text) if g), default=self.t.line_height))
        s = pygame.Surface((w, h), pygame.SRCALPHA)
        s.fill((0, 0, 0, 0))
        x = 0
        for ch in text:
            g = self.t.glyph(ch)
            if not g:
                continue
            adv, fr = g
            if fr.width and fr.height:
                gk = id(fr)
                img = self.glyph_surf.get(gk)
                if img is None:
                    img = self.glyph_surf[gk] = indexed(fr.width, fr.height, fr.pixels)
                s.blit(img, (x, 0))
            x += adv
        if color != WHITE:
            tint = pygame.Surface((w, h), pygame.SRCALPHA)
            tint.fill(color + (255,))
            s.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        if len(self.cache) > 600:
            self.cache.clear()
        self.cache[key] = s
        return s


class D2Hud:
    def __init__(self, fonts, assets):
        self.fonts = fonts
        self.assets = assets
        src = assets.src
        self.src = src
        self.ind = getattr(assets, "indexed_surface_ui", assets.indexed_surface)
        self.frames = {}
        for n in ("800ctrlpnl7", "hlthmana", "overlap", "invchar6", "minipanel", "minipanelbtn", "level",
                  "runbutton", "mediumbuttonblank", "blank", "buysellbtn", "skillpoints", "buysell", "buyselltabs",
                  "gemsocket", "supertransmogrifier", "miniconvert", "tradestash", "npcinv"):
            self.frames[n] = self._load(PANEL + n + ".dc6", required=n in ("800ctrlpnl7", "hlthmana", "invchar6"))
        # D2's quest log and waypoint panels (Extract D2 interface.bat); without them a look-alike is drawn
        for n in ("questbackground", "questsockets", "questdone", "questlast", "expquesttabs",
                  "waygatebackground", "waygateicons", "expwaygatetabs", "waygatetabs"):
            self.frames[n] = self._load("data\\global\\ui\\MENU\\" + n + ".dc6")
        self._qicons = {}
        self.q_sel = {}
        self.cursor = self._load("data\\global\\ui\\CURSOR\\ohand.dc6")
        self.cursor_buysell = self._load("data\\global\\ui\\CURSOR\\buysell.dc6")   # 8 = identify (magnifying glass)
        self._class_art = {}
        self.skill_icons = None
        self.tree_back = None
        self.generic_icons = self._load(SPELLS + "Skillicon.DC6")
        self.use_class("bar")
        self.f16 = D2Font(src, "font16")
        self.f10 = D2Font(src, "fontformal10")
        self.f30 = D2Font(src, "font30")
        self.show_inv = False
        self.show_char = False
        self.show_skills = False
        self.show_quests = False
        self.show_loot = False
        self.loot_list = None
        self.show_automap = False
        self.automap_mode = 0           # 0 off, 1 full, 2 mini
        self.show_minipanel = True
        self.skill_popup = False
        self.store = None            # an open vendor (game.itemactions.Store)
        self.show_cube = False
        self.cube_item = None        # the Horadric Cube whose window is open
        self.npc_menu = None         # NPC whose talk / trade menu is open
        self.tracker_menu = False    # the quest tracker's list of objectives
        self.minimaps = {}
        self.regions = []
        self.hover_lines = None
        self.skill_page = 1
        self.scaled = {}
        self.s = 1.0
        self.lw = 800

    def use_class(self, cls):
        """Skill icons and skill tree art of the character's class."""
        if cls not in self._class_art:
            from game.skills import CLASS_BY_CODE
            info = CLASS_BY_CODE.get(cls, CLASS_BY_CODE["bar"])
            prefix, letter = info[3], info[4]
            icons = self._load(SPELLS + prefix.title() + "Skillicon.DC6") or self._load(SPELLS + prefix + "skillicon.dc6")
            back = self._load(SPELLS + "skltree_%s_back.DC6" % letter)
            self._class_art[cls] = (icons, back)
        self.skill_icons, self.tree_back = self._class_art[cls]
        self._art_class = cls

    # ------------------------------------------------------------ loading / scaling helpers
    def _load(self, path, required=False):
        if not self.src.has(path):
            if required:
                raise FileNotFoundError(path)
            return None
        try:
            dc = DC6(self.src.read(path))
        except Exception:
            if required:
                raise
            return None
        return [self.ind(f.width, f.height, f.pixels) if f.width and f.height else None for f in dc.frames]

    def S(self, img, k=None):
        """Scaled copy of a logical-size surface (cached)."""
        k = self.s if k is None else k
        key = (id(img), round(k, 3))
        ent = self.scaled.get(key)
        # the cache keeps the source image alive (and checks it): an id alone can be reused by a new
        # surface once the old one is gone - that put old tooltip text on the END TURN button
        if ent is None or ent[0] is not img:
            w, h = img.get_size()
            out = pygame.transform.smoothscale(img, (max(1, int(round(w * k))), max(1, int(round(h * k)))))
            if len(self.scaled) > 2500:
                self.scaled.clear()
            self.scaled[key] = (img, out)
            return out
        return ent[1]

    def P(self, x, y):
        return int(round(x * self.s)), int(round(y * self.s))

    def R(self, x, y, w, h):
        return pygame.Rect(int(round(x * self.s)), int(round(y * self.s)), int(round(w * self.s)), int(round(h * self.s)))

    def put(self, surf, img, x, y, area=None):
        if img is None:
            return
        sc = self.S(img)
        if area is None:
            surf.blit(sc, self.P(x, y))
        else:
            ax, ay, aw, ah = area
            r = pygame.Rect(int(ax * self.s), int(ay * self.s), int(round(aw * self.s)), int(round(ah * self.s)))
            surf.blit(sc, (int((x + ax) * self.s), int((y + ay) * self.s)), r)

    def text(self, surf, font, text, color, x, y, align="left", box_w=None):
        img = font.render(str(text), color, self.ind)
        w = img.get_width()
        if align == "center":
            x = x + ((box_w or 0) - w) / 2.0
        elif align == "right":
            x = x + (box_w or 0) - w
        self.put(surf, img, x, y)
        return w

    def region(self, x, y, w, h, action, arg=None):
        self.regions.append((pygame.Rect(int(x), int(y), int(w), int(h)), action, arg))

    # ------------------------------------------------------------ interface used by main.py
    def logical(self, pos):
        return pos[0] / self.s, pos[1] / self.s

    def hit(self, pos):
        lx, ly = self.logical(pos)
        for rect, action, arg in reversed(self.regions):
            if rect.collidepoint((int(lx), int(ly))):
                return action, arg
        return None

    def over_ui(self, pos):
        return self.hit(pos) is not None

    def grid_cell_at(self, pos):
        """Backpack cell under the mouse, or None."""
        if not self.show_inv:
            return None
        lx, ly = self.logical(pos)
        ox = self.lw - 320
        cx, cy = int((lx - ox - GRID_X) // CELL), int((ly - GRID_Y) // CELL)
        if 0 <= cx < 10 and 0 <= cy < 4:
            return cx, cy + 4 * self._inv_page()
        return None

    def _inv_page(self):
        """Which backpack page is shown (the second only with the Bigger Inventory option)."""
        w = getattr(self, "world", None)
        p = getattr(w, "player", None)
        if p is None or p.INV_H <= 4:
            self.inv_page = 0
        return getattr(self, "inv_page", 0)

    # ------------------------------------------------------------ drawing
    def draw(self, surf, world, scene, mouse):
        W, H = surf.get_size()
        self.s = H / 600.0
        self.lw = W / self.s
        self.regions = []
        self.hover_lines = None
        self.mouse = self.logical(mouse)
        self.world = world
        p = world.player
        self._draw_log(surf, scene)
        self._draw_automap(surf, world)
        if self.store is not None:
            self._draw_store(surf, world)
        elif getattr(self, "show_cube", False) and self.cube_item is not None:
            self._draw_cube(surf, world)
        elif getattr(self, "show_waypoints", False):
            self._draw_waypoints(surf, world)
        elif getattr(self, "show_merc", False) and getattr(p, "merc", None):
            self._draw_merc(surf, world)
        elif self.show_quests:
            self._draw_quests(surf, p)
        elif self.show_char:
            self._draw_char(surf, p)
        if self.show_inv:
            self._draw_inventory(surf, world)
        elif self.show_skills:
            self._draw_skill_tree(surf, p)
        if getattr(self, "loot_list", None) is not None:
            self._draw_loot(surf, world)
        self._draw_control_panel(surf, world, scene)
        self._draw_tracker(surf, world, scene)
        if self.skill_popup:
            self._draw_skill_popup(surf, p)
        if self.npc_menu is not None and self.store is None:
            self._draw_npc_menu(surf, world)
        if scene.banner:
            text, col, t = scene.banner
            img = self.f30.render(text, col if col != (220, 60, 50) else (255, 60, 60), self.ind)
            sc = self.S(img)
            sc.set_alpha(int(255 * min(1.0, t * 2)))
            surf.blit(sc, (W / 2 - sc.get_width() / 2, int(70 * self.s)))
            sc.set_alpha(None)
        tip = getattr(self, "world_tip", None)
        if not self.hover_lines and tip and getattr(world, "held", None) is None:
            texts, cols = tip
            anchor = getattr(self, "world_tip_anchor", None)
            if anchor is not None:
                # monster info sits at the top of the screen, out of the way of the fight
                self.tooltip(surf, list(zip(texts, list(cols) + [WHITE] * len(texts))), self.mouse, top=True)
            else:
                self.tooltip(surf, list(zip(texts, list(cols) + [WHITE] * len(texts))), self.mouse)
        if self.hover_lines:
            self.tooltip(surf, self.hover_lines, self.mouse)
        held = getattr(world, "held", None)
        if held is not None:
            self._draw_held(surf, held)
        self._draw_cursor(surf)

    # ------------------------------------------------------------ quest tracker
    def _quest_slot(self, qid):
        """(act, icon number) of a quest in D2's quest log."""
        from game import quests, quests2, quests345
        lists = {1: self.QUEST_ORDER[1], 2: [q for q, _ in quests2.ACT2]}
        for a, lst in quests345.ACTS.items():
            lists[a] = [q for q, _ in lst]
        for a, lst in lists.items():
            if qid in lst:
                return a, lst.index(qid) + 1
        return None

    def tracked_objective(self, world):
        """The objective you track (the quest's next part once one is done), or None."""
        from game import questguide
        p = world.player
        key = getattr(p, "tracked_quest", None)
        if not key:
            return None, []
        objs = questguide.objectives(world)
        cur = next((o for o in objs if o.key == key), None)
        if cur is None:
            cur = next((o for o in objs if o.qid == key.split(":")[0]), None)
            if cur is not None:
                p.tracked_quest = cur.key
        return cur, objs

    def _draw_tracker(self, surf, world, scene):
        """Bottom left, above the life globe: the tracked quest's icon (click: choose what to track),
        a compass arrow towards the next step and what that step is."""
        import math
        from game import questguide
        p = world.player
        px0, py0 = getattr(self, "panel_origin", ((self.lw - 704) / 2.0, 600 - 104))
        bx, by, bs = px0 + 6, py0 - 54, 46
        mx, my = self.mouse
        obj, objs = self.tracked_objective(world)
        if obj is None and not objs:
            objs = questguide.objectives(world)
        hot = pygame.Rect(int(bx), int(by), bs, bs).collidepoint((int(mx), int(my)))
        # the button: the quest's own icon from the quest log (D2's quest book when nothing is tracked)
        box = pygame.Surface((int(bs * self.s), int(bs * self.s)), pygame.SRCALPHA)
        box.fill((20, 16, 10, 225))
        surf.blit(box, self.P(bx, by))
        icon = None
        if obj is not None:
            slot = self._quest_slot(obj.qid)
            frames = self._quest_icon(*slot) if slot else None
            if frames:
                icon = frames[min(25, len(frames) - 1)]
        if icon is None:
            btns = self.frames.get("minipanelbtn") or []
            icon = btns[12] if len(btns) > 12 else None
        if icon is not None:
            iw, ih = icon.get_size()
            k = min((bs - 6) / float(iw), (bs - 6) / float(ih)) * self.s
            img = self.S(icon, k)
            surf.blit(img, (int((bx + bs / 2.0) * self.s - img.get_width() / 2),
                            int((by + bs / 2.0) * self.s - img.get_height() / 2)))
        else:
            self.text(surf, self.f16, "?", GOLD, bx, by + 14, "center", bs)
        pygame.draw.rect(surf, (230, 200, 120) if hot or self.tracker_menu else (140, 120, 75), self.R(bx, by, bs, bs), 1)
        self.region(bx, by, bs, bs, "tracker")
        if hot:
            self.hover_lines = [("Quest Tracker (J)", WHITE),
                                ("Click: choose a quest to follow" if objs else "No quest under way", GREY)]
        # the compass and what to do
        if obj is not None:
            name = getattr(getattr(self, "assets", None), "act_info", None)
            name = name.name if name is not None else (lambda lid: str(lid))
            cache = self.__dict__.setdefault("_track_cache", {})
            now = pygame.time.get_ticks() if hasattr(pygame.time, "get_ticks") else 0
            ck = (obj.key, p.pos, id(world), getattr(world, "level_id", None))
            if cache.get("k") != ck or now - cache.get("t", 0) > 500:
                try:
                    cell, lines = questguide.guide(world, obj, name)
                except Exception:
                    cell, lines = None, [obj.label]
                cache.update(k=ck, t=now, cell=cell, lines=lines)
            cell, lines = cache["cell"], cache["lines"]
            cx, cy, r = bx + bs + 26, by + bs / 2.0, 21
            ring = pygame.Surface((int(2 * r * self.s) + 2, int(2 * r * self.s) + 2), pygame.SRCALPHA)
            pygame.draw.circle(ring, (20, 16, 10, 220), (ring.get_width() // 2, ring.get_height() // 2), int(r * self.s))
            surf.blit(ring, (int((cx - r) * self.s), int((cy - r) * self.s)))
            pygame.draw.circle(surf, (140, 120, 75), self.P(cx, cy), int(r * self.s), 1)
            if cell is not None and cell != p.pos:
                from render.iso import cell_to_world
                ax, ay = cell_to_world(*p.pos)
                tx, ty = cell_to_world(*cell)
                ang = math.atan2(ty - ay, tx - ax)
                ca, sa = math.cos(ang), math.sin(ang)
                pts = [(16, 0), (-8, 9), (-3, 0), (-8, -9)]
                poly = [self.P(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]
                pygame.draw.polygon(surf, (240, 200, 90), poly)
                pygame.draw.polygon(surf, (90, 60, 20), poly, 1)
                d = max(abs(cell[0] - p.x), abs(cell[1] - p.y))
                if d <= 3:
                    lines = list(lines) + ["Right here"]
            else:
                self.text(surf, self.f16, "?", GREY, cx - 12, cy - 8, "center", 24)
            tx0 = cx + r + 8
            for i, (t, col) in enumerate(zip(lines[:3], [GOLD, WHITE, (150, 220, 150)])):
                img = (self.f16 if i == 0 else self.f10).render(t, col, self.ind)
                bg = pygame.Surface((int((img.get_width() + 8) * self.s), int((img.get_height() + 2) * self.s)), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 150))
                yy = by + 2 + i * 15
                surf.blit(bg, self.P(tx0 - 4, yy - 1))
                self.put(surf, img, tx0, yy)
            self.region(cx - r, cy - r, 2 * r, 2 * r, "tracker")
        if self.tracker_menu:
            self._draw_tracker_menu(surf, world, objs, bx, by)

    def _draw_tracker_menu(self, surf, world, objs, bx, by):
        p = world.player
        rows = [(o.key, "%s: %s" % (o.title, o.label)) for o in objs] + [(None, "Stop tracking")]
        w = max([self.f16.width(t) for _, t in rows] + [120]) + 34
        h = len(rows) * 20 + 8
        x, y = bx, by - h - 6
        bg = pygame.Surface((int(w * self.s), int(h * self.s)), pygame.SRCALPHA)
        bg.fill((10, 8, 5, 235))
        surf.blit(bg, self.P(x, y))
        pygame.draw.rect(surf, (140, 120, 75), self.R(x, y, w, h), 1)
        mx, my = self.mouse
        cur = getattr(p, "tracked_quest", None)
        for i, (key, text) in enumerate(rows):
            ry = y + 4 + i * 20
            hot = pygame.Rect(int(x), int(ry), int(w), 20).collidepoint((int(mx), int(my)))
            if hot:
                hl = pygame.Surface((int((w - 4) * self.s), int(19 * self.s)), pygame.SRCALPHA)
                hl.fill((90, 70, 30, 200))
                surf.blit(hl, self.P(x + 2, ry))
            col = GOLD if key == cur else (WHITE if key else GREY)
            if key:
                slot = self._quest_slot(key.split(":")[0])
                frames = self._quest_icon(*slot) if slot else None
                if frames:
                    f = frames[min(25, len(frames) - 1)]
                    k = 18.0 / max(f.get_size()) * self.s
                    img = self.S(f, k)
                    surf.blit(img, self.P(x + 6, ry + 1))
            self.text(surf, self.f16, text, col, x + 28, ry + 3)
            self.region(x, ry, w, 20, "track_pick", key or "")
        if not objs:
            self.text(surf, self.f10, "No quest under way", GREY, x + 6, y - 14)

    # ------------------------------------------------------------ message log
    def _left_panel_open(self):
        return bool(self.show_char or self.show_quests or getattr(self, "show_cube", False)
                    or getattr(self, "show_merc", False) or self.store is not None
                    or getattr(self, "show_waypoints", False))

    def _loot_rect(self):
        """Where the 'Items on screen' window sits (logical px), or None."""
        if getattr(self, "loot_list", None) is None:
            return None
        w = 270
        x0 = 330 if self._left_panel_open() else 8
        if x0 + w > self.lw - (320 if (self.show_inv or self.show_skills) else 0):
            x0 = 8
        h = 34 + max(1, len(self.loot_list[:20])) * 16 + 22
        return (x0, 104, w, h)

    def _left_edge(self):
        """The message log starts right of whatever window is open on the left."""
        x0 = 330 if self._left_panel_open() else 8
        lr = self._loot_rect()
        if lr is not None and lr[0] <= x0 + 10:
            x0 = lr[0] + lr[2] + 8
        return x0

    def covered_rects(self, W, H):
        """Screen rects hidden by open windows (world labels there would show through)."""
        s = H / 600.0
        lw = W / s
        out = []
        if self._left_panel_open():
            out.append(pygame.Rect(0, 0, int(320 * s), int(500 * s)))
        if self.show_inv or self.show_skills:
            out.append(pygame.Rect(int((lw - 320) * s), 0, int(320 * s), int(500 * s)))
        lr = self._loot_rect()
        if lr is not None:
            out.append(pygame.Rect(int(lr[0] * s), int(lr[1] * s), int(lr[2] * s), int(lr[3] * s)))
        return out

    def _draw_log(self, surf, scene):
        lines = [l for l in scene.log if l[2] < 9][-6:]
        y = 6
        x0 = self._left_edge()
        for text, col, age in lines:
            img = self.f16.render(text, col, self.ind)
            sc = self.S(img)
            if age > 7:
                sc.set_alpha(int(255 * max(0.0, (9 - age) / 2)))
            surf.blit(sc, self.P(x0, y))
            sc.set_alpha(None)
            y += 15

    # ------------------------------------------------------------ tooltip
    def tooltip(self, surf, lines, at, left_of=None, top=False):
        """lines: [(text, colour)] - drawn like D2's item description box."""
        if lines and isinstance(lines, tuple) and len(lines) == 2 and isinstance(lines[0], list):
            texts, cols = lines
            lines = list(zip(texts, cols + [WHITE] * (len(texts) - len(cols))))
        lh = 15
        w = max((self.f16.width(t) for t, _ in lines), default=10) + 14
        h = len(lines) * lh + 8
        if top:
            x, y = self.lw / 2.0 - w / 2.0, 6          # monster info: the top centre of the screen
        elif left_of is not None:
            x = left_of.x - w - 12
            if x < 4:
                x = left_of.x + left_of.w + 12
            x = min(max(4, x), self.lw - w - 4)
            y = min(max(4, left_of.y + left_of.h / 2 - h / 2), 600 - 110 - h)
        else:
            x = min(max(4, at[0] - w / 2), self.lw - w - 4)
            y = at[1] - h - 18
            if y < 4:
                y = at[1] + 24
        bg = pygame.Surface((int(w * self.s), int(h * self.s)), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 205))
        surf.blit(bg, self.P(x, y))
        for i, (t, c) in enumerate(lines):
            self.text(surf, self.f16, t, c, x, y + 4 + i * lh, "center", w)

    # ------------------------------------------------------------ control panel
    def _draw_control_panel(self, surf, world, scene):
        p = world.player
        cp = self.frames["800ctrlpnl7"]
        px0 = (self.lw - 704) / 2.0
        py0 = 600 - 104
        self.panel_origin = (px0, py0)
        # globes behind their holders
        pv = scene.view(p)
        # D2 order: holders, then the globes resting in their bowls, then the glass rims
        x = px0
        for i in range(6):
            img = cp[i]
            self.put(surf, img, x, py0 + 104 - img.get_height())
            x += img.get_width()
        GY = 12
        self._globe(surf, 0, px0 + 30, py0 + GY, max(0, pv.shown_hp) / float(max(1, p.max_hp)))
        self._globe(surf, 1, px0 + 594, py0 + GY, p.mana / float(max(1, p.max_mana)))
        ov = self.frames.get("overlap")
        if ov:
            self.put(surf, ov[0], px0 + 29, py0 + GY - 1)
            self.put(surf, ov[1] if len(ov) > 1 else ov[0], px0 + 593, py0 + GY - 1)
        self.region(px0, py0 + 49, 704, 55, "panel")
        self.region(px0, py0, 117, 104, "life")
        self.region(px0 + 587, py0, 117, 104, "mana")
        mx, my = self.mouse
        if pygame.Rect(int(px0 + 30), int(py0 + 12), 80, 80).collidepoint((int(mx), int(my))):
            self.hover_lines = [("Life: %d / %d" % (max(0, pv.shown_hp), p.max_hp), WHITE)]
        if pygame.Rect(int(px0 + 594), int(py0 + 12), 80, 80).collidepoint((int(mx), int(my))):
            self.hover_lines = [("Mana: %d / %d" % (p.mana, p.max_mana), WHITE)]

        # experience (thin bar) and action points (the stamina bar)
        prev = p.xp_threshold(p.level - 1)
        frac = (p.xp - prev) / float(max(1, p.xp_to_next() - prev))
        self._bar(surf, px0 + 210, py0 + 64, 118, 3, frac, (205, 190, 110))
        combat = world.mode == "combat"
        ap_frac = p.ap / float(max(1, p.max_ap)) if combat else 1.0
        self._bar(surf, px0 + 226, py0 + 76, 102, 17, ap_frac, (196, 156, 24) if combat else (120, 100, 40))
        if combat:
            self.text(surf, self.f10, "AP %d / %d" % (p.ap, p.max_ap), WHITE, px0 + 226, py0 + 78, "center", 102)
        if pygame.Rect(int(px0 + 210), int(py0 + 60), 118, 9).collidepoint((int(mx), int(my))):
            self.hover_lines = [("Experience: %d / %d" % (p.xp, p.xp_to_next()), WHITE)]
        if pygame.Rect(int(px0 + 226), int(py0 + 74), 102, 20).collidepoint((int(mx), int(my))):
            self.hover_lines = [("Action Points: %d / %d" % (p.ap if combat else p.max_ap, p.max_ap), WHITE),
                                ("Moving costs 1 AP per step in combat", GREY)]

        # run button = fast animations toggle
        rb = self.frames.get("runbutton")
        if rb:
            self.put(surf, rb[2 if scene.speed > 1 else 0], px0 + 208, py0 + 75)
            self.region(px0 + 208, py0 + 75, 16, 20, "speed")

        # skills: left = normal attack, right = selected skill
        self._skill_box(surf, px0 + 153, py0 + 65, getattr(p, "left_skill", None), "left")
        self._skill_box(surf, px0 + 510, py0 + 65, p.right_skill, "right")

        # belt
        for i in range(4):
            bx, by = px0 + 375 + i * 31, py0 + 66
            if i < len(p.belt):
                self._icon(surf, p.belt[i], bx, by, 29, 29)
                if pygame.Rect(int(bx), int(by), 29, 29).collidepoint((int(mx), int(my))):
                    self.hover_lines = p.belt[i].describe_lines(p)
            self.text(surf, self.f10, str(i + 1), GREY, bx + 21, by + 18)
            self.region(bx, by, 29, 29, "potion", i)

        # mini panel (character, inventory, skills, automap, ...)
        self.region(px0 + 342, py0 + 62, 17, 30, "minipanel")
        if self.show_minipanel and self.frames.get("minipanel"):
            mpx, mpy = px0 + 262, py0 + 22
            self.put(surf, self.frames["minipanel"][0], mpx, mpy)
            btns = self.frames.get("minipanelbtn") or []
            entries = [(0, "char", "Character (C)"), (2, "inv", "Inventory (I)"), (4, "skills", "Skill Tree (T)"),
                       (6, None, "Party"), (8, "automap", "Automap (Tab)"), (10, None, "Message Log"),
                       (12, "quests", "Quest Log (Q)"), (14, "menu", "Game Menu (Esc)")]
            for k, (fi, action, label) in enumerate(entries):
                bx = mpx + 4 + k * 21
                pressed = (action == "char" and self.show_char) or (action == "inv" and self.show_inv) or \
                          (action == "skills" and self.show_skills) or (action == "automap" and self.automap_mode) or \
                          (action == "quests" and self.show_quests)
                if fi + (1 if pressed else 0) < len(btns):
                    self.put(surf, btns[fi + (1 if pressed else 0)], bx, mpy + 3)
                if action:
                    self.region(bx, mpy + 3, 20, 20, action)
                if pygame.Rect(int(bx), int(mpy + 3), 20, 20).collidepoint((int(mx), int(my))):
                    self.hover_lines = [(label, WHITE)]

        # level-up buttons
        lvl = self.frames.get("level")
        if lvl and p.stat_points:
            self.put(surf, lvl[0], px0 + 121, py0 + 18)
            self.region(px0 + 121, py0 + 18, 30, 30, "char")
            if pygame.Rect(int(px0 + 121), int(py0 + 18), 30, 30).collidepoint((int(mx), int(my))):
                self.hover_lines = [("New Stats", WHITE)]
        if lvl and getattr(p, "skills", None) and p.skills.points:
            self.put(surf, lvl[0], px0 + 553, py0 + 18)
            self.region(px0 + 553, py0 + 18, 30, 30, "skills")
            if pygame.Rect(int(px0 + 553), int(py0 + 18), 30, 30).collidepoint((int(mx), int(my))):
                self.hover_lines = [("New Skill", WHITE)]

        # end turn (only on your turn in combat)
        if combat and world.turn == "player":
            mb = self.frames.get("mediumbuttonblank")
            bx, by = self.lw / 2.0 - 64, py0 - 36
            if mb:
                hot = pygame.Rect(int(bx), int(by), 128, 35).collidepoint((int(mx), int(my)))
                self.put(surf, mb[1 if hot and len(mb) > 1 else 0], bx, by)
            self.text(surf, self.f16, "END TURN", WHITE, bx, by + 11, "center", 128)
            self.text(surf, self.f10, "Round %d   (Space)" % world.round, GOLD, bx, by - 14, "center", 128)
            self.region(bx, by, 128, 35, "end_turn")

    def _green_globe(self):
        """D2's life globe turns green while you are poisoned: the red globe with red and green swapped."""
        gg = getattr(self, "_gglobe", None)
        if gg is None:
            src = self.frames["hlthmana"][0]
            gg = src
            try:
                gg = src.copy()
                w, h = gg.get_size()
                for yy in range(h):
                    for xx in range(w):
                        c = gg.get_at((xx, yy))
                        if c[3]:
                            gg.set_at((xx, yy), (c[1], c[0], c[2], c[3]))
            except Exception:
                gg = src
            self._gglobe = gg
        return gg

    def _globe(self, surf, idx, x, y, frac):
        g = self.frames["hlthmana"][idx]
        if idx == 0 and (getattr(self.world.player, "effects", None) or {}).get("poison"):
            g = self._green_globe()
        frac = max(0.0, min(1.0, frac))
        h = g.get_height()
        top = int(round(h * (1 - frac)))
        if top < h:
            self.put(surf, g, x, y, area=(0, top, g.get_width(), h - top))

    def _bar(self, surf, x, y, w, h, frac, color):
        frac = max(0.0, min(1.0, frac))
        if frac <= 0:
            return
        r = self.R(x, y, w * frac, h)
        bar = pygame.Surface(r.size, pygame.SRCALPHA)
        bar.fill(color + (200,))
        surf.blit(bar, r.topleft)

    def _skill_icon(self, name):
        p = self.world.player
        if getattr(self, "_art_class", None) != getattr(p, "cls", "bar"):
            self.use_class(getattr(p, "cls", "bar"))
        if name is None or name == "attack":
            if self.generic_icons:
                return self.generic_icons[0]
            return None
        if name == "throw":
            gi = self.generic_icons
            return gi[6] if gi and len(gi) > 6 and gi[6] is not None else None
        s = p.skills.tree.get(name)
        if s and self.skill_icons and s.icon < len(self.skill_icons):
            return self.skill_icons[s.icon]
        return None

    def _skill_box(self, surf, x, y, name, side):
        icon = self._skill_icon(name)
        p = self.world.player
        if icon is not None:
            k = self.s * 36.0 / max(icon.get_width(), 1)
            surf.blit(self.S(icon, k), self.P(x, y))
        else:
            label = "ATK" if name in (None, "attack") else "THR" if name == "throw" else "".join(w[0] for w in name.split())[:3].upper()
            self.text(surf, self.f16, label, GOLD, x, y + 11, "center", 36)
        self.region(x, y, 36, 36, "skill_" + side)
        mx, my = self.mouse
        if pygame.Rect(int(x), int(y), 36, 36).collidepoint((int(mx), int(my))):
            if True:
                if name in (None, "attack"):
                    self.hover_lines = [("%s click: Attack" % side.title(), WHITE), ("Click here to choose a skill", GREY)]
                else:
                    ap, mana = self.world.skill_cost(name)
                    sk = p.skills.tree.get(name)
                    title = sk.title if sk is not None else name
                    self.hover_lines = [(title, GREEN), ("Level %d" % p.skills.level(name), WHITE)] + \
                        [(t, WHITE) for t in p.skills.describe(name)] + \
                        [("%d AP, %s mana" % (ap, _num(mana)), GREY), ("Click to change skill", GREY)]

    def _draw_skill_popup(self, surf, p):
        """Choose the left / right click skill: learned active skills in rows above that button."""
        px0, py0 = self.panel_origin
        side = self.skill_popup if self.skill_popup in ("left", "right") else "right"
        options = ["attack"] + (["throw"] if getattr(p, "throwing", False) else []) + [n for n in p.skills.actives()]
        current = (getattr(p, "left_skill", None) if side == "left" else p.right_skill) or "attack"
        per_row = 8
        for i, name in enumerate(options):
            row, col = divmod(i, per_row)
            x = (px0 + 704 - 40 - col * 40) if side == "right" else (px0 + 4 + col * 40)
            y = py0 + 20 - row * 40
            bg = pygame.Surface((int(38 * self.s), int(38 * self.s)), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 200))
            surf.blit(bg, self.P(x - 1, y - 1))
            icon = self._skill_icon(name)
            if icon is not None:
                surf.blit(self.S(icon, self.s * 36.0 / icon.get_width()), self.P(x, y))
            else:
                lab = "ATK" if name == "attack" else "THR" if name == "throw" else "".join(w[0] for w in name.split())[:3].upper()
                self.text(surf, self.f16, lab, GOLD, x, y + 11, "center", 36)
            if name == current:
                pygame.draw.rect(surf, GOLD, self.R(x - 1, y - 1, 38, 38), 1)
            self.region(x, y, 36, 36, "pick_skill", (side, name))
            mx, my = self.mouse
            if pygame.Rect(int(x), int(y), 36, 36).collidepoint((int(mx), int(my))):
                sk = p.skills.tree.get(name)
                title = {"attack": "Attack", "throw": "Throw"}.get(name) or (sk.title if sk else name)
                self.hover_lines = [(title, GREEN if name not in ("attack", "throw") else WHITE)]

    # ------------------------------------------------------------ panels
    def _panel_bg(self, surf, ox, frames, base=0):
        for i, (x, y) in zip(range(base, base + 4), [(0, 0), (256, 0), (0, 256), (256, 256)]):
            if i < len(frames) and frames[i] is not None:
                self.put(surf, frames[i], ox + x, y)
        self.region(ox, 0, 320, 432, "panel")

    def _respec_button(self, surf):
        bx, by = 14, 394
        hot = pygame.Rect(bx, by, 104, 22).collidepoint((int(self.mouse[0]), int(self.mouse[1])))
        bg = pygame.Surface((int(104 * self.s), int(22 * self.s)), pygame.SRCALPHA)
        bg.fill((80, 60, 30, 240) if hot else (40, 30, 20, 230))
        surf.blit(bg, self.P(bx, by))
        pygame.draw.rect(surf, GOLD, self.R(bx, by, 104, 22), 1)
        self.text(surf, self.f10, "RESPEC", GOLD if hot else WHITE, bx, by + 5, "center", 104)
        self.region(bx, by, 104, 22, "respec")
        if hot:
            self.hover_lines = [("Respec (free)", WHITE), ("Every stat and skill point you spent", GREY),
                                ("goes back, like Akara's reset in D2", GREY)]

    def _draw_char(self, surf, p):
        self._panel_bg(surf, 0, self.frames["invchar6"], 0)
        self._respec_button(surf)
        t, f10, f16 = self.text, self.f10, self.f16
        t(surf, f16, p.name, GOLD, 11, 12, "center", 171)
        t(surf, f16, getattr(p, "class_name", "Barbarian"), GOLD, 193, 12, "center", 117)
        t(surf, f10, "Level", GOLD, 10, 34, "center", 44)
        t(surf, f16, str(p.level), WHITE, 10, 50, "center", 44)
        t(surf, f10, "Experience", GOLD, 66, 34, "center", 116)
        t(surf, f16, str(p.xp), WHITE, 66, 50, "center", 116)
        t(surf, f10, "Next Level", GOLD, 192, 34, "center", 118)
        t(surf, f16, str(p.xp_to_next()), WHITE, 192, 50, "center", 118)
        rows = [("Strength", p.strength, p.base_str, "str", 83), ("Dexterity", p.dexterity, p.base_dex, "dex", 145),
                ("Vitality", p.vitality, p.base_vit, "vit", 231), ("Energy", p.energy, p.base_eng, "eng", 293)]
        lvl = self.frames.get("level")
        for label, val, base, key, y in rows:
            t(surf, f10, label, GOLD, 10, y + 2, "center", 65)
            t(surf, f16, str(val), BLUE if val > base else WHITE, 76, y + 1, "center", 39)
            if p.stat_points and lvl:
                img = lvl[0]
                k = self.s * 20.0 / img.get_width()
                surf.blit(self.S(img, k), self.P(124, y - 2))
                self.region(124, y - 2, 20, 20, "stat", key)
        res = getattr(p, "res", {})
        right = [("Damage", "%d-%d" % p.dmg, 83, 98, 260), ("Attack Cost", "%d AP" % p.attack_cost, 107, 98, 260),
                 ("Attack Rating", str(p.ar), 145, 108, 271), ("Defense", str(p.defense), 169, 109, 271),
                 ("Chance to Block", "%d%%" % getattr(p, "block_chance", 0), 193, 109, 271)]
        for label, val, y, lw_, vx in right:
            t(surf, f10, label, GOLD, 161, y + 2, "center", lw_)
            t(surf, f16, val, WHITE, vx, y + 1, "center", 310 - vx)
        world = self.world
        ap_now = p.ap if world.mode == "combat" else p.max_ap
        for label, cur, mx_, y in (("Action Points", ap_now, p.max_ap, 231), ("Life", p.hp, p.max_hp, 255),
                                   ("Mana", p.mana, p.max_mana, 293)):
            t(surf, f10, label, GOLD, 161, y + 2, "center", 69)
            t(surf, f16, str(int(cur)), WHITE, 231, y + 1, "center", 39)       # mana regenerates in fractions
            t(surf, f16, str(int(mx_)), WHITE, 271, y + 1, "center", 39)
        for i, (label, key) in enumerate((("Fire Resist", "fire"), ("Cold Resist", "cold"),
                                          ("Lightning Resist", "ltng"), ("Poison Resist", "pois"))):
            y = 332 + i * 24
            t(surf, f10, label, GOLD, 174, y + 2, "center", 96)
            v = res.get(key, 0)
            t(surf, f16, str(v), WHITE if v >= 0 else RED, 271, y + 1, "center", 39)
        if p.stat_points:
            t(surf, f10, "Stat Points", RED, 10, 340, "center", 110)
            t(surf, f10, "Remaining", RED, 10, 354, "center", 110)
            t(surf, f16, str(p.stat_points), WHITE, 10, 370, "center", 110)
        self._close_button(surf, CHAR_CLOSE, 0, "char")

    # D2's quest log (questbackground.dc6, 320x432): tabs on top, a 3 x 2 board of 80x95 sockets with the
    # 72x86 quest icons, the quest's name bar and its description box, Play Dialogue + close at the bottom
    QUEST_SOCKETS = [(40, 33), (120, 33), (200, 33), (40, 130), (120, 130), (200, 130)]
    QUEST_SLOTS = [(x + 4, y + 4) for x, y in QUEST_SOCKETS]
    QUEST_ORDER = {1: ["den", "blood_raven", "malus", "cain", "tower", "andariel"]}         # D2's quest log order
    QUEST_CLOSE = (278, 389, 32, 32)
    WP_CLOSE = (272, 385, 32, 32)

    def _quest_icon(self, act, n):
        key = (act, n)
        if key not in self._qicons:
            self._qicons[key] = self._load("data\\global\\ui\\MENU\\a%dq%d.dc6" % (act, n))
        return self._qicons[key]

    def _greyed(self, img):
        """A grey copy of an icon (cached)."""
        cache = self.__dict__.setdefault("_grey_cache", {})
        ent = cache.get(id(img))
        g = ent[1] if ent is not None and ent[0] is img else None
        if g is None:
            try:
                g = pygame.transform.grayscale(img)
            except Exception:
                g = img.copy()
                w, h = g.get_size()
                for yy in range(h):
                    for xx in range(w):
                        r, gg, b, a = g.get_at((xx, yy))
                        if a:
                            v = (r * 30 + gg * 59 + b * 11) // 100
                            g.set_at((xx, yy), (v, v, v, a))
            cache[id(img)] = (img, g)
        return g

    def _act_tabs(self, surf, acts, current, action, frames_key):
        """D2's act tabs (63x31 each, bright = the open act) along the top of the panel."""
        tabs = self.frames.get(frames_key) or self.frames.get("expwaygatetabs")
        for a in range(1, 6):
            x, y, w = 2 + (a - 1) * 63, 0, 63
            if a not in acts:
                continue
            on = a == current
            f = None
            if tabs:
                k = (a - 1) * 2 + (0 if on else 1)
                f = tabs[k] if k < len(tabs) else None
            if f is not None:
                self.put(surf, f, x, y)
            else:
                box = pygame.Surface((int((w - 2) * self.s), int(28 * self.s)), pygame.SRCALPHA)
                box.fill((70, 58, 30, 230) if on else (20, 16, 10, 200))
                surf.blit(box, self.P(x, y))
                pygame.draw.rect(surf, (120, 100, 60) if on else (70, 60, 40), self.R(x, y, w - 2, 28), 1)
                self.text(surf, self.f16, "I II III IV V".split()[a - 1], WHITE if on else (150, 140, 120),
                          x, y + 6, "center", w - 2)
            self.region(x, y, w, 30, action, a)

    def _draw_quests(self, surf, p):
        """D2's quest log: act tabs, the board of quest icons (in colour while the quest is under way,
        grey once done after D2's completion animation, dark when not started), the chosen quest's
        name and what to do next."""
        from game.quests import journal
        from game.acts import act_of
        bg = self.frames.get("questbackground")
        self._panel_bg(surf, 0, bg or self.frames.get("blank") or self.frames["invchar6"], 0)
        here = act_of(self.world.level_id) if getattr(self, "world", None) and self.world.level_id else 1
        top = max([here, int(getattr(p, "current_act", 1) or 1)] + [act_of(l) for l in getattr(p, "visited", ()) if l])
        acts = list(range(1, min(5, top) + 1))
        if getattr(self, "q_act", None) not in acts:
            self.q_act = here if here in acts else acts[-1]
        act = self.q_act
        self._act_tabs(surf, acts, act, "q_tab", "expquesttabs")
        entries = journal(p, act)
        from game import quests as _q
        ids = [q for q, _ in ({1: _q.ACT1}.get(act) or [])]
        order = self.QUEST_ORDER.get(act)
        if order and ids:
            entries = [entries[ids.index(q)] for q in order if q in ids]
        sel = self.q_sel.get(act)
        if sel is None or sel >= len(entries):
            sel = next((i for i, e in enumerate(entries) if e[1] not in ("done", "none")), 0)
            self.q_sel[act] = sel
        sockets = self.frames.get("questsockets")
        mx, my = self.mouse
        import time as _t
        seen = p.__dict__.setdefault("_quest_anim", {})
        for i, (title, status, text) in enumerate(entries[:6]):
            sx, sy = self.QUEST_SOCKETS[i]
            x, y = self.QUEST_SLOTS[i]
            if sockets:
                f = sockets[1 if i == sel and len(sockets) > 1 else 0]
                if f is not None:
                    self.put(surf, f, sx, sy)
            else:
                pygame.draw.rect(surf, (200, 170, 90) if i == sel else (60, 55, 45), self.R(sx, sy, 80, 95), 2)
            icon = self._quest_icon(act, i + 1)
            if icon:
                if status == "done":
                    # D2 plays the completion animation once (the first time you look), then the grey icon
                    t0 = seen.get((act, i))
                    if t0 is None:
                        t0 = seen[(act, i)] = _t.time()
                    k = int((_t.time() - t0) * 12)
                    idx = k if k < 24 else 24
                else:
                    idx = 25 if status != "none" else 26
                f = icon[min(idx, len(icon) - 1)]
                if f is not None:
                    self.put(surf, f, x, y)
            else:
                box = pygame.Surface((int(72 * self.s), int(86 * self.s)), pygame.SRCALPHA)
                box.fill((50, 40, 25, 230) if status not in ("done", "none") else ((40, 40, 40, 230) if status == "done" else (12, 12, 12, 230)))
                surf.blit(box, self.P(x, y))
                self.text(surf, self.f30, "+" if status == "done" else ("?" if status == "none" else "!"),
                          GREY if status == "done" else ((230, 200, 120) if status != "none" else (80, 75, 65)),
                          x, y + 26, "center", 72)
            self.region(sx, sy, 80, 95, "q_pick", (act, i))
            if pygame.Rect(int(sx), int(sy), 80, 95).collidepoint((int(mx), int(my))):
                self.hover_lines = [(title, GOLD if status != "none" else GREY)]
        if entries:
            title, status, text = entries[sel]
            self.text(surf, self.f16, title, WHITE if status != "none" else GREY, 0, 234, "center", 320)
            if status == "done":
                text = "Quest completed."
            words, line, y = (text or "").split(), "", 262
            for wd in words:
                trial = (line + " " + wd).strip()
                if self.f16.width(trial) > 284:
                    self.text(surf, self.f16, line, WHITE, 18, y)
                    y += 16
                    line = wd
                else:
                    line = trial
            if line:
                self.text(surf, self.f16, line, WHITE, 18, y)
        # Play Quest Dialogue (D2 replays what the quest giver said): here the quest's text goes to the log
        ql = self.frames.get("questlast")
        if entries and entries[sel][1] != "none":
            bx, by = 226, 389
            hot = pygame.Rect(bx, by, 32, 32).collidepoint((int(mx), int(my)))
            if ql:
                f = ql[1 if hot and len(ql) > 1 else 0]
                if f is not None:
                    self.put(surf, f, bx + 1, by + 1)
            self.region(bx, by, 32, 32, "q_dialogue", entries[sel])
            if hot:
                self.hover_lines = [("Play Quest Dialogue", WHITE)]
        self._close_button(surf, self.QUEST_CLOSE, 0, "quests")

    # ------------------------------------------------------------ vendors
    STORE_GRID = (15, 62)

    def _draw_npc_menu(self, surf, world):
        """D2's NPC menu: Talk / Trade / Gamble / ... / Cancel."""
        from game.itemactions import NPC_OPTIONS
        npc = self.npc_menu
        opts = NPC_OPTIONS.get(getattr(npc, "npc", ""), ["Talk"]) + ["Cancel"]
        w, h = 200, 34 + 24 * len(opts)
        x0, y0 = self.lw / 2.0 - w / 2.0, 120
        bg = pygame.Surface((int(w * self.s), int(h * self.s)), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 215))
        surf.blit(bg, self.P(x0, y0))
        pygame.draw.rect(surf, (110, 100, 70), self.R(x0, y0, w, h), 1)
        self.text(surf, self.f16, npc.name, GOLD, x0, y0 + 8, "center", w)
        mx, my = self.mouse
        for i, o in enumerate(opts):
            y = y0 + 32 + i * 24
            hot = pygame.Rect(int(x0), int(y - 2), w, 22).collidepoint((int(mx), int(my)))
            self.text(surf, self.f16, o, WHITE if hot else (200, 190, 160), x0, y, "center", w)
            self.region(x0, y - 2, w, 22, "npc_opt", o)

    def _draw_store(self, surf, world):
        from game.itemactions import TAB_NAMES
        st = self.store
        p = world.player
        fr = self.frames.get("buysell") or self.frames.get("blank") or self.frames["invchar6"]
        self._panel_bg(surf, 0, fr, 0)
        tabs = self.frames.get("buyselltabs") or []
        mx, my = self.mouse
        for i, (page, _) in enumerate(st.tabs):
            x = 1 + i * 79
            active = i == st.tab
            f = tabs[(i * 2 + (0 if active else 1)) % len(tabs)] if tabs else None
            if f is not None:
                self.put(surf, f, x, 0)
            self.text(surf, self.f10, TAB_NAMES.get(page, page), WHITE if active else GREY, x, 9, "center", 79)
            self.region(x, 0, 79, 31, "store_tab", i)
        gx, gy = self.STORE_GRID
        held = getattr(world, "held", None)
        self.region(gx, gy, 10 * CELL, 10 * CELL, "store_grid")
        for it in st.items():
            sx, sy = it.store_pos
            w, h = max(1, it.invw), max(1, it.invh)
            x, y = gx + sx * CELL, gy + sy * CELL
            tint = pygame.Surface((int((w * CELL - 1) * self.s), int((h * CELL - 1) * self.s)), pygame.SRCALPHA)
            ok = it.mod_list is None or not hasattr(it, "requirements_ok") or it.requirements_ok(p)
            tint.fill((10, 10, 40, 120) if ok else (150, 0, 0, 70))
            surf.blit(tint, self.P(x, y))
            self._icon(surf, it, x, y, w * CELL - 1, h * CELL - 1)
            self.region(x, y, w * CELL, h * CELL, "store_item", it)
            if held is None and pygame.Rect(int(x), int(y), w * CELL, h * CELL).collidepoint((int(mx), int(my))):
                lines = list(it.describe_lines(p)) if not getattr(it, "gamble", False) else \
                    [(it.base.get("name", it.name), WHITE), ("Gamble: a random magic item of this kind", GREY)]
                cost = world.price_of(it)
                lines.append(("Cost: %d" % cost, WHITE if p.gold >= cost else RED))
                lines.append(("Left click to buy", GREY))
                self.hover_lines = lines
        self.text(surf, self.f16, "Gold: %d" % p.gold, GOLD, 20, 359)
        self.text(surf, self.f10, "Right click your", GREY, 14, 385)
        self.text(surf, self.f10, "items to sell", GREY, 14, 400)
        from game.itemactions import SMITHS
        if getattr(st, "npc", None) in SMITHS:
            self._socket_button(surf, world, st)
        if st.tabs and st.tabs[0][0] == "gamble":
            # D2: a new selection of gambling items
            bx, by = 170, 356
            hot = pygame.Rect(bx, by, 90, 22).collidepoint((int(mx), int(my)))
            bg = pygame.Surface((int(90 * self.s), int(22 * self.s)), pygame.SRCALPHA)
            bg.fill((80, 60, 30, 240) if hot else (40, 30, 20, 230))
            surf.blit(bg, self.P(bx, by))
            pygame.draw.rect(surf, GOLD, self.R(bx, by, 90, 22), 1)
            self.text(surf, self.f10, "REFRESH", GOLD if hot else WHITE, bx, by + 5, "center", 90)
            self.region(bx, by, 90, 22, "gamble_refresh")
            if hot:
                self.hover_lines = [("Refresh", WHITE), ("New items to gamble on", GREY)]
        self._close_button(surf, (271, 383, 32, 32), 0, "store_close")

    SOCKET_BTN = (167, 383, 32, 32)

    def _socket_button(self, surf, world, st):
        """The blacksmith's Socket Item button: click it, then click an item (hammer cursor)."""
        x, y, bw, bh = self.SOCKET_BTN
        mode = getattr(world, "cursor_mode", None)
        on = bool(mode and mode[0] == "socket")
        b = self.frames.get("buysellbtn") or []
        if len(b) > 1:
            self.put(surf, b[1 if on else 0], x, y)
        else:
            pygame.draw.rect(surf, GOLD, self.R(x, y, bw, bh), 1)
        hole = (self.frames.get("gemsocket") or [None])[0]
        if hole is not None:
            hw, hh = hole.get_size()
            k = min(1.0, 22.0 / max(hw, hh)) * self.s
            img = self.S(hole, k)
            surf.blit(img, (int((x + bw / 2.0 + (1 if on else 0)) * self.s - img.get_width() / 2),
                            int((y + bh / 2.0 + (1 if on else 0)) * self.s - img.get_height() / 2)))
        else:
            pygame.draw.circle(surf, (20, 20, 20), self.P(x + 16, y + 16), int(8 * self.s))
            pygame.draw.circle(surf, (150, 130, 80), self.P(x + 16, y + 16), int(8 * self.s), 1)
        self.region(x, y, bw, bh, "socket_mode")
        mx, my = self.mouse
        if pygame.Rect(x, y, bw, bh).collidepoint((int(mx), int(my))) and getattr(world, "held", None) is None:
            self.hover_lines = [("Socket Item", WHITE),
                                ("Then click an item: one more socket" if not on else "Click again to stop", GREY),
                                ("Costs twice the item's price", GREY)]

    def _draw_sockets(self, surf, it, x, y, w, h):
        """Socket holes (and what's in them) over a hovered item, like D2."""
        n = getattr(it, "sockets", 0)
        if not n:
            return
        gs = (self.frames.get("gemsocket") or [None])[0]
        cols = 1 if w < 50 else 2
        rows = (n + cols - 1) // cols
        for i in range(n):
            cx = x + (w / cols) * (i % cols) + (w / cols - 28) / 2.0
            cy = y + (h / rows) * (i // cols) + (h / rows - 28) / 2.0
            if gs is not None:
                self.put(surf, gs, cx, cy)
            else:
                pygame.draw.circle(surf, (60, 60, 60), self.P(cx + 14, cy + 14), int(12 * self.s), 1)
            if i < len(it.socketed):
                self._icon(surf, it.socketed[i], cx + 2, cy + 2, 24, 24)

    def _draw_waypoints(self, surf, world):
        """D2's waypoint panel (waygatebackground.dc6): act tabs, then the act's waypoints in the nine
        slots down the left - a blue gate for the ones you found, crossed out for the others. The boss
        waypoints of this game are on a second page."""
        from game.acts import WAYPOINTS, act_of, BOSS_WAYPOINTS
        p = world.player
        info = getattr(world, "info", None)
        bg = self.frames.get("waygatebackground")
        here = world.level_id
        mx, my = self.mouse
        got = getattr(p, "waypoints", {1})
        acts = [a for a in sorted(WAYPOINTS) if any(l in got for l in WAYPOINTS[a])] or [1]
        if getattr(self, "wp_act", None) not in acts:
            cur = act_of(here) if here else 1
            self.wp_act = cur if cur in acts else acts[-1]
        bosses = BOSS_WAYPOINTS.get(self.wp_act, [])
        rows = list(WAYPOINTS[self.wp_act])[:11]
        extra = max(0, len(rows) - 9)
        self._waygate_bg(surf, bg, extra)
        self._act_tabs(surf, acts, self.wp_act, "wp_tab", "expwaygatetabs")
        self.text(surf, self.f16, "Choose your destination", GOLD, 0, 36, "center", 320)
        icons = self.frames.get("waygateicons")
        for i, lid in enumerate(rows):
            y = 58 + i * 36
            name = info.name(lid) if info else str(lid)
            on = lid in got
            hot = on and lid != here and pygame.Rect(15, y, 290, 34).collidepoint((int(mx), int(my)))
            if icons:
                k = (2 if lid == here else (1 if hot else 0)) if on else 3
                f = icons[min(k, len(icons) - 1)]
                if f is not None:
                    self.put(surf, f, 17, y + 2)
            else:
                box = pygame.Surface((int(30 * self.s), int(30 * self.s)), pygame.SRCALPHA)
                box.fill((60, 90, 150, 230) if on else (25, 22, 18, 220))
                surf.blit(box, self.P(17, y + 2))
            col = (GOLD if lid == here else ((255, 255, 255) if hot else (200, 190, 170))) if on else (95, 90, 80)
            self.text(surf, self.f16, name, col, 58, y + 10)
            if on and lid != here:
                self.region(15, y, 290, 34, "waypoint", lid)
        # TEST ONLY: remove later
        bx, by = 170, 394 + 36 * extra
        hot = pygame.Rect(bx, by, 96, 22).collidepoint((int(mx), int(my)))
        box = pygame.Surface((int(96 * self.s), int(22 * self.s)), pygame.SRCALPHA)
        box.fill((90, 40, 30, 220) if hot else (50, 20, 15, 200))
        surf.blit(box, self.P(bx, by))
        self.text(surf, self.f10, "All (test)", WHITE, bx, by + 5, "center", 96)
        self.region(bx, by, 96, 22, "wp_all")
        x, y, cw, ch = self.WP_CLOSE
        self._close_button(surf, (x, y + 36 * extra, cw, ch), 0, "waypoints")

    def _waygate_bg(self, surf, bg, extra):
        """D2's waypoint background, made taller by `extra` slots (36 px each) for this game's boss
        waypoints: a band of the slot column is repeated, so the slots keep lining up."""
        if not bg:
            self._panel_bg(surf, 0, self.frames.get("blank") or self.frames["invchar6"], 0)
            if extra:
                box = pygame.Surface((int(320 * self.s), int(36 * extra * self.s)), pygame.SRCALPHA)
                box.fill((10, 10, 10, 230))
                surf.blit(box, self.P(0, 432))
            return
        key = ("waygate", extra)
        comp = self.__dict__.setdefault("_bg_cache", {}).get(key)
        if comp is None:
            add = 36 * extra
            comp = pygame.Surface((320, 432 + add), pygame.SRCALPHA)
            comp.fill((0, 0, 0, 0))
            for i, (x, y) in enumerate([(0, 0), (256, 0), (0, 256 + add), (256, 256 + add)]):
                if i < len(bg) and bg[i] is not None:
                    comp.blit(bg[i], (x, y))
            if add:
                band = pygame.Surface((320, add), pygame.SRCALPHA)
                band.fill((0, 0, 0, 0))
                for i, x in ((0, 0), (1, 256)):
                    if i < len(bg) and bg[i] is not None:
                        band.blit(bg[i], (x, -(256 - add)))
                comp.blit(band, (0, 256))
            self._bg_cache[key] = comp
        self.put(surf, comp, 0, 0)
        self.region(0, 0, 320, 432 + 36 * extra, "panel")

    # ------------------------------------------------------------ the Horadric Cube
    CUBE_GRID = (117, 138)
    CUBE_BUTTON = (145, 259, 32, 32)
    CUBE_CLOSE = (275, 384, 32, 32)

    # ------------------------------------------------------------ the hireling
    MERC_SLOTS = {"helm": (131, 2, 60, 60), "armor": (131, 71, 60, 90), "weapon": (16, 44, 60, 117),
                  "shield": (247, 44, 60, 117)}

    def _draw_merc(self, surf, world):
        from game import hireling
        p = world.player
        merc = p.merc
        fr = self.frames.get("npcinv") or self.frames.get("blank") or self.frames["invchar6"]
        self._panel_bg(surf, 0, fr, 0)
        t, f10, f16 = self.text, self.f10, self.f16
        mx, my = self.mouse
        held = getattr(world, "held", None)
        k = hireling.KINDS.get(merc["kind"], {})
        for slot, (x, y, w, h) in self.MERC_SLOTS.items():
            if slot == "shield" and not k.get("shield"):
                continue
            it = (merc.get("items") or {}).get(slot)
            hot = pygame.Rect(x, y, w, h).collidepoint((int(mx), int(my)))
            if held is not None and hot:
                ok = hireling.can_wear(merc, held, slot)
                tint = pygame.Surface((int(w * self.s), int(h * self.s)), pygame.SRCALPHA)
                tint.fill((0, 120, 0, 70) if ok else (140, 0, 0, 70))
                surf.blit(tint, self.P(x, y))
            if it is not None:
                self._icon(surf, it, x, y, w, h)
                if hot and held is None:
                    self.hover_lines = it.describe_lines(p)
            self.region(x, y, w, h, "merc_slot", slot)
        st = hireling.stats(world.content, merc) or {}
        dead = merc.get("dead")
        t(surf, f16, merc["name"], GOLD if not dead else RED, 4, 200, "center", 153)
        t(surf, f16, hireling.TITLES.get(merc["kind"], ""), GOLD, 161, 200, "center", 155)
        t(surf, f10, "Experience", GOLD, 5, 224, "center", 124)
        t(surf, f16, str(merc["xp"]), WHITE, 5, 239, "center", 124)
        t(surf, f10, "Level", GOLD, 135, 224, "center", 51)
        t(surf, f16, str(merc["level"]), WHITE, 135, 239, "center", 51)
        t(surf, f10, "Next Level", GOLD, 191, 224, "center", 124)
        t(surf, f16, str(hireling.xp_needed(world.content, merc)), WHITE, 191, 239, "center", 124)
        unit = next((a for a in world.allies() if getattr(a, "hireling", False) and a.alive), None)
        life = "%d/%d" % (unit.hp, unit.max_hp) if unit is not None else ("dead" if dead else str(st.get("hp", 0)))
        rows = [("Strength", st.get("str", 0), "Dexterity", st.get("dex", 0)),
                ("Damage", "%d-%d" % tuple(st.get("dmg", (0, 0))), "Defense", st.get("defense", 0)),
                ("Life", life, "Attack Rating", st.get("ar", 0)),
                ("Resistances", "%d%%" % st.get("res", 0), "Skill", (st.get("skills") or [("-", 0)])[-1][0][:12])]
        for i, (a, av, b, bv) in enumerate(rows):
            y = 266 + i * 24
            t(surf, f10, a, GOLD, 6, y + 2, "center", 99)
            t(surf, f10, str(av), WHITE, 106, y + 2, "center", 50)
            t(surf, f10, b, GOLD, 164, y + 2, "center", 98)
            t(surf, f10, str(bv), WHITE, 263, y + 2, "center", 52)
        if dead:
            t(surf, f10, "Dead - %s brings them back for %d gold" % (k.get("seller", "the hiring NPC"),
                                                                   hireling.resurrect_cost(merc)), RED, 4, 372, "center", 260)
        self._close_button(surf, self.CUBE_CLOSE, 0, "merc_close")

    STASH_GRID = (28, 96)
    STASH_CELL = 22                 # the 12 x 16 stash uses smaller cells to fit D2's panel width
    STASH_H = 490                   # the stash panel is taller than D2's 432
    STASH_CLOSE = (276, 452, 32, 32)

    def _is_stash(self):
        return getattr(getattr(self, "cube_item", None), "code", "") == "stash"

    def _grid_geom(self):
        from game.cube import dims
        box = self.cube_item
        if self._is_stash():
            return self.STASH_GRID, dims(box)
        return self.CUBE_GRID, dims(box)

    def _gcell(self):
        return self.STASH_CELL if self._is_stash() else CELL

    def cube_cell_at(self, pos):
        if not getattr(self, "show_cube", False) or self.cube_item is None:
            return None
        if self._is_stash() and getattr(self.cube_item, "tab", 1) == 0:
            return None                       # the gem & rune tab has no grid
        lx, ly = self.logical(pos)
        (gx, gy), (W, H) = self._grid_geom()
        c = self._gcell()
        cx, cy = int((lx - gx) // c), int((ly - gy) // c)
        if 0 <= cx < W and 0 <= cy < H:
            return cx, cy
        return None

    def cube_anchor(self, item):
        (gx, gy), (W, H) = self._grid_geom()
        c = self._gcell()
        w, h = max(1, item.invw or 1), max(1, item.invh or 1)
        mx, my = self.mouse
        fx = int(round((mx - gx) / c - w / 2.0))
        fy = int(round((my - gy) / c - h / 2.0))
        return max(0, min(W - w, fx)), max(0, min(H - h, fy))

    def _stash_bg(self, surf):
        """D2's stash art, stretched to the bigger stash: its header, the side borders repeated
        down the grid, and the bottom edge."""
        bg = self.frames.get("tradestash")
        H = self.STASH_H
        comp = self.__dict__.setdefault("_bg_cache", {}).get(("stash", H))
        if comp is None:
            comp = pygame.Surface((320, H), pygame.SRCALPHA)
            comp.fill((12, 12, 12, 255))
            if bg and len(bg) >= 4:
                full = pygame.Surface((320, 432), pygame.SRCALPHA)
                full.fill((0, 0, 0, 0))
                for f, (x, y) in zip(bg, [(0, 0), (256, 0), (0, 256), (256, 256)]):
                    if f is not None:
                        full.blit(f, (x, y))
                top, band0, band1, foot = 92, 92, 330, 40
                comp.blit(full, (0, 0), pygame.Rect(0, 0, 320, top))
                y = top
                while y < H - foot:
                    hgt = min(band1 - band0, H - foot - y)
                    comp.blit(full, (0, y), pygame.Rect(0, band0, 320, hgt))
                    y += hgt
                comp.blit(full, (0, H - foot), pygame.Rect(0, 432 - foot, 320, foot))
            self._bg_cache[("stash", H)] = comp
        self.put(surf, comp, 0, 0)
        self.region(0, 0, 320, H, "panel")

    def _bank_layout(self):
        """(code, x, y, size) for every gem and rune on the stash's first tab."""
        lay = self.__dict__.get("_bank_lay")
        if lay is not None:
            return lay
        from game.cube import bank_codes
        rows, runes = bank_codes(getattr(self.world, "content", None))
        lay = []
        gs, rs = 36, 29
        gx = 28 + (264 - gs * 7) // 2
        for r, row in enumerate(rows):
            for c, code in enumerate(row):
                if code:
                    lay.append((code, gx + c * gs, 100 + r * gs, gs))
        rx = 28 + (264 - rs * 9) // 2
        ry = 100 + 5 * gs + 14
        for i, code in enumerate(runes):
            lay.append((code, rx + (i % 9) * rs, ry + (i // 9) * rs, rs))
        if rows and runes:
            self._bank_lay = lay
        return lay

    def _bank_icon(self, code):
        cache = self.__dict__.setdefault("_bank_items", {})
        it = cache.get(code)
        if it is None:
            c = getattr(self.world, "content", None)
            base = c.base_by_code.get(code) if c is not None else None
            if base is None:
                return None
            import random as _r
            it = cache[code] = c.make_item(base, 1, _r.Random(0))
        return it

    def _draw_bank(self, surf, world, box):
        p = world.player
        mx, my = self.mouse
        held = getattr(world, "held", None)
        bank = getattr(box, "bank", {}) or {}
        self.region(28, 96, 264, 352, "bank_area")
        lay = self._bank_layout()
        gem_end = max([y + sz for code, x, y, sz in lay if not code.startswith("r")] or [100])
        self.text(surf, self.f10, "Runes", GOLD, 28, gem_end + 1, "center", 264)
        for code, x, y, sz in lay:
            it = self._bank_icon(code)
            n = bank.get(code, 0)
            cell = pygame.Surface((int((sz - 2) * self.s), int((sz - 2) * self.s)), pygame.SRCALPHA)
            cell.fill((10, 10, 40, 150) if n else (0, 0, 0, 120))
            surf.blit(cell, self.P(x + 1, y + 1))
            pygame.draw.rect(surf, (90, 80, 55) if n else (45, 40, 30), self.R(x + 1, y + 1, sz - 2, sz - 2), 1)
            if it is not None:
                self._icon(surf, it, x + 2, y + 2, sz - 4, sz - 4)
            if not n:
                dim = pygame.Surface((int((sz - 4) * self.s), int((sz - 4) * self.s)), pygame.SRCALPHA)
                dim.fill((0, 0, 0, 165))
                surf.blit(dim, self.P(x + 2, y + 2))
            else:
                img = self.f10.render(str(n), WHITE, self.ind)
                tw, th = img.get_width(), img.get_height()
                tag = pygame.Surface((int((tw + 4) * self.s), int((th + 1) * self.s)), pygame.SRCALPHA)
                tag.fill((0, 0, 0, 200))
                surf.blit(tag, self.P(x + sz - tw - 6, y + sz - th - 3))
                self.put(surf, img, x + sz - tw - 4, y + sz - th - 3)
            self.region(x, y, sz, sz, "bank_take", code)
            if held is None and pygame.Rect(int(x), int(y), sz, sz).collidepoint((int(mx), int(my))) and it is not None:
                lines = [(it.name, it.color), ("In stash: %d" % n, WHITE if n else GREY)]
                if n:
                    lines += [("Left click: take one", GREY), ("Right click: one to your backpack", GREY)]
                self.hover_lines = lines
        if held is not None and pygame.Rect(28, 96, 264, 352).collidepoint((int(mx), int(my))):
            from game.cube import bankable
            if bankable(held):
                self.hover_lines = [("Click to put it on its stack", GREY)]

    def _draw_stash_tabs(self, surf, box):
        """Cycle the 30 tabs: arrows beside the tab name (or the mouse wheel over the stash)."""
        from game.cube import STASH_TABS
        tab = getattr(box, "tab", 1)
        name = "Gems & Runes" if tab == 0 else "Tab %d" % (tab + 1)
        self.text(surf, self.f16, name, GOLD, 96, 51, "center", 150)
        lab = pygame.Surface((int(50 * self.s), int(18 * self.s)), pygame.SRCALPHA)
        lab.fill((0, 0, 0, 200))
        surf.blit(lab, self.P(90, 459))
        self.text(surf, self.f10, "%d / %d" % (tab + 1, STASH_TABS), WHITE, 90, 463, "center", 50)
        b = self.frames.get("buysellbtn") or []
        mx, my = self.mouse
        for (x, d, fi) in ((14, -1, 12), (52, 1, 14)):
            hot = pygame.Rect(x, 452, 32, 32).collidepoint((int(mx), int(my)))
            down = hot and hasattr(pygame.mouse, "get_pressed") and pygame.mouse.get_pressed()[0]
            if len(b) > fi + 1:
                self.put(surf, b[fi + (1 if down else 0)], x, 452)
            else:
                pygame.draw.rect(surf, GOLD, self.R(x, 452, 32, 32), 1)
                self.text(surf, self.f16, "<" if d < 0 else ">", GOLD, x, 459, "center", 32)
            self.region(x, 452, 32, 32, "stash_tab", d)
            if hot:
                self.hover_lines = [("Previous tab" if d < 0 else "Next tab", WHITE), ("Mouse wheel: cycle tabs", GREY)]

    def _draw_cube(self, surf, world):
        from game import cube as cb
        p = world.player
        box = self.cube_item
        stash = self._is_stash()
        mx, my = self.mouse
        held = getattr(world, "held", None)
        if stash:
            self._stash_bg(surf)
            self.text(surf, self.f10, "Gold in stash: %d" % getattr(box, "gold", 0), WHITE, 96, 25, "center", 150)
            self.region(73, 20, 176, 22, "stash_gold")
            if pygame.Rect(73, 20, 176, 22).collidepoint((int(mx), int(my))) and held is None:
                self.hover_lines = [("Left click: put your gold in the stash", WHITE),
                                    ("Right click: take the stash's gold", WHITE)]
            self._draw_stash_tabs(surf, box)
            well = pygame.Surface((int(276 * self.s), int(366 * self.s)), pygame.SRCALPHA)
            well.fill((8, 8, 10, 255))
            surf.blit(well, self.P(22, 86))
            pygame.draw.rect(surf, (120, 105, 70), self.R(22, 86, 276, 366), 1)
            if getattr(box, "tab", 1) == 0:
                self._draw_bank(surf, world, box)
                self._close_button(surf, self.STASH_CLOSE, 0, "cube_close")
                return
        else:
            fr = self.frames.get("supertransmogrifier") or self.frames.get("blank") or self.frames["invchar6"]
            self._panel_bg(surf, 0, fr, 0)
            self.text(surf, self.f16, "Horadric Cube", GOLD, 0, 104, "center", 320)
        (gx, gy), (GW, GH) = self._grid_geom()
        C = self._gcell()
        if stash:
            # the stash's own grid (D2's art only has room for 6 x 8)
            back = pygame.Surface((int(GW * C * self.s) + 2, int(GH * C * self.s) + 2), pygame.SRCALPHA)
            back.fill((6, 6, 10, 255))
            surf.blit(back, self.P(gx - 1, gy - 1))
            for i in range(GW + 1):
                pygame.draw.line(surf, (38, 36, 32), self.P(gx + i * C, gy), self.P(gx + i * C, gy + GH * C))
            for j in range(GH + 1):
                pygame.draw.line(surf, (38, 36, 32), self.P(gx, gy + j * C), self.P(gx + GW * C, gy + j * C))
            pygame.draw.rect(surf, (120, 105, 70), self.R(gx - 2, gy - 2, GW * C + 4, GH * C + 4), 1)
        self.region(gx, gy, GW * C, GH * C, "cube_grid")
        for it in getattr(box, "contents", []) or []:
            if getattr(it, "cube_pos", None) is None:
                continue
            cx, cy = it.cube_pos
            w, h = max(1, it.invw or 1), max(1, it.invh or 1)
            x, y = gx + cx * C, gy + cy * C
            tint = pygame.Surface((int((w * C - 1) * self.s), int((h * C - 1) * self.s)), pygame.SRCALPHA)
            tint.fill((10, 10, 40, 120))
            surf.blit(tint, self.P(x + 1, y + 1))
            self._icon(surf, it, x + 1, y + 1, w * C - 1, h * C - 1)
            if held is None and pygame.Rect(int(x), int(y), w * C, h * C).collidepoint((int(mx), int(my))):
                self.hover_lines = list(it.describe_lines(p))
        if held is not None and self.cube_cell_at((mx * self.s, my * self.s)) is not None:
            ax, ay = self.cube_anchor(held)
            ok, over = cb.fits(box, held, ax, ay)
            good = ok and len(over) <= 1 and (held.code != "box" or stash)
            w, h = max(1, held.invw or 1), max(1, held.invh or 1)
            tint = pygame.Surface((int(w * C * self.s), int(h * C * self.s)), pygame.SRCALPHA)
            tint.fill((0, 120, 0, 70) if good else (140, 0, 0, 70))
            surf.blit(tint, self.P(gx + ax * C, gy + ay * C))
        if stash:
            self._close_button(surf, self.STASH_CLOSE, 0, "cube_close")
            return
        bx, by, bw, bh = self.CUBE_BUTTON
        btn = self.frames.get("miniconvert") or []
        hot = pygame.Rect(bx, by, bw, bh).collidepoint((int(mx), int(my)))
        down = hot and pygame.mouse.get_pressed()[0] if hasattr(pygame.mouse, "get_pressed") else False
        f = btn[1 if down and len(btn) > 1 else 0] if btn else None
        if f is not None:
            self.put(surf, f, bx, by)
        else:
            pygame.draw.rect(surf, (150, 130, 80), self.R(bx, by, bw, bh), 1)
        self.region(bx, by, bw, bh, "transmute")
        if hot and held is None:
            self.hover_lines = [("Transmute", WHITE)]
        self._close_button(surf, self.CUBE_CLOSE, 0, "cube_close")

    def _close_button(self, surf, box, ox, action):
        b = self.frames.get("buysellbtn")
        x, y, w, h = box
        if b and len(b) > 10:
            self.put(surf, b[10], ox + x, y)
        self.region(ox + x, y, w, h, action)

    def _icon(self, surf, item, x, y, w, h):
        """D2 inventory graphic for an item, centred in a logical box."""
        frames = None
        try:
            name = self.assets._inv_name(item)
            frames = self.assets._dc6(name) if name else None
        except Exception:
            frames = None
        if frames:
            img = frames[0][0]
            iw, ih = img.get_size()
            k = min(1.0, w / float(iw), h / float(ih)) * self.s
            sc = self.S(img, k)
            surf.blit(sc, (int((x + w / 2.0) * self.s - sc.get_width() / 2), int((y + h / 2.0) * self.s - sc.get_height() / 2)))
        else:
            self.assets.draw_item_icon(surf, item, self.R(x, y, w, h))

    def _draw_inventory(self, surf, world):
        p = world.player
        ox = self.lw - 320
        self._panel_bg(surf, ox, self.frames["invchar6"], 4)
        mx, my = self.mouse
        held = getattr(world, "held", None)
        self._weapon_tabs(surf, p, ox)
        for slot, (x, y, w, h) in INV_SLOTS.items():
            it = p.equipment.get(slot)
            box = pygame.Rect(int(ox + x), int(y), w, h)
            hot = box.collidepoint((int(mx), int(my)))
            if held is not None and hot:
                ok = world.slot_accepts(held, slot)
                tint = pygame.Surface((int(w * self.s), int(h * self.s)), pygame.SRCALPHA)
                tint.fill((0, 120, 0, 70) if ok else (140, 0, 0, 70))
                surf.blit(tint, self.P(ox + x, y))
            if it:
                if it.mod_list is not None and not it.requirements_ok(p):
                    tint = pygame.Surface((int(w * self.s), int(h * self.s)), pygame.SRCALPHA)
                    tint.fill((150, 0, 0, 70))
                    surf.blit(tint, self.P(ox + x, y))
                self._icon(surf, it, ox + x, y, w, h)
                if hot and held is None:
                    self.hover_lines = list(it.describe_lines(p)) + self._socket_cost_lines(it)
                    self._draw_sockets(surf, it, ox + x, y, w, h)
                elif hot and held is not None and getattr(held, "gem", None) and getattr(it, "sockets", 0):
                    self._draw_sockets(surf, it, ox + x, y, w, h)
            self.region(ox + x, y, w, h, "slot", slot)
        # backpack grid (one page of 4 rows; two pages with the Bigger Inventory option)
        page = self._inv_page()
        for it in p.inventory:
            if getattr(it, "inv_pos", None) is None:
                continue
            cx, cy = it.inv_pos
            if not page * 4 <= cy < page * 4 + 4:
                continue
            cy -= page * 4
            w, h = p._size(it)
            x, y = ox + GRID_X + cx * CELL, GRID_Y + cy * CELL
            if it.mod_list is not None and not it.requirements_ok(p):
                tint = pygame.Surface((int((w * CELL - 1) * self.s), int((h * CELL - 1) * self.s)), pygame.SRCALPHA)
                tint.fill((150, 0, 0, 70))
                surf.blit(tint, self.P(x, y))
            else:
                tint = pygame.Surface((int((w * CELL - 1) * self.s), int((h * CELL - 1) * self.s)), pygame.SRCALPHA)
                tint.fill((10, 10, 40, 120))      # D2 shades the cells an item covers
                surf.blit(tint, self.P(x, y))
            self._icon(surf, it, x, y, w * CELL - 1, h * CELL - 1)
            hot = pygame.Rect(int(x), int(y), w * CELL, h * CELL).collidepoint((int(mx), int(my)))
            if hot and (held is None or (getattr(held, "gem", None) and getattr(it, "sockets", 0))):
                self._draw_sockets(surf, it, x, y, w * CELL - 1, h * CELL - 1)
            if held is None and hot:
                lines = list(it.describe_lines(p))
                cur = p.equipment.get("ring1" if it.slot == "ring" else it.slot) if it.slot else None
                if cur:
                    lines = lines + [("", WHITE), ("Equipped: " + cur.shown_name, cur.color)]
                if self.store is not None:
                    from game.d2items import sell_price
                    from game.qol import is_goblin
                    if not is_goblin(it) and it.kind != "quest":
                        lines.append(("Sell value: %d (Ctrl + right click, or drag it to the shop)" % sell_price(it), GOLD))
                self.hover_lines = lines + self._socket_cost_lines(it)
        if held is not None:
            cell = self.grid_cell_at((mx * self.s, my * self.s))
            if cell:
                hw, hh = p._size(held)
                gx, gy = self._held_anchor(cell, held)
                ok, over = p.inv_fits(held, gx, gy)
                good = ok and len(over) <= 1
                tint = pygame.Surface((int((hw * CELL) * self.s), int((hh * CELL) * self.s)), pygame.SRCALPHA)
                tint.fill((0, 120, 0, 70) if good else (140, 0, 0, 70))
                surf.blit(tint, self.P(ox + GRID_X + gx * CELL, GRID_Y + (gy - page * 4) * CELL))
        self.region(ox + GRID_X, GRID_Y, 10 * CELL, 4 * CELL, "grid")
        if p.INV_H > 4:
            self._inv_page_tabs(surf, ox, page)
        self.text(surf, self.f16, str(p.gold), WHITE, ox + GOLD_BOX[0] + 4, GOLD_BOX[1] + 2)
        self._close_button(surf, INV_CLOSE, ox, "inv")

    def _held_anchor(self, cell, item):
        """Top-left grid cell for the held item so that it is centred on the mouse (D2 behaviour)."""
        p = self.world.player
        w, h = p._size(item)
        mx, my = self.mouse
        ox = self.lw - 320
        fx = (mx - ox - GRID_X) / CELL - w / 2.0
        fy = (my - GRID_Y) / CELL - h / 2.0
        gx = int(round(fx))
        gy = int(round(fy))
        page = self._inv_page()
        return max(0, min(10 - w, gx)), max(0, min(4 - h, gy)) + 4 * page

    # the I / II tabs above the weapon and shield slots (D2's art shows set I as the active one)
    WEAPON_TABS = [(17, 24, 30, 19), (51, 24, 30, 19), (247, 24, 31, 19), (282, 24, 31, 19)]

    def _weapon_tabs(self, surf, p, ox):
        cur = getattr(p, "weapon_set", 0)
        mx, my = self.mouse
        for i, (x, y, w, h) in enumerate(self.WEAPON_TABS):
            tab = i % 2
            if cur == 1:
                patch = pygame.Surface((int(w * self.s), int(h * self.s)), pygame.SRCALPHA)
                if tab == 0:
                    patch.fill((0, 0, 0, 120))
                    surf.blit(patch, self.P(ox + x, y))
                else:
                    patch.fill((70, 64, 50, 0))
                    surf.blit(patch, self.P(ox + x, y), special_flags=pygame.BLEND_RGB_ADD)
            if tab != cur:
                self.region(ox + x, y, w, h, "weapon_swap")
            if pygame.Rect(int(ox + x), int(y), w, h).collidepoint((int(mx), int(my))):
                other = p.swap_gear.get("weapon") if tab != cur else p.equipment.get("weapon")
                self.hover_lines = [("Weapon set %s%s" % ("I" * (tab + 1), " (in use)" if tab == cur else ""), WHITE),
                                    (other.shown_name if other is not None else "No weapon", GREY),
                                    ("W: swap weapons", GREY)]

    def _inv_page_tabs(self, surf, ox, page):
        """Bigger Inventory: the two backpack pages (I / II) beside the gold box."""
        b = self.frames.get("buysellbtn") or []
        mx, my = self.mouse
        for i in (0, 1):
            x, y = ox + 228 + i * 36, 385
            on = i == page
            if len(b) > 1:
                self.put(surf, b[1 if on else 0], x, y)
            else:
                pygame.draw.rect(surf, GOLD, self.R(x, y, 32, 32), 1)
            self.text(surf, self.f16, "I" * (i + 1), GOLD if on else WHITE, x, y + 9, "center", 32)
            self.region(x, y, 32, 32, "inv_page", i)
            if pygame.Rect(int(x), int(y), 32, 32).collidepoint((int(mx), int(my))):
                self.hover_lines = [("Backpack page %s" % ("I" * (i + 1)), WHITE)]

    def _draw_held(self, surf, it):
        p = self.world.player
        w, h = p._size(it)
        mx, my = self.mouse
        self._icon(surf, it, mx - w * CELL / 2.0, my - h * CELL / 2.0, w * CELL - 1, h * CELL - 1)

    def _socket_cost_lines(self, it):
        """While the blacksmith's socket service is open: what the next socket would cost."""
        w = self.world
        mode = getattr(w, "cursor_mode", None)
        if not mode or mode[0] != "socket" or getattr(it, "kind", "") != "equip" or not isinstance(it.base, dict):
            return []
        c = getattr(w, "content", None)
        cap = c.max_sockets(it.base, getattr(it, "ilvl", 1) or 1) if c is not None else it.base.get("maxsock", 0)
        have = getattr(it, "sockets", 0) or 0
        if cap <= 0:
            return [("", WHITE), ("Can't have sockets", RED)]
        if have >= cap:
            return [("", WHITE), ("Sockets: %d / %d (full)" % (have, cap), GREY)]
        cost = w.socket_cost(it)
        return [("", WHITE), ("Sockets: %d / %d" % (have, cap), WHITE),
                ("Add a socket: %d gold" % cost, GOLD if w.player.gold >= cost else RED)]

    def _draw_cursor(self, surf):
        if not self.cursor or not self.cursor[0]:
            return
        mx, my = self.mouse
        if getattr(self.world, "held", None) is None:
            mode = getattr(self.world, "cursor_mode", None)
            bs = getattr(self, "cursor_buysell", None)
            if mode and mode[0] == "identify" and bs and len(bs) > 8 and bs[8] is not None:
                self.put(surf, bs[8], mx, my)       # D2's identify cursor
                return
            if mode and mode[0] == "socket" and bs and len(bs) > 1 and bs[1] is not None:
                self.put(surf, bs[1], mx, my)       # D2's repair hammer
                return
            self.put(surf, self.cursor[0], mx, my)

    # ------------------------------------------------------------ skill tree
    def _draw_skill_tree(self, surf, p):
        """D2's skill tree: 320x432 panel on the right; tab column (frames 0-3) under the page
        (frames 4k..4k+3, page 1 = bottom tab); 48x48 icons on a 69x68 grid from (15, 15)."""
        ox = self.lw - 320
        book = p.skills
        if getattr(self, "_art_class", None) != getattr(p, "cls", "bar"):
            self.use_class(getattr(p, "cls", "bar"))
        t = self.text
        names = book.page_names()
        tb = self.tree_back
        real = bool(tb) and len(tb) >= 16
        if real:
            self._panel_bg(surf, ox, tb, 0)
            self._panel_bg(surf, ox, tb, 4 * self.skill_page)
        else:
            self._panel_bg(surf, ox, self.frames.get("blank") or self.frames["invchar6"], 0)
        # skill points left (the little box at the top of the tab column)
        t(surf, self.f16, str(book.points), WHITE if book.points else GREY, ox + 252, 62, "center", 50)
        t(surf, self.f10, "Skill Choices", GOLD, ox + 236, 28, "center", 80)
        t(surf, self.f10, "Remaining", GOLD, ox + 236, 42, "center", 80)
        # unlearn every skill (all points back)
        rbx, rby = ox + 12, 408
        hot = pygame.Rect(int(rbx), int(rby), 96, 18).collidepoint((int(self.mouse[0]), int(self.mouse[1])))
        bg = pygame.Surface((int(96 * self.s), int(18 * self.s)), pygame.SRCALPHA)
        bg.fill((40, 30, 20, 230) if not hot else (80, 60, 30, 240))
        surf.blit(bg, self.P(rbx, rby))
        pygame.draw.rect(surf, GOLD, self.R(rbx, rby, 96, 18), 1)
        t(surf, self.f10, "RESET SKILLS", GOLD if hot else WHITE, rbx, rby + 3, "center", 96)
        self.region(rbx, rby, 96, 18, "reset_skills")
        if hot:
            self.hover_lines = [("Reset skills", WHITE), ("Every point you spent goes back", GREY),
                                ("to Skill Choices Remaining", GREY)]
        tab_y = {3: 110, 2: 218, 1: 325}
        for page in (1, 2, 3):
            ty = tab_y[page]
            active = page == self.skill_page
            words = names.get(page, "").split()
            lines, line = [], ""
            for wd in words:
                trial = (line + " " + wd).strip()
                if self.f10.width(trial) > 76 and line:
                    lines.append(line)
                    line = wd
                else:
                    line = trial
            if line:
                lines.append(line)
            y0 = ty + 52 - 7 * len(lines)
            for li, ln in enumerate(lines):
                t(surf, self.f10, ln, WHITE if active else GREY, ox + 234, y0 + li * 14, "center", 82)
            self.region(ox + 232, ty, 86, 104, "skill_page", page)
        mx, my = self.mouse
        clvl = p.level
        for name, s in book.tree.items():
            if s.page != self.skill_page or name in getattr(book, "foreign", ()):
                continue
            x = ox + 15 + (s.col - 1) * 69
            y = 15 + (s.row - 1) * 68
            lv = book.levels.get(name, 0)
            can = book.can_learn(name, clvl)
            reachable = lv or (clvl >= s.reqlevel and all(book.levels.get(q, 0) for q in s.prereqs if q in book.tree))
            icons = self.skill_icons
            idx = s.icon if (lv or reachable) else s.icon + 1
            icon = icons[idx] if icons and idx < len(icons) and icons[idx] is not None else \
                (icons[s.icon] if icons and s.icon < len(icons) else None)
            if icon is not None:
                surf.blit(self.S(icon, self.s * 48.0 / icon.get_width()), self.P(x, y))
            else:
                box = pygame.Surface((int(48 * self.s), int(48 * self.s)), pygame.SRCALPHA)
                box.fill((30, 26, 20, 240))
                surf.blit(box, self.P(x, y))
                pygame.draw.rect(surf, GOLD if lv else (90, 80, 60), self.R(x, y, 48, 48), 1)
                for li, word in enumerate(s.title.split()[:3]):
                    t(surf, self.f10, word[:8], WHITE if lv else GREY, x, y + 4 + li * 13, "center", 48)
            if not lv and not reachable and (icons is None or s.icon + 1 >= len(icons)):
                dim = pygame.Surface((int(48 * self.s), int(48 * self.s)), pygame.SRCALPHA)
                dim.fill((0, 0, 0, 140))
                surf.blit(dim, self.P(x, y))
            if lv:
                t(surf, self.f16, str(book.level(name)), BLUE if book.level(name) > lv else WHITE, x + 49, y + 35,
                  "center", 16)
            self.region(x, y, 48, 48, "learn", name)
            if pygame.Rect(int(x), int(y), 48, 48).collidepoint((int(mx), int(my))):
                self.hover_lines = self.skill_tooltip(p, name, can)
        close = (12, 383, 32, 32) if self.skill_page == 2 else (168, 383, 32, 32)
        self._close_button(surf, close if real else (272, 390, 32, 32), ox, "skills")

    def skill_tooltip(self, p, name, can=False):
        """D2-style skill tooltip: name, description, current and next level, synergies."""
        book = p.skills
        s = book.tree[name]
        lv = book.levels.get(name, 0)
        clvl = p.level
        lines = [(s.title, GREEN)]
        if s.long:
            for chunk in _wrap(s.long[:1].upper() + s.long[1:], 46):
                lines.append((chunk, WHITE))
        if lv:
            lines.append(("Current Skill Level: %d" % book.level(name), WHITE))
            lines += [(x_, WHITE) for x_ in book.describe(name) if x_]
            if lv < s.maxlvl:
                lines.append(("Next Level", WHITE))
                lines += [(x_, BLUE) for x_ in book.describe_next(name) if x_]
        else:
            lines.append(("First Level", WHITE))
            lines += [(x_, WHITE) for x_ in book.describe_next(name) if x_]
        syn = book.synergy_lines(name)
        if syn:
            lines.append(("", WHITE))
            lines += [(x_, GREEN if i == 0 else WHITE) for i, x_ in enumerate(syn)]
        if s.kind != "passive":
            ap = book.ap_cost(name, p.attack_cost)
            lines.append(("Costs %d AP" % ap, GOLD))
        if not lv or can:
            lines.append(("Required Level: %d" % s.reqlevel, WHITE if clvl >= s.reqlevel else RED))
            for pre in s.prereqs:
                q = book.tree.get(pre)
                lines.append(("Requires " + (q.title if q else pre), WHITE if book.levels.get(pre) else RED))
        if can:
            lines.append(("Click to learn" if not lv else "Click to add a point", GOLD))
        elif lv and s.kind != "passive":
            lines.append(("Right click: use as right skill", GREY))
        return lines

    # ------------------------------------------------------------ loot window (V)
    def _draw_loot(self, surf, world):
        """Everything lying on the screen; click a line to pick it up."""
        rows = self.loot_list[:20]
        more = len(self.loot_list) - len(rows)
        p = world.player
        lh = 16
        w = 270
        x0 = self._loot_rect()[0]
        y0 = 104
        h = 34 + max(1, len(rows)) * lh + 22
        bg = pygame.Surface((int(w * self.s), int(h * self.s)), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 215))
        surf.blit(bg, self.P(x0, y0))
        gold = (199, 179, 119)
        pygame.draw.rect(surf, (110, 95, 60), pygame.Rect(self.P(x0, y0), (int(w * self.s), int(h * self.s))), 1)
        self.region(x0, y0, w, h, "loot_panel")
        self.text(surf, self.f16, "Items on screen", gold, x0, y0 + 6, "center", w)
        self.text(surf, self.f16, "x", (200, 80, 60), x0 + w - 16, y0 + 5)
        self.region(x0 + w - 20, y0 + 2, 18, 18, "loot_close")
        mx, my = self.mouse
        if not rows:
            self.text(surf, self.f16, "Nothing here", (150, 150, 150), x0, y0 + 30, "center", w)
        from game.grid import chebyshev
        for i, (cell, it) in enumerate(rows):
            y = y0 + 28 + i * lh
            name = "%d Gold" % it.amount if it.kind == "gold" else getattr(it, "shown_name", it.name)
            d = chebyshev(cell, p.pos)
            r = pygame.Rect(int(x0 + 4), int(y), int(w - 8), lh)
            if r.collidepoint((int(mx), int(my))):
                hl = pygame.Surface((int((w - 8) * self.s), int(lh * self.s)), pygame.SRCALPHA)
                hl.fill((90, 80, 50, 120))
                surf.blit(hl, self.P(x0 + 4, y))
                if it.kind != "gold" and hasattr(it, "describe_lines"):
                    self.hover_lines = it.describe_lines(p)
            self.text(surf, self.f16, name, it.color, x0 + 10, y + 1)
            self.text(surf, self.f16, "%d" % d, (150, 150, 150), x0 + w - 40, y + 1, "right", 30)
            self.region(x0 + 4, y, w - 8, lh, "loot_pick", (cell, it))
        hint = "Click to pick up (V closes)" if world.mode != "combat" else "Combat: only next to you, 1 AP"
        if more > 0:
            hint = "... %d more further away" % more
        self.text(surf, self.f16, hint, (150, 150, 150), x0, y0 + h - 18, "center", w)

    # ------------------------------------------------------------ automap
    def _draw_automap(self, surf, world):
        if not self.automap_mode:
            return
        am = self.minimaps.get(id(world))
        if am is None:
            from .automap import Automap
            am = self.minimaps[id(world)] = Automap(world)
        W, H = surf.get_size()
        if self.automap_mode == 1:
            am.draw_full(surf, (W / 2, H / 2 - 50 * self.s))
        else:
            am.draw_mini(surf, pygame.Rect(int(W - 240 * self.s), int(20 * self.s), int(230 * self.s), int(150 * self.s)))
        diff = getattr(getattr(self.assets, "content", None), "sfx", "")
        dname = {"": "Normal", "(n)": "Nightmare", "(h)": "Hell"}.get(diff, "Normal")
        self.text(surf, self.f16, world.level_name, GOLD, self.lw - 210, 6, "right", 200)
        self.text(surf, self.f16, dname, WHITE, self.lw - 210, 22, "right", 200)
