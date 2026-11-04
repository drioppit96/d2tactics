"""Turn-based potions (the potion system specification):

- Healing / mana potions restore a burst at once and then a little every turn for 5 turns, as a
  share of your maximum life / mana:
      Minor 60% + 2%/turn, Light 70% + 3%, (standard) 80% + 4%, Greater 90% + 5%, Super 100% + 6%.
  Full Rejuvenation: 100% life and mana at once + 6%/turn for 5 turns (130% in all).
- You drink only from the belt. In combat the belt is locked: no drinking from the backpack and no
  putting potions into the belt (they go to the backpack).
- The belt has 4 slots (columns, keys 1-4) and 2 rows at first (8 potions); Siege on Harrogath (killing
  Shenk) adds a row in Normal and one in Nightmare (4 rows, 16 potions at most); in Hell it gives
  4 Full Rejuvenation potions, the only way to get them. You drink the bottom potion of a column and
  the ones above slide down; the rows above open up when you hover over the belt, like D2.
- Drinking in combat puts that slot on an 8-turn cooldown (each slot counts down on its own).
- The Horadric Cube infuses a potion with a gem (potion + gem): the gem adds a buff for 2 (chipped)
  to 6 (perfect) turns, and the bottle gets an outline in the gem's colour.
"""
import random

from .d2items import GRADES

REGEN_TURNS = 5
SLOT_COOLDOWN = 8
MAX_SLOTS = 4
MAX_ROWS = 4

# potion code -> (instant %, % per turn for REGEN_TURNS turns)
TIERS = {"hp1": (60, 2), "hp2": (70, 3), "hp3": (80, 4), "hp4": (90, 5), "hp5": (100, 6),
         "mp1": (60, 2), "mp2": (70, 3), "mp3": (80, 4), "mp4": (90, 5), "mp5": (100, 6),
         "rvs": (35, 0), "rvl": (100, 6)}
FULL_REJUV = "rvl"


GEM_COLORS = {"amethyst": (175, 70, 235), "diamond": (235, 235, 250), "skull": (205, 195, 170),
              "ruby": (240, 40, 40), "sapphire": (60, 110, 255), "topaz": (250, 220, 40),
              "emerald": (40, 220, 80)}
GEM_TITLES = {"amethyst": "Amethyst", "diamond": "Diamond", "skull": "Skull", "ruby": "Ruby",
              "sapphire": "Sapphire", "topaz": "Topaz", "emerald": "Emerald"}


def infusion_stats(gem, grade):
    """The buff a gem infusion gives: (turns, stats, on-drink AP, cleanses, description lines)."""
    g = max(0, min(4, grade))
    turns = 2 + g
    stats, ap, cleanse, lines = {}, 0, [], []
    if gem == "amethyst":
        v = (10, 20, 30, 40, 50)[g]
        stats["mf"] = v
        lines.append("+%d%% Magic Find" % v)
    elif gem == "diamond":
        ap = (1, 2, 2, 2, 3)[g]
        v = (5, 5, 10, 10, 15)[g]
        stats["dr_pct"] = v
        lines += ["+%d AP when drunk" % ap, "Damage Reduced by %d%%" % v]
    elif gem == "skull":
        cleanse = ["poison", "debuffs"]
        stats["pois_immune"] = 1
        lines += ["Cleanses poison and all debuffs", "Immune to poison"]
        if g == 4:
            stats.update(cbf=1, curse_immune=1, stun_immune=1)
            lines.append("Cannot be stunned, frozen or cursed")
        else:
            stats["cc_res"] = 50
            lines.append("Resists crowd control (50%)")
    elif gem in ("ruby", "sapphire", "topaz"):
        et = {"ruby": "fire", "sapphire": "cold", "topaz": "ltng"}[gem]
        v = (15, 25, 35, 45, 50)[g]
        stats["res_" + et] = v
        stats["maxres_" + et] = v              # (a potion's resistance goes past your cap, up to 95%)
        lines.append("+%d%% %s Resistance" % (v, {"fire": "Fire", "cold": "Cold", "ltng": "Lightning"}[et]))
        if gem == "sapphire":
            stats["cbf"] = 1
            cleanse = ["chill"]
            lines.append("Cannot Be Frozen")
        if gem == "topaz":
            cleanse = ["shock"]
            lines.append("Cleanses shock")
    elif gem == "emerald":
        v = (20, 35, 50, 65, 80)[g]
        stats["res_pois"] = v
        stats["maxres_pois"] = v
        lines.append("+%d%% Poison Resistance" % v)
    return turns, stats, ap, cleanse, lines


