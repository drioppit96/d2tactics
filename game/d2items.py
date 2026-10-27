"""Gems, runes, sockets, runewords, identification and prices (D2's item extras).

Gem and rune bonuses come from Gems.txt when the install has it, with D2 1.14's values
built in as a fallback. Runewords come from Runes.txt (non-ladder ones).
"""
GRADES = ["Chipped", "Flawed", "", "Flawless", "Perfect"]
GEM_TYPES = {"gema": "amethyst", "gemt": "topaz", "gems": "sapphire", "geme": "emerald", "gemr": "ruby",
             "gemd": "diamond", "gemz": "skull"}

# (weapon mods, armor/helm mods, shield mods) per grade: [(prop code, min, max)]
_G = lambda w, a, s: [(w[i], a[i], s[i]) for i in range(5)]
BUILTIN_GEMS = {
    "amethyst": _G([[("att", v, v)] for v in (40, 60, 80, 100, 150)], [[("str", v, v)] for v in (3, 4, 6, 8, 10)],
                   [[("ac", v, v)] for v in (8, 12, 18, 24, 30)]),
    "topaz": _G([[("dmg-ltng", 1, v)] for v in (8, 14, 22, 30, 40)], [[("mag%", v, v)] for v in (9, 13, 16, 20, 24)],
                [[("res-ltng", v, v)] for v in (12, 16, 22, 28, 40)]),
    "sapphire": _G([[("dmg-cold", a, b)] for a, b in ((1, 3), (3, 5), (4, 7), (6, 10), (10, 14))],
                   [[("mana", v, v)] for v in (10, 17, 24, 31, 38)], [[("res-cold", v, v)] for v in (12, 16, 22, 28, 40)]),
    "emerald": _G([[("dmg-pois", v, v)] for v in (10, 20, 40, 60, 100)], [[("dex", v, v)] for v in (3, 4, 6, 8, 10)],
                  [[("res-pois", v, v)] for v in (12, 16, 22, 28, 40)]),
    "ruby": _G([[("dmg-fire", a, b)] for a, b in ((3, 4), (5, 8), (8, 12), (10, 16), (15, 20))],
               [[("hp", v, v)] for v in (10, 17, 24, 31, 38)], [[("res-fire", v, v)] for v in (12, 16, 22, 28, 40)]),
    "diamond": _G([[("dmg-undead", v, v)] for v in (28, 34, 44, 54, 64)], [[("att", v, v)] for v in (20, 40, 60, 80, 100)],
                  [[("res-all", v, v)] for v in (6, 8, 11, 14, 19)]),
    "skull": _G([[("lifesteal", a, a), ("manasteal", b, b)] for a, b in ((2, 1), (2, 2), (3, 2), (3, 3), (4, 3))],
                [[("regen", a, a), ("manarecovery", b, b)] for a, b in ((2, 8), (3, 8), (3, 12), (4, 12), (5, 19))],
                [[("thorns", v, v)] for v in (4, 8, 12, 16, 20)]),
}
_W, _A, _S = 0, 1, 2
BUILTIN_RUNES = {   # rune number: (weapon, armor/helm, shield)
    1: ([("att", 50, 50), ("light", 1, 1)], [("ac", 15, 15), ("light", 1, 1)], [("ac", 15, 15), ("light", 1, 1)]),
    2: ([("dmg-undead", 75, 75), ("att-undead", 50, 50)], [("regen-stam", 15, 15)], [("block", 7, 7)]),
    3: ([("mana-kill", 2, 2)], [("mana-kill", 2, 2)], [("mana-kill", 2, 2)]),
    4: ([("knock", 1, 1)], [("ac-miss", 30, 30)], [("ac-miss", 30, 30)]),
    5: ([("reduce-ac", 25, 25)], [("manarecovery", 15, 15)], [("manarecovery", 15, 15)]),
    6: ([("dmg-max", 9, 9)], [("dmg-to-mana", 15, 15)], [("dmg-to-mana", 15, 15)]),
    7: ([("dmg-pois", 75, 75)], [("res-pois", 30, 30)], [("res-pois", 35, 35)]),
    8: ([("dmg-fire", 5, 30)], [("res-fire", 30, 30)], [("res-fire", 35, 35)]),
    9: ([("dmg-ltng", 1, 50)], [("res-ltng", 30, 30)], [("res-ltng", 35, 35)]),
    10: ([("dmg-cold", 3, 14)], [("res-cold", 30, 30)], [("res-cold", 35, 35)]),
    11: ([("lifesteal", 7, 7)], [("thorns", 14, 14)], [("thorns", 14, 14)]),
    12: ([("dmg-min", 9, 9)], [("red-dmg", 7, 7)], [("red-dmg", 7, 7)]),
    13: ([("swing2", 20, 20)], [("balance2", 20, 20)], [("block2", 20, 20)]),
    14: ([("howl", 25, 25)], [("regen", 7, 7)], [("regen", 7, 7)]),
    15: ([("ease", -20, -20)], [("ease", -15, -15)], [("ease", -15, -15)]),
    16: ([("vit", 10, 10)],) * 3, 17: ([("enr", 10, 10)],) * 3, 18: ([("dex", 10, 10)],) * 3,
    19: ([("str", 10, 10)],) * 3,
    20: ([("gold%", 75, 75)], [("gold%", 50, 50)], [("gold%", 50, 50)]),
    21: ([("dmg-demon", 75, 75), ("att-demon", 100, 100)], [("ac%", 30, 30)], [("ac%", 30, 30)]),
    22: ([("openwounds", 25, 25)], [("res-all", 15, 15)], [("res-all", 22, 22)]),
    23: ([("noheal", 1, 1)], [("red-mag", 7, 7)], [("red-mag", 7, 7)]),
    24: ([("mag%", 30, 30)], [("mag%", 25, 25)], [("mag%", 25, 25)]),
    25: ([("att%", 20, 20)], [("res-pois-max", 5, 5)], [("res-pois-max", 5, 5)]),
    26: ([("manasteal", 7, 7)], [("res-fire-max", 5, 5)], [("res-fire-max", 5, 5)]),
    27: ([("dmg%", 50, 50)], [("res-cold-max", 5, 5)], [("res-cold-max", 5, 5)]),
    28: ([("deadly", 20, 20)], [("res-ltng-max", 5, 5)], [("res-ltng-max", 5, 5)]),
    29: ([("stupidity", 1, 1)], [("mana%", 5, 5)], [("mana", 50, 50)]),
    30: ([("crush", 20, 20)], [("red-dmg%", 8, 8)], [("red-dmg%", 8, 8)]),
    31: ([("ignore-ac", 1, 1)], [("hp%", 5, 5)], [("hp", 50, 50)]),
    32: ([("freeze", 3, 3)], [("nofreeze", 1, 1)], [("nofreeze", 1, 1)]),
    33: ([("indestruct", 1, 1)],) * 3,
}
RUNE_NAMES = ["El", "Eld", "Tir", "Nef", "Eth", "Ith", "Tal", "Ral", "Ort", "Thul", "Amn", "Sol", "Shael", "Dol",
              "Hel", "Io", "Lum", "Ko", "Fal", "Lem", "Pul", "Um", "Mal", "Ist", "Gul", "Vex", "Ohm", "Lo", "Sur",
              "Ber", "Jah", "Cham", "Zod"]
