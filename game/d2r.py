"""Diablo II: Resurrected's balance changes, new runewords, set upgrades and Sunder Charms.

The game reads Diablo's own 1.14d tables out of your install, so it plays by 1.14d rules. D2R
changed a lot of those rules in its patch 2.4 (the first class balance pass in eleven years),
2.6 and later. This file is that change list, written as patches laid over the tables after
they are read. Nothing here touches your install.

Four things live here:

    SKILLS      what patch 2.4 did to each skill, as edits to the skill's own table row
    RUNEWORDS   the sixteen runewords 2.4 and 2.6 added (your 1.14d Runes.txt has none of them)
    SETS        the set bonuses 2.4 raised or added
    SUNDER      the six Sunder Charms, which break a monster's immunity

Some of D2R's changes mean nothing in a turn-based game - animation speed, being able to
interrupt a move, casting delays, attack speed caps, aiming a beam freely. NOT_APPLICABLE at
the bottom lists them, so it is clear they were read and skipped rather than missed.

    patch_skills(trees)     after game/skills.py has read the skill tables
    runewords()             extra entries for game/d2items.py's runeword list
    patch_sets(content)     after game/d2content.py has read SetItems.txt and Sets.txt
    sunder_drop(world, m)   a champion's chance to drop a Sunder Charm
    sundered(player, et)    is this element's immunity broken for this hero
"""
import os

# On by default. Setting the environment variable D2TACTICS_D2R=0 plays by plain 1.14d rules
# instead, which is how the before-and-after comparisons in testing were made.
ENABLED = os.environ.get("D2TACTICS_D2R", "1") != "0"

RUNE_ORDER = ["El", "Eld", "Tir", "Nef", "Eth", "Ith", "Tal", "Ral", "Ort", "Thul", "Amn", "Sol", "Shael",
              "Dol", "Hel", "Io", "Lum", "Ko", "Fal", "Lem", "Pul", "Um", "Mal", "Ist", "Gul", "Vex",
              "Ohm", "Lo", "Sur", "Ber", "Jah", "Cham", "Zod"]


def _r(*names):
    """Rune names -> the item codes the sockets hold ("Nef" -> "r04")."""
    return ["r%02d" % (RUNE_ORDER.index(n) + 1) for n in names]


