"""Plays world events back as animations and draws the map."""
import math

import pygame

from game.grid import WALL
from .iso import cell_to_world

# D2 animation mode codes, so real DCC animations can be mapped 1:1 later:
# NU neutral, WL walk, A1 attack, SC cast, GH get hit, DD death, DT dead


class UnitView:
    def __init__(self, unit):
        self.unit = unit
        self.rx, self.ry = float(unit.x), float(unit.y)
        self.mode = "DT" if not unit.alive else "NU"
        self.t = 0.0
        self.dur = 0.0
        self.path = []
        self.speed = 8.0
        self.flash = 0.0
        self.shown_hp = unit.hp
        self.facing = unit.facing
        self.lunge_to = None
        self.slide = None

    @property
    def dead(self):
        return self.mode in ("DD", "DT")

    def busy(self):
        return bool(self.path) or self.slide is not None or self.mode in ("A1", "SC", "DD")


class FloatText:
    def __init__(self, text, color, wx, wy, big=False):
        self.text, self.color = text, color
        self.wx, self.wy = wx, wy
        self.t = 0.0
        self.big = big


class Projectile:
    def __init__(self, kind, src, dst):
        self.kind = kind
        self.src, self.dst = src, dst
        d = math.hypot(dst[0] - src[0], dst[1] - src[1])
        self.dur = 0.08 + d * 0.045
        self.t = 0.0

    def pos(self):
        k = min(1.0, self.t / self.dur)
        return self.src[0] + (self.dst[0] - self.src[0]) * k, self.src[1] + (self.dst[1] - self.src[1]) * k


