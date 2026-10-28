"""Player and monsters.

`token` is the D2 sprite token (data/global/chars/<token> or monsters/<token>), so the
D2 asset loader can find the real animation files for each unit.
"""
import random

from .items import Item, SLOTS


ATTACK_AP_OFFSET = 0  # added to every attack's AP (settings.ini [game] attack_ap_offset)
AP_LEVELS = (10, 20, 30, 45, 60, 80)   # +1 max AP at each of these character levels


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
        self.radius = 0         # big monsters (D2 size 3) fill the 3x3 cells around them

    @property
    def pos(self):
        return (self.x, self.y)

    def face(self, tx, ty):
        dx, dy = tx - self.x, ty - self.y
        if dx or dy:
            self.facing = ((dx > 0) - (dx < 0), (dy > 0) - (dy < 0))


# D2 CharStats.txt: str dex int vit, hpadd, to-hit factor, life/mana per level and per point (x4), block factor
CLASS_STATS = {
    "ama": dict(name="Amazon", token="AM", stats=(20, 25, 15, 20), hpadd=30, thf=5, lpl=8, mpl=6, lpv=12, mpm=6, block=25),
    "sor": dict(name="Sorceress", token="SO", stats=(10, 25, 35, 10), hpadd=30, thf=-15, lpl=4, mpl=8, lpv=8, mpm=8, block=20),
    "nec": dict(name="Necromancer", token="NE", stats=(15, 25, 25, 15), hpadd=30, thf=-10, lpl=6, mpl=8, lpv=8, mpm=8, block=20),
    "pal": dict(name="Paladin", token="PA", stats=(25, 20, 15, 25), hpadd=30, thf=20, lpl=8, mpl=6, lpv=12, mpm=6, block=30),
    "bar": dict(name="Barbarian", token="BA", stats=(30, 20, 10, 25), hpadd=30, thf=20, lpl=8, mpl=4, lpv=16, mpm=4, block=25),
    "dru": dict(name="Druid", token="DZ", stats=(15, 20, 20, 25), hpadd=30, thf=5, lpl=6, mpl=8, lpv=8, mpm=8, block=20),
    "ass": dict(name="Assassin", token="AI", stats=(20, 20, 25, 20), hpadd=30, thf=15, lpl=8, mpl=6, lpv=12, mpm=7, block=25),
}
# starting gear (CharStats item1..: right hand, left hand) - codes of Weapons/Armor.txt
CLASS_KIT = {"ama": ("jav", "buc"), "sor": ("sst", None), "nec": ("wnd", None), "pal": ("ssd", "buc"),
             "bar": ("hax", "buc"), "dru": ("clb", "buc"), "ass": ("ktr", "buc")}
# the skill every class starts with points in? (D2 gives none; this game gives one free point)


