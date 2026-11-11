"""Saving and loading characters (like D2: the hero is saved, the maps are new each game).

Saves are small JSON files in the "saves" folder next to the game.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR = os.path.join(ROOT, "saves")
NORMAL_DIR = SAVE_DIR


def set_mode(mode):
    """Normal and tactics mode have separate heroes: tactics heroes live in saves/tactics."""
    global SAVE_DIR
    base = NORMAL_DIR
    SAVE_DIR = os.path.join(base, "tactics") if mode == "tactics" else base
    return SAVE_DIR


SHARED_STASH = "_stash.json"         # one stash for every character on this install


def shared_stash_path():
    """The chest is account wide: it sits beside the saves, not inside a mode's folder."""
    return os.path.join(NORMAL_DIR, SHARED_STASH)


def save_shared_stash(stash):
    os.makedirs(NORMAL_DIR, exist_ok=True)
    path = shared_stash_path()
    with open(path + ".tmp", "w") as f:
        json.dump(_stash_dict(stash), f, indent=1)
    os.replace(path + ".tmp", path)


def load_shared_stash(content):
    """The chest every character shares (a new, empty one the first time)."""
    from .cube import make_stash, cube_add, stash_tab
    st = make_stash()
    try:
        with open(shared_stash_path()) as f:
            sd = json.load(f)
    except Exception:
        return st
    st.gold = sd.get("gold", 0) or 0
    st.bank = {k: int(v) for k, v in (sd.get("bank") or {}).items() if int(v) > 0}
    for i, page in enumerate((sd.get("pages") or [])[:len(st.pages)]):
        stash_tab(st, i + 1)
        for d in page or []:
            it = _item_from(d, content)
            if it is not None:
                if getattr(it, "cube_pos", None) is not None:
                    st.contents.append(it)
                else:
                    cube_add(st, it)
    stash_tab(st, 1)
    return st


def _safe(name):
    return re.sub(r"[^A-Za-z0-9_-]", "_", name) or "hero"


def _stash_dict(st):
    if st is None:
        return dict(gold=0, items=[])
    pages = getattr(st, "pages", None)
    if pages is None:
        pages = [getattr(st, "contents", None) or []]
    return dict(gold=getattr(st, "gold", 0), bank=dict(getattr(st, "bank", {}) or {}),
                pages=[[_item_dict(it) for it in page] for page in pages])


def _item_dict(it):
    if it is None:
        return None
    mods = {k: (list(v) if isinstance(v, tuple) else v) for k, v in (it.mods or {}).items()}
    ml = None
    if it.mod_list is not None:
        ml = [[e[0], list(e[1]) if isinstance(e[1], tuple) else e[1]] + ([e[2]] if len(e) > 2 and e[2] else [])
              for e in it.mod_list]
    return dict(name=it.name, code=it.code, slot=it.slot, rarity=it.rarity, kind=it.kind, mods=mods, mod_list=ml,
                defense=it.defense, dmg=list(it.dmg) if it.dmg else None, ap=it.ap, amount=it.amount,
                potion=getattr(it, "potion", "heal"), inv_pos=list(it.inv_pos) if getattr(it, "inv_pos", None) else None,
                levelreq=it.levelreq, sockets=getattr(it, "sockets", 0),
                socketed=[_item_dict(x) for x in getattr(it, "socketed", []) or []],
                runeword=getattr(it, "runeword", None), identified=getattr(it, "identified", True),
                use=getattr(it, "use", None), quantity=getattr(it, "quantity", 0),
                gem=list(it.gem) if isinstance(getattr(it, "gem", None), (list, tuple)) else getattr(it, "gem", None),
                affixes=[dict(name=a.get("name", ""), multiply=a.get("multiply", 0), add=a.get("add", 0))
                         for a in getattr(it, "affixes", []) or []], extra_lines=list(getattr(it, "extra_lines", []) or []),
                base_defense=getattr(it, "base_defense", None), ilvl=getattr(it, "ilvl", None),
                contents=[_item_dict(x) for x in it.contents] if getattr(it, "contents", None) is not None else None,
                cube_pos=list(it.cube_pos) if getattr(it, "cube_pos", None) else None,
                unique_name=getattr(it, "unique_name", None), set_item=getattr(it, "set_item", None),
                jewel_props=[list(p) for p in getattr(it, "jewel_props", []) or []] or None,
                invfile=getattr(it, "invfile", "") or "",
                ethereal=bool(getattr(it, "ethereal", False)), grade=getattr(it, "grade", "") or "",
                charm=bool(getattr(it, "charm", False)),
                charges={k: list(v) for k, v in (getattr(it, "charges", None) or {}).items()} or None,
                belt_col=getattr(it, "belt_col", None),
                infused=list(it.infused) if getattr(it, "infused", None) else None,
                base_name=getattr(it, "_base_name", None))


