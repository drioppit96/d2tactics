"""Isometric projection. Same proportions as Diablo 2: one cell (a D2 subtile) is a
32x16 pixel diamond, and a full D2 floor tile (160x80) covers 5x5 cells."""

TILE_W = 32
TILE_H = 16
HALF_W = TILE_W / 2
HALF_H = TILE_H / 2


def cell_to_world(x, y):
    """Centre of a cell in world pixels (x, y may be fractional while animating)."""
    return (x - y) * HALF_W, (x + y) * HALF_H


class Camera:
    def __init__(self, screen_w, screen_h, scale=2.0):
        self.sw, self.sh = screen_w, screen_h
        self.scale = scale
        self.wx = 0.0
        self.wy = 0.0

    def resize(self, w, h):
        self.sw, self.sh = w, h

    def follow(self, wx, wy, dt, stiffness=8.0):
        k = min(1.0, dt * stiffness)
        self.wx += (wx - self.wx) * k
        self.wy += (wy - self.wy) * k

    def snap(self, wx, wy):
        self.wx, self.wy = wx, wy

    def to_screen(self, wx, wy):
        return ((wx - self.wx) * self.scale + self.sw / 2,
                (wy - self.wy) * self.scale + self.sh / 2)

    def cell_to_screen(self, x, y):
        return self.to_screen(*cell_to_world(x, y))

    def screen_to_cell(self, sx, sy):
        wx = (sx - self.sw / 2) / self.scale + self.wx
        wy = (sy - self.sh / 2) / self.scale + self.wy
        fx = (wx / HALF_W + wy / HALF_H) / 2
        fy = (wy / HALF_H - wx / HALF_W) / 2
        return int(round(fx)), int(round(fy))

    def visible_cell_range(self, grid, margin=4):
        """Bounding box of cells that can appear on screen."""
        corners = [self.screen_to_cell(0, 0), self.screen_to_cell(self.sw, 0),
                   self.screen_to_cell(0, self.sh), self.screen_to_cell(self.sw, self.sh)]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        return (max(0, min(xs) - margin), max(0, min(ys) - margin),
                min(grid.w - 1, max(xs) + margin), min(grid.h - 1, max(ys) + margin + 3))
