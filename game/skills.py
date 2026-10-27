"""Skills for all seven classes, read from D2's Skills.txt / SkillDesc.txt.

Everything numeric comes straight from the game tables: tree layout, icons, required levels,
prerequisites, mana, damage per level (with D2's level brackets and `hitshift`), synergies
(`EDmgSymPerCalc` / `DmgSymPerCalc` ...), durations, radii, aura and passive stats, the
tooltip lines of SkillDesc. How a skill *plays* on a turn-based grid is decided by its
"kind" (melee, missile, nova, area, curse, aura, summon ...), worked out from the table
columns plus a small override list below.

Without D2 data (placeholder art) only the built-in Barbarian tree is available.
"""
import math
from .d2calc import evaluate, linear, diminishing

TURN_SECONDS = 2          # one combat round lasts about two seconds of D2 time
FRAMES = 25               # D2 runs at 25 frames per second

# code, display name, sprite token, icon file prefix, skill-tree letter
CLASSES = [
    ("ama", "Amazon", "AM", "am", "a"),
    ("ass", "Assassin", "AI", "as", "i"),
    ("nec", "Necromancer", "NE", "ne", "n"),
    ("bar", "Barbarian", "BA", "ba", "b"),
    ("pal", "Paladin", "PA", "pa", "p"),
    ("sor", "Sorceress", "SO", "so", "s"),
    ("dru", "Druid", "DZ", "dr", "d"),
]
CLASS_BY_CODE = {c[0]: c for c in CLASSES}
CLASS_CODE_BY_NAME = {c[1]: c[0] for c in CLASSES}
DEFAULT_PAGE_NAMES = {
    "bar": {1: "Combat Skills", 2: "Combat Masteries", 3: "Warcries"},
    "ama": {1: "Bow and Crossbow", 2: "Passive and Magic", 3: "Javelin and Spear"},
    "sor": {1: "Fire Spells", 2: "Lightning Spells", 3: "Cold Spells"},
    "nec": {1: "Curses", 2: "Poison and Bone", 3: "Summoning"},
    "pal": {1: "Combat Skills", 2: "Offensive Auras", 3: "Defensive Auras"},
    "dru": {1: "Summoning", 2: "Shape Shifting", 3: "Elemental"},
    "ass": {1: "Traps", 2: "Shadow Disciplines", 3: "Martial Arts"},
}
PAGE_NAMES = DEFAULT_PAGE_NAMES["bar"]

# ---------------------------------------------------------------- built-in Barbarian (no D2 data)
# name: (page, row, col, reqlevel, prereqs, mana, icon, kind)
BUILTIN = {
    "Bash": (1, 1, 2, 1, (), 2, 0, "attack"),
    "Leap": (1, 2, 1, 6, (), 2, 12, "move"),
    "Double Swing": (1, 2, 3, 6, ("Bash",), 8, 14, "attack"),
    "Stun": (1, 3, 2, 12, ("Bash",), 2, 26, "attack"),
    "Double Throw": (1, 3, 3, 12, ("Double Swing",), 1, 28, "attack"),
    "Leap Attack": (1, 4, 1, 18, ("Leap",), 9, 34, "attack"),
    "Concentrate": (1, 4, 2, 18, ("Stun",), 2, 36, "attack"),
    "Frenzy": (1, 5, 3, 24, ("Double Throw",), 3, 42, "attack"),
    "Whirlwind": (1, 6, 1, 30, ("Leap Attack", "Concentrate"), 25, 50, "move"),
    "Berserk": (1, 6, 2, 30, ("Concentrate",), 4, 52, "attack"),
    "Sword Mastery": (2, 1, 1, 1, (), 0, 2, "passive"),
    "Axe Mastery": (2, 1, 2, 1, (), 0, 4, "passive"),
    "Mace Mastery": (2, 1, 3, 1, (), 0, 6, "passive"),
    "Pole Arm Mastery": (2, 2, 1, 6, (), 0, 16, "passive"),
    "Throwing Mastery": (2, 2, 2, 6, (), 0, 18, "passive"),
    "Spear Mastery": (2, 2, 3, 6, (), 0, 20, "passive"),
    "Increased Stamina": (2, 3, 1, 12, (), 0, 30, "passive"),
    "Iron Skin": (2, 4, 3, 18, (), 0, 38, "passive"),
    "Increased Speed": (2, 5, 1, 24, ("Increased Stamina",), 0, 44, "passive"),
    "Natural Resistance": (2, 6, 3, 30, ("Iron Skin",), 0, 54, "passive"),
    "Howl": (3, 1, 1, 1, (), 4, 8, "cry"),
    "Find Potion": (3, 1, 3, 1, (), 2, 10, "corpse"),
    "Taunt": (3, 2, 1, 6, ("Howl",), 3, 22, "attack"),
    "Shout": (3, 2, 2, 6, ("Howl",), 6, 24, "cry"),
    "Find Item": (3, 3, 3, 12, ("Find Potion",), 7, 32, "corpse"),
    "Battle Cry": (3, 4, 1, 18, ("Taunt",), 5, 40, "cry"),
    "Battle Orders": (3, 5, 2, 24, ("Shout",), 7, 46, "cry"),
    "Grim Ward": (3, 5, 3, 24, ("Find Item",), 4, 48, "corpse"),
    "War Cry": (3, 6, 1, 30, ("Battle Cry", "Battle Orders"), 10, 56, "cry"),
    "Battle Command": (3, 6, 2, 30, ("Battle Orders",), 11, 58, "cry"),
}
BAR_KINDS = {n: v[7] for n, v in BUILTIN.items()}