def _item_from(d, content):
    if d is None:
        return None
    from .items import Item
    mods = {k: (tuple(v) if isinstance(v, list) else v) for k, v in d.get("mods", {}).items()}
    it = Item(d["name"], d["code"], d.get("slot"), d.get("rarity", "normal"), mods,
              dmg=tuple(d["dmg"]) if d.get("dmg") else None, ap=d.get("ap"), defense=d.get("defense", 0),
              amount=d.get("amount", 0), kind=d.get("kind", "equip"))
    it.potion = d.get("potion", "heal")
    it.belt_col = d.get("belt_col")
    if d.get("infused"):
        it.infused = tuple(d["infused"])
        it._base_name = d.get("base_name") or it.name
    if d.get("mod_list") is not None:
        it.mod_list = [tuple([e[0], tuple(e[1]) if isinstance(e[1], list) else e[1]] + list(e[2:]))
                       for e in d["mod_list"]]
    base = getattr(content, "base_by_code", {}).get(d["code"]) if content is not None else None
    if base is not None:
        it.base = base
        if it.mod_list is None and it.kind == "equip":
            it.mod_list = []
        it.reqstr, it.reqdex = base.get("reqstr", 0), base.get("reqdex", 0)
        it.invfile, it.flippy = base.get("invfile", ""), base.get("flippyfile", "")
        it.invw, it.invh = base.get("invw", 1), base.get("invh", 1)
        it.two_handed = base.get("two_handed", False)
        it.block = base.get("block", 0)
        it.gfx = base.get("gfx", "")
        it.wclass = base.get("wclass", "")
        it.look = base.get("look")
        it.strbonus, it.dexbonus = base.get("strbonus", 0), base.get("dexbonus", 0)
    if d.get("kind") == "gold":
        it.invfile, it.flippy = "invgld1", "flpgld"
    it.levelreq = d.get("levelreq", 0)
    it.sockets = d.get("sockets", 0) or 0
    it.socketed = [x for x in (_item_from(sd, content) for sd in d.get("socketed", []) or []) if x is not None]
    it.runeword = d.get("runeword")
    it.identified = d.get("identified", True)
    it.use = d.get("use")
    it.quantity = d.get("quantity", 0) or 0
    g = d.get("gem")
    it.gem = tuple(g) if isinstance(g, list) else g
    it.affixes = list(d.get("affixes", []) or [])
    it.extra_lines = list(d.get("extra_lines", []) or [])
    rules = getattr(content, "sockets", None) if content is not None else None
    if it.gem is not None and rules is not None:
        try:
            it.filler_lines = rules.describe_filler(it)
            it.rune_letter = rules.letter(it)
        except Exception:
            pass
    if d.get("base_defense") is not None:
        it.base_defense = d["base_defense"]
    if d.get("inv_pos"):
        it.inv_pos = tuple(d["inv_pos"])
    if d.get("cube_pos"):
        it.cube_pos = tuple(d["cube_pos"])
    if d.get("ilvl"):
        it.ilvl = d["ilvl"]
    if d.get("invfile"):
        it.invfile = d["invfile"]          # uniques, sets and jewels have their own pictures
    if d.get("unique_name"):
        it.unique_name = d["unique_name"]
    if d.get("set_item") and content is not None and hasattr(content, "attach_set"):
        content._load_uniques()
        si = content.set_item_by_index.get(d["set_item"])
        if si is not None:
            content.attach_set(it, si)
    if d.get("ethereal"):
        it.ethereal = True
    if d.get("grade"):
        it.grade = d["grade"]
    if d.get("charges"):
        it.charges = {k: list(v) for k, v in d["charges"].items()}
    if d.get("charm"):
        it.charm = True
        it.slot = None
    if d.get("jewel_props"):
        it.jewel_props = [tuple(p) for p in d["jewel_props"]]
        it.slot = None
    if d.get("contents") is not None or it.code == "box":
        it.contents = [x for x in (_item_from(c, content) for c in d.get("contents") or []) if x is not None]
    return it


