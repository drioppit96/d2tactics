"""The Warlock - this game's own eighth class (not in D2).

A blood knight: a warrior-sorcerer who pays for his spells with his own life, binds demons and
fights in the front line. Three trees of ten skills, laid out like the Necromancer's:

  Dark Arms    melee: blood-fuelled strikes, a weapon mastery, life steal, a whirling finisher
  Blood Magic  spells that cost LIFE instead of mana and deal magic damage; draining, healing
  Demonology   lesser demons in numbers (imps, succubi), one greater demon at a time, binding

Nothing here is drawn by hand: every skill is built from D2's own tables at load time - its
numbers from a D2 skill of the same tier (so it stays in step with the other classes), its
picture and sound from D2 missiles / overlays, tinted blood red at runtime ("name@blood").
The hero himself is D2's Iron Wolf sprite (sword, shield, cast and run animations) in a
blood-and-soot palette.
"""
from .grid import chebyshev

CODE = "war"
NAME = "Warlock"
PAGES = {1: "Dark Arms", 2: "Blood Magic", 3: "Demonology"}
BLURB = "A blood knight: he pays for his sorcery with his own life and binds demons to his will."
TINT = "blood"

YELLOW = (255, 230, 90)
GREY = (170, 170, 170)
RED = (230, 80, 70)


def _lv(base, per):
    return lambda L: base + per * (L - 1)


# ------------------------------------------------------------------ tooltips
def _dmg_lines(env):
    from .skills import damage_lines
    return damage_lines(env)


def _life_line(env):
    c = env.mana()
    return ["Life Cost: %s" % (("%.1f" % c).rstrip("0").rstrip("."))] if c else []


def _mana_line(env):
    c = env.mana()
    return ["Mana Cost: %s" % (("%.1f" % c).rstrip("0").rstrip("."))] if c else []


def _melee_lines(env):
    x, L = env.s.extra, env.lvl
    out = []
    if x.get("dmg"):
        out.append("Damage: +%d percent" % (x["dmg"][0] + x["dmg"][1] * (L - 1)))
    if x.get("ar"):
        out.append("Attack Rating: +%d percent" % (x["ar"][0] + x["ar"][1] * (L - 1)))
    if x.get("leech"):
        out.append("Life stolen: %d percent of the damage" % (x["leech"][0] + x["leech"][1] * (L - 1)))
    if x.get("self_damage"):
        out.append("Costs you %d percent of the damage dealt as life" % x["self_damage"])
    if x.get("execute"):
        out.append("+%d percent damage against enemies below half life" % x["execute"])
    out.append("Uses your weapon damage")
    return out


def _demon_lines(env):
    x, L = env.s.extra, env.lvl
    out = []
    if x.get("greater"):
        out.append("A greater demon: only one can serve you at a time")
    else:
        out.append("Demons: %d" % x["max"](L))
    out.append("Life: +%d percent" % x["life"](L))
    out.append("Damage: +%d percent" % x["dmg"](L))
    if x.get("leech"):
        out.append("Steals %d percent of its damage as life" % x["leech"])
    return out + _mana_line(env)


def _stat_lines(env, prefix, n):
    names = {"passive_mastery_melee_dmg": "Damage: +%d percent", "passive_mastery_melee_th": "Attack Rating: +%d percent",
             "passive_mastery_melee_crit": "Critical strike: %d percent", "lifedrainmindam": "Life stolen per hit: %d percent",
             "passive_critical_strike": "Critical strike: %d percent", "damagepercent": "Damage: +%d percent",
             "item_tohit_percent": "Attack Rating: +%d percent", "item_armor_percent": "Defense: +%d percent"}
    return [names[st] % v for st, v in env.stats(prefix, n) if st in names]


def _buff_lines(env):
    from .skills import turns_from_frames
    return _stat_lines(env, "aurastat", 6) + ["Lasts %d turns" % (turns_from_frames(env.duration_frames()) or 10)] + _mana_line(env)