# what potion sellers stock: the best tier (1 Minor .. 5 Super) by difficulty and act; they sell it
# and the tier below
VENDOR_BEST = {"normal": (2, 2, 3, 3, 3), "nightmare": (3, 3, 4, 4, 4), "hell": (4, 4, 5, 5, 5)}


def vendor_tiers(act, difficulty):
    best = VENDOR_BEST.get(difficulty, VENDOR_BEST["normal"])[max(1, min(5, int(act))) - 1]
    return {str(t) for t in (best - 1, best) if t >= 1}


# ------------------------------------------------------------------ the item
def drinkable(it):
    return getattr(it, "kind", "") == "potion" and getattr(it, "potion", "") in ("heal", "mana", "rejuv")


def infusion(it):
    inf = getattr(it, "infused", None)
    return tuple(inf) if inf else None


def outline_color(it):
    inf = infusion(it)
    return GEM_COLORS.get(inf[0]) if inf else None


def describe(it):
    """Tooltip lines for a healing / mana / rejuvenation potion."""
    WHITE, GREY = (255, 255, 255), (170, 170, 170)
    burst, per = TIERS.get(it.code, (0, 0))
    what = {"heal": "life", "mana": "mana", "rejuv": "life and mana"}.get(it.potion, "life")
    out = [(it.shown_name if hasattr(it, "shown_name") else it.name, WHITE)]
    out.append(("Restores %d%% %s at once" % (burst, what), WHITE))
    if per:
        out.append(("+%d%% %s per turn for %d turns" % (per, what, REGEN_TURNS), WHITE))
    inf = infusion(it)
    if inf:
        turns, _, _, _, lines = infusion_stats(*inf)
        col = GEM_COLORS.get(inf[0], WHITE)
        out.append(("Infused: %s%s (%d turns)" % ((GRADES[inf[1]] + " ") if GRADES[inf[1]] else "",
                                                  GEM_TITLES[inf[0]], turns), col))
        out += [(t, col) for t in lines]
    out.append(("Right click in the belt (or keys 1-4) to drink: 2 AP", GREY))
    out.append(("Each belt slot rests %d turns after a drink in combat" % SLOT_COOLDOWN, GREY))
    return out


def name_of(it):
    inf = infusion(it)
    base = getattr(it, "_base_name", None) or it.name
    return "%s (%s)" % (base, GEM_TITLES[inf[0]]) if inf else base


def infuse(it, gem, grade):
    if not getattr(it, "_base_name", None):
        it._base_name = it.name
    it.infused = (gem, grade)
    it.name = name_of(it)


# ------------------------------------------------------------------ the belt
def belt_slots(p):
    """The belt always has 4 slots (columns, keys 1-4)."""
    return MAX_SLOTS


def belt_rows(p):
    """Rows of potions: 2 at first, +1 for Shenk in Normal, +1 for Shenk in Nightmare (4 at most)."""
    got = set(getattr(p, "belt_unlocks", None) or ())
    return min(MAX_ROWS, 2 + len(got & {"normal", "nightmare"}))


def column(p, c):
    return [it for it in p.belt if getattr(it, "belt_col", None) == c]


def _cooldowns(p):
    cd = getattr(p, "belt_cd", None)
    if not isinstance(cd, list) or len(cd) != MAX_SLOTS:
        cd = p.belt_cd = [0] * MAX_SLOTS
    return cd


def cooldown(p, c):
    return _cooldowns(p)[c]


def _free_column(p, it):
    n, rows = belt_slots(p), belt_rows(p)
    cols = [column(p, c) for c in range(n)]
    for c in range(n):                         # a column of the same potions first, like D2
        if cols[c] and len(cols[c]) < rows and cols[c][0].code == it.code:
            return c
    for c in range(n):
        if not cols[c]:
            return c
    for c in range(n):
        if len(cols[c]) < rows:
            return c
    return None


def has_room(p, it):
    return getattr(it, "kind", "") == "potion" and _free_column(p, it) is not None


def belt_add(p, it, world=None):
    """Put a potion into the belt. Not in combat (the belt is locked). -> True if it went in."""
    if world is not None and getattr(world, "mode", "") == "combat":
        return False
    c = _free_column(p, it) if getattr(it, "kind", "") == "potion" else None
    if c is None:
        return False
    it.belt_col = c
    it.inv_pos = None
    p.belt.append(it)
    return True


