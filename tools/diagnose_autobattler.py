"""A test drive of the D2 Autobattler that writes everything into one file: diagnose_report.txt.

    "Diagnose D2 Autobattler.bat" (or: python tools/diagnose_autobattler.py [seconds])

It opens the game as usual, on a COPY of the heroes (saves_auto is never touched: the copy is in
a temporary folder and is thrown away), starts a run for up to four heroes (an Amazon first, if
there is one), shows the first of them on screen and lets them play for 3 minutes. Meanwhile it
records:
- every screen frame's time, and where the game's time goes (Python's profiler);
- each run's floors, kills, deaths and its time per game frame;
- each hero every second: where he is, what he is doing, his target, its distance and life;
  a hero who neither moves nor hurts anything for 8 seconds is listed with what he did then;
- what perf.log, stuck.log, build_profile.log and errors.log got during the drive.
Then it closes and says where the report is. Nothing is sent anywhere: the file is for the
player to send on.
"""
import cProfile
import io
import os
import platform
import pstats
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
REPORT = os.path.join(HERE, "diagnose_report.txt")
LOGS = ("perf.log", "stuck.log", "build_profile.log", "errors.log")


def _tail_since(path, size0):
    try:
        with open(path, "rb") as f:
            f.seek(size0)
            return f.read().decode("utf-8", "replace")
    except OSError:
        return ""


