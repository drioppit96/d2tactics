"""D2 item properties (Properties.txt codes as used by UniqueItems, SetItems, Sets, Runes, Gems
and the affix tables): what each one does to the hero, and its tooltip line.

    apply(item, [(code, param, min, max)], rng)     adds them to an item
    text(code, value, param)                        D2-style line for one property
"""
import random

from .d2content import PROP_MAP, ELEM_PARTS

CLASS_CODES = ["ama", "sor", "nec", "pal", "bar", "dru", "ass"]
CLASS_NAMES = {"ama": "Amazon", "sor": "Sorceress", "nec": "Necromancer", "pal": "Paladin", "bar": "Barbarian",
               "dru": "Druid", "ass": "Assassin"}
TAB_NAMES = ["Bow and Crossbow Skills", "Passive and Magic Skills", "Javelin and Spear Skills",
             "Fire Skills", "Lightning Skills", "Cold Skills",
             "Curses", "Poison and Bone Skills", "Summoning Skills",
             "Combat Skills", "Offensive Auras", "Defensive Auras",
             "Combat Skills", "Masteries", "Warcries",
             "Summoning Skills", "Shape Shifting Skills", "Elemental Skills",
             "Traps", "Shadow Disciplines", "Martial Arts"]

# per character level (value = param / 8 per level, like D2's "x/lvl" properties)
PER_LEVEL = {"ac/lvl": "def", "hp/lvl": "life", "mana/lvl": "mana", "att/lvl": "ar", "str/lvl": "str",
             "dex/lvl": "dex", "vit/lvl": "vit", "enr/lvl": "eng", "dmg/lvl": "maxdmg", "dmg%/lvl": "ed",
             "thorns/lvl": "thorns", "gold%/lvl": "gf", "mag%/lvl": "mf", "res-fire/lvl": "res_fire",
             "res-cold/lvl": "res_cold", "res-ltng/lvl": "res_ltng", "res-pois/lvl": "res_pois",
             "abs-fire/lvl": "absorb_fire", "abs-cold/lvl": "absorb_cold", "abs-ltng/lvl": "absorb_ltng",
             "deadly/lvl": "ds", "stam/lvl": "stamina", "regen-stam/lvl": "stamina_regen", "dmg-max/lvl": "maxdmg",
             "att-und/lvl": "ar_undead", "dmg-und/lvl": "dmg_undead", "att-dem/lvl": "ar_demon",
             "dmg-dem/lvl": "dmg_demon", "ac%/lvl": "edef"}
# extra stat keys (beyond d2content.PROP_MAP)
EXTRA_MAP = {
    "regen-mana": "mana_regen_pct", "red-dmg%": "dr_pct", "heal-kill": "life_kill", "addxp": "xp_pct",
    "res-fire-max": "maxres_fire", "res-cold-max": "maxres_cold", "res-ltng-max": "maxres_ltng",
    "res-pois-max": "maxres_pois", "res-all-max": "maxres_all", "abs-fire": "absorb_fire", "abs-cold": "absorb_cold",
    "abs-ltng": "absorb_ltng", "abs-fire%": "absorb_fire_pct", "abs-cold%": "absorb_cold_pct",
    "abs-ltng%": "absorb_ltng_pct", "abs-mag": "absorb_mag", "dmg-undead": "dmg_undead", "dmg-demon": "dmg_demon",
    "ac-miss": "def_missile", "ac-hth": "def_melee", "reduce-ac": "target_def", "light-thorns": "ltng_thorns",
    "pierce-fire": "pierce_fire", "pierce-cold": "pierce_cold", "pierce-ltng": "pierce_ltng",
    "pierce-pois": "pierce_pois", "extra-fire": "extra_fire", "extra-cold": "extra_cold", "extra-ltng": "extra_ltng",
    "extra-pois": "extra_pois", "half-freeze": "half_freeze", "noheal": "noheal", "pierce": "pierce",
    "block3": "fbr", "Light": "light", "demon-heal": "demon_heal", "stamdrain": "stamdrain",
    "fireskill": "elem_fire_skills", "allskills": "all_skills",
}
TEXT_ONLY = {"indestruct", "ethereal", "rep-dur", "rep-quant", "stack", "state", "magicarrow", "explosivearrow",
             "fade", "bloody", "rip", "cheap", "reanimate", "randclassskill", "skill-rand"}
WITH_PARAM = {"skill", "oskill", "aura", "charged", "hit-skill", "gethit-skill", "kill-skill", "death-skill",
              "levelup-skill", "att-skill", "skilltab"}

