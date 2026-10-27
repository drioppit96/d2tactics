"""D2's Esc menu (Options / Save and Exit Game / Return to Game) and the options page.

Options are kept in options.ini next to the game (settings.ini stays as you wrote it).
"""
import configparser
import os

import pygame

GOLD = (199, 179, 119)
WHITE = (255, 255, 255)
GREY = (120, 120, 120)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPTIONS_FILE = os.path.join(HERE, "options.ini")

DEFAULTS = {"light_radius": 100, "highlight_monster": True, "highlight_tile": True,
            "show_move_range": True, "show_skill_area": True, "monster_names": True}
LIGHT_STEPS = [50, 75, 100, 125, 150, 200, 250, 300]


def load_options():
    o = dict(DEFAULTS)
    cfg = configparser.ConfigParser()
    try:
        cfg.read(OPTIONS_FILE)
        if cfg.has_section("options"):
            s = cfg["options"]
            for k, v in DEFAULTS.items():
                if k not in s:
                    continue
                if isinstance(v, bool):
                    o[k] = s.getboolean(k)
                else:
                    o[k] = max(25, min(400, s.getint(k)))
    except Exception:
        pass
    return o


def save_options(o):
    cfg = configparser.ConfigParser()
    cfg["options"] = {k: ("yes" if v else "no") if isinstance(v, bool) else str(v) for k, v in o.items()}
    try:
        with open(OPTIONS_FILE, "w") as f:
            f.write("; In-game options (Esc > Options). Delete this file to reset them.\n")
            cfg.write(f)
    except Exception:
        pass


