"""Diablo 2 game content (items, affixes, monsters, levels) read from the game's own tables.

Used by the rules whenever a D2 install is configured. Everything is plain data, so it
works without graphics too.
"""
import random

from d2.source import read_table
from d2.strings import Strings, tidy_internal_name
from .items import Item, D2_COLORS

# body location -> our equipment slot
BODYLOC_SLOT = {"head": "helm", "tors": "armor", "glov": "gloves", "feet": "boots", "belt": "belt",
                "neck": "amulet", "rrin": "ring", "lrin": "ring", "rarm": "weapon", "larm": "weapon"}

# D2 property code -> (our stat key, how to read the mod: "val" = rolled value, "minmax" = min/max as range)
PROP_MAP = {
    "dmg%": ("ed", "val"), "att": ("ar", "val"), "att%": ("ar_pct", "val"), "ac": ("def", "val"),
    "ac%": ("edef", "val"), "hp": ("life", "val"), "mana": ("mana", "val"), "str": ("str", "val"),
    "dex": ("dex", "val"), "vit": ("vit", "val"), "enr": ("eng", "val"), "light": ("light", "val"),
    "thorns": ("thorns", "val"), "dmg-min": ("mindmg", "val"), "dmg-max": ("maxdmg", "val"),
    "move1": ("frw", "val"), "move2": ("frw", "val"), "move3": ("frw", "val"),
    "swing1": ("ias", "val"), "swing2": ("ias", "val"), "swing3": ("ias", "val"),
    "regen": ("regen", "val"), "lifesteal": ("ll", "val"), "manasteal": ("ml", "val"),
    "res-fire": ("res_fire", "val"), "res-cold": ("res_cold", "val"), "res-ltng": ("res_ltng", "val"),
    "res-pois": ("res_pois", "val"), "res-all": ("res_all", "val"),
    "red-dam": ("dr", "val"), "red-mag": ("mdr", "val"), "mag%": ("mf", "val"), "gold%": ("gf", "val"),
    "block": ("block", "val"), "block2": ("fbr", "val"), "balance1": ("fhr", "val"), "balance2": ("fhr", "val"),
    "balance3": ("fhr", "val"), "cast1": ("fcr", "val"), "cast2": ("fcr", "val"), "cast3": ("fcr", "val"),
    "dmg-fire": ("fire_dmg", "minmax"), "dmg-cold": ("cold_dmg", "minmax"), "dmg-ltng": ("ltng_dmg", "minmax"),
    "dmg-pois": ("pois_dmg", "minmax"), "dmg-norm": ("flat_dmg", "minmax"), "dmg": ("flat_dmg", "minmax"),
    "knock": ("knock", "val"), "nofreeze": ("cbf", "val"), "howl": ("howl", "val"),
    "dmg-to-mana": ("dmg_to_mana", "val"), "manarecovery": ("mana_regen_pct", "val"),
    "hp%": ("life_pct", "val"), "mana%": ("mana_pct", "val"), "stamina": ("stamina", "val"),
    "dur": ("dur", "val"), "ease": ("req_pct", "val"), "openwounds": ("ow", "val"), "crush": ("cb", "val"),
    "deadly": ("ds", "val"), "slow": ("slow", "val"), "stupidity": ("blind", "val"),
    "freeze": ("freeze", "val"), "nec": ("skill_class", "val"), "allskills": ("all_skills", "val"),
}

# rolled together into one "Adds X-Y <element> Damage" line
ELEM_PARTS = {"fire-min": ("fire", 0), "fire-max": ("fire", 1), "cold-min": ("cold", 0), "cold-max": ("cold", 1),
              "ltng-min": ("ltng", 0), "ltng-max": ("ltng", 1), "pois-min": ("pois", 0), "pois-max": ("pois", 1),
              "mag-min": ("mag", 0), "mag-max": ("mag", 1)}
IGNORED = {"fire-len", "cold-len", "pois-len"}
# not supported yet (skills, charges, sockets): affixes with these don't spawn
SKIP_CODES = {"charged", "skilltab", "gethit-skill", "hit-skill", "att-skill", "sock", "stack", "",
              "ama", "pal", "nec", "sor", "bar", "dru", "ass", "kill-skill", "death-skill", "levelup-skill"}
