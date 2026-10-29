"""Plays world events back as animations and draws the map."""
import math

import pygame

from game.grid import WALL
from .iso import cell_to_world

# D2 animation mode codes, so real DCC animations can be mapped 1:1 later:
# NU neutral, WL walk, A1 attack, SC cast, GH get hit, DD death, DT dead


NOVA_COLORS = {"fire": (255, 140, 40), "cold": (120, 180, 255), "ltng": (240, 240, 140), "pois": (110, 220, 80),
               "mag": (230, 200, 255), "curse": (200, 40, 60), "phys": (220, 210, 190)}


def status_tint(u):
    """D2 colours a unit by its state: frozen / chilled blue, poisoned green, bleeding red."""
    eff = getattr(u, "effects", None) or {}
    if eff.get("freeze"):
        return (80, 130, 255)
    if eff.get("chill") or eff.get("chilled"):
        return (125, 165, 255)
    if eff.get("poison"):
        return (110, 225, 100)
    if eff.get("bleed"):
        return (255, 120, 120)
    for c in (getattr(u, "curses", None) or {}).values():
        if "slow" in c.get("flags", ()) or c.get("stats", {}).get("slowed"):
            return (125, 165, 255)
    return None


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
        self.stop_t = 0.0       # a short grace before "walk" turns into "stand" between steps

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
    def __init__(self, kind, src, dst, missile=None):
        self.kind = kind
        self.missile = missile
        self.src, self.dst = src, dst
        d = math.hypot(dst[0] - src[0], dst[1] - src[1])
        self.dur = 0.06 + d / 650.0      # world pixels -> ~0.2 s over 5 tiles
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
        self.novas = []          # [world pos, radius in cells, colour, time] spell rings
        self.effects = []        # [kind, name, unit or world pos, time, duration]: explosions, cast overlays
        self.items_shown = set()
        self.log = []
        self.banner = None       # (text, color, time left)
        self.speed = 1.0
        self.show_grid = False
        self.show_labels = False
        self.selected = None      # monster under the mouse (highlighted)
        self.walk_target = None   # where you are walking to (you face it, not the next tile)
        self.skill_area = None    # (cells, hit cells, out of range) of the right skill under the mouse
        self.opts = {}
        self._sel_draw = None
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
        if self.queue or self.current is not None or self.wait > 0 or self.projectiles:
            return False
        explore = getattr(self.world, "mode", "") == "explore"
        for v in self.views.values():
            if v.busy() and not (explore and getattr(v.unit, "ally", False)):
                return False
        return True

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
        if kind == "place":
            v = self.view(ev[1])
            v.path = []
            v.slide = None
            v.rx, v.ry = float(ev[2][0]), float(ev[2][1])
            v.mode = "NU"
            return 0
        if kind == "move":
            unit, cells = ev[1], ev[2]
            v = self.view(unit)
            if not cells:
                return 0
            if not self._seen(unit, cells):
                v.rx, v.ry = cells[-1]
                return 0
            explore = getattr(self.world, "mode", "") == "explore"
            free = explore and (unit.is_player or getattr(unit, "ally", False))
            if free and v.path and v.mode == "WL":
                v.path.extend(cells)          # keep walking smoothly, step after step
                return 0
            v.path = list(cells)
            v.mode = "WL"
            v.speed = (9.5 if explore else 7.0) if unit.is_player else (11.0 if free else 9.0)
            if free:
                return 0                      # free walking (you and your followers) doesn't hold anything up
            return None   # wait until the walk finishes
        if kind == "attack":
            unit, target, skill = ev[1], ev[2], ev[3]
            v = self.view(unit)
            v.facing = (max(-1, min(1, target[0] - unit.x)), max(-1, min(1, target[1] - unit.y)))
            if not self._seen(unit):
                return 0
            v.mode = "SC" if skill in ("resurrect", "cast") else "A1"
            v.t, v.dur = 0.0, 0.38 if skill in ("bash", "cast") else 0.3
            return None
        if kind == "projectile":
            unit, src, dst, pk = ev[1:5]
            missile = ev[5] if len(ev) > 5 else None
            v = self.view(unit)
            v.facing = (max(-1, min(1, dst[0] - src[0])), max(-1, min(1, dst[1] - src[1])))
            v.mode = "A1" if pk in ("arrow", "spike") else "SC"
            v.t, v.dur = 0.0, 0.2
            self.projectiles.append(Projectile(pk, cell_to_world(*src), cell_to_world(*dst), missile))
            return None
        if kind == "overlay":
            unit, name = ev[1], ev[2]
            self.effects.append(["overlay", name, unit, 0.0, None])
            return 0
        if kind == "area":
            self.banner = [ev[1], (199, 179, 119), 2.0]
            return 0
        if kind == "nova":
            unit, centre, radius, elem = ev[1:5]
            missile = ev[5] if len(ev) > 5 else None
            wc = cell_to_world(*centre)
            assets = self.assets
            anim = assets.missile_anim(missile) if missile and hasattr(assets, "missile_anim") else None
            if anim is not None and centre == unit.pos and anim.n_dirs > 1:
                # D2 novas are rings of missiles flying outwards
                for i in range(16):
                    a = i * math.pi / 8
                    dst = (wc[0] + math.cos(a) * radius * 32, wc[1] + math.sin(a) * radius * 16)
                    pr = Projectile("nova", wc, dst, missile)
                    pr.dur = 0.35
                    self.projectiles.append(pr)
            elif anim is not None:
                # areas: the spell's graphic at the target and around it
                import random as _r
                spots = [wc] + [(wc[0] + _r.uniform(-1, 1) * radius * 28, wc[1] + _r.uniform(-1, 1) * radius * 14)
                                for _ in range(min(8, 2 + radius * 2))]
                for k, sp in enumerate(spots):
                    self.effects.append(["missile", missile, sp, -0.06 * k, anim.duration() or 0.5])
            else:
                self.novas.append([wc, radius, NOVA_COLORS.get(elem, (230, 220, 200)), 0.0])
            return 0.22
        if kind == "teleport":
            v = self.view(ev[1])
            v.path, v.slide = [], None
            v.rx, v.ry = float(ev[3][0]), float(ev[3][1])
            v.flash = 1.0
            self.novas.append([cell_to_world(*ev[3]), 1, (140, 160, 255), 0.0])
            return 0.15
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
        if kind == "object":
            ev[1]["op_t"] = self.clock          # a chest opens, a barrel breaks, a door swings
            return 0
        if kind == "explosion":
            name = ev[2] if len(ev) > 2 else "explosivepotionexp"
            anim = self.assets.missile_anim(name) if hasattr(self.assets, "missile_anim") else None
            if anim is not None:
                self.effects.append(["missile", name, cell_to_world(*ev[1]), 0.0, anim.duration() or 0.5])
            return 0.1
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
                expl = self.assets.missile_explosion(p.missile) if p.missile and hasattr(self.assets, "missile_explosion") else None
                if expl and p.kind != "nova":
                    anim = self.assets.missile_anim(expl)
                    if anim is not None:
                        self.effects.append(["missile", expl, p.dst, 0.0, anim.duration() or 0.4])
        for e in list(self.effects):
            e[3] += dt
            if e[4] is not None and e[3] > e[4]:
                self.effects.remove(e)
            elif e[4] is None and e[3] > 3.0:
                self.effects.remove(e)
        for n in list(self.novas):
            n[3] += dt
            if n[3] > 0.45:
                self.novas.remove(n)
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
            if ev[0] == "projectile":
                # a volley (Teeth, Charged Bolt, Multiple Shot, Twister ...) leaves all at once
                while self.queue and self.queue[0][0] == "projectile" and self.queue[0][1] is ev[1]:
                    self._start(self.queue.pop(0))
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
            goal = self.walk_target if v.unit.is_player else None
            if goal is not None and math.hypot(goal[0] - v.rx, goal[1] - v.ry) > 0.7:
                # face where you are going: a zig-zag of tiles still reads as one straight walk
                v.facing = (goal[0] - v.rx, goal[1] - v.ry)
            elif dist > 0.01:
                v.facing = (dx, dy) if v.unit.is_player else \
                    ((dx > 0.01) - (dx < -0.01), (dy > 0.01) - (dy < -0.01))
            step = v.speed * dt
            v.t += dt * 1.6
            v.mode = "WL"
            v.stop_t = 0.12
            # carry over what is left of this frame's movement into the next tile (no stop at each tile)
            while v.path and dist <= step:
                v.rx, v.ry = float(tx), float(ty)
                v.path.pop(0)
                step -= dist
                if v.path:
                    tx, ty = v.path[0]
                    dx, dy = tx - v.rx, ty - v.ry
                    dist = math.hypot(dx, dy)
            if v.path and dist > 0:
                v.rx += dx / dist * step
                v.ry += dy / dist * step
            return
        if v.mode == "WL" and v.stop_t > 0:
            v.stop_t -= dt          # the next step usually arrives within a frame or two
            v.t += dt * 1.6
            if v.stop_t <= 0:
                v.mode = "NU"
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
        light = world.player.light * self.opts.get("light_radius", 100) / 100.0
        x0, y0, x1, y1 = cam.visible_cell_range(g)
        pv = self.view(world.player)
        psum = pv.rx + pv.ry
        tm = getattr(world, "tilemap", None)
        use_tiles = tm is not None and hasattr(assets, "draw_tile")
        drawables = []

        if use_tiles:
            f2 = getattr(tm, "floor2", None)
            tx0, ty0 = max(0, x0 // 5 - 1), max(0, y0 // 5 - 1)
            tx1, ty1 = min(tm.tw - 1, x1 // 5 + 1), min(tm.th - 1, y1 // 5 + 2)
            for ty in range(ty0, ty1 + 1):
                for tx in range(tx0, tx1 + 1):
                    if (tx, ty) not in tm.drawn:
                        continue          # like D2, the terrain around you is always shown
                    ref = tm.floor.get((tx, ty))
                    if ref:
                        assets.draw_tile(surf, ref, tx, ty, cam)
                    ref2 = f2.get((tx, ty)) if f2 else None
                    if ref2:
                        assets.draw_tile(surf, ref2, tx, ty, cam)
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
        self._draw_hazards(surf, cam, g)
        if self.skill_area:
            cells, hits, far = self.skill_area
            for (x, y) in cells:
                if g.in_bounds(x, y) and g.explored[y][x] and (x, y) not in hits:
                    self._diamond(surf, cam, x, y, (120, 120, 120, 45) if far else (255, 170, 40, 55))
            for (x, y) in hits:
                if g.in_bounds(x, y):
                    self._diamond(surf, cam, x, y, (120, 120, 120, 70) if far else (235, 60, 30, 105))
        sel = self.selected if self.selected is not None and self.selected.alive else None
        self._sel_draw = None
        if sel is not None and self.opts.get("highlight_tile", True):
            for c in self._footprint(sel):
                self._diamond(surf, cam, c[0], c[1], (230, 50, 40, 70))

        for cell, items in world.ground.items():
            if use_tiles or g.explored[cell[1]][cell[0]]:
                for it in items:
                    if id(it) in self.items_shown:
                        drawables.append((cell[0] + cell[1] - 0.01, 1, "item", (cell, it)))
        for o in getattr(world, "objects", ()):
            x, y = o["cell"]
            if x0 - 4 <= x <= x1 + 4 and y0 - 4 <= y <= y1 + 4:
                if o.get("generic"):
                    drawables.append((x + y, 1.5, "gobject", o))
                else:
                    drawables.append((x + y, 1.5, "object", (o["kind"], o.get("oid", 0), o["cell"], o.get("used"))))
        for c, lid in getattr(world, "waypoints", {}).items():
            if x0 - 4 <= c[0] <= x1 + 4 and y0 - 4 <= c[1] <= y1 + 4:
                drawables.append((c[0] + c[1] - 0.5, 0.2, "object", ("waypoint", lid, c, False)))
        for v in self.views.values():
            cx, cy = int(round(v.rx)), int(round(v.ry))
            if getattr(v.unit, "hidden", False):
                continue                   # hidden traps and the hell meteors' spawners
            if not v.unit.is_player and not self.unit_seen(v.unit, cam, v):
                continue
            layer = 0.5 if v.dead else 2
            drawables.append((v.rx + v.ry + (0 if not v.dead else -0.4), layer, "unit", v))
        drawables.sort(key=lambda d: (d[0], d[1]))

        far = []                 # enemies outside your light: drawn again, dimmed, above the darkness
        self._labels = []
        self.unit_hits = []      # (world-space rect, unit) for mouse picking, back to front
        self.object_hits = []    # (world-space rect, object) the same for chests, shrines, doors ...
        # where the player is on screen: scenery drawn after him that covers him goes see-through
        ppx, ppy = cam.cell_to_screen(pv.rx, pv.ry)
        prect = pygame.Rect(int(ppx - 22), int(ppy - 86), 44, 92)
        player_key = pv.rx + pv.ry
        for key, _, kind, obj in drawables:
            if kind == "tile":
                ref, tx, ty = obj
                alpha = None
                if key > player_key and hasattr(assets, "tile_rect"):
                    r = assets.tile_rect(ref, tx, ty, cam)
                    if r is not None and r.colliderect(prect):
                        alpha = 105
                assets.draw_tile(surf, ref, tx, ty, cam, alpha=alpha)
            elif kind == "wall":
                x, y = obj
                b = self.brightness(x, y, light) or 0.22
                # walls standing between the camera and the player get cut down (like D2)
                near = abs((x - y) - (pv.rx - pv.ry)) < 4.5 and 0 < (x + y) - psum < 6
                assets.draw_wall(surf, obj, cam.cell_to_screen(x, y), s, b, cutaway=near)
            elif kind == "object":
                okind, oid, cell, used = obj
                if hasattr(assets, "draw_object"):
                    assets.draw_object(surf, okind, oid, cam.cell_to_screen(*cell), s, self.clock, used)
            elif kind == "gobject":
                if hasattr(assets, "draw_gen_object"):
                    r = assets.draw_gen_object(surf, obj, cam.cell_to_screen(*obj["cell"]), s, self.clock)
                    if r is not None and obj["kind"] != "decor":
                        self.object_hits.append((r, obj))       # click the picture, like D2
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
                tint = status_tint(u) if u.alive and not v.dead else None
                if tint:
                    pose["tint"] = tint
                feet = cam.cell_to_screen(v.rx, v.ry)
                rect = assets.draw_unit(surf, u, pose, feet, s, max(0.35, b))
                if u is sel and not v.dead:
                    self._sel_draw = (u, dict(pose), feet)
                elif use_tiles and u.alive and not v.dead and not u.is_player and not getattr(u, "ally", False) \
                        and math.hypot(v.rx - pv.rx, v.ry - pv.ry) > light * 0.7:
                    far.append((u, dict(pose), feet))
                if u.alive and not v.dead and hasattr(assets, "draw_overlay"):
                    for st in self._unit_states(u):
                        for ov in assets.state_overlays(st):
                            assets.draw_overlay(surf, ov, feet, self.clock, loop=True)
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
            sp = cam.to_screen(wx, wy)
            vec = (p.dst[0] - p.src[0], p.dst[1] - p.src[1])
            if not (p.missile and hasattr(assets, "draw_missile") and
                    assets.draw_missile(surf, p.missile, (sp[0], sp[1] - 12), vec, p.t)):
                assets.draw_projectile(surf, p.kind, sp, s, p.t)
        for e in list(self.effects):
            kind, name, where, t, dur = e
            if t < 0:
                continue
            if kind == "missile":
                sp = cam.to_screen(*where)
                if hasattr(assets, "draw_missile"):
                    assets.draw_missile(surf, name, sp, (0, 1), t, loop=False)
            elif kind == "overlay" and hasattr(assets, "draw_overlay"):
                v = self.view(where)
                feet = cam.cell_to_screen(v.rx, v.ry)
                if not assets.draw_overlay(surf, name, feet, t):
                    self.effects.remove(e)
        for (wx, wy), r, col, t in self.novas:
            k = min(1.0, t / 0.3)
            rw, rh = max(2, int(r * 32 * k * s)), max(1, int(r * 16 * k * s))
            ring = pygame.Surface((rw * 2 + 4, rh * 2 + 4), pygame.SRCALPHA)
            a = int(200 * (1 - t / 0.45))
            pygame.draw.ellipse(ring, col + (max(0, a // 3),), ring.get_rect())
            pygame.draw.ellipse(ring, col + (max(0, a),), ring.get_rect(), max(1, int(3 * s)))
            sx, sy = cam.to_screen(wx, wy)
            surf.blit(ring, (int(sx - rw - 2), int(sy - rh - 2)))

        if use_tiles:
            self._draw_darkness(surf, cam, light)
            for u, pose, feet in far:
                self._draw_ghost(surf, cam, u, pose, feet)
        if sel is not None:
            self._draw_selected(surf, cam, sel)

    SEEN_MARGIN = 160      # px (1:1 world scale) beyond the screen edge: about 2 D2 tiles

    def unit_seen(self, u, cam, v=None):
        """Monsters show up as soon as they are within ~2 tiles of the screen (whatever your zoom),
        if you have a line of sight to them - not only inside your light radius."""
        g = self.world.grid
        v = v or self.view(u)
        cx, cy = int(round(v.rx)), int(round(v.ry))
        if not g.in_bounds(cx, cy):
            return False
        if g.visible[cy][cx]:
            return True
        if getattr(u, "ally", False) or getattr(u, "ai", "") == "npc":
            return True                 # your followers and the town's people are always shown
        if not u.alive or v.dead:
            return g.explored[cy][cx]
        sx, sy = cam.cell_to_screen(v.rx, v.ry)
        m = self.SEEN_MARGIN * cam.scale
        if not (-m <= sx <= cam.sw + m and -m <= sy <= cam.sh + m + 60 * cam.scale):
            return False
        # like D2: whatever is on screen shows - monsters that know about you, monsters near you and
        # monsters on ground you have seen (no line-of-sight check: cave walls and stairs hid them)
        if getattr(u, "aware", False) or g.explored[cy][cx]:
            return True
        p = self.world.player
        return math.hypot(cx - p.x, cy - p.y) <= 12

    def _footprint(self, u):
        r = getattr(u, "radius", 0)
        return [(u.x + dx, u.y + dy) for dy in range(-r, r + 1) for dx in range(-r, r + 1)]

    HAZARD_COLORS = {"fire": (255, 120, 30, 70), "cold": (120, 170, 255, 70), "pois": (90, 220, 60, 70),
                     "ltng": (230, 230, 120, 60)}

    def _draw_hazards(self, surf, cam, g):
        """Fire Wall, Blaze trails, Meteor fire, Blizzard ...: what keeps burning on the ground."""
        hz = getattr(self.world, "hazards", None)
        if not hz:
            return
        assets = self.assets
        for i, h in enumerate(hz):
            cells = h["cells"]
            col = self.HAZARD_COLORS.get(h.get("elem"), (255, 120, 30, 60))
            vis = h.get("vis")
            dense = len(cells) <= 12
            for (x, y) in cells:
                if not g.in_bounds(x, y) or not g.visible[y][x]:
                    continue
                self._diamond(surf, cam, x, y, col)
                if vis and hasattr(assets, "draw_missile") and (dense or (x + 2 * y) % 3 == 0):
                    sx, sy = cam.cell_to_screen(x, y)
                    # each cell starts its loop at a different point so the flames don't pulse together
                    assets.draw_missile(surf, vis, (sx, sy), (0, 1), self.clock + (x * 7 + y * 13) % 10 * 0.07,
                                        loop=True)

    def _draw_ghost(self, surf, cam, u, pose, feet):
        """A monster beyond your light radius, shown dimmed so you can see what is coming."""
        pose = dict(pose, tint=(205, 195, 190, 255), no_shadow=True)
        try:
            self.assets.draw_unit(surf, u, pose, feet, cam.scale, 1.0)
        except Exception:
            pass

    def _draw_selected(self, surf, cam, u):
        """The monster under the mouse: drawn again above the darkness with a red rim, and its
        tile(s) outlined - so it stays readable at the edge of your light."""
        if self.opts.get("highlight_tile", True):
            for c in self._footprint(u):
                self._diamond(surf, cam, c[0], c[1], (255, 70, 50, 150), outline=True)
        if not self.opts.get("highlight_monster", True) or self._sel_draw is None:
            return
        _, pose, feet = self._sel_draw
        try:
            self.assets.draw_unit(surf, u, dict(pose, outline=(255, 60, 40), no_shadow=True), feet, cam.scale, 1.0)
        except Exception:
            pass

    def _unit_states(self, u):
        """D2 states shown as overlays: your aura and buffs, curses on monsters."""
        p = self.world.player
        tree = getattr(getattr(p, "skills", None), "tree", {})
        out = []
        if u.is_player:
            names = list(getattr(u, "buffs", {}).keys())
            if getattr(u, "active_aura", None):
                names.append(u.active_aura)
            for n in names:
                sk = tree.get(n)
                if sk is not None and sk.data and sk.data.get("aurastate"):
                    out.append(sk.data["aurastate"])
        else:
            for n in getattr(u, "curses", {}) or {}:
                sk = tree.get(n)
                if sk is not None and sk.data and sk.data.get("auratargetstate"):
                    out.append(sk.data["auratargetstate"])
        return out

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
        cache = self.__dict__.setdefault("_diamonds", {})
        key = (w, h, tuple(rgba), outline)
        tmp = cache.get(key)
        if tmp is None:
            tmp = pygame.Surface((w, h), pygame.SRCALPHA)
            tmp.fill((0, 0, 0, 0))
            pts = [(w / 2, 1), (w - 1, h / 2), (w / 2, h - 1), (1, h / 2)]
            if outline:
                col = rgba if len(rgba) > 3 and rgba[3] >= 100 else (255, 255, 255, 120)
                pygame.draw.lines(tmp, col, True, pts, 1)
            else:
                pygame.draw.polygon(tmp, rgba, pts)
            if len(cache) > 64:
                cache.clear()
            cache[key] = tmp
        surf.blit(tmp, (cx - w / 2, cy - h / 2))

    def _draw_labels(self, surf, labels):
        """Item names on the ground; overlapping labels get stacked upwards like in D2."""
        font = self.fonts["small"]
        placed = []
        for it, (x, y) in sorted(labels, key=lambda l: -l[1][1]):
            text = "%d Gold" % it.amount if it.kind == "gold" else getattr(it, "shown_name", it.name)
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
            if u.is_player or v.dead or getattr(u, "ai", "") in ("npc", "wall") or getattr(u, "invulnerable", False):
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
            pygame.draw.rect(surf, (40, 190, 60) if getattr(u, "ally", False) else (200, 30, 30), (sx - w / 2, top, w * frac, 4))