# ------------------------------------------------------------------ the thirty skills
# slot: the Necromancer skill whose place (tab, row, column, level, arrows) it takes
# base: the D2 skill whose row it starts from (numbers, missiles, sounds)   icon: D2 skill whose icon it wears
SKILLS = [
    # ---- Dark Arms (the Curses tab's places)
    dict(name="Blood Strike", slot="Amplify Damage", icon="Bash", sound="Bash",
         row=dict(range="h2h", mana="0"),
         extra=dict(kind="melee", weapon=True, dmg=(60, 10), ar=(20, 7), self_damage=6),
         short="a savage blow paid for in blood",
         long="A savage blow that costs you a little of your own life.", lines=_melee_lines),
    dict(name="Dark Blade", slot="Dim Vision", icon="Sword Mastery",
         row=dict(passive="1", passivestat1="passive_mastery_melee_dmg", passivecalc1="20+(lvl-1)*4",
                  passivestat2="passive_mastery_melee_th", passivecalc2="20+(lvl-1)*6",
                  passivestat3="passive_mastery_melee_crit", passivecalc3="3+lvl/2"),
         extra=dict(kind="passive"),
         short="mastery of every melee weapon",
         long="Passive - improves your damage, attack rating and critical strikes with any melee weapon.",
         lines=lambda env: _stat_lines(env, "passivestat", 5)),
    dict(name="Siphon Strike", slot="Weaken", icon="Cobra Strike", sound="Cobra Strike",
         row=dict(range="h2h", mana="2"),
         extra=dict(kind="melee", weapon=True, dmg=(20, 4), ar=(15, 5), leech=(15, 2)),
         short="a strike that drinks the enemy's life",
         long="A strike that returns part of the damage dealt to you as life.",
         lines=lambda env: _melee_lines(env) + _mana_line(env)),
    dict(name="Cleave", slot="Iron Maiden", icon="Double Swing", sound="Double Swing",
         row=dict(range="h2h", mana="3"),
         extra=dict(kind="melee", weapon=True, sweep=True, dmg=(0, 6), ar=(10, 5)),
         short="one sweep through every enemy next to you",
         long="A wide sweep that strikes every enemy standing next to you.",
         lines=lambda env: _melee_lines(env) + _mana_line(env)),
    dict(name="Hellforged", slot="Terror", icon="Iron Skin", sound="Shout",
         row=dict(aurastat1="item_armor_percent", aurastatcalc1="50+(lvl-1)*10", auralencalc="(12+lvl)*25",
                  mana="6", manashift="8", aurastate="shout"),
         extra=dict(kind="buff"),
         short="your armour hardens like demon hide",
         long="Hardens your armour with hellfire for a time, greatly raising your defense.", lines=_buff_lines),
    dict(name="Shadow Charge", slot="Confuse", icon="Charge", sound="Charge",
         row=dict(range="h2h", mana="6"),
         extra=dict(kind="charge", weapon=True, dmg=(80, 12), ar=(40, 10)),
         short="rush an enemy and strike",
         long="Rush up to 8 cells to an enemy and strike it, knocking it back.",
         lines=lambda env: _melee_lines(env) + _mana_line(env)),
    dict(name="Blood Thirst", slot="Life Tap", icon="Hunger",
         row=dict(passive="1", passivestat1="lifedrainmindam", passivecalc1="3+lvl/2",
                  passivestat2="passive_critical_strike", passivecalc2="4+lvl"),
         extra=dict(kind="passive"),
         short="every hit feeds you",
         long="Passive - your weapon hits steal life, and you strike critically more often.",
         lines=lambda env: _stat_lines(env, "passivestat", 5)),
    dict(name="Execute", slot="Attract", icon="Berserk", sound="Berserk",
         row=dict(range="h2h", mana="4"),
         extra=dict(kind="melee", weapon=True, dmg=(100, 15), ar=(30, 8), execute=100),
         short="a killing blow for the wounded",
         long="A heavy blow that is twice as deadly against enemies below half life.",
         lines=lambda env: _melee_lines(env) + _mana_line(env)),
    dict(name="Bloodlust", slot="Decrepify", icon="Frenzy", sound="Battle Orders",
         row=dict(aurastat1="damagepercent", aurastatcalc1="40+(lvl-1)*6", aurastat2="item_tohit_percent",
                  aurastatcalc2="40+(lvl-1)*8", auralencalc="(12+lvl/2)*25", mana="8", manashift="8",
                  aurastate="battleorders"),
         extra=dict(kind="buff"),
         short="fury that sharpens every blow",
         long="A blood frenzy: for a time you hit much harder and more surely.", lines=_buff_lines),
    dict(name="Dark Tempest", slot="Lower Resist", icon="Whirlwind", sound="Whirlwind",
         row=dict(range="h2h", mana="12"),
         extra=dict(kind="melee_nova", weapon=True, radius=2, dmg=(30, 8), ar=(30, 8), leech=(10, 1)),
         short="a whirl of steel around you",
         long="Strike every enemy within 2 cells of you at once, drinking life from each hit.",
         lines=lambda env: ["Radius: 2 cells"] + _melee_lines(env) + _mana_line(env)),
    # ---- Blood Magic (the Poison and Bone tab's places): paid in life, magic damage
    dict(name="Blood Bolt", slot="Teeth", base="Fire Bolt", icon="Fire Bolt", sound="Teeth", scale=110, tint=True,
         row=dict(etype="mag", mana="8", lvlmana="1", manashift="7", minmana="0"),
         extra=dict(kind="missile", life_cost=True),
         short="a bolt of your own blood",
         long="Hurls a bolt of your own blood. Blood magic is paid for in life, not mana.",
         lines=lambda env: _dmg_lines(env) + _life_line(env)),
    dict(name="Blood Ward", slot="Bone Armor", base="Bone Armor", icon="Bone Armor", sound="Bone Armor",
         row=dict(),
         extra=dict(kind="buff", life_cost=True, absorb=True),
         short="a shell of blood that soaks up blows",
         long="A shell of hardened blood that absorbs damage until it breaks.",
         lines=lambda env: ["Absorbs %d damage" % max(10, env.calc("calc1") or env.ln(1, 2))] + _life_line(env)),
    dict(name="Drain Life", slot="Poison Dagger", base="Ice Blast", icon="Life Tap", sound="Life Tap", scale=60,
         row=dict(etype="mag", elen="0", mana="10", lvlmana="1", manashift="7", minmana="0"),
         extra=dict(kind="drain", life_cost=True, heal=50),
         short="tear the life out of an enemy",
         long="Tears the life out of one enemy and gives part of it to you.",
         lines=lambda env: _dmg_lines(env) + ["Heals you for 50 percent of the damage"] + _life_line(env)),
    dict(name="Consume Corpse", slot="Corpse Explosion", icon="Corpse Explosion", sound="Corpse Explosion",
         row=dict(mana="0"),
         extra=dict(kind="consume", heal=_lv(20, 2), mana=_lv(10, 1)),
         short="feed on the dead",
         long="Devour a corpse to restore your life and mana.",
         lines=lambda env: ["Restores %d percent of your life" % env.s.extra["heal"](env.lvl),
                            "Restores %d percent of your mana" % env.s.extra["mana"](env.lvl)]),
    dict(name="Boiling Blood", slot="Bone Wall", base="Eruption", icon="Poison Explosion", sound="Poison Explosion",
         scale=80, tint=True, missile="firewall",
         row=dict(etype="mag", mana="16", lvlmana="2", manashift="7", minmana="0"),
         extra=dict(kind="area", radius=2, linger=2, life_cost=True),
         short="the ground itself bleeds and burns",
         long="A pool of boiling blood wells up from the ground and scalds whatever stands in it.",
         lines=lambda env: _dmg_lines(env) + ["Radius: 2 cells, lingers 2 turns"] + _life_line(env)),
    dict(name="Blood Nova", slot="Poison Explosion", base="Nova", icon="Poison Nova", sound="Poison Nova",
         scale=100, tint=True,
         row=dict(etype="mag", mana="24", lvlmana="2", manashift="7", minmana="0"),
         extra=dict(kind="nova", life_cost=True, radius=5),
         short="a ring of blood bursts from you",
         long="A ring of blood bursts out of you in every direction.",
         lines=lambda env: _dmg_lines(env) + _life_line(env)),
    dict(name="Blood Lance", slot="Bone Spear", base="Bone Spear", icon="Bone Spear", sound="Bone Spear", tint=True,
         row=dict(),
         extra=dict(kind="missile", pierce=True, life_cost=True),
         short="a lance of blood that runs enemies through",
         long="A lance of blood that passes through every enemy in its way.",
         lines=lambda env: _dmg_lines(env) + _life_line(env)),
    dict(name="Transfusion", slot="Bone Prison", icon="Prayer", sound="Prayer",
         row=dict(mana="30", lvlmana="4", manashift="7", minmana="0"),
         extra=dict(kind="transfuse", life_cost=True, radius=5, heal=_lv(28, 8)),
         short="your blood heals your companions",
         long="Give your own blood to heal every companion and minion near you.",
         lines=lambda env: ["Heals allies within 5 cells: %d life" % env.s.extra["heal"](env.lvl)] + _life_line(env)),
    dict(name="Blood Storm", slot="Poison Nova", base="Blizzard", icon="Blizzard", sound="Blizzard", scale=85,
         tint=True, missile="blizzard1",
         row=dict(etype="mag", elen="0"),
         extra=dict(kind="area", radius=3, linger=2, life_cost=True),
         short="a rain of blood shards",
         long="Shards of frozen blood rain down on an area and keep falling.",
         lines=lambda env: _dmg_lines(env) + ["Radius: 3 cells, lingers 2 turns"] + _life_line(env)),
    dict(name="Soul Rend", slot="Bone Spirit", base="Bone Spirit", icon="Bone Spirit", sound="Bone Spirit", tint=True,
         row=dict(),
         extra=dict(kind="missile", always_hit=True, life_cost=True),
         short="a hungry spirit that never misses",
         long="A blood spirit that hunts its target down and cannot miss.",
         lines=lambda env: _dmg_lines(env) + _life_line(env)),
    # ---- Demonology (the Summoning tab's places)
    dict(name="Demon Mastery", slot="Skeleton Mastery", icon="Skeleton Mastery",
         row=dict(passive="1"), extra=dict(kind="passive"),
         short="stronger demons",
         long="Passive - every demon you summon has more life and hits harder.",
         lines=lambda env: ["Demon life: +%d percent" % (4 * env.lvl), "Demon damage: +%d percent" % (4 * env.lvl)]),
    dict(name="Summon Imp", slot="Raise Skeleton", icon="Raise Skeleton", sound="Raise Skeleton",
         row=dict(mana="6", lvlmana="1", manashift="8"),
         extra=dict(kind="demon", monster="imp1", ranged=True, hp=0.5, hit=0.6, max=lambda L: min(6, 1 + L // 4),
                    life=_lv(0, 3), dmg=_lv(0, 4)),
         short="a fire-spitting imp",
         long="Summons an imp that spits fire at your enemies. More imps obey you as the skill grows.",
         lines=_demon_lines),
    dict(name="Death Mauler", slot="Clay Golem", icon="Summon Grizzly", sound="Clay Golem",
         row=dict(mana="12", lvlmana="2", manashift="8"),
         extra=dict(kind="demon", monster="deathmauler1", greater=True, hp=1.8, hit=0.9, life=_lv(20, 6), dmg=_lv(0, 5)),
         short="a hulking beast to hold the line",
         long="Summons a Death Mauler - a hulking beast that holds the front line for you.", lines=_demon_lines),
    dict(name="Dark Pact", slot="Golem Mastery", icon="Golem Mastery",
         row=dict(passive="1"), extra=dict(kind="passive"),
         short="demons that strike true",
         long="Passive - your demons hit more surely and are harder to hit.",
         lines=lambda env: ["Demon attack rating: +%d percent" % (10 * env.lvl), "Demon defense: +%d percent" % (10 * env.lvl)]),
    dict(name="Summon Succubus", slot="Raise Skeletal Mage", icon="Shadow Warrior", sound="Raise Skeletal Mage",
         row=dict(mana="8", lvlmana="1", manashift="8"),
         extra=dict(kind="demon", monster="succubus1", ranged=True, hp=0.7, hit=0.9, max=lambda L: min(4, 1 + L // 6),
                    life=_lv(0, 3), dmg=_lv(10, 4)),
         short="a winged temptress who strikes from afar",
         long="Summons a succubus that hurls blood stars from a distance.", lines=_demon_lines),
    dict(name="Blood Lord", slot="BloodGolem", icon="BloodGolem", sound="BloodGolem",
         row=dict(mana="20", lvlmana="3", manashift="8"),
         extra=dict(kind="demon", monster="bloodlord1", greater=True, hp=1.4, hit=1.3, life=_lv(20, 5), dmg=_lv(20, 6),
                    leech=25),
         short="a frenzied demon that feeds as it kills",
         long="Summons a Blood Lord - a frenzied demon that heals itself with every blow.", lines=_demon_lines),
    dict(name="Demon Skin", slot="Summon Resist", icon="Summon Resist",
         row=dict(passive="1"), extra=dict(kind="passive"),
         short="demons that shrug off the elements",
         long="Passive - your demons resist fire, cold, lightning and poison.",
         lines=lambda env: ["Demon resistances: +%d percent" % min(75, 18 + 3 * env.lvl)]),
    dict(name="Enslave", slot="IronGolem", icon="Conversion", sound="Attract",
         row=dict(mana="18", lvlmana="1", manashift="8", cltmissilea="curseattract"),
         extra=dict(kind="enslave", chance=lambda L: min(90, 40 + 3 * L), turns=lambda L: 3 + L // 4),
         short="break an enemy's will",
         long="Breaks the will of one enemy: it fights for you until its soul burns out. Bosses resist.",
         lines=lambda env: ["Chance: %d percent" % env.s.extra["chance"](env.lvl),
                            "Lasts %d turns" % env.s.extra["turns"](env.lvl)] + _mana_line(env)),
    dict(name="Pit Lord", slot="FireGolem", icon="FireGolem", sound="FireGolem",
         row=dict(mana="35", lvlmana="5", manashift="8"),
         extra=dict(kind="demon", monster="megademon1", greater=True, hp=2.2, hit=1.6, life=_lv(30, 5), dmg=_lv(40, 7)),
         short="a lord of the burning hells",
         long="Summons a Pit Lord - a towering demon of the Burning Hells.", lines=_demon_lines),
    dict(name="Demonic Sacrifice", slot="Revive", icon="Sacrifice", sound="Corpse Explosion",
         row=dict(mana="10", manashift="8"),
         extra=dict(kind="sacrifice", radius=3, blast=_lv(40, 4), heal=_lv(15, 1)),
         short="a demon dies so you may live",
         long="One of your demons explodes: its life burns the enemies around it and part of it heals you.",
         lines=lambda env: ["Enemies within 3 cells take %d percent of the demon's life" % env.s.extra["blast"](env.lvl),
                            "Heals you for %d percent of it" % env.s.extra["heal"](env.lvl)] + _mana_line(env)),
]
BY_NAME = {d["name"]: d for d in SKILLS}
SOUND_BASE = {d["name"]: d.get("sound") for d in SKILLS if d.get("sound")}
DEMON_SKILLS = {d["name"] for d in SKILLS if d["extra"].get("kind") == "demon"} | {"Enslave"}

_MISSILE_COLS = ("srvmissile", "cltmissile", "srvmissilea", "cltmissilea", "srvmissileb", "cltmissileb",
                 "srvmissilec", "cltmissilec", "cltmissiled")
_SCALE_COLS = ["emin", "emax", "mindam", "maxdam"] + ["eminlev%d" % i for i in range(1, 6)] + \
    ["emaxlev%d" % i for i in range(1, 6)] + ["minlevdam%d" % i for i in range(1, 6)] + \
    ["maxlevdam%d" % i for i in range(1, 6)]
# what a cloned D2 row must not carry over (it would make the engine treat the skill as the original)
_DROP_COLS = ("skilldesc", "summon", "pettype", "aura", "passive", "itypea1", "itypea2", "itypea3", "itypeb1",
              "itypeb2", "itypeb3", "etypea1", "etypea2", "etypeb1", "etypeb2", "reqskill1", "reqskill2", "reqskill3",
              "edmgsympercalc", "dmgsympercalc", "elensympercalc", "passiveitype", "restrict", "state1", "state2",
              "state3")


def build(rows, descs, trees, strings=None):
    """The Warlock's tree from D2's tables: {skill name: Skill}."""
    from .skills import Skill, CLASS_BY_CODE
    by = {r["skill"]: r for r in rows if r.get("skill")}
    nec = trees.get("nec") or {}
    if not nec:
        return {}
    slot_name = {d["slot"]: d["name"] for d in SKILLS}
    tree = {}
    for i, d in enumerate(SKILLS):
        slot = nec.get(d["slot"])
        if slot is None:
            continue
        base = by.get(d.get("base") or "")
        row = dict(base) if base else {}
        for c in _DROP_COLS:
            row.pop(c, None)
        if d.get("scale") and base:
            for c in _SCALE_COLS:
                v = row.get(c)
                try:
                    if v not in (None, ""):
                        row[c] = str(int(round(int(v) * d["scale"] / 100.0)))
                except ValueError:
                    pass
        if d.get("missile"):
            for c in ("srvmissilea", "cltmissilea"):
                row[c] = d["missile"]
        row.update(d.get("row") or {})
        if d.get("tint"):
            row["castoverlay"] = ""               # (the base skill's fire / frost flash would not match)
            for c in _MISSILE_COLS:
                if row.get(c) and "@" not in row[c]:
                    row[c] = "%s@%s" % (row[c], TINT)
        row["skill"] = d["name"]
        row["charclass"] = CODE
        row["reqlevel"] = str(slot.reqlevel)
        extra = dict(d["extra"])
        s = Skill(d["name"], slot.page, slot.row, slot.col, slot.reqlevel,
                  [slot_name[p] for p in slot.prereqs if p in slot_name], 0, 2 * i, extra["kind"])
        s.cls, s.data, s.desc = CODE, row, {}
        s.maxlvl = 20
        s.title, s.short, s.long = d["name"], d.get("short", ""), d.get("long", "")
        s.element = row.get("etype", "")
        s.itype = ()
        s.extra = extra
        s.weapon = bool(extra.get("weapon"))
        s.lines = d.get("lines")
        s.strings = strings
        # the icon: a D2 skill's, from its class's icon file (tinted by the HUD)
        src = by.get(d.get("icon") or "")
        if src is not None:
            dd = descs.get(src.get("skilldesc"), {})
            info = CLASS_BY_CODE.get(src.get("charclass") or "", None)
            try:
                s.icon_src = (info[3] if info else "", int(dd.get("iconcel") or 0))
            except ValueError:
                s.icon_src = None
        else:
            s.icon_src = None
        tree[d["name"]] = s
    return tree


def describe(book, s, lv):
    """Tooltip lines of a Warlock skill at a level."""
    from .skills import SkillEnv
    env = SkillEnv(book, s, lv)
    fn = getattr(s, "lines", None)
    try:
        return list(fn(env)) if fn else []
    except Exception:
        return []


# ------------------------------------------------------------------ how the new kinds of skill play
class WarlockCaster:
    """Mixed into World next to SkillCaster: the Warlock's own kinds of skill."""

    def life_cost(self, name):
        """Life a blood-magic skill costs right now (0 for everything else)."""
        p = self.player
        s = p.skills.tree.get(name) if getattr(p, "skills", None) else None
        if s is None or not s.extra.get("life_cost") or getattr(self, "_free_cast", False):
            return 0
        if p.skills.charged_only(name):
            return 0
        return int(round(self._skill_env(name).mana() + 0.49))

    # -- Drain Life
    def _k_drain(self, s, env, target, cell, ap, mana):
        p = self.player
        if target is None or not target.alive:
            self.log("Drain a monster.", GREY)
            return False
        if not self._in_range(target.pos):
            return False
        self._spend(ap, mana, target.pos, "cast")
        self._wake([target])
        hp0 = target.hp
        self.skill_damage(env, target)
        dealt = max(0, hp0 - max(0, target.hp))
        self.emit("projectile", p, target.pos, p.pos, "bone", "firebolt@blood")   # the blood streams back
        heal = dealt * s.extra.get("heal", 50) // 100
        if heal > 0 and p.alive:
            heal = min(heal, p.max_hp - p.hp)
            p.hp += heal
            if heal:
                self.emit("heal", p, heal)
        return True

    # -- Consume Corpse
    def _k_consume(self, s, env, target, cell, ap, mana):
        p = self.player
        corpse = None
        for c in self.corpses:
            if not getattr(c, "exploded", False) and (cell is None or chebyshev(c.pos, cell) <= 1) \
                    and self.udist(c, p) <= 8:
                corpse = c
                break
        if corpse is None:
            self.log("Target a corpse near you.", GREY)
            return False
        self._spend(ap, mana, corpse.pos, "cast")
        corpse.exploded = corpse.searched = True
        if corpse in self.corpses:
            self.corpses.remove(corpse)
        self.emit("explosion", corpse.pos, "corpseexplosion")
        heal = min(p.max_hp - p.hp, p.max_hp * s.extra["heal"](env.lvl) // 100)
        if heal > 0:
            p.hp += heal
            self.emit("heal", p, heal)
        p.mana = min(p.max_mana, p.mana + p.max_mana * s.extra["mana"](env.lvl) // 100)
        self.log("You feed on the corpse.", YELLOW)
        return True

    # -- Transfusion
    def _k_transfuse(self, s, env, target, cell, ap, mana):
        from . import tactics
        p = self.player
        r = s.extra.get("radius", 5)
        who = [h for h in tactics.living(self) if h is not p and self.udist(h, p) <= r]
        who += [a for a in self.allies() if not getattr(a, "party_member", False) and a.ai not in ("turret", "wall")
                and self.udist(a, p) <= r]
        who = [u for u in who if u.hp < u.max_hp]
        if not who:
            self.log("No wounded companion near you.", GREY)
            return False
        self._spend(ap, mana, None, "cast")
        amount = s.extra["heal"](env.lvl)
        for u in who:
            heal = min(amount, u.max_hp - u.hp)
            u.hp += heal
            self.emit("heal", u, heal)
        self.log("%s: %d healed." % (s.title, len(who)), YELLOW)
        return True

    # -- demons
    def _demons(self):
        return [a for a in self.allies() if getattr(a, "summon_skill", None) in DEMON_SKILLS]

    def _k_demon(self, s, env, target, cell, ap, mana):
        p = self.player
        x, L = s.extra, env.lvl
        if x.get("greater"):
            for a in self.allies():
                if getattr(a, "greater_demon", False) and getattr(a, "master", p) is p:
                    a.alive = False
                    self.emit("death", a)
        else:
            mine = [a for a in self._owned(s.key) if getattr(a, "master", p) is p]      # (each Warlock his own)
            while len(mine) >= x["max"](L):
                old = mine.pop(0)
                old.alive = False
                self.emit("death", old)
        self._spend(ap, mana, None, "cast")
        t = self._summon_template(x["monster"], max(1, p.level))
        a = self._spawn_ally(s, env, cell if cell is not None and chebyshev(cell, p.pos) <= 3 else p.pos, template=t)
        if a is None:
            self.log("No room to summon.", GREY)
            return False
        a.name = s.title if x.get("greater") else s.title.replace("Summon ", "")
        a.greater_demon = bool(x.get("greater"))
        a.master = p
        book = p.skills
        # a demon's strength comes from its master: his level, the skill, his masteries - and the
        # difficulty (D2's monster tables would make an imp useless and a Blood Lord a boss)
        cl = max(1, p.level)
        diff = getattr(getattr(self, "content", None), "difficulty", "normal")
        kh, kd = {"nightmare": (1.5, 1.3), "hell": (2.2, 1.7)}.get(diff, (1.0, 1.0))
        base_hp = (20 + 9 * cl) * x.get("hp", 1.0) * kh
        lo, hi = (2 + 0.55 * cl) * x.get("hit", 1.0) * kd, (4 + 1.0 * cl) * x.get("hit", 1.0) * kd
        life = x["life"](L) + 4 * book.level("Demon Mastery")
        dmg = x["dmg"](L) + 4 * book.level("Demon Mastery")
        a.max_hp = a.hp = max(1, int(base_hp * (100 + life) / 100))
        a.dmg = (max(1, int(lo * (100 + dmg) / 100)), max(2, int(hi * (100 + dmg) / 100)))
        pact = book.level("Dark Pact")
        if pact:
            a.ar = a.ar * (100 + 10 * pact) // 100
            a.defense = a.defense * (100 + 10 * pact) // 100
        skin = book.level("Demon Skin")
        if skin:
            res = dict(getattr(a, "res", {}) or {})
            for et in ("fire", "cold", "ltng", "pois"):
                res[et] = min(75, max(res.get(et, 0), 0) + min(75, 18 + 3 * skin))
            a.res = res
        if x.get("leech"):
            a.leech = x["leech"]
        if x.get("ranged"):
            a.range = max(getattr(a, "range", 1), 6)
            a.ai = "ally_ranged"
        self.log("%s answers your call." % a.name, YELLOW)
        return True

    # -- Enslave
    def _k_enslave(self, s, env, target, cell, ap, mana):
        if target is None or not target.alive or getattr(target, "ally", False):
            self.log("Enslave a monster.", GREY)
            return False
        if not self._in_range(target.pos):
            return False
        self._spend(ap, mana, target.pos, "cast")
        self.emit("explosion", target.pos, "curseattract")
        self._wake([target])
        boss = target.unique or getattr(target, "boss", False) or getattr(target, "champion", False)
        if boss or self.rng.randrange(100) >= s.extra["chance"](env.lvl):
            self.log("%s resists your will." % target.name, GREY)
            return True
        self._make_ally(target, s.extra["turns"](env.lvl))
        target.summon_skill = "Enslave"
        target.greater_demon = False
        self.log("%s is enslaved!" % target.name, YELLOW)
        return True

    # -- Demonic Sacrifice
    def _k_sacrifice(self, s, env, target, cell, ap, mana):
        p = self.player
        mine = self._demons()
        if cell is not None:
            mine.sort(key=lambda a: chebyshev(a.pos, cell))
        if not mine or (cell is not None and chebyshev(mine[0].pos, cell) > 2):
            self.log("Target one of your demons.", GREY)
            return False
        a = mine[0]
        if not self._in_range(a.pos, los=False):
            return False
        self._spend(ap, mana, a.pos, "cast")
        r = s.extra.get("radius", 3)
        pool = a.max_hp
        a.alive = False
        self.emit("death", a)
        self.emit("explosion", a.pos, "corpseexplosion")
        self.emit("explosion", a.pos, "explodingarrowexp@%s" % TINT)
        foes = [m for m in self.enemies() if self.udist(m, a) <= r]
        self._wake(foes)
        dmg = pool * s.extra["blast"](env.lvl) // 100
        for m in foes:
            half = dmg // 2
            self.phys_hit(m, half, half, p)
            self.elem_hit(m, "fire", dmg - half, dmg - half, p, show=False)
        heal = min(p.max_hp - p.hp, pool * s.extra["heal"](env.lvl) // 100)
        if heal > 0:
            p.hp += heal
            self.emit("heal", p, heal)
        self.log("%s is sacrificed: %d enem%s burned." % (a.name, len(foes), "y" if len(foes) == 1 else "ies"), YELLOW)
        return True

    # -- Dark Tempest
    def _k_melee_nova(self, s, env, target, cell, ap, mana):
        p = self.player
        r = s.extra.get("radius", 2)
        foes = [m for m in self.enemies() if self.udist(m, p) <= r]
        if not foes:
            self.log("No enemy within reach.", GREY)
            return False
        self._spend(ap, mana, foes[0].pos, "attack")
        self.emit("nova", p, p.pos, r, "fire", None)
        self._wake(foes)
        for m in foes:
            if not m.alive:
                continue
            hp0 = m.hp
            if self._resolve_attack(p, m, s.key, quiet_anim=True):
                self.after_melee_hit(p, m, s.key, max(0, hp0 - max(0, m.hp)))
        return True
