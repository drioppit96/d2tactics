"""What is per act: towns, which world each level lives in, waypoint lists, outdoor areas,
and how the numbers in a DS1's object list are read (MonPreset.txt rows of that act).
"""
from . import act1

# level id -> act
ACT_RANGES = {1: range(1, 40), 2: range(40, 75), 3: range(75, 103), 4: range(103, 109), 5: range(109, 137)}
TOWNS = {1: 1, 2: 40, 3: 75, 4: 103, 5: 109}
TOWN_IDS = set(TOWNS.values())
WORLD_KEYS = {1: "wild", 2: "desert"}            # the seamless outdoor world of each act

# Act 2: Lut Gholein + the desert are one world, the Canyon of the Magi its own
ACT2_OUTDOOR = (40, 41, 42, 43, 44, 45)
OUTDOOR_IDS = set(act1.OUTDOOR_IDS) | set(ACT2_OUTDOOR) | {46}

WAYPOINTS = {
    1: list(act1.WAYPOINT_LEVELS),
    2: [40, 48, 42, 57, 43, 44, 52, 74, 46],     # D2's act 2 waypoint list, in order
}

TOWN_NPCS = {
    1: dict(act1.TOWN_NPCS),
    # MonPreset.txt act 2 order: 0 warriv2, 1 atma, 2 drognan, 3 fara, 8 greiz, 9 elzix, 10 lysander,
    # 11 meshif1, 12 geglash, 13 jerhyn, 20 cain2
    2: {0: "warriv2", 1: "atma", 2: "drognan", 3: "fara", 8: "greiz", 9: "elzix", 10: "lysander",
        11: "meshif1", 12: "geglash", 13: "jerhyn", 20: "cain2"},
}
# who you start next to when you arrive in town
TOWN_START_NPC = {1: "warriv1", 2: "warriv2"}

_monpreset_cache = {}


def act_of(level_id):
    if isinstance(level_id, str):
        return {"wild": 1, "desert": 2}.get(level_id, 1)
    for act, r in ACT_RANGES.items():
        if level_id in r:
            return act
    return 1


def world_of(level_id):
    """The key of the world a level lives in (outdoor worlds hold several levels)."""
    if level_id in act1.WORLD_OF:
        return act1.WORLD_OF[level_id]
    if level_id in ACT2_OUTDOOR:
        return "desert"
    from . import act2
    return act2.WORLD_OF.get(level_id, level_id)


def is_town(level_id):
    return level_id in TOWN_IDS


def monpreset(kit, act):
    key = (id(kit.src), act)
    if key not in _monpreset_cache:
        rows = []
        try:
            from d2.source import read_table
            rows = [(r.get("place") or "") for r in read_table(kit.src, "MonPreset") if (r.get("act") or "") == str(act)]
        except Exception:
            rows = []
        _monpreset_cache[key] = rows
    return _monpreset_cache[key]


def apply_act_tables(b, act, kit):
    b.act = act
    b.monpreset = monpreset(kit, act) or act1.MONPRESET_A1
    b.town_npcs = TOWN_NPCS.get(act, {})
    b.town_id = TOWNS.get(act, 1)
    from . import objtable
    b.quest_objects = objtable.quest_objects(kit, act)
