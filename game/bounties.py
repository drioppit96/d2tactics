"""The Tree of Inifuss: bounties, the thing Act 6 is for.

Diablo's story ends when Baal falls. Sanctuary is where this game carries on, and the
Tree is what it carries on with: a board of eight contracts against the world below, three of
them in hand at a time.

    board(world)            the eight offers, made the first time you look and kept after
    accept(world, bid)      take one (three at once, no more)
    on_killed(world, unit)  count a kill towards whatever is in hand
    claim(world, bid)       hand in a finished one and take the reward

A contract in hand keeps its plaque on the Tree for as long as it is held: nothing replaces it,
nothing finishes it by itself, and there is no giving it up. The one way it leaves your log is
handing it in at the Tree, finished.

A bounty lives on the hero (p.bounties, p.bounty_board), so it keeps across levels and saves and
each hero carries his own. Everything is per difficulty: stepping up to Nightmare wipes the board
and whatever was in hand, because the contracts were written against the world you have left.
"""
from .acts import ACT_RANGES, TOWN_IDS, SUMMIT

MAX_HELD = 3            # contracts in hand at once
REFRESH_AFTER = 3       # contracts handed in before the Tree writes its board again
BOARD_SIZE = 8          # offers on the Tree: two rows of four
BOARD_VERSION = 4       # bumped when the contracts themselves change: old boards are rewritten
#: a hero's contracts were cleared out once, when the kinds of contract changed for the last
#: Raising this clears every hero's board and hand once, the next time his contracts are read,
#: and the new number is written to his save so it never runs twice. Only raise it when the
#: contracts themselves change in a way _migrate cannot mend: a log full of work is lost here,
#: so a contract an older build wrote is normally brought up to date instead.
WIPE = 2
COLOR = (199, 179, 119)
GREY = (150, 145, 135)

#: what a contract can ask for
CULL = "cull"           # kill N of a whole kind of creature (demons, the dead...), anywhere
HUNT = "hunt"           # kill one named unique, by name
BOSS = "boss"           # kill one of the act bosses
ORGAN = "organ"         # deposit N body parts of one creature (game/organs.py)
GEM = "gem"             # deposit N perfect gems of one colour
RUNE = "rune"           # deposit N of one rune
RIFT = "rift"           # clear N floors of the rift, over as many runs as it takes

#: the three you hand in rather than hunt down
DEPOSIT = (ORGAN, GEM, RUNE)

#: the act bosses worth a contract, by the boss tag game/actworld.py gives them. The named
#: uniques that used to sit here are Hunt's business now.
BOSSES = [("andariel", "Andariel"), ("duriel", "Duriel"), ("mephisto", "Mephisto"),
          ("diablo", "Diablo")]

#: D2's named uniques and where each one stands. Every pair here was checked by building that
#: level and finding the monster on it, so a Hunt never sends you somewhere it is not.
NAMED = [("Bishibosh", 3), ("Rakanishu", 4), ("Treehead WoodFist", 5), ("Corpsefire", 8),
         ("Coldcrow", 9), ("Blood Raven", 17), ("The Countess", 25), ("The Smith", 28),
         ("Pitspawn Fouldog", 29), ("Bone Ash", 33), ("Griswold", 38),
         ("Beetleburst", 42), ("Dark Elder", 44), ("Radament", 49), ("Fangskin", 61),
         ("Coldworm the Burrower", 64), ("The Summoner", 74),
         # Act 3 (levels 75 to 102) is left out: its levels do not build reliably yet, and a
         # contract that sends you somewhere the game cannot open is worse than no contract.
         ("Izual", 105), ("Hephasto The Armorer", 107),
         ("Shenk the Overseer", 110), ("Dac Farren", 110), ("Eldritch the Rectifier", 111),
         ("Eyeback the Unleashed", 111), ("Frozenstein", 114), ("Pindleskin", 121),
         ("Nihlathak", 124)]

#: what a Cull asks for: the whole kind, not one family of it. D2's "human" class is townspeople
#: and hirelings almost to a man, so there is nothing in it to cull and it is not offered.
CLASSES = [("demon", "demons"), ("undead", "the walking dead"), ("beast", "beasts")]
CLASS_ICON = {"demon": "demon", "undead": "undead", "beast": "gargoyle"}

