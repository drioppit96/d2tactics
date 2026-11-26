"""Torment: the difficulty after Hell, in tiers of ten floors, up to level 1000.

Hell's floor 60 cleared opens it. Torment floors count from 1; every ten are a tier, the tenth an
act boss as everywhere else (and the gate to the next tier).

  Monsters   built from Hell's tables at their own level (at most 99), then grown to the
             floor's Torment level: tier T's first floor is level 100 + 45 T (Torment 1: 145,
             Torment 20: 1000), one level more each floor of the tier. Per 45 levels: life x1.6,
             damage x1.35, attack rating and defence x1.3 - so each tier is a step up, not a
             slope. Experience: an ordinary kill is worth 1/40 of the level it was killed at
             (champions x3, uniques x5, act bosses x50).
  Each tier  T1 more champions; T2 every unique an extra modifier; T3 monsters faster (10% a
  adds      tier past 2, at most 50%); T4 act bosses enrage below half life (+50% damage);
             T5 and on +5 to all monster resistances a tier (not past 75, immunities kept).
  Heroes     go on levelling past 99, to 1000: D2's experience table goes on by 2% more a level
             past its end, every level still 5 stat points and a skill point, and a skill takes
             one more point than D2's 20 for every two levels past 99.
  Rewards    +25% magic find and gold find a tier while on a Torment floor; a Torment floor
             cleared gives the account its tier in Rare Fragments, an act boss its tier in
             Platinum.
  Death      back to the start of the tier, not to Torment 1.
  Gear       what drops on a Torment floor is the tier's: plain, magic and rare items always on
             the elite base of their kind; every item (uniques, sets and runewords made in it
             too) carries its tier, and its numbers grow with it: damage (the base's, flat and
             elemental) and attack rating x1.5 a tier; defence (the base's and flat), life, mana,
             attributes and flat damage reduction x1.35 a tier. Speeds, resistances, leech,
             chances, +skills and percentages of the base (Enhanced Damage, Enhanced Defense)
             stay as they are. It needs 45 levels more a tier past the first. A set's bonuses
             grow with the lowest tier among its worn pieces. Skills (spells, not weapon blows)
             deal x1.5 per tier of the hero's worn gear on average (ten slots).
"""
import math
import random

TIER_FLOORS = 10
LEVELS_PER_TIER = 45
LEVEL_CAP = 1000
#: monsters, per 45 levels past 99
GROW = {"hp": 1.6, "dm": 1.35, "th": 1.3, "ac": 1.3}
#: gear, per tier
GEAR_OFF = 1.5
GEAR_DEF = 1.35
KILLS_PER_LEVEL = 40
XP_GROWTH = 1.02                 # each level past the table's end needs 2% more than the last
SKILL_EXTRA_EVERY = 2            # one more point a skill can take per this many levels past 99
REWARD_FIND = 25                 # magic and gold find a tier, on a Torment floor
SLOTS = ("weapon", "shield", "helm", "armor", "gloves", "belt", "boots", "amulet", "ring1", "ring2")

_installed = [False]


# ------------------------------------------------------------------ floors and levels
def tier_of(depth):
    return (max(1, int(depth)) - 1) // TIER_FLOORS + 1


def level_of(depth):
    """The monsters' level on a Torment floor."""
    t = tier_of(depth)
    return min(LEVEL_CAP, 100 + LEVELS_PER_TIER * t + (max(1, int(depth)) - 1) % TIER_FLOORS)


def tier_start(depth):
    """The last floor cleared before this floor's tier: a death sends the run back to after it."""
    return (tier_of(depth) - 1) * TIER_FLOORS


def grow(col, level):
    return GROW[col] ** (max(0, level - 99) / float(LEVELS_PER_TIER))


# ------------------------------------------------------------------ experience
def _last_step(table):
    """(the last level the table really holds, the XP its last step took)."""
    i = len(table) - 1
    while i > 1 and table[i] <= table[i - 1]:
        i -= 1                                   # (D2's table repeats its last row)
    need = table[i] - table[i - 1] if i >= 1 and table[i] > table[i - 1] else 300000000
    return i, need


def xp_total(level, table):
    """Total XP needed to leave `level`: D2's table while it lasts, then each level 2% more than
    the one before."""
    last, need = _last_step(table)
    if level <= last:
        return table[level]
    n = level - last
    g = XP_GROWTH
    return int(table[last] + need * (g ** (n + 1) - g) / (g - 1))


