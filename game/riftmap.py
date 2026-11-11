"""Rift maps: Gheed's modifier scrolls (this game's own - not in D2).

Gheed sells scrolls on a "Maps" tab once the red portals are open. A scroll carries a curse and a
boon for every tier it has - tier 1 one of each, tier 2 two, tier 3 three - and costs 10, 100 or
1000 gold. Reading one at the start of an Infernal Rift floor twists that one floor: its monsters
hit harder, or are immune to an element, or there are half again as many of them, and in return the
floor pays more - magic find, gold, experience, extra drops.

    stock(content, rng, player)      what Gheed has on the Maps tab
    describe(item)                   the scroll's tooltip (the modifiers, not just the name)
    use(world, item)                 read it: only at the start of a floor, only one at a time
    value(world, key)                how strong a modifier is on this floor (0: not active)

One scroll at a time, and it holds for that floor only: the next floor starts clean.
"""
import random

from . import rift

RED = (235, 90, 70)
BLUE = (110, 110, 255)
GREY = (170, 170, 170)
GOLD = (199, 179, 119)
WHITE = (230, 230, 230)

TIER_NAME = {1: "Lesser", 2: "Greater", 3: "Infernal"}
TIER_COST = {1: 10, 2: 100, 3: 1000}
CODES = {1: "rmp1", 2: "rmp2", 3: "rmp3"}

# key -> (shown name, line, the value at tier 1 / 2 / 3)
CURSES = {
    "hateful":    ("Hateful",    "Monsters deal +%d%% damage",            (30, 45, 60)),
    "unyielding": ("Unyielding", "Monsters have +%d%% life",              (50, 100, 150)),
    "warded":     ("Warded",     "All monsters are immune to %s",         None),
    "swift":      ("Swift",      "Monsters gain +%d Action Points",       (1, 2, 2)),
    "legion":     ("Legion",     "%d%% more monster packs",               (25, 50, 75)),
    "crowned":    ("Crowned",    "%d%% of the monsters are champions",    (25, 40, 60)),
    "cursed":     ("Cursed",     "Every monster carries a boss aura",     None),
    "sapping":    ("Sapping",    "Your resistances are %d lower here",    (20, 30, 40)),
    "barren":     ("Barren",     "Monsters drop no potions",              None),
}
BOONS = {
    "fortunate":  ("Fortunate",  "+%d%% Better Chance of Getting Magic Items", (40, 80, 120)),
    "golden":     ("Golden",     "+%d%% Extra Gold from Monsters",        (40, 80, 120)),
    "storied":    ("Storied",    "+%d%% Experience Gained",               (20, 35, 50)),
    "bountiful":  ("Bountiful",  "Monsters drop %d extra item roll(s)",   (1, 1, 2)),
    "jeweled":    ("Jeweled",    "Gems and runes drop %d times as often", (2, 3, 4)),
    "ancient":    ("Ancient",    "Items drop as if %d levels higher",     (3, 5, 8)),
    "fabled":     ("Fabled",     "Rare, set and unique chance +%d%%",     (40, 70, 100)),
    "hoarded":    ("Hoarded",    "The floor's keeper drops %d extra items", (2, 4, 6)),
}
ELEMENTS = [("fire", "Fire"), ("cold", "Cold"), ("ltng", "Lightning"), ("pois", "Poison")]


# ------------------------------------------------------------------ the scroll
def register_bases(content):
    """Three item bases of our own (the Horadric Scroll's icon), so the scrolls price, draw and save
    like any other misc item."""
    src = content.base_by_code.get("tr1") or content.base_by_code.get("tsc")
    if src is None:
        return
    for tier, code in CODES.items():
        if code in content.base_by_code:
            continue
        b = dict(src)
        b.pop("quest", None)
        b.update(code=code, name="%s Rift Map" % TIER_NAME[tier], use="rift_map", cost=TIER_COST[tier],
                 qlvl=1, levelreq=0, page="misc", slot="", normal_only=True, magic_only=False,
                 shop={}, gamble=0, kind="misc", maxsock=0, sockcaps=(0, 0, 0), tier=tier)
        content.base_by_code[code] = b          # (not in content.bases: it never drops and no NPC column sells it)


def roll(tier, rng=None):
    """The scroll's modifiers: `tier` curses and `tier` boons, each as strong as the tier."""
    rng = rng or random
    tier = max(1, min(3, int(tier)))
    out = dict(tier=tier, curses=[], boons=[])
    for table, where in ((CURSES, "curses"), (BOONS, "boons")):
        for key in rng.sample(sorted(table), tier):
            vals = table[key][2]
            if key == "warded":
                out[where].append([key, rng.choice(ELEMENTS)[0]])
            else:
                out[where].append([key, vals[tier - 1] if vals else 0])
    return out