#: where each of them stands, so a contract against one can open a portal to it
BOSS_LEVEL = {"andariel": 37, "duriel": 73, "mephisto": 102, "diablo": 108}

#: the carved plaques the board shows, by what the contract is against
ICON_BY_KIND = {CULL: "skulls", HUNT: "skulls", BOSS: "horned_skull",
                ORGAN: "gauntlet", GEM: "eye", RUNE: "serpent", RIFT: "trident"}
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
#: a deposit asks you to give up something you could have used, so it pays better
#: what a contract is worth, before its size is taken into account. Hunt and Boss have no sizes
#: of their own - one named head is one named head - so they are weighted for the whole job
#: rather than for the smallest of three.
WEIGHT = {CULL: 1.0, HUNT: 2.2, BOSS: 3.2, ORGAN: 1.6, GEM: 2.6, RUNE: 3.0, RIFT: 2.0}

DIFF_MULT = {"normal": 1.0, "nightmare": 2.4, "hell": 5.0}


# ---------------------------------------------------------------- the hero's own state
def init(p):
    if not hasattr(p, "bounties"):
        p.bounties = []
    if not hasattr(p, "bounty_board"):
        p.bounty_board = None
    if not hasattr(p, "bounty_done"):
        p.bounty_done = 0
    if int(getattr(p, "bounty_wipe", 0) or 0) != WIPE:
        # the clear-out. It sits here, in the first thing every path calls, so it happens whether
        # the contracts are read by the quest log, the Tree or Sanctuary's pedestals
        p.bounty_wipe = WIPE
        p.bounties = []
        p.bounty_board = None


def party(world):
    """Everyone the contracts belong to. Bounties are the whole team's, not one hero's."""
    try:
        from . import tactics
        crowd = [h for h in (tactics.party(world) or []) if h is not None]
    except Exception:
        crowd = []
    pl = getattr(world, "player", None)
    if pl is not None and pl not in crowd:
        crowd.append(pl)
    for h in crowd:
        init(h)
    return crowd


def _mirror(world):
    """Give every hero the leader's board and hand, so the team sees and carries one set."""
    crowd = party(world)
    if len(crowd) < 2:
        return
    lead = world.player
    for h in crowd:
        if h is lead:
            continue
        h.bounty_board = lead.bounty_board
        h.bounties = lead.bounties
        h.bounty_done = lead.bounty_done


def _difficulty(world):
    return (getattr(getattr(world, "content", None), "difficulty", "normal") or "normal").lower()


#: contract kinds that still exist. A board is kept across saves, so one written by an older
#: build can be carrying a kind this one no longer has ("clear", which asked you to empty a
#: whole area): those are dropped rather than left on the Tree for ever.
KINDS = (CULL, HUNT, BOSS, ORGAN, GEM, RUNE, RIFT)


def _migrate(world, o):
    """Bring a contract written by an older build up to date, or return None to strike it off.

    Boss contracts used to name one boss in `target`; they now keep a list in `targets`, and
    one written the old way could never be finished because nothing was ever matched against
    it. Hunt contracts used to name a kind of monster, which Hunt no longer asks for at all,
    so those cannot be rescued and are dropped.
    """
    k = o.get("kind")
    if k == BOSS and not o.get("targets"):
        tag = o.get("target")
        if not tag or tag not in dict(BOSSES):
            return None
        o["targets"] = [tag]
        o["got"] = [g for g in (o.get("got") or []) if g in o["targets"]]
        o["count"] = 1
        o["done"] = len(o["got"])
        if o.get("level") is None:
            o["level"] = BOSS_LEVEL.get(tag)
    if k == HUNT and not o.get("targets"):
        return None
    if k in (BOSS, HUNT):
        o.setdefault("got", [])
    o.setdefault("tier", 1)
    o.setdefault("done", 0)
    o.setdefault("count", 1)
    if not o.get("icon"):
        o["icon"] = CLASS_ICON.get(o.get("mclass"), ICON_BY_KIND.get(k, "skulls"))
    if not o.get("item"):
        o["item"] = _roll_reward(world, o)
    return o


