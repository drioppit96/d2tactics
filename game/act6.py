"""Act 6: Sanctuary.

Diablo ends when Baal falls. This game carries on: once the Lord of Destruction is dead, a red
portal called Destruction's End opens in Harrogath and leads to Sanctuary above - a town of
its own, where the Tree of Inifuss hands out bounties. It is named apart from D2's own Arreat
Summit (Levels.txt 120, "Rocky Summit") so the two never stand for one another.

It is a town, so the usual town rules hold: nothing spawns there, the party rests, and the stash
and the waypoint work. The layout is assets/maps/sanctuary.json, a hand-made map that stamps
Diablo's own mountaintop preset and then changes it (game/custommap.py).

Act 6 is per difficulty, like everything else the hero's quests track: beating Baal in Normal
opens Sanctuary in Normal, and Nightmare and Hell each want their own Baal.

    available(player)       is the Summit open for this hero, in this difficulty
    ensure_portal(world)    the portal in Harrogath, once Baal is dead
    on_enter(world, lid)    arriving at the Summit: the way home
"""
from .acts import SUMMIT

MAP_NAME = "sanctuary"          # assets/maps/sanctuary.json, bound by its "level": 137
HARROGATH = 109
WORLDSTONE = 132          # the Worldstone Chamber, where Baal falls
PORTAL_NAME = "Destruction's End"
STASH_OID = 88            # the chest the map puts beside the Tree: the hero's stash
TREE_OID = 30             # the Tree of Inifuss: the bounty board
ALTAR_OIDS = (546,)       # the Ancients' altar in the middle of the ring: removed, not used
COLOR = (199, 179, 119)


def available(player):
    """Act 6 opens for a hero who has killed Baal in the difficulty he is playing."""
    q = getattr(player, "quests", None) or {}
    return q.get("baal") in ("cleared", "done")


def blocked(player):
    """The line to show someone who tries to go up before Baal is dead, or None."""
    if available(player):
        return None
    return "The way to Sanctuary is shut. Baal still holds the Worldstone."


def ensure_portal(world):
    """The red portal that stands in Harrogath once Baal has fallen, and the one that opens in the
    Worldstone Chamber over his body. Called whenever a level is entered or a save is loaded."""
    p = getattr(world, "player", None)
    if p is None or not available(p):
        return
    lid = getattr(world, "level_id", None)
    if lid == HARROGATH:
        _place(world, SUMMIT, _near_town_centre(world))
    elif lid == WORLDSTONE:
        _place(world, SUMMIT, p.pos)
    # the Summit needs no portal home: the great red portal in the middle of the plateau is its
    # waypoint (game/acts.py WAYPOINTS[6]), and the waypoint menu goes anywhere you have been


def open_on_baal_death(world):
    """Baal is down in the Worldstone Chamber: Destruction's End tears open where he fell, so the
    party can walk straight up to the Summit instead of going back to Harrogath first."""
    p = getattr(world, "player", None)
    if p is None or not available(p):
        return
    if getattr(world, "level_id", None) != WORLDSTONE:
        return
    before = len(world.objects)
    _place(world, SUMMIT, p.pos, prefer=world._free_cell_near((p.x + 2, p.y + 2), 4))
    if len(world.objects) > before:
        world.log("The Worldstone is broken. %s opens above you - Sanctuary waits."
                  % PORTAL_NAME, COLOR)


def _near_town_centre(world):
    """Beside the waypoint in Harrogath, where a player will walk past it."""
    wp = next(iter(getattr(world, "waypoints", {})), None)
    base = (wp[0] + 6, wp[1] + 5) if wp else (world.player.x + 6, world.player.y + 5)
    return base


def _place(world, target, near, prefer=None):
    """One Destruction's End portal to `target`, and no more than one."""
    if any(o.get("kind") == "portal" and o.get("target") == target for o in world.objects):
        return
    cell = None
    if prefer is not None:
        cell = prefer if world.grid.walkable(*prefer) else world._free_cell_near(prefer, 4)
    if cell is None and near is not None:
        cell = world._free_cell_near(near, 4) or world._free_cell_near(near, 10)
    if cell is None:
        cell = world._free_cell_near(world.player.pos, 8)
    if cell is None:
        return
    world.objects.append(dict(kind="portal", cell=cell, level=world.level_id, oid=0, used=False,
                              target=target, name=PORTAL_NAME))
    if prefer is None:
        world.log("A portal tears open: %s." % PORTAL_NAME, COLOR)


#: the three the mountaintop preset carries, one statue each
ANCIENT_IDS = ("ancientbarb1", "ancientbarb2", "ancientbarb3")


