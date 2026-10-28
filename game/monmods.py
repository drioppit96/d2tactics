"""Unique and champion monsters (D2's MonUMod.txt): random names, Extra Strong, Extra Fast, Cursed,
Magic Resistant, Fire / Cold / Lightning Enchanted, Mana Burn, Teleportation, Spectral Hit, Stone Skin,
Multiple Shots, auras - and the champion kinds (Champion, Berserker, Fanatic, Ghostly).

    make_unique(world, m)            a monster becomes a random unique (name + mods)
    make_champion(world, m, kind)    a champion of a pack
    apply(world, m, mod ids)         MonUMod ids (SuperUniques.txt Mod1-3 use the same numbers)
    on_monster_hit / on_struck / on_death / turn_start     what the mods do in a fight
"""
from .grid import chebyshev

# MonUMod ids
STRONG, FAST, CURSE, RESIST, FIRE, LIGHTNING, COLD, MANAHIT, TELEPORT, SPECTRAL, STONESKIN, MULTISHOT, AURA = \
    5, 6, 7, 8, 9, 17, 18, 25, 26, 27, 28, 29, 30
CHAMPION, GHOSTLY, FANATIC, POSSESSED, BERSERK = 16, 36, 37, 38, 39
RANDOM_MODS = [STRONG, FAST, CURSE, RESIST, FIRE, LIGHTNING, COLD, MANAHIT, TELEPORT, SPECTRAL, STONESKIN,
               MULTISHOT, AURA]
NAMES = {STRONG: "Extra Strong", FAST: "Extra Fast", CURSE: "Cursed", RESIST: "Magic Resistant",
         FIRE: "Fire Enchanted", LIGHTNING: "Lightning Enchanted", COLD: "Cold Enchanted", MANAHIT: "Mana Burn",
         TELEPORT: "Teleportation", SPECTRAL: "Spectral Hit", STONESKIN: "Stone Skin", MULTISHOT: "Multiple Shots",
         GHOSTLY: "Ghostly", FANATIC: "Fanatic", BERSERK: "Berserker", POSSESSED: "Possessed", CHAMPION: "Champion"}
MONSTER_AURAS = ["Might", "Holy Fire", "Holy Freeze", "Holy Shock", "Conviction", "Blessed Aim", "Fanaticism",
                 "Thorns", "Defiance", "Prayer", "Vigor", "Concentration"]
BLUE = (110, 110, 255)


def _difficulty(world):
    sfx = getattr(world.content, "sfx", "") if world.content is not None else ""
    return {"": 0, "(n)": 1, "(h)": 2}.get(sfx, 0)


def _unique_name(world):
    c = world.content
    rng = world.rng
    tables = getattr(c, "_uname_tables", None) if c is not None else None
    if tables is None and c is not None:
        from d2.source import read_table
        tables = []
        for t in ("UniquePrefix", "UniqueSuffix", "UniqueAppellation"):
            try:
                names = [r.get("name", "") for r in read_table(c.src, t) if r.get("name")]
            except Exception:
                names = []
            tables.append([c.strings.get(n, n) if getattr(c, "strings", None) is not None else n for n in names])
        c._uname_tables = tables
    if not tables or not all(tables):
        return None
    pre, suf, app = tables
    name = rng.choice(pre) + " " + rng.choice(suf)
    if rng.random() < 0.5:
        name += " " + rng.choice(app)
    return name


def make_unique(world, m, n_mods=None):
    """A random unique (D2: +hp, +3 levels, 1-3 random properties by difficulty)."""
    rng = world.rng
    d = _difficulty(world)
    m.unique = True
    name = _unique_name(world)
    if name:
        m.base_name = getattr(m, "base_name", m.name)
        m.name = name
    m.max_hp = m.hp = int(m.max_hp * 4)
    m.level += 3
    m.xp_value *= 5
    m.ar = int(m.ar * 1.25)
    n = n_mods if n_mods is not None else 1 + d + (1 if rng.random() < 0.5 else 0)
    pool = [x for x in RANDOM_MODS if x != MULTISHOT or getattr(m, "range", 1) > 1]
    rng.shuffle(pool)
    apply(world, m, pool[:max(1, min(4, n))])