TEXT = {
    "dmg%": "+{0}% Enhanced Damage", "att": "+{0} to Attack Rating", "att%": "{0}% Bonus to Attack Rating",
    "ac": "+{0} Defense", "ac%": "+{0}% Enhanced Defense", "hp": "+{0} to Life", "mana": "+{0} to Mana",
    "str": "+{0} to Strength", "dex": "+{0} to Dexterity", "vit": "+{0} to Vitality", "enr": "+{0} to Energy",
    "light": "+{0} to Light Radius", "Light": "+{0} to Light Radius", "thorns": "Attacker Takes Damage of {0}",
    "dmg-min": "+{0} to Minimum Damage", "dmg-max": "+{0} to Maximum Damage",
    "move1": "+{0}% Faster Run/Walk", "move2": "+{0}% Faster Run/Walk", "move3": "+{0}% Faster Run/Walk",
    "swing1": "+{0}% Increased Attack Speed", "swing2": "+{0}% Increased Attack Speed",
    "swing3": "+{0}% Increased Attack Speed", "regen": "Replenish Life +{0}", "lifesteal": "{0}% Life Stolen per Hit",
    "manasteal": "{0}% Mana Stolen per Hit", "res-fire": "Fire Resist +{0}%", "res-cold": "Cold Resist +{0}%",
    "res-ltng": "Lightning Resist +{0}%", "res-pois": "Poison Resist +{0}%", "res-all": "All Resistances +{0}",
    "red-dmg": "Damage Reduced by {0}", "red-dam": "Damage Reduced by {0}", "red-mag": "Magic Damage Reduced by {0}",
    "mag%": "{0}% Better Chance of Getting Magic Items", "gold%": "{0}% Extra Gold from Monsters",
    "block": "{0}% Increased Chance of Blocking", "block2": "+{0}% Faster Block Rate", "block3": "+{0}% Faster Block Rate",
    "balance1": "+{0}% Faster Hit Recovery", "balance2": "+{0}% Faster Hit Recovery", "balance3": "+{0}% Faster Hit Recovery",
    "cast1": "+{0}% Faster Cast Rate", "cast2": "+{0}% Faster Cast Rate", "cast3": "+{0}% Faster Cast Rate",
    "dmg-fire": "Adds {0}-{1} Fire Damage", "dmg-cold": "Adds {0}-{1} Cold Damage",
    "dmg-ltng": "Adds {0}-{1} Lightning Damage", "dmg-pois": "Adds {0}-{1} Poison Damage",
    "dmg-mag": "Adds {0}-{1} Magic Damage", "dmg-norm": "Adds {0}-{1} Damage", "dmg": "Adds {0}-{1} Damage",
    "knock": "Knockback", "nofreeze": "Cannot Be Frozen", "howl": "Hit Causes Monster to Flee {0}%",
    "dmg-to-mana": "{0}% Damage Taken Goes To Mana", "manarecovery": "Regenerate Mana {0}%",
    "regen-mana": "Regenerate Mana {0}%", "hp%": "Increase Maximum Life {0}%", "mana%": "Increase Maximum Mana {0}%",
    "stam": "+{0} Maximum Stamina", "stamina": "+{0} Maximum Stamina", "regen-stam": "Heal Stamina Plus {0}%",
    "dur": "+{0} Maximum Durability", "ease": "Requirements {0}%", "openwounds": "{0}% Chance of Open Wounds",
    "crush": "{0}% Chance of Crushing Blow", "deadly": "{0}% Deadly Strike", "slow": "Slows Target by {0}%",
    "stupidity": "Hit Blinds Target", "freeze": "Freezes Target +{0}", "allskills": "+{0} to All Skills",
    "res-pois-len": "Poison Length Reduced by {0}%", "att-demon": "+{0} to Attack Rating against Demons",
    "att-undead": "+{0} to Attack Rating against Undead", "dmg-demon": "+{0}% Damage to Demons",
    "dmg-undead": "+{0}% Damage to Undead", "mana-kill": "+{0} to Mana after each Kill",
    "heal-kill": "+{0} Life after each Kill", "ignore-ac": "Ignore Target's Defense",
    "dmg-ac": "-{0} to Monster Defense Per Hit", "ac-miss": "+{0} Defense vs. Missile",
    "ac-hth": "+{0} Defense vs. Melee", "reduce-ac": "-{0}% Target Defense", "red-dmg%": "Damage Reduced by {0}%",
    "noheal": "Prevent Monster Heal", "indestruct": "Indestructible", "ethereal": "Ethereal",
    "res-fire-max": "+{0}% to Maximum Fire Resist", "res-cold-max": "+{0}% to Maximum Cold Resist",
    "res-ltng-max": "+{0}% to Maximum Lightning Resist", "res-pois-max": "+{0}% to Maximum Poison Resist",
    "res-all-max": "+{0}% to All Maximum Resistances", "fireskill": "+{0} to Fire Skills",
    "pierce-fire": "-{0}% to Enemy Fire Resistance", "pierce-cold": "-{0}% to Enemy Cold Resistance",
    "pierce-ltng": "-{0}% to Enemy Lightning Resistance", "pierce-pois": "-{0}% to Enemy Poison Resistance",
    "extra-fire": "+{0}% to Fire Skill Damage", "extra-cold": "+{0}% to Cold Skill Damage",
    "extra-ltng": "+{0}% to Lightning Skill Damage", "extra-pois": "+{0}% to Poison Skill Damage",
    "abs-fire": "+{0} Fire Absorb", "abs-cold": "+{0} Cold Absorb", "abs-ltng": "+{0} Lightning Absorb",
    "abs-mag": "+{0} Magic Absorb", "abs-fire%": "Fire Absorb {0}%", "abs-cold%": "Cold Absorb {0}%",
    "abs-ltng%": "Lightning Absorb {0}%", "half-freeze": "Half Freeze Duration",
    "light-thorns": "Attacker Takes Lightning Damage of {0}", "pierce": "{0}% Chance to Pierce",
    "all-stats": "+{0} to all Attributes", "addxp": "+{0}% to Experience Gained", "demon-heal": "+{0} Life after each Demon Kill",
    "stamdrain": "{0}% Slower Stamina Drain", "rep-dur": "Repairs 1 Durability in {0} Seconds",
    "rep-quant": "Replenishes Quantity", "stack": "Increased Stack Size", "magicarrow": "Fires Magic Arrows",
    "explosivearrow": "Fires Explosive Arrows or Bolts", "fade": "Fade", "bloody": "", "rip": "Slain Monsters Rest in Peace",
    "cheap": "Reduces all Vendor Prices {0}%", "reanimate": "{0}% Reanimate as monster", "sock": "Socketed ({0})",
    "knock": "Knockback", "state": "", "regen-stam": "Heal Stamina Plus {0}%",
    "fire-min": "+{0} to Minimum Fire Damage", "fire-max": "+{0} to Maximum Fire Damage",
    "cold-min": "+{0} to Minimum Cold Damage", "cold-max": "+{0} to Maximum Cold Damage",
    "ltng-min": "+{0} to Minimum Lightning Damage", "ltng-max": "+{0} to Maximum Lightning Damage",
    "pois-min": "+{0} to Minimum Poison Damage", "pois-max": "+{0} to Maximum Poison Damage",
    "mag-min": "+{0} to Minimum Magic Damage", "mag-max": "+{0} to Maximum Magic Damage",
}
_skill_names = None
SRC = None              # the D2 data source (set by D2Content)
LEVEL = 1               # character level the "per level" lines are shown for (set by the tooltip)


