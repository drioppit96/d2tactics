"""Runs: one hero (or a group) grinding rift floors one after another, in real time.

A run builds a rift floor (game/rift.py, at twice the usual size when big_maps is on), puts the
heroes at its start, and plays it frame by frame with autobattler/realtime.py until the floor's
boss is dead (next floor, one deeper) or every hero on the run is dead (the run is over).

Between floors the heroes are healed, as if they had been back to town. Heroes are saved after
every floor and when the run ends.

RunManager holds every run of the account and plays at most max_active heroes at once.

Floors are built on a background thread, one at a time, so the game keeps playing (and drawing)
while a run builds its next floor. Each floor is rolled from a new seed when it is built (its
place within the act, its monsters, its map), so the same depth is a different floor every time.
The rift keeps floor plans in module globals keyed by depth; a build replaces the plan of its
depth under the build lock.

Without Diablo II files (placeholder art) a run plays on the engine's simple generated cave
instead, with the monster farthest from the start as its boss. That is also how the tests run.
"""
import random
import threading
from time import perf_counter as _clock

from . import brain, gear, realtime, roster, timing

BUILD_LOCK = threading.Lock()       # one floor built at a time
PREBUILD = True                     # build the next floor while this one is played

#: set by the screen while it works out and draws a frame: floors built ahead wait meanwhile
MAIN_BUSY = [False]

#: build jobs a run is waiting for (its floor is due): they go before any floor built ahead,
#: and while there is one, nothing steps aside for the screen
WAITING = set()
HOLDER = [None]     # the thread building now (for perf.log)
HOLDER_NOTE = [None]    # the premade floors' process at work (for perf.log)

_GIVE = [0.0]


class _Aborted(BaseException):
    """A floor being built ahead is dropped when a run needs its own floor now: one floor is
    built at a time, and the run waiting must not wait for a floor that isn't needed yet. (Not
    an Exception, so the engine's own "except Exception" doesn't catch it.)"""


def _hook_for(job):
    """The profile hook of a thread building a floor ahead (see _give_way)."""
    def hook(frame, event, arg, _job=job, _waiting=WAITING, _give=_give_way):
        if event == "call" and _waiting and _job.get("locked") and not _job.get("needed"):
            # (only as a Python function starts: raised as a C call returns, it could leave a
            # lock taken - a with-block's lock is taken in C before the block begins)
            raise _Aborted()
        _give(frame, event, arg)
    return hook


def _give_way(frame, event, arg, _busy=MAIN_BUSY, _waiting=WAITING, _give=_GIVE,
              _sleep=__import__("time").sleep, _now=_clock):
    """The profile hook of a thread building a floor ahead. Python runs one thread at a time; a
    floor being built took about half of that time, so the screen stuttered. While the screen
    is busy the builder steps aside a millisecond at a time - for 20 ms, then it builds 5 ms -
    and it builds freely while the screen waits for its next frame. Once any run is waiting for
    its floor it stops stepping aside (that floor is next, and the screen can wait)."""
    if not _busy[0] or _waiting:
        _give[0] = 0.0
        return
    t = _now()
    if not _give[0]:
        _give[0] = t
    waited = t - _give[0]
    if waited < 0.020:
        _sleep(0.001)
    elif waited > 0.025:
        _give[0] = t


def _take_build_lock(job, _sleep=__import__("time").sleep):
    """One floor is built at a time. A floor a run is waiting for goes first: a floor built
    ahead takes its turn only when no run is waiting."""
    while True:
        if job.get("needed") or not WAITING:
            if BUILD_LOCK.acquire(timeout=0.05):
                if job.get("needed") or not WAITING:
                    HOLDER[0] = threading.current_thread().name
                    job["locked"] = True
                    return
                BUILD_LOCK.release()
        _sleep(0.02)


PROFILE_BUILDS = 1      # the first floor a run waits for each session is timed in build_profile.log
PROFILED = [0]


def _write_profile(prof, job, secs):
    """Where a floor's build time goes, for the first few floors of a session: build_profile.log
    in the game folder (to find what makes building slow on a real D2 floor)."""
    try:
        import io
        import os
        import pstats
        import time
        out = io.StringIO()
        st = pstats.Stats(prof, stream=out)
        out.write("%s  floor %s (%s, %s): %.1f s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), job["key"][0],
                                                      job["key"][1], job["key"][2], secs))
        st.sort_stats("cumulative").print_stats(30)
        st.sort_stats("tottime").print_stats(25)
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(here, "build_profile.log"), "a") as f:
            f.write(out.getvalue() + "\n")
    except Exception:
        pass


def _need(job):
    """A run is waiting for this job's floor now."""
    job["needed"] = True
    WAITING.add(id(job))
    if not job["thread"].is_alive():     # (finished meanwhile: nothing to wait for)
        WAITING.discard(id(job))


SESSION_SEED = random.randrange(1, 1 << 30)

STATES = ("build", "fight", "pause", "town", "gate", "over")

DIFFICULTIES = ("normal", "nightmare", "hell")
DIFF_NAMES = {"normal": "Normal", "nightmare": "Nightmare", "hell": "Hell"}
CAPPED_DIFFICULTIES = ("normal", "nightmare")   # monsters above the hero brought down to him
UNLOCK_AT = 60          # clearing rift floor 60 opens the next difficulty


