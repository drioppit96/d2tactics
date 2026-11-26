"""The Horadric Cube's recipes in the D2 Autobattler (the player's own recipes only).

A recipe looks at what is in the cube, says whether it takes it, and makes what comes out. Its cost
is paid in account-wide currencies (autobattler/account.py) when it is transmuted.
"""
from .account import CURRENCIES

PLAIN = ("normal", "superior", "low")


class Recipe:
    def __init__(self, key, name, lines, cost, check, make):
        self.key, self.name, self.lines, self.cost = key, name, lines, cost
        self.check, self.make = check, make

    def why_not(self, items, hero, content=None):
        """None if the recipe takes what is in the cube, else why not."""
        try:
            return self.check(items, hero, content)
        except TypeError:
            return self.check(items, hero)

    def cost_text(self):
        return ", ".join("%d %s" % (v, CURRENCIES.get(k, k)) for k, v in self.cost.items())


# ------------------------------------------------------------------ Craft Rare
def _rare_check(items, hero):
    if len(items) != 1:
        return "Put one white or blue item in the cube."
    it = items[0]
    if getattr(it, "kind", "") != "equip" or getattr(it, "charm", False):
        return "Only weapons, armor, rings and amulets can be crafted."
    if getattr(it, "rarity", "") not in PLAIN + ("magic",) or getattr(it, "runeword", None):
        return "Only a white or blue item can be crafted."
    if not isinstance(getattr(it, "base", None), dict):
        return "This item has no base to craft from."
    return None


def _rare_make(items, hero, content, rng):
    """A new rare item of the same base, at his level (as if a monster of his level dropped it),
    identified, with no sockets."""
    it = items[0]
    if content is None:
        return None
    new = content.make_item(it.base, max(1, int(getattr(hero, "level", 1))), rng, "rare", sockets=0,
                            identified=True)
    if new is None or getattr(new, "rarity", "") != "rare":
        return None
    try:
        from game import durability
        durability.init(new, it.base, rng)
    except Exception:
        pass
    return [new]


# ------------------------------------------------------------------ Add Socket
def socket_cap(it, content=None):
    """The most sockets this item's base can have at its item level (D2's MaxSock columns)."""
    base = getattr(it, "base", None)
    if not isinstance(base, dict):
        return 0
    if content is not None and hasattr(content, "max_sockets"):
        try:
            return int(content.max_sockets(base, int(getattr(it, "ilvl", 1) or 1)))
        except Exception:
            pass
    return int(base.get("maxsock", 0) or 0)


def _socket_check(items, hero, content=None):
    if len(items) != 1:
        return "Put one weapon or armor in the cube."
    it = items[0]
    if getattr(it, "kind", "") != "equip" or getattr(it, "charm", False):
        return "Only weapons and armor take sockets."
    if getattr(it, "runeword", None):
        return "A runeword's sockets are fixed."
    cap = socket_cap(it, content)
    if cap <= 0:
        return "This item can't have sockets."
    if int(getattr(it, "sockets", 0) or 0) >= cap:
        return "It already has all the sockets it can have (%d)." % cap
    return None


def _socket_make(items, hero, content, rng):
    """One more socket in the same item (its gems, runes and jewels stay in theirs)."""
    it = items[0]
    if _socket_check(items, hero, content):
        return None
    it.sockets = int(getattr(it, "sockets", 0) or 0) + 1
    if getattr(it, "socketed", None) is None:
        it.socketed = []
    return [it]


RECIPES = [
    Recipe("craft_rare", "Craft Rare",
           ["One white or blue weapon, armor, ring or amulet.",
            "It becomes a new rare item of the same base,",
            "rolled for the hero's level (no sockets)."],
           {"rare_cores": 50}, _rare_check, _rare_make),
    Recipe("add_socket", "Add Socket",
           ["One weapon or armor (any quality but a runeword).",
            "It gets one more socket, up to the most its",
            "base can have at its item level."],
           {"platinum": 30}, _socket_check, _socket_make),
]
