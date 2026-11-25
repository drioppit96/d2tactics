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
PACK = 6                # cells: the monsters round one that is attacked wake with it
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
PET_THINK = 6           # the same for summons
DIRECT = 12             # cells: closer than this, walk straight at the goal (no path search)
PATH_BUDGET = 3         # full path searches per run per frame; the rest wait a frame or two
FRAME_PATHS = 4         # full path searches per frame for all runs together
FRAME_NODES = 2000      # floor cells searched for routes (goal_route) per frame, all runs together
SEARCH_CHUNK = 500      # cells searched in one go
FLOW_R = 24            # cells: how far round each hero the monsters' distance map reaches
FLOW_EVERY = 25         # frames: the distance map is made again at most this often (when he moved)
POISON_EVERY = 5        # frames between poison ticks (D2 ticks every frame: same total)
BIG_PATH = 800          # cells a big monster's path search looks at, at most
CASTER_REACH = 40       # cells: a caster monster further than this from every hero doesn't act
CASTER_PATH = 1500      # cells a caster monster's path search looks at, at most
ROUTE_SECONDS = 10      # a route to a far monster is kept this long (or until it is walked)
#: what the runs have used of this frame's searches (reset by new_frame, once per game frame)
BUDGET = {"paths": 0, "nodes": 0}


def label_areas(world):
    """Which cells of a floor are joined by walkable ground: {cell: area number}, worked out once
    per floor (on the thread that builds it). Two units in different areas can't walk to each
    other however long they search - a railing, a chasm, a wall all the way round - so nobody
    has to find that out by searching the whole floor, over and over."""
    from game.grid import FLOOR, Grid
    g = world.grid
    exact = type(g).walkable is Grid.walkable
    cells, w, h = g.cells, g.w, g.h
    area = {}
    n = 0

    def nbs(x, y):
        if not exact:
            return list(Grid.neighbors(g, x, y))
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not dx and not dy:
                    continue
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h) or cells[ny][nx] != FLOOR:
                    continue
                if dx and dy and (cells[y][nx] != FLOOR or cells[ny][x] != FLOOR):
                    continue
                out.append((nx, ny))
        return out
    for y in range(h):
        row = cells[y]
        for x in range(w):
            if (row[x] != FLOOR if exact else not g.walkable(x, y)) or (x, y) in area:
                continue
            n += 1
            area[(x, y)] = n
            q = deque([(x, y)])
            while q:
                cx, cy = q.popleft()
                for c in nbs(cx, cy):
                    if c not in area:
                        area[c] = n
                        q.append(c)
    world._areas = area
    return area


def new_frame():
    BUDGET["paths"] = BUDGET["nodes"] = 0
CROWD = 3               # cells: a monster this close whose way in is blocked waits for a gap
HERO_WALK = 6.0         # CharStats WalkVelocity
HERO_RUN = 9.0          # CharStats RunVelocity (heroes run while on a run)
MONSTER_VEL = 4.0       # when MonStats can't be read


class State:
    __slots__ = ("mode", "frames", "hit_at", "target", "path", "prog", "next_path", "next_drink",
                 "speed", "kind", "plan", "stunned", "total", "next_think", "skip", "path_goal",
                 "last_pos", "moved_at", "next_kite", "anim", "futile", "dealt_at", "unstuck_at")

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
        self.next_kite = 0          # the frame he may step away from melee monsters again
        self.anim = None            # the animation of the swing / cast under way (A1, TH, SC, S1...)
        self.futile = None          # [id(target), its life, blows and casts since it last went down]
        self.dealt_at = 0           # the frame he last took life off a monster
        self.unstuck_at = 0         # the frame his path was last dropped for not moving