# ---------------------------------------------------------------- skills (patch 2.4)
# Each entry is what to change about one skill. Every key is optional:
#
#   col      straight into the skill's table row: damage columns (emin, emax, eminlev1..5),
#            attack rating (tohit, levtohit), mana, the param columns the game's own formulas
#            read - param8 is nearly always the synergy percentage
#   syn      replaces the elemental damage synergies: {other skill: percent per level}
#   psyn     the same for physical damage synergies
#   wsyn     synergies for a weapon skill (bow, javelin, claw): adds percent damage per level
#            of the other skill, because those skills take their damage from the weapon
#   escale   multiplies the skill's elemental damage (for "damage about 75% higher")
#   pscale   the same for its physical damage
#   manalvl  mana per level, as a decimal (the table can only hold whole numbers)
#   hp_mult  a summon's life, multiplied
#   extra    behaviour flags, the same ones game/skills.py's OVERRIDES uses
#
# The table keys are Diablo's internal skill names: "Fire Trauma" is Fire Blast, "Shock Field"
# is Shock Web, "Royal Strike" is Phoenix Strike, "Plague Poppy" is Poison Creeper, "Wearwolf"
# and "Wearbear" are the two shape shifts.
SKILLS = {
    # ---------------- Amazon
    "Fire Arrow": dict(manalvl=0.0),
    "Magic Arrow": dict(col={"mindam": 2, "maxdam": 2}),
    "Multiple Shot": dict(wsyn={"Guided Arrow": 12}),
    "Guided Arrow": dict(col={"param4": 7}, wsyn={"Multiple Shot": 12}),
    "Strafe": dict(col={"tohit": 30, "levtohit": 9}, wsyn={"Multiple Shot": 5, "Guided Arrow": 10}),
    "Exploding Arrow": dict(col={"param8": 14, "eminlev4": 18, "eminlev5": 30, "emaxlev4": 21, "emaxlev5": 34},
                            manalvl=0.25),
    "Immolation Arrow": dict(escale=2.0, manalvl=0.25),
    "Freezing Arrow": dict(manalvl=0.25),
    "Impale": dict(extra={"always_hit": True, "slow_hit": 2}),
    "Fend": dict(extra={"hits": 2}),
    "Power Strike": dict(syn={"Lightning Strike": 14, "Lightning Bolt": 14, "Charged Strike": 14}),
    "Charged Strike": dict(syn={"Lightning Strike": 14, "Lightning Bolt": 14, "Power Strike": 14}),
    "Lightning Strike": dict(syn={"Charged Strike": 11, "Lightning Bolt": 11, "Power Strike": 11}),
    "Plague Javelin": dict(col={"param8": 14}, escale=1.25),
    "Inner Sight": dict(col={"param5": 27}),
    "Slow Missiles": dict(col={"param5": 27}),
    # ---------------- Sorceress
    "Frost Nova": dict(escale=1.25),
    "Frozen Armor": dict(col={"param8": 9}),
    "Shiver Armor": dict(escale=1.25),
    "Chilling Armor": dict(escale=3.0, col={"param1": 60, "param2": 7, "param8": 9}),
    "Nova": dict(col={"mana": 13}, syn={"Static Field": 5}),
    "Thunder Storm": dict(syn={"Static Field": 7}),
    "Inferno": dict(escale=1.75, col={"param8": 16, "mana": 16}),
    "Blaze": dict(escale=1.6, col={"param8": 6, "param7": 0}),
    "Hydra": dict(extra={"turret_max": 6}),
    # ---------------- Necromancer
    "Raise Skeletal Mage": dict(hp_mult=1.3),
    "BloodGolem": dict(pscale=1.2, hp_mult=1.15),
    "FireGolem": dict(escale=1.4),
    "Bone Armor": dict(col={"param1": 30, "param2": 15}),
    "Bone Spear": dict(col={"param8": 8}),
    "Bone Spirit": dict(col={"param8": 8}),
    # D2R: Weaken takes 33% off their damage and 1% more per level (1.14d was a flat 33%)
    "Weaken": dict(col={"aurastatcalc1": "-(par5 + lvl - 1)"}),
    # ---------------- Paladin
    "Holy Fire": dict(col={"param8": 21, "param7": 10}, extra={"melee_double": True}),
    "Holy Freeze": dict(extra={"melee_double": True}),
    "Holy Shock": dict(extra={"melee_double": True}),
    "Sanctuary": dict(extra={"melee_double": True}),
    "Thorns": dict(extra={"flat_thorns": True}),
    "Sacrifice": dict(extra={"self_damage_scales": True}),
    "Conversion": dict(extra={"convert_max": 90}),
    "Holy Bolt": dict(escale=1.5, syn={"Fist of the Heavens": 50, "Prayer": 20},
                      extra={"undead_only": False, "pierce": True}),
    "Fist of the Heavens": dict(extra={"undead_only": False}),
    # ---------------- Barbarian
    "War Cry": dict(pscale=1.3, manalvl=0.75),
    "Shout": dict(col={"param1": 150}),
    "Battle Command": dict(col={"param1": 150}),
    # D2R: a wider ward that also slows the monsters fleeing it and makes them take more
    # damage. The radius and those two effects live in game/world.py (WARD_RADIUS).
    "Grim Ward": dict(),
    "Sword Mastery": dict(col={"param1": 40}),
    "Axe Mastery": dict(col={"param1": 40}),
    "Mace Mastery": dict(col={"param1": 40}),
    "Pole Arm Mastery": dict(col={"param1": 40}),
    "Spear Mastery": dict(col={"param1": 40}),
    "Throwing Mastery": dict(col={"param1": 44}),
    "Double Throw": dict(extra={"dmg_base": 16, "dmg_lvl": 8}),
    "Leap Attack": dict(extra={"dmg_base": 200, "dmg_lvl": 30, "ar_base": 100, "ar_lvl": 20, "splash": 2}),
    # ---------------- Druid
    "Molten Boulder": dict(col={"param7": 12}),
    "Volcano": dict(col={"param7": 16}),
    "Armageddon": dict(pscale=2.0, psyn={"Volcano": 18}),
    "Arctic Blast": dict(escale=2.0, syn={"Cyclone Armor": 15}),
    "Twister": dict(pscale=1.5),
    "Wearbear": dict(col={"param2": 15, "param3": 40, "param4": 10}, extra={"always_hit": False}),
    "Rabies": dict(col={"levtohit": 10, "param8": 20}),
    "Fury": dict(col={"levtohit": 10}),
    "Maul": dict(col={"tohit": 40, "levtohit": 15, "param3": 30}),
    "Shock Wave": dict(col={"param8": 10}),
    "Fire Claws": dict(escale=1.75, syn={"Firestorm": 22, "Molten Boulder": 22}),
    "Raven": dict(col={"levtohit": 30}, escale=1.5),
    "Summon Spirit Wolf": dict(hp_mult=1.8, extra={"elem": "cold", "slow_hit": 1}),
    "Summon Fenris": dict(hp_mult=1.9, pscale=1.3),
    "Summon Grizzly": dict(hp_mult=1.15),
    "Plague Poppy": dict(escale=2.5, hp_mult=2.0),
    "Spirit of Barbs": dict(extra={"flat_thorns": True}),
    # ---------------- Assassin
    "Tiger Strike": dict(col={"tohit": 25, "levtohit": 10}),
    "Cobra Strike": dict(col={"tohit": 25, "levtohit": 10}),
    "Fists of Fire": dict(col={"tohit": 25, "levtohit": 10}),
    "Claws of Thunder": dict(col={"tohit": 25, "levtohit": 10}),
    "Blades of Ice": dict(col={"tohit": 25, "levtohit": 10}),
    "Royal Strike": dict(col={"tohit": 25, "levtohit": 10}),
    "Dragon Talon": dict(extra={"one_charge": True}),
    "Dragon Claw": dict(extra={"one_charge": True, "dmg_base": 50, "dmg_lvl": 15}),
    "Dragon Tail": dict(extra={"one_charge": True, "dmg_base": 50, "dmg_lvl": 20}),
    "Dragon Flight": dict(extra={"one_charge": True, "dmg_base": 100, "dmg_lvl": 35}),
    "Venom": dict(col={"param2": 300}),
    "Shock Field": dict(syn={"Charged Bolt Sentry": 17, "Lightning Sentry": 17}),
    "Charged Bolt Sentry": dict(syn={"Fire Trauma": 9, "Lightning Sentry": 9, "Death Sentry": 6}),
    "Lightning Sentry": dict(syn={"Shock Field": 18, "Charged Bolt Sentry": 18, "Death Sentry": 12}),
    "Fire Trauma": dict(col={"param8": 11}),
    "Wake of Fire Sentry": dict(syn={"Fire Trauma": 10, "Inferno Sentry": 10}),
    "Inferno Sentry": dict(syn={"Fire Trauma": 18, "Wake of Fire Sentry": 18, "Death Sentry": 10}),
    "Blade Sentinel": dict(pscale=2.0, psyn={"Blade Fury": 10, "Blade Shield": 10}),
    "Blade Fury": dict(col={"levtohit": 10}, psyn={"Blade Sentinel": 10, "Blade Shield": 10}),
    "Blade Shield": dict(pscale=3.0, psyn={"Blade Sentinel": 10, "Blade Fury": 10}),
}

