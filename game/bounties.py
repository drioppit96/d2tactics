"""The Tree of Inifuss: bounties, the thing Act 6 is for.

Diablo's story ends when Baal falls. Sanctuary is where this game carries on, and the
Tree is what it carries on with: a board of six contracts against the world below, refreshed for
gold, three of them in hand at a time.

    board(world)            the six offers, made the first time you look and kept after
    accept(world, bid)      take one (three at once, no more)
    abandon(world, bid)     give one up, its slot comes free
    reroll(world)           pay to replace every offer you have not taken
    on_killed(world, unit)  count a kill towards whatever is in hand
    claim(world, bid)       hand in a finished one and take the reward

A bounty lives on the hero (p.bounties, p.bounty_board), so it keeps across levels and saves and
each hero carries his own. Everything is per difficulty: stepping up to Nightmare wipes the board
and whatever was in hand, because the contracts were written against the world you have left.
"""
from .acts import ACT_RANGES, TOWN_IDS, SUMMIT

MAX_HELD = 3            # contracts in hand at once
BOARD_SIZE = 8          # offers on the Tree: two rows of four
REROLL_BASE = 2000      # gold for the first reroll of a board; it doubles each time
COLOR = (199, 179, 119)
GREY = (150, 145, 135)

#: what a contract can ask for
CULL = "cull"           # kill N of a kind, anywhere
HUNT = "hunt"           # kill a unique or champion in one area
CLEAR = "clear"         # leave one area with nothing alive on it
BOSS = "boss"           # kill one of the act bosses

#: the act bosses worth a contract, by the boss tag game/actworld.py gives them
BOSSES = [("andariel", "Andariel"), ("duriel", "Duriel"), ("mephisto", "Mephisto"),
          ("diablo", "Diablo"), ("shenk", "Shenk the Overseer"), ("nihlathak", "Nihlathak"),
          ("countess", "The Countess"), ("summoner", "The Summoner"), ("blood_raven", "Blood Raven")]

#: the carved plaques the board shows, by what the contract is against
ICON_BY_KIND = {CULL: "skulls", HUNT: "gargoyle", CLEAR: "trident", BOSS: "horned_skull"}
#: a contract against one of these families gets its own plaque instead
ICON_BY_FAMILY = {"zombie": "undead", "skeleton": "undead", "returned": "undead",
                  "burningdead": "undead", "corpsefire": "undead", "skmage": "undead",
                  "wraith": "undead", "ghost": "undead", "mummy": "undead",
                  "fallen": "demon", "fallenshaman": "demon", "imp": "demon",
                  "gargoyle": "gargoyle", "goatman": "demon", "demon": "demon",
                  "megademon": "demon", "vampire": "winged_skull", "doomknight": "winged_skull"}
ICONS = ("demon", "undead", "eye", "horned_skull", "trident", "skulls", "coin",
         "gargoyle", "gauntlet", "winged_skull", "serpent")

#: reward weight by kind - a contract that takes longer pays more
WEIGHT = {CULL: 1.0, HUNT: 1.4, CLEAR: 1.8, BOSS: 2.2}

DIFF_MULT = {"normal": 1.0, "nightmare": 2.4, "hell": 5.0}


# ---------------------------------------------------------------- the hero's own state
def init(p):
    if not hasattr(p, "bounties"):
        p.bounties = []
    if not hasattr(p, "bounty_board"):
        p.bounty_board = None
    if not hasattr(p, "bounty_done"):
        p.bounty_done = 0


def _difficulty(world):
    return (getattr(getattr(world, "content", None), "difficulty", "normal") or "normal").lower()


def _wipe_if_stale(world):
    """A board written for Normal means nothing in Nightmare."""
    p = world.player
    init(p)
    diff = _difficulty(world)
    b = p.bounty_board
    if b is not None and b.get("diff") != diff:
        p.bounty_board = None
        p.bounties = [x for x in p.bounties if x.get("diff") == diff]


# ---------------------------------------------------------------- making the offers
def _areas(world):
    """Levels a contract may name: somewhere this hero has been, that is not a town."""
    p = world.player
    seen = [l for l in sorted(getattr(p, "visited", ()) or ())
            if isinstance(l, int) and l not in TOWN_IDS and l != SUMMIT]
    return seen or [2]


def _level_name(world, lid):
    info = getattr(world, "info", None)
    try:
        return info.name(lid) or ("Level %d" % lid)
    except Exception:
        return "Level %d" % lid


