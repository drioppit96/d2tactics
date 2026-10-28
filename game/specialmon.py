"""D2's odd monsters and traps: hidden missile traps, fire towers, lightning spires, gargoyle traps,
catapults, trapped souls, nests that hatch monsters (mosquito nests, sarcophagi, fallen holes, evil huts,
vile mothers, maggot queens), Act 3's water tentacles, the Regurgitator that eats corpses, and the hell
meteors that rain on the River of Flame.

    spawn_preset(world, name, cell, owner, lvl, taken)   -> True when the preset was one of these
    turn(world, m)                                       -> True when the monster's turn is done
"""
from .grid import chebyshev

# MonStats id (prefix) -> how it behaves
TRAPS = {"trap-firebolt": ("fire", "firebolt"), "trap-lightning": ("ltng", "chainlightning"),
         "trap-nova": ("ltng", "nova"), "trap-poisoncloud": ("pois", "trappoisonjavcloud"),
         "trap-horzmissile": ("phys", "arrow"), "trap-vertmissile": ("phys", "arrow"),
         "trap-melee": ("phys", None)}
TURRETS = {"firetower": ("fire", "firebolt", 7), "lightningspire": ("ltng", "arcanelightningbolt", 8),
           "gargoyletrap": ("phys", "gargoyletrapmissile", 7), "trappedsoul1": ("fire", "firebolt", 5),
           "trappedsoul2": ("fire", "firebolt", 5), "catapult": ("ltng", "catapultchargedball on", 13)}
NESTS = ("suckernest", "sarcophagus", "evilhole", "evilhut", "fallennest")
MOBILE_SPAWNERS = ("vilemother", "maggotqueen")


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _variant(world, base, lvl, n=5):
    """The base1..baseN MonStats row closest to the area level."""
    c = world.content
    best = None
    for i in range(1, n + 1):
        mid = "%s%d" % (base, i)
        r = c.monstats.get(mid) if c is not None else None
        if r is None:
            continue
        ml = _int(r.get("level" + c.sfx) or r.get("level"), 1)
        if best is None or abs(ml - lvl) < best[0]:
            best = (abs(ml - lvl), mid)
    return best[1] if best else None