def make_champion(world, m, kind=None):
    rng = world.rng
    d = _difficulty(world)
    if kind is None:
        kinds = [CHAMPION, CHAMPION, BERSERK, FANATIC, GHOSTLY] + ([POSSESSED] if d == 2 else [])
        kind = rng.choice(kinds)
    m.champion = True
    m.max_hp = m.hp = int(m.max_hp * 3)
    m.level += 2
    m.xp_value *= 3
    m.ar = int(m.ar * 1.2)
    apply(world, m, [kind])


def apply(world, m, mods):
    """Give a monster MonUMod properties (ids)."""
    rng = world.rng
    have = list(getattr(m, "mods", []))
    m.res = dict(getattr(m, "res", {}) or {})
    for mid in mods:
        if mid in have or not mid:
            continue
        have.append(mid)
        lo, hi = m.dmg
        if mid == STRONG:
            m.dmg = (lo * 7 // 4 + 1, hi * 7 // 4 + 1)
        elif mid == FAST:
            m.max_ap = m.ap = m.max_ap + 3
        elif mid == RESIST:
            for k in ("fire", "cold", "ltng"):
                m.res[k] = min(95, m.res.get(k, 0) + 40) if m.res.get(k, 0) < 100 else m.res[k]
        elif mid in (FIRE, COLD, LIGHTNING):
            k = {FIRE: "fire", COLD: "cold", LIGHTNING: "ltng"}[mid]
            if m.res.get(k, 0) < 100:
                m.res[k] = min(95, m.res.get(k, 0) + 50)
            m.ench = getattr(m, "ench", {})
            m.ench[k] = (max(1, lo // 2 + m.level // 2), max(2, hi + m.level))
        elif mid == STONESKIN:
            m.defense = m.defense * 2 + 10
            if m.res.get("phys", 0) < 100:
                m.res["phys"] = min(75, m.res.get("phys", 0) + 50)
        elif mid == MULTISHOT:
            m.multishot = True
        elif mid == AURA:
            m.aura = rng.choice(MONSTER_AURAS)
            if m.aura == "Might":
                m.dmg = (lo * 3 // 2 + 1, hi * 3 // 2 + 1)
            elif m.aura in ("Fanaticism", "Vigor"):
                m.max_ap = m.ap = m.max_ap + 2
            elif m.aura in ("Blessed Aim",):
                m.ar = int(m.ar * 1.5)
            elif m.aura == "Defiance":
                m.defense = m.defense * 2 + 10
            elif m.aura == "Concentration":
                m.dmg = (lo * 3 // 2 + 1, hi * 3 // 2 + 1)
        elif mid == BERSERK:
            m.dmg = (lo * 2 + 1, hi * 2 + 1)
            m.defense = 0
        elif mid == FANATIC:
            m.max_ap = m.ap = m.max_ap + 2
            m.ar = int(m.ar * 1.3)
        elif mid == GHOSTLY:
            if m.res.get("phys", 0) < 100:
                m.res["phys"] = min(75, m.res.get("phys", 0) + 50)
            m.ghostly = True
        elif mid == POSSESSED:
            m.max_hp = m.hp = m.max_hp * 2
    m.mods = have
    m.mod_names = [("%s Aura" % m.aura) if x == AURA else NAMES[x]
                   for x in have if (x in NAMES or (x == AURA and getattr(m, "aura", None))) and x != CHAMPION]


def pass_aura(boss, minion):
    """D2: a unique's aura is shared by its minions."""
    a = getattr(boss, "aura", None)
    if a:
        minion.aura = a


# ---------------------------------------------------------------- in a fight
def on_monster_hit(world, m, p, dmg):
    """The monster hit you: enchanted damage, spectral hit, mana burn, curses."""
    if not p.alive:
        return
    rng = world.rng
    for k, (lo, hi) in (getattr(m, "ench", None) or {}).items():
        world.elem_hit(p, k, lo, hi, m, 50, show=False)
        if k == "cold" and p.alive:
            chill(p)
    mods = getattr(m, "mods", ())
    if SPECTRAL in mods and p.alive:
        k = rng.choice(("fire", "cold", "ltng"))
        lo, hi = m.dmg
        world.elem_hit(p, k, max(1, lo // 2), max(2, hi // 2), m, 50, show=False)
    if MANAHIT in mods and dmg > 0:
        burn = min(int(p.mana), dmg)
        if burn:
            p.mana -= burn
            world.log("%s burns %d mana!" % (m.name, burn), BLUE)
    if CURSE in mods and rng.random() < 0.35 and "curse:Amplify Damage" not in p.buffs:
        p.buffs["curse:Amplify Damage"] = {"turns": 3, "stats": {"dr_pct": -100}, "title": "Amplify Damage",
                                          "curse": True}
        p.recalc()
        world.log("%s curses you: Amplify Damage!" % m.name, (255, 80, 80))


def chill(p, turns=2):
    if getattr(p, "cbf", 0) or (hasattr(p, "mod") and p.mod("cbf")):
        return
    if hasattr(p, "mod") and p.mod("half_freeze"):
        turns = max(1, turns // 2)
    p.effects["chilled"] = max(p.effects.get("chilled", 0), turns)


def on_struck(world, m):
    """You hit the monster: Lightning Enchanted throws out charged bolts."""
    if LIGHTNING not in getattr(m, "mods", ()) or not m.alive or world.rng.random() > 0.35:
        return
    p = world.player
    if chebyshev(m.pos, p.pos) <= 6 and world.grid.line_of_sight(m.pos, p.pos):
        lo, hi = m.ench.get("ltng", (1, 6)) if getattr(m, "ench", None) else (1, 6)
        world.emit("projectile", m, m.pos, p.pos, "ltng", "chargedbolt")
        world.elem_hit(p, "ltng", lo, hi, m, 0, show=False)
        world.log("%s discharges!" % m.name, BLUE)


def on_death(world, m):
    """Fire Enchanted explode, Cold Enchanted release a frost nova."""
    ench = getattr(m, "ench", None) or {}
    p = world.player
    if "fire" in ench:
        world.emit("explosion", m.pos, "fireexplode")
        if chebyshev(m.pos, p.pos) <= 2 and p.alive:
            lo, hi = ench["fire"]
            world.elem_hit(p, "fire", lo * 2, hi * 2, None, 0, show=False)
            world.log("%s explodes!" % m.name, (255, 140, 60))
    if "cold" in ench:
        world.emit("explosion", m.pos, "frostnova")
        if chebyshev(m.pos, p.pos) <= 4 and p.alive:
            lo, hi = ench["cold"]
            world.elem_hit(p, "cold", lo, hi, None, 0, show=False)
            chill(p, 3)


def turn_start(world, m):
    """Start of a modded monster's turn: teleport next to you, auras."""
    p = world.player
    rng = world.rng
    mods = getattr(m, "mods", ())
    if TELEPORT in mods and m.aware and world.udist(m, p) > 2 and rng.random() < 0.45:
        spots = [(p.x + dx, p.y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
        occ = world.occupied(m)
        spots = [c for c in spots if world.grid.walkable(*c) and c not in occ]
        if spots:
            src = m.pos
            m.x, m.y = rng.choice(spots)
            world.emit("teleport", m, src, m.pos)
            world.log("%s teleports!" % m.name, BLUE)
    aura = getattr(m, "aura", None)
    if not aura or not m.aware:
        return
    d = chebyshev(m.pos, p.pos)
    lvl = max(1, m.level // 4)
    if aura == "Holy Fire" and d <= 4:
        world.elem_hit(p, "fire", 1 + lvl, 3 + lvl * 2, m, 0, show=False)
    elif aura == "Holy Shock" and d <= 4:
        world.elem_hit(p, "ltng", 1, 5 + lvl * 4, m, 0, show=False)
    elif aura == "Holy Freeze" and d <= 6:
        chill(p, 1)
    elif aura == "Prayer":
        for o in world.monsters:
            if o.alive and not o.ally and o.ai != "npc" and chebyshev(o.pos, m.pos) <= 6 and o.hp < o.max_hp:
                o.hp = min(o.max_hp, o.hp + 2 + lvl)


def player_res_penalty(world, p):
    """Conviction auras of monsters near you lower your resistances."""
    pen = 0
    for m in world.monsters:
        if m.alive and getattr(m, "aura", None) == "Conviction" and m.aware and chebyshev(m.pos, p.pos) <= 6:
            pen = max(pen, 25 + m.level // 2)
    return pen


def thorns(world, m, attacker, dmg):
    """A monster with Thorns hits back when you hit it in melee."""
    if getattr(m, "aura", None) == "Thorns" and attacker is world.player and dmg > 0 and attacker.alive:
        world._damage(attacker, max(1, dmg // 4), m)
