"""D2 Autobattler: heroes grind rift floors in real time while you manage them.

This is a working first screen, not the final menu: a roster on the left (create, select, start
and stop runs), the active runs on the right, and a watch view for any run. The final manager
screen replaces it once its layout is settled.

Keys and mouse:
    click a hero            select it (Ctrl+click adds more heroes for a group run)
    S / Start run           start a run for the selected heroes
    X / Stop run            the selected heroes' run stops after the current floor
    W / click a run         watch that run (Esc goes back)
    T / Style               the selected heroes' fighting style (balanced, aggressive, careful)
    + / -                   game speed
"""
import os
import sys
import time

import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from main import load_settings, load_assets, log_error          # noqa: E402  (the same engine)
from autobattler import brain, config, roster                   # noqa: E402
from autobattler.runs import RunManager                         # noqa: E402
from autobattler.timing import FPS, Timings                     # noqa: E402

GOLD = (199, 179, 119)
TEXT = (220, 220, 220)
GREY = (140, 140, 140)
RED = (220, 80, 60)
GREEN = (110, 200, 110)
BG = (14, 12, 10)
PANEL = (28, 24, 20)
LINE = (70, 58, 44)
CLASS_NAMES = {"ama": "Amazon", "sor": "Sorceress", "nec": "Necromancer", "pal": "Paladin",
               "bar": "Barbarian", "dru": "Druid", "ass": "Assassin"}


class Button:
    def __init__(self, rect, label, action, enabled=True):
        self.rect = pygame.Rect(rect)
        self.label, self.action, self.enabled = label, action, enabled