def xp_need(level):
    """XP from `level` to the next."""
    from game import units
    t = units.XP_TABLE
    return max(1, xp_total(level, t) - xp_total(level - 1, t))


def extra_cap(clvl):
    return max(0, int(clvl) - 99) // SKILL_EXTRA_EVERY


# ------------------------------------------------------------------ monsters
def _quality(m):
    if getattr(m, "rift_boss", False) and getattr(m, "boss", None):
        return 50
    if getattr(m, "unique", False):
        return 5
    if getattr(m, "champion", False):
        return 3
    return 1


def scale_monster(w, m, level):
    """A monster grown to a Torment level (once)."""
    if getattr(m, "_torment", False) or getattr(m, "ally", False) or getattr(m, "is_player", False) \
            or getattr(m, "ai", "") == "npc":
        return False
    from game import rift
    if getattr(m, "level", 1) != 99 and getattr(w, "content", None) is not None:
        try:
            rift.scale_to_level(w, m, 99)
        except Exception:
            pass
    hp, dm, th, ac = (grow(k, level) for k in ("hp", "dm", "th", "ac"))
    m.max_hp = max(1, int(m.max_hp * hp))
    m.hp = m.max_hp
    lo, hi = m.dmg
    m.dmg = (max(1, int(lo * dm)), max(2, int(hi * dm)))
    m.ar = max(5, int(m.ar * th))
    m.defense = max(0, int(getattr(m, "defense", 0) * ac))
    ench = getattr(m, "ench", None)
    if ench:
        m.ench = {k: (max(1, int(a * dm)), max(2, int(b * dm))) for k, (a, b) in ench.items()}
    m.level = int(level)
    m.drop_level = 99
    m.xp_value = max(1, int(xp_need(level) / KILLS_PER_LEVEL)) * _quality(m)
    m._torment = True
    return True


def twists(w, tier, rng=None):
    """What each tier adds, on top of the numbers."""
    from game import monmods
    rng = rng or getattr(w, "rng", random)
    foes = [m for m in w.monsters if not getattr(m, "ally", False) and not getattr(m, "is_player", False)
            and getattr(m, "ai", "") != "npc" and getattr(m, "alive", True)]
    for m in foes:
        if getattr(m, "_twisted", False):
            continue
        m._twisted = True
        plain = not (getattr(m, "unique", False) or getattr(m, "champion", False) or getattr(m, "boss", None))
        if tier >= 1 and plain and rng.random() < min(0.3, 0.05 * tier):
            try:
                monmods.make_champion(w, m)
            except Exception:
                pass
        if tier >= 2 and getattr(m, "unique", False) and not getattr(m, "boss", None):
            have = set(getattr(m, "mods", []) or [])
            pool = [x for x in monmods.RANDOM_MODS if x not in have
                    and (x != monmods.MULTISHOT or getattr(m, "range", 1) > 1)]
            if pool:
                try:
                    monmods.apply(w, m, [rng.choice(pool)])
                except Exception:
                    pass
        if tier >= 3:
            m.speed_bonus = min(50, 10 * (tier - 2))
        if tier >= 4 and getattr(m, "rift_boss", False) and getattr(m, "boss", None):
            m.enrage = True
        if tier >= 5:
            res = dict(getattr(m, "res", {}) or {})
            for k in ("fire", "cold", "ltng", "pois"):
                v = res.get(k, 0)
                if v < 100:
                    res[k] = min(75, v + 5 * (tier - 4))
            m.res = res


def apply_floor(w, depth):
    """Every monster on a Torment floor to its level, and the tier's twists."""
    tier, level = tier_of(depth), level_of(depth)
    w.torment_tier = tier
    w.torment_level = level
    for m in list(w.monsters):
        scale_monster(w, m, level)
    twists(w, tier)
    for m in w.monsters:
        if getattr(m, "_torment", False) and getattr(m, "_twisted", False) and not getattr(m, "_xp_set", False):
            m._xp_set = True
            m.xp_value = max(1, int(xp_need(level) / KILLS_PER_LEVEL)) * _quality(m)   # (after twists)


def keep_up(w):
    """Monsters that came later (raised, called up, a boss's minions): to the floor's level."""
    lvl = getattr(w, "torment_level", None)
    if not lvl:
        return
    new = [m for m in w.monsters if not getattr(m, "_torment", False) and getattr(m, "alive", True)
           and not getattr(m, "ally", False) and not getattr(m, "is_player", False) and getattr(m, "ai", "") != "npc"]
    if new:
        for m in new:
            scale_monster(w, m, lvl)
        twists(w, w.torment_tier)


