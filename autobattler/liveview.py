"""The watch screen's picture: the engine's renderer, driven straight from the real-time state.

The engine's Scene plays its events one after another with pauses between them, the way turns
play out. In real time that queue only falls behind (and looks turn-based), so here it is not
used for units at all. Every frame each unit's picture is set from autobattler/realtime.py:

    position    between the cell it stands on and the next cell of its walk, by how far into that
                step it is: an even glide at its D2 speed, no tile-to-tile hops
    animation   WL while walking, A1 while swinging, SC while casting, GH in hit recovery, DD when
                it dies; attack, cast and hit recovery play over exactly the frames the real-time
                code gives them (IAS / FCR / FHR), so a faster hero is visibly faster
    facing      where it walks or what it hits

Spell graphics, missiles, explosions, overlays, damage numbers and deaths still go through the
Scene's own code, the moment they happen.
"""
from render.scene import Scene

from . import timing

EFFECTS = {"projectile", "spiral", "overlay", "area", "nova", "teleport", "damage", "miss", "heal",
           "death", "resurrect", "drop", "flames", "explosion", "levelup", "skill_sound"}
WALK_CYCLE = 1.6            # walk animation cycles per second of game time (as the Scene does)


class LiveView:
    def __init__(self, run, assets, fonts):
        self.run = run
        self.world = run.world
        self.sim = run.sim
        self.scene = Scene(run.world, assets, fonts)
        self.scene.queue = []

    def update(self, dt, speed=1.0):
        sc, w = self.scene, self.world
        sc.speed = speed
        evs = list(w.events)
        del w.events[:]
        for ev in evs:
            if ev and ev[0] in EFFECTS:
                try:
                    sc._start(ev)
                except Exception:
                    pass
        sc.queue, sc.current, sc.wait = [], None, 0.0
        sc.update(dt)                          # missiles, explosions, floating numbers, overlays
        game_dt = dt * speed
        for u in [w.player] + list(w.monsters):
            self._sync(u, game_dt)

    def _sync(self, u, gdt):
        v = self.scene.view(u)
        v.path = []
        v.slide = None
        if not u.alive:
            if v.mode not in ("DD", "DT"):
                v.mode, v.t, v.dur = "DD", 0.0, 0.45
            return
        s = self.sim.st.get(id(u)) if self.sim is not None else None
        x, y = float(u.x), float(u.y)
        if s is not None and s.mode == "walk" and s.path:
            nx, ny = s.path[0]
            f = max(0.0, min(1.0, s.prog))
            x, y = x + (nx - x) * f, y + (ny - y) * f
            if (nx, ny) != (u.x, u.y):
                v.facing = (nx - u.x, ny - u.y)
            if v.mode != "WL":
                v.mode, v.t = "WL", 0.0
            v.t += gdt * WALK_CYCLE
        elif s is not None and s.mode in ("attack", "cast", "gethit") and getattr(s, "total", 0):
            mode = {"attack": "A1", "cast": "SC", "gethit": "GH"}[s.mode]
            v.mode = mode
            v.dur = s.total / float(timing.FPS)
            v.t = max(0.0, (s.total - s.frames) / float(timing.FPS))
            v.facing = u.facing
        else:
            if v.mode not in ("NU",):
                v.mode, v.t = "NU", 0.0
            v.t += gdt
            v.facing = u.facing
        v.rx, v.ry = x, y
        v.shown_hp = u.hp

    def draw(self, surf, cam):
        self.scene.draw(surf, cam, None, None, None)

    def focus(self):
        return self.scene.player_world_pos()
