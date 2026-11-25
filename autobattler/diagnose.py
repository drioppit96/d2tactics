"""What the heroes are doing, written down: for the in-game report (F9) and the test drive
(tools/diagnose_autobattler.py).

A Recorder looks at every hero on a run once a second (where he stands, what he is doing, his
target, its distance and life, whether he has a shot at it) and keeps the last few minutes. A
hero who neither moves nor hurts a monster for 8 seconds while awake monsters are near is noted
as a stall, with the monsters round him. report() puts it all in one text, with the game's own
timing and each run's log; a profile of the last seconds is added when one was taken.
"""
import time

KEEP = 240              # samples kept per hero (4 minutes)


class Recorder:
    def __init__(self):
        self.samples = {}           # hero name -> [row]
        self.stalls = {}            # hero name -> [row]
        self.last_seen = {}
        self.t0 = time.time()

    def sample(self, app):
        """Look at every hero on a run (call about once a second)."""
        from game.grid import chebyshev
        t = time.time() - self.t0
        for run in app.mgr.active():
            for h in run.heroes:
                rows = self.samples.setdefault(h.name, [])
                sim = run.sim
                if sim is None or run.state != "fight":
                    rows.append("%5.0fs  %s, floor %d" % (t, run.state, run.depth))
                    del rows[:-KEEP]
                    continue
                s = sim._state(h)
                b = sim.brain(h)
                tgt = s.target
                tg = "-"
                if tgt is not None:
                    try:
                        tg = "%s %s, %d cells, %d/%d, shot %s, path %s" % (
                            getattr(tgt, "name", "?"), tgt.pos, chebyshev(h.pos, tgt.pos), tgt.hp, tgt.max_hp,
                            sim._can_shoot(h, tgt.pos), sim._missile_reaches(h, tgt))
                    except Exception:
                        tg = getattr(tgt, "name", "?")
                row = "%5.0fs  floor %d %s | %s | %s | %s | life %d/%d mana %d" % (
                    t, run.depth, h.pos, b.last, tg, s.mode, h.hp, h.max_hp, getattr(h, "mana", 0))
                rows.append(row)
                del rows[:-KEEP]
                near = [m for m in sim.foes() if getattr(m, "aware", False) and chebyshev(m.pos, h.pos) <= 10]
                key = (h.pos, sum(m.hp for m in near), run.depth)
                prev = self.last_seen.get(h.name)
                if prev is not None and prev[0] == key and near:
                    if t - prev[1] >= 8:
                        g = sim.w.grid
                        self.stalls.setdefault(h.name, []).append(row + " | near: " + ", ".join(
                            "%s %s %d/%d r%d walkable %s, shot %s, skipped %s" % (
                                getattr(m, "name", "?"), m.pos, m.hp, m.max_hp, getattr(m, "radius", 0),
                                g.walkable(*m.pos), sim._can_shoot(h, m.pos), s.skip.get(id(m), 0) > sim.frame)
                            for m in sorted(near, key=lambda m: chebyshev(m.pos, h.pos))[:5]))
                        del self.stalls[h.name][:-40]
                        self.last_seen[h.name] = (key, t)
                else:
                    self.last_seen[h.name] = (key, t)

    def report(self, app, title, profile_text=None, extra=()):
        import os
        import platform
        out = [title, "Python %s, %s, %d processor cores" % (platform.python_version(), platform.platform(),
                                                               os.cpu_count() or 0)]
        out += list(extra)
        out.append("")
        out.append("== the game's own timing (F3)")
        for line in app.perf.lines(app.mgr):
            out.append("   " + line)
        out.append("")
        out.append("== runs")
        for r in app.mgr.runs:
            out.append("run %s: %s, state %s, floor %d" % (r.id, ", ".join(h.name for h in r.heroes), r.state, r.depth))
            for line in list(getattr(r, "log", []) or [])[-25:]:
                out.append("     | %s" % (line if isinstance(line, str) else line[0]))
            if r.sim is not None:
                out.append("     casts %s" % dict(r.sim.casts))
        out.append("")
        out.append("== heroes, every second (floor, position | doing | target, distance, its life | mode)")
        for name, rows in self.samples.items():
            out.append("-- %s" % name)
            for row in rows[-120:]:
                out.append("   " + row)
        out.append("")
        out.append("== stalls: heroes who neither moved nor hurt anything for 8 s or more, monsters near")
        if not any(self.stalls.values()):
            out.append("   none")
        for name, rows in self.stalls.items():
            out.append("-- %s: %d" % (name, len(rows)))
            for row in rows[-20:]:
                out.append("   " + row)
        if profile_text:
            out.append("")
            out.append("== where the time went")
            out.append(profile_text)
        return "\n".join(out) + "\n"
