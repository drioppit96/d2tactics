"""The manager screen's look: Diablo II's own fonts, stone panels and buttons, from your install.

Everything is drawn on one 800 x 600 canvas (D2's own resolution) and scaled to the window, like
the D2 Tactics front-end screens. The art is read at runtime from the player's MPQs, by the same
loaders the game uses:

    fonts       font16, font30, fontformal10 (render/d2hud.py D2Font)
    panels      the quest panel's carved stone, tiled to any size (D2Hud._panel_frame)
    buttons     FrontEnd\\widebuttonblank.dc6 and mediumbuttonblank.dc6 (the character select
                screen's), frame 0 up and frame 1 pressed
    items       the inventory graphic and D2's description box (D2Hud._icon, D2Hud.tooltip)

Without Diablo II files (placeholder art) the same layout is drawn with plain dark boxes and a
system font.
"""
import pygame

GOLD = (199, 179, 119)
WHITE = (255, 255, 255)
GREY = (140, 140, 140)
DARK = (90, 86, 78)
RED = (220, 70, 50)
GREEN = (24, 255, 0)
BLUE = (105, 105, 255)
FE = "data\\global\\ui\\FrontEnd\\"
W, H = 800, 600


class Look:
    def __init__(self, assets, fallback_fonts):
        self.assets = assets
        self.hud = None
        self.bg = None
        self.wide = None
        self.medium = None
        self.fb = fallback_fonts
        self._cache = {}
        src = getattr(assets, "src", None)
        if src is not None:
            try:
                from render.d2hud import D2Hud
                self.hud = D2Hud(fallback_fonts, assets)
                self.hud.s = 1.0
                self.hud.lw = W
                self.hud.mouse = (0, 0)
                self.bg = self.hud.frames.get("questbackground")
                self.medium = self._frames(FE + "mediumbuttonblank.dc6") or self.hud.frames.get("mediumbuttonblank")
                self.wide = self._joined(self._frames(FE + "widebuttonblank.dc6"))
            except Exception:
                import traceback
                traceback.print_exc()
                self.hud = None

    @property
    def d2(self):
        return self.hud is not None

    def _frames(self, path):
        """DC6 frames as images in the units palette (as the character select screen loads them)."""
        h = self.hud
        if h is None or not h.src.has(path):
            return None
        try:
            from d2.dc6 import DC6
            from d2.palette import load_palette
            pal = None
            for p in ("data\\global\\palette\\units\\pal.dat", "data\\global\\palette\\act1\\pal.dat"):
                if h.src.has(p):
                    pal = load_palette(h.src.read(p))
                    break
            dc = DC6(h.src.read(path))
            out = []
            for f in dc.frames:
                if not f.width or not f.height:
                    out.append(None)
                    continue
                s = pygame.image.frombuffer(bytes(f.pixels), (f.width, f.height), "P")
                if pal is not None:
                    s.set_palette(pal)
                s.set_colorkey(0)
                img = pygame.Surface((f.width, f.height), pygame.SRCALPHA)
                img.fill((0, 0, 0, 0))
                img.blit(s, (0, 0))
                out.append(img)
            return out
        except Exception:
            return None

    def _joined(self, frames):
        """D2 keeps a wide button as two frames side by side: up = 0+1, pressed = 2+3."""
        if not frames:
            return None
        def join(a, b):
            parts = [frames[i] for i in (a, b) if i < len(frames) and frames[i] is not None]
            if not parts:
                return None
            out = pygame.Surface((sum(p.get_width() for p in parts), max(p.get_height() for p in parts)), pygame.SRCALPHA)
            out.fill((0, 0, 0, 0))
            x = 0
            for p in parts:
                out.blit(p, (x, 0))
                x += p.get_width()
            return out
        return [join(0, 1), join(2, 3) or join(0, 1)]

    # ------------------------------------------------------------ text
    def font(self, size):
        if self.hud is not None:
            return {"small": self.hud.f10, "med": self.hud.f16, "big": self.hud.f30}[size]
        return self.fb[{"small": "small", "med": "med", "big": "big"}[size]]

    def render(self, size, text, color):
        f = self.font(size)
        if self.hud is not None:
            return f.render(str(text), color, self.hud.ind)
        return f.render(str(text), True, color)

    def text(self, surf, size, text, color, x, y, align="left", box_w=0):
        img = self.render(size, text, color)
        w = img.get_width()
        if align == "center":
            x = x + (box_w - w) / 2.0
        elif align == "right":
            x = x + box_w - w
        surf.blit(img, (int(x), int(y)))
        return w

    def width(self, size, text):
        f = self.font(size)
        return f.width(str(text)) if self.hud is not None else f.size(str(text))[0]

    # ------------------------------------------------------------ panels and buttons
    def panel(self, surf, rect, dark=False):
        r = pygame.Rect(rect)
        key = ("panel", r.w, r.h, dark)
        img = self._cache.get(key)
        if img is None:
            img = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            if self.hud is not None and self.bg and r.w >= 200 and r.h >= 200:
                try:
                    self.hud.regions = []
                    self.hud._panel_frame(img, self.bg, r.w, r.h, split=0 if dark else None)
                except Exception:
                    img = None
            if img is None or (self.hud is None or not self.bg or r.w < 200 or r.h < 200):
                img = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
                img.fill((12, 11, 10, 235))
                pygame.draw.rect(img, (70, 62, 46), img.get_rect(), 2)
                pygame.draw.rect(img, (24, 22, 18), img.get_rect().inflate(-6, -6), 1)
            self._cache[key] = img
        surf.blit(img, r.topleft)

    def inset(self, surf, rect):
        """A sunken black field inside a panel (lists, the viewport, item grids)."""
        r = pygame.Rect(rect)
        pygame.draw.rect(surf, (4, 4, 6), r)
        pygame.draw.rect(surf, (96, 84, 58), r, 1)

    def button(self, surf, rect, label, hot=False, down=False, enabled=True):
        r = pygame.Rect(rect)
        art = None
        if self.hud is not None:
            frames = self.wide if (r.w >= 200 and self.wide) else self.medium
            if frames:
                img = frames[1 if down and len(frames) > 1 and frames[1] is not None else 0]
                if img is not None:
                    key = ("btn", id(img), r.w, r.h)
                    art = self._cache.get(key)
                    if art is None:
                        art = pygame.transform.smoothscale(img, (r.w, r.h))
                        self._cache[key] = art
        if art is not None:
            surf.blit(art, r.topleft)
        else:
            pygame.draw.rect(surf, (42, 38, 32) if enabled else (24, 22, 20), r)
            pygame.draw.rect(surf, (110, 98, 72) if enabled else (60, 56, 48), r, 1)
        if not enabled:
            shade = pygame.Surface(r.size, pygame.SRCALPHA)
            shade.fill((0, 0, 0, 130))
            surf.blit(shade, r.topleft)
        col = (WHITE if hot else (220, 210, 190)) if enabled else DARK
        size = "med" if r.h >= 26 else "small"
        img = self.render(size, label, col)
        surf.blit(img, (r.centerx - img.get_width() // 2 + (1 if down else 0),
                        r.centery - img.get_height() // 2 + (1 if down else 0)))

    def bar(self, surf, rect, frac, color):
        r = pygame.Rect(rect)
        pygame.draw.rect(surf, (20, 18, 16), r)
        pygame.draw.rect(surf, color, (r.x, r.y, int(r.w * max(0.0, min(1.0, frac))), r.h))
        pygame.draw.rect(surf, (96, 84, 58), r, 1)

    # ------------------------------------------------------------ items
    def icon(self, surf, it, x, y, w, h):
        if self.hud is not None and getattr(it, "kind", "") != "gold":
            try:
                self.hud._icon(surf, it, x, y, w, h)
                return
            except Exception:
                pass
        col = getattr(it, "color", None) or GOLD
        pygame.draw.rect(surf, (30, 28, 26), (x + 1, y + 1, w - 2, h - 2))
        label = "%d" % getattr(it, "amount", 0) if getattr(it, "kind", "") == "gold" else \
            str(getattr(it, "name", "?"))[:1]
        self.text(surf, "small", label, col, x, y + h // 2 - 5, "center", w)

    def tooltip(self, surf, lines, at):
        if not lines:
            return
        if self.hud is not None:
            try:
                self.hud.tooltip(surf, lines, at)
                return
            except Exception:
                pass
        lh = 16
        w = max(self.width("med", t) for t, _ in lines) + 14
        h = len(lines) * lh + 8
        x = min(max(4, at[0] - w // 2), W - w - 4)
        y = at[1] - h - 18 if at[1] - h - 18 > 4 else at[1] + 24
        box = pygame.Surface((w, h), pygame.SRCALPHA)
        box.fill((0, 0, 0, 215))
        surf.blit(box, (x, y))
        for i, (t, c) in enumerate(lines):
            self.text(surf, "med", t, c, x, y + 4 + i * lh, "center", w)

    def item_lines(self, it, hero):
        if getattr(it, "kind", "") == "gold":
            return [("%d Gold" % getattr(it, "amount", 0), GOLD)]
        try:
            return list(it.describe_lines(hero))
        except Exception:
            return [(str(getattr(it, "shown_name", None) or getattr(it, "name", "?")), getattr(it, "color", WHITE))]
