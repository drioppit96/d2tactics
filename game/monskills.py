"""Monster skills (MonStats Skill1-8): bolts, novas, blizzards, curses, teleports, charges, heals,
summons and corpse explosions - the spells D2's monsters and bosses cast besides their plain attacks.

    skills_of(row)        -> [(skill, level)] from a MonStats row
    try_cast(world, m)    -> True if the monster used a skill this step (AP paid)
"""
from .grid import chebyshev

# skill -> (kind, element, power, missile shown)
#   bolt: a missile at you   nova: a ring around the caster   area: lands on you (radius 1)
#   curse / prison / teleport / charge / melee / heal / summon / ce / tentacles / hose / cone
SKILLS = {
    "AndrialSpray": ("cone", "pois", 1.2, "andarielspray"), "AndyPoisonBolt": ("bolt", "pois", 1.0, "andypoisonbolt"),
    "PrimeLightning": ("bolt", "ltng", 1.1, "monsterlight"), "PrimeBolt": ("bolt", "ltng", 0.8, "chargedbolt"),
    "PrimePoisonNova": ("nova", "pois", 1.0, "primepoisoncloud"), "MephistoMissile": ("bolt", "mag", 1.0, "mephisto"),
    "MephFrostNova": ("nova", "cold", 0.9, "frostnova"), "Blizzard": ("area", "cold", 1.2, "blizzardcenter"),
    "DiabLight": ("hose", "ltng", 0.9, "diablight"), "DiabCold": ("touch", "cold", 1.2, None),
    "DiabFire": ("nova", "fire", 1.0, "diabfire"), "DiabWall": ("area", "fire", 1.0, "diabwallmaker"),
    "PrimeFirewall": ("area", "fire", 0.9, "vampirefirewallmaker"), "DiabPrison": ("prison", None, 0, None),
    "DiabRun": ("charge", None, 1.0, None),
    "Baal Nova": ("nova", "fire", 1.1, "baal nova"), "Baal Inferno": ("cone", "fire", 1.2, "baal inferno"),
    "Baal Cold Missiles": ("area", "cold", 1.0, "baal cold maker"), "Baal Teleport": ("teleport", None, 0, None),
    "Baal Clone Teleport": ("teleport", None, 0, None), "Baal Tentacle": ("tentacles", None, 0, None),
    "Defense Curse": ("curse", "def", 0, None), "Blood Mana": ("curse", "bloodmana", 0, None),
    "NihlathakCorpseExplosion": ("ce", "fire", 1.0, "corpseexplosion"),
    "Horror Arctic Blast": ("cone", "cold", 0.9, "frozenhorror arcticblast1"),
    "Hydra": ("bolt", "fire", 0.9, "hydra"), "ZakarumHeal": ("heal", None, 1.0, None),
    "UnHolyBolt": ("bolt", "mag", 0.8, "unholybolt1"), "Frost Nova": ("nova", "cold", 0.8, "frostnova"),
    "Glacial Spike": ("bolt", "cold", 1.0, "glacialspike"), "Fire Ball": ("bolt", "fire", 1.0, "fireball"),
    "VampireFirewall": ("area", "fire", 0.8, "vampirefirewallmaker"), "VampireFireball": ("bolt", "fire", 0.9, "vampirefireball"),
    "VampireMeteor": ("area", "fire", 1.2, "vampiremeteorcenter"), "VampireMissile": ("bolt", "mag", 0.6, "vampiremissile"),
    "Weaken": ("curse", "weaken", 0, None), "Amplify Damage": ("curse", "amp", 0, None),
    "SuccubusBolt": ("bolt", "mag", 0.8, "succubusmiss"), "ImpBolt": ("bolt", "ltng", 0.7, "imp charged bolt"),
    "Imp Fireball": ("bolt", "fire", 0.8, "impfireball"), "Imp Inferno": ("cone", "fire", 0.8, "impinferno"),
    "FetishInferno": ("cone", "fire", 0.8, "fetishinferno1"), "MonBlizzard": ("area", "cold", 0.9, "monblizcenter"),
    "ZakarumLightning": ("bolt", "ltng", 0.9, "monsterlight"), "MonTeleport": ("teleport", None, 0, None),
    "Imp Teleport": ("teleport", None, 0, None), "Charge": ("charge", None, 1.0, None),
    "Leap": ("charge", None, 0.8, None), "Leap Attack": ("charge", None, 1.3, None),
    "Jab": ("melee", None, 1.5, None), "Smite": ("melee", None, 1.3, None), "Whirlwind": ("melee", None, 1.6, None),
    "Overseer Whip": ("melee", None, 1.2, None), "Quick Strike": ("melee", None, 1.2, None),
    "BloodLordFrenzy": ("melee", None, 1.6, None), "DeathMaul": ("melee", None, 1.4, None),
    "Healing Vortex": ("heal", None, 0.6, None), "Cry Help": ("summon", None, 0, None),
    "MinionSpawner": ("summon", None, 0, None), "Siege Beast Stomp": ("nova", "phys", 0.8, None),
    "Charged Bolt": ("bolt", "ltng", 0.7, "chargedbolt"), "Lightning": ("bolt", "ltng", 1.0, "lightningbolt"),
    "Fire Bolt": ("bolt", "fire", 0.7, "firebolt"), "Ice Bolt": ("bolt", "cold", 0.7, "icebolt"),
    "Poison Nova": ("nova", "pois", 0.9, "poisonnova"), "Corpse Explosion": ("ce", "fire", 0.8, "corpseexplosion"),
    "Bone Spear": ("bolt", "mag", 0.9, "bonespear"), "Teeth": ("bolt", "mag", 0.7, "teeth"),
    "Iron Maiden": ("curse", "amp", 0, None), "Decrepify": ("curse", "weaken", 0, None),
}
# casters (D2 AI names) - see world._caster_turn: one big spell OR move + one small attack per turn
CASTER_AIS = {"FallenShaman", "FetishShaman", "SkeletonMage", "FingerMage", "OblivionKnight", "GreaterMummy",
              "Vampire", "HighPriest", "ZakarumPriest", "SuccubusWitch", "Imp", "WillOWisp"}