# synergy columns: elemental damage, physical damage
_SYN_COL = {"syn": "edmgsympercalc", "psyn": "dmgsympercalc"}


def _syn_text(pairs):
    return " + ".join("skill('%s'.blvl)*%d" % (k, v) for k, v in sorted(pairs.items()))


def patch_skills(trees):
    """Lay the 2.4 changes over the skill rows the tables gave us."""
    if not ENABLED:
        return
    for tree in trees.values():
        for key, s in tree.items():
            p = SKILLS.get(key)
            if not p or s.data is None:
                continue
            s.data = dict(s.data)                      # the row is shared; work on our own copy
            for col, val in (p.get("col") or {}).items():
                s.data[col] = str(val)
            for which, column in _SYN_COL.items():
                if p.get(which):
                    s.data[column] = _syn_text(p[which])
            for k in ("escale", "pscale", "manalvl", "hp_mult", "wsyn"):
                if k in p:
                    s.extra[k] = p[k]
            s.extra.update(p.get("extra") or {})
            s.d2r = True


# ---------------------------------------------------------------- runewords (patch 2.4 and 2.6)
# (name, runes, item types it fits, item types it does not, [(property, param, min, max)])
# The item types are Diablo's own: swor sword, knif dagger, h2h claw, axe, mace, staf staff,
# miss bow and crossbow, tors body armour, helm, shie shield, weap any weapon.
# Property codes are the same ones the item tables use (game/props.py lists them all).
RUNEWORDS = [
    ("Flickering Flame", _r("Nef", "Pul", "Vex"), {"helm"}, set(), [
        ("aura", "Resist Fire", 4, 8), ("fireskill", "", 3, 3), ("pierce-fire", "", 10, 15),
        ("ac%", "", 30, 30), ("ac-miss", "", 30, 30), ("mana", "", 50, 75),
        ("res-fire-max", "", 5, 5), ("half-freeze", "", 1, 1), ("res-pois-len", "", 50, 50)]),
    ("Mist", _r("Cham", "Shael", "Gul", "Thul", "Ith"), {"miss"}, set(), [
        ("aura", "Concentration", 8, 12), ("allskills", "", 3, 3), ("swing1", "", 20, 20),
        ("pierce", "", 100, 100), ("dmg%", "", 325, 375), ("dmg-max", "", 9, 9),
        ("att%", "", 20, 20), ("dmg-cold", "", 3, 14), ("freeze", "", 3, 3),
        ("vit", "", 24, 24), ("res-all", "", 40, 40)]),
    ("Obsession", _r("Zod", "Ist", "Lem", "Lum", "Io", "Nef"), {"staf"}, set(), [
        ("gethit-skill", "Weaken", 24, 10), ("allskills", "", 4, 4), ("cast1", "", 65, 65),
        ("balance1", "", 60, 60), ("knock", "", 1, 1), ("vit", "", 10, 10), ("enr", "", 10, 10),
        ("hp%", "", 15, 25), ("regen-mana", "", 15, 30), ("res-all", "", 60, 70),
        ("gold%", "", 75, 75), ("mag%", "", 30, 30), ("indestruct", "", 1, 1)]),
    ("Pattern", _r("Tal", "Ort", "Thul"), {"h2h"}, set(), [
        ("block3", "", 30, 30), ("att%", "", 10, 10), ("dmg-fire", "", 12, 32),
        ("dmg-ltng", "", 1, 50), ("dmg-cold", "", 3, 14), ("dmg-pois", "", 75, 75),
        ("str", "", 6, 6), ("dex", "", 6, 6), ("res-all", "", 15, 15), ("dmg%", "", 40, 80)]),
    ("Plague", _r("Cham", "Shael", "Um"), {"swor", "knif", "h2h"}, set(), [
        ("hit-skill", "Poison Nova", 25, 15), ("gethit-skill", "Lower Resist", 20, 12),
        ("aura", "Cleansing", 13, 17), ("allskills", "", 1, 2), ("swing1", "", 20, 20),
        ("pierce-pois", "", 23, 23), ("deadly", "", 8, 8), ("openwounds", "", 25, 25),
        ("freeze", "", 3, 3), ("dmg%", "", 220, 320)]),
    ("Unbending Will", _r("Fal", "Io", "Ith", "Eld", "El", "Hel"), {"swor"}, set(), [
        ("hit-skill", "Taunt", 18, 18), ("skilltab", "12", 3, 3), ("swing1", "", 20, 30),
        ("dmg%", "", 300, 350), ("dmg-max", "", 9, 9), ("att", "", 50, 50),
        ("dmg-undead", "", 75, 75), ("att-undead", "", 50, 50), ("lifesteal", "", 8, 10),
        ("noheal", "", 1, 1), ("str", "", 10, 10), ("vit", "", 10, 10), ("red-dmg", "", 8, 8),
        ("light", "", 1, 1), ("ease", "", -20, -20)]),
    ("Wisdom", _r("Pul", "Ith", "Eld"), {"helm"}, set(), [
        ("pierce", "", 33, 33), ("att%", "", 15, 25), ("manasteal", "", 4, 8),
        ("ac%", "", 30, 30), ("enr", "", 10, 10), ("stamdrain", "", 15, 15),
        ("nofreeze", "", 1, 1), ("mana-kill", "", 5, 5), ("dmg-to-mana", "", 15, 15)]),
    # ---- patch 2.6: the five helms, the two Hustles, Mosaic, Metamorphosis
    ("Bulwark", _r("Shael", "Io", "Sol"), {"helm"}, set(), [
        ("balance1", "", 20, 20), ("lifesteal", "", 4, 6), ("ac%", "", 75, 100),
        ("vit", "", 10, 10), ("hp%", "", 5, 5), ("regen", "", 30, 30),
        ("red-dmg", "", 7, 7), ("red-dmg%", "", 15, 15)]),
    ("Cure", _r("Shael", "Io", "Tal"), {"helm"}, set(), [
        ("aura", "Cleansing", 1, 1), ("balance1", "", 20, 20), ("ac%", "", 75, 100),
        ("vit", "", 10, 10), ("hp%", "", 5, 5), ("res-pois", "", 5, 5), ("res-pois-len", "", 40, 60)]),
    ("Ground", _r("Shael", "Io", "Ort"), {"helm"}, set(), [
        ("balance1", "", 20, 20), ("ac%", "", 75, 100), ("vit", "", 10, 10), ("hp%", "", 5, 5),
        ("res-ltng", "", 5, 5), ("abs-ltng%", "", 40, 60), ("res-ltng-max", "", 5, 5)]),
    ("Hearth", _r("Shael", "Io", "Thul"), {"helm"}, set(), [
        ("balance1", "", 20, 20), ("ac%", "", 75, 100), ("vit", "", 10, 10), ("hp%", "", 5, 5),
        ("res-cold", "", 5, 5), ("abs-cold%", "", 40, 60), ("nofreeze", "", 1, 1)]),
    ("Temper", _r("Shael", "Io", "Ral"), {"helm"}, set(), [
        ("balance1", "", 20, 20), ("ac%", "", 75, 100), ("vit", "", 10, 10), ("hp%", "", 5, 5),
        ("res-fire", "", 5, 5), ("abs-fire%", "", 40, 60), ("res-fire-max", "", 5, 5)]),
    ("Hustle", _r("Shael", "Ko", "Eld"), {"tors"}, set(), [
        ("balance1", "", 20, 20), ("move1", "", 20, 20), ("dex", "", 10, 10),
        ("res-all", "", 10, 10), ("stamdrain", "", 50, 50)]),
    ("Hustle", _r("Shael", "Ko", "Eld"), {"weap"}, {"tors"}, [
        ("hit-skill", "Burst of Speed", 5, 1), ("swing1", "", 30, 30), ("dmg%", "", 100, 100),
        ("dmg-undead", "", 75, 75), ("att-undead", "", 50, 50), ("dex", "", 10, 10)]),
    ("Mosaic", _r("Mal", "Gul", "Amn"), {"h2h"}, set(), [
        ("skilltab", "20", 2, 2), ("swing1", "", 20, 20), ("dmg%", "", 200, 250),
        ("att%", "", 20, 20), ("extra-fire", "", 8, 15), ("extra-cold", "", 8, 15),
        ("extra-ltng", "", 8, 15), ("noheal", "", 1, 1)]),
    ("Metamorphosis", _r("Io", "Cham", "Fal"), {"helm"}, set(), [
        ("skilltab", "16", 5, 5), ("ac%", "", 50, 80), ("crush", "", 25, 25),
        ("str", "", 10, 10), ("vit", "", 10, 10), ("res-all", "", 10, 10), ("nofreeze", "", 1, 1)]),
]

