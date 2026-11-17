"""Essences: the three currencies every character on the account shares.

What a creature leaves behind when it dies, kept as a number rather than as something in the bag.
There are three, one for each kind of thing that can die:

    Essence of the Damned      demons
    Essence of the Dead        the walking dead
    Essence of the Beasts      beasts

They are account wide. They sit on the one chest every character shares, so it makes no odds
which hero in the party walks over the drop - it counts for all of them, and for every other
character on the account, and it is still there in the next session.

    kind_for(world, unit)    which essence this creature leaves, or None
    roll_drop(world, unit)   what it leaves this time, as something to walk over, or None
    count(player, kind)      how many the account holds
    add / take               put some in, spend some (the Tree, on hand-in)
"""
import random

DAMNED = "damned"          # demons
DEAD = "dead"              # the walking dead
BEAST = "beast"            # beasts

#: kind -> (what it is called, the colour it is drawn in, D2 art: inventory, on the ground)
ESSENCES = {
    DAMNED: ("Essence of the Damned",   (214,  92,  78), ("invbet", "flpgsr")),
    DEAD:   ("Essence of the Dead",     (124, 178, 226), ("invtes", "flpgsb")),
    BEAST:  ("Essence of the Beasts",   (142, 196, 104), ("invfed", "flpgsg")),
}

#: the order they are shown in, everywhere
ORDER = (DAMNED, DEAD, BEAST)

#: which kind of creature leaves which. An act boss leaves its own kind's essence like anything
#: else, only a great deal more of it.
BY_CLASS = {"demon": DAMNED, "undead": DEAD, "beast": BEAST}

#: how often a kill leaves one, by what the thing was. Scarce enough to be worth seeing on the
#: floor: about one ordinary monster in fourteen, and a unique almost always.
CHANCE = {"normal": 0.07, "champion": 0.30, "unique": 0.70, "boss": 1.0}

#: how many it leaves, by what the thing was
AMOUNT = {"normal": (1, 5), "champion": (1, 7), "unique": (3, 10), "boss": (8, 16)}

COLOR = (199, 179, 119)


def label(kind):
    return ESSENCES[kind][0] if kind in ESSENCES else kind


def color(kind):
    return ESSENCES[kind][1] if kind in ESSENCES else (200, 200, 200)


def art(kind):
    return ESSENCES[kind][2] if kind in ESSENCES else ("invbet", "flpgsr")


# ---------------------------------------------------------------- the account's holdings
def purse(player):
    """The account's essences: a dict on the shared chest, so every hero reads the same one."""
    # there used to be a fourth, the Old Ones', for act bosses. Anything still held of it counts
    # as the Damned's, which is what an act boss leaves now.
    st = getattr(player, "stash", None)
    holder = st if st is not None else player
    got = getattr(holder, "essences", None)
    if not isinstance(got, dict):
        got = {}
        try:
            holder.essences = got
        except Exception:
            return {}
    gone = got.pop("old", 0)
    if gone:
        got[DAMNED] = int(got.get(DAMNED, 0) or 0) + int(gone)
    return got


def count(player, kind):
    return int(purse(player).get(kind, 0) or 0)


def holdings(player):
    """[(kind, name, how many)] in the order they are shown."""
    bag = purse(player)
    return [(k, label(k), int(bag.get(k, 0) or 0)) for k in ORDER]


def add(player, kind, n):
    if kind not in ESSENCES or n <= 0:
        return 0
    bag = purse(player)
    bag[kind] = int(bag.get(kind, 0) or 0) + int(n)
    return bag[kind]


def take(player, kind, n):
    """Spend that many. False (and nothing spent) if the account has not got them."""
    bag = purse(player)
    have = int(bag.get(kind, 0) or 0)
    if have < n:
        return False
    bag[kind] = have - int(n)
    return True


# ---------------------------------------------------------------- what leaves what
def _grade(unit):
    if getattr(unit, "boss", None):
        return "boss"
    if getattr(unit, "unique", False):
        return "unique"
    if getattr(unit, "champion", False):
        return "champion"
    return "normal"


def kind_for(world, unit):
    """Which essence this creature leaves, or None if it leaves nothing."""
    if unit is None or getattr(unit, "is_player", False) or getattr(unit, "ai", "") == "npc":
        return None
    if getattr(unit, "ally", False) or getattr(unit, "summoned", False):
        return None
    from . import bounties
    mid = str(getattr(unit, "d2id", "") or "")
    if not mid:
        return None
    return BY_CLASS.get(bounties.mon_class(world, mid))


def roll_drop(world, unit, rng=None):
    """Called when something dies. What it leaves lying there, or None."""
    kind = kind_for(world, unit)
    if kind is None:
        return None
    rng = rng or getattr(world, "rng", random)
    grade = _grade(unit)
    if rng.random() >= CHANCE.get(grade, 0.0):
        return None
    lo, hi = AMOUNT.get(grade, (1, 1))
    return make(kind, rng.randint(lo, hi))


def make(kind, n=1):
    """A pile of essence, as something lying on the floor to be walked over."""
    from .items import Item
    name, _col, (inv, flippy) = ESSENCES[kind]
    it = Item(name, "es_" + kind, None, kind="essence")
    it.invfile, it.flippy = inv, flippy
    it.invw = it.invh = 1
    it.amount = max(1, int(n))
    it.quantity = it.amount
    it.essence = kind
    it.identified = True
    return it


def is_essence(it):
    return getattr(it, "kind", "") == "essence"


def collect(player, it):
    """Walking over one: it goes to the account's purse, never into the bag."""
    if not is_essence(it):
        return False
    add(player, getattr(it, "essence", None), int(getattr(it, "amount", 1) or 1))
    return True
