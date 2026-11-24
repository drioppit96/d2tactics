"""Each hero's own combat brain: what to do next, decided from his build, gear and the fight.

Every time a hero is free to act, his brain looks at every skill he can use right now and gives
each one a score, then does the best one (or a normal attack, or a step away, or a potion).

    damage skills   expected damage per second: the skill's own numbers (game/skills.py SkillEnv,
                    with synergies and D2R changes), times the monsters it would reach (the
                    pack around the target for areas and novas, the ones on the line for lines),
                    times what their resistances let through (immune = 0), divided by the time
                    the cast or swing takes (FCR / IAS breakpoints, autobattler/timing.py)
    weapon skills   the weapon's damage with the skill's bonus, times the chance to hit
    curses          worth casting on a pack of three or more, or on a boss, that isn't cursed yet
    auras           the best one is switched on: a defensive one while life is low
    buffs, warcries kept up: cast again when they run out
    summons         cast while there are fewer than the skill allows (the engine says no when full)

Mana: a skill that would leave the hero below his profile's reserve scores much lower, so heroes
keep enough for a heal-up or an escape instead of running dry.

Each hero has a profile (saved with him, in mode_state["autobattler"]):

    style           balanced | aggressive | careful
                      aggressive: drinks later, never backs off, spends mana freely
                      careful: drinks earlier, ranged heroes keep their distance, bigger reserve
    potion_at       life %% below which he drinks
    mana_reserve    mana %% he tries to keep
    keep_distance   auto (ranged heroes and casters back off from melee monsters) | yes | no
    favourite       a skill he prefers when it is close to the best (+25%%)
    never           skills he doesn't use
    auto_points     spend skill and stat points by his class build plan (BUILDS, STATS); off by
                    default: the player spends them on the Character screen

The class build plans are only what a new hero learns by default; any skill he has points in is
used, whatever the plan.
"""
from game.grid import chebyshev

from . import timing

# frames per cast at 0% FCR (human form): the class base for the cast formula
CAST_FRAMES0 = {"ama": 19, "ass": 16, "bar": 13, "dru": 18, "nec": 15, "pal": 15, "sor": 13}

STYLES = {
    "balanced": dict(potion_at=45, mana_reserve=15, back_off_at=70),
    "aggressive": dict(potion_at=30, mana_reserve=5, back_off_at=0),
    "careful": dict(potion_at=60, mana_reserve=25, back_off_at=95),
}
DEFAULT_PROFILE = dict(style="balanced", potion_at=None, mana_reserve=None, keep_distance="auto",
                       favourite="", never=[], auto_points=False)
THROW_RANGE = 14

#: how a build fights (Brain.role): how far he keeps from melee monsters, in cells
ROLE_DISTANCE = {"melee": 0, "ranged": 5, "thrower": 4, "caster": 5, "summoner": 6}
ROLE_NAMES = {"melee": "Melee", "ranged": "Bow / crossbow", "thrower": "Thrower",
              "caster": "Caster", "summoner": "Summoner"}

DAMAGE_KINDS = ("missile", "nova", "area", "line", "chain", "charge", "spiral", "corpse_blast", "melee", "attack")
SUMMON_KINDS = ("summon", "golem", "raise", "revive", "turret", "wall")
SPELL_RANGE = 14            # cells: how far a hero casts a targeted spell
DEFENSIVE_AURAS = ("Prayer", "Defiance", "Cleansing", "Meditation", "Redemption", "Salvation",
                   "Resist Fire", "Resist Cold", "Resist Lightning", "Vigor")