SPELL_KINDS = {"bolt", "nova", "area", "cone", "hose", "ce", "curse", "prison"}
BIG_KINDS = {"area", "nova", "hose", "ce", "summon", "tentacles"}
MOVE_KINDS = {"teleport", "charge"}


def spell_size(name):
    """'big' (meteor, blizzard, novas, corpse explosion, summons: the caster's whole turn),
    'move' (teleport, charge) or 'small' (bolts, curses, heals...)."""
    kind, _el, power, _m = SKILLS[name]
    if kind in MOVE_KINDS:
        return "move"
    if kind in BIG_KINDS or (kind == "bolt" and power >= 1.15):
        return "big"
    return "small"


REACH = {"bolt": 7, "hose": 7, "area": 7, "cone": 4, "nova": 3, "curse": 7, "prison": 7, "touch": 1, "melee": 1}


def small_reach(m):
    """How close a caster comes before its smaller attack: its missile or its shortest-reaching small spell."""
    r = [REACH[SKILLS[n][0]] for n, _ in getattr(m, "mskills", ()) if spell_size(n) == "small" and SKILLS[n][0] in REACH]
    if m.range > 1:
        r.append(m.range)
    return min(r) if r else 1


def is_caster(d2ai, skills):
    return d2ai in CASTER_AIS or any(SKILLS[s][0] in SPELL_KINDS for s, _ in skills or ())


CURSE_STATS = {"amp": ("Amplify Damage", {"dr_pct": -100}), "weaken": ("Weaken", {"ed": -33}),
               "def": ("Defense Curse", {"def_pct": -50}), "bloodmana": ("Blood Mana", {"mana_regen_pct": -100})}


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def skills_of(row):
    out = []
    for i in range(1, 9):
        s = row.get("skill%d" % i, "")
        if s and s in SKILLS:
            out.append((s, max(1, _int(row.get("sk%dlvl" % i), 1))))
    return out


def _dmg(m, power, boss=False):
    lvl = max(1, m.level)
    mult = power * (1.6 if boss else 1.0)
    return max(1, int(lvl * 1.2 * mult)), max(2, int((lvl * 3.2 + 6) * mult))


def _hit(world, u, el, lo, hi, src):
    if el == "phys" or el is None:
        dmg = world.rng.randint(lo, max(lo, hi))
        if getattr(u, "is_player", False):
            dmg = max(1, dmg - getattr(u, "dr", 0))
        world._damage(u, dmg, src)
    else:
        world.elem_hit(u, el, lo, hi, src, 75, show=False)


def _targets_near(world, cell, r):
    p = world.player
    out = [p] if p.alive and chebyshev(p.pos, cell) <= r else []
    out += [a for a in world.allies() if a.alive and chebyshev(a.pos, cell) <= r and not getattr(a, "invulnerable", False)]
    return out


