"""Asset providers.

Everything the renderer draws goes through an AssetProvider. Right now that is
PlaceholderAssets, which draws simple procedural art. The next step is a D2Assets
provider with the same methods, which reads real tiles and sprites from the MPQ
files of your Diablo 2 install. The rest of the game won't need to change.
"""
import math

import pygame

from .iso import TILE_W, TILE_H

WALL_H = 34   # world pixels


def shade(c, b):
    return (max(0, min(255, int(c[0] * b))), max(0, min(255, int(c[1] * b))), max(0, min(255, int(c[2] * b))))


def _hash(x, y, k=0):
    h = (x * 73856093) ^ (y * 19349663) ^ (k * 83492791)
    return (h & 0xFFFF) / 0xFFFF


def screen_dir(facing):
    fx, fy = facing
    sx, sy = fx - fy, (fx + fy) / 2
    n = math.hypot(sx, sy) or 1
    return sx / n, sy / n


# kind -> (body height, body width, colour override or None)
BODY = {
    "BA": (30, 12), "ZM": (27, 12), "FA": (17, 9), "FS": (18, 9), "SI": (9, 16),
}


class AssetProvider:
    name = "base"

    def draw_floor(self, surf, cell, pos, s, b, grid_lines=False): ...
    def draw_wall(self, surf, cell, pos, s, b, cutaway=False): ...
    def draw_unit(self, surf, unit, pose, pos, s, b): ...
    def draw_ground_item(self, surf, item, pos, s, b, t=10.0): ...
    def draw_item_icon(self, surf, item, rect): ...
    def draw_projectile(self, surf, kind, pos, s, t): ...


