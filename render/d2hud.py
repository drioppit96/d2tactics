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
        self.ind = assets.indexed_surface
        self.frames = {}
        for n in ("800ctrlpnl7", "hlthmana", "overlap", "invchar6", "minipanel", "minipanelbtn", "level",
                  "runbutton", "mediumbuttonblank", "blank", "buysellbtn", "skillpoints"):
            self.frames[n] = self._load(PANEL + n + ".dc6", required=n in ("800ctrlpnl7", "hlthmana", "invchar6"))
        self.cursor = self._load("data\\global\\ui\\CURSOR\\ohand.dc6")
        self.skill_icons = self._load(SPELLS + "BaSkillicon.DC6")
        self.generic_icons = self._load(SPELLS + "Skillicon.DC6")
        self.tree_back = self._load(SPELLS + "skltree_b_back.DC6")
        self.f16 = D2Font(src, "font16")
        self.f10 = D2Font(src, "fontformal10")
        self.f30 = D2Font(src, "font30")
        self.show_inv = False
        self.show_char = False
        self.show_skills = False
        self.show_automap = False
        self.automap_mode = 0           # 0 off, 1 full, 2 mini
        self.show_minipanel = True
        self.skill_popup = False
        self.minimaps = {}
        self.regions = []
        self.hover_lines = None
        self.skill_page = 1
        self.scaled = {}
        self.s = 1.0
        self.lw = 800

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
        if self.show_char:
            self._draw_char(surf, p)
        if self.show_inv:
            self._draw_inventory(surf, world)
        elif self.show_skills:
            self._draw_skill_tree(surf, p)
        self._draw_control_panel(surf, world, scene)
        if self.skill_popup:
            self._draw_skill_popup(surf, p)
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
        x0 = 330 if self.show_char else 8
        for text, col, age in lines:
            img = self.f16.render(text, col, self.ind)
            sc = self.S(img)
            if age > 7:
                sc.set_alpha(int(255 * max(0.0, (9 - age) / 2)))
            surf.blit(sc, self.P(x0, y))
            sc.set_alpha(None)
            y += 15

    # ------------------------------------------------------------ tooltip
    def tooltip(self, surf, lines, at):
        """lines: [(text, colour)] - drawn like D2's item description box."""
        if lines and isinstance(lines, tuple) and len(lines) == 2 and isinstance(lines[0], list):
            texts, cols = lines
            lines = list(zip(texts, cols + [WHITE] * (len(texts) - len(cols))))
        lh = 15
        w = max((self.f16.width(t) for t, _ in lines), default=10) + 14
        h = len(lines) * lh + 8
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
        self._globe(surf, 0, px0 + 30, py0 - 16, max(0, pv.shown_hp) / float(max(1, p.max_hp)))
        self._globe(surf, 1, px0 + 594, py0 - 16, p.mana / float(max(1, p.max_mana)))
        x = px0
        for i in range(6):
            img = cp[i]
            self.put(surf, img, x, py0 + 104 - img.get_height())
            x += img.get_width()
        ov = self.frames.get("overlap")
        if ov:
            self.put(surf, ov[0], px0 + 29, py0 - 17)
            self.put(surf, ov[1] if len(ov) > 1 else ov[0], px0 + 593, py0 - 17)
        self.region(px0, py0 + 49, 704, 55, "panel")
        self.region(px0, py0 - 16, 117, 120, "life")
        self.region(px0 + 587, py0 - 16, 117, 120, "mana")
        mx, my = self.mouse
        if pygame.Rect(int(px0 + 30), int(py0 - 16), 80, 80).collidepoint((int(mx), int(my))):
            self.hover_lines = [("Life: %d / %d" % (max(0, pv.shown_hp), p.max_hp), WHITE)]
        if pygame.Rect(int(px0 + 594), int(py0 - 16), 80, 80).collidepoint((int(mx), int(my))):
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
                       (12, None, "Quest Log"), (14, "menu", "Game Menu (Esc)")]
            for k, (fi, action, label) in enumerate(entries):
                bx = mpx + 4 + k * 21
                pressed = (action == "char" and self.show_char) or (action == "inv" and self.show_inv) or \
                          (action == "skills" and self.show_skills) or (action == "automap" and self.automap_mode)
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
                    self.hover_lines = [(name, GREEN), ("Level %d" % p.skills.level(name), WHITE)] + \
                        [(t, WHITE) for t in p.skills.describe(name)] + \
                        [("%d AP, %d mana" % (ap, mana), GREY), ("Click to change skill", GREY)]

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
                self.hover_lines = [("Attack" if name == "attack" else name, GREEN if name != "attack" else WHITE)]

    # ------------------------------------------------------------ panels
    def _panel_bg(self, surf, ox, frames, base=0):
        for i, (x, y) in zip(range(base, base + 4), [(0, 0), (256, 0), (0, 256), (256, 256)]):
            if i < len(frames) and frames[i] is not None:
                self.put(surf, frames[i], ox + x, y)
        self.region(ox, 0, 320, 432, "panel")

    def _draw_char(self, surf, p):
        self._panel_bg(surf, 0, self.frames["invchar6"], 0)
        t, f10, f16 = self.text, self.f10, self.f16
        t(surf, f16, "Barbarian", GOLD, 11, 12, "center", 171)
        t(surf, f16, "Barbarian", GOLD, 193, 12, "center", 117)
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
            if held is None and pygame.Rect(int(x), int(y), w * CELL, h * CELL).collidepoint((int(mx), int(my))):
                lines = it.describe_lines(p)
                cur = p.equipment.get("ring1" if it.slot == "ring" else it.slot) if it.slot else None
                if cur:
                    lines = lines + [("", WHITE), ("Equipped: " + cur.name, cur.color)]
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
        ox = self.lw - 320
        book = p.skills
        if self.tree_back:
            n = len(self.tree_back)
            base = 4 * (self.skill_page - 1) if n >= 12 else 0
            self._panel_bg(surf, ox, self.tree_back, base)
        else:
            self._panel_bg(surf, ox, self.frames.get("blank") or self.frames["invchar6"], 0)
        t = self.text
        t(surf, self.f16, "Skill Choices Remaining: %d" % book.points, GOLD if book.points else GREY, ox + 8, 14)
        # page tabs on the right (D2: three tree tabs)
        from game.skills import PAGE_NAMES
        for page in (1, 2, 3):
            ty = 70 + (page - 1) * 110
            active = page == self.skill_page
            bg = pygame.Surface((int(70 * self.s), int(96 * self.s)), pygame.SRCALPHA)
            bg.fill((40, 32, 20, 220) if active else (0, 0, 0, 150))
            if not self.tree_back:
                surf.blit(bg, self.P(ox + 244, ty))
            for li, word in enumerate(PAGE_NAMES[page].split()):
                t(surf, self.f10, word, GOLD if active else GREY, ox + 244, ty + 30 + li * 16, "center", 70)
            self.region(ox + 244, ty, 70, 96, "skill_page", page)
        mx, my = self.mouse
        clvl = p.level
        for name, s in book.tree.items():
            if s.page != self.skill_page:
                continue
            x = ox + SKILL_TREE_X + (s.col - 1) * SKILL_TREE_DX
            y = SKILL_TREE_Y + (s.row - 1) * SKILL_TREE_DY
            lv = book.levels.get(name, 0)
            can = book.can_learn(name, clvl)
            icon = self.skill_icons[s.icon] if self.skill_icons and s.icon < len(self.skill_icons) else None
            if icon is not None:
                surf.blit(self.S(icon, self.s * 48.0 / icon.get_width()), self.P(x, y))
            else:
                box = pygame.Surface((int(48 * self.s), int(48 * self.s)), pygame.SRCALPHA)
                box.fill((30, 26, 20, 240))
                surf.blit(box, self.P(x, y))
                pygame.draw.rect(surf, GOLD if lv else (90, 80, 60), self.R(x, y, 48, 48), 1)
                words = name.split()
                for li, word in enumerate(words[:3]):
                    t(surf, self.f10, word[:8], WHITE if lv else GREY, x, y + 4 + li * 13, "center", 48)
            if not lv and not can:
                dim = pygame.Surface((int(48 * self.s), int(48 * self.s)), pygame.SRCALPHA)
                dim.fill((0, 0, 0, 140))
                surf.blit(dim, self.P(x, y))
            if lv:
                t(surf, self.f16, str(lv), WHITE, x + 50, y + 34)
            self.region(x, y, 48, 48, "learn", name)
            if pygame.Rect(int(x), int(y), 48, 48).collidepoint((int(mx), int(my))):
                lines = [(name, GREEN)]
                if lv:
                    lines.append(("Current Skill Level: %d" % lv, WHITE))
                lines += [(x_, WHITE) for x_ in book.describe(name) if x_]
                if s.kind != "passive":
                    ap, mana = (self.world.skill_cost(name) if lv else (0, s.mana))
                    lines.append(("Mana Cost: %d" % mana, BLUE))
                if not lv or can:
                    lines.append(("Required Level: %d" % s.reqlevel, WHITE if clvl >= s.reqlevel else RED))
                    for pre in s.prereqs:
                        lines.append(("Requires " + pre, WHITE if book.levels.get(pre) else RED))
                if can:
                    lines.append(("Click to learn" if not lv else "Click to add a point", GOLD))
                elif lv and s.kind != "passive":
                    lines.append(("Right click: use as right skill", GREY))
                self.hover_lines = lines
        self._close_button(surf, (272, 390, 32, 32) if not self.tree_back else INV_CLOSE, ox, "skills")

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
