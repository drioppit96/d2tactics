"""Draws this game's own decoration sprites (assets/decor/*.png) in Diablo II's style: lit from the
upper left, gritty, snapped to D2's Act 3 colours. Run it again after changing a drawing:

    python tools/make_decor.py <path to your Diablo II folder or extracted files>

Every sprite is drawn here in code (nothing of Blizzard's art is copied); only the 256 colours of
D2's palette are used to make them sit right next to the game's own tiles.
"""
import math
import os
import random
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "decor")
S = 4                                          # supersampling
G = 1.5                                        # final size: D2's props are big, chunky things
U = (1.0, 0.5)                                 # one cell-unit along the map's x axis, on screen
V = (-1.0, 0.5)                                # ... along its y axis

WOOD = (136, 98, 58)
DWOOD = (104, 72, 44)
IRON = (118, 120, 124)
STEEL = (150, 152, 156)
BONE = (150, 138, 108)
STONE = (84, 82, 72)
CLOTH_RED = (120, 22, 18)
GOLD = (176, 140, 60)
STRAW = (170, 146, 80)
LEATHER = (96, 64, 40)
MOSS = (64, 78, 40)
DIRT = (58, 48, 36)
BLOOD = (78, 14, 10)


def sh(c, k, a=255):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3]) + (a,)


ANCHORS = {}                                  # name -> the sprite's ground point (pixels)


