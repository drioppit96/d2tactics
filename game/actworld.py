"""Turn an Act 1 level (game/act1.py) into a playable World: entrances, NPCs, monsters,
super uniques from the presets, waypoints and quest objects."""
import random

from .act1 import (LEVEL_NAMES, OUTDOOR_IDS, WORLD_OF, warp_cells, arrival_cell, build_outdoors, build_level,
                   SUB)
from .grid import chebyshev
from .units import Monster

DUNGEON_AMBIENT = 205
OUTDOOR_AMBIENT = 120
TOWN_AMBIENT = 70

NPC_IDS = {"gheed", "cain1", "akara", "rogue1", "kashya", "warriv1", "charsi", "navi",
           "warriv2", "atma", "drognan", "fara", "greiz", "elzix", "lysander", "meshif1", "geglash", "jerhyn",
           "cain2", "act2male", "act2female", "act2guard1", "act2guard4", "act2guard5", "act2vendor1",
           "act2vendor2", "fish", "tyrael1", "place_talkingguard", "place_dumbguard"}
# map markers that aren't fighters in this game (traps and towers come later)
NOT_SPAWNED = ("trap-", "firetower", "lightningspire", "gargoyletrap", "sarcophagus", "place_npc_pack",
               "place_maggot", "place_tightspotboss", "compellingorb", "mephistospirit", "window", "hellmeteor",
               "trappedsoul", "catapult", "baalthrone", "baaltaunt", "worldstoneeffect", "evilhut", "place_dead",
               "injuredbarb", "act5barb", "place_reanimateddead", "place_tentacle", "place_amphibian",
               "place_fetishnest", "place_mosquitonest", "regurgitator", "malachai")
# boss presets named by their MonStats id
BOSS_IDS = {"radament": ("Radament", "radament"), "duriel": ("Duriel", "duriel"),
            "summoner": ("The Summoner", "summoner"), "mephisto": ("Mephisto", "mephisto"),
            "diablo": ("Diablo", "diablo"), "izual": ("Izual", "izual"),
            "baalcrab": ("Baal", "baal"), "nihlathakboss": ("Nihlathak", "nihlathak"),
            # the Ancients' statues on Arreat Summit wake up as the three Ancients
            "ancientstatue1": ("Talic the Defender", "ancients", "ancientbarb1"),
            "ancientstatue2": ("Madawc the Guardian", "ancients", "ancientbarb2"),
            "ancientstatue3": ("Korlic the Protector", "ancients", "ancientbarb3")}


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


class ActInfo:
    """Static info about act 1 levels (names, monster levels, rosters)."""

    def __init__(self, kit, content):
        self.kit, self.content = kit, content
        self.rows = kit.levels
        self.strings = getattr(content, "strings", None)

    def name(self, lid):
        r = self.rows.get(lid)
        if r and self.strings is not None and r.get("levelname"):
            nm = self.strings.get(r["levelname"], None)
            if nm:
                return nm
        return LEVEL_NAMES.get(lid, "Level %s" % lid)

    def monster_level(self, lid):
        r = self.rows.get(lid) or {}
        sfx = getattr(self.content, "sfx", "")
        col = {"": "monlvl1ex", "(n)": "monlvl2ex", "(h)": "monlvl3ex"}.get(sfx, "monlvl1ex")
        return max(1, _int(r.get(col)) or _int(r.get("monlvl1"), 1))

    def roster(self, lid):
        r = self.rows.get(lid)
        if not r or self.content is None:
            return []
        sfx = getattr(self.content, "sfx", "")
        prefix = "mon" if sfx == "" else "nmon"
        ids = [r.get("%s%d" % (prefix, i), "").lower() for i in range(1, 11)]
        ids = [i for i in ids if i and i in self.content.monstats]
        if not ids:
            ids = [i for i in self.content.roster(r)]
        return ids


PORTAL_KINDS = ("portal", "arcane_portal", "duriel_portal")
CODE_NPCS = {"jungle": ["hratli"], "siege": ["larzuk", "tyrael3"]}