# What a new hero of each class learns, in order: (skill title, level to reach). Prerequisites
# are learned on the way. "@mastery" is the Barbarian mastery for the weapon he holds.
BUILDS = {
    "sor": [("Frozen Armor", 1), ("Ice Bolt", 1), ("Ice Blast", 6), ("Frost Nova", 1), ("Static Field", 1),
            ("Ice Blast", 20), ("Glacial Spike", 5), ("Blizzard", 20), ("Cold Mastery", 10),
            ("Frozen Orb", 20), ("Glacial Spike", 20), ("Cold Mastery", 20)],
    "nec": [("Teeth", 1), ("Amplify Damage", 1), ("Bone Armor", 1), ("Teeth", 6), ("Corpse Explosion", 1),
            ("Bone Spear", 20), ("Bone Wall", 1), ("Bone Prison", 1), ("Bone Spirit", 20), ("Teeth", 20),
            ("Bone Armor", 10)],
    "pal": [("Might", 1), ("Holy Bolt", 1), ("Blessed Hammer", 7), ("Prayer", 1), ("Blessed Aim", 1),
            ("Concentration", 1), ("Blessed Hammer", 20), ("Holy Shield", 1), ("Concentration", 20),
            ("Vigor", 20), ("Blessed Aim", 20)],
    "bar": [("Bash", 1), ("Howl", 1), ("Double Swing", 1), ("Shout", 1), ("@mastery", 4), ("Frenzy", 10),
            ("Battle Orders", 5), ("Frenzy", 20), ("Battle Command", 1), ("@mastery", 20),
            ("Battle Orders", 20), ("Double Swing", 20)],
    "ama": [("Jab", 1), ("Inner Sight", 1), ("Power Strike", 6), ("Poison Javelin", 1), ("Dodge", 1),
            ("Lightning Bolt", 1), ("Charged Strike", 10), ("Lightning Fury", 20), ("Charged Strike", 20),
            ("Power Strike", 20), ("Valkyrie", 1), ("Lightning Bolt", 20)],
    "dru": [("Firestorm", 1), ("Raven", 1), ("Molten Boulder", 1), ("Firestorm", 6), ("Oak Sage", 1),
            ("Fissure", 10), ("Summon Spirit Wolf", 1), ("Volcano", 1), ("Fissure", 20), ("Armageddon", 20),
            ("Molten Boulder", 20)],
    "ass": [("Fire Blast", 1), ("Burst of Speed", 1), ("Shock Web", 1), ("Fire Blast", 6),
            ("Charged Bolt Sentry", 1), ("Lightning Sentry", 10), ("Fade", 1), ("Lightning Sentry", 20),
            ("Death Sentry", 10), ("Shock Web", 20), ("Death Sentry", 20), ("Shadow Warrior", 1)],
}
# stat points per level (5): (str, dex, vit, energy), with caps for strength and dexterity
STATS = {
    "sor": ((1, 0, 4, 0), 60, 50), "nec": ((1, 0, 4, 0), 60, 50), "dru": ((1, 0, 4, 0), 70, 50),
    "pal": ((2, 1, 2, 0), 110, 80), "bar": ((2, 1, 2, 0), 120, 80), "ama": ((1, 2, 2, 0), 90, 130),
    "ass": ((1, 1, 3, 0), 80, 80),
}
MASTERY = {"swor": "Sword Mastery", "knif": "Sword Mastery", "axe": "Axe Mastery", "mace": "Mace Mastery",
           "hamm": "Mace Mastery", "club": "Mace Mastery", "scep": "Mace Mastery", "pole": "Pole Arm Mastery",
           "spea": "Spear Mastery", "jave": "Throwing Mastery", "taxe": "Throwing Mastery"}


# ------------------------------------------------------------------ the hero's profile
def profile(hero):
    ms = getattr(hero, "mode_state", None)
    if not isinstance(ms, dict):
        ms = {}
        hero.mode_state = ms
    prof = ms.setdefault("autobattler", {})
    for k, v in DEFAULT_PROFILE.items():
        prof.setdefault(k, list(v) if isinstance(v, list) else v)
    if prof["style"] not in STYLES:
        prof["style"] = "balanced"
    if not prof.get("points_by_hand_v1"):
        # points are the player's now (Character screen); heroes from before switch over once
        prof["points_by_hand_v1"] = True
        prof["auto_points"] = False
    return prof


