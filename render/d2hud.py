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
                  "gemsocket", "supertransmogrifier", "miniconvert"):
            self.frames[n] = self._load(PANEL + n + ".dc6", required=n in ("800ctrlpnl7", "hlthmana", "invchar6"))
        self.cursor = self._load("data\\global\\ui\\CURSOR\\ohand.dc6")
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
        out = self.scaled.get(key)
        if out is None:
            w, h = img.get_size()
            out = pygame.transform.smoothscale(img, (max(1, int(round(w * k))), max(1, int(round(h * k)))))
            if len(self.scaled) > 2500:
                self.scaled.clear()
            self.scaled[key] = out
        return out

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
            return cx, cy
        return None

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
                # monster info sits to the left of the monster, so it never covers it
                a = pygame.Rect(int(anchor.x / self.s), int(anchor.y / self.s),
                                int(anchor.w / self.s), int(anchor.h / self.s))
                self.tooltip(surf, list(zip(texts, list(cols) + [WHITE] * len(texts))), self.mouse, left_of=a)
            else:
                self.tooltip(surf, list(zip(texts, list(cols) + [WHITE] * len(texts))), self.mouse)
        if self.hover_lines:
            self.tooltip(surf, self.hover_lines, self.mouse)
        held = getattr(world, "held", None)
        if held is not None:
            self._draw_held(surf, held)
        self._draw_cursor(surf)

    # ------------------------------------------------------------ message log
    def _draw_log(self, surf, scene):
        lines = [l for l in scene.log if l[2] < 9][-6:]
        y = 6
        x0 = 330 if (self.show_char or self.show_quests or getattr(self, "show_cube", False)) else 8
        for text, col, age in lines:
            img = self.f16.render(text, col, self.ind)
            sc = self.S(img)
            if age > 7:
                sc.set_alpha(int(255 * max(0.0, (9 - age) / 2)))
            surf.blit(sc, self.P(x0, y))
            sc.set_alpha(None)
            y += 15

    # ------------------------------------------------------------ tooltip
    def tooltip(self, surf, lines, at, left_of=None):
        """lines: [(text, colour)] - drawn like D2's item description box."""
        if lines and isinstance(lines, tuple) and len(lines) == 2 and isinstance(lines[0], list):
            texts, cols = lines
            lines = list(zip(texts, cols + [WHITE] * (len(texts) - len(cols))))
        lh = 15
        w = max((self.f16.width(t) for t, _ in lines), default=10) + 14
        h = len(lines) * lh + 8
        if left_of is not None:
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
        self._skill_box(surf, px0 + 153, py0 + 65, None, "left")
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

    def _globe(self, surf, idx, x, y, frac):
        g = self.frames["hlthmana"][idx]
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
            label = "ATK" if name in (None, "attack") else "".join(w[0] for w in name.split())[:3].upper()
            self.text(surf, self.f16, label, GOLD, x, y + 11, "center", 36)
        self.region(x, y, 36, 36, "skill_" + side)
        mx, my = self.mouse
        if pygame.Rect(int(x), int(y), 36, 36).collidepoint((int(mx), int(my))):
            if side == "left":
                self.hover_lines = [("Attack", WHITE), ("Left click a monster", GREY)]
            else:
                if name in (None, "attack"):
                    self.hover_lines = [("Right click: Attack", WHITE), ("Click here to choose a skill", GREY)]
                else:
                    ap, mana = self.world.skill_cost(name)
                    sk = p.skills.tree.get(name)
                    title = sk.title if sk is not None else name
                    self.hover_lines = [(title, GREEN), ("Level %d" % p.skills.level(name), WHITE)] + \
                        [(t, WHITE) for t in p.skills.describe(name)] + \
                        [("%d AP, %s mana" % (ap, _num(mana)), GREY), ("Click to change skill", GREY)]

    def _draw_skill_popup(self, surf, p):
        """Choose the right-click skill: learned active skills in a row above the button."""
        px0, py0 = self.panel_origin
        options = ["attack"] + [n for n in p.skills.actives()]
        per_row = 8
        for i, name in enumerate(options):
            row, col = divmod(i, per_row)
            x = px0 + 704 - 40 - col * 40
            y = py0 + 20 - row * 40
            bg = pygame.Surface((int(38 * self.s), int(38 * self.s)), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 200))
            surf.blit(bg, self.P(x - 1, y - 1))
            icon = self._skill_icon(name)
            if icon is not None:
                surf.blit(self.S(icon, self.s * 36.0 / icon.get_width()), self.P(x, y))
            else:
                lab = "ATK" if name == "attack" else "".join(w[0] for w in name.split())[:3].upper()
                self.text(surf, self.f16, lab, GOLD, x, y + 11, "center", 36)
            if name == (p.right_skill or "attack"):
                pygame.draw.rect(surf, GOLD, self.R(x - 1, y - 1, 38, 38), 1)
            self.region(x, y, 36, 36, "pick_skill", name)
            mx, my = self.mouse
            if pygame.Rect(int(x), int(y), 36, 36).collidepoint((int(mx), int(my))):
                sk = p.skills.tree.get(name)
                self.hover_lines = [("Attack" if name == "attack" else (sk.title if sk else name), GREEN if name != "attack" else WHITE)]

    # ------------------------------------------------------------ panels
    def _panel_bg(self, surf, ox, frames, base=0):
        for i, (x, y) in zip(range(base, base + 4), [(0, 0), (256, 0), (0, 256), (256, 256)]):
            if i < len(frames) and frames[i] is not None:
                self.put(surf, frames[i], ox + x, y)
        self.region(ox, 0, 320, 432, "panel")

    def _draw_char(self, surf, p):
        self._panel_bg(surf, 0, self.frames["invchar6"], 0)
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
            t(surf, f16, str(cur), WHITE, 231, y + 1, "center", 39)
            t(surf, f16, str(mx_), WHITE, 271, y + 1, "center", 39)
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

    def _draw_quests(self, surf, p):
        from game.quests import journal
        from game.acts import act_of
        self._panel_bg(surf, 0, self.frames.get("blank") or self.frames["invchar6"], 0)
        self.text(surf, self.f30, "Quests", GOLD, 0, 14, "center", 320)
        # D2's act tabs: every act you have reached
        here = act_of(self.world.level_id) if getattr(self, "world", None) and self.world.level_id else 1
        top = max([here, int(getattr(p, "current_act", 1) or 1)] + [act_of(l) for l in getattr(p, "visited", ()) if l])
        acts = list(range(1, min(5, top) + 1))
        if getattr(self, "q_act", None) not in acts:
            self.q_act = here if here in acts else acts[-1]
        tw = 280 // max(1, len(acts))
        for i, a in enumerate(acts):
            x = 20 + i * tw
            on = a == self.q_act
            box = pygame.Surface((int((tw - 4) * self.s), int(20 * self.s)), pygame.SRCALPHA)
            box.fill((70, 58, 30, 220) if on else (0, 0, 0, 140))
            surf.blit(box, self.P(x, 44))
            self.text(surf, self.f10, "Act " + "I II III IV V".split()[a - 1], WHITE if on else (150, 140, 120),
                      x, 48, "center", tw - 4)
            self.region(x, 44, tw - 4, 20, "q_tab", a)
        y = 74
        for title, status, text in journal(p, self.q_act):
            col = {"done": GREY, "active": WHITE, "cleared": YELLOW}.get(status, (110, 105, 95))
            self.text(surf, self.f16, title, GOLD if status != "none" else (120, 110, 90), 20, y)
            y += 17
            if status in ("done", "none"):
                text = "Completed." if status == "done" else "Not started."
            # wrap the journal line into the panel width
            words, line = text.split(), ""
            for wd in words:
                trial = (line + " " + wd).strip()
                if self.f10.width(trial) > 280:
                    self.text(surf, self.f10, line, col, 26, y)
                    y += 13
                    line = wd
                else:
                    line = trial
            if line:
                self.text(surf, self.f10, line, col, 26, y)
                y += 13
            y += 8
        self._close_button(surf, CHAR_CLOSE, 0, "quests")

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
        self.text(surf, self.f10, "Right click your items to sell", GREY, 20, 392)
        self._close_button(surf, (271, 383, 32, 32), 0, "store_close")

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
        """D2's waypoint list: every activated waypoint of the act; click one to travel."""
        from game.acts import WAYPOINTS, act_of
        p = world.player
        info = getattr(world, "info", None)
        self._panel_bg(surf, 0, self.frames.get("blank") or self.frames["invchar6"], 0)
        self.text(surf, self.f30, "Waypoints", GOLD, 0, 14, "center", 320)
        here = world.level_id
        mx, my = self.mouse
        got = getattr(p, "waypoints", {1})
        # D2's act tabs: every act you have a waypoint in
        acts = [a for a in sorted(WAYPOINTS) if any(l in got for l in WAYPOINTS[a])] or [1]
        if getattr(self, "wp_act", None) not in acts:
            cur = act_of(here) if here else 1
            self.wp_act = cur if cur in acts else acts[-1]
        tw = 280 // max(1, len(acts))
        for i, a in enumerate(acts):
            x = 20 + i * tw
            on = a == self.wp_act
            box = pygame.Surface((int((tw - 4) * self.s), int(20 * self.s)), pygame.SRCALPHA)
            box.fill((70, 58, 30, 220) if on else (0, 0, 0, 140))
            surf.blit(box, self.P(x, 44))
            self.text(surf, self.f10, "Act " + "I II III IV V".split()[a - 1], WHITE if on else (150, 140, 120),
                      x, 48, "center", tw - 4)
            self.region(x, 44, tw - 4, 20, "wp_tab", a)
        for i, lid in enumerate(WAYPOINTS[self.wp_act]):
            y = 76 + i * 32
            name = info.name(lid) if info else str(lid)
            on = lid in got
            hot = on and pygame.Rect(20, y - 4, 280, 28).collidepoint((int(mx), int(my)))
            box = pygame.Surface((int(280 * self.s), int(26 * self.s)), pygame.SRCALPHA)
            box.fill((60, 50, 30, 200) if hot else (0, 0, 0, 120))
            surf.blit(box, self.P(20, y - 4))
            col = (GOLD if lid == here else WHITE) if on else (90, 85, 75)
            self.text(surf, self.f16, name, col, 30, y)
            if on and lid != here:
                self.region(20, y - 4, 280, 28, "waypoint", lid)
        self._close_button(surf, CHAR_CLOSE, 0, "waypoints")

    # ------------------------------------------------------------ the Horadric Cube
    CUBE_GRID = (117, 138)
    CUBE_BUTTON = (145, 259, 32, 32)
    CUBE_CLOSE = (275, 384, 32, 32)

    def cube_cell_at(self, pos):
        if not getattr(self, "show_cube", False):
            return None
        lx, ly = self.logical(pos)
        gx, gy = self.CUBE_GRID
        cx, cy = int((lx - gx) // CELL), int((ly - gy) // CELL)
        from game.cube import W, H
        if 0 <= cx < W and 0 <= cy < H:
            return cx, cy
        return None

    def cube_anchor(self, item):
        from game.cube import W, H
        w, h = max(1, item.invw or 1), max(1, item.invh or 1)
        mx, my = self.mouse
        gx, gy = self.CUBE_GRID
        fx = int(round((mx - gx) / CELL - w / 2.0))
        fy = int(round((my - gy) / CELL - h / 2.0))
        return max(0, min(W - w, fx)), max(0, min(H - h, fy))

    def _draw_cube(self, surf, world):
        from game import cube as cb
        p = world.player
        box = self.cube_item
        fr = self.frames.get("supertransmogrifier") or self.frames.get("blank") or self.frames["invchar6"]
        self._panel_bg(surf, 0, fr, 0)
        self.text(surf, self.f16, "Horadric Cube", GOLD, 0, 104, "center", 320)
        gx, gy = self.CUBE_GRID
        mx, my = self.mouse
        held = getattr(world, "held", None)
        self.region(gx, gy, cb.W * CELL, cb.H * CELL, "cube_grid")
        for it in getattr(box, "contents", []) or []:
            if getattr(it, "cube_pos", None) is None:
                continue
            cx, cy = it.cube_pos
            w, h = max(1, it.invw or 1), max(1, it.invh or 1)
            x, y = gx + cx * CELL, gy + cy * CELL
            tint = pygame.Surface((int((w * CELL - 1) * self.s), int((h * CELL - 1) * self.s)), pygame.SRCALPHA)
            tint.fill((10, 10, 40, 120))
            surf.blit(tint, self.P(x + 1, y + 1))
            self._icon(surf, it, x + 1, y + 1, w * CELL - 1, h * CELL - 1)
            if held is None and pygame.Rect(int(x), int(y), w * CELL, h * CELL).collidepoint((int(mx), int(my))):
                self.hover_lines = list(it.describe_lines(p))
        if held is not None and self.cube_cell_at((mx * self.s, my * self.s)) is not None:
            ax, ay = self.cube_anchor(held)
            ok, over = cb.fits(box, held, ax, ay)
            good = ok and len(over) <= 1 and held.code != "box"
            w, h = max(1, held.invw or 1), max(1, held.invh or 1)
            tint = pygame.Surface((int(w * CELL * self.s), int(h * CELL * self.s)), pygame.SRCALPHA)
            tint.fill((0, 120, 0, 70) if good else (140, 0, 0, 70))
            surf.blit(tint, self.P(gx + ax * CELL, gy + ay * CELL))
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
                    self.hover_lines = it.describe_lines(p)
                    self._draw_sockets(surf, it, ox + x, y, w, h)
                elif hot and held is not None and getattr(held, "gem", None) and getattr(it, "sockets", 0):
                    self._draw_sockets(surf, it, ox + x, y, w, h)
            self.region(ox + x, y, w, h, "slot", slot)
        # backpack grid
        for it in p.inventory:
            if getattr(it, "inv_pos", None) is None:
                continue
            cx, cy = it.inv_pos
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
                    lines.append(("Sell value: %d (right click)" % sell_price(it), GOLD))
                self.hover_lines = lines
        if held is not None:
            cell = self.grid_cell_at((mx * self.s, my * self.s))
            if cell:
                hw, hh = p._size(held)
                gx, gy = self._held_anchor(cell, held)
                ok, over = p.inv_fits(held, gx, gy)
                good = ok and len(over) <= 1
                tint = pygame.Surface((int((hw * CELL) * self.s), int((hh * CELL) * self.s)), pygame.SRCALPHA)
                tint.fill((0, 120, 0, 70) if good else (140, 0, 0, 70))
                surf.blit(tint, self.P(ox + GRID_X + gx * CELL, GRID_Y + gy * CELL))
        self.region(ox + GRID_X, GRID_Y, 10 * CELL, 4 * CELL, "grid")
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
        return max(0, min(10 - w, gx)), max(0, min(4 - h, gy))

    def _draw_held(self, surf, it):
        p = self.world.player
        w, h = p._size(it)
        mx, my = self.mouse
        self._icon(surf, it, mx - w * CELL / 2.0, my - h * CELL / 2.0, w * CELL - 1, h * CELL - 1)

    def _draw_cursor(self, surf):
        if not self.cursor or not self.cursor[0]:
            return
        mx, my = self.mouse
        if getattr(self.world, "held", None) is None:
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
            if s.page != self.skill_page:
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
        x0 = 330 if (self.show_char or self.show_quests or self.store is not None) else 8
        if x0 + w > self.lw - (320 if (self.show_inv or self.show_skills) else 0):
            x0 = 8
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