def _wipe_if_stale(world):
    """A board written for Normal means nothing in Nightmare, and a kind the game has dropped
    means nothing at all."""
    p = world.player
    init(p)
    party(world)             # everyone in the team, so each one's own fields are set up
    diff = _difficulty(world)
    b = p.bounty_board
    if b is not None and b.get("diff") != diff:
        p.bounty_board = None
        p.bounties = [x for x in p.bounties if x.get("diff") == diff]
        b = None
    kept = []
    for x in p.bounties:
        if x.get("kind") in KINDS and _migrate(world, x) is not None:
            kept.append(x)
    gone = len(p.bounties) - len(kept)
    if gone:
        p.bounties = kept
        world.log("%d contract%s the Tree no longer writes %s struck off." % (
            gone, "" if gone == 1 else "s", "was" if gone == 1 else "were"), GREY)
    if b is not None:
        ok = [o.get("kind") in KINDS and _migrate(world, o) is not None for o in b.get("offers", ())]
        if not all(ok):
            rng, areas, taken = world.rng, _areas(world), set()
            b["offers"] = [o if ok[i] else _distinct(world, rng, 800 + i, areas, taken)
                           for i, o in enumerate(b["offers"])]


# ---------------------------------------------------------------- making the offers
def _open_world(lid):
    """A level a contract may name: a real place in the world, not a town and not a rift floor.

    Rift floors are built fresh for each run, so a portal to one would open on a level that no
    longer exists by the time you walked through it.
    """
    if not isinstance(lid, int) or lid in TOWN_IDS or lid == SUMMIT:
        return False
    from . import arena
    if arena.is_arena(lid):
        return False                 # the Tree's own rooms are not places in the world
    try:
        from . import rift
        if rift.is_rift(lid):
            return False
    except Exception:
        pass
    try:
        from . import riftmap
        if getattr(riftmap, "is_rift", None) and riftmap.is_rift(lid):
            return False
    except Exception:
        pass
    return True


def _areas(world):
    """Levels a contract may name: somewhere this hero has been, out in the open world."""
    p = world.player
    seen = [l for l in sorted(getattr(p, "visited", ()) or ()) if _open_world(l)]
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


def _plural(name, n):
    """'3 Thul Runes', '5 Fallen Hearts' - the count reads first, so the name follows it."""
    if n == 1 or not name:
        return name
    if name.endswith("y") and name[-2:-1].lower() not in "aeiou":
        return name[:-1] + "ies"            # Perfect Ruby -> Perfect Rubies
    if name.endswith("s") and name.lower().endswith("bones"):
        return name                          # Bones is already plural
    return name + ("es" if name[-1] in "sxz" else "s")


#: most contracts come in three sizes. Tier 1 is an evening's work, tier 3 a project, and the
#: reward follows: the gold, the experience and the item level all scale with it. Hunt and Boss
#: are the exception: they name one target and have no sizes.
TIERS = (1, 2, 3)
TIER_NAME = {1: "", 2: "Greater ", 3: "Grand "}
TIER_PAY = {1: 1.0, 2: 2.2, 3: 4.0}

#: how much each kind asks for, by tier
AMOUNT = {CULL: (30, 60, 100), RIFT: (5, 10, 15), BOSS: (1, 1, 1), HUNT: (1, 1, 1),
          ORGAN: (10, 25, 50), GEM: (2, 4, 7), RUNE: (5, 3, 2)}

#: which runes a deposit asks for, by tier, as positions in D2's own list (1 El ... 33 Zod).
#: A bigger contract asks for fewer runes, but far better ones: five of El to Ral, three of Ort
#: to Io, or two of Lum to Ist.
RUNE_ASK = {1: (1, 8), 2: (9, 16), 3: (17, 24)}

#: which runes a reward can pay, by tier. The bands sit above what the same tier asks for, so a
#: rune contract always hands back something better than it took, and every other kind of
#: contract pays a rune worth keeping rather than the El that an even falloff would give.
RUNE_PAY = {1: (5, 12), 2: (11, 19), 3: (17, 26)}

#: how far above the rune it asked for a rune contract must pay, and how wide that band is.
#: D2's cube turns two or three of a rune into the next one up, so paying three to six places
#: above what it took is a clear profit on the trade without reaching the top of the list.
RUNE_STEP = 3
RUNE_SPAN = 3
RUNE_CAP = 30             # Ber: the Tree does not hand out the last three runes