def try_cast(world, m, size=None, chance=None):
    """size: only spells of that size ('big' / 'small' / 'move'); chance overrides how often it tries."""
    sk = getattr(m, "mskills", None)
    if size is not None and sk:
        sk = [x for x in sk if spell_size(x[0]) == size]
    if not sk or m.ap < m.attack_cost:
        return False
    rng = world.rng
    tgt = world._monster_target(m)
    if tgt is None or not tgt.alive:
        return False
    d = world.udist(m, tgt)
    los = world.grid.line_of_sight(m.pos, tgt.pos)
    boss = bool(getattr(m, "boss", None))
    if chance is None:
        chance = 0.55 if boss else (0.5 if m.range > 1 else 0.3)
    if rng.random() > chance:
        return False
    usable = []
    for name, lvl in sk:
        kind = SKILLS[name][0]
        if kind in ("bolt", "hose", "area") and (d > 9 or not los):
            continue
        if kind == "cone" and (d > 4 or not los):
            continue
        if kind == "nova" and d > 4:
            continue
        if kind in ("touch", "melee") and d > 1:
            continue
        if kind == "charge" and (d <= 1 or d > 8 or not los):
            continue
        if kind == "teleport" and not (d > 4 or (m.hp < m.max_hp * 0.3 and d <= 2)):
            continue
        if kind == "heal" and not any(o.alive and not o.ally and o.ai != "npc" and o.hp < o.max_hp * 0.6
                                      and chebyshev(o.pos, m.pos) <= 6 for o in world.monsters):
            continue
        if kind == "curse" and (d > 8 or not getattr(tgt, "is_player", False) or
                                "curse:" + CURSE_STATS[SKILLS[name][1]][0] in tgt.buffs):
            continue
        if kind == "ce" and not _ce_corpse(world, tgt):
            continue
        if kind == "summon" and len([o for o in world.monsters if getattr(o, "summoned_by", None) is m and o.alive]) >= 6:
            continue
        if kind == "tentacles" and getattr(m, "_tentacles", 0) >= 3:
            continue
        if kind == "prison" and (d > 8 or not getattr(tgt, "is_player", False) or tgt.effects.get("chilled")):
            continue
        usable.append((name, lvl))
    if not usable:
        return False
    name, lvl = rng.choice(usable)
    m.ap -= m.attack_cost
    return cast(world, m, name, lvl, tgt)