def make(content, tier, rng=None):
    rng = rng or random
    register_bases(content)
    base = content.base_by_code.get(CODES.get(max(1, min(3, int(tier)))))
    if base is None:
        return None
    it = content.make_item(base, 1, rng)
    if it is None:
        return None
    it.mods = dict(it.mods or {})
    it.mods["rift"] = roll(tier, rng)
    it.name = "%s Rift Map" % TIER_NAME[it.mods["rift"]["tier"]]
    return it


def stock(content, rng, player):
    """Gheed's Maps tab: three lesser, two greater and one infernal scroll, rolled again every visit."""
    if not rift.available(player):
        return []
    out = []
    for tier, n in ((1, 3), (2, 2), (3, 1)):
        for _ in range(n):
            it = make(content, tier, rng)
            if it is not None:
                out.append(it)
    return out


def state_of(item):
    st = (getattr(item, "mods", None) or {}).get("rift")
    return st if isinstance(st, dict) else None


def line(key, val):
    name, text, _ = (CURSES.get(key) or BOONS.get(key) or (key, key, None))
    if key == "warded":
        return "%s: %s" % (name, text % dict(ELEMENTS).get(val, str(val).title()))
    if "%d" not in text:
        return "%s: %s" % (name, text)
    return "%s: %s" % (name, text % val)


def describe(item):
    """The tooltip: every modifier the scroll carries, not just its name."""
    st = state_of(item)
    if st is None:
        return [(item.name, GOLD), ("Rift Map", GREY)]
    out = [(item.name, GOLD), ("Tier %d Rift Map" % st["tier"], WHITE)]
    for key, val in st.get("curses", []):
        out.append((line(key, val), RED))
    for key, val in st.get("boons", []):
        out.append((line(key, val), BLUE))
    out.append(("Right click at the start of an Infernal Rift floor", GREY))
    out.append(("One map at a time, and only on that one floor", GREY))
    return out


# ------------------------------------------------------------------ what is active on this floor
def active(world):
    """The modifiers twisting the floor you are standing on (None: none)."""
    lid = getattr(world, "level_id", None)
    if not rift.is_rift(lid):
        return None
    p = getattr(world, "player", None)
    st = getattr(p, "rift_mods", None)
    if not isinstance(st, dict) or getattr(p, "rift_map_depth", None) != rift.depth_of(lid):
        return None
    return st


def value(world, key):
    """How strong `key` is on this floor: its value, or 0 if the floor does not carry it."""
    st = active(world)
    if not st:
        return 0
    for k, v in st.get("curses", []) + st.get("boons", []):
        if k == key:
            return v if isinstance(v, int) else 1
    return 0


def warded_element(world):
    st = active(world)
    for k, v in (st or {}).get("curses", []):
        if k == "warded":
            return v
    return None


def clear(player):
    player.rift_mods = None
    player.rift_map_depth = None


def summary(world):
    """One line for the message log."""
    st = active(world)
    if not st:
        return ""
    keys = [k for k, _ in st.get("curses", []) + st.get("boons", [])]
    return ", ".join((CURSES.get(k) or BOONS.get(k))[0] for k in keys)


# ------------------------------------------------------------------ reading one
def can_use(world, item):
    p = world.player
    if not rift.is_rift(getattr(world, "level_id", None)):
        return False, "A rift map can only be read inside an Infernal Rift."
    if active(world):
        return False, "A map is already twisting this floor."
    if getattr(p, "rift_map_depth", None) == rift.depth_of(world.level_id):
        return False, "This floor has already had its map."
    if world.corpses or getattr(world, "_rift_fought", False):
        return False, "Too late: a rift map only works before the first blood is spilt."
    if state_of(item) is None:
        return False, "That map is blank."
    return True, ""


def use(world, item):
    """Read the scroll: the floor you stand on is twisted for as long as you are on it."""
    ok, why = can_use(world, item)
    if not ok:
        world.log("Gheed's map: %s" % why, GREY)
        return False
    p = world.player
    p.rift_mods = state_of(item)
    p.rift_map_depth = rift.depth_of(world.level_id)
    apply_to_floor(world)
    world.log("The map burns away. %s is twisted: %s" % (rift.name(world.level_id), summary(world)), RED)
    for key, val in p.rift_mods.get("curses", []):
        world.log("  %s" % line(key, val), RED)
    for key, val in p.rift_mods.get("boons", []):
        world.log("  %s" % line(key, val), BLUE)
    return True


# ------------------------------------------------------------------ twisting the floor
def _monsters(world):
    return [m for m in world.monsters
            if m.alive and not getattr(m, "ally", False) and getattr(m, "ai", "") != "npc"]