def _make_offer(world, rng, n, areas):
    diff = _difficulty(world)
    p = world.player
    kind = rng.choices([CULL, HUNT, BOSS, ORGAN, GEM, RUNE, RIFT],
                       weights=[26, 18, 10, 20, 7, 7, 12])[0]
    # one head is one head: a hunt and a boss contract name one target and come in one size
    tier = 1 if kind in (HUNT, BOSS) else rng.choice(TIERS)
    want = AMOUNT[kind][tier - 1]
    lid = rng.choice(areas)
    o = dict(id="b%d" % n, kind=kind, diff=diff, done=0, level=lid, tier=tier)
    pre = TIER_NAME[tier]
    if kind == BOSS:
        tag, shown = rng.choice(BOSSES)
        o.update(targets=[tag], got=[], count=1, level=BOSS_LEVEL.get(tag),
                 title="Slay %s" % shown,
                 text="%s still draws breath. End it." % shown)
    elif kind == HUNT:
        who, where = rng.choice(NAMED)
        o.update(targets=[who], got=[], count=1, level=where,
                 title="Hunt %s" % who,
                 text="%s is in %s. Bring it down." % (who, _level_name(world, where)))
    elif kind == RIFT:
        o.update(target=None, count=want, level=None,
                 title="%sDelve the Rift" % pre,
                 text="Clear %d floors of the rift, however many runs it takes." % want)
    elif kind == ORGAN:
        from . import organs
        token = rng.choice(sorted(organs.ORGANS))
        nm = organs.label(token)
        o.update(target=organs.code_for(token), count=want, level=None, deposit=nm, organ=token,
                 title="%sDeposit %d %s" % (pre, want, nm),
                 text="Bring the Tree %d %s." % (want, nm))
    elif kind == GEM:
        code, nm = _perfect_gem(world, rng)
        o.update(target=code, count=want, level=None, deposit=nm,
                 title="%sDeposit %d %s" % (pre, want, _plural(nm, want)),
                 text="The Tree wants %d %s." % (want, _plural(nm, want)))
    elif kind == RUNE:
        code, nm, rank = _rune_pick(world, rng, *RUNE_ASK[tier])
        o.update(target=code, count=want, level=None, deposit=nm, rune_rank=rank,
                 title="%sDeposit %d %s" % (pre, want, _plural(nm, want)),
                 text="The Tree wants %d %s." % (want, _plural(nm, want)))
    else:
        cls, shown = rng.choice(CLASSES)
        o.update(target=cls, count=want, level=None, mclass=cls,
                 title="%sCull %s" % (pre, shown),
                 text="Kill %d of %s, wherever in the world you find them." % (want, shown))
    lvl = max(1, getattr(p, "level", 1))
    k = WEIGHT[kind] * DIFF_MULT.get(diff, 1.0) * TIER_PAY[tier]
    o["gold"] = int(600 * k + lvl * 90 * k)
    o["xp"] = int(p.xp_threshold(lvl) * 0.04 * k) if hasattr(p, "xp_threshold") else int(500 * k)
    o["ilvl"] = min(99, lvl + int(6 * WEIGHT[kind] * TIER_PAY[tier]))
    if kind == CULL:
        o["icon"] = CLASS_ICON.get(o.get("mclass"), "skulls")
    elif kind == ORGAN:
        o["icon"] = "gauntlet"
    else:
        o["icon"] = ICON_BY_KIND[kind]
    o["item"] = _roll_reward(world, o)      # the base only: what it turns out to be waits
    return o


#: what a contract's item roll can turn into, over and above the ordinary boss drop
SET_CHANCE = 0.03         # a set item
UNIQUE_CHANCE = 0.03      # a unique
GEM_CHANCE = 0.05         # a perfect gem
RUNE_CHANCE = 0.05        # a rune, the high ones far less often


def _gem_bases(world, grade=4):
    c = getattr(world, "content", None)
    return [b for b in (getattr(c, "bases", None) or [])
            if b.get("gem") and b["gem"][0] == "gem" and b["gem"][2] == grade]


def _perfect_gem(world, rng):
    """A perfect gem base: (code, its name)."""
    gems = _gem_bases(world)
    if not gems:
        return "gpr", "Perfect Ruby"
    b = rng.choice(gems)
    return b["code"], b.get("name") or b["code"]


