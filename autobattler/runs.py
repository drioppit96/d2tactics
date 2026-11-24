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

from . import brain, gear, realtime, roster, timing

BUILD_LOCK = threading.Lock()       # one floor built at a time
SESSION_SEED = random.randrange(1, 1 << 30)

STATES = ("build", "fight", "pause", "town", "over")


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
        self.depth = max(1, max(int(getattr(h, "rift_depth", 0) or 0) for h in self.heroes) + 1)
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
        return "%s - floor %d" % (names, self.depth)

    def note(self, text):
        self.log.append(text)
        del self.log[:-40]

    # ------------------------------------------------------------ floors
    def build(self):
        """Start building the floor in the background; finish setting it up once it's built."""
        if getattr(self, "_thread", None) is None:
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
            self._built, self._error = None, None
            self._thread = threading.Thread(target=self._build_world, name="floor-%d" % self.id, daemon=True)
            self._thread.start()
            return
        if self._thread.is_alive():
            return                              # still building: the other runs play on
        self._thread = None
        if self._error is not None or self._built is None:
            self.note("This floor could not be built (see errors.log).")
            self.finish("error")
            return
        w = self._built
        self._built = None
        self._place_group(w)
        scale_for_players(w, len(self.heroes))
        w.mode = "explore"
        self.world = w
        self.sim = realtime.Sim(w, self.heroes, self.timings, self.cfg.get("move_scale", 1.0))
        self.state = "fight"
        self.note("Floor %d: %s" % (self.depth, getattr(w, "level_name", "") or "rift"))

    def _build_world(self):
        try:
            with BUILD_LOCK:
                a = self.assets
                if getattr(a, "act_kit", None) is not None:
                    from game import rift
                    from game.actworld import make_world
                    lid = rift.level_id(self.depth)
                    # every floor is rolled anew: its place (dungeon or outdoors of the act), its
                    # monsters and its map - the same depth is a different floor each time
                    seed = random.randrange(1, 1 << 30)
                    rift._SEED = seed
                    for h in self.heroes:
                        h.rift_seed = seed
                    rift.PLANS.pop(lid, None)
                    w = make_world(a.act_kit, a.act_info, a.content, lid, player=self.leader,
                                   seed=random.randrange(1 << 30))
                else:
                    from game.world import World
                    w = World(seed=random.randrange(1 << 30), depth_level=self.depth, player=self.leader)
                    self._mark_boss(w)
                self._built = w
        except Exception as e:
            import traceback
            self._error = e
            traceback.print_exc()
            try:
                from main import log_error
                log_error(traceback.format_exc())
            except Exception:
                pass

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

    def go_town(self, auto=False):
        """To town (a town portal): the floor waits as it is, the heroes are in Sanctuary, where
        Tyrael mends them and the traders have new stock, and they put their gems, runes, unique
        and set items in the account's stash. With auto (a full backpack) they go back to the
        floor on their own a moment later. -> True if they went."""
        if self.state != "fight" or self.sim is None:
            return False
        self.state = "town"
        from . import stash
        st = stash.get(getattr(self.assets, "content", None))
        stored = 0
        for h in self.heroes:
            if h.alive:
                h.hp, h.mana = h.max_hp, getattr(h, "max_mana", getattr(h, "mana", 0))
            h._town_visit = int(getattr(h, "_town_visit", 0) or 0) + 1
            n = stash.deposit(h, st)
            stored += n
            if n:
                self.note("%s puts %d item%s in the stash." % (h.name, n, "" if n == 1 else "s"))
            if auto:
                sold, gold = sell_magic_and_rare(h)
                if sold:
                    self.note("%s sells %d magic and rare item%s for %d gold." % (h.name, sold, "" if sold == 1 else "s", gold))
            roster.save(h)
        if stored:
            stash.save()
        self._auto_back = int(self.AUTO_TOWN_SECONDS * timing.FPS) if auto else 0
        self.note(("Backpack full: to town from floor %d." if auto else
                   "To town from floor %d; the floor waits.") % self.depth)
        return True

    def _should_empty_bag(self):
        """A hero had no room for something he wanted: home, if that would make room (he carries
        gems, runes, unique or set items the stash takes, or magic or rare items to sell)."""
        from . import stash
        if not any(stash.keeps(it) or getattr(it, "rarity", "") in ("magic", "rare")
                   for h in self.heroes for it in h.inventory):
            self.sim.no_room = False
            return False
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
            if getattr(self, "_thread", None) is None:
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
        self.sim.tick()
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
                prof["best"] = max(int(prof.get("best", 0) or 0), int(getattr(h, "rift_depth", 0) or 0))
                h.rift_depth = 0
                h.alive = True
                roster.save(h)
            if self.stop_requested:
                self.finish("died")
            else:
                self.depth = 1
                self.state = "pause"
                self.pause = int(self.cfg.get("floor_pause", 1) * timing.FPS)
                self._restart = True
        elif self.sim.no_room and self._should_empty_bag():
            self.sim.no_room = False
            self.go_town(auto=True)
        elif self.sim.cleared() and self.sim.phase == "fight":
            self.sim.open_portal(self.sim.boss_cell())
            self.note("Floor %d: the boss is dead, a portal opens." % self.depth)
        elif self.sim.at_portal:
            self.kills += self.sim.kills
            self.floors += 1
            for h in self.heroes:
                h.rift_depth = max(int(getattr(h, "rift_depth", 0) or 0), self.depth)
                prof = brain.profile(h)
                prof["best"] = max(int(prof.get("best", 0) or 0), h.rift_depth)
                roster.save(h)
            for who, what in self.sim.picked:
                self.note("%s picked up %s." % (who, what))
            self.note("Floor %d cleared: through the portal." % self.depth)
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
        rule = potions.COLUMN_RULE
        while len(getattr(h, "belt", []) or []) < cap and guard < 40:
            guard += 1
            if rule:
                # healing fills columns 1-2, mana 3-4 (config.apply_d2_rules)
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