class PlaceholderAssets(AssetProvider):
    name = "placeholder"

    def __init__(self):
        self._shadow_cache = {}

    # ---------------------------------------------------------------- terrain
    def draw_floor(self, surf, cell, pos, s, b, grid_lines=False):
        x, y = cell
        cx, cy = pos
        hw, hh = TILE_W * s / 2, TILE_H * s / 2
        v = _hash(x, y)
        base = (58 + int(v * 14), 49 + int(v * 10), 40 + int(v * 8))
        pts = [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]
        pygame.draw.polygon(surf, shade(base, b), pts)
        # a couple of pebbles so the floor isn't flat colour
        for k in range(2):
            px = cx + (_hash(x, y, k + 1) - 0.5) * hw
            py = cy + (_hash(x, y, k + 7) - 0.5) * hh
            r = max(1, int(s * (1 + _hash(x, y, k + 3))))
            pygame.draw.circle(surf, shade((40, 34, 28), b), (int(px), int(py)), r)
        if grid_lines:
            pygame.draw.lines(surf, shade((90, 80, 66), b), True, pts, 1)

    def draw_wall(self, surf, cell, pos, s, b, cutaway=False):
        x, y = cell
        cx, cy = pos
        hw, hh = TILE_W * s / 2, TILE_H * s / 2
        H = (5 if cutaway else WALL_H + int(_hash(x, y, 5) * 10)) * s
        j = lambda k: (_hash(x, y, k) - 0.5) * 4 * s   # rocky jitter
        top = [(cx + j(1), cy - hh - H + j(2)), (cx + hw, cy - H + j(3)),
               (cx + j(4), cy + hh - H), (cx - hw, cy - H + j(6))]
        left = [(cx - hw, cy), (cx, cy + hh), top[2], top[3]]
        right = [(cx, cy + hh), (cx + hw, cy), top[1], top[2]]
        pygame.draw.polygon(surf, shade((50, 43, 36), b), left)
        pygame.draw.polygon(surf, shade((66, 57, 47), b), right)
        pygame.draw.polygon(surf, shade((84, 74, 62) if not cutaway else (70, 62, 52), b), top)

    # ---------------------------------------------------------------- units
    def _shadow(self, s, w):
        key = (round(s, 2), w)
        if key not in self._shadow_cache:
            sw, sh = int(w * 1.6 * s), int(w * 0.7 * s)
            sh_surf = pygame.Surface((max(2, sw), max(2, sh)), pygame.SRCALPHA)
            pygame.draw.ellipse(sh_surf, (0, 0, 0, 110), (0, 0, max(2, sw), max(2, sh)))
            self._shadow_cache[key] = sh_surf
        return self._shadow_cache[key]

    def draw_unit(self, surf, unit, pose, pos, s, b):
        cx, cy = pos
        bh, bw = BODY.get(unit.token, (24, 11))
        if unit.unique:
            bh, bw = int(bh * 1.3), int(bw * 1.3)
        color = unit.color
        mode = pose["mode"]
        phase = pose.get("phase", 0.0)
        dx, dy = screen_dir(pose.get("facing", unit.facing))

        if mode in ("DD", "DT"):   # dying / dead corpse
            k = 1.0 if mode == "DT" else min(1.0, phase)
            pool = (90, 10, 10) if unit.token != "SI" else (70, 30, 20)
            pr = pygame.Rect(0, 0, int(bw * 2.2 * s * k) + 2, int(bw * 0.9 * s * k) + 2)
            pr.center = (int(cx), int(cy))
            pygame.draw.ellipse(surf, shade(pool, b * 0.8), pr)
            body = pygame.Rect(0, 0, int(bh * 0.9 * s), int(bw * 0.6 * s))
            body.center = (int(cx), int(cy - (1 - k) * bh * s * 0.5))
            pygame.draw.ellipse(surf, shade(color, b * 0.45), body)
            return

        sh = self._shadow(s, bw)
        surf.blit(sh, (cx - sh.get_width() / 2, cy - sh.get_height() / 2))

        ox = oy = 0.0
        if mode == "WL":
            oy = -abs(math.sin(phase * math.pi * 2)) * 2.5 * s
        elif mode in ("A1", "SC"):
            lunge = math.sin(min(1.0, phase) * math.pi) * 6 * s
            ox, oy = dx * lunge, dy * lunge
        elif mode == "GH":
            ox = math.sin(phase * 40) * 1.5 * s
        cx += ox
        cy += oy

        c = color
        if pose.get("flash", 0) > 0:
            f = pose["flash"]
            c = tuple(int(c[i] + (255 - c[i]) * f) for i in range(3))
        body_c = shade(c, b)
        dark_c = shade(c, b * 0.6)

        if unit.unique:
            glow = pygame.Surface((int(bw * 4 * s), int(bw * 2 * s)), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (255, 220, 120, 60), glow.get_rect())
            surf.blit(glow, (cx - glow.get_width() / 2, cy - glow.get_height() / 2))

        if unit.token == "SI":   # quill rat: low spiky body
            r = pygame.Rect(0, 0, int(bw * s), int(bh * s))
            r.midbottom = (int(cx), int(cy + 2 * s))
            for k in range(7):
                a = math.pi + k * math.pi / 6
                sx0, sy0 = r.centerx + math.cos(a) * bw * 0.35 * s, r.centery + math.sin(a) * bh * 0.4 * s
                pygame.draw.line(surf, shade((220, 210, 180), b), (sx0, sy0),
                                 (sx0 + math.cos(a) * 5 * s, sy0 + math.sin(a) * 5 * s), max(1, int(s)))
            pygame.draw.ellipse(surf, body_c, r)
            head = (int(r.centerx + dx * bw * 0.5 * s), int(r.centery + dy * bh * 0.3 * s))
            pygame.draw.circle(surf, dark_c, head, int(3 * s))
            return

        # humanoid: legs, tapered torso, head, weapon toward facing
        top_y = cy - bh * s
        legs_y = cy - bh * 0.35 * s
        step = math.sin(phase * math.pi * 2) * 2 * s if mode == "WL" else 0
        lw = max(1, int(2 * s))
        pygame.draw.line(surf, dark_c, (cx - bw * 0.2 * s, legs_y), (cx - bw * 0.25 * s + step, cy - s), lw)
        pygame.draw.line(surf, dark_c, (cx + bw * 0.2 * s, legs_y), (cx + bw * 0.25 * s - step, cy - s), lw)
        torso = [(cx - bw * 0.5 * s, top_y + bh * 0.25 * s), (cx + bw * 0.5 * s, top_y + bh * 0.25 * s),
                 (cx + bw * 0.32 * s, legs_y), (cx - bw * 0.32 * s, legs_y)]
        pygame.draw.polygon(surf, body_c, torso)
        head_r = max(2, int(bw * 0.3 * s))
        pygame.draw.circle(surf, shade((c[0] * 0.9 + 20, c[1] * 0.85 + 15, c[2] * 0.8 + 10), b),
                           (int(cx + dx * s), int(top_y + head_r * 0.6)), head_r)
        # weapon / staff
        sx0, sy0 = cx + dx * bw * 0.45 * s, top_y + bh * 0.35 * s
        swing = 0.0
        if mode in ("A1", "SC"):
            swing = math.sin(min(1.0, phase) * math.pi) * 1.2
        ang = math.atan2(dy, dx) - 0.9 + swing
        length = (10 if unit.token != "FS" else 14) * s
        wcol = (200, 200, 210) if unit.token in ("BA", "FA") else (120, 90, 60)
        if unit.token == "ZM":
            wcol = shade(c, 0.8)
            length = 7 * s
        ex, ey = sx0 + math.cos(ang) * length, sy0 + math.sin(ang) * length
        pygame.draw.line(surf, shade(wcol, b), (sx0, sy0), (ex, ey), max(1, int(1.5 * s)))
        if unit.token == "FS" and mode == "SC":   # shaman casting glow
            pygame.draw.circle(surf, (255, 150, 50), (int(ex), int(ey)), int(3 * s))

    # ---------------------------------------------------------------- items
    def _item_shape(self, surf, item, cx, cy, size, b):
        k = item.kind
        if k == "gold":
            for i, (ox, oy) in enumerate([(-0.3, 0.1), (0.25, 0.15), (0, -0.15)]):
                pygame.draw.circle(surf, shade((230, 190, 60), b), (int(cx + ox * size), int(cy + oy * size)), max(1, int(size * 0.22)))
            return
        if k == "potion":
            pygame.draw.circle(surf, shade((200, 30, 30), b), (int(cx), int(cy + size * 0.1)), max(2, int(size * 0.32)))
            pygame.draw.rect(surf, shade((180, 160, 140), b), (cx - size * 0.08, cy - size * 0.45, size * 0.16, size * 0.25))
            return
        slot = item.slot
        col = (90, 90, 230) if item.rarity == "magic" else (200, 200, 200)
        if slot == "weapon":
            pygame.draw.line(surf, shade((190, 190, 200), b), (cx - size * 0.4, cy + size * 0.4), (cx + size * 0.4, cy - size * 0.4), max(2, int(size * 0.12)))
            pygame.draw.line(surf, shade((120, 80, 40), b), (cx - size * 0.15, cy + size * 0.05), (cx - size * 0.05, cy + size * 0.15), max(2, int(size * 0.15)))
        elif slot in ("ring", "ring1", "ring2"):
            pygame.draw.circle(surf, shade((220, 200, 90), b), (int(cx), int(cy)), max(2, int(size * 0.25)), max(1, int(size * 0.08)))
        elif slot == "amulet":
            pygame.draw.circle(surf, shade((220, 200, 90), b), (int(cx), int(cy - size * 0.1)), max(2, int(size * 0.3)), 1)
            pygame.draw.circle(surf, shade((90, 160, 230), b), (int(cx), int(cy + size * 0.2)), max(2, int(size * 0.15)))
        else:
            r = pygame.Rect(0, 0, int(size * 0.7), int(size * 0.7))
            r.center = (int(cx), int(cy))
            pygame.draw.rect(surf, shade((120, 95, 60), b), r)
        if item.rarity == "magic":
            pygame.draw.circle(surf, shade(col, b), (int(cx + size * 0.35), int(cy - size * 0.35)), max(1, int(size * 0.1)))

    def draw_ground_item(self, surf, item, pos, s, b, t=10.0):
        self._item_shape(surf, item, pos[0], pos[1] - 3 * s, 10 * s, b)

    def draw_item_icon(self, surf, item, rect):
        self._item_shape(surf, item, rect.centerx, rect.centery, min(rect.w, rect.h) * 0.8, 1.0)

    def draw_projectile(self, surf, kind, pos, s, t):
        x, y = pos
        y -= 14 * s
        if kind == "fireball":
            pygame.draw.circle(surf, (255, 120, 30), (int(x), int(y)), int(4 * s))
            pygame.draw.circle(surf, (255, 230, 140), (int(x), int(y)), int(2 * s))
        else:
            pygame.draw.circle(surf, (230, 220, 190), (int(x), int(y)), max(1, int(1.5 * s)))
