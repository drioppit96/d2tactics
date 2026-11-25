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


RECIPES = [
    Recipe("craft_rare", "Craft Rare",
           ["One white or blue weapon, armor, ring or amulet.",
            "It becomes a new rare item of the same base,",
            "rolled for the hero's level (no sockets)."],
           {"rare_cores": 1}, _rare_check, _rare_make),
]
