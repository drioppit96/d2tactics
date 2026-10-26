"""Player and monsters.

`token` is the D2 sprite token (data/global/chars/<token> or monsters/<token>), so the
D2 asset loader can find the real animation files for each unit.
"""
import random

from .items import Item, SLOTS


class Unit:
    is_player = False

    def __init__(self, name, x, y):
        self.name = name
        self.x, self.y = x, y
        self.level = 1
        self.max_hp = self.hp = 10
        self.max_ap = self.ap = 6
        self.ar = 20
        self.defense = 0
        self.dmg = (1, 3)
        self.attack_cost = 3
        self.range = 1          # 1 = melee
        self.alive = True
        self.facing = (1, 1)
        self.token = "ZM"
        self.color = (150, 150, 150)
        self.unique = False
        self.thorns = 0

    @property
    def pos(self):
        return (self.x, self.y)

    def face(self, tx, ty):
        dx, dy = tx - self.x, ty - self.y
        if dx or dy:
            self.facing = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))


class Player(Unit):
    is_player = True

    def __init__(self, x, y):
        super().__init__("Barbarian", x, y)
        self.token = "BA"
        self.color = (200, 160, 90)
        # D2 Barbarian starting stats
        self.base_str, self.base_dex, self.base_vit, self.base_eng = 30, 20, 25, 10
        self.stat_points = 0
        self.xp = 0
        self.gold = 0
        self.mana = 10
        self.equipment = {s: None for s in SLOTS}
        self.inventory = []
        self.belt = []          # potions, max 4
        self.equipment["weapon"] = Item("Hand Axe", "hax", "weapon", dmg=(3, 6), ap=3)
        self.equipment["armor"] = Item("Quilted Armor", "qui", "armor", defense=9)
        self.recalc()
        self.hp = self.max_hp
        self.mana = self.max_mana
        self.ap = self.max_ap

    def mod(self, stat):
        return sum(it.mods.get(stat, 0) for it in self.equipment.values() if it)

    @property
    def strength(self):
        return self.base_str + self.mod("str")

    @property
    def dexterity(self):
        return self.base_dex + self.mod("dex")

    @property
    def vitality(self):
        return self.base_vit + self.mod("vit")

    def recalc(self):
        """Derived stats, roughly D2's Barbarian formulas."""
        old_max = getattr(self, "max_hp", None)
        self.max_hp = 55 + (self.vitality - 25) * 4 + (self.level - 1) * 2 + self.mod("life")
        self.max_mana = 10 + (self.base_eng - 10) + (self.level - 1) * 1 + self.mod("mana")
        weapon = self.equipment["weapon"]
        lo, hi = weapon.dmg if weapon else (1, 2)
        lo += self.mod("mindmg")
        hi = max(hi, lo)
        mult = 1 + self.strength / 100 + self.mod("ed") / 100
        self.dmg = (max(1, int(lo * mult)), max(1, int(hi * mult)))
        self.attack_cost = weapon.ap if weapon else 3
        self.ar = (self.dexterity - 7) * 5 + 20 + self.mod("ar") + (self.level - 1) * 5
        self.defense = self.dexterity // 4 + sum(it.defense for it in self.equipment.values() if it)
        self.max_ap = 8 + self.mod("ap")
        self.thorns = self.mod("thorns")
        self.light = 9 + self.mod("light")
        if old_max is not None:
            self.hp = min(self.hp, self.max_hp)
            self.mana = min(self.mana, self.max_mana)

    @staticmethod
    def xp_threshold(level):
        """Total XP needed to leave `level` (D2's real table for the first levels)."""
        table = [0, 500, 1500, 3750, 7875, 14175, 22680, 32886, 44396, 57715, 72144]
        if level < len(table):
            return table[level]
        return table[-1] + (level - len(table) + 1) * 20000

    def xp_to_next(self):
        return self.xp_threshold(self.level)

    def gain_xp(self, amount):
        """Returns number of levels gained."""
        self.xp += amount
        gained = 0
        while self.xp >= self.xp_to_next():
            self.level += 1
            self.stat_points += 5
            gained += 1
            self.recalc()
            self.hp = self.max_hp
            self.mana = self.max_mana
        return gained


# Monster templates. xp values are scaled up from D2 so levelling happens in a short dungeon.
MONSTERS = {
    "zombie":  dict(name="Zombie",       token="ZM", hp=(12, 16), dmg=(2, 5), ar=25, df=2,  ap=4, cost=4, rng=1, xp=110, color=(110, 140, 90),  ai="melee"),
    "fallen":  dict(name="Fallen",       token="FA", hp=(5, 8),   dmg=(1, 3), ar=30, df=4,  ap=7, cost=3, rng=1, xp=45,  color=(200, 70, 60),   ai="fallen"),
    "shaman":  dict(name="Fallen Shaman", token="FS", hp=(8, 10), dmg=(2, 4), ar=40, df=3,  ap=6, cost=4, rng=6, xp=90,  color=(230, 120, 40),  ai="shaman"),
    "quill":   dict(name="Quill Rat",    token="SI", hp=(6, 9),   dmg=(1, 3), ar=35, df=3,  ap=6, cost=3, rng=5, xp=60,  color=(150, 120, 90),  ai="ranged"),
    "corpsefire": dict(name="Corpsefire", token="ZM", hp=(70, 70), dmg=(4, 9), ar=60, df=12, ap=5, cost=4, rng=1, xp=900, color=(220, 200, 120), ai="melee", unique=True),
}


class Monster(Unit):
    def __init__(self, kind, x, y, level=1, rng=random):
        t = MONSTERS[kind]
        super().__init__(t["name"], x, y)
        self.kind = kind
        self.level = level
        self.token = t["token"]
        self.max_hp = self.hp = rng.randint(*t["hp"]) + (level - 1) * 2
        lo, hi = t["dmg"]
        self.dmg = (lo + (level - 1) // 2, hi + (level - 1) // 2)
        self.ar = t["ar"] + (level - 1) * 8
        self.defense = t["df"] + (level - 1) * 2
        self.max_ap = self.ap = t["ap"]
        self.attack_cost = t["cost"]
        self.range = t["rng"]
        self.xp_value = t["xp"] + (level - 1) * t["xp"] // 3
        self.color = t["color"]
        self.ai = t["ai"]
        self.unique = t.get("unique", False)
        self.aware = False
        self.panic = 0       # fallen run away for a turn when a pack mate dies
        self.home = (x, y)