# what D2 keeps separately for each difficulty (quests, waypoints, Cain, the act you are in...)
PER_DIFF = ("quests", "waypoints", "visited", "cain", "act", "quest_stats", "boss_kills", "map_explored",
            "tracked_quest", "cairn_order", "rift_depth")
DIFFICULTIES = ("normal", "nightmare", "hell")


def unlocked(data):
    """The difficulties a saved hero may play: Normal, + Nightmare once Baal fell in Normal, + Hell
    once he fell in Nightmare."""
    got = list(data.get("unlocked") or ["normal"])
    if "unlocked" not in data and (data.get("quests") or {}).get("baal") in ("cleared", "done"):
        nxt = {"normal": "nightmare", "nightmare": "hell"}.get(data.get("difficulty") or "normal")
        if nxt:
            got.append(nxt)                  # (saves from before difficulties were chosen in the game)
    return [d for d in DIFFICULTIES if d in got]


def switch_difficulty(data, new):
    """The save, set up to play `new`: the current difficulty's progress is put aside and the other
    one's taken out (a fresh start the first time: Act 1, no quests, only the Encampment's waypoint)."""
    cur = data.get("difficulty") or "normal"
    if new == cur:
        return data
    d = dict(data)
    state = dict(d.get("diff_state") or {})
    state[cur] = {k: d.get(k) for k in PER_DIFF}
    fresh = dict(quests={}, waypoints=[1], visited=[1], cain=False, act=1, quest_stats={}, boss_kills=[],
                 map_explored={}, tracked_quest=None, cairn_order=None, rift_depth=0)
    d.update(state.pop(new, None) or fresh)
    d["diff_state"] = state
    d["difficulty"] = new
    d["unlocked"] = unlocked(data)
    return d


# what tactics mode keeps apart from the normal game: its own quests, waypoints, acts and difficulties
# (the hero itself - level, skills, gear, gold, stash - is the same hero in both modes)
PER_MODE = PER_DIFF + ("difficulty", "diff_state", "unlocked")


def switch_mode(data, new):
    """The save, set up to play game mode `new` ("normal" or "tactics"): the other mode's progress
    is put aside (a fresh Act 1 in Normal difficulty the first time)."""
    cur = data.get("mode") or "normal"
    if new == cur:
        return data
    d = dict(data)
    state = dict(d.get("mode_state") or {})
    state[cur] = {k: d.get(k) for k in PER_MODE}
    fresh = dict(quests={}, waypoints=[1], visited=[1], cain=False, act=1, quest_stats={}, boss_kills=[],
                 map_explored={}, tracked_quest=None, cairn_order=None, rift_depth=0, difficulty="normal",
                 diff_state={}, unlocked=["normal"])
    d.update(state.pop(new, None) or fresh)
    d["mode_state"] = state
    d["mode"] = new
    return d


