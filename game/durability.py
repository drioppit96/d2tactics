"""Durability, broken items, ethereal items and repairs (like D2).

    max_dur / dur      on weapons and armor whose base has durability (Weapons/Armor.txt)
    ethereal           +50% damage / defense, -10 str/dex requirements, half durability, no repairs
    broken (dur 0)     the item does nothing until it is repaired
Weapons wear when they hit, armor when you are hit. Smiths repair everything you carry.
"""

WEAR_WEAPON = 8          # 1 in N hits costs the weapon a point of durability
WEAR_ARMOR = 6           # 1 in N hits you take costs a random armor piece a point
ETHEREAL_CHANCE = 0.03


def has_dur(it):
    return getattr(it, "max_dur", 0) > 0


def broken(it):
    return has_dur(it) and getattr(it, "dur", 1) <= 0


def indestructible(it):
    return any(e[0] == "indestruct" for e in (getattr(it, "mod_list", None) or []))


def init(it, base, rng, ethereal_ok=True):
    if getattr(it, "max_dur", None) is not None and it.max_dur:
        return
    d = base.get("dur", 0)
    if not d:
        it.max_dur = 0
        return
    d += it.mods.get("dur", 0) if isinstance(it.mods.get("dur", 0), int) else 0
    d = d * (100 + getattr(it, "dur_pct", 0)) // 100
    if getattr(it, "grade", "") == "low":
        d = max(1, d * 2 // 3)
    if ethereal_ok and not getattr(it, "ethereal", False) and rng.random() < ETHEREAL_CHANCE \
            and it.rarity not in ("set",) and not getattr(it, "sockets", 0):
        make_ethereal(it)
    if getattr(it, "ethereal", False):
        d = d // 2 + 1
    it.max_dur = d
    it.dur = d


def make_ethereal(it):
    it.ethereal = True
    if it.dmg:
        it.dmg = (it.dmg[0] * 3 // 2, it.dmg[1] * 3 // 2)
    if getattr(it, "base_defense", None):
        it.base_defense = it.base_defense * 3 // 2
        it.defense = it.base_defense * (100 + it.mods.get("edef", 0)) // 100 + it.mods.get("def", 0)
    it.reqstr = max(0, it.reqstr - 10)
    it.reqdex = max(0, it.reqdex - 10)


def wear(world, unit, kind):
    """A hit wore down the weapon (kind "weapon") or a piece of armor ("armor")."""
    if not getattr(unit, "is_player", False):
        return
    rng = world.rng
    eq = unit.equipment
    if kind == "weapon":
        it = eq.get("weapon")
        if it is None or not has_dur(it) or indestructible(it) or rng.randrange(WEAR_WEAPON):
            return
    else:
        if rng.randrange(WEAR_ARMOR):
            return
        pieces = [eq.get(k) for k in ("helm", "armor", "shield", "gloves", "boots", "belt")]
        pieces = [x for x in pieces if x is not None and has_dur(x) and not indestructible(x)]
        if not pieces:
            return
        it = rng.choice(pieces)
    if it.dur <= 0:
        return
    it.dur -= 1
    if it.dur == 0:
        world.log("Your %s is broken!" % it.shown_name, (255, 80, 80))
        unit.recalc()
    elif it.dur * 10 <= it.max_dur and (it.dur + 1) * 10 > it.max_dur:
        world.log("Your %s is about to break." % it.shown_name, (255, 200, 80))


def tick_self_repair(unit):
    """Items with "Repairs 1 Durability in N Seconds": a point every N/2 turns (a turn is ~2 s)."""
    for it in unit.equipment.values():
        if it is None or not has_dur(it) or it.dur >= it.max_dur:
            continue
        rate = 0
        for e in getattr(it, "mod_list", None) or []:
            if e[0] == "rep-dur":
                v = e[1][1] if isinstance(e[1], tuple) else e[1]
                rate = max(rate, int(v or 0))
        if not rate:
            continue
        it._rep_acc = getattr(it, "_rep_acc", 0) + 2 * rate
        if it._rep_acc >= 100:
            it._rep_acc -= 100
            was = it.dur
            it.dur = min(it.max_dur, it.dur + 1)
            if was == 0:
                unit.recalc()


def recharge_cost(it):
    n = sum(max(0, c[1] - c[0]) * (c[2] + 2) for c in (getattr(it, "charges", None) or {}).values())
    return n * 2


def repair_cost(it):
    if not has_dur(it) or getattr(it, "ethereal", False) or it.dur >= it.max_dur:
        return recharge_cost(it)
    base = it.base if isinstance(getattr(it, "base", None), dict) else {}
    value = max(10, base.get("cost", 100))
    mult = {"magic": 2, "rare": 3, "crafted": 3, "set": 4, "unique": 5}.get(it.rarity, 1)
    missing = it.max_dur - it.dur
    cost = value * mult * missing // max(1, it.max_dur * 4) + missing
    if it.dur == 0:
        cost += value * mult // 10
    return max(1, cost) + recharge_cost(it)


def carried(p):
    out = [x for x in p.equipment.values() if x is not None]
    out += list(p.inventory)
    return out


def repair_all(world):
    """A smith repairs what you carry (not ethereal items). Returns (cost, items repaired)."""
    p = world.player
    todo = [it for it in carried(p) if repair_cost(it)]
    if not todo:
        world.log("Nothing needs repairing.", (160, 160, 160))
        return 0, 0
    cost = sum(repair_cost(it) for it in todo)
    if p.gold < cost:
        world.log("Repairs cost %d gold - you don't have enough." % cost, (255, 80, 80))
        return 0, 0
    p.gold -= cost
    for it in todo:
        if has_dur(it) and not getattr(it, "ethereal", False):
            it.dur = it.max_dur
        for c in (getattr(it, "charges", None) or {}).values():
            c[0] = c[1]
    p.recalc()
    world.log("Repaired %d item%s for %d gold." % (len(todo), "" if len(todo) == 1 else "s", cost), (199, 179, 119))
    return cost, len(todo)