def main(seconds=180):
    sizes = {n: (os.path.getsize(os.path.join(HERE, n)) if os.path.exists(os.path.join(HERE, n)) else 0)
             for n in LOGS}
    from autobattler import roster
    real = roster.SAVE_DIR
    tmp = tempfile.mkdtemp(prefix="d2ab_diag_")
    copy = os.path.join(tmp, "saves_auto")
    if os.path.isdir(real):
        shutil.copytree(real, copy)
    else:
        os.makedirs(copy)
    roster.SAVE_DIR = copy                       # (the heroes' copy: the real saves stay as they are)
    out = []
    say = out.append
    say("D2 Autobattler diagnosis, %s" % time.strftime("%Y-%m-%d %H:%M:%S"))
    say("Python %s, %s, %s, %d processor cores" % (platform.python_version(), platform.platform(),
                                                   platform.machine(), os.cpu_count() or 0))
    try:
        import autobattler_main as am
        import pygame
        say("pygame %s" % pygame.version.ver)
        app = am.App()
        mgr = app.mgr
        say("D2 files: %s; settings: %s" % ("read" if getattr(app.assets, "act_kit", None) else "NOT read",
                                            {k: app.cfg[k] for k in sorted(app.cfg)}))
        heroes = [h for h in app.heroes.values()]
        heroes.sort(key=lambda h: (getattr(h, "cls", "") != "ama", -getattr(h, "level", 1)))
        heroes = heroes[:4]
        if not heroes:
            say("No heroes to test with: make one in the game first.")
            return out, tmp
        for h in heroes:
            r = mgr.start([h])
            say("run %s: %s, level %d %s, from floor %d" % (getattr(r, "id", "?"), h.name, h.level,
                                                          am.CLASS_NAMES.get(h.cls, h.cls), getattr(r, "depth", 0)))
        app.selected = [heroes[0].name]
        app.screen_name = "roster"
        frames, samples, stalls = [], {h.name: [] for h in heroes}, {}
        last_seen = {}
        prof = cProfile.Profile()
        clock = pygame.time.Clock()
        start = last = time.perf_counter()
        n = 0
        prof.enable()
        while time.perf_counter() - start < seconds and app.running:
            now = time.perf_counter()
            app._dt = min(0.25, now - last)
            last = now
            from autobattler import runs as abruns
            abruns.MAIN_BUSY[0] = True
            try:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        app.running = False
                app.step(app._dt)
                app.draw()
            finally:
                abruns.MAIN_BUSY[0] = False
            frames.append((time.perf_counter() - now) * 1000)
            clock.tick(60)
            n += 1
            if n % 60 == 0:
                _sample(app, heroes, samples, stalls, last_seen, now - start)
        prof.disable()
        el = time.perf_counter() - start
        frames.sort()
        say("")
        say("== screen: %d frames in %.0f s = %.1f frames/s" % (len(frames), el, len(frames) / max(1e-6, el)))
        if frames:
            say("   frame time ms: median %.1f, 90%% %.1f, 99%% %.1f, worst %.0f; over 50 ms: %d, over 100 ms: %d, over 500 ms: %d" % (
                frames[len(frames) // 2], frames[int(len(frames) * .9)], frames[int(len(frames) * .99)], frames[-1],
                sum(1 for f in frames if f > 50), sum(1 for f in frames if f > 100), sum(1 for f in frames if f > 500)))
        say("")
        say("== the game's own timing (F3)")
        for line in app.perf.lines(mgr):
            say("   " + line)
        say("")
        say("== runs")
        for r in mgr.runs:
            sim = r.sim
            say("run %s: %s, state %s, floor %d, game frames %d, %.1f ms each, floors built %d in %.1f s" % (
                r.id, ", ".join(h.name for h in r.heroes), r.state, r.depth, getattr(r, "game_frames", 0),
                1000 * getattr(r, "game_secs", 0) / max(1, getattr(r, "game_frames", 0)),
                getattr(r, "builds", 0), getattr(r, "build_secs", 0)))
            for line in list(getattr(r, "log", []) or [])[-25:]:
                say("     | %s" % (line if isinstance(line, str) else line[0]))
            if sim is not None:
                say("     casts %s" % dict(sim.casts))
        say("")
        say("== heroes, every second (pos | doing | target, distance, its life | mode)")
        for name, rows in samples.items():
            say("-- %s" % name)
            for row in rows[-60:]:
                say("   " + row)
        say("")
        say("== stalls: heroes who neither moved nor hurt anything for 8 s or more, monsters near")
        if not stalls:
            say("   none")
        for name, rows in stalls.items():
            say("-- %s: %d" % (name, len(rows)))
            for row in rows[:20]:
                say("   " + row)
        say("")
        say("== where the time went (main thread, cumulative)")
        s = io.StringIO()
        st = pstats.Stats(prof, stream=s)
        st.sort_stats("cumulative").print_stats(45)
        st.sort_stats("tottime").print_stats(35)
        say(s.getvalue())
        for r in mgr.active():
            r.finish("stopped")
        pygame.quit()
    except Exception:
        import traceback
        say("THE DIAGNOSIS STOPPED WITH AN ERROR:\n" + traceback.format_exc())
    for name in LOGS:
        text = _tail_since(os.path.join(HERE, name), sizes[name])
        say("")
        say("== %s during the drive" % name)
        say(text[-20000:] if text else "   (nothing)")
    return out, tmp


def _sample(app, heroes, samples, stalls, last_seen, t):
    from game.grid import chebyshev
    for h in heroes:
        run = app.run_of(h.name)
        sim = getattr(run, "sim", None) if run else None
        if sim is None or run.state != "fight":
            samples[h.name].append("%5.0fs  %s" % (t, run.state if run else "no run"))
            continue
        s = sim._state(h)
        b = sim.brain(h)
        tgt = s.target
        tg = "-"
        if tgt is not None:
            tg = "%s %s, %d cells, %d/%d, shot %s, path %s" % (
                getattr(tgt, "name", "?"), tgt.pos, chebyshev(h.pos, tgt.pos), tgt.hp, tgt.max_hp,
                sim._can_shoot(h, tgt.pos), sim._missile_reaches(h, tgt))
        row = "%5.0fs  %s | %s | %s | %s | life %d/%d mana %d" % (
            t, h.pos, b.last, tg, s.mode, h.hp, h.max_hp, getattr(h, "mana", 0))
        samples[h.name].append(row)
        near = [m for m in sim.foes() if getattr(m, "aware", False) and chebyshev(m.pos, h.pos) <= 10]
        hp_near = sum(m.hp for m in near)
        key = (h.pos, hp_near)
        prev = last_seen.get(h.name)
        if prev is not None and prev[0] == key and near:
            if t - prev[1] >= 8:
                stalls.setdefault(h.name, []).append(row + " | near: " + ", ".join(
                    "%s %s %d/%d walkable %s" % (getattr(m, "name", "?"), m.pos, m.hp, m.max_hp,
                                                 sim.w.grid.walkable(*m.pos)) for m in near[:5]))
                last_seen[h.name] = (key, t)
        else:
            last_seen[h.name] = (key, t)


if __name__ == "__main__":
    secs = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    print("Test drive of the D2 Autobattler: %d seconds, on a copy of your heroes." % secs)
    out, tmp = main(secs)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    shutil.rmtree(tmp, ignore_errors=True)
    print("\nDone. The report is:\n  %s\nSend that file." % REPORT)
