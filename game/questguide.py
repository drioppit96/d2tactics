"""Quest tracker: what to do next for each open quest, and which way to go.

objectives(world)          -> [Objective] for the quests under way (some quests have several parts)
guide(world, objective)    -> (cell or None, text): where the HUD arrow points and what it says

The way is found over D2's level graph: the outdoor areas that join seamlessly, the entrances
(Levels.txt Vis), the fixed portals and your waypoints. In the level of the objective the arrow
points at the boss, the quest object or the NPC; elsewhere at the exit (passage, entrance, portal or
waypoint) that is the next step towards it.
"""
import heapq

from .acts import TOWNS, act_of

# areas that join without an entrance (one outdoor world)
OUTDOOR_LINKS = [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7), (3, 17), (26, 27), (27, 28), (32, 33),
                 (40, 41), (41, 42), (42, 43), (43, 44), (44, 45),
                 (75, 79), (80, 76), (80, 77), (79, 80), (80, 81), (81, 82), (82, 83),
                 (103, 104), (104, 105), (105, 106), (107, 108),
                 (109, 110), (110, 111), (111, 112)]
# portals: the cairn stones, the palace cellar, the Summoner's journal, Mephisto's red portal,
# Anya's portal, the Worldstone portal
PORTAL_LINKS = [(4, 38), (54, 74), (74, 46), (102, 103), (109, 121), (131, 132)]

NPC_TOWN = {}
for _act, _ids in {1: ("akara", "kashya", "charsi", "warriv1", "cain1", "gheed"),
                   2: ("atma", "drognan", "jerhyn", "cain2", "meshif1", "fara", "lysander", "greiz", "elzix"),
                   3: ("ormus", "alkor", "meshif2", "cain3", "hratli", "asheara", "natalya"),
                   4: ("tyrael2", "cain4", "jamella", "halbu"),
                   5: ("larzuk", "malah", "qual-kehk", "drehya", "tyrael3", "cain6", "anya")}.items():
    for _n in _ids:
        NPC_TOWN[_n] = TOWNS[_act]


class Objective:
    def __init__(self, key, qid, title, label, level, find=None):
        self.key, self.qid, self.title, self.label = key, qid, title, label
        self.level, self.find = level, find

    def __repr__(self):
        return "Objective(%s -> %s %s)" % (self.key, self.level, self.find)


def _titles():
    from . import quests, quests2, quests345
    t = dict(quests.ACT1)
    t.update(dict(quests2.ACT2))
    t.update(quests345.TITLES)
    return t


def _npc(name):
    return (NPC_TOWN.get(name, 1), ("npc", name))


