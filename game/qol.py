"""Quality of life options (Game Menu > Quality of Life). They belong to the character and are
saved with it; in tactics mode they are the party's, so every hero has them.

  big_inv  - a second backpack page: twice the inventory (10 x 8, shown 10 x 4 at a time)
  goblin   - vendors sell the Loot Goblin: a 1x1 item, never used up; right click it to sell your
             loot anywhere; a golden Fallen (the goblin) pops up while his shop is open
  inf_buffs - your own buffs (Battle Orders, Shout, Bone Armor, Holy Shield, Fade...) never wear off
  used_up_pots - D2's potions: every potion is used up when you drink it, and none has a cooldown
             (off: healing and mana potions are permanent and rest a few turns after a drink)
"""
from .items import Item

OPTIONS = [("big_inv", "BIGGER INVENTORY"), ("goblin", "LOOT GOBLIN"), ("inf_buffs", "INFINITE BUFFS"),
           ("used_up_pots", "USED-UP POTIONS")]

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


def heroes(world):
    """Everyone the options apply to: the whole party in tactics mode, otherwise the one hero."""
    from . import tactics
    return [h for h in tactics.everyone(world) if h is not None]


def toggle(world, key):
    """Turn an option on / off for every hero. Returns the message for the log."""
    hs = heroes(world)
    on = not get(world.player, key)
    if key == "big_inv" and not on:
        for h in hs:
            if any(getattr(it, "inv_pos", None) and it.inv_pos[1] >= 4 for it in h.inventory):
                return "Empty %s's lower backpack rows first." % h.name
    for h in hs:
        q = getattr(h, "qol", None)
        if q is None:
            q = h.qol = {}
        q[key] = on
    if key == "goblin":
        ensure_pet(world)
    return "%s: %s." % (dict(OPTIONS)[key].title(), "on" if on else "off")


def sync(party):
    """One hero having an option on means the party has it (loading a party put together before
    the options were shared)."""
    party = [h for h in party if h is not None]
    on = set()
    for h in party:
        on |= {k for k, v in (getattr(h, "qol", None) or {}).items() if v}
    for h in party:
        q = getattr(h, "qol", None)
        if q is None:
            q = h.qol = {}
        for k in on:
            q[k] = True
    return on


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
    """The golden Fallen (the goblin himself) shows up while you trade with the Loot Goblin, and runs
    off once you close his shop."""
    import time
    p = world.player
    if p is None or not hasattr(world, "monsters"):
        return
    want = get(p, "goblin") and has_goblin(p) and getattr(world, "goblin_open", False)
    pets = [m for m in world.monsters if getattr(m, "pet", None) == GOBLIN_PET]
    if not want:
        for m in pets:
            t = getattr(m, "fled_at", None)
            if t is None:
                # off he scurries: a dash away from you, then he is gone
                m.fled_at = time.time()
                far = None
                for r in (9, 7, 5, 3):
                    dx, dy = (m.x - p.x), (m.y - p.y)
                    if dx == 0 and dy == 0:
                        dx, dy = 1, 1
                    n = float(max(abs(dx), abs(dy)))
                    c = (m.x + int(round(dx * r / n)), m.y + int(round(dy * r / n)))
                    if world.grid.walkable(*c) and world.unit_at(c) is None:
                        path = world.grid.find_path(m.pos, c, limit=4000) if hasattr(world.grid, "find_path") else None
                        if path:
                            far = path
                            break
                if far:
                    m.x, m.y = far[-1]
                    world.emit("move", m, far)
            elif time.time() - t > 1.2:
                world.monsters.remove(m)
        return
    pets = [m for m in pets if getattr(m, "fled_at", None) is None]
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
