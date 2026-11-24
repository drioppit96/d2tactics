"""Real-time combat on one World: D2's 25 frames a second instead of turns and AP.

Every hero and every awake monster has a small state: what it is doing (standing, walking,
swinging, recovering from a hit), how many frames are left of it, and the cells still to walk.
Each call to tick() is one D2 frame.

The blow itself is the engine's: World._resolve_attack does the to-hit roll, block, damage,
resistances, life steal, death, experience and drops exactly as in the turn-based game. What
this file adds is the timing (game/timing.py) and the decisions (who attacks whom, when to walk,
when to drink).

Rules used here:
- A swing lands at the middle of the attack animation, and starts the next decision when the
  animation is over.
- A hero who loses at least 1/12 of his life in one blow, or a monster that loses 1/8, is knocked
  into hit recovery: the swing it was in the middle of is lost.
- Monsters wake up when a hero comes within AGGRO cells, and wait AI_DELAY frames between
  attacks on top of their attack animation.
- A hero drinks a healing potion from his belt below his profile's potion_at, at most once a
  second.
- What a hero does next is decided by his own brain (autobattler/brain.py): skills, auras,
  curses, buffs, summons, a normal attack, or backing off.
- Skills are cast through the engine's own skill code (World.use_skill, as that hero), so every
  skill does exactly what it does in the turn-based game. A cast takes its FCR time (spells) or
  IAS time (skills that swing) and lands part way through.
- The engine counts a turn as two seconds of D2 time (game/skills.py TURN_SECONDS). Every 50
  frames the turn-based upkeep runs once: auras, buffs and curses tick, mana regenerates,
  poison and lingering spells (Blizzard, Fire Wall ...) do their damage, summons, golems,
  traps and hirelings act, frozen and stunned monsters lose that round, and monsters that cast
  spells take a turn.
"""
import random
from collections import deque

from game.grid import chebyshev

from . import brain as brains
from . import timing

AGGRO = 14              # cells: a monster this close to a hero wakes up
HERO_SIGHT = 18         # cells: how far a hero looks for something to fight
AI_DELAY = 8            # frames a monster waits after its attack before the next decision
ROUND = 50              # frames per turn of the turn-based upkeep (2 seconds)
LOOT_SECONDS = 25       # after the boss: at most this long picking things up, then the portal
LOOT_REACH = 30         # cells: how far a hero goes for an item he wants
DRINK_COOLDOWN = 25     # frames between two potions
MANA_DRINK_AT = 25      # mana %% below which a hero drinks a mana potion
REPATH = 12             # frames between two path searches while chasing
THINK = 6               # frames between two decisions while a hero is walking
MONSTER_THINK = 4       # the same for monsters
DIRECT = 12             # cells: closer than this, walk straight at the goal (no path search)
PATH_BUDGET = 3         # full path searches per run per frame; the rest wait a frame or two
FRAME_PATHS = 6         # full path searches per frame for all runs together
FRAME_GOALS = 2         # floor searches (goal_route) per frame for all runs together
FLOW_R = 24            # cells: how far round each hero the monsters' distance map reaches
FLOW_EVERY = 15         # frames: the distance map is made again at most this often (when he moved)
ROUTE_SECONDS = 10      # a route to a far monster is kept this long (or until it is walked)
#: what the runs have used of this frame's searches (reset by new_frame, once per game frame)
BUDGET = {"paths": 0, "goals": 0}


def new_frame():
    BUDGET["paths"] = BUDGET["goals"] = 0
CROWD = 3               # cells: a monster this close whose way in is blocked waits for a gap
HERO_WALK = 6.0         # CharStats WalkVelocity
HERO_RUN = 9.0          # CharStats RunVelocity (heroes run while on a run)
MONSTER_VEL = 4.0       # when MonStats can't be read


class State:
    __slots__ = ("mode", "frames", "hit_at", "target", "path", "prog", "next_path", "next_drink",
                 "speed", "kind", "plan", "stunned", "total", "next_think", "skip", "path_goal",
                 "last_pos", "moved_at")

    def __init__(self):
        self.mode = "idle"          # idle | walk | attack | gethit
        self.frames = 0             # frames left of the current animation
        self.hit_at = -1            # frame count at which the pending swing lands
        self.target = None
        self.path = []
        self.prog = 0.0
        self.next_path = 0
        self.next_drink = 0
        self.speed = 0.0            # cells per second
        self.kind = None            # "arrow" for ranged attacks
        self.plan = None            # the skill being cast (brain.Plan)
        self.stunned = 0            # frame until which it can't act (frozen, stunned)
        self.total = 0              # frames of the current swing / cast / hit recovery
        self.next_think = 0         # while walking: the frame of the next decision
        self.skip = {}              # id(monster) -> frame: no way to reach it (a wall between), leave it be
        self.path_goal = None       # the cell the current path was searched for
        self.last_pos = None        # where it stood when it last moved, and when (stuck check)
        self.moved_at = 0


