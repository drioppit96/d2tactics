"""Body parts: what a creature leaves behind, and what the Tree of Inifuss buys.

There are six of them and no more. A demon leaves Demonic Blood, a Demonic Heart or a Burning
Essence; the walking dead leave Bone Marrow, an Essence of the Damned or Bones. Which of its
kind's three a creature leaves is fixed per family, so the same monster always gives the same
token and you can go looking for the one you need. Beasts leave nothing.

They are worth nothing to a vendor and do nothing in a fight: they are there to be handed in at
the Tree. They stack to 99 in one inventory square, the way the stash banks gems, so collecting
them does not eat the bag.

    organ_of(world, unit)   the (token, name) a monster leaves, or None
    roll_drop(world, unit)  called when something dies: the token, or None
    make(world, token)      one of them, as an item
    count(player, code)     how many the hero is carrying
    take(player, code, n)   spend that many (the Tree, on hand-in)
"""
import random

#: the six, by their token id
DEMON_BLOOD = "demon_blood"
DEMON_HEART = "demon_heart"
BURNING_ESSENCE = "burning_essence"
BONE_MARROW = "bone_marrow"
DAMNED_ESSENCE = "damned_essence"
BONES = "bones"

#: token -> (what it is called, which kind of creature leaves it, D2 art: code, inv, flippy)
ORGANS = {
    DEMON_BLOOD:     ("Demonic Blood",         "demon",  ("hp5", "invhp5", "flprpl")),
    DEMON_HEART:     ("Demonic Heart",         "demon",  ("qhr", "invhrt", "flphrt")),
    BURNING_ESSENCE: ("Burning Essence",       "demon",  ("rvs", "invvps", "flpvps")),
    BONE_MARROW:     ("Bone Marrow",           "undead", ("mp5", "invmp5", "flpbpl")),
    DAMNED_ESSENCE:  ("Essence of the Damned", "undead", ("rvl", "invvpl", "flpvpl")),
    BONES:           ("Bones",                 "undead", ("qbr", "invbrnz", "flpbrnz")),
}

#: the three each kind of creature can leave, in a fixed order
BY_CLASS = {"demon": (DEMON_BLOOD, DEMON_HEART, BURNING_ESSENCE),
            "undead": (BONE_MARROW, DAMNED_ESSENCE, BONES)}

STACK = 99

#: how often a kill leaves its token
CHANCE = 0.14


def label(token):
    return ORGANS[token][0] if token in ORGANS else token


def code_for(token):
    return "og_" + token


def family(mid):
    """D2 numbers a monster's variants (fallen1..fallen5): one token covers the family."""
    s = str(mid or "")
    return s.rstrip("0123456789") or s


def token_for(world, unit_or_id):
    """Which of the six this creature leaves, or None if its kind leaves nothing.

    A family always leaves the same one, so Fallen are always worth the same token and you can
    hunt the thing you actually need.
    """
    from . import bounties
    mid = unit_or_id if isinstance(unit_or_id, str) else str(getattr(unit_or_id, "d2id", "") or "")
    if not mid:
        return None
    cls = bounties.mon_class(world, mid)
    three = BY_CLASS.get(cls)
    if not three:
        return None
    fam = family(mid)
    return three[sum(ord(ch) for ch in fam) % len(three)]


def organ_of(world, unit):
    """(token, its name) for what this monster leaves, or None if it leaves nothing."""
    if unit is None or getattr(unit, "is_player", False) or getattr(unit, "npc", None):
        return None
    if getattr(unit, "ally", False) or getattr(unit, "summoned", False):
        return None
    token = token_for(world, unit)
    if token is None:
        return None
    return token, label(token)


def make(world, token, n=1):
    """One stack of a body part, as an item."""
    from .items import Item
    name, _cls, (code, inv, flippy) = ORGANS[token]
    it = Item(name, code_for(token), None, kind="organ")
    it.invfile, it.flippy = inv, flippy
    it.invw = it.invh = 1
    it.quantity = max(1, int(n))
    it.organ = token
    it.identified = True
    return it


def roll_drop(world, unit, rng=None):
    """Called when something dies. The token it leaves, or None."""
    o = organ_of(world, unit)
    if o is None:
        return None
    rng = rng or getattr(world, "rng", random)
    if rng.random() >= CHANCE:
        return None
    return make(world, o[0])


# ---------------------------------------------------------------- the hero's holdings
def is_organ(it):
    return getattr(it, "kind", "") == "organ"


def count(player, code):
    return sum(max(1, getattr(it, "quantity", 1) or 1)
               for it in (player.inventory or []) if is_organ(it) and it.code == code)


def holdings(player):
    """{code: (name, how many)} for everything the hero is carrying."""
    out = {}
    for it in (player.inventory or []):
        if is_organ(it):
            n = out.get(it.code, (it.name, 0))[1]
            out[it.code] = (it.name, n + max(1, getattr(it, "quantity", 1) or 1))
    return out


def add(player, it):
    """Put a body part away, merging into a stack that has room. False: the bag is full."""
    if not is_organ(it):
        return player.inv_add(it)
    left = max(1, getattr(it, "quantity", 1) or 1)
    for cur in (player.inventory or []):
        if is_organ(cur) and cur.code == it.code and cur.quantity < STACK:
            room = STACK - cur.quantity
            take_now = min(room, left)
            cur.quantity += take_now
            left -= take_now
            if left <= 0:
                return True
    while left > 0:
        part = make_like(it, min(STACK, left))
        if not player.inv_add(part):
            it.quantity = left
            return False
        left -= part.quantity
    return True


def make_like(it, n):
    from .items import Item
    part = Item(it.name, it.code, None, kind="organ")
    part.invfile, part.flippy = it.invfile, it.flippy
    part.invw = part.invh = 1
    part.quantity = n
    part.organ = getattr(it, "organ", None)
    part.identified = True
    return part


def take(player, code, n):
    """Spend n of them. False (and nothing spent) if the hero has not got that many."""
    if count(player, code) < n:
        return False
    left = n
    for it in list(player.inventory or []):
        if left <= 0:
            break
        if not (is_organ(it) and it.code == code):
            continue
        have = max(1, getattr(it, "quantity", 1) or 1)
        if have <= left:
            left -= have
            player.inventory.remove(it)
        else:
            it.quantity = have - left
            left = 0
    return True