# Mosaic's own trick: a finishing move does not use up the charge-up stack, it refreshes it
MOSAIC = "Mosaic"


def runewords():
    """The new runewords in the shape game/d2items.py keeps its own list in."""
    if not ENABLED:
        return []
    out = []
    for name, runes, itypes, etypes, props in RUNEWORDS:
        out.append(dict(name=name, runes=list(runes), props=list(props),
                        itypes=set(itypes), etypes=set(etypes), d2r=True))
    return out


# ---------------------------------------------------------------- set items (patch 2.4)
# The set's own bonuses: how many pieces you must wear -> the properties it should give after
# 2.4. "full" is the whole set. A line whose property the set already has replaces that line's
# numbers; anything new is added. SETS_DROP lists the lines 2.4 took out because something
# better took their place.
#
# Three of 2.4's new lines grow with your character level ("+2 per level" cold damage and so
# on). The hero's set bonuses are worked out without rolling, so a range would always give its
# top value; where a per-level property exists here it is used ("mag%/lvl" is value/8 per
# level), and where one does not the line is a fixed amount of about what the real one reaches
# at the level those sets are actually worn.
SETS = {
    "Arcanna's Tricks": {3: [("regen-mana", "", 12, 12)], "full": [("allskills", "", 1, 1)]},
    "Arctic Gear": {"full": [("cold-max", "", 60, 60)]},
    "Bul-Kathos' Children": {"full": [("lifesteal", "", 10, 10), ("deadly", "", 20, 20),
                                      ("dmg-fire", "", 20, 200), ("ac", "", 200, 200)]},
    "Cathan's Traps": {2: [("regen-mana", "", 16, 16)]},
    "Civerb's Vestments": {2: [("res-fire", "", 25, 25)], "full": [("att%", "", 25, 25), ("ac", "", 50, 50)]},
    "Cow King's Leathers": {"full": [("ac", "", 100, 100), ("hp", "", 100, 100), ("allskills", "", 1, 1)]},
    "Infernal Tools": {"full": [("mana%", "", 20, 20), ("nofreeze", "", 1, 1)]},
    "Iratha's Finery": {3: [("pierce", "", 24, 24)]},
    "Milabrega's Regalia": {2: [("ltng-max", "", 60, 60)], 3: [("nofreeze", "", 1, 1)]},
    "Naj's Ancient Vestige": {2: [("mag%/lvl", "12", 12, 12)], "full": [("regen", "", 20, 20),
                                                                        ("fireskill", "", 2, 2), ("hp%", "", 12, 12)]},
    "Sazabi's Grand Tribute": {2: [("res-pois-len", "", 75, 75)],
                               "full": [("allskills", "", 1, 1), ("red-dmg%", "", 16, 16)]},
    "Vidala's Rig": {2: [("manasteal", "", 7, 7)], "full": [("cold-max", "", 45, 45)]},
}
SETS_DROP = {"Arctic Gear": {"full": ["cold-min", "cold-max", "cold-len", "dmg-cold"]},
             "Vidala's Rig": {"full": ["cold-min", "cold-max", "cold-len", "dmg-cold"]}}