def setup(world, built, grid, rng, info, level_key):
    """Fill a World with an Act 1 level."""
    b = built
    world.grid, world.rng, world.tilemap = grid, rng, b.tm
    world.level_key = level_key
    world.info = info
    world.areas = dict(b.areas)
    world.town_rect = getattr(b, "town_rect", None)
    world.exits = {}
    world.entries = {}           # level you came from -> where you arrive
    world.waypoints = {}         # cell -> level id
    world.objects = []           # quest objects: dict(kind, cell, level, state)
    kit = info.kit
    # ---- entrances (warp tiles grouped by their vis slot)
    groups = {}
    for tile, main, owner in b.warps:
        groups.setdefault((owner, main), []).append(tile)
    for (owner, main), tiles in groups.items():
        target = kit.vis(owner, main)
        if not target:
            continue
        cells = []
        for t in tiles:
            cells += warp_cells(grid, t)
        cells = sorted(set(cells))
        if not cells:
            continue
        for c in cells:
            world.exits[c] = target
        world.entries.setdefault(target, arrival_cell(grid, cells, set(world.exits), rng))
    # ---- seamless edges between two worlds (e.g. the jungle's end and Lower Kurast): cells -> level
    for cells, target in getattr(b, "edge_exits", []) or []:
        cells = [c for c in cells if grid.walkable(*c)]
        if not cells:
            continue
        for c in cells:
            world.exits[c] = target
        world.entries.setdefault(target, arrival_cell(grid, cells, set(world.exits), rng, dist=5))
    # ---- doors without warp tiles (Barracks <-> Outer Cloister)
    if level_key == 28:
        edge = [(x, y) for y in range(grid.h) for x in (0, 1, grid.w - 2, grid.w - 1) if grid.walkable(x, y)] + \
               [(x, y) for x in range(grid.w) for y in (0, 1, grid.h - 2, grid.h - 1) if grid.walkable(x, y)]
        room = getattr(b, "court_room", None)
        if room:
            rx, ry, rw, rh = room
            edge = [c for c in edge if rx * SUB - 2 <= c[0] <= (rx + rw) * SUB + 2 and ry * SUB - 2 <= c[1] <= (ry + rh) * SUB + 2]
        for c in edge:
            world.exits[c] = 27
        if edge:
            world.entries[27] = arrival_cell(grid, edge, set(world.exits), rng)
    if level_key == "wild" and getattr(b, "court_rect", None):
        cx, cy, cw, ch = b.court_rect
        x0, y0, x1, y1 = cx * SUB, cy * SUB, (cx + cw) * SUB, (cy + ch) * SUB
        door = [(x, y) for x in range(x0, x1) for y in (y0, y0 + 1) if grid.walkable(x, y)]
        door += [(x, y) for y in range(y0, y1 - 20) for x in (x0, x0 + 1, x1 - 2, x1 - 1) if grid.walkable(x, y)]
        for c in door:
            world.exits[c] = 28
        if door:
            world.entries[28] = arrival_cell(grid, door, set(world.exits), rng)
    if level_key == 39:
        # the red portal from the camp puts you near a corner of the farm
        c0 = _free_near(grid, (2 * 8 * SUB + 10, 2 * 8 * SUB + 10), 30)
        if c0 is not None:
            world.entries[1] = c0
    # ---- objects: waypoints and quest objects
    for kind, cell, owner, oid in b.objects:
        c = _free_near(grid, cell, 10)
        if c is None:
            continue
        if kind == "waypoint":
            world.waypoints[c] = owner
        elif kind in PORTAL_KINDS:
            # a fixed portal (Arcane Sanctuary, Canyon, Duriel's Lair): oid = where it leads;
            # coming back through it you arrive next to it
            world.objects.append(dict(kind=kind, cell=c, level=owner, oid=0, used=False, target=oid))
            world.entries.setdefault(oid, arrival_cell(grid, [c], set(world.exits), rng, dist=2))
        else:
            world.objects.append(dict(kind=kind, cell=c, level=owner, oid=oid, used=False))
    # ---- NPCs
    world.npcs = []
    monsters = []
    from .world import NPC_NAMES
    content = world.content
    for npc_id, cell in b.npcs:
        if npc_id == "navi" and any(n.npc == "navi" for n in world.npcs):
            continue
        cell = _free_near(grid, cell)
        if cell is None:
            continue
        t = None
        if content and npc_id in content.monstats:
            t = content.monster_template(npc_id)
        m = Monster("zombie", *cell, rng=rng, template=t)
        m.npc = npc_id
        m.name = NPC_NAMES.get(npc_id, m.name)
        m.ai = "npc"
        m.aware = False
        world.npcs.append(m)
        monsters.append(m)
    # D2 places Jerhyn by code (no preset): in front of the palace door
    if level_key == "desert" and 50 in world.entries and not any(n.npc == "jerhyn" for n in world.npcs):
        door = world.entries[50]
        cell = None
        for r in range(3, 9):
            for dx in range(-r, r + 1):
                c = (door[0] + dx, door[1] + r)
                if grid.walkable(*c) and c not in world.exits and c not in {m.pos for m in monsters}:
                    cell = c
                    break
            if cell:
                break
        if cell:
            t = content.monster_template("jerhyn") if content and "jerhyn" in content.monstats else None
            m = Monster("zombie", *cell, rng=rng, template=t)
            m.npc, m.name, m.ai, m.aware = "jerhyn", NPC_NAMES.get("jerhyn", "Jerhyn"), "npc", False
            world.npcs.append(m)
            monsters.append(m)
    # NPCs D2 places by code (no preset in the town's DS1): near the middle of the town
    for npc_id in CODE_NPCS.get(level_key, ()):
        if any(n.npc == npc_id for n in world.npcs) or not world.town_rect:
            continue
        x0, y0, x1, y1 = world.town_rect
        occ = {m.pos for m in monsters}
        cx, cy = (x0 + x1) // 2 + rng.randint(-25, 25), (y0 + y1) // 2 + rng.randint(-25, 25)
        cell = None
        for r in range(0, 60, 2):
            for dx in range(-r, r + 1, 2):
                for dy in (-r, r):
                    c = (cx + dx, cy + dy)
                    if grid.walkable(*c) and c not in occ and c not in world.exits:
                        cell = c
                        break
                if cell:
                    break
            if cell:
                break
        if cell:
            t = content.monster_template(npc_id) if content and npc_id in content.monstats else None
            m = Monster("zombie", *cell, rng=rng, template=t)
            m.npc, m.name, m.ai, m.aware = npc_id, NPC_NAMES.get(npc_id, npc_id.title()), "npc", False
            world.npcs.append(m)
            monsters.append(m)
    world.monsters = monsters
    # ---- monsters
    taken = {m.pos for m in monsters}
    safe = list(world.entries.values()) + list(world.waypoints)
    for name, cell, owner in b.presets:
        _spawn_preset(world, name, cell, owner, taken, info)
    from .acts import TOWN_IDS
    world._reach = reach_tiles(grid, [c for c in safe if c] + ([world._default_start()] if world.npcs else []))
    from . import objects as gobjects
    import time as _t
    _t0 = _t.time()
    gobjects.populate(world, b, info, taken, safe)
    world._obj_time = _t.time() - _t0
    for lid, rect in world.areas.items():
        if lid in TOWN_IDS or lid == 20:
            continue
        _populate(world, lid, rect, taken, safe, info)