def enraged(m):
    """An act boss of Torment 4 and on, below half life: +50% damage."""
    return getattr(m, "enrage", False) and m.hp * 2 < m.max_hp


# ------------------------------------------------------------------ gear
SCALE_OFF = {"dmg-min", "dmg-max", "dmg-norm", "mindmg", "maxdmg", "att", "dmg-fire", "dmg-cold", "dmg-ltng",
             "dmg-pois", "dmg-mag", "fire-min", "fire-max", "cold-min", "cold-max", "ltng-min", "ltng-max",
             "pois-min", "pois-max", "mag-min", "mag-max", "dmg-throw", "thorns", "dmg-undead", "dmg-demon"}
SCALE_DEF = {"ac", "ac-miss", "ac-hth", "hp", "mana", "str", "dex", "vit", "enr", "all-stats", "red-dmg",
             "red-mag", "regen", "stam", "heal-kill", "mana-kill"}


def factor(code, tier):
    if tier <= 0:
        return None
    if code in SCALE_OFF:
        return GEAR_OFF ** tier
    if code in SCALE_DEF:
        return GEAR_DEF ** tier
    return None


def _sv(v, f):
    if isinstance(v, tuple):
        return (max(1, int(round(v[0] * f))), max(1, int(round(v[1] * f))))
    return int(round(v * f)) if v >= 0 else v


def scale_lines(it, tier, start=0):
    """The item's property lines from `start` on, grown to `tier` (its stats with them)."""
    from game import props as P
    from game.d2content import PROP_MAP
    if not it.mod_list:
        return
    out = list(it.mod_list[:start])
    for e in it.mod_list[start:]:
        code, v = e[0], e[1]
        param = e[2] if len(e) > 2 else ""
        f = factor(code, tier)
        if f is None or not isinstance(v, (int, tuple)) or isinstance(v, bool):
            out.append(e)
            continue
        nv = _sv(v, f)
        out.append((code, nv, param) if len(e) > 2 else (code, nv))
        # the item's stats, by the same keys props.apply wrote them under
        if code == "all-stats":
            for k in ("str", "dex", "vit", "eng"):
                it.mods[k] = it.mods.get(k, 0) + (nv - v)
            continue
        info = PROP_MAP.get(code)
        if isinstance(v, tuple):
            if info and info[1] == "minmax":
                key = info[0]
            elif code.startswith("dmg-"):
                key = info[0] if info else ("mag_dmg" if code == "dmg-mag" else code[4:] + "_dmg")
            else:
                continue
            old = it.mods.get(key, (0, 0))
            old = old if isinstance(old, tuple) else (0, 0)
            it.mods[key] = (old[0] + nv[0] - v[0], old[1] + nv[1] - v[1])
            continue
        key = P.stat_key(code, param)
        if key is not None and code not in P.TEXT_ONLY and not isinstance(it.mods.get(key), tuple):
            it.mods[key] = it.mods.get(key, 0) + (nv - v)
    it.mod_list = out
    if getattr(it, "base_defense", None) is not None:
        it.defense = it.base_defense * (100 + it.mods.get("edef", 0)) // 100 + it.mods.get("def", 0)


def scale_plist(plist, tier):
    """[(code, param, lo, hi)] grown to `tier` (a set piece's own bonuses)."""
    out = []
    for p in plist:
        code, param, lo, hi = p
        f = factor(code, tier)
        if f is None:
            out.append(p)
        else:
            out.append((code, param, int(round(lo * f)), int(round(hi * f))))
    return out


def _base_numbers(it, tier):
    """The base's own damage and defence, grown to the tier."""
    off, de = GEAR_OFF ** tier, GEAR_DEF ** tier
    if it.dmg:
        it.dmg = (max(1, int(it.dmg[0] * off)), max(1, int(it.dmg[1] * off)))
    if getattr(it, "dmg2", None):
        it.dmg2 = (max(1, int(it.dmg2[0] * off)), max(1, int(it.dmg2[1] * off)))
    if getattr(it, "base_defense", None) is not None:
        it.base_defense = max(1, int(it.base_defense * de))
        it.defense = it.base_defense * (100 + it.mods.get("edef", 0)) // 100 + it.mods.get("def", 0)