def _merge(have, adds):
    """Replace the lines whose property the patch names, keep the rest, append what is new."""
    out = []
    by_code = {p[0]: p for p in adds}
    seen = set()
    for p in have:
        if p[0] in by_code:
            out.append(by_code[p[0]])
            seen.add(p[0])
        else:
            out.append(p)
    out += [p for p in adds if p[0] not in seen]
    return out


def patch_sets(content):
    """Raise the set bonuses 2.4 raised. content is the D2Content that has read the tables."""
    if not ENABLED or not getattr(content, "sets", None):
        return
    by_name = {}
    for idx, sd in content.sets.items():
        by_name[(sd.get("name") or idx).strip()] = sd
        by_name[idx.strip()] = sd
    for name, adds in SETS.items():
        sd = by_name.get(name)
        if sd is None:
            continue
        for where, codes in SETS_DROP.get(name, {}).items():
            if where == "full":
                sd["full"] = [p for p in sd["full"] if p[0] not in codes]
        for n, lines in adds.items():
            if n == "full":
                sd["full"] = _merge(list(sd["full"]), lines)
            else:
                sd["partial"][n] = _merge(list(sd["partial"].get(n) or []), lines)


# ---------------------------------------------------------------- Sunder Charms
# D2R's answer to "my lightning sorceress cannot hurt a lightning immune". A Sunder Charm
# breaks one kind of immunity: an immune monster's resistance becomes 95% instead, so your
# damage gets through, barely. The price is a big hole in your own resistance to that element.
# In Diablo these drop only inside a Terror Zone; here they drop from any champion or unique
# monster, on Nightmare and Hell (never on Normal).
#
# (key, charm name, element, the line it shows, the penalty it puts on you)
SUNDER = [
    ("fire", "Flame Rift", "fire", "Monster Fire Immunity is Sundered", ("res-fire", -90, -70)),
    ("cold", "Cold Rupture", "cold", "Monster Cold Immunity is Sundered", ("res-cold", -90, -70)),
    ("ltng", "Crack of the Heavens", "ltng", "Monster Lightning Immunity is Sundered", ("res-ltng", -90, -70)),
    ("pois", "Rotting Fissure", "pois", "Monster Poison Immunity is Sundered", ("res-pois", -90, -70)),
    ("mag", "Black Cleft", "mag", "Monster Magic Immunity is Sundered", ("res-mag", -65, -45)),
    ("phys", "Bone Break", "phys", "Monster Physical Immunity is Sundered", ("dmg-taken", 10, 20)),
]
SUNDER_BY_KEY = {s[0]: s for s in SUNDER}
SUNDER_CHANCE = 0.012          # per champion or unique monster killed, before magic find
SUNDER_RES = 95                # what a sundered immunity drops to