def _mark(m, kind, **kw):
    m.special = kind
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def spawn_preset(world, name, cell, owner, lvl, taken):
    from .actworld import _spawn, _free_near, _scatter
    low = name.lower()
    g = world.grid
    rng = world.rng
    c = world.content
    if c is None:
        return False
    if low.startswith("trap-") and low in TRAPS:
        cell = _free_near(g, cell, 4)
        m = _spawn(world, low, cell, lvl, taken)
        if m is None:
            return True
        el, mis = TRAPS[low]
        _mark(m, "trap", hidden=True, invulnerable=True, stationary=True, sight=4, shots=3, elem=el, trap_missile=mis)
        m.name = "Trap"
        m.xp_value = 0
        return True
    base = low.rstrip("0123456789")
    if low in TURRETS or base in TURRETS:
        el, mis, rng_ = TURRETS.get(low) or TURRETS[base]
        if any(getattr(o, "special", None) == "turret" and chebyshev(o.pos, cell) <= 8 for o in world.monsters):
            return True                 # D2's pieces often stack two markers on one spot
        m = _spawn(world, low if low in c.monstats else base + "1", _free_near(g, cell, 4), lvl, taken)
        if m is not None:
            _mark(m, "turret", stationary=True, elem=el, trap_missile=mis, range=rng_, sight=rng_ + 2)
        return True
    if low == "catapultspotter1" or low == "catapultspotter2":
        return True                     # D2's invisible helpers that aim the catapults
    if low.startswith(("place_tentacle",)):
        head = _variant(world, "tentaclehead", lvl, 3)
        if head is None:
            return True
        hcell = _free_near(g, cell, 5)
        m = _spawn(world, head, hcell, lvl, taken)
        if m is None:
            return True
        _mark(m, "tentacle_head", stationary=True, range=6, elem="pois", trap_missile="tentaclegoo")
        tent = _variant(world, "tentacle", lvl, 3)
        for c2 in _scatter(world, hcell, rng.randint(3, 5), taken, radius=4):
            t = _spawn(world, tent, c2, lvl, taken) if tent else None
            if t is not None:
                _mark(t, "tentacle", stationary=True, reach=2)
        return True
    if low == "place_mosquitonest":
        mid = _variant(world, "suckernest", lvl, 4)
        m = _spawn(world, mid, _free_near(g, cell, 5), lvl, taken) if mid else None
        if m is not None:
            _nest(world, m)
        return True
    if low in ("sarcophagus", "evilhut", "place_fallennest"):
        mid = {"place_fallennest": _variant(world, "evilhole", lvl, 5)}.get(low, low)
        m = _spawn(world, mid, _free_near(g, cell, 5), lvl, taken) if mid else None
        if m is not None:
            _nest(world, m)
        return True
    if low == "place_fetishnest":
        roster = world.info.roster(owner) if getattr(world, "info", None) else []
        fet = next((r for r in roster if r.startswith("fetish") and not r.startswith("fetishshaman")), None) or \
            _variant(world, "fetish", lvl, 5)
        sham = next((r for r in roster if r.startswith("fetishshaman")), None) or _variant(world, "fetishshaman", lvl, 5)
        centre = _free_near(g, cell, 5)
        if centre is None:
            return True
        if sham:
            _spawn(world, sham, centre, lvl, taken)
        for c2 in _scatter(world, centre, rng.randint(4, 7), taken, radius=5):
            if fet:
                _spawn(world, fet, c2, lvl, taken)
        return True
    if low.startswith("regurgitator") or low == "place_maggot":
        mid = low if low in c.monstats else _variant(world, "maggotqueen", lvl, 5)
        m = _spawn(world, mid, _free_near(g, cell, 5), lvl, taken) if mid else None
        if m is not None and low.startswith("regurgitator"):
            _mark(m, "regurgitator")
        elif m is not None:
            _mark(m, "spawner", child=(c.monstats.get(mid, {}).get("spawn") or "").lower(), children=[])
        return True
    if low == "hellmeteor":
        m = _spawn(world, "hellmeteor", _free_near(g, cell, 5), lvl, taken)
        if m is not None:
            _mark(m, "meteor", hidden=True, invulnerable=True, stationary=True, sight=14)
            m.xp_value = 0
        return True
    return False


def _nest(world, m):
    c = world.content
    child = (c.monstats.get(m.d2id, {}).get("spawn") or "").lower() if c is not None else ""
    _mark(m, "nest", stationary=True, child=child, children=[], sight=9)


def tag_roster_monster(world, m):
    """Monsters from the area rosters that need special handling (vile mothers, maggot queens...)."""
    mid = (getattr(m, "d2id", "") or "").lower()
    if mid.startswith(MOBILE_SPAWNERS):
        c = world.content
        child = (c.monstats.get(mid, {}).get("spawn") or "").lower() if c is not None else ""
        if child:
            _mark(m, "spawner", child=child, children=[])
    elif mid.startswith("regurgitator"):
        _mark(m, "regurgitator")


# ---------------------------------------------------------------- their turns
def _shoot(world, m, target, el, missile, lo, hi, area=0):
    if missile:
        world.emit("projectile", m, m.pos, target.pos, {"fire": "fireball", "ltng": "ltng", "cold": "cold",
                                                          "pois": "spike"}.get(el, "arrow"), missile)
    victims = [target]
    if area:
        victims = [u for u in [world.player] + world.allies() if u.alive and chebyshev(u.pos, target.pos) <= area]
    for u in victims:
        if el == "phys":
            dmg = world.rng.randint(lo, max(lo, hi))
            if getattr(u, "is_player", False):
                dmg = max(1, dmg - getattr(u, "dr", 0))
            world._damage(u, dmg, m)
        else:
            world.elem_hit(u, el, lo, hi, m, 75, show=False)