def _monster_name(world, mid):
    c = getattr(world, "content", None)
    try:
        row = c.monstats.get(mid) or {}
        key = row.get("namestr") or mid
        return c.strings.get(key, key)
    except Exception:
        return str(mid)


def _roster(world, lid):
    try:
        return [m for m in (world.info.roster(lid) or []) if m]
    except Exception:
        return []


def _make_offer(world, rng, n, areas):
    diff = _difficulty(world)
    p = world.player
    kind = rng.choices([CULL, HUNT, CLEAR, BOSS], weights=[40, 30, 20, 10])[0]
    lid = rng.choice(areas)
    o = dict(id="b%d" % n, kind=kind, diff=diff, done=0, level=lid)
    if kind == BOSS:
        tag, title = rng.choice(BOSSES)
        o.update(target=tag, count=1, level=None,
                 title="Slay %s" % title,
                 text="%s still draws breath. End it." % title)
    elif kind == CLEAR:
        o.update(target=None, count=1,
                 title="Clear %s" % _level_name(world, lid),
                 text="Leave nothing alive in %s." % _level_name(world, lid))
    elif kind == HUNT:
        o.update(target=None, count=1,
                 title="Hunt in %s" % _level_name(world, lid),
                 text="A champion or a unique walks %s. Bring it down."
                      % _level_name(world, lid))
    else:
        roster = _roster(world, lid)
        mid = rng.choice(roster) if roster else "fallen1"
        count = rng.choice((8, 10, 12, 15))
        o.update(target=mid, count=count,
                 title="Cull the %s" % _monster_name(world, mid),
                 text="Kill %d %s, wherever you find them."
                      % (count, _monster_name(world, mid)))
    lvl = max(1, getattr(p, "level", 1))
    k = WEIGHT[kind] * DIFF_MULT.get(diff, 1.0)
    o["gold"] = int(600 * k + lvl * 90 * k)
    o["xp"] = int(p.xp_threshold(lvl) * 0.04 * k) if hasattr(p, "xp_threshold") else int(500 * k)
    o["ilvl"] = min(99, lvl + int(6 * WEIGHT[kind]))
    o["icon"] = ICON_BY_FAMILY.get(_family(o.get("target")), ICON_BY_KIND[kind])
    o["item"] = _roll_reward(world, o)      # rolled now, so the board can show what it pays
    return o


def _roll_reward(world, o):
    """The one item a contract pays, rolled when the contract is written and kept with it."""
    from .save import _item_dict
    c = getattr(world, "content", None)
    try:
        if c is not None and hasattr(c, "roll_drop"):
            drops = c.roll_drop(o["ilvl"], True, world.rng)
        else:
            from . import items
            drops = items.roll_drop(o["ilvl"], True, world.rng)
    except Exception:
        return None
    for it in (drops or []):
        if it is not None and getattr(it, "kind", "") != "gold":
            try:
                return _item_dict(it)
            except Exception:
                return None
    return None


def reward_item(world, o):
    """The contract's reward, rebuilt from what was stored with it (None if it pays only gold)."""
    d = o.get("item")
    if not d:
        return None
    from .save import _item_from
    try:
        return _item_from(d, getattr(world, "content", None))
    except Exception:
        return None


def _distinct(world, rng, n, areas, taken, tries=12):
    """An offer that is not already on the board: two 'Hunt in Cold Plains' read as a mistake."""
    o = _make_offer(world, rng, n, areas)
    for _ in range(tries):
        key = (o["kind"], o.get("level"), o.get("target"))
        if key not in taken:
            break
        o = _make_offer(world, rng, n, areas)
    taken.add((o["kind"], o.get("level"), o.get("target")))
    return o


def board(world):
    """The six offers on the Tree, made once and then kept until they are taken or rerolled."""
    _wipe_if_stale(world)
    p = world.player
    if p.bounty_board is None:
        rng = world.rng
        areas = _areas(world)
        taken = set()
        p.bounty_board = dict(diff=_difficulty(world), rerolls=0,
                              offers=[_distinct(world, rng, i, areas, taken) for i in range(BOARD_SIZE)])
    return p.bounty_board


def reroll_cost(world):
    b = board(world)
    return REROLL_BASE * (2 ** int(b.get("rerolls", 0)))


