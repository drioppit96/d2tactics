"""Quality of life options (Game Menu > Quality of Life). They belong to the character and are
saved with it.

  big_inv  - a second backpack page: twice the inventory (10 x 8, shown 10 x 4 at a time)
  goblin   - vendors sell the Loot Goblin: a 1x1 item, never used up; right click it to sell your
             loot anywhere, and a golden Fallen (the goblin) follows you around
  inf_buffs - your own buffs (Battle Orders, Shout, Bone Armor, Holy Shield, Fade...) never wear off
"""
from .items import Item

OPTIONS = [("big_inv", "BIGGER INVENTORY"), ("goblin", "LOOT GOBLIN"), ("inf_buffs", "INFINITE BUFFS")]

# what Infinite Buffs keeps going: your own skill buffs (shouts, armors, auras' partners, forms...)
NOT_BUFFS = ("Antidote", "Thawing")


def endless(player, key, b):
    """With the Infinite Buffs option, a buff from your own skills never runs out
    (curses, shrines and potions still do)."""
    if not get(player, "inf_buffs"):
        return False
    return not (str(key).startswith(("curse:", "shrine:")) or b.get("curse") or b.get("shrine") or key in NOT_BUFFS)
GOBLIN_CODE = "lgb"
GOBLIN_PRICE = 1000
GOLD = (199, 179, 119)
GREY = (170, 170, 170)


def get(player, key):
    return bool((getattr(player, "qol", None) or {}).get(key, False))


def toggle(world, key):
    """Turn an option on / off. Returns the message for the log."""
    p = world.player
    q = getattr(p, "qol", None)
    if q is None:
        q = p.qol = {}
    on = not q.get(key, False)
    if key == "big_inv" and not on:
        if any(getattr(it, "inv_pos", None) and it.inv_pos[1] >= 4 for it in p.inventory):
            return "Empty your second backpack page first."
    q[key] = on
    if key == "goblin":
        ensure_pet(world)
    return "%s: %s." % (dict(OPTIONS)[key].title(), "on" if on else "off")


# ------------------------------------------------------------------ the loot goblin
def make_goblin():
    it = Item("Loot Goblin", GOBLIN_CODE, None, kind="misc")
    it.use = "goblin"
    it.invfile = "invgld"
    it.invw = it.invh = 1
    return it


def is_goblin(it):
    return getattr(it, "code", "") == GOBLIN_CODE


def has_goblin(player):
    return any(is_goblin(it) for it in getattr(player, "inventory", []) or [])


def describe(it):
    return [("Loot Goblin", GOLD), ("Right click: sell your loot to the goblin", GREY),
            ("Never used up", GREY)]


def stock(store, player):
    """With the option on, every vendor's last page offers the Loot Goblin."""
    from .itemactions import STORE_W, STORE_H
    if not get(player, "goblin") or store is None or not store.tabs or store.tabs[0][0] == "gamble":
        return
    if store.npc == "goblin":
        return
    page = next((lst for name, lst in store.tabs if name == "misc"), store.tabs[-1][1])
    if any(is_goblin(it) for it in page):
        return
    taken = set()
    for it in page:
        sx, sy = it.store_pos
        for i in range(max(1, it.invw)):
            for j in range(max(1, it.invh)):
                taken.add((sx + i, sy + j))
    spot = next(((x, y) for y in range(STORE_H - 1, -1, -1) for x in range(STORE_W - 1, -1, -1)
                 if (x, y) not in taken), None)
    if spot is None:
        return
    g = make_goblin()
    g.store_pos = spot
    g.infinite = True
    page.append(g)


def goblin_store():
    from .itemactions import Store
    return Store("goblin", [("misc", [])])


GOBLIN_PET = "lootgoblin"


def ensure_pet(world):
    """The golden Fallen follows you while the option is on and you carry the goblin."""
    p = world.player
    if p is None or not hasattr(world, "monsters"):
        return
    want = get(p, "goblin") and has_goblin(p)
    pets = [m for m in world.monsters if getattr(m, "pet", None) == GOBLIN_PET]
    if not want:
        for m in pets:
            world.monsters.remove(m)
        return
    if any(m.alive for m in pets):
        return
    from .units import Monster
    c = world.content
    t = c.monster_template("fallen1") if c is not None and "fallen1" in getattr(c, "monstats", {}) else None
    cell = None
    for r in (1, 2, 3):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                cc = (p.x + dx, p.y + dy)
                if cell is None and world.grid.walkable(*cc) and world.unit_at(cc) is None:
                    cell = cc
    if cell is None:
        return
    m = Monster("fallen", *cell, rng=world.rng, template=t)
    m.name = "Loot Goblin"
    m.ally = True
    m.ai = "pet"
    m.pet = GOBLIN_PET
    m.invulnerable = True
    m.aware = False
    m.life_turns = None
    m.color_shift = "gold"
    world.monsters.append(m)
    world.emit("place", m, cell)
