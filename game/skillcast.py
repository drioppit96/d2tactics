"""Turn-based behaviour of every class skill (mixed into World).

The numbers come from game/skills.py (D2's tables); this file decides what happens on the
grid: who gets hit, for how much, which status effects stick and for how many turns.

Status effects on monsters (m.effects):
  chill  - turns; a chilled monster gets 2 AP less          freeze - turns; skips its turn
  poison - [damage per turn, turns]                          stun / flee - as before
Curses live in m.curses: {skill: {"turns": n, "stats": {...}, "flags": set()}}.
Player buffs live in p.buffs: {skill: {"turns": n, "stats": {...}}} (summed into Player.recalc).
"""
import random

from .grid import chebyshev, DIRS8
from .skills import SkillEnv, turns_from_frames, STAT_MAP, FRAMES, TURN_SECONDS
from .units import Monster

YELLOW = (255, 230, 90)
GREY = (170, 170, 170)
BLUE = (120, 160, 255)
GREEN = (100, 220, 100)

SPELL_RANGE = 12          # cells
ELEMS = ("fire", "cold", "ltng", "pois", "mag")


def _line(a, b):
    """Cells from a (exclusive) towards b (inclusive), Bresenham."""
    x0, y0 = a
    x1, y1 = b
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    out = []
    while (x0, y0) != (x1, y1):
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy
        out.append((x0, y0))
    return out


