"""Saving and loading characters (like D2: the hero is saved, the maps are new each game).

Saves are small JSON files in the "saves" folder next to the game.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR = os.path.join(ROOT, "saves")


def _safe(name):
    return re.sub(r"[^A-Za-z0-9_-]", "_", name) or "hero"


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
                charges={k: list(v) for k, v in (getattr(it, "charges", None) or {}).items()} or None)


def _item_from(d, content):
    if d is None:
        return None
    from .items import Item
    mods = {k: (tuple(v) if isinstance(v, list) else v) for k, v in d.get("mods", {}).items()}
    it = Item(d["name"], d["code"], d.get("slot"), d.get("rarity", "normal"), mods,
              dmg=tuple(d["dmg"]) if d.get("dmg") else None, ap=d.get("ap"), defense=d.get("defense", 0),
              amount=d.get("amount", 0), kind=d.get("kind", "equip"))
    it.potion = d.get("potion", "heal")
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


def save_character(player, difficulty="normal"):
    """Write the hero to saves/<name>.json. Returns the path."""
    os.makedirs(SAVE_DIR, exist_ok=True)
    p = player
    data = dict(
        version=1, name=p.name, cls=p.cls, level=p.level, xp=p.xp, gold=p.gold, difficulty=difficulty,
        stats=[p.base_str, p.base_dex, p.base_vit, p.base_eng], stat_points=p.stat_points,
        skills=dict(p.skills.levels), skill_points=p.skills.points, right_skill=p.right_skill,
        quests=dict(getattr(p, "quests", {})), waypoints=sorted(getattr(p, "waypoints", {1})),
        visited=sorted(getattr(p, "visited", {1})), cain=bool(getattr(p, "cain_rescued", False)),
        hireling=bool(getattr(p, "has_hireling", False)),
        hireling_kind=getattr(p, "hireling_kind", ""), quest_stats=dict(getattr(p, "quest_stats", {}) or {}), act=int(getattr(p, "current_act", 1) or 1),
        equipment={k: _item_dict(v) for k, v in p.equipment.items()},
        inventory=[_item_dict(it) for it in p.inventory], belt=[_item_dict(it) for it in p.belt],
        merc=(dict(kind=p.merc["kind"], hid=p.merc["hid"], name=p.merc["name"], level=p.merc["level"],
                   xp=p.merc["xp"], dead=bool(p.merc.get("dead")),
                   items={k: _item_dict(v) for k, v in (p.merc.get("items") or {}).items() if v is not None})
              if getattr(p, "merc", None) else None),
        stash=dict(gold=getattr(getattr(p, "stash", None), "gold", 0),
                   items=[_item_dict(it) for it in (getattr(getattr(p, "stash", None), "contents", None) or [])]),
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
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(SAVE_DIR, fn)) as f:
                d = json.load(f)
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
    p.right_skill = data.get("right_skill") if data.get("right_skill") in p.skills.tree else None
    p.quests = dict(data.get("quests", {}))
    p.waypoints = set(data.get("waypoints", [1]))
    p.visited = set(data.get("visited", [1]))
    p.cain_rescued = data.get("cain", False)
    p.has_hireling = data.get("hireling", False)
    p.hireling_kind = data.get("hireling_kind", "")
    p.quest_stats = dict(data.get("quest_stats", {}) or {})
    p.current_act = data.get("act", 1)
    for k in p.equipment:
        p.equipment[k] = _item_from(data.get("equipment", {}).get(k), content)
    p.inventory = [it for it in (_item_from(d, content) for d in data.get("inventory", [])) if it is not None]
    p.belt = [it for it in (_item_from(d, content) for d in data.get("belt", [])) if it is not None]
    md = data.get("merc")
    if md:
        p.merc = dict(kind=md.get("kind", "rogue"), hid=md.get("hid", 0), name=md.get("name", "Hireling"),
                      level=md.get("level", 1), xp=md.get("xp", 0), dead=bool(md.get("dead")),
                      items={k: _item_from(v, content) for k, v in (md.get("items") or {}).items() if v})
    from .cube import make_stash, cube_add
    p.stash = make_stash()
    sd = data.get("stash") or {}
    p.stash.gold = sd.get("gold", 0) or 0
    for d in sd.get("items", []) or []:
        it = _item_from(d, content)
        if it is None:
            continue
        if getattr(it, "cube_pos", None) is not None:
            p.stash.contents.append(it)
        else:
            cube_add(p.stash, it)
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
    return p