def save_character(player, difficulty="normal"):
    """Write the hero to saves/<name>.json. Returns the path."""
    os.makedirs(SAVE_DIR, exist_ok=True)
    p = player
    data = dict(
        version=1, name=p.name, cls=p.cls, level=p.level, xp=p.xp, gold=p.gold,
        difficulty=getattr(p, "difficulty", None) or difficulty,
        unlocked=list(getattr(p, "diff_unlocked", None) or ["normal"]),
        diff_state=dict(getattr(p, "diff_state", None) or {}),
        stats=[p.base_str, p.base_dex, p.base_vit, p.base_eng], stat_points=p.stat_points,
        skills=dict(p.skills.levels), skill_points=p.skills.points, right_skill=p.right_skill, left_skill=getattr(p, "left_skill", None),
        aura=getattr(p, "active_aura", None),
        hotkeys=dict(getattr(p, "hotkeys", None) or {}),
        boss_kills=list(getattr(p, "boss_kills", []) or []),
        tracked_quest=getattr(p, "tracked_quest", None),
        qol=dict(getattr(p, "qol", None) or {}),
        imbues=dict(getattr(p, "imbues", None) or {}),
        weapon_set=getattr(p, "weapon_set", 0),
        rift_seed=getattr(p, "rift_seed", None),
        stash_merged=bool(getattr(p, "stash_merged", False)),
        heard=sorted(getattr(p, "heard", None) or ()),
        rift_mods=getattr(p, "rift_mods", None),
        rift_map_depth=getattr(p, "rift_map_depth", None),
        swap_gear={k: _item_dict(v) for k, v in (getattr(p, "swap_gear", None) or {}).items()},
        set_skills={str(k): list(v) for k, v in (getattr(p, "set_skills", None) or {}).items()},
        quests=dict(getattr(p, "quests", {})), waypoints=sorted(getattr(p, "waypoints", {1})),
        visited=sorted(getattr(p, "visited", {1})), cain=bool(getattr(p, "cain_rescued", False)),
        hireling=bool(getattr(p, "has_hireling", False)),
        hireling_kind=getattr(p, "hireling_kind", ""), map_seed=getattr(p, "map_seed", None),
        rift_depth=int(getattr(p, "rift_depth", 0) or 0),
        cairn_order=getattr(p, "cairn_order", None), map_explored=dict(getattr(p, "map_explored", None) or {}), quest_stats=dict(getattr(p, "quest_stats", {}) or {}), act=int(getattr(p, "current_act", 1) or 1),
        equipment={k: _item_dict(v) for k, v in p.equipment.items()},
        inventory=[_item_dict(it) for it in p.inventory], belt=[_item_dict(it) for it in p.belt],
        merc=(dict(kind=p.merc["kind"], hid=p.merc["hid"], name=p.merc["name"], level=p.merc["level"],
                   xp=p.merc["xp"], dead=bool(p.merc.get("dead")),
                   items={k: _item_dict(v) for k, v in (p.merc.get("items") or {}).items() if v is not None})
              if getattr(p, "merc", None) else None),
        stash=_stash_dict(getattr(p, "stash", None)),
        belt_unlocks=list(getattr(p, "belt_unlocks", None) or []),
        mode=getattr(p, "mode", "normal") or "normal",
        mode_state=dict(getattr(p, "mode_state", None) or {}),
    )
    path = os.path.join(SAVE_DIR, _safe(p.name) + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)
    return path


def delete_character(name):
    """Delete a hero: the save is moved to saves/deleted (move it back to undo)."""
    path = os.path.join(SAVE_DIR, _safe(name) + ".json")
    if not os.path.isfile(path):
        return False
    trash = os.path.join(SAVE_DIR, "deleted")
    os.makedirs(trash, exist_ok=True)
    dest = os.path.join(trash, _safe(name) + ".json")
    n = 1
    while os.path.exists(dest):
        n += 1
        dest = os.path.join(trash, "%s (%d).json" % (_safe(name), n))
    os.replace(path, dest)
    return True


def list_saves():
    out = []
    if not os.path.isdir(SAVE_DIR):
        return out
    for fn in sorted(os.listdir(SAVE_DIR)):
        if not fn.endswith(".json") or fn.startswith("_"):
            continue
        try:
            with open(os.path.join(SAVE_DIR, fn)) as f:
                d = json.load(f)
            from .units import CLASS_STATS
            if d.get("cls", "bar") not in CLASS_STATS:
                continue                 # (a hero of a class this version doesn't have)
            out.append(d)
        except Exception:
            continue
    out.sort(key=lambda d: -d.get("level", 1))
    return out


