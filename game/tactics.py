"""Tactics mode: a party of up to three heroes, smaller and denser maps, curated stronger packs.

The hero you control is always world.player; the others walk with you as allies (in
world.monsters, like a hireling) and take their turn in combat one after another: End Turn hands
control to the next hero, and after the last one the monsters move.
"""
ACTIVE = False            # set when a tactics game starts (read by the map builders and the world)
HP_MULT = 2.5             # monsters as in a 4-player D2 game (/players 4: +150% life)
XP_MULT = 3.0             # fewer, tougher monsters and no hireling: more experience per kill
FALLEN_LIFE = 4           # a fallen hero gets up with 1/4 of their life when the fight is over


def on():
    return ACTIVE


def party(world):
    """The heroes of this game, in party order (the first is the leader)."""
    pt = getattr(world, "party", None)
    return list(pt) if pt else [world.player]


def living(world):
    return [h for h in party(world) if h.alive]


def _as_follower(world, hero):
    """A hero you are not controlling right now: walks with you and fights beside you."""
    hero.ally = True
    hero.party_member = True
    hero.ai = "party"
    hero.aware = False
    hero.life_turns = None
    hero.hireling = False
    hero.summon_skill = None
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


def scale_monster(m):
    """A monster joining a fight in tactics mode: 4-player life (once)."""
    if getattr(m, "_tscaled", False) or getattr(m, "ally", False) or getattr(m, "ai", "") == "npc":
        return
    m._tscaled = True
    frac = m.hp / float(max(1, m.max_hp))
    m.max_hp = int(m.max_hp * HP_MULT)
    m.hp = max(1, int(m.max_hp * frac))