class Sim:
    def __init__(self, world, heroes, timings=None, move_scale=1.0, rng=None):
        self.w = world
        self._nb_cache = self._cache_neighbors(world)
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
        self._paths_left = PATH_BUDGET
        self.occ = {}
        self.flow = {}              # id(hero) -> (frame, his cell, {cell: steps to him})
        self._was_watched = False
        self.phase = "fight"        # fight | loot (boss dead, picking up) | portal (walking to it)
        self.no_room = False        # a hero found something he wanted and had no room for it
        self.need_town = False      # a hero is nearly dead with no healing potion left
        self.notes = []             # things for the run's log (summons ...), taken by the run
        self._foes_at_start = None
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
        if self.frame % POISON_EVERY == 0:
            self._tick_poison()
        if self.frame % ROUND == 0:
            self._round()
        if self.phase == "loot" and (self.frame >= self.loot_until or not any(self._next_item(h) for h in heroes)):
            self.phase = "portal"
        for h in heroes:
            self._quaff(h)
        for u in heroes + self.pets() + [m for m in self.foes() if getattr(m, "aware", False) and not self._engine_moved(m)]:
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

    last_error = None

    def _engine(self, fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as e:
            self.errors += 1
            self.last_error = "error: %s" % e
            if self.errors <= 5:
                import traceback
                traceback.print_exc()
                try:
                    from main import log_error
                    log_error(traceback.format_exc())
                except Exception:
                    pass
            return None

    @staticmethod
    def _cache_neighbors(world):
        """The floor's walkable neighbours of a cell, worked out once and kept (the route, flow
        and path searches ask for them millions of times). Emptied every 30 seconds, in case a
        door opened or something was knocked down."""
        g = getattr(world, "grid", None)
        if g is None:
            return {}
        from game.grid import Grid
        from game.grid import FLOOR, DIRS8
        cache = {}
        plain = Grid.neighbors
        exact = type(g).walkable is Grid.walkable     # (a grid with its own walkable(): ask it)

        def neighbors(x, y, _c=cache, _g=g):
            k = (x, y)
            r = _c.get(k)
            if r is None:
                if exact:
                    # the same answer as Grid.neighbors, worked out on the cells directly
                    # (about four times faster than through walkable() and in_bounds())
                    cells, w, h = _g.cells, _g.w, _g.h
                    out = []
                    for dx, dy in DIRS8:
                        nx, ny = x + dx, y + dy
                        if not (0 <= nx < w and 0 <= ny < h) or cells[ny][nx] != FLOOR:
                            continue
                        if dx and dy:
                            ax, by = x + dx, y + dy
                            if not (0 <= ax < w and 0 <= y < h) or cells[y][ax] != FLOOR or \
                                    not (0 <= x < w and 0 <= by < h) or cells[by][x] != FLOOR:
                                continue
                        out.append((nx, ny))
                    r = _c[k] = tuple(out)
                else:
                    r = _c[k] = tuple(plain(_g, x, y))
            return r
        g.neighbors = neighbors
        return cache

    def _round(self):
        from game import tactics
        self._rounds_done = getattr(self, "_rounds_done", 0) + 1
        if self._rounds_done % 15 == 0:
            self._nb_cache.clear()            # (every 30 s: a door may have opened)
            self.__dict__.get("_fit_cache", {}).clear()
        g = self.w.grid
        for m in self.foes():
            if not g.walkable(*m.pos):
                self._relocate(m)             # (one standing in a wall: no arrow reaches it, it can't move)
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
        heroes = self.living_heroes()
        for m in [m for m in self.foes() if getattr(m, "aware", False)]:
            if getattr(m, "boss", None) and getattr(m, "caster", False):
                # an act boss: walks and strikes in real time like any monster (below), and
                # casts its spells (poison, fire, lightning ...) on top, once a round
                if any(chebyshev(m.pos, h.pos) <= CASTER_REACH for h in heroes) and \
                        self._state(m).mode not in ("attack", "cast"):
                    from game import monskills
                    m.ap = max(getattr(m, "ap", 0), getattr(m, "max_ap", 0), getattr(m, "attack_cost", 0))
                    with self._Guard(w, "monsters"), self._short_paths(w.grid):
                        self._engine(monskills.try_cast, w, m)
            if self._engine_moved(m):
                if not any(chebyshev(m.pos, h.pos) <= CASTER_REACH for h in heroes):
                    continue                    # (far from every hero: it waits, as in D2)
                with self._Guard(w, "monsters"), self._short_paths(w.grid):
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

    @staticmethod
    def _engine_moved(m):
        """Caster monsters move with the engine's own code, once a round; act bosses don't (they
        would strike once a second at best and stand about between): the sim moves them."""
        return getattr(m, "caster", False) and not getattr(m, "boss", None)

    class _short_paths:
        """The engine's caster monsters search their way with grid.find_path, which may look
        over the whole floor (60000 cells) when the hero can't be reached - over a second on a
        big outdoor floor, every round. While they move here, a search gives up after
        CASTER_PATH cells; one that far off waits."""

        def __init__(self, grid):
            self.g = grid

        def __enter__(self):
            g = self.g
            full = type(g).find_path

            def find_path(start, goal, blocked=frozenset(), max_cost=None, allow_goal_blocked=False,
                          limit=60000, _full=full, _g=g):
                return _full(_g, start, goal, blocked, max_cost, allow_goal_blocked, min(limit, CASTER_PATH))
            g.find_path = find_path
            return self

        def __exit__(self, *exc):
            self.g.__dict__.pop("find_path", None)
            return False

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
        s.next_think = self.frame + (THINK if u.is_player else PET_THINK if getattr(u, "ally", False) else MONSTER_THINK)
        if u.is_player:
            self._hero_think(u, s)
        elif getattr(u, "ally", False):
            self._pet_think(u, s)
        else:
            self._monster_think(u, s)

    # ------------------------------------------------------------ decisions
    def _hero_think(self, h, s):
        b = self.brain(h)
        self._unstick(h, s)
        if self._no_progress(h, s, b):
            return
        if self._survive(h, s, b):
            return
        if self._loot_or_leave(h, s, b):
            return
        tgt = s.target if (s.target is not None and s.target.alive) else None
        if tgt is None or chebyshev(h.pos, tgt.pos) > HERO_SIGHT or s.skip.get(id(tgt), 0) > self.frame:
            # what he can see: in the open in front of him, not behind a wall (one behind a wall
            # is found by the route below, by walking - so he doesn't turn back and forth
            # between a monster he sees through the wall and the way round to another)
            ranged = self._reach(h) > 1
            seen = [m for m in self.foes() if s.skip.get(id(m), 0) <= self.frame
                    and chebyshev(m.pos, h.pos) <= HERO_SIGHT
                    and (chebyshev(m.pos, h.pos) <= 2 or self._line_clear(h.pos, m.pos))
                    and (self.reachable(h, m) or (ranged and self._can_shoot(h, m)))]
            tgt = self._pick_target(h, seen)
            s.target = tgt
        elif not self._priority(tgt) and self.frame % 10 == 0:
            # a resurrecting monster (a Fallen Shaman, a Greater Mummy...) comes into sight while
            # he is busy with one of its minions: that one first, or it raises them again
            seen = [m for m in self.foes() if s.skip.get(id(m), 0) <= self.frame and self._priority(m) >= 2
                    and chebyshev(m.pos, h.pos) <= HERO_SIGHT
                    and (chebyshev(m.pos, h.pos) <= 2 or self._line_clear(h.pos, m.pos))]
            if seen:
                tgt = self._pick_target(h, seen)
                s.target, s.plan = tgt, None
        if tgt is not None and self._futile(h, s, tgt):
            s.target = None
            s.next_think = self.frame + 1
            return
        # (what the skills are weighed against: awake ones he hasn't given up on for a moment, and
        # can walk to or shoot - not one across a railing he would cast at for ever)
        awake = [m for m in self.foes() if (getattr(m, "aware", False) or chebyshev(m.pos, h.pos) <= HERO_SIGHT)
                 and s.skip.get(id(m), 0) <= self.frame
                 and (m is tgt or self.reachable(h, m) or
                      (chebyshev(m.pos, h.pos) <= brains.SPELL_RANGE and self._can_shoot(h, m)))]
        if self._kite(h, s, b):
            return
        plan = b.decide(tgt, awake)
        if plan is None or plan.what == "attack":
            if tgt is None:
                if self.phase != "fight":
                    return                       # (the boss is dead: no hunting for more, the portal waits)
                route = self.goal_route(h)
                if route is None:
                    s.next_think = self.frame + 1     # (this frame's searches are used up)
                elif route:
                    b.last = "looking for monsters"
                    blocker = self.occ.get(route[0])
                    if blocker not in (None, h) and not self._friendly(h, blocker):
                        # someone in the way: round him by a free cell next to the one after
                        nxt = route[1] if len(route) > 1 else None
                        side = next((c for c in self.w.grid.neighbors(*h.pos) if c not in self.occ
                                     and nxt is not None and chebyshev(c, nxt) <= 1), None)
                        if side is None:
                            s.mode, s.path = "idle", []
                            s.next_think = self.frame + 4     # wait for him to move on
                            return
                        route = [side] + list(route[1:])
                        self.st[("route", id(h))] = (self.st[("route", id(h))][0], self.st[("route", id(h))][1], route)
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
        ready = self.__dict__.setdefault("_ready", set())
        if nxt is not None:
            ready.discard(id(h))
            cell, it = nxt
            if chebyshev(h.pos, cell) <= 1:
                self.take(h, cell, it)
            else:
                b.last = "going for %s" % self._item_name(it)
                if not self._walk_to(h, s, cell, reach=1):
                    self.skip_items.add(id(it))
            return True
        if self.phase == "portal" and self.portal is not None:
            # the group goes through together, once every hero has picked up what he wants
            if chebyshev(h.pos, self.portal) <= 1:
                ready.add(id(h))
                b.last = "at the portal"
            else:
                b.last = "to the portal"
                if not self._walk_to(h, s, self.portal, reach=1):
                    ready.add(id(h))         # (no way to it: he goes through anyway)
            living = self.living_heroes()
            if living and (all(id(x) in ready for x in living) or
                           self.frame >= self.loot_until + LOOT_SECONDS * timing.FPS):
                self.at_portal = True
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
            self.no_room = True              # (the run may send him home to empty his bag)
        return ok

    # ------------------------------------------------------------ staying alive
    RETREAT_AT = 25             # life %: no healing potion left -> home to Tyrael and the traders
    EMERGENCY_AT = 30           # life %: a rejuvenation potion first, if he has one

    def _melee_on(self, h, r=1):
        """Awake melee monsters within r cells of him (their size counted)."""
        return [m for m in self.foes() if getattr(m, "aware", False) and getattr(m, "range", 1) <= 1
                and chebyshev(m.pos, h.pos) <= r + getattr(m, "radius", 0)]

    def _quaff(self, h):
        """Potions, every frame: D2 lets you drink in the middle of a swing, a cast or a hit, and
        a hero who waited for his next decision could die first."""
        s = self._state(h)
        if self.frame < s.next_drink:
            return
        pct = 100.0 * h.hp / max(1, h.max_hp)
        b = self.brain(h)
        if pct >= brains.setting(h, "potion_at") and not (
                getattr(h, "max_mana", 0) and h.mana * 100 < h.max_mana * MANA_DRINK_AT):
            return
        fighting = bool(self._awake_near(h, HERO_SIGHT))
        if pct < self.EMERGENCY_AT and self._drink(h, ("rejuv", "heal")):
            s.next_drink = self.frame + DRINK_COOLDOWN
            b.last = "drinks a potion (life low)"
        elif pct < brains.setting(h, "potion_at") and self._drink(h, ("heal", "rejuv")):
            s.next_drink = self.frame + DRINK_COOLDOWN
            b.last = "drinks a healing potion"
        elif getattr(h, "max_mana", 0) and h.mana * 100 < h.max_mana * MANA_DRINK_AT and \
                (fighting or b.role() in ("caster", "summoner")) and self._drink(h, ("mana", "rejuv")):
            s.next_drink = self.frame + DRINK_COOLDOWN
            b.last = "drinks a mana potion"

    def _survive(self, h, s, b):
        """Getting out of trouble, before anything else (potions: _quaff, every frame). -> True
        when that is what he does this moment."""
        from game import potions
        pct = 100.0 * h.hp / max(1, h.max_hp)
        fighting = bool(self._awake_near(h, HERO_SIGHT))
        has_heal = any(getattr(x, "potion", "") in ("heal", "rejuv") for x in (getattr(h, "belt", None) or []))
        if pct < self.RETREAT_AT and not has_heal and fighting and not getattr(self, "town_spent", False):
            self.need_town = True              # (the run takes him home to be mended)
            b.last = "retreats: no potions left"
            self._back_off(h, s)
            return True
        crowd = self._melee_on(h)
        if pct < 50 and len(crowd) >= 3 and self.frame >= s.next_kite:
            if self._back_off(h, s):           # surrounded and hurt: out of the ring first
                s.next_kite = self.frame + 20
                b.last = "backs out of the crowd"
                return True
        return False

    def _kite(self, h, s, b):
        """Ranged heroes, throwers, casters and summoners keep melee monsters off: when one
        reaches him he steps away (at most twice a second, so he still gets his attacks in)."""
        if b.keep_distance() <= 0 or self.frame < s.next_kite:
            return False
        if not self._melee_on(h, 1):
            return False
        if self._back_off(h, s):
            s.next_kite = self.frame + 12
            b.last = "kiting"
            return True
        s.next_kite = self.frame + 25           # (cornered: he fights for a second)
        return False

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
        reach = brains.SPELL_RANGE - 1         # (a cell spare: the monster may step back while he casts)
        if sk is not None and (getattr(sk, "weapon", False) or sk.kind in ("attack", "melee")):
            reach = self._reach(h)
        if plan.skill == "throw":
            reach = int(getattr(h, "throw_range", brains.THROW_RANGE))
        aim = plan.target.pos if plan.target is not None else plan.cell
        tr = getattr(plan.target, "radius", 0) if plan.target is not None else 0
        reach += tr                          # (a big monster's body is nearer than its middle)
        aimed = (sk is not None and sk.kind not in ("aura", "buff", "cry", "nova", "passive")
                 and sk.kind not in brains.SUMMON_KINDS) or plan.skill == "throw"
        if aim is not None and aimed and chebyshev(h.pos, aim) <= reach and (
                not self._can_shoot(h, aim) or
                (sk is not None and sk.kind == "missile" and plan.target is not None
                 and not self._missile_reaches(h, plan.target))):
            # a pillar or a wall between: walk round until the way is open
            if plan.target is not None and not self.reachable(h, plan.target):
                s.skip[id(plan.target)] = self.frame + 5 * timing.FPS     # (no way round there is)
                s.target = None
                return
            if not self._walk_to(h, s, aim, reach=1, target_r=tr) and plan.target is not None:
                s.skip[id(plan.target)] = self.frame + 2 * timing.FPS
                s.target = None
            return
        if aim is not None and sk is not None and sk.kind not in ("aura", "buff", "cry") and \
                sk.kind not in brains.SUMMON_KINDS and chebyshev(h.pos, aim) > reach:
            if not self._walk_to(h, s, aim, reach=reach - tr, target_r=tr) and plan.target is not None:
                s.skip[id(plan.target)] = self.frame + 2 * timing.FPS     # no way to it: another one
                s.target = None
            return
        if aim is not None and aim != h.pos:
            h.face(*aim)
        self._wake(plan.target)
        s.anim = self.skill_anim(sk, plan.skill)
        s.mode, s.frames, s.plan, s.path = "cast", max(1, plan.frames), plan, []
        s.total = s.frames
        s.hit_at = max(0, s.frames // 2)
        if self.watched:
            self.w.emit("attack", h, aim or h.pos, "cast" if sk is not None and sk.kind not in ("attack", "melee") else "attack")

    @staticmethod
    def skill_anim(sk, name=None):
        """The animation D2 plays for a skill: its Skills.txt anim (A1, A2, TH, SC, S1-S4, KK);
        Throw throws; a weapon skill without one swings or shoots; a spell casts."""
        if name == "throw":
            return "TH"
        d = getattr(sk, "data", None) or {}
        anim = (d.get("anim") or "").strip().upper()
        if anim in ("A1", "A2", "TH", "SC", "KK", "S1", "S2", "S3", "S4"):
            return anim
        if sk is not None and (getattr(sk, "weapon", False) or sk.kind in ("attack", "melee")):
            return "A1"
        return "SC"

    def _cast(self, h, s):
        from game import tactics
        plan = s.plan
        s.plan = None
        if plan is None or not h.alive:
            return
        if plan.target is not None and not plan.target.alive:
            return
        if plan.target is not None and plan.cell is not None:
            plan.cell = plan.target.pos      # aimed where the monster is now, not where it was
                                             # when the cast began (it walks on meanwhile)
        w = self.w
        ok = False
        with self._Guard(w):
            with tactics.acting_as(w, h):
                h.ap = max(getattr(h, "ap", 0), 20)
                n0 = len(w.events)
                before = set(id(m) for m in w.monsters)
                hp0 = {id(m): m.hp for m in self.foes()}
                ok = bool(self._engine(w.use_skill, plan.skill, plan.target, plan.cell))
                for m in self.foes():
                    if m.hp < hp0.get(id(m), m.hp):
                        self._wake(m)        # (hurt by it, wherever it stood: it comes)
                        s.dealt_at = self.frame
                if len(self.foes()) < len(hp0):
                    s.dealt_at = self.frame  # (and one it killed is gone from the list)
                if not ok:
                    # why the engine said no, for the run's log (once per skill per floor)
                    why = [e[1] for e in w.events[n0:] if e and e[0] == "log"]
                    seen = self.st.setdefault(("failed", id(h)), set())
                    if plan.skill not in seen:
                        seen.add(plan.skill)
                        self.notes.append("%s can't use %s: %s" % (h.name, plan.skill, why[-1] if why else
                                                                   (self.last_error or "no reason given")))
                for m in w.monsters:
                    if id(m) not in before and getattr(m, "ally", False):
                        m.summoner = h               # (whose it is: his brain counts his own)
                        self.notes.append("%s summons %s." % (h.name, getattr(m, "name", plan.skill)))
                if not self.watched:
                    del w.events[n0:]
        self.brain(h).done(plan, ok)
        if ok:
            self.casts[plan.skill] = self.casts.get(plan.skill, 0) + 1
            if plan.target is not None:
                self._count_blow(s, plan.target)


    # ------------------------------------------------------------ summons, in real time
    PET_AIS = ("ally", "ally_ranged")
    PET_LEASH = 3               # cells: how close a summon keeps to its summoner with nothing to fight
    PET_GUARD = 12              # cells round the summoner it goes after monsters in

    def pets(self):
        """The heroes' summons that walk and fight (skeletons, golems, wolves, Valkyries,
        revives ...), played frame by frame like everyone else. Turrets, traps, vines and spirits
        keep to the engine's round (allies_turn), which skips these."""
        if getattr(self, "_pets_frame", -1) == self.frame:
            return self._pets
        out = []
        for m in self.w.monsters:
            if m.alive and getattr(m, "ally", False) and not getattr(m, "is_player", False) \
                    and getattr(m, "ai", "") in self.PET_AIS and not getattr(m, "decoy", False) \
                    and not getattr(m, "party_member", False):
                m.realtime = True
                out.append(m)
        self._pets_frame, self._pets = self.frame, out
        return out

    #: summons a hero has up from the start of every floor, as many as his skill level allows
    READY_SUMMONS = ("Raise Skeleton", "Raise Skeletal Mage")

    def prefill_summons(self, h):
        """A necromancer starts each floor with his skeletons and skeletal mages already raised:
        as many as his skill levels allow (Skills.txt petmax), beside him. -> how many rose."""
        from game import tactics
        w = self.w
        book = getattr(h, "skills", None)
        if book is None:
            return 0
        n = 0
        for name in self.READY_SUMMONS:
            s = book.tree.get(name)
            if s is None or s.data is None or book.level(name) <= 0:
                continue
            with self._Guard(w):
                with tactics.acting_as(w, h):
                    try:
                        env = w._skill_env(name)
                        cap = w._petmax(s, env)
                        have = sum(1 for a in w._owned(name) if getattr(a, "summoner", h) is h)
                        for _ in range(max(0, cap - have)):
                            a = w._spawn_ally(s, env, h.pos)
                            if a is None:
                                break
                            a.summoner = h
                            if name == "Raise Skeletal Mage":
                                a.range = 6
                                a.ai = "ally_ranged"
                                a.missile_elem = w.rng.choice(("fire", "cold", "ltng", "pois"))
                            n += 1
                    except Exception:
                        import traceback
                        traceback.print_exc()
            if not self.watched:
                del w.events[:]
        return n

    def _owner(self, a):
        o = getattr(a, "summoner", None)
        if o is not None and o.alive:
            return o
        return self._nearest(a, self.living_heroes(), 10 ** 6)

    def _pet_think(self, a, s):
        """A summon: after the monsters round its summoner (or the one it is near), else back to
        his side."""
        owner = self._owner(a)
        if owner is None:
            return
        key = (self.frame, id(owner))
        if getattr(self, "_guard_key", None) != key:
            # the monsters round a summoner, once a frame for all his summons
            ox, oy = owner.pos
            g = self.PET_GUARD
            self._guard_key = key
            self._guard = [m for m in self.foes() if abs(m.x - ox) <= g and abs(m.y - oy) <= g]
        foes = self._guard
        if not foes:
            ax, ay = a.pos
            foes = [m for m in self.foes() if abs(m.x - ax) <= 6 and abs(m.y - ay) <= 6]
        if s.skip:
            foes = [m for m in foes if s.skip.get(id(m), 0) <= self.frame]
        tgt = s.target if (s.target is not None and s.target.alive and s.target in foes) else \
            self._nearest(a, foes, 10 ** 6)
        if tgt is not None:
            s.target = tgt
            tgt.aware = True
            self._engage(a, s, tgt, self._reach(a))
            return
        s.target = None
        if chebyshev(a.pos, owner.pos) > self.PET_LEASH:
            self._walk_to(a, s, owner.pos, reach=2)
        else:
            s.mode, s.path = "idle", []

    def area_of(self, u_or_cell):
        """The walkable area a unit or cell is in (see label_areas), None if unknown."""
        areas = getattr(self.w, "_areas", None)
        if areas is None:
            areas = label_areas(self.w)
        c = u_or_cell if isinstance(u_or_cell, tuple) else u_or_cell.pos
        a = areas.get(c)
        if a is None:
            # (standing on a cell that isn't floor - a big body over an edge: the area of a
            # floor cell next to it)
            x, y = c
            for dx in (-1, 0, 1, -2, 2):
                for dy in (-1, 0, 1, -2, 2):
                    a = areas.get((x + dx, y + dy))
                    if a is not None:
                        return a
        return a

    def reachable(self, a, b):
        """a can walk to b (or next to it)."""
        x, y = self.area_of(a), self.area_of(b)
        return x is None or y is None or x == y

    def _monster_think(self, m, s):
        heroes = self.living_heroes() + self.pets()      # (summons are fought like heroes)
        near = [u for u in heroes if self.reachable(m, u) or
                (self._reach(m) > 1 and chebyshev(m.pos, u.pos) <= self._reach(m) + 2 and self._can_shoot(m, u))]
        tgt = self._nearest(m, near, 10 ** 6)
        if tgt is None:
            # every hero is where it can't walk (across a railing, a chasm): it waits there -
            # no search for a way that isn't there
            s.mode, s.path = "idle", []
            s.next_think = self.frame + 2 * timing.FPS
            return
        s.target = tgt
        self._engage(m, s, tgt, self._reach(m))

    def _reach(self, u):
        if getattr(u, "is_player", False):
            if getattr(u, "ranged", False):
                return max(2, int(getattr(u, "range", 1)))
            return max(1, int(getattr(u, "reach", 1)))
        return max(1, int(getattr(u, "range", 1)))

    @staticmethod
    def _friendly(a, b):
        """Both on the heroes' side (heroes and their summons)."""
        side = lambda x: bool(getattr(x, "is_player", False) or getattr(x, "ally", False))
        return side(a) and side(b)

    def _can_shoot(self, a, b):
        """A shot or a missile from a reaches b: next to it, or open floor all the way (a pillar
        or a wall corner between them stops it, as in D2)."""
        apos, bpos = getattr(a, "pos", a), getattr(b, "pos", b)
        return chebyshev(apos, bpos) <= 1 + getattr(b, "radius", 0) or self._line_clear(apos, bpos)

    def _missile_reaches(self, h, tgt):
        """The engine's own flight for a missile spell from h at tgt hits a monster (the line it
        flies can differ from the one the hero looks along: it must not end in a wall)."""
        fn = getattr(self.w, "_first_hit_on_line", None)
        if fn is None:
            return True
        try:
            hit, _end = fn(h.pos, tgt.pos, max_len=chebyshev(h.pos, tgt.pos) + 2)
        except Exception:
            return True
        return bool(hit)

    FUTILE_BLOWS = 8            # blows and casts at one monster without its life going down
    FUTILE_SKIP = 10            # seconds it is then left alone

    @staticmethod
    def _count_blow(s, tgt):
        f = s.futile
        if f is None or f[0] != id(tgt):
            s.futile = [id(tgt), tgt.hp, 1]
        else:
            f[2] += 1

    def _fits_terrain(self, r):
        """{cell: can a body of radius r stand there (floor under all of it)}, filled as asked."""
        cache = self.__dict__.setdefault("_fit_cache", {})
        return cache.setdefault(r, {})

    def _path_big(self, u, goal, reach, target_r, limit, r=None):
        """The engine's path_near for a big monster (radius 1 or more), without its cost: there
        every cell looked at checked the monster's whole body against the floor and every unit
        (Python's profiler on a player's PC: 79 ms a search, two thirds of all the game's time).
        Here the floor under a body is worked out once per cell and floor, and the other units'
        cells are widened by the body once per search."""
        import heapq
        if r is None:
            r = getattr(u, "radius", 0)
        g = self.w.grid
        fit = self._fits_terrain(r)
        cells, gw, gh = g.cells, g.w, g.h
        from game.grid import FLOOR
        exact = type(g).walkable is __import__("game.grid", fromlist=["Grid"]).Grid.walkable

        def terrain(c):
            v = fit.get(c)
            if v is None:
                x, y = c
                v = True
                for dy in range(-r, r + 1):
                    for dx in range(-r, r + 1):
                        cx, cy = x + dx, y + dy
                        if exact:
                            if not (0 <= cx < gw and 0 <= cy < gh) or cells[cy][cx] != FLOOR:
                                v = False
                                break
                        elif not g.walkable(cx, cy):
                            v = False
                            break
                    if not v:
                        break
                fit[c] = v
            return v
        mine = set()
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                mine.add((u.x + dx, u.y + dy))
        wide = set()
        blockers = [c for c, o in self.occ.items() if o is not u and c not in mine]
        blockers += [c for c in (getattr(self.w, "obj_block", None) or ()) if c not in mine]
        for c in blockers:
            x, y = c
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    wide.add((x + dx, y + dy))
        start = u.pos
        want = reach + r + target_r
        if chebyshev(start, goal) <= want:
            return []
        heap = [(chebyshev(start, goal), 0, start)]
        came = {start: None}
        cost = {start: 0}
        n = 0
        while heap:
            _, gc, cur = heapq.heappop(heap)
            n += 1
            if n > limit:
                return None
            if cur != start and chebyshev(cur, goal) <= want:
                path = []
                while cur != start:
                    path.append(cur)
                    cur = came[cur]
                path.reverse()
                return path
            if gc > cost.get(cur, 1 << 30):
                continue
            for nb in g.neighbors(*cur):
                if nb in wide or not terrain(nb):
                    continue
                ng = gc + 1
                if ng < cost.get(nb, 1 << 30):
                    cost[nb] = ng
                    came[nb] = cur
                    heapq.heappush(heap, (ng + max(0, chebyshev(nb, goal) - want), ng, nb))
        return None

    def _tick_poison(self):
        """D2's poison: its damage a little at a time over its length (here every POISON_EVERY
        frames, what those frames would have done). Who poisoned it gets the kill."""
        w = self.w
        units = [u for u in w.monsters if u.alive and (getattr(u, "effects", None) or {}).get("poison_rt")]
        units += [h for h in self.heroes if h.alive and (getattr(h, "effects", None) or {}).get("poison_rt")]
        if not units:
            return
        from game import dmglog
        with self._Guard(w):
            for u in units:
                eff = u.effects
                rate, left, src = eff["poison_rt"]
                n = min(POISON_EVERY, left)
                acc = eff.get("poison_acc", 0.0) + rate * n
                dmg = int(acc)
                eff["poison_acc"] = acc - dmg
                left -= n
                if left <= 0:
                    for k in ("poison_rt", "poison", "poison_src", "poison_acc"):
                        eff.pop(k, None)
                else:
                    eff["poison_rt"] = [rate, left, src]
                    eff["poison"] = [max(1, int(rate * 25)), max(1, left // 50)]
                if dmg > 0:
                    try:
                        dmglog.new_blow(w)
                        self._engine(w._damage, u, dmg, src)
                    except Exception:
                        u.hp = max(0, u.hp - dmg)

    def _relocate(self, m):
        """Put a monster on the nearest free floor cell: one inside a wall, a rock or a pillar
        (a big monster set down partly on one) can't be hit by missiles and can't move itself, so
        hero and monster would stand facing each other for ever."""
        g = self.w.grid
        seen = {m.pos}
        q = deque([m.pos])
        while q and len(seen) < 4000:
            c = q.popleft()
            if c != m.pos and g.walkable(*c) and c not in self.occ:
                if self.occ.get(m.pos) is m:
                    del self.occ[m.pos]
                m.x, m.y = c
                self.occ[c] = m
                st = self._state(m)
                st.path, st.path_goal, st.prog = [], None, 0.0
                return True
            x, y = c
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (x + dx, y + dy)
                    if n not in seen and g.in_bounds(*n):
                        seen.add(n)
                        q.append(n)
        return False

    def _futile(self, h, s, tgt):
        """A monster whose life doesn't go down whatever he does (one stuck in a wall that
        missiles can't reach, one immune to all he has): leave it and go on to the others.
        A boss is never left - the floor needs it dead."""
        f = s.futile
        if f is None or f[0] != id(tgt):
            return False
        if tgt.hp < f[1]:
            f[1], f[2] = tgt.hp, 0
            return False
        f[1] = max(f[1], tgt.hp)
        if f[2] < self.FUTILE_BLOWS:
            return False
        if getattr(tgt, "rift_boss", False):
            f[2] = 0
            self._relocate(tgt)              # (the boss isn't left: it is put on open floor)
            return False
        s.futile = None
        s.skip[id(tgt)] = self.frame + self.FUTILE_SKIP * timing.FPS
        self._relocate(tgt)                  # (wherever it stood, it stands on open floor now)
        self.notes.append("%s leaves %s at %d,%d: %d attacks did nothing to it." % (
            h.name, getattr(tgt, "name", "a monster"), tgt.pos[0], tgt.pos[1], self.FUTILE_BLOWS))
        return True

    def _engage(self, u, s, tgt, reach):
        r = getattr(u, "radius", 0) + getattr(tgt, "radius", 0)
        if reach > 1 and chebyshev(u.pos, tgt.pos) <= reach + r and not self._can_shoot(u, tgt):
            # in range but something in the way: closer, until the way is open
            if not self._walk_to(u, s, tgt.pos, reach=1, target_r=getattr(tgt, "radius", 0)):
                s.skip[id(tgt)] = self.frame + 2 * timing.FPS
                s.target = None
            return
        if chebyshev(u.pos, tgt.pos) <= reach + r:
            self._start_attack(u, s, tgt, ranged=reach > 1)
        elif not self._walk_to(u, s, tgt.pos, reach=reach, target_r=getattr(tgt, "radius", 0)):
            # no way to it from here (behind a wall, or boxed in by its own pack): pick another
            # (after the boss, longer: the floor is done and the portal waits)
            s.skip[id(tgt)] = self.frame + (2 if self.phase == "fight" else 10) * timing.FPS
            s.target = None
            # (a hero looks for another at once; a monster has only the heroes to go for, so it
            # waits 2 s before it searches again - not a failed search every frame)
            s.next_think = self.frame if u.is_player else self.frame + 2 * timing.FPS

    RAISERS = ("resurrect", "raise", "revive")

    def _priority(self, m):
        """How much sooner than its distance says a hero goes for this monster:
        2 - it brings the dead back (Fallen and Fetish Shamans, Greater Mummies...): kill it first,
            or everything else killed gets up again;
        1 - another caster (mages, priests...): it hurts from afar and hides behind the others;
        0 - the rest."""
        p = getattr(m, "_ab_priority", None)
        if p is None:
            skills = " ".join(str(x) for x in (getattr(m, "mskills", None) or [])).lower()
            name = str(getattr(m, "name", "")).lower()
            if getattr(m, "ai", "") == "shaman" or "shaman" in name or any(k in skills for k in self.RAISERS):
                p = 2
            elif getattr(m, "caster", False):
                p = 1
            else:
                p = 0
            try:
                m._ab_priority = p
            except Exception:
                pass
        return p

    PRIORITY_CELLS = (0, 4, 10)    # cells nearer a monster of priority 0 / 1 / 2 counts as

    def _pick_target(self, h, units):
        """The monster in sight to go for: the nearest, but resurrecting monsters count as 10
        cells nearer and other casters 4 (and the floor's boss 3)."""
        best, bd = None, None
        for o in units:
            d = chebyshev(h.pos, o.pos) - self.PRIORITY_CELLS[self._priority(o)]
            if getattr(o, "rift_boss", False):
                d -= 3
            if bd is None or d < bd:
                best, bd = o, d
        return best

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
        walk to, by walking distance (a breadth-first search over the whole floor, so a wall or
        the map's edge between them never fools him, and he never turns back and forth between
        two half-searched guesses). A big floor is searched over several frames, SEARCH_CHUNK
        cells at a time, at most FRAME_NODES cells a frame for all runs together; he waits
        meanwhile.

        The route is kept while he walks it (at most ROUTE_SECONDS). -> the cells still ahead of
        him, [] when there is nowhere to go, None while the search is still going."""
        key = ("route", id(h))
        ent = self.st.get(key)
        old = None
        if ent is not None:
            until, foe, route = ent
            if (foe is None or foe.alive) and route:
                if h.pos in route:
                    route = route[route.index(h.pos) + 1:]
                    self.st[key] = (until, foe, route)
                if route and chebyshev(h.pos, route[0]) <= 1:
                    if until > self.frame:
                        return route
                    old = route                  # (stale: walked on while a new one is searched)
        skey = ("search", id(h))
        gen = self.st.get(skey)
        if gen is None or (old is None and gen[0] != h.pos):
            gen = self.st[skey] = (h.pos, self._route_search(h))
        try:
            while BUDGET["nodes"] < FRAME_NODES:
                BUDGET["nodes"] += SEARCH_CHUNK
                next(gen[1])
            return old                          # (not done: more next frame)
        except StopIteration as done:
            foe, route = done.value
        self.st.pop(skey, None)
        if old is not None and gen[0] != h.pos and h.pos in route:
            route = route[route.index(h.pos) + 1:]     # (searched from where he was a moment ago)
        elif old is not None and gen[0] != h.pos:
            self.st.pop(key, None)
            return old
        self.st[key] = (self.frame + ROUTE_SECONDS * timing.FPS, foe, route)
        if foe is None and self.foes():
            skip = self._state(h).skip
            if any(skip.get(id(m), 0) > self.frame and self.reachable(h, m) for m in self.foes()):
                pass                         # (only some he has given up on for a moment: not
                                             # "none left to reach" - he looks again later)
            elif any(getattr(m, "rift_boss", False) for m in self.foes()):
                self._bring_boss(h)          # the floor's boss can't be reached: it comes to him
            else:
                self.stranded = True         # monsters left, none of them reachable: floor done
        return route

    def _bring_boss(self, h):
        """The floor's boss stands where no hero can walk to: it is put on open floor 5-8 cells
        from the hero (the floor is only done when it is dead, so it can't be left there)."""
        g = self.w.grid
        for m in self.foes():
            if not getattr(m, "rift_boss", False):
                continue
            r = getattr(m, "radius", 0)
            for d in (6, 5, 7, 8, 4, 3):
                ring = [(h.x + dx, h.y + dy) for dx in range(-d, d + 1) for dy in range(-d, d + 1)
                        if max(abs(dx), abs(dy)) == d]
                random.shuffle(ring)
                for c in ring:
                    if all(g.walkable(c[0] + a, c[1] + b) and ((c[0] + a, c[1] + b) not in self.occ
                                                                or self.occ.get((c[0] + a, c[1] + b)) is m)
                           for a in range(-r, r + 1) for b in range(-r, r + 1)) and self._line_clear(h.pos, c):
                        m.x, m.y = c
                        m.aware = True
                        self._rebuild_occ()
                        st = self._state(m)
                        st.path, st.path_goal, st.prog = [], None, 0.0
                        self.notes.append("%s couldn't be reached: it comes out." % getattr(m, "name", "The boss"))
                        return True
        return False

    def _route_search(self, h):
        """Breadth-first over the floor from the hero, SEARCH_CHUNK cells per step (a generator:
        it returns (monster, cells to beside it), or (None, []) when none can be reached)."""
        skip = self._state(h).skip
        foes = [m for m in self.foes() if skip.get(id(m), 0) <= self.frame and self.reachable(h, m)]
        at = {}
        for m in foes:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    at.setdefault((m.x + dx, m.y + dy), m)
        if not at:
            return None, []
        g = self.w.grid
        start = h.pos
        occ = self.occ
        came = {start: None}
        q = deque([start])
        n = 0
        while q:
            c = q.popleft()
            m = at.get(c)
            if m is not None and c != start and m.alive:
                route = []
                while c is not None and c != start:
                    route.append(c)
                    c = came[c]
                route.reverse()
                if route and route[-1] == m.pos:
                    route.pop()              # stop beside it, not on it
                return m, route
            for nb in g.neighbors(*c):
                if nb not in came:
                    came[nb] = c
                    o = occ.get(nb)
                    if o is not None and nb not in at and not getattr(o, "ally", False) \
                            and not getattr(o, "is_player", False):
                        continue             # (a monster stands there: the way goes round it;
                                             #  his own side moves out of the way)
                    q.append(nb)
            n += 1
            if n >= SEARCH_CHUNK:
                n = 0
                yield
        return None, []

    # ------------------------------------------------------------ actions
    def _wake(self, m):
        """A monster a hero or a summon goes for wakes up, and so does its pack (as in D2: shoot
        one from off screen and they all come for you)."""
        if m is None or getattr(m, "ally", False) or getattr(m, "is_player", False):
            return
        if not getattr(m, "aware", False):
            m.aware = True
            mx, my = m.pos
            for o in self.foes():
                if not getattr(o, "aware", False) and abs(o.x - mx) <= PACK and abs(o.y - my) <= PACK:
                    o.aware = True

    def _start_attack(self, u, s, tgt, ranged=False):
        if u.is_player or getattr(u, "ally", False):
            self._wake(tgt)
        u.face(*tgt.pos)
        fpd, speed = self.t.fpd(u, "A1")
        if u.is_player:
            ias = u.mod("ias") if hasattr(u, "mod") else 0
            frames = timing.attack_frames(fpd, ias, self._wsm(u), 0, speed)
        else:
            frames = timing.attack_frames(fpd, 0, 0, 0, speed)
        s.mode, s.frames, s.target, s.total = "attack", frames, tgt, frames
        s.anim = "A1"
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
        if u.is_player:
            self._count_blow(s, tgt)
            self._dealt_check = (s, tgt, before)
        try:
            el = getattr(u, "missile_elem", None) if getattr(u, "ally", False) and not u.is_player else None
            if el and s.kind == "arrow":
                # a summon that shoots its element (the skeletal mages)
                if self.watched:
                    self.w.emit("projectile", u, u.pos, tgt.pos, {"fire": "fireball", "cold": "cold", "ltng": "ltng"}.get(el, "spike"))
                lo, hi = u.dmg
                self.w.elem_hit(tgt, el, lo, hi * 2, u, 50, show=False)
            else:
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
                # beyond the map's reach: straight at him while the way is open, else a path
                # search below (an awake monster far off still comes - it never just waits)
                step = self._direct_step(u, goal) if self._line_clear(u.pos, goal) else None
                if step is None:
                    step = False
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
            limit = 3000 if u.is_player else (600 if getattr(u, "ally", False) else 1500)
            if u.is_player and d <= 12:
                limit = 800                  # (somewhere close: a long search means there is no way)
            blocked = None
            if u.is_player or getattr(u, "ally", False):
                # his own side moves out of his way (they change places): only monsters block him
                blocked = {c for c, o in self.occ.items() if o is not u and not self._friendly(u, o)}
            if getattr(u, "radius", 0):
                path = self._path_big(u, goal, reach, target_r, BIG_PATH)
                if not path:
                    # its whole body doesn't fit through (a narrow passage): it squeezes through
                    # like a small one, as D2's big monsters do, rather than standing there
                    path = self._path_big(u, goal, reach, target_r, BIG_PATH, r=0)
            else:
                path = self.w.path_near(u, goal, reach=reach, target_r=target_r, limit=limit, blocked=blocked)
            s.path_goal = goal
            s.next_path = self.frame + (REPATH * 3 if (u.is_player and d > DIRECT) or d > FLOW_R else REPATH)
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
        if ent is not None and (chebyshev(ent[1], h.pos) <= 2 or self.frame - ent[0] < FLOW_EVERY):
            return ent[2]                   # (a step or two off: still good enough to close in)
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

    NO_PROGRESS = 8     # seconds without moving a cell or taking life off a monster, monsters about

    def _no_progress(self, h, s, b):
        """A hero who for 8 seconds has neither moved a cell nor hurt a monster, with monsters
        awake near him (shooting into a wall, a skill the engine refuses, a target he can't
        reach...): what he was doing is written to stuck.log, he leaves that monster for 10 s and
        walks off a few cells to look again."""
        chk = getattr(self, "_dealt_check", None)
        if chk is not None:
            self._dealt_check = None
            st, tgt, before = chk
            if tgt.hp < before or not tgt.alive:
                st.dealt_at = self.frame
        last = max(s.moved_at, s.dealt_at, getattr(self, "_floor_start", 0))
        if self.frame - last < self.NO_PROGRESS * timing.FPS:
            return False
        if not any(getattr(m, "aware", False) and chebyshev(m.pos, h.pos) <= HERO_SIGHT
                   and (self.reachable(h, m) or self._can_shoot(h, m)) for m in self.foes()):
            # (every awake monster near counts here, also one he has given up on for a while:
            # one he can't hit and that can't reach him is what holds him)
            s.dealt_at = self.frame
            return False
        s.dealt_at = s.moved_at = self.frame
        tgt = s.target
        self._write_stuck(h, s, b, tgt)
        if tgt is not None:
            s.skip[id(tgt)] = self.frame + 10 * timing.FPS
            self._relocate(tgt)
        s.target, s.plan, s.path, s.path_goal = None, None, [], None
        s.mode, s.frames = "idle", 0
        self.st.pop(("route", id(h)), None)
        g = self.w.grid
        here = h.pos
        cells = [(here[0] + dx, here[1] + dy) for dx in range(-6, 7) for dy in range(-6, 7)
                 if 3 <= max(abs(dx), abs(dy)) and g.walkable(here[0] + dx, here[1] + dy)
                 and (here[0] + dx, here[1] + dy) not in self.occ
                 and self.reachable(here, (here[0] + dx, here[1] + dy))]
        random.shuffle(cells)
        for c in cells[:6]:
            if self._walk_to(h, s, c, reach=0):
                break
        b.last = "stuck: moving off to look again"
        self.notes.append("%s was stuck (nothing hit, not moving for %d s): moved off. Details in stuck.log." % (
            h.name, self.NO_PROGRESS))
        return True

    def _write_stuck(self, h, s, b, tgt):
        try:
            import os
            import time
            here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            lines = ["%s  %s (%s) at %s, floor %s, frame %d" % (
                time.strftime("%Y-%m-%d %H:%M:%S"), h.name, getattr(h, "cls", "?"), h.pos,
                getattr(self.w, "level_name", "?"), self.frame)]
            lines.append("  doing: %s; mode %s; plan %s; life %d/%d mana %d/%d" % (
                b.last, s.mode, getattr(s.plan, "skill", None) or getattr(s.plan, "kind", None),
                h.hp, h.max_hp, getattr(h, "mana", 0), getattr(h, "max_mana", 0)))
            if tgt is not None:
                lines.append("  target: %s at %s, %d cells, life %d/%d, line of fire %s, missile path %s, walkable %s" % (
                    getattr(tgt, "name", "?"), tgt.pos, chebyshev(h.pos, tgt.pos), tgt.hp, tgt.max_hp,
                    self._can_shoot(h, tgt.pos), self._missile_reaches(h, tgt),
                    self.w.grid.walkable(*tgt.pos)))
            near = sorted(self._awake_near(h), key=lambda m: chebyshev(h.pos, m.pos))[:6]
            lines.append("  awake near: " + ", ".join("%s %s %d/%d" % (getattr(m, "name", "?"), m.pos, m.hp, m.max_hp)
                                                      for m in near))
            lines.append("  reasons: " + "; ".join(self.notes[-4:]))
            logs = [e[1] for e in list(getattr(self.w, "events", []))[-200:]
                    if isinstance(e, tuple) and len(e) > 1 and e[0] == "log"]
            lines.append("  engine log: " + " | ".join(str(t) for t in logs[-6:]))
            with open(os.path.join(here, "stuck.log"), "a") as f:
                f.write("\n".join(lines) + "\n\n")
        except Exception:
            pass

    def _unstick(self, h, s):
        """A hero who hasn't moved for 3 seconds while he means to go somewhere (and isn't
        fighting): drop his path and route, leave his target be for a while, and look again."""
        if s.last_pos != h.pos:
            s.last_pos, s.moved_at = h.pos, self.frame
            return False
        if s.mode in ("attack", "cast", "gethit") or self.frame - max(s.moved_at, s.unstuck_at) < 3 * timing.FPS:
            return False
        s.unstuck_at = self.frame            # (not moved_at: the 8-second stall check counts on it)
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
            if other is not None and other is not u and self._friendly(u, other) and \
                    self._state(other).mode == "walk" and self._state(other).path:
                # one of his own side walking on ahead: follow, don't change places (two who
                # swap back and forth undo each other's steps and never get anywhere)
                s.prog = min(s.prog, 1.0)
                break
            if other is not None and other is not u and self._friendly(u, other) and not getattr(other, "radius", 0) \
                    and self._state(other).mode not in ("attack", "cast"):
                # one of his own side in the way: they change places, as D2's minions make way
                if self.occ.get(u.pos) is u:
                    del self.occ[u.pos]
                other.x, other.y = u.pos
                self.occ[other.pos] = other
                os_ = self._state(other)
                os_.path, os_.mode = [], "idle"
                other = None
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
        """A potion of the first of `kinds` he has anywhere in his belt (any row, as a right click
        in D2's open belt), by the engine's own potion code - as him, so every hero of a group
        drinks from his own belt."""
        from game import potions, tactics
        w = self.w
        try:
            best = None
            for c in range(potions.belt_slots(h)):
                for row, it in enumerate(potions.column(h, c)):
                    k = getattr(it, "potion", "")
                    if k in kinds:
                        key = (kinds.index(k), row)
                        if best is None or key < best[0]:
                            best = (key, c, row)
            if best is None:
                return False
            with self._Guard(w):
                with tactics.acting_as(w, h):
                    h.ap = max(getattr(h, "ap", 0), 10)
                    return bool(self._engine(potions.drink, w, best[1], best[2]))
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
        share = getattr(self.w, "_clear_share", None)
        if share:
            # (a level to get through, not to empty: done when most of it is dead)
            if self._foes_at_start is None:
                self._foes_at_start = max(1, len(self.foes()))
            return len(self.foes()) <= self._foes_at_start * share
        return not self.foes()

    def wiped(self):
        return not self.living_heroes()