class Scene:
    def __init__(self, world, assets, fonts):
        self.world = world
        self.assets = assets
        self.fonts = fonts
        self.views = {}
        self.queue = []
        self.current = None
        self.wait = 0.0
        self.floats = []
        self.projectiles = []
        self.items_shown = set()
        self.log = []
        self.banner = None       # (text, color, time left)
        self.speed = 1.0
        self.show_grid = False
        self.show_labels = False
        self.flags = set()       # game_over / victory
        self.clock = 0.0
        self.drop_time = {}
        self.bar_lift = getattr(assets, 'bar_lift', 0)   # taller real sprites -> bars higher
        for u in [world.player] + world.monsters:
            self.views[id(u)] = UnitView(u)

    def view(self, unit):
        v = self.views.get(id(unit))
        if v is None:
            v = self.views[id(unit)] = UnitView(unit)
        return v

    # ------------------------------------------------------------ event intake
    def pull_events(self):
        if self.world.events:
            self.queue.extend(self.world.events)
            self.world.events.clear()

    def idle(self):
        return not self.queue and self.current is None and self.wait <= 0 and \
            not self.projectiles and not any(v.busy() for v in self.views.values())

    def _seen(self, unit, cells=()):
        g = self.world.grid
        if unit.is_player:
            return True
        cand = [unit.pos] + list(cells)
        return any(g.visible[c[1]][c[0]] for c in cand)

    def _start(self, ev):
        """Begin playing one event. Returns seconds to wait before the next one."""
        kind = ev[0]
        if kind == "log":
            self.log.append([ev[1], ev[2], 0.0])
            self.log = self.log[-60:]
            return 0
        if kind == "move":
            unit, cells = ev[1], ev[2]
            v = self.view(unit)
            if not cells:
                return 0
            if not self._seen(unit, cells):
                v.rx, v.ry = cells[-1]
                return 0
            v.path = list(cells)
            v.mode = "WL"
            v.speed = 7.0 if unit.is_player else 9.0
            return None   # wait until the walk finishes
        if kind == "attack":
            unit, target, skill = ev[1], ev[2], ev[3]
            v = self.view(unit)
            v.facing = (max(-1, min(1, target[0] - unit.x)), max(-1, min(1, target[1] - unit.y)))
            if not self._seen(unit):
                return 0
            v.mode = "SC" if skill == "resurrect" else "A1"
            v.t, v.dur = 0.0, 0.3 if skill != "bash" else 0.38
            return None
        if kind == "projectile":
            unit, src, dst, pk = ev[1:]
            v = self.view(unit)
            v.facing = (max(-1, min(1, dst[0] - src[0])), max(-1, min(1, dst[1] - src[1])))
            v.mode, v.t, v.dur = "SC" if pk == "fireball" else "A1", 0.0, 0.2
            self.projectiles.append(Projectile(pk, cell_to_world(*src), cell_to_world(*dst)))
            return None
        if kind == "damage":
            unit, amount, hp_after = ev[1:]
            v = self.view(unit)
            v.shown_hp = hp_after
            v.flash = 1.0
            if v.mode == "NU":
                v.mode, v.t, v.dur = "GH", 0.0, 0.18
            wx, wy = cell_to_world(v.rx, v.ry)
            col = (255, 70, 70) if unit.is_player else (255, 255, 255)
            if self._seen(unit):
                self.floats.append(FloatText(str(amount), col, wx, wy - 30, big=amount >= 10))
            return 0.08
        if kind == "miss":
            v = self.view(ev[1])
            if self._seen(ev[1]):
                wx, wy = cell_to_world(v.rx, v.ry)
                self.floats.append(FloatText("miss", (170, 170, 170), wx, wy - 30))
            return 0.08
        if kind == "heal":
            v = self.view(ev[1])
            v.shown_hp = min(ev[1].max_hp, v.shown_hp + ev[2])
            wx, wy = cell_to_world(v.rx, v.ry)
            self.floats.append(FloatText(f"+{ev[2]}", (90, 230, 90), wx, wy - 30))
            return 0.15
        if kind == "death":
            v = self.view(ev[1])
            v.shown_hp = 0
            v.path = []
            v.mode, v.t, v.dur = "DD", 0.0, 0.45
            return 0.1
        if kind == "resurrect":
            v = self.view(ev[1])
            v.mode, v.t = "NU", 0.0
            v.rx, v.ry = ev[1].x, ev[1].y
            v.shown_hp = ev[1].max_hp
            v.flash = 1.0
            return 0.25
        if kind == "knockback":
            v = self.view(ev[1])
            v.slide = (ev[2], ev[3], 0.0)
            return None
        if kind == "drop":
            self.items_shown.add(id(ev[2]))
            self.drop_time[id(ev[2])] = self.clock
            return 0.04
        if kind == "pickup":
            self.items_shown.discard(id(ev[2]))
            return 0
        if kind == "combat_start":
            self.banner = ["COMBAT", (220, 60, 50), 1.1]
            return 0.35
        if kind == "combat_end":
            self.banner = ["Combat over", (170, 170, 170), 1.0]
            return 0.2
        if kind == "turn":
            if ev[1] == "monsters":
                self.banner = ["Enemy turn", (210, 120, 90), 0.8]
                return 0.25
            self.banner = ["Your turn", (230, 210, 140), 0.8]
            return 0
        if kind == "levelup":
            self.banner = [f"Level {ev[1]}!", (255, 230, 90), 1.6]
            wx, wy = cell_to_world(*self.world.player.pos)
            self.floats.append(FloatText("LEVEL UP", (255, 230, 90), wx, wy - 50, big=True))
            return 0.3
        if kind in ("game_over", "victory"):
            self.flags.add(kind)
            return 0
        return 0

    # ------------------------------------------------------------ update
    def update(self, dt):
        dt *= self.speed
        self.clock += dt
        self.pull_events()
        for v in self.views.values():
            self._update_view(v, dt)
        for p in list(self.projectiles):
            p.t += dt
            if p.t >= p.dur:
                self.projectiles.remove(p)
        for f in list(self.floats):
            f.t += dt
            if f.t > 1.1:
                self.floats.remove(f)
        for entry in self.log:
            entry[2] += dt / self.speed
        if self.banner:
            self.banner[2] -= dt
            if self.banner[2] <= 0:
                self.banner = None

        # sequential playback: one blocking event at a time
        if self.wait > 0:
            self.wait -= dt
        while self.wait <= 0:
            if self.current is not None:
                if self._blocking_done():
                    self.current = None
                else:
                    break
            if not self.queue:
                break
            ev = self.queue.pop(0)
            w = self._start(ev)
            if w is None:
                self.current = ev
            else:
                self.wait = w

        # sync anything that drifted (regen, stat changes) once everything has played
        if self.idle():
            for v in self.views.values():
                u = v.unit
                if u.alive and v.dead:
                    v.mode = "NU"
                if u.alive:
                    v.shown_hp = u.hp
                    v.rx, v.ry = float(u.x), float(u.y)

    def _blocking_done(self):
        ev = self.current
        kind = ev[0]
        if kind in ("move", "attack", "knockback"):
            return not self.view(ev[1]).busy()
        if kind == "projectile":
            return not self.projectiles
        return True

    def _update_view(self, v, dt):
        if v.flash > 0:
            v.flash = max(0.0, v.flash - dt * 5)
        if v.path:
            tx, ty = v.path[0]
            dx, dy = tx - v.rx, ty - v.ry
            dist = math.hypot(dx, dy)
            if dist > 0.01:
                v.facing = ((dx > 0.01) - (dx < -0.01), (dy > 0.01) - (dy < -0.01))
            step = v.speed * dt
            v.t += dt * 1.6
            if dist <= step:
                v.rx, v.ry = float(tx), float(ty)
                v.path.pop(0)
                if not v.path:
                    v.mode = "NU"
            else:
                v.rx += dx / dist * step
                v.ry += dy / dist * step
            return
        if v.slide:
            (sx, sy), (ex, ey), t = v.slide
            t += dt / 0.14
            if t >= 1:
                v.rx, v.ry = float(ex), float(ey)
                v.slide = None
            else:
                v.rx, v.ry = sx + (ex - sx) * t, sy + (ey - sy) * t
                v.slide = ((sx, sy), (ex, ey), t)
            return
        if v.mode in ("A1", "SC", "GH", "DD"):
            v.t += dt
            if v.t >= v.dur:
                v.mode = "DT" if v.mode == "DD" else "NU"
                v.t = 0.0
        else:
            v.t += dt

    def player_world_pos(self):
        v = self.view(self.world.player)
        return cell_to_world(v.rx, v.ry)

    # ------------------------------------------------------------ drawing
    def brightness(self, x, y, light):
        g = self.world.grid
        if not g.explored[y][x]:
            return 0.0
        if not g.visible[y][x]:
            return 0.22
        v = self.view(self.world.player)
        d = math.hypot(x - v.rx, y - v.ry)
        return max(0.3, min(1.0, 1.15 - (d / light) ** 1.6 * 0.85))

    def draw(self, surf, cam, hover_cell=None, highlight=None, path_preview=None):
        """World pass. Drawn at 1:1 into an offscreen buffer that main.py scales to the window."""
        world, g, assets = self.world, self.world.grid, self.assets
        s = cam.scale
        light = world.player.light
        x0, y0, x1, y1 = cam.visible_cell_range(g)
        pv = self.view(world.player)
        psum = pv.rx + pv.ry
        tm = getattr(world, "tilemap", None)
        use_tiles = tm is not None and hasattr(assets, "draw_tile")
        drawables = []

        if use_tiles:
            tx0, ty0 = max(0, x0 // 5 - 1), max(0, y0 // 5 - 1)
            tx1, ty1 = min(tm.tw - 1, x1 // 5 + 1), min(tm.th - 1, y1 // 5 + 2)
            for ty in range(ty0, ty1 + 1):
                for tx in range(tx0, tx1 + 1):
                    if (tx, ty) not in tm.drawn:
                        continue          # like D2, the terrain around you is always shown
                    ref = tm.floor.get((tx, ty))
                    if ref:
                        assets.draw_tile(surf, ref, tx, ty, cam)
                    for wref in tm.walls.get((tx, ty), ()):
                        # props sort by the back of their tile, so units next to them stay visible
                        drawables.append((tx * 5 + ty * 5 + 1, 0, "tile", (wref, tx, ty)))
        else:
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if g.cells[y][x] == WALL:
                        continue
                    b = self.brightness(x, y, light)
                    if b <= 0:
                        continue
                    assets.draw_floor(surf, (x, y), cam.cell_to_screen(x, y), s, b, self.show_grid)
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if g.cells[y][x] == WALL and g.explored[y][x]:
                        drawables.append((x + y, 0, "wall", (x, y)))

        # overlays on the floor: move range, path, hover
        if highlight:
            for (x, y), cost in highlight.items():
                if g.visible[y][x]:
                    self._diamond(surf, cam, x, y, (70, 130, 210, 30))
        if path_preview:
            for (x, y), ok in path_preview:
                self._diamond(surf, cam, x, y, (80, 200, 90, 90) if ok else (210, 60, 50, 90))
        if hover_cell and g.in_bounds(*hover_cell) and g.explored[hover_cell[1]][hover_cell[0]]:
            self._diamond(surf, cam, *hover_cell, (255, 255, 255, 40), outline=True)

        for cell, items in world.ground.items():
            if use_tiles or g.explored[cell[1]][cell[0]]:
                for it in items:
                    if id(it) in self.items_shown:
                        drawables.append((cell[0] + cell[1] - 0.01, 1, "item", (cell, it)))
        for v in self.views.values():
            cx, cy = int(round(v.rx)), int(round(v.ry))
            if not g.in_bounds(cx, cy) or not g.visible[cy][cx]:
                continue
            layer = 0.5 if v.dead else 2
            drawables.append((v.rx + v.ry + (0 if not v.dead else -0.4), layer, "unit", v))
        drawables.sort(key=lambda d: (d[0], d[1]))

        self._labels = []
        self.unit_hits = []      # (world-space rect, unit) for mouse picking, back to front
        for _, _, kind, obj in drawables:
            if kind == "tile":
                ref, tx, ty = obj
                # scenery in front of the player turns see-through, like in D2
                cx, cy = tx * 5 + 2, ty * 5 + 2
                front = 0 < (cx + cy) - psum < 12 and abs((cx - cy) - (pv.rx - pv.ry)) < 7
                assets.draw_tile(surf, ref, tx, ty, cam, alpha=110 if front else None)
            elif kind == "wall":
                x, y = obj
                b = self.brightness(x, y, light) or 0.22
                # walls standing between the camera and the player get cut down (like D2)
                near = abs((x - y) - (pv.rx - pv.ry)) < 4.5 and 0 < (x + y) - psum < 6
                assets.draw_wall(surf, obj, cam.cell_to_screen(x, y), s, b, cutaway=near)
            elif kind == "item":
                cell, it = obj
                b = 1.0 if use_tiles else self.brightness(cell[0], cell[1], light)
                assets.draw_ground_item(surf, it, cam.cell_to_screen(*cell), s, max(b, 0.4),
                                        t=self.clock - self.drop_time.get(id(it), -100.0))
                if self.show_labels or getattr(self, "alt_held", False) or (hover_cell == cell):
                    self._labels.append((it, cell_to_world(*cell)))
            else:
                v = obj
                u = v.unit
                b = 1.0 if use_tiles else self.brightness(int(round(v.rx)), int(round(v.ry)), light)
                pose = {"mode": v.mode, "phase": (v.t / v.dur) if v.dur and v.mode in ("A1", "SC", "DD", "GH") else v.t,
                        "flash": v.flash, "facing": v.facing}
                feet = cam.cell_to_screen(v.rx, v.ry)
                rect = assets.draw_unit(surf, u, pose, feet, s, max(0.35, b))
                if not u.is_player and u.alive and not v.dead:
                    if rect is None:
                        rect = pygame.Rect(0, 0, int(22 * s), int(38 * s))
                        rect.midbottom = (int(feet[0]), int(feet[1] + 4 * s))
                    # keep the core of the sprite, trimming empty margins
                    r = pygame.Rect(rect.x + rect.w * 0.2, rect.y + rect.h * 0.1, rect.w * 0.6, rect.h * 0.9)
                    wx = (r.x - cam.sw / 2) / s + cam.wx
                    wy = (r.y - cam.sh / 2) / s + cam.wy
                    self.unit_hits.append((pygame.Rect(int(wx), int(wy), int(r.w / s), int(r.h / s)), u))

        for p in self.projectiles:
            wx, wy = p.pos()
            assets.draw_projectile(surf, p.kind, cam.to_screen(wx, wy), s, p.t)

        if use_tiles:
            self._draw_darkness(surf, cam, light)

    def _tile_explored(self, tx, ty):
        g = self.world.grid
        ex = g.explored
        for sx, sy in ((2, 2), (0, 0), (4, 4), (0, 4), (4, 0), (2, 0), (0, 2), (4, 2), (2, 4)):
            x, y = tx * 5 + sx, ty * 5 + sy
            if y < g.h and x < g.w and ex[y][x]:
                return True
        return False

    def _draw_darkness(self, surf, cam, light):
        """D2-style lighting: darkness everywhere except a soft light radius around the player."""
        w, h = surf.get_size()
        self.ambient = getattr(self.world, "ambient", self.AMBIENT)
        if getattr(self, "_dark", None) is None or self._dark.get_size() != (w, h) or self._light_r != (light, self.ambient):
            self._dark = pygame.Surface((w, h), pygame.SRCALPHA)
            self._light_r = (light, self.ambient)
            rw, rh = int(light * 32 * 1.15), int(light * 16 * 1.15)
            # concentric rings, each removing a little darkness -> smooth falloff to the edge
            acc = pygame.Surface((rw * 2, rh * 2), pygame.SRCALPHA)
            steps = 24
            for i in range(steps):
                k = 1 - i / steps
                r = pygame.Rect(0, 0, int(rw * 2 * k), int(rh * 2 * k))
                r.center = (rw, rh)
                ring = pygame.Surface((rw * 2, rh * 2), pygame.SRCALPHA)
                pygame.draw.ellipse(ring, (0, 0, 0, max(1, self.ambient // steps + 1)), r)
                acc.blit(ring, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            self._glow = acc
        self._dark.fill((0, 0, 0, self.ambient))
        px, py = cam.to_screen(*self.player_world_pos())
        gw, gh = self._glow.get_size()
        self._dark.blit(self._glow, (int(px - gw / 2), int(py - gh / 2 - 20)), special_flags=pygame.BLEND_RGBA_SUB)
        surf.blit(self._dark, (0, 0))

    AMBIENT = 205

    def draw_overlay(self, surf, cam):
        """Text and bars drawn on top at window resolution, so they stay crisp."""
        labels = [(it, cam.to_screen(wx, wy)) for it, (wx, wy) in getattr(self, "_labels", [])]
        self._draw_labels(surf, labels)
        self._draw_overhead_bars(surf, cam)
        for f in self.floats:
            font = self.fonts["big"] if f.big else self.fonts["med"]
            sx, sy = cam.to_screen(f.wx, f.wy - f.t * 22)
            img = font.render(f.text, True, f.color)
            if f.t > 0.7:
                img.set_alpha(int(255 * max(0, 1 - (f.t - 0.7) / 0.4)))
            surf.blit(img, (sx - img.get_width() / 2, sy))

    def _diamond(self, surf, cam, x, y, rgba, outline=False):
        from .iso import TILE_W, TILE_H
        s = cam.scale
        cx, cy = cam.cell_to_screen(x, y)
        hw, hh = TILE_W * s / 2, TILE_H * s / 2
        w, h = int(hw * 2) + 2, int(hh * 2) + 2
        tmp = pygame.Surface((w, h), pygame.SRCALPHA)
        pts = [(w / 2, 1), (w - 1, h / 2), (w / 2, h - 1), (1, h / 2)]
        if outline:
            pygame.draw.lines(tmp, (255, 255, 255, 120), True, pts, 1)
        else:
            pygame.draw.polygon(tmp, rgba, pts)
        surf.blit(tmp, (cx - w / 2, cy - h / 2))

    def _draw_labels(self, surf, labels):
        """Item names on the ground; overlapping labels get stacked upwards like in D2."""
        font = self.fonts["small"]
        placed = []
        for it, (x, y) in sorted(labels, key=lambda l: -l[1][1]):
            text = "%d Gold" % it.amount if it.kind == "gold" else it.name
            img = font.render(text, True, it.color)
            r = pygame.Rect(0, 0, img.get_width() + 8, img.get_height() + 2)
            r.center = (int(x), int(y - 26))
            for _ in range(30):
                hit = [p for p in placed if p.colliderect(r)]
                if not hit:
                    break
                r.y = min(p.y for p in hit) - r.h - 1
            placed.append(r)
            bg = pygame.Surface(r.size, pygame.SRCALPHA)
            bg.fill((0, 0, 0, 170))
            surf.blit(bg, r.topleft)
            surf.blit(img, (r.x + 4, r.y + 1))

    def _draw_overhead_bars(self, surf, cam):
        """Small HP bars over damaged / aware monsters."""
        g = self.world.grid
        for v in self.views.values():
            u = v.unit
            if u.is_player or v.dead or getattr(u, "ai", "") == "npc":
                continue
            cx, cy = int(round(v.rx)), int(round(v.ry))
            if not g.visible[cy][cx]:
                continue
            if not (u.unique or v.shown_hp < u.max_hp):
                continue
            sx, sy = cam.cell_to_screen(v.rx, v.ry)
            w = 26 * cam.scale / 2 + (10 if u.unique else 0)
            top = sy - ((44 if u.unique else 36) + self.bar_lift) * cam.scale
            pygame.draw.rect(surf, (20, 0, 0), (sx - w / 2, top, w, 4))
            frac = max(0.0, v.shown_hp / u.max_hp)
            pygame.draw.rect(surf, (200, 30, 30), (sx - w / 2, top, w * frac, 4))
