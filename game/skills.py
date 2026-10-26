"""Barbarian skills, turn-based.

The tree (pages, rows, columns, prerequisites, required levels, mana, icon numbers) comes
from D2's Skills.txt / SkillDesc.txt when available, with a built-in copy as fallback.
How each skill plays on a grid is defined here.
"""

# name: (page, row, col, reqlevel, prereqs, mana, icon, kind)
#   kind: attack (targets an adjacent monster), move (targets a cell), cry (around you), passive
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
PAGE_NAMES = {1: "Combat Skills", 2: "Combat Masteries", 3: "Warcries"}

# weapon type codes each mastery applies to
MASTERY_TYPES = {"Sword Mastery": {"swor", "knif"}, "Axe Mastery": {"axe"}, "Mace Mastery": {"mace", "hamm", "club", "scep", "blun"},
                 "Pole Arm Mastery": {"pole"}, "Spear Mastery": {"spea"}, "Throwing Mastery": {"thro", "jave", "taxe", "tkni"}}


class Skill:
    def __init__(self, name, page, row, col, reqlevel, prereqs, mana, icon, kind):
        self.name, self.page, self.row, self.col = name, page, row, col
        self.reqlevel, self.prereqs, self.mana, self.icon, self.kind = reqlevel, tuple(prereqs), mana, icon, kind


def load_tree(src=None):
    """Barbarian tree; positions/requirements from D2's tables when a source is given."""
    tree = {n: Skill(n, *v) for n, v in BUILTIN.items()}
    if src is None:
        return tree
    try:
        from d2.source import read_table
        descs = {r["skilldesc"]: r for r in read_table(src, "SkillDesc") if r.get("skilldesc")}
        for r in read_table(src, "Skills"):
            if r.get("charclass") != "bar" or r.get("skill") not in tree:
                continue
            s = tree[r["skill"]]
            d = descs.get(r.get("skilldesc"), {})
            s.reqlevel = int(r.get("reqlevel") or s.reqlevel)
            s.prereqs = tuple(x for x in (r.get("reqskill1"), r.get("reqskill2"), r.get("reqskill3")) if x)
            s.mana = int(r.get("mana") or 0) or s.mana
            if d.get("skillpage"):
                s.page, s.row, s.col = int(d["skillpage"]), int(d["skillrow"]), int(d["skillcolumn"])
            if d.get("iconcel"):
                s.icon = int(d["iconcel"])
    except Exception:
        pass
    return tree


class SkillBook:
    """What a character has learned."""

    def __init__(self, tree):
        self.tree = tree
        self.levels = {}
        self.points = 1            # one point to spend right away
        self.bonus = 0             # +skills from Battle Command

    def level(self, name):
        base = self.levels.get(name, 0)
        return base + self.bonus if base else 0

    def can_learn(self, name, clvl):
        s = self.tree.get(name)
        if not s or self.points <= 0 or clvl < s.reqlevel or self.levels.get(name, 0) >= 20:
            return False
        return all(self.levels.get(p, 0) > 0 for p in s.prereqs)

    def learn(self, name, clvl):
        if not self.can_learn(name, clvl):
            return False
        self.levels[name] = self.levels.get(name, 0) + 1
        self.points -= 1
        return True

    def actives(self):
        return [n for n in self.levels if self.tree[n].kind != "passive"]

    # ------------------------------------------------------------ numbers per skill level
    def mana_cost(self, name):
        s = self.tree[name]
        lv = self.level(name)
        if name == "Double Swing":
            return max(2, 8 - (lv - 1) // 4)
        if name == "Whirlwind":
            return 25 + (lv - 1) // 4
        if name == "War Cry":
            return 10 + (lv - 1) // 4
        return s.mana

    def ap_cost(self, name, weapon_ap):
        s = self.tree[name]
        if s.kind == "cry" or s.kind == "corpse":
            return 3
        if name in ("Double Swing", "Frenzy"):
            return weapon_ap + 2
        if name == "Leap":
            return 3
        if name in ("Leap Attack", "Whirlwind"):
            return weapon_ap + 3
        if name == "Taunt":
            return 2
        return weapon_ap + 1

    def describe(self, name):
        """Short effect text for the current level (and the next one) - tooltip lines."""
        lv = max(1, self.level(name))
        return describe_skill(name, lv)


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


def passive_bonuses(book, player):
    """Stat bonuses from learned passives (applied in Player.recalc)."""
    out = {"ed": 0, "ar_pct": 0, "def_pct": 0, "ap": 0, "res": 0}
    weapon = player.equipment.get("weapon")
    base = getattr(weapon, "base", None) if weapon is not None else None
    wtypes = set(base.get("ancestors", ())) if isinstance(base, dict) else set()
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
