"""D2's clickable world objects: chests, caskets, urns, barrels, corpses, weapon and armor racks,
shrines, wells, doors and the stash - plus the torches, braziers and other props drawn in the maps.

Where they come from (like D2):
* the objects placed in the map pieces (DS1 type-2 objects -> objpreset.PRESET -> Objects.txt)
* the random ones every area rolls: Levels.txt ObjGrp0-7 / ObjPrb0-7 name groups of ObjGroup.txt
  (object ids, density and chance), rolled per room of the area

What they do comes from Objects.txt (OperateFn) and Shrines.txt.
"""
import random

from .grid import chebyshev

# Objects.txt OperateFn -> what the object is in this game
OPERATE_KIND = {1: "casket", 3: "urn", 4: "chest", 5: "barrel", 7: "xbarrel", 14: "corpse", 19: "armor_rack",
                20: "weapon_rack", 26: "bookshelf", 2: "shrine", 22: "well", 8: "door", 29: "door", 32: "stash"}
DECOR_FNS = {0, 11, 13}               # torches, braziers, fires, banners, bodies on stakes: drawn only
LOOT_KINDS = {"casket", "urn", "chest", "barrel", "xbarrel", "corpse", "armor_rack", "weapon_rack", "bookshelf"}
BREAKS = {"urn", "barrel", "xbarrel"}           # D2: these break when you open them
OPEN_WORD = {"chest": "open", "casket": "open", "corpse": "search", "armor_rack": "search",
             "weapon_rack": "search", "bookshelf": "search"}

# Shrines.txt codes: what D2 calls them in the game (the table's own names are the designers' notes)
SHRINE_NAMES = {1: "Refilling Shrine", 2: "Health Shrine", 3: "Mana Shrine", 6: "Armor Shrine",
                7: "Combat Shrine", 8: "Resist Fire Shrine", 9: "Resist Cold Shrine",
                10: "Resist Lightning Shrine", 11: "Resist Poison Shrine", 12: "Skill Shrine",
                13: "Mana Recharge Shrine", 14: "Stamina Shrine", 15: "Experience Shrine", 17: "Portal Shrine",
                18: "Gem Shrine", 19: "Fire Shrine", 20: "Monster Shrine", 21: "Exploding Shrine",
                22: "Poison Shrine"}
SHRINE_OUT = {0, 4, 5, 16}            # never used in the released game
FRAMES_PER_TURN = 50                  # D2 runs at 25 frames a second; a turn is about two seconds


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


class ObjData:
    """Objects.txt, ObjGroup.txt and Shrines.txt."""

    def __init__(self, src):
        from d2.source import read_table
        self.src = src
        self._gfx = {}
        self.rows = {}
        try:
            for r in read_table(src, "Objects"):
                if (r.get("id") or "").isdigit():
                    self.rows[int(r["id"])] = r
        except Exception:
            pass
        self.groups = {}
        try:
            for r in read_table(src, "ObjGroup"):
                off = _int(r.get("offset"), -1)
                items = []
                for i in range(8):
                    oid = _int(r.get("id%d" % i))
                    if oid:
                        items.append((oid, _int(r.get("density%d" % i)), _int(r.get("prob%d" % i))))
                self.groups[off] = dict(items=items, shrines=r.get("shrines") == "1", wells=r.get("wells") == "1")
        except Exception:
            pass
        self.shrines = {}
        try:
            for r in read_table(src, "Shrines"):
                code = _int(r.get("code"), -1)
                if code >= 0:
                    self.shrines[code] = dict(code=code, arg0=_int(r.get("arg0")), arg1=_int(r.get("arg1")),
                                              frames=_int(r.get("duration in frames")),
                                              rarity=max(1, _int(r.get("rarity"), 1)))
        except Exception:
            pass

    def kind(self, oid):
        """What an Objects.txt row is here: a kind from OPERATE_KIND, "decor" or None (not used)."""
        r = self.rows.get(oid)
        if r is None:
            return None
        tok = (r.get("token") or "").strip()
        if not tok or len(tok) > 2 or r.get("draw", "1") == "0":
            return None
        if not self.has_gfx(tok):
            return None
        fn = _int(r.get("operatefn"))
        if fn in OPERATE_KIND:
            return OPERATE_KIND[fn]
        if fn in DECOR_FNS:
            return "decor"
        return None

    def has_gfx(self, tok):
        tok = tok.upper()
        if tok not in self._gfx:
            ok = False
            for m in ("NU", "ON", "OP"):
                try:
                    if self.src.has("data\\global\\objects\\%s\\COF\\%s%sHTH.cof" % (tok, tok, m)):
                        ok = True
                        break
                except Exception:
                    ok = True
                    break
            self._gfx[tok] = ok
        return self._gfx[tok]

    def size(self, oid):
        r = self.rows.get(oid, {})
        return max(1, _int(r.get("sizex"), 1)), max(1, _int(r.get("sizey"), 1))

    def name(self, oid, strings=None):
        r = self.rows.get(oid, {})
        n = r.get("name", "")
        if strings is not None and n in getattr(strings, "table", {}):
            n = strings.get(n, n)
        return n.replace("_", " ").strip().title() or "Object"


