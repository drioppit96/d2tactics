"""D2 Tactics - turn-based tactical combat prototype on a Diablo 2 style isometric grid.

Run:  python main.py
"""
import configparser
import os
import sys

import pygame

from game.grid import chebyshev
from game.world import World
from render.assets import PlaceholderAssets
from render.hud import Hud, GOLD, TEXT
from render.iso import Camera
from render.scene import Scene

HERE = os.path.dirname(os.path.abspath(__file__))


def load_settings():
    cfg = configparser.ConfigParser()
    cfg.read_dict({"display": {"width": "1280", "height": "720", "fullscreen": "no", "scale": "auto"},
                   "diablo2": {"path": ""}, "game": {"difficulty": "normal"}})
    cfg.read(os.path.join(HERE, "settings.ini"))
    return cfg


def load_assets(cfg, progress=None):
    path = cfg.get("diablo2", "path").strip()
    if path:
        try:
            from render.d2assets import D2Assets
            return D2Assets(path, cfg.get("game", "difficulty").strip().lower(), progress), None
        except Exception as e:  # files not found or unreadable
            import traceback
            traceback.print_exc()
            return PlaceholderAssets(), f"D2 graphics not loaded ({e}); using placeholder art."
    return PlaceholderAssets(), None


class Game:
    def __init__(self):
        self.cfg = load_settings()
        pygame.init()
        w = self.cfg.getint("display", "width")
        h = self.cfg.getint("display", "height")
        flags = pygame.RESIZABLE
        if self.cfg.getboolean("display", "fullscreen"):
            flags = pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption("D2 Tactics - prototype")
        self.clock = pygame.time.Clock()
        serif = "georgia,palatinolinotype,timesnewroman,serif"
        self.fonts = {
            "small": pygame.font.SysFont(serif, 15),
            "med": pygame.font.SysFont(serif, 19, bold=True),
            "big": pygame.font.SysFont(serif, 30, bold=True),
            "title": pygame.font.SysFont(serif, 22, bold=True),
        }
        self.loading("Starting...")
        self.assets, self.asset_warning = load_assets(self.cfg, self.loading)
        scale = self.cfg.get("display", "scale").strip().lower()
        zoom = getattr(self.assets, "native_scale", 2.0) if scale in ("", "auto") else float(scale)
        self.cam = Camera(w, h, zoom)
        self._offscreen = None
        self._path_cache = {}
        self.new_world()
        self.running = True

    def loading(self, message):
        """Simple loading screen; also keeps Windows from marking the window 'not responding'."""
        pygame.event.pump()
        W, H = self.screen.get_size()
        self.screen.fill((0, 0, 0))
        font = pygame.font.SysFont("georgia,palatinolinotype,timesnewroman,serif", 30, bold=True)
        small = pygame.font.SysFont("georgia,palatinolinotype,timesnewroman,serif", 17)
        t = font.render("D2 Tactics", True, (199, 179, 119))
        self.screen.blit(t, (W / 2 - t.get_width() / 2, H / 2 - 50))
        s = small.render(message, True, (190, 180, 160))
        self.screen.blit(s, (W / 2 - s.get_width() / 2, H / 2 + 6))
        pygame.display.flip()

    def new_world(self, seed=None):
        """New game: start in the Rogue Encampment when D2 files are available."""
        self.levels = {}
        self.hud = Hud(self.fonts, self.assets) if not hasattr(self, "hud") else self.hud
        self.hud.minimaps = {}
        content = getattr(self.assets, "content", None)
        if getattr(self.assets, "town_kit", None):
            self.loading("Building the Rogue Encampment...")
            self.world = World(seed=seed, level_builder=self.assets.town_builder, content=content,
                               level_id="town", level_name="Rogue Encampment", town=True, exit_to="den")
        else:
            builder = getattr(self.assets, "level_builder", None)
            self.world = World(seed=seed, level_builder=builder, content=content)
        self.levels[self.world.level_id] = self.world
        self._start_scene()
        if self.asset_warning:
            self.world.log(self.asset_warning, (230, 160, 90))

    def _start_scene(self):
        self._path_cache = {}
        self.scene = Scene(self.world, self.assets, self.fonts)
        self.scene.banner = [self.world.level_name, (199, 179, 119), 2.0]
        self.cam.snap(*self.scene.player_world_pos())

    def change_level(self, target):
        """Walk through an exit: levels are kept, so killed monsters stay dead."""
        old = self.world
        old.pending_exit = None
        old.last_pos = old.player.pos
        player = old.player
        if target in self.levels:
            w = self.levels[target]
            w.player = player
            if w.town and getattr(w, "last_pos", None):
                # step back into the camp, away from the exit you used
                lx, ly = w.last_pos
                inside = [c for c in w.grid.reachable(w.entry, 400) if c not in w.exits
                          and all(max(abs(c[0] - e[0]), abs(c[1] - e[1])) > 3 for e in w.exits)]
                spot = min(inside, key=lambda c: abs(c[0] - lx) + abs(c[1] - ly)) if inside else w.entry
            else:
                spot = w.entry
            w.relocate_player(spot)
            w.log("You return to the %s." % w.level_name, (199, 179, 119))
        else:
            self.loading("Entering the Den of Evil...")
            w = World(seed=None, level_builder=self.assets.level_builder, content=getattr(self.assets, "content", None),
                      level_id=target, level_name="Den of Evil", player=player, exit_to="town")
            self.levels[target] = w
        self.world = w
        self._start_scene()

    # ------------------------------------------------------------ input
    def can_act(self):
        return self.scene.idle() and self.world.player_can_act() and "game_over" not in self.scene.flags

    def monster_under_mouse(self, pos):
        """A monster whose sprite is under the mouse (front-most first), else None."""
        W, H = self.screen.get_size()
        wx = (pos[0] - W / 2) / self.cam.scale + self.cam.wx
        wy = (pos[1] - H / 2) / self.cam.scale + self.cam.wy
        for rect, u in reversed(getattr(self.scene, "unit_hits", [])):
            if u.alive and rect.collidepoint((int(wx), int(wy))):
                return u
        return None

    def monster_at(self, cell):
        g = self.world.grid
        if not g.in_bounds(*cell) or not g.visible[cell[1]][cell[0]]:
            return None
        u = self.world.unit_at(cell)
        return u if u is not None and not u.is_player else None

    def handle_click(self, pos, button):
        ui = self.hud.hit(pos)
        if ui:
            action, arg = ui
            w = self.world
            if action == "end_turn" and self.can_act():
                w.end_player_turn()
            elif action == "inv":
                self.hud.show_inv = not self.hud.show_inv
            elif action == "char":
                self.hud.show_char = not self.hud.show_char
            elif action == "potion" and self.can_act():
                w.use_potion(arg)
            elif action == "item":
                if button == 1:
                    w.equip(arg)
                elif button == 3:
                    w.drop_item(arg)
            elif action == "unequip":
                w.unequip(arg)
            elif action == "stat":
                w.add_stat(arg)
            return
        if pos[1] > self.screen.get_height() - Hud.BAR_H:
            return
        if not self.can_act():
            return
        cell = self.cam.screen_to_cell(*pos)
        m = self.monster_under_mouse(pos) or self.monster_at(cell)
        if m:
            self.world.player_attack(m, "bash" if button == 3 else "attack")
        elif button == 1:
            g = self.world.grid
            if cell == self.world.player.pos and cell in self.world.ground:
                self.world.player_pickup(cell)
            elif g.in_bounds(*cell) and g.walkable(*cell):
                self.world.player_move_to(cell)

    def handle_key(self, key):
        w = self.world
        if key == pygame.K_ESCAPE:
            if self.hud.show_inv or self.hud.show_char:
                self.hud.show_inv = self.hud.show_char = False
            else:
                self.running = False
        elif key in (pygame.K_SPACE, pygame.K_e) and self.can_act():
            w.end_player_turn()
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4) and self.can_act():
            w.use_potion(key - pygame.K_1)
        elif key == pygame.K_i:
            self.hud.show_inv = not self.hud.show_inv
        elif key == pygame.K_c:
            self.hud.show_char = not self.hud.show_char
        elif key == pygame.K_g:
            self.scene.show_grid = not self.scene.show_grid
        elif key == pygame.K_TAB:
            self.hud.show_automap = not self.hud.show_automap      # D2: Tab = automap
        elif key == pygame.K_l:
            self.scene.show_labels = not self.scene.show_labels    # keep item names on
        elif key == pygame.K_f:
            self.scene.speed = 1.0 if self.scene.speed > 1 else 2.5
        elif key == pygame.K_r and ("game_over" in self.scene.flags or "victory" in self.scene.flags):
            self.new_world()
        elif key == pygame.K_n and "victory" in self.scene.flags:
            self.new_world()

    def _trim_cache(self):
        if len(self._path_cache) > 60:
            self._path_cache = dict(list(self._path_cache.items())[-30:])

    # ------------------------------------------------------------ hover info
    def hover_info(self, mouse):
        """Returns (hover_cell, move_range, path_preview, tooltip)."""
        if self.hud.over_ui(mouse):
            return None, None, None, None
        w = self.world
        cell = self.cam.screen_to_cell(*mouse)
        if not self.can_act():
            return cell, None, None, None
        p = w.player
        highlight = None
        if w.mode == "combat":
            hk = ("r", p.pos, p.ap, w.round, len(w.living_monsters()), tuple(m.pos for m in w.aware_monsters()))
            if hk not in self._path_cache:
                self._trim_cache()
                self._path_cache[hk] = w.reachable_cells()
            highlight = self._path_cache[hk]
        m = self.monster_under_mouse(mouse) or self.monster_at(cell)
        tip = None
        preview = None
        key_base = (p.pos, w.mode, p.ap, w.round, len(w.living_monsters()))
        if m and getattr(m, "ai", "") == "npc":
            return cell, highlight, None, ([m.name, "Click to talk"], [(90, 200, 255), TEXT])
        if m:
            hc, cost = w.preview_attack(m, "attack")
            hb, bcost = w.preview_attack(m, "bash")
            dist = chebyshev(p.pos, m.pos)
            name_col = GOLD if m.unique else TEXT
            lines = [m.name, f"Level {m.level}   Life {self.scene.view(m).shown_hp}/{m.max_hp}",
                     f"Attack: {int(hc * 100)}% to hit, {cost} AP",
                     f"Bash: {int(hb * 100)}% to hit, {bcost} AP"]
            if dist > 1:
                key = ("m", m.pos) + key_base
                if key not in self._path_cache:
                    self._trim_cache()
                    self._path_cache[key] = w.grid.find_path(p.pos, m.pos, blocked=w.occupied(p), allow_goal_blocked=True)
                path = self._path_cache[key]
                if path:
                    steps = len(path) - 1
                    lines.append(f"Walk {steps} + attack = {steps + cost} AP" if w.mode == "combat" else f"Walk {steps}")
                    preview = [(c, w.mode == "explore" or i < p.ap) for i, c in enumerate(path[:-1])]
            tip = (lines, [name_col, TEXT, TEXT, TEXT, TEXT])
        else:
            g = w.grid
            if g.in_bounds(*cell) and g.walkable(*cell) and cell != p.pos:
                key = ("c", cell) + key_base
                if key not in self._path_cache:
                    self._trim_cache()
                    self._path_cache[key] = w.path_for_player(cell)
                path = self._path_cache[key]
                if path and w.mode == "combat":      # outside combat you just walk, no AP to plan
                    preview = [(c, i < p.ap) for i, c in enumerate(path)]
                    if w.mode == "combat":
                        tip = ([f"{len(path)} AP" + ("" if len(path) <= p.ap else f"  (only {p.ap} left)")],
                               [TEXT if len(path) <= p.ap else (230, 120, 90)])
            if cell in w.exits and w.exits[cell]:
                names = {"den": "To the Den of Evil", "town": "To the Rogue Encampment"}
                tip = ([names.get(w.exits[cell], "Exit")], [(240, 210, 90)])
            items = w.ground.get(cell)
            if items and g.explored[cell[1]][cell[0]]:
                lines = items[0].describe_lines(p)
                tip = ([t for t, _ in lines], [c for _, c in lines])
        return cell, highlight, preview, tip

    # ------------------------------------------------------------ main loop
    def frame(self, dt):
        mouse = pygame.mouse.get_pos()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.VIDEORESIZE:
                self.cam.resize(ev.w, ev.h)
            elif ev.type == pygame.KEYDOWN:
                self.handle_key(ev.key)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
                self.handle_click(ev.pos, ev.button)
            elif ev.type == pygame.MOUSEWHEEL:
                self.cam.scale = max(1.0, min(3.5, self.cam.scale + ev.y * 0.25))

        try:
            self.scene.alt_held = bool(pygame.key.get_mods() & pygame.KMOD_ALT)
        except Exception:
            self.scene.alt_held = False
        self.scene.update(dt)
        if self.world.pending_exit and self.scene.idle():
            self.change_level(self.world.pending_exit)
        self.cam.resize(*self.screen.get_size())
        self.cam.follow(*self.scene.player_world_pos(), dt)

        cell, highlight, preview, tip = self.hover_info(mouse)
        self.screen.fill((0, 0, 0))
        self.draw_world(cell, highlight, preview)
        self.scene.draw_overlay(self.screen, self.cam)
        self.hud.draw(self.screen, self.world, self.scene, mouse)
        if tip and not self.hud.hover_lines:
            from render.hud import tooltip
            tooltip(self.screen, self.fonts, tip[0], tip[1], mouse)
        self.draw_overlays()
        pygame.display.flip()

    def draw_world(self, cell, highlight, preview):
        """Draw the world 1:1 into a smaller buffer, then scale it up to the window (zoom)."""
        W, H = self.screen.get_size()
        z = self.cam.scale
        ow, oh = max(1, int(W / z + 0.5)), max(1, int(H / z + 0.5))
        if self._offscreen is None or self._offscreen.get_size() != (ow, oh):
            self._offscreen = pygame.Surface((ow, oh))
        off = self._offscreen
        off.fill((0, 0, 0))
        rcam = Camera(ow, oh, 1.0)
        rcam.wx, rcam.wy = self.cam.wx, self.cam.wy
        self.scene.draw(off, rcam, cell, highlight, preview)
        if abs(z - round(z)) < 1e-6:
            img = pygame.transform.scale(off, (int(ow * z), int(oh * z)))
        else:
            img = pygame.transform.smoothscale(off, (int(ow * z), int(oh * z)))
        self.screen.blit(img, (int(W / 2 - ow * z / 2), int(H / 2 - oh * z / 2)))

    def draw_overlays(self):
        W, H = self.screen.get_size()
        if "game_over" in self.scene.flags and self.scene.idle():
            shade = pygame.Surface((W, H), pygame.SRCALPHA)
            shade.fill((40, 0, 0, 150))
            self.screen.blit(shade, (0, 0))
            for i, (text, font, col) in enumerate([("You have died", "big", (220, 50, 40)),
                                                    ("Press R for a new cave, Esc to quit", "med", TEXT)]):
                img = self.fonts[font].render(text, True, col)
                self.screen.blit(img, (W / 2 - img.get_width() / 2, H / 2 - 40 + i * 50))
        elif "victory" in self.scene.flags:
            img = self.fonts["med"].render("Den of Evil cleared - press N for a new cave", True, GOLD)
            self.screen.blit(img, (W / 2 - img.get_width() / 2, 84))

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.frame(min(dt, 0.05))
        pygame.quit()


if __name__ == "__main__":
    Game().run()
    sys.exit(0)