# weapon type codes each mastery applies to (Barbarian; masteries of other classes use passiveitype)
MASTERY_TYPES = {"Sword Mastery": {"swor", "knif"}, "Axe Mastery": {"axe"}, "Mace Mastery": {"mace", "hamm", "club", "scep", "blun"},
                 "Pole Arm Mastery": {"pole"}, "Spear Mastery": {"spea"}, "Throwing Mastery": {"thro", "jave", "taxe", "tkni"}}

# ---------------------------------------------------------------- how the other skills play
# kind: melee | missile | nova | area | line | chain | curse | buff | aura | summon | raise | golem |
#       turret | wall | revive | corpse_blast | teleport | charge | passive
# extras: radius, pierce, targets (calc), linger (turns), stun, knock, always_hit, splash, hits, undead_only
OVERRIDES = {
    # Amazon
    "Magic Arrow": dict(kind="missile", weapon=True), "Fire Arrow": dict(kind="missile", weapon=True),
    "Cold Arrow": dict(kind="missile", weapon=True), "Multiple Shot": dict(kind="missile", weapon=True, targets="calc1"),
    "Exploding Arrow": dict(kind="missile", weapon=True, splash=2), "Ice Arrow": dict(kind="missile", weapon=True),
    "Guided Arrow": dict(kind="missile", weapon=True, always_hit=True),
    "Strafe": dict(kind="missile", weapon=True, targets="calc1"),
    "Immolation Arrow": dict(kind="missile", weapon=True, splash=2, linger=2),
    "Freezing Arrow": dict(kind="missile", weapon=True, splash=2),
    "Poison Javelin": dict(kind="missile", weapon=True, linger=2), "Lightning Bolt": dict(kind="missile", weapon=True, pierce=True),
    "Plague Javelin": dict(kind="missile", weapon=True, splash=2, linger=2),
    "Lightning Fury": dict(kind="missile", weapon=True, splash=3),
    "Jab": dict(kind="melee", hits=3), "Fend": dict(kind="melee", sweep=True),
    "Power Strike": dict(kind="melee"), "Charged Strike": dict(kind="melee", chain="calc1"),
    "Lightning Strike": dict(kind="melee", chain="calc1"), "Impale": dict(kind="melee"),
    "Inner Sight": dict(kind="curse", self_centred=True), "Slow Missiles": dict(kind="curse", self_centred=True),
    "Dopplezon": dict(kind="summon"), "Valkyrie": dict(kind="summon"),
    # Sorceress
    "Fire Bolt": dict(kind="missile"), "Ice Bolt": dict(kind="missile"), "Ice Blast": dict(kind="missile"),
    "Charged Bolt": dict(kind="missile", targets="calc1", spread=True), "Fire Ball": dict(kind="missile", splash=2),
    "Lightning": dict(kind="missile", pierce=True), "Glacial Spike": dict(kind="missile", splash=2),
    "Frozen Orb": dict(kind="missile", splash=3, pierce=True), "Telekinesis": dict(kind="missile", knock=True),
    "Frost Nova": dict(kind="nova"), "Nova": dict(kind="nova"), "Static Field": dict(kind="nova", static=True),
    "Inferno": dict(kind="line", length=5, per_second=True), "Blaze": dict(kind="buff", per_second=True),
    "Fire Wall": dict(kind="line", length=5, linger=3, per_second=True, across=True),
    "Blizzard": dict(kind="area", radius=3, linger=2), "Meteor": dict(kind="area", radius=3, linger=2),
    "Chain Lightning": dict(kind="chain"), "Teleport": dict(kind="teleport"), "Hydra": dict(kind="turret"),
    "Thunder Storm": dict(kind="buff", periodic=True), "Energy Shield": dict(kind="buff"),
    "Frozen Armor": dict(kind="buff"), "Shiver Armor": dict(kind="buff"), "Chilling Armor": dict(kind="buff"),
    "Enchant": dict(kind="buff"),
    # Necromancer
    "Teeth": dict(kind="missile", targets="calc1", spread=True), "Bone Spear": dict(kind="missile", pierce=True),
    "Bone Spirit": dict(kind="missile", always_hit=True), "Poison Nova": dict(kind="nova"),
    "Corpse Explosion": dict(kind="corpse_blast"), "Poison Explosion": dict(kind="corpse_blast"),
    "Bone Wall": dict(kind="wall"), "Bone Prison": dict(kind="wall", prison=True), "Bone Armor": dict(kind="buff"),
    "Raise Skeleton": dict(kind="raise"), "Raise Skeletal Mage": dict(kind="raise"), "Revive": dict(kind="revive"),
    "Clay Golem": dict(kind="golem"), "BloodGolem": dict(kind="golem"), "IronGolem": dict(kind="golem"),
    "FireGolem": dict(kind="golem"), "Poison Dagger": dict(kind="melee"),
    # Paladin
    "Holy Bolt": dict(kind="missile", undead_only=True, pierce=True), "Blessed Hammer": dict(kind="nova", radius=2),
    "Fist of the Heavens": dict(kind="area", radius=2, always_hit=True), "Charge": dict(kind="charge"),
    "Holy Shield": dict(kind="buff"), "Smite": dict(kind="melee", always_hit=True, stun=1, knock=True),
    "Zeal": dict(kind="melee", hits="calc1"), "Sacrifice": dict(kind="melee", self_damage=8),
    "Vengeance": dict(kind="melee"), "Conversion": dict(kind="melee", convert=True),
    # Druid
    "Firestorm": dict(kind="line", length=6, linger=2), "Molten Boulder": dict(kind="line", length=7, knock=True),
    "Arctic Blast": dict(kind="line", length=5, per_second=True), "Eruption": dict(kind="area", radius=2, linger=2),
    "Volcano": dict(kind="area", radius=2, linger=3), "Armageddon": dict(kind="buff", periodic=True),
    "Hurricane": dict(kind="buff", periodic=True), "Cyclone Armor": dict(kind="buff"),
    "Twister": dict(kind="missile", targets=3, spread=True, stun=1), "Tornado": dict(kind="missile", splash=1),
    "Shock Wave": dict(kind="nova", radius=3, stun=2), "Wearwolf": dict(kind="buff", shift=True),
    "Wearbear": dict(kind="buff", shift=True), "Feral Rage": dict(kind="melee", charges=True),
    "Maul": dict(kind="melee", charges=True), "Rabies": dict(kind="melee"), "Fire Claws": dict(kind="melee"),
    "Hunger": dict(kind="melee"), "Fury": dict(kind="melee", hits="calc1"),
    "Raven": dict(kind="summon"), "Plague Poppy": dict(kind="summon"), "Cycle of Life": dict(kind="summon"),
    "Vines": dict(kind="summon"), "Oak Sage": dict(kind="summon"), "Heart of Wolverine": dict(kind="summon"),
    "Spirit of Barbs": dict(kind="summon"), "Summon Spirit Wolf": dict(kind="summon"),
    "Summon Fenris": dict(kind="summon"), "Summon Grizzly": dict(kind="summon"),
    # Assassin
    "Fire Trauma": dict(kind="area", radius=2), "Shock Field": dict(kind="area", radius=2),
    "Psychic Hammer": dict(kind="missile", knock=True), "Blade Fury": dict(kind="missile", targets=3, spread=True),
    "Mind Blast": dict(kind="area", radius=2, stun=1), "Dragon Flight": dict(kind="charge", teleport=True),
    "Dragon Talon": dict(kind="melee", hits="calc1", finisher=True), "Dragon Claw": dict(kind="melee", hits=2, finisher=True),
    "Dragon Tail": dict(kind="melee", splash=2, finisher=True),
    "Tiger Strike": dict(kind="melee", charges=True), "Cobra Strike": dict(kind="melee", charges=True),
    "Fists of Fire": dict(kind="melee", charges=True), "Claws of Thunder": dict(kind="melee", charges=True),
    "Blades of Ice": dict(kind="melee", charges=True), "Royal Strike": dict(kind="melee", charges=True),
    "Blade Sentinel": dict(kind="turret"), "Charged Bolt Sentry": dict(kind="turret"),
    "Wake of Fire Sentry": dict(kind="turret"), "Lightning Sentry": dict(kind="turret"),
    "Inferno Sentry": dict(kind="turret"), "Death Sentry": dict(kind="turret"),
    "Shadow Warrior": dict(kind="summon"), "Shadow Master": dict(kind="summon"),
    "Cloak of Shadows": dict(kind="curse", self_centred=True), "Fade": dict(kind="buff"),
    "Quickness": dict(kind="buff"), "Venom": dict(kind="buff"), "Blade Shield": dict(kind="buff", periodic=True),
}