def reroll(world):
    p = world.player
    cost = reroll_cost(world)
    if p.gold < cost:
        world.log("The Tree wants %d gold for new contracts." % cost, GREY)
        return False
    b = board(world)
    p.gold -= cost
    rng = world.rng
    areas = _areas(world)
    held = {x["id"] for x in p.bounties}
    n = int(b.get("rerolls", 0)) * BOARD_SIZE + BOARD_SIZE
    taken = {(o["kind"], o.get("level"), o.get("target")) for o in b["offers"] if o["id"] in held}
    b["offers"] = [o if o["id"] in held else _distinct(world, rng, n + i, areas, taken)
                   for i, o in enumerate(b["offers"])]
    b["rerolls"] = int(b.get("rerolls", 0)) + 1
    world.log("The Tree's leaves turn. New contracts.", COLOR)
    return True


# ---------------------------------------------------------------- taking and giving up
def held(p):
    init(p)
    return p.bounties


def accept(world, bid):
    p = world.player
    b = board(world)
    if len(p.bounties) >= MAX_HELD:
        world.log("You can carry three contracts, no more.", GREY)
        return False
    o = next((x for x in b["offers"] if x["id"] == bid), None)
    if o is None or any(x["id"] == bid for x in p.bounties):
        return False
    p.bounties.append(dict(o))
    world.log("Contract taken: %s." % o["title"], COLOR)
    return True


def abandon(world, bid):
    p = world.player
    init(p)
    o = next((x for x in p.bounties if x["id"] == bid), None)
    if o is None:
        return False
    p.bounties.remove(o)
    world.log("Contract given up: %s." % o["title"], GREY)
    return True


def complete(o):
    return o.get("done", 0) >= o.get("count", 1)


# ---------------------------------------------------------------- counting the work
def _family(mid):
    """D2 numbers a monster's variants (fallen1..fallen5): one contract covers the whole family."""
    s = str(mid or "")
    return s.rstrip("0123456789") or s


def on_killed(world, unit):
    """A monster died somewhere: count it against whatever this hero is carrying."""
    p = getattr(world, "player", None)
    if p is None or unit is None:
        return
    init(p)
    if not p.bounties:
        return
    lid = getattr(world, "level_id", None)
    mid = str(getattr(unit, "d2id", "") or "")
    boss = getattr(unit, "boss", None)
    special = bool(getattr(unit, "unique", False) or getattr(unit, "champion", False))
    for o in p.bounties:
        if complete(o):
            continue
        k = o["kind"]
        if k == BOSS and boss and boss == o.get("target"):
            o["done"] = o["count"]
        elif k == CULL and _family(mid) and _family(mid) == _family(o.get("target")):
            o["done"] = min(o["count"], o.get("done", 0) + 1)
        elif k == HUNT and special and lid == o.get("level"):
            o["done"] = o["count"]
        elif k == CLEAR and lid == o.get("level"):
            alive = [m for m in world.monsters
                     if m.alive and m is not unit and not getattr(m, "is_player", False)
                     and not getattr(m, "npc", None) and not getattr(m, "ally", False)]
            if not alive:
                o["done"] = o["count"]
        if complete(o):
            world.log("Contract done: %s. The Tree is waiting." % o["title"], COLOR)


# ---------------------------------------------------------------- the reward
def claim(world, bid):
    p = world.player
    init(p)
    o = next((x for x in p.bounties if x["id"] == bid), None)
    if o is None or not complete(o):
        return False
    p.bounties.remove(o)
    b = p.bounty_board
    if b is not None:
        b["offers"] = [x for x in b["offers"] if x["id"] != bid]
        rng = world.rng
        while len(b["offers"]) < BOARD_SIZE:
            taken = {(x["kind"], x.get("level"), x.get("target")) for x in b["offers"]}
            b["offers"].append(_distinct(world, rng, 900 + len(b["offers"]) + p.bounty_done,
                                         _areas(world), taken))
    p.gold += o["gold"]
    if hasattr(p, "gain_xp"):
        p.gain_xp(o["xp"])
    p.bounty_done = int(getattr(p, "bounty_done", 0)) + 1
    world.log("%s: %d gold and %d experience." % (o["title"], o["gold"], o["xp"]), COLOR)
    _give_reward(world, o)
    return True


def _give_reward(world, o):
    """Hand over the item the contract was written with."""
    p = world.player
    it = reward_item(world, o)
    if it is None:
        return
    if p.inv_add(it):
        world.log("The Tree gives you %s." % getattr(it, "shown_name", it.name),
                  getattr(it, "color", COLOR))
    else:
        cell = world._drop_cell(p.pos)
        world.ground.setdefault(cell, []).append(it)
        world.emit("drop", cell, it)