def objectives(world):
    """Every objective of the quests under way, all acts you have reached."""
    from .quests2 import has_item
    from . import act2, quests345
    p = world.player
    q = getattr(p, "quests", {}) or {}
    have = lambda code: has_item(p, code, world)
    T = _titles()
    out = []

    def add(qid, label, level, find=None, part=""):
        if level is None:
            return
        out.append(Objective(qid + (":" + part if part else ""), qid, T.get(qid, qid), label, level, find))

    def st(qid):
        return q.get(qid, "none")
    # ---- Act 1
    s = st("den")
    if s == "active":
        add("den", "Clear the Den of Evil", 8, ("monsters",))
    elif s == "cleared":
        add("den", "Talk to Akara", *_npc("akara"))
    s = st("blood_raven")
    if s == "active":
        add("blood_raven", "Kill Blood Raven", 17, ("boss", "blood_raven"))
    elif s == "cleared":
        add("blood_raven", "Talk to Kashya", *_npc("kashya"))
    s = st("cain")
    if s == "active":
        add("cain", "Find the Tree of Inifuss", 5, ("object", "inifuss"))
    elif s == "scroll":
        add("cain", "Take the scroll to Akara", *_npc("akara"))
    elif s == "stones":
        add("cain", "Touch the Cairn Stones", 4, ("object", "cairn"))
    elif s == "portal":
        add("cain", "Free Deckard Cain", 38, ("object", "cage"))
    elif s == "cleared":
        add("cain", "Talk to Akara", *_npc("akara"))
    if st("tower") == "active":
        add("tower", "Kill the Countess", 25, ("boss", "countess"))
    s = st("malus")
    if s == "active":
        add("malus", "Find the Horadric Malus", 28, ("object", "malus"))
    elif s == "cleared":
        add("malus", "Return the Malus to Charsi", *_npc("charsi"))
    s = st("andariel")
    if s == "active":
        add("andariel", "Kill Andariel", 37, ("boss", "andariel"))
    elif s == "cleared":
        add("andariel", "Talk to Warriv", *_npc("warriv1"))
    # ---- Act 2
    s = st("radament")
    if s == "active":
        add("radament", "Kill Radament", 49, ("boss", "radament"))
    elif s == "cleared":
        add("radament", "Talk to Atma", *_npc("atma"))
    s = st("staff")
    if s == "active":
        whole = have("hst")
        if not have("box"):
            add("staff", "Horadric Cube", 60, ("object", "cube_chest"), "cube")
        if not whole and not have("msf"):
            add("staff", "Staff of Kings", 64, ("object", "staff_chest"), "staff")
        if not whole and not have("vip"):
            add("staff", "Amulet of the Viper", 61, ("object", "viper_altar"), "amulet")
    elif s == "cleared":
        add("staff", "Show the staff to Cain", *_npc("cain2"))
    s = st("tainted")
    if s == "active":
        add("tainted", "Smash the altar", 61, ("object", "viper_altar"))
    elif s == "cleared":
        add("tainted", "Talk to Drognan", *_npc("drognan"))
    s = st("arcane")
    if s == "active":
        add("arcane", "Talk to Jerhyn", *_npc("jerhyn"))
    elif s == "palace":
        add("arcane", "Find the Arcane Sanctuary", 74)
    s = st("summoner")
    if s == "active":
        add("summoner", "Kill the Summoner", 74, ("boss", "summoner"))
    elif s == "cleared":
        add("summoner", "Read Horazon's Journal", 74, ("object", "journal"))
    s = st("tombs")
    real = act2.CURRENT_REAL
    if s == "active" and real:
        add("tombs", "Place the staff in the true tomb", real, ("object", "orifice"))
    elif s == "placed":
        add("tombs", "Kill Duriel", 73, ("boss", "duriel"))
    elif s == "cleared":
        add("tombs", "Talk to Jerhyn", *_npc("jerhyn"))
    # ---- Act 3
    s = st("bird")
    if s == "active":
        add("bird", "A unique monster in Lower Kurast", 79, ("unique",))
    elif s == "jade":
        add("bird", "Show the figurine to Meshif", *_npc("meshif2"))
    elif s == "bird":
        add("bird", "Show the bird to Alkor", *_npc("alkor"))
    s = st("gidbinn")
    if s == "active":
        if getattr(p, "armory_lit", False):
            from .act3 import SMITH_NAME
            add("gidbinn", "Kill " + SMITH_NAME, 76, ("boss", "armory_smith"))
        else:
            add("gidbinn", "Light the four altars (Kurast Armory)", 76, ("object", "armory_altar"))
    elif s == "cleared":
        add("gidbinn", "Bring the Gidbinn to Ormus", *_npc("ormus"))
    s = st("khalim")
    if s == "active":
        if not have("qf2"):
            if not have("qey"):
                add("khalim", "Khalim's Eye (Silkmother Vashra)", 76, ("boss", "silkmother"), "eye")
            if not have("qbr"):
                add("khalim", "Khalim's Brain (Scribe Ophizek, Forbidden Library)", 86, ("boss", "scribe"), "brain")
            if not have("qhr"):
                add("khalim", "Khalim's Heart", 93, ("object", "heart_chest"), "heart")
            if not have("qf1"):
                add("khalim", "Khalim's Flail (the Council)", 83, ("boss", "council"), "flail")
    elif s == "cleared":
        add("khalim", "Smash the Compelling Orb", 83, ("object", "orb"))
    s = st("lamesen")
    if s == "active":
        add("lamesen", "Find Lam Esen's Tome", quests345.lamesen_temple(p), ("object", "lamtome"))
    elif s == "cleared":
        add("lamesen", "Bring the tome to Alkor", *_npc("alkor"))
    s = st("council")
    if s == "active":
        add("council", "Kill the High Council", 83, ("boss", "council"))
    elif s == "cleared":
        add("council", "Talk to Cain", *_npc("cain3"))
    if st("mephisto") == "active":
        add("mephisto", "Kill Mephisto", 102, ("boss", "mephisto"))
    # ---- Act 4
    s = st("izual")
    if s == "active":
        add("izual", "Kill Izual", 105, ("boss", "izual"))
    elif s == "cleared":
        add("izual", "Talk to Tyrael", *_npc("tyrael2"))
    s = st("forge")
    if s == "active":
        if not have("mss"):
            add("forge", "Get the Soulstone from Cain", *_npc("cain4"))
        elif not have("hfh"):
            add("forge", "Kill Hephasto for the hammer", 107, ("boss", "hephasto"))
        else:
            add("forge", "Smash the Soulstone on the Hellforge", 107, ("object", "hellforge"))
    elif s == "cleared":
        add("forge", "Talk to Cain", *_npc("cain4"))
    s = st("diablo")
    if s == "active":
        add("diablo", "Kill Diablo", 108, ("boss", "diablo"))
    elif s == "cleared":
        add("diablo", "Talk to Tyrael", *_npc("tyrael2"))
    # ---- Act 5
    s = st("shenk")
    if s == "active":
        add("shenk", "Kill Shenk the Overseer", 110, ("boss", "shenk"))
    elif s == "cleared":
        add("shenk", "Talk to Larzuk", *_npc("larzuk"))
    s = st("barbs")
    if s == "active":
        add("barbs", "Break the prisons", 111, ("object", "prison"))
    elif s == "cleared":
        add("barbs", "Talk to Qual-Kehk", *_npc("qual-kehk"))
    s = st("anya")
    if s == "active":
        if have("ice"):
            add("anya", "Thaw Anya", 114, ("object", "anya"))
        else:
            add("anya", "Get the potion from Malah", *_npc("malah"))
    elif s == "cleared":
        add("anya", "Talk to Malah", *_npc("malah"))
    s = st("nihl")
    if s == "active":
        add("nihl", "Kill Nihlathak", 124, ("boss", "nihlathak"))
    elif s == "cleared":
        add("nihl", "Talk to Anya", *_npc("drehya"))
    if st("ancients") == "active":
        add("ancients", "Defeat the Ancients", 120, ("boss", "ancients"))
    s = st("baal")
    if s == "active":
        add("baal", "Kill Baal", 131, ("boss", "baal"))
    elif s == "cleared":
        add("baal", "Talk to Tyrael", *_npc("tyrael3"))
    return out