ELEMENT_NAMES = {"fire": "Fire", "cold": "Cold", "ltng": "Lightning", "pois": "Poison", "mag": "Magic"}


def _int(v, default=0):
    try:
        return int(str(v).strip().strip('"'))
    except (TypeError, ValueError):
        return default


def _bracket(base, per, lvl, brackets=((2, 8), (9, 16), (17, 22), (23, 28), (29, 999))):
    """D2 per-level growth: +per[0] for levels 2-8, +per[1] for 9-16 ..."""
    v = base
    for i, (lo, hi) in enumerate(brackets):
        if lvl < lo:
            break
        n = min(lvl, hi) - lo + 1
        v += n * (per[i] if i < len(per) else 0)
    return v


class Skill:
    def __init__(self, name, page, row, col, reqlevel, prereqs, mana, icon, kind):
        self.key = self.name = name
        self.page, self.row, self.col = page, row, col
        self.reqlevel, self.prereqs, self.mana, self.icon, self.kind = reqlevel, tuple(prereqs), mana, icon, kind
        self.cls = "bar"
        self.data = None          # Skills.txt row (None = built-in)
        self.desc = None          # SkillDesc.txt row
        self.title = name
        self.short = ""
        self.long = ""
        self.extra = {}
        self.maxlvl = 20
        self.weapon = False       # uses the weapon's damage
        self.element = ""
        self.itype = ()


def _strings_get(strings, key, fallback=""):
    if not key:
        return fallback
    if strings is None:
        return fallback or key
    v = strings.get(key, None) if hasattr(strings, "get") else None
    return v if v is not None else (fallback or key)


