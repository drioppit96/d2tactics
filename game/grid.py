"""Map grid, pathfinding and line of sight.

One grid cell corresponds to one Diablo 2 "subtile" (a D2 floor tile is 5x5 cells),
so real D2 tile maps can later be laid onto this grid without conversion.
"""
import heapq

FLOOR = 0
WALL = 1

# 8 directions, D2 style movement
DIRS8 = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]


def chebyshev(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class Grid:
    def __init__(self, width, height, fill=WALL):
        self.w = width
        self.h = height
        self.cells = [[fill] * width for _ in range(height)]
        self.explored = [[False] * width for _ in range(height)]
        self.visible = [[False] * width for _ in range(height)]
        self.new_explored = []       # cells revealed since the minimap last looked
        self._lit = []               # cells marked visible last time (cleared cheaply)
        self.explored_cells = []     # every explored cell, in order (the automap redraws from it)

    def in_bounds(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def walkable(self, x, y):
        return self.in_bounds(x, y) and self.cells[y][x] == FLOOR

    def neighbors(self, x, y):
        for dx, dy in DIRS8:
            nx, ny = x + dx, y + dy
            if not self.walkable(nx, ny):
                continue
            # no diagonal corner cutting past walls
            if dx and dy and (not self.walkable(x + dx, y) or not self.walkable(x, y + dy)):
                continue
            yield nx, ny

    def find_path(self, start, goal, blocked=frozenset(), max_cost=None, allow_goal_blocked=False, limit=60000):
        """A* path from start to goal (exclusive of start). Returns list of cells or None.

        blocked: cells occupied by units. allow_goal_blocked lets you path *next to* a unit:
        the goal itself may be occupied, and the caller drops the last step.
        """
        if start == goal:
            return []
        if not self.walkable(*goal) or (goal in blocked and not allow_goal_blocked):
            return None             # (searching the whole map for a cell nobody can stand on is slow)
        open_heap = [(chebyshev(start, goal), 0, start)]
        came = {start: None}
        cost = {start: 0}
        expanded = 0
        while open_heap:
            _, g, cur = heapq.heappop(open_heap)
            expanded += 1
            if expanded > limit:
                return None          # big outdoor maps: give up instead of searching everything
            if cur == goal:
                path = []
                while cur != start:
                    path.append(cur)
                    cur = came[cur]
                path.reverse()
                return path
            if g > cost.get(cur, 1 << 30):
                continue
            for nb in self.neighbors(*cur):
                if nb in blocked and not (allow_goal_blocked and nb == goal):
                    continue
                ng = g + 1
                if max_cost is not None and ng > max_cost:
                    continue
                if ng < cost.get(nb, 1 << 30):
                    cost[nb] = ng
                    came[nb] = cur
                    # tiny tie-breaker favours straight lines, looks nicer
                    h = chebyshev(nb, goal) + 0.001 * (abs(nb[0] - goal[0]) + abs(nb[1] - goal[1]))
                    heapq.heappush(open_heap, (ng + h, ng, nb))
        return None

    def reachable(self, start, max_cost, blocked=frozenset()):
        """All cells reachable within max_cost steps -> {cell: cost}. Used to show move range."""
        dist = {start: 0}
        frontier = [start]
        while frontier:
            nxt = []
            for cur in frontier:
                d = dist[cur]
                if d >= max_cost:
                    continue
                for nb in self.neighbors(*cur):
                    if nb in blocked or nb in dist:
                        continue
                    dist[nb] = d + 1
                    nxt.append(nb)
            frontier = nxt
        return dist

    def line_of_sight(self, a, b):
        """Bresenham line; walls between a and b block sight (endpoints don't)."""
        x0, y0 = a
        x1, y1 = b
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while (x0, y0) != (x1, y1):
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
            if (x0, y0) != (x1, y1) and not self.walkable(x0, y0):
                return False
        return True

    def update_visibility(self, origin, radius):
        """What you can see: rays from you to the edge of the radius, stopped by walls.
        (Casting rays is far cheaper than a line-of-sight test per cell, so the radius can be a
        whole screen.)"""
        vis = self.visible
        for x, y in self._lit:
            vis[y][x] = False
        lit = self._lit = []
        ox, oy = origin
        if not self.in_bounds(ox, oy):
            return
        explored, cells, w, h = self.explored, self.cells, self.w, self.h
        r2 = radius * radius
        new = self.new_explored
        allc = self.explored_cells

        def mark(x, y):
            if not vis[y][x]:
                vis[y][x] = True
                lit.append((x, y))
                if not explored[y][x]:
                    explored[y][x] = True
                    new.append((x, y))
                    allc.append((x, y))
        mark(ox, oy)
        ends = []
        for i in range(-radius, radius + 1):
            ends += [(ox + i, oy - radius), (ox + i, oy + radius), (ox - radius, oy + i), (ox + radius, oy + i)]
        for x1, y1 in ends:
            x0, y0 = ox, oy
            dx, dy = abs(x1 - x0), -abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1
            err = dx + dy
            while (x0, y0) != (x1, y1):
                e2 = 2 * err
                if e2 >= dy:
                    err += dy
                    x0 += sx
                if e2 <= dx:
                    err += dx
                    y0 += sy
                if not (0 <= x0 < w and 0 <= y0 < h) or (x0 - ox) ** 2 + (y0 - oy) ** 2 > r2:
                    break
                mark(x0, y0)
                if cells[y0][x0] == WALL:
                    break
        # reveal the walls bordering visible floor too
        for x, y in list(lit):
            if cells[y][x] == WALL:
                continue
            for ddx, ddy in DIRS8:
                nx, ny = x + ddx, y + ddy
                if 0 <= nx < w and 0 <= ny < h and cells[ny][nx] == WALL:
                    mark(nx, ny)
