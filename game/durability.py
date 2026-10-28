"""Ethereal items (D2: +50% damage / defense, -10 strength / dexterity requirements).

Durability is not used in this game: items never wear out or break, and arrows, bolts and
throwing weapons are never used up.
"""

ETHEREAL_CHANCE = 0.03
NO_DUR_CODES = {"dur", "dur%", "rep-dur", "indestruct", "rep-quant", "stack"}   # properties with nothing to do here


def has_dur(it):
    return False


def broken(it):
    return False


def init(it, base, rng, ethereal_ok=True):
    it.max_dur = 0
    if ethereal_ok and not getattr(it, "ethereal", False) and rng.random() < ETHEREAL_CHANCE \
            and it.rarity not in ("set",) and not getattr(it, "sockets", 0) and not base.get("quiver"):
        make_ethereal(it)


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
    return


def tick_self_repair(unit):
    return


def recharge_cost(it):
    n = sum(max(0, c[1] - c[0]) * (c[2] + 2) for c in (getattr(it, "charges", None) or {}).values())
    return n * 2


def carried(p):
    out = [x for x in p.equipment.values() if x is not None]
    out += list(p.inventory)
    return out


def recharge_all(world):
    """A smith refills the charges of what you carry. Returns the cost."""
    p = world.player
    todo = [it for it in carried(p) if recharge_cost(it)]
    if not todo:
        world.log("Nothing needs recharging.", (160, 160, 160))
        return 0
    cost = sum(recharge_cost(it) for it in todo)
    if p.gold < cost:
        world.log("Recharging costs %d gold - you don't have enough." % cost, (255, 80, 80))
        return 0
    p.gold -= cost
    for it in todo:
        for c in (getattr(it, "charges", None) or {}).values():
            c[0] = c[1]
    p.recalc()
    world.log("Recharged %d item%s for %d gold." % (len(todo), "" if len(todo) == 1 else "s", cost), (199, 179, 119))
    return cost