def load_all(src, strings=None):
    """Every class skill from the tables -> {class code: {skill key: Skill}}."""
    from d2.source import read_table
    descs = {r["skilldesc"]: r for r in read_table(src, "SkillDesc") if r.get("skilldesc")}
    trees = {c[0]: {} for c in CLASSES}
    for r in read_table(src, "Skills"):
        cls = r.get("charclass")
        if cls not in trees or not r.get("skill"):
            continue
        d = descs.get(r.get("skilldesc"), {})
        if not d.get("skillpage") or d.get("skillpage") == "0":
            continue
        key = r["skill"]
        s = Skill(key, _int(d["skillpage"]), _int(d["skillrow"]), _int(d["skillcolumn"]), _int(r.get("reqlevel"), 1),
                  [x for x in (r.get("reqskill1"), r.get("reqskill2"), r.get("reqskill3")) if x], _int(r.get("mana")),
                  _int(d.get("iconcel")), "")
        s.cls, s.data, s.desc = cls, r, d
        s.maxlvl = _int(r.get("maxlvl"), 20) or 20
        s.title = _strings_get(strings, d.get("str name"), key)
        s.short = _strings_get(strings, d.get("str short"), "")
        s.long = _strings_get(strings, d.get("str long"), "")
        s.element = r.get("etype", "")
        s.itype = tuple(x for x in (r.get("itypea1"), r.get("itypea2"), r.get("itypea3")) if x)
        s.extra = dict(OVERRIDES.get(key, {}))
        s.kind = _classify(s)
        s.weapon = s.extra.get("weapon", False) or r.get("range") in ("h2h", "rng") and s.kind in ("melee", "charge") \
            or (s.kind == "missile" and r.get("srcdam") not in ("", "0") and bool(s.itype))
        s.strings = strings
        trees[cls][key] = s
    return trees


def _classify(s):
    r = s.data
    if r.get("passive") == "1":
        return "passive"
    if s.cls == "bar" and s.key in BAR_KINDS:
        return BAR_KINDS[s.key]
    if "kind" in s.extra:
        return s.extra["kind"]
    if r.get("aura") == "1":
        return "aura"
    do = r.get("srvdofunc", "")
    if do in ("30", "61", "59"):
        return "curse"
    if r.get("summon"):
        return {"31": "raise", "56": "golem", "57": "golem", "45": "turret", "44": "turret", "144": "turret",
                "60": "wall", "62": "wall"}.get(do, "summon")
    if r.get("range") == "h2h":
        return "melee"
    if r.get("srvmissile") or r.get("srvmissilea"):
        return "missile"
    if r.get("aurastate"):
        return "buff"
    return "buff"


def load_tree(src=None, cls="bar", strings=None):
    """One class's tree. With no D2 data only the built-in Barbarian tree exists."""
    if src is None:
        tree = {n: Skill(n, *v) for n, v in BUILTIN.items()}
        return tree
    try:
        trees = load_all(src, strings)
        if trees.get(cls):
            return trees[cls]
    except Exception:
        import traceback
        traceback.print_exc()
    return {n: Skill(n, *v) for n, v in BUILTIN.items()}


