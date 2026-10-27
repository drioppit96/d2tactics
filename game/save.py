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
        ml = [[c, list(v) if isinstance(v, tuple) else v] for c, v in it.mod_list]
    return dict(name=it.name, code=it.code, slot=it.slot, rarity=it.rarity, kind=it.kind, mods=mods, mod_list=ml,
                defense=it.defense, dmg=list(it.dmg) if it.dmg else None, ap=it.ap, amount=it.amount,
                potion=getattr(it, "potion", "heal"), inv_pos=list(it.inv_pos) if getattr(it, "inv_pos", None) else None,
                levelreq=it.levelreq)


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
        it.mod_list = [(c, tuple(v) if isinstance(v, list) else v) for c, v in d["mod_list"]]
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
    if d.get("inv_pos"):
        it.inv_pos = tuple(d["inv_pos"])
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
        equipment={k: _item_dict(v) for k, v in p.equipment.items()},
        inventory=[_item_dict(it) for it in p.inventory], belt=[_item_dict(it) for it in p.belt],
    )
    path = os.path.join(SAVE_DIR, _safe(p.name) + ".json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)
    return path


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
    for k in p.equipment:
        p.equipment[k] = _item_from(data.get("equipment", {}).get(k), content)
    p.inventory = [it for it in (_item_from(d, content) for d in data.get("inventory", [])) if it is not None]
    p.belt = [it for it in (_item_from(d, content) for d in data.get("belt", [])) if it is not None]
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
