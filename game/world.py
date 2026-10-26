"""The rules: exploration vs. combat, turns, action points, attacks, AI, loot.

Every action resolves instantly and appends events to `self.events`. The frontend
plays those events back as animations, so game logic never waits on rendering.

Event tuples:
  ("move", unit, [cells])           ("attack", attacker, target_cell, skill)
  ("projectile", unit, src, dst, kind)
  ("damage", unit, amount, hp_after) ("miss", unit)
  ("death", unit)                    ("heal", unit, amount)
  ("knockback", unit, src, dst)      ("resurrect", unit)
  ("drop", cell, item)               ("pickup", cell, item)
  ("log", text, color)               ("combat_start",) ("combat_end",)
  ("turn", "player"|"monsters")      ("levelup", level)
  ("game_over",)                     ("victory",)
"""
import random

from .grid import chebyshev, DIRS8
from .items import roll_drop, SLOTS
from .mapgen import generate_cave, populate
from .units import Player, Monster

SIGHT = 8           # how far monsters notice you
ALERT_RADIUS = 6    # pack mates that get woken up with them
POTION_AP = 2
PICKUP_AP = 1
BASH_MANA = 2

RED = (255, 80, 80)
NPC_NAMES = {"akara": "Akara", "charsi": "Charsi", "gheed": "Gheed", "kashya": "Kashya", "warriv1": "Warriv",
             "cain1": "Deckard Cain", "rogue1": "Rogue Scout", "navi": "Flavie", "chicken": "Chicken"}
NPC_LINES = {
    "akara": "Akara: Rest a moment, I will mend your wounds.",
    "charsi": "Charsi: My forge isn't ready for trading yet - check back soon!",
    "gheed": "Gheed: Gambling and trade? Not quite yet, friend. Soon.",
    "kashya": "Kashya: The Den of Evil is close by. Clear it out, and we'll talk.",
    "warriv1": "Warriv: The caravan waits for the pass to clear. The road east is closed.",
    "rogue1": "Rogue Scout: Stay sharp out there.",
    "navi": "Flavie: The wilderness beyond is crawling with the Fallen.",
    "chicken": "Cluck.",
}
GREEN = (100, 220, 100)
YELLOW = (255, 230, 90)
GREY = (170, 170, 170)


# D2's melee hit chance is very low early on; in a turn-based game every miss costs a whole
# action, so the player's attacks get a floor (settings.ini [game] min_hit_chance)
PLAYER_HIT_FLOOR = 0.60


def hit_chance(attacker, defender, ar_bonus_pct=0):
    """D2's to-hit formula: 200% * AR/(AR+DEF) * alvl/(alvl+dlvl), clamped 5..95.
    Player attacks are rescaled to PLAYER_HIT_FLOOR..95%."""
    ar = attacker.ar * (100 + ar_bonus_pct) / 100
    df = max(0, defender.defense)
    eff = getattr(defender, "effects", {})
    if eff.get("bc"):
        df = df * (100 - eff.get("bc_def", 50)) / 100.0
    chance = 2 * (ar / (ar + df if ar + df else 1)) * (attacker.level / (attacker.level + defender.level))
    chance = max(0.05, min(0.95, chance))
    if getattr(attacker, "is_player", False) and PLAYER_HIT_FLOOR > 0.05:
        # map D2's 5..95% onto floor..95%
        chance = PLAYER_HIT_FLOOR + (chance - 0.05) / 0.90 * (0.95 - PLAYER_HIT_FLOOR)
    return chance