def unlocked(h):
    prof = brain.profile(h)
    got = [d for d in DIFFICULTIES if d in (prof.get("unlocked") or ["normal"])]
    return got or ["normal"]


def difficulty_of(h):
    d = brain.profile(h).get("difficulty", "normal")
    return d if d in unlocked(h) else "normal"


def rift_cleared(h, diff):
    """The deepest rift floor he has cleared on this difficulty since he last died there."""
    return int((brain.profile(h).get("rift_by") or {}).get(diff, 0) or 0)


def set_rift_cleared(h, diff, n):
    prof = brain.profile(h)
    prof.setdefault("rift_by", {})[diff] = int(n)
    if diff == "normal":
        prof["cleared"] = int(n)

#: what a run farms (the hero's choice, profile "farm")
#:   rift    the Infernal Rift, floor after floor, an act boss every tenth
#:   boss    the Black Road: a small walled room with one of the Great Evils in it, again and again
#:   runes   the Forgotten Tower's cellar, levels 1 to 5, the Countess at the bottom, then again
FARMS = ("rift", "boss", "runes")
FARM_NAMES = {"rift": "Infernal Rift", "boss": "Black Road", "runes": "Rune run (Countess)"}
TOWER = (21, 22, 23, 24, 25)        # Tower Cellar Level 1-5 (game/act1.py); the Countess is on 5
CELLAR_CLEAR = 0.35                 # a cellar level above hers is done when this share of it is left


def farm_of(h):
    f = brain.profile(h).get("farm", "rift")
    return f if f in FARMS else "rift"