def make_tier(it, tier):
    """An item of a Torment tier: its numbers, its requirement, its tooltip line."""
    if tier <= 0 or getattr(it, "torment", 0):
        return it
    it.torment = int(tier)
    scale_lines(it, tier)
    _base_numbers(it, tier)
    if getattr(it, "set_bonus", None):
        it.set_bonus = [(k, scale_plist(pl, tier)) for k, pl in it.set_bonus]
    it.levelreq = int(getattr(it, "levelreq", 0) or 0) + LEVELS_PER_TIER * (tier - 1)
    _line(it)
    return it


def _line(it):
    t = "Torment %d" % it.torment
    lines = [x for x in (it.extra_lines or []) if not str(x).startswith("Torment ")]
    it.extra_lines = [t] + lines


def on_load(it):
    """A saved Torment item: its mods, lines, damage and defence were saved grown; what is read
    from the base again (two-handed damage) and from the set (its own bonuses) is grown again."""
    t = int(getattr(it, "torment", 0) or 0)
    if t <= 0:
        return
    off = GEAR_OFF ** t
    if getattr(it, "dmg2", None):
        it.dmg2 = (max(1, int(it.dmg2[0] * off)), max(1, int(it.dmg2[1] * off)))
    if getattr(it, "set_bonus", None):
        it.set_bonus = [(k, scale_plist(pl, t)) for k, pl in it.set_bonus]


def elite_base(content, base):
    tiers = base.get("tiers") if isinstance(base, dict) else None
    if not tiers or len(tiers) < 3:
        return base
    return (getattr(content, "base_by_code", None) or {}).get(tiers[2], base)


def on_drops(w, unit, drops):
    """What drops on a Torment floor is the tier's."""
    tier = int(getattr(w, "torment_tier", 0) or 0)
    if tier <= 0:
        return drops
    content = getattr(w, "content", None)
    out = []
    for it in drops:
        if getattr(it, "kind", "") != "equip" or getattr(it, "charm", False) or getattr(it, "gem", None) is not None \
                or getattr(it, "jewel_props", None):
            out.append(it)
            continue
        if getattr(it, "rarity", "") in ("normal", "superior", "low", "magic", "rare") and content is not None:
            base = getattr(it, "base", None)
            eb = elite_base(content, base)
            if eb is not base and eb is not None:
                try:
                    q = getattr(it, "rarity", "normal")
                    new = content.make_item(eb, max(99, int(getattr(it, "ilvl", 99) or 99)), w.rng,
                                            "normal" if q in ("low", "superior") else q,
                                            identified=getattr(it, "identified", True))
                    if new is not None:
                        if getattr(it, "ethereal", False) and not getattr(new, "ethereal", False):
                            new.ethereal = True
                        it = new
                except Exception:
                    pass
        out.append(make_tier(it, tier))
    return out


def on_runeword(host, n0):
    t = int(getattr(host, "torment", 0) or 0)
    if t > 0:
        scale_lines(host, t, n0)


def worn_tier(hero):
    """The hero's Torment gear, on average over ten slots (an empty slot counts 0)."""
    eq = getattr(hero, "equipment", None) or {}
    items = [v for v in eq.values() if v is not None]
    tot = sum(int(getattr(it, "torment", 0) or 0) for it in items)
    return tot / float(len(SLOTS))


def on_set_bonus(part, items):
    t = min(int(getattr(it, "torment", 0) or 0) for it in items)
    if t > 0:
        scale_lines(part, t)


def on_recalc(hero):
    book = getattr(hero, "skills", None)
    if book is not None:
        book.torment_power = GEAR_OFF ** worn_tier(hero)
    t = int(getattr(hero, "_torment_tier", 0) or 0)
    st = getattr(hero, "_skill_stats", None)
    if t > 0 and st is not None:
        st["mf"] = st.get("mf", 0) + REWARD_FIND * t
        st["gf"] = st.get("gf", 0) + REWARD_FIND * t


# ------------------------------------------------------------------ switching it on
def install():
    """The engine's hooks (off for D2 Tactics)."""
    if _installed[0]:
        return
    _installed[0] = True
    from game import units, skills, world, d2items, save
    units.LEVEL_CAP = LEVEL_CAP
    units.XP_EXTEND = lambda level, table: xp_total(level, table)
    units.RECALC_HOOKS.append(on_recalc)
    units.SET_BONUS_HOOK = on_set_bonus
    skills.EXTRA_CAP = extra_cap
    world.DROP_HOOK = on_drops
    d2items.RUNEWORD_HOOK = on_runeword
    save.ITEM_LOAD_HOOKS.append(on_load)