def _only_three(world):
    """At most one of each Ancient on the Summit.

    The map a player is running may not be the one the game ships: the map editor writes
    maps/sanctuary.json beside it, and that copy is used when it is the newer of the two. A
    copy that stamps the mountaintop preset twice, or that was saved with the statues already in
    its own monster list, puts two or three Korlics on the plateau instead of one - and because
    the Summit is a town where nothing respawns, they simply pile up.

    Only the repeats go. Anything else the map puts up here is the map author's business, not
    ours, so monsters that are not Ancients are left exactly where they were placed.
    """
    keep, drop, seen = [], [], set()
    for m in world.monsters:
        if getattr(m, "boss", None) == "ancients" or str(getattr(m, "d2id", "")) in ANCIENT_IDS:
            key = str(getattr(m, "d2id", "")) or m.name
            if key in seen:
                drop.append(m)
                continue
            seen.add(key)
        keep.append(m)
    if not drop:
        return
    world.monsters = keep
    for m in drop:
        m.alive = False
    world.log("The Summit settles: %d repeated %s sent back to the mountain." % (
        len(drop), "guardian" if len(drop) == 1 else "guardians"), COLOR)


def bounty_portals(world):
    """The three pedestals in the ring, one per contract in hand.

    Take a contract that sends you somewhere and the pedestal it stands on opens, leading
    straight to the area the work is in. It stays open until the contract is done, then shuts:
    there is nothing left to go there for. A deposit is settled at the Tree, so it opens nothing.
    """
    if getattr(world, "level_id", None) != SUMMIT:
        return
    spots = list(getattr(world, "pedestals", None) or ())
    if not spots:
        return
    from . import bounties
    p = world.player
    bounties.init(p)
    want = []
    for o in bounties.held(p):
        lvl = bounties.destination(o)
        if lvl is None or bounties.complete(o, p):
            continue
        want.append((o["id"], lvl, o["title"]))
    # they are ordinary portals, so they draw and work like any other; "bounty" marks them ours
    world.objects = [o for o in world.objects if not o.get("bounty")]
    for i, (bid, lvl, title) in enumerate(want[:len(spots)]):
        cell = spots[i]
        if not world.grid.walkable(*cell):
            cell = world._free_cell_near(cell, 3) or cell
        world.objects.append(dict(kind="portal", cell=cell, level=SUMMIT, oid=0, used=False,
                                  target=lvl, name=title, bounty=bid))


def on_enter(world, lid):
    """Arriving somewhere: open the portal if this is one of the two ends of it."""
    if lid in (HARROGATH, SUMMIT, WORLDSTONE):
        ensure_portal(world)
    if lid == SUMMIT:
        _only_three(world)
        # The mountaintop preset carries the Ancients' three statues and the altar they rise from.
        # The Rite of Passage was fought below, in Act 5, and Sanctuary is a town: none of it
        # belongs here, so the statues and the altar go rather than standing about as scenery.
        # their three pedestals are kept: the bounty portals stand on them (bounty_portals below)
        world.pedestals = sorted((m.x, m.y) for m in world.monsters
                                 if getattr(m, "boss", None) == "ancients"
                                 or str(getattr(m, "d2id", "")) in ANCIENT_IDS)
        world.monsters = [m for m in world.monsters
                          if getattr(m, "boss", None) != "ancients"
                          and str(getattr(m, "d2id", "")) not in ANCIENT_IDS]
        world.objects = [o for o in world.objects
                         if o.get("oid") not in ALTAR_OIDS and o.get("kind") != "altar"]
        # the chest beside the Tree of Inifuss is the hero's own stash. The map places D2's chest
        # for its look; a town turns every container into scenery (game/objects.py), so it is made
        # a stash here, keeping its art.
        for o in world.objects:
            if o.get("oid") == STASH_OID and o.get("kind") in ("decor", "chest"):
                o["kind"], o["name"] = "stash", "Stash"
        # the Tree of Inifuss is what Act 6 is for: click it for the bounty board
        for o in world.objects:
            if o.get("oid") == TREE_OID and o.get("kind") in ("decor", "chest", "bounty"):
                o["kind"], o["name"] = "bounty", "Tree of Inifuss"
        from . import bounties
        bounties.init(world.player)
        bounty_portals(world)
        p = world.player
        seen = p.__dict__.setdefault("visited", set())
        if SUMMIT not in seen:
            seen.add(SUMMIT)
        if not getattr(p, "_summit_seen", False):
            p._summit_seen = True
            world.log("You stand in Sanctuary. The Tree of Inifuss waits below.", COLOR)