class GameMenu:
    def __init__(self, game):
        self.game = game
        self.page = "main"
        self.sel = 0
        self.t = 0.0
        self.rects = []
        hud = game.hud
        self.font = None
        self.small = None
        self.pent = None
        src = getattr(game.assets, "src", None)
        if src is not None and hasattr(hud, "f16"):
            from .d2hud import D2Font
            try:
                self.font = D2Font(src, "font42")
            except Exception:
                self.font = getattr(hud, "f30", None)
            try:
                self.small = D2Font(src, "font30")
            except Exception:
                self.small = self.font
            self.pent = hud._load("data\\global\\ui\\CURSOR\\pentspin.dc6")

    # ------------------------------------------------------------ items
    def items(self):
        o = self.game.opts
        if self.page == "main":
            return [("OPTIONS", "options"), ("SAVE AND EXIT GAME", "save_exit"), ("RETURN TO GAME", "close")]
        onoff = lambda k: "ON" if o[k] else "OFF"
        return [("LIGHT RADIUS: %d%%" % o["light_radius"], "light"),
                ("HIGHLIGHT MONSTER: " + onoff("highlight_monster"), "hl_mon"),
                ("HIGHLIGHT TILE: " + onoff("highlight_tile"), "hl_tile"),
                ("SHOW MOVE RANGE: " + onoff("show_move_range"), "range"),
                ("SHOW SKILL AREA: " + onoff("show_skill_area"), "area"),
                ("PREVIOUS MENU", "back")]

    def activate(self, action, step=1):
        g = self.game
        o = g.opts
        if action == "options":
            self.page, self.sel = "options", 0
        elif action == "back":
            self.page, self.sel = "main", 0
        elif action == "close":
            g.menu = None
        elif action == "save_exit":
            g.menu = None
            g.save_and_exit()
        elif action == "light":
            cur = o["light_radius"]
            steps = LIGHT_STEPS
            i = min(range(len(steps)), key=lambda j: abs(steps[j] - cur))
            o["light_radius"] = steps[(i + step) % len(steps)]
        elif action == "hl_mon":
            o["highlight_monster"] = not o["highlight_monster"]
        elif action == "hl_tile":
            o["highlight_tile"] = not o["highlight_tile"]
        elif action == "area":
            o["show_skill_area"] = not o["show_skill_area"]
        elif action == "range":
            o["show_move_range"] = not o["show_move_range"]
        if action in ("light", "hl_mon", "hl_tile", "range", "area"):
            save_options(o)
            g.apply_options()

    def key(self, key):
        items = self.items()
        if key == pygame.K_ESCAPE:
            if self.page == "options":
                self.page, self.sel = "main", 0
            else:
                self.game.menu = None
        elif key in (pygame.K_UP, pygame.K_w):
            self.sel = (self.sel - 1) % len(items)
        elif key in (pygame.K_DOWN, pygame.K_s):
            self.sel = (self.sel + 1) % len(items)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
            self.activate(items[self.sel][1])
        elif key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
            act = items[self.sel][1]
            if act in ("light", "hl_mon", "hl_tile", "range", "area"):
                self.activate(act, -1 if key in (pygame.K_LEFT, pygame.K_a) else 1)

    def click(self, pos, button=1):
        for i, (r, action) in enumerate(self.rects):
            if r.collidepoint(pos):
                self.sel = i
                self.activate(action, -1 if button == 3 else 1)
                return True
        return True       # the menu swallows clicks

    # ------------------------------------------------------------ drawing
    def update(self, dt):
        self.t += dt

    def _render(self, text, color, big=True):
        f = self.font if big else self.small
        if f is not None:
            return f.render(text, color, self.game.hud.ind)
        return self.game.fonts["big" if big else "med"].render(text, True, color)

    def draw(self, surf, mouse):
        W, H = surf.get_size()
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        surf.blit(shade, (0, 0))
        k = H / 600.0
        items = self.items()
        gap = 52 if self.page == "main" else 46
        y0 = 300 - gap * len(items) / 2.0
        self.rects = []
        laid = []
        for i, (label, action) in enumerate(items):
            img = self._render(label, GOLD, big=True)
            big = not (self.page == "options" and img.get_width() * k > W * 0.8)
            iw, ih = int(img.get_width() * k * (1 if big else 0.8)), int(img.get_height() * k)
            x = W / 2 - iw / 2
            y = (y0 + i * gap) * k
            r = pygame.Rect(int(x) - 10, int(y) - 4, iw + 20, ih + 8)
            self.rects.append((r, action))
            laid.append((label, big, x, y))
        if mouse != getattr(self, "_last_mouse", None):
            self._last_mouse = mouse
            for i, (r, _) in enumerate(self.rects):
                if r.collidepoint(mouse):
                    self.sel = i
        for i, (label, big, x, y) in enumerate(laid):
            img = self._render(label, GOLD if i != self.sel else WHITE, big=big)
            iw, ih = int(img.get_width() * k), int(img.get_height() * k)
            sc = pygame.transform.smoothscale(img, (max(1, iw), max(1, ih))) if abs(k - 1) > 0.01 else img
            x = W / 2 - iw / 2
            surf.blit(sc, (int(x), int(y)))
            if i == self.sel and self.pent:
                frames = [f for f in self.pent if f is not None]
                if frames:
                    f = frames[int(self.t * 20) % len(frames)]
                    pw, ph = int(f.get_width() * k), int(f.get_height() * k)
                    ps = pygame.transform.smoothscale(f, (max(1, pw), max(1, ph))) if abs(k - 1) > 0.01 else f
                    cy = int(y + ih / 2 - ph / 2)
                    surf.blit(ps, (int(x - pw - 16 * k), cy))
                    surf.blit(ps, (int(x + iw + 16 * k), cy))
        if self.page == "options":
            hint = self._render("Click or Enter to change, right click / Left to go back a step", GREY, big=False)
            hw, hh = int(hint.get_width() * k * 0.6), int(hint.get_height() * k * 0.6)
            hs = pygame.transform.smoothscale(hint, (max(1, hw), max(1, hh)))
            surf.blit(hs, (int(W / 2 - hw / 2), int(H - 140 * k)))
