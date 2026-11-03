"""The seven Horadric symbols of Tal Rasha's tombs (Canyon of the Magi).

Each tomb entrance carries one; Horazon's Journal shows the true tomb's symbol in the quest log.
Drawn with plain lines so they work at any size: a carved gold glyph with a dark outline."""
import math

import pygame

NAMES = ["Crescent", "Triangle", "Eye", "Square", "Star", "Cross", "Spiral"]
GOLD = (226, 190, 110)
DARK = (25, 18, 8)


def symbol_of(level_id):
    """Tomb level 66..72 -> symbol index 0..6."""
    return (int(level_id) - 66) % 7


def _paths(i, cx, cy, r):
    """Polylines (closed?, points) for symbol i, centred on (cx, cy), radius r."""
    P = lambda a, rr=1.0: (cx + math.cos(a) * r * rr, cy + math.sin(a) * r * rr)
    if i == 0:      # crescent
        outer = [P(math.radians(a)) for a in range(60, 301, 15)]
        inner = [(cx + r * 0.35 + math.cos(math.radians(a)) * r * 0.75,
                  cy + math.sin(math.radians(a)) * r * 0.75) for a in range(300, 59, -15)]
        return [(True, outer + inner)]
    if i == 1:      # triangle with a dot
        pts = [P(math.radians(-90 + k * 120)) for k in range(3)]
        return [(True, pts), ("dot", [(cx, cy + r * 0.1)])]
    if i == 2:      # eye
        top = [(cx - r + 2 * r * t / 10.0, cy - math.sin(math.pi * t / 10.0) * r * 0.6) for t in range(11)]
        bot = [(cx + r - 2 * r * t / 10.0, cy + math.sin(math.pi * t / 10.0) * r * 0.6) for t in range(11)]
        return [(True, top + bot), ("dot", [(cx, cy)])]
    if i == 3:      # square in a diamond
        d = [P(math.radians(a)) for a in (-90, 0, 90, 180)]
        q = r * 0.42
        s = [(cx - q, cy - q), (cx + q, cy - q), (cx + q, cy + q), (cx - q, cy + q)]
        return [(True, d), (True, s)]
    if i == 4:      # five-pointed star
        pts = [P(math.radians(-90 + k * 144)) for k in range(5)]
        return [(True, pts)]
    if i == 5:      # cross in a circle
        circ = [P(math.radians(a)) for a in range(0, 360, 20)]
        return [(True, circ), (False, [P(math.radians(-45)), P(math.radians(135))]),
                (False, [P(math.radians(45)), P(math.radians(-135))])]
    # spiral
    pts = []
    for k in range(0, 50):
        a = k * 0.32
        rr = 0.12 + 0.88 * k / 49.0
        pts.append((cx + math.cos(a) * r * rr, cy + math.sin(a) * r * rr))
    return [(False, pts)]


def draw(surf, i, cx, cy, r, color=GOLD, width=None, glow=False):
    """Draw symbol i at (cx, cy) with radius r (screen pixels)."""
    w = width or max(2, int(r / 6))
    if glow:
        g = pygame.Surface((int(r * 3), int(r * 3)), pygame.SRCALPHA)
        pygame.draw.circle(g, (255, 200, 90, 50), (int(r * 1.5), int(r * 1.5)), int(r * 1.45))
        surf.blit(g, (int(cx - r * 1.5), int(cy - r * 1.5)))
    for col, ww in ((DARK, w + 3), (color, w)):
        for closed, pts in _paths(i, cx, cy, r):
            if closed == "dot":
                for p in pts:
                    pygame.draw.circle(surf, col, (int(p[0]), int(p[1])), max(2, int(ww * 0.9)))
                continue
            ip = [(int(x), int(y)) for x, y in pts]
            pygame.draw.lines(surf, col, bool(closed), ip, ww)