def belt_put(world, it, c):
    """Drag and drop: a potion held on the cursor goes into belt slot c (or, if that one is full, the
    first slot with room). Not in combat. -> True if it went in."""
    p = world.player
    if getattr(it, "kind", "") != "potion":
        return False
    if world.mode == "combat":
        world.log("The belt is locked in combat.", (170, 170, 170))
        return False
    if 0 <= c < belt_slots(p) and len(column(p, c)) < belt_rows(p):
        it.belt_col, it.inv_pos = c, None
        p.belt.append(it)
        return True
    if belt_add(p, it, world):
        return True
    world.log("Your belt is full.", (170, 170, 170))
    return False


def belt_take(world, c, row=0):
    """Left click on a belt potion: it comes onto the cursor (not in combat). -> the potion or None."""
    p = world.player
    if world.mode == "combat":
        world.log("The belt is locked in combat.", (170, 170, 170))
        return None
    col = column(p, c)
    if not 0 <= row < len(col):
        return None
    it = col[row]
    belt_remove(p, it)
    return it


def belt_remove(p, it):
    if it in p.belt:
        p.belt.remove(it)
    it.belt_col = None


def normalize(p):
    """Every belt potion in a usable column, no column over the belt's rows; the rest to the backpack."""
    n, rows = belt_slots(p), belt_rows(p)
    keep, spill = [], []
    counts = [0] * MAX_SLOTS
    for it in list(p.belt):
        c = getattr(it, "belt_col", None)
        if c is None or not (0 <= c < n) or counts[c] >= rows:
            spill.append(it)
        else:
            counts[c] += 1
            keep.append(it)
    p.belt = keep
    out = []
    for it in spill:
        it.belt_col = None
        if not belt_add(p, it):
            out.append(it)
    for it in out:
        if not p.inv_add(it):
            out_ground = getattr(p, "_belt_overflow", [])
            out_ground.append(it)
            p._belt_overflow = out_ground
    return out


# ------------------------------------------------------------------ drinking
def drink(world, c, row=0):
    """Drink a potion of belt slot c (the bottom one; row: one higher up, right clicked in the open
    belt). -> True if you drank."""
    p = world.player
    combat = world.mode == "combat"
    if not 0 <= c < belt_slots(p):
        return False
    col = column(p, c)
    if not col:
        return False
    if combat and cooldown(p, c) > 0:
        world.log("That belt slot needs %d more turn%s." % (cooldown(p, c), "" if cooldown(p, c) == 1 else "s"),
                  (170, 170, 170))
        return False
    pot = col[min(max(0, row), len(col) - 1)]
    if not drinkable(pot):
        if not world.player_can_act():
            return False
        return world._drink_special(pot)
    if not world.player_can_act():
        return False
    from .world import POTION_AP
    if combat:
        if p.ap < POTION_AP:
            world.log("Not enough AP to drink.", (170, 170, 170))
            return False
        p.ap -= POTION_AP
        _cooldowns(p)[c] = SLOT_COOLDOWN
    belt_remove(p, pot)
    apply(world, pot)
    world._maybe_auto_end()
    return True


