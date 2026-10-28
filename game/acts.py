"""What is per act: towns, which world each level lives in, waypoint lists, outdoor areas,
and how the numbers in a DS1's object list are read (MonPreset.txt rows of that act).
"""
from . import act1

# level id -> act
ACT_RANGES = {1: range(1, 40), 2: range(40, 75), 3: range(75, 103), 4: range(103, 109), 5: range(109, 137)}
TOWNS = {1: 1, 2: 40, 3: 75, 4: 103, 5: 109}
TOWN_IDS = set(TOWNS.values())
WORLD_KEYS = {1: "wild", 2: "desert", 3: "jungle", 4: "mesa", 5: "siege"}   # the town's world of each act

# Act 2: Lut Gholein + the desert are one world, the Canyon of the Magi its own
ACT2_OUTDOOR = (40, 41, 42, 43, 44, 45)
# Act 3: the docks + the jungle; Kurast + the Causeway + Travincal
ACT3_JUNGLE = (75, 76, 77, 78)
ACT3_KURAST = (79, 80, 81, 82, 83)
# Act 4: the Fortress + the mesa; the River of Flame + the Chaos Sanctum
ACT4_MESA = (103, 104, 105, 106)
ACT4_LAVA = (107, 108)
# Act 5: Harrogath, the Bloody Foothills, Rigid Highlands, Arreat Plateau; the Tundra alone
ACT5_SIEGE = (109, 110, 111, 112)
GROUPS = {}
for _k, _ids in (("desert", ACT2_OUTDOOR), ("jungle", ACT3_JUNGLE), ("kurast", ACT3_KURAST), ("mesa", ACT4_MESA),
                 ("lava", ACT4_LAVA), ("siege", ACT5_SIEGE)):
    for _i in _ids:
        GROUPS[_i] = _k
OUTDOOR_IDS = set(act1.OUTDOOR_IDS) | set(ACT2_OUTDOOR) | {46} | set(ACT3_JUNGLE) | set(ACT3_KURAST) | \
    set(ACT4_MESA) | set(ACT4_LAVA) | set(ACT5_SIEGE) | {117, 120}

WAYPOINTS = {
    1: list(act1.WAYPOINT_LEVELS),
    2: [40, 48, 42, 57, 43, 44, 52, 74, 46],     # D2's waypoint lists, in order
    3: [75, 76, 77, 78, 79, 80, 81, 83, 101],
    4: [103, 106, 107],
    5: [109, 111, 112, 113, 115, 117, 118, 123, 129],
}
# Objects.txt tokens of each waypoint (a different look per act / area)
WAYPOINT_TOKEN = {40: "WM", 42: "WM", 43: "WM", 44: "WM", 46: "WM", 48: "QM", 52: "W7", 57: "WP", 74: "WP",
                  75: "WZ", 76: "WP", 77: "WP", 78: "WP", 79: "WP", 80: "WP", 81: "WP", 83: "QL", 101: "WI",
                  103: "YG", 106: "WV", 107: "WV",
                  109: "YY", 111: "5A", 112: "5A", 113: "5A", 115: "5A", 117: "5A", 118: "5A", 123: "3P",
                  129: "8Y"}

TOWN_NPCS = {
    1: dict(act1.TOWN_NPCS),
    # MonPreset.txt rows of each act
    2: {0: "warriv2", 1: "atma", 2: "drognan", 3: "fara", 8: "greiz", 9: "elzix", 10: "lysander",
        11: "meshif1", 12: "geglash", 13: "jerhyn", 20: "cain2"},
    3: {0: "cain3", 4: "asheara", 5: "hratli", 6: "alkor", 7: "ormus", 8: "meshif2", 15: "natalya"},
    4: {7: "tyrael2", 10: "jamella", 11: "halbu", 25: "cain4"},
    5: {0: "larzuk", 1: "drehya", 2: "malah", 3: "nihlathak", 4: "qual-kehk", 7: "tyrael3", 8: "cain6",
        21: "cain6"},
}
# who you start next to when you arrive in town
TOWN_START_NPC = {1: "warriv1", 2: "warriv2", 3: "meshif2", 4: "tyrael2", 5: "malah"}

_monpreset_cache = {}


def act_of(level_id):
    if isinstance(level_id, str):
        return {"wild": 1, "desert": 2, "jungle": 3, "kurast": 3, "mesa": 4, "lava": 4, "siege": 5}.get(level_id, 1)
    for act, r in ACT_RANGES.items():
        if level_id in r:
            return act
    return 1


def world_of(level_id):
    """The key of the world a level lives in (outdoor worlds hold several levels)."""
    if level_id in act1.WORLD_OF:
        return act1.WORLD_OF[level_id]
    if level_id in GROUPS:
        return GROUPS[level_id]
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
