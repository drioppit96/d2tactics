"""Stat and skill points spent by the player (the Character screen).

Each hero's profile has auto_points: on, his points go by his class plan (brain.spend_points) at
each level up and before each floor; off, they wait for the player. Heroes spend by hand unless
the player turns the plan on.
"""
from . import brain

STATS = {"str": "base_str", "dex": "base_dex", "vit": "base_vit", "eng": "base_eng"}


def by_hand(hero):
    return not brain.profile(hero).get("auto_points", False)


def set_auto(hero, on):
    brain.profile(hero)["auto_points"] = bool(on)
    if on:
        brain.spend_points(hero)


def add_stat(hero, key, n=1):
    """Put up to n points into one stat. -> how many went in."""
    attr = STATS.get(key)
    pts = int(getattr(hero, "stat_points", 0) or 0)
    n = min(n, pts)
    if attr is None or n <= 0:
        return 0
    before_hp, before_mana = hero.max_hp, getattr(hero, "max_mana", 0)
    setattr(hero, attr, getattr(hero, attr) + n)
    hero.stat_points = pts - n
    hero.recalc()
    hero.hp += max(0, hero.max_hp - before_hp)          # D2: the new life and mana are there at once
    if hasattr(hero, "mana"):
        hero.mana += max(0, getattr(hero, "max_mana", 0) - before_mana)
    return n


def reset_stats(hero):
    """Every spent stat point back (free). -> how many."""
    s0, d0, e0, v0 = hero.start_stats
    back = (hero.base_str - s0) + (hero.base_dex - d0) + (hero.base_vit - v0) + (hero.base_eng - e0)
    hero.base_str, hero.base_dex, hero.base_vit, hero.base_eng = s0, d0, v0, e0
    hero.stat_points = int(getattr(hero, "stat_points", 0) or 0) + max(0, back)
    hero.recalc()
    hero.hp = min(hero.hp, hero.max_hp)
    hero.mana = min(hero.mana, hero.max_mana)
    return max(0, back)


def learn(hero, name):
    """One point into a skill, if he may (points left, level, the skills before it). -> bool."""
    book = getattr(hero, "skills", None)
    if book is None or not book.learn(name, hero.level):
        return False
    hero.recalc()
    return True


def reset_skills(hero):
    """Every spent skill point back (free). -> how many."""
    n = hero.skills.reset()
    hero.right_skill = None
    hero.left_skill = None
    for b in ("Wearwolf", "Wearbear"):
        (getattr(hero, "buffs", None) or {}).pop(b, None)
    hero.shape = None
    hero.recalc()
    return n


# ------------------------------------------------------------------ the skill tooltip, as D2 shows it
GREEN = (0, 220, 0)
WHITE = (255, 255, 255)
BLUE = (105, 105, 255)
RED = (255, 80, 80)
GOLD = (199, 179, 119)
GREY = (140, 140, 140)


def _real_time(lines, book, name, lv):
    """The engine's lines in real time: durations in seconds (it counts 2-second turns for the
    turn-based game), and nothing about the turn-based game's right-click aura slot."""
    from game.skills import SkillEnv, _seconds
    out = []
    for x in lines:
        if not x or x.startswith("Active while selected"):
            continue
        if x.startswith("Lasts ") and x.endswith(" turns"):
            s = book.tree[name]
            try:
                frames = SkillEnv(book, s, lv).duration_frames()
            except Exception:
                frames = 0
            if not frames or any(y.startswith("Duration") for y in lines):
                continue
            x = "Duration: %s seconds" % _seconds(frames)
        out.append(x)
    return out


def skill_tooltip(hero, name):
    """D2's skill tree tooltip: name, description, required level and skills, then this level and
    the next, then what it gets bonuses from. Numbers from D2's own SkillDesc / Skills tables."""
    from render.d2hud import _wrap
    book = hero.skills
    s = book.tree[name]
    lv = book.levels.get(name, 0)
    lines = [(s.title, GREEN)]
    for chunk in _wrap((s.long or "")[:1].upper() + (s.long or "")[1:], 46) if s.long else []:
        lines.append((chunk, WHITE))
    lines.append(("", WHITE))
    if not lv:
        lines.append(("Required Level: %d" % s.reqlevel, WHITE if hero.level >= s.reqlevel else RED))
        for pre in s.prereqs:
            q = book.tree.get(pre)
            if q is not None:
                lines.append(("Requires %s" % q.title, WHITE if book.levels.get(pre) else RED))
        lines.append(("First Level", WHITE))
        lines += [(x, WHITE) for x in _real_time(book.describe_next(name), book, name, 1)]
    else:
        cur = book.level(name)
        lines.append(("Current Skill Level: %d" % cur, WHITE))
        lines += [(x, WHITE) for x in _real_time(book.describe(name), book, name, cur)]
        if lv < s.maxlvl:
            lines.append(("", WHITE))
            lines.append(("Next Level", WHITE))
            lines += [(x, BLUE) for x in _real_time(book.describe_next(name), book, name, cur + 1)]
    syn = book.synergy_lines(name)
    if syn:
        lines.append(("", WHITE))
        lines += [(x, GREEN if i == 0 else WHITE) for i, x in enumerate(syn)]
    if book.can_learn(name, hero.level):
        lines.append(("", WHITE))
        lines.append(("Click to learn" if not lv else "Click to add a point", GOLD))
    return lines
