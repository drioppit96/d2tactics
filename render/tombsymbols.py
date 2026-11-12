"""The seven Horadric symbols of Tal Rasha's tombs (Canyon of the Magi).

Each tomb entrance carries one; Horazon's Journal shows the true tomb's symbol in the quest log.
The shapes follow D2's own seven glyphs - notched ring, crescent, square, pinwheel, chevron,
triangle, bullseye - drawn as line work so they stay crisp at any size: a pale carved glyph on a
dark outline, the way they are cut into the tomb lintels."""
import math

import pygame

NAMES = ["Ring", "Crescent", "Square", "Pinwheel", "Chevron", "Triangle", "Bullseye"]
GOLD = (226, 190, 110)
DARK = (25, 18, 8)


def symbol_of(level_id):
    """Tomb level 66..72 -> symbol index 0..6."""
    return (int(level_id) - 66) % 7


def _arc(cx, cy, r, a0, a1, step=10):
    n = max(2, int(abs(a1 - a0) / step) + 1)
    return [(cx + math.cos(math.radians(a0 + (a1 - a0) * k / (n - 1.0))) * r,
             cy + math.sin(math.radians(a0 + (a1 - a0) * k / (n - 1.0))) * r) for k in range(n)]


def _paths(i, cx, cy, r):
    """Drawing ops for symbol i, centred on (cx, cy), radius r.

    Each op is (kind, points): True = closed polyline, False = open polyline,
    "dot" = filled circles at the points, "thin" = a half-width open polyline."""
    if i == 0:                                      # ring with the notched inner band
        out = [(True, _arc(cx, cy, r, 0, 360, 12)), ("thin", _arc(cx, cy, r * 0.58, 0, 360, 12))]
        for k in range(14):                         # the ticks cut into the band between them
            a = math.radians(k * (360.0 / 14))
            out.append(("thin", [(cx + math.cos(a) * r * 0.60, cy + math.sin(a) * r * 0.60),
                                 (cx + math.cos(a) * r * 0.76, cy + math.sin(a) * r * 0.76)]))
        return out
    if i == 1:                                      # crescent, horns up, under a thin arc
        outer = _arc(cx, cy + r * 0.04, r, 0, 180, 8)
        inner = _arc(cx, cy - r * 0.34, r * 0.98, 180, 0, 8)
        return [(True, outer + inner), ("thin", _arc(cx, cy - r * 0.02, r * 1.14, 24, 156, 8))]
    if i == 2:                                      # square frame with two upright bars
        q = r * 0.86
        sq = [(cx - q, cy - q), (cx + q, cy - q), (cx + q, cy + q), (cx - q, cy + q)]
        inn = r * 0.40
        return [(True, sq),
                (False, [(cx - inn, cy - q), (cx - inn, cy + q)]),
                (False, [(cx + inn, cy - q), (cx + inn, cy + q)]),
                ("thin", [(cx - q, cy - q * 0.62), (cx + q, cy - q * 0.62)]),
                ("thin", [(cx - q, cy + q * 0.62), (cx + q, cy + q * 0.62)])]
    if i == 3:                                      # five bladed pinwheel
        out = []
        for k in range(5):
            a = math.radians(-90 + k * 72)
            tip = (cx + math.cos(a) * r, cy + math.sin(a) * r)
            b = a + math.radians(26)
            mid = (cx + math.cos(b) * r * 0.54, cy + math.sin(b) * r * 0.54)
            hub = (cx + math.cos(a - math.radians(30)) * r * 0.20,
                   cy + math.sin(a - math.radians(30)) * r * 0.20)
            out.append((True, [hub, mid, tip]))
        return out
    if i == 4:                                      # nested chevrons over a small diamond
        def vee(w, h, y0):
            return [(cx - w, cy - h + y0), (cx, cy + h + y0), (cx + w, cy - h + y0)]
        d = r * 0.16
        return [(False, vee(r * 0.92, r * 0.78, -r * 0.05)),
                (False, vee(r * 0.60, r * 0.46, -r * 0.14)),
                (True, [(cx, cy - r * 0.62 - d), (cx + d, cy - r * 0.62),
                        (cx, cy - r * 0.62 + d), (cx - d, cy - r * 0.62)])]
    if i == 5:                                      # triangle inside a triangle
        tri = lambda k: [(cx + math.cos(math.radians(-90 + j * 120)) * r * k,
                          cy + math.sin(math.radians(-90 + j * 120)) * r * k) for j in range(3)]
        return [(True, tri(1.0)), ("thin", tri(0.58))]
    # bullseye: heavy ring around a solid centre
    return [(True, _arc(cx, cy, r * 0.94, 0, 360, 12)), ("dot", [(cx, cy)])]


_DOT_R = {3: 0.14, 6: 0.26}


def draw(surf, i, cx, cy, r, color=GOLD, width=None, glow=False):
    """Draw symbol i at (cx, cy) with radius r (screen pixels)."""
    w = width or max(2, int(r / 5))
    if glow:
        g = pygame.Surface((int(r * 3), int(r * 3)), pygame.SRCALPHA)
        pygame.draw.circle(g, (255, 200, 90, 50), (int(r * 1.5), int(r * 1.5)), int(r * 1.45))
        surf.blit(g, (int(cx - r * 1.5), int(cy - r * 1.5)))
    for col, grow in ((DARK, 3), (color, 0)):
        for kind, pts in _paths(i, cx, cy, r):
            if kind == "dot":
                for p in pts:
                    pygame.draw.circle(surf, col, (int(p[0]), int(p[1])),
                                       max(2, int(r * _DOT_R.get(i, 0.22)) + (grow // 2)))
                continue
            ww = max(1, (w // 2 if kind == "thin" else w) + grow)
            ip = [(int(x), int(y)) for x, y in pts]
            pygame.draw.lines(surf, col, kind is True, ip, ww)