def _rune_pick(world, rng, lo=1, hi=33):
    """One rune out of a band of D2's list, the higher end of the band the rarer.

    Returns (code, name, rank). A band keeps a reward honest: without one an even falloff over
    all thirty-three runes hands out El almost every time, which is no reward at all.
    """
    c = getattr(world, "content", None)
    by = getattr(c, "base_by_code", None) or {}
    lo, hi = max(1, int(lo)), min(33, int(hi))
    if hi < lo:
        hi = lo
    runes = [("r%02d" % n, n) for n in range(lo, hi + 1) if "r%02d" % n in by]
    if not runes:
        runes = [("r%02d" % n, n) for n in range(1, 34) if "r%02d" % n in by]
    if not runes:
        return "r01", "El Rune", 1
    weights = [0.82 ** (n - runes[0][1]) for _, n in runes]
    code, n = rng.choices(runes, weights=weights)[0]
    b = by.get(code) or {}
    return code, (b.get("name") or code), n


def _make_code(world, code, ilvl, rng):
    c = getattr(world, "content", None)
    b = (getattr(c, "base_by_code", None) or {}).get(code)
    if b is None:
        return None
    try:
        return c.make_item(b, ilvl, rng)
    except Exception:
        return None


def _roll_reward(world, o):
    """The item a contract will pay, chosen when the contract is written - but only the item, not
    what it will turn out to be.

    The board shows it plain and white, and claiming it hands over that same base - never another
    one. How good it turns out to be is settled here too, out of sight, because a base that is
    going to be a set piece or a unique has to be one that has such a piece at all; the board
    simply does not say which it will be until the work is handed in (claim_item below). One
    reward in ten is a perfect gem or a rune, and those are what they are either way.

    A contract that asked for gems or runes never pays in gems: it pays a rune, and a rune well
    above the one it took, because handing over three runes for a gem is no trade at all.
    """
    from .save import _item_dict
    c = getattr(world, "content", None)
    rng = world.rng
    ilvl = o["ilvl"]
    tier = int(o.get("tier", 1) or 1)
    kind = o.get("kind")
    lo, hi = RUNE_PAY.get(tier, RUNE_PAY[1])
    hi = min(RUNE_CAP, hi)
    if kind == RUNE:
        lo = min(RUNE_CAP, max(lo, int(o.get("rune_rank", 0) or 0) + RUNE_STEP))
        hi = min(RUNE_CAP, max(hi, lo + RUNE_SPAN))
    hoard = kind in (GEM, RUNE)
    r = rng.random()
    if r < GEM_CHANCE and not hoard:
        code, _nm = _perfect_gem(world, rng)
        it = _make_code(world, code, ilvl, rng)
    elif r < (RUNE_CHANCE * 3 if hoard else GEM_CHANCE + RUNE_CHANCE):
        code, _nm, _rank = _rune_pick(world, rng, lo, hi)
        it = _make_code(world, code, ilvl, rng)
    else:
        quality = _roll_quality(rng, tier)
        it = _base_for(c, ilvl, rng, quality)
        if it is not None:
            o["quality"] = quality
    if it is None:
        return None
    it.identified = True
    try:
        return _item_dict(it)
    except Exception:
        return None


def _roll_quality(rng, tier):
    """Magic, rare, set or unique, at the odds this contract's size earns."""
    odds = TIER_RARITY.get(int(tier or 1), TIER_RARITY[1])
    r = rng.random()
    for q in ("unique", "set", "rare"):
        if r < odds[q]:
            return q
        r -= odds[q]
    return "magic"


def _base_for(c, ilvl, rng, quality):
    """A base the contract can show, white, and still pay at `quality` when it is handed in.

    Most bases have no set piece or unique of their own, so one that is going to be either has
    to be drawn until it is one that has one. Whatever comes out is what the board shows and
    what the Tree hands over: only how good it is was decided here.
    """
    if c is None:
        return None

    def draw(q):
        try:
            b = c.pick_base(max(1, ilvl), rng)
            if b is None:
                return None, None
            made = c.make_item(b, ilvl, rng, q)
            return (b, made) if made is not None and getattr(made, "rarity", "") == q else (b, None)
        except Exception:
            return None, None

    tries = 24 if quality in ("unique", "set") else 1
    first = None
    for _ in range(tries):
        b, made = draw(quality)
        if first is None and b is not None:
            first = b
        if made is not None:
            try:
                return c.make_item(b, ilvl, rng, "normal")      # the board shows it plain
            except Exception:
                return None
    if first is None:
        return None
    try:
        return c.make_item(first, ilvl, rng, "normal")
    except Exception:
        return None


