"""Hirelings like D2's: they level up from kills (Hireling.txt stats per level, up to your level),
wear a helm, body armor and the weapon their kind can use (and a shield for Iron Wolves),
keep their aura / skills, die and are resurrected for gold.

    p.merc = dict(kind, hid, name, level, xp, dead, items={slot: Item})
    spawn(world, kind, free)        hire (or bring back) the hireling as an ally unit
    gain_xp(world, amount)          after a kill
    can_wear(merc, item, slot)      what a hireling of this kind can put on
"""
from .grid import chebyshev

KINDS = {"rogue": dict(hireling="Rogue Scout", ids=(0, 1), mon="roguehire", wtypes=("bow",), shield=False,
                       style="ranged", seller="Kashya"),
         "act2hire": dict(hireling="Desert Mercenary", ids=(6, 7, 8), mon="act2hire", wtypes=("spea", "pole"),
                          shield=False, style="melee", seller="Greiz"),
         "act3hire": dict(hireling="Eastern Sorceror", ids=(15, 16, 17), mon="act3hire", wtypes=("swor",),
                          shield=True, style="ranged", seller="Asheara"),
         "act5hire1": dict(hireling="Barbarian", ids=(24,), mon="act5hire1", wtypes=("swor",), shield=False,
                           style="melee", seller="Qual-Kehk")}
TITLES = {"rogue": "Rogue Scout", "act2hire": "Desert Guard", "act3hire": "Iron Wolf", "act5hire1": "Barbarian"}
SLOTS = ("helm", "armor", "weapon", "shield")
AURA_SKILLS = {"Prayer", "Defiance", "Blessed Aim", "Might", "Thorns", "Holy Freeze"}
ELEM_OF = {"Fire Arrow": "fire", "Cold Arrow": "cold", "Fire Ball": "fire", "Inferno": "fire",
           "Glacial Spike": "cold", "Ice Blast": "cold", "Charged Bolt": "ltng", "Lightning": "ltng"}


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def _rows(content):
    rows = getattr(content, "_hire_rows", None)
    if rows is None:
        from d2.source import read_table
        rows = {}
        try:
            for r in read_table(content.src, "Hireling"):
                if r.get("difficulty") == "1" and r.get("version") == "100":
                    rows.setdefault(_int(r.get("id")), []).append(r)
        except Exception:
            pass
        for v in rows.values():
            v.sort(key=lambda r: _int(r.get("level")))
        content._hire_rows = rows
    return rows


def row_for(content, hid, level):
    lst = _rows(content).get(hid) or []
    if not lst:
        return None
    best = lst[0]
    for r in lst:
        if _int(r.get("level")) <= level:
            best = r
    return best