def build_player(data, content):
    """A Player from saved data."""
    from .skills import load_tree
    from .units import Player
    cls = data.get("cls", "bar")
    tree = load_tree(content.src, cls, getattr(content, "strings", None)) if content else None
    p = Player(0, 0, cls=cls, name=data.get("name"), tree=tree)
    p.level = data.get("level", 1)
    p.xp = data.get("xp", 0)
    p.gold = data.get("gold", 0)
    st = data.get("stats")
    if st:
        p.base_str, p.base_dex, p.base_vit, p.base_eng = st
    p.stat_points = data.get("stat_points", 0)
    p.skills.levels = {k: v for k, v in data.get("skills", {}).items() if k in p.skills.tree}
    p.skills.points = data.get("skill_points", 0)
    p.right_skill = data.get("right_skill") if (data.get("right_skill") in p.skills.tree
                                                or data.get("right_skill") == "throw") else None
    p.quests = dict(data.get("quests", {}))
    p.difficulty = data.get("difficulty") or "normal"
    p.mode = data.get("mode") or "normal"
    p.mode_state = dict(data.get("mode_state") or {})
    p.diff_unlocked = unlocked(data)
    p.diff_state = dict(data.get("diff_state") or {})
    p.waypoints = set(data.get("waypoints", [1]))
    p.visited = set(data.get("visited", [1]))
    p.cain_rescued = data.get("cain", False)
    p.has_hireling = data.get("hireling", False)
    p.hireling_kind = data.get("hireling_kind", "")
    p.map_seed = data.get("map_seed")
    p.left_skill = data.get("left_skill")
    p.boss_kills = list(data.get("boss_kills") or [])
    p.tracked_quest = data.get("tracked_quest")
    p.qol = dict(data.get("qol") or {})
    p.imbues = dict(data.get("imbues") or {})
    p.weapon_set = int(data.get("weapon_set", 0) or 0)
    p.rift_seed = data.get("rift_seed")
    p.stash_merged = bool(data.get("stash_merged", False))
    p.heard = set(data.get("heard") or ())
    p.rift_mods = data.get("rift_mods")
    p.rift_map_depth = data.get("rift_map_depth")
    p.swap_gear = {k: _item_from(v, content) for k, v in (data.get("swap_gear") or {}).items()}
    p.swap_gear.setdefault("weapon", None)
    p.swap_gear.setdefault("shield", None)
    p.set_skills = {int(k): tuple(v) for k, v in (data.get("set_skills") or {}).items()}
    p.map_explored = dict(data.get("map_explored") or {})      # the automap ("same maps every game")
    p.cairn_order = data.get("cairn_order")
    p.rift_depth = int(data.get("rift_depth", 0) or 0)
    p.quest_stats = dict(data.get("quest_stats", {}) or {})
    p.current_act = data.get("act", 1)
    for k in p.equipment:
        p.equipment[k] = _item_from(data.get("equipment", {}).get(k), content)
    p.inventory = [it for it in (_item_from(d, content) for d in data.get("inventory", [])) if it is not None]
    p.belt = [it for it in (_item_from(d, content) for d in data.get("belt", [])) if it is not None]
    p.belt_unlocks = list(data.get("belt_unlocks") or [])
    if "belt_unlocks" not in data and p.quests.get("shenk") in ("cleared", "done"):
        p.belt_unlocks = ["normal"]          # (saves from before the potion system: Shenk already killed)
    md = data.get("merc")
    if md:
        p.merc = dict(kind=md.get("kind", "rogue"), hid=md.get("hid", 0), name=md.get("name", "Hireling"),
                      level=md.get("level", 1), xp=md.get("xp", 0), dead=bool(md.get("dead")),
                      items={k: _item_from(v, content) for k, v in (md.get("items") or {}).items() if v})
    from .cube import make_stash, cube_add, stash_tab, bankable
    p.stash = st = make_stash()
    sd = data.get("stash") or {}
    st.gold = sd.get("gold", 0) or 0
    st.bank = {k: int(v) for k, v in (sd.get("bank") or {}).items() if int(v) > 0}
    pages = sd.get("pages")
    if pages is None:
        pages = [sd.get("items", []) or []]        # an old save: the 6 x 8 stash becomes tab 2
    for i, page in enumerate(pages[:len(st.pages)]):
        stash_tab(st, i + 1)
        for d in page or []:
            it = _item_from(d, content)
            if it is None:
                continue
            if getattr(it, "cube_pos", None) is not None:
                st.contents.append(it)
            elif not cube_add(st, it):
                p.inventory.append(it)              # re-packed below
    stash_tab(st, 1)
    # anything without a valid backpack spot gets re-packed
    loose = [it for it in p.inventory if getattr(it, "inv_pos", None) is None]
    for it in loose:
        p.inventory.remove(it)
        p.inv_add(it)
    p.recalc()
    p.hp, p.mana = p.max_hp, p.max_mana
    s = p.skills.tree.get(p.right_skill) if p.right_skill else None
    if s is not None and s.kind == "aura":
        p.active_aura = p.right_skill
        if cls == "pal":
            p.right_skill = None             # (the paladin's aura has its own slot now)
    p.hotkeys = {str(k): v for k, v in (data.get("hotkeys") or {}).items()}
    a = data.get("aura")
    if a and a in p.skills.tree and p.skills.tree[a].kind == "aura":
        p.active_aura = a
    return p


