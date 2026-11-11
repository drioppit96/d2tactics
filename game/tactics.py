"""Tactics mode: a party of up to three heroes, smaller and denser maps, curated stronger packs.

The hero you control is always world.player; the others walk with you as allies (in
world.monsters, like a hireling) and take their turn in combat one after another: End Turn hands
control to the next hero, and after the last one the monsters move.
"""
ACTIVE = False            # set when a tactics game starts (read by the map builders and the world)
HP_MULT = 2.5             # monsters as in a 4-player D2 game (/players 4: +150% life) - Hell
# Normal and Nightmare: three heroes out-damage D2's 4-player life, so monsters there are tougher
DIFF_HP = {"normal": 3.5, "nightmare": 3.5, "hell": HP_MULT}
DIFF_DMG = {"normal": 1.35, "nightmare": 1.35, "hell": 1.0}      # monster damage to the party
XP_MULT = 1.2             # the difficulty's own experience + 20% (fewer monsters, no hireling)
FALLEN_LIFE = 4           # a fallen hero gets up with 1/4 of their life when the fight is over


def on():
    return ACTIVE


def party(world):
    """The heroes of this game, in party order (the first is the leader)."""
    pt = getattr(world, "party", None)
    return list(pt) if pt else [world.player]


def living(world):
    return [h for h in party(world) if h.alive]


def everyone(world):
    """Every hero the quest rewards belong to: the whole party shares what one of them earns."""
    hs = [h for h in party(world) if h is not None]
    p = getattr(world, "player", None)
    if p is not None and p not in hs:
        hs.append(p)
    return hs or ([p] if p is not None else [])


def _as_follower(world, hero):
    """A hero you are not controlling right now: walks with you and fights beside you."""
    hero.ally = True
    hero.party_member = True
    hero.ai = "party"
    hero.aware = False
    hero.life_turns = None
    hero.hireling = False
    hero.summon_skill = None
    hero.aura_source = world.aura_stats
    if hero not in world.monsters:
        world.monsters.append(hero)


# the game's progress, one for the whole party (the leader's when the party forms): quests, waypoints...
PROGRESS = ("quests", "waypoints", "visited", "cain_rescued", "quest_stats", "boss_kills", "map_explored",
            "tracked_quest", "cairn_order", "current_act", "difficulty", "diff_state", "diff_unlocked", "portal",
            "map_seed")          # (not mode_state: each hero's own normal-game progress)


def share_progress(src, dst):
    for k in PROGRESS:
        if hasattr(src, k):
            setattr(dst, k, getattr(src, k))


def attach(world, heroes):
    """Start a party game: heroes[0] is world.player, the others join as followers next to them."""
    world.party = list(heroes)
    lead = world.player
    for h in heroes:
        if h is not lead:
            share_progress(lead, h)
    occ = world.occupied()
    for h in heroes:
        if h is lead:
            continue
        spot = world._free_cell_near((lead.x + 1, lead.y + 1), 4) or lead.pos
        for c in [(lead.x + dx, lead.y + dy) for dx, dy in ((1, 1), (-1, 1), (1, -1), (2, 0), (0, 2))]:
            if world.grid.walkable(*c) and c not in occ:
                spot = c
                break
        h.x, h.y = spot
        occ.add(spot)
        _as_follower(world, h)


def switch_to(world, hero):
    """Take control of another hero of the party."""
    old = world.player
    if hero is old or not hero.alive or hero not in party(world):
        return False
    if hero in world.monsters:
        world.monsters.remove(hero)
    hero.ally = False
    hero.ai = "player"
    share_progress(old, hero)            # (quests, waypoints... are the party's, whoever leads)
    world.player = hero
    _as_follower(world, old)
    return True


class acting_as:
    """Run world code as if another hero were the one you control (equipping a party member from
    the inventory screens): world.player is that hero inside the with-block."""

    def __init__(self, world, hero):
        self.world, self.hero = world, hero

    def __enter__(self):
        self.old = self.world.player
        self.world.player = self.hero
        return self.hero

    def __exit__(self, *exc):
        self.world.player = self.old
        return False


def next_in_turn(world):
    """The next hero who has not had their turn this round (party order), or None."""
    for h in party(world):
        if h.alive and getattr(h, "_acted", -1) != world.round and h is not world.player:
            return h
    return None