EXTRA_TEXT = {
    "dmg-undead": "+{0}% Damage to Undead", "att-undead": "+{0} to Attack Rating against Undead",
    "dmg-demon": "+{0}% Damage to Demons", "att-demon": "+{0} to Attack Rating against Demons",
    "ac-miss": "+{0} Defense vs. Missile", "reduce-ac": "-{0}% Target Defense", "red-dmg%": "Damage Reduced by {0}%",
    "noheal": "Prevent Monster Heal", "indestruct": "Indestructible", "hp%": "Increase Maximum Life {0}%",
    "res-fire-max": "+{0}% to Maximum Fire Resist", "res-cold-max": "+{0}% to Maximum Cold Resist",
    "res-ltng-max": "+{0}% to Maximum Lightning Resist", "res-pois-max": "+{0}% to Maximum Poison Resist",
    "mana-kill": "+{0} to Mana after each Kill", "allskills": "+{0} to All Skills", "fireskill": "+{0} to Fire Skills",
    "regen-mana": "Regenerate Mana {0}%", "pierce-fire": "-{0}% to Enemy Fire Resistance",
    "pierce-cold": "-{0}% to Enemy Cold Resistance", "pierce-ltng": "-{0}% to Enemy Lightning Resistance",
    "dmg-mag": "Adds {0}-{1} Magic Damage", "heal-kill": "+{0} Life after each Kill", "all-stats": "+{0} to all Attributes",
    "abs-mag": "Magic Absorb +{0}", "extra-pois": "+{0}% to Poison Skill Damage", "stam": "+{0} Maximum Stamina",
    "ethereal": "Ethereal (Cannot be Repaired)", "rep-dur": "Repairs 1 Durability in {0} Seconds",
}