#: what a contract pays out at, by tier. A bigger contract is not only more gold: it is a better
#: roll. Everything these do not claim is magic, so the extra rares, sets and uniques come
#: straight out of the magic share and nothing else is touched.
#: These are shares of the item roll, and one reward in ten is a gem or a rune before it gets
#: here, so they are set a tenth high to land where they are meant to: 3% of all rewards at
#: tier 1, not 3% of the nine in ten that reach this.
TIER_RARITY = {1: {"unique": 0.034, "set": 0.034, "rare": 0.190},
               2: {"unique": 0.068, "set": 0.068, "rare": 0.290},
               3: {"unique": 0.115, "set": 0.115, "rare": 0.400}}


def claim_item(world, o):
    """What the contract actually pays, decided now that the work is done.

    The base and how good it is were both fixed when the contract was written; this is where the
    item is actually made, out of that base and nothing else. A gem or a rune is already what it
    is and passes through.
    """
    c = getattr(world, "content", None)
    d = o.get("item")
    if not d or c is None:
        return reward_item(world, o)
    rng = world.rng
    code = d.get("code")
    base = (getattr(c, "base_by_code", None) or {}).get(code)
    if base is None or base.get("gem"):
        it = reward_item(world, o)          # gems and runes are already decided
        if it is not None:
            it.identified = True
        return it
    ilvl = o.get("ilvl") or 1
    want = o.get("quality") or "magic"
    it = None
    # the base is the one the board showed and does not change here. If it turns out to have no
    # piece of the kind that was rolled for it, it steps down a rung rather than becoming some
    # other item: what was promised is what is handed over
    ladder = ("unique", "set", "rare", "magic")
    for q in ladder[ladder.index(want) if want in ladder else len(ladder) - 1:]:
        try:
            cand = c.make_item(base, ilvl, rng, q)
        except Exception:
            cand = None
        if cand is not None:
            it = cand
            break
    if it is None:
        it = reward_item(world, o)
    if it is not None:
        it.identified = True                          # the Tree hands nothing over unread
    return it


def reward_item(world, o):
    """The contract's reward as the board shows it: the base, plain and unrolled."""
    d = o.get("item")
    if not d:
        return None
    from .save import _item_from
    try:
        it = _item_from(d, getattr(world, "content", None))
        if it is not None:
            it.identified = True
            it.rarity = "normal"        # the board shows the base, plain and white: nothing is decided
        return it
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
    """The eight offers on the Tree, made the first time you look and kept after."""
    _wipe_if_stale(world)
    p = world.player
    b = p.bounty_board
    if b is not None and int(b.get("version", 0)) != BOARD_VERSION:
        # the contracts themselves have changed since this board was written: start again, but
        # leave anything already in hand alone, because the work behind it was real
        b = p.bounty_board = None
    if b is None:
        rng = world.rng
        areas = _areas(world)
        taken = set()
        p.bounty_board = dict(diff=_difficulty(world), version=BOARD_VERSION,
                              offers=[_distinct(world, rng, i, areas, taken) for i in range(BOARD_SIZE)])
    _graft_held(world)
    _mirror(world)
    return p.bounty_board


def _graft_held(world):
    """Make sure everything in hand has a plaque on the Tree.

    The panel's buttons work on the contract the plaque belongs to, so a contract held but no
    longer on the board - one carried through a rewrite of the board, or left behind by an older
    build - could be neither handed in nor claimed. Anything in hand that has no plaque takes
    the place of one that is not.
    """
    p = world.player
    b = p.bounty_board
    if not b:
        return
    offers = b.get("offers") or []
    shown = {o.get("id") for o in offers}
    orphans = [x for x in p.bounties if x.get("id") not in shown]
    if not orphans:
        return
    free = [i for i, o in enumerate(offers) if o.get("id") not in {x["id"] for x in p.bounties}]
    for x in orphans:
        if free:
            offers[free.pop(0)] = x
        else:
            offers.append(x)
    b["offers"] = offers


# ---------------------------------------------------------------- taking and giving up
def _sync_portals(world):
    """Sanctuary's three pedestals follow what is in hand (game/act6.py)."""
    try:
        from . import act6
        act6.bounty_portals(world)
    except Exception:
        pass


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
    for h in party(world):
        if not any(x["id"] == bid for x in h.bounties):
            h.bounties.append(dict(o))
    _mirror(world)
    world.log("Contract taken: %s." % o["title"], COLOR)
    _sync_portals(world)
    return True


