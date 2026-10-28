"""What item properties do beyond plain stats (D2's "chance to cast", charges, item auras, +skills
of other classes, deadly strike, crushing blow, open wounds, pierce, absorb...).

    refresh(player)               after every recalc: which skills items grant, charge or cast
    on_hit / on_struck / on_kill  chance-to-cast skills and the on-hit effects
    cast_free(world, name, lvl)   cast a skill at a set level, no AP / mana (procs and charges)
"""
from .grid import chebyshev

PROC_EVENTS = {"hit-skill": "hit", "gethit-skill": "struck", "att-skill": "attack", "kill-skill": "kill",
               "death-skill": "death", "levelup-skill": "levelup"}
_ALL = {}


def all_skills(src, strings=None):
    """Every class skill by name (so a Barbarian's ring can cast Frost Nova)."""
    key = id(src)
    if key not in _ALL:
        from .skills import load_all
        out = {}
        try:
            for cls, tree in load_all(src, strings).items():
                for name, s in tree.items():
                    out.setdefault(name, s)
                    out.setdefault(s.title.lower(), s)
        except Exception:
            pass
        _ALL[key] = out
    return _ALL[key]


def _skill(book, name):
    s = book.tree.get(name)
    if s is not None:
        return s
    from . import props
    src = props.SRC
    if src is None:
        return None
    idx = all_skills(src, getattr(book, "strings", None))
    return idx.get(name) or idx.get(str(name).lower())


def _val(v):
    return v if isinstance(v, tuple) else (v, v)


def refresh(p):
    """Collect what the hero's active items grant: oskills, charges, chance-to-cast, auras."""
    book = getattr(p, "skills", None)
    if book is None:
        return
    from .props import skill_name
    granted, charged, procs, auras = {}, {}, [], {}
    for it in getattr(p, "_active", []) or []:
        if not getattr(it, "identified", True):
            continue
        for e in getattr(it, "mod_list", None) or []:
            code = e[0]
            par = e[2] if len(e) > 2 else ""
            if code in ("skill", "oskill"):
                name = skill_name(par)
                s = _skill(book, name)
                if s is not None and (s.key not in book.tree or not book.levels.get(s.key)):
                    granted[s.key] = granted.get(s.key, 0) + int(_val(e[1])[1])
            elif code == "charged":
                s = _skill(book, skill_name(par))
                if s is None:
                    continue
                n, lvl = _val(e[1])
                ch = getattr(it, "charges", None)
                if ch is None:
                    ch = it.charges = {}
                if s.key not in ch:
                    ch[s.key] = [int(n), int(n), int(lvl)]
                if ch[s.key][0] > 0 and (s.key not in charged or charged[s.key][0] < lvl):
                    charged[s.key] = (int(lvl), it)
            elif code in PROC_EVENTS:
                s = _skill(book, skill_name(par))
                if s is not None:
                    chance, lvl = _val(e[1])
                    procs.append((PROC_EVENTS[code], int(chance), s.key, max(1, int(lvl))))
            elif code == "aura":
                s = _skill(book, skill_name(par))
                if s is not None:
                    lo, hi = _val(e[1])
                    auras[s.key] = max(auras.get(s.key, 0), int(hi or lo or 1))
    # skills of other classes live in the book while an item gives them (marked foreign)
    for name in set(granted) | set(charged) | {pr[2] for pr in procs} | set(auras):
        if name not in book.tree:
            s = _skill(book, name)
            if s is not None:
                book.tree[name] = s
                book.foreign = getattr(book, "foreign", set()) | {name}
    book.granted, book.charged, book.procs, book.item_auras = granted, charged, procs, auras


def is_foreign(book, name):
    return name in getattr(book, "foreign", ()) and name not in getattr(book, "levels", {})


def cast_free(world, name, lvl, target=None, cell=None):
    """Cast a skill at a set level without AP or mana (chance-to-cast, charges)."""
    p = world.player
    book = p.skills
    if name not in book.tree:
        return False
    s = book.tree[name]
    if s.kind in ("passive", "aura"):
        return False
    old_forced = getattr(book, "forced", None)
    book.forced = dict(old_forced or {})
    book.forced[name] = lvl
    prev_free = getattr(world, "_free_cast", False)
    world._free_cast = True
    turn = world.turn
    world.turn = "player"           # a proc can fire during the monsters' turn
    ap = p.ap
    try:
        if target is not None and not target.alive:
            target = None
            if cell is None:
                return False
        if s.kind in ("attack", "melee"):
            return False            # D2 procs are spells; weapon skills don't proc
        if s.kind in ("cry", "corpse", "move"):
            ok = world.use_skill(name, target=target, cell=cell)
        else:
            ok = world.cast_generic(name, target, cell)
    except Exception:
        ok = False
    finally:
        world._free_cast = prev_free
        world.turn = turn
        p.ap = ap
        book.forced = old_forced or {}
    return ok


