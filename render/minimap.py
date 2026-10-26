"""Automap: fills in as you explore. Small corner map always, big overlay on Tab (like D2)."""
import pygame

from game.grid import WALL, DIRS8

FLOOR_C = (52, 44, 34, 255)
EDGE_C = (190, 180, 150, 255)
EXIT_C = (240, 210, 90)
NPC_C = (90, 200, 255)


class Minimap:
    def __init__(self, world):
        self.world = world
        g = world.grid
        self.ox = g.h                        # iso projection: 2px wide, 1px tall per cell
        self.surf = pygame.Surface(((g.w + g.h) * 2 + 4, (g.w + g.h) + 4), pygame.SRCALPHA)
        self.surf.fill((0, 0, 0, 0))
        # everything already explored (e.g. after re-entering a level)
        for y in range(g.h):
            for x in range(g.w):
                if g.explored[y][x]:
                    self._plot(x, y)
        g.new_explored = []

    def to_map(self, x, y):
        return (x - y) * 2 + self.ox * 2, (x + y)

    def _plot(self, x, y):
        g = self.world.grid
        px, py = self.to_map(x, y)
        if g.cells[y][x] == WALL:
            near_floor = any(g.walkable(x + dx, y + dy) for dx, dy in DIRS8)
            if near_floor:
                self.surf.fill(EDGE_C, (px, py, 2, 1))
        else:
            self.surf.fill(FLOOR_C, (px, py, 2, 1))

    def update(self):
        g = self.world.grid
        if g.new_explored:
            for x, y in g.new_explored:
                self._plot(x, y)
            g.new_explored = []

    def _markers(self, surf, ox, oy, k):
        w = self.world
        done = set()
        for (x, y), target in w.exits.items():
            if not w.grid.explored[y][x]:
                continue
            key = (x // 6, y // 6)
            if key in done:
                continue
            done.add(key)
            px, py = self.to_map(x, y)
            pygame.draw.circle(surf, EXIT_C, (int(ox + px * k), int(oy + py * k)), max(2, int(2 * k)))
        for m in w.npcs:
            if w.grid.explored[m.y][m.x]:
                px, py = self.to_map(m.x, m.y)
                pygame.draw.circle(surf, NPC_C, (int(ox + px * k), int(oy + py * k)), max(2, int(1.5 * k)))
        px, py = self.to_map(*w.player.pos)
        pygame.draw.circle(surf, (255, 255, 255), (int(ox + px * k), int(oy + py * k)), max(2, int(2 * k)))
        pygame.draw.circle(surf, (220, 40, 40), (int(ox + px * k), int(oy + py * k)), max(1, int(1.2 * k)))

    def draw_corner(self, surf, rect):
        """Small map in a box, centred on the player."""
        self.update()
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        bg.fill((0, 0, 0, 150))
        surf.blit(bg, rect.topleft)
        px, py = self.to_map(*self.world.player.pos)
        src = pygame.Rect(int(px - rect.w / 2), int(py - rect.h / 2), rect.w, rect.h)
        clip = surf.get_clip()
        surf.set_clip(rect)
        surf.blit(self.surf, (rect.x - src.x, rect.y - src.y))
        self._markers(surf, rect.x - src.x, rect.y - src.y, 1)
        surf.set_clip(clip)
        pygame.draw.rect(surf, (92, 78, 52), rect, 1)

    def draw_overlay(self, surf, k=2):
        """Big see-through map over the screen, centred on the player (D2's Tab automap)."""
        self.update()
        W, H = surf.get_size()
        px, py = self.to_map(*self.world.player.pos)
        big = pygame.transform.scale(self.surf, (self.surf.get_width() * k, self.surf.get_height() * k))
        big.set_alpha(190)
        ox, oy = W / 2 - px * k, (H - 120) / 2 - py * k
        surf.blit(big, (int(ox), int(oy)))
        self._markers(surf, ox, oy, k)