class Player(Unit):
    is_player = True

    def __init__(self, x, y, cls="bar", name=None, tree=None):
        cs = CLASS_STATS.get(cls, CLASS_STATS["bar"])
        super().__init__(name or cs["name"], x, y)
        self.cls = cls
        self.class_name = cs["name"]
        self.cs = cs
        self.token = cs["token"]
        self.color = (200, 160, 90)
        self.base_str, self.base_dex, self.base_eng, self.base_vit = cs["stats"]
        self.start_stats = (self.base_str, self.base_dex, self.base_eng, self.base_vit)
        self.stat_points = 0
        self.xp = 0
        self.gold = 0
        self.mana = 10
        self.equipment = {s: None for s in SLOTS}
        self.inventory = []
        self.belt = []          # potions, max 4
        from .skills import SkillBook, load_tree
        self.skills = SkillBook(tree if tree is not None else load_tree(), cls)
        self.right_skill = None     # skill used with the right mouse button
        self.active_aura = None     # Paladin aura (the right skill when it is an aura)
        self.effects = {}           # Barbarian warcry buffs: name -> turns left
        self.buffs = {}             # other classes' buffs: skill -> {"turns", "stats", ...}
        self.shape = None           # Druid: wolf / bear
        self.frenzy = 0             # Frenzy charges -> bonus AP next turn
        self.bonus = {}
        self.aura_source = None     # callable -> aura stats (set by the World)
        if cls == "bar" and tree is None:
            self.equipment["weapon"] = Item("Hand Axe", "hax", "weapon", dmg=(3, 6), ap=3)
            self.equipment["armor"] = Item("Quilted Armor", "qui", "armor", defense=9)
        else:
            self.equipment["weapon"] = Item("Club", "clb", "weapon", dmg=(1, 6), ap=3)
        self.recalc()
        self.hp = self.max_hp
        self.mana = self.max_mana
        self.ap = self.max_ap

    # ------------------------------------------------------------ D2 backpack: 10 x 4 cells
    INV_W, INV_H = 10, 4

    def _size(self, it):
        return max(1, getattr(it, "invw", 1) or 1), max(1, getattr(it, "invh", 1) or 1)

    def inv_cells(self, ignore=None):
        taken = {}
        for it in self.inventory:
            if it is ignore or getattr(it, "inv_pos", None) is None:
                continue
            w, h = self._size(it)
            x0, y0 = it.inv_pos
            for y in range(y0, y0 + h):
                for x in range(x0, x0 + w):
                    taken[(x, y)] = it
        return taken

    def inv_fits(self, it, x0, y0, ignore=None):
        """-> (fits inside the grid, list of items overlapped)"""
        w, h = self._size(it)
        if x0 < 0 or y0 < 0 or x0 + w > self.INV_W or y0 + h > self.INV_H:
            return False, []
        taken = self.inv_cells(ignore)
        over = []
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                o = taken.get((x, y))
                if o is not None and o not in over:
                    over.append(o)
        return True, over

    def inv_add(self, it):
        """Put an item in the first free spot (columns left to right, like D2). False if full."""
        w, h = self._size(it)
        for x0 in range(self.INV_W - w + 1):
            for y0 in range(self.INV_H - h + 1):
                ok, over = self.inv_fits(it, x0, y0)
                if ok and not over:
                    it.inv_pos = (x0, y0)
                    self.inventory.append(it)
                    return True
        return False

    def inv_at(self, x, y):
        return self.inv_cells().get((x, y))

    def active_items(self):
        """Equipped items whose requirements are met (D2 ignores the rest)."""
        out = []
        for it in self.equipment.values():
            if it and (it.mod_list is None or (self.level >= it.levelreq and self.base_str + self._raw("str") >= it.reqstr
                                                and self.base_dex + self._raw("dex") >= it.reqdex)):
                out.append(it)
        return out

    def _raw(self, stat):
        return sum(it.mods.get(stat, 0) for it in self.equipment.values()
                   if it and not isinstance(it.mods.get(stat, 0), tuple))

    def mod(self, stat):
        v0 = getattr(self, "_skill_stats", {}).get(stat, 0)
        v0 = 0 if isinstance(v0, tuple) else v0
        active = [it for it in getattr(self, "_active", []) if getattr(it, "identified", True)]
        v = v0 + sum(it.mods.get(stat, 0) for it in active if not isinstance(it.mods.get(stat, 0), tuple))
        # D2's "per character level" properties: value / 8 per level
        per = sum(it.mods.get(stat + "@lvl", 0) for it in active)
        if per:
            v += per * self.level // 8
        return v

    def set_bonuses(self):
        """Bonuses of the set items you wear (more pieces, more bonuses; all of them: the full set)."""
        from .items import Item
        from . import props
        worn = {}
        for it in self._active:
            if getattr(it, "set_name", None) and getattr(it, "identified", True):
                worn.setdefault(it.set_name, []).append(it)
        self.sets_worn = {k: sorted({getattr(i, "set_item", "") for i in v}) for k, v in worn.items()}
        holder = Item("Set bonuses", "", None, kind="equip")
        holder.mod_list = []
        any_bonus = False
        for name, items in worn.items():
            n = len(self.sets_worn[name])
            for it in items:
                for k, plist in getattr(it, "set_bonus", []) or []:
                    if n >= k + 1:
                        props.apply(holder, plist, roll=False)
                        any_bonus = True
            sd = getattr(items[0], "set_def", None) or {}
            for k, plist in sd.get("partial", {}).items():
                if n >= k:
                    props.apply(holder, plist, roll=False)
                    any_bonus = True
            if sd.get("members") and n >= len(sd["members"]):
                props.apply(holder, sd.get("full", []), roll=False)
                any_bonus = True
        holder.defense = 0
        return holder if any_bonus else None

    def mod_range(self, stat):
        lo = hi = 0
        sv = getattr(self, "_skill_stats", {}).get(stat)
        if isinstance(sv, tuple):
            lo, hi = sv
        for it in getattr(self, "_active", []):
            if not getattr(it, "identified", True):
                continue
            v = it.mods.get(stat)
            if isinstance(v, tuple):
                lo += v[0]
                hi += v[1]
        return lo, hi

    def _skill_items(self):
        """+skills from items: all skills, +class skills, +skill tab, +single skill."""
        sk = getattr(self, "skills", None)
        if sk is None:
            return
        from .props import CLASS_CODES
        ci = CLASS_CODES.index(self.cls) if self.cls in CLASS_CODES else -1
        tot = {}
        for it in self._active:
            if not getattr(it, "identified", True):
                continue
            for k, v in it.mods.items():
                if isinstance(v, tuple):
                    continue
                if k in ("all_skills", "cls_" + self.cls) or k.startswith(("tab_", "sk_")):
                    tot[k] = tot.get(k, 0) + v
        sk.item_bonus = tot.get("all_skills", 0) + tot.get("cls_" + self.cls, 0)
        sk.tab_bonus = {}
        sk.single_bonus = {}
        for k, v in tot.items():
            if k.startswith("tab_"):
                try:
                    t = int(k[4:])
                except ValueError:
                    continue
                if t // 3 == ci:
                    sk.tab_bonus[t % 3 + 1] = sk.tab_bonus.get(t % 3 + 1, 0) + v
            elif k.startswith("sk_"):
                s = sk.find(k[3:])
                if s is not None:
                    sk.single_bonus[s.name] = sk.single_bonus.get(s.name, 0) + v

    def _gather_skill_stats(self):
        """Buffs, the active aura and passives, as item-style stats."""
        out = {}

        def add(k, v):
            if isinstance(v, tuple):
                a = out.get(k, (0, 0))
                a = a if isinstance(a, tuple) else (0, 0)
                out[k] = (a[0] + v[0], a[1] + v[1])
            else:
                out[k] = out.get(k, 0) + v
        for b in getattr(self, "buffs", {}).values():
            for k, v in b.get("stats", {}).items():
                add(k, v)
        for k, v in (getattr(self, "quest_stats", None) or {}).items():     # Potion of Life, Malah's scroll
            add(k, v)
        if self.aura_source is not None:
            try:
                for k, v in self.aura_source().items():
                    add(k, v)
            except Exception:
                pass
        return out

    @property
    def strength(self):
        return self.base_str + self.mod("str")

    @property
    def dexterity(self):
        return self.base_dex + self.mod("dex")

    @property
    def vitality(self):
        return self.base_vit + self.mod("vit")

    @property
    def energy(self):
        return self.base_eng + self.mod("eng")

    def recalc(self):
        """Derived stats with D2's formulas for the character's class (CharStats.txt)."""
        cs = self.cs
        self._skill_stats = {}
        from .skills import passive_bonuses
        pb = passive_bonuses(self.skills, self) if hasattr(self, "skills") else {"ed": 0, "ar_pct": 0, "def_pct": 0, "ap": 0, "res": 0}
        extra = self._gather_skill_stats()
        for k, v in pb.items():
            if k in ("ed", "ar_pct", "def_pct", "ap", "res"):
                continue
            if isinstance(v, tuple):
                extra[k] = v
            else:
                extra[k] = extra.get(k, 0) + v
        self._skill_stats = extra
        self.bonus = dict(pb)
        self.bonus.update({k: v for k, v in extra.items() if not isinstance(v, tuple)})
        self._active = self.active_items()
        sb = self.set_bonuses()
        if sb is not None:
            self._active.append(sb)
        self._skill_items()
        old_max = getattr(self, "max_hp", None)
        s0, d0, e0, v0 = self.start_stats
        life = v0 + cs["hpadd"] + (self.vitality - v0) * cs["lpv"] / 4.0 + (self.level - 1) * cs["lpl"] / 4.0 + self.mod("life")
        self.max_hp = int(life * (100 + self.mod("life_pct")) / 100)
        mana = e0 + (self.energy - e0) * cs["mpm"] / 4.0 + (self.level - 1) * cs["mpl"] / 4.0 + self.mod("mana")
        self.max_mana = int(mana * (100 + self.mod("mana_pct")) / 100)
        weapon = self.equipment["weapon"] if self.equipment["weapon"] in self._active else None
        lo, hi = weapon.dmg if weapon and weapon.dmg else (1, 2)
        if getattr(self, "shape", None) and (weapon is None or not weapon.dmg):
            lo, hi = 2, 5
        lo += self.mod("mindmg")
        hi += self.mod("maxdmg")
        flo, fhi = self.mod_range("flat_dmg")
        lo, hi = lo + flo, hi + fhi
        hi = max(hi, lo)
        if weapon and weapon.mod_list is not None:
            bonus = (self.strength * weapon.strbonus + self.dexterity * weapon.dexbonus) / 10000.0
        else:
            bonus = self.strength / 100.0
        mult = 1 + bonus + (self.mod("ed") + pb["ed"]) / 100.0
        self.dmg = (max(1, int(lo * mult)), max(1, int(hi * mult)))
        self.elem = {k: self.mod_range(k + "_dmg") for k in ("fire", "cold", "ltng", "pois", "mag")}
        self.elem = {k: v for k, v in self.elem.items() if v[1] > 0}
        wtypes = set(weapon.base.get("ancestors", ())) if weapon is not None and isinstance(getattr(weapon, "base", None), dict) else set()
        self.ranged = bool(wtypes & {"miss", "bow", "xbow", "jave", "thro", "taxe", "tkni"}) and not (wtypes & {"spea"} and "jave" not in wtypes)
        # attack AP = the weapon's D2 speed: very fast 1, fast 2, normal 3, slow 4, very slow 5.
        # Increased attack speed shifts it like D2 (about 10 speed per 20% IAS); bare hands are normal
        from .items import speed_tier
        wsm = 0
        if weapon is not None:
            b = weapon.base if isinstance(getattr(weapon, "base", None), dict) else {}
            wsm = b.get("speed", {1: -20, 2: -10, 3: 0, 4: 10, 5: 20}.get(weapon.ap or 3, 0))
        self.attack_speed = wsm - self.mod("ias") // 2
        self.attack_cost = max(1, speed_tier(self.attack_speed)[0] + ATTACK_AP_OFFSET)
        self.range = 10 if wtypes & {"miss", "bow", "xbow"} else (6 if self.ranged else 1)
        ar = self.dexterity * 5 - 35 + cs["thf"] + self.mod("ar") + (self.level - 1) * 5
        self.ar = int(ar * (100 + self.mod("ar_pct") + pb["ar_pct"]) / 100)
        eff = getattr(self, "effects", {})
        def_pct = pb["def_pct"] + self.mod("def_pct") + (eff.get("shout_pct", 0) if eff.get("shout") else 0) \
            + (eff.get("conc_pct", 0) if eff.get("concentrate") else 0)
        self.defense = self.dexterity // 4 + sum(it.defense for it in self._active) + self.mod("def")
        self.defense = int(self.defense * (100 + def_pct) / 100)
        if eff.get("berserk"):
            self.defense = 0
        if eff.get("bo"):
            self.max_hp = int(self.max_hp * (100 + eff.get("bo_pct", 0)) / 100)
            self.max_mana = int(self.max_mana * (100 + eff.get("bo_pct", 0)) / 100)
        frw = self.mod("frw")
        # more AP as you grow: character level, dexterity above your class's start, faster run/walk
        dex_bonus = max(0, self.dexterity - d0) // 40
        lvl_bonus = sum(1 for t in AP_LEVELS if self.level >= t)
        self.max_ap = 8 + lvl_bonus + dex_bonus + self.mod("ap") + max(0, frw) // 20 + pb["ap"]
        self.thorns = self.mod("thorns")
        self.light = 9 + self.mod("light")
        self.regen = self.mod("regen")
        self.leech = self.mod("ll")
        self.mana_leech = self.mod("ml")
        self.dr = self.mod("dr")
        self.mdr = self.mod("mdr")
        self.mf = self.mod("mf")
        self.gf = self.mod("gf")
        self.crit = pb.get("crit", 0)
        allres = self.mod("res_all")
        cap = {k: min(95, 75 + self.mod("maxres_" + k) + self.mod("maxres_all")) for k in ("fire", "cold", "ltng", "pois")}
        self.res = {k: min(cap[k], allres + pb["res"] + self.mod("res_" + k)) for k in ("fire", "cold", "ltng", "pois")}
        self.res_cap = cap
        self.dr_pct = min(50, self.mod("dr_pct"))
        self.life_kill = self.mod("life_kill")
        self.mana_kill = self.mod("mana_kill")
        self.xp_pct = self.mod("xp_pct")
        shield = self.equipment.get("shield")
        if shield and shield in self._active and shield.slot == "shield":
            # D2: (class block factor + shield block) * (dex - 15) / (clvl * 2), max 75%
            blk = (cs["block"] + shield.block + self.mod("block")) * max(0, self.dexterity - 15) / (self.level * 2.0)
            self.block_chance = max(0, min(75, int(blk)))
        elif self.mod("weapon_block") and wtypes & {"h2h", "h2h2"}:
            self.block_chance = min(75, self.mod("weapon_block"))
        else:
            self.block_chance = 0
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
        while self.level < 99 and self.xp >= self.xp_to_next():
            self.level += 1
            self.stat_points += 5
            if hasattr(self, "skills"):
                self.skills.points += 1      # D2: one skill point per level
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
    def __init__(self, kind, x, y, level=1, rng=random, template=None):
        t = template or MONSTERS[kind]
        super().__init__(t["name"], x, y)
        self.kind = kind
        self.d2id = t.get("id")
        self.missile = t.get("missile", "")
        if template:
            level = t["level"]     # D2 stats already include the monster's level
        self.level = level
        self.token = t["token"]
        if template:
            self.max_hp = self.hp = rng.randint(*t["hp"])
            self.dmg = t["dmg"]
            self.ar = t["ar"]
            self.defense = t["df"]
        else:
            self.max_hp = self.hp = rng.randint(*t["hp"]) + (level - 1) * 2
            lo, hi = t["dmg"]
            self.dmg = (lo + (level - 1) // 2, hi + (level - 1) // 2)
            self.ar = t["ar"] + (level - 1) * 8
            self.defense = t["df"] + (level - 1) * 2
        self.max_ap = self.ap = t["ap"]
        self.radius = 1 if t.get("size", 2) >= 3 else 0
        self.attack_cost = t["cost"]
        self.range = t["rng"]
        self.xp_value = t["xp"] if template else t["xp"] + (level - 1) * t["xp"] // 3
        self.color = t["color"]
        self.ai = t["ai"]
        self.unique = t.get("unique", False)
        self.aware = False
        self.panic = 0       # fallen run away for a turn when a pack mate dies
        self.effects = {}    # stun / flee / battle cry / taunt: turns left
        self.home = (x, y)
        self.res = dict(t.get("res", {}))
        self.undead = t.get("undead", False)
        self.demon = t.get("demon", False)
        self.curses = {}
        self.ally = False
        self.life_turns = None
