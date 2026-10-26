"""HUD and panels, loosely styled after Diablo 2's bottom bar."""
import math

import pygame

from game.items import SLOTS

GOLD = (199, 179, 119)
PANEL_BG = (14, 12, 10, 235)
EDGE = (92, 78, 52)
TEXT = (220, 210, 190)
DIM = (140, 130, 115)

SLOT_NAMES = {"weapon": "Weapon", "shield": "Shield", "helm": "Helm", "armor": "Armor", "gloves": "Gloves",
              "belt": "Belt", "boots": "Boots", "amulet": "Amulet", "ring1": "Ring", "ring2": "Ring"}


def panel(surf, rect, title=None, fonts=None):
    bg = pygame.Surface(rect.size, pygame.SRCALPHA)
    bg.fill(PANEL_BG)
    surf.blit(bg, rect.topleft)
    pygame.draw.rect(surf, EDGE, rect, 2)
    if title and fonts:
        img = fonts["title"].render(title, True, GOLD)
        surf.blit(img, (rect.centerx - img.get_width() / 2, rect.y + 8))


def orb(surf, center, radius, frac, color, label, fonts):
    cx, cy = center
    pygame.draw.circle(surf, (20, 14, 12), center, radius + 4)
    pygame.draw.circle(surf, (8, 6, 6), center, radius)
    frac = max(0.0, min(1.0, frac))
    if frac > 0:
        top = cy + radius - 2 * radius * frac
        fill = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(fill, color + (255,), (radius, radius), radius)
        cut = int(top - (cy - radius))
        if cut > 0:
            pygame.draw.rect(fill, (0, 0, 0, 0), (0, 0, radius * 2, cut))
        surf.blit(fill, (cx - radius, cy - radius))
        hl = pygame.Surface((radius, radius // 2), pygame.SRCALPHA)
        pygame.draw.ellipse(hl, (255, 255, 255, 40), hl.get_rect())
        surf.blit(hl, (cx - radius * 0.7, cy - radius * 0.75))
    pygame.draw.circle(surf, EDGE, center, radius + 4, 3)
    img = fonts["small"].render(label, True, TEXT)
    surf.blit(img, (cx - img.get_width() / 2, cy + radius + 6))


def text_lines(surf, font, lines, x, y, colors=None, line_h=None):
    line_h = line_h or font.get_linesize()
    for i, line in enumerate(lines):
        col = colors[i] if colors else TEXT
        surf.blit(font.render(line, True, col), (x, y + i * line_h))


def tooltip(surf, fonts, lines, colors, pos):
    font = fonts["small"]
    w = max(font.size(l)[0] for l in lines) + 16
    h = len(lines) * font.get_linesize() + 10
    x = min(pos[0] + 18, surf.get_width() - w - 4)
    y = max(4, min(pos[1] - h - 8, surf.get_height() - h - 4))
    bg = pygame.Surface((w, h), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 215))
    surf.blit(bg, (x, y))
    pygame.draw.rect(surf, EDGE, (x, y, w, h), 1)
    for i, line in enumerate(lines):
        img = font.render(line, True, colors[i] if i < len(colors) else TEXT)
        surf.blit(img, (x + w / 2 - img.get_width() / 2, y + 5 + i * font.get_linesize()))


class Hud:
    BAR_H = 120

    def __init__(self, fonts, assets):
        self.fonts = fonts
        self.assets = assets
        self.show_inv = False
        self.show_char = False
        self.regions = []    # (rect, action, arg) for click handling
        self.hover_lines = None
        self._bar_top = 10 ** 6
        self.minimaps = {}
        self.show_automap = False

    def hit(self, pos):
        for rect, action, arg in reversed(self.regions):
            if rect.collidepoint(pos):
                return action, arg
        return None

    def over_ui(self, pos):
        return any(r.collidepoint(pos) for r, _, _ in self.regions) or pos[1] > self._bar_top

    def draw(self, surf, world, scene, mouse):
        self.regions = []
        self.hover_lines = None
        W, H = surf.get_size()
        self._bar_top = H - self.BAR_H
        p = world.player
        pv = scene.view(p)

        # bottom bar
        bar = pygame.Rect(0, H - self.BAR_H, W, self.BAR_H)
        bg = pygame.Surface(bar.size, pygame.SRCALPHA)
        bg.fill((16, 13, 10, 245))
        surf.blit(bg, bar.topleft)
        pygame.draw.line(surf, EDGE, bar.topleft, bar.topright, 2)

        r = 40
        orb(surf, (70, H - self.BAR_H + 52), r, pv.shown_hp / p.max_hp, (170, 20, 20),
            f"Life {max(0, pv.shown_hp)}/{p.max_hp}", self.fonts)
        orb(surf, (W - 70, H - self.BAR_H + 52), r, p.mana / max(1, p.max_mana), (30, 50, 190),
            f"Mana {p.mana}/{p.max_mana}", self.fonts)

        # XP bar
        prev = p.xp_threshold(p.level - 1)
        need = p.xp_to_next()
        frac = (p.xp - prev) / max(1, need - prev)
        xr = pygame.Rect(140, H - self.BAR_H + 8, W - 280, 6)
        pygame.draw.rect(surf, (30, 26, 20), xr)
        pygame.draw.rect(surf, (200, 180, 90), (xr.x, xr.y, xr.w * max(0, min(1, frac)), xr.h))

        # action points / mode
        cx = W // 2
        y = H - self.BAR_H + 14
        if world.mode == "combat":
            label = f"Round {world.round}   AP {p.ap}/{p.max_ap}"
            img = self.fonts["med"].render(label, True, GOLD if world.turn == "player" else DIM)
            surf.blit(img, (cx - img.get_width() / 2, y))
            pip_w = 18
            x0 = cx - p.max_ap * (pip_w + 4) / 2
            for i in range(p.max_ap):
                col = (90, 200, 90) if i < p.ap else (45, 45, 40)
                pygame.draw.rect(surf, col, (x0 + i * (pip_w + 4), y + 26, pip_w, 10))
        else:
            img = self.fonts["med"].render("Exploring", True, DIM)
            surf.blit(img, (cx - img.get_width() / 2, y))

        # belt
        bx = cx - 2 * 44 - 150
        for i in range(4):
            rect = pygame.Rect(bx + i * 44, H - 50, 38, 38)
            pygame.draw.rect(surf, (30, 26, 22), rect)
            pygame.draw.rect(surf, EDGE, rect, 1)
            if i < len(p.belt):
                self.assets.draw_item_icon(surf, p.belt[i], rect)
                if rect.collidepoint(mouse):
                    self._item_tip(p.belt[i], p)
            surf.blit(self.fonts["small"].render(str(i + 1), True, DIM), (rect.x + 3, rect.y + 1))
            self.regions.append((rect, "potion", i))

        # buttons
        bw = 118
        btns = [("End Turn [Space]", "end_turn"), ("Inventory [I]", "inv"), ("Character [C]", "char")]
        x = cx + 30
        for label, action in btns:
            rect = pygame.Rect(x, H - 48, bw, 34)
            active = action != "end_turn" or (world.mode == "combat" and world.turn == "player")
            hot = rect.collidepoint(mouse) and active
            pygame.draw.rect(surf, (60, 48, 30) if hot else (34, 28, 20), rect)
            pygame.draw.rect(surf, EDGE if active else (50, 44, 34), rect, 1)
            img = self.fonts["small"].render(label, True, TEXT if active else (90, 85, 75))
            surf.blit(img, (rect.centerx - img.get_width() / 2, rect.centery - img.get_height() / 2))
            if active:
                self.regions.append((rect, action, None))
            x += bw + 8
        if p.stat_points:
            img = self.fonts["small"].render(f"+{p.stat_points} stat points", True, (255, 230, 90))
            surf.blit(img, (140, H - self.BAR_H + 40))

        gold_img = self.fonts["small"].render(f"Gold: {p.gold}    Level {p.level}", True, GOLD)
        surf.blit(gold_img, (140, H - self.BAR_H + 20))

        self._draw_log(surf, scene)
        mm = self.minimaps.get(id(world))
        if mm is None:
            from .minimap import Minimap
            mm = self.minimaps[id(world)] = Minimap(world)
        if self.show_automap:
            mm.draw_overlay(surf)
        elif not self.show_inv:
            box = pygame.Rect(W - 236, 8, 228, 150)
            mm.draw_corner(surf, box)
            name = self.fonts["small"].render(world.level_name, True, GOLD)
            surf.blit(name, (box.right - name.get_width() - 6, box.bottom + 2))
        if self.show_inv:
            self._draw_inventory(surf, world, mouse)
        if self.show_char:
            self._draw_character(surf, world, mouse)
        if scene.banner:
            text, col, t = scene.banner
            img = self.fonts["big"].render(text, True, col)
            img.set_alpha(int(255 * min(1.0, t * 2)))
            surf.blit(img, (W / 2 - img.get_width() / 2, 40))
        if self.hover_lines:
            lines, cols = self.hover_lines
            tooltip(surf, self.fonts, lines, cols, mouse)

    def _draw_log(self, surf, scene):
        font = self.fonts["small"]
        lines = [l for l in scene.log if l[2] < 9][-7:]
        y = 10
        for text, col, age in lines:
            img = font.render(text, True, col)
            if age > 7:
                img.set_alpha(int(255 * max(0.0, (9 - age) / 2)))
            shadow = font.render(text, True, (0, 0, 0))
            surf.blit(shadow, (13, y + 1))
            surf.blit(img, (12, y))
            y += font.get_linesize()

    def _item_tip(self, it, p, compare=None):
        lines = it.describe_lines(p) if hasattr(it, "describe_lines") else [(l, it.color) for l in it.describe()]
        if compare is not None:
            lines = lines + [("", TEXT), ("Currently equipped: " + compare.name, compare.color)]
        self.hover_lines = ([t for t, _ in lines], [c for _, c in lines])

    def _draw_inventory(self, surf, world, mouse):
        W, H = surf.get_size()
        p = world.player
        rect = pygame.Rect(W - 330, 36, 320, min(H - self.BAR_H - 44, 560))
        panel(surf, rect, "Inventory", self.fonts)
        self.regions.append((rect, "panel", None))
        font = self.fonts["small"]
        y = rect.y + 40
        surf.blit(font.render("Equipped  (click to take off)", True, DIM), (rect.x + 12, y))
        y += 20
        # equipment: two columns of boxes, icon + name
        bw, bh = 148, 42
        for i, slot in enumerate(SLOTS):
            col, row = i % 2, i // 2
            box = pygame.Rect(rect.x + 10 + col * (bw + 4), y + row * (bh + 4), bw, bh)
            it = p.equipment.get(slot)
            hot = box.collidepoint(mouse)
            pygame.draw.rect(surf, (42, 35, 26) if hot else (24, 20, 16), box)
            pygame.draw.rect(surf, EDGE if it else (52, 46, 36), box, 1)
            icon = pygame.Rect(box.x + 2, box.y + 2, bh - 4, bh - 4)
            if it:
                self.assets.draw_item_icon(surf, it, icon)
                name = it.name
                while font.size(name)[0] > bw - bh - 6 and len(name) > 4:
                    name = name[:-4] + "..."
                ok = it.mod_list is None or it.requirements_ok(p)
                surf.blit(font.render(name, True, it.color if ok else (255, 80, 80)), (box.x + bh, box.y + 4))
                surf.blit(font.render(SLOT_NAMES[slot], True, DIM), (box.x + bh, box.y + 22))
                self.regions.append((box, "unequip", slot))
                if hot:
                    self._item_tip(it, p)
            else:
                surf.blit(font.render(SLOT_NAMES[slot], True, (90, 84, 70)), (box.x + bh, box.y + 13))
        y += 5 * (bh + 4) + 8
        surf.blit(font.render("Backpack %d/20  (left: equip / drink, right: drop)" % len(p.inventory), True, DIM),
                  (rect.x + 12, y))
        y += 20
        cell = 58
        for i in range(20):
            col, row = i % 5, i // 5
            box = pygame.Rect(rect.x + 12 + col * (cell + 2), y + row * (cell + 2), cell, cell)
            if box.bottom > rect.bottom - 2:
                break
            hot = box.collidepoint(mouse)
            pygame.draw.rect(surf, (40, 34, 26) if hot else (18, 16, 13), box)
            pygame.draw.rect(surf, (60, 52, 40), box, 1)
            if i < len(p.inventory):
                it = p.inventory[i]
                if it.rarity == "magic":
                    pygame.draw.rect(surf, (24, 24, 60), box.inflate(-2, -2))
                self.assets.draw_item_icon(surf, it, box.inflate(-6, -6))
                if it.mod_list is not None and not it.requirements_ok(p):
                    tint = pygame.Surface(box.size, pygame.SRCALPHA)
                    tint.fill((160, 0, 0, 60))
                    surf.blit(tint, box.topleft)
                self.regions.append((box, "item", i))
                if hot:
                    cur = p.equipment.get("ring1" if it.slot == "ring" else it.slot) if it.slot else None
                    self._item_tip(it, p, cur)

    def _draw_character(self, surf, world, mouse):
        p = world.player
        rect = pygame.Rect(10, 40, 300, 420)
        panel(surf, rect, "Barbarian", self.fonts)
        self.regions.append((rect, "panel", None))
        font = self.fonts["small"]
        y = rect.y + 44
        lines = [f"Level {p.level}", f"Experience {p.xp} / {p.xp_to_next()}", ""]
        text_lines(surf, font, lines, rect.x + 14, y)
        y += len(lines) * font.get_linesize() + 4
        for key, label, val in [("str", "Strength", p.strength), ("dex", "Dexterity", p.dexterity),
                                ("vit", "Vitality", p.vitality), ("eng", "Energy", p.base_eng)]:
            surf.blit(font.render(f"{label}", True, TEXT), (rect.x + 14, y))
            surf.blit(font.render(str(val), True, GOLD), (rect.x + 130, y))
            if p.stat_points:
                b = pygame.Rect(rect.x + 170, y - 2, 22, 20)
                pygame.draw.rect(surf, (70, 56, 30) if b.collidepoint(mouse) else (40, 32, 20), b)
                pygame.draw.rect(surf, EDGE, b, 1)
                surf.blit(font.render("+", True, (255, 230, 90)), (b.x + 6, b.y + 1))
                self.regions.append((b, "stat", key))
            y += 26
        if p.stat_points:
            surf.blit(font.render(f"Points left: {p.stat_points}", True, (255, 230, 90)), (rect.x + 14, y))
        y += 30
        res = getattr(p, "res", {})
        info = [f"Damage {p.dmg[0]}-{p.dmg[1]}  ({p.attack_cost} AP per swing)",
                f"Attack Rating {p.ar}", f"Defense {p.defense}   Block {getattr(p, 'block_chance', 0)}%",
                "Resist  F %d  C %d  L %d  P %d" % tuple(res.get(k, 0) for k in ("fire", "cold", "ltng", "pois")),
                f"Life {p.hp}/{p.max_hp}",
                f"Action Points {p.max_ap}", "Bash: right click, +50% dmg,", "  knockback, 2 mana, +1 AP"]
        text_lines(surf, font, info, rect.x + 14, y)