def gem_kind(base):
    """('gem', name, grade) / ('rune', number) / None for a base dict."""
    t = base.get("type", "")
    if t in GEM_TYPES:
        name = base.get("name", "")
        grade = 2
        for i, g in enumerate(GRADES):
            if g and name.lower().startswith(g.lower()):
                grade = i
        return ("gem", GEM_TYPES[t], grade)
    if t == "rune":
        code = base.get("code", "r01")
        try:
            return ("rune", int(code[1:]))
        except ValueError:
            return None
    return None


class SocketRules:
    def __init__(self, content, read_table):
        self.content = content
        self.gems_txt = {}
        try:
            for r in read_table(content.src, "Gems"):
                code = r.get("code")
                if not code:
                    continue
                mods = []
                for part in ("weaponmod", "helmmod", "shieldmod"):
                    lst = []
                    for i in (1, 2, 3):
                        c = r.get("%s%dcode" % (part, i))
                        if c:
                            lst.append((c, _int(r.get("%s%dmin" % (part, i))), _int(r.get("%s%dmax" % (part, i)))))
                    mods.append(lst)
                self.gems_txt[code] = (mods, r.get("letter", ""))
        except Exception:
            self.gems_txt = {}
        self.runewords = []
        try:
            for r in read_table(content.src, "Runes"):
                if r.get("complete") != "1" or r.get("server") == "1":
                    continue
                runes = [r.get("rune%d" % i) for i in range(1, 7) if r.get("rune%d" % i)]
                if not runes:
                    continue
                props = []
                for i in range(1, 8):
                    c = r.get("t1code%d" % i)
                    if c:
                        props.append((c, r.get("t1param%d" % i, ""), _int(r.get("t1min%d" % i)), _int(r.get("t1max%d" % i))))
                name = r.get("rune name") or r.get("name")
                if self.content.strings is not None and r.get("name") in self.content.strings.table:
                    name = self.content.strings.get(r["name"], name)
                self.runewords.append(dict(name=name, runes=runes, props=props,
                                           itypes={r.get("itype%d" % i) for i in range(1, 7) if r.get("itype%d" % i)},
                                           etypes={r.get("etype%d" % i) for i in range(1, 4) if r.get("etype%d" % i)}))
        except Exception:
            self.runewords = []

    def mods_for(self, filler, host):
        """Property codes a gem / rune gives inside the host item."""
        part = self._part(host)
        if filler.code in self.gems_txt:
            return list(self.gems_txt[filler.code][0][part])
        g = getattr(filler, "gem", None)
        if g and g[0] == "gem":
            return list(BUILTIN_GEMS.get(g[1], [((), (), ())] * 5)[g[2]][part])
        if g and g[0] == "rune":
            t = BUILTIN_RUNES.get(g[1])
            if t:
                return list(t[min(part, len(t) - 1)])
        return []

    def _part(self, host):
        anc = host.base.get("ancestors", ()) if isinstance(host.base, dict) else ()
        if host.slot == "weapon":
            return 0
        if host.slot == "shield" or "shie" in anc or "shld" in anc:
            return 2
        return 1

    def letter(self, filler):
        g = getattr(filler, "gem", None)
        if g and g[0] == "rune":
            return RUNE_NAMES[g[1] - 1] if 1 <= g[1] <= 33 else "?"
        return ""

    def describe_filler(self, filler):
        """Tooltip lines for a gem / rune: what it does in each kind of item."""
        from .items import MOD_TEXT
        out = []
        dummy_w = type("H", (), {"slot": "weapon", "base": {}})()
        dummy_a = type("H", (), {"slot": "helm", "base": {}})()
        dummy_s = type("H", (), {"slot": "shield", "base": {}})()
        for label, host in (("Weapons", dummy_w), ("Armor", dummy_a), ("Shields", dummy_s)):
            parts = []
            for code, lo, hi in self.mods_for(filler, host):
                parts.append(prop_text(code, lo, hi))
            out.append("%s: %s" % (label, ", ".join(parts) if parts else "-"))
        return out

    def find_runeword(self, host):
        if host.rarity != "normal" or not host.sockets or len(host.socketed) != host.sockets:
            return None
        codes = [f.code for f in host.socketed]
        if any(getattr(f, "gem", (None,))[0] != "rune" for f in host.socketed):
            return None
        anc = host.base.get("ancestors", set()) if isinstance(host.base, dict) else set()
        for rw in self.runewords:
            if rw["runes"] == codes and rw["itypes"] & anc and not (rw["etypes"] & anc):
                return rw
        return None


