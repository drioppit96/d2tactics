"""Runs: one hero (or a group) grinding rift floors one after another, in real time.

A run builds a rift floor (game/rift.py, at twice the usual size when big_maps is on), puts the
heroes at its start, and plays it frame by frame with autobattler/realtime.py until the floor's
boss is dead (next floor, one deeper) or every hero on the run is dead (the run is over).

Between floors the heroes are healed, as if they had been back to town. Heroes are saved after
every floor and when the run ends.

RunManager holds every run of the account and plays at most max_active heroes at once.

The rift module keeps the plan of each floor in module globals (PLANS, _SEED). Several runs share
them, so each run keeps its own floor's plan and puts it back before each of its frames.

Without Diablo II files (placeholder art) a run plays on the engine's simple generated cave
instead, with the monster farthest from the start as its boss. That is also how the tests run.
"""
import random

from . import brain, realtime, roster, timing

STATES = ("build", "fight", "pause", "over")


class Run:
    _ids = 0

    def __init__(self, heroes, assets, cfg, timings=None):
        Run._ids += 1
        self.id = Run._ids
        self.heroes = list(heroes)
        self.assets = assets
        self.cfg = cfg
        self.timings = timings
        self.state = "build"
        self.depth = max(1, max(int(getattr(h, "rift_depth", 0) or 0) for h in self.heroes) + 1)
        self.world = None
        self.sim = None
        self.pause = 0
        self.floors = 0
        self.kills = 0
        self.stop_requested = False
        self.result = None
        self.log = []
        self._plan = None
        self._seed = None
        self._lid = None

    @property
    def leader(self):
        return self.heroes[0]

    def title(self):
        names = ", ".join(h.name for h in self.heroes)
        return "%s - floor %d" % (names, self.depth)

    def note(self, text):
        self.log.append(text)
        del self.log[:-40]

    # ------------------------------------------------------------ floors
    def build(self):
        from game import rift
        a = self.assets
        for h in self.heroes:
            brain.spend_points(h)
            h._ab_level = h.level
            h.hp, h.alive = h.max_hp, True
            h.mana = getattr(h, "max_mana", getattr(h, "mana", 0))
        if getattr(a, "act_kit", None) is not None:
            rift.BIG = bool(self.cfg.get("big_maps", True))
            rift.forget(None)
            rift.rift_seed(self.leader)
            lid = rift.level_id(self.depth)
            from game.actworld import make_world
            w = make_world(a.act_kit, a.act_info, a.content, lid, player=self.leader,
                           seed=random.randrange(1 << 30))
            self._lid = lid
            self._plan = dict(rift.PLANS.get(lid) or {})
            self._seed = rift._SEED
        else:
            from game.world import World
            w = World(seed=random.randrange(1 << 30), depth_level=self.depth, player=self.leader)
            self._mark_boss(w)
        self._place_group(w)
        w.mode = "explore"
        self.world = w
        self.sim = realtime.Sim(w, self.heroes, self.timings, self.cfg.get("move_scale", 1.0))
        self.state = "fight"
        self.note("Floor %d: %s" % (self.depth, getattr(w, "level_name", "") or "rift"))

    def _mark_boss(self, w):
        foes = [m for m in w.monsters if not getattr(m, "ally", False)]
        if foes:
            boss = max(foes, key=lambda m: abs(m.x - w.player.x) + abs(m.y - w.player.y))
            boss.rift_boss = True
            boss.max_hp = boss.hp = int(boss.max_hp * 2.5)

    def _place_group(self, w):
        """Heroes after the first stand beside him; to the engine they are party members."""
        if len(self.heroes) < 2:
            return
        w.party = list(self.heroes)
        taken = {m.pos for m in w.monsters} | {w.player.pos}
        for h in self.heroes[1:]:
            cell = None
            try:
                cell = w._free_cell_near(w.player.pos, 6)
            except Exception:
                cell = None
            if cell is None or cell in taken:
                ring = w.grid.reachable(w.player.pos, 6) if hasattr(w.grid, "reachable") else {}
                cell = next((c for c in ring if c not in taken), w.player.pos)
            h.x, h.y = cell
            taken.add(cell)
            h.alive = True
            from game import tactics
            tactics._as_follower(w, h)      # the fields the engine expects of a party hero

    def _restore_rift(self):
        if self._lid is None:
            return
        from game import rift
        rift.PLANS[self._lid] = self._plan
        rift._SEED = self._seed

    # ------------------------------------------------------------ frames
    def tick(self):
        if self.state == "build":
            self.build()
            return
        if self.state == "pause":
            self.pause -= 1
            if self.pause <= 0:
                if self.stop_requested:
                    self.finish("stopped")
                else:
                    self.depth += 1
                    self.state = "build"
            return
        if self.state != "fight":
            return
        self._restore_rift()
        xp0 = self.leader.xp
        self.sim.tick()
        self._share_xp(self.leader.xp - xp0)
        for h in self.heroes:
            if h.alive and h.level != getattr(h, "_ab_level", h.level):
                h._ab_level = h.level
                brain.spend_points(h)       # a level up: new points go where his plan says
                self.note("%s reached level %d." % (h.name, h.level))
        if self.sim.wiped():
            self.kills += self.sim.kills
            self.note("Everyone fell on floor %d." % self.depth)
            self.finish("died")
        elif self.sim.cleared():
            self.kills += self.sim.kills
            self.floors += 1
            for h in self.heroes:
                h.rift_depth = max(int(getattr(h, "rift_depth", 0) or 0), self.depth)
                roster.save(h)
            self.note("Floor %d cleared." % self.depth)
            self.state = "pause"
            self.pause = int(self.cfg.get("floor_pause", 3) * timing.FPS)
        elif self.stop_requested:
            self.finish("stopped")

    def _share_xp(self, gained):
        """Kills give experience to world.player; the rest of the group gets the same amount."""
        if gained <= 0 or len(self.heroes) < 2:
            return
        for h in self.heroes[1:]:
            if h.alive:
                try:
                    h.gain_xp(gained)
                except Exception:
                    h.xp += gained

    def finish(self, why):
        self.state = "over"
        self.result = why
        for h in self.heroes:
            h.hp, h.alive = h.max_hp, True
            for attr in ("ally", "party_member"):
                if hasattr(h, attr):
                    setattr(h, attr, False)
            roster.save(h)
        self.world = None
        self.sim = None