def held_count(player, o):
    """How much of a deposit contract the hero is actually carrying."""
    from . import organs
    code = o.get("target")
    if o["kind"] == ORGAN:
        return organs.count(player, code)
    n = 0
    for it in (player.inventory or []):
        if getattr(it, "code", None) == code and getattr(it, "gem", None):
            n += max(1, getattr(it, "quantity", 1) or 1)
    st = getattr(player, "stash", None)
    if st is not None:
        n += int((getattr(st, "bank", None) or {}).get(code, 0))
    return n


def progress(player, o):
    """Where a contract stands: kills are counted as they happen, deposits are counted now."""
    if o["kind"] in DEPOSIT:
        return min(o.get("count", 1), held_count(player, o))
    return o.get("done", 0)


def destination(o):
    """The level a contract sends you to, or None for one you settle at the Tree.

    A deposit is handed in at the Tree and opens nothing, and nothing ever opens onto a rift.
    """
    if o.get("kind") in DEPOSIT:
        return None
    lvl = o.get("level")
    return lvl if _open_world(lvl) else None


def complete(o, player=None):
    if player is not None and o["kind"] in DEPOSIT:
        return held_count(player, o) >= o.get("count", 1)
    return o.get("done", 0) >= o.get("count", 1)


# ---------------------------------------------------------------- counting the work
#: MonType.txt is a tree - "skeleton" is a "lowundead" is an "undead". This walks it to the root
#: and sorts what comes out into the four kinds a Cull can ask for.
_CLASS_ROOT = {"demon": "demon", "undead": "undead", "human": "human"}


def _montype_tree(world):
    c = getattr(world, "content", None)
    cache = getattr(c, "_montype_equiv", None)
    if cache is None:
        cache = {}
        try:
            from d2.source import read_table
            for r in read_table(c.src, "MonType"):
                t = (r.get("type") or "").strip().lower()
                if t:
                    cache[t] = (r.get("equiv1") or "").strip().lower()
        except Exception:
            cache = {}
        try:
            c._montype_equiv = cache
        except Exception:
            pass
    return cache


def mon_class(world, mid):
    """Which of the four kinds a monster belongs to: demon, undead, human or beast."""
    c = getattr(world, "content", None)
    if c is None or not mid:
        return None
    row = (getattr(c, "monstats", None) or {}).get(mid) or {}
    t = (row.get("montype") or "").strip().lower()
    if not t:
        return None
    equiv = _montype_tree(world)
    seen = set()
    while t and t not in seen:
        if t in _CLASS_ROOT:
            return _CLASS_ROOT[t]
        seen.add(t)
        t = equiv.get(t) or ""
    return "beast"          # insects, constructs and everything with no kin named above


def _family(mid):
    """D2 numbers a monster's variants (fallen1..fallen5): one contract covers the whole family."""
    s = str(mid or "")
    return s.rstrip("0123456789") or s


def on_killed(world, unit):
    """A monster died somewhere: count it against the team's contracts."""
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
    name = (getattr(unit, "name", "") or "").lower()
    for o in p.bounties:
        if complete(o):
            continue
        k = o["kind"]
        wants = o.get("targets") or ([o["target"]] if o.get("target") else [])
        if k == BOSS and boss and boss in wants:
            got = o.setdefault("got", [])
            if boss not in got:
                got.append(boss)
                o["done"] = len(got)
                o["count"] = max(o.get("count", 1), len(wants))
        elif k == CULL and o.get("mclass") and mon_class(world, mid) == o["mclass"]:
            o["done"] = min(o["count"], o.get("done", 0) + 1)
        elif k == HUNT and special:
            got = o.setdefault("got", [])
            for want in wants:
                if want.lower() == name and want not in got:
                    got.append(want)
                    o["done"] = len(got)
        if complete(o):
            world.log("Contract done: %s. The Tree is waiting." % o["title"], COLOR)
    _mirror(world)


