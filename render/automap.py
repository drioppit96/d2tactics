"""D2-style automap: thin light lines along the walls of everything you have explored.

Tab cycles: full map over the screen (centred on you, like D2) -> small map in the
corner -> off. The map is stored in 512x512 chunks so even the whole outdoor act
(about 1000 x 1600 cells) costs only the memory of what you have explored.
"""
import pygame

from game.grid import WALL

LINE = (210, 200, 175, 235)
EXIT_C = (240, 210, 90)
NPC_C = (90, 170, 255)
WP_C = (120, 160, 255)
HW, HH = 4, 2        # half-size of one cell on the map (cell = 8 x 4 px)
CHUNK = 512


class Automap:
    def __init__(self, world):
        self.world = world
        g = world.grid
        self.ox = g.h * HW + 4
        self.chunks = {}
        cells = getattr(g, "explored_cells", None)
        if cells is None:
            cells = [(x, y) for y in range(g.h) for x in range(g.w) if g.explored[y][x]]
        for x, y in cells:
            self._plot(x, y)
        g.new_explored = []

    def to_map(self, x, y):
        return (x - y) * HW + self.ox, (x + y) * HH + 4

    def _chunk(self, key):
        c = self.chunks.get(key)
        if c is None:
            c = self.chunks[key] = pygame.Surface((CHUNK, CHUNK), pygame.SRCALPHA)
            c.fill((0, 0, 0, 0))
        return c

    def _line(self, a, b):
        keys = {(int(a[0]) // CHUNK, int(a[1]) // CHUNK), (int(b[0]) // CHUNK, int(b[1]) // CHUNK)}
        for kx, ky in keys:
            surf = self._chunk((kx, ky))
            ox, oy = kx * CHUNK, ky * CHUNK
            pygame.draw.line(surf, LINE, (a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy), 1)

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
                self._line(a, b)

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

    def _blit_region(self, surf, ox, oy, view):
        """Blit the chunks overlapping view (map-space rect) at screen offset (ox, oy)."""
        x0, y0 = int(view.x) // CHUNK, int(view.y) // CHUNK
        x1, y1 = int(view.right) // CHUNK, int(view.bottom) // CHUNK
        for ky in range(y0, y1 + 1):
            for kx in range(x0, x1 + 1):
                c = self.chunks.get((kx, ky))
                if c is not None:
                    surf.blit(c, (int(ox + kx * CHUNK), int(oy + ky * CHUNK)))

    def _markers(self, surf, ox, oy, k, clip):
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
            p = (int(ox + mx * k), int(oy + my * k))
            if clip.collidepoint(p):
                pygame.draw.circle(surf, EXIT_C, p, max(2, int(2.5 * k)), 1)
        for (x, y) in getattr(w, "waypoints", {}):
            if w.grid.explored[y][x]:
                mx, my = self.to_map(x, y)
                p = (int(ox + mx * k), int(oy + my * k))
                if clip.collidepoint(p):
                    pygame.draw.rect(surf, WP_C, (p[0] - 3, p[1] - 2, 7, 5), 1)
        for m in w.npcs:
            if w.grid.explored[m.y][m.x]:
                mx, my = self.to_map(m.x, m.y)
                p = (int(ox + mx * k), int(oy + my * k))
                if clip.collidepoint(p):
                    pygame.draw.circle(surf, NPC_C, p, max(1, int(1.5 * k)))
        mx, my = self.to_map(*w.player.pos)
        px, py = int(ox + mx * k), int(oy + my * k)
        r = max(3, int(4 * k))
        pygame.draw.line(surf, (255, 255, 255), (px - r, py), (px + r, py), 2)
        pygame.draw.line(surf, (255, 255, 255), (px, py - r // 2 - 1), (px, py + r // 2 + 1), 2)

    def draw_full(self, surf, centre, k=1.0):
        self.update()
        mx, my = self.to_map(*self.world.player.pos)
        ox, oy = centre[0] - mx * k, centre[1] - my * k
        W, H = surf.get_size()
        view = pygame.Rect(int(-ox), int(-oy), W, H)
        self._blit_region(surf, ox, oy, view)
        self._markers(surf, ox, oy, k, surf.get_rect())

    def draw_mini(self, surf, rect):
        self.update()
        mx, my = self.to_map(*self.world.player.pos)
        k = 0.5
        src = pygame.Rect(int(mx - rect.w / k / 2), int(my - rect.h / k / 2), int(rect.w / k), int(rect.h / k))
        part = pygame.Surface(src.size, pygame.SRCALPHA)
        part.fill((0, 0, 0, 0))
        self._blit_region(part, -src.x, -src.y, src)
        small = pygame.transform.smoothscale(part, rect.size)
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        bg.fill((0, 0, 0, 110))
        surf.blit(bg, rect.topleft)
        surf.blit(small, rect.topleft)
        old = surf.get_clip()
        surf.set_clip(rect)
        self._markers(surf, rect.x - src.x * k, rect.y - src.y * k, k, rect)
        surf.set_clip(old)