# ---------------------------------------------------------------- formula environment
class SkillEnv:
    """Values of one skill at one level, for D2's calc expressions."""

    def __init__(self, book, skill, lvl=None):
        self.book, self.s = book, skill
        self.r = skill.data or {}
        self.lvl = max(1, lvl if lvl is not None else book.level(skill.key))
        self._depth = 0

    def par(self, i):
        return _int(self.r.get("param%d" % i))

    def ln(self, a, b):
        return linear(self.par(a), self.par(b), self.lvl)

    def dm(self, a, b):
        return diminishing(self.par(a), self.par(b), self.lvl)

    def name(self, n):
        if n == "lvl":
            return self.lvl
        if n == "blvl":
            return self.book.levels.get(self.s.key, 0) if self.book else self.lvl
        if n.startswith("par") and n[3:].isdigit():
            return self.par(int(n[3:]))
        if n.startswith("ln") and len(n) == 4 and n[2:].isdigit():
            return self.ln(int(n[2]), int(n[3]))
        if n.startswith("dm") and len(n) == 4 and n[2:].isdigit():
            return self.dm(int(n[2]), int(n[3]))
        if n.startswith("clc") and n[3:].isdigit():
            return self.calc("calc%s" % n[3:])
        if n == "toht":
            return self.tohit()
        if n == "edmn":
            return int(self._shift(self.elem_raw()[0]))
        if n == "edmx":
            return int(self._shift(self.elem_raw()[1]))
        if n == "edns":
            return self.elem_raw()[0] << _int(self.r.get("hitshift"))
        if n in ("ednx", "edxs"):
            return self.elem_raw()[1] << _int(self.r.get("hitshift"))
        if n == "edln":
            return self.elem_len()
        if n == "dmmn":
            return self.phys_raw()[0]
        if n == "dmmx":
            return self.phys_raw()[1]
        if n == "mana":
            return int(self.mana())
        if n == "enms":
            return self.lvl * 4
        return 0

    def ref(self, func, name, field):
        if func != "skill" or self.book is None or self._depth > 3:
            return 0
        other = self.book.find(name)
        if other is None:
            return 0
        if field == "blvl":
            return self.book.levels.get(other.key, 0)
        lvl = self.book.level(other.key)
        if field == "lvl":
            return lvl
        if lvl <= 0 and field not in ("par1", "par2", "par3", "par4", "par5", "par6", "par7", "par8"):
            return 0
        env = SkillEnv(self.book, other, max(1, lvl))
        env._depth = self._depth + 1
        return env.name(field)

    def calc(self, col):
        self._depth += 1
        try:
            return evaluate(self.r.get(col, ""), self)
        finally:
            self._depth -= 1

    # -------------------------------------------------- numbers
    def tohit(self):
        if self.r.get("tohitcalc"):
            return self.calc("tohitcalc")
        return _int(self.r.get("tohit")) + _int(self.r.get("levtohit")) * (self.lvl - 1)

    def _shift(self, v):
        hs = _int(self.r.get("hitshift"), 0)
        return v * (1 << hs) / 256.0

    def elem_raw(self):
        r, L = self.r, self.lvl
        lo = _bracket(_int(r.get("emin")), [_int(r.get("eminlev%d" % i)) for i in range(1, 6)], L)
        hi = _bracket(_int(r.get("emax")), [_int(r.get("emaxlev%d" % i)) for i in range(1, 6)], L)
        return lo, hi

    def phys_raw(self):
        r, L = self.r, self.lvl
        lo = _bracket(_int(r.get("mindam")), [_int(r.get("minlevdam%d" % i)) for i in range(1, 6)], L)
        hi = _bracket(_int(r.get("maxdam")), [_int(r.get("maxlevdam%d" % i)) for i in range(1, 6)], L)
        return lo, hi

    def elem_len(self):
        r = self.r
        n = _bracket(_int(r.get("elen")), [_int(r.get("elevlen%d" % i)) for i in range(1, 4)], self.lvl,
                     ((2, 8), (9, 16), (17, 999)))
        if r.get("elensympercalc"):
            n = n * (100 + self.calc("elensympercalc")) // 100
        return n

    def synergy(self):
        return self.calc("edmgsympercalc") if self.r.get("edmgsympercalc") else 0

    def phys_synergy(self):
        return self.calc("dmgsympercalc") if self.r.get("dmgsympercalc") else 0

    def elem_damage(self):
        """-> (element, lo, hi, length_frames) with synergies; poison as total damage."""
        et = self.r.get("etype", "")
        lo, hi = self.elem_raw()
        if not et or (lo == 0 and hi == 0) or et == "stun":
            return None
        syn = self.synergy()
        lo, hi = self._shift(lo), self._shift(hi)
        length = self.elem_len()
        if et == "pois":
            lo, hi = lo * max(1, length), hi * max(1, length)
        if self.s.extra.get("per_second"):
            lo, hi = lo * FRAMES, hi * FRAMES
        lo, hi = lo * (100 + syn) / 100.0, hi * (100 + syn) / 100.0
        return et, int(lo), int(max(lo, hi)), length

    def phys_damage(self):
        lo, hi = self.phys_raw()
        if lo == 0 and hi == 0:
            return None
        syn = self.phys_synergy()
        lo, hi = self._shift(lo) * (100 + syn) / 100.0, self._shift(hi) * (100 + syn) / 100.0
        return int(lo), int(max(lo, hi))

    def mana(self):
        r = self.r
        if not r:
            return self.s.mana
        shift = _int(r.get("manashift"), 8)
        cost = (_int(r.get("mana")) + _int(r.get("lvlmana")) * (self.lvl - 1)) * (1 << shift) / 256.0
        return max(cost, _int(r.get("minmana")) if cost > 0 else 0)

    def duration_frames(self):
        return self.calc("auralencalc") if self.r.get("auralencalc") else 0

    def radius(self):
        if "radius" in self.s.extra:
            return self.s.extra["radius"]
        v = self.calc("aurarangecalc") if self.r.get("aurarangecalc") else 0
        # D2 radii are in sub-tiles (= one grid cell here); keep them playable on a tactical grid
        return max(1, min(12, int(round(v * 2 / 3.0)))) if v else 0

    def stats(self, prefix, n):
        """[(stat, value)] for aurastat1-6 / passivestat1-5."""
        out = []
        for i in range(1, n + 1):
            st = self.r.get("%s%d" % (prefix, i))
            if not st:
                continue
            calc_col = ("aurastatcalc%d" if prefix == "aurastat" else "passivecalc%d") % i
            out.append((st, self.calc(calc_col)))
        return out


def turns_from_frames(frames):
    if frames <= 0:
        return 0
    return max(1, int(round(frames / float(FRAMES * TURN_SECONDS))))