def apply_to_floor(world):
    """Everything a map does to the monsters standing on the floor (the rest is read while you play)."""
    st = active(world)
    if not st:
        return
    rng = world.rng
    v = lambda k: value(world, k)
    if v("legion"):
        _legion(world, v("legion"))
    mons = _monsters(world)
    life = v("unyielding")
    if life:
        for m in mons:
            m.max_hp = max(1, int(m.max_hp * (100 + life) / 100.0))
            m.hp = m.max_hp
    elem = warded_element(world)
    if elem:
        for m in mons:
            m.res = dict(getattr(m, "res", {}) or {})
            m.res[elem] = 100
    ap = v("swift")
    if ap:
        for m in mons:
            m.max_ap = m.ap = m.max_ap + ap
    from . import monmods
    champ = v("crowned")
    if champ:
        pool = [m for m in mons if not getattr(m, "unique", False) and not getattr(m, "champion", False)
                and not getattr(m, "rift_boss", False)]
        rng.shuffle(pool)
        for m in pool[:len(pool) * champ // 100]:
            monmods.make_champion(world, m)
        if champ >= 60:
            _twin_keeper(world)
    if v("cursed"):
        for m in _monsters(world):
            if not getattr(m, "aura", None):
                monmods.apply(world, m, [monmods.AURA])
    if v("hoarded"):
        for m in _monsters(world):
            if getattr(m, "rift_boss", False):
                m.rift_hoard = v("hoarded")


def _legion(world, pct):
    """Half again as many packs: more of them, spawned away from where you stand."""
    from . import actworld, tactics
    lid = world.level_id
    info = world.info
    roster = info.roster(lid) if info is not None else []
    if not roster:
        return
    lvl = info.monster_level(lid)
    weights = []
    for r in roster:
        t = actworld._template(world, r, lvl)
        weights.append((t or {}).get("rarity", 1) or 1)
    packs = len(world.__dict__.get("_tpacks", []) or []) or max(1, len(_monsters(world)) // 4)
    want = max(1, packs * pct // 100)
    rng = world.rng
    g = world.grid
    taken = {m.pos for m in world.monsters}
    from .grid import chebyshev
    heroes = [h.pos for h in (tactics.party(world) if tactics.ACTIVE else [world.player]) if h is not None]
    made = 0
    for _ in range(want * 200):
        if made >= want:
            break
        c = (rng.randrange(0, g.w), rng.randrange(0, g.h))
        if not g.walkable(*c) or c in taken:
            continue
        if any(chebyshev(c, h) < 16 for h in heroes):
            continue
        if tactics.ACTIVE:
            tactics.populate_pack(world, c, roster, weights, lvl, taken, 1 + (lvl >= 12) + (lvl >= 24))
        else:
            mid = rng.choices(roster, weights=weights)[0]
            actworld._pack(world, c, mid, lvl, taken)
        made += 1


def _twin_keeper(world):
    """Crowned at its worst: the floor's keeper does not stand alone."""
    from . import actworld, monmods
    boss = next((m for m in world.monsters if m.alive and getattr(m, "rift_boss", False)), None)
    if boss is None or getattr(world, "_rift_twin", False):
        return
    taken = {m.pos for m in world.monsters}
    cell = world._free_cell_near(boss.pos, 8)
    if cell is None:
        return
    twin = actworld._spawn(world, getattr(boss, "d2id", "") or boss.name.lower(), cell,
                           getattr(boss, "level", 1), taken)
    if twin is None:
        return
    world._rift_twin = True
    monmods.make_unique(world, twin)
    twin.rift_boss = True
    twin.max_hp = int(twin.max_hp * 2.5)
    twin.hp = twin.max_hp
    twin.name = "%s, Keeper of the Rift" % twin.name


# ------------------------------------------------------------------ what the floor pays
def extra_picks(world, unit):
    """Extra whole drop rolls for one kill (Bountiful, and Hoarded for the keeper)."""
    n = value(world, "bountiful")
    if getattr(unit, "rift_boss", False):
        n += getattr(unit, "rift_hoard", 0) or value(world, "hoarded")
    return min(8, n)


def ilvl_bonus(world):
    return value(world, "ancient")


def quality_bonus(world):
    return 1.0 + value(world, "fabled") / 100.0


def gold_bonus(world):
    return value(world, "golden")


def mf_bonus(world):
    return value(world, "fortunate")


def xp_mult(world):
    return 1.0 + value(world, "storied") / 100.0


def damage_mult(world):
    return 1.0 + value(world, "hateful") / 100.0


def res_penalty(world):
    return value(world, "sapping")


def filter_drops(world, drops, unit):
    """Barren takes the potions away; Jeweled sprinkles in gems and runes."""
    st = active(world)
    if not st:
        return drops
    if value(world, "barren"):
        drops = [d for d in drops if getattr(d, "kind", "") != "potion"]
    mult = value(world, "jeweled")
    if mult > 1 and world.content is not None:
        # the base game rolls D2's "Good" class (gems, runes, jewellery) on about 4% of kills
        for _ in range(mult - 1):
            if world.rng.random() < 0.04:
                g = world.content.make_gem_or_rune(getattr(unit, "level", 1) or 1, world.rng)
                if g is not None:
                    drops = list(drops) + [g]
    return drops