class App:
    def __init__(self):
        self.cfg_game = load_settings()
        self.cfg = config.load()
        config.apply_d2_rules()
        roster.use_folder()
        pygame.init()
        w, h = self.cfg_game.getint("display", "width"), self.cfg_game.getint("display", "height")
        self.screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        pygame.display.set_caption("D2 Autobattler")
        serif = "georgia,palatinolinotype,timesnewroman,serif"
        self.f = {"s": pygame.font.SysFont(serif, 15), "m": pygame.font.SysFont(serif, 18, bold=True),
                  "b": pygame.font.SysFont(serif, 28, bold=True)}
        self.clock = pygame.time.Clock()
        self._loading("Reading Diablo II files...")
        self.assets, self.warning = load_assets(self.cfg_game, self._loading)
        content = getattr(self.assets, "content", None)
        self.content = content
        self.timings = Timings(getattr(content, "src", None) if content else None)
        self.mgr = RunManager(self.assets, self.cfg, self.timings)
        self.heroes = {}                 # name -> Player (one object per hero, shared with its run)
        self.selected = []
        self.screen_name = "roster"      # roster | create | watch
        self.watch = None
        self.scene = None
        self.cam = None
        self.new_cls = "bar"
        self.new_name = ""
        self.message = self.warning or ""
        self.acc = 0.0
        self.buttons = []
        self.reload_heroes()
        self.running = True

    # ------------------------------------------------------------ helpers
    def _loading(self, text):
        self.screen.fill(BG)
        surf = self.f["m"].render(text, True, GOLD) if hasattr(self, "f") else None
        if surf is not None:
            self.screen.blit(surf, surf.get_rect(center=self.screen.get_rect().center))
        pygame.display.flip()
        pygame.event.pump()

    def reload_heroes(self):
        busy = self.mgr.busy_names()
        datas = roster.list_heroes()
        names = set()
        for d in datas:
            n = d.get("name")
            names.add(n)
            if n in busy and n in self.heroes:
                continue                 # (a hero on a run keeps the object the run plays)
            try:
                self.heroes[n] = roster.load(d, self.content)
            except Exception:
                import traceback
                traceback.print_exc()
        for n in list(self.heroes):
            if n not in names and n not in busy:
                del self.heroes[n]
        self.selected = [n for n in self.selected if n in self.heroes]

    def text(self, s, pos, font="s", color=TEXT, center=False):
        surf = self.f[font].render(str(s), True, color)
        r = surf.get_rect(center=pos) if center else surf.get_rect(topleft=pos)
        self.screen.blit(surf, r)
        return r

    def button(self, rect, label, action, enabled=True):
        b = Button(rect, label, action, enabled)
        pygame.draw.rect(self.screen, (60, 48, 34) if enabled else (34, 30, 26), b.rect)
        pygame.draw.rect(self.screen, GOLD if enabled else LINE, b.rect, 1)
        self.text(label, b.rect.center, "m", GOLD if enabled else GREY, center=True)
        self.buttons.append(b)
        return b

    def run_of(self, name):
        return next((r for r in self.mgr.active() if any(h.name == name for h in r.heroes)), None)

    # ------------------------------------------------------------ actions
    def start_run(self):
        heroes = [self.heroes[n] for n in self.selected if n in self.heroes]
        r = self.mgr.start(heroes)
        self.message = r if isinstance(r, str) else "Run started: %s" % ", ".join(h.name for h in heroes)

    def cycle_style(self):
        """The selected heroes' fighting style: balanced -> aggressive -> careful."""
        for n in self.selected:
            h = self.heroes.get(n)
            if h is not None:
                st = brain.cycle_style(h)
                if n not in self.mgr.busy_names():
                    roster.save(h)       # (a hero on a run is saved with it after the floor)
                self.message = "%s fights %s now." % (n, {"balanced": "balanced", "aggressive": "aggressively",
                                                          "careful": "carefully"}[st])

    def stop_run(self):
        for n in self.selected:
            r = self.run_of(n)
            if r is not None:
                r.stop_requested = True
                self.message = "%s will stop after this floor." % ", ".join(h.name for h in r.heroes)

    def open_watch(self, run):
        if run is None:
            return
        for r in self.mgr.active():
            if r.sim is not None:
                r.sim.watched = False
        self.watch = run
        self.scene = None
        self.screen_name = "watch"

    def create(self):
        if roster.count() >= self.cfg["max_heroes"]:
            self.message = "The roster is full (%d heroes)." % self.cfg["max_heroes"]
            return
        p = roster.create(self.new_cls, self.new_name, self.content, self.cfg["max_heroes"])
        if p is None:
            self.message = "The roster is full."
            return
        self.heroes[p.name] = p
        self.selected = [p.name]
        self.new_name = ""
        self.screen_name = "roster"
        self.message = "%s the %s joins the roster." % (p.name, CLASS_NAMES.get(p.cls, p.cls))
        self.reload_heroes()

    # ------------------------------------------------------------ input
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((ev.w, ev.h), pygame.RESIZABLE)
            if self.cam is not None:
                self.cam.resize(ev.w, ev.h)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.buttons:
                if b.enabled and b.rect.collidepoint(ev.pos):
                    b.action()
                    return
            if self.screen_name == "roster":
                self._click_roster(ev.pos)
        elif ev.type == pygame.MOUSEWHEEL and self.screen_name == "watch" and self.cam is not None:
            self.cam.scale = max(1.0, min(3.5, self.cam.scale + ev.y * 0.25))
        elif ev.type == pygame.KEYDOWN:
            self._key(ev)

    def _key(self, ev):
        if self.screen_name == "create":
            if ev.key == pygame.K_ESCAPE:
                self.screen_name = "roster"
            elif ev.key == pygame.K_RETURN:
                self.create()
            elif ev.key == pygame.K_BACKSPACE:
                self.new_name = self.new_name[:-1]
            elif ev.unicode and (ev.unicode.isalnum() or ev.unicode in "-_") and len(self.new_name) < 15:
                self.new_name += ev.unicode
            return
        if ev.key == pygame.K_ESCAPE:
            if self.screen_name == "watch":
                self.screen_name = "roster"
                if self.watch is not None and self.watch.sim is not None:
                    self.watch.sim.watched = False
                self.watch = None
            return
        if ev.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.cfg["speed"] = min(8.0, self.cfg["speed"] * 2)
        elif ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.cfg["speed"] = max(0.25, self.cfg["speed"] / 2)
        elif ev.key == pygame.K_s and self.screen_name == "roster":
            self.start_run()
        elif ev.key == pygame.K_x and self.screen_name == "roster":
            self.stop_run()
        elif ev.key == pygame.K_t and self.screen_name == "roster":
            self.cycle_style()
        elif ev.key == pygame.K_w and self.screen_name == "roster" and self.selected:
            self.open_watch(self.run_of(self.selected[0]))

    def _click_roster(self, pos):
        for name, rect in getattr(self, "_hero_rects", []):
            if rect.collidepoint(pos):
                ctrl = pygame.key.get_mods() & pygame.KMOD_CTRL
                if ctrl:
                    if name in self.selected:
                        self.selected.remove(name)
                    else:
                        self.selected.append(name)
                else:
                    self.selected = [name]
                return
        for run, rect in getattr(self, "_run_rects", []):
            if rect.collidepoint(pos):
                self.open_watch(run)
                return

    # ------------------------------------------------------------ the frame
    def step(self, dt):
        """Play D2 frames for this much real time (all runs, watched or not)."""
        self.acc += dt * FPS * self.cfg["speed"]
        n = 0
        while self.acc >= 1.0 and n < FPS * 4:
            self.mgr.tick()
            self.acc -= 1.0
            n += 1
        if self.acc > FPS:
            self.acc = 0.0               # (too slow to keep up: drop the backlog instead of spiralling)

    def draw(self):
        self.buttons = []
        self.screen.fill(BG)
        if self.screen_name == "create":
            self.draw_create()
        elif self.screen_name == "watch":
            self.draw_watch()
        else:
            self.draw_roster()
        pygame.display.flip()

    def draw_roster(self):
        W, H = self.screen.get_size()
        self.text("D2 Autobattler", (24, 16), "b", GOLD)
        self.text("Speed x%g   (+ / -)" % self.cfg["speed"], (W - 220, 26), "s", GREY)
        left = pygame.Rect(20, 64, W // 2 - 30, H - 150)
        right = pygame.Rect(W // 2 + 10, 64, W // 2 - 30, H - 150)
        for r in (left, right):
            pygame.draw.rect(self.screen, PANEL, r)
            pygame.draw.rect(self.screen, LINE, r, 1)
        self.text("Heroes %d / %d" % (len(self.heroes), self.cfg["max_heroes"]), (left.x + 12, left.y + 8), "m", GOLD)
        busy = self.mgr.busy_names()
        self._hero_rects = []
        y = left.y + 40
        for name in sorted(self.heroes, key=lambda n: (-self.heroes[n].level, n)):
            h = self.heroes[name]
            row = pygame.Rect(left.x + 8, y, left.w - 16, 26)
            if name in self.selected:
                pygame.draw.rect(self.screen, (60, 46, 30), row)
            state = "on a run" if name in busy else ""
            self.text("%s" % name, (row.x + 6, row.y + 4), "s", GOLD if name in self.selected else TEXT)
            self.text("Lv %d %s" % (h.level, CLASS_NAMES.get(h.cls, h.cls)), (row.x + 170, row.y + 4), "s", TEXT)
            self.text("floor %d  %s" % (int(getattr(h, "rift_depth", 0) or 0), brain.profile(h)["style"]),
                      (row.x + 330, row.y + 4), "s", GREY)
            if state:
                self.text(state, (row.right - 80, row.y + 4), "s", GREEN)
            self._hero_rects.append((name, row))
            y += 28
            if y > left.bottom - 30:
                break
        active = self.mgr.active()
        self.text("Runs %d / %d heroes busy" % (sum(len(r.heroes) for r in active), self.cfg["max_active"]),
                  (right.x + 12, right.y + 8), "m", GOLD)
        self._run_rects = []
        y = right.y + 40
        for r in self.mgr.runs[::-1]:
            row = pygame.Rect(right.x + 8, y, right.w - 16, 44)
            col = TEXT if r.state != "over" else GREY
            self.text(r.title(), (row.x + 6, row.y + 2), "s", GOLD if r.state != "over" else GREY)
            hp = ""
            if r.state == "fight":
                hp = "   ".join("%s %d/%d" % (h.name, max(0, h.hp), h.max_hp) for h in r.heroes)
            status = {"build": "building the floor", "fight": "fighting", "pause": "floor cleared",
                      "over": "ended (%s)" % (r.result or "")}.get(r.state, r.state)
            self.text("%s - floors %d, kills %d   %s" % (status, r.floors, r.kills, hp), (row.x + 6, row.y + 22), "s", col)
            if r.state != "over":
                self._run_rects.append((r, row))
            y += 48
            if y > right.bottom - 50:
                break
        by = H - 74
        self.button((20, by, 160, 40), "New hero", self._open_create,
                    roster.count() < self.cfg["max_heroes"])
        self.button((190, by, 160, 40), "Start run (S)", self.start_run, bool(self.selected))
        self.button((360, by, 160, 40), "Stop run (X)", self.stop_run,
                    any(self.run_of(n) for n in self.selected))
        self.button((530, by, 160, 40), "Watch (W)", lambda: self.open_watch(self.run_of(self.selected[0])),
                    bool(self.selected) and self.run_of(self.selected[0]) is not None)
        self.button((700, by, 160, 40), "Style (T)", self.cycle_style, bool(self.selected))
        if self.message:
            self.text(self.message, (20, H - 28), "s", GOLD)

    def _open_create(self):
        self.screen_name = "create"

    def draw_create(self):
        W, H = self.screen.get_size()
        self.text("New hero", (24, 16), "b", GOLD)
        x, y = 24, 80
        for cls in roster.CLASSES:
            def pick(c=cls):
                self.new_cls = c
            b = self.button((x, y, 170, 40), CLASS_NAMES[cls], pick)
            if cls == self.new_cls:
                pygame.draw.rect(self.screen, (240, 210, 120), b.rect, 3)
            x += 180
            if x > W - 190:
                x, y = 24, y + 50
        y += 70
        self.text("Name (type it): %s_" % self.new_name, (24, y), "m", TEXT)
        self.button((24, y + 50, 160, 40), "Create (Enter)", self.create)
        self.button((194, y + 50, 160, 40), "Back (Esc)", lambda: setattr(self, "screen_name", "roster"))
        if self.message:
            self.text(self.message, (24, H - 28), "s", GOLD)

    def draw_watch(self):
        r = self.watch
        W, H = self.screen.get_size()
        if r is None or r.state == "over":
            self.text("This run is over. Esc goes back.", (24, 24), "m", GOLD)
            return
        if r.world is None or r.sim is None:
            self.text("Building floor %d..." % r.depth, (24, 24), "m", GOLD)
            return
        r.sim.watched = True
        if getattr(self.assets, "act_kit", None) is not None:
            self._draw_scene(r)
        else:
            self._draw_topdown(r)
        self.text(r.title(), (16, 10), "m", GOLD)
        y = 36
        for h in r.heroes:
            thought = r.sim.brain(h).last if r.sim is not None else ""
            self.text("%s  life %d/%d  mana %d   %s" % (h.name, max(0, h.hp), h.max_hp, int(getattr(h, "mana", 0)),
                                                     thought), (16, y), "s", TEXT if h.alive else RED)
            y += 20
        self.text("Esc: back   wheel: zoom   +/-: speed x%g" % self.cfg["speed"], (16, H - 26), "s", GREY)

    def _draw_scene(self, r):
        """The engine's own renderer, fed by the run's events."""
        from render.iso import Camera
        from render.scene import Scene
        if self.scene is None or self.scene.world is not r.world:
            self.scene = Scene(r.world, self.assets, {"small": self.f["s"], "med": self.f["m"],
                                                       "big": self.f["b"], "title": self.f["m"]})
            W, H = self.screen.get_size()
            zoom = getattr(self.assets, "native_scale", 1.5)
            self.cam = Camera(W, H, zoom)
            wx, wy = self.scene.player_world_pos()
            self.cam.snap(wx, wy)
        self.scene.update(self._dt)
        wx, wy = self.scene.player_world_pos()
        self.cam.follow(wx, wy, self._dt)
        W, H = self.screen.get_size()
        z = self.cam.scale
        ow, oh = max(1, int(W / z)), max(1, int(H / z))
        off = pygame.Surface((ow, oh))
        rcam = Camera(ow, oh, 1.0)
        rcam.wx, rcam.wy = self.cam.wx, self.cam.wy
        self.scene.draw(off, rcam, None, None, None)
        self.screen.blit(pygame.transform.scale(off, (W, H)), (0, 0))

    def _draw_topdown(self, r):
        """Without Diablo II files: the floor seen from above (grey floor, red monsters, gold heroes)."""
        w = r.world
        W, H = self.screen.get_size()
        g = w.grid
        lead = next((h for h in r.heroes if h.alive), r.heroes[0])
        cs = 8
        ox, oy = W // 2 - lead.x * cs, H // 2 - lead.y * cs
        x0, x1 = max(0, -ox // cs), min(g.w, (W - ox) // cs + 1)
        y0, y1 = max(0, -oy // cs), min(g.h, (H - oy) // cs + 1)
        for yy in range(y0, y1):
            for xx in range(x0, x1):
                if g.walkable(xx, yy):
                    pygame.draw.rect(self.screen, (44, 40, 36), (ox + xx * cs, oy + yy * cs, cs - 1, cs - 1))
        for m in w.monsters:
            if m.alive and not getattr(m, "ally", False):
                col = (255, 140, 40) if getattr(m, "rift_boss", False) else RED
                pygame.draw.circle(self.screen, col, (ox + m.x * cs + cs // 2, oy + m.y * cs + cs // 2), cs // 2 + 1)
        for h in r.heroes:
            if h.alive:
                pygame.draw.circle(self.screen, GOLD, (ox + h.x * cs + cs // 2, oy + h.y * cs + cs // 2), cs // 2 + 2)

    def run(self):
        self._dt = 0.0
        last = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            self._dt = min(0.25, now - last)
            last = now
            for ev in pygame.event.get():
                self.handle(ev)
            self.step(self._dt)
            self.draw()
            self.clock.tick(60)
        for r in self.mgr.active():
            r.finish("stopped")
        pygame.quit()


if __name__ == "__main__":
    try:
        App().run()
    except Exception:
        import traceback
        log_error(traceback.format_exc())
        traceback.print_exc()
        print("\nThe error was also written to errors.log in the game folder.")
        sys.exit(1)
    sys.exit(0)
