"""Body parts: what a creature leaves behind, and what the Tree of Inifuss buys.

Every kind of monster drops one token of itself - a demon its heart, the walking dead its brain,
anything that still has warm blood a vial of it. They are worth nothing to a vendor and do
nothing in a fight: they are there to be handed in at the Tree, which writes contracts asking
for twenty Fallen Hearts or a dozen Skeleton Brains.

They stack to 99 in one inventory square, the way the stash banks gems, so collecting them does
not eat the bag.

    organ_of(unit)          the (kind, family, name) a monster drops, or None
    roll_drop(world, unit)  called when something dies: the token, or None
    make(world, family, k)  one of them, as an item
    count(player, code)     how many the hero is carrying
    take(player, code, n)   spend that many (the Tree, on hand-in)
"""
import random

HEART, BRAIN, BLOOD = "heart", "brain", "blood"

#: D2's own quest-item art, which is exactly these three things
ART = {HEART: ("qhr", "invhrt", "flpmhrt"),
       BRAIN: ("qbr", "invbrnz", "flpmbrn"),
       BLOOD: ("hp5", "invhp5", "flphp5")}
LABEL = {HEART: "Heart", BRAIN: "Brain", BLOOD: "Blood Vial"}

STACK = 99

#: how often a kill leaves its token
CHANCE = 0.14

#: the walking dead leave a brain, demons a heart; anything else still bleeds
UNDEAD = ("skeleton", "sk_archer", "skmage", "zombie", "returned", "burningdead", "horror",
          "bonewarrior", "mummy", "unraveler", "baalhighpriest", "wraith", "ghost", "specter",
          "apparition", "corpsefire", "bloodraven", "sarcophagus", "guard", "undead", "bighead",
          "skelmage", "boneash", "blunderbore", "greifer")
DEMON = ("fallen", "fallenshaman", "imp", "goatman", "demon", "megademon", "bloodlord",
         "corruptrogue", "cr_archer", "cr_lancer", "doomknight", "oblivionknight", "overseer",
         "minion", "gargoyle", "willowisp", "venomlord", "balrog", "pitlord", "diablo", "baal",
         "mephisto", "andariel", "duriel", "succubus", "bloodwitch", "regurgitator",
         "deathmauler", "diabloclone", "putriddefiler", "painworm")


def family(mid):
    """D2 numbers a monster's variants (fallen1..fallen5): one token covers the family."""
    s = str(mid or "")
    return s.rstrip("0123456789") or s


def kind_for(fam):
    f = (fam or "").lower()
    if any(f.startswith(u) or u in f for u in UNDEAD):
        return BRAIN
    if any(f.startswith(d) or d in f for d in DEMON):
        return HEART
    return BLOOD


def code_for(fam, k):
    return "og_%s_%s" % (fam, k)


def organ_of(world, unit):
    """(kind, family, display name) for what this monster leaves, or None if it leaves nothing."""
    if unit is None or getattr(unit, "is_player", False) or getattr(unit, "npc", None):
        return None
    if getattr(unit, "ally", False) or getattr(unit, "summoned", False):
        return None
    fam = family(getattr(unit, "d2id", ""))
    if not fam:
        return None
    k = kind_for(fam)
    return k, fam, "%s %s" % (_pretty(world, fam, unit), LABEL[k])


def _pretty(world, fam, unit):
    """The monster's own name, without the unique's title: 'Fallen', not 'Rakanishu'."""
    c = getattr(world, "content", None)
    try:
        row = c.monstats.get(getattr(unit, "d2id", "")) or {}
        key = row.get("namestr") or fam
        return c.strings.get(key, key)
    except Exception:
        return fam.title()


def make(world, fam, k, n=1):
    """One stack of a body part, as an item."""
    from .items import Item
    code, inv, flippy = ART[k]
    name = "%s %s" % (fam.title(), LABEL[k])
    c = getattr(world, "content", None)
    try:
        row = c.monstats.get(fam + "1") or c.monstats.get(fam) or {}
        key = row.get("namestr")
        if key:
            name = "%s %s" % (c.strings.get(key, key), LABEL[k])
    except Exception:
        pass
    it = Item(name, code_for(fam, k), None, kind="organ")
    it.invfile, it.flippy = inv, flippy
    it.invw = it.invh = 1
    it.quantity = max(1, int(n))
    it.organ = (k, fam)
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
    k, fam, _ = o
    return make(world, fam, k)


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
            n, name = out.get(it.code, (0, it.name))[0], it.name
            out[it.code] = (name, n + max(1, getattr(it, "quantity", 1) or 1))
    return {k: (v[0], v[1]) for k, v in out.items()}


def add(player, it):
    """Put a body part away, merging into a stack that has room. False: the bag is full."""
    if not is_organ(it):
        return player.inv_add(it)
    left = max(1, getattr(it, "quantity", 1) or 1)
    for cur in (player.inventory or []):
        if is_organ(cur) and cur.code == it.code and cur.quantity < STACK:
            room = STACK - cur.quantity
            take = min(room, left)
            cur.quantity += take
            left -= take
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
