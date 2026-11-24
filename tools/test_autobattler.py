"""Checks for the autobattler that need no Diablo II files (placeholder art, generated cave).

    python tools/test_autobattler.py
"""
import os
import random
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from autobattler import config, roster, timing  # noqa: E402
from autobattler.runs import RunManager         # noqa: E402

FAILS = []


def check(cond, what):
    print(("ok    " if cond else "FAIL  ") + what)
    if not cond:
        FAILS.append(what)


def test_timing():
    # Barbarian hit recovery breakpoints (published table): FHR -> frames
    base = (timing.HERO_GH_FRAMES["bar"] + 1) / 2.0
    table = {0: 9, 6: 9, 7: 8, 14: 8, 15: 7, 27: 6, 48: 5, 86: 4, 200: 3}
    got = {fhr: timing.hit_recovery_frames(base, fhr) for fhr in table}
    check(got == table, "Barbarian FHR breakpoints %s" % got)
    sor = (timing.HERO_GH_FRAMES["sor"] + 1) / 2.0
    check(timing.hit_recovery_frames(sor, 0) == 15, "Sorceress 0% FHR = 15 frames")
    check(timing.attack_frames(15, 0) == 14, "15-frame attack at 0 IAS = 14 frames")
    fast = [timing.attack_frames(15, ias) for ias in (0, 20, 40, 80, 200)]
    check(fast == sorted(fast, reverse=True) and fast[-1] < fast[0], "IAS only ever speeds attacks up %s" % fast)
    check(timing.eias(1000) == 75, "EIAS is capped at 75")
    check(timing.effective(20) == 17 and timing.effective(20, 150) == 17, "diminishing returns")
    check(abs(timing.move_speed(9, 0) - 9.0) < 1e-9, "run speed without FRW")


def _hero(name, cls="bar"):
    from game.units import Player
    p = Player(0, 0, cls=cls, name=name)
    p.recalc()
    return p


class _NoAssets:
    act_kit = None
    content = None


def _cfg():
    c = dict(config.DEFAULTS)
    c["floor_pause"] = 0.2
    return c


def test_runs():
    config.apply_d2_rules()
    random.seed(7)
    mgr = RunManager(_NoAssets(), _cfg())
    a, b = _hero("Alpha"), _hero("Bravo", "pal")
    r = mgr.start([a])
    check(not isinstance(r, str), "a run starts")
    g = mgr.start([b, _hero("Charlie", "ama")])
    check(not isinstance(g, str), "a group run starts")
    again = mgr.start([a])
    check(isinstance(again, str), "a hero can't be on two runs: %r" % again)
    many = [_hero("H%d" % i) for i in range(6)]
    full = mgr.start(many[:4])
    check(not isinstance(full, str), "up to 8 heroes on runs")
    eighth = mgr.start(many[4:5])
    check(not isinstance(eighth, str), "the 8th hero still fits")
    over = mgr.start(many[5:6])
    check(isinstance(over, str), "the 9th hero is refused: %r" % over)
    frames = 0
    floors_seen = 0
    while frames < 25 * 60 * 6:              # six minutes of game time
        mgr.tick()
        frames += 1
        floors_seen = max(floors_seen, r.floors)
        if r.state == "over" and g.state == "over" and full.state == "over":
            break
    check(r.kills > 0 or r.floors > 0, "the solo run fights: %d kills, %d floors, %s" % (r.kills, r.floors, r.state))
    check(g.kills > 0 or g.floors > 0, "the group run fights: %d kills, %d floors, %s" % (g.kills, g.floors, g.state))
    check(all(x.state != "over" or x.result in ("died", "stopped") for x in (r, g, full)),
          "runs end only by dying or stopping (no errors): %s" % [x.result for x in (r, g, full)])
    print("      solo: floors %d kills %d level %d state %s" % (r.floors, r.kills, a.level, r.state))
    print("      group: floors %d kills %d levels %s" % (g.floors, g.kills, [h.level for h in g.heroes]))


def test_floor_progress():
    """A strong hero clears the placeholder floor and goes on to the next one."""
    config.apply_d2_rules()
    random.seed(3)
    mgr = RunManager(_NoAssets(), _cfg())
    h = _hero("Strong")
    h.level = 30
    h.base_str, h.base_vit, h.base_dex = 150, 200, 80
    h.recalc()
    h.hp = h.max_hp
    r = mgr.start([h])
    for _ in range(25 * 60 * 8):
        mgr.tick()
        if r.floors >= 2 or r.state == "over":
            break
    check(r.floors >= 2, "floor cleared -> next floor: %d floors, depth %d, %d kills, %s" % (r.floors, r.depth, r.kills, r.state))
    check(int(getattr(h, "rift_depth", 0)) >= 1, "the deepest floor is remembered on the hero")


def test_roster():
    from game import save as gsave
    old = (roster.SAVE_DIR, gsave.SAVE_DIR, gsave.NORMAL_DIR)
    with tempfile.TemporaryDirectory() as tmp:
        roster.SAVE_DIR = os.path.join(tmp, "saves_auto")
        roster.use_folder()
        for i in range(3):
            roster.create("bar", "Tester", None, max_heroes=3)
        check(roster.count() == 3, "three heroes made, names kept apart")
        check(roster.create("bar", "One more", None, max_heroes=3) is None, "the roster cap holds")
        check(os.path.isdir(roster.SAVE_DIR), "heroes go to saves_auto")
    roster.SAVE_DIR, gsave.SAVE_DIR, gsave.NORMAL_DIR = old


def test_big_maps():
    from game import rift

    class _MK:
        rw = rh = 8

    class _Kit:
        mazes = {"cave": _MK()}
    rift.BIG = False
    small = rift._fit(_Kit(), "cave", 6, False)
    rift.BIG = True
    big = rift._fit(_Kit(), "cave", 12, False)
    rift.BIG = False
    check(big["grid"] ** 2 >= 2 * small["grid"] ** 2 and big["rooms"] >= 2 * small["rooms"] - 2,
          "big floors: grid %d -> %d, rooms %d -> %d" % (small["grid"], big["grid"], small["rooms"], big["rooms"]))


if __name__ == "__main__":
    _tmp = tempfile.TemporaryDirectory()        # nothing a test makes lands among your real heroes
    roster.SAVE_DIR = os.path.join(_tmp.name, "saves_auto")
    roster.use_folder()
    test_timing()
    test_big_maps()
    test_roster()
    test_runs()
    test_floor_progress()
    print("\n%s" % ("all passed" if not FAILS else "%d FAILED" % len(FAILS)))
    sys.exit(1 if FAILS else 0)
