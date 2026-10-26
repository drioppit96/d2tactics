"""Items, affixes and drop tables (a simplified version of D2's item system).

`code` fields are the real D2 item codes, so the D2 asset loader can later look up
the matching inventory icon (data/global/items/inv<code>.dc6) for each item.
"""
import random

WHITE = (230, 230, 230)
BLUE = (110, 110, 255)
GOLD_COLOR = (199, 179, 119)  # D2 unique / gold text colour
ORANGE = (255, 168, 0)

SLOTS = ["weapon", "helm", "armor", "gloves", "boots", "amulet", "ring1", "ring2"]

# name, code, slot, item level, stats
BASES = [
    # weapons: dmg range, AP cost per swing
    dict(name="Club",         code="clb", slot="weapon", qlvl=1, dmg=(1, 6),  ap=3),
    dict(name="Hand Axe",     code="hax", slot="weapon", qlvl=1, dmg=(3, 6),  ap=3),
    dict(name="Short Sword",  code="ssd", slot="weapon", qlvl=1, dmg=(2, 7),  ap=3),
    dict(name="Scimitar",     code="scm", slot="weapon", qlvl=3, dmg=(2, 6),  ap=2),
    dict(name="Mace",         code="mac", slot="weapon", qlvl=4, dmg=(3, 10), ap=4),
    dict(name="Axe",          code="axe", slot="weapon", qlvl=5, dmg=(4, 11), ap=4),
    dict(name="Long Sword",   code="lsd", slot="weapon", qlvl=7, dmg=(3, 19), ap=4),
    # armour: defence range
    dict(name="Cap",          code="cap", slot="helm",   qlvl=1, df=(3, 5)),
    dict(name="Skull Cap",    code="skp", slot="helm",   qlvl=5, df=(8, 11)),
    dict(name="Quilted Armor", code="qui", slot="armor", qlvl=1, df=(8, 11)),
    dict(name="Leather Armor", code="lea", slot="armor", qlvl=3, df=(14, 17)),
    dict(name="Hard Leather Armor", code="hla", slot="armor", qlvl=5, df=(21, 24)),
    dict(name="Leather Gloves", code="lgl", slot="gloves", qlvl=1, df=(2, 3)),
    dict(name="Boots",        code="lbt", slot="boots",  qlvl=1, df=(2, 3)),
    # jewellery: only drops magic
    dict(name="Ring",         code="rin", slot="ring",   qlvl=1, magic_only=True),
    dict(name="Amulet",       code="amu", slot="amulet", qlvl=1, magic_only=True),
]

# (name, allowed slots or None for any, stat, (min, max))
PREFIXES = [
    ("Jagged",     {"weapon"},                 "ed",      (10, 20)),
    ("Bronze",     {"weapon", "gloves", "ring", "amulet"}, "ar", (10, 20)),
    ("Sturdy",     {"helm", "armor", "gloves", "boots"},   "edef", (10, 20)),
    ("Lizard's",   {"helm", "ring", "amulet"}, "mana",    (1, 5)),
    ("Glimmering", None,                       "light",   (1, 1)),
]
SUFFIXES = [
    ("of the Jackal",  None,                     "life",   (1, 5)),
    ("of the Fox",     {"armor", "helm", "amulet", "ring"}, "life", (6, 10)),
    ("of Strength",    None,                     "str",    (1, 2)),
    ("of Dexterity",   None,                     "dex",    (1, 2)),
    ("of Thorns",      {"armor"},                "thorns", (1, 3)),
    ("of Haste",       {"boots"},                "ap",     (1, 1)),
    ("of Blight",      {"weapon"},               "mindmg", (1, 2)),
]

STAT_LABELS = {
    "ed": "+{}% Enhanced Damage", "ar": "+{} to Attack Rating", "edef": "+{}% Enhanced Defense",
    "mana": "+{} to Mana", "light": "+{} to Light Radius", "life": "+{} to Life",
    "str": "+{} to Strength", "dex": "+{} to Dexterity", "thorns": "Attacker Takes Damage of {}",
    "ap": "+{} Action Point", "mindmg": "+{} to Minimum Damage", "vit": "+{} to Vitality",
}


