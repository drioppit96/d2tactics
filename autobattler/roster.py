"""The account's heroes: up to max_heroes of them, saved in the saves_auto folder.

The save format is the game's own (game/save.py), so an autobattler hero is a normal D2 Tactics
hero file. They are kept in a separate folder so the two games never share characters.
"""
import os
import random

from game import save as gsave

from . import gear

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR = os.path.join(ROOT, "saves_auto")
CLASSES = ["ama", "sor", "nec", "pal", "bar", "dru", "ass"]


def use_folder():
    """Point the game's save code at saves_auto (call once at start)."""
    os.makedirs(SAVE_DIR, exist_ok=True)
    gsave.NORMAL_DIR = SAVE_DIR
    gsave.SAVE_DIR = SAVE_DIR


def list_heroes():
    return gsave.list_saves()


def count():
    return len(list_heroes())


def create(cls, name, content, max_heroes=30):
    """A new hero with D2's starting kit. Returns the Player, or None when the roster is full."""
    import types
    from game.units import Player
    from game.world import World
    from game.skills import load_tree
    if count() >= max_heroes:
        return None
    name = (name or "").strip()[:15] or "Hero"
    taken = {(d.get("name") or "").lower() for d in list_heroes()}
    base, n = name, 2
    while name.lower() in taken:
        name = "%s%d" % (base[:13], n)
        n += 1
    tree = load_tree(content.src, cls, getattr(content, "strings", None)) if content else None
    p = Player(0, 0, cls=cls if content else "bar", name=name, tree=tree)
    if content:
        try:
            World._d2_starting_gear(types.SimpleNamespace(content=content, player=p, rng=random.Random()))
        except Exception:
            import traceback
            traceback.print_exc()
    p.map_seed = random.randrange(1 << 30)
    p.rift_depth = 0
    gear.prepare(p)
    gsave.save_character(p)
    return p


def load(data, content):
    p = gsave.build_player(data, content)
    gear.prepare(p)
    try:
        from . import extratree
        extratree.attach(p, content, data.get("skills") or {})   # (the fourth tree, with its levels)
    except Exception:
        import traceback
        traceback.print_exc()
    return p


def save(p):
    try:
        return gsave.save_character(p)
    except Exception:
        import traceback
        traceback.print_exc()
        return None


def delete(name):
    return gsave.delete_character(name)
