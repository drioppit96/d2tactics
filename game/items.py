"""Items, affixes and drop tables (a simplified version of D2's item system).

`code` fields are the real D2 item codes, so the D2 asset loader can later look up
the matching inventory icon (data/global/items/inv<code>.dc6) for each item.
"""
import random

WHITE = (230, 230, 230)
BLUE = (110, 110, 255)
GOLD_COLOR = (199, 179, 119)  # D2 unique / gold text colour
ORANGE = (255, 168, 0)

SLOTS = ["weapon", "shield", "helm", "armor", "gloves", "belt", "boots", "amulet", "ring1", "ring2"]

# D2 item name colours
D2_COLORS = {"normal": (230, 230, 230), "magic": (105, 105, 255), "rare": (255, 255, 100),
             "set": (0, 252, 0), "unique": (199, 179, 119), "crafted": (255, 168, 0)}
RED_TEXT = (255, 80, 80)

# D2-style property lines for mods; {0}/{1} = value or min/max
MOD_TEXT = {
    "dmg%": "+{0}% Enhanced Damage", "att": "+{0} to Attack Rating", "att%": "{0}% Bonus to Attack Rating",
    "ac": "+{0} Defense", "ac%": "+{0}% Enhanced Defense", "hp": "+{0} to Life", "mana": "+{0} to Mana",
    "str": "+{0} to Strength", "dex": "+{0} to Dexterity", "vit": "+{0} to Vitality", "enr": "+{0} to Energy",
    "light": "+{0} to Light Radius", "thorns": "Attacker Takes Damage of {0}",
    "dmg-min": "+{0} to Minimum Damage", "dmg-max": "+{0} to Maximum Damage",
    "move1": "+{0}% Faster Run/Walk", "move2": "+{0}% Faster Run/Walk", "move3": "+{0}% Faster Run/Walk",
    "swing1": "+{0}% Increased Attack Speed", "swing2": "+{0}% Increased Attack Speed",
    "swing3": "+{0}% Increased Attack Speed", "regen": "Replenish Life +{0}",
    "lifesteal": "{0}% Life Stolen per Hit", "manasteal": "{0}% Mana Stolen per Hit",
    "res-fire": "Fire Resist +{0}%", "res-cold": "Cold Resist +{0}%", "res-ltng": "Lightning Resist +{0}%",
    "res-pois": "Poison Resist +{0}%", "res-pois-len": "Poison Length Reduced by {0}%", "res-all": "All Resistances +{0}", "red-dam": "Damage Reduced by {0}",
    "red-mag": "Magic Damage Reduced by {0}", "mag%": "{0}% Better Chance of Getting Magic Items",
    "gold%": "{0}% Extra Gold from Monsters", "block": "{0}% Increased Chance of Blocking",
    "block2": "+{0}% Faster Block Rate", "balance1": "+{0}% Faster Hit Recovery",
    "balance2": "+{0}% Faster Hit Recovery", "balance3": "+{0}% Faster Hit Recovery",
    "cast1": "+{0}% Faster Cast Rate", "cast2": "+{0}% Faster Cast Rate", "cast3": "+{0}% Faster Cast Rate",
    "dmg-fire": "Adds {0}-{1} Fire Damage", "dmg-cold": "Adds {0}-{1} Cold Damage",
    "dmg-ltng": "Adds {0}-{1} Lightning Damage", "dmg-pois": "Adds {0}-{1} Poison Damage",
    "dmg-norm": "Adds {0}-{1} Magic Damage", "red-dmg": "Damage Reduced by {0}", "stam": "+{0} Maximum Stamina",
    "regen-stam": "Heal Stamina Plus {0}%", "att-demon": "+{0} to Attack Rating against Demons",
    "att-undead": "+{0} to Attack Rating against Undead", "mana-kill": "+{0} to Mana after each Kill",
    "ignore-ac": "Ignore Target's Defense", "dmg-ac": "-{0} to Monster Defense Per Hit",
    "ac/lvl": "+{0} Defense (Based on Character Level)", "dmg/lvl": "+{0} to Maximum Damage (Based on Character Level)",
    "mana/lvl": "+{0} to Mana (Based on Character Level)", "dmg": "Adds {0}-{1} Damage", "knock": "Knockback",
    "nofreeze": "Cannot Be Frozen", "howl": "Hit Causes Monster to Flee {0}%",
    "hp%": "Increase Maximum Life {0}%", "mana%": "Increase Maximum Mana {0}%",
    "manarecovery": "Regenerate Mana {0}%", "stamina": "+{0} Maximum Stamina", "dur": "+{0} Maximum Durability",
    "ease": "Requirements {0}%", "openwounds": "{0}% Chance of Open Wounds", "crush": "{0}% Chance of Crushing Blow",
    "deadly": "{0}% Deadly Strike", "slow": "Slows Target by {0}%", "stupidity": "Hit Blinds Target",
    "freeze": "Freezes Target", "rep-dur": "Repairs 1 Durability in {0} Seconds",
    "rep-quant": "Replenishes Quantity", "dmg-to-mana": "{0}% Damage Taken Goes To Mana",
}

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