# ------------------------------------------------------------------ the level graph
_GRAPH = {}


def _graph(kit):
    key = id(kit)
    g = _GRAPH.get(key)
    if g is not None:
        return g
    g = {}

    def link(a, c, w=1.0):
        if a and c and a != c:
            g.setdefault(a, {})[c] = min(w, g.get(a, {}).get(c, w))
            g.setdefault(c, {})[a] = min(w, g.get(c, {}).get(a, w))
    for a, c in OUTDOOR_LINKS + PORTAL_LINKS + [(77, 86)]:     # (the Scriptorium's temple stairs)
        link(a, c)
    for lid in range(1, 137):
        for i in range(8):
            try:
                v = kit.vis(lid, i)
            except Exception:
                v = None
            if v:
                link(lid, v)
    _GRAPH[key] = g
    return g


def route(world, start, goal):
    """Levels from start to goal, each with how you get there ("walk" / "waypoint")."""
    if start == goal:
        return [(start, None)]
    kit = getattr(getattr(world, "info", None), "kit", None)
    base = _graph(kit) if kit is not None else {}
    from . import act2
    extra = {}

    def link(a, c, w=1.0):
        extra.setdefault(a, {})[c] = w
        extra.setdefault(c, {})[a] = w
    if act2.CURRENT_REAL:
        link(act2.CURRENT_REAL, 73)
    for grp in getattr(world, "warp_groups", []) or []:
        src = world.area_at(next(iter(grp["cells"]))) if grp.get("cells") else None
        if src and grp.get("target"):
            link(src, grp["target"])
    for o in getattr(world, "objects", []) or []:
        if o.get("kind") in ("portal", "arcane_portal", "duriel_portal", "red_portal") and o.get("target"):
            src = world.area_at(o["cell"])
            if src:
                link(src, o["target"])
    # the Monastery Gate hangs off Tamoe Highland or the Black Marsh (whichever had room)
    link(getattr(world, "mg_from", None) or 7, 26)
    wps = sorted(l for l in (getattr(world.player, "waypoints", None) or ()) if isinstance(l, int))
    WP = "wp"

    def nbrs(n):
        for c, w in base.get(n, {}).items():
            yield c, w, "walk"
        for c, w in extra.get(n, {}).items():
            yield c, w, "walk"
        if n in wps:
            for c in wps:
                if c != n:
                    yield c, 2.5, WP
    dist = {start: 0.0}
    prev = {}
    heap = [(0.0, start)]
    while heap:
        d, n = heapq.heappop(heap)
        if n == goal:
            break
        if d > dist.get(n, 1e18):
            continue
        for c, w, how in nbrs(n):
            nd = d + w
            if nd < dist.get(c, 1e18):
                dist[c] = nd
                prev[c] = (n, how)
                heapq.heappush(heap, (nd, c))
    if goal not in prev:
        return None
    path = []
    n = goal
    while n != start:
        pn, how = prev[n]
        path.append((n, how))
        n = pn
    path.append((start, None))
    path.reverse()
    return path


# ------------------------------------------------------------------ pointing
def _nearest(cells, frm):
    best = None
    for c in cells:
        d = max(abs(c[0] - frm[0]), abs(c[1] - frm[1]))
        if best is None or d < best[0]:
            best = (d, c)
    return best[1] if best else None