# ---------------------------------------------------------------- what a character has learned
class SkillBook:
    def __init__(self, tree, cls="bar"):
        self.tree = tree
        self.cls = cls
        self.levels = {}
        self.points = 1            # one point to spend right away
        self.bonus = 0             # +all skills (Battle Command, items)
        self._by_title = {}
        for k, s in tree.items():
            self._by_title[k.lower()] = s
            self._by_title[s.title.lower()] = s

    def find(self, name):
        s = self.tree.get(name)
        return s if s is not None else self._by_title.get(str(name).lower())

    def level(self, name):
        base = self.levels.get(name, 0)
        return base + self.bonus if base else 0

    def can_learn(self, name, clvl):
        s = self.tree.get(name)
        if not s or self.points <= 0 or clvl < s.reqlevel or self.levels.get(name, 0) >= s.maxlvl:
            return False
        return all(self.levels.get(p, 0) > 0 for p in s.prereqs if p in self.tree)

    def learn(self, name, clvl):
        if not self.can_learn(name, clvl):
            return False
        self.levels[name] = self.levels.get(name, 0) + 1
        self.points -= 1
        return True

    def actives(self):
        return [n for n in self.levels if self.tree[n].kind != "passive"]

    def env(self, name, lvl=None):
        return SkillEnv(self, self.tree[name], lvl)

    # ------------------------------------------------------------ costs
    def mana_cost(self, name):
        s = self.tree[name]
        lv = max(1, self.level(name))
        if s.data is None:
            if name == "Double Swing":
                return max(2, 8 - (lv - 1) // 4)
            if name == "Whirlwind":
                return 25 + (lv - 1) // 4
            if name == "War Cry":
                return 10 + (lv - 1) // 4
            return s.mana
        m = SkillEnv(self, s, lv).mana()
        return round(m, 1) if m != int(m) else int(m)

    def ap_cost(self, name, weapon_ap):
        """AP for a skill, worked out from its mana cost (at your current skill level).

        Spells and other non-weapon skills: 1.5 + sqrt(mana), rounded, 2..10 AP
        (Fire Bolt 3, Frost Nova 5, Meteor 6, Frozen Orb 7, Revive 8).
        Skills that swing or shoot your weapon: the weapon's attack AP + 0.6 * sqrt(mana)
        (Bash +1, Leap Attack +2, Whirlwind +3). Auras cost 1 AP to switch on.
        """
        s = self.tree[name]
        k = s.kind
        if k == "aura":
            return 1
        mana = max(0.0, float(self.mana_cost(name) or 0))
        weapon_skill = k in ("attack", "melee", "charge") or (k == "missile" and s.weapon) or \
            name in ("Double Swing", "Frenzy", "Leap Attack", "Whirlwind", "Double Throw")
        if weapon_skill:
            return int(weapon_ap + max(1, int(0.6 * math.sqrt(mana) + 0.5)))
        return max(2, min(10, int(1.5 + math.sqrt(mana) + 0.5)))

    # ------------------------------------------------------------ text
    def describe(self, name):
        lv = max(1, self.level(name))
        s = self.tree[name]
        if s.data is None:
            return describe_skill(name, lv)
        return describe_d2(self, s, lv)

    def describe_next(self, name):
        s = self.tree[name]
        if s.data is None:
            return describe_skill(name, self.level(name) + 1)
        return describe_d2(self, s, self.level(name) + 1)

    def synergy_lines(self, name):
        s = self.tree[name]
        return synergy_lines(self, s) if s.data is not None else []

    def page_names(self, strings=None):
        return DEFAULT_PAGE_NAMES.get(self.cls, PAGE_NAMES)


# ---------------------------------------------------------------- tooltips from SkillDesc
def _desc_text(s, key):
    if not key:
        return ""
    return _strings_get(getattr(s, "strings", None), key, key)


def _fmt_num(v):
    if isinstance(v, float) and v != int(v):
        return ("%.1f" % v).rstrip("0").rstrip(".")
    return str(int(v))


def _yards(v):
    return _fmt_num(round(v * 2 / 3.0, 1))


def _seconds(frames):
    return _fmt_num(round(frames / 25.0, 1))


def describe_d2(book, s, lv):
    """The per-level lines of a D2 tooltip (dsc2 + descline1-6 of SkillDesc), plus damage and mana."""
    env = SkillEnv(book, s, lv)
    d = s.desc or {}
    lines = []
    for pre, n in (("dsc2", 4), ("desc", 6)):
        for i in range(1, n + 1):
            code = _int(d.get("%sline%d" % (pre, i)))
            if not code:
                continue
            ta = _desc_text(s, d.get("%stexta%d" % (pre, i)))
            tb = _desc_text(s, d.get("%stextb%d" % (pre, i)))
            ca = evaluate(d.get("%scalca%d" % (pre, i), ""), env) if d.get("%scalca%d" % (pre, i)) else 0
            cb = evaluate(d.get("%scalcb%d" % (pre, i), ""), env) if d.get("%scalcb%d" % (pre, i)) else 0
            line = _descline(code, ta, tb, ca, cb)
            if line and line not in lines:
                lines.append(line)
    lines += damage_lines(env)
    m = env.mana()
    if m:
        lines.append("Mana Cost: %s" % _fmt_num(round(m, 1)))
    k = s.kind
    dur = env.duration_frames()
    if k in ("curse", "buff") and dur:
        lines.append("Lasts %d turns" % turns_from_frames(dur))
    if k == "aura":
        lines.append("Active while selected as your right skill")
    return lines


def damage_lines(env):
    s = env.s
    out = []
    pd = env.phys_damage()
    if pd and pd[1] > 0:
        out.append("Damage: %d-%d" % pd)
    ed = env.elem_damage()
    if ed:
        et, lo, hi, ln = ed
        name = ELEMENT_NAMES.get(et, et.title())
        if et == "pois":
            out.append("Poison Damage: %d-%d over %s seconds" % (lo, hi, _seconds(ln)))
        else:
            out.append("%s Damage: %d-%d%s" % (name, lo, hi, " per second" if s.extra.get("per_second") else ""))
            if et == "cold" and ln:
                out.append("Cold Length: %s seconds" % _seconds(ln))
    if s.weapon and s.kind in ("melee", "missile", "charge"):
        out.append("Uses your weapon damage")
    return out


def _descline(code, ta, tb, ca, cb):
    n, m = _fmt_num(ca), _fmt_num(cb)
    if code in (1, 8, 9, 10, 11, 14, 17, 18, 22, 23, 24, 26, 27, 28, 29, 30, 33, 34, 35, 39, 40, 41, 48, 49, 50,
                53, 54, 55, 56, 63, 72, 73):
        return None                          # blank lines / numbers this game prints itself
    if code in (2, 4):
        return ("%s +%s %s" % (ta, n, tb)).strip()
    if code in (3, 5, 61):
        return ("%s %s %s" % (ta, n, tb)).strip()
    if code == 6:
        return ("+%s %s %s" % (n, ta, tb)).strip()
    if code == 7:
        return ("%s %s" % (n, ta)).strip()
    if code in (12, 31, 57):
        return "%s %s seconds" % (ta or "Duration:", _seconds(ca))
    if code == 13:
        return ("Life: +%s percent" % n) if ca else None
    if code in (19, 37):
        return "%s %s yards" % (ta or "Radius:", _yards(ca))
    if code in (32, 70):
        return "%s %s +%s" % (ta, tb, n)
    if code == 36:
        return "%s: %s" % (ta.title(), n) if ta else None
    if code in (38, 52):
        return ("%s %s-%s %s" % (ta, n, m, tb)).strip()
    if code in (16,):
        return "%s %s-%s seconds" % (ta, _seconds(ca), _seconds(cb))
    if code == 43:
        return "%s %s-%s" % (ta, _fmt_num(ca // 256), _fmt_num(cb // 256))
    if code in (47, 59):
        return "%s %s-%s" % (ta, n, m)
    if code in (51, 66):
        return ta.replace("%d", str(int(ca))).replace("%%", "%")
    if code == 62:
        return "%s %s %s-%s" % (ta, tb, n, m)
    if code in (67,):
        return ("%s +%s %s" % (ta, n, tb)).strip()
    if code == 68:
        return "%s %s %s" % (n, ta, tb)
    if code == 25:
        return ta
    if ta or tb:
        if ca or cb:
            return ("%s %s %s" % (ta, n, tb)).strip()
        return ("%s %s" % (ta, tb)).strip()
    return None


def synergy_lines(book, s):
    """'Receives bonuses from' lines (dsc3) - the D2 synergies."""
    d = s.desc or {}
    env = SkillEnv(book, s, max(1, book.level(s.key)))
    out = []
    for i in range(1, 8):
        code = _int(d.get("dsc3line%d" % i))
        if not code:
            continue
        ta, tb = _desc_text(s, d.get("dsc3texta%d" % i)), _desc_text(s, d.get("dsc3textb%d" % i))
        ca = evaluate(d.get("dsc3calca%d" % i, ""), env) if d.get("dsc3calca%d" % i) else 0
        if code == 40:
            out.append("Receives bonuses from:")
        elif code == 63:
            out.append("%s: +%s%% %s" % (ta, _fmt_num(ca), tb))
        elif code == 18:
            out.append(ta)
        elif ta:
            out.append(("%s %s" % (ta, tb)).strip())
    return out


# ---------------------------------------------------------------- built-in Barbarian text / passives
def describe_skill(name, lv):
    L = lv - 1
    d = {
        "Bash": ["Powerful blow that knocks the target back", "+%d%% damage, +%d%% attack rating" % (50 + 5 * L, 20 + 5 * L)],
        "Double Swing": ["Two attacks in one action", "+%d%% attack rating" % (15 + 5 * L)],
        "Stun": ["The target loses its next %d turn(s)" % (1 + L // 6), "+%d%% attack rating" % (5 + 5 * L)],
        "Leap": ["Jump up to %d cells, knocking nearby enemies back" % (4 + L // 3)],
        "Leap Attack": ["Leap to a monster and strike", "+%d%% damage, +%d%% attack rating" % (100 + 30 * L, 50 + 15 * L)],
        "Concentrate": ["Uninterruptible attack, +%d%% defense this turn" % (100 + 10 * L), "+%d%% damage" % (70 + 5 * L)],
        "Frenzy": ["Two hits; each hit gives +1 AP next turn (max 3)", "+%d%% damage" % (90 + 5 * L)],
        "Whirlwind": ["Spin through enemies, hitting everything you pass", "%d%% damage" % (50 + 8 * L)],
        "Berserk": ["Hit with magic damage, but your defense drops to 0", "+%d%% damage" % (150 + 15 * L)],
        "Double Throw": ["Throwing weapons only (not implemented yet)"],
        "Howl": ["Monsters within %d cells flee for %d turns" % (4 + L // 2, 2 + L // 4)],
        "Find Potion": ["Search a corpse for a potion (%d%% chance)" % min(100, 30 + 5 * L)],
        "Taunt": ["Target attacks you, -%d%% damage and -%d%% attack" % (5 + 2 * L, 5 + 2 * L)],
        "Shout": ["+%d%% defense for %d turns" % (100 + 10 * L, 6 + L)],
        "Find Item": ["Search a corpse for an item (%d%% chance)" % min(60, 15 + 3 * L)],
        "Battle Cry": ["Monsters within %d cells: -%d%% defense, -%d%% damage" % (5, 50 + 2 * L, 25 + L)],
        "Battle Orders": ["+%d%% max life and mana for %d turns" % (35 + 3 * L, 8 + L)],
        "Grim Ward": ["Turn a corpse into a totem that scares monsters"],
        "War Cry": ["%d-%d damage to monsters around you and stuns them" % (20 + 6 * L, 30 + 6 * L)],
        "Battle Command": ["+1 to all skills for %d turns" % (6 + L)],
        "Increased Stamina": ["+1 action point" + (" (+2 from level 10)" if lv < 10 else " (+2)")],
        "Increased Speed": ["+1 action point" + (" (+2 from level 8)" if lv < 8 else " (+2)")],
        "Iron Skin": ["+%d%% defense" % (30 + 10 * L)],
        "Natural Resistance": ["+%d%% to all resistances" % min(80, 12 + 4 * L)],
    }
    if name in MASTERY_TYPES:
        return ["+%d%% damage, +%d%% attack rating" % (28 + 8 * L, 28 + 5 * L), "with the matching weapon type"]
    return d.get(name, [""])


# D2 stat -> this game's stat (same names as the item mods, so Player.mod() can sum both)
STAT_MAP = {
    "damagepercent": "ed", "tohit": "ar", "item_tohit_percent": "ar_pct", "armorclass": "def",
    "skill_armor_percent": "def_pct", "item_armor_percent": "def_pct", "fireresist": "res_fire",
    "coldresist": "res_cold", "lightresist": "res_ltng", "poisonresist": "res_pois", "velocitypercent": "frw",
    "attackrate": "ias", "strength": "str", "dexterity": "dex", "hitpoints": "life", "item_maxhp_percent": "life_pct",
    "item_maxmana_percent": "mana_pct", "thorns": "thorns", "thorns_percent": "thorns_pct", "toblock": "block",
    "manarecoverybonus": "mana_regen_pct", "passive_fire_mastery": "fire_mastery",
    "passive_ltng_mastery": "ltng_mastery", "passive_cold_mastery": "cold_mastery", "passive_cold_pierce": "cold_pierce",
    "passive_fire_pierce": "fire_pierce", "passive_ltng_pierce": "ltng_pierce", "passive_pois_pierce": "pois_pierce",
    "passive_critical_strike": "crit", "passive_dodge": "dodge", "passive_avoid": "avoid", "passive_evade": "evade",
    "skill_pierce": "pierce", "passive_mastery_melee_th": "mastery_ar", "passive_mastery_melee_dmg": "mastery_ed",
    "passive_mastery_melee_crit": "mastery_crit", "passive_mastery_throw_th": "mastery_ar",
    "passive_mastery_throw_dmg": "mastery_ed", "passive_mastery_throw_crit": "mastery_crit",
    "passive_weaponblock": "weapon_block", "item_absorbfire_percent": "absorb_fire", "item_allskills": "all_skills",
    "lifedrainmindam": "ll", "item_normaldamage": "flat_min", "passive_summon_resist": "summon_res",
    "skill_staminapercent": "", "item_undeaddamage_percent": "ed_undead", "item_undead_tohit": "ar_undead",
    "maxfireresist": "", "maxcoldresist": "", "maxlightresist": "", "maxpoisonresist": "",
}


def passive_bonuses(book, player):
    """Stat bonuses from learned passives (applied in Player.recalc)."""
    out = {"ed": 0, "ar_pct": 0, "def_pct": 0, "ap": 0, "res": 0}
    weapon = player.equipment.get("weapon")
    base = getattr(weapon, "base", None) if weapon is not None else None
    wtypes = set(base.get("ancestors", ())) if isinstance(base, dict) else set()
    if weapon is not None and isinstance(base, dict) and base.get("type"):
        wtypes.add(base.get("type"))
    if any(s.data is not None for s in book.tree.values()):
        return _d2_passives(book, player, wtypes, out)
    for name, types in MASTERY_TYPES.items():
        lv = book.level(name)
        if lv and weapon is not None and wtypes & types:
            out["ed"] += 28 + 8 * (lv - 1)
            out["ar_pct"] += 28 + 5 * (lv - 1)
    lv = book.level("Iron Skin")
    if lv:
        out["def_pct"] += 30 + 10 * (lv - 1)
    lv = book.level("Natural Resistance")
    if lv:
        out["res"] += min(80, 12 + 4 * (lv - 1))
    lv = book.level("Increased Stamina")
    if lv:
        out["ap"] += 1 + (1 if lv >= 10 else 0)
    lv = book.level("Increased Speed")
    if lv:
        out["ap"] += 1 + (1 if lv >= 8 else 0)
    return out


def _d2_passives(book, player, wtypes, out):
    stats = {}
    for key, s in book.tree.items():
        if s.kind != "passive":
            continue
        lv = book.level(key)
        if lv <= 0:
            continue
        env = SkillEnv(book, s, lv)
        itype = s.data.get("passiveitype", "")
        if key in MASTERY_TYPES:
            ok = bool(wtypes & MASTERY_TYPES[key])
        elif itype:
            ok = itype in wtypes or (itype in ("h2h",) and "h2h" in wtypes) or (itype == "miss" and wtypes & {"bow", "xbow", "miss"})
        else:
            ok = True
        if not ok:
            continue
        for st, v in env.stats("passivestat", 5):
            ours = STAT_MAP.get(st)
            if ours:
                stats[ours] = stats.get(ours, 0) + v
        if key == "Natural Resistance":
            pass
    # masteries feed damage / AR; speed passives give AP
    out["ed"] += stats.pop("mastery_ed", 0)
    out["ar_pct"] += stats.pop("mastery_ar", 0)
    out["crit"] = stats.pop("mastery_crit", 0) + stats.pop("crit", 0)
    out["def_pct"] += stats.pop("def_pct", 0)
    frw = stats.pop("frw", 0)
    out["ap"] += (1 if frw >= 10 else 0) + (1 if frw >= 30 else 0)
    if book.level("Increased Stamina"):
        out["ap"] += 1
    for k, v in stats.items():
        out[k] = out.get(k, 0) + v
    return out