def revive_fallen(world):
    """After the fight, fallen heroes get back up (with a quarter of their life)."""
    lead = world.player
    for h in party(world):
        if h.alive:
            continue
        h.alive = True
        h.hp = max(1, h.max_hp // FALLEN_LIFE)
        spot = h.pos if world.grid.walkable(*h.pos) and h.pos not in world.occupied(h) else \
            world._free_cell_near(lead.pos, 4)
        if spot:
            h.x, h.y = spot
        if h is not lead:
            _as_follower(world, h)
        world.emit("resurrect", h)
        world.log("%s gets back up." % h.name, (200, 200, 120))


def carry(old, new):
    """The party moves with you to another level (the followers go with the allies)."""
    new.party = getattr(old, "party", None)
    for h in new.party or ():
        h.aura_source = new.aura_stats


def _diff(world):
    return getattr(getattr(world, "content", None), "difficulty", "normal") or "normal"


def damage_mult(world, unit, source):
    """Monster damage to the party (heroes, minions) on this difficulty."""
    if source is None or getattr(source, "ally", False) or getattr(source, "is_player", False):
        return 1.0
    if not (getattr(unit, "is_player", False) or getattr(unit, "ally", False)):
        return 1.0
    return DIFF_DMG.get(_diff(world), 1.0)


def scale_monster(m, world=None):
    """A monster joining a fight in tactics mode: more life (once) - by the difficulty."""
    if getattr(m, "_tscaled", False) or getattr(m, "ally", False) or getattr(m, "ai", "") == "npc":
        return
    m._tscaled = True
    frac = m.hp / float(max(1, m.max_hp))
    m.max_hp = int(m.max_hp * (DIFF_HP.get(_diff(world), HP_MULT) if world is not None else HP_MULT))
    m.hp = max(1, int(m.max_hp * frac))


# ------------------------------------------------------------------ who monsters go for
FAST_AP = 8          # D2 velocity 5+ (Fallen, dolls, skeletons, Act 2 huntresses, leapers...)


def pick_target(world, m):
    """Tactics targeting, decided once per monster per round:
    * fast melee monsters (Fallen, dolls, skeletons, Act 2 huntresses...) spread themselves over
      the party - every hero they can reach is as likely as any other, so the back line is not
      singled out and the front line is not ignored;
    * ranged monsters and casters: half the time the nearest, half the time any hero in range.
    Everyone else (and when nothing fits): the nearest, as before (None)."""
    memo = getattr(m, "_tpick", None)
    if memo and memo[0] == world.round and (memo[1] is None or memo[1].alive):
        return memo[1]
    pick = None
    heroes = [h for h in living(world) if not getattr(h, "invisible", False)]
    ranged = m.ai in ("ranged", "shaman") or getattr(m, "caster", False) or getattr(m, "range", 1) > 1
    if heroes and not getattr(m, "stationary", False):
        rng = getattr(world, "rng", None)
        roll = rng.random() if rng is not None else __import__("random").random()
        if ranged:
            if roll < 0.5:
                reach = getattr(m, "range", 6) + 6
                near = [h for h in heroes if world.udist(m, h) <= reach]
                if near:
                    pick = near[int(roll * 2 * len(near)) % len(near)]
        elif getattr(m, "max_ap", 0) >= FAST_AP:
            # a fast monster can reach anyone, so it picks evenly: one hero in three, not the squishiest
            reach = [h for h in heroes if world.udist(m, h) <= m.max_ap * 2 + 4]
            if reach:
                pick = reach[int(roll * len(reach)) % len(reach)]
    m._tpick = (world.round, pick)
    return pick


# ------------------------------------------------------------------ curated packs
SUPPORT_AIS = {"FallenShaman", "FetishShaman", "GreaterMummy", "ZakarumPriest", "Shaman", "Unraveler"}


def role_of(t):
    """What a monster does in a fight: support (heals / raises / curses), ranged, brute, melee."""
    kinds = set()
    from .monskills import SKILLS
    for name, _lvl in t.get("skills") or []:
        if name in SKILLS:
            kinds.add(SKILLS[name][0])
    if t.get("ai") == "shaman" or t.get("d2ai") in SUPPORT_AIS or kinds & {"heal", "summon", "curse"}:
        return "support"
    if t.get("ai") == "ranged" or t.get("caster"):
        return "ranged"
    if t.get("size", 2) >= 3:
        return "brute"
    return "melee"


def pack_plan(templates, mid, rng, depth):
    """The members of one tactics pack (monster ids), built around `mid` from the area's own
    monsters: a front line, something at range, sometimes a support, 4-8 in all."""
    by_role = {}
    for r, t in templates.items():
        by_role.setdefault(role_of(t), []).append(r)
    role = role_of(templates[mid])
    out = []
    front = [mid] if role in ("melee", "brute") else (by_role.get("melee") or by_role.get("brute") or [mid])[:1]
    n_front = 3 + (1 if depth >= 2 else 0) + (1 if depth >= 3 else 0) + (1 if rng.random() < 0.4 else 0)
    if role == "brute":
        n_front = max(1, n_front - 2)           # a brute is worth two
    out += [front[0]] * n_front
    ranged = [mid] if role == "ranged" else by_role.get("ranged")
    if ranged:
        out += [ranged[0] if ranged[0] == mid else rng.choice(ranged)] * (1 + (1 if rng.random() < 0.5 else 0))
    sup = [mid] if role == "support" else by_role.get("support")
    if sup and (role == "support" or rng.random() < 0.5):
        out.append(sup[0] if sup[0] == mid else rng.choice(sup))
    return out[:8]


SHAMANS = {"FallenShaman", "FetishShaman"}


def guard_shamans(members, templates, content):
    """A shaman (Fallen / Fetish Shaman) never stands alone: at least 3 of its own kind of minion
    (the Fallen it raises) guard it."""
    out = list(members)
    for r in set(members):
        t = templates.get(r)
        if t is None or not (t.get("ai") == "shaman" or t.get("d2ai") in SHAMANS):
            continue
        mn = t.get("minion") or ""
        if not mn or content is None or mn not in content.monstats:
            continue
        have = sum(1 for x in out if x == mn)
        out += [mn] * max(0, 3 * out.count(r) - have)
    return out


def populate_pack(world, centre, roster, weights, lvl, taken, depth=1):
    """One curated tactics pack at `centre` (called by the level populator in tactics mode)."""
    from .actworld import _template, _scatter, _spawn, is_nest
    from . import monmods
    rng = world.rng
    templates = {}
    for r in roster:
        if is_nest(r):
            continue
        t = _template(world, r, lvl)
        if t is not None and not t.get("stationary"):
            templates[r] = t
    if not templates:
        return
    pool = [r for r in roster if r in templates]
    wts = [weights[roster.index(r)] for r in pool]
    mid = rng.choices(pool, weights=wts)[0]
    members = guard_shamans(pack_plan(templates, mid, rng, depth), templates, world.content)
    roll = rng.random()
    spots = _scatter(world, centre, len(members), taken, radius=4 + len(members) // 2)
    units = []
    for m, cell in zip(members, spots):
        u = _spawn(world, m, cell, lvl, taken)
        if u is not None:
            units.append(u)
    if not units:
        return
    world.__dict__.setdefault("_tpacks", []).append(units)
    # the special ones: a unique leading the pack (with an aura for its minions), or a champion
    if roll < 0.12:
        boss = units[0]
        monmods.make_unique(world, boss)
        for u in units[1:]:
            u.minion_of = boss
            u.color_shift = getattr(boss, "color_shift", 0)
            monmods.pass_aura(boss, u)
    elif roll < 0.42:
        kinds = [monmods.CHAMPION, monmods.BERSERK, monmods.FANATIC, monmods.GHOSTLY]
        monmods.make_champion(world, rng.choice(units), rng.choice(kinds))


# ------------------------------------------------------------------ tactics rules
YELLOW = (240, 220, 90)


def _hero(u):
    return getattr(u, "is_player", False)


def combo_bonus(world, attacker, target, kind):
    """Combo states (tactics mode): % extra damage for this hit, and what it was.
    kind: "phys" for weapon hits, else the element."""
    if not ACTIVE or target is None or not target.alive:
        return 0, None
    eff = getattr(target, "effects", None) or {}
    pct, why = 0, None
    if eff.get("freeze") and kind in ("phys", "fire"):
        pct, why = 50, "Shatter!"                        # a frozen target breaks
        eff.pop("freeze", None)
    elif eff.get("poison") and kind == "fire":
        per, turns = eff["poison"]
        eff.pop("poison", None)                          # the poison flares up all at once
        world._damage(target, per * turns, attacker)
        why = "Ignite!"
    if _hero(attacker) and not _hero(target) and kind == "phys" and len(getattr(world, "party", None) or []) > 1:
        # flanking: two or more heroes next to the target
        near = [h for h in party(world) if h.alive and max(abs(h.x - target.x), abs(h.y - target.y)) <= 1]
        if len(near) >= 2:
            pct += 20                                     # (flanked: quietly, every hit)
    return pct, why


def stunned_discount(target):
    """Attacks on a stunned / knocked-down target cost 1 AP less and always hit (tactics)."""
    eff = getattr(target, "effects", None) or {}
    return ACTIVE and bool(eff.get("stun") or eff.get("freeze"))


def knock_collide(world, src_unit, target, dest):
    """A knockback the ground doesn't allow (tactics): slammed into a wall or another body: damage
    and a stun; pushed into lava: small monsters burn up; into water: stuck for a turn."""
    if not ACTIVE or not target.alive:
        return
    g = world.grid
    lava = getattr(g, "lava", None)
    if lava and dest in lava and not getattr(target, "unique", False) and not getattr(target, "boss", None) \
            and not _hero(target):
        world.log("%s is pushed into the lava!" % target.name, YELLOW)
        world._damage(target, target.hp + 1, src_unit)
        return
    if dest in getattr(g, "water", ()):
        target.effects["stun"] = max(target.effects.get("stun", 0), 1)
        world.log("%s stumbles into the water." % target.name, YELLOW)
        return
    dmg = max(1, target.max_hp // 10)
    world._damage(target, dmg, src_unit)
    if target.alive:
        target.effects["stun"] = max(target.effects.get("stun", 0), 1)
    world.log("%s is slammed into %s! (stunned)" % (target.name, "a wall" if not g.walkable(*dest) else "another"),
              YELLOW)


def opportunity(world, mover, frm, to):
    """Attacks of opportunity (tactics): stepping away from an enemy next to you gives it a free
    blow (once per round each). Melee units only; stunned, frozen or chilled ones can't."""
    if not ACTIVE or world.mode != "combat" or not mover.alive:
        return
    if _hero(mover) or getattr(mover, "ally", False):
        foes = [m for m in world.living_monsters() if m.aware and m.ai != "npc"]
    else:
        foes = [h for h in party(world) if h.alive] + [a for a in world.allies() if not _hero(a)
                                                     and a.ai not in ("turret", "wall")]
    for f in foes:
        if f is mover or not f.alive:
            continue
        if max(abs(f.x - frm[0]), abs(f.y - frm[1])) != 1 or max(abs(f.x - to[0]), abs(f.y - to[1])) <= 1:
            continue
        if getattr(f, "range", 1) > 1 and not _hero(f):
            continue
        eff = getattr(f, "effects", None) or {}
        if eff.get("stun") or eff.get("freeze") or eff.get("chill") or getattr(f, "stationary", False):
            continue
        if _hero(f) and getattr(f, "range", 1) > 1:
            continue                              # (bows, javelins thrown and spells don't)
        if getattr(f, "_aoo_round", -1) == world.round:
            continue
        f._aoo_round = world.round
        mover_was = (mover.x, mover.y)
        mover.x, mover.y = frm                    # the blow lands as you leave
        world.log("%s strikes %s as they leave!" % (f.name, mover.name), YELLOW)
        try:
            world._resolve_attack(f, mover)
        finally:
            if mover.alive:
                mover.x, mover.y = mover_was
        if not mover.alive:
            return


def threatened(world, cell, mover):
    """Cells next to an enemy who could hit you as you leave (for the move preview)."""
    return any(m.aware and getattr(m, "range", 1) <= 1 and max(abs(m.x - cell[0]), abs(m.y - cell[1])) <= 1
               for m in world.living_monsters())

# melee skills that knock the target back a tile in tactics mode (D2's own Bash and Smite already do)
PUSHERS = {"Bash", "Smite", "Charge", "Leap Attack", "Concentrate", "Maul", "Dragon Tail"}