def _free_near(grid, cell, radius=4):
    if grid.walkable(*cell):
        return cell
    for r in range(1, radius + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                c = (cell[0] + dx, cell[1] + dy)
                if grid.walkable(*c):
                    return c
    return None


def _template(world, mid, lvl, unique=False):
    c = world.content
    key = c.monstats_key(mid) if c else None
    if key is None:
        return None
    t = c.monster_template(key, unique=unique, level=lvl)
    return t


def _spawn(world, mid, cell, lvl, taken, unique=False, name=None, champion=False):
    if cell is None or cell in taken or not world.grid.walkable(*cell):
        return None
    t = _template(world, mid, lvl, unique)
    if t is None:
        return None
    if champion:
        t = dict(t)
        t["hp"] = (t["hp"][0] * 3, t["hp"][1] * 3)
        t["dmg"] = (t["dmg"][0] * 2, t["dmg"][1] * 2)
        t["xp"] *= 3
        t["level"] += 2
    m = Monster(t["ai"] if t["ai"] in ("fallen", "shaman") else "zombie", *cell, rng=world.rng, template=t)
    m.kind = {"fallen": "fallen", "shaman": "shaman"}.get(t["ai"], "d2")
    m.ai = t["ai"]
    m.unique = unique
    m.champion = champion
    if name:
        m.name = name
    world.monsters.append(m)
    taken.add(cell)
    return m


def _spots(world, centre, n, taken, radius=4):
    out = []
    g = world.grid
    for r in range(0, radius + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                c = (centre[0] + dx, centre[1] + dy)
                if g.walkable(*c) and c not in taken and c not in out:
                    out.append(c)
                    if len(out) >= n:
                        return out
    return out


def _superunique(world, name):
    c = world.content
    table = getattr(c, "superuniques", {}) or {}
    if name.lower() in table:
        return table[name.lower()]
    for r in table.values():
        if r.get("name", "").lower() == name.lower():
            return r
    return None


def _spawn_preset(world, name, cell, owner, taken, info):
    lvl = info.monster_level(owner)
    roster = info.roster(owner)
    rng = world.rng
    if name in NPC_IDS or name in ("chicken", "cow", "camel"):
        return
    if name == "compellingorb":
        # Travincal's Compelling Orb: an object you smash with Khalim's Will
        c = _free_near(world.grid, cell, 8)
        if c is not None:
            world.objects.append(dict(kind="orb", cell=c, level=owner, oid=0, used=False))
        return
    if name.lower().startswith(NOT_SPAWNED):
        return
    if name.lower() in BOSS_IDS:
        entry = BOSS_IDS[name.lower()]
        title, boss = entry[0], entry[1]
        mid = entry[2] if len(entry) > 2 else name.lower()
        m = _spawn(world, mid, _free_near(world.grid, cell, 8), lvl + 2, taken, unique=True, name=title)
        if m is not None:
            m.boss = boss
        return
    if name == "The Cow King" and owner != 39:
        return      # D2 only puts him on the Moo Moo Farm (some outdoor presets carry his marker)
    if name in ("place_fallen", "place_fallenshaman"):
        base = "fallenshaman" if name.endswith("shaman") else "fallen"
        mid = next((m for m in roster if m.startswith(base) and (base != "fallen" or not m.startswith("fallenshaman"))),
                   base + "1")
        _spawn(world, mid, _free_near(world.grid, cell, 8), lvl, taken)
        return
    if name == "place_bloodraven":
        m = _spawn(world, "bloodraven", _free_near(world.grid, cell, 8), lvl + 2, taken, unique=True, name="Blood Raven")
        if m is not None:
            m.boss = "blood_raven"
            m.xp_value *= 2
        return
    if name == "andariel":
        m = _spawn(world, "andariel", _free_near(world.grid, cell, 8), lvl, taken, unique=True, name="Andariel")
        if m is not None:
            m.boss = "andariel"
        return
    if name.startswith("place_group") or name in ("place_unique_pack", "place_champion"):
        if not roster:
            return
        pct = _int(name.replace("place_group", "")) if name.startswith("place_group") else 100
        if rng.randrange(100) >= pct:
            return
        _pack(world, cell, rng.choice(roster), lvl, taken, champion=name in ("place_unique_pack", "place_champion"))
        return
    su = _superunique(world, name)
    if su is not None:
        mid = su.get("class", "")
        cell2 = _free_near(world.grid, cell, 8)
        shown = su.get("name") or name
        if world.content is not None and getattr(world.content, "strings", None) is not None:
            shown = world.content.strings.get(shown, shown)
        m = _spawn(world, mid, cell2, lvl + 3, taken, unique=True, name=shown)
        if m is None:
            return
        m.boss = {"Corpsefire": "corpsefire", "The Countess": "countess", "The Smith": "smith",
                  "Griswold": "griswold", "Coldworm the Burrower": "coldworm",
                  "Fangskin": "fangskin", "Bloodwitch the Wild": "bloodwitch",
                  "Ismail Vilehand": "council", "Geleb Flamefinger": "council", "Bremm Sparkfist": "council",
                  "Toorc Icefist": "council", "Wyand Voidfinger": "council", "Maffer Dragonhand": "council",
                  "Siege Boss": "shenk", "Grand Vizier of Chaos": "seal", "Lord De Seis": "seal",
                  "Infector of Souls": "seal", "Witch Doctor Endugu": "endugu",
                  "Sszark the Burning": "sszark", "Dac Farren": "dacfarren", "The Feature Creep": "hephasto"}.get(name, "superunique")
        lo, hi = _int(su.get("mingrp")), _int(su.get("maxgrp"))
        for c in _scatter(world, cell2, rng.randint(lo, max(lo, hi)) if hi else 0, taken):
            _spawn(world, mid, c, lvl + 1, taken, champion=False)


def _scatter(world, centre, n, taken, radius=6, gap=2):
    """Spots for a pack spread over a few tiles (at least `gap` cells apart, in sight of the centre)
    instead of a tight clump; falls back to the nearest free cells."""
    g = world.grid
    rng = world.rng
    out = []
    for _ in range(n * 25):
        if len(out) >= n:
            break
        c = (centre[0] + rng.randint(-radius, radius), centre[1] + rng.randint(-radius, radius))
        if not g.walkable(*c) or c in taken or c in out:
            continue
        if any(max(abs(c[0] - o[0]), abs(c[1] - o[1])) < gap for o in out):
            continue
        if not g.line_of_sight(centre, c):
            continue
        out.append(c)
    if len(out) < n:
        out += [c for c in _spots(world, centre, n * 2, taken | set(out)) if c not in out][:n - len(out)]
    return out


def _pack(world, centre, mid, lvl, taken, champion=False):
    c = world.content
    t = _template(world, mid, lvl)
    if t is None:
        return
    rng = world.rng
    lo, hi = sorted(t["group"])
    n = rng.randint(max(2, lo), max(3, hi))
    members = [mid] * n
    if t["minion"] and t["minion"] in c.monstats:
        plo, phi = t["party"] if t["party"][1] else (2, 4)
        members += [t["minion"]] * rng.randint(max(1, plo), max(1, phi))
    members = members[:7]
    spots = _scatter(world, centre, len(members), taken, radius=5 + len(members) // 3)
    for i, (m, cell) in enumerate(zip(members, spots)):
        _spawn(world, m, cell, lvl, taken, champion=champion and i == 0)


def reach_tiles(grid, seeds):
    """Tiles (5x5 cells) you can walk to from the entrances: monsters only spawn there
    (no packs stranded on a lava lake or behind a cliff)."""
    if not seeds:
        return None
    tw, th = grid.w // 5, grid.h // 5
    ok = bytearray(tw * th)
    for ty in range(th):
        for tx in range(tw):
            if grid.walkable(tx * 5 + 2, ty * 5 + 2) or grid.walkable(tx * 5 + 1, ty * 5 + 1):
                ok[ty * tw + tx] = 1
    seen = bytearray(tw * th)
    stack = []
    for c in seeds:
        t = (c[0] // 5, c[1] // 5)
        if 0 <= t[0] < tw and 0 <= t[1] < th:
            i = t[1] * tw + t[0]
            if not seen[i]:
                seen[i] = 1
                stack.append(i)
    while stack:
        i = stack.pop()
        x, y = i % tw, i // tw
        for j in (i - 1 if x > 0 else -1, i + 1 if x < tw - 1 else -1, i - tw if y > 0 else -1, i + tw if y < th - 1 else -1):
            if j >= 0 and ok[j] and not seen[j]:
                seen[j] = 1
                stack.append(j)
    return (seen, tw, th)


def _reachable(world, c):
    r = getattr(world, "_reach", None)
    if r is None:
        return True
    seen, tw, th = r
    tx, ty = c[0] // 5, c[1] // 5
    return 0 <= tx < tw and 0 <= ty < th and seen[ty * tw + tx]


def _populate(world, lid, rect, taken, safe, info):
    roster = info.roster(lid)
    if not roster:
        return
    rng = world.rng
    g = world.grid
    x0, y0, x1, y1 = rect
    x1, y1 = min(x1, g.w), min(y1, g.h)
    area = max(1, (x1 - x0) * (y1 - y0))
    samples = 300
    hits = sum(1 for _ in range(samples) if g.walkable(rng.randrange(x0, x1), rng.randrange(y0, y1)))
    walk = area * hits / float(samples)
    from .acts import OUTDOOR_IDS as ALL_OUTDOOR
    outdoor = lid in ALL_OUTDOOR
    per_pack = 1500 if outdoor else 330
    n_packs = min(int(walk / per_pack), 42 if outdoor else 40)
    lvl = info.monster_level(lid)
    centres = []
    tries = 0
    town = world.town_rect
    while len(centres) < n_packs and tries < n_packs * 40:
        tries += 1
        c = (rng.randrange(x0, x1), rng.randrange(y0, y1))
        if not g.walkable(*c) or c in taken or not _reachable(world, c):
            continue
        if any(chebyshev(c, s) < 22 for s in safe if s):
            continue
        if town and town[0] - 30 <= c[0] <= town[2] + 30 and town[1] - 30 <= c[1] <= town[3] + 30:
            continue
        if any(chebyshev(c, p) < (9 if outdoor else 6) for p in centres):
            continue
        centres.append(c)
    weights = []
    for r in roster:
        t = _template(world, r, lvl)
        weights.append(t["rarity"] if t else 1)
    for c in centres:
        mid = rng.choices(roster, weights=weights)[0]
        _pack(world, c, mid, lvl, taken)


# ---------------------------------------------------------------- building whole worlds
# the outdoor worlds of Acts 3-5: key -> (module, builder)
LATE_WORLDS = {"jungle": ("act3", "build_jungle"), "kurast": ("act3", "build_kurast"),
               "mesa": ("act4", "build_mesa"), "lava": ("act4", "build_lava"),
               "siege": ("act5", "build_siege"), 117: ("act5", "build_tundra")}


def _late_dungeon(level_key):
    if not isinstance(level_key, int) or level_key < 75:
        return None
    import importlib
    for mod in ("act3", "act4", "act5"):
        try:
            m = importlib.import_module("game." + mod)
        except ImportError:
            continue
        if level_key in getattr(m, "DUNGEONS", {}):
            return m
    return None


def make_world(kit, info, content, level_key, seed=None, player=None, char_class="bar", char_name=None):
    """level_key: "wild" (the whole outdoor act) or a dungeon level id."""
    from .world import World
    from . import act2
    if level_key == "wild":
        b, grid, rng = build_outdoors(kit, seed, content)
    elif level_key == "desert":
        b, grid, rng = act2.build_desert(kit, seed, content)
    elif level_key == 46:
        b, grid, rng = act2.build_canyon(kit, seed, content)
    elif level_key == 39:
        from .act1 import build_cow
        b, grid, rng = build_cow(kit, seed, content)
    elif level_key in LATE_WORLDS:
        mod, fn = LATE_WORLDS[level_key]
        import importlib
        b, grid, rng = getattr(importlib.import_module("game." + mod), fn)(kit, seed, content)
    elif _late_dungeon(level_key):
        b, grid, rng = _late_dungeon(level_key).build_level(kit, level_key, seed)
    elif level_key in act2.DUNGEONS:
        real = act2.CURRENT_REAL or act2.real_tomb(getattr(player, "name", None) or char_name)
        b, grid, rng = act2.build_level(kit, level_key, seed, real=real)
    else:
        b, grid, rng = build_level(kit, level_key, seed)
    w = World(built=(b, grid, rng), content=content, level_key=level_key, info=info, player=player,
              char_class=char_class, char_name=char_name)
    settle_big_monsters(w)
    return w


def settle_big_monsters(w):
    """Big monsters need their 3x3 cells free: move them to the nearest spot where they fit."""
    for m in w.monsters:
        if not m.alive or not getattr(m, "radius", 0):
            continue
        blocked = w.occupied(m)
        if w.fits(m.pos, m.radius, blocked):
            continue
        best = None
        for r in range(1, 8):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    c = (m.x + dx, m.y + dy)
                    if max(abs(dx), abs(dy)) == r and w.fits(c, m.radius, blocked):
                        best = c
                        break
                if best:
                    break
            if best:
                break
        if best:
            m.x, m.y = best
            m.home = best
        else:
            m.radius = 0        # no room anywhere near: behaves like a normal-sized monster


def ensure_cain(world):
    """Once rescued, Deckard Cain waits in the camp."""
    p = world.player
    if not getattr(p, "cain_rescued", False) or world.level_key != "wild":
        return
    if any(getattr(n, "npc", "") == "cain1" for n in world.npcs):
        return
    akara = next((n for n in world.npcs if getattr(n, "npc", "") == "akara"), None)
    if akara is None:
        return
    from .world import NPC_NAMES
    cell = None
    occ = world.occupied()
    for r in (2, 3, 4, 5):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                c = (akara.x + dx, akara.y + dy)
                if world.grid.walkable(*c) and c not in occ:
                    cell = c
                    break
            if cell:
                break
        if cell:
            break
    if cell is None:
        return
    c = world.content
    t = c.monster_template("cain1") if c and "cain1" in c.monstats else None
    m = Monster("zombie", *cell, rng=world.rng, template=t)
    m.npc = "cain1"
    m.name = NPC_NAMES.get("cain1", "Deckard Cain")
    m.ai = "npc"
    m.aware = False
    world.npcs.append(m)
    world.monsters.append(m)