def _fan_targets(src, dst, n, length):
    """End points of n missiles fanned out around the line src -> dst (D2 Teeth / Charged Bolt)."""
    import math
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    if dx == 0 and dy == 0:
        dx = 1
    a0 = math.atan2(dy, dx)
    fan = math.radians(min(100.0, 14.0 * (n - 1)))
    step = fan / (n - 1) if n > 1 else 0.0
    out = [dst]                          # the first one always flies straight at what you aimed at
    for i in range(1, n):
        off = step * ((i + 1) // 2) * (1 if i % 2 else -1)
        a = a0 + off
        out.append((int(round(src[0] + math.cos(a) * length)), int(round(src[1] + math.sin(a) * length))))
    return out


def _extend(a, b, length):
    """A straight line from a through b, `length` cells long."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return []
    far = (a[0] + dx * 40, a[1] + dy * 40)
    return _line(a, far)[:length]


class SkillCaster:
    # ------------------------------------------------------------ helpers
    def enemies(self):
        return [m for m in self.monsters if m.alive and m.ai != "npc" and not getattr(m, "ally", False)]

    def allies(self):
        return [m for m in self.monsters if m.alive and getattr(m, "ally", False)]

    def _skill_env(self, name):
        p = self.player
        book = p.skills
        book.clvl = p.level
        return SkillEnv(book, book.tree[name], max(1, book.level(name)))

    def _mastery(self, et):
        b = getattr(self.player, "bonus", {}) or {}
        items = self.player.mod("extra_" + et) if et in ("fire", "cold", "ltng", "pois") else 0   # +% to X skill damage
        return b.get({"fire": "fire_mastery", "cold": "cold_mastery", "ltng": "ltng_mastery", "pois": "pois_mastery"}.get(et, ""), 0) + items

    def _pierce(self, et):
        b = getattr(self.player, "bonus", {}) or {}
        items = self.player.mod("pierce_" + et) if et in ("fire", "cold", "ltng", "pois") else 0  # -% to enemy X resistance
        return b.get(et + "_pierce", 0) + items

    def mstat(self, m, stat):
        """A monster's stat change from curses / auras."""
        tot = 0
        for c in getattr(m, "curses", {}).values():
            tot += c["stats"].get(stat, 0)
        return tot

    def _has_flag(self, m, flag):
        return any(flag in c.get("flags", ()) for c in getattr(m, "curses", {}).values())

    def _resist(self, m, et):
        res = getattr(m, "res", {}).get(et, 0)
        res += self.mstat(m, "res_" + et) + self.mstat(m, "res_all")
        if getattr(m, "is_player", False):
            from .monmods import player_res_penalty
            return min(75, res) - player_res_penalty(self, m)
        if et in ("fire", "cold", "ltng", "pois") and res < 100:
            res -= self._pierce(et)
        if res >= 100:
            return 100            # immune
        return max(-100, res)

    # ------------------------------------------------------------ damage
    def elem_hit(self, target, et, lo, hi, src, length=0, show=True):
        """Elemental damage with resistances, chill and poison. Returns damage dealt."""
        if not target.alive or hi <= 0:
            return 0
        if et == "pois":
            total = self.rng.randint(int(lo), int(max(lo, hi)))
            total = total * (100 + self._mastery(et)) // 100 if src is self.player else total
            total = total * (100 - self._resist(target, et)) // 100
            if total <= 0:
                if show:
                    self.log("%s is immune to poison." % target.name, GREY)
                return 0
            secs = max(1, length) / float(FRAMES)
            turns = max(1, min(4, int(round(secs / TURN_SECONDS))))
            per = max(1, total // turns)
            cur = target.effects.get("poison")
            if not cur or cur[0] * cur[1] < per * turns:
                target.effects["poison"] = [per, turns]
            # the first tick lands right away
            self._damage(target, per, src)
            return per
        dmg = self.rng.randint(int(lo), int(max(lo, hi)))
        if src is self.player:
            dmg = dmg * (100 + self._mastery(et)) // 100
        res = self._resist(target, et)
        if res >= 100:
            if show:
                self.log("%s is immune to %s." % (target.name, {"fire": "fire", "cold": "cold", "ltng": "lightning", "mag": "magic"}.get(et, et)), GREY)
            return 0
        dmg = max(0, dmg * (100 - res) // 100)
        if dmg > 0 and getattr(target, "is_player", False):
            from .itemfx import absorb
            dmg, healed = absorb(target, et, dmg)
            if healed:
                self.emit("heal", target, healed)
        if dmg <= 0:
            return 0
        self._damage(target, dmg, src)
        if et == "cold" and target.alive and not target.is_player:
            turns = max(1, min(3, turns_from_frames(length))) if length else 1
            target.effects["chill"] = max(target.effects.get("chill", 0), turns)
        return dmg

    def phys_hit(self, target, lo, hi, src):
        if not target.alive or hi <= 0:
            return 0
        dmg = self.rng.randint(int(lo), int(max(lo, hi)))
        amp = -self.mstat(target, "dr_pct")
        dmg = max(1, dmg * (100 + amp) // 100)
        if getattr(target, "res", {}).get("phys", 0):
            dmg = max(0, dmg * (100 - min(100, target.res["phys"] - amp)) // 100)
        if dmg:
            self._damage(target, dmg, src)
        return dmg

    def skill_damage(self, env, target, mult_pct=100, show=True):
        """Damage of a spell-like skill (no weapon) on one target."""
        total = 0
        if env.s.extra.get("undead_only") and not getattr(target, "undead", False):
            return 0
        pd = env.phys_damage()
        if pd:
            total += self.phys_hit(target, pd[0] * mult_pct // 100, pd[1] * mult_pct // 100, self.player)
        ed = env.elem_damage()
        if ed:
            et, lo, hi, ln = ed
            total += self.elem_hit(target, et, lo * mult_pct // 100, hi * mult_pct // 100, self.player, ln, show)
        if env.s.extra.get("stun") and target.alive and not target.is_player:
            target.effects["stun"] = max(target.effects.get("stun", 0), env.s.extra["stun"])
        if env.s.extra.get("knock") and target.alive:
            self._knockback(self.player, target)
        if env.s.key == "Static Field" and target.alive:
            pct = env.par(4) or 25
            dmg = max(1, target.hp * pct // 100)
            self._damage(target, dmg, self.player)
            total += dmg
        return total

    def _wake(self, targets):
        for m in targets:
            m.aware = True
        if self.mode == "explore" and targets:
            self.check_awareness_force()

    # ------------------------------------------------------------ dispatch
    def cast_generic(self, name, target=None, cell=None):
        """Skills of the other six classes (and the Barbarian's that share a pattern)."""
        p = self.player
        book = p.skills
        s = book.tree[name]
        env = self._skill_env(name)
        ap, mana = self.skill_cost(name)
        k = s.kind
        if k == "passive":
            return False
        if k == "aura":
            if getattr(p, "active_aura", None) != name:
                self.select_right_skill(name)
            return True
        if p.mana < mana:
            self.log("Not enough mana.", GREY)
            return False
        if self.mode == "combat" and p.ap < ap:
            self.log("Need %d AP for %s." % (ap, s.title), GREY)
            return False
        if cell is None and target is not None:
            cell = target.pos
        if target is None and cell is not None:
            u = self.unit_at(cell)
            if u is not None and u is not p and u.ai != "npc" and not getattr(u, "ally", False):
                target = u
        handler = getattr(self, "_k_" + k, None)
        if handler is None:
            self.log("%s can't be used yet." % s.title, GREY)
            return False
        if k in ("turret", "teleport", "wall") and cell is not None and (cell in self.occupied() or not self.grid.walkable(*cell)):
            cell = self._free_cell_near(cell)
        if self.mode == "explore" and cell is not None and k in ("missile", "nova", "area", "line", "chain", "curse",
                                                                  "corpse_blast", "charge"):
            # attacking from the shadows starts the fight (you keep your full turn)
            centre = p.pos if k == "nova" else cell
            near = [m for m in self.enemies() if chebyshev(m.pos, centre) <= 6]
            if near and self.mode == "explore":
                near[0].aware = True
                self.check_awareness_force()
        self._casting = s
        ok = handler(s, env, target, cell, ap, mana)
        self._casting = None
        if ok:
            self._maybe_auto_end()
        return ok

    def _free_cell_near(self, cell, radius=3):
        occ = self.occupied()
        for r in range(0, radius + 1):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    c = (cell[0] + dx, cell[1] + dy)
                    if self.grid.walkable(*c) and c not in occ:
                        return c
        return cell

    def _spend(self, ap, mana, anim_cell=None, anim="cast"):
        p = self.player
        if self.mode == "combat":
            p.ap -= ap
        p.mana = max(0, p.mana - mana)
        if anim_cell is not None:
            p.face(*anim_cell)
        self.emit("attack", p, anim_cell or p.pos, anim)
        s = getattr(self, "_casting", None)
        if s is not None and s.data and s.data.get("castoverlay"):
            self.emit("overlay", p, s.data["castoverlay"])

    @staticmethod
    def vis_missile(s, area=False):
        """The Missiles.txt entry D2 draws for a skill (client missile first)."""
        d = s.data or {}
        if area:
            return d.get("cltmissilea") or d.get("srvmissilea") or d.get("cltmissile") or d.get("srvmissile") or None
        return d.get("cltmissile") or d.get("srvmissile") or d.get("cltmissilea") or d.get("srvmissilea") or None

    def weapon_missile(self, unit):
        if not unit.is_player:
            m = getattr(unit, "missile", "") or ""
            if m:
                return m
            return {"shaman": "shafire1"}.get(getattr(unit, "ai", ""), "arrow")
        w = unit.equipment.get("weapon")
        anc = set(w.base.get("ancestors", ())) if w is not None and isinstance(getattr(w, "base", None), dict) else set()
        if "xbow" in anc:
            return "bolt"
        if "jave" in anc:
            return "javelin"
        if anc & {"taxe"}:
            return "throwaxe"
        if anc & {"tkni"}:
            return "throwknife"
        return "arrow"

    def _in_range(self, cell, rng=SPELL_RANGE, los=True):
        p = self.player
        if cell is None or chebyshev(cell, p.pos) > rng:
            self.log("Out of range.", GREY)
            return False
        if los and not self.grid.line_of_sight(p.pos, cell):
            self.log("No line of sight.", GREY)
            return False
        return True

    # ------------------------------------------------------------ melee (weapon) skills
    def _k_melee(self, s, env, target, cell, ap, mana):
        if target is None:
            return False
        return self.player_attack(target, s.key, ap_cost=ap, mana_cost=mana)

    def melee_mods(self, attacker, skill):
        """Generic D2 melee skill: +damage%, +AR%, added elemental damage, hits, effects."""
        s = attacker.skills.tree.get(skill)
        m = {"dmg": 0, "ar": 0, "knock": False, "stun": 0, "magic": False, "elem": None, "always": False,
             "leech": 0, "hits": 1}
        if s is None or s.data is None:
            return m
        env = self._skill_env(skill)
        d = s.desc or {}
        for pre, n in (("desc", 6), ("dsc2", 4)):
            for i in range(1, n + 1):
                ta = (d.get("%stexta%d" % (pre, i)) or "")
                txt = env.s.strings.get(ta, ta) if getattr(env.s, "strings", None) else ta
                code = d.get("%sline%d" % (pre, i))
                calc = d.get("%scalca%d" % (pre, i), "")
                if not calc or code not in ("2", "3", "4", "5", "6"):
                    continue
                from .d2calc import evaluate
                v = evaluate(calc, env)
                low = txt.lower()
                if low.startswith("damage") or "kick damage" in low or low.startswith("your damage"):
                    m["dmg"] += v
                elif low.startswith("attack") or "attack rating" in low:
                    m["ar"] += v
                elif "life steal" in low or "life stolen" in low:
                    m["leech"] += v
        if s.data.get("tohit") or s.data.get("tohitcalc"):
            if m["ar"] == 0:
                m["ar"] = env.tohit()
        ed = env.elem_damage()
        if ed:
            m["elem"] = ed
        x = s.extra
        hits = x.get("hits", 1)
        if hits == "calc1":
            hits = max(1, env.calc("calc1"))
        m["hits"] = max(1, min(6, int(hits)))
        m["stun"] = x.get("stun", 0)
        if s.key == "Maul" or s.key == "Smite":
            m["stun"] = max(m["stun"], 1)
        m["knock"] = bool(x.get("knock"))
        m["always"] = bool(x.get("always_hit"))
        if s.element == "mag":
            m["magic"] = True
        # assassin charge-ups / finishers
        if x.get("charges"):
            p = self.player
            ch = p.effects.get("charges", 0)
            m["dmg"] += 0
        return m

    def after_melee_hit(self, attacker, target, skill, dealt):
        """Extra effects of melee skills once a hit landed."""
        p = self.player
        s = p.skills.tree.get(skill)
        if s is None or s.data is None:
            return
        env = self._skill_env(skill)
        x = s.extra
        if x.get("chain") and target.alive is not None:
            ed = env.elem_damage()
            n = max(1, env.calc("calc1"))
            if ed:
                foes = sorted([m for m in self.enemies() if m is not target and self.udist(m, target) <= 4],
                              key=lambda m: self.udist(m, target))[:n]
                for m in foes:
                    self.emit("projectile", p, target.pos, m.pos, "ltng")
                    self.elem_hit(m, ed[0], ed[1], ed[2], p, ed[3])
        if x.get("sweep"):
            pass
        if x.get("splash"):
            ed = env.elem_damage()
            for m in self.enemies():
                if m is not target and self.udist(m, target) <= x["splash"] and ed:
                    self.elem_hit(m, ed[0], ed[1], ed[2], p, ed[3])
        if x.get("charges"):
            p.effects["charges"] = min(3, p.effects.get("charges", 0) + 1)
            p.effects["charge_skill"] = skill
        if x.get("finisher") and p.effects.get("charges"):
            self._release_charges(target)
        if x.get("self_damage"):
            hurt = max(1, dealt * x["self_damage"] // 100)
            p.hp = max(1, p.hp - hurt)
            self.emit("damage", p, hurt, p.hp)
        if x.get("convert") and target.alive and not target.unique:
            chance = 0
            for i in range(1, 4):
                pass
            if self.rng.random() < 0.15 + 0.02 * env.lvl:
                self._make_ally(target)
                self.log("%s is converted!" % target.name, YELLOW)

    def _release_charges(self, target):
        p = self.player
        n = p.effects.pop("charges", 0)
        sk = p.effects.pop("charge_skill", None)
        if not n or sk is None or not target.alive:
            return
        env = self._skill_env(sk)
        ed = env.elem_damage()
        self.log("%d charges released!" % n, YELLOW)
        if ed:
            self.elem_hit(target, ed[0], ed[1] * n, ed[2] * n, p, ed[3])
        else:
            lo, hi = p.dmg
            self._damage(target, self.rng.randint(lo, hi) * n, p)

    # ------------------------------------------------------------ projectiles
    def _first_hit_on_line(self, src, dst, pierce=False, max_len=SPELL_RANGE):
        cells = _extend(src, dst, max_len)
        foes = self._foe_index(src, max_len)
        hit = []
        for c in cells:
            if not self.grid.in_bounds(*c) or not self.grid.walkable(*c):
                break
            u = foes.get(c)
            if u is not None and u not in hit:
                hit.append(u)
                if not pierce:
                    return hit, c
        return hit, (cells[-1] if cells else dst)

    def _foe_index(self, centre, r):
        """{cell: monster} for every enemy body near `centre` (one pass instead of unit_at per cell)."""
        idx = {}
        for m in self.monsters:
            if not m.alive or m.ai == "npc" or getattr(m, "ally", False):
                continue
            if abs(m.x - centre[0]) > r + 2 or abs(m.y - centre[1]) > r + 2:
                continue
            rr = getattr(m, "radius", 0)
            for dy in range(-rr, rr + 1):
                for dx in range(-rr, rr + 1):
                    idx[(m.x + dx, m.y + dy)] = m
        return idx

    def _missile_path(self, src, dst, pierce=False, max_len=SPELL_RANGE, foes=None):
        """(cells the missile flies over, units it hits) - stops at walls and, unless it pierces,
        at the first enemy."""
        cells = _line(src, dst)[:max_len] if max(abs(dst[0] - src[0]), abs(dst[1] - src[1])) >= max_len \
            else _extend(src, dst, max_len)
        if foes is None:
            foes = self._foe_index(src, max_len)
        path, hit = [], []
        for c in cells:
            if not self.grid.in_bounds(*c) or not self.grid.walkable(*c):
                break
            path.append(c)
            u = foes.get(c)
            if u is not None:
                if u not in hit:
                    hit.append(u)
                if not pierce:
                    break
        return path, hit

    def _spread_count(self, s, env):
        n = s.extra.get("targets", 1)
        if n == "calc1":
            n = max(1, env.calc("calc1"))
        return max(1, min(24, int(n)))

    def _spread_shots(self, s, env, cell):
        """[(path cells, unit hit or None)] for each missile of a fan."""
        p = self.player
        n = self._spread_count(s, env)
        out = []
        foes = self._foe_index(p.pos, SPELL_RANGE)
        for end in _fan_targets(p.pos, cell, n, SPELL_RANGE):
            path, hit = self._missile_path(p.pos, end, max_len=SPELL_RANGE, foes=foes)
            out.append((path, hit[0] if hit else None))
        return out

    def skill_preview(self, name, cell):
        """Cells a skill would cover if cast at `cell` -> (cells, cells of monsters it hits), or None
        for skills that don't aim (the frontend highlights them under the mouse)."""
        p = self.player
        book = getattr(p, "skills", None)
        if not name or book is None or name not in book.tree or cell is None:
            return None
        s = book.tree[name]
        k = s.kind
        env = self._skill_env(name)
        x = s.extra
        sq = lambda c, r: {(c[0] + dx, c[1] + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)}

        def body(m):
            return sq(m.pos, getattr(m, "radius", 0))
        cells, hits = set(), set()
        if k == "missile":
            if s.weapon and not x.get("spread") and not x.get("splash") and not x.get("pierce"):
                return None
            if self._spread_count(s, env) > 1 and x.get("spread"):
                for path, m in self._spread_shots(s, env, cell):
                    cells.update(path)
                    if m is not None:
                        hits |= body(m)
            else:
                path, hit = self._missile_path(p.pos, cell, pierce=bool(x.get("pierce")))
                cells.update(path)
                for m in hit:
                    hits |= body(m)
                if x.get("splash"):
                    centre = hit[0].pos if hit else (path[-1] if path else cell)
                    area = sq(centre, x["splash"])
                    cells |= {c for c in area if self.grid.walkable(*c)}
                    for m in self.enemies():
                        if chebyshev(m.pos, centre) <= x["splash"]:
                            hits |= body(m)
        elif k == "nova":
            r = x.get("radius") or env.radius() or 4
            if s.key in ("Frost Nova", "Nova", "Poison Nova"):
                r = max(r, 5)
            cells = {c for c in sq(p.pos, r) if self.grid.walkable(*c) and c != p.pos}
            for m in self.enemies():
                if self.udist(m, p) <= r and self.grid.line_of_sight(p.pos, m.pos):
                    hits |= body(m)
        elif k in ("area", "curse"):
            if k == "curse" and x.get("self_centred"):
                cell = p.pos
            r = (x.get("radius") or env.radius() or 2) if k == "area" else (env.radius() or 2)
            if s.key == "Attract":
                r = 0
            cells = {c for c in sq(cell, r) if self.grid.walkable(*c)}
            for m in self.enemies():
                if chebyshev(m.pos, cell) <= r:
                    hits |= body(m)
        elif k == "line":
            length = self._line_length(s, env)
            if x.get("across"):
                dx, dy = cell[0] - p.x, cell[1] - p.y
                px, py = (-(dy > 0) + (dy < 0), (dx > 0) - (dx < 0))
                if px == 0 and py == 0:
                    px = 1
                line = [(cell[0] + px * i, cell[1] + py * i) for i in range(-(length // 2), length // 2 + 1)]
            else:
                line = _extend(p.pos, cell, length)
            cells = {c for c in line if self.grid.walkable(*c)}
            for m in self.enemies():
                if m.pos in cells:
                    hits |= body(m)
        elif k == "corpse_blast":
            corpse = next((c for c in self.corpses if not getattr(c, "exploded", False)
                           and chebyshev(c.pos, cell) <= 1), None)
            if corpse is None:
                return None
            r = max(2, env.radius() or 3)
            cells = {c for c in sq(corpse.pos, r) if self.grid.walkable(*c)}
            for m in self.enemies():
                if self.udist(m, corpse) <= r:
                    hits |= body(m)
        elif k == "chain":
            path, hit = self._missile_path(p.pos, cell)
            cells.update(path)
            for m in hit:
                hits |= body(m)
        else:
            return None
        return cells, hits

    def _k_missile(self, s, env, target, cell, ap, mana):
        p = self.player
        x = s.extra
        if cell is None:
            return False
        if s.weapon:
            weapon = p.equipment.get("weapon")
            wt = set(weapon.base.get("ancestors", ())) if weapon is not None and isinstance(getattr(weapon, "base", None), dict) else set()
            need = set(s.itype)
            if need and not (wt & need) and not (wt & {"miss", "bow", "xbow"} and "miss" in need):
                names = {"miss": "a bow or crossbow", "jave": "javelins", "spea": "a spear", "thro": "a throwing weapon"}
                self.log("%s needs %s." % (s.title, names.get(next(iter(need)), "the right weapon")), GREY)
                return False
        if not self._in_range(cell, SPELL_RANGE, los=False):
            return False
        n = self._spread_count(s, env)
        self._spend(ap, mana, cell, "attack" if s.weapon else "cast")
        kind = {"fire": "fireball", "cold": "cold", "ltng": "ltng", "pois": "spike", "mag": "bone"}.get(s.element, "arrow" if s.weapon else "spike")
        vm = self.vis_missile(s) or (self.weapon_missile(p) if s.weapon else None)
        if n > 1 and x.get("spread"):
            # a fan of missiles (Teeth, Charged Bolt, Multiple Shot): each flies its own line and hits
            # the first monster on it - several can hit the same one
            shots = self._spread_shots(s, env, cell)
            hit_any = [m for _, m in shots if m is not None]
            self._wake(list({id(m): m for m in hit_any}.values()))
            # the whole volley flies at once, then the hits land
            for path, m in shots:
                end = m.pos if m is not None else (path[-1] if path else cell)
                self.emit("projectile", p, p.pos, end, kind, vm)
            for path, m in shots:
                if m is not None and m.alive:
                    self._missile_hit(s, env, m)
            return True
        if n > 1:
            # Strafe: one shot at each of the n nearest monsters in sight
            cand = [m for m in self.enemies() if self.udist(m, p) <= SPELL_RANGE
                    and self.grid.line_of_sight(p.pos, m.pos)]
            cand.sort(key=lambda m: (chebyshev(m.pos, cell), self.udist(m, p)))
            foes = cand[:n]
            if foes:
                self._wake(foes)
                for m in foes:
                    self.emit("projectile", p, p.pos, m.pos, kind, vm)
                for m in foes:
                    self._missile_hit(s, env, m)
                return True
        hit, end = self._first_hit_on_line(p.pos, cell, pierce=bool(x.get("pierce")))
        self.emit("projectile", p, p.pos, hit[-1].pos if hit else end, kind, vm)
        if hit:
            self._wake(hit)
        for m in hit:
            self._missile_hit(s, env, m)
        if x.get("splash"):
            centre = hit[0].pos if hit else end
            if s.key == "Frozen Orb":
                self.emit("nova", p, centre, x["splash"], "cold", "frozenorbbolt")   # the orb bursts into ice bolts
            others = [m for m in self.enemies() if chebyshev(m.pos, centre) <= x["splash"] and m not in hit]
            self._wake(others)
            for m in others:
                self.skill_damage(env, m, 100 if not s.weapon else 60, show=False)
            if x.get("linger"):
                self._add_hazard(centre, x["splash"], env, x["linger"], self.ground_missile(s))
        return True

    def _missile_hit(self, s, env, m):
        p = self.player
        if s.weapon:
            # bow / javelin skill: a normal ranged attack plus the skill's bonuses
            ok = self._resolve_attack(p, m, s.key, ranged_kind=None, quiet_anim=True)
            return ok
        self.skill_damage(env, m)
        return True

    # ------------------------------------------------------------ areas
    def _k_nova(self, s, env, target, cell, ap, mana):
        p = self.player
        r = s.extra.get("radius") or env.radius() or 4
        if s.key in ("Frost Nova", "Nova", "Poison Nova"):
            r = max(r, 5)
        foes = [m for m in self.enemies() if self.udist(m, p) <= r and self.grid.line_of_sight(p.pos, m.pos)]
        self._spend(ap, mana, None, "cast")
        self.emit("nova", p, p.pos, r, s.element or "phys", self.vis_missile(s, area=True))
        self._wake(foes)
        for m in foes:
            self.skill_damage(env, m)
        if not foes:
            self.log("%s hits nothing." % s.title, GREY)
        return True

    def _k_area(self, s, env, target, cell, ap, mana):
        if not self._in_range(cell):
            return False
        r = s.extra.get("radius") or env.radius() or 2
        foes = [m for m in self.enemies() if chebyshev(m.pos, cell) <= r]
        self._spend(ap, mana, cell, "cast")
        self.emit("nova", self.player, cell, r, s.element or "phys", self.vis_missile(s, area=True))
        self._wake(foes)
        for m in foes:
            self.skill_damage(env, m)
        if s.extra.get("linger"):
            self._add_hazard(cell, r, env, s.extra["linger"], self.ground_missile(s))
        return True

    def _k_line(self, s, env, target, cell, ap, mana):
        p = self.player
        if cell is None:
            return False
        length = self._line_length(s, env)
        if s.extra.get("across"):
            # a wall across the line of fire, centred on the target cell
            if not self._in_range(cell):
                return False
            dx, dy = cell[0] - p.x, cell[1] - p.y
            px, py = (-(dy > 0) + (dy < 0), (dx > 0) - (dx < 0))
            if px == 0 and py == 0:
                px = 1
            cells = [(cell[0] + px * i, cell[1] + py * i) for i in range(-(length // 2), length // 2 + 1)]
        else:
            cells = _extend(p.pos, cell, length)
        cells = [c for c in cells if self.grid.walkable(*c)]
        foes = [m for m in self.enemies() if m.pos in cells]
        self._spend(ap, mana, cell, "cast")
        if cells:
            self.emit("projectile", p, p.pos, cells[-1], {"fire": "fireball", "cold": "cold"}.get(s.element, "spike"),
                      self.vis_missile(s, area=True))
        self._wake(foes)
        for m in foes:
            self.skill_damage(env, m)
            if s.extra.get("knock") and m.alive:
                self._knockback(p, m)
        if s.extra.get("linger"):
            self.hazards.append({"cells": {c for c in cells}, "env": env, "turns": s.extra["linger"],
                                 "vis": self.ground_missile(s), "elem": s.element, "hit": set()})
        return True

    @staticmethod
    def _line_length(s, env):
        n = s.extra.get("length", 5)
        if s.key == "Fire Wall":
            n = 5 + 2 * (env.lvl // 2)     # D2's wall grows with the skill level
        return n

    GROUND_MISSILES = {"Fire Wall": "firewall", "Meteor": "meteorfire", "Blizzard": "blizzard1",
                       "Blaze": "blaze", "Immolation Arrow": "immolationfire", "Fire Ball": "meteorfire",
                       "Firestorm": "firestorm", "Poison Nova": "poisonnova", "Volcano": "meteorfire",
                       "Armageddon": "meteorfire", "Wake of Fire Sentry": "firewall"}

    def ground_missile(self, s):
        """The Missiles.txt animation that keeps burning / freezing on the ground for a skill."""
        return self.GROUND_MISSILES.get(s.key) or self.vis_missile(s, area=True)

    def _add_hazard(self, centre, r, env, turns, vis=None):
        cells = {(centre[0] + dx, centre[1] + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)}
        cells = {c for c in cells if self.grid.walkable(*c)}
        self.hazards.append({"cells": cells, "env": env, "turns": turns, "vis": vis,
                             "elem": env.s.element, "hit": set()})

    def in_hazard(self, unit, cell):
        return not unit.is_player and not getattr(unit, "ally", False) and any(
            cell in h["cells"] and id(unit) not in h["hit"] for h in self.hazards)

    def hazard_step(self, unit, cell):
        """A monster walking into fire / ice on the ground gets hurt (once per hazard per round)."""
        for h in getattr(self, "hazards", ()):
            if cell in h["cells"] and id(unit) not in h["hit"] and unit.alive and not getattr(unit, "ally", False) \
                    and not unit.is_player:
                h["hit"].add(id(unit))
                self.skill_damage(h["env"], unit, 50, show=False)

    def blaze_step(self, cell):
        """Blaze: every step you take leaves burning ground behind you (D2)."""
        p = self.player
        if "Blaze" not in getattr(p, "buffs", {}) or "Blaze" not in p.skills.tree:
            return
        env = self._skill_env("Blaze")
        if not hasattr(self, "hazards"):
            self.hazards = []
        self.hazards.append({"cells": {cell}, "env": env, "turns": 3, "vis": "blaze", "elem": "fire",
                             "hit": set(), "trail": True})
        trail = [h for h in self.hazards if h.get("trail")]
        for h in trail[:-24]:              # outside combat turns don't pass: keep the trail short
            self.hazards.remove(h)

    def tick_hazards(self):
        keep = []
        for h in getattr(self, "hazards", []):
            for m in self.enemies():
                if m.pos in h["cells"] and id(m) not in h["hit"]:
                    m.aware = True
                    self.skill_damage(h["env"], m, 50, show=False)
            h["hit"] = set()
            h["turns"] -= 1
            if h["turns"] > 0:
                keep.append(h)
        self.hazards = keep

    def _k_chain(self, s, env, target, cell, ap, mana):
        p = self.player
        if target is None:
            hit, end = self._first_hit_on_line(p.pos, cell) if cell else ([], None)
            target = hit[0] if hit else None
        if target is None:
            self.log("No target.", GREY)
            return False
        if not self._in_range(target.pos):
            return False
        jumps = max(1, env.calc("calc1") or 3)
        self._spend(ap, mana, target.pos, "cast")
        done, cur, src = set(), target, p.pos
        for _ in range(jumps + 1):
            if cur is None:
                break
            self.emit("projectile", p, src, cur.pos, "ltng", self.vis_missile(s))
            done.add(id(cur))
            self._wake([cur])
            self.skill_damage(env, cur)
            nxt = [m for m in self.enemies() if id(m) not in done and self.udist(m, cur) <= 5]
            src = cur.pos
            cur = min(nxt, key=lambda m: chebyshev(m.pos, src)) if nxt else None
        return True

    def _k_corpse_blast(self, s, env, target, cell, ap, mana):
        corpse = None
        for c in self.corpses:
            if not getattr(c, "exploded", False) and (cell is None or chebyshev(c.pos, cell) <= 1) \
                    and self.udist(c, self.player) <= SPELL_RANGE:
                corpse = c
                break
        if corpse is None:
            self.log("Target a corpse.", GREY)
            return False
        r = max(2, env.radius() or 3)
        foes = [m for m in self.enemies() if self.udist(m, corpse) <= r]
        self._spend(ap, mana, corpse.pos, "cast")
        corpse.exploded = True
        corpse.searched = True
        if corpse in self.corpses:
            self.corpses.remove(corpse)
        self.emit("nova", self.player, corpse.pos, r, s.element or "fire")
        self._wake(foes)
        if s.key == "Corpse Explosion":
            lo, hi = env.par(1) or 70, env.par(2) or 120
            for m in foes:
                dmg = corpse.max_hp * self.rng.randint(lo, hi) // 100
                half = dmg // 2
                self.phys_hit(m, half, half, self.player)
                self.elem_hit(m, "fire", dmg - half, dmg - half, self.player, show=False)
        else:
            for m in foes:
                self.skill_damage(env, m)
        return True

    # ------------------------------------------------------------ curses
    def _k_curse(self, s, env, target, cell, ap, mana):
        p = self.player
        if s.extra.get("self_centred"):
            cell = p.pos
        if cell is None or not self._in_range(cell, SPELL_RANGE, los=False):
            return False
        r = env.radius() or 2
        turns = turns_from_frames(env.duration_frames()) or 4
        stats = {}
        for st, v in env.stats("aurastat", 6):
            ours = _curse_stat(st)
            if ours:
                stats[ours] = stats.get(ours, 0) + v
        flags = set()
        name = s.key
        flags.add({"Terror": "terror", "Confuse": "confuse", "Attract": "attract", "Dim Vision": "blind",
                   "Iron Maiden": "maiden", "Life Tap": "lifetap", "Decrepify": "slow", "Slow Missiles": "slowmiss",
                   "Cloak of Shadows": "blind"}.get(name, "curse"))
        if name == "Attract":
            r = 0
        foes = [m for m in self.enemies() if chebyshev(m.pos, cell) <= r]
        if not foes and target is not None:
            foes = [target]
        self._spend(ap, mana, cell, "cast")
        self.emit("nova", p, cell, r, "curse")
        for m in foes:
            if m.unique and "terror" in flags:
                continue
            m.curses = getattr(m, "curses", {})
            m.curses = {k: v for k, v in m.curses.items() if k == name or len(m.curses) < 1}
            m.curses[name] = {"turns": turns, "stats": dict(stats), "flags": flags, "title": s.title}
            if "terror" in flags:
                m.effects["flee"] = max(m.effects.get("flee", 0), turns)
        self._wake(foes)
        self.log("%s: %d monster%s cursed." % (s.title, len(foes), "" if len(foes) == 1 else "s"), YELLOW)
        return True

    def tick_curses(self, m):
        cs = getattr(m, "curses", None)
        if not cs:
            return
        for k in list(cs):
            cs[k]["turns"] -= 1
            if cs[k]["turns"] <= 0:
                cs.pop(k)

    # ------------------------------------------------------------ buffs / auras
    def _k_buff(self, s, env, target, cell, ap, mana):
        p = self.player
        turns = turns_from_frames(env.duration_frames()) or 10
        stats = {}
        for st, v in env.stats("aurastat", 6):
            ours = STAT_MAP.get(st)
            if ours:
                stats[ours] = stats.get(ours, 0) + v
        if s.extra.get("shift"):
            # one shape at a time
            for other in ("Wearwolf", "Wearbear"):
                p.buffs.pop(other, None)
            p.shape = "wolf" if s.key == "Wearwolf" else "bear"
        extra = {}
        key = s.key
        if key == "Energy Shield":
            extra["eshield"] = env.ln(1, 2) if env.par(1) else 20 + 2 * env.lvl
        if key in ("Bone Armor", "Cyclone Armor"):
            extra["absorb"] = max(10, env.calc("calc1") or env.ln(1, 2))
            turns = 99
        if key in ("Frozen Armor", "Shiver Armor", "Chilling Armor"):
            for other in ("Frozen Armor", "Shiver Armor", "Chilling Armor"):
                p.buffs.pop(other, None)
            extra["retaliate"] = key
        if key in ("Enchant", "Venom", "Fire Claws"):
            ed = env.elem_damage()
            if ed:
                stats[ed[0] + "_dmg"] = (ed[1], ed[2])
        if key == "Holy Shield":
            stats["block"] = stats.get("block", 0) + 25
        if s.extra.get("periodic"):
            extra["periodic"] = key
        p.buffs[key] = {"turns": turns, "stats": stats, "title": s.title, **extra}
        self._spend(ap, mana, None, "cast")
        hp_frac = p.hp / float(max(1, p.max_hp))
        p.recalc()
        if s.extra.get("shift"):
            p.hp = min(p.max_hp, max(1, int(round(p.max_hp * hp_frac))))
        self.log("%s (%d turns)." % (s.title, turns), YELLOW)
        return True

    def tick_player_buffs(self):
        p = self.player
        changed = False
        for k in list(getattr(p, "buffs", {})):
            b = p.buffs[k]
            if b.get("periodic"):
                self._periodic(k, b)
            b["turns"] -= 1
            if b["turns"] <= 0 or (b.get("absorb") is not None and b["absorb"] <= 0 and "absorb" in b):
                p.buffs.pop(k)
                changed = True
                if k in ("Wearwolf", "Wearbear"):
                    p.shape = None
                self.log("%s wears off." % b.get("title", k), GREY)
        if changed:
            hp_frac = p.hp / float(max(1, p.max_hp))
            p.recalc()
            p.hp = min(p.max_hp, max(1, int(round(p.max_hp * hp_frac))))

    def _periodic(self, key, b):
        """Thunder Storm, Armageddon, Hurricane, Blade Shield, Blaze: hit monsters near you."""
        p = self.player
        if key not in p.skills.tree:
            return
        env = self._skill_env(key)
        r = {"Thunder Storm": 6, "Armageddon": 4, "Hurricane": 3, "Blade Shield": 1, "Blaze": 1}.get(key, 3)
        foes = [m for m in self.enemies() if m.aware and self.udist(m, p) <= r]
        if not foes:
            return
        if key == "Thunder Storm":
            foes = [self.rng.choice(foes)]
        for m in foes[:4]:
            self.emit("projectile", p, p.pos, m.pos, {"ltng": "ltng", "fire": "fireball", "cold": "cold"}.get(env.s.element, "spike"))
            self.skill_damage(env, m, 100, show=False)

    def _auras(self):
        """(name, env) of every aura on you: the one you chose plus the ones your items give."""
        p = self.player
        out = []
        name = getattr(p, "active_aura", None)
        if name and name in p.skills.tree and p.skills.level(name):
            out.append((name, self._skill_env(name)))
        from .skills import SkillEnv
        for n, lvl in (getattr(p.skills, "item_auras", {}) or {}).items():
            if n in p.skills.tree and n != name:
                out.append((n, SkillEnv(p.skills, p.skills.tree[n], lvl)))
        from .hireling import aura
        ma = aura(self)
        if ma and ma[0] != name and ma[0] not in [o[0] for o in out]:
            from .itemfx import _skill
            s = _skill(p.skills, ma[0])
            if s is not None:
                out.append((ma[0], SkillEnv(p.skills, s, ma[1])))
        return out

    def aura_turn(self):
        """Once per round: offensive auras damage, Prayer heals, Meditation restores mana."""
        for name, env in self._auras():
            self._aura_turn_one(name, env)

    def _aura_turn_one(self, name, env):
        p = self.player
        r = max(2, min(8, env.radius() or 5))
        if name == "Prayer":
            heal = max(1, env.calc("calc1") or (env.lvl + 1))
            heal = env.elem_damage()[1] if env.elem_damage() else heal
            if p.hp < p.max_hp:
                p.hp = min(p.max_hp, p.hp + max(2, heal))
                self.emit("heal", p, heal)
        elif name == "Meditation":
            p.mana = min(p.max_mana, p.mana + max(2, p.max_mana * (env.ln(1, 2) or 100) // 1000))
        elif name in ("Holy Fire", "Holy Freeze", "Holy Shock", "Sanctuary"):
            foes = [m for m in self.enemies() if m.aware and self.udist(m, p) <= r]
            if name == "Sanctuary":
                foes = [m for m in foes if getattr(m, "undead", False)]
            if foes:
                self.emit("nova", p, p.pos, r, {"Holy Fire": "fire", "Holy Freeze": "cold", "Holy Shock": "ltng"}.get(name, "mag"))
            for m in foes:
                self.skill_damage(env, m, 100, show=False)
                if name == "Sanctuary" and m.alive:
                    self._knockback(p, m)
        elif name == "Conviction":
            stats = {}
            for st, v in env.stats("aurastat", 6):
                ours = _curse_stat(st)
                if ours:
                    stats[ours] = stats.get(ours, 0) + v
            for m in self.enemies():
                if self.udist(m, p) <= r:
                    m.curses = getattr(m, "curses", {})
                    m.curses["Conviction"] = {"turns": 2, "stats": stats, "flags": {"aura"}, "title": "Conviction"}
        elif name == "Cleansing":
            p.effects.pop("poison", None)
        elif name == "Redemption":
            for c in list(self.corpses):
                if self.udist(c, p) <= r and not getattr(c, "searched", False):
                    c.searched = True
                    self.corpses.remove(c)
                    gain = max(5, env.ln(1, 2) if env.par(1) else 25)
                    p.hp = min(p.max_hp, p.hp + gain)
                    p.mana = min(p.max_mana, p.mana + gain)
                    self.emit("heal", p, gain)
                    break

    def aura_stats(self):
        """Player stat changes from the active aura (summed into Player.recalc)."""
        out = {}
        for name, env in self._auras():
            for k, v in self._aura_stats_one(name, env).items():
                if isinstance(v, tuple):
                    a = out.get(k, (0, 0))
                    out[k] = (a[0] + v[0], a[1] + v[1])
                else:
                    out[k] = out.get(k, 0) + v
        return out

    def _aura_stats_one(self, name, env):
        out = {}
        for st, v in env.stats("aurastat", 6):
            ours = STAT_MAP.get(st)
            if ours:
                out[ours] = out.get(ours, 0) + v
        # Holy Fire / Freeze / Shock also add elemental damage to your attacks
        ed = env.elem_damage()
        if ed and name in ("Holy Fire", "Holy Freeze", "Holy Shock"):
            mult = env.par(5) or 6
            out[ed[0] + "_dmg"] = (ed[1] * mult, ed[2] * mult)
        if name == "Fanaticism":
            out["ed"] = out.get("ed", 0) + env.ln(3, 4) // 2
        return out

    # ------------------------------------------------------------ movement skills
    def _k_teleport(self, s, env, target, cell, ap, mana):
        p = self.player
        if cell is None or not self.grid.walkable(*cell) or cell in self.occupied(p):
            self.log("Can't teleport there.", GREY)
            return False
        if not self.grid.explored[cell[1]][cell[0]]:
            self.log("You can only teleport where you have seen.", GREY)
            return False
        if chebyshev(cell, p.pos) > 14:
            self.log("Too far (14 cells).", GREY)
            return False
        self._spend(ap, mana, cell, "cast")
        src = p.pos
        p.x, p.y = cell
        self.emit("teleport", p, src, cell)
        self.grid.update_visibility(p.pos, self.sight_radius())
        self.check_awareness()
        if self.mode == "explore" and cell in self.exits and self.exits[cell]:
            self.pending_exit = self.exits[cell]
        return True

    def _k_charge(self, s, env, target, cell, ap, mana):
        p = self.player
        if target is None:
            self.log("Charge at a monster.", GREY)
            return False
        reach = 8 if not s.extra.get("teleport") else 10
        spots = [(target.x + dx, target.y + dy) for dx, dy in DIRS8]
        spots = [c for c in spots if self.grid.walkable(*c) and c not in self.occupied(p) and chebyshev(c, p.pos) <= reach]
        if not spots and self.udist(p, target) > 1:
            self.log("Can't reach it.", GREY)
            return False
        if self.mode == "combat" and p.ap < ap:
            self.log("Need %d AP." % ap, GREY)
            return False
        if self.mode == "explore":
            target.aware = True
            self.check_awareness_force()
        if self.udist(p, target) > 1:
            dest = min(spots, key=lambda c: chebyshev(c, p.pos))
            src = p.pos
            if not s.extra.get("teleport"):
                path = self.grid.find_path(p.pos, dest, blocked=self.occupied(p))
                if not path:
                    self.log("Can't charge there.", GREY)
                    return False
                p.x, p.y = dest
                self.emit("move", p, path)
            else:
                p.x, p.y = dest
                self.emit("teleport", p, src, dest)
            self.grid.update_visibility(p.pos, self.sight_radius())
        if self.mode == "combat":
            p.ap -= ap
        p.mana -= mana
        self._resolve_attack(p, target, s.key)
        if target.alive:
            self._knockback(p, target)
        return True

    # ------------------------------------------------------------ summons
    def _summon_template(self, mid, level):
        c = self.content
        t = None
        if c is not None and mid:
            key = c.monstats_key(mid) if hasattr(c, "monstats_key") else (mid if mid in c.monstats else None)
            if key:
                try:
                    t = c.monster_template(key, level=level)
                except Exception:
                    t = None
        if t is None:
            t = dict(name=mid or "Minion", token="SK", hp=(20 + 4 * level, 24 + 5 * level), dmg=(2 + level // 2, 4 + level),
                     ar=40 + 10 * level, df=10 + 3 * level, ap=6, cost=3, rng=1, xp=0, color=(120, 200, 255),
                     ai="melee", level=level, id=mid)
        return t

    def _make_ally(self, m, turns=None):
        m.ally = True
        m.aware = False
        m.ai = "ally" if m.range <= 1 else "ally_ranged"
        m.life_turns = turns
        m.effects = {}
        m.curses = {}
        return m

    def _spawn_ally(self, s, env, near, template=None, turns=None, ai=None):
        p = self.player
        lvl = max(1, p.level)
        t = template or self._summon_template(s.data.get("summon", ""), lvl)
        cells = [near] + [(near[0] + dx, near[1] + dy) for r in (1, 2) for dx in range(-r, r + 1) for dy in range(-r, r + 1)]
        occ = self.occupied()
        cell = next((c for c in cells if self.grid.walkable(*c) and c not in occ), None)
        if cell is None:
            return None
        m = Monster(t.get("id") or "ally", cell[0], cell[1], level=lvl, rng=self.rng, template=t)
        if m.radius and not self.fits(cell, m.radius, occ):
            m.radius = 0
        m.name = s.title if not template else m.name
        self._make_ally(m, turns)
        # D2 skill bonuses for minions: +damage%, +AR, +defense from the skill's aura stats
        for st, v in env.stats("aurastat", 6):
            if st == "damagepercent":
                m.dmg = (max(1, m.dmg[0] * (100 + v) // 100), max(1, m.dmg[1] * (100 + v) // 100))
            elif st == "tohit":
                m.ar += v
            elif st in ("armorclass", "item_armor_percent"):
                m.defense = m.defense * (100 + v) // 100 if st.endswith("percent") else m.defense + v
        life = env.calc("calc1") if s.data.get("calc1") and s.kind in ("raise", "golem", "summon") else 0
        if 0 < life < 1000:
            m.max_hp = m.hp = m.max_hp * (100 + life) // 100
        m.summon_skill = s.key
        if ai:
            m.ai = ai
        self.monsters.append(m)
        self.emit("resurrect", m)
        return m

    def _petmax(self, s, env):
        if s.data.get("petmax"):
            v = env.calc("petmax")
            return max(1, v)
        return 1

    def _owned(self, key):
        return [a for a in self.allies() if getattr(a, "summon_skill", None) == key]

    def _k_summon(self, s, env, target, cell, ap, mana):
        p = self.player
        mine = self._owned(s.key)
        if len(mine) >= self._petmax(s, env):
            mine[0].alive = False
            self.emit("death", mine[0])
        self._spend(ap, mana, None, "cast")
        turns = turns_from_frames(env.duration_frames()) if s.key in ("Dopplezon",) else None
        a = self._spawn_ally(s, env, p.pos, turns=turns)
        if a is None:
            self.log("No room to summon.", GREY)
            return False
        if s.key == "Dopplezon":
            a.decoy = True
            a.dmg = (0, 0)
        self.log("%s summoned." % s.title, YELLOW)
        return True

    def _k_golem(self, s, env, target, cell, ap, mana):
        for a in self.allies():
            if getattr(a, "summon_skill", "") in ("Clay Golem", "BloodGolem", "IronGolem", "FireGolem"):
                a.alive = False
                self.emit("death", a)
        return self._k_summon(s, env, target, cell, ap, mana)

    def _k_raise(self, s, env, target, cell, ap, mana):
        corpse = self._corpse_near(cell)
        if corpse is None:
            self.log("Cast it on a corpse.", GREY)
            return False
        if len(self._owned(s.key)) >= self._petmax(s, env):
            self.log("You already command %d." % len(self._owned(s.key)), GREY)
            return False
        self._spend(ap, mana, corpse.pos, "cast")
        corpse.searched = True
        self.corpses.remove(corpse)
        a = self._spawn_ally(s, env, corpse.pos)
        if a is not None and s.key == "Raise Skeletal Mage":
            a.range = 6
            a.ai = "ally_ranged"
            a.missile_elem = self.rng.choice(("fire", "cold", "ltng", "pois"))
        self.log("%s rises." % s.title, YELLOW)
        return True

    def _k_revive(self, s, env, target, cell, ap, mana):
        corpse = self._corpse_near(cell, allow_unique=False)
        if corpse is None:
            self.log("Cast it on the corpse of a normal monster.", GREY)
            return False
        if len(self._owned(s.key)) >= max(1, env.lvl):
            self.log("You can't revive more.", GREY)
            return False
        self._spend(ap, mana, corpse.pos, "cast")
        self.corpses.remove(corpse)
        corpse.alive = True
        corpse.hp = corpse.max_hp = corpse.max_hp * 2
        self._make_ally(corpse, turns=turns_from_frames(env.calc("auralencalc") or 4500))
        corpse.summon_skill = s.key
        self.emit("resurrect", corpse)
        self.log("%s is revived." % corpse.name, YELLOW)
        return True

    def _corpse_near(self, cell, allow_unique=True):
        p = self.player
        best = None
        for c in self.corpses:
            if getattr(c, "searched", False) or getattr(c, "exploded", False) or getattr(c, "ally", False):
                continue
            if not allow_unique and c.unique:
                continue
            if self.udist(c, p) > SPELL_RANGE or self.unit_at(c.pos) is not None:
                continue
            d = chebyshev(c.pos, cell) if cell else self.udist(c, p)
            if cell and d > 1:
                continue
            if best is None or d < best[0]:
                best = (d, c)
        return best[1] if best else None

    def _k_turret(self, s, env, target, cell, ap, mana):
        p = self.player
        if cell is None or not self._in_range(cell, 8, los=False):
            return False
        if not self.grid.walkable(*cell) or cell in self.occupied():
            self.log("Place it on a free spot.", GREY)
            return False
        mine = self._owned(s.key)
        limit = 5 if "Sentry" in s.key or "Fire" in s.key else (99 if s.key == "Hydra" else 3)
        if len(mine) >= limit:
            mine[0].alive = False
            self.emit("death", mine[0])
        self._spend(ap, mana, cell, "cast")
        t = self._summon_template(s.data.get("summon", ""), p.level)
        t = dict(t)
        t["hp"] = (999, 999)
        t["ap"] = 6
        shots = 5 if "Sentry" in s.key or s.key.startswith("Wake") else 0
        turns = turns_from_frames(env.duration_frames()) or (5 if s.key == "Hydra" else 8)
        a = self._spawn_ally(s, env, cell, template=t, turns=turns, ai="turret")
        if a is None:
            return False
        a.name = s.title
        a.shots = shots or None
        a.turret_env = env
        a.invulnerable = True
        a.range = 8
        self.log("%s placed." % s.title, YELLOW)
        return True

    def _k_wall(self, s, env, target, cell, ap, mana):
        p = self.player
        if cell is None or not self._in_range(cell, 10, los=False):
            return False
        if s.extra.get("prison") and target is not None:
            spots = [(target.x + dx, target.y + dy) for dx, dy in DIRS8]
        else:
            dx, dy = cell[0] - p.x, cell[1] - p.y
            px, py = (-(dy > 0) + (dy < 0), (dx > 0) - (dx < 0))
            if px == 0 and py == 0:
                px = 1
            spots = [(cell[0] + px * i, cell[1] + py * i) for i in range(-2, 3)]
        occ = self.occupied()
        spots = [c for c in spots if self.grid.walkable(*c) and c not in occ]
        if not spots:
            self.log("No room for a wall.", GREY)
            return False
        self._spend(ap, mana, cell, "cast")
        hp = max(20, env.calc("calc1") or (19 + 23 * env.lvl))
        for c in spots:
            t = dict(name="Bone Wall", token="BW", hp=(hp, hp), dmg=(0, 0), ar=0, df=0, ap=0, cost=99, rng=1, xp=0,
                     color=(230, 230, 210), ai="wall", level=p.level, id="bonewall")
            m = Monster("bonewall", c[0], c[1], level=p.level, rng=self.rng, template=t)
            self._make_ally(m, turns=turns_from_frames(env.duration_frames() or 600) or 12)
            m.ai = "wall"
            m.summon_skill = s.key
            self.monsters.append(m)
            self.emit("resurrect", m)
        return True

    # ------------------------------------------------------------ allies' turn
    def allies_turn(self):
        for a in list(self.allies()):
            if not a.alive:
                continue
            a.ap = a.max_ap
            if a.life_turns is not None:
                a.life_turns -= 1
                if a.life_turns < 0:
                    a.alive = False
                    self.emit("death", a)
                    continue
            if a.ai == "wall" or getattr(a, "decoy", False):
                continue
            if a.ai == "turret":
                self._turret_shoot(a)
                continue
            guard = 0
            while a.ap > 0 and a.alive and guard < 10:
                guard += 1
                foe = self._nearest_foe(a)
                if foe is None:
                    break
                if a.range > 1:
                    d = self.udist(a, foe)
                    if d <= a.range and self.grid.line_of_sight(a.pos, foe.pos):
                        if a.ap < a.attack_cost:
                            break
                        a.ap -= a.attack_cost
                        el = getattr(a, "missile_elem", None)
                        if el:
                            a.face(*foe.pos)
                            self.emit("projectile", a, a.pos, foe.pos, {"fire": "fireball", "cold": "cold", "ltng": "ltng"}.get(el, "spike"))
                            lo, hi = a.dmg
                            self.elem_hit(foe, el, lo, hi * 2, a, 50, show=False)
                        else:
                            self._resolve_attack(a, foe, ranged_kind="arrow")
                        continue
                if self.udist(a, foe) == 1 and self._adjacent_reachable(a.pos, foe.pos):
                    if a.ap < a.attack_cost:
                        break
                    a.ap -= a.attack_cost
                    foe.aware = True
                    self._resolve_attack(a, foe)
                    continue
                path = self._path_to_adjacent(a, foe.pos)
                if not path:
                    break
                self._walk(a, path[: a.ap])

    def _nearest_foe(self, a, rng=24):
        best = None
        for m in self.enemies():
            if not m.aware and self.mode == "combat" and self.udist(m, self.player) > 16:
                continue
            d = self.udist(m, a)
            if d <= rng and (best is None or d < best[0]):
                best = (d, m)
        return best[1] if best else None

    def _turret_shoot(self, a):
        env = getattr(a, "turret_env", None)
        foes = [m for m in self.enemies() if self.udist(m, a) <= a.range and self.grid.line_of_sight(a.pos, m.pos)]
        if not foes or env is None:
            return
        n = 2 if env.s.key == "Hydra" else 1
        for _ in range(n):
            foe = min(foes, key=lambda m: self.udist(m, a))
            if not foe.alive:
                foes = [m for m in foes if m.alive]
                if not foes:
                    return
                continue
            a.face(*foe.pos)
            el = env.s.element
            self.emit("projectile", a, a.pos, foe.pos, {"fire": "fireball", "cold": "cold", "ltng": "ltng"}.get(el, "spike"))
            foe.aware = True
            if env.s.key == "Blade Sentinel" or not env.elem_damage():
                pd = env.phys_damage() or (3, 8)
                self.phys_hit(foe, pd[0], pd[1], self.player)
            else:
                self.skill_damage(env, foe, 100, show=False)
            if a.shots is not None:
                a.shots -= 1
                if a.shots <= 0:
                    a.alive = False
                    self.emit("death", a)
                    return

    def allies_follow(self):
        """Out of combat your minions keep up with you."""
        p = self.player
        occ = None
        for a in self.allies():
            if a.ai in ("turret", "wall"):
                continue
            d = self.udist(a, p)
            if d <= 3:
                continue
            if d > 25:
                spots = [(p.x + dx, p.y + dy) for dx in (-2, -1, 1, 2) for dy in (-2, -1, 1, 2)]
                if occ is None:
                    occ = self.occupied()
                spot = next((c for c in spots if self.grid.walkable(*c) and c not in occ), None)
                if spot:
                    occ.discard(a.pos)
                    occ.add(spot)
                    a.x, a.y = spot
                    self.emit("place", a, spot)     # appear next to you instead of sliding across the map
                continue
            if occ is None:
                occ = self.occupied()
            occ.discard(a.pos)
            path = self.grid.find_path(a.pos, p.pos, blocked=occ, allow_goal_blocked=True, limit=2500)
            if path and len(path) > 2:
                self._walk(a, path[: len(path) - 2])
            occ.add(a.pos)

    # ------------------------------------------------------------ monster statuses
    def monster_status(self, m):
        """Start of a monster's turn: poison ticks, chill/freeze, curses. Returns False if it can't act."""
        eff = m.effects
        if eff.get("poison"):
            per, turns = eff["poison"]
            self._damage(m, per, self.player)
            turns -= 1
            if turns <= 0:
                eff.pop("poison")
            else:
                eff["poison"] = [per, turns]
            if not m.alive:
                return False
        if eff.get("bleed"):
            from .itemfx import tick_bleed
            tick_bleed(self, m)
            if not m.alive:
                return False
        self.tick_curses(m)
        if eff.get("freeze"):
            eff["freeze"] -= 1
            self.emit("miss", m)
            return False
        if eff.get("chill"):
            eff["chill"] -= 1
            m.ap = max(1, m.ap - 2)
        if self._has_flag(m, "slow"):
            m.ap = max(1, m.ap // 2)
        if self._has_flag(m, "blind") and self.udist(m, self.player) > 2:
            return False
        return True


def _curse_stat(st):
    return {"damageresist": "dr_pct", "damagepercent": "ed", "armorclass": "def", "item_armor_percent": "def_pct",
            "skill_armor_percent": "def_pct", "fireresist": "res_fire", "coldresist": "res_cold",
            "lightresist": "res_ltng", "poisonresist": "res_pois", "tohit": "ar", "item_tohit_percent": "ar_pct",
            "velocitypercent": "frw", "attackrate": "ias", "lifedrainmindam": "lifetap", "thorns_percent": "maiden",
            "other_animrate": "slowed"}.get(st, "")