def charm_entry(key):
    """A Sunder Charm as a UniqueItems.txt-shaped row, so make_unique() can build it."""
    k, name, et, line, (pcode, plo, phi) = SUNDER_BY_KEY[key]
    return dict(index="Sunder " + k, name=name, code="cm3", lvl=60, lvlreq=60, rarity=1, invfile="",
                props=[("sunder-" + k, "", 1, 1), (pcode, "", plo, phi)])


def sunder_drop(world, unit):
    """A champion's or unique's chance at a Sunder Charm. Returns a list (empty most of the time)."""
    if not ENABLED or world.content is None:
        return []
    if not (getattr(unit, "champion", False) or getattr(unit, "unique", False)):
        return []
    diff = (getattr(world.content, "difficulty", "normal") or "normal").lower()
    if diff == "normal":
        return []                      # D2R: never on Normal
    p = world.player
    mf = world.team_mf() if hasattr(world, "team_mf") else 0
    chance = SUNDER_CHANCE * (1.0 + min(2.0, mf / 300.0))
    if getattr(unit, "unique", False):
        chance *= 2.0                  # super uniques and act bosses are the better hunt
    if world.rng.random() >= chance:
        return []
    base = next((b for b in world.content.bases if b.get("code") == "cm3"), None)
    if base is None:
        return []
    have = {getattr(it, "unique_name", None) for it in _all_carried(p)}
    pool = [s[0] for s in SUNDER if ("Sunder " + s[0]) not in have] or [s[0] for s in SUNDER]
    key = world.rng.choice(pool)
    it = world.content.make_unique(base, max(60, unit.level), world.rng, identified=False,
                                   which=charm_entry(key))
    return [it] if it is not None else []


