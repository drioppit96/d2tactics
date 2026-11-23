"""Skip Campaign: a hero who starts at the end of the story instead of the beginning.

Ticked on the new-character screen, this hands the hero everything the campaign would have
given: every quest finished, every waypoint, all three difficulties open, and a start in
Sanctuary. Three rewards are deliberately left standing so you can still choose what they land
on - Charsi's imbue, Larzuk's sockets and Anya's item - and two more are held by Sanctuary's
Tyrael until the hero is old enough to be worth the gift.

Each difficulty is its own run in D2, so this is applied again the first time a skipped hero
walks into Nightmare and into Hell (see save.switch_difficulty).
"""

#: left at "ready to claim" instead of finished, because you pick what they are spent on
READY = {
    "malus": "done",        # Tools of the Trade: handed in, so Charsi offers the imbue
    "shenk": "cleared",     # Siege on Harrogath: Larzuk still owes you the sockets
    "nihl": "cleared",      # Betrayal of Harrogath: Anya still owes you the item
}

#: what the point rewards of one run add up to: Den of Evil +1 skill, Radament's Book of Skill
#: +1, Izual +2, Lam Esen's Tome +5 stats. Larzuk's skill point is not here - it comes with the
#: sockets, when you go and ask him for them.
SKILL_POINTS = 4
STAT_POINTS = 5

#: Sanctuary's Tyrael holds Malah's Scroll of Resistance and Alkor's Potion of Life until this
#: level, one pair per difficulty
CLAIM_LEVEL = {"normal": 20, "nightmare": 40, "hell": 60}
CLAIMED = "tyrael_gift"           # in quest_stats, which is kept per difficulty

#: Malah's Scroll of Resistance and Alkor's Potion of Life, by their own codes
GIFTS = ("tr2", "xyz")


def _all_quest_ids():
    from . import quests, quests2, quests345
    ids = [q for q, _ in quests.ACT1] + [q for q, _ in quests2.ACT2]
    for lst in quests345.ACTS.values():
        ids += [q for q, _ in lst]
    return ids


def _all_waypoints():
    from .acts import WAYPOINTS
    out = set()
    for lst in WAYPOINTS.values():
        out.update(lst)
    return out


def quest_state():
    """Every quest of one run as a skipped hero finds it."""
    q = {qid: "done" for qid in _all_quest_ids()}
    q.update(READY)
    return q


def run_state():
    """The per-difficulty half of a skipped hero's save: quests, waypoints, the act."""
    wps = sorted(_all_waypoints())
    return dict(quests=quest_state(), waypoints=wps, visited=wps, cain=True, act=6,
                quest_stats={}, boss_kills=[], map_explored={}, tracked_quest=None,
                cairn_order=None, rift_depth=0)


def apply_to(player):
    """A newly made hero who skipped the campaign: the whole story behind them, all three
    difficulties open, standing in Sanctuary."""
    st = run_state()
    player.skip_campaign = True
    player.quests = dict(st["quests"])
    player.waypoints = set(st["waypoints"])
    player.visited = set(st["visited"])
    player.cain_rescued = True
    player.current_act = 6
    player.quest_stats = {}
    player.diff_unlocked = ["normal", "nightmare", "hell"]
    player.stat_points += STAT_POINTS
    player.skills.points += SKILL_POINTS


def fresh_run(data):
    """The state for a difficulty this skipped hero has not played yet, with its own rewards.

    D2 hands out the quest points again in every difficulty, and so does this.
    """
    d = run_state()
    d["stat_points"] = int(data.get("stat_points", 0) or 0) + STAT_POINTS
    d["skill_points"] = int(data.get("skill_points", 0) or 0) + SKILL_POINTS
    return d


def is_skipped(player):
    return bool(getattr(player, "skip_campaign", False))


def _difficulty(world):
    return getattr(world.player, "difficulty", None) or "normal"


def claimable(world):
    """True if Sanctuary's Tyrael is holding this difficulty's pair of gifts for you."""
    p = world.player
    if not is_skipped(p):
        return False
    diff = _difficulty(world)
    if (getattr(p, "quest_stats", None) or {}).get(CLAIMED):
        return False
    return p.level >= CLAIM_LEVEL.get(diff, 20)


def waiting_line(world):
    """What Tyrael says to a hero who is not old enough yet, or None."""
    p = world.player
    if not is_skipped(p) or (getattr(p, "quest_stats", None) or {}).get(CLAIMED):
        return None
    need = CLAIM_LEVEL.get(_difficulty(world), 20)
    if p.level >= need:
        return None
    return ("Tyrael: Two gifts of this world are in my keeping for you. Come back at level %d "
            "and they are yours." % need)


def claim(world):
    """Hand over the Scroll of Resistance and the Potion of Life, once per difficulty."""
    p = world.player
    if not claimable(world):
        return False
    from .quests2 import give_item
    given = []
    for code in GIFTS:
        it = give_item(world, code, quiet=True)
        if it is not None:
            given.append(it.name)
    if not given:
        world.log("Tyrael: 'I cannot find them. Strange.'", (170, 170, 170))
        return False
    st = p.__dict__.setdefault("quest_stats", {})
    st[CLAIMED] = 1
    world.log("Tyrael gives you %s. Read the one and drink the other." % " and ".join(given),
              (199, 179, 119))
    return True
