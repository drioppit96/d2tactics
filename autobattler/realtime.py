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
- A hero drinks a healing potion from his belt below DRINK_AT of his life, at most once a second.
"""
import random

from game.grid import chebyshev

from . import timing

AGGRO = 14              # cells: a monster this close to a hero wakes up
HERO_SIGHT = 18         # cells: how far a hero looks for something to fight
AI_DELAY = 8            # frames a monster waits after its attack before the next decision
DRINK_AT = 0.45         # drink below this share of life
DRINK_COOLDOWN = 25     # frames between two potions
REPATH = 12             # frames between two path searches while chasing
HERO_WALK = 6.0         # CharStats WalkVelocity
HERO_RUN = 9.0          # CharStats RunVelocity (heroes run while on a run)
MONSTER_VEL = 4.0       # when MonStats can't be read


class State:
    __slots__ = ("mode", "frames", "hit_at", "target", "path", "prog", "next_path", "next_drink",
                 "speed", "kind")

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


class Sim:
    def __init__(self, world, heroes, timings=None, move_scale=1.0, rng=None):
        self.w = world
        self.heroes = list(heroes)
        self.t = timings or timing.Timings(getattr(getattr(world, "content", None), "src", None))
        self.move_scale = move_scale
        self.rng = rng or random.Random()
        self.frame = 0
        self.st = {}
        self.kills = 0
        self.watched = False        # while False the engine's animation events are thrown away
        for h in self.heroes:
            self._state(h)

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
        return [m for m in self.w.monsters
                if m.alive and not getattr(m, "ally", False) and getattr(m, "ai", "") != "npc"]

    # ------------------------------------------------------------ one frame
    def tick(self):
        self.frame += 1
        heroes = self.living_heroes()
        if not heroes:
            return
        for m in self.foes():
            if not getattr(m, "aware", False) and any(chebyshev(m.pos, h.pos) <= AGGRO for h in heroes):
                m.aware = True
        for u in heroes + [m for m in self.foes() if getattr(m, "aware", False)]:
            if u.alive:
                self._step(u)
        if not self.watched:
            del self.w.events[:]

    def _step(self, u):
        s = self._state(u)
        if s.mode in ("attack", "gethit"):
            s.frames -= 1
            if s.mode == "attack" and s.frames == s.hit_at:
                self._land(u, s)
            if s.frames > 0:
                return
            s.mode = "idle"
            if not u.is_player:
                s.frames = AI_DELAY
            return
        if s.mode == "idle" and s.frames > 0:
            s.frames -= 1
            return
        if u.is_player:
            self._hero_think(u, s)
        else:
            self._monster_think(u, s)

    # ------------------------------------------------------------ decisions
    def _hero_think(self, h, s):
        if h.hp < h.max_hp * DRINK_AT and self.frame >= s.next_drink:
            if self._drink(h):
                s.next_drink = self.frame + DRINK_COOLDOWN
        tgt = s.target if (s.target is not None and s.target.alive) else None
        if tgt is None or chebyshev(h.pos, tgt.pos) > HERO_SIGHT:
            tgt = self._nearest(h, self.foes(), HERO_SIGHT)
            s.target = tgt
        if tgt is None:
            goal = self.goal_cell()
            if goal is not None and chebyshev(h.pos, goal) > 2:
                self._walk_to(h, s, goal, reach=1)
            return
        self._engage(h, s, tgt, self._reach(h))

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
        else:
            self._walk_to(u, s, tgt.pos, reach=reach, target_r=getattr(tgt, "radius", 0))

    def _nearest(self, u, units, limit):
        best, bd = None, limit + 1
        for o in units:
            d = chebyshev(u.pos, o.pos)
            if d < bd:
                best, bd = o, d
        return best

    def goal_cell(self):
        """Where a hero heads when nothing is in sight: the floor's boss, else the far end."""
        boss = next((m for m in self.w.monsters if m.alive and getattr(m, "rift_boss", False)), None)
        if boss is not None:
            return boss.pos
        rest = self.foes()
        if rest:
            h = self.living_heroes()[0]
            return min(rest, key=lambda m: chebyshev(m.pos, h.pos)).pos
        return None

    # ------------------------------------------------------------ actions
    def _start_attack(self, u, s, tgt, ranged=False):
        u.face(*tgt.pos)
        fpd, speed = self.t.fpd(u, "A1")
        if u.is_player:
            ias = u.mod("ias") if hasattr(u, "mod") else 0
            frames = timing.attack_frames(fpd, ias, self._wsm(u), 0, speed)
        else:
            frames = timing.attack_frames(fpd, 0, 0, 0, speed)
        s.mode, s.frames, s.target = "attack", frames, tgt
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
        if was_alive and not tgt.alive and not tgt.is_player:
            self.kills += 1
        elif tgt.alive and lost > 0:
            share = 12 if tgt.is_player else 8
            if lost * share >= tgt.max_hp:
                self._hit_recovery(tgt)

    def _hit_recovery(self, u):
        s = self._state(u)
        fpd, speed = self.t.fpd(u, "GH")
        fhr = u.mod("fhr") if getattr(u, "is_player", False) and hasattr(u, "mod") else 0
        s.mode = "gethit"
        s.frames = timing.hit_recovery_frames(fpd, fhr, speed)
        s.hit_at = -1
        s.path = []

    def _walk_to(self, u, s, goal, reach=1, target_r=0):
        if s.speed <= 0:
            return
        if not s.path or self.frame >= s.next_path:
            path = self.w.path_near(u, goal, reach=reach, target_r=target_r, limit=6000)
            s.next_path = self.frame + REPATH
            s.path = list(path or [])
            if not s.path:
                return
        s.mode = "walk"
        s.prog += s.speed / timing.FPS
        moved = []
        while s.prog >= 1.0 and s.path:
            nxt = s.path[0]
            other = self.w.unit_at(nxt)
            if other is not None and other is not u:
                s.path = []              # someone stepped in the way: look again next frame
                s.next_path = self.frame
                s.prog = 0.0
                break
            s.path.pop(0)
            s.prog -= 1.0
            u.face(*nxt)
            u.x, u.y = nxt
            moved.append(nxt)
        if moved:
            if u.is_player and u is getattr(self.w, "player", None):
                try:
                    self.w.grid.update_visibility(u.pos, self.w.sight_radius())
                except Exception:
                    pass
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

    def _drink(self, h):
        """A healing (or rejuvenation) potion from the belt, by the engine's own potion code."""
        from game import potions
        w = self.w
        if h is not w.player:
            return False                 # (the engine's potion code drinks for world.player)
        try:
            for c in range(potions.belt_slots(h)):
                col = potions.column(h, c)
                if col and getattr(col[0], "potion", "") in ("heal", "rejuv"):
                    old_mode = w.mode
                    w.mode = "explore"   # no AP in real time
                    h.ap = max(getattr(h, "ap", 0), 10)
                    try:
                        return bool(potions.drink(w, c))
                    finally:
                        w.mode = old_mode
        except Exception:
            import traceback
            traceback.print_exc()
        return False

    # ------------------------------------------------------------ results
    def boss_dead(self):
        bosses = [m for m in self.w.monsters if getattr(m, "rift_boss", False)]
        return bool(bosses) and not any(m.alive for m in bosses)

    def cleared(self):
        """The floor is done: its boss is dead (or, with no boss on it, every monster is)."""
        if any(getattr(m, "rift_boss", False) for m in self.w.monsters):
            return self.boss_dead()
        return not self.foes()

    def wiped(self):
        return not self.living_heroes()