class Run:
    _ids = 0

    def __init__(self, heroes, assets, cfg, timings=None):
        Run._ids += 1
        self.id = Run._ids
        self.heroes = list(heroes)
        self.assets = assets
        self.cfg = cfg
        self.timings = timings
        self.state = "build"
        self.town_used = False      # the floor's one trip to town is spent (no save scumming)
        self.farm = farm_of(self.heroes[0])
        self.difficulty = difficulty_of(self.heroes[0])
        self.depth = max(1, max(cleared(h, self.difficulty) for h in self.heroes) + 1) if self.farm == "rift" else 1
        self.deaths = 0
        self.world = None
        self.sim = None
        self.pause = 0
        self.floors = 0
        self.kills = 0
        self.stop_requested = False
        self.result = None
        self.log = []

    @property
    def leader(self):
        return self.heroes[0]

    def title(self):
        names = ", ".join(h.name for h in self.heroes)
        return "%s - %s" % (names, self.where())

    def where(self):
        """Where the run is, for the screens: rift floor, Black Road number, tower level."""
        if self.farm == "boss":
            return "Black Road %d" % self.depth
        if self.farm == "runes":
            return "Tower Cellar %d (run %d)" % ((self.depth - 1) % 5 + 1, (self.depth - 1) // 5 + 1)
        tag = "" if self.difficulty == "normal" else " (%s)" % DIFF_NAMES[self.difficulty]
        return "floor %d%s" % (self.depth, tag)

    def level_key(self, depth=None):
        from game import arena, rift
        depth = self.depth if depth is None else depth
        if self.farm == "boss":
            return arena.BOSS_LEVEL
        if self.farm == "runes":
            return TOWER[(depth - 1) % 5]
        return rift.level_id(depth)

    def note(self, text):
        self.log.append(text)
        del self.log[:-40]

    # ------------------------------------------------------------ floors
    def build(self):
        """Start building the floor in the background; finish setting it up once it's built."""
        if getattr(self, "_job", None) is None or self._job["key"] != self._job_key():
            pre = getattr(self, "_pre", None)
            self._pre = None
            if pre is not None and pre["key"] == self._job_key():
                self._job = pre                 # (built - or being built - while the last floor was played)
            else:
                self._job = self._start_job(self.depth)
            _need(self._job)
            self._wait_since = _clock()
            self._thread = self._job["thread"]
            for h in self.heroes:
                q = getattr(h, "qol", None)
                if not isinstance(q, dict):
                    q = h.qol = {}
                q["big_inv"] = True
                q["inv_rows"] = gear.ROWS       # twice D2's backpack: 10 x 8
                brain.spend_points(h)
                h._ab_level = h.level
                self._refill_belt(h)
                h.hp, h.alive = h.max_hp, True
                h.mana = getattr(h, "max_mana", getattr(h, "mana", 0))
            return
        job = self._job
        if job["thread"].is_alive():
            return                              # still building: the other runs play on
        if job.get("aborted"):
            # (it was being built ahead and was dropped for another run's floor: build it now)
            self._job = self._start_job(self.depth)
            self._thread = self._job["thread"]
            return
        self._job = self._thread = None
        if job["error"] is not None or job["built"] is None:
            self.note("This floor could not be built (see errors.log).")
            self.finish("error")
            return
        w = job["built"]
        if job["stand_in"] is not None:
            self._adopt(w, job["stand_in"])
        self._place_group(w)
        cap_levels(w, self.level_cap())
        scale_for_players(w, len(self.heroes))
        w.mode = "explore"
        self.world = w
        self.sim = realtime.Sim(w, self.heroes, self.timings, self.cfg.get("move_scale", 1.0))
        for h in self.heroes:
            n = self.sim.prefill_summons(h)
            if n:
                self.note("%s starts the floor with %d raised." % (h.name, n))
        self.state = "fight"
        self.note("%s: %s" % (self.where()[:1].upper() + self.where()[1:], getattr(w, "level_name", "") or "rift"))
        if PREBUILD and not self.stop_requested:
            # the next floor is built now, in the background, while this one is played: through
            # the portal it is (nearly always) ready at once
            self._pre = self._start_job(self.depth + 1, stand_in=True)

    def level_cap(self):
        """No monster is above this level: the group's highest hero level. Normal and Nightmare
        only; in Hell the monsters keep their own level (None: no cap)."""
        if self.difficulty not in CAPPED_DIFFICULTIES:
            return None
        return max(1, max(getattr(h, "level", 1) for h in self.heroes))

    def _job_key(self, depth=None):
        return (self.depth if depth is None else depth, self.farm, self.difficulty)

    def _start_job(self, depth, stand_in=False):
        """Build floor `depth` on a thread. A floor built ahead (stand_in) is built round a copy
        of the leader: the engine puts its player at the floor's start, and the real one is
        still fighting on this floor."""
        import copy
        job = {"key": self._job_key(depth), "built": None, "error": None, "needed": not stand_in,
               "stand_in": copy.copy(self.leader) if stand_in else None}
        job["thread"] = threading.Thread(target=self._build_world, args=(job,),
                                         name="floor-%d-%d" % (self.id, depth), daemon=True)
        if job["needed"]:
            WAITING.add(id(job))
        job["thread"].start()
        return job

    def _adopt(self, w, stand_in):
        """A floor built ahead round a copy of the leader: the real leader takes the copy's place."""
        p = self.leader
        p.x, p.y = stand_in.x, stand_in.y
        for k in ("arena_visit", "rift_seed"):
            if hasattr(stand_in, k):
                setattr(p, k, getattr(stand_in, k))
        for k, v in list(vars(stand_in).items()):
            if getattr(v, "__self__", None) is w:
                setattr(p, k, v)                 # (hooks into the new floor: its auras ...)
        for k, v in list(vars(w).items()):
            if v is stand_in:
                setattr(w, k, p)
            elif isinstance(v, list) and any(x is stand_in for x in v):
                setattr(w, k, [p if x is stand_in else x for x in v])

    def _build_world(self, job):
        import sys
        import time as _time
        t0 = _time.perf_counter()
        prof = None
        if not job.get("needed"):
            sys.setprofile(_hook_for(job))      # (built ahead: the screen goes first, see _give_way)
        elif PROFILED[0] < PROFILE_BUILDS:
            PROFILED[0] += 1
            import cProfile
            try:
                prof = cProfile.Profile()
                prof.enable()
            except Exception:
                prof = None                     # (another profiler already running: no timing)
        try:
            self._build_world_inner(job)
        except _Aborted:
            job["aborted"] = True
            job["built"] = None
        finally:
            if prof is not None:
                prof.disable()
                _write_profile(prof, job, _time.perf_counter() - t0)
            sys.setprofile(None)
            WAITING.discard(id(job))
            # (for perf.log: how long floors take to build, on their own thread)
            self.build_secs = getattr(self, "build_secs", 0.0) + _time.perf_counter() - t0
            self.builds = getattr(self, "builds", 0) + 1

    def _build_world_inner(self, job):
        depth = job["key"][0]
        player = job["stand_in"] or self.leader
        try:
            _take_build_lock(job)
            try:
                a = self.assets
                if getattr(a, "act_kit", None) is not None:
                    from game import rift
                    from game.actworld import make_world
                    content = getattr(self.assets, "content", None)
                    if content is not None:
                        content.set_difficulty(self.difficulty)
                    lid = self.level_key(depth)
                    if self.farm == "rift":
                        # every floor is rolled anew: its place (dungeon or outdoors of the act),
                        # its monsters and its map - the same depth is a different floor each time
                        seed = random.randrange(1, 1 << 30)
                        rift._SEED = seed
                        for h in self.heroes:
                            h.rift_seed = seed
                        rift.PLANS.pop(lid, None)
                    boss_floor = self.farm == "rift" and depth % rift.BOSS_EVERY == 0
                    if boss_floor:
                        # every tenth floor: an arena of the act's own outdoors (2x2 blocks inside
                        # its border), with the act's boss in it and nothing else (premade ones
                        # from map_cache/; without premade maps the Black Road's arena)
                        from . import mapcache
                        if rift.act_of_depth(depth) == 2:
                            # Act 2's boss: D2's own Duriel's Lair (one preset, built at once)
                            w = make_world(a.act_kit, a.act_info, a.content, DURIEL_LAIR,
                                           player=player, seed=random.randrange(1 << 30))
                        elif mapcache._ORIGINAL is not None:
                            w = make_world(a.act_kit, a.act_info, a.content, lid, player=player,
                                           seed=random.randrange(1 << 30))
                        else:
                            from game import arena
                            w = make_world(a.act_kit, a.act_info, a.content, arena.BOSS_LEVEL,
                                           player=player, seed=random.randrange(1 << 30))
                        self._act_boss_arena(w, lid, depth)
                    else:
                        w = make_world(a.act_kit, a.act_info, a.content, lid, player=player,
                                       seed=random.randrange(1 << 30))
                    for h in self.heroes:
                        # (the engine ends a rift run when its hero "leaves the rift"; here only
                        # the run decides that, so it never sees him as having been in one)
                        h._in_rift = False
                    self._mark_farm_boss(w, lid)
                else:
                    from game.world import World
                    w = World(seed=random.randrange(1 << 30), depth_level=depth, player=player)
                    self._mark_boss(w)
                try:
                    realtime.label_areas(w)    # (which parts of the floor join: on this thread)
                except Exception:
                    pass
                job["built"] = w
            finally:
                HOLDER[0] = None
                job["locked"] = False
                BUILD_LOCK.release()
        except Exception as e:
            import traceback
            job["error"] = e
            traceback.print_exc()
            try:
                from main import log_error
                log_error(traceback.format_exc())
            except Exception:
                pass

    def _act_boss_arena(self, w, lid, depth):
        """The act boss of this stretch of ten floors, alone in the arena, at the rift's level
        for this floor."""
        from game import actworld, arena, rift
        w._arena_done = True                     # (not the Black Road's own random Great Evil)
        w.monsters[:] = [m for m in w.monsters if getattr(m, "ally", False) or getattr(m, "is_player", False)
                         or getattr(m, "ai", "") == "npc"]
        mid = rift.ACT_BOSSES[rift.act_of_depth(depth) - 1]
        tag = "baal" if mid == "baalcrab" else mid
        lvl = rift.act_level(depth) if rift.ACT_LEVELS else max(1, getattr(w.player, "level", 1))
        if getattr(w, "level_key", None) == DURIEL_LAIR:
            # (the lair's way back to the Tomb: the run opens its own portal when he dies)
            w.objects[:] = [o for o in w.objects if o.get("kind") not in actworld.PORTAL_KINDS]
        far = arena._far_cell(w, w.player.pos)
        taken = set(w.occupied())
        boss = actworld._spawn(w, mid, far, lvl, taken, unique=True)
        if boss is None:
            # (that cell was taken or no floor: any free floor cell, the furthest first)
            g = w.grid
            cells = [(x, y) for y in range(g.h) for x in range(g.w) if g.walkable(x, y) and (x, y) not in taken]
            cells.sort(key=lambda c: -max(abs(c[0] - w.player.x), abs(c[1] - w.player.y)))
            for c in cells[:200]:
                boss = actworld._spawn(w, mid, c, lvl, taken, unique=True)
                if boss is not None:
                    break
        if boss is None:
            w.log("The act boss could not be set down in the arena.")
            try:
                from main import log_error
                log_error("act boss arena: %s could not be spawned (floor %d)" % (mid, depth))
            except Exception:
                pass
            return
        boss.boss = tag
        boss.rift_boss = True
        if not rift.BIG:
            rift.scale_to_level(w, boss, lvl)
            boss.max_hp = int(boss.max_hp * 1.5)
        boss.hp = boss.max_hp
        boss.aware = True
        w.log("%s waits in the arena, alone." % boss.name)

    def _mark_farm_boss(self, w, lid):
        """The Black Road's Great Evil and the Countess end their floor; a cellar level above hers
        is done when most of it is dead (CELLAR_CLEAR left)."""
        if self.farm == "boss":
            from game import arena
            try:
                arena.populate(w)
            except Exception:
                import traceback
                traceback.print_exc()
            for m in w.monsters:
                if getattr(m, "boss", None) and not getattr(m, "ally", False):
                    m.rift_boss = True
        elif self.farm == "runes":
            if lid == TOWER[-1]:
                for m in w.monsters:
                    if (getattr(m, "boss", "") or "") == "countess" or "countess" in (getattr(m, "name", "") or "").lower():
                        m.rift_boss = True
            else:
                w._clear_share = CELLAR_CLEAR

    def _mark_boss(self, w):
        foes = [m for m in w.monsters if not getattr(m, "ally", False)]
        if foes:
            boss = max(foes, key=lambda m: abs(m.x - w.player.x) + abs(m.y - w.player.y))
            boss.rift_boss = True
            boss.max_hp = boss.hp = int(boss.max_hp * 2.5)

    def _place_group(self, w):
        """Heroes after the first stand beside him; to the engine they are party members."""
        if len(self.heroes) < 2:
            return
        w.party = list(self.heroes)
        taken = {m.pos for m in w.monsters} | {w.player.pos}
        for h in self.heroes[1:]:
            cell = None
            try:
                cell = w._free_cell_near(w.player.pos, 6)
            except Exception:
                cell = None
            if cell is None or cell in taken:
                ring = w.grid.reachable(w.player.pos, 6) if hasattr(w.grid, "reachable") else {}
                cell = next((c for c in ring if c not in taken), w.player.pos)
            h.x, h.y = cell
            taken.add(cell)
            h.alive = True
            from game import tactics
            tactics._as_follower(w, h)      # the fields the engine expects of a party hero

    # ------------------------------------------------------------ town and back
    AUTO_TOWN_SECONDS = 3       # how long an automatic trip home takes before he goes back

    def go_town(self, auto=False, sell=True, why="backpack full"):
        """To town (a town portal): the floor waits as it is, the heroes are in Sanctuary, where
        Tyrael mends them and the traders have new stock, and they put their gems, runes, unique
        and set items in the account's stash. With auto (a full backpack) they go back to the
        floor on their own a moment later. -> True if they went."""
        if self.state != "fight" or self.sim is None or self.town_used:
            return False
        self.town_used = True                   # (one trip per floor, until it is cleared or he dies)
        self.state = "town"
        from . import stash
        st = stash.get(getattr(self.assets, "content", None))
        stored = 0
        for h in self.heroes:
            if h.alive:
                h.hp, h.mana = h.max_hp, getattr(h, "max_mana", getattr(h, "mana", 0))
            h._town_visit = int(getattr(h, "_town_visit", 0) or 0) + 1
            n = stash.deposit(h, st, getattr(self.assets, "content", None))
            stored += n
            if n:
                self.note("%s puts %d item%s in the stash." % (h.name, n, "" if n == 1 else "s"))
            if auto and sell:
                cores0, plat0 = gear.rare_cores(h), gear.platinum(h)
                sold, gold = sell_magic_and_rare(h)
                if sold:
                    cores, plat = gear.rare_cores(h) - cores0, gear.platinum(h) - plat0
                    self.note("%s sells %d item%s for %d gold%s." % (h.name, sold, "" if sold == 1 else "s", gold,
                                                                     gear.gains_text(cores, plat)))
            roster.save(h)
        if stored:
            stash.save()
        self._auto_back = int(self.AUTO_TOWN_SECONDS * timing.FPS) if auto else 0
        self.note(("To town from floor %d (" + why + ").") % self.depth if auto else
                  "To town from floor %d; the floor waits." % self.depth)
        return True

    def _should_empty_bag(self):
        """A hero had no room for something he wanted: home, if that would make room (he carries
        gems, runes, unique or set items the stash takes, or magic or rare items to sell)."""
        from . import stash
        content = getattr(self.assets, "content", None)
        if not any(stash.keeps(it, content) or sellable_on_trip(it)
                   for h in self.heroes for it in h.inventory):
            self.sim.no_room = False
            return False
        return True

    def to_gate(self):
        """The floor before an act boss: back to town (mended, the stash and the traders as on any
        trip home), and the boss waits until the player sends them in (Fight boss)."""
        from . import stash
        st = stash.get(getattr(self.assets, "content", None))
        for h in self.heroes:
            if h.alive:
                h.hp, h.mana = h.max_hp, getattr(h, "max_mana", getattr(h, "mana", 0))
            h._town_visit = int(getattr(h, "_town_visit", 0) or 0) + 1
            stash.deposit(h, st, getattr(self.assets, "content", None))
            roster.save(h)
        stash.save()
        self.depth += 1
        self.state = "gate"
        self.note("Floor %d: the act boss waits. Back in town - Fight boss when ready." % self.depth)

    def fight_boss(self):
        """The player sends them in: the boss floor is built and the run goes on."""
        if self.state != "gate":
            return False
        for h in self.heroes:
            h.recalc()
            gear.prepare(h)
        self.state = "build"
        self.note("Into floor %d to face the act boss." % self.depth)
        return True

    def resume(self):
        """Back through the portal: the run goes on where it was left."""
        if self.state != "town":
            return False
        self._auto_back = 0
        if self.sim is not None:
            self.sim.skip_items.clear()          # (with room again, what he left is worth a look)
        for h in self.heroes:
            h.recalc()                          # (gear changed in town)
            self._refill_belt(h)                # (the traders: potions for the belt)
            h.hp = min(h.hp, h.max_hp)
            h.mana = min(h.mana, getattr(h, "max_mana", h.mana))
            gear.prepare(h)
        self.state = "fight"
        self.note("Back on floor %d." % self.depth)
        return True

    # ------------------------------------------------------------ frames
    def tick(self):
        if self.state == "build":
            self.build()
            return
        if self.state == "pause":
            # through the portal (or back to floor 1): the next floor is built during the pause,
            # so the pause and the building overlap instead of adding up
            if self.stop_requested:
                self.finish("stopped")
                return
            if not getattr(self, "_next_set", False):
                if not getattr(self, "_restart", False):
                    self.depth += 1
                self._restart = False
                self._next_set = True
            if getattr(self, "_job", None) is None or self._job["key"] != self._job_key():
                self.build()                    # (starts the build thread, nothing more)
            self.pause -= 1
            if self.pause <= 0:
                self._next_set = False
                self.state = "build"
            return
        if self.state == "town" and getattr(self, "_auto_back", 0):
            self._auto_back -= 1               # (an automatic trip home: back by himself)
            if self._auto_back <= 0:
                self.resume()
            return
        if self.state != "fight":
            return                              # (town: the floor waits)
        xp0 = self.leader.xp
        self.sim.town_spent = self.town_used     # (no retreat home once the floor's trip is spent)
        if self.sim.frame % 25 == 0:
            cap_levels(self.world, self.level_cap())    # (monsters raised or called up meanwhile)
        self.sim.tick()
        while self.sim.notes:
            self.note(self.sim.notes.pop(0))
        self._share_xp(self.leader.xp - xp0)
        for h in self.heroes:
            if h.alive and h.level != getattr(h, "_ab_level", h.level):
                h._ab_level = h.level
                brain.spend_points(h)       # a level up: new points go where his plan says
                self.note("%s reached level %d." % (h.name, h.level))
        if self.sim.wiped():
            # death: the run starts again from the first floor (the heroes get up at the start)
            self.kills += self.sim.kills
            self.deaths += 1
            self.note("Everyone fell on floor %d. Back to floor 1." % self.depth)
            for h in self.heroes:
                prof = brain.profile(h)        # (saved with him; his best floor ever)
                if self.farm == "rift":
                    prof["best"] = max(int(prof.get("best", 0) or 0), int(getattr(h, "rift_depth", 0) or 0))
                    h.rift_depth = 0
                    set_rift_cleared(h, self.difficulty, 0)
                    prof["cleared"] = 0
                h.alive = True
                roster.save(h)
            self.town_used = False
            if self.stop_requested:
                self.finish("died")
            else:
                self.depth = 1
                self.state = "pause"
                self.pause = int(self.cfg.get("floor_pause", 1) * timing.FPS)
                self._restart = True
        elif self.sim.need_town and not self.town_used:
            self.sim.need_town = False
            self.go_town(auto=True, sell=False, why="out of healing potions")
        elif self.sim.no_room and not self.town_used and self._should_empty_bag():
            self.sim.no_room = False
            self.go_town(auto=True)
        elif self.sim.cleared() and self.sim.phase == "fight":
            self.sim.open_portal(self.sim.boss_cell())
            self.note("%s: done, a portal opens." % self.where())
        elif self.sim.at_portal:
            self.kills += self.sim.kills
            self.floors += 1
            self.town_used = False
            for h in self.heroes:
                if self.farm == "rift":
                    h.rift_depth = max(int(getattr(h, "rift_depth", 0) or 0), self.depth)
                    prof = brain.profile(h)
                    set_rift_cleared(h, self.difficulty, max(rift_cleared(h, self.difficulty), self.depth))
                    prof["best"] = max(int(prof.get("best", 0) or 0), h.rift_depth)
                    if self.depth >= UNLOCK_AT:
                        i = DIFFICULTIES.index(self.difficulty)
                        if i + 1 < len(DIFFICULTIES) and DIFFICULTIES[i + 1] not in unlocked(h):
                            prof["unlocked"] = unlocked(h) + [DIFFICULTIES[i + 1]]
                            self.note("%s: %s is open." % (h.name, DIFF_NAMES[DIFFICULTIES[i + 1]]))
                roster.save(h)
            for who, what in self.sim.picked:
                self.note("%s picked up %s." % (who, what))
            self.note("%s cleared: through the portal." % self.where())
            if self.farm == "rift" and (self.depth + 1) % 10 == 0 and not self.stop_requested:
                self.to_gate()
            else:
                self.state = "pause"
                self.pause = int(self.cfg.get("floor_pause", 1) * timing.FPS)
        elif self.stop_requested:
            self.finish("stopped")

    # potions bought between floors: what is missing from the belt, as far as his gold goes
    def _refill_belt(self, h):
        from game import potions
        a = self.assets
        content = getattr(a, "content", None)
        try:
            cap = potions.belt_slots(h) * potions.belt_rows(h)
        except Exception:
            cap = 8
        caster = getattr(h, "cls", "") in ("sor", "nec", "dru", "ass")
        act = ((max(1, self.depth) - 1) // 10) % 5 + 1
        diff = getattr(content, "difficulty", "normal") if content else "normal"
        try:
            tier = max(int(t) for t in potions.vendor_tiers(act, diff))
        except Exception:
            tier = 1
        bought = 0
        guard = 0
        rule = potions.COLUMN_RULE or potions.ROW_RULE
        while len(getattr(h, "belt", []) or []) < cap and guard < 40:
            guard += 1
            if rule:
                # the rows he has for each kind (his belt rows, Inventory screen)
                free_hp = potions._free_column(h, _probe("heal")) is not None
                free_mp = potions._free_column(h, _probe("mana")) is not None
                if not free_hp and not free_mp:
                    break
                want_mana = free_mp and (not free_hp or
                                         sum(1 for x in h.belt if getattr(x, "potion", "") == "mana") <
                                         sum(1 for x in h.belt if getattr(x, "potion", "") in ("heal", "rejuv")))
            else:
                heals = sum(1 for it in h.belt if getattr(it, "potion", "") in ("heal", "rejuv"))
                manas = sum(1 for it in h.belt if getattr(it, "potion", "") == "mana")
                want_mana = manas < (cap // 2 if caster else cap // 4) and heals >= manas
            it = None
            if content is not None:
                # the best tier the traders sell that he can pay for (a poor hero buys Minor ones)
                base = price = None
                for t in range(tier, 0, -1):
                    code = ("mp%d" if want_mana else "hp%d") % t
                    b = getattr(content, "base_by_code", {}).get(code)
                    if b is None:
                        continue
                    cost = int(b.get("cost", 0) or 0) or 25 * t
                    if h.gold >= cost:
                        base, price = b, cost
                        break
                if base is None:
                    break
                it = content.make_item(base, max(1, h.level), random.Random())
                h.gold -= price
            elif content is None:
                from game.items import make_potion
                it = make_potion(h.level)          # (placeholder game: no shop, a plain potion)
            if it is None or not potions.belt_add(h, it, None):
                break
            bought += 1
        if bought:
            self.note("%s fills his belt (%d potions)." % (h.name, bought))
        elif not getattr(h, "belt", None):
            self.note("%s has no gold for potions." % h.name)

    def _share_xp(self, gained):
        """Kills give experience to world.player; the rest of the group gets the same amount."""
        if gained <= 0 or len(self.heroes) < 2:
            return
        for h in self.heroes[1:]:
            if h.alive:
                try:
                    h.gain_xp(gained)
                except Exception:
                    h.xp += gained

    def ground_items(self):
        return self.sim.ground_items() if self.sim is not None else []

    def take(self, hero, cell, it):
        """Manual loot from the loot window: this hero takes it (outside a fight, from anywhere on
        the floor, by the engine's rule)."""
        if self.sim is None or hero not in self.heroes or not hero.alive:
            return False
        return self.sim.take(hero, cell, it)

    def finish(self, why):
        self.state = "over"
        self.result = why
        for h in self.heroes:
            h.hp, h.alive = h.max_hp, True
            for attr in ("ally", "party_member"):
                if hasattr(h, attr):
                    setattr(h, attr, False)
            roster.save(h)
        self.world = None
        self.sim = None


def cleared(h, diff="normal"):
    """The deepest floor he has cleared on a difficulty since he last died there: the next run
    starts one deeper. (Normal also reads the older single count.)"""
    n = rift_cleared(h, diff)
    if diff == "normal":
        n = max(n, int(getattr(h, "rift_depth", 0) or 0), int(brain.profile(h).get("cleared", 0) or 0))
    return n


def cap_levels(w, cap):
    """A monster above the hero's level is brought down to it (its life, damage, attack rating,
    defence and experience by D2's MonLvl tables, the same way the rift scales its bosses); one at
    or below it stays as it is. Its drops follow its new level."""
    from game import rift
    if cap is None or getattr(w, "content", None) is None:
        return
    for m in w.monsters:
        if getattr(m, "ally", False) or getattr(m, "is_player", False) or getattr(m, "ai", "") == "npc" \
                or not getattr(m, "alive", True):
            continue
        if getattr(m, "level", 1) > cap:
            frac = m.hp / float(max(1, m.max_hp))
            rift.scale_to_level(w, m, cap)
            m.hp = max(1, int(m.max_hp * frac))


def scale_for_players(w, players):
    """D2's /players setting: each player past the first gives monsters +50% life and +50%
    experience ((players + 1) / 2). One hero plays /players 1: D2's own numbers, untouched."""
    if players <= 1:
        return
    k = (players + 1) / 2.0
    for m in w.monsters:
        if getattr(m, "ally", False) or getattr(m, "is_player", False) or getattr(m, "ai", "") == "npc" \
                or getattr(m, "_players_scaled", False):
            continue
        m._players_scaled = True
        m.max_hp = max(1, int(m.max_hp * k))
        m.hp = m.max_hp
        m.xp_value = max(1, int(getattr(m, "xp_value", 1) * k))


def sellable_on_trip(it):
    """What the automatic trip home sells: magic (blue) and rare (yellow) items, and plain weapons
    and armor (what the stash takes - runeword bases among them - has gone in before this)."""
    if getattr(it, "kind", "") == "quest" or getattr(it, "charm", False):    # (charms are never sold)
        return False
    if getattr(it, "rarity", "") in ("magic", "rare"):
        return True
    return getattr(it, "kind", "") == "equip" and getattr(it, "rarity", "") in ("normal", "superior", "low") \
        and not getattr(it, "runeword", None)


def sell_magic_and_rare(h):
    """The automatic trip home: everything sellable_on_trip in his backpack is sold at D2's sell
    price; what he wears is kept. -> (items sold, gold)."""
    from game.d2items import sell_price
    sold = gold = 0
    for it in list(h.inventory):
        if not sellable_on_trip(it):
            continue
        try:
            value = sell_price(it)
        except Exception:
            continue
        h.inventory.remove(it)
        it.inv_pos = None
        h.gold += value
        gear.on_sold(h, it)                     # (a rare one: a Rare Core; a socketed one: a Platinum)
        sold += 1
        gold += value
    return sold, gold


def _probe(kind):
    """A stand-in potion of a kind, to ask the belt whether it has room for one."""
    from game.items import Item
    it = Item("probe", "hp1" if kind == "heal" else "mp1", None, kind="potion")
    it.potion = kind
    return it


DURIEL_LAIR = 73       # D2's Duriel's Lair: Act 2's boss floors (20, 70, ...) are fought in it


class RunManager:
    def __init__(self, assets, cfg, timings=None):
        self.assets = assets
        self.cfg = cfg
        self.timings = timings
        self.runs = []
        if getattr(assets, "act_kit", None) is not None:
            from game import rift
            rift.BIG = bool(cfg.get("big_maps", True))
            rift.CONTENT = assets.content
            rift.ACT_LEVELS = True           # monsters by the act's own levels, not the hero's
            rift.AREA = float(cfg.get("map_area", 0.5))     # floors half the size they were
            if cfg.get("premade_maps", True):
                from . import mapcache
                mapcache.install()           # floors from a pool of 204 kept layouts
            rift.SIXTH = True                # floors 51-60 in Act 5's places, Baal on 60
            # Diablo II's own drops: every monster's own treasure classes, ItemRatio.txt quality
            # with D2's magic find, no D2 Tactics boosts (act bosses' x1.8, the two-piece floor,
            # the Countess's chest hoard every kill)
            assets.content.D2_DROPS = True
            rift.forget(None)
            rift._SEED = SESSION_SEED

    def active(self):
        return [r for r in self.runs if r.state != "over"]

    def busy_names(self):
        """Heroes with a run going (on a floor, or in town between its floors)."""
        return {h.name for r in self.active() for h in r.heroes}

    def on_floor_names(self):
        """Heroes on a rift floor now (not in town)."""
        return {h.name for r in self.active() if r.state not in ("town", "gate") for h in r.heroes}

    def free_slots(self):
        return self.cfg["max_active"] - sum(len(r.heroes) for r in self.active())

    def start(self, heroes):
        """Start a run for these heroes (a group when more than one). -> Run, or a reason why not."""
        heroes = list(heroes)
        if not heroes:
            return "Pick a hero first."
        if len(heroes) > self.cfg["max_group"]:
            return "At most %d heroes on one run." % self.cfg["max_group"]
        if any(h.name in self.busy_names() for h in heroes):
            return "One of them is already on a run."
        if len(heroes) > self.free_slots():
            return "Only %d heroes can be on runs at the same time." % self.cfg["max_active"]
        r = Run(heroes, self.assets, self.cfg, self.timings)
        self.runs.append(r)
        return r

    def tick(self):
        if not WAITING:
            for r in self.runs:
                pre = getattr(r, "_pre", None)
                if pre is not None and pre.get("aborted") and r.state == "fight" and \
                        pre["key"] == r._job_key(r.depth + 1):
                    r._pre = r._start_job(r.depth + 1, stand_in=True)   # (dropped earlier: again)
        realtime.new_frame()
        runs = self.active()
        if runs:
            # the frame's path searches are shared: a different run goes first each frame
            self._turn = (getattr(self, "_turn", 0) + 1) % len(runs)
            runs = runs[self._turn:] + runs[:self._turn]
        self._tick_runs(runs)

    #: game time per screen frame (s) for the runs nobody is watching; the watched run always
    #: gets all its frames
    BUDGET = 0.010
    MAX_BEHIND = 3          # game frames a run may owe before the rest are dropped (it slows down)

    def step(self, dt, speed=1.0, fps=25):
        """Play dt seconds of every run, the screen first: the run being watched gets all its game
        frames; the others share what is left of BUDGET, the one most behind first. On a PC too
        slow for all of them, the runs nobody is watching slow down instead of the screen
        stuttering. Returns the number of run-frames played."""
        runs = self.active()
        cap = self.MAX_BEHIND * max(1.0, speed)
        for r in runs:
            r.acc = min(getattr(r, "acc", 0.0) + dt * fps * speed, cap)
        start = _clock()
        n = 0
        ticked = set()

        def first(r):
            # the watched run, and one that has had nothing for 3 screen frames, can't be put off
            return (r.sim is not None and getattr(r.sim, "watched", False)) or \
                (getattr(r, "_starved", 0) >= 3 and id(r) not in ticked)
        while True:
            due = [r for r in runs if r.acc >= 1.0 and r in self.runs]
            if not due:
                break
            due.sort(key=lambda r: (not first(r), -r.acc))
            if n and _clock() - start > self.BUDGET:
                due = [r for r in due if first(r)]
                if not due:
                    break
            realtime.new_frame()
            for r in due:
                if r is not due[0] and not first(r) and _clock() - start > self.BUDGET:
                    break
                self._tick_runs([r])
                ticked.add(id(r))
                r.acc -= 1.0
                n += 1
        for r in runs:
            r._starved = 0 if (id(r) in ticked or r.acc < 1.0) else getattr(r, "_starved", 0) + 1
        if not WAITING:
            for r in self.runs:
                pre = getattr(r, "_pre", None)
                if pre is not None and pre.get("aborted") and r.state == "fight" and \
                        pre["key"] == r._job_key(r.depth + 1):
                    r._pre = r._start_job(r.depth + 1, stand_in=True)
            self._fill_maps()
        return n

    def _fill_maps(self):
        """The pool of premade floors is filled by a process of its own (autobattler/mapworker.py):
        on a thread next to the game it took time from the screen. Every 10 s the game looks for
        the floors it has saved meanwhile."""
        from . import mapcache, mapworker
        if getattr(self.assets, "act_kit", None) is None or mapcache._ORIGINAL is None:
            return
        if _clock() < getattr(self, "_fill_after", 0.0):
            return
        self._fill_after = _clock() + 10.0
        try:
            if mapworker.running():
                with mapcache._LOCK:
                    mapcache._INDEX = None
                HOLDER_NOTE[0] = "premade floors: %d/%d" % (mapcache.total(), mapcache.MAP_POOL +
                                                            mapcache.ARENA_POOL * len(mapcache.arenas()))
            elif not getattr(self, "_worker_started", False):
                self._worker_started = True
                mapworker.start(self.assets)
            else:
                HOLDER_NOTE[0] = None
        except Exception:
            mapcache._log("starting the premade floors' process")

    def _tick_runs(self, runs):
        content = getattr(self.assets, "content", None)
        for r in runs:
            if content is not None and r.state == "fight" and BUILD_LOCK.acquire(False):
                # (drops and levels read this run's difficulty; never changed under a floor being
                # built, which sets its own)
                try:
                    content.set_difficulty(getattr(r, "difficulty", "normal"))
                finally:
                    BUILD_LOCK.release()
            t0 = _clock()
            try:
                r.tick()
            except Exception:
                import traceback
                traceback.print_exc()
                r.note("This run stopped because of an error (see the console / errors.log).")
                r.finish("error")
            r.game_secs = getattr(r, "game_secs", 0.0) + _clock() - t0
            r.game_frames = getattr(r, "game_frames", 0) + 1
        # finished runs are kept for their log, but only the last 30
        over = [r for r in self.runs if r.state == "over"]
        for r in over[:-30]:
            self.runs.remove(r)
