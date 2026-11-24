"""autobattler.ini: the autobattler's own settings (the D2 install path stays in settings.ini).

The file is written with its defaults the first time the autobattler starts. It is not part of
the repository, so updates never overwrite it.
"""
import configparser
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "autobattler.ini")

DEFAULT_TEXT = """[autobattler]
# how many heroes one account can have
max_heroes = 30
# how many heroes can be on a run at the same time (alone or in groups)
max_active = 8
# how many heroes can go on one run together
max_group = 4
# rift floors are about twice the area of the D2 Tactics ones (yes / no)
big_maps = yes
# game speed: 1 = D2's own 25 frames a second, 2 = twice as fast ...
speed = 1.0
# walking speed in cells per second for each point of D2's velocity (CharStats / MonStats)
move_scale = 1.0
# seconds between stepping through the portal and the next floor starting (the next floor is
# built during it, so it only adds time when the floor is built faster than this)
floor_pause = 1
"""

DEFAULTS = {"max_heroes": 30, "max_active": 8, "max_group": 4, "big_maps": True, "speed": 1.0,
            "move_scale": 1.0, "floor_pause": 1.0}


def load():
    if not os.path.exists(PATH):
        try:
            with open(PATH, "w") as f:
                f.write(DEFAULT_TEXT)
        except OSError:
            pass
    _update_old_file()
    cfg = configparser.ConfigParser()
    cfg.read_string(DEFAULT_TEXT)
    cfg.read(PATH)
    s = cfg["autobattler"]
    out = dict(DEFAULTS)
    try:
        out["max_heroes"] = max(1, min(30, s.getint("max_heroes")))
        out["max_active"] = max(1, min(8, s.getint("max_active")))
        out["max_group"] = max(1, min(out["max_active"], s.getint("max_group")))
        out["big_maps"] = s.getboolean("big_maps")
        out["speed"] = max(0.25, min(8.0, s.getfloat("speed")))
        out["move_scale"] = max(0.2, min(4.0, s.getfloat("move_scale")))
        out["floor_pause"] = max(0.0, min(30.0, s.getfloat("floor_pause")))
    except (ValueError, KeyError):
        pass
    return out


OLD_PAUSE = "# seconds between the boss dying and the next floor starting\nfloor_pause = 3\n"
NEW_PAUSE = DEFAULT_TEXT[DEFAULT_TEXT.index("# seconds between stepping"):]


def _update_old_file():
    """A file still holding the first version's untouched floor pause (3 seconds, added on top of
    the floor's build time) gets the new default."""
    try:
        with open(PATH) as f:
            text = f.read()
        if OLD_PAUSE in text:
            with open(PATH, "w") as f:
                f.write(text.replace(OLD_PAUSE, NEW_PAUSE))
    except OSError:
        pass


def apply_d2_rules():
    """Diablo II's own odds and damage, not the D2 Tactics adjustments in settings.ini
    (min_hit_chance, monster_hit_chance, normal_monster_damage, normal_monster_hit_bonus)."""
    import game.world as gw
    gw.PLAYER_HIT_FLOOR = 0.05
    gw.MONSTER_HIT_FLOOR = 0.05
    gw.NORMAL_MON_DAMAGE = 1.0
    gw.NORMAL_MON_HIT = 0.0
    from game import tactics
    tactics.ACTIVE = False