QUEST_HINTS = {"cube": "Right click to open. Put items in and press Transmute",
               "book_skill": "Right click to read (+1 skill point)",
               "horadric_scroll": "Right click to read",
               "msf": "Cube it with the Viper Amulet",
               "vip": "Cube it with the Staff of Kings",
               "hst": "Place it in the orifice in Tal Rasha's Tomb"}


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
        # filled in for items made from D2's tables
        self.base = None
        self.mod_list = None
        self.levelreq = self.reqstr = self.reqdex = 0
        self.invfile = self.flippy = ""
        self.invw = self.invh = 1
        self.two_handed = False
        self.block = 0
        self.gfx = ""
        self.wclass = ""
        self.look = None
        self.strbonus = self.dexbonus = 0
        self.potion = "heal"
        # sockets, runewords, identification, scrolls/tomes, gems/runes
        self.sockets = 0
        self.socketed = []
        self.runeword = None
        self.identified = True
        self.use = None          # "tp" / "id" for scrolls and tomes
        self.quantity = 0        # tome charges
        self.gem = None          # ("gem", name, grade) / ("rune", n)
        self.affixes = []
        self.extra_lines = []
        self.base_defense = None

    @property
    def color(self):
        if self.kind in ("gold", "potion"):
            return WHITE
        if self.kind == "quest":
            return D2_COLORS["unique"]
        if self.gem is not None:
            return ORANGE if self.gem[0] == "rune" else WHITE
        if self.sockets and self.rarity == "normal":
            return (150, 150, 150)       # D2: socketed white items are grey
        return D2_COLORS.get(self.rarity, WHITE)

    @property
    def shown_name(self):
        if not self.identified and isinstance(self.base, dict):
            return self.base.get("name", self.name)
        return self.runeword or self.name

    def requirements_ok(self, player):
        return (player.level >= self.levelreq and player.strength >= self.reqstr
                and player.dexterity >= self.dexterity_req())

    def dexterity_req(self):
        return self.reqdex

    def describe_lines(self, player=None):
        """[(text, colour)] in D2's tooltip order."""
        if self.kind == "gold":
            return [("%d Gold" % self.amount, WHITE)]
        if self.kind == "quest":
            out = [(self.name, self.color)]
            hint = QUEST_HINTS.get(self.use or self.code)
            if self.code == "box":
                n = len(getattr(self, "contents", []) or [])
                out.append(("Holds %d item%s" % (n, "" if n == 1 else "s"), WHITE))
            if hint:
                out.append((hint, (170, 170, 170)))
            out.append(("Quest Item", (170, 170, 170)))
            return out
        if self.kind == "potion":
            what = {"heal": "Heals %d life", "mana": "Restores %d mana", "rejuv": "Restores %d%% life and mana",
                    "antidote": "Cures poison, +%d%% poison resistance for a while",
                    "thawing": "Thaws you, +%d%% cold resistance for a while",
                    "stamina": "+%d AP next turn"}
            return [(self.name, WHITE), (what.get(self.potion, "%d") % self.amount, WHITE),
                    ("2 AP to drink (keys 1-4 in the belt, right click in the backpack)", (170, 170, 170))]
        if self.use:
            out = [(self.name, WHITE)]
            if self.quantity:
                out.append(("Quantity: %d" % self.quantity, WHITE))
            out.append(("Right click to read" + (" (opens a portal to town)" if self.use == "tp" else
                                                  " (then click an item)"), (170, 170, 170)))
            return out
        if self.gem is not None:
            out = [(self.name, self.color), ("Can be Inserted into Socketed Items", WHITE)]
            out += [(l, WHITE) for l in getattr(self, "filler_lines", [])]
            if self.levelreq > 1:
                ok = player is None or player.level >= self.levelreq
                out.append(("Required Level: %d" % self.levelreq, WHITE if ok else RED_TEXT))
            return out
        if self.mod_list is None:
            return [(l, self.color if i == 0 else WHITE) for i, l in enumerate(self.describe())]
        if self.runeword:
            out = [(self.runeword, D2_COLORS["unique"]), (self.name, (150, 150, 150)),
                   ("'%s'" % "".join(getattr(f, "rune_letter", "") for f in self.socketed), D2_COLORS["unique"])]
        else:
            out = [(self.shown_name, self.color)]
            if self.rarity in ("rare", "crafted") and self.identified and isinstance(self.base, dict):
                out.append((self.base.get("name", ""), self.color))
        if self.dmg:
            lo, hi = self.dmg
            if self.two_handed:
                out.append(("Two-Hand Damage: %d to %d" % (lo, hi), WHITE))
            else:
                out.append(("One-Hand Damage: %d to %d" % (lo, hi), WHITE))
            base = self.base if isinstance(getattr(self, "base", None), dict) else {}
            if "speed" in base:
                ap, label = speed_tier(base["speed"])
                out.append(("%s Attack Speed (%d AP)" % (label, ap), WHITE))
        if self.defense:
            out.append(("Defense: %d" % self.defense, WHITE))
        if self.block:
            out.append(("Chance to Block: %d%%" % self.block, WHITE))

        def req(text, ok):
            out.append((text, WHITE if ok else RED_TEXT))
        if self.reqdex:
            req("Required Dexterity: %d" % self.reqdex, player is None or player.dexterity >= self.reqdex)
        if self.reqstr:
            req("Required Strength: %d" % self.reqstr, player is None or player.strength >= self.reqstr)
        if self.levelreq > 1:
            req("Required Level: %d" % self.levelreq, player is None or player.level >= self.levelreq)
        if not self.identified:
            out.append(("Unidentified", RED_TEXT))
            return out
        from .d2items import EXTRA_TEXT
        for code, v in self.mod_list:
            fmt = MOD_TEXT.get(code) or EXTRA_TEXT.get(code) or (code + " {0}")
            try:
                text = fmt.format(*v) if isinstance(v, tuple) else fmt.format(v)
            except Exception:
                text = code
            out.append((text, D2_COLORS["magic"]))
        for t in self.extra_lines:
            out.append((t, D2_COLORS["magic"]))
        if self.sockets:
            out.append(("Socketed (%d)" % self.sockets, D2_COLORS["magic"]))
            for f in self.socketed:
                out.append(("  " + f.name, (170, 170, 170)))
        return out

    def describe(self):
        if self.mod_list is not None:
            return [t for t, _ in self.describe_lines()]
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


SPEED_TIERS = ((-20, 1, "Very Fast"), (-10, 2, "Fast"), (5, 3, "Normal"), (15, 4, "Slow"), (999, 5, "Very Slow"))


def speed_tier(wsm):
    """Weapon speed modifier (Weapons.txt 'speed', lower = faster) -> (AP per attack, D2 speed name)."""
    for limit, ap, label in SPEED_TIERS:
        if wsm <= limit:
            return ap, label
    return 5, "Very Slow"


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