def setting(hero, key):
    prof = profile(hero)
    v = prof.get(key)
    return STYLES[prof["style"]].get(key) if v is None else v


def cycle_style(hero):
    prof = profile(hero)
    names = list(STYLES)
    prof["style"] = names[(names.index(prof["style"]) + 1) % len(names)]
    return prof["style"]


# ------------------------------------------------------------------ what he picks up
# Each rule is on or off per hero (the Pickup screen). "words": anything whose name contains one of
# these (comma separated) is picked up whatever the other rules say.
PICKUP_RULES = [("gold", "Gold", True), ("potions", "Potions (while the belt has room)", True),
                ("runes", "Runes", True), ("gems", "Gems", True), ("charms", "Charms", True),
                ("jewelry", "Rings, amulets, jewels", True), ("unique", "Unique items", True),
                ("set", "Set items", True), ("rare", "Rare and crafted items", True),
                ("magic", "Magic items", False), ("sockets", "Plain items with sockets", True),
                ("normal", "Plain items", False), ("other", "Everything else (scrolls, keys ...)", False)]


def pickup_rules(hero):
    prof = profile(hero)
    r = prof.setdefault("pickup", {})
    for k, _t, default in PICKUP_RULES:
        r.setdefault(k, default)
    r.setdefault("words", "")
    return r


def item_tags(it):
    """What kind of thing an item is, for the pickup rules and the loot window's filters."""
    tags = set()
    kind = getattr(it, "kind", "")
    if kind == "gold":
        return {"gold"}
    if kind == "potion":
        return {"potions"}
    gem = getattr(it, "gem", None)
    if gem:
        tags.add("runes" if gem[0] == "rune" else "gems")
    if getattr(it, "charm", False):
        tags.add("charms")
    slot = str(getattr(it, "slot", "") or "").lower()
    b = getattr(it, "base", None)
    btype = str(b.get("type", "")).lower() if isinstance(b, dict) else ""
    if slot in ("ring", "amulet", "rring", "lring", "neck") or btype in ("ring", "amul", "jewl"):
        tags.add("jewelry")
    rar = str(getattr(it, "rarity", "") or "normal").lower()
    if rar in ("unique", "set", "rare", "magic"):
        tags.add(rar)
    elif rar == "crafted":
        tags.add("rare")
    elif kind == "equip" and not tags:
        tags.add("sockets" if int(getattr(it, "sockets", 0) or 0) > 0 else "normal")
    if not tags:
        tags.add("other")
    return tags


def wants(hero, it):
    r = pickup_rules(hero)
    name = str(getattr(it, "shown_name", None) or getattr(it, "name", "") or "").lower()
    for w in (r.get("words") or "").split(","):
        w = w.strip().lower()
        if w and w in name:
            return True
    tags = item_tags(it)
    if "potions" in tags and getattr(it, "potion", "") in ("heal", "mana", "rejuv"):
        # healing, mana and rejuvenation potions: always, while his belt has a place for that
        # kind (healing in columns 1-2, mana in 3-4); with the belt full, by his rules
        try:
            from game import potions
            if potions._free_column(hero, it) is not None:
                return True
        except Exception:
            pass
    if "potions" in tags:
        if not r.get("potions"):
            return False
        try:
            from game import potions
            return bool(potions.has_room(hero, it))
        except Exception:
            return len(getattr(hero, "belt", []) or []) < 8
    return any(r.get(t) for t in tags)


# ------------------------------------------------------------------ spending points
def _mastery_for(hero):
    w = (getattr(hero, "equipment", None) or {}).get("rhand")
    b = getattr(w, "base", None)
    anc = set(b.get("ancestors", ())) if isinstance(b, dict) else set()
    for t, name in MASTERY.items():
        if t in anc:
            return name
    return "Sword Mastery"