def _all_carried(p):
    out = list(getattr(p, "inventory", []) or [])
    out += list((getattr(p, "equipment", None) or {}).values())
    return [it for it in out if it is not None]


def sundered(unit, et):
    """Does this hero carry the charm that breaks this element's immunity?"""
    if not ENABLED or unit is None or not hasattr(unit, "mod"):
        return False
    return bool(unit.mod("sunder_" + et))


# ---------------------------------------------------------------- hirelings (patch 2.4)
# 2.4 made mercenaries hire at your own level instead of a few levels under it, and gave the
# Iron Wolves a flat buff. Our hirelings already level up with you, so only the hire level and
# the Iron Wolf numbers change.
MERC_HIRE_AT_PLAYER_LEVEL = True
IRON_WOLF = dict(life=1.25, defense=1.40, res=20)


# ---------------------------------------------------------------- read and skipped
# D2R changes that cannot mean anything in a turn-based tactics game, listed so it is clear
# they were considered:
NOT_APPLICABLE = [
    "Casting delays and cooldowns (Valkyrie, Hydra, Blizzard, Meteor, Fire Wall, Armageddon, "
    "Hurricane, Dragon Flight, Blade Sentinel, Immolation Arrow): skills here cost action "
    "points, not seconds, so there is no cooldown to shorten.",
    "Animation speed and attack speed caps (Impale 30% faster, Werewolf and Werebear 75% to "
    "150%, Fury 40%, Maul per charge, Leap and Leap Attack 75%): a turn is a turn.",
    "Being able to interrupt or not be interrupted (Dodge, Avoid, Werebear, Impale): there is "
    "no animation to interrupt.",
    "Free-form aiming (Inferno, Arctic Blast) and holding the button to place more Hydras: "
    "both already work that way here, because you pick a target square.",
    "Stamina (Frenzy's Increased Stamina synergy, slower stamina drain): walking costs action "
    "points here, not stamina.",
    "Tooltip-only fixes (Fade's physical resist line, Multiple Shot's synergy line, Enchant).",
    "Whirlwind moving to the enemy's first position rather than tracking: it already strikes "
    "everything on the path it is given.",
    "Druids keeping wolves and bears summoned together: already true here, because each "
    "summoning skill counts its own minions.",
]