def _procs(world, event, target=None):
    p = world.player
    book = getattr(p, "skills", None)
    if book is None or getattr(world, "_in_proc", False):
        return
    lst = [pr for pr in getattr(book, "procs", []) if pr[0] == event]
    if not lst:
        return
    world._in_proc = True
    try:
        for _, chance, name, lvl in lst:
            if world.rng.randrange(100) < chance:
                cell = target.pos if target is not None and target.alive else None
                s = book.tree.get(name)
                if s is not None and s.kind in ("nova", "cry", "buff", "summon", "aura"):
                    cell = p.pos
                if cell is None and s is not None and s.kind not in ("nova", "buff", "cry"):
                    continue
                if cast_free(world, name, lvl, target=target if target is not None and target.alive else None, cell=cell):
                    world.log("%s (%d%% chance to cast)" % (s.title if s else name, chance), (110, 110, 255))
    finally:
        world._in_proc = False


def on_attack(world, target):
    _procs(world, "attack", target)


def on_hit(world, attacker, target, dmg, ranged=False):
    """You hit a monster: crushing blow, open wounds, chance-to-cast on striking."""
    p = world.player
    if attacker is not p or not target.alive:
        if attacker is p:
            _procs(world, "hit", None)
        return
    rng = world.rng
    cb = p.mod("cb")
    if cb and target.alive and rng.randrange(100) < min(100, cb if not ranged else cb // 2):
        boss = getattr(target, "unique", False) or getattr(target, "boss", None)
        cut = target.hp // (8 if boss else 4)
        if cut > 0:
            world.log("Crushing blow!", (255, 200, 80))
            world._damage(target, cut, p)
    ow = p.mod("ow")
    if ow and target.alive and rng.randrange(100) < ow and not getattr(target, "res", {}).get("phys", 0) >= 100:
        per = max(1, (p.level * 3 + 10) // 4)
        turns = 4
        target.effects["bleed"] = [per, turns]
        world.log("%s is bleeding!" % target.name, (255, 80, 80))
    _procs(world, "hit", target)


def on_struck(world, attacker):
    _procs(world, "struck", attacker if attacker is not None and getattr(attacker, "alive", False) else None)


def on_kill(world, victim):
    _procs(world, "kill", None)


def on_levelup(world):
    _procs(world, "levelup", None)


def deadly(world, p, dmg):
    """Deadly strike: double physical damage."""
    ds = p.mod("ds")
    if ds and world.rng.randrange(100) < min(100, ds):
        return dmg * 2, True
    return dmg, False


def absorb(p, et, dmg):
    """Elemental absorb: part of the damage heals you instead (D2: % then flat)."""
    if dmg <= 0 or not getattr(p, "is_player", False):
        return dmg, 0
    pct = min(40, p.mod("absorb_%s_pct" % et)) if et in ("fire", "cold", "ltng") else 0
    flat = p.mod("absorb_%s" % et) if et in ("fire", "cold", "ltng") else (p.mod("absorb_mag") if et == "mag" else 0)
    taken = dmg - dmg * pct // 100
    healed = dmg - taken
    a = min(taken, flat)
    taken -= a
    healed += a
    if healed:
        p.hp = min(p.max_hp, p.hp + healed)
    return taken, healed


def pierce_next(world, p, target):
    """Pierce: the missile flies on to the next monster on the same line."""
    pc = p.mod("pierce")
    if not pc or world.rng.randrange(100) >= pc:
        return None
    from .skillcast import _extend
    line = _extend(p.pos, target.pos, 14)
    seen_target = False
    for c in line:
        if not world.grid.walkable(*c):
            break
        if c == target.pos:
            seen_target = True
            continue
        if not seen_target:
            continue
        u = world.unit_at(c)
        if u is not None and u is not p and u.alive and getattr(u, "ai", "") != "npc" and not getattr(u, "ally", False):
            return u
    return None


def tick_bleed(world, m):
    b = m.effects.get("bleed")
    if not b:
        return
    per, turns = b
    world._damage(m, per, world.player)
    turns -= 1
    if turns <= 0 or not m.alive:
        m.effects.pop("bleed", None)
    else:
        m.effects["bleed"] = [per, turns]