def attach_shared_stash(content, heroes, stash=None):
    """Give every hero the one account-wide chest, carrying over whatever each of them had in a
    stash of their own the first time (so nothing stored before this is lost)."""
    from .cube import cube_add
    st = stash if stash is not None else load_shared_stash(content)
    for h in heroes:
        own = getattr(h, "stash", None)
        if own is not None and own is not st and not getattr(h, "stash_merged", False):
            for page in (getattr(own, "pages", None) or [getattr(own, "contents", None) or []]):
                for it in list(page):
                    try:
                        cube_add(st, it)
                    except Exception:
                        pass
            st.gold = getattr(st, "gold", 0) + (getattr(own, "gold", 0) or 0)
            for k, v in (getattr(own, "bank", {}) or {}).items():
                st.bank[k] = st.bank.get(k, 0) + int(v)
        h.stash_merged = True
        h.stash = st
    return st


def _hero_items(p):
    """Everything a hero carries: backpack, both weapon sets, and whatever is in the cube."""
    items = list(p.inventory) + [x for x in p.equipment.values() if x] + \
        [x for x in (getattr(p, "swap_gear", None) or {}).values() if x]
    for it in list(items):
        items += list(getattr(it, "contents", None) or [])
    return items


def identify_all_characters(content, skip=()):
    """Deckard Cain's eye reaches every character on this install, not only the one standing in
    front of him: their saves are read, identified and written back. Returns how many items."""
    from . import d2items
    global SAVE_DIR
    was, total = SAVE_DIR, 0
    skip = {(s or "").lower() for s in skip}
    try:
        for folder in (NORMAL_DIR, os.path.join(NORMAL_DIR, "tactics")):
            if not os.path.isdir(folder):
                continue
            SAVE_DIR = folder
            for fn in sorted(os.listdir(folder)):
                if not fn.endswith(".json") or fn.startswith("_"):
                    continue
                try:
                    with open(os.path.join(folder, fn)) as f:
                        data = json.load(f)
                    if (data.get("name", "") or "").lower() in skip:
                        continue             # (a hero in the party: identified where he stands)
                    p = build_player(data, content)
                    n = sum(1 for it in _hero_items(p) if d2items.identify(it))
                    if n:
                        p.recalc()
                        save_character(p, data.get("difficulty", "normal"))
                        total += n
                except Exception:
                    continue
    finally:
        SAVE_DIR = was
    return total