def _learn_chain(book, key, clvl, depth=0):
    """Learn `key` once, learning any missing prerequisite first. -> True if a point was spent."""
    s = book.tree.get(key)
    if s is None or depth > 8 or book.points <= 0:
        return False
    for pre in s.prereqs:
        if pre in book.tree and book.levels.get(pre, 0) <= 0:
            return _learn_chain(book, pre, clvl, depth + 1)
    return book.learn(key, clvl)


def spend_points(hero):
    """Skill points by the class build plan, stat points by the class stat plan."""
    if not profile(hero).get("auto_points", False):
        return                              # the player spends them (Character screen)
    book = getattr(hero, "skills", None)
    clvl = getattr(hero, "level", 1)
    changed = False
    if book is not None:
        plan = BUILDS.get(getattr(hero, "cls", ""), [])
        guard = 0
        while book.points > 0 and guard < 200:
            guard += 1
            spent = False
            for title, want in plan:
                if title == "@mastery":
                    title = _mastery_for(hero)
                s = book.find(title)
                if s is None or book.levels.get(s.key, 0) >= min(want, s.maxlvl):
                    continue
                if _learn_chain(book, s.key, clvl):
                    spent = changed = True
                    break
            if not spent:
                break                       # nothing in the plan can take a point yet: keep it
    pts = int(getattr(hero, "stat_points", 0) or 0)
    if pts > 0:
        (s_, d_, v_, e_), cap_s, cap_d = STATS.get(getattr(hero, "cls", ""), ((1, 1, 3, 0), 80, 60))
        order = ["str"] * s_ + ["dex"] * d_ + ["vit"] * v_ + ["eng"] * e_
        i = 0
        while pts > 0 and i < 10000:
            k = order[i % len(order)]
            i += 1
            if k == "str" and hero.base_str >= cap_s:
                k = "vit"
            if k == "dex" and hero.base_dex >= cap_d:
                k = "vit"
            attr = {"str": "base_str", "dex": "base_dex", "vit": "base_vit", "eng": "base_eng"}[k]
            setattr(hero, attr, getattr(hero, attr) + 1)
            pts -= 1
        hero.stat_points = 0
        changed = True
    if changed:
        try:
            hero.recalc()
        except Exception:
            pass


# ------------------------------------------------------------------ deciding
class Plan:
    __slots__ = ("what", "skill", "target", "cell", "frames", "score", "why")

    def __init__(self, what, skill=None, target=None, cell=None, frames=0, score=0.0, why=""):
        self.what, self.skill, self.target, self.cell = what, skill, target, cell
        self.frames, self.score, self.why = frames, score, why


