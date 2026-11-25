"""The premade floors are made in a process of their own.

Python runs one thread at a time in a process: a floor built on a thread next to the game took
time from the screen however it stepped aside. A second process has its own Python and runs on
another processor core, so the game doesn't feel it. It reads the player's D2 files itself, builds
the floors map_cache/ is still missing (mapcache.missing(), act boss arenas first), saves each
one, and stops when the pool is full. The game picks the new files up as they appear.

It runs at below-normal priority, so on a PC with one core the game still goes first.
"""
import os
import sys
import time


def _below_normal():
    if os.name == "nt":
        try:
            import ctypes
            k = ctypes.windll.kernel32
            k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)     # BELOW_NORMAL_PRIORITY_CLASS
        except Exception:
            pass
    else:
        try:
            os.nice(10)
        except Exception:
            pass


def work(d2_path, area, folder, here):
    """The worker process: build missing premade floors until the pool is full."""
    _below_normal()
    if here not in sys.path:
        sys.path.insert(0, here)
    log = os.path.join(here, "errors.log")
    try:
        from d2.source import open_source, read_table
        from game import rift
        from game.act1 import OutdoorKit
        from game.d2content import D2Content
        from autobattler import mapcache
        src = open_source(d2_path, lambda *a: None, os.path.join(here, "cache", "mpq"))
        content = D2Content(src, "normal")
        kit = OutdoorKit(src, read_table(src, "Levels"), read_table(src, "LvlTypes"))
        rift.BIG, rift.CONTENT, rift.ACT_LEVELS, rift.SIXTH = True, content, True, True
        rift.AREA = area
        mapcache.FOLDER = folder
        while True:
            mapcache._INDEX = None           # (the game may have kept floors of its own meanwhile)
            if not mapcache.missing():
                return
            try:
                mapcache.build_missing_one(kit)
            except Exception:
                import traceback
                with open(log, "a") as f:
                    f.write("premade floors (worker): %s\n" % traceback.format_exc())
                time.sleep(1)
    except Exception:
        import traceback
        try:
            with open(log, "a") as f:
                f.write("premade floors (worker) could not start: %s\n" % traceback.format_exc())
        except Exception:
            pass


_PROC = None


def start(assets):
    """Start the worker if floors are missing and it isn't running. Returns True if it runs."""
    global _PROC
    from game import rift
    from . import mapcache
    if _PROC is not None and _PROC.is_alive():
        return True
    if not mapcache.missing():
        return False
    d2_path = getattr(assets, "d2_path", None)
    if not d2_path:
        return False
    import multiprocessing
    ctx = multiprocessing.get_context("spawn")
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _PROC = ctx.Process(target=work, args=(d2_path, rift.AREA, mapcache.FOLDER, here),
                        name="premade-floors", daemon=True)
    _PROC.start()
    return True


def running():
    return _PROC is not None and _PROC.is_alive()