class Sim:
    def __init__(self, world, heroes, timings=None, move_scale=1.0, rng=None):
        self.w = world
        self.heroes = list(heroes)
        self.t = timings or timing.Timings(getattr(getattr(world, "content", None), "src", None))
        self.move_scale = move_scale
        self.rng = rng or random.Random()
        self.frame = 0
        self.st = {}
        self.dead = set()           # every monster that died on this floor, however it died
        self.casts = {}             # skill -> times cast on this floor
        self.watched = False        # while False the engine's animation events are thrown away
        self.brains = {}
        self.errors = 0
        self._foes, self._foes_frame = [], -1
        self._cut_short = False
        self._paths_left = PATH_BUDGET
        self.occ = {}
        self.flow = {}              # id(hero) -> (frame, his cell, {cell: steps to him})
        self._was_watched = False
        self.phase = "fight"        # fight | loot (boss dead, picking up) | portal (walking to it)
        self.portal = None          # the cell of the red portal to the next floor
        self.loot_until = 0
        self.at_portal = False
        self.skip_items = set()     # id(item): not wanted after all, or no room for it
        self.picked = []            # (hero, item name) this floor
        for h in self.heroes:
            self._state(h)
            self.brains[id(h)] = brains.Brain(h, self)

    def brain(self, h):
        b = self.brains.get(id(h))
        if b is None:
            b = self.brains[id(h)] = brains.Brain(h, self)
        return b

    # ------------------------------------------------------------ state
    def _state(self, u):
        s = self.st.get(id(u))
        if s is None:
            s = State()
            s.speed = self._speed(u)
            self.st[id(u)] = s
        return s

    def _speed(self, u):
        if getattr(u, "is_player", False):
            frw = u.mod("frw") if hasattr(u, "mod") else 0
            return timing.move_speed(HERO_RUN, frw, self.move_scale)
        if getattr(u, "stationary", False):
            return 0.0
        vel = MONSTER_VEL
        c = getattr(self.w, "content", None)
        row = (getattr(c, "monstats", None) or {}).get(getattr(u, "d2id", None) or getattr(u, "kind", None)) if c else None
        if row:
            try:
                vel = float(int((row.get("velocity") or "0").strip() or 0))
            except ValueError:
                pass
        return timing.move_speed(vel, 0, self.move_scale) if vel > 0 else 0.0

    def living_heroes(self):
        return [h for h in self.heroes if h.alive]

    def foes(self):
        """The living monsters, worked out once per frame."""
        if self._foes_frame != self.frame:
            self._foes = [m for m in self.w.monsters
                          if m.alive and not getattr(m, "ally", False) and getattr(m, "ai", "") != "npc"]
            self._foes_frame = self.frame
        return self._foes

    def _rebuild_occ(self):
        """Who stands where, once per frame (the engine's unit_at looks through every monster)."""
        occ = {}
        for m in self.w.monsters:
            if m.alive:
                occ[m.pos] = m
                r = getattr(m, "radius", 0)
                if r:
                    for dx in range(-r, r + 1):
                        for dy in range(-r, r + 1):
                            occ.setdefault((m.x + dx, m.y + dy), m)
        for h in self.heroes:
            if h.alive:
                occ[h.pos] = h
        self.occ = occ

    def _at(self, cell):
        return self.occ.get(cell)

    # ------------------------------------------------------------ one frame
    def tick(self):
        self.frame += 1
        heroes = self.living_heroes()
        if not heroes:
            return
        self._rebuild_occ()
        self._paths_left = PATH_BUDGET
        if self.watched and not self._was_watched:
            self._update_sight()                 # (only kept up while someone watches)
        self._was_watched = self.watched
        if self.frame % 5 == 0:                  # (five times a second is plenty to wake up)
            for m in self.foes():
                if not getattr(m, "aware", False) and any(chebyshev(m.pos, h.pos) <= AGGRO for h in heroes):
                    m.aware = True
        if self.frame % ROUND == 0:
            self._round()
        if self.phase == "loot" and (self.frame >= self.loot_until or not any(self._next_item(h) for h in heroes)):
            self.phase = "portal"
        for u in heroes + [m for m in self.foes() if getattr(m, "aware", False) and not getattr(m, "caster", False)]:
            if u.alive:
                self._step(u)
        for m in self.w.monsters:
            if not m.alive and not getattr(m, "ally", False) and not getattr(m, "is_player", False):
                self.dead.add(id(m))
        if not self.watched:
            del self.w.events[:]

    @property
    def kills(self):
        return len(self.dead)

    # ------------------------------------------------------------ the 2-second upkeep
    class _Guard:
        """Engine code is turn-based: keep the world in "explore" on the heroes' turn around it."""

        def __init__(self, w, turn="player"):
            self.w, self.turn = w, turn

        def __enter__(self):
            self.mode, self.old_turn = self.w.mode, self.w.turn
            self.w.mode, self.w.turn = "explore", self.turn

        def __exit__(self, *exc):
            self.w.mode, self.w.turn = "explore", "player"
            self.w.game_over = False
            return False

    def _engine(self, fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except Exception:
            self.errors += 1
            if self.errors <= 5:
                import traceback
                traceback.print_exc()
            return None

    def _round(self):
        from game import tactics
        w = self.w
        with self._Guard(w):
            if hasattr(w, "aura_turn"):
                self._engine(w.aura_turn)
            for h in self.living_heroes():
                with tactics.acting_as(w, h):
                    self._engine(w._hero_turn_start)
            if hasattr(w, "_tick_buffs"):
                self._engine(w._tick_buffs)
            if hasattr(w, "allies_turn"):
                self._engine(w.allies_turn)
            if hasattr(w, "tick_hazards"):
                self._engine(w.tick_hazards)
        for m in [m for m in self.foes() if getattr(m, "aware", False)]:
            if getattr(m, "caster", False):
                with self._Guard(w, "monsters"):
                    self._engine(w._monster_turn, m)       # (its own status, spells and moves)
                continue
            s = self._state(m)
            eff = getattr(m, "effects", None) or {}
            ok = True
            if hasattr(w, "monster_status"):
                with self._Guard(w, "monsters"):
                    ok = self._engine(w.monster_status, m)
            if eff.get("stun"):
                eff["stun"] -= 1
                ok = False
            if ok is False and m.alive:
                s.stunned = self.frame + ROUND
                s.mode, s.frames, s.path, s.hit_at = "idle", 0, [], -1

    def _step(self, u):
        s = self._state(u)
        if s.stunned > self.frame:
            return
        if s.mode in ("attack", "gethit", "cast"):
            s.frames -= 1
            if s.frames == s.hit_at:
                if s.mode == "attack":
                    self._land(u, s)
                elif s.mode == "cast":
                    self._cast(u, s)
            if s.frames > 0:
                return
            s.mode = "idle"
            if not u.is_player:
                s.frames = AI_DELAY
            return
        if s.mode == "idle" and s.frames > 0:
            s.frames -= 1
            return
        if s.mode == "walk" and s.path and self.frame < s.next_think:
            self._advance(u, s)              # keep walking; the next decision comes in a moment
            return
        s.next_think = self.frame + (THINK if u.is_player else MONSTER_THINK)
        if u.is_player:
            self._hero_think(u, s)
        else:
            self._monster_think(u, s)

    # ------------------------------------------------------------ decisions
    def _hero_think(self, h, s):
        b = self.brain(h)
        self._unstick(h, s)
        if self.frame >= s.next_drink and getattr(h, "max_mana", 0) and \
                h.mana * 100 < h.max_mana * MANA_DRINK_AT and self._drink(h, ("mana", "rejuv")):
            s.next_drink = self.frame + DRINK_COOLDOWN
            b.last = "drinks a mana potion"
        if self._loot_or_leave(h, s, b):
            return
        if h.hp * 100 < h.max_hp * brains.setting(h, "potion_at") and self.frame >= s.next_drink:
            if self._drink(h):
                s.next_drink = self.frame + DRINK_COOLDOWN
        tgt = s.target if (s.target is not None and s.target.alive) else None
        if tgt is None or chebyshev(h.pos, tgt.pos) > HERO_SIGHT or s.skip.get(id(tgt), 0) > self.frame:
            # what he can see: in the open in front of him, not behind a wall (one behind a wall
            # is found by the route below, by walking - so he doesn't turn back and forth
            # between a monster he sees through the wall and the way round to another)
            seen = [m for m in self.foes() if s.skip.get(id(m), 0) <= self.frame
                    and chebyshev(m.pos, h.pos) <= HERO_SIGHT
                    and (chebyshev(m.pos, h.pos) <= 2 or self._line_clear(h.pos, m.pos))]
            tgt = self._nearest(h, seen, HERO_SIGHT)
            s.target = tgt
        awake = [m for m in self.foes() if getattr(m, "aware", False) or chebyshev(m.pos, h.pos) <= HERO_SIGHT]
        plan = b.decide(tgt, awake)
        if plan is not None and plan.what == "skill" and tgt is not None and \
                b.ranged_hero(brains.SPELL_RANGE) and self._should_back_off(h, b):
            if self._back_off(h, s):
                b.last = "backing off"
                return
        if plan is None or plan.what == "attack":
            if tgt is None:
                if self.phase != "fight":
                    return                       # (the boss is dead: no hunting for more, the portal waits)
                route = self.goal_route(h)
                if route is None:
                    s.next_think = self.frame + 1     # (this frame's searches are used up)
                elif route:
                    b.last = "looking for monsters"
                    if self.occ.get(route[0]) not in (None, h):
                        self.st.pop(("route", id(h)), None)    # someone in the way: a new route
                        s.next_think = self.frame + 1
                        return
                    s.path = list(route)
                    s.mode = "walk"
                    self._advance(h, s)
                return
            self._engage(h, s, tgt, self._reach(h))
            return
        self._start_cast(h, s, plan)

    # ------------------------------------------------------------ loot and the portal
    def open_portal(self, cell):
        """The boss is dead: a red portal to the next floor opens where it fell."""
        if self.phase != "fight":
            return
        g = self.w.grid
        if cell is None or not g.walkable(*cell):
            cell = self.living_heroes()[0].pos if self.living_heroes() else cell
        self.portal = cell
        self.phase = "loot"
        self.loot_until = self.frame + LOOT_SECONDS * timing.FPS
        self.w.objects.append(dict(kind="red_portal", cell=cell, level=None, oid=0, used=False, target=None,
                                   rift_next=True))
        if self.watched:
            self.w.emit("object", cell)

    def _awake_near(self, h, r=HERO_SIGHT):
        """Awake monsters near him that he can get to (one behind a wall doesn't hold him back
        from picking things up or going to the portal)."""
        skip = self._state(h).skip
        return [m for m in self.foes() if getattr(m, "aware", False) and chebyshev(m.pos, h.pos) <= r
                and skip.get(id(m), 0) <= self.frame
                and (chebyshev(m.pos, h.pos) <= 2 or self._line_clear(h.pos, m.pos))]

    def ground_items(self):
        out = []
        for cell, items in list((getattr(self.w, "ground", None) or {}).items()):
            for it in list(items):
                out.append((cell, it))
        return out

    def _next_item(self, h):
        best, bd = None, LOOT_REACH + 1
        for cell, it in self.ground_items():
            if id(it) in self.skip_items:
                continue
            d = chebyshev(h.pos, cell)
            if d < bd and brains.wants(h, it):
                best, bd = (cell, it), d
        return best

    def _loot_or_leave(self, h, s, b):
        """With nothing awake around him: pick up what he wants; after the boss, go to the portal.
        -> True when that is what he is doing this moment."""
        if self._awake_near(h):
            return False
        nxt = self._next_item(h)
        if nxt is not None:
            cell, it = nxt
            if chebyshev(h.pos, cell) <= 1:
                self.take(h, cell, it)
            else:
                b.last = "going for %s" % self._item_name(it)
                if not self._walk_to(h, s, cell, reach=1):
                    self.skip_items.add(id(it))
            return True
        if self.phase == "portal" and self.portal is not None:
            if chebyshev(h.pos, self.portal) <= 1:
                if h is self.living_heroes()[0]:
                    self.at_portal = True
                b.last = "at the portal"
            else:
                b.last = "to the portal"
                if not self._walk_to(h, s, self.portal, reach=1):
                    self.at_portal = True    # (no way to it: go through anyway)
            return True
        return False

    def _item_name(self, it):
        if getattr(it, "kind", "") == "gold":
            return "%d gold" % getattr(it, "amount", 0)
        return str(getattr(it, "shown_name", None) or getattr(it, "name", "an item"))

    def take(self, h, cell, it):
        """The engine's own pickup (gold to the purse, potions to the belt, tomes, stacks, the
        backpack), as that hero. -> True if he took it."""
        from game import quests, tactics
        w = self.w
        hook = quests.on_pickup
        quests.on_pickup = lambda *a, **k: None   # the autobattler has no quests
        try:
            with self._Guard(w):
                with tactics.acting_as(w, h):
                    ok = bool(self._engine(w.pickup_item, cell, it))
        finally:
            quests.on_pickup = hook
        if ok:
            self.picked.append((h.name, self._item_name(it)))
            self.brain(h).last = "picked up %s" % self._item_name(it)
        else:
            self.skip_items.add(id(it))      # no room: leave it (it stays in the loot window)
        return ok

    def _should_back_off(self, h, b):
        limit = brains.setting(h, "back_off_at")
        if not limit or h.hp * 100 > h.max_hp * limit:
            return False
        return any(chebyshev(m.pos, h.pos) <= 1 + getattr(m, "radius", 0) and getattr(m, "range", 1) <= 1
                   for m in self.foes() if getattr(m, "aware", False))

    def _back_off(self, h, s):
        """A few steps to the open cell farthest from the monsters next to him."""
        g = self.w.grid
        foes = [m for m in self.foes() if chebyshev(m.pos, h.pos) <= 8]
        best, bd = None, -1
        for dx in range(-4, 5):
            for dy in range(-4, 5):
                c = (h.x + dx, h.y + dy)
                if c == h.pos or not g.walkable(*c) or c in self.occ:
                    continue
                d = min([chebyshev(c, m.pos) for m in foes] or [99])
                if d > bd:
                    best, bd = c, d
        if best is None or bd <= 1:
            return False
        self._walk_to(h, s, best, reach=0)
        return True

    # ------------------------------------------------------------ casting
    def _start_cast(self, h, s, plan):
        book = getattr(h, "skills", None)
        sk = book.tree.get(plan.skill) if book else None
        reach = brains.SPELL_RANGE
        if sk is not None and (getattr(sk, "weapon", False) or sk.kind in ("attack", "melee")):
            reach = self._reach(h)
        if plan.skill == "throw":
            reach = int(getattr(h, "throw_range", brains.THROW_RANGE))
        aim = plan.target.pos if plan.target is not None else plan.cell
        if aim is not None and sk is not None and sk.kind not in ("aura", "buff", "cry") and \
                sk.kind not in brains.SUMMON_KINDS and chebyshev(h.pos, aim) > reach:
            if not self._walk_to(h, s, aim, reach=reach) and plan.target is not None:
                s.skip[id(plan.target)] = self.frame + 2 * timing.FPS     # no way to it: another one
                s.target = None
            return
        if aim is not None and aim != h.pos:
            h.face(*aim)
        s.mode, s.frames, s.plan, s.path = "cast", max(1, plan.frames), plan, []
        s.total = s.frames
        s.hit_at = max(0, s.frames // 2)
        if self.watched:
            self.w.emit("attack", h, aim or h.pos, "cast" if sk is not None and sk.kind not in ("attack", "melee") else "attack")

    def _cast(self, h, s):
        from game import tactics
        plan = s.plan
        s.plan = None
        if plan is None or not h.alive:
            return
        if plan.target is not None and not plan.target.alive:
            return
        w = self.w
        ok = False
        with self._Guard(w):
            with tactics.acting_as(w, h):
                h.ap = max(getattr(h, "ap", 0), 20)
                n0 = len(w.events)
                ok = bool(self._engine(w.use_skill, plan.skill, plan.target, plan.cell))
                if not self.watched:
                    del w.events[n0:]
        self.brain(h).done(plan, ok)
        if ok:
            self.casts[plan.skill] = self.casts.get(plan.skill, 0) + 1


    def _monster_think(self, m, s):
        heroes = self.living_heroes()
        tgt = self._nearest(m, heroes, 10 ** 6)
        if tgt is None:
            return
        s.target = tgt
        self._engage(m, s, tgt, self._reach(m))

    def _reach(self, u):
        if getattr(u, "is_player", False):
            if getattr(u, "ranged", False):
                return max(2, int(getattr(u, "range", 1)))
            return max(1, int(getattr(u, "reach", 1)))
        return max(1, int(getattr(u, "range", 1)))

    def _engage(self, u, s, tgt, reach):
        r = getattr(u, "radius", 0) + getattr(tgt, "radius", 0)
        if chebyshev(u.pos, tgt.pos) <= reach + r:
            self._start_attack(u, s, tgt, ranged=reach > 1)
        elif not self._walk_to(u, s, tgt.pos, reach=reach, target_r=getattr(tgt, "radius", 0)):
            # no way to it from here (behind a wall, or boxed in by its own pack): pick another
            # (after the boss, longer: the floor is done and the portal waits)
            s.skip[id(tgt)] = self.frame + (2 if self.phase == "fight" else 10) * timing.FPS
            s.target = None
            s.next_think = self.frame

    def _nearest(self, u, units, limit):
        best, bd = None, limit + 1
        for o in units:
            d = chebyshev(u.pos, o.pos)
            if d < bd:
                best, bd = o, d
        return best

    def goal_cell(self, h=None):
        """The cell at the end of the hero's route (see goal_route), or None."""
        h = h or (self.living_heroes() or [None])[0]
        if h is None:
            return None
        ent = self.st.get(("route", id(h)))
        return ent[2][-1] if ent is not None and ent[2] else None

    def goal_route(self, h):
        """Where a hero heads when nothing is in sight: the cells to the nearest monster he can
        walk to, found by walking the floor's cells, so a wall between doesn't fool him. On a floor
        too big to search in one go, the route goes as far as the search reached towards the
        nearest monster, and the next search carries on from there.

        The route is kept while he walks it (at most ROUTE_SECONDS), so the floor is searched about
        once per stretch, not every few frames. -> the cells still ahead of him, [] when there is
        nowhere to go, None when this frame's searches are used up (he waits a frame)."""
        key = ("route", id(h))
        ent = self.st.get(key)
        if ent is not None:
            until, foe, route = ent
            if until > self.frame and (foe is None or foe.alive) and route:
                if h.pos in route:
                    route = route[route.index(h.pos) + 1:]
                    self.st[key] = (until, foe, route)
                if route and chebyshev(h.pos, route[0]) <= 1:
                    return route
        if BUDGET["goals"] >= FRAME_GOALS:
            return None
        BUDGET["goals"] += 1
        foe, route = self._nearest_reachable(h)
        self.st[key] = (self.frame + ROUTE_SECONDS * timing.FPS, foe, route)
        if foe is None and self.foes() and not self._cut_short:
            self.stranded = True             # monsters left, none of them reachable: floor done
        return route

    def _nearest_reachable(self, h, cap=12000):
        """Breadth-first over the floor from the hero. -> (monster, cells to it) for the nearest
        one he can walk to; when the search stops at `cap` cells, (nearest monster, cells to the
        searched cell closest to it); (None, []) when there is none."""
        skip = self._state(h).skip
        foes = [m for m in self.foes() if skip.get(id(m), 0) <= self.frame]
        at = {}
        for m in foes:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    at.setdefault((m.x + dx, m.y + dy), m)
        self._cut_short = False
        if not at:
            return None, []
        g = self.w.grid
        start = h.pos
        occ = self.occ
        came = {start: None}
        q = deque([start])
        found = end = None
        while q:
            if len(came) >= cap:
                self._cut_short = True
                break
            c = q.popleft()
            m = at.get(c)
            if m is not None and c != start:
                found, end = m, c
                break
            for nb in g.neighbors(*c):
                if nb not in came:
                    came[nb] = c
                    if nb in occ and nb not in at:
                        continue             # (someone stands there: the way goes round him)
                    q.append(nb)
        if found is None and self._cut_short:
            found = min(foes, key=lambda m: chebyshev(m.pos, start))
            fx, fy = found.pos
            end = min(came, key=lambda c: (max(abs(c[0] - fx), abs(c[1] - fy)), -abs(c[0] - start[0]) - abs(c[1] - start[1])))
        if found is None or end is None:
            return None, []
        route = []
        c = end
        while c is not None and c != start:
            route.append(c)
            c = came[c]
        route.reverse()
        if route and route[-1] == found.pos:
            route.pop()                      # stop beside it, not on it
        return found, route

    # ------------------------------------------------------------ actions
    def _start_attack(self, u, s, tgt, ranged=False):
        u.face(*tgt.pos)
        fpd, speed = self.t.fpd(u, "A1")
        if u.is_player:
            ias = u.mod("ias") if hasattr(u, "mod") else 0
            frames = timing.attack_frames(fpd, ias, self._wsm(u), 0, speed)
        else:
            frames = timing.attack_frames(fpd, 0, 0, 0, speed)
        s.mode, s.frames, s.target, s.total = "attack", frames, tgt, frames
        s.hit_at = frames // 2
        s.kind = "arrow" if ranged and (not u.is_player or getattr(u, "ranged", False)) else None
        s.path = []
        if self.watched:
            self.w.emit("attack", u, tgt.pos, "attack")

    def _land(self, u, s):
        tgt = s.target
        if tgt is None or not tgt.alive or not u.alive:
            return
        before = tgt.hp
        was_alive = tgt.alive
        try:
            self.w._resolve_attack(u, tgt, "attack", ranged_kind=s.kind, quiet_anim=True)
        except Exception:
            # one bad blow must not stop eight runs: log it and carry on
            import traceback
            traceback.print_exc()
            return
        lost = before - max(0, tgt.hp)
        if tgt.alive and lost > 0:
            share = 12 if tgt.is_player else 8
            if lost * share >= tgt.max_hp:
                self._hit_recovery(tgt)

    def _hit_recovery(self, u):
        s = self._state(u)
        fpd, speed = self.t.fpd(u, "GH")
        fhr = u.mod("fhr") if getattr(u, "is_player", False) and hasattr(u, "mod") else 0
        s.mode = "gethit"
        s.frames = s.total = timing.hit_recovery_frames(fpd, fhr, speed)
        s.hit_at = -1
        s.path = []

    def _walk_to(self, u, s, goal, reach=1, target_r=0):
        """Walk towards `goal`. -> False when there is no way there from here."""
        if s.speed <= 0:
            return False
        want = reach + getattr(u, "radius", 0) + target_r
        d = chebyshev(u.pos, goal)
        if d <= want:
            s.path = []
            return True
        if d <= DIRECT and self._line_clear(u.pos, goal):
            step = self._direct_step(u, goal)
            if step is not None:
                s.path = [step]              # close by and nothing in the way: straight at it
                s.mode = "walk"
                self._advance(u, s)
                return True
        hero = self.occ.get(goal) if not u.is_player and not getattr(u, "radius", 0) else None
        if hero is not None and getattr(hero, "is_player", False):
            step = self._flow_step(u, hero)
            if step is False:
                # beyond the map's reach: straight at him while that works, else it waits
                step = self._direct_step(u, goal) if d <= 2 * FLOW_R else None
                if step is None:
                    s.path, s.mode = [], "idle"
                    s.next_think = self.frame + timing.FPS
                    return True
            if step is not False:
                if step is None:
                    s.path, s.mode = [], "idle"
                    s.next_think = self.frame + 6    # every way nearer is taken: wait for a gap
                    return True
                s.path = [step]
                s.mode = "walk"
                self._advance(u, s)
                return True
        if not u.is_player and d <= CROWD + target_r:
            s.path = []
            s.mode = "idle"
            s.next_think = self.frame + 6        # boxed in by its own pack: wait for a gap
            return True
        moved = s.path_goal is None or chebyshev(s.path_goal, goal) > 1
        if not s.path or self.frame >= s.next_path or (moved and d <= DIRECT):
            if self._paths_left <= 0 or BUDGET["paths"] >= FRAME_PATHS:
                s.next_think = self.frame + 1     # (this frame's searches are used up: next frame)
                return True
            self._paths_left -= 1
            BUDGET["paths"] += 1
            limit = 3000 if u.is_player else 1500
            path = self.w.path_near(u, goal, reach=reach, target_r=target_r, limit=limit)
            s.path_goal = goal
            s.next_path = self.frame + (REPATH * 3 if u.is_player and d > DIRECT else REPATH)
            s.path = list(path or [])
            if not s.path:
                s.mode = "idle"
                return False
        s.mode = "walk"
        self._advance(u, s)
        return True

    def _update_sight(self):
        p = getattr(self.w, "player", None)
        if p is None:
            return
        try:
            self.w.grid.update_visibility(p.pos, self.w.sight_radius())
        except Exception:
            pass

    # ------------------------------------------------------------ monsters closing in
    def _flow(self, h):
        """Steps to hero `h` from every cell within FLOW_R of him (breadth-first over the floor).
        Every monster after him walks down this map, so one search a few times a second serves
        the whole pack instead of a path search per monster."""
        ent = self.flow.get(id(h))
        if ent is not None and (ent[1] == h.pos or self.frame - ent[0] < FLOW_EVERY):
            return ent[2]
        g = self.w.grid
        hx, hy = h.pos
        dist = {h.pos: 0}
        q = deque([h.pos])
        while q:
            c = q.popleft()
            d = dist[c] + 1
            for nb in g.neighbors(*c):
                if nb not in dist and abs(nb[0] - hx) <= FLOW_R and abs(nb[1] - hy) <= FLOW_R:
                    dist[nb] = d
                    q.append(nb)
        self.flow[id(h)] = (self.frame, h.pos, dist)
        return dist

    def _flow_step(self, u, hero):
        """The free neighbouring cell nearer to `hero` by his distance map. -> cell, or None when
        no free cell is nearer (boxed in: wait), or False when he is out of the map's reach."""
        dist = self._flow(hero)
        here = dist.get(u.pos)
        if here is None:
            return False
        best, bd = None, here
        for nb in self.w.grid.neighbors(*u.pos):
            d = dist.get(nb)
            if d is not None and d < bd and nb not in self.occ:
                best, bd = nb, d
        return best

    def _line_clear(self, a, b):
        """Nothing but open floor on the straight line from a to b (no wall, no corner cut), so
        stepping straight at b can't walk into a dead end."""
        g = self.w.grid
        x, y = a
        bx, by = b
        n = max(abs(bx - x), abs(by - y))
        if n <= 1:
            return True
        px, py = x, y
        for i in range(1, n + 1):
            cx = x + int(round((bx - x) * i / float(n)))
            cy = y + int(round((by - y) * i / float(n)))
            if (cx, cy) != (bx, by) and not g.walkable(cx, cy):
                return False
            if cx != px and cy != py and (not g.walkable(cx, py) or not g.walkable(px, cy)):
                return False
            px, py = cx, cy
        return True

    def _unstick(self, h, s):
        """A hero who hasn't moved for 3 seconds while he means to go somewhere (and isn't
        fighting): drop his path and route, leave his target be for a while, and look again."""
        if s.last_pos != h.pos:
            s.last_pos, s.moved_at = h.pos, self.frame
            return False
        if s.mode in ("attack", "cast", "gethit") or self.frame - s.moved_at < 3 * timing.FPS:
            return False
        s.moved_at = self.frame
        s.path, s.path_goal = [], None
        self.st.pop(("route", id(h)), None)
        if s.target is not None:
            s.skip[id(s.target)] = self.frame + 5 * timing.FPS
            s.target = None
        self.brain(h).last = "stuck: looking for another way"
        return True

    def _direct_step(self, u, goal):
        """The free neighbouring cell that gets closest to `goal`, if it gets closer at all."""
        if getattr(u, "radius", 0):
            return None                      # (big monsters need the path search's room checks)
        g = self.w.grid
        best, bd = None, (chebyshev(u.pos, goal), 0.0)
        for nb in g.neighbors(*u.pos):
            if nb in self.occ:
                continue
            dd = (chebyshev(nb, goal), (nb[0] - goal[0]) ** 2 + (nb[1] - goal[1]) ** 2)
            if dd < bd:
                best, bd = nb, dd
        return best

    def _advance(self, u, s):
        """Move along s.path at the unit's speed (part of a cell per frame)."""
        s.prog += s.speed / timing.FPS
        moved = []
        while s.prog >= 1.0 and s.path:
            nxt = s.path[0]
            other = self.occ.get(nxt)
            if other is not None and other is not u:
                s.path = []              # someone stepped in the way: look again next frame
                s.next_path = self.frame
                s.prog = 0.0
                break
            s.path.pop(0)
            s.prog -= 1.0
            u.face(*nxt)
            if self.occ.get(u.pos) is u:
                del self.occ[u.pos]
            u.x, u.y = nxt
            self.occ[nxt] = u
            moved.append(nxt)
        if moved:
            if self.watched and u.is_player and u is getattr(self.w, "player", None):
                self._update_sight()
            if self.watched:
                self.w.emit("move", u, moved)

    def _wsm(self, u):
        w = (getattr(u, "equipment", None) or {}).get("rhand")
        b = getattr(w, "base", None)
        if isinstance(b, dict):
            try:
                return int(b.get("speed", 0) or 0)
            except (TypeError, ValueError):
                return 0
        return 0

    def _drink(self, h, kinds=("heal", "rejuv")):
        """A potion of one of `kinds` from his belt, by the engine's own potion code (as him, so
        every hero of a group drinks from his own belt)."""
        from game import potions, tactics
        w = self.w
        try:
            for c in range(potions.belt_slots(h)):
                col = potions.column(h, c)
                if col and getattr(col[0], "potion", "") in kinds:
                    with self._Guard(w):
                        with tactics.acting_as(w, h):
                            h.ap = max(getattr(h, "ap", 0), 10)
                            return bool(self._engine(potions.drink, w, c))
        except Exception:
            import traceback
            traceback.print_exc()
        return False

    # ------------------------------------------------------------ results
    def boss_dead(self):
        bosses = [m for m in self.w.monsters if getattr(m, "rift_boss", False)]
        return bool(bosses) and not any(m.alive for m in bosses)

    def boss_cell(self):
        dead = [m for m in self.w.monsters if getattr(m, "rift_boss", False) and not m.alive]
        return dead[0].pos if dead else None

    def cleared(self):
        """The floor is done: its boss is dead (or, with no boss on it, every monster is), or the
        monsters that are left can't be reached from where the heroes are."""
        if getattr(self, "stranded", False):
            return True
        if any(getattr(m, "rift_boss", False) for m in self.w.monsters):
            return self.boss_dead()
        return not self.foes()

    def wiped(self):
        return not self.living_heroes()