class World:
    def __init__(self, seed=None, depth_level=1, level_builder=None, content=None,
                 level_id="den", level_name="Den of Evil", town=False, player=None, exit_to=None):
        self.seed = seed if seed is not None else random.randrange(1 << 30)
        self.tilemap = None
        self.level_id, self.level_name, self.town = level_id, level_name, town
        if level_builder is not None:
            self.grid, self.rng, self.tilemap = level_builder(self.seed)
        else:
            self.grid, self.rng = generate_cave(seed=self.seed)
        self.content = content
        self.npcs = []
        self.exits = {}              # cell -> target level id
        self.pending_exit = None
        if town:
            start = self.tilemap.entry or next(iter(self.tilemap.exits))
            monsters = self._spawn_npcs()
            for c in self.tilemap.exits:
                self.exits[c] = exit_to
        else:
            level_row = content.level_row(level_name) if content else None
            start, monsters = populate(self.grid, self.rng, depth_level, content, level_row)
            if exit_to:
                # the entrance cell is the way back out; you arrive a few steps inside (like D2)
                self.exits[start] = exit_to
                ring = self.grid.reachable(start, 4)
                inside = [c for c, d in ring.items() if d == 4 and not any(m.pos == c for m in monsters)]
                if inside:
                    start = max(inside, key=lambda c: sum(1 for nb in self.grid.neighbors(*c)))
        self.entry = start
        if player is None:
            self.player = Player(*start)
            if content:
                from .skills import SkillBook, load_tree
                self.player.skills = SkillBook(load_tree(content.src))
                self._d2_starting_gear()
        else:
            self.player = player
            player.x, player.y = start
            player.alive = True
        self.monsters = monsters
        self.corpses = []            # dead monsters, shamans can raise fallen
        self.ground = {}             # cell -> [items]
        self.events = []
        self.mode = "explore"        # explore | combat
        self.turn = "player"
        self.round = 0
        self.game_over = False
        self.boss_dead = False
        self._regen_steps = 0
        self.ambient = 70 if town else 205     # how dark it is outside your light radius
        self.grid.update_visibility(self.player.pos, self.sight_radius())
        self.enter_message()

    def enter_message(self):
        from . import quests
        quests.init(self.player)
        if self.town:
            self.log("Rogue Encampment. Talk to Akara to heal. Leave the camp to fight.", YELLOW)
            self.log("Left click: move / talk / attack. Right click: Bash. Space: end turn. Tab: map.", GREY)
        else:
            self.log("You enter the %s. Corpsefire lurks in the depths." % self.level_name, YELLOW)

    def _spawn_npcs(self):
        out, seen = [], set()
        for npc_id, cell in getattr(self.tilemap, "npcs", []):
            if npc_id == "navi" and npc_id in seen:
                continue           # one Flavie is enough
            seen.add(npc_id)
            t = None
            if self.content and npc_id in self.content.monstats:
                t = self.content.monster_template(npc_id)
                t["name"] = NPC_NAMES.get(npc_id, t["name"])
            m = Monster("zombie", *cell, rng=self.rng, template=t)
            m.npc = npc_id
            m.name = NPC_NAMES.get(npc_id, m.name)
            m.ai = "npc"
            m.aware = False
            out.append(m)
            self.npcs.append(m)
        return out

    def relocate_player(self, cell):
        p = self.player
        p.x, p.y = cell
        p.alive = True
        self.mode, self.turn = "explore", "player"
        self.pending_exit = None
        self.grid.update_visibility(p.pos, self.sight_radius())

    def _d2_starting_gear(self):
        """D2's Barbarian starts with a Hand Axe, a Buckler and healing potions."""
        c, p = self.content, self.player
        for slot, code in (("weapon", "hax"), ("shield", "buc"), ("armor", None)):
            p.equipment[slot] = c.make_item(c.base_by_code[code], 1, self.rng) if code in c.base_by_code else None
        if "hp1" in c.base_by_code:
            p.belt = [c.make_item(c.base_by_code["hp1"], 1, self.rng) for _ in range(4)]
        p.recalc()
        p.hp, p.mana = p.max_hp, p.max_mana

    def sight_radius(self):
        # on D2 maps you see terrain well beyond your light radius, like in the game
        return self.player.light + (6 if self.tilemap is not None else 0)

    # ------------------------------------------------------------ helpers
    def log(self, text, color=(220, 220, 220)):
        self.events.append(("log", text, color))

    def emit(self, *ev):
        self.events.append(ev)

    def unit_at(self, cell):
        if self.player.alive and self.player.pos == cell:
            return self.player
        for m in self.monsters:
            if m.alive and m.pos == cell:
                return m
        return None

    def occupied(self, exclude=None):
        cells = {m.pos for m in self.monsters if m.alive and m is not exclude}
        if self.player.alive and self.player is not exclude:
            cells.add(self.player.pos)
        return cells

    def living_monsters(self):
        return [m for m in self.monsters if m.alive]

    def aware_monsters(self):
        return [m for m in self.monsters if m.alive and m.aware]

    def player_can_act(self):
        return not self.game_over and self.turn == "player"

    # ------------------------------------------------------------ awareness / combat state
    def check_awareness(self):
        newly = []
        p = self.player
        for m in self.living_monsters():
            if m.aware or m.ai == "npc":
                continue
            if chebyshev(m.pos, p.pos) <= SIGHT and self.grid.line_of_sight(m.pos, p.pos):
                newly.append(m)
        for m in list(newly):
            m.aware = True
            for o in self.living_monsters():
                if not o.aware and o.ai != "npc" and chebyshev(o.pos, m.pos) <= ALERT_RADIUS:
                    o.aware = True
                    newly.append(o)
        if newly and self.mode == "explore":
            self.mode = "combat"
            self.round = 1
            self.player.ap = self.player.max_ap
            self.emit("combat_start")
            names = sorted({m.name for m in newly})
            self.log(f"Combat! {', '.join(names)} spotted you.", RED)
        return newly

    def check_combat_end(self):
        if self.mode == "combat" and not self.aware_monsters():
            self.mode = "explore"
            self.turn = "player"
            self.player.ap = self.player.max_ap
            self.emit("combat_end")
            self.log("The area is quiet again.", GREY)

    # ------------------------------------------------------------ player actions
    def move_cost_ok(self, n):
        return self.mode == "explore" or self.player.ap >= n

    def reachable_cells(self):
        """Move range for highlighting (combat only)."""
        if self.mode != "combat":
            return {}
        return self.grid.reachable(self.player.pos, self.player.ap, blocked=self.occupied(self.player))

    def path_for_player(self, cell):
        return self.grid.find_path(self.player.pos, cell, blocked=self.occupied(self.player))

    def player_move_to(self, cell, pickup=True):
        if not self.player_can_act():
            return False
        path = self.path_for_player(cell)
        if not path:
            return False
        if self.mode == "combat":
            path = path[: self.player.ap]
            if not path:
                return False
        walked = []
        p = self.player
        for step in path:
            p.face(*step)
            p.x, p.y = step
            walked.append(step)
            if self.mode == "combat":
                p.ap -= 1
            else:
                self._regen_steps += 1
                if self._regen_steps % 2 == 0 and p.hp < p.max_hp:
                    p.hp += 1
                if self._regen_steps % 10 == 0:
                    self._tick_buffs()           # buffs also run out while exploring
            self.grid.update_visibility(p.pos, self.sight_radius())
            self._auto_pickup_gold(step)
            was_explore = self.mode == "explore"
            if self.check_awareness() and was_explore:
                break   # spotted: stop walking, combat begins
            if self.mode == "explore" and step in self.exits and self.exits[step]:
                self.pending_exit = self.exits[step]
                break
        self.emit("move", p, walked)
        if pickup and walked and walked[-1] == cell and cell in self.ground:
            self.player_pickup(cell)
        self._maybe_auto_end()
        return True

    def _auto_pickup_gold(self, cell):
        items = self.ground.get(cell)
        if not items:
            return
        for it in [i for i in items if i.kind == "gold"]:
            items.remove(it)
            self.player.gold += it.amount
            self.emit("pickup", cell, it)
            self.log(f"Picked up {it.amount} gold.", (230, 210, 140))
        if not items:
            del self.ground[cell]

    def player_pickup(self, cell):
        p = self.player
        if p.pos != cell or cell not in self.ground:
            return False
        if self.mode == "combat":
            if p.ap < PICKUP_AP:
                self.log("Not enough AP to pick that up.", GREY)
                return False
            p.ap -= PICKUP_AP
        items = self.ground[cell]
        for it in list(items):
            if it.kind == "gold":
                p.gold += it.amount
            elif it.kind == "potion" and len(p.belt) < 4:
                p.belt.append(it)
            elif p.inv_add(it):
                pass
            else:
                self.log("Your inventory is full.", GREY)
                continue
            items.remove(it)
            self.emit("pickup", cell, it)
            self.log(f"Picked up {it.name}.", it.color)
        if not items:
            del self.ground[cell]
        return True

    def attack_cost(self, skill):
        return self.player.attack_cost + (1 if skill == "bash" else 0)

    def preview_attack(self, target, skill="attack"):
        bonus = 20 if skill == "bash" else 0
        return hit_chance(self.player, target, bonus), self.attack_cost(skill)

    def interact(self, npc):
        """Walk up to an NPC and talk (Akara heals, like in D2)."""
        p = self.player
        if chebyshev(p.pos, npc.pos) > 1:
            path = self.grid.find_path(p.pos, npc.pos, blocked=self.occupied(p), allow_goal_blocked=True)
            if not path or len(path) < 2:
                return False
            self.player_move_to(path[-2])
            if chebyshev(p.pos, npc.pos) > 1 or self.pending_exit:
                return True
        p.face(*npc.pos)
        npc.face(*p.pos)
        from . import quests
        extra = quests.talk(self, npc)
        if extra:
            for line in extra:
                self.log(line, (220, 210, 170))
        else:
            self.log(NPC_LINES.get(npc.npc, npc.name + ": Hello."), (220, 210, 170))
        if npc.npc == "akara":
            p.hp, p.mana = p.max_hp, p.max_mana
            self.emit("heal", p, 0)
        return True

    def player_attack(self, target, skill="attack", ap_cost=None, mana_cost=0):
        """Attack (or use a melee skill on) a monster, walking next to it first if AP allows."""
        if getattr(target, "ai", "") == "npc":
            return self.interact(target)
        if not self.player_can_act() or not target.alive:
            return False
        p = self.player
        if skill == "bash" and ap_cost is None:          # placeholder-mode Bash
            if p.mana < BASH_MANA:
                self.log("Not enough mana for Bash.", GREY)
                skill = "attack"
            else:
                mana_cost = BASH_MANA
        if p.mana < mana_cost:
            self.log("Not enough mana.", GREY)
            return False
        cost = ap_cost if ap_cost is not None else self.attack_cost(skill)
        if chebyshev(p.pos, target.pos) > 1 or not self._adjacent_reachable(p.pos, target.pos):
            path = self.grid.find_path(p.pos, target.pos, blocked=self.occupied(p), allow_goal_blocked=True)
            if not path or len(path) < 2:
                return False
            path = path[:-1]
            if self.mode == "combat":
                if len(path) + cost > p.ap:
                    # can't reach and swing this turn: get as close as AP allows
                    self.log("Not enough AP to reach and attack - moving closer.", GREY)
                    return self.player_move_to(path[min(len(path), p.ap) - 1]) if p.ap else False
                self.player_move_to(path[-1])
            else:
                mode_before = self.mode
                self.player_move_to(path[-1])
                if self.mode != mode_before or p.pos != path[-1]:
                    return True     # got spotted on the way; let the player decide again
        if self.mode == "explore":
            # attacking an unaware monster starts combat (you get a free first strike)
            target.aware = True
            self.check_awareness_force()
        if p.ap < cost:
            self.log(f"Need {cost} AP for that.", GREY)
            return False
        p.ap -= cost
        p.mana -= mana_cost
        swings = 2 if skill in ("Double Swing", "Frenzy") else 1
        if skill == "Concentrate":
            lv = p.skills.level(skill)
            p.effects["conc_pct"] = 100 + 10 * (lv - 1)
            self._buff("concentrate", 1)
        if skill == "Berserk":
            self._buff("berserk", 1)
        if skill == "Taunt":
            lv = p.skills.level(skill)
            target.aware = True
            target.effects["taunt"] = 5 + 2 * (lv - 1)
            target.effects["taunt_turns"] = 4 + lv
            self.emit("attack", p, target.pos, "cast")
            self.log("%s is taunted!" % target.name, YELLOW)
            self._maybe_auto_end()
            return True
        for _ in range(swings):
            if not target.alive:
                break
            hit = self._resolve_attack(p, target, skill)
            if hit and skill == "Frenzy":
                p.frenzy += 1
        self._maybe_auto_end()
        return True

    # ------------------------------------------------------------ skills
    def _buff(self, name, turns, **extra):
        p = self.player
        p.effects[name] = max(p.effects.get(name, 0), turns)
        p.effects.update(extra)
        p.recalc()

    def _tick_buffs(self):
        p = self.player
        changed = False
        for k in ("shout", "bo", "bcmd", "concentrate", "berserk"):
            if p.effects.get(k):
                p.effects[k] -= 1
                if p.effects[k] <= 0:
                    p.effects.pop(k)
                    changed = True
                    if k == "bcmd":
                        p.skills.bonus = 0
                    if k in ("shout", "bo", "bcmd"):
                        names = {"shout": "Shout", "bo": "Battle Orders", "bcmd": "Battle Command"}
                        self.log("%s wears off." % names[k], GREY)
        self.wards = [(x, y, t - 1) for x, y, t in getattr(self, "wards", []) if t > 1]
        if changed:
            hp_frac = p.hp / float(max(1, p.max_hp))
            p.recalc()
            p.hp = min(p.max_hp, max(1, int(round(p.max_hp * hp_frac))))

    def skill_cost(self, name):
        """(AP, mana) for using a learned skill right now."""
        p = self.player
        if not name or name == "attack":
            return p.attack_cost, 0
        book = p.skills
        return book.ap_cost(name, p.attack_cost), book.mana_cost(name)

    def use_skill(self, name, target=None, cell=None):
        """Right mouse button: use the selected skill on a monster, a cell or around you."""
        p = self.player
        if not self.player_can_act():
            return False
        if not name or name == "attack":
            return self.player_attack(target) if target is not None else False
        book = p.skills
        lv = book.level(name)
        if lv <= 0:
            self.log("You haven't learned %s." % name, GREY)
            return False
        s = book.tree[name]
        ap, mana = self.skill_cost(name)
        if s.kind == "attack":
            if target is None or getattr(target, "ai", "") == "npc":
                return False
            if name == "Double Throw":
                self.log("Double Throw needs throwing weapons (coming later).", GREY)
                return False
            if name == "Leap Attack":
                return self._leap(cell=None, target=target, ap=ap, mana=mana, lv=lv)
            return self.player_attack(target, name, ap_cost=ap, mana_cost=mana)
        if p.mana < mana:
            self.log("Not enough mana.", GREY)
            return False
        if self.mode == "combat" and p.ap < ap:
            self.log("Need %d AP for %s." % (ap, name), GREY)
            return False
        if s.kind == "move":
            if cell is None and target is not None:
                cell = target.pos
            if cell is None:
                return False
            if name == "Leap":
                return self._leap(cell=cell, target=None, ap=ap, mana=mana, lv=lv)
            return self._whirlwind(cell, ap, mana, lv)
        if s.kind == "cry":
            return self._warcry(name, lv, ap, mana)
        if s.kind == "corpse":
            return self._corpse_skill(name, cell or (target.pos if target else None), lv, ap, mana)
        return False

    def _pay(self, ap, mana):
        p = self.player
        if self.mode == "combat":
            p.ap -= ap
        p.mana -= mana

    def _leap(self, cell, target, ap, mana, lv):
        p = self.player
        reach = 4 + (lv - 1) // 3
        if target is not None:
            spots = [(target.x + dx, target.y + dy) for dx, dy in DIRS8]
            spots = [c for c in spots if self.grid.walkable(*c) and c not in self.occupied(p)
                     and chebyshev(c, p.pos) <= reach]
            if not spots:
                self.log("Can't leap there.", GREY)
                return False
            cell = min(spots, key=lambda c: chebyshev(c, p.pos))
        if not self.grid.walkable(*cell) or cell in self.occupied(p) or chebyshev(cell, p.pos) > reach:
            self.log("Too far to leap (%d cells)." % reach, GREY)
            return False
        if self.mode == "explore" and target is not None:
            target.aware = True
            self.check_awareness_force()
        if self.mode == "combat" and p.ap < ap:
            self.log("Need %d AP." % ap, GREY)
            return False
        self._pay(ap, mana)
        src = p.pos
        p.face(*cell)
        p.x, p.y = cell
        self.emit("knockback", p, src, cell)       # a quick slide reads as a jump
        self.grid.update_visibility(p.pos, self.sight_radius())
        if target is None:
            for m in self.living_monsters():
                if m.ai != "npc" and chebyshev(m.pos, p.pos) == 1:
                    self._knockback(p, m, 2)
        else:
            self._resolve_attack(p, target, "Leap Attack")
        self.check_awareness()
        self._maybe_auto_end()
        return True

    def _whirlwind(self, cell, ap, mana, lv):
        p = self.player
        dist = chebyshev(cell, p.pos)
        if dist > 6 or dist < 1:
            self.log("Whirlwind reaches up to 6 cells.", GREY)
            return False
        # straight line, passing through monsters; the end cell must be free
        steps, x, y = [], p.x, p.y
        while (x, y) != cell:
            x += (cell[0] > x) - (cell[0] < x)
            y += (cell[1] > y) - (cell[1] < y)
            if not self.grid.walkable(x, y):
                break
            steps.append((x, y))
        while steps and steps[-1] in self.occupied(p):
            steps.pop()
        if not steps:
            return False
        if self.mode == "explore":
            self.check_awareness_force()
        self._pay(ap, mana)
        hit = set()
        path = []
        for st in steps:
            if st in self.occupied(p):
                continue
            p.x, p.y = st
            path.append(st)
            for m in self.living_monsters():
                if m.ai != "npc" and id(m) not in hit and chebyshev(m.pos, st) == 1:
                    hit.add(id(m))
                    m.aware = True
                    self._resolve_attack(p, m, "Whirlwind")
        self.emit("move", p, path)
        self.grid.update_visibility(p.pos, self.sight_radius())
        self._maybe_auto_end()
        return True

    def _warcry(self, name, lv, ap, mana):
        p = self.player
        L = lv - 1
        near = [m for m in self.living_monsters() if m.ai != "npc"]
        if name in ("Howl", "Battle Cry", "War Cry") and self.mode == "explore":
            if any(chebyshev(m.pos, p.pos) <= 6 for m in near):
                self.check_awareness_force()
        self._pay(ap, mana)
        self.emit("attack", p, p.pos, "cast")
        if name == "Howl":
            r, turns = 4 + L // 2, 2 + L // 4
            n = 0
            for m in near:
                if chebyshev(m.pos, p.pos) <= r:
                    m.effects["flee"] = turns
                    n += 1
            self.log("You howl! %d monsters flee." % n, YELLOW)
        elif name == "Shout":
            p.effects["shout_pct"] = 100 + 10 * L
            self._buff("shout", 6 + L)
            self.log("Shout: +%d%% defense." % (100 + 10 * L), YELLOW)
        elif name == "Battle Orders":
            pct = 35 + 3 * L
            p.effects["bo_pct"] = pct
            self._buff("bo", 8 + L)
            p.hp = min(p.max_hp, p.hp + p.max_hp * pct // (100 + pct))
            self.log("Battle Orders: +%d%% life and mana." % pct, YELLOW)
        elif name == "Battle Command":
            p.skills.bonus = 1
            self._buff("bcmd", 6 + L)
            self.log("Battle Command: +1 to all skills.", YELLOW)
        elif name == "Battle Cry":
            n = 0
            for m in near:
                if chebyshev(m.pos, p.pos) <= 5:
                    m.effects.update(bc=True, bc_def=min(90, 50 + 2 * L), bc_dmg=min(75, 25 + L), bc_turns=5 + L)
                    m.aware = True
                    n += 1
            self.log("Battle Cry weakens %d monsters." % n, YELLOW)
        elif name == "War Cry":
            lo, hi = 20 + 6 * L, 30 + 6 * L
            for m in list(near):
                if chebyshev(m.pos, p.pos) <= 3 and m.alive:
                    m.aware = True
                    self._damage(m, self.rng.randint(lo, hi), p)
                    if m.alive:
                        m.effects["stun"] = 1
            self.log("War Cry!", YELLOW)
        self._maybe_auto_end()
        return True

    def _corpse_skill(self, name, cell, lv, ap, mana):
        p = self.player
        L = lv - 1
        corpse = None
        for c in self.corpses:
            if not getattr(c, "searched", False) and chebyshev(c.pos, p.pos) <= 2 and (cell is None or c.pos == cell):
                corpse = c
                break
        if corpse is None:
            self.log("Stand next to an unsearched corpse.", GREY)
            return False
        self._pay(ap, mana)
        corpse.searched = True
        self.emit("attack", p, corpse.pos, "cast")
        if name == "Grim Ward":
            self.wards = getattr(self, "wards", []) + [(corpse.x, corpse.y, 6 + L)]
            self.log("A grim ward rises. Monsters keep away from it.", YELLOW)
            return True
        found = None
        if name == "Find Potion" and self.rng.random() * 100 < min(100, 30 + 5 * L):
            found = self.content.make_potion(max(1, corpse.level), self.rng) if self.content else None
            if found is None:
                from .items import make_potion
                found = make_potion(corpse.level, self.rng)
        elif name == "Find Item" and self.rng.random() * 100 < min(60, 15 + 3 * L):
            drops = (self.content.roll_drop(corpse.level, True, self.rng) if self.content
                     else roll_drop(corpse.level, True, self.rng))
            found = drops[0] if drops else None
        if found:
            cellp = self._drop_cell(corpse.pos)
            self.ground.setdefault(cellp, []).append(found)
            self.emit("drop", cellp, found)
            self.log("You find %s." % found.name, found.color)
        else:
            self.log("Nothing found.", GREY)
        self._maybe_auto_end()
        return True

    def _adjacent_reachable(self, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        if dx and dy:   # diagonal: can't attack through a wall corner
            return self.grid.walkable(a[0] + dx, a[1]) or self.grid.walkable(a[0], a[1] + dy)
        return True

    def check_awareness_force(self):
        if self.mode == "explore":
            for o in self.living_monsters():
                if o.aware is False and o.ai != "npc" and chebyshev(o.pos, self.player.pos) <= ALERT_RADIUS:
                    o.aware = True
            self.mode = "combat"
            self.round = 1
            self.player.ap = self.player.max_ap
            self.emit("combat_start")
            self.log("You strike first!", YELLOW)

    def use_inventory_potion(self, item):
        p = self.player
        if item in p.inventory and len(p.belt) < 4 + 1:
            p.inventory.remove(item)
            item.inv_pos = None
            p.belt.insert(0, item)
            if not self.use_potion(0):
                p.belt.pop(0)
                p.inv_add(item)

    def use_potion(self, slot):
        p = self.player
        if not self.player_can_act() or slot >= len(p.belt):
            return False
        if self.mode == "combat":
            if p.ap < POTION_AP:
                self.log("Not enough AP to drink.", GREY)
                return False
            p.ap -= POTION_AP
        pot = p.belt.pop(slot)
        kind = getattr(pot, "potion", "heal")
        if kind == "mana":
            got = min(pot.amount, p.max_mana - p.mana)
            p.mana += got
            self.log(f"You drink a {pot.name} (+{got} mana).", (120, 140, 255))
        else:
            amount = pot.amount if kind == "heal" else p.max_hp * pot.amount // 100
            healed = min(amount, p.max_hp - p.hp)
            p.hp += healed
            if kind == "rejuv":
                p.mana = min(p.max_mana, p.mana + p.max_mana * pot.amount // 100)
            self.emit("heal", p, healed)
            self.log(f"You drink a {pot.name} (+{healed}).", GREEN)
        self._maybe_auto_end()
        return True

    def _maybe_auto_end(self):
        """In combat, end the turn automatically when the player can't do anything useful."""
        if self.mode == "combat" and self.turn == "player" and self.player.ap <= 0:
            self.end_player_turn()

    def end_player_turn(self):
        if self.mode != "combat" or self.turn != "player" or self.game_over:
            return
        self.turn = "monsters"
        self.emit("turn", "monsters")
        for m in list(self.aware_monsters()):
            if self.game_over:
                break
            if m.alive:
                self._monster_turn(m)
        # monsters that came into view during the enemy phase join next round
        self.check_awareness()
        # ... and ones that lost you give up the chase (so you can explore freely again)
        p = self.player
        for m in self.aware_monsters():
            d = chebyshev(m.pos, p.pos)
            if d > 18 or (d > SIGHT + 2 and not self.grid.line_of_sight(m.pos, p.pos)):
                m.aware = False
        if self.game_over:
            return
        self.round += 1
        p = self.player
        self._tick_buffs()
        p.ap = p.max_ap + min(3, p.frenzy)
        p.frenzy = 0
        p.mana = min(p.max_mana, p.mana + 1)
        if getattr(p, "regen", 0):
            p.hp = min(p.max_hp, p.hp + p.regen)
        self.turn = "player"
        self.emit("turn", "player")
        self.check_combat_end()

    # ------------------------------------------------------------ inventory
    def _inv_index(self, ref):
        p = self.player
        if isinstance(ref, int):
            return ref if 0 <= ref < len(p.inventory) else None
        return p.inventory.index(ref) if ref in p.inventory else None

    def equip(self, ref, slot=None):
        """Equip an inventory item (index or item); the old one goes back to the backpack."""
        p = self.player
        i = self._inv_index(ref)
        if i is None:
            return False
        it = p.inventory[i]
        if it.kind == "potion":
            if len(p.belt) < 4:
                p.belt.append(p.inventory.pop(i))
                it.inv_pos = None
            return True
        if it.kind != "equip" or not it.slot:
            return False
        if it.mod_list is not None and not it.requirements_ok(p):
            self.log("You can't use that yet (requirements).", RED)
            return False
        p.inventory.pop(i)
        spot = it.inv_pos
        it.inv_pos = None
        old = self._put_on(it, slot)
        for o in old:
            o.inv_pos = None
            ok, over = p.inv_fits(o, *spot) if spot else (False, [])
            if ok and not over:
                o.inv_pos = spot
                p.inventory.append(o)
            elif not p.inv_add(o):
                self.ground.setdefault(p.pos, []).append(o)
                self.emit("drop", p.pos, o)
        p.recalc()
        self.log(f"Equipped {it.name}.", it.color)
        return True

    def _put_on(self, it, slot=None):
        """Wear an item; returns what had to come off (0-2 items)."""
        p = self.player
        if slot is None:
            slot = it.slot
            if slot == "ring":
                slot = "ring1" if p.equipment["ring1"] is None or p.equipment["ring2"] is not None else "ring2"
        removed = []
        if p.equipment.get(slot):
            removed.append(p.equipment[slot])
        p.equipment[slot] = it
        weapon = p.equipment.get("weapon")
        if slot == "weapon" and it.two_handed and p.equipment.get("shield"):
            removed.append(p.equipment["shield"])
            p.equipment["shield"] = None
        if slot == "shield" and weapon is not None and weapon.two_handed:
            removed.append(weapon)
            p.equipment["weapon"] = None
        return removed

    def slot_accepts(self, it, slot):
        if it is None or it.kind != "equip":
            return False
        if slot in ("ring1", "ring2"):
            return it.slot == "ring"
        return it.slot == slot

    def unequip(self, slot):
        p = self.player
        it = p.equipment.get(slot)
        if it and p.inv_add(it):
            p.equipment[slot] = None
            p.recalc()

    def drop_item(self, ref):
        p = self.player
        i = self._inv_index(ref)
        if i is not None:
            it = p.inventory.pop(i)
            it.inv_pos = None
            self.ground.setdefault(p.pos, []).append(it)
            self.emit("drop", p.pos, it)

    # ------------------------------------------------------------ the item on the cursor (D2 style)
    held = None

    def pick_from_inventory(self, item):
        p = self.player
        if self.held is not None or item not in p.inventory:
            return False
        p.inventory.remove(item)
        item.inv_pos = None
        self.held = item
        return True

    def pick_from_slot(self, slot):
        p = self.player
        it = p.equipment.get(slot)
        if it is None or self.held is not None:
            return False
        p.equipment[slot] = None
        self.held = it
        p.recalc()
        return True

    def place_held(self, x0, y0):
        """Drop the cursor item into the grid; swaps with exactly one overlapped item, like D2."""
        p, it = self.player, self.held
        if it is None:
            return False
        ok, over = p.inv_fits(it, x0, y0)
        if not ok or len(over) > 1:
            return False
        if over:
            swap = over[0]
            p.inventory.remove(swap)
            swap.inv_pos = None
        else:
            swap = None
        it.inv_pos = (x0, y0)
        p.inventory.append(it)
        self.held = swap
        return True

    def equip_held(self, slot):
        p, it = self.player, self.held
        if it is None:
            return False
        if it.kind == "potion" and slot == "belt_potion":
            if len(p.belt) < 4:
                p.belt.append(it)
                self.held = None
            return True
        if not self.slot_accepts(it, slot):
            return False
        if it.mod_list is not None and not it.requirements_ok(p):
            self.log("You can't use that yet (requirements).", RED)
            return False
        removed = self._put_on(it, slot)
        self.held = None
        if removed:
            self.held = removed[0]
            for extra in removed[1:]:
                if not p.inv_add(extra):
                    self.ground.setdefault(p.pos, []).append(extra)
                    self.emit("drop", p.pos, extra)
        p.recalc()
        self.log(f"Equipped {it.name}.", it.color)
        return True

    def drop_held(self):
        it = self.held
        if it is None:
            return False
        self.held = None
        p = self.player
        self.ground.setdefault(p.pos, []).append(it)
        self.emit("drop", p.pos, it)
        return True

    def add_stat(self, stat):
        p = self.player
        if p.stat_points <= 0:
            return
        attr = {"str": "base_str", "dex": "base_dex", "vit": "base_vit", "eng": "base_eng"}[stat]
        setattr(p, attr, getattr(p, attr) + 1)
        p.stat_points -= 1
        before = p.max_hp
        p.recalc()
        p.hp += max(0, p.max_hp - before)

    # ------------------------------------------------------------ combat resolution
    def _skill_mods(self, attacker, skill):
        """Damage / attack rating bonuses and effects of a melee skill at its current level."""
        m = {"dmg": 0, "ar": 0, "knock": False, "stun": 0, "magic": False}
        if not attacker.is_player or skill in ("attack", None):
            if skill == "bash":                       # monsters / placeholder Bash
                m.update(dmg=50, ar=20, knock=True)
            return m
        lv = max(1, attacker.skills.level(skill))
        L = lv - 1
        if skill in ("Bash", "bash"):
            m.update(dmg=50 + 5 * L, ar=20 + 5 * L, knock=True)
        elif skill == "Double Swing":
            m.update(ar=15 + 5 * L)
        elif skill == "Stun":
            m.update(ar=5 + 5 * L, stun=1 + L // 6)
        elif skill == "Leap Attack":
            m.update(dmg=100 + 30 * L, ar=50 + 15 * L)
        elif skill == "Concentrate":
            m.update(dmg=70 + 5 * L, ar=60 + 10 * L)
        elif skill == "Frenzy":
            m.update(dmg=90 + 5 * L, ar=100 + 7 * L)
        elif skill == "Berserk":
            m.update(dmg=150 + 15 * L, ar=100 + 15 * L, magic=True)
        elif skill == "Whirlwind":
            m.update(dmg=-50 + 8 * L, ar=5 * L)
        return m

    def _resolve_attack(self, attacker, target, skill="attack", ranged_kind=None):
        """One swing (or shot). Returns True on a hit."""
        attacker.face(*target.pos)
        mods = self._skill_mods(attacker, skill)
        anim = "bash" if mods["knock"] else ("resurrect" if skill == "resurrect" else "attack")
        if ranged_kind:
            self.emit("projectile", attacker, attacker.pos, target.pos, ranged_kind)
        else:
            self.emit("attack", attacker, target.pos, anim)
        if self.rng.random() > hit_chance(attacker, target, mods["ar"]):
            self.emit("miss", target)
            return False
        if target.is_player and getattr(target, "block_chance", 0) and self.rng.random() * 100 < target.block_chance:
            self.emit("miss", target)
            self.log("Blocked!", GREY)
            return False
        dmg = self.rng.randint(*attacker.dmg)
        dmg = max(1, int(dmg * (100 + mods["dmg"]) / 100.0))
        aeff = getattr(attacker, "effects", {})
        if aeff.get("bc"):
            dmg = max(1, dmg * (100 - aeff.get("bc_dmg", 25)) // 100)
        if aeff.get("taunt"):
            dmg = max(1, dmg * (100 - aeff.get("taunt", 5)) // 100)
        if attacker.is_player:
            for kind, (lo, hi) in getattr(attacker, "elem", {}).items():
                dmg += self.rng.randint(lo, max(lo, hi))
        if target.is_player and getattr(target, "dr", 0) and not mods["magic"]:
            dmg = max(1, dmg - target.dr)
        self._damage(target, dmg, attacker)
        if attacker.is_player and target is not attacker:
            if attacker.leech and attacker.hp < attacker.max_hp:
                attacker.hp = min(attacker.max_hp, attacker.hp + max(1, dmg * attacker.leech // 100))
            if attacker.mana_leech:
                attacker.mana = min(attacker.max_mana, attacker.mana + max(1, dmg * attacker.mana_leech // 100))
        # thorns
        if target.is_player and target.alive and not ranged_kind and target.thorns and attacker.alive:
            self._damage(attacker, target.thorns, target)
        if mods["stun"] and target.alive and not target.is_player:
            target.effects["stun"] = max(target.effects.get("stun", 0), mods["stun"])
            self.log("%s is stunned!" % target.name, YELLOW)
        if mods["knock"] and target.alive:
            self._knockback(attacker, target)
        return True

    def _knockback(self, src_unit, target, cells=1):
        for _ in range(cells):
            dx = (target.x > src_unit.x) - (target.x < src_unit.x)
            dy = (target.y > src_unit.y) - (target.y < src_unit.y)
            dest = (target.x + dx, target.y + dy)
            if not (self.grid.walkable(*dest) and dest not in self.occupied()):
                return
            src = target.pos
            target.x, target.y = dest
            self.emit("knockback", target, src, dest)

    def _damage(self, unit, amount, source):
        unit.hp -= amount
        self.emit("damage", unit, amount, max(0, unit.hp))
        if unit.hp <= 0:
            self._kill(unit, source)

    def _kill(self, unit, source):
        unit.alive = False
        unit.hp = 0
        self.emit("death", unit)
        if unit.is_player:
            self.game_over = True
            self.log("You have died.", RED)
            self.emit("game_over")
            return
        self.corpses.append(unit)
        p = self.player
        gained = p.gain_xp(unit.xp_value)
        if gained:
            self.emit("levelup", p.level)
            self.log(f"Level up! You are now level {p.level}. Press C to spend stat points.", YELLOW)
        if self.content:
            drops = self.content.roll_drop(unit.level, unit.unique, self.rng, mf=p.mf, gf=p.gf)
        else:
            drops = roll_drop(unit.level, unit.unique, self.rng)
        for it in drops:
            cell = self._drop_cell(unit.pos)
            self.ground.setdefault(cell, []).append(it)
            self.emit("drop", cell, it)
        if unit.unique:
            self.boss_dead = True
            self.log("Corpsefire is slain! The Den of Evil is cleansed.", (199, 179, 119))
            self.emit("victory")
        from . import quests
        quests.on_monster_killed(self)
        # D2 flavour: fallen scatter when a pack mate dies
        for m in self.living_monsters():
            if m.ai == "fallen" and chebyshev(m.pos, unit.pos) <= 5 and self.rng.random() < 0.5:
                m.panic = 1
        self.check_combat_end()

    def _drop_cell(self, origin):
        """Spread drops around so each pile can be clicked."""
        cand = [origin] + [(origin[0] + dx, origin[1] + dy) for dx, dy in DIRS8]
        for c in cand:
            if self.grid.walkable(*c) and c not in self.ground:
                return c
        return origin

    # ------------------------------------------------------------ monster AI
    def _monster_turn(self, m):
        m.ap = m.max_ap
        p = self.player
        eff = m.effects
        for k in ("bc", "taunt"):
            if eff.get(k + "_turns"):
                eff[k + "_turns"] -= 1
                if eff[k + "_turns"] <= 0:
                    eff.pop(k, None)
        if eff.get("stun"):
            eff["stun"] -= 1
            self.emit("miss", m)          # shows a little "miss" puff: it can't act
            return
        if eff.get("flee"):
            eff["flee"] -= 1
            self._move_away(m, m.ap)
            return
        for wx, wy, turns in getattr(self, "wards", []):
            if chebyshev(m.pos, (wx, wy)) <= 4:
                self._move_away(m, m.ap)
                return
        if m.panic:
            m.panic -= 1
            self._move_away(m, m.ap)
            return
        guard = 0
        while m.ap > 0 and m.alive and p.alive and guard < 12:
            guard += 1
            if m.ai == "shaman" and self._try_resurrect(m):
                continue
            if m.range > 1:
                acted = self._ranged_step(m)
            else:
                acted = self._melee_step(m)
            if not acted:
                break

    def _melee_step(self, m):
        p = self.player
        if chebyshev(m.pos, p.pos) == 1 and self._adjacent_reachable(m.pos, p.pos):
            if m.ap >= m.attack_cost:
                m.ap -= m.attack_cost
                self._resolve_attack(m, p)
                return True
            return False
        path = self._path_to_adjacent(m, p.pos)
        if not path:
            return False
        steps = path[: m.ap]
        self._walk(m, steps)
        return True

    def _ranged_step(self, m):
        p = self.player
        d = chebyshev(m.pos, p.pos)
        los = self.grid.line_of_sight(m.pos, p.pos)
        if d <= m.range and los and m.ap >= m.attack_cost:
            # quill rats back off first if they are in your face and can still shoot after
            if d <= 1 and m.ap >= m.attack_cost + 1 and self._move_away(m, 1):
                return True
            m.ap -= m.attack_cost
            kind = "fireball" if m.ai == "shaman" else "spike"
            self._resolve_attack(m, p, ranged_kind=kind)
            return True
        if d <= m.range and los:
            return False    # in position, out of AP
        # approach until in range with line of sight, keep AP for the shot
        path = self.grid.find_path(m.pos, p.pos, blocked=self.occupied(m), allow_goal_blocked=True)
        if not path:
            path = self._path_to_adjacent(m, p.pos)
            if not path:
                return False
        else:
            path = path[:-1]
        steps = []
        budget = m.ap - m.attack_cost if m.ap > m.attack_cost else m.ap
        for c in path[: max(1, budget)]:
            steps.append(c)
            if chebyshev(c, p.pos) <= m.range and self.grid.line_of_sight(c, p.pos):
                break
        if not steps:
            return False
        self._walk(m, steps)
        return True

    def _try_resurrect(self, m):
        # raising takes the shaman's whole turn, and it doesn't always try
        if m.ap < m.max_ap or self.rng.random() > 0.6:
            return False
        for c in self.corpses:
            if c.ai == "fallen" and chebyshev(c.pos, m.pos) <= 6 and self.unit_at(c.pos) is None \
                    and self.grid.line_of_sight(m.pos, c.pos):
                m.ap = 0
                self.corpses.remove(c)
                c.alive = True
                c.hp = c.max_hp
                c.aware = True
                c.panic = 0
                m.face(*c.pos)
                self.emit("attack", m, c.pos, "resurrect")
                self.emit("resurrect", c)
                self.log(f"{m.name} raises a fallen!", (255, 140, 60))
                return True
        return False

    def _path_to_adjacent(self, m, target):
        blocked = self.occupied(m)
        path = self.grid.find_path(m.pos, target, blocked=blocked, allow_goal_blocked=True)
        if path and len(path) >= 1:
            path = path[:-1]
            # first step must not be the target cell itself
            return path if path else None
        # direct route blocked by other monsters: try each free cell around the target
        best = None
        for dx, dy in DIRS8:
            c = (target[0] + dx, target[1] + dy)
            if not self.grid.walkable(*c) or c in blocked:
                continue
            pth = self.grid.find_path(m.pos, c, blocked=blocked)
            if pth and (best is None or len(pth) < len(best)):
                best = pth
        if best:
            return best
        # completely boxed in: shuffle closer greedily
        options = [nb for nb in self.grid.neighbors(*m.pos) if nb not in blocked]
        options = [o for o in options if chebyshev(o, target) < chebyshev(m.pos, target)]
        return [min(options, key=lambda o: chebyshev(o, target))] if options else None

    def _move_away(self, m, max_steps):
        p = self.player
        steps = []
        cur = m.pos
        blocked = self.occupied(m)
        for _ in range(max_steps):
            opts = [nb for nb in self.grid.neighbors(*cur) if nb not in blocked and nb not in steps]
            opts = [o for o in opts if chebyshev(o, p.pos) > chebyshev(cur, p.pos)]
            if not opts:
                break
            cur = max(opts, key=lambda o: (chebyshev(o, p.pos), -abs(o[0] - p.x) - abs(o[1] - p.y)))
            steps.append(cur)
        if not steps:
            return False
        self._walk(m, steps)
        return True

    def _walk(self, m, steps):
        for c in steps:
            m.face(*c)
            m.x, m.y = c
            m.ap -= 1
        self.emit("move", m, list(steps))