def data_for(content):
    d = getattr(content, "_objdata", None)
    if d is None and content is not None:
        d = content._objdata = ObjData(content.src)
    return d


def footprint(cell, size):
    sx, sy = size
    return [(cell[0] + dx, cell[1] + dy) for dx in range(-(sx // 2), sx - sx // 2)
            for dy in range(-(sy // 2), sy - sy // 2)]


def _ring_ok(grid, cells):
    """Every cell around a footprint walkable: blocking it can't cut a path in two."""
    cs = set(cells)
    for x, y in cells:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c = (x + dx, y + dy)
                if c not in cs and not grid.walkable(*c):
                    return False
    return all(grid.walkable(*c) for c in cells)


def make(world, oid, cell, owner, data, town=False):
    kind = data.kind(oid)
    if kind is None:
        return None
    r = data.rows[oid]
    o = dict(kind=kind, cell=cell, level=owner, oid=oid, used=False, generic=True,
             token=r["token"].strip().upper(), size=data.size(oid), mode="NU", op_t=None)
    o["name"] = data.name(oid, getattr(world.content, "strings", None))
    o["block"] = []
    if kind == "shrine":
        o["shrine"] = _pick_shrine(_int(r.get("parm0")), data, world.rng)
        o["name"] = SHRINE_NAMES.get(o["shrine"], "Shrine")
    elif kind == "well":
        o["name"] = "Well"
    elif kind == "door":
        o["name"] = "Door"
        o["open"] = town            # town doors stand open
        if town:
            o["mode"] = "ON"
    elif kind == "stash":
        o["name"] = "Stash"
    elif kind in ("weapon_rack", "armor_rack"):
        o["name"] = "Weapon Rack" if kind == "weapon_rack" else "Armor Stand"
    elif kind == "decor":
        frames0 = _int(r.get("framecnt0"))
        o["cycle"] = frames0 > 1
    if kind != "decor":
        cells = footprint(cell, o["size"])
        if kind == "door":
            o["block"] = [c for c in cells if world.grid.walkable(*c)]
        elif _int(r.get("hascollision0")) and _ring_ok(world.grid, cells):
            o["block"] = cells
    return o


def _pick_shrine(parm, data, rng):
    if parm == 1:
        return 2
    if parm == 2:
        return 3
    pool = [s for c, s in data.shrines.items() if c not in SHRINE_OUT and c in SHRINE_NAMES]
    if not pool:
        return 1
    return rng.choices([s["code"] for s in pool], weights=[s["rarity"] for s in pool])[0]


def rebuild_blocks(world):
    world.obj_block = set()
    for o in world.objects:
        if not o.get("generic") or not o.get("block"):
            continue
        if o["kind"] == "door":
            if not o.get("open"):
                world.obj_block.update(o["block"])
        elif not (o["kind"] in BREAKS and o["used"]):
            world.obj_block.update(o["block"])


# ---------------------------------------------------------------- populating a level
def populate(world, built, info, taken, safe):
    """The map pieces' own objects, then each area's random ones (Levels.txt ObjGrp)."""
    data = data_for(world.content)
    if data is None or not data.rows:
        world.obj_block = set()
        return
    from .acts import TOWN_IDS
    act = getattr(built, "act", 1) or 1
    from .objpreset import object_id
    g = world.grid
    near = set()
    for c in list(world.exits) + list(world.waypoints) + [s for s in safe if s]:
        near.add(c)
    exits = list(world.entries.values()) + list(world.waypoints)

    def clear_of(c, dist):
        return all(chebyshev(c, e) > dist for e in exits)
    used_cells = set()
    for o in world.objects:
        used_cells.add(o["cell"])
    for n, cell, owner in getattr(built, "gen_objects", []):
        oid = object_id(act, n)
        if oid is None:
            continue
        kind = data.kind(oid)
        if kind is None:
            continue
        if kind == "decor":
            if not g.in_bounds(*cell):
                continue
        else:
            if not g.walkable(*cell) and kind not in ("door",):
                c2 = _free(g, cell, 2)
                if c2 is None:
                    continue
                cell = c2
            if cell in used_cells or cell in world.exits:
                continue
        o = make(world, oid, cell, owner, data, town=owner in TOWN_IDS)
        if o is None:
            continue
        if owner in TOWN_IDS and o["kind"] not in ("stash", "decor"):
            o["kind"], o["block"] = "decor", []          # nothing to open or break in town
        if any(c in taken or c in world.exits for c in o["block"]):
            o["block"] = [] if o["kind"] != "door" else [c for c in o["block"] if c not in world.exits]
        world.objects.append(o)
        used_cells.add(cell)
    _doors(world, built, data, used_cells)
    # random objects per room
    rng = world.rng
    for lid, rect in world.areas.items():
        if lid in TOWN_IDS:
            continue
        row = info.rows.get(lid) if hasattr(info, "rows") else None
        if not row:
            continue
        groups = []
        for i in range(8):
            grp, prb = _int(row.get("objgrp%d" % i)), _int(row.get("objprb%d" % i))
            if grp and prb and grp in data.groups and data.groups[grp]["items"]:
                groups.append((data.groups[grp], prb))
        if not groups:
            continue
        x0, y0, x1, y1 = rect
        x1, y1 = min(x1, g.w), min(y1, g.h)
        room = 40
        shrines = wells = 0
        for ry in range(y0, y1, room):
            for rx in range(x0, x1, room):
                walk = sum(1 for _ in range(24) if g.walkable(rng.randrange(rx, min(rx + room, x1)),
                                                                rng.randrange(ry, min(ry + room, y1))))
                if walk < 10:
                    continue
                for grp, prb in groups:
                    if rng.randrange(100) >= prb:
                        continue
                    items = grp["items"]
                    oid, density, _ = rng.choices(items, weights=[max(1, p) for _, _, p in items])[0]
                    k = data.kind(oid)
                    if (k == "shrine" and shrines >= 2) or (k == "well" and wells >= 2):
                        continue
                    count = 1 if density == 0 else 1 + rng.randrange(1 + min(3, density // 32))
                    for _ in range(count):
                        o = _place_random(world, data, oid, lid, (rx, ry, min(rx + room, x1), min(ry + room, y1)),
                                          taken, used_cells, clear_of)
                        if o is not None:
                            if o["kind"] == "shrine":
                                shrines += 1
                            elif o["kind"] == "well":
                                wells += 1
    rebuild_blocks(world)


# which door D2 hangs in a doorway (wall tiles with the door orientations 8 = left, 9 = right) by area
DOOR_PAIRS = [((29, 30, 31), (290, 291)), ((28,), (15, 16)), ((33,), (62, 63)), ((34, 35, 36, 37), (294, 295)),
              ((18, 19, 9, 10, 11, 12, 13, 14, 15, 16), (292, 293)), ((27, 32), (23, 24)), ((17,), (13, 14)),
              ((38,), (15, 16)), ((60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72), (91, 92)),
              ((1, 2, 3, 4, 5, 6, 7, 20, 21, 22, 23, 24, 25), (15, 16))]


def door_objects(lid):
    for ids, pair in DOOR_PAIRS:
        if lid in ids:
            return pair
    return None


def _doors(world, built, data, used_cells):
    g = world.grid
    from .acts import TOWN_IDS
    lines = {}           # (orientation, line coordinate, owner) -> set of opening coordinates
    for (tx, ty), orient, owner in getattr(built, "doors", []) or []:
        if owner in TOWN_IDS or door_objects(owner) is None:
            continue
        if orient == 8:                 # west edge of the tile: x fixed
            x = tx * 5
            for y in range(ty * 5, ty * 5 + 5):
                if g.walkable(x, y):
                    lines.setdefault((8, x, owner), set()).add(y)
        else:                           # north edge: y fixed
            y = ty * 5
            for x in range(tx * 5, tx * 5 + 5):
                if g.walkable(x, y):
                    lines.setdefault((9, y, owner), set()).add(x)
    for (orient, line, owner), coords in lines.items():
        run = []
        for v in sorted(coords) + [None]:
            if run and (v is None or v != run[-1] + 1):
                if 2 <= len(run) <= 9:
                    cells = [(line, c) for c in run] if orient == 8 else [(c, line) for c in run]
                    if not any(c in world.exits or c in used_cells for c in cells):
                        oid = door_objects(owner)[0 if orient == 8 else 1]
                        o = make(world, oid, cells[len(cells) // 2], owner, data)
                        if o is not None:
                            o["block"] = cells
                            world.objects.append(o)
                            used_cells.update(cells)
                run = []
            if v is not None:
                run.append(v)


def _free(g, cell, r):
    for d in range(1, r + 1):
        for dx in range(-d, d + 1):
            for dy in range(-d, d + 1):
                c = (cell[0] + dx, cell[1] + dy)
                if g.walkable(*c):
                    return c
    return None


def _place_random(world, data, oid, lid, rect, taken, used_cells, clear_of):
    g, rng = world.grid, world.rng
    x0, y0, x1, y1 = rect
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None
    size = data.size(oid)
    for _ in range(25):
        c = (rng.randrange(x0 + 1, x1 - 1), rng.randrange(y0 + 1, y1 - 1))
        cells = footprint(c, size)
        if not _ring_ok(g, cells):
            continue
        if any(x in taken or x in used_cells or x in world.exits for x in cells):
            continue
        if any(chebyshev(c, u) < 4 for u in used_cells if abs(u[0] - c[0]) < 6):
            continue
        if not clear_of(c, 6):
            continue
        from .actworld import _reachable
        if not _reachable(world, c):
            continue
        o = make(world, oid, c, lid, data)
        if o is None:
            return None
        world.objects.append(o)
        used_cells.update(cells)
        return o
    return None


# ---------------------------------------------------------------- using them
def operate(world, o):
    """Click on a generic object. Returns True if something happened."""
    kind = o["kind"]
    if kind == "door":
        return _door(world, o)
    if kind == "stash":
        world.open_stash = True
        return True
    if o["used"]:
        return False
    if kind in LOOT_KINDS:
        return _loot(world, o)
    if kind == "shrine":
        return _shrine(world, o)
    if kind == "well":
        return _well(world, o)
    return False


def _door(world, o):
    if o.get("open"):
        occ = world.occupied()
        if any(c in occ for c in o["block"]):
            world.log("Something is in the way.", (160, 160, 160))
            return False
        o["open"] = False
        o["mode"] = "NU"
    else:
        o["open"] = True
        o["mode"] = "OP"
        o["op_t"] = None
    rebuild_blocks(world)
    world.emit("object", o)
    return True


def _area_level(world, o):
    info = getattr(world, "info", None)
    try:
        return info.monster_level(o["level"]) if info else 1
    except Exception:
        return 1


def _loot(world, o):
    o["used"] = True
    o["mode"] = "OP"
    o["op_t"] = None
    kind = o["kind"]
    rebuild_blocks(world)
    world.emit("object", o)
    c = world.content
    if c is None:
        return True
    rng = world.rng
    lvl = _area_level(world, o)
    p = world.player
    mf, gf = getattr(p, "mf", 0), getattr(p, "gf", 0)
    drops = []
    if kind == "xbarrel":
        _explode(world, o, lvl)
        return True
    data = data_for(c)
    trap = _int(data.rows.get(o["oid"], {}).get("trapprob")) if data else 0
    if trap and rng.randrange(100) < trap:
        _trap(world, o, lvl)
    if kind in ("weapon_rack", "armor_rack"):
        b = c.pick_base(max(1, lvl), rng, ("weapon",) if kind == "weapon_rack" else ("armor",))
        if b:
            drops.append(c.make_item(b, lvl, rng, c.roll_quality(b, lvl, rng, mf)))
    elif kind == "bookshelf":
        if rng.random() < 0.5:
            code = rng.choice(("tsc", "isc"))
            if code in c.base_by_code:
                drops.append(c.make_item(c.base_by_code[code], lvl, rng))
    else:
        picks, nothing = {"chest": (2, 0.25), "casket": (2, 0.4)}.get(kind, (1, 0.55))
        if o.get("sparkly"):
            picks, nothing = 4, 0.0
        for _ in range(picks):
            it = _pick(c, lvl, rng, mf, gf, nothing)
            if it is not None:
                drops.append(it)
    for it in drops:
        cell = world._drop_cell(o["cell"])
        world.ground.setdefault(cell, []).append(it)
        world.emit("drop", cell, it)
    if not drops and kind in OPEN_WORD:
        world.log("It's empty.", (160, 160, 160))
    return True


def _trap(world, o, lvl):
    """D2's trapped chests: fire, lightning or poison bursts out when you open them."""
    rng = world.rng
    el = rng.choice(("fire", "ltng", "pois", "cold"))
    mis = {"fire": "fireexplode", "ltng": "chargedboltexplode", "pois": "poisonnova", "cold": "iceexplode"}[el]
    world.emit("explosion", o["cell"], mis)
    world.log("It was trapped!", (255, 140, 60))
    p = world.player
    if p.alive and chebyshev(p.pos, o["cell"]) <= 3:
        world.elem_hit(p, el, 1 + lvl, 4 + lvl * 3, None, 75, show=False)


def _pick(c, lvl, rng, mf, gf, nothing):
    r = rng.random()
    if r < nothing:
        return None
    r = (r - nothing) / max(0.01, 1 - nothing)
    if r < 0.42:
        return c.make_gold(lvl, rng, gf)
    if r < 0.70:
        return c.make_potion(lvl, rng)
    if r < 0.75:
        return c.make_gem_or_rune(lvl, rng)
    b = c.pick_base(max(1, lvl), rng)
    if not b:
        return None
    return c.make_item(b, lvl, rng, c.roll_quality(b, lvl, rng, mf))


def _explode(world, o, lvl):
    lo, hi = 2 + lvl, 6 + lvl * 3
    world.emit("explosion", o["cell"])
    world.log("The barrel explodes!", (255, 140, 60))
    for u in list(world.monsters) + [world.player]:
        if u.alive and getattr(u, "ai", "") != "npc" and chebyshev(u.pos, o["cell"]) <= 3:
            world.elem_hit(u, "fire", lo, hi, None, show=False)


def _buff(world, title, stats, frames):
    p = world.player
    turns = max(5, frames // FRAMES_PER_TURN)
    for k in list(p.buffs):
        if p.buffs[k].get("shrine"):
            del p.buffs[k]              # D2: one shrine effect at a time
    p.buffs["shrine:" + title] = {"turns": turns, "stats": stats, "title": title, "shrine": True}
    p.recalc()


def _shrine(world, o):
    data = data_for(world.content)
    code = o.get("shrine", 1)
    s = data.shrines.get(code, dict(arg0=0, arg1=0, frames=2400))
    p = world.player
    o["used"] = True
    o["mode"] = "OP"
    o["op_t"] = None
    world.emit("object", o)
    rng = world.rng
    name = SHRINE_NAMES.get(code, "Shrine")
    gold = (255, 215, 90)
    if code == 1:
        p.hp, p.mana = p.max_hp, p.max_mana
        world.log("Refilling Shrine: you are healed.", gold)
    elif code == 2:
        p.hp = p.max_hp
        world.log("Health Shrine: you are healed.", gold)
    elif code == 3:
        p.mana = p.max_mana
        world.log("Mana Shrine: your mana is restored.", gold)
    elif code == 6:
        _buff(world, "Armor Shrine", {"def_pct": s["arg0"] or 100}, s["frames"])
        world.log("Armor Shrine: +%d%% defense." % (s["arg0"] or 100), gold)
    elif code == 7:
        _buff(world, "Combat Shrine", {"ar_pct": s["arg0"] or 200, "ed": s["arg1"] or 200}, s["frames"])
        world.log("Combat Shrine: +200% damage and attack rating.", gold)
    elif code in (8, 9, 10, 11):
        el = {8: "fire", 9: "cold", 10: "ltng", 11: "pois"}[code]
        _buff(world, name, {"res_" + el: s["arg0"] or 75, "maxres_" + el: 0}, s["frames"])
        world.log("%s: +%d%% resistance." % (name, s["arg0"] or 75), gold)
    elif code == 12:
        _buff(world, "Skill Shrine", {"all_skills": s["arg0"] or 2}, s["frames"])
        world.log("Skill Shrine: +2 to all skills.", gold)
    elif code == 13:
        _buff(world, "Mana Recharge Shrine", {"mana_regen_pct": s["arg0"] or 400}, s["frames"])
        world.log("Mana Recharge Shrine: much faster mana regeneration.", gold)
    elif code == 14:
        _buff(world, "Stamina Shrine", {"stamina_inf": 1}, s["frames"])
        world.log("Stamina Shrine.", gold)
    elif code == 15:
        _buff(world, "Experience Shrine", {"xp_pct": s["arg0"] or 50}, s["frames"])
        world.log("Experience Shrine: +50% experience.", gold)
    elif code == 17:
        world.town_portal()
        world.log("Portal Shrine: a portal to town opens.", gold)
    elif code == 18:
        _gem_shrine(world, o)
    elif code == 19:
        world.log("Fire Shrine!", (255, 120, 60))
        lvl = _area_level(world, o)
        for u in list(world.monsters) + [p]:
            if u.alive and getattr(u, "ai", "") != "npc" and chebyshev(u.pos, o["cell"]) <= 6:
                world.elem_hit(u, "fire", 1 + lvl, 4 + lvl * 2, None, show=False)
        world.emit("explosion", o["cell"])
    elif code == 20:
        cand = [m for m in world.monsters if m.alive and not m.ally and getattr(m, "ai", "") != "npc"
                and not getattr(m, "boss", None) and not getattr(m, "unique", False)]
        if cand:
            m = min(cand, key=lambda m: chebyshev(m.pos, o["cell"]))
            try:
                from . import monmods
                monmods.make_unique(world, m)
            except ImportError:
                m.max_hp, m.hp = m.max_hp * 3, m.hp * 3
                m.unique = True
            world.log("Monster Shrine: %s grows stronger!" % m.name, (255, 120, 60))
        else:
            world.log("Monster Shrine.", gold)
    elif code in (21, 22):
        _potion_shrine(world, o, "exploding" if code == 21 else "poison", s)
    else:
        world.log(name + ".", gold)
    p.recalc()
    return True


def _gem_shrine(world, o):
    c = world.content
    p = world.player
    gems = [it for it in p.inventory if isinstance(getattr(it, "gem", None), tuple) and it.gem and it.gem[0] not in ("rune", "jewel")]
    if gems and c is not None and hasattr(c, "upgrade_gem"):
        g = world.rng.choice(gems)
        if c.upgrade_gem(g):
            world.log("Gem Shrine: your %s grows brighter." % g.name, (255, 215, 90))
            return
    if c is not None:
        it = c.make_gem_or_rune(_area_level(world, o) + 10, world.rng)
        if it is not None:
            cell = world._drop_cell(o["cell"])
            world.ground.setdefault(cell, []).append(it)
            world.emit("drop", cell, it)
    world.log("Gem Shrine.", (255, 215, 90))


def _potion_shrine(world, o, what, s):
    c = world.content
    n = world.rng.randint(max(1, s.get("arg0") or 5), max(1, s.get("arg1") or 10))
    world.log(("Exploding" if what == "exploding" else "Poison") + " Shrine: potions spill out!", (255, 215, 90))
    if c is None:
        return
    codes = ("opl", "opm", "ops") if what == "exploding" else ("gpl", "gpm", "gps")
    lvl = _area_level(world, o)
    code = codes[0] if lvl > 20 else (codes[1] if lvl > 10 else codes[2])
    base = c.base_by_code.get(code)
    if base is None:
        return
    for _ in range(n):
        it = c.make_item(base, lvl, world.rng)
        cell = world._drop_cell(o["cell"])
        world.ground.setdefault(cell, []).append(it)
        world.emit("drop", cell, it)


def _well(world, o):
    p = world.player
    o["used"] = True
    o["mode"] = "OP"
    o["op_t"] = None
    p.hp = p.max_hp
    for k in ("poison", "pois", "poisoned"):
        p.effects.pop(k, None)
    world.emit("object", o)
    world.log("You drink from the well. Your wounds close.", (255, 215, 90))
    return True


def tooltip(o):
    k = o["kind"]
    if k == "door":
        return [o["name"], "Click to " + ("close" if o.get("open") else "open")]
    if k == "stash":
        return ["Stash", "Click to open"]
    return [o["name"]]


def clickable(o):
    if not o.get("generic"):
        return True
    k = o["kind"]
    if k == "decor":
        return False
    if k in ("door", "stash"):
        return True
    return not o["used"]