class Brain:
    def __init__(self, hero, sim):
        self.h = hero
        self.sim = sim
        self.w = sim.w
        self.cool = {}               # skill -> frame it can be used again (D2 casting delay, failures)
        self.rebuff = {}             # buff / warcry / aura -> frame to renew it
        self.last = ""               # what he decided last (shown on the watch screen)
        self._info = {}              # skill -> its numbers, worked out again every 10 seconds

    # ------------------------------------------------------------ helpers
    def _book(self):
        return getattr(self.h, "skills", None)

    def foes_near(self, cell, r, foes):
        return [m for m in foes if chebyshev(m.pos, cell) <= r]

    def res_factor(self, m, element):
        if not element:
            return 1.0
        res = (getattr(m, "res", None) or {}).get({"fire": "fire", "cold": "cold", "ltng": "ltng", "light": "ltng",
                                                  "pois": "pois", "mag": "mag"}.get(element, element), 0) or 0
        if res >= 100:
            try:
                from game import d2r
                if d2r.sundered(self.h, element):
                    res = d2r.SUNDER_RES
            except Exception:
                pass
        return max(0.0, (100 - min(100, res)) / 100.0)

    def cast_frames(self, skill):
        """Frames this skill takes: the attack formula for skills that swing, the cast one for spells."""
        d = getattr(skill, "data", None) or {}
        anim = (d.get("anim") or "").upper()
        if skill.kind in ("attack", "melee") or getattr(skill, "weapon", False) or anim in ("A1", "A2", "TH", "KK", "S1", "S2", "S3", "S4"):
            return self.attack_frames(anim if anim and anim != "SC" else "A1")
        f0 = CAST_FRAMES0.get(getattr(self.h, "cls", ""), 15)
        fcr = self.h.mod("fcr") if hasattr(self.h, "mod") else 0
        return timing.cast_frames(f0 + 1, fcr)

    def attack_frames(self, mode="A1"):
        fpd, speed = self.sim.t.fpd(self.h, mode)
        ias = self.h.mod("ias") if hasattr(self.h, "mod") else 0
        return timing.attack_frames(fpd, ias, self.sim._wsm(self.h), 0, speed)

    def weapon_avg(self):
        lo, hi = getattr(self.h, "dmg", (1, 2))
        avg = (lo + hi) / 2.0
        for _, (elo, ehi) in (getattr(self.h, "elem", None) or {}).items():
            avg += (elo + ehi) / 2.0
        return avg

    def hit_chance(self, m):
        try:
            from game.world import hit_chance
            return hit_chance(self.h, m)
        except Exception:
            return 0.75

    def role(self):
        """What his build is, from what he holds and where his skill points are:
            ranged     a bow or crossbow in hand
            thrower    a javelin, throwing knife or axe in hand (Throw comes first)
            summoner   a third or more of his points in summons
            caster     more points in damage spells than in weapon skills
            melee      everything else
        Worked out again when his level, weapon or skills change."""
        h = self.h
        book = self._book()
        wpn = (getattr(h, "equipment", None) or {}).get("weapon")
        key = (getattr(h, "level", 1), id(wpn), tuple(sorted((book.levels or {}).items())) if book else ())
        if getattr(self, "_role_key", None) == key:
            return self._role
        if getattr(h, "ranged", False):
            role = "ranged"
        elif getattr(h, "throwing", False):
            role = "thrower"
        else:
            summon = spell = weapon = total = 0
            for name, lv in ((book.levels or {}).items() if book else ()):
                sk = book.tree.get(name)
                if sk is None or not lv:
                    continue
                total += lv
                if sk.kind in SUMMON_KINDS:
                    summon += lv
                elif getattr(sk, "weapon", False) or sk.kind in ("attack", "melee"):
                    weapon += lv
                elif sk.kind in DAMAGE_KINDS:
                    spell += lv
            if summon >= max(3, total / 3.0):
                role = "summoner"
            elif spell > weapon and spell >= 2:
                role = "caster"
            else:
                role = "melee"
        self._role_key, self._role = key, role
        return role

    def keep_distance(self):
        """Cells he keeps from melee monsters (0: he goes in). The profile's keep_distance can
        force it on or off."""
        ks = profile(self.h).get("keep_distance", "auto")
        if ks == "no":
            return 0
        d = ROLE_DISTANCE.get(self.role(), 0)
        return d or (4 if ks == "yes" else 0)

    def ranged_hero(self, best_reach):
        ks = profile(self.h).get("keep_distance", "auto")
        if ks == "yes":
            return True
        if ks == "no":
            return False
        return best_reach > 3 or getattr(self.h, "ranged", False)

    # ------------------------------------------------------------ the decision
    def decide(self, target, foes):
        """-> a Plan. `target` is the monster the hero is busy with (may be None), `foes` every
        awake monster on the floor."""
        h, sim = self.h, self.sim
        frame = sim.frame
        book = self._book()
        mana_left_pct = 100.0 * h.mana / max(1, getattr(h, "max_mana", 1))
        reserve = setting(h, "mana_reserve")
        never = set(profile(h).get("never") or [])
        fav = profile(h).get("favourite") or ""
        near = [m for m in foes if chebyshev(m.pos, h.pos) <= SPELL_RANGE]
        boss = next((m for m in near if getattr(m, "rift_boss", False) or getattr(m, "unique", False)), None)
        plans = []

        # the normal attack: the baseline every skill has to beat
        if target is not None:
            frames = self.attack_frames("A1")
            hit = self.weapon_avg() * self.hit_chance(target) * self.res_factor(target, "phys")
            dps = hit * timing.FPS / max(1, frames)
            if target.hp <= hit * 1.2:
                dps *= 3.0                    # it dies to one blow: no mana spent on it
            if getattr(h, "throwing", False) and frame >= self.cool.get("throw", 0):
                # a javelin, knife or axe in hand: Throw is his main attack, from a distance
                far = chebyshev(target.pos, h.pos) >= 2
                plans.append(Plan("skill", "throw", target, None, frames, dps * (1.6 if far else 1.2), "throw"))
                dps *= 0.8
            plans.append(Plan("attack", None, target, None, frames, dps, "attack"))

        if book is not None:
            for name in book.actives():
                if name in never or frame < self.cool.get(name, 0):
                    continue
                s = book.tree.get(name)
                if s is None or s.kind == "passive":
                    continue
                try:
                    mana = float(book.mana_cost(name)) if not book.charged_only(name) else 0.0
                except Exception:
                    continue
                if mana > h.mana:
                    continue
                p = self._score(name, s, target, near, boss, frame)
                if p is None or p.score <= 0:
                    continue
                left = 100.0 * (h.mana - mana) / max(1, getattr(h, "max_mana", 1))
                if mana > 0 and left < reserve and p.what == "skill":
                    p.score *= 0.25            # it would eat into the reserve
                if mana > 0 and p.what == "skill" and p.score < 4e4:
                    # damage skills: the lower his mana, the more they must be worth it, so
                    # some is always left for what saves him (buffs, summons are not touched)
                    p.score *= min(1.0, 0.3 + mana_left_pct / 100.0)
                    if target is not None and target.hp <= self.weapon_avg() * 1.2 and len(near) <= 2:
                        p.score *= 0.3        # a nearly dead monster isn't worth a spell
                if name == fav or getattr(s, "title", "") == fav:
                    p.score *= 1.25
                plans.append(p)

        if not plans:
            return None
        best = max(plans, key=lambda p: p.score)
        self.last = best.why
        return best

    GOLEMS = ("Clay Golem", "BloodGolem", "IronGolem", "FireGolem")

    def _mine(self):
        """His living summons (the run tags each with its summoner when it is cast)."""
        h = self.h
        return [a for a in self.sim.w.monsters if a.alive and getattr(a, "ally", False)
                and getattr(a, "summon_skill", None) and getattr(a, "summoner", h) is h]

    def _summons_full(self, name, s):
        mine = self._mine()
        if name in self.GOLEMS:
            return any(getattr(a, "summon_skill", "") in self.GOLEMS for a in mine)
        have = sum(1 for a in mine if a.summon_skill == name)
        cap = 1
        try:
            if s.data is not None and s.data.get("petmax"):
                cap = max(1, int(self.info(name, s)["env"].calc("petmax")))
        except Exception:
            cap = 1
        return have >= cap

    def info(self, name, s):
        """A skill's numbers (damage, element, radius, duration, cast frames): working them out is
        the slow part of a decision, so they are kept for 10 seconds (or until a level up)."""
        frame = self.sim.frame
        key = (name, getattr(self.h, "level", 1))
        got = self._info.get(key)
        if got is not None and got["until"] > frame:
            return got
        out = dict(until=frame + 250, env=None, elem=None, eavg=0.0, pavg=0.0, radius=0, dur=0,
                   frames=self.cast_frames(s))
        try:
            from game.skills import SkillEnv
            env = SkillEnv(self._book(), s)
            out["env"] = env
            try:
                e = env.elem_damage()
                if e:
                    out["elem"], out["eavg"] = e[0], (e[1] + e[2]) / 2.0
            except Exception:
                pass
            try:
                pd = env.phys_damage()
                if pd:
                    out["pavg"] = (pd[0] + pd[1]) / 2.0
            except Exception:
                pass
            try:
                out["radius"] = env.radius() or 0
            except Exception:
                pass
            try:
                out["dur"] = env.duration_frames() or 0
            except Exception:
                pass
        except Exception:
            pass
        self._info[key] = out
        return out

    def _score(self, name, s, target, near, boss, frame):
        h = self.h
        k = s.kind
        inf = self.info(name, s)
        env = inf["env"]
        frames = inf["frames"]
        per_sec = timing.FPS / float(max(1, frames))

        # ---- auras: switched on, not cast
        if k == "aura":
            if getattr(h, "active_aura", None) == name or frame < self.rebuff.get("@aura", 0):
                return None
            hurt = h.hp < h.max_hp * 0.5
            title = getattr(s, "title", name)
            defensive = title in DEFENSIVE_AURAS or name in DEFENSIVE_AURAS
            cur = getattr(h, "active_aura", None)
            if cur and not hurt and not defensive:
                return None              # (already running an aura; only swap to heal up)
            score = 1e6 if (hurt and defensive) or (not cur and not defensive) or (not cur) else 0
            return Plan("skill", name, None, h.pos, 1, score, "aura %s" % title) if score else None

        # ---- buffs and warcries that buff: keep them up
        if k in ("buff", "cry") and not self._offensive_cry(s):
            if frame < self.rebuff.get(name, 0):
                return None
            if k == "cry" and not near and frame > 50:
                pass                       # (warcries are fine before a fight too)
            return Plan("skill", name, None, h.pos, frames, 5e5, "buff %s" % getattr(s, "title", name))

        # ---- summons: only while he has fewer than the skill allows (one golem, one Valkyrie,
        # as many skeletons as its level gives); a summon that is up is not cast again
        if k in SUMMON_KINDS:
            if self._summons_full(name, s):
                return None
            if k in ("raise", "revive"):
                corpse = self._corpse_near(h.pos, 10)
                if corpse is None:
                    return None
                return Plan("skill", name, None, corpse, frames, 4e5, "raise from a corpse")
            cell = target.pos if (target is not None and k in ("turret", "wall")) else h.pos
            return Plan("skill", name, None, cell, frames, 3e5 if near else 2e5, "summon %s" % getattr(s, "title", name))

        if not near:
            return None

        # ---- curses: packs of 3+, or a boss, not cursed yet
        if k == "curse":
            r = inf["radius"] or 3
            centre, n = self._best_cluster(near, r, uncursed=name)
            if centre is None:
                return None
            if n >= 3 or (boss is not None and name not in (getattr(boss, "curses", None) or {})):
                cell = centre if n >= 3 else boss.pos
                return Plan("skill", name, None, cell, frames, 2e5 + n, "curse %s on %d" % (getattr(s, "title", name), max(1, n)))
            return None

        # ---- offensive warcries (Howl, Taunt, Battle Cry, War Cry): around the hero
        if k in ("cry", "attack") and self._offensive_cry(s):
            n = len(self.foes_near(h.pos, 5, near))
            if n < 2 or frame < self.rebuff.get(name, 0):
                return None
            return Plan("skill", name, None, h.pos, frames, 1e3 * n, "warcry on %d" % n)

        # ---- damage
        if k in DAMAGE_KINDS or k in ("move", "teleport"):
            return self._damage_plan(name, s, inf, frames, per_sec, target, near, boss)
        return None

    def _offensive_cry(self, s):
        return getattr(s, "title", s.key) in ("Howl", "Taunt", "Battle Cry", "War Cry", "Grim Ward")

    def _damage_plan(self, name, s, inf, frames, per_sec, target, near, boss):
        h = self.h
        k = s.kind
        elem, eavg, pavg = inf["elem"], inf["eavg"], inf["pavg"]
        weapon = getattr(s, "weapon", False) or k in ("attack", "melee")
        if weapon:
            bonus = 0
            try:
                bonus = self.w._skill_mods(h, name).get("dmg", 0)
            except Exception:
                pass
            pavg += self.weapon_avg() * (100 + bonus) / 100.0
        if eavg <= 0 and pavg <= 0:
            return None
        main = target if target is not None else min(near, key=lambda m: chebyshev(m.pos, h.pos))
        if weapon:
            reach = max(1, int(getattr(h, "reach", 1) or 1))
            if getattr(h, "ranged", False) or k == "missile":
                reach = max(reach, int(getattr(h, "range", 1) or 1), 8)
        else:
            reach = SPELL_RANGE
        radius = inf["radius"]
        if k == "nova":
            hit = self.foes_near(h.pos, max(2, radius or 4), near)
            cell = h.pos
        elif k in ("area", "corpse_blast"):
            centre, _ = self._best_cluster(near, max(2, radius or 3))
            if centre is None:
                return None
            hit = self.foes_near(centre, max(2, radius or 3), near)
            cell = centre
        elif k in ("line", "chain", "spiral", "move"):
            hit = [m for m in near if chebyshev(m.pos, main.pos) <= 3][:4]
            cell = main.pos
        else:
            hit = [main]
            cell = main.pos
        if k == "teleport":
            return None                      # (getting about: handled by walking for now)
        if not hit:
            return None
        if chebyshev(h.pos, main.pos) > reach + getattr(main, "radius", 0):
            reach_ok = False
        else:
            reach_ok = True
        total = 0.0
        for m in hit:
            part = pavg * self.res_factor(m, "phys") * (self.hit_chance(m) if weapon else 1.0)
            part += eavg * self.res_factor(m, elem)
            if getattr(m, "rift_boss", False):
                part *= 1.3                  # the boss is what ends the floor
            total += part
        score = total * per_sec
        if not reach_ok:
            score *= 0.6                     # he would have to walk first
        title = getattr(s, "title", name)
        why = "%s on %d" % (title, len(hit)) if len(hit) > 1 else title
        p = Plan("skill", name, main if k not in ("nova", "area", "corpse_blast") else None, cell, frames, score, why)
        p.why = why
        return p

    def _best_cluster(self, near, r, uncursed=None):
        best, bn = None, 0
        for m in near:
            group = [o for o in near if chebyshev(o.pos, m.pos) <= r]
            if uncursed:
                group = [o for o in group if uncursed not in (getattr(o, "curses", None) or {})]
            if len(group) > bn:
                best, bn = m.pos, len(group)
        return best, bn

    def _corpse_near(self, cell, r):
        for c in getattr(self.w, "corpses", []) or []:
            if getattr(c, "raised", False) or getattr(c, "used", False):
                continue
            if chebyshev(c.pos, cell) <= r:
                return c.pos
        return None

    # ------------------------------------------------------------ after the deed
    def done(self, plan, ok):
        """Remember casting delays, buff durations, and skills that didn't work."""
        if plan.what != "skill" or not plan.skill:
            return
        book = self._book()
        s = book.tree.get(plan.skill) if book else None
        d = getattr(s, "data", None) or {}
        frame = self.sim.frame
        if not ok:
            self.cool[plan.skill] = frame + 75       # (full, no corpse, blocked: try again in 3 s)
            return
        try:
            delay = int(d.get("delay") or 0)
        except ValueError:
            delay = 0
        if delay:
            self.cool[plan.skill] = frame + delay
        if s is not None and s.kind == "aura":
            self.rebuff["@aura"] = frame + 125
        elif s is not None and s.kind in ("buff", "cry", "curse") or (s is not None and self._offensive_cry(s)):
            dur = self.info(plan.skill, s)["dur"]
            self.rebuff[plan.skill] = frame + max(100, int(dur * 0.85) if dur else 500)