def cast(world, m, name, lvl, tgt):
    kind, el, power, missile = SKILLS[name]
    rng = world.rng
    boss = bool(getattr(m, "boss", None))
    lo, hi = _dmg(m, power, boss)
    world.emit("attack", m, tgt.pos, "cast")
    if kind == "bolt":
        world.emit("projectile", m, m.pos, tgt.pos, {"fire": "fireball", "cold": "cold", "ltng": "ltng"}.get(el, "spike"), missile)
        _hit(world, tgt, el, lo, hi, m)
    elif kind == "hose":                # Diablo's red lightning: a stream of bolts
        for _ in range(3):
            world.emit("projectile", m, m.pos, tgt.pos, "ltng", missile)
            if tgt.alive:
                _hit(world, tgt, el, lo, hi, m)
        world.log("%s's lightning tears into you!" % m.name, (255, 90, 90))
    elif kind == "cone":
        world.emit("projectile", m, m.pos, tgt.pos, "fireball" if el == "fire" else "spike", missile)
        for u in _targets_near(world, tgt.pos, 1):
            _hit(world, u, el, lo, hi, m)
    elif kind == "nova":
        world.emit("nova", m, m.pos, 4, el or "phys", missile)
        for u in _targets_near(world, m.pos, 4):
            _hit(world, u, el, lo, hi, m)
    elif kind == "area":
        world.emit("explosion", tgt.pos, missile or "fireexplode")
        for u in _targets_near(world, tgt.pos, 1):
            _hit(world, u, el, lo, hi, m)
        if el == "cold" and getattr(tgt, "is_player", False):
            from .monmods import chill
            chill(tgt, 1)
    elif kind == "touch":
        _hit(world, tgt, "cold", lo, hi, m)
        if getattr(tgt, "is_player", False):
            from .monmods import chill
            chill(tgt, 2)
    elif kind == "prison":
        tgt.effects["chilled"] = 2
        world.log("Bone walls rise around you!", (255, 90, 90))
    elif kind == "curse":
        title, stats = CURSE_STATS[el]
        tgt.buffs["curse:" + title] = {"turns": 4, "stats": dict(stats), "title": title, "curse": True}
        tgt.recalc()
        world.log("%s curses you: %s!" % (m.name, title), (255, 90, 90))
    elif kind == "teleport":
        _teleport(world, m, tgt, away=m.hp < m.max_hp * 0.3)
    elif kind == "charge":
        if _teleport(world, m, tgt, away=False, walk=True) and tgt.alive:
            world._resolve_attack(m, tgt)
    elif kind == "melee":
        hits = 3 if name == "Jab" else (2 if name in ("BloodLordFrenzy", "Whirlwind") else 1)
        for _ in range(hits):
            if tgt.alive:
                world._resolve_attack(m, tgt)
        if name == "Whirlwind":
            for a in world.allies():
                if a.alive and world.udist(a, m) <= 1:
                    world._resolve_attack(m, a, quiet_anim=True)
    elif kind == "heal":
        for o in world.monsters:
            if o.alive and not o.ally and o.ai != "npc" and chebyshev(o.pos, m.pos) <= 6 and o.hp < o.max_hp:
                h = max(3, o.max_hp * int(15 * power) // 100)
                o.hp = min(o.max_hp, o.hp + h)
                world.emit("heal", o, h)
    elif kind == "summon":
        _summon(world, m, 2)
    elif kind == "tentacles":
        _tentacles(world, m, tgt)
    elif kind == "ce":
        c = _ce_corpse(world, tgt)
        if c is not None:
            world.corpses.remove(c)
            c.searched = True
            world.emit("explosion", c.pos, "corpseexplosion")
            frac = rng.randint(60, 100)
            dmg = max(1, c.max_hp * frac // 100) // 2
            for u in _targets_near(world, c.pos, 2):
                world._damage(u, max(1, dmg - getattr(u, "dr", 0)) if getattr(u, "is_player", False) else dmg, m)
                if u.alive:
                    world.elem_hit(u, "fire", dmg // 2, dmg, m, 0, show=False)
            world.log("%s explodes a corpse!" % m.name, (255, 140, 60))
    return True


def _ce_corpse(world, tgt):
    best = None
    for c in world.corpses:
        if getattr(c, "searched", False) or getattr(c, "is_player", False):
            continue
        dd = chebyshev(c.pos, tgt.pos)
        if dd <= 2 and (best is None or dd < chebyshev(best.pos, tgt.pos)):
            best = c
    return best


def _teleport(world, m, tgt, away=False, walk=False):
    rng = world.rng
    occ = world.occupied(m)
    if away:
        cands = [(m.x + dx, m.y + dy) for dx in range(-8, 9) for dy in range(-8, 9)
                 if max(abs(dx), abs(dy)) >= 6]
    else:
        cands = [(tgt.x + dx, tgt.y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy]
    rng.shuffle(cands)
    for c in cands:
        if world.grid.walkable(*c) and c not in occ and (not walk or world.grid.line_of_sight(m.pos, c)):
            src = m.pos
            m.x, m.y = c
            world.emit("teleport", m, src, c)
            return True
    return False


def _summon(world, m, n):
    from .actworld import _spawn, _spots
    c = world.content
    row = c.monstats.get(getattr(m, "d2id", "") or "", {}) if c is not None else {}
    mid = (row.get("minion1") or row.get("spawn") or "").lower()
    if not mid and getattr(m, "boss", None) == "nihlathak":
        mid = "minion1"
    if not mid or mid not in (c.monstats if c is not None else {}):
        return
    taken = world.occupied()
    for cell in _spots(world, m.pos, n, taken, radius=3):
        k = _spawn(world, mid, cell, max(1, m.level - 2), set(taken))
        if k is not None:
            k.aware = True
            k.summoned_by = m
            world.emit("place", k, k.pos)
    world.log("%s calls for help!" % m.name, (255, 140, 60))


def _tentacles(world, m, tgt):
    """Baal's tentacles burst out of the floor around you."""
    from .actworld import _spawn
    c = world.content
    lvl = max(1, m.level - 5)
    mid = next((x for x in ("baaltentacle5", "baaltentacle1") if c is not None and x in c.monstats), None)
    if mid is None:
        return
    taken = world.occupied()
    made = 0
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (2, 2)):
        cell = (tgt.x + dx, tgt.y + dy)
        if world.grid.walkable(*cell) and cell not in taken and made < 3:
            k = _spawn(world, mid, cell, lvl, set(taken))
            if k is not None:
                k.aware = True
                k.stationary = True
                k.special = "tentacle"
                k.reach = 2
                k.life_turns = 6
                world.emit("place", k, k.pos)
                made += 1
    m._tentacles = getattr(m, "_tentacles", 0) + 1
    world.log("Tentacles burst from the ground!", (255, 90, 90))