def apply(world, pot):
    p = world.player
    burst, per = TIERS.get(pot.code, (pot.amount if pot.potion == "rejuv" else 50, 0))
    kind = pot.potion
    life = kind in ("heal", "rejuv")
    mana = kind in ("mana", "rejuv")
    healed = got = 0
    if life:
        healed = min(p.max_hp * burst // 100, p.max_hp - p.hp)
        p.hp += healed
        world.emit("heal", p, healed)
    if mana:
        got = min(p.max_mana * burst // 100, p.max_mana - p.mana)
        p.mana += got
    if per:
        regen = p.__dict__.setdefault("potion_regen", [])
        regen.append(dict(hp=per if life else 0, mana=per if mana else 0, turns=REGEN_TURNS))
    msg = "You drink a %s (" % pot.name + ", ".join(
        x for x in (("+%d life" % healed) if life else "", ("+%d mana" % got) if mana else "") if x) + ")."
    world.log(msg, (120, 140, 255) if kind == "mana" else (110, 220, 110))
    inf = infusion(pot)
    if inf:
        _infusion_buff(world, *inf)


def _infusion_buff(world, gem, grade):
    p = world.player
    turns, stats, ap, cleanse, lines = infusion_stats(gem, grade)
    if "poison" in cleanse:
        p.effects.pop("poison", None)
        p.effects.pop("poison_src", None)
    if "debuffs" in cleanse:
        for k in ("chilled", "chill", "stun", "freeze", "bleed"):
            p.effects.pop(k, None)
        for k in [k for k, b in getattr(p, "buffs", {}).items() if b.get("curse")]:
            p.buffs.pop(k)
    if "chill" in cleanse:
        p.effects.pop("chilled", None)
        p.effects.pop("chill", None)
    if "shock" in cleanse:
        p.effects.pop("shock", None)
    if ap and world.mode == "combat":
        p.ap += ap
    if stats:
        p.__dict__.setdefault("potion_buffs", {})[gem] = dict(turns=turns, stats=stats, grade=grade)
        hp_frac = p.hp / float(max(1, p.max_hp))
        p.recalc()
        p.hp = min(p.max_hp, max(1, int(round(p.max_hp * hp_frac))))
    world.log("%s infusion: %s (%d turns)." % (GEM_TITLES[gem], ", ".join(lines), turns), GEM_COLORS[gem])


def buff_stat(p, stat):
    return sum(b["stats"].get(stat, 0) for b in (getattr(p, "potion_buffs", None) or {}).values())


def tick(world, regen=True, buffs=True, cooldowns=True):
    """A turn passes: regeneration streams, infusion buffs and slot cooldowns."""
    p = world.player
    if regen:
        left = []
        for r in getattr(p, "potion_regen", None) or []:
            if p.alive:
                p.hp = min(p.max_hp, p.hp + p.max_hp * r["hp"] // 100)
                p.mana = min(p.max_mana, p.mana + p.max_mana * r["mana"] // 100)
            r["turns"] -= 1
            if r["turns"] > 0:
                left.append(r)
        p.potion_regen = left
    if buffs and getattr(p, "potion_buffs", None):
        gone = []
        for gem, b in p.potion_buffs.items():
            b["turns"] -= 1
            if b["turns"] <= 0:
                gone.append(gem)
        for gem in gone:
            p.potion_buffs.pop(gem)
            world.log("The %s infusion wears off." % GEM_TITLES[gem].lower(), (170, 170, 170))
        if gone:
            hp_frac = p.hp / float(max(1, p.max_hp))
            p.recalc()
            p.hp = min(p.max_hp, max(1, int(round(p.max_hp * hp_frac))))
    if cooldowns:
        cd = _cooldowns(p)
        for i in range(MAX_SLOTS):
            cd[i] = max(0, cd[i] - 1)


def combat_over(p):
    """Out of combat the belt slots are ready again."""
    p.belt_cd = [0] * MAX_SLOTS


# ------------------------------------------------------------------ crowd control checks
def resists_cc(p, rng=random):
    """Skull infusion: 50% to shrug off a chill / stun (the perfect one: always)."""
    if getattr(p, "is_player", False) and hasattr(p, "mod"):
        if p.mod("stun_immune"):
            return True
        v = p.mod("cc_res")
        return bool(v) and rng.randrange(100) < v
    return False


def curse_immune(p):
    return bool(getattr(p, "is_player", False) and hasattr(p, "mod") and p.mod("curse_immune"))


# ------------------------------------------------------------------ the cube and Shenk
def cube_infuse(items):
    """Potion + gem in the cube -> the potion infused (the gem used up). None if it isn't that."""
    if len(items) != 2:
        return None
    pots = [x for x in items if drinkable(x)]
    gems = [x for x in items if isinstance(getattr(x, "gem", None), (tuple, list)) and x.gem and x.gem[0] == "gem"]
    if len(pots) != 1 or len(gems) != 1:
        return None
    pot, gem = pots[0], gems[0]
    infuse(pot, gem.gem[1], int(gem.gem[2]))
    return pot


def shenk_reward(world, difficulty):
    """Siege on Harrogath in each difficulty: a belt slot (Normal, Nightmare) or 4 Full Rejuvenations (Hell)."""
    p = world.player
    got = p.__dict__.setdefault("belt_unlocks", [])
    if difficulty in got:
        return
    got.append(difficulty)
    if difficulty in ("normal", "nightmare"):
        world.log("Your belt has %d rows now (%d potions)." % (belt_rows(p), belt_rows(p) * MAX_SLOTS),
                  (199, 179, 119))
        normalize(p)
    elif difficulty == "hell" and world.content is not None and FULL_REJUV in world.content.base_by_code:
        c = world.content
        for _ in range(4):
            c.allow_full_rejuv = True
            try:
                it = c.make_item(c.base_by_code[FULL_REJUV], 1, world.rng)
            finally:
                c.allow_full_rejuv = False
            if not belt_add(p, it) and not p.inv_add(it):
                world.ground.setdefault(p.pos, []).append(it)
        world.log("You receive 4 Full Rejuvenation Potions.", (199, 179, 119))