class Spr:
    """A sprite canvas; (0, 0) is the middle of its footprint on the ground."""

    def __init__(self, w, h, base=None, seed=1):
        pad = 60                                  # room all round; the result is cropped to the drawing
        self.w, self.h = w + 2 * pad, h + 2 * pad
        self.img = Image.new("RGBA", (self.w * S, self.h * S), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
        self.ox, self.oy = self.w * S // 2, ((base if base is not None else h - 16) + pad) * S
        self.rnd = random.Random(seed)
        self.glows = []

    # coordinates: x, y on the ground (map units, ~1 = one cell = 16 px wide), z up in pixels
    def p(self, x, y, z=0.0):
        return (self.ox + (x * U[0] + y * V[0]) * 16 * S, self.oy + ((x * U[1] + y * V[1]) * 16 - z) * S)

    def poly(self, pts, col):
        self.d.polygon([self.p(*q) for q in pts], fill=col)

    def line(self, pts, col, w=1.0):
        self.d.line([self.p(*q) for q in pts], fill=col, width=max(1, int(w * S)))

    def disc(self, x, y, z, r, col, flat=1.0):
        X, Y = self.p(x, y, z)
        self.d.ellipse((X - r * S, Y - r * S * flat, X + r * S, Y + r * S * flat), fill=col)

    def _mat(self, col):
        def near(a, b_):
            return sum(abs(int(u) - int(v)) for u, v in zip(a[:3], b_)) < 70
        if near(col, STONE) and abs(int(col[0]) - int(col[2])) < 25:
            return "stone"
        if near(col, WOOD) or near(col, DWOOD) or near(col, STRAW):
            return "wood"
        if near(col, IRON) or near(col, STEEL):
            return "iron"
        return None

    def _face_lines(self, corner, ax, ay, along, up, length, height, col, mat, k):
        """Texture one face: corner + along * t (0..length cells) + up * z (0..height px)."""
        rnd = self.rnd
        P = lambda t, zz: (corner[0] + along[0] * t, corner[1] + along[1] * t, corner[2] + zz)
        if mat == "wood":
            step = 4.5
            zz = step
            while zz < height - 1:                                     # plank seams
                self.line([P(0, zz), P(length, zz)], sh(col, k * 0.5), 0.45)
                zz += step
            for _ in range(int(length * height / 5) + 2):              # grain
                t0, z0 = rnd.uniform(0, length), rnd.uniform(0.5, height - 0.5)
                self.line([P(t0, z0), P(min(length, t0 + rnd.uniform(0.2, 0.7)), z0)],
                          sh(col, k * rnd.choice((0.7, 1.18))), 0.3)
            for t in (0.12, length - 0.12):                            # nails
                for zz in (1.5, height - 1.5):
                    X, Y = self.p(*P(t, zz))
                    self.d.ellipse((X - 0.5 * S, Y - 0.5 * S, X + 0.5 * S, Y + 0.5 * S), fill=sh(IRON, 0.5))
        elif mat == "stone":
            zz, row = 0.0, 0
            while zz < height:
                h_ = rnd.uniform(4.5, 6.5)
                self.line([P(0, min(height, zz + h_)), P(length, min(height, zz + h_))], sh(col, k * 0.45), 0.5)
                t = (row % 2) * 0.45
                while t < length:
                    self.line([P(t, zz), P(t, min(height, zz + h_))], sh(col, k * 0.45), 0.5)
                    t += rnd.uniform(0.8, 1.1)
                zz += h_
                row += 1
            for _ in range(int(length * height / 6)):                  # chips and pits
                X, Y = self.p(*P(rnd.uniform(0, length), rnd.uniform(0, height)))
                r = rnd.uniform(0.3, 0.9) * S
                self.d.ellipse((X - r, Y - r * 0.6, X + r, Y + r * 0.6), fill=sh(col, k * rnd.choice((0.55, 1.25))))
        elif mat == "iron":
            for _ in range(int(length * 6) + 2):                       # scratches
                t0, z0 = rnd.uniform(0, length), rnd.uniform(0, height)
                self.line([P(t0, z0), P(min(length, t0 + rnd.uniform(0.1, 0.4)), z0 + rnd.uniform(-1, 1))],
                          sh(col, k * 1.3), 0.3)
            for t in (0.15, length - 0.15):                            # rivets
                X, Y = self.p(*P(t, height * 0.5))
                self.d.ellipse((X - 0.6 * S, Y - 0.6 * S, X + 0.6 * S, Y + 0.6 * S), fill=sh(col, k * 1.4))

    def box(self, x, y, w, d, h, col, z=0.0, top=None, mat="auto"):
        """A box from (x, y) spanning w along x and d along y, h pixels tall (lit from the left),
        textured by its material (wood planks and grain, stone courses, scratched iron) and with a
        worn, lighter top edge."""
        a = [(x, y + d, z), (x + w, y + d, z), (x + w, y + d, z + h), (x, y + d, z + h)]
        b = [(x + w, y, z), (x + w, y + d, z), (x + w, y + d, z + h), (x + w, y, z + h)]
        t = [(x, y, z + h), (x + w, y, z + h), (x + w, y + d, z + h), (x, y + d, z + h)]
        self.poly(a, sh(col, 0.78))
        self.poly(b, sh(col, 0.52))
        self.poly(t, sh(top or col, 1.0))
        m = self._mat(col) if mat == "auto" else mat
        if m:
            self._face_lines((x, y + d, z), 0, 0, (1, 0), None, w, h, col, m, 0.78)
            self._face_lines((x + w, y, z), 0, 0, (0, 1), None, d, h, col, m, 0.52)
        if m == "wood":                                               # top boards
            yy = y + 0.33
            while yy < y + d - 0.05:
                self.line([(x, yy, z + h), (x + w, yy, z + h)], sh(top or col, 0.62), 0.45)
                yy += 0.33
        elif m == "stone":                                            # flagstones, cracked
            yy = y
            while yy < y + d:
                self.line([(x, yy, z + h), (x + w, yy, z + h)], sh(top or col, 0.6), 0.45)
                xx = x + self.rnd.uniform(0.2, 0.7)
                while xx < x + w:
                    self.line([(xx, yy, z + h), (xx, min(y + d, yy + 0.7), z + h)], sh(top or col, 0.6), 0.45)
                    xx += self.rnd.uniform(0.6, 1.0)
                yy += 0.7
        # worn edges catch the light
        self.line([(x, y + d, z + h), (x + w, y + d, z + h)], sh(top or col, 1.3), 0.5)
        self.line([(x, y, z + h), (x, y + d, z + h)], sh(top or col, 1.2), 0.4)
        return t

    def planks(self, x, y, w, d, h, col, z=0.0, n=3):
        self.box(x, y, w, d, h, col, z)
        for i in range(1, n):
            f = i / float(n)
            self.line([(x, y + d, z + h * f), (x + w, y + d, z + h * f)], sh(col, 0.45), 0.6)
            self.line([(x + w, y, z + h * f), (x + w, y + d, z + h * f)], sh(col, 0.32), 0.6)

    def barrel(self, x, y, r, h, col=WOOD, z=0.0):
        X, Y = self.p(x, y, z)
        for i in range(int(2 * r * S)):
            fx = i / (2.0 * r * S)
            k = 0.45 + 0.75 * math.sin(math.pi * min(1.0, fx * 1.15)) * (1.15 - fx * 0.5)
            xx = X - r * S + i
            bulge = math.sin(math.pi * fx) * 0.6 * S
            self.d.line([(xx, Y - h * S + r * S * 0.45 - bulge), (xx, Y + r * S * 0.45 * math.sin(math.pi * fx) + bulge)],
                        fill=sh(col, k))
        for f in (0.2, 0.8):
            yy = Y - h * S * f
            self.d.arc((X - r * S, yy - r * S * 0.45, X + r * S, yy + r * S * 0.45), 0, 180, fill=sh(IRON, 0.8), width=S)
        self.d.ellipse((X - r * S, Y - h * S - r * S * 0.45, X + r * S, Y - h * S + r * S * 0.45), fill=sh(col, 0.85))
        self.d.ellipse((X - r * S * 0.8, Y - h * S - r * S * 0.33, X + r * S * 0.8, Y - h * S + r * S * 0.33),
                       fill=sh(col, 0.6))

    def pole(self, x, y, h, col=DWOOD, w=1.6, z=0.0, lean=(0, 0)):
        self.line([(x, y, z), (x + lean[0], y + lean[1], z + h)], sh(col, 0.6), w + 0.6)
        self.line([(x - 0.03, y, z), (x + lean[0] - 0.03, y + lean[1], z + h)], sh(col, 1.1), w * 0.5)

    def blade(self, x, y, z, h, col=STEEL, w=1.6, hilt=GOLD, tilt=0.0):
        top = (x + tilt, y, z + h)
        self.line([(x, y, z), top], sh(col, 0.7), w)
        self.line([(x - 0.04, y, z + 2), (top[0] - 0.04, y, top[2] - 2)], sh(col, 1.25), w * 0.4)
        self.line([(x - 0.35, y + 0.1, z), (x + 0.35, y - 0.1, z)], sh(hilt, 0.9), 1.4)
        self.line([(x, y, z), (x, y, z - 6)], sh(LEATHER, 0.8), 1.4)

    def spear(self, x, y, z, h, lean=0.0):
        self.pole(x, y, h, DWOOD, 1.2, z, (lean, 0))
        tx, ty, tz = x + lean, y, z + h
        self.poly([(tx - 0.12, ty, tz), (tx + 0.12, ty, tz), (tx + lean * 0.05, ty, tz + 9)], sh(STEEL, 1.1))

    def skull(self, x, y, z, s=1.0):
        X, Y = self.p(x, y, z)
        r = 5 * S * s
        self.d.ellipse((X - r, Y - r * 0.95, X + r, Y + r * 0.85), fill=sh(BONE, 0.6))
        self.d.ellipse((X - r * 0.9, Y - r * 0.95, X + r * 0.8, Y + r * 0.6), fill=sh(BONE, 0.95))
        self.d.ellipse((X - r * 0.7, Y - r * 0.9, X + r * 0.2, Y - r * 0.1), fill=sh(BONE, 1.15))
        for ex in (-0.38, 0.3):
            self.d.ellipse((X + (ex - 0.2) * r, Y - 0.05 * r, X + (ex + 0.2) * r, Y + 0.33 * r), fill=(14, 10, 8, 255))
        self.d.rectangle((X - r * 0.45, Y + r * 0.45, X + r * 0.45, Y + r * 0.9), fill=sh(BONE, 0.7))

    def bone(self, x0, y0, x1, y1, z=0.0, w=1.4):
        self.line([(x0, y0, z), (x1, y1, z)], sh(BONE, 0.5), w + 0.8)
        self.line([(x0, y0, z + 0.6), (x1, y1, z + 0.6)], sh(BONE, 1.05), w * 0.6)
        for q in ((x0, y0), (x1, y1)):
            self.disc(q[0], q[1], z + 0.4, w * 0.9, sh(BONE, 0.9))

    def grit(self, n, rx, ry, cols, size=(1.0, 2.6), dz=0.0):
        for _ in range(n):
            a = self.rnd.uniform(0, 2 * math.pi)
            r = abs(self.rnd.gauss(0, 0.45))
            if r > 1:
                continue
            x, y = math.cos(a) * r * rx, math.sin(a) * r * ry
            e = self.rnd.uniform(*size)
            X, Y = self.p(x, y, dz)
            self.d.ellipse((X - e * S, Y - e * S * 0.55, X + e * S, Y + e * S * 0.55),
                           fill=sh(self.rnd.choice(cols), self.rnd.uniform(0.55, 1.1)))

    def glow(self, x, y, z, r, col=(255, 150, 50)):
        self.glows.append((self.p(x, y, z), r, col))

    def finish(self, pal, name, noise=0.16):
        """Grimdark pass, then D2's palette: the sprite is aged (grime, rust, soot, wood grain),
        darkened towards the ground (ambient occlusion), desaturated into Kurast's murk, given a
        hard rim light from the upper left and a dark outline, and snapped to the palette."""
        rnd = self.rnd
        big = self.img
        BW, BH = big.size
        # grime and rot at full resolution: dark blotches, soot streaks running down, rust spots
        grime = Image.new("RGBA", (BW, BH), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grime)
        for _ in range(int(BW * BH / 2600)):
            x, y = rnd.uniform(0, BW), rnd.uniform(0, BH)
            r = rnd.uniform(3, 10) * S / 2
            gd.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(16, 12, 8, rnd.randint(30, 80)))
        for _ in range(int(BW / 6)):
            x, y = rnd.uniform(0, BW), rnd.uniform(0, BH * 0.8)
            gd.line([(x, y), (x + rnd.uniform(-2, 2) * S, y + rnd.uniform(6, 22) * S)],
                    fill=(14, 10, 6, rnd.randint(40, 90)), width=max(1, int(rnd.uniform(0.5, 1.5) * S)))
        from PIL import ImageFilter
        grime = grime.filter(ImageFilter.GaussianBlur(2.2 * S))
        mask = big.split()[3]
        grime.putalpha(Image.composite(grime.split()[3], Image.new("L", (BW, BH), 0), mask))
        big = Image.alpha_composite(big, grime)
        px = big.load()
        oy = self.oy
        for yy in range(0, BH):
            # occlusion: the lowest pixels (near the ground) darkest, the tops catch the light
            k_ao = 0.7 + 0.3 * min(1.0, max(0.0, (oy - yy) / float(28 * S)))
            for xx in range(0, BW):
                r, g, b, a = px[xx, yy]
                if a < 30:
                    continue
                lum = (r * 30 + g * 59 + b * 11) / 100.0
                sat = max(r, g, b) - min(r, g, b)
                if sat < 22 and 60 < lum < 200 and rnd.random() < 0.035:      # rust on grey metal and stone
                    r, g, b = r * 0.9 + 30, g * 0.65 + 8, b * 0.45
                # desaturate into the murk, push the shadows down, keep fire and gold alive
                hot = r > 200 and g > 90 and b < 120
                keep = 0.85 if hot else 0.55
                r, g, b = (lum + (r - lum) * keep, lum + (g - lum) * keep, lum + (b - lum) * keep)
                c = 1.0 if hot else k_ao
                r, g, b = (255 * ((v * c) / 255.0) ** 1.1 for v in (r, g, b))
                r, g, b = r * 0.97, g * 0.98, b * 0.9           # a cold, sickly cast
                px[xx, yy] = (int(min(255, r)), int(min(255, g)), int(min(255, b)), a)
        W, H = int(self.w * G), int(self.h * G)
        img = big.resize((W, H), Image.LANCZOS)
        px = img.load()
        for yy in range(H):
            for xx in range(W):
                r, g, b, a = px[xx, yy]
                if a > 30:
                    n = rnd.uniform(1 - noise, 1 + noise * 0.6) * 0.95
                    px[xx, yy] = (min(255, int(r * n)), min(255, int(g * n)), min(255, int(b * n)), a)
        if self.glows:
            gl = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gd = ImageDraw.Draw(gl)
            for (X, Y), r, col in self.glows:
                X, Y, r = X / S * G, Y / S * G, r * G
                for k in range(int(r), 0, -2):
                    gd.ellipse((X - k, Y - k * 0.7, X + k, Y + k * 0.7), fill=col + (7,))
            img = Image.alpha_composite(img, gl)
        alpha = img.split()[3].point(lambda v: 255 if v > 110 else 0)
        # rim light from the upper left and a dark outline (D2's sprites read by their edges)
        A = alpha.load()
        px = img.load()
        out = img.copy()
        po = out.load()
        for yy in range(H):
            for xx in range(W):
                if not A[xx, yy]:
                    continue
                r, g, b, a = px[xx, yy]
                edge = any(not (0 <= xx + dx < W and 0 <= yy + dy < H and A[xx + dx, yy + dy])
                           for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                lit = not (0 <= xx - 1 < W and 0 <= yy - 1 < H and A[xx - 1, yy - 1])
                if edge and not lit:
                    r, g, b = r * 0.45, g * 0.42, b * 0.4
                po[xx, yy] = (int(r), int(g), int(b), a)
        img = out
        flat = []
        for c in pal[:256]:
            flat += list(c[:3])
        pimg = Image.new("P", (1, 1))
        pimg.putpalette(flat)
        rgb = img.convert("RGB").quantize(palette=pimg, dither=Image.Dither.FLOYDSTEINBERG).convert("RGB")
        rgb.putalpha(alpha)
        x0, y0, x1, y1 = alpha.getbbox() or (0, 0, rgb.width, rgb.height)
        x0, y0 = max(0, x0 - 2), max(0, y0 - 2)
        x1, y1 = min(rgb.width, x1 + 2), min(rgb.height, y1 + 2)
        rgb = rgb.crop((x0, y0, x1, y1))
        os.makedirs(OUT, exist_ok=True)
        rgb.save(os.path.join(OUT, name + ".png"))
        ANCHORS[name] = [int(self.ox / S * G) - x0, int(self.oy / S * G) - y0]
        return rgb


# ---------------------------------------------------------------- the sprites
def anvil(pal):
    s = Spr(100, 100, seed=2)
    s.grit(240, 2.8, 1.4, [DIRT, (40, 34, 28), IRON])
    s.barrel(0, 0, 10, 16, WOOD)                               # the stump
    s.box(-0.8, -0.45, 1.6, 0.9, 6, IRON, z=16)                # anvil body
    s.box(-0.5, -0.3, 1.0, 0.6, 3, sh(IRON, 0.8)[:3], z=13)    # waist
    s.box(-1.0, -0.55, 2.0, 1.1, 4, sh(IRON, 1.05)[:3], z=22)  # face
    s.poly([(1.0, -0.4, 26), (1.9, 0.0, 24.5), (1.0, 0.4, 26)], sh(STEEL, 1.0))    # horn
    s.poly([(1.0, -0.4, 22), (1.9, 0.0, 24.5), (1.0, 0.4, 22)], sh(IRON, 0.6))
    # a red-hot blade cooling on it
    s.line([(-0.9, 0.15, 26.5), (0.9, -0.15, 26.5)], (255, 120, 30, 255), 1.6)
    s.line([(-0.8, 0.15, 27.2), (0.8, -0.15, 27.2)], (255, 220, 120, 255), 0.6)
    s.glow(0, 0, 27, 16)
    # the hammer leaning on the stump, tongs on the ground
    s.line([(1.0, 1.0, 0), (0.6, 0.7, 18)], sh(WOOD, 1.0), 1.4)
    s.box(0.35, 0.55, 0.55, 0.35, 4, IRON, z=17)
    s.line([(-2.2, 0.8, 1), (-0.8, 1.3, 1)], sh(IRON, 1.0), 0.9)
    s.line([(-2.2, 1.0, 1), (-0.9, 1.1, 1)], sh(IRON, 1.0), 0.9)
    s.barrel(-2.2, -1.0, 6, 10, (88, 90, 96))                 # quench bucket
    s.disc(-2.2, -1.0, 10.2, 4.4, (52, 66, 74, 255), 0.45)
    return s.finish(pal, "anvil")


def forge(pal):
    s = Spr(150, 170, base=154, seed=3)
    s.grit(300, 4.2, 2.0, [DIRT, (30, 26, 22), (90, 40, 20)])
    s.box(-2.2, -1.6, 4.4, 3.2, 34, STONE)                     # furnace
    for i in range(6):                                         # stone courses
        z = 5 + i * 5.5
        s.line([(-2.2, 1.6, z), (2.2, 1.6, z)], sh(STONE, 0.45), 0.6)
        s.line([(2.2, -1.6, z), (2.2, 1.6, z)], sh(STONE, 0.35), 0.6)
    for _ in range(90):                                        # soot and ash on the hearth top
        s.disc(s.rnd.uniform(-2.0, 2.0), s.rnd.uniform(-1.4, 1.4), 34, s.rnd.uniform(0.4, 1.0),
               sh((52, 48, 44), s.rnd.uniform(0.7, 1.2)), 0.5)
    s.box(-0.8, -0.6, 1.6, 1.2, 46, sh(STONE, 0.9)[:3], z=34)  # chimney
    s.poly([(-0.55, -0.4, 80.2), (0.55, -0.4, 80.2), (0.55, 0.4, 80.2), (-0.55, 0.4, 80.2)], (10, 8, 6, 255))   # flue
    for k in range(5):                                         # smoke
        X, Y = s.p(0.1 * k, -0.1 * k, 84 + k * 7)
        r = (3 + k * 1.6) * S
        s.d.ellipse((X - r, Y - r * 0.8, X + r, Y + r * 0.8), fill=(46, 44, 42, 150 - k * 22))
    # the glowing mouth
    s.poly([(-1.0, 1.61, 6), (1.0, 1.61, 6), (1.0, 1.61, 17), (0.0, 1.61, 21), (-1.0, 1.61, 17)], (40, 12, 4, 255))
    s.poly([(-0.8, 1.62, 6), (0.8, 1.62, 6), (0.8, 1.62, 12), (-0.8, 1.62, 12)], (255, 110, 20, 255))
    s.poly([(-0.5, 1.63, 6), (0.5, 1.63, 6), (0.4, 1.63, 9), (-0.4, 1.63, 9)], (255, 220, 120, 255))
    s.glow(0, 1.8, 10, 26)
    s.glow(0, -0.2, 80, 10, (255, 120, 40))                    # embers at the chimney
    # bellows and a coal heap
    s.poly([(2.4, 1.0, 2), (3.6, 1.6, 2), (3.6, 1.6, 7), (2.4, 1.0, 10)], sh(LEATHER, 0.9))
    s.line([(3.6, 1.6, 6), (4.4, 2.0, 9)], sh(WOOD, 1.0), 1.0)
    for _ in range(40):
        a = s.rnd.uniform(0, math.pi * 2)
        r = s.rnd.uniform(0, 1.0)
        s.disc(-2.8 + math.cos(a) * r, 2.2 + math.sin(a) * r * 0.5, s.rnd.uniform(0, 4) * (1 - r),
               1.2, sh((40, 38, 36), s.rnd.uniform(0.6, 1.3)))
    return s.finish(pal, "forge")


def weaponrack(pal):
    s = Spr(120, 120, seed=4)
    s.grit(120, 3.0, 1.2, [DIRT, DWOOD])
    s.box(-2.6, -0.2, 5.2, 0.4, 4, DWOOD)                      # base beam
    s.pole(-2.4, 0, 36, DWOOD, 2.0)
    s.pole(2.4, 0, 36, DWOOD, 2.0)
    s.box(-2.7, -0.15, 5.4, 0.3, 3, WOOD, z=30)                # top rail
    s.box(-2.7, -0.15, 5.4, 0.3, 2, WOOD, z=16)                # middle rail
    xs = [-1.9, -1.3, -0.6, 0.1, 0.8, 1.5, 2.0]
    for i, x in enumerate(xs):
        if i % 3 == 0:
            s.spear(x, 0.05, 2, 44, lean=0.15)
        elif i % 3 == 1:
            s.blade(x, 0.05, 8, 26, tilt=0.05)
        else:
            s.pole(x, 0.05, 30, WOOD, 1.2, 2, (0.1, 0))         # axe
            s.poly([(x + 0.1, 0.05, 32), (x + 0.75, 0.05, 36), (x + 0.75, 0.05, 26), (x + 0.1, 0.05, 28)],
                   sh(IRON, 1.0))
    # a fallen sword and a shield leaning on the rack
    s.line([(1.2, 1.4, 1), (3.3, 0.6, 1)], sh(STEEL, 0.9), 1.3)
    s.disc(-3.0, 0.7, 9, 7, sh(CLOTH_RED, 0.9), 1.0)
    s.disc(-3.0, 0.7, 9, 5.5, sh(CLOTH_RED, 0.6), 1.0)
    s.disc(-3.0, 0.7, 9, 2, sh(GOLD, 1.0), 1.0)
    return s.finish(pal, "weaponrack")


def armorstand(pal):
    s = Spr(90, 120, seed=5)
    s.grit(80, 2.0, 1.0, [DIRT])
    s.box(-0.7, -0.7, 1.4, 1.4, 4, STONE)                      # a chipped stone plinth
    s.pole(0, 0, 50, DWOOD, 2.0, z=4)
    s.line([(-1.4, 0, 40), (1.4, 0, 40)], sh(DWOOD, 0.9), 1.8)   # shoulders
    # breastplate with a red Zakarum tabard
    X, Y = s.p(0, 0, 40)
    d = s.d
    d.polygon([(X - 9 * S, Y), (X + 9 * S, Y), (X + 7 * S, Y + 18 * S), (X - 7 * S, Y + 18 * S)], fill=sh(IRON, 0.75))
    d.polygon([(X - 8 * S, Y), (X + 2 * S, Y), (X - 1 * S, Y + 17 * S), (X - 6 * S, Y + 17 * S)], fill=sh(STEEL, 1.05))
    d.polygon([(X - 4 * S, Y + 6 * S), (X + 4 * S, Y + 6 * S), (X + 5 * S, Y + 30 * S), (X - 5 * S, Y + 30 * S)],
              fill=sh(CLOTH_RED, 1.0))
    d.ellipse((X - 2.4 * S, Y + 13 * S, X + 2.4 * S, Y + 17 * S), fill=sh(GOLD, 1.0))
    d.ellipse((X - 1 * S, Y + 14 * S, X + 1 * S, Y + 16 * S), fill=(30, 10, 6, 255))
    for k in (-1, 1):                                          # pauldrons
        d.ellipse((X + k * 11 * S - 5 * S, Y - 3 * S, X + k * 11 * S + 5 * S, Y + 5 * S), fill=sh(IRON, 1.0 if k < 0 else 0.7))
    # helm on top
    hx, hy = s.p(0, 0, 54)
    d.ellipse((hx - 6 * S, hy - 7 * S, hx + 6 * S, hy + 6 * S), fill=sh(IRON, 0.8))
    d.ellipse((hx - 5 * S, hy - 7 * S, hx + 2 * S, hy + 2 * S), fill=sh(STEEL, 1.05))
    d.rectangle((hx - 4 * S, hy - 1 * S, hx + 4 * S, hy + 1 * S), fill=(18, 14, 10, 255))
    d.line([(hx, hy - 7 * S), (hx, hy - 13 * S)], fill=sh(CLOTH_RED, 1.1), width=2 * S)
    return s.finish(pal, "armorstand")


def crates(pal):
    s = Spr(140, 130, base=104, seed=6)
    s.grit(200, 3.6, 1.8, [DIRT, DWOOD, STRAW])
    s.planks(-2.4, -1.2, 2.2, 2.0, 22, WOOD)
    s.planks(0.0, -1.0, 1.8, 1.8, 18, sh(WOOD, 0.9)[:3])
    s.planks(-2.0, -1.0, 1.6, 1.6, 16, sh(WOOD, 1.05)[:3], z=22)
    s.line([(-2.4, 0.8, 22), (-0.2, 0.8, 0)], sh(DWOOD, 0.6), 0.7)          # rope/strap
    s.barrel(2.2, 0.6, 7, 20)
    s.barrel(3.4, -0.6, 6, 18, sh(WOOD, 0.85)[:3])
    # a broken crate spilling iron ingots
    s.planks(-0.6, 1.4, 1.4, 1.0, 6, sh(WOOD, 0.8)[:3])
    for i in range(5):
        s.box(-0.4 + i * 0.32, 2.3 + (i % 2) * 0.25, 0.28, 0.6, 2.5, IRON, z=0)
    return s.finish(pal, "crates")


def arrows(pal):
    s = Spr(110, 100, seed=7)
    s.grit(120, 3.0, 1.4, [DIRT, STRAW])
    for bx, by in ((-1.3, 0), (1.0, -0.4), (0.2, 1.0)):
        s.barrel(bx, by, 6, 12, STRAW)                          # wicker baskets
        for k in range(16):
            ax = bx + s.rnd.uniform(-0.25, 0.25)
            lean = s.rnd.uniform(-0.25, 0.25)
            h = s.rnd.uniform(14, 20)
            s.line([(ax, by, 12), (ax + lean, by, 12 + h)], sh(WOOD, 1.0), 0.7)
            s.disc(ax + lean, by, 12 + h, 1.0, sh((200, 196, 190), s.rnd.uniform(0.7, 1.0)))   # fletching
    # javelins leaning together
    for k in range(4):
        s.spear(2.2 + k * 0.15, 0.6, 0, 40, lean=-0.6 + k * 0.2)
    return s.finish(pal, "arrows")


def dummy(pal):
    s = Spr(90, 130, seed=8)
    s.grit(120, 2.0, 1.0, [DIRT, STRAW])
    s.pole(0, 0, 58, DWOOD, 2.2)
    s.line([(-1.6, 0, 44), (1.6, 0, 44)], sh(DWOOD, 1.0), 2.0)
    X, Y = s.p(0, 0, 44)
    d = s.d
    d.ellipse((X - 9 * S, Y - 2 * S, X + 9 * S, Y + 22 * S), fill=sh(STRAW, 0.7))
    d.ellipse((X - 8 * S, Y - 2 * S, X + 3 * S, Y + 19 * S), fill=sh(STRAW, 1.0))
    d.ellipse((X - 6 * S, Y - 16 * S, X + 6 * S, Y - 3 * S), fill=sh(LEATHER, 0.9))      # sack head
    d.line([(X - 9 * S, Y + 6 * S), (X + 9 * S, Y + 8 * S)], fill=sh(DWOOD, 0.8), width=S)  # rope
    # painted target and arrows stuck in it
    d.ellipse((X - 3.5 * S, Y + 6 * S, X + 2.5 * S, Y + 12 * S), fill=sh(CLOTH_RED, 1.1))
    d.ellipse((X - 1.5 * S, Y + 8 * S, X + 0.5 * S, Y + 10 * S), fill=(220, 210, 180, 255))
    for k in range(5):
        x0, y0 = X + s.rnd.uniform(-6, 6) * S, Y + s.rnd.uniform(0, 16) * S
        d.line([(x0, y0), (x0 + 9 * S, y0 - 3 * S)], fill=sh(WOOD, 1.0), width=S)
        d.ellipse((x0 + 8 * S, y0 - 4.5 * S, x0 + 11 * S, y0 - 1.5 * S), fill=(200, 196, 190, 255))
    for k in range(4):                                         # spent arrows on the ground
        a = s.rnd.uniform(-1.2, 1.2)
        s.line([(a, 1.0, 0.5), (a + 0.9, 1.3, 0.5)], sh(WOOD, 0.9), 0.7)
    return s.finish(pal, "dummy")


def debris(pal):
    s = Spr(140, 90, base=70, seed=9)
    s.grit(260, 4.0, 1.8, [DIRT, BLOOD, (40, 34, 28)])
    for _ in range(18):                                        # blood
        x, y = s.rnd.uniform(-2.5, 2.5), s.rnd.uniform(-1.2, 1.2)
        s.disc(x, y, 0, s.rnd.uniform(2, 5), sh(BLOOD, s.rnd.uniform(0.6, 1.1)), 0.5)
    # broken shields (round, red with gold), a dented helm, snapped swords and spear shafts
    for x, y, r in ((-2.2, 0.2, 7), (1.6, 0.8, 6), (0.2, -0.8, 5)):
        X, Y = s.p(x, y, 1)
        s.d.ellipse((X - r * S, Y - r * S * 0.5, X + r * S, Y + r * S * 0.5), fill=sh(CLOTH_RED, 0.75))
        s.d.ellipse((X - r * S * 0.8, Y - r * S * 0.45, X + r * S * 0.6, Y + r * S * 0.3), fill=sh(CLOTH_RED, 1.0))
        s.d.ellipse((X - 2 * S, Y - 1 * S, X + 2 * S, Y + 1 * S), fill=sh(GOLD, 1.0))
        s.d.line([(X - r * S * 0.2, Y - r * S * 0.5), (X + r * S * 0.3, Y + r * S * 0.4)], fill=(20, 14, 10, 255), width=S)
    hx, hy = s.p(-0.4, 0.9, 3)
    s.d.ellipse((hx - 5 * S, hy - 5 * S, hx + 5 * S, hy + 3 * S), fill=sh(IRON, 0.8))
    s.d.ellipse((hx - 4 * S, hy - 5 * S, hx + 1 * S, hy + 1 * S), fill=sh(STEEL, 1.0))
    s.line([(-3.0, -0.6, 1), (-1.4, -1.2, 1)], sh(STEEL, 1.0), 1.2)
    s.line([(2.4, -0.6, 1), (3.6, -0.2, 1)], sh(STEEL, 0.9), 1.2)
    s.line([(0.6, 1.6, 0.5), (3.0, 1.0, 0.5)], sh(DWOOD, 1.0), 1.2)
    s.skull(1.2, -1.2, 3, 0.8)
    return s.finish(pal, "debris")


def banner(pal):
    s = Spr(80, 170, seed=10)
    s.grit(60, 1.6, 0.8, [DIRT])
    s.box(-0.6, -0.6, 1.2, 1.2, 4, STONE)
    s.pole(0, 0, 120, DWOOD, 2.2)
    s.line([(-1.5, 0, 112), (1.5, 0, 112)], sh(DWOOD, 1.0), 1.8)
    X, Y = s.p(0, 0, 112)
    d = s.d
    pts = [(X - 13 * S, Y), (X + 13 * S, Y), (X + 12 * S, Y + 52 * S), (X + 5 * S, Y + 46 * S), (X + 1 * S, Y + 58 * S),
           (X - 4 * S, Y + 47 * S), (X - 12 * S, Y + 54 * S)]
    d.polygon(pts, fill=sh(CLOTH_RED, 0.75))
    d.polygon([(X - 12 * S, Y), (X + 2 * S, Y), (X - 1 * S, Y + 50 * S), (X - 11 * S, Y + 52 * S)], fill=sh(CLOTH_RED, 1.0))
    for k in range(4):                                         # folds
        x = X + (-9 + k * 6) * S
        d.line([(x, Y + 2 * S), (x + 1 * S, Y + 48 * S)], fill=sh(CLOTH_RED, 0.55), width=S)
    # the Zakarum eye in gold
    d.ellipse((X - 8 * S, Y + 14 * S, X + 8 * S, Y + 26 * S), fill=sh(GOLD, 0.9))
    d.ellipse((X - 6 * S, Y + 16 * S, X + 6 * S, Y + 24 * S), fill=sh(CLOTH_RED, 0.7))
    d.ellipse((X - 2.5 * S, Y + 17.5 * S, X + 2.5 * S, Y + 22.5 * S), fill=sh(GOLD, 1.15))
    d.line([(X, Y + 28 * S), (X, Y + 40 * S)], fill=sh(GOLD, 0.8), width=S)
    d.line([(X - 5 * S, Y + 34 * S), (X + 5 * S, Y + 34 * S)], fill=sh(GOLD, 0.8), width=S)
    return s.finish(pal, "banner")


def corpse(pal):
    s = Spr(130, 80, base=56, seed=11)
    s.grit(160, 3.6, 1.6, [BLOOD, DIRT])
    for _ in range(14):
        s.disc(s.rnd.uniform(-2.6, 2.0), s.rnd.uniform(-0.8, 1.2), 0, s.rnd.uniform(2, 6), sh(BLOOD, s.rnd.uniform(0.5, 1.0)), 0.5)
    # a fallen Zakarum guard: red tabard, steel, outflung arm, his spear broken
    body = [(-2.4, 0.2, 2), (1.0, -0.4, 2)]
    s.line(body, sh(IRON, 0.6), 6)
    s.line([(-2.2, 0.2, 3.5), (0.8, -0.4, 3.5)], sh(CLOTH_RED, 1.0), 4)
    s.line([(-0.6, -0.1, 3.5), (0.0, -1.4, 1.5)], sh(IRON, 0.9), 2)        # arm
    s.line([(1.0, -0.4, 2), (2.6, 0.4, 1)], sh(LEATHER, 0.8), 2.6)          # legs
    s.line([(0.9, -0.3, 2), (2.4, -0.6, 1)], sh(LEATHER, 0.7), 2.6)
    X, Y = s.p(-2.9, 0.4, 3)
    s.d.ellipse((X - 4 * S, Y - 4 * S, X + 4 * S, Y + 3 * S), fill=sh(STEEL, 0.9))   # helm
    s.line([(-1.2, 1.4, 0.5), (0.6, 0.6, 0.5)], sh(DWOOD, 1.0), 1.2)
    s.line([(1.0, 1.6, 0.5), (2.2, 1.2, 0.5)], sh(DWOOD, 1.0), 1.2)
    s.poly([(2.2, 1.2, 0.5), (2.6, 1.0, 0.5), (2.5, 1.3, 0.5)], sh(STEEL, 1.1))
    return s.finish(pal, "corpse")


def cart(pal):
    s = Spr(140, 110, seed=12)
    s.grit(160, 3.6, 1.6, [DIRT, (40, 34, 28)])
    s.planks(-2.4, -1.0, 4.4, 2.0, 12, WOOD, z=6)
    for wx in (-1.6, 1.2):                                     # wheels
        X, Y = s.p(wx, 1.0, 7)
        s.d.ellipse((X - 8 * S, Y - 8 * S, X + 8 * S, Y + 8 * S), fill=sh(DWOOD, 0.7))
        s.d.ellipse((X - 6 * S, Y - 6 * S, X + 6 * S, Y + 6 * S), fill=sh(DWOOD, 1.0))
        for a in range(0, 180, 45):
            r = math.radians(a)
            s.d.line([(X - math.cos(r) * 6 * S, Y - math.sin(r) * 6 * S), (X + math.cos(r) * 6 * S, Y + math.sin(r) * 6 * S)],
                     fill=sh(DWOOD, 0.6), width=S)
    s.line([(2.0, 0.0, 10), (4.4, 0.0, 3)], sh(DWOOD, 1.0), 1.6)            # shaft
    for i in range(9):                                         # ore and iron bars
        s.disc(-1.6 + (i % 5) * 0.8, -0.4 + (i // 5) * 0.7, 19 + (i % 3), 3.2, sh((70, 66, 64), 0.8 + 0.1 * (i % 3)))
    for i in range(3):
        s.box(-1.4 + i * 0.9, -0.2, 0.7, 0.3, 2.5, sh(IRON, 1.1)[:3], z=22)
    return s.finish(pal, "cart")


def bones(pal):
    s = Spr(160, 120, seed=13)
    s.grit(500, 4.0, 1.8, [DIRT, (40, 34, 28)])
    s.box(-3.0, -1.4, 3.2, 1.6, 7, STONE)                      # a toppled Zakarum altar slab
    X, Y = s.p(-1.6, -0.6, 7)
    s.d.arc((X - 10 * S, Y - 5 * S, X + 10 * S, Y + 3 * S), 200, 340, fill=sh(STONE, 0.45), width=2 * S)
    s.d.arc((X - 10 * S, Y - 2 * S, X + 10 * S, Y + 6 * S), 20, 160, fill=sh(STONE, 0.45), width=2 * S)
    for _ in range(14):
        x0, y0 = s.rnd.uniform(-2.2, 2.6), s.rnd.uniform(-0.6, 1.6)
        a = s.rnd.uniform(0, math.pi)
        s.bone(x0, y0, x0 + math.cos(a) * 1.6, y0 + math.sin(a) * 0.8, 0.5, 1.5)
    for x, y, k in ((-0.4, 0.4, 1.0), (0.9, 0.0, 0.9), (0.3, 1.0, 1.1)):
        s.skull(x, y, 5, k)
    for x, y in ((-2.6, -1.0), (-0.6, -1.2)):
        X, Y = s.p(x, y, 7)
        s.d.rectangle((X - 1.5 * S, Y - 8 * S, X + 1.5 * S, Y), fill=sh((160, 150, 120), 1.0))
        s.d.ellipse((X - 1.5 * S, Y - 13 * S, X + 1.5 * S, Y - 8 * S), fill=(255, 200, 90, 255))
        s.glow(x, y, 17, 12)
    return s.finish(pal, "bones")


def blood(pal):
    s = Spr(120, 60, base=30, seed=14)
    for _ in range(30):
        s.disc(s.rnd.gauss(0, 1.0), s.rnd.gauss(0, 0.5), 0, s.rnd.uniform(1.5, 6), sh(BLOOD, s.rnd.uniform(0.5, 1.1)), 0.5)
    for _ in range(14):                                        # drag marks
        x = s.rnd.uniform(-1, 3)
        s.line([(x, 0.0, 0), (x + 1.5, -0.4, 0)], sh(BLOOD, 0.7), 1.0)
    return s.finish(pal, "blood", noise=0.1)


# ---------------------------------------------------------------- second set
def statue(pal):
    """A Zakarum zealot in stone on a stepped plinth, spear grounded, head bowed - one hand broken off."""
    s = Spr(110, 230, seed=21)
    s.grit(160, 2.4, 1.2, [DIRT, STONE, (40, 36, 30)])
    s.box(-1.4, -1.4, 2.8, 2.8, 8, STONE)
    s.box(-1.0, -1.0, 2.0, 2.0, 8, sh(STONE, 1.05)[:3], z=8)
    X, Y = s.p(0, 0, 16)
    d = s.d
    st, dk, lt = sh(STONE, 0.95), sh(STONE, 0.6), sh(STONE, 1.3)
    d.polygon([(X - 12 * S, Y), (X + 12 * S, Y), (X + 9 * S, Y - 60 * S), (X - 9 * S, Y - 60 * S)], fill=st)  # robe
    d.polygon([(X - 12 * S, Y), (X - 2 * S, Y), (X - 3 * S, Y - 60 * S), (X - 9 * S, Y - 60 * S)], fill=lt)
    for k in range(5):                                                    # robe folds
        x = X + (-8 + k * 4) * S
        d.line([(x, Y - 58 * S), (x + (k - 2) * S, Y)], fill=dk, width=S)
    d.polygon([(X - 13 * S, Y - 60 * S), (X + 13 * S, Y - 60 * S), (X + 10 * S, Y - 82 * S), (X - 10 * S, Y - 82 * S)], fill=st)
    d.polygon([(X - 13 * S, Y - 60 * S), (X - 1 * S, Y - 60 * S), (X - 2 * S, Y - 82 * S), (X - 10 * S, Y - 82 * S)], fill=lt)
    d.ellipse((X - 7 * S, Y - 96 * S, X + 7 * S, Y - 80 * S), fill=st)  # hooded head, bowed
    d.ellipse((X - 6 * S, Y - 96 * S, X + 1 * S, Y - 84 * S), fill=lt)
    d.ellipse((X - 3 * S, Y - 88 * S, X + 4 * S, Y - 82 * S), fill=(18, 16, 14, 255))
    s.line([(0.9, 0.3, 16), (0.9, 0.3, 120)], dk, 2.2)                    # the spear
    s.line([(0.85, 0.3, 16), (0.85, 0.3, 120)], st, 1.0)
    s.poly([(0.75, 0.3, 120), (1.05, 0.3, 120), (0.9, 0.3, 132)], lt)
    d.ellipse((X + 7 * S, Y - 72 * S, X + 15 * S, Y - 64 * S), fill=st)  # the hand on it
    s.disc(-1.8, 1.2, 1, 2.2, dk, 0.6)                                    # the broken hand on the ground
    for _ in range(26):                                                   # moss and cracks
        x0, y0 = X + s.rnd.uniform(-10, 10) * S, Y - s.rnd.uniform(4, 90) * S
        d.line([(x0, y0), (x0 + s.rnd.uniform(-3, 3) * S, y0 + s.rnd.uniform(2, 6) * S)], fill=sh(MOSS, 0.9), width=S)
    return s.finish(pal, "statue")


def bunks(pal):
    """Two wooden cots with filthy blankets, a dropped helmet and a chamber pot."""
    s = Spr(170, 130, seed=22)
    s.grit(200, 3.6, 1.8, [DIRT, STRAW])
    for oy in (-1.3, 0.6):
        s.box(-2.6, oy, 4.6, 1.3, 8, DWOOD)                               # frame
        for x in (-2.5, 1.8):
            s.box(x, oy, 0.2, 0.2, 14, DWOOD)                             # posts
        s.box(-2.4, oy + 0.1, 4.2, 1.1, 3, sh((96, 84, 66), 1.0)[:3], z=8, mat=None)   # straw mattress
        s.box(-2.2, oy + 0.1, 2.8, 1.1, 2, sh((86, 30, 24), 0.8)[:3], z=11, mat=None)  # blanket
        s.box(1.0, oy + 0.25, 0.8, 0.8, 2, sh((160, 150, 120), 0.8)[:3], z=11, mat=None)   # pillow
    hx, hy = s.p(2.6, 1.7, 2)
    s.d.ellipse((hx - 5 * S, hy - 6 * S, hx + 5 * S, hy + 3 * S), fill=sh(IRON, 0.85))
    s.d.ellipse((hx - 4 * S, hy - 6 * S, hx + 1 * S, hy + 1 * S), fill=sh(STEEL, 1.0))
    s.barrel(-3.0, 1.6, 4, 5, (90, 70, 50))
    return s.finish(pal, "bunks")


def table(pal):
    """A long mess table, benches, spilled mugs, a half-eaten loaf - and a knife stuck in the wood."""
    s = Spr(180, 120, seed=23)
    s.grit(200, 3.8, 1.8, [DIRT, (60, 50, 38)])
    for x in (-2.4, 1.9):
        for y in (-0.5, 0.5):
            s.box(x, y, 0.25, 0.25, 12, DWOOD)                            # legs
    s.planks(-2.6, -0.7, 5.0, 1.6, 3, WOOD, z=12)
    for y in (-1.5, 1.2):                                                 # benches
        s.box(-2.4, y, 4.4, 0.4, 2, sh(WOOD, 0.85)[:3], z=6)
        for x in (-2.2, 1.7):
            s.box(x, y + 0.1, 0.2, 0.2, 6, DWOOD)
    for x, y in ((-1.6, -0.2), (-0.6, 0.3), (0.9, -0.1)):                 # mugs
        s.barrel(x, y, 2.0, 4, sh(DWOOD, 1.1)[:3], z=15)
    s.disc(0.2, 0.3, 15.5, 4, sh((150, 110, 60), 0.9), 0.55)               # bread
    s.disc(-0.4, -0.1, 15.2, 5, sh((100, 30, 18), 0.6), 0.45)             # spilt wine
    s.line([(1.4, 0.4, 15), (1.5, 0.3, 24)], sh(STEEL, 1.1), 0.9)         # the knife
    s.barrel(3.0, 1.0, 2.0, 4, sh(DWOOD, 1.1)[:3])                        # a mug on the floor
    return s.finish(pal, "table")


def kegs(pal):
    """Kegs on a wooden cradle, one tapped and dripping."""
    s = Spr(160, 130, seed=24)
    s.grit(180, 3.4, 1.6, [DIRT, (70, 30, 20)])
    s.box(-2.6, -0.8, 5.0, 1.6, 4, DWOOD)
    for x in (-1.6, 0.4):
        X, Y = s.p(x, 0, 14)
        for i in range(int(18 * S)):                                      # a keg on its side
            k = 0.5 + 0.7 * math.sin(math.pi * i / (18.0 * S))
            s.d.line([(X - 14 * S, Y - 9 * S + i), (X + 14 * S, Y - 9 * S + i + 0)], fill=sh(WOOD, k))
        for f in (-0.6, 0.0, 0.6):
            s.d.line([(X + f * 14 * S, Y - 9 * S), (X + f * 14 * S, Y + 9 * S)], fill=sh(IRON, 0.7), width=S)
        s.d.ellipse((X + 11 * S, Y - 9 * S, X + 17 * S, Y + 9 * S), fill=sh(WOOD, 0.8))
    s.barrel(2.4, 0.4, 7, 16)                                             # a standing one
    s.line([(1.1, 0.3, 14), (1.5, 0.3, 11)], sh(IRON, 1.0), 1.0)          # tap
    s.disc(1.6, 0.6, 0, 4, sh((80, 30, 20), 0.8), 0.5)                    # the puddle
    return s.finish(pal, "kegs")


def grindstone(pal):
    """A treadle grindstone with a bucket, sparks frozen in mid-air and a notched sword waiting."""
    s = Spr(140, 130, seed=25)
    s.grit(180, 3.0, 1.4, [DIRT, IRON])
    s.box(-1.6, -0.5, 3.2, 1.0, 10, DWOOD)                                # frame
    X, Y = s.p(0, 0, 22)
    s.d.ellipse((X - 16 * S, Y - 16 * S, X + 16 * S, Y + 16 * S), fill=sh((110, 104, 92), 0.8))   # wheel
    s.d.ellipse((X - 15 * S, Y - 15 * S, X + 10 * S, Y + 10 * S), fill=sh((120, 114, 100), 1.05))
    for k in range(8):
        a = k * math.pi / 4
        s.d.line([(X, Y), (X + math.cos(a) * 15 * S, Y + math.sin(a) * 15 * S)], fill=sh((110, 104, 92), 0.7), width=S)
    s.d.ellipse((X - 3 * S, Y - 3 * S, X + 3 * S, Y + 3 * S), fill=sh(IRON, 1.0))
    s.line([(0, 0, 22), (1.8, 0.4, 30)], sh(IRON, 0.9), 1.4)              # crank
    for _ in range(14):                                                   # sparks
        a = s.rnd.uniform(-0.6, 0.6)
        l = s.rnd.uniform(4, 12) * S
        x0, y0 = X + 14 * S, Y - 6 * S
        s.d.line([(x0, y0), (x0 + math.cos(a) * l, y0 + math.sin(a) * l)], fill=(255, 200, 90, 255), width=S)
    s.glow(0.6, -0.3, 26, 12, (255, 170, 60))
    s.blade(-2.4, 0.9, 0, 24, tilt=0.4)
    s.barrel(2.4, 1.0, 5, 8, (80, 82, 86))
    return s.finish(pal, "grindstone")


def target(pal):
    """A straw archery butt on a tripod, painted rings, arrows in it and around it."""
    s = Spr(110, 160, seed=26)
    s.grit(140, 2.4, 1.2, [DIRT, STRAW])
    s.line([(-1.0, 0.6, 0), (0, 0, 40)], sh(DWOOD, 1.0), 1.6)
    s.line([(1.0, 0.6, 0), (0, 0, 40)], sh(DWOOD, 0.8), 1.6)
    s.line([(0, -1.0, 0), (0, 0, 40)], sh(DWOOD, 0.7), 1.6)
    X, Y = s.p(0, 0.3, 46)
    d = s.d
    for r, c in ((20, sh(STRAW, 0.75)), (18, sh(STRAW, 1.0)), (13, sh((200, 196, 180), 0.8)), (9, sh(CLOTH_RED, 1.0)),
                 (5, sh((200, 196, 180), 0.9)), (2.5, sh(GOLD, 1.1))):
        d.ellipse((X - r * 0.8 * S, Y - r * S, X + r * 0.8 * S, Y + r * S), fill=c)
    for _ in range(40):                                                   # straw ends
        a = s.rnd.uniform(0, 2 * math.pi)
        d.line([(X + math.cos(a) * 15 * S, Y + math.sin(a) * 19 * S), (X + math.cos(a) * 17 * S, Y + math.sin(a) * 21 * S)],
               fill=sh(STRAW, 1.2), width=S)
    for _ in range(5):
        x0, y0 = X + s.rnd.uniform(-8, 8) * S, Y + s.rnd.uniform(-10, 10) * S
        d.line([(x0, y0), (x0 + 12 * S, y0 - 5 * S)], fill=sh(WOOD, 1.0), width=S)
        d.ellipse((x0 + 11 * S, y0 - 7 * S, x0 + 14 * S, y0 - 3 * S), fill=(200, 196, 190, 255))
    for _ in range(4):
        a = s.rnd.uniform(-1.5, 1.5)
        s.line([(a, 1.3, 0.5), (a + 0.9, 1.6, 2.5)], sh(WOOD, 0.9), 0.7)
    return s.finish(pal, "target")


def shieldrack(pal):
    """A wooden frame hung with Zakarum shields - red, the gold eye, one split in two."""
    s = Spr(170, 140, seed=27)
    s.grit(140, 3.4, 1.2, [DIRT, DWOOD])
    s.pole(-2.6, 0, 40, DWOOD, 2.0)
    s.pole(2.6, 0, 40, DWOOD, 2.0)
    s.box(-2.8, -0.15, 5.6, 0.3, 3, WOOD, z=36)
    for i, x in enumerate((-1.7, 0.0, 1.7)):
        X, Y = s.p(x, 0.2, 22)
        r = 11
        d = s.d
        d.ellipse((X - r * S, Y - r * 1.15 * S, X + r * S, Y + r * 1.15 * S), fill=sh(IRON, 0.6))
        d.ellipse((X - (r - 1.5) * S, Y - (r - 1.5) * 1.15 * S, X + (r - 1.5) * S, Y + (r - 1.5) * 1.15 * S),
                  fill=sh(CLOTH_RED, 0.95))
        d.ellipse((X - 5 * S, Y - 3.5 * S, X + 5 * S, Y + 3.5 * S), fill=sh(GOLD, 0.95))
        d.ellipse((X - 2 * S, Y - 2 * S, X + 2 * S, Y + 2 * S), fill=sh(CLOTH_RED, 0.5))
        d.line([(X, Y - 12 * S), s.p(x, 0, 36)], fill=sh(LEATHER, 0.8), width=S)
        if i == 2:                                                        # the split one
            d.line([(X - 3 * S, Y - 13 * S), (X + 2 * S, Y + 13 * S)], fill=(14, 10, 8, 255), width=2 * S)
    for k in range(2):                                                    # fallen ones
        X, Y = s.p(-1.0 + k * 2.4, 1.4, 1)
        s.d.ellipse((X - 10 * S, Y - 5 * S, X + 10 * S, Y + 5 * S), fill=sh(CLOTH_RED, 0.7))
        s.d.ellipse((X - 4 * S, Y - 2 * S, X + 4 * S, Y + 2 * S), fill=sh(GOLD, 0.8))
    return s.finish(pal, "shieldrack")


def chest(pal):
    """An iron-bound strongbox, lid forced open, a few coins and a dagger spilled - long looted."""
    s = Spr(120, 100, seed=28)
    s.grit(160, 2.8, 1.4, [DIRT, (60, 50, 38)])
    s.box(-1.4, -0.8, 2.8, 1.6, 12, DWOOD)
    for f in (0.15, 0.85):                                                # iron bands
        x = -1.4 + 2.8 * f
        s.line([(x, 0.8, 0), (x, 0.8, 12)], sh(IRON, 0.9), 1.2)
        s.line([(1.4, -0.8 + 1.6 * f, 0), (1.4, -0.8 + 1.6 * f, 12)], sh(IRON, 0.7), 1.2)
    s.poly([(-1.4, -0.8, 12), (1.4, -0.8, 12), (1.4, -0.9, 26), (-1.4, -0.9, 26)], sh(DWOOD, 0.9))   # lid up
    s.poly([(-1.3, -0.6, 12.2), (1.3, -0.6, 12.2), (1.3, 0.7, 12.2), (-1.3, 0.7, 12.2)], (16, 12, 8, 255))  # empty inside
    for _ in range(8):
        s.disc(s.rnd.uniform(-0.8, 2.2), s.rnd.uniform(1.0, 1.8), 0.5, 1.4, sh(GOLD, s.rnd.uniform(0.8, 1.2)), 0.5)
    s.line([(1.6, 1.4, 0.5), (2.6, 0.9, 0.5)], sh(STEEL, 1.1), 1.0)
    return s.finish(pal, "chest")


def cauldron(pal):
    """A black cauldron on a tripod over embers, something grey bubbling, a ladle hanging off it."""
    s = Spr(120, 140, seed=29)
    s.grit(200, 2.6, 1.3, [DIRT, (30, 26, 22)])
    for _ in range(30):                                                   # the fire bed
        a, r = s.rnd.uniform(0, 2 * math.pi), s.rnd.uniform(0, 1.2)
        s.disc(math.cos(a) * r, math.sin(a) * r * 0.6, 0.5, 1.6,
               (255, 120, 30, 255) if s.rnd.random() < 0.3 else sh((40, 36, 32), s.rnd.uniform(0.7, 1.2)), 0.6)
    s.glow(0, 0, 4, 22)
    for a in (0, 2.1, 4.2):                                               # tripod
        s.line([(math.cos(a) * 1.8, math.sin(a) * 1.8, 0), (0, 0, 48)], sh(IRON, 0.7), 1.4)
    s.line([(0, 0, 48), (0, 0, 34)], sh(IRON, 0.9), 0.8)                  # chain
    X, Y = s.p(0, 0, 22)
    s.d.ellipse((X - 15 * S, Y - 10 * S, X + 15 * S, Y + 14 * S), fill=(24, 22, 22, 255))       # pot
    s.d.ellipse((X - 13 * S, Y - 9 * S, X + 4 * S, Y + 6 * S), fill=(44, 42, 42, 255))
    s.d.ellipse((X - 14 * S, Y - 13 * S, X + 14 * S, Y - 5 * S), fill=(30, 28, 26, 255))
    s.d.ellipse((X - 12 * S, Y - 12 * S, X + 12 * S, Y - 6 * S), fill=(96, 98, 80, 255))        # the stew
    for _ in range(5):
        bx, by = X + s.rnd.uniform(-8, 8) * S, Y + s.rnd.uniform(-11, -7) * S
        s.d.ellipse((bx - 1.5 * S, by - 1 * S, bx + 1.5 * S, by + 1 * S), fill=(130, 132, 110, 255))
    s.d.line([(X + 6 * S, Y - 9 * S), (X + 18 * S, Y - 22 * S)], fill=sh(DWOOD, 1.0), width=S)  # ladle
    for k in range(4):                                                    # steam
        r = (3 + k * 2) * S
        sx, sy = X + (k - 1) * 2 * S, Y - (18 + k * 7) * S
        s.d.ellipse((sx - r, sy - r * 0.7, sx + r, sy + r * 0.7), fill=(120, 120, 110, 110 - k * 20))
    return s.finish(pal, "cauldron")


def gibbet(pal):
    """A hanging cage on a gallows arm, a skeleton slumped inside - a warning at the gate."""
    s = Spr(120, 250, seed=30)
    s.grit(120, 2.0, 1.0, [DIRT, BONE])
    s.box(-0.8, -0.8, 1.6, 1.6, 6, STONE)
    s.pole(0, 0, 150, DWOOD, 2.6, z=6)
    s.line([(0, 0, 150), (2.4, -1.2, 150)], sh(DWOOD, 1.0), 2.2)          # the arm
    s.line([(0, 0, 130), (1.4, -0.7, 150)], sh(DWOOD, 0.8), 1.2)          # brace
    s.line([(2.4, -1.2, 150), (2.4, -1.2, 132)], sh(IRON, 0.8), 0.8)      # chain
    X, Y = s.p(2.4, -1.2, 92)
    d = s.d
    for k in range(7):                                                    # cage bars
        x = X + (-9 + k * 3) * S
        d.line([(x, Y - 40 * S), (x, Y)], fill=sh(IRON, 0.7 + 0.08 * k), width=S)
    for yy in (0, -20, -40):
        d.ellipse((X - 9 * S, Y + yy * S - 3 * S, X + 9 * S, Y + yy * S + 3 * S), outline=sh(IRON, 0.9), width=S)
    d.polygon([(X - 9 * S, Y - 40 * S), (X + 9 * S, Y - 40 * S), (X, Y - 47 * S)], fill=sh(IRON, 0.6))
    # the prisoner: skull drooping on the ribs, an arm through the bars
    s.skull(2.35, -1.25, 118, 0.9)
    for k in range(4):
        d.arc((X - 6 * S, Y - (27 - k * 3) * S, X + 6 * S, Y - (21 - k * 3) * S), 200, 340, fill=sh(BONE, 1.0), width=S)
    d.line([(X + 2 * S, Y - 22 * S), (X + 12 * S, Y - 8 * S)], fill=sh(BONE, 0.9), width=S)
    d.line([(X - 3 * S, Y - 8 * S), (X - 4 * S, Y - 1 * S)], fill=sh(BONE, 0.8), width=S)
    for _ in range(3):                                                    # crows' leavings below
        s.bone(s.rnd.uniform(1.2, 2.8), s.rnd.uniform(-0.6, 0.2), s.rnd.uniform(1.6, 3.2), s.rnd.uniform(-0.2, 0.6), 0.5, 1.2)
    return s.finish(pal, "gibbet")


def spikes(pal):
    """Sharpened stakes in a row, heads of the fallen guard on three of them."""
    s = Spr(170, 160, seed=31)
    s.grit(200, 3.6, 1.4, [DIRT, BLOOD, (40, 34, 28)])
    xs = [-2.6, -1.7, -0.8, 0.1, 1.0, 1.9, 2.8]
    for i, x in enumerate(xs):
        h = 40 + (i * 7) % 13
        s.line([(x, -0.2, 0), (x + 0.1, -0.2, h)], sh(DWOOD, 0.8), 2.4)
        s.line([(x - 0.04, -0.2, 0), (x + 0.06, -0.2, h)], sh(WOOD, 1.0), 1.0)
        s.poly([(x - 0.08, -0.2, h), (x + 0.18, -0.2, h), (x + 0.1, -0.2, h + 8)], sh(WOOD, 0.8))
        if i in (1, 3, 5):
            X, Y = s.p(x + 0.1, -0.2, h + 2)
            s.d.ellipse((X - 6 * S, Y - 11 * S, X + 6 * S, Y + 1 * S), fill=sh((120, 96, 80), 0.75))   # head
            s.d.ellipse((X - 5 * S, Y - 11 * S, X + 2 * S, Y - 3 * S), fill=sh((140, 110, 92), 0.85))
            s.d.ellipse((X - 4 * S, Y - 7 * S, X - 1 * S, Y - 5 * S), fill=(16, 10, 8, 255))
            s.d.ellipse((X + 1 * S, Y - 7 * S, X + 4 * S, Y - 5 * S), fill=(16, 10, 8, 255))
            s.d.line([(X - 2 * S, Y - 2 * S), (X + 2 * S, Y - 2 * S)], fill=(40, 10, 8, 255), width=S)
            for _ in range(5):                                            # blood running down the stake
                ry = s.rnd.uniform(4, 20)
                s.d.line([(X + s.rnd.uniform(-1, 1) * S, Y), (X + s.rnd.uniform(-1, 1) * S, Y + ry * S)],
                         fill=sh(BLOOD, 1.0), width=S)
    for _ in range(10):
        s.disc(s.rnd.uniform(-2.4, 2.8), s.rnd.uniform(0.2, 1.2), 0, s.rnd.uniform(2, 4), sh(BLOOD, 0.8), 0.5)
    return s.finish(pal, "spikes")


def sacks(pal):
    """Grain sacks heaped against a crate, one slit open and spilling, a rat-gnawed hole."""
    s = Spr(150, 110, seed=32)
    s.grit(220, 3.4, 1.6, [DIRT, STRAW, (150, 130, 90)])
    s.planks(0.8, -1.0, 1.8, 1.6, 16, WOOD)
    SACK = (128, 110, 80)
    for x, y, z, r in ((-1.6, 0.2, 0, 11), (-0.2, 0.6, 0, 12), (-1.0, -0.6, 0, 10), (-0.9, 0.0, 14, 10), (1.5, 1.2, 0, 9)):
        X, Y = s.p(x, y, z + r * 0.7)
        s.d.ellipse((X - r * S, Y - r * 0.75 * S, X + r * S, Y + r * 0.75 * S), fill=sh(SACK, 0.65))
        s.d.ellipse((X - r * 0.95 * S, Y - r * 0.75 * S, X + r * 0.45 * S, Y + r * 0.4 * S), fill=sh(SACK, 0.95))
        s.d.line([(X + r * 0.6 * S, Y - r * 0.6 * S), (X + r * 0.95 * S, Y - r * 0.95 * S)], fill=sh(SACK, 0.5), width=2 * S)  # tied neck
    for _ in range(60):                                                   # spilt grain
        s.disc(s.rnd.uniform(0.6, 2.6), s.rnd.uniform(1.3, 2.1), 0.3, 0.8, sh((190, 170, 110), s.rnd.uniform(0.7, 1.1)), 0.6)
    X, Y = s.p(-0.2, 0.6, 6)
    s.d.ellipse((X + 2 * S, Y, X + 6 * S, Y + 3 * S), fill=(14, 10, 8, 255))   # the gnawed hole
    return s.finish(pal, "sacks")


SPRITES2 = [statue, bunks, table, kegs, grindstone, target, shieldrack, chest, cauldron, gibbet, spikes, sacks]


SPRITES = [anvil, forge, weaponrack, armorstand, crates, arrows, dummy, debris, banner, cart, bones, blood] + SPRITES2


def main(path):
    sys.path.insert(0, ROOT)
    from d2.source import open_source
    from d2.palette import load_palette
    src = open_source(path)
    pal = load_palette(src.read("data\\global\\palette\\act3\\pal.dat"))
    for f in SPRITES:
        f(pal)
        print("drew", f.__name__)
    import json
    with open(os.path.join(OUT, "anchors.json"), "w") as fh:
        json.dump(ANCHORS, fh, indent=1)
    # the hand-made sprite sheets (assets/decor_src) replace these drawings where they exist
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import import_sprites
    import_sprites.main(path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "")