def sell_magic_and_rare(h):
    """The automatic trip home: every magic (blue) and rare (yellow) item in his backpack is sold
    at D2's sell price; what he wears is kept. -> (items sold, gold)."""
    from game.d2items import sell_price
    sold = gold = 0
    for it in list(h.inventory):
        if getattr(it, "rarity", "") not in ("magic", "rare") or getattr(it, "kind", "") == "quest":
            continue
        try:
            value = sell_price(it)
        except Exception:
            continue
        h.inventory.remove(it)
        it.inv_pos = None
        h.gold += value
        sold += 1
        gold += value
    return sold, gold


def _probe(kind):
    """A stand-in potion of a kind, to ask the belt whether it has room for one."""
    from game.items import Item
    it = Item("probe", "hp1" if kind == "heal" else "mp1", None, kind="potion")
    it.potion = kind
    return it


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
            rift.forget(None)
            rift._SEED = SESSION_SEED

    def active(self):
        return [r for r in self.runs if r.state != "over"]

    def busy_names(self):
        """Heroes with a run going (on a floor, or in town between its floors)."""
        return {h.name for r in self.active() for h in r.heroes}

    def on_floor_names(self):
        """Heroes on a rift floor now (not in town)."""
        return {h.name for r in self.active() if r.state != "town" for h in r.heroes}

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
        realtime.new_frame()
        runs = self.active()
        if runs:
            # the frame's path searches are shared: a different run goes first each frame
            self._turn = (getattr(self, "_turn", 0) + 1) % len(runs)
            runs = runs[self._turn:] + runs[:self._turn]
        for r in runs:
            try:
                r.tick()
            except Exception:
                import traceback
                traceback.print_exc()
                r.note("This run stopped because of an error (see the console / errors.log).")
                r.finish("error")
        # finished runs are kept for their log, but only the last 30
        over = [r for r in self.runs if r.state == "over"]
        for r in over[:-30]:
            self.runs.remove(r)
