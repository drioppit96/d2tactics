"""Turn-based potions (the potion system specification):

- Healing / mana potions restore D2's own flat amount, all of it the moment you drink:
      30 / 60 / 100 / 180 / 320 life, and 20 / 40 / 80 / 150 / 250 mana.
  Rejuvenations work in shares of your maximum: 35% of life and mana, 100% for a Full one.
- You drink only from the belt. In combat the belt is locked: no drinking from the backpack and no
  putting potions into the belt (they go to the backpack).
- The belt has 4 slots (columns, keys 1-4) and 2 rows at first (8 potions); Siege on Harrogath (killing
  Shenk) adds a row in Normal and one in Nightmare (4 rows, 16 potions at most); in Hell it gives
  4 Full Rejuvenation potions, the only way to get them. You drink the bottom potion of a column and
  the ones above slide down; the rows above open up when you hover over the belt, like D2.
- Every potion is used up when you drink it, as in D2.
- The Horadric Cube infuses a potion with a gem (potion + gem): the gem adds a buff for 2 (chipped)
  to 6 (perfect) turns, and the bottle gets an outline in the gem's colour.
"""
import random

from .d2items import GRADES

MAX_SLOTS = 4
MAX_ROWS = 4

#: potion code -> life or mana restored, D2's own figures. The same numbers sit on the bases
#: themselves (d2content.POTIONS), which is where a bottle gets its own; this is the fallback
#: and the list of what counts as a potion. A rejuvenation is the exception and works in
#: percent of your maximum, as it does in D2.
TIERS = {"hp1": 30, "hp2": 60, "hp3": 100, "hp4": 180, "hp5": 320,
         "mp1": 20, "mp2": 40, "mp3": 80, "mp4": 150, "mp5": 250}
REJUV_PCT = {"rvs": 35, "rvl": 100}


def restores(it):
    """(flat amount, percent) - a potion restores one or the other."""
    code = getattr(it, "code", "")
    if getattr(it, "potion", "") == "rejuv":
        return 0, REJUV_PCT.get(code, getattr(it, "amount", 0) or 35)
    return (getattr(it, "amount", 0) or TIERS.get(code, 0)), 0
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
    what = {"heal": "life", "mana": "mana", "rejuv": "life and mana"}.get(it.potion, "life")
    out = [(it.shown_name if hasattr(it, "shown_name") else it.name, WHITE)]
    flat, pct = restores(it)
    out.append(("Restores %d%% %s" % (pct, what) if pct else "Restores %d %s" % (flat, what), WHITE))
    inf = infusion(it)
    if inf:
        turns, _, _, _, lines = infusion_stats(*inf)
        col = GEM_COLORS.get(inf[0], WHITE)
        out.append(("Infused: %s%s (%d turns)" % ((GRADES[inf[1]] + " ") if GRADES[inf[1]] else "",
                                                  GEM_TITLES[inf[0]], turns), col))
        out += [(t, col) for t in lines]
    out.append(("Right click in the belt (or keys 1-4) to drink: 2 AP", GREY))
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


# D2's Belts.txt: the rows of potions each belt holds (no belt: 1 row of 4)
BELT_ROWS = {}
for _codes, _rows in ((("lbl", "zlb", "ulc"), 2), (("vbl", "zvb", "uvc"), 2), (("mbl", "zmb", "umc"), 3),
                      (("tbl", "ztb", "utc"), 3), (("hbl", "zhb", "uhc"), 4)):
    for _c in _codes:
        BELT_ROWS[_c] = _rows


def belt_rows(p):
    """Rows of potions, from the belt you wear (D2): none 1, Sash / Light Belt 2, Belt / Heavy Belt 3,
    Plated Belt 4 (and their exceptional and elite versions)."""
    belt = (getattr(p, "equipment", None) or {}).get("belt")
    if belt is None:
        return 1
    return min(MAX_ROWS, BELT_ROWS.get(getattr(belt, "code", ""), 2))


def column(p, c):
    return [it for it in p.belt if getattr(it, "belt_col", None) == c]


def permanent(it):
    """Nothing is: every potion is used up when you drink it, the way D2 does it."""
    return False


def cooldown_of(it):
    """Kept so the rest of the game can ask; no potion rests any more."""
    return 0


#: which belt columns (keys 1-4) a kind of potion may go in, or None for D2's own rule (any
#: column, its own kind first). The D2 Autobattler sets healing to 1-2 and mana to 3-4.
COLUMN_RULE = None


def _free_column(p, it):
    n, rows = belt_slots(p), belt_rows(p)
    rule = COLUMN_RULE.get(getattr(it, "potion", None)) if COLUMN_RULE else None
    if rule is not None:
        cols = {c: column(p, c) for c in rule if c < n}
        for c in sorted(cols, key=lambda c: (-len(cols[c]) if cols[c] and cols[c][0].code == it.code else 1, c)):
            if len(cols[c]) < rows and (not cols[c] or cols[c][0].code == it.code
                                        or getattr(cols[c][0], "potion", "") == getattr(it, "potion", "")):
                return c
        return None
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
def drink(world, c, row=None):
    """Drink a potion of belt slot c (the bottom one; row: one higher up, right clicked in the open
    belt). -> True if you drank."""
    p = world.player
    combat = world.mode == "combat"
    if not 0 <= c < belt_slots(p):
        return False
    col = column(p, c)
    if not col:
        return False
    if row is None:                          # keys 1-4: the lowest potion of the slot
        pot = col[0]
    else:
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
    belt_remove(p, pot)                      # every potion is used up
    world.emit("sound", "item_potion_drink")
    apply(world, pot)
    world._maybe_auto_end()
    return True


def apply(world, pot):
    p = world.player
    kind = pot.potion
    life = kind in ("heal", "rejuv")
    mana = kind in ("mana", "rejuv")
    flat, pct = restores(pot)
    healed = got = 0
    if life:
        want = p.max_hp * pct // 100 if pct else flat
        healed = min(want, p.max_hp - p.hp)
        p.hp += healed
        world.emit("heal", p, healed)
    if mana:
        want = p.max_mana * pct // 100 if pct else flat
        got = min(want, p.max_mana - p.mana)
        p.mana += got
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
    """A turn passes: infusion buffs count down."""
    p = world.player
    if regen and getattr(p, "potion_regen", None):
        p.potion_regen = []          # potions heal all at once now; old saves may still carry one
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



def combat_over(p):
    """Out of combat every potion is ready again."""
    for it in list(p.belt) + [x for x in p.inventory if getattr(x, "kind", "") == "potion"]:
        it.cd = 0


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
    """Siege on Harrogath in each difficulty: Larzuk's socketing - and a skill point."""
    p = world.player
    got = p.__dict__.setdefault("belt_unlocks", [])
    if difficulty in got:
        return
    got.append(difficulty)
    from . import tactics
    for h in tactics.everyone(world):                # one skill point each
        h.skills.points += 1
    world.log("Larzuk gives every hero a skill point.", (199, 179, 119))