def skill_name(param):
    """Skills.txt id or name -> the skill's name."""
    global _skill_names
    p = str(param or "").strip()
    if not p:
        return "?"
    if _skill_names is None:
        _skill_names = {}
        try:
            from d2.source import read_table
            for r in read_table(SRC, "Skills"):
                if r.get("skill"):
                    _skill_names[r.get("id", "")] = r["skill"]
                    _skill_names[r["skill"].lower()] = r["skill"]
        except Exception:
            pass
    return _skill_names.get(p, _skill_names.get(p.lower(), p))


def text(code, v, param=""):
    """One tooltip line. v is a number or (min, max)."""
    code = code.lstrip("*")
    lo, hi = v if isinstance(v, tuple) else (v, v)
    if code in CLASS_NAMES:
        return "+%d to %s Skill Levels" % (hi, CLASS_NAMES[code])
    if code == "skilltab":
        try:
            t = int(param)
        except (TypeError, ValueError):
            t = -1
        if 0 <= t < len(TAB_NAMES):
            return "+%d to %s (%s Only)" % (hi, TAB_NAMES[t], CLASS_NAMES[CLASS_CODES[t // 3]])
        return "+%d to a Skill Tab" % hi
    if code in ("skill", "oskill"):
        return "+%d to %s" % (hi, skill_name(param)) + (" (Class Only)" if code == "skill" else "")
    if code == "aura":
        return "Level %d %s Aura When Equipped" % (hi, skill_name(param))
    if code == "charged":
        return "Level %d %s (%d Charges)" % (hi, skill_name(param), lo)
    if code in ("hit-skill", "gethit-skill", "kill-skill", "death-skill", "levelup-skill", "att-skill"):
        when = {"hit-skill": "on striking", "gethit-skill": "when struck", "kill-skill": "when you Kill an Enemy",
                "death-skill": "when you Die", "levelup-skill": "when you Level-Up", "att-skill": "on attack"}[code]
        return "%d%% Chance to cast level %d %s %s" % (lo, hi, skill_name(param), when)
    if code in PER_LEVEL:
        what = TEXT.get(code.replace("/lvl", ""), code + " {0}")
        val = (_int(param) or hi) * max(1, LEVEL) // 8
        try:
            return what.format(val) + " (Based on Character Level)" if "{1}" not in what else what
        except Exception:
            return code
    fmt = TEXT.get(code)
    if fmt is None:
        from .items import MOD_TEXT
        from .d2items import EXTRA_TEXT
        fmt = MOD_TEXT.get(code) or EXTRA_TEXT.get(code) or (code + " {0}")
    if not fmt:
        return ""
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


def stat_key(code, param=""):
    """The hero stat a property feeds (None = only shown)."""
    code = code.lstrip("*")
    if code in PER_LEVEL:
        return PER_LEVEL[code] + "@lvl"
    if code in CLASS_NAMES:
        return "cls_" + code
    if code == "skilltab":
        return "tab_%d" % _int(param, -1)
    if code in ("skill", "oskill"):
        return "sk_" + skill_name(param).lower()
    if code in EXTRA_MAP:
        return EXTRA_MAP[code]
    info = PROP_MAP.get(code)
    return info[0] if info else None


def apply(item, props, rng=random, roll=True):
    """Add [(code, param, min, max)] to an item: its stats (item.mods), lines (item.mod_list)."""
    if item.mod_list is None:
        item.mod_list = []
    elem = {}
    for code, param, lo, hi in props:
        if not code or code.startswith("*"):
            continue                    # '*' = commented out in D2's own tables
        if code in ELEM_PARTS:
            e, i = ELEM_PARTS[code]
            elem.setdefault(e, [0, 0])[i] = rng.randint(min(lo, hi), max(lo, hi)) if roll else max(lo, hi)
            continue
        if code in ("fire-len", "cold-len", "pois-len", "dmg-elem", "dmg-elem-min", "dmg-elem-max"):
            continue
        if code == "sock":
            n = rng.randint(min(lo, hi), max(lo, hi)) if roll and lo != hi else max(lo, hi)
            item.sockets = max(getattr(item, "sockets", 0), n)
            continue
        if code == "all-stats":
            v = rng.randint(min(lo, hi), max(lo, hi)) if roll else max(lo, hi)
            for k in ("str", "dex", "vit", "eng"):
                item.mods[k] = item.mods.get(k, 0) + v
            item.mod_list.append((code, v, ""))
            continue
        info = PROP_MAP.get(code)
        if info and info[1] == "minmax":
            v = (min(lo, hi), max(lo, hi))
            old = item.mods.get(info[0], (0, 0))
            old = old if isinstance(old, tuple) else (0, 0)
            item.mods[info[0]] = (old[0] + v[0], old[1] + v[1])
            item.mod_list.append((code, v, ""))
            continue
        if code in PER_LEVEL:
            v = _int(param) or max(lo, hi)
        elif code in ("aura", "charged", "hit-skill", "gethit-skill", "kill-skill", "death-skill",
                      "levelup-skill", "att-skill"):
            item.mod_list.append((code, (lo, hi), param))
            continue
        else:
            v = rng.randint(min(lo, hi), max(lo, hi)) if roll and lo != hi else max(lo, hi)
        key = stat_key(code, param)
        if key is not None and code not in TEXT_ONLY:
            if isinstance(item.mods.get(key), tuple):
                continue
            item.mods[key] = item.mods.get(key, 0) + v
        item.mod_list.append((code, v, param))
    for e, (lo, hi) in elem.items():
        key = "dmg-" + e if e != "mag" else "dmg-mag"
        info = PROP_MAP.get(key) or (("mag_dmg", "minmax") if e == "mag" else None)
        k = info[0] if info else e + "_dmg"
        old = item.mods.get(k, (0, 0))
        old = old if isinstance(old, tuple) else (0, 0)
        item.mods[k] = (old[0] + lo, old[1] + max(lo, hi))
        item.mod_list.append((key, (lo, max(lo, hi)), ""))
    if getattr(item, "base_defense", None) is not None:
        item.defense = item.base_defense * (100 + item.mods.get("edef", 0)) // 100 + item.mods.get("def", 0)