PROP_MAP.update({"res-pois-len": ("pois_len", "val"), "red-dmg": ("dr", "val"), "stam": ("stamina", "val"), "regen-stam": ("stamina_regen", "val"),
                 "att-demon": ("ar_demon", "val"), "att-undead": ("ar_undead", "val"), "mana-kill": ("mana_kill", "val"),
                 "ignore-ac": ("ignore_ac", "val"), "dmg-ac": ("dmg_ac", "val"), "ac/lvl": ("def_lvl", "val"),
                 "dmg/lvl": ("maxdmg_lvl", "val"), "mana/lvl": ("mana_lvl", "val")})

POTIONS = {"yps": ("antidote", 50), "wms": ("thawing", 50), "vps": ("stamina", 2), "hp1": ("heal", 30), "hp2": ("heal", 60), "hp3": ("heal", 100), "hp4": ("heal", 180),
           "hp5": ("heal", 320), "mp1": ("mana", 20), "mp2": ("mana", 40), "mp3": ("mana", 80),
           "mp4": ("mana", 150), "mp5": ("mana", 250), "rvs": ("rejuv", 35), "rvl": ("rejuv", 100)}


def _int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


class D2Content:
    def __init__(self, src, difficulty="normal"):
        self.src = src
        sfx = {"normal": "", "nightmare": "(n)", "hell": "(h)"}.get(difficulty, "")
        self.sfx = sfx
        self.strings = Strings(src)
        self.types = {r["code"]: r for r in read_table(src, "ItemTypes") if r.get("code")}
        self._ancestors = {}
        self.bases = []
        self.base_by_code = {}
        for table, kind in (("Weapons", "weapon"), ("Armor", "armor"), ("Misc", "misc")):
            for r in read_table(src, table):
                code = r.get("code", "")
                if not code or not r.get("name") or r.get("name", "").lower() in ("expansion", "not used"):
                    continue
                b = self._make_base(r, kind)
                if b:
                    self.bases.append(b)
                    self.base_by_code[code] = b
        self.prefixes = self._affixes("MagicPrefix")
        self.suffixes = self._affixes("MagicSuffix")
        self.monstats = {r["id"].lower(): r for r in read_table(src, "MonStats") if r.get("id")}
        self.monlvl = {_int(r.get("level")): r for r in read_table(src, "MonLvl") if r.get("level")}
        self.levels = [r for r in read_table(src, "Levels")]
        try:
            self.superuniques = {r.get("superunique", "").lower(): r for r in read_table(src, "SuperUniques")}
        except Exception:
            self.superuniques = {}
        from .d2items import SocketRules
        self.sockets = SocketRules(self, read_table)

    # ------------------------------------------------------------ item types
    def ancestors(self, code):
        """All type codes an item type counts as (e.g. 'axe' -> axe, mele, weap)."""
        if code in self._ancestors:
            return self._ancestors[code]
        out, stack = set(), [code]
        while stack:
            c = stack.pop()
            if not c or c in out:
                continue
            out.add(c)
            t = self.types.get(c)
            if t:
                stack += [t.get("equiv1", ""), t.get("equiv2", "")]
        self._ancestors[code] = out
        return out

    def _bodyloc(self, type_code):
        for c in [type_code] + sorted(self.ancestors(type_code)):
            t = self.types.get(c)
            if t and t.get("bodyloc1"):
                return t["bodyloc1"]
        return ""

    def _make_base(self, r, kind):
        if r.get("spawnable", "1") == "0" and kind != "misc":
            return None
        if r.get("quest", "") not in ("", "0"):
            return None
        tcode = r.get("type", "")
        anc = self.ancestors(tcode)
        cls = ""
        for c in anc:
            t = self.types.get(c)
            if t and t.get("class"):
                cls = t["class"]
        key = r.get("namestr") or r["code"]
        display = self.strings.get(key, None) if key in self.strings.table else tidy_internal_name(r["name"])
        b = {
            "name": display, "code": r["code"], "type": tcode, "kind": kind, "ancestors": anc,
            "qlvl": _int(r.get("level")), "levelreq": _int(r.get("levelreq")),
            "reqstr": _int(r.get("reqstr")), "reqdex": _int(r.get("reqdex")),
            "invfile": r.get("invfile", ""), "flippyfile": r.get("flippyfile", ""),
            "invw": _int(r.get("invwidth"), 1), "invh": _int(r.get("invheight"), 1),
            "rarity": max(1, _int(r.get("rarity"), 1)), "class": cls,
            "magic_only": bool(self.types.get(tcode, {}).get("magic") == "1"),
            "normal_only": bool(self.types.get(tcode, {}).get("normal") == "1"),
        }
        b["cost"] = _int(r.get("cost"))
        b["gamble"] = _int(r.get("gamble cost"))
        b["shop"] = {}
        for npc in ("charsi", "gheed", "akara"):
            vals = tuple(_int(r.get(npc + k)) for k in ("min", "max", "magicmin", "magicmax", "magiclvl"))
            if vals[1] or vals[3]:
                b["shop"][npc] = vals
        b["maxsock"] = _int(r.get("gemsockets"))
        t = self.types.get(tcode, {})
        b["sockcaps"] = (_int(t.get("maxsock1")), _int(t.get("maxsock25")), _int(t.get("maxsock40")))
        page = ""
        for c in [tcode] + sorted(anc):
            if self.types.get(c, {}).get("storepage"):
                page = self.types[c]["storepage"]
                break
        b["page"] = page or {"weapon": "weap", "armor": "armo"}.get(kind, "misc")
        loc = self._bodyloc(tcode)
        slot = BODYLOC_SLOT.get(loc, "")
        if "shld" in anc or "shie" in anc:
            slot = "shield"
        b["slot"] = slot
        if kind == "weapon":
            two = r.get("2handed") == "1"
            lo, hi = (_int(r.get("2handmindam")), _int(r.get("2handmaxdam"))) if two and not r.get("mindam") \
                else (_int(r.get("mindam")), _int(r.get("maxdam")))
            if not hi and r.get("minmisdam"):
                lo, hi = _int(r.get("minmisdam")), _int(r.get("maxmisdam"))
            speed = _int(r.get("speed"))
            ap = 3 + (1 if two else 0) + (1 if speed >= 10 else 0) - (1 if speed <= -10 else 0)
            b.update(dmg=(max(1, lo), max(1, hi)), two_handed=two, ap=max(2, min(5, ap)),
                     wclass=(r.get("2handedwclass") if two and r.get("1or2handed") != "1" else r.get("wclass")) or "1hs",
                     gfx=(r.get("alternategfx") or r["code"]).upper(),
                     strbonus=_int(r.get("strbonus")), dexbonus=_int(r.get("dexbonus")),
                     ranged=bool({"miss", "bow", "xbow"} & anc))
        elif kind == "armor":
            b.update(defense=(_int(r.get("minac")), _int(r.get("maxac"))), block=_int(r.get("block")),
                     gfx=(r.get("alternategfx") or r["code"]).upper(),
                     look={k: _int(r.get(k)) for k in ("torso", "legs", "rarm", "larm", "rspad", "lspad")})
        else:
            code = r["code"]
            from .d2items import gem_kind
            if code in POTIONS:
                b["potion"] = POTIONS[code]
            elif code in ("tsc", "isc", "tbk", "ibk"):
                b["use"] = "tp" if code in ("tsc", "tbk") else "id"
                b["tome"] = code in ("tbk", "ibk")
            elif gem_kind(b):
                b["gem"] = gem_kind(b)
            elif slot in ("ring", "amulet"):
                pass              # rings and amulets are equipment
            elif code != "gld":
                return None       # quest items, keys, charms: not used
        return b

    def _affixes(self, table):
        out = []
        for r in read_table(self.src, table):
            if r.get("spawnable") != "1" or not r.get("name"):
                continue
            mods = []
            for i in (1, 2, 3):
                code = r.get("mod%dcode" % i, "")
                if code:
                    mods.append((code, r.get("mod%dparam" % i, ""), _int(r.get("mod%dmin" % i)), _int(r.get("mod%dmax" % i))))
            if not mods or any(m[0] in SKIP_CODES for m in mods):
                continue
            out.append({
                "name": self.strings.get(r["name"], r["name"]), "level": _int(r.get("level")), "maxlevel": _int(r.get("maxlevel")),
                "levelreq": _int(r.get("levelreq")), "freq": max(0, _int(r.get("frequency"), 1)),
                "group": r.get("group", ""), "mods": mods,
                "itypes": {r.get("itype%d" % i) for i in range(1, 8) if r.get("itype%d" % i)},
                "etypes": {r.get("etype%d" % i) for i in range(1, 6) if r.get("etype%d" % i)},
                "classspecific": r.get("classspecific", ""),
                "multiply": _int(r.get("multiply")), "add": _int(r.get("add")),
            })
        return out

    # ------------------------------------------------------------ item generation
    player_cls = "bar"

    def pick_base(self, ilvl, rng, kinds=("weapon", "armor", "misc")):
        cands = [b for b in self.bases if b["kind"] in kinds and b["slot"] and b["qlvl"] <= ilvl
                 and "gem" not in b and "use" not in b and "potion" not in b]
        if not cands:
            return None
        total = sum(b["rarity"] for b in cands)
        r = rng.uniform(0, total)
        for b in cands:
            r -= b["rarity"]
            if r <= 0:
                return b
        return cands[-1]

    def _roll_affix(self, table, base, ilvl, rng, used_groups):
        cands = [a for a in table
                 if a["level"] <= ilvl and (not a["maxlevel"] or ilvl <= a["maxlevel"])
                 and a["itypes"] & base["ancestors"] and not (a["etypes"] & base["ancestors"])
                 and a["group"] not in used_groups and a["freq"] > 0
                 and (not a["classspecific"] or a["classspecific"] == self.player_cls)]
        if not cands:
            return None
        total = sum(a["freq"] for a in cands)
        r = rng.uniform(0, total)
        for a in cands:
            r -= a["freq"]
            if r <= 0:
                return a
        return cands[-1]

    def make_item(self, base, ilvl, rng, quality="normal", sockets=None, identified=None):
        if "potion" in base:
            kind, amount = base["potion"]
            it = Item(base["name"], base["code"], None, amount=amount, kind="potion")
            it.potion = kind
            it.base = base
            it.invfile, it.flippy = base["invfile"], base["flippyfile"]
            return it
        if "use" in base or "gem" in base:
            it = Item(base["name"], base["code"], None, kind="misc")
            it.base = base
            it.invfile, it.flippy = base["invfile"], base["flippyfile"]
            it.invw, it.invh = base["invw"], base["invh"]
            it.levelreq = base["levelreq"]
            it.mod_list = []
            if "use" in base:
                it.use = base["use"]
                it.quantity = 20 if base.get("tome") else 0
            else:
                it.gem = base["gem"]
                rules = self.sockets
                it.filler_lines = rules.describe_filler(it)
                it.rune_letter = rules.letter(it)
            return it
        mods_raw = []       # (code, value or (min,max))
        affixes = []
        if base["magic_only"]:
            quality = "magic"
        if base["normal_only"]:
            quality = "normal"
        name = base["name"]
        levelreq = base["levelreq"]
        if quality == "magic":
            used = set()
            want_pre = rng.random() < 0.5
            want_suf = rng.random() < 0.5 or not want_pre
            pre = self._roll_affix(self.prefixes, base, ilvl, rng, used) if want_pre else None
            if pre:
                used.add(pre["group"])
            suf = self._roll_affix(self.suffixes, base, ilvl, rng, used) if want_suf else None
            if not pre and not suf:
                suf = self._roll_affix(self.suffixes, base, ilvl, rng, used) or \
                    self._roll_affix(self.prefixes, base, ilvl, rng, used)
            for a in (pre, suf):
                if a:
                    affixes.append(a)
                    levelreq = max(levelreq, a["levelreq"])
                    elem = {}
                    length = 0
                    for code, param, lo, hi in a["mods"]:
                        info = PROP_MAP.get(code)
                        if code in ELEM_PARTS:
                            e, i = ELEM_PARTS[code]
                            elem.setdefault(e, [0, 0])[i] = rng.randint(min(lo, hi), max(lo, hi))
                        elif code in ("pois-len", "cold-len", "fire-len"):
                            length = max(lo, hi)
                        elif code in IGNORED:
                            continue
                        elif info and info[1] == "minmax":
                            mods_raw.append((code, (lo, hi)))
                        else:
                            mods_raw.append((code, rng.randint(min(lo, hi), max(lo, hi))))
                    for e, (lo, hi) in elem.items():
                        if e == "pois" and length:
                            # D2 poison is per-frame damage over 'length' frames (256ths)
                            lo, hi = max(1, lo * length // 256), max(1, hi * length // 256)
                        mods_raw.append(("dmg-" + e if e != "mag" else "dmg-norm", (lo, max(lo, hi))))
            if pre:
                name = pre["name"] + " " + name
            if suf:
                name = name + " " + suf["name"]
            if not affixes:
                quality = "normal"
        stats = {}
        for code, v in mods_raw:
            info = PROP_MAP.get(code)
            key = info[0] if info else code
            if isinstance(v, tuple):
                old = stats.get(key, (0, 0))
                stats[key] = (old[0] + v[0], old[1] + v[1])
            else:
                stats[key] = stats.get(key, 0) + v
        defense = 0
        raw_def = None
        if base["kind"] == "armor":
            lo, hi = base["defense"]
            defense = raw_def = rng.randint(min(lo, hi), max(lo, hi))
            if "edef" in stats:
                defense = defense * (100 + stats["edef"]) // 100
            defense += stats.get("def", 0)
        it = Item(name, base["code"], base["slot"], quality, stats,
                  dmg=base.get("dmg"), ap=base.get("ap"), defense=defense)
        it.base = base
        it.mod_list = mods_raw
        it.levelreq = levelreq
        it.reqstr, it.reqdex = base["reqstr"], base["reqdex"]
        it.invfile, it.flippy = base["invfile"], base["flippyfile"]
        it.invw, it.invh = base["invw"], base["invh"]
        it.two_handed = base.get("two_handed", False)
        it.block = base.get("block", 0)
        it.gfx = base.get("gfx", "")
        it.wclass = base.get("wclass", "")
        it.look = base.get("look")
        it.strbonus, it.dexbonus = base.get("strbonus", 0), base.get("dexbonus", 0)
        it.affixes = affixes
        it.base_defense = raw_def
        if quality == "magic" and identified is not True:
            it.identified = bool(identified)
        # D2: a normal item can come with sockets (up to what the base and item level allow)
        if sockets is None and quality == "normal" and base.get("maxsock") and rng.random() < 0.15:
            sockets = rng.randint(1, self.max_sockets(base, ilvl))
        if sockets:
            it.sockets = min(sockets, self.max_sockets(base, ilvl)) or sockets
        return it

    def max_sockets(self, base, ilvl):
        caps = base.get("sockcaps", (0, 0, 0))
        cap = caps[2] if ilvl >= 40 else caps[1] if ilvl >= 25 else caps[0]
        return max(0, min(base.get("maxsock", 0), cap or base.get("maxsock", 0)))

    def make_gem_or_rune(self, mlvl, rng):
        """Gems (chipped/flawed early) or low runes, like Act 1 drops."""
        if rng.random() < 0.35:
            n = 1 + min(32, int(rng.expovariate(1.0 / (1.5 + mlvl / 6.0))))
            b = self.base_by_code.get("r%02d" % n)
        else:
            gems = [b for b in self.bases if b.get("gem") and b["gem"][0] == "gem"]
            grade = 0 if rng.random() < 0.7 else (1 if rng.random() < 0.8 or mlvl < 10 else 2)
            gems = [b for b in gems if b["gem"][2] == grade] or gems
            b = rng.choice(gems) if gems else None
        return self.make_item(b, mlvl, rng) if b else None

    def make_gold(self, mlvl, rng, gf=0):
        amt = int(rng.randint(mlvl * 2 + 1, mlvl * 9 + 10) * (100 + gf) / 100)
        it = Item("Gold", "gld", None, amount=amt, kind="gold")
        it.invfile, it.flippy = "invgld1", "flpgld"
        return it

    def make_potion(self, mlvl, rng):
        code = "hp1" if mlvl < 6 else "hp2"
        if rng.random() < 0.3:
            code = "mp1" if mlvl < 8 else "mp2"
        return self.make_item(self.base_by_code[code], mlvl, rng) if code in self.base_by_code else None

    def roll_drop(self, mlvl, is_boss=False, rng=random, mf=0, gf=0):
        """A simplified version of D2's treasure classes: nothing, gold, potions or an item."""
        out = []
        picks = 5 if is_boss else 1
        for _ in range(picks):
            r = rng.random()
            if not is_boss and r < 0.62:
                continue
            if r < 0.80 and not is_boss:
                out.append(self.make_gold(mlvl, rng, gf))
            elif r < 0.92 and not is_boss:
                p = self.make_potion(mlvl, rng)
                if p:
                    out.append(p)
            elif r < 0.935 and not is_boss:
                g = self.make_gem_or_rune(mlvl, rng)
                if g:
                    out.append(g)
            else:
                ilvl = mlvl + (2 if is_boss else 0)
                b = self.pick_base(max(1, ilvl), rng)
                if not b:
                    continue
                magic = 0.18 * (1 + mf / 100.0) + (0.6 if is_boss else 0)
                out.append(self.make_item(b, ilvl, rng, "magic" if rng.random() < magic else "normal"))
        if is_boss:
            out.append(self.make_gold(mlvl * 2, rng, gf))
        return out

    # ------------------------------------------------------------ monsters
    def level_row(self, name_part):
        for r in self.levels:
            if name_part.lower() in r.get("name", "").lower() or name_part.lower() in r.get("levelname", "").lower():
                return r
        return None

    def roster(self, level_row):
        ids = [level_row.get("mon%d" % i, "").lower() for i in range(1, 11)]
        return [i for i in ids if i and i in self.monstats]

    def monstats_key(self, mid):
        k = (mid or "").lower()
        return k if k in self.monstats else None

    def monster_template(self, mid, unique=False, level=None):
        """Everything needed to spawn a monster at its normal-difficulty level (or `level`)."""
        mid = mid.lower()
        r = self.monstats[mid]
        sfx = self.sfx
        lvl = max(1, _int(r.get("level" + sfx) or r.get("level"), 1)) if level is None else max(1, level)
        ml = self.monlvl.get(lvl) or self.monlvl.get(1)
        base_hp, base_ac = _int(ml.get("hp" + sfx) or ml.get("hp")), _int(ml.get("ac" + sfx) or ml.get("ac"))
        base_th, base_dm = _int(ml.get("th" + sfx) or ml.get("th")), _int(ml.get("dm" + sfx) or ml.get("dm"))
        base_xp = _int(ml.get("xp" + sfx) or ml.get("xp"))
        pct = lambda col: _int(r.get(col + sfx) or r.get(col))
        hp = (max(1, base_hp * pct("minhp") // 100), max(1, base_hp * pct("maxhp") // 100))
        dmg = (max(1, base_dm * pct("a1mind") // 100), max(1, base_dm * pct("a1maxd") // 100))
        ai_name = r.get("ai", "")
        miss = r.get("missa1", "") or r.get("missa2", "")
        if ai_name in ("FallenShaman",):
            ai = "shaman"
        elif ai_name == "Fallen":
            ai = "fallen"
        elif miss or ai_name in ("CorruptArcher", "SkeletonBow", "QuillRat", "Vampire", "Arach"):
            ai = "ranged"
        else:
            ai = "melee"
        vel = _int(r.get("velocity"), 3)
        t = {
            "id": mid, "name": self._name(r), "token": r.get("code", "ZM").upper(), "level": lvl,
            "hp": hp, "dmg": dmg, "ar": max(5, base_th * pct("a1th") // 100),
            "df": max(0, base_ac * pct("ac") // 100), "xp": max(1, base_xp * pct("exp") // 100),
            "ap": max(4, min(9, 3 + vel)), "cost": 3 if vel <= 2 else 2,
            "rng": 6 if ai in ("ranged", "shaman") else 1, "ai": ai,
            "missile": miss, "minion": r.get("minion1", "").lower(),
            "party": (_int(r.get("partymin")), _int(r.get("partymax"))),
            "group": (max(1, _int(r.get("mingrp"), 1)), max(1, _int(r.get("maxgrp"), 1))),
            "color": (150, 150, 150), "unique": unique, "rarity": max(1, _int(r.get("rarity"), 1)),
            "res": {"phys": pct("resdm"), "mag": pct("resma"), "fire": pct("resfi"), "ltng": pct("resli"),
                    "cold": pct("resco"), "pois": pct("respo")},
            "undead": r.get("lundead") == "1" or r.get("hundead") == "1", "demon": r.get("demon") == "1",
        }
        if unique:
            t["hp"] = (t["hp"][0] * 4, t["hp"][1] * 4)
            t["dmg"] = (t["dmg"][0] * 3 // 2 + 1, t["dmg"][1] * 3 // 2 + 1)
            t["ar"] = t["ar"] * 3 // 2
            t["xp"] *= 5
            t["level"] += 3
        return t

    def _name(self, r):
        # MonStats only holds a string key; turn "Zombie1"-style ids into readable names
        names = {"zombie": "Zombie", "fallen": "Fallen", "fallenshaman": "Fallen Shaman", "quillrat": "Quill Rat",
                 "brute": "Gargantuan Beast", "corruptrogue": "Dark Hunter", "cr_archer": "Dark Archer",
                 "cr_lancer": "Dark Spearwoman", "skeleton": "Skeleton", "wraith": "Ghost", "crownest": "Foul Crow Nest",
                 "foulcrow": "Foul Crow", "bighead": "Afflicted", "goatman": "Moon Clan", "vampire": "Banished",
                 "arach": "Arach", "fetish": "Fetish", "sk_archer": "Skeleton Archer", "skmage_pois": "Skeleton Mage"}
        key = r.get("namestr", "")
        if key and key in self.strings.table:
            return self.strings.get(key)
        mid = r.get("id", "")
        stem = mid.rstrip("0123456789").lower()
        return names.get(stem, key or mid)
