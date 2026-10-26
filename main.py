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
                   "diablo2": {"path": ""}})
    cfg.read(os.path.join(HERE, "settings.ini"))
    return cfg


def load_assets(cfg):
    path = cfg.get("diablo2", "path").strip()
    if path:
        try:
            from render.d2assets import D2Assets
            return D2Assets(path), None
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
        self.assets, self.asset_warning = load_assets(self.cfg)
        scale = self.cfg.get("display", "scale").strip().lower()
        zoom = getattr(self.assets, "native_scale", 2.0) if scale in ("", "auto") else float(scale)
        self.cam = Camera(w, h, zoom)
        self._offscreen = None
        self._path_cache = {}
        self.new_world()
        self.running = True

    def new_world(self, seed=None):
        builder = getattr(self.assets, "level_builder", None)
        self.world = World(seed=seed, level_builder=builder)
        self._path_cache = {}
        self.scene = Scene(self.world, self.assets, self.fonts)
        self.hud = Hud(self.fonts, self.assets)
        if self.asset_warning:
            self.world.log(self.asset_warning, (230, 160, 90))
        self.cam.snap(*self.scene.player_world_pos())

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
            elif g.in_bounds(*cell) and g.explored[cell[1]][cell[0]]:
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
            self.scene.show_labels = not self.scene.show_labels
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
            if g.in_bounds(*cell) and g.walkable(*cell) and g.explored[cell[1]][cell[0]] and cell != p.pos:
                key = ("c", cell) + key_base
                if key not in self._path_cache:
                    self._trim_cache()
                    self._path_cache[key] = w.path_for_player(cell)
                path = self._path_cache[key]
                if path:
                    preview = [(c, w.mode == "explore" or i < p.ap) for i, c in enumerate(path)]
                    if w.mode == "combat":
                        tip = ([f"{len(path)} AP" + ("" if len(path) <= p.ap else f"  (only {p.ap} left)")],
                               [TEXT if len(path) <= p.ap else (230, 120, 90)])
            items = w.ground.get(cell)
            if items and g.explored[cell[1]][cell[0]]:
                it = items[0]
                tip = (it.describe(), [it.color])
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

        self.scene.update(dt)
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
