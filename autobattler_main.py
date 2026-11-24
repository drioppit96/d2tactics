"""D2 Autobattler: heroes grind rift floors in real time while you manage them.

Everything is drawn on one 800 x 600 canvas in Diablo II's own fonts, panels and buttons
(autobattler/ui.py) and scaled to the window.

Screens:
    Heroes      the roster, a small live view of the selected hero's run, his status, the buttons
    New hero    class and name
    Loot        what lies on the selected hero's floor: filters, search, click to take it
    Inventory   D2's inventory panel: the hero's gear and his 10 x 8 backpack (twice D2's);
                equip, take off, move, identify, belt potions, sell
    Pickup      what the selected hero picks up on his own
    Watch       the selected hero's run full screen

Keys: S start run, X stop, W watch, T style, L loot, I inventory, P pickup, + / - speed,
F3 timings (also written to perf.log every 30 seconds), Esc back. Ctrl+click adds heroes to a
group.
"""
import os
import sys
import time

import pygame

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from main import load_settings, load_assets, log_error          # noqa: E402  (the same engine)
from autobattler import brain, config, gear, roster             # noqa: E402
from autobattler.runs import RunManager                         # noqa: E402
from autobattler.timing import FPS, Timings                     # noqa: E402
from autobattler.ui import Look, GOLD, WHITE, GREY, RED, GREEN, BLUE, W, H   # noqa: E402

CLASS_NAMES = {"ama": "Amazon", "sor": "Sorceress", "nec": "Necromancer", "pal": "Paladin",
               "bar": "Barbarian", "dru": "Druid", "ass": "Assassin"}
STYLE_NAMES = {"balanced": "Balanced", "aggressive": "Aggressive", "careful": "Careful"}
# loot window filters: label -> item_tags it shows (None = everything)
FILTERS = [("All", None), ("Gold", {"gold"}), ("Potions", {"potions"}), ("Runes", {"runes"}), ("Gems", {"gems"}),
           ("Charms", {"charms"}), ("Jewelry", {"jewelry"}), ("Unique", {"unique"}), ("Set", {"set"}),
           ("Rare", {"rare"}), ("Magic", {"magic"}), ("Bases", {"sockets", "normal"})]
CELL = 22                      # item grid cell on the 800 x 600 canvas (the stash's cell size)
LOOT_COLS, LOOT_ROWS = 12, 14


class Perf:
    """Where the time goes: F3 shows it on screen, and perf.log gets it every 30 seconds."""

    def __init__(self):
        self.t = {}
        self.n = {}
        self.worst = {}
        self.frames = 0
        self.since = time.time()
        self.written = time.time()

    def add(self, key, secs, count):
        self.t[key] = self.t.get(key, 0.0) + secs
        self.n[key] = self.n.get(key, 0) + count
        self.worst[key] = max(self.worst.get(key, 0.0), secs)
        if key == "draw":
            self.frames += 1

    def lines(self, mgr):
        el = max(1e-6, time.time() - self.since)
        out = ["%.0f screen frames/s" % (self.frames / el)]
        g, d = self.t.get("game", 0.0), self.t.get("draw", 0.0)
        gn = max(1, self.n.get("game", 0))
        out.append("game: %.1f ms per game frame (D2 allows 40), worst burst %.0f ms" % (1000 * g / gn, 1000 * self.worst.get("game", 0)))
        out.append("drawing: %.1f ms per screen frame, worst %.0f ms" % (1000 * d / max(1, self.frames), 1000 * self.worst.get("draw", 0)))
        for r in mgr.active():
            w = r.world
            out.append("run %d: %s, floor %d, %d monsters, %s" % (r.id, r.state, r.depth,
                                                               len(w.monsters) if w is not None else 0,
                                                               "%dx%d cells" % (w.grid.w, w.grid.h) if w is not None else "building"))
        if el > 5:
            self.since = time.time()
            self.t, self.n, self.worst, self.frames = {}, {}, {}, 0
        return out

    def maybe_write(self, mgr):
        if time.time() - self.written < 30:
            return
        self.written = time.time()
        try:
            with open(os.path.join(HERE, "perf.log"), "a") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n  " + "\n  ".join(self.lines(mgr)) + "\n")
        except OSError:
            pass