class RunManager:
    def __init__(self, assets, cfg, timings=None):
        self.assets = assets
        self.cfg = cfg
        self.timings = timings
        self.runs = []

    def active(self):
        return [r for r in self.runs if r.state != "over"]

    def busy_names(self):
        return {h.name for r in self.active() for h in r.heroes}

    def free_slots(self):
        return self.cfg["max_active"] - sum(len(r.heroes) for r in self.active())

    def start(self, heroes):
        """Start a run for these heroes (a group when more than one). -> Run, or a reason why not."""
        heroes = list(heroes)
        if not heroes:
            return "Pick a hero first."
        if len(heroes) > self.cfg["max_group"]:
            return "At most %d heroes on one run." % self.cfg["max_group"]
        if any(h.name in self.busy_names() for h in heroes):
            return "One of them is already on a run."
        if len(heroes) > self.free_slots():
            return "Only %d heroes can be on runs at the same time." % self.cfg["max_active"]
        r = Run(heroes, self.assets, self.cfg, self.timings)
        self.runs.append(r)
        return r

    def tick(self):
        built = False
        for r in self.active():
            if r.state == "build":
                if built:
                    continue                 # one new floor per frame: no pile-up of building
                built = True
            try:
                r.tick()
            except Exception:
                import traceback
                traceback.print_exc()
                r.note("This run stopped because of an error (see the console / errors.log).")
                r.finish("error")
        # finished runs are kept for their log, but only the last 30
        over = [r for r in self.runs if r.state == "over"]
        for r in over[:-30]:
            self.runs.remove(r)