def on_rift_floor(world):
    """A rift floor was cleared: every Delve contract in hand counts it."""
    p = getattr(world, "player", None)
    if p is None:
        return
    init(p)
    for o in p.bounties:
        if o.get("kind") != RIFT or complete(o):
            continue
        o["done"] = min(o["count"], o.get("done", 0) + 1)
        if complete(o):
            world.log("Contract done: %s. The Tree is waiting." % o["title"], COLOR)
        else:
            world.log("%s: %d of %d floors." % (o["title"], o["done"], o["count"]), COLOR)
    _mirror(world)


def _spend_deposit(player, o):
    """Hand the goods over: the Tree keeps them."""
    from . import organs
    code, want = o.get("target"), o.get("count", 1)
    if o["kind"] == ORGAN:
        return organs.take(player, code, want)
    left = want
    for it in list(player.inventory or []):
        if left <= 0:
            break
        if getattr(it, "code", None) == code and getattr(it, "gem", None):
            player.inventory.remove(it)
            left -= 1
    st = getattr(player, "stash", None)
    bank = getattr(st, "bank", None) if st is not None else None
    if left > 0 and bank:
        take = min(left, int(bank.get(code, 0)))
        if take:
            bank[code] = int(bank.get(code, 0)) - take
            if bank[code] <= 0:
                bank.pop(code, None)
            left -= take
    return left <= 0


# ---------------------------------------------------------------- the reward
def claim(world, bid):
    """Hand a finished contract in. One payment, one item, and the whole team is done with it."""
    p = world.player
    crowd = party(world)
    o = next((x for x in p.bounties if x["id"] == bid), None)
    if o is None or not complete(o, p):
        return False
    if o["kind"] in DEPOSIT and not _spend_deposit(p, o):
        world.log("You are not carrying them.", GREY)
        return False
    for h in crowd:                      # everybody is done with it, not only the one who walked up
        h.bounties = [x for x in h.bounties if x["id"] != bid]
    b = p.bounty_board
    if b is not None:
        b["offers"] = [x for x in b["offers"] if x["id"] != bid]
        rng = world.rng
        while len(b["offers"]) < BOARD_SIZE:
            taken = {(x["kind"], x.get("level"), x.get("target")) for x in b["offers"]}
            b["offers"].append(_distinct(world, rng, 900 + len(b["offers"]) + p.bounty_done,
                                         _areas(world), taken))
    # the gold and the item are the contract's, paid once; the experience is everyone's
    p.gold += o["gold"]
    for h in crowd:
        if hasattr(h, "gain_xp"):
            h.gain_xp(o["xp"])
        h.bounty_done = int(getattr(h, "bounty_done", 0)) + 1
    who = "%d in the party" % len(crowd) if len(crowd) > 1 else "you"
    world.log("%s: %d gold, and %d experience to %s." % (o["title"], o["gold"], o["xp"], who), COLOR)
    _give_reward(world, o)
    if b is not None:
        b["claims"] = int(b.get("claims", 0) or 0) + 1
        if b["claims"] >= REFRESH_AFTER:
            b["claims"] = 0
            _rewrite(world)
    _mirror(world)
    _sync_portals(world)
    return True


def _rewrite(world):
    """Every contract on the Tree written again, except the ones in hand.

    This happens on its own after three are handed in. What is held keeps its plaque and its
    place in the quest log, because the work behind it is real and nothing out here undoes it.
    """
    p = world.player
    b = p.bounty_board
    if not b:
        return
    rng = world.rng
    areas = _areas(world)
    held_ids = {x["id"] for x in p.bounties}
    taken = {(o["kind"], o.get("level"), o.get("target")) for o in b["offers"] if o["id"] in held_ids}
    n = 1700 + int(getattr(p, "bounty_done", 0) or 0) * BOARD_SIZE
    b["offers"] = [o if o["id"] in held_ids else _distinct(world, rng, n + i, areas, taken)
                   for i, o in enumerate(b["offers"])]
    world.log("The Tree's leaves turn. New contracts.", COLOR)


def _give_reward(world, o):
    """The Tree lays the reward at your feet: its worth is decided here, and you pick it up."""
    p = world.player
    it = claim_item(world, o)
    if it is None:
        return
    it.identified = True
    cell = world._drop_cell(p.pos) if hasattr(world, "_drop_cell") else p.pos
    world.ground.setdefault(cell, []).append(it)
    world.emit("drop", cell, it)
    world.log("The Tree lets fall %s." % getattr(it, "shown_name", it.name),
              getattr(it, "color", COLOR))
