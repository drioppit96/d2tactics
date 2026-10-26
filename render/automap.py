"""D2-style automap: thin light lines along the walls of everything you have explored.

Tab cycles: full map over the screen (centred on you, like D2) -> small map in the
corner -> off.
"""
import pygame

from game.grid import WALL

LINE = (210, 200, 175, 235)
EXIT_C = (240, 210, 90)
NPC_C = (90, 170, 255)
HW, HH = 4, 2        # half-size of one cell on the map (cell = 8 x 4 px)


class Automap:
    def __init__(self, world):
        self.world = world
        g = world.grid
        self.ox = g.h * HW + 4
        self.surf = pygame.Surface(((g.w + g.h) * HW + 8, (g.w + g.h) * HH + 8), pygame.SRCALPHA)
        self.surf.fill((0, 0, 0, 0))
        for y in range(g.h):
            for x in range(g.w):
                if g.explored[y][x]:
                    self._plot(x, y)
        g.new_explored = []

    def to_map(self, x, y):
        return (x - y) * HW + self.ox, (x + y) * HH + 4

    def _plot(self, x, y):
        g = self.world.grid
        if g.cells[y][x] == WALL:
            return
        cx, cy = self.to_map(x, y)
        top, right, bottom, left = (cx, cy - HH), (cx + HW, cy), (cx, cy + HH), (cx - HW, cy)
        # draw the diamond edges that face a wall (shared edges listed by neighbour)
        for (nx, ny), a, b in (((x, y - 1), top, right), ((x + 1, y), right, bottom),
                               ((x, y + 1), bottom, left), ((x - 1, y), left, top)):
            if not g.walkable(nx, ny):
                pygame.draw.line(self.surf, LINE, a, b, 1)

    def update(self):
        g = self.world.grid
        if g.new_explored:
            for x, y in g.new_explored:
                self._plot(x, y)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if g.in_bounds(nx, ny) and g.explored[ny][nx]:
                        self._plot(nx, ny)
            g.new_explored = []

    def _markers(self, surf, ox, oy, k):
        w = self.world
        done = set()
        for (x, y), target in w.exits.items():
            if not target or not w.grid.explored[y][x]:
                continue
            key = (x // 8, y // 8)
            if key in done:
                continue
            done.add(key)
            mx, my = self.to_map(x, y)
            pygame.draw.circle(surf, EXIT_C, (int(ox + mx * k), int(oy + my * k)), max(2, int(2.5 * k)), 1)
        for m in w.npcs:
            if w.grid.explored[m.y][m.x]:
                mx, my = self.to_map(m.x, m.y)
                pygame.draw.circle(surf, NPC_C, (int(ox + mx * k), int(oy + my * k)), max(1, int(1.5 * k)))
        mx, my = self.to_map(*w.player.pos)
        px, py = int(ox + mx * k), int(oy + my * k)
        r = max(3, int(4 * k))
        pygame.draw.line(surf, (255, 255, 255), (px - r, py), (px + r, py), 2)
        pygame.draw.line(surf, (255, 255, 255), (px, py - r // 2 - 1), (px, py + r // 2 + 1), 2)

    def draw_full(self, surf, centre, k=1.0):
        self.update()
        mx, my = self.to_map(*self.world.player.pos)
        ox, oy = centre[0] - mx * k, centre[1] - my * k
        surf.blit(self.surf, (int(ox), int(oy)))
        self._markers(surf, ox, oy, k)

    def draw_mini(self, surf, rect):
        self.update()
        mx, my = self.to_map(*self.world.player.pos)
        k = 0.5
        src = pygame.Rect(int(mx - rect.w / k / 2), int(my - rect.h / k / 2), int(rect.w / k), int(rect.h / k))
        part = pygame.Surface(src.size, pygame.SRCALPHA)
        part.fill((0, 0, 0, 0))
        part.blit(self.surf, (-src.x, -src.y))
        small = pygame.transform.smoothscale(part, rect.size)
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        bg.fill((0, 0, 0, 110))
        surf.blit(bg, rect.topleft)
        surf.blit(small, rect.topleft)
        self._markers(surf, rect.x - src.x * k, rect.y - src.y * k, k)
