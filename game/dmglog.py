"""A record of what each blow was made of.

Every hit is kept as a list of parts, one per kind of damage: how much was rolled against the
target (before the target's resistances, armour and reductions) and how much of it actually
landed. The combat log reads the hits your heroes dealt; the death log keeps the hits a hero
took in the fight that killed him.

Nothing here changes the game. It only writes down what the damage code already worked out.
"""

ELEMENTS = ("phys", "fire", "cold", "ltng", "pois", "mag")

#: what each kind of damage is shown in
COLORS = {"phys": (230, 230, 230), "fire": (255, 140, 50), "cold": (120, 185, 255),
          "ltng": (255, 225, 90), "pois": (120, 215, 110), "mag": (190, 150, 255)}
NAMES = {"phys": "physical", "fire": "fire", "cold": "cold", "ltng": "lightning",
         "pois": "poison", "mag": "magic"}

KEEP = 120          # hits kept in the combat log
KEEP_DEATH = 30     # hits kept for a death


class Hit(object):
    """One blow: who swung, who took it, and what it was made of."""

    __slots__ = ("src", "target", "kind", "round", "parts", "skill", "res", "_tok")

    def __init__(self, src, target, rnd, skill=""):
        self.src = (getattr(src, "name", "") or "?") if src is not None else "something"
        self.target = getattr(target, "name", "") or "?"
        self.kind = _kind_of(target)
        self.round = rnd
        self.skill = skill
        self.parts = []            # [(element, rolled, landed)]
        # what the target was shrugging off at that moment, so the line explains itself later
        r = getattr(target, "res", None) or {}
        self.res = {k: int(r.get(k, 0) or 0) for k in ELEMENTS if r.get(k)}

    def rolled(self):
        return sum(p[1] for p in self.parts)

    def landed(self):
        return sum(p[2] for p in self.parts)


def _kind_of(u):
    for flag, word in (("undead", "undead"), ("demon", "demon")):
        if getattr(u, flag, False):
            return word
    if getattr(u, "is_player", False):
        return "hero"
    return "beast"


def _log(world):
    lg = getattr(world, "dmg_log", None)
    if lg is None:
        lg = world.dmg_log = []
    return lg


def note(world, src, target, element, rolled, landed, skill=""):
    """One part of a blow. Parts that follow each other on the same pair of units are the same
    blow, so a weapon's fire damage sits in the same line as the swing that carried it."""
    if world is None or target is None:
        return
    if rolled <= 0 and landed <= 0:
        return
    lg = _log(world)
    cur = lg[-1] if lg else None
    tok = getattr(world, "_hit_token", 0)
    name = (getattr(src, "name", "") or "?") if src is not None else "something"
    if cur is None or cur.src != name or \
            cur.target != (getattr(target, "name", "") or "?") or getattr(cur, "_tok", None) != tok:
        cur = Hit(src, target, getattr(world, "round", 0), skill)
        cur._tok = tok
        lg.append(cur)
        del lg[:-KEEP]
    elif skill and not cur.skill:
        cur.skill = skill
    cur.parts.append((element, int(rolled), int(landed)))
    world._last_noted = (tok, id(src), id(target))
    if getattr(target, "is_player", False):
        taken = getattr(world, "_taken", None)
        if taken is None:
            taken = world._taken = {}
        hits = taken.setdefault(id(target), [])
        if not hits or hits[-1] is not cur:
            hits.append(cur)
            del hits[:-KEEP_DEATH]


def unaccounted(world, src, target, amount):
    """Damage that reached a unit without going through the damage code that writes parts down
    (a scripted blow, a trap, a boss's own routine). Kept so a death still shows what landed."""
    if world is None or target is None or amount <= 0:
        return
    tok = getattr(world, "_hit_token", 0)
    if getattr(world, "_last_noted", None) == (tok, id(src), id(target)):
        return
    new_blow(world)
    note(world, src, target, "phys", amount, amount)


def new_blow(world):
    """Start a new blow: the next parts noted belong to a line of their own."""
    if world is not None:
        world._hit_token = getattr(world, "_hit_token", 0) + 1


def scale_landed(world, factor):
    """The last blow was cut again after its parts were written down (a hero's Damage Reduced,
    say): spread that cut over the parts so the line still adds up to what was taken."""
    lg = getattr(world, "dmg_log", None)
    if not lg or factor >= 1.0:
        return
    h = lg[-1]
    h.parts = [(e, r, max(0, int(round(l * factor)))) for e, r, l in h.parts]


def died(world, hero):
    """Keep the blows that killed a hero, so the death log can show them afterwards."""
    taken = getattr(world, "_taken", None) or {}
    hits = list(taken.get(id(hero), []))
    if not hits:
        return
    deaths = getattr(world, "death_log", None)
    if deaths is None:
        deaths = world.death_log = []
    deaths.append({"hero": getattr(hero, "name", "?"), "round": getattr(world, "round", 0),
                   "hits": hits})
    del deaths[:-10]
    taken[id(hero)] = []


def hits_by(world, unit):
    """The blows one hero struck, newest last."""
    name = getattr(unit, "name", "")
    return [h for h in _log(world) if h.src == name]