class App:
    def __init__(self):
        self.cfg_game = load_settings()
        self.cfg = config.load()
        config.apply_d2_rules()
        roster.use_folder()
        pygame.init()
        w, h = self.cfg_game.getint("display", "width"), self.cfg_game.getint("display", "height")
        self.window = pygame.display.set_mode((w, h), pygame.RESIZABLE)
        pygame.display.set_caption("D2 Autobattler")
        serif = "georgia,palatinolinotype,timesnewroman,serif"
        self.sysfonts = {"small": pygame.font.SysFont(serif, 13), "med": pygame.font.SysFont(serif, 16, bold=True),
                         "big": pygame.font.SysFont(serif, 26, bold=True), "title": pygame.font.SysFont(serif, 16, bold=True)}
        self.canvas = pygame.Surface((W, H))
        self._loading("Reading Diablo II files...")
        self.assets, self.warning = load_assets(self.cfg_game, self._loading)
        self.content = getattr(self.assets, "content", None)
        self.look = Look(self.assets, self.sysfonts)
        self.timings = Timings(getattr(self.content, "src", None) if self.content else None)
        self.mgr = RunManager(self.assets, self.cfg, self.timings)
        self.heroes = {}
        self.selected = []
        self.screen_name = "roster"
        self.views = {}              # run id -> (world, LiveView)
        self.focus = None            # text field taking the keyboard: name | search | words
        self.bench = None            # the inventory screen's item handling (autobattler/gear.py)
        self.new_cls, self.new_name = "bar", ""
        self.search, self.filter = "", "All"
        self.loot_page = 0
        self.scroll = 0
        self.message = self.warning or ""
        self.regions = []
        self.mouse = (0, 0)
        self.down = None
        self.acc = 0.0
        self._dt = 0.0
        self.show_perf = False
        self.perf = Perf()
        self.reload_heroes()
        self.running = True

    # ------------------------------------------------------------ helpers
    def _loading(self, text):
        self.canvas.fill((0, 0, 0))
        f = self.sysfonts["med"]
        img = f.render(text, True, GOLD)
        self.canvas.blit(img, img.get_rect(center=(W // 2, H // 2)))
        self._present()
        pygame.event.pump()

    def _present(self):
        """The 800 x 600 canvas, scaled to fit the window (black bars where the shape differs)."""
        ww, wh = self.window.get_size()
        k = min(ww / float(W), wh / float(H))
        size = (max(1, int(W * k)), max(1, int(H * k)))
        self._ofs = ((ww - size[0]) // 2, (wh - size[1]) // 2)
        self._k = k
        self.window.fill((0, 0, 0))
        if size == (W, H):
            self.window.blit(self.canvas, self._ofs)
        else:
            self.window.blit(pygame.transform.smoothscale(self.canvas, size), self._ofs)
        pygame.display.flip()

    def logical(self, pos):
        ox, oy = getattr(self, "_ofs", (0, 0))
        k = getattr(self, "_k", 1.0) or 1.0
        return ((pos[0] - ox) / k, (pos[1] - oy) / k)

    def region(self, rect, action, *args):
        self.regions.append((pygame.Rect(rect), action, args))

    def hot(self, rect):
        return pygame.Rect(rect).collidepoint(self.mouse)

    def button(self, rect, label, action, *args, enabled=True):
        r = pygame.Rect(rect)
        self.look.button(self.canvas, r, label, hot=self.hot(r) and enabled,
                         down=enabled and self.down is not None and r.collidepoint(self.down), enabled=enabled)
        if enabled:
            self.region(r, action, *args)

    def reload_heroes(self):
        busy = self.mgr.busy_names()
        names = set()
        for d in roster.list_heroes():
            n = d.get("name")
            names.add(n)
            if n in busy and n in self.heroes:
                continue
            try:
                self.heroes[n] = roster.load(d, self.content)
            except Exception:
                import traceback
                traceback.print_exc()
        for n in list(self.heroes):
            if n not in names and n not in busy:
                del self.heroes[n]
        self.selected = [n for n in self.selected if n in self.heroes]
        if not self.selected and self.heroes:
            self.selected = [sorted(self.heroes, key=lambda n: (-self.heroes[n].level, n))[0]]

    def hero(self):
        return self.heroes.get(self.selected[0]) if self.selected else None

    def run_of(self, name):
        return next((r for r in self.mgr.active() if any(h.name == name for h in r.heroes)), None)

    def view_of(self, run):
        """The run's live view (made again when it moves to a new floor)."""
        if run is None or run.world is None or run.sim is None:
            return None
        ent = self.views.get(run.id)
        if ent is None or ent[0] is not run.world:
            from autobattler.liveview import LiveView
            lv = LiveView(run, self.assets, {"small": self.sysfonts["small"], "med": self.sysfonts["med"],
                                             "big": self.sysfonts["big"], "title": self.sysfonts["title"]})
            if self.look.hud is not None:
                lv.scene.d2_fonts = {"med": self.look.hud.f16, "big": self.look.hud.f30,
                                     "small": self.look.hud.f10, "ind": self.look.hud.ind}
            ent = self.views[run.id] = (run.world, lv)
        return ent[1]

    def draw_view(self, run, rect, follow=True):
        """A run's floor drawn into `rect` of the canvas, 1:1 like D2, centred on its first hero."""
        from render.iso import Camera
        r = pygame.Rect(rect)
        lv = self.view_of(run)
        self.look.inset(self.canvas, r)
        if run is not None and run.state in ("pause", "build") and lv is not None:
            # between floors: the old floor is over (and the heroes already stand on the new one)
            self.look.text(self.canvas, "med", "Next: floor %d..." % run.depth, GOLD,
                           r.x, r.centery - 8, "center", r.w)
            return
        if lv is None:
            self.look.text(self.canvas, "med", "Building floor %d..." % run.depth if run else "", GOLD,
                           r.x, r.centery - 8, "center", r.w)
            return
        for other in self.mgr.active():
            if other.sim is not None:
                other.sim.watched = other is run
        lv.update(self._dt, self.cfg["speed"])
        sub = self.canvas.subsurface(r.inflate(-2, -2))
        cam = getattr(lv, "_cam", None)
        if cam is None or cam.sw != sub.get_width() or cam.sh != sub.get_height():
            cam = lv._cam = Camera(sub.get_width(), sub.get_height(), 1.0)
            cam.snap(*lv.focus())
        cam.follow(*lv.focus(), dt=self._dt)
        sub.fill((0, 0, 0))
        try:
            lv.draw(sub, cam)
        except Exception:
            import traceback
            traceback.print_exc()

    # ------------------------------------------------------------ actions
    def go(self, name):
        if name != "inventory":
            self._close_bench()          # the cursor item goes back in the backpack
        self.screen_name = name
        self.focus = {"create": "name", "loot": "search", "pickup": "words"}.get(name)
        self.loot_page = 0

    def select(self, name):
        if pygame.key.get_mods() & pygame.KMOD_CTRL:
            if name in self.selected:
                self.selected.remove(name)
            else:
                self.selected.append(name)
        else:
            self.selected = [name]

    def start_run(self):
        heroes = [self.heroes[n] for n in self.selected if n in self.heroes]
        r = self.mgr.start(heroes)
        self.message = r if isinstance(r, str) else "Run started: %s" % ", ".join(h.name for h in heroes)

    def stop_run(self):
        for n in self.selected:
            r = self.run_of(n)
            if r is not None:
                r.stop_requested = True
                self.message = "%s will stop after this floor." % ", ".join(h.name for h in r.heroes)

    def cycle_style(self):
        for n in self.selected:
            h = self.heroes.get(n)
            if h is not None:
                st = brain.cycle_style(h)
                if n not in self.mgr.busy_names():
                    roster.save(h)
                self.message = "%s: %s" % (n, STYLE_NAMES[st])

    def create(self):
        p = roster.create(self.new_cls, self.new_name, self.content, self.cfg["max_heroes"])
        if p is None:
            self.message = "The roster is full (%d heroes)." % self.cfg["max_heroes"]
            return
        self.heroes[p.name] = p
        self.selected = [p.name]
        self.new_name = ""
        self.message = "%s the %s joins the roster." % (p.name, CLASS_NAMES.get(p.cls, p.cls))
        self.go("roster")
        self.reload_heroes()

    def take(self, cell, it):
        h = self.hero()
        run = self.run_of(h.name) if h else None
        if run is None:
            return
        name = "%d gold" % it.amount if it.kind == "gold" else getattr(it, "shown_name", it.name)
        if run.take(h, cell, it):
            self.message = "%s takes %s." % (h.name, name)
        else:
            self.message = "%s has no room for %s." % (h.name, name)

    def toggle_rule(self, key):
        h = self.hero()
        if h is None:
            return
        r = brain.pickup_rules(h)
        r[key] = not r.get(key)
        if h.name not in self.mgr.busy_names():
            roster.save(h)

    def set_filter(self, name):
        self.filter, self.loot_page = name, 0

    def page(self, d, pages):
        self.loot_page = max(0, min(pages - 1, self.loot_page + d))

    # ------------------------------------------------------------ input
    def handle(self, ev):
        if ev.type == pygame.QUIT:
            self.running = False
        elif ev.type == pygame.VIDEORESIZE:
            self.window = pygame.display.set_mode((ev.w, ev.h), pygame.RESIZABLE)
        elif ev.type == pygame.MOUSEMOTION:
            self.mouse = self.logical(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            self.down = self.logical(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            pos = self.logical(ev.pos)
            self.down = None
            for rect, action, args in reversed(self.regions):
                if rect.collidepoint(pos):
                    action(*args)
                    return
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 3 and self.screen_name == "inventory":
            self.mouse = self.logical(ev.pos)
            self.inv_right()
        elif ev.type == pygame.MOUSEWHEEL and self.screen_name == "roster":
            self.scroll = max(0, self.scroll - ev.y)
        elif ev.type == pygame.KEYDOWN:
            self._key(ev)

    def _key(self, ev):
        if self.focus and ev.key not in (pygame.K_ESCAPE, pygame.K_RETURN):
            field = {"name": "new_name", "search": "search", "words": None}[self.focus]
            h = self.hero()
            cur = getattr(self, field) if field else (brain.pickup_rules(h)["words"] if h else "")
            if ev.key == pygame.K_BACKSPACE:
                cur = cur[:-1]
            elif ev.unicode and ev.unicode.isprintable() and len(cur) < (15 if field == "new_name" else 40):
                if field == "new_name" and not (ev.unicode.isalnum() or ev.unicode in "-_"):
                    return
                cur += ev.unicode
            else:
                return
            if field:
                setattr(self, field, cur)
                self.loot_page = 0
            elif h is not None:
                brain.pickup_rules(h)["words"] = cur
            return
        if ev.key == pygame.K_F3:
            self.show_perf = not self.show_perf
            return
        if ev.key == pygame.K_ESCAPE:
            if self.screen_name != "roster":
                if self.screen_name == "pickup" and self.hero() and self.hero().name not in self.mgr.busy_names():
                    roster.save(self.hero())
                self.go("roster")
            return
        if ev.key == pygame.K_RETURN and self.screen_name == "create":
            self.create()
            return
        if ev.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.cfg["speed"] = min(8.0, self.cfg["speed"] * 2)
        elif ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.cfg["speed"] = max(0.25, self.cfg["speed"] / 2)
        elif self.screen_name == "inventory" and ev.key == pygame.K_w:
            self.inv_swap()
        elif self.screen_name == "roster":
            act = {pygame.K_s: self.start_run, pygame.K_x: self.stop_run, pygame.K_t: self.cycle_style,
                   pygame.K_w: lambda: self.go("watch"), pygame.K_l: lambda: self.go("loot"),
                   pygame.K_i: lambda: self.go("inventory"), pygame.K_p: lambda: self.go("pickup")}.get(ev.key)
            if act is not None and (self.hero() is not None or ev.key == pygame.K_s):
                act()

    # ------------------------------------------------------------ the frame
    MAX_CATCH_UP = 6       # game frames per screen frame at most: a slow PC slows the game, never freezes it

    def step(self, dt):
        t0 = time.perf_counter()
        self.acc += dt * FPS * self.cfg["speed"]
        n = 0
        limit = self.MAX_CATCH_UP * max(1, int(round(self.cfg["speed"])))
        while self.acc >= 1.0 and n < limit:
            self.mgr.tick()
            self.acc -= 1.0
            n += 1
        if self.acc > 2:
            self.acc = 0.0                       # (behind: drop the backlog)
        self.perf.add("game", time.perf_counter() - t0, n)

    def draw(self):
        t0 = time.perf_counter()
        self.regions = []
        self.canvas.fill((0, 0, 0))
        {"roster": self.draw_roster, "create": self.draw_create, "loot": self.draw_loot,
         "inventory": self.draw_inventory, "pickup": self.draw_pickup, "watch": self.draw_watch
         }.get(self.screen_name, self.draw_roster)()
        if self.message and self.screen_name != "watch":
            self.look.text(self.canvas, "small", self.message, GOLD, 12, 580)
        if getattr(self, "_tip", None):
            self.look.tooltip(self.canvas, self._tip, self.mouse)
        self._tip = None
        if self.show_perf:
            for i, line in enumerate(self.perf.lines(self.mgr)):
                self.look.text(self.canvas, "small", line, (120, 255, 120), 8, 40 + i * 13)
        self.perf.add("draw", time.perf_counter() - t0, 1)
        self._present()
        self.perf.maybe_write(self.mgr)

    def _title(self, text):
        self.look.text(self.canvas, "big", text, GOLD, 0, 6, "center", W)
        self.look.text(self.canvas, "small", "Speed x%g  (+ / -)" % self.cfg["speed"], GREY, 0, 16, "right", W - 14)

    def draw_roster(self):
        c, L = self.canvas, self.look
        self._title("D2 Autobattler")
        # heroes
        L.panel(c, (6, 40, 300, 428))
        L.text(c, "med", "Heroes %d / %d" % (len(self.heroes), self.cfg["max_heroes"]), GOLD, 6, 56, "center", 300)
        lst = pygame.Rect(26, 78, 260, 370)
        L.inset(c, lst)
        busy = self.mgr.busy_names()
        names = sorted(self.heroes, key=lambda n: (-self.heroes[n].level, n))
        per = lst.h // 30
        self.scroll = max(0, min(self.scroll, max(0, len(names) - per)))
        for i, n in enumerate(names[self.scroll:self.scroll + per]):
            h = self.heroes[n]
            row = pygame.Rect(lst.x + 2, lst.y + 2 + i * 30, lst.w - 4, 28)
            if n in self.selected:
                pygame.draw.rect(c, (52, 42, 26), row)
            elif self.hot(row):
                pygame.draw.rect(c, (26, 22, 18), row)
            L.text(c, "med", n, GOLD if n in self.selected else WHITE, row.x + 6, row.y + 2)
            L.text(c, "small", "Lv %d %s - floor %d" % (h.level, CLASS_NAMES.get(h.cls, h.cls),
                                                     int(getattr(h, "rift_depth", 0) or 0)), GREY, row.x + 6, row.y + 16)
            if n in busy:
                L.text(c, "small", "on a run", GREEN, row.x, row.y + 9, "right", row.w - 6)
            self.region(row, self.select, n)
        # the selected hero's run, live
        h = self.hero()
        run = self.run_of(h.name) if h else None
        L.panel(c, (312, 40, 482, 290), dark=True)
        view = pygame.Rect(330, 78, 446, 232)
        if run is not None:
            w = run.world
            area = getattr(w, "level_name", "") if w is not None else ""
            L.text(c, "med", "Floor %d  %s" % (run.depth, area), GOLD, 312, 56, "center", 482)
            self.draw_view(run, view)
            self.region(view, self.go, "watch")
        else:
            L.text(c, "med", h.name if h else "No hero selected", GOLD, 312, 56, "center", 482)
            L.inset(c, view)
            L.text(c, "med", "Not on a run" if h else "", GREY, view.x, view.centery - 8, "center", view.w)
        # his status
        L.panel(c, (312, 334, 482, 134), dark=True)
        if h is not None:
            x, y = 334, 352
            mx = max(1, getattr(h, "max_mana", 1))
            L.text(c, "small", "Life %d / %d" % (max(0, h.hp), h.max_hp), WHITE, x, y)
            L.bar(c, (x + 110, y + 2, 120, 8), h.hp / float(max(1, h.max_hp)), (170, 20, 20))
            L.text(c, "small", "Mana %d / %d" % (int(getattr(h, "mana", 0)), mx), WHITE, x, y + 16)
            L.bar(c, (x + 110, y + 18, 120, 8), getattr(h, "mana", 0) / float(mx), (40, 60, 200))
            try:
                need = h.xp_to_next()
                frac = 1.0 - need / float(max(1, need + 1)) if need else 1.0
            except Exception:
                frac = 0.0
            L.text(c, "small", "Level %d %s   %s" % (h.level, CLASS_NAMES.get(h.cls, h.cls),
                                                   STYLE_NAMES[brain.profile(h)["style"]]), GOLD, x + 250, y)
            L.text(c, "small", "Gold %d   Floor %d   Best %d" % (getattr(h, "gold", 0), int(getattr(h, "rift_depth", 0) or 0),
                                                            int(brain.profile(h).get("best", 0) or 0)),
                   WHITE, x + 250, y + 16)
            if run is not None and run.sim is not None:
                L.text(c, "small", "Now: %s" % (run.sim.brain(h).last or "..."), GOLD, x, y + 36)
                L.text(c, "small", "This run: %d floors, %d kills, %d deaths" % (run.floors, run.kills + run.sim.kills,
                                                                                getattr(run, "deaths", 0)), WHITE, x + 250, y + 36)
            for i, line in enumerate((run.log if run else [])[-3:]):
                L.text(c, "small", line, GREY, x, y + 56 + i * 14)
        # buttons
        has = h is not None
        on_run = has and run is not None
        bw, bh, gap = 150, 32, 8
        row1 = [("New hero", lambda: self.go("create"), roster.count() < self.cfg["max_heroes"]),
                ("Start run", self.start_run, has and not on_run),
                ("Stop run", self.stop_run, on_run),
                ("Watch", lambda: self.go("watch"), on_run),
                ("Style", self.cycle_style, has)]
        row2 = [("Loot", lambda: self.go("loot"), on_run),
                ("Inventory", lambda: self.go("inventory"), has),
                ("Pickup", lambda: self.go("pickup"), has),
                ("Speed -", lambda: self.cfg.__setitem__("speed", max(0.25, self.cfg["speed"] / 2)), True),
                ("Speed +", lambda: self.cfg.__setitem__("speed", min(8.0, self.cfg["speed"] * 2)), True)]
        for j, row in enumerate((row1, row2)):
            for i, (label, act, en) in enumerate(row):
                self.button((10 + i * (bw + gap), 476 + j * (bh + 6), bw, bh), label, act, enabled=en)

    def draw_create(self):
        c, L = self.canvas, self.look
        self._title("New Hero")
        L.panel(c, (150, 60, 500, 420))
        for i, cls in enumerate(roster.CLASSES):
            r = pygame.Rect(190 + (i % 2) * 220, 100 + (i // 2) * 44, 200, 34)
            self.button(r, CLASS_NAMES[cls], lambda c_=cls: setattr(self, "new_cls", c_))
            if cls == self.new_cls:
                pygame.draw.rect(c, GOLD, r.inflate(4, 4), 1)
        L.text(c, "med", "Name", GOLD, 190, 290)
        field = pygame.Rect(190, 310, 420, 28)
        L.inset(c, field)
        L.text(c, "med", self.new_name + ("_" if int(time.time() * 2) % 2 else ""), WHITE, field.x + 8, field.y + 6)
        self.button((190, 400, 200, 34), "Create", self.create, enabled=roster.count() < self.cfg["max_heroes"])
        self.button((410, 400, 200, 34), "Back", lambda: self.go("roster"))

    def _loot_items(self, run):
        items = run.ground_items() if run is not None else []
        tags = dict(FILTERS).get(self.filter)
        q = self.search.strip().lower()
        out = []
        for cell, it in items:
            if tags is not None and not (brain.item_tags(it) & tags):
                continue
            if q:
                name = ("%d gold" % it.amount) if it.kind == "gold" else \
                    str(getattr(it, "shown_name", None) or getattr(it, "name", ""))
                text = name.lower() + " " + " ".join(t.lower() for t, _ in self.look.item_lines(it, self.hero()))
                if q not in text:
                    continue
            out.append((cell, it))
        return out

    def _pack(self, items):
        """Items laid out like the stash, page after page (largest first)."""
        order = sorted(items, key=lambda ci: (-(ci[1].invw or 1) * (ci[1].invh or 1), ci[1].kind == "gold"))
        pages = []
        for cell, it in order:
            w, h = max(1, it.invw or 1), max(1, it.invh or 1)
            placed = False
            for pg in pages:
                for y in range(LOOT_ROWS - h + 1):
                    for x in range(LOOT_COLS - w + 1):
                        if all((x + i, y + j) not in pg["occ"] for i in range(w) for j in range(h)):
                            pg["occ"].update((x + i, y + j) for i in range(w) for j in range(h))
                            pg["items"].append((cell, it, x, y, w, h))
                            placed = True
                            break
                    if placed:
                        break
                if placed:
                    break
            if not placed:
                pages.append({"occ": {(i, j) for i in range(w) for j in range(h)}, "items": [(cell, it, 0, 0, w, h)]})
        return [p["items"] for p in pages] or [[]]

    def draw_loot(self):
        c, L = self.canvas, self.look
        h = self.hero()
        run = self.run_of(h.name) if h else None
        self._title("Loot")
        L.panel(c, (6, 40, 788, 432))
        # filters and search
        for i, (label, _t) in enumerate(FILTERS):
            r = pygame.Rect(22 + (i % 6) * 64, 58 + (i // 6) * 26, 60, 22)
            self.button(r, label, self.set_filter, label)
            if label == self.filter:
                pygame.draw.rect(c, GOLD, r.inflate(2, 2), 1)
        field = pygame.Rect(420, 60, 240, 22)
        L.text(c, "small", "Search", GOLD, 420, 46)
        L.inset(c, field)
        L.text(c, "med", self.search + ("_" if int(time.time() * 2) % 2 else ""), WHITE, field.x + 6, field.y + 3)
        self.button((668, 60, 100, 22), "Clear", lambda: setattr(self, "search", ""))
        items = self._loot_items(run)
        pages = self._pack(items)
        self.loot_page = max(0, min(self.loot_page, len(pages) - 1))
        gx, gy = 22, 116
        grid = pygame.Rect(gx - 1, gy - 1, LOOT_COLS * CELL + 2, LOOT_ROWS * CELL + 2)
        L.inset(c, grid)
        for i in range(LOOT_COLS + 1):
            pygame.draw.line(c, (34, 32, 28), (gx + i * CELL, gy), (gx + i * CELL, gy + LOOT_ROWS * CELL))
        for j in range(LOOT_ROWS + 1):
            pygame.draw.line(c, (34, 32, 28), (gx, gy + j * CELL), (gx + LOOT_COLS * CELL, gy + j * CELL))
        for cell, it, x, y, w, hh in pages[self.loot_page]:
            r = pygame.Rect(gx + x * CELL, gy + y * CELL, w * CELL, hh * CELL)
            tint = pygame.Surface((r.w - 1, r.h - 1), pygame.SRCALPHA)
            wanted = h is not None and brain.wants(h, it)
            tint.fill((10, 40, 10, 120) if wanted else (10, 10, 40, 120))
            c.blit(tint, (r.x + 1, r.y + 1))
            L.icon(c, it, r.x + 1, r.y + 1, r.w - 1, r.h - 1)
            self.region(r, self.take, cell, it)
            if self.hot(r):
                lines = L.item_lines(it, h)
                lines.append(("Click: %s takes it" % h.name if h else "", GREY))
                self._tip = lines
        n_all = len(run.ground_items()) if run is not None else 0
        L.text(c, "small", "%d of %d items on floor %d" % (len(items), n_all, run.depth) if run else "No run: nothing on the ground",
               WHITE, gx, gy + LOOT_ROWS * CELL + 6)
        if len(pages) > 1:
            self.button((gx + 150, gy + LOOT_ROWS * CELL + 4, 40, 20), "<", self.page, -1, len(pages))
            L.text(c, "small", "%d / %d" % (self.loot_page + 1, len(pages)), WHITE, gx + 194, gy + LOOT_ROWS * CELL + 8)
            self.button((gx + 230, gy + LOOT_ROWS * CELL + 4, 40, 20), ">", self.page, 1, len(pages))
        # the hero's backpack, to see the room he has
        if h is not None:
            L.text(c, "med", "%s's backpack" % h.name, GOLD, 330, 110)
            self._backpack(h, 330, 132)
            L.text(c, "small", "Green: his pickup rules want it.  Blue: they don't.", GREY, 330, 300)
            L.text(c, "small", "Click any item to take it with %s." % h.name, GREY, 330, 316)
            L.text(c, "small", "Items stay here until the floor ends.", GREY, 330, 332)
        self.button((640, 430, 140, 30), "Back", lambda: self.go("roster"))

    def _backpack(self, h, x0, y0):
        c, L = self.canvas, self.look
        cols, rows = getattr(h, "INV_W", 10), getattr(h, "INV_H", 7)
        L.inset(c, (x0 - 1, y0 - 1, cols * CELL + 2, rows * CELL + 2))
        for i in range(cols + 1):
            pygame.draw.line(c, (34, 32, 28), (x0 + i * CELL, y0), (x0 + i * CELL, y0 + rows * CELL))
        for j in range(rows + 1):
            pygame.draw.line(c, (34, 32, 28), (x0, y0 + j * CELL), (x0 + cols * CELL, y0 + j * CELL))
        for it in getattr(h, "inventory", []) or []:
            pos = getattr(it, "inv_pos", None)
            if not pos:
                continue
            ix, iy = pos
            try:
                w, hh = h._size(it)
            except Exception:
                w, hh = max(1, it.invw or 1), max(1, it.invh or 1)
            r = pygame.Rect(x0 + ix * CELL, y0 + iy * CELL, w * CELL, hh * CELL)
            L.icon(c, it, r.x + 1, r.y + 1, r.w - 1, r.h - 1)
            if self.hot(r):
                self._tip = L.item_lines(it, h)

    # ------------------------------------------------------------ inventory (D2's own panel)
    INV_X, INV_Y = 470, 40          # where D2's 320-wide inventory panel sits on the canvas

    def gear_bench(self):
        """The item bench for the selected hero (made again when the selection changes)."""
        h = self.hero()
        b = self.bench
        if b is not None and b.player is not h:
            self._close_bench()
            b = None
        if b is None and h is not None:
            gear.prepare(h)
            b = self.bench = gear.Bench(h, self.content)
        return b

    def _close_bench(self):
        b, self.bench = self.bench, None
        if b is None:
            return
        sold = b.finish()
        if sold:
            self.message = "%s had no room: %d item%s sold." % (b.player.name, sold, "" if sold == 1 else "s")
        self._gear_saved(b)

    def _gear_saved(self, b):
        """Idle heroes are saved after each change; a hero on a run is saved by the run."""
        if b is not None and b.changed and b.player.name not in self.mgr.busy_names():
            roster.save(b.player)
            b.changed = False

    def _inv_geometry(self):
        from render.d2hud import INV_SLOTS, GRID_X, GRID_Y, CELL as IC
        return INV_SLOTS, GRID_X, GRID_Y, IC

    def _inv_cell(self, item=None):
        """Backpack cell under the mouse; with `item`, the top-left cell that centres it on the
        mouse, like D2."""
        slots, gx, gy, ic = self._inv_geometry()
        b = self.bench
        rows = b.player.INV_H if b else gear.ROWS
        mx, my = self.mouse[0] - self.INV_X, self.mouse[1] - self.INV_Y
        if not (gx <= mx < gx + 10 * ic and gy <= my < gy + rows * ic):
            return None
        if item is None:
            return int((mx - gx) // ic), int((my - gy) // ic)
        w, hh = b.player._size(item)
        cx = int(round((mx - gx) / float(ic) - w / 2.0))
        cy = int(round((my - gy) / float(ic) - hh / 2.0))
        return max(0, min(10 - w, cx)), max(0, min(rows - hh, cy))

    def _inv_slot(self):
        slots, gx, gy, ic = self._inv_geometry()
        mx, my = self.mouse[0] - self.INV_X, self.mouse[1] - self.INV_Y
        for slot, (x, y, w, hh) in slots.items():
            if x <= mx < x + w and y <= my < y + hh:
                return slot
        return None

    def _inv_tab(self):
        from render.d2hud import D2Hud
        mx, my = self.mouse[0] - self.INV_X, self.mouse[1] - self.INV_Y
        for i, (x, y, w, hh) in enumerate(D2Hud.WEAPON_TABS):
            if x <= mx < x + w and y <= my < y + hh:
                return i % 2
        return None

    def inv_click(self):
        b = self.gear_bench()
        if b is None:
            return
        from render.d2hud import INV_CLOSE
        slots, gx, gy, ic = self._inv_geometry()
        dy = gy + b.player.INV_H * ic - 371          # the panel's bottom row moves down with the grid
        close = pygame.Rect(self.INV_X + INV_CLOSE[0], self.INV_Y + INV_CLOSE[1] + dy, INV_CLOSE[2], INV_CLOSE[3])
        if b.held is None and close.collidepoint(self.mouse):
            self.go("roster")
            return
        tab = self._inv_tab()
        if tab is not None:
            if b.held is None and tab != getattr(b.player, "weapon_set", 0):
                b.swap_weapons()
        else:
            slot = self._inv_slot()
            if slot is not None:
                b.click_slot(slot)
            else:
                cell = self._inv_cell(b.held)
                if cell is not None:
                    b.click_cell(*cell)
        self._gear_saved(b)

    def inv_right(self):
        """Right click: wear / belt / identify (Ctrl: sell); on a worn item, take it off."""
        b = self.gear_bench()
        if b is None:
            return
        if b.cursor_mode or b.held is not None:
            b.cursor_mode = None
            return
        slot = self._inv_slot()
        if slot is not None:
            b.unequip(slot)
        else:
            cell = self._inv_cell()
            it = b.player.inv_at(*cell) if cell else None
            b.right_click(it, sell=bool(pygame.key.get_mods() & pygame.KMOD_CTRL))
        self._gear_saved(b)

    def inv_sell_held(self):
        b = self.bench
        if b is not None and b.held is not None:
            b.sell(b.held)
            self._gear_saved(b)

    def inv_floor(self, it=None):
        b = self.bench
        if b is None:
            return
        if b.held is not None:
            b.drop_held()
        elif it is not None:
            b.take_from_floor(it)

    def inv_identify_all(self):
        b = self.gear_bench()
        if b is not None:
            b.identify_all()
            self._gear_saved(b)

    def inv_swap(self):
        b = self.gear_bench()
        if b is not None and b.held is None:
            b.swap_weapons()
            self._gear_saved(b)

    def draw_inventory(self):
        c, L = self.canvas, self.look
        b = self.gear_bench()
        h = b.player if b else None
        self._title("Inventory")
        if h is None:
            self.button((640, 540, 140, 30), "Back", lambda: self.go("roster"))
            return
        run = self.run_of(h.name)
        # ---- left: who he is, what he has, the buttons
        L.panel(c, (6, 40, 456, 534))
        L.text(c, "med", "%s - level %d %s" % (h.name, h.level, CLASS_NAMES.get(h.cls, h.cls)), GOLD, 6, 54, "center", 456)
        L.text(c, "small", ("On a run: rift floor %d" % run.depth) if run else "In town", GREY, 6, 74, "center", 456)
        res = getattr(h, "res", {}) or {}
        try:
            dmg = "%d-%d" % tuple(h.dmg)
        except Exception:
            dmg = "-"
        left = [("Strength", h.strength), ("Dexterity", h.dexterity), ("Vitality", h.vitality),
                ("Energy", h.energy), ("Life", "%d / %d" % (h.hp, h.max_hp)),
                ("Mana", "%d / %d" % (h.mana, h.max_mana)), ("Gold", h.gold)]
        right = [("Damage", dmg), ("Attack Rating", getattr(h, "ar", 0)), ("Defense", getattr(h, "defense", 0)),
                 ("Fire Resist", res.get("fire", 0)), ("Cold Resist", res.get("cold", 0)),
                 ("Lightning Resist", res.get("ltng", 0)), ("Poison Resist", res.get("pois", 0))]
        for col, rows in ((24, left), (244, right)):
            for i, (label, val) in enumerate(rows):
                y = 98 + i * 20
                L.text(c, "small", label, GOLD, col, y)
                v = val if isinstance(val, str) else "%d" % val
                colr = RED if (not isinstance(val, str) and label.endswith("Resist") and val < 0) else WHITE
                L.text(c, "small", v, colr, col + 196, y, "right")
        # the belt, as the bottom of D2's screen shows it
        from game import potions
        by = 252
        L.text(c, "small", "Belt", GOLD, 24, by)
        nrows = potions.belt_rows(h)
        for col in range(4):
            stack = potions.column(h, col)
            for r in range(nrows):
                rect = pygame.Rect(70 + col * 32, by - 4 + (nrows - 1 - r) * 30, 30, 28)
                L.inset(c, rect)
                if r < len(stack):
                    L.icon(c, stack[r], rect.x + 1, rect.y + 1, rect.w - 2, rect.h - 2)
                    if self.hot(rect):
                        self._tip = L.item_lines(stack[r], h)
        # the buttons
        y0 = 384
        n_unid = b.unidentified()
        self.button((24, y0, 200, 30), "Identify all (%d)" % n_unid, self.inv_identify_all, enabled=n_unid > 0)
        self.button((240, y0, 200, 30), "Swap weapons (W)", self.inv_swap, enabled=b.held is None)
        # the sell box and the floor (things put down, or pushed out with no room)
        sell = pygame.Rect(24, y0 + 40, 200, 56)
        L.inset(c, sell)
        if b.held is not None and b.sellable(b.held):
            from game.d2items import sell_price
            L.text(c, "small", "Sell for %d gold" % sell_price(b.held), GOLD, sell.x, sell.y + 20, "center", sell.w)
        else:
            L.text(c, "small", "Sell: drop an item here", GREY, sell.x, sell.y + 12, "center", sell.w)
            L.text(c, "small", "(or Ctrl + right click it)", GREY, sell.x, sell.y + 28, "center", sell.w)
        floor = pygame.Rect(240, y0 + 40, 200, 56)
        L.inset(c, floor)
        loose = b.floor()
        if not loose:
            L.text(c, "small", "Floor: put items down here", GREY, floor.x, floor.y + 20, "center", floor.w)
        for i, it in enumerate(loose[:7]):
            r = pygame.Rect(floor.x + 4 + i * 28, floor.y + 6, 26, 44)
            L.icon(c, it, r.x, r.y, r.w, r.h)
            if self.hot(r) and b.held is None:
                self._tip = L.item_lines(it, h)
            self.region(r, self.inv_floor, it)
        # what happened last, and how it works
        for i, (text, colr) in enumerate(b.messages[-2:]):
            L.text(c, "small", text, colr or GREY, 24, y0 + 104 + i * 15)
        hint = "Click the item to identify (right click cancels)" if b.cursor_mode else \
            "Click: pick up / place / wear.  Right click: wear, belt, identify; on a worn item, take it off."
        L.text(c, "small", hint, GOLD if b.cursor_mode else GREY, 24, y0 + 136)
        self.button((330, 536, 120, 28), "Back", lambda: self.go("roster"))
        # held item: anywhere outside the panel puts it on the floor
        if b.held is not None:
            self.regions.insert(0, (pygame.Rect(0, 0, W, H), self.inv_floor, ()))
            self.region(sell, self.inv_sell_held)
            self.region(floor, self.inv_floor)
        # ---- right: D2's inventory panel, 10 x 8 backpack
        self._draw_d2_inventory(b)
        self.region((self.INV_X, self.INV_Y, 320, 548), self.inv_click)
        if b.held is not None:
            w, hh = h._size(b.held)
            ic = self._inv_geometry()[3]
            L.icon(c, b.held, self.mouse[0] - w * ic / 2.0, self.mouse[1] - hh * ic / 2.0, w * ic - 1, hh * ic - 1)
            self._tip = None
        elif b.cursor_mode:
            L.text(c, "small", "?", GOLD, self.mouse[0] + 10, self.mouse[1] - 4)

    def _draw_d2_inventory(self, b):
        """D2's inventory panel (invchar6) with the hero's gear, drawn by the game's own HUD code;
        without D2 files, plain boxes in the same places."""
        c, L = self.canvas, self.look
        h = b.player
        slots, gx, gy, ic = self._inv_geometry()
        rows = h.INV_H
        height = gy + rows * ic + 61
        sub = c.subsurface(pygame.Rect(self.INV_X, self.INV_Y, 320, min(H - self.INV_Y, height)))
        hud = L.hud
        if hud is not None:
            keep = (hud.lw, getattr(hud, "world", None), hud.mouse, hud.regions, getattr(hud, "show_inv", False), hud.store)
            try:
                hud.lw, hud.world, hud.store, hud.show_inv = 320, b, None, True
                hud.mouse = (self.mouse[0] - self.INV_X, self.mouse[1] - self.INV_Y)
                hud.regions, hud.hover_lines, hud.hover_item = [], None, None
                hud._draw_inventory(sub, b, hero=h)
                tip = hud.hover_lines
            except Exception:
                import traceback
                traceback.print_exc()
                hud = None
                tip = None
            finally:
                if L.hud is not None:
                    (L.hud.lw, L.hud.world, L.hud.mouse, L.hud.regions, L.hud.show_inv, L.hud.store) = keep
            if hud is not None:
                # the purse: gold only (the essences are D2 Tactics' own)
                from render.d2hud import PURSE_BOX
                dy = gy + rows * ic - 371
                box = pygame.Rect(PURSE_BOX[0], PURSE_BOX[1] + dy, PURSE_BOX[2], PURSE_BOX[3])
                sub.fill((17, 16, 14), box)
                pygame.draw.rect(sub, (74, 66, 50), box, 1)
                L.text(sub, "med", "Gold  %d" % h.gold, GOLD, box.x + 10, box.y + 15)
                if tip and b.held is None:
                    self._tip = tip
                return
        # plain version
        L.panel(sub, (0, 0, 320, sub.get_height()))
        mx, my = self.mouse[0] - self.INV_X, self.mouse[1] - self.INV_Y
        for slot, (x, y, w, hh) in slots.items():
            r = pygame.Rect(x, y, w, hh)
            L.inset(sub, r)
            it = h.equipment.get(slot)
            if it is not None:
                L.icon(sub, it, x + 1, y + 1, w - 2, hh - 2)
                if r.collidepoint((mx, my)) and b.held is None:
                    self._tip = L.item_lines(it, h)
        L.inset(sub, (gx - 1, gy - 1, 10 * ic + 2, rows * ic + 2))
        for it in h.inventory:
            pos = getattr(it, "inv_pos", None)
            if not pos:
                continue
            w, hh = h._size(it)
            r = pygame.Rect(gx + pos[0] * ic, gy + pos[1] * ic, w * ic, hh * ic)
            L.icon(sub, it, r.x + 1, r.y + 1, r.w - 2, r.h - 2)
            if r.collidepoint((mx, my)) and b.held is None:
                self._tip = L.item_lines(it, h)
        L.text(sub, "med", "Gold  %d" % h.gold, GOLD, 60, gy + rows * ic + 20)

    def draw_pickup(self):
        c, L = self.canvas, self.look
        h = self.hero()
        self._title("Pickup")
        L.panel(c, (100, 40, 600, 432))
        if h is None:
            return
        L.text(c, "med", "What %s picks up on his own" % h.name, GOLD, 100, 58, "center", 600)
        rules = brain.pickup_rules(h)
        for i, (key, label, _d) in enumerate(brain.PICKUP_RULES):
            r = pygame.Rect(140, 84 + i * 22, 520, 21)
            box = pygame.Rect(r.x, r.y + 3, 16, 16)
            L.inset(c, box)
            if rules.get(key):
                pygame.draw.line(c, GOLD, (box.x + 3, box.centery), (box.x + 7, box.bottom - 4), 2)
                pygame.draw.line(c, GOLD, (box.x + 7, box.bottom - 4), (box.right - 3, box.y + 3), 2)
            L.text(c, "med", label, WHITE if rules.get(key) else GREY, r.x + 26, r.y + 3)
            self.region(r, self.toggle_rule, key)
        y = 84 + len(brain.PICKUP_RULES) * 22 + 6
        L.text(c, "small", "Also anything whose name contains (comma separated):", GOLD, 140, y)
        field = pygame.Rect(140, y + 16, 520, 24)
        L.inset(c, field)
        L.text(c, "med", rules.get("words", "") + ("_" if int(time.time() * 2) % 2 else ""), WHITE, field.x + 6, field.y + 4)
        self.button((520, y + 50, 140, 30), "Done", lambda: self._key_escape())

    def _key_escape(self):
        h = self.hero()
        if h is not None and h.name not in self.mgr.busy_names():
            roster.save(h)
        self.go("roster")

    def draw_watch(self):
        c, L = self.canvas, self.look
        h = self.hero()
        run = self.run_of(h.name) if h else None
        if run is None:
            self._title("Watch")
            L.text(c, "med", "This hero is not on a run. Esc goes back.", GOLD, 0, 280, "center", W)
            return
        self.draw_view(run, (0, 0, W, H))
        bar = pygame.Surface((W, 22 + 18 * len(run.heroes)), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 150))
        c.blit(bar, (0, 0))
        L.text(c, "med", "Floor %d  %s" % (run.depth, getattr(run.world, "level_name", "") if run.world else ""), GOLD, 10, 4)
        for i, x in enumerate(run.heroes):
            thought = run.sim.brain(x).last if run.sim is not None else ""
            L.text(c, "small", "%s  life %d/%d  mana %d   %s" % (x.name, max(0, x.hp), x.max_hp, int(getattr(x, "mana", 0)), thought),
                   WHITE if x.alive else RED, 10, 24 + i * 18)
        L.text(c, "small", "Esc: back   + / -: speed x%g" % self.cfg["speed"], GREY, 0, 584, "right", W - 10)
        self.region((0, 0, W, H), lambda: None)

    def run(self):
        last = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            self._dt = min(0.25, now - last)
            last = now
            for ev in pygame.event.get():
                self.handle(ev)
            self.step(self._dt)
            self.draw()
            pygame.time.Clock().tick(60)
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