def prop_text(code, lo, hi):
    from .items import MOD_TEXT
    fmt = MOD_TEXT.get(code) or EXTRA_TEXT.get(code) or (code + " {0}")
    try:
        if "{1}" in fmt:
            return fmt.format(lo, hi)
        return fmt.format(hi if lo == hi or not lo else "%d-%d" % (lo, hi))
    except Exception:
        return code


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def apply_props(item, props, rng):
    """Add D2 properties [(code, min, max)] to an item (stats + description lines)."""
    from .d2content import PROP_MAP
    if item.mod_list is None:
        item.mod_list = []
    for code, lo, hi in props:
        info = PROP_MAP.get(code)
        if info and info[1] == "minmax":
            v = (min(lo, hi), max(lo, hi))
            key = info[0]
            old = item.mods.get(key, (0, 0))
            old = old if isinstance(old, tuple) else (0, 0)
            item.mods[key] = (old[0] + v[0], old[1] + v[1])
            item.mod_list.append((code, v))
            continue
        v = rng.randint(min(lo, hi), max(lo, hi)) if lo != hi else hi
        key = info[0] if info else code
        if isinstance(item.mods.get(key), tuple):
            continue
        item.mods[key] = item.mods.get(key, 0) + v
        item.mod_list.append((code, v))
    if getattr(item, "base_defense", None) is not None:
        item.defense = item.base_defense * (100 + item.mods.get("edef", 0)) // 100 + item.mods.get("def", 0)


def insert(content, host, filler, rng):
    """Put a gem / rune into a socketed item. Returns a message or None if it doesn't fit."""
    rules = content.sockets
    if not getattr(host, "sockets", 0) or len(host.socketed) >= host.sockets:
        return None
    if getattr(filler, "gem", None) is None:
        return None
    if filler.levelreq > host.levelreq:
        host.levelreq = filler.levelreq
    host.socketed.append(filler)
    apply_props(host, rules.mods_for(filler, host), rng)
    rw = rules.find_runeword(host)
    if rw is not None:
        host.runeword = rw["name"]
        host.rarity = "unique"
        props = [(c, lo, hi) for c, param, lo, hi in rw["props"] if c not in UNSUPPORTED]
        apply_props(host, props, rng)
        for c, param, lo, hi in rw["props"]:
            if c in UNSUPPORTED:
                host.extra_lines.append(_unsupported_text(c, param, lo, hi))
        return "The runes glow - %s!" % rw["name"]
    return "Inserted %s." % filler.name


UNSUPPORTED = {"charged", "aura", "oskill", "hit-skill", "gethit-skill", "kill-skill", "death-skill",
               "levelup-skill", "skill", "skilltab", "att-skill", "str/lvl", "mag%/lvl", "dmg-elem"}


def _unsupported_text(code, param, lo, hi):
    if code == "aura":
        return "Level %d %s Aura When Equipped" % (hi, param)
    if code == "oskill":
        return "+%d to %s" % (hi, param)
    if code == "charged":
        return "Level %d %s (charges)" % (hi, param)
    if code in ("hit-skill", "gethit-skill", "kill-skill", "death-skill", "levelup-skill", "att-skill"):
        return "%d%% chance to cast level %d %s" % (lo, hi, param)
    return "%s %s" % (code, param)


def price(item):
    """What a vendor asks for an item (gold)."""
    base = item.base if isinstance(item.base, dict) else {}
    cost = max(1, base.get("cost", 0) or 10)
    if item.kind == "potion" or getattr(item, "use", None):
        return cost
    if getattr(item, "gem", None):
        return cost
    extra = 0
    mult = 1024
    for a in getattr(item, "affixes", []) or []:
        mult += a.get("multiply", 0)
        extra += a.get("add", 0)
    if item.rarity == "magic":
        mult = max(mult, 2048)
    v = cost * mult // 1024 + extra
    if getattr(item, "sockets", 0):
        v += 50 * item.sockets
    for f in getattr(item, "socketed", []):
        v += price(f) // 2
    if getattr(item, "runeword", None):
        v *= 3
    return max(1, int(v))


def sell_price(item):
    return max(1, price(item) // 5)


def identify(item):
    if getattr(item, "identified", True):
        return False
    item.identified = True
    return True