def _passage(world, a, b, frm):
    """The way from area a into the neighbouring area b of the same world: the middle of the
    walkable run along their shared border nearest to you."""
    cache = world.__dict__.setdefault("_guide_passage", {})
    key = (a, b)
    runs = cache.get(key)
    if runs is None:
        runs = []
        ra, rb = world.areas.get(a), world.areas.get(b)
        g = world.grid
        if ra and rb:
            line = []
            if abs(ra[2] - rb[0]) <= 1 or abs(rb[2] - ra[0]) <= 1:          # side by side
                x = rb[0] if abs(ra[2] - rb[0]) <= 1 else ra[0]
                for y in range(max(ra[1], rb[1]), min(ra[3], rb[3])):
                    line.append((x, y) if g.walkable(x, y) and g.walkable(x - 1, y) else None)
            elif abs(ra[3] - rb[1]) <= 1 or abs(rb[3] - ra[1]) <= 1:        # one above the other
                y = rb[1] if abs(ra[3] - rb[1]) <= 1 else ra[1]
                for x in range(max(ra[0], rb[0]), min(ra[2], rb[2])):
                    line.append((x, y) if g.walkable(x, y) and g.walkable(x, y - 1) else None)
            cur = []
            for c in line + [None]:
                if c is not None:
                    cur.append(c)
                elif cur:
                    if len(cur) >= 3:
                        runs.append(cur[len(cur) // 2])
                    cur = []
        if not runs and rb:
            from .act1 import _walk_centre
            c = _walk_centre(world.grid, rb, None, b)
            if c:
                runs = [c]
        cache[key] = runs
    return _nearest(runs, frm)


def _find(world, find, level):
    p = world.player
    here = lambda c: (world.area_at(c) or world.level_id) == level
    if find is None:
        return None
    kind = find[0]
    if kind == "boss":
        ms = [m for m in world.monsters if m.alive and getattr(m, "boss", None) == find[1]]
        return _nearest([m.pos for m in ms], p.pos)
    if kind == "unique":
        ms = [m for m in world.monsters if m.alive and getattr(m, "unique", False) and not getattr(m, "ally", False)
              and getattr(m, "ai", "") != "npc" and here(m.pos)]
        return _nearest([m.pos for m in ms], p.pos)
    if kind == "monsters":
        ms = [m for m in world.monsters if m.alive and not getattr(m, "ally", False) and getattr(m, "ai", "") != "npc"]
        return _nearest([m.pos for m in ms], p.pos)
    if kind == "object":
        obs = [o["cell"] for o in world.objects if o.get("kind") == find[1] and not o.get("used")]
        return _nearest(obs, p.pos)
    if kind == "npc":
        ns = [n.pos for n in getattr(world, "npcs", []) if getattr(n, "npc", "") == find[1]]
        return _nearest(ns, p.pos)
    return None


def guide(world, obj, name=lambda lid: str(lid)):
    """(cell to point at or None, [text lines]) for an objective."""
    p = world.player
    here = world.area_at(p.pos) or world.level_id
    if not isinstance(here, int):
        here = world.level_key if isinstance(world.level_key, int) else None
    if here is None:
        return None, [obj.label]
    if here == obj.level or (obj.find and obj.find[0] in ("npc",) and obj.level == here):
        cell = _find(world, obj.find, obj.level)
        return cell, [obj.label, "Here: %s" % name(obj.level)]
    path = route(world, here, obj.level)
    if not path or len(path) < 2:
        return None, [obj.label, "In %s" % name(obj.level)]
    nxt, how = path[1]
    tail = "%s  >  %s" % (name(nxt), name(obj.level)) if nxt != obj.level else name(obj.level)
    # the objective's own area in this world (seamless): point straight at the target when known
    if nxt == obj.level and obj.level in (getattr(world, "areas", {}) or {}) and how != "wp":
        cell = _find(world, obj.find, obj.level)
        if cell is not None:
            return cell, [obj.label, "To %s" % tail]
    if how == "wp":
        wps = [c for c, lid in world.waypoints.items() if lid == here] or list(world.waypoints)
        return _nearest(wps, p.pos), [obj.label, "Waypoint to %s" % tail]
    if nxt in (getattr(world, "areas", {}) or {}):
        return _passage(world, here, nxt, p.pos), [obj.label, "To %s" % tail]
    cells = []
    for grp in getattr(world, "warp_groups", []) or []:
        if grp.get("target") == nxt:
            cells.extend(grp["cells"])
    for o in getattr(world, "objects", []) or []:
        if o.get("target") == nxt and o.get("kind") in ("portal", "arcane_portal", "duriel_portal", "red_portal", "tp"):
            cells.append(o["cell"])
    if not cells:
        cells = [c for c, t in (getattr(world, "exits", {}) or {}).items() if t == nxt]
    return _nearest(cells, p.pos), [obj.label, "To %s" % tail]