def stats(content, merc):
    """Life, defense, attack rating, damage, resistances of a hireling at its level, with its gear."""
    L = merc["level"]
    r = row_for(content, merc["hid"], L)
    if r is None:
        return None
    d = max(0, L - _int(r.get("level")))
    g = lambda k: _int(r.get(k))
    st = dict(hp=g("hp") + g("hp/lvl") * d, defense=g("defense") + g("def/lvl") * d,
              str=g("str") + g("str/lvl") * d // 8, dex=g("dex") + g("dex/lvl") * d // 8,
              ar=g("ar") + g("ar/lvl") * d, dmg=[g("dmg-min") + g("dmg/lvl") * d // 8, g("dmg-max") + g("dmg/lvl") * d // 8],
              res=g("resist") + g("resist/lvl") * d // 4, skills=[], elem={}, leech=0, ap=0)
    for i in range(1, 6):
        sk = r.get("skill%d" % i)
        if sk:
            lvl = max(1, g("level%d" % i) + g("lvlperlvl%d" % i) * d // 32)
            st["skills"].append((sk, lvl))
    items = [it for it in (merc.get("items") or {}).values() if it is not None and wearable(merc, it, st)]
    ed = 0
    lifep = 0
    for it in items:
        mods = it.mods or {}
        st["defense"] += it.defense or 0
        st["hp"] += mods.get("life", 0) if isinstance(mods.get("life", 0), int) else 0
        lifep += mods.get("life_pct", 0) if isinstance(mods.get("life_pct", 0), int) else 0
        st["ar"] += mods.get("ar", 0) if isinstance(mods.get("ar", 0), int) else 0
        ed += mods.get("ed", 0) if isinstance(mods.get("ed", 0), int) else 0
        st["res"] += mods.get("res_all", 0) if isinstance(mods.get("res_all", 0), int) else 0
        st["leech"] += mods.get("ll", 0) if isinstance(mods.get("ll", 0), int) else 0
        st["ap"] += (mods.get("ias", 0) if isinstance(mods.get("ias", 0), int) else 0) // 25
        for el in ("fire", "cold", "ltng", "pois"):
            v = mods.get(el + "_dmg")
            if isinstance(v, tuple):
                a = st["elem"].get(el, (0, 0))
                st["elem"][el] = (a[0] + v[0], a[1] + v[1])
        if it.dmg and (merc.get("items") or {}).get("weapon") is it:
            st["dmg"][0] += it.dmg[0]
            st["dmg"][1] += it.dmg[1]
    st["dmg"] = (max(1, st["dmg"][0] * (100 + ed) // 100), max(2, st["dmg"][1] * (100 + ed) // 100))
    st["hp"] = st["hp"] * (100 + lifep) // 100
    st["res"] = min(75, st["res"])
    return st


def wearable(merc, it, st=None):
    """Requirements met (hirelings have their own strength / dexterity / level)."""
    if it.mod_list is None:
        return True
    if st is None:
        st = dict(str=999, dex=999)
    return merc["level"] >= it.levelreq and st["str"] >= it.reqstr and st["dex"] >= it.reqdex


def can_wear(merc, it, slot):
    """The right kind of item for this hireling and slot."""
    if it is None or it.kind != "equip":
        return False
    k = KINDS.get(merc["kind"], {})
    anc = set(it.base.get("ancestors", ())) if isinstance(getattr(it, "base", None), dict) else set()
    if slot == "helm":
        return it.slot == "helm" and not (anc & {"phlm", "pelt", "head"})      # no class-only helms
    if slot == "armor":
        return it.slot == "armor"
    if slot == "weapon":
        if it.slot != "weapon" or not (anc & set(k.get("wtypes", ()))):
            return False
        if merc["kind"] == "act3hire" and it.two_handed:
            return False
        return True
    if slot == "shield":
        return k.get("shield", False) and it.slot == "shield" and not (anc & {"ashd", "head"})
    return False


def new_merc(world, kind):
    k = KINDS[kind]
    rng = world.rng
    p = world.player
    names = None
    c = world.content
    hid = rng.choice(k["ids"])
    r = row_for(c, hid, 1)
    if r is not None and getattr(c, "strings", None) is not None:
        a, b = r.get("namefirst", ""), r.get("namelast", "")
        try:
            lo, hi = int(a[-2:]), int(b[-2:])
            pre = a[:-2]
            names = [c.strings.get("%s%02d" % (pre, i), None) for i in range(lo, hi + 1)]
            names = [n for n in names if n and not n.startswith(pre)]
        except ValueError:
            names = None
    lvl0 = _int(r.get("level"), 1) if r is not None else 1
    return dict(kind=kind, hid=hid, name=rng.choice(names) if names else TITLES.get(kind, "Hireling"),
                level=max(1, min(p.level, max(lvl0, p.level - 2))), xp=0, dead=False, items={})


def xp_needed(content, merc):
    r = row_for(content, merc["hid"], merc["level"])
    per = _int(r.get("exp/lvl"), 100) if r is not None else 100
    L = merc["level"]
    return per * L * L * (L + 1) // 10


def spawn(world, kind=None, free=True):
    """The hireling as an ally next to you (from p.merc; a new one if there is none)."""
    p = world.player
    c = world.content
    if c is None:
        return None
    merc = getattr(p, "merc", None)
    if merc is None or (kind and merc["kind"] != kind and not free):
        merc = p.merc = new_merc(world, kind or "rogue")
    if merc.get("dead"):
        return None
    if any(getattr(a, "hireling", False) and a.alive for a in world.allies()):
        return None
    k = KINDS[merc["kind"]]
    key = c.monstats_key(k["mon"]) or c.monstats_key("rogue1")
    if not key:
        return None
    st = stats(c, merc)
    t = dict(c.monster_template(key, level=merc["level"]))
    if st is not None:
        t["hp"] = (st["hp"], st["hp"])
        t["dmg"] = st["dmg"]
        t["ar"] = st["ar"]
        t["df"] = st["defense"]
        t["res"] = {"fire": st["res"], "cold": st["res"], "ltng": st["res"], "pois": st["res"]}
    t["name"] = merc["name"]
    t["ai"] = "ranged" if k["style"] == "ranged" else "melee"
    t["rng"] = 8 if k["style"] == "ranged" else 1
    t["skills"] = []
    from .units import Monster
    occ = world.occupied()
    spots = [(p.x + dx, p.y + dy) for dx in (-1, 1, 0, -2, 2) for dy in (-1, 1, 0, -2, 2)]
    cell = next((s for s in spots if world.grid.walkable(*s) and s not in occ), None)
    if cell is None:
        return None
    m = Monster(merc["kind"], cell[0], cell[1], level=merc["level"], rng=world.rng, template=t)
    m.level = merc["level"]
    world._make_ally(m)
    if k["style"] == "ranged":
        m.ai = "ally_ranged"
        m.range = 8
    m.name = merc["name"]
    m.summon_skill = "hireling"
    m.hireling = True
    p.has_hireling = True
    p.hireling_kind = merc["kind"]
    _apply_skills(m, st)
    world.monsters.append(m)
    world.emit("resurrect", m)
    return m


def _apply_skills(m, st):
    m.hit_elem = {}
    m.merc_aura = None
    m.hit_stun = 0
    if st is None:
        return
    for el, v in st["elem"].items():
        m.hit_elem[el] = v
    m.leech = st["leech"]
    m.max_ap = m.ap = m.max_ap + st["ap"]
    for name, lvl in st["skills"]:
        if name in AURA_SKILLS:
            m.merc_aura = (name, lvl)
        elif name in ELEM_OF:
            el = ELEM_OF[name]
            lo, hi = m.dmg
            a = m.hit_elem.get(el, (0, 0))
            m.hit_elem[el] = (a[0] + lo // 2 + lvl, a[1] + hi // 2 + lvl * 3)
        elif name in ("Stun", "Bash"):
            m.hit_stun = max(m.hit_stun, 15 + lvl)


def refresh_unit(world):
    """Gear or level changed: update the hireling on the map."""
    p = world.player
    merc = getattr(p, "merc", None)
    if merc is None:
        return
    for a in world.allies():
        if getattr(a, "hireling", False) and a.alive:
            st = stats(world.content, merc)
            if st is None:
                return
            frac = a.hp / float(max(1, a.max_hp))
            a.max_hp = st["hp"]
            a.hp = max(1, int(st["hp"] * frac))
            a.dmg, a.ar, a.defense, a.level = st["dmg"], st["ar"], st["defense"], merc["level"]
            a.res = {"fire": st["res"], "cold": st["res"], "ltng": st["res"], "pois": st["res"], "phys": 0, "mag": 0}
            base_ap = a.max_ap - getattr(a, "_merc_ap", 0)
            a._merc_ap = st["ap"]
            _apply_skills(a, st)
            a.max_ap = base_ap + st["ap"]
            a.name = merc["name"]


def gain_xp(world, amount):
    p = world.player
    merc = getattr(p, "merc", None)
    if merc is None or merc.get("dead") or amount <= 0:
        return
    if not any(getattr(a, "hireling", False) and a.alive for a in world.allies()):
        return
    merc["xp"] += amount
    up = False
    while merc["level"] < min(98, p.level) and merc["xp"] >= xp_needed(world.content, merc):
        merc["xp"] -= xp_needed(world.content, merc)
        merc["level"] += 1
        up = True
    if up:
        world.log("%s is now level %d." % (merc["name"], merc["level"]), (199, 179, 119))
        refresh_unit(world)


def on_death(world, m):
    p = world.player
    merc = getattr(p, "merc", None)
    if merc is not None and getattr(m, "hireling", False):
        merc["dead"] = True
        world.log("%s has died. %s can bring them back." % (merc["name"], KINDS[merc["kind"]]["seller"]), (255, 80, 80))


def resurrect_cost(merc):
    return min(50000, 50 + merc["level"] * merc["level"] * 5)


def resurrect(world):
    p = world.player
    merc = getattr(p, "merc", None)
    if merc is None or not merc.get("dead"):
        return False
    cost = resurrect_cost(merc)
    if p.gold < cost:
        world.log("Resurrecting %s costs %d gold." % (merc["name"], cost), (160, 160, 160))
        return False
    p.gold -= cost
    merc["dead"] = False
    spawn(world, merc["kind"])
    world.log("%s is back at your side (%d gold)." % (merc["name"], cost), (199, 179, 119))
    return True


def equip(world, slot, item):
    """Put an item on the hireling; returns what came off (or the item itself if it doesn't fit)."""
    merc = world.player.merc
    if not can_wear(merc, item, slot):
        world.log("%s can't use that." % merc["name"], (160, 160, 160))
        return item
    st = stats(world.content, dict(merc, items={}))
    if item.mod_list is not None and not wearable(merc, item, st):
        world.log("%s doesn't meet the requirements." % merc["name"], (160, 160, 160))
        return item
    old = merc["items"].get(slot)
    merc["items"][slot] = item
    if slot == "weapon" and item.two_handed and merc["items"].get("shield"):
        world.log("Two-handed: take the shield off first.", (160, 160, 160))
        merc["items"][slot] = old
        return item
    refresh_unit(world)
    return old


def unequip(world, slot):
    merc = world.player.merc
    it = merc["items"].pop(slot, None)
    refresh_unit(world)
    return it


def aura(world):
    """(aura, level) the hireling gives you (Desert Guards' Prayer / Defiance / Blessed Aim)."""
    for a in world.allies():
        if getattr(a, "hireling", False) and a.alive and getattr(a, "merc_aura", None):
            if chebyshev(a.pos, world.player.pos) <= 12:
                return a.merc_aura
    return None