class Item:
    def __init__(self, name, code, slot, rarity="normal", mods=None, dmg=None, ap=None,
                 defense=0, amount=0, kind="equip"):
        self.name = name
        self.code = code
        self.slot = slot
        self.rarity = rarity
        self.mods = mods or {}
        self.dmg = dmg
        self.ap = ap
        self.defense = defense
        self.amount = amount  # gold amount / potion heal
        self.kind = kind      # equip | gold | potion

    @property
    def color(self):
        if self.kind == "gold":
            return WHITE
        if self.rarity == "magic":
            return BLUE
        if self.rarity == "unique":
            return GOLD_COLOR
        return WHITE

    def describe(self):
        lines = [self.name]
        if self.kind == "gold":
            return [f"{self.amount} Gold"]
        if self.kind == "potion":
            return [self.name, f"Heals {self.amount} life", "2 AP to drink (keys 1-4)"]
        if self.dmg:
            lo, hi = self.dmg
            lines.append(f"Damage: {lo} to {hi}")
            lines.append(f"Attack cost: {self.ap} AP")
        if self.defense:
            lines.append(f"Defense: {self.defense}")
        for stat, val in self.mods.items():
            lines.append(STAT_LABELS.get(stat, stat + " {}").format(val))
        return lines


def make_gold(level, rng=random):
    amt = rng.randint(1, 8) * max(1, level) + rng.randint(0, 6)
    return Item("Gold", "gld", None, amount=amt, kind="gold")


def make_potion(level, rng=random):
    if level >= 4 and rng.random() < 0.5:
        return Item("Light Healing Potion", "hp2", None, amount=45, kind="potion")
    return Item("Minor Healing Potion", "hp1", None, amount=25, kind="potion")


def _roll_affix(table, slot, rng):
    choices = [a for a in table if a[1] is None or slot in a[1]]
    if not choices:
        return None
    name, _, stat, (lo, hi) = rng.choice(choices)
    return name, stat, rng.randint(lo, hi)


def make_item(level, magic_chance=0.25, rng=random):
    bases = [b for b in BASES if b["qlvl"] <= max(1, level)]
    base = rng.choice(bases)
    slot = base["slot"]
    magic = base.get("magic_only") or rng.random() < magic_chance
    mods = {}
    name = base["name"]
    if magic:
        affix_slot = slot
        pre = _roll_affix(PREFIXES, affix_slot, rng) if rng.random() < 0.7 else None
        suf = _roll_affix(SUFFIXES, affix_slot, rng) if (pre is None or rng.random() < 0.6) else None
        if pre is None and suf is None:
            suf = _roll_affix(SUFFIXES, affix_slot, rng)
        if pre:
            name = f"{pre[0]} {name}"
            mods[pre[1]] = mods.get(pre[1], 0) + pre[2]
        if suf:
            name = f"{name} {suf[0]}"
            mods[suf[1]] = mods.get(suf[1], 0) + suf[2]
    defense = rng.randint(*base["df"]) if "df" in base else 0
    if defense and "edef" in mods:
        defense = defense * (100 + mods["edef"]) // 100
    return Item(name, base["code"], slot, "magic" if magic else "normal", mods,
                dmg=base.get("dmg"), ap=base.get("ap"), defense=defense)


def roll_drop(mlevel, is_boss=False, rng=random):
    """Returns a list of items a dying monster drops."""
    if is_boss:
        drops = [make_gold(mlevel * 3, rng), make_potion(mlevel, rng)]
        drops += [make_item(mlevel + 2, magic_chance=1.0, rng=rng) for _ in range(2)]
        drops.append(make_item(mlevel + 2, magic_chance=0.5, rng=rng))
        return drops
    r = rng.random()
    if r < 0.50:
        return []
    if r < 0.72:
        return [make_gold(mlevel, rng)]
    if r < 0.88:
        return [make_potion(mlevel, rng)]
    return [make_item(mlevel, rng=rng)]