def _lvl_dmg(m, mult=1.0):
    lvl = max(1, m.level)
    return max(1, int(lvl * mult)), max(2, int((lvl * 3 + 4) * mult))


def turn(world, m):
    kind = getattr(m, "special", None)
    p = world.player
    rng = world.rng
    if kind is None:
        return False
    tgt = p
    d = chebyshev(m.pos, p.pos)
    los = world.grid.line_of_sight(m.pos, p.pos)
    if kind == "trap":
        if m.shots <= 0 or d > m.sight + 3 or not los:
            m.aware = False
            if m.shots <= 0:
                m.sight = -1             # spent
            return True
        m.shots -= 1
        if m.elem == "phys" and m.trap_missile is None:
            if d <= 1:
                _shoot(world, m, tgt, "phys", None, *_lvl_dmg(m, 1.5))
        else:
            _shoot(world, m, tgt, m.elem, m.trap_missile, *_lvl_dmg(m), area=2 if m.d2id == "trap-nova" else 0)
        world.log("A trap fires!", (255, 140, 60))
        return True
    if kind in ("turret", "tentacle_head"):
        if d <= m.range and (los or m.range >= 12):
            lo, hi = m.dmg if m.elem == "phys" else _lvl_dmg(m)
            _shoot(world, m, tgt, m.elem, m.trap_missile, lo, hi, area=1 if m.range >= 12 else 0)
        return True
    if kind == "tentacle":
        if m.life_turns is not None:
            m.life_turns -= 1
            if m.life_turns < 0:
                m.alive = False
                world.emit("death", m)
                return True
        if d <= getattr(m, "reach", 2):
            world._resolve_attack(m, tgt)
        return True
    if kind == "meteor":
        if d <= m.sight and rng.random() < 0.35:
            spot = (p.x + rng.randint(-2, 2), p.y + rng.randint(-2, 2))
            world.emit("explosion", spot, "meteorexplode")
            for u in [p] + world.allies():
                if u.alive and chebyshev(u.pos, spot) <= 1:
                    world.elem_hit(u, "fire", *_lvl_dmg(m, 1.5), m, 0, show=False)
            world.log("A meteor falls from the burning sky!", (255, 140, 60))
        if d > m.sight + 4:
            m.aware = False
        return True
    if kind == "nest":
        _hatch(world, m, every=2)
        return True
    if kind == "spawner":
        _hatch(world, m, every=3)
        return False
    if kind == "regurgitator":
        if m.hp < m.max_hp * 0.7:
            for c in list(world.corpses):
                if chebyshev(c.pos, m.pos) <= 3 and not getattr(c, "searched", False):
                    c.searched = True
                    world.corpses.remove(c)
                    heal = m.max_hp // 4
                    m.hp = min(m.max_hp, m.hp + heal)
                    world.emit("heal", m, heal)
                    world.log("%s devours a corpse!" % m.name, (255, 80, 80))
                    return True
        if 2 <= d <= 5 and los and rng.random() < 0.4:
            _shoot(world, m, tgt, "phys", "regurgitatorcorpse", *m.dmg)
            return True
        return False
    return False


def _hatch(world, m, every=2):
    if not m.child or not m.aware:
        return
    m.children = [x for x in m.children if x.alive]
    m._hatch_t = getattr(m, "_hatch_t", 0) + 1
    if m._hatch_t % every or len(m.children) >= 6:
        return
    from .actworld import _spawn, _spots
    taken = world.occupied()
    spots = _spots(world, m.pos, 1, taken, radius=2 + getattr(m, "radius", 0))
    if not spots:
        return
    lvl = max(1, m.level - 1)
    k = _spawn(world, m.child, spots[0], lvl, set(taken))
    if k is not None:
        k.aware = True
        m.children.append(k)
        world.emit("place", k, k.pos)
        world.log("%s releases %s!" % (m.name, k.name), (255, 140, 60))
