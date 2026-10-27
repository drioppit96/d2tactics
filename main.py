"""D2 Tactics - turn-based tactical combat prototype on a Diablo 2 style isometric grid.

Run:  python main.py
"""
import configparser
import os
import sys

import pygame

from game.grid import chebyshev
from game.world import World
from render.assets import PlaceholderAssets
from render.hud import Hud, GOLD, TEXT
from render.iso import Camera
from render.scene import Scene

HERE = os.path.dirname(os.path.abspath(__file__))


def load_settings():
    cfg = configparser.ConfigParser()
    cfg.read_dict({"display": {"width": "1280", "height": "720", "fullscreen": "no", "scale": "auto"},
                   "diablo2": {"path": ""}, "game": {"difficulty": "normal", "min_hit_chance": "60"}})
    cfg.read(os.path.join(HERE, "settings.ini"))
    return cfg


def load_assets(cfg, progress=None):
    path = cfg.get("diablo2", "path").strip()
    if path:
        try:
            from render.d2assets import D2Assets
            return D2Assets(path, cfg.get("game", "difficulty").strip().lower(), progress), None
        except Exception as e:  # files not found or unreadable
            import traceback
            traceback.print_exc()
            return PlaceholderAssets(), f"D2 graphics not loaded ({e}); using placeholder art."
    return PlaceholderAssets(), None


class Game:
    def __init__(self):
        self.cfg = load_settings()
        try:
            import game.world as _gw
            _gw.PLAYER_HIT_FLOOR = max(5, min(95, self.cfg.getint("game", "min_hit_chance"))) / 100.0
        except Exception:
            pass
        pygame.init()
        w = self.cfg.getint("display", "width")
        h = self.cfg.getint("display", "height")
        flags = pygame.RESIZABLE
        if self.cfg.getboolean("display", "fullscreen"):
            flags = pygame.FULLSCREEN
        self.screen = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption("D2 Tactics - prototype")
        self.clock = pygame.time.Clock()
        serif = "georgia,palatinolinotype,timesnewroman,serif"
        self.fonts = {
            "small": pygame.font.SysFont(serif, 15),
            "med": pygame.font.SysFont(serif, 19, bold=True),
            "big": pygame.font.SysFont(serif, 30, bold=True),
            "title": pygame.font.SysFont(serif, 22, bold=True),
        }
        self.loading("Starting...")
        self.assets, self.asset_warning = load_assets(self.cfg, self.loading)
        scale = self.cfg.get("display", "scale").strip().lower()
        zoom = getattr(self.assets, "native_scale", 2.0) if scale in ("", "auto") else float(scale)
        self.cam = Camera(w, h, zoom)
        self._offscreen = None
        self._path_cache = {}
        self.creator = None
        self.state = "play"
        if getattr(self.assets, "act_kit", None) is not None:
            # D2 files: start at D2's character creation screen
            self.hud = self.make_hud()
            from render.charcreate import CharCreate
            try:
                self.creator = CharCreate(self)
                self.state = "create"
            except Exception:
                import traceback
                traceback.print_exc()
                self.creator = None
        if self.state != "create":
            self.new_world()
        self.running = True

    def loading(self, message):
        """Simple loading screen; also keeps Windows from marking the window 'not responding'."""
        pygame.event.pump()
        W, H = self.screen.get_size()
        self.screen.fill((0, 0, 0))
        font = pygame.font.SysFont("georgia,palatinolinotype,timesnewroman,serif", 30, bold=True)
        small = pygame.font.SysFont("georgia,palatinolinotype,timesnewroman,serif", 17)
        t = font.render("D2 Tactics", True, (199, 179, 119))
        self.screen.blit(t, (W / 2 - t.get_width() / 2, H / 2 - 50))
        s = small.render(message, True, (190, 180, 160))
        self.screen.blit(s, (W / 2 - s.get_width() / 2, H / 2 + 6))
        pygame.display.flip()

    def new_world(self, seed=None):
        """New game: start in the Rogue Encampment when D2 files are available."""
        self.levels = {}
        self.hud = self.make_hud() if not hasattr(self, "hud") else self.hud
        self.hud.minimaps = {}
        content = getattr(self.assets, "content", None)
        if getattr(self.assets, "town_kit", None):
            self.loading("Building the Rogue Encampment...")
            self.world = World(seed=seed, level_builder=self.assets.town_builder, content=content,
                               level_id="town", level_name="Rogue Encampment", town=True, exit_to="den")
        else:
            builder = getattr(self.assets, "level_builder", None)
            self.world = World(seed=seed, level_builder=builder, content=content)
        self.levels[self.world.level_id] = self.world
        if hasattr(self.assets, "warm"):
            import time as _t
            t0 = _t.time()
            self.assets.warm(self.world.player, self.loading)
            for npc in self.world.npcs[:6]:
                try:
                    self.assets._sprites_for(npc).frames("NU", npc.facing)
                except Exception:
                    pass
        self._prebuilt = {}
        self._builders = {}
        if getattr(self.world, "town", False):
            self.prebuild("den")
        self._start_scene()
        if self.asset_warning:
            self.world.log(self.asset_warning, (230, 160, 90))

    # ------------------------------------------------------------ Act 1 (D2 files)
    def start_act(self, cls, name, saved=None):
        """New (or loaded) character: build the whole outdoor act and start in the Rogue Encampment."""
        from game.actworld import make_world
        a = self.assets
        self.state = "play"
        self.levels = {}
        self._prebuilt, self._builders, self._build_queue = {}, {}, []
        self.hud.minimaps = {}
        if hasattr(self.hud, "use_class"):
            self.hud.use_class(cls)
        self.loading("Building Act 1 - the Rogue Encampment and the wilderness...")
        player = None
        if saved is not None:
            from game.save import build_player
            player = build_player(saved, a.content)
        self.world = make_world(a.act_kit, a.act_info, a.content, "wild", char_class=cls, char_name=name, player=player)
        self.levels["wild"] = self.world
        if player is not None:
            from game.actworld import ensure_cain
            ensure_cain(self.world)
            if getattr(player, "has_hireling", False):
                from game.quests import hire_rogue
                hire_rogue(self.world)
        self.loading("Preparing your hero...")
        if hasattr(a, "warm"):
            a.warm(self.world.player, self.loading)
            for npc in self.world.npcs[:8]:
                try:
                    a._sprites_for(npc).frames("NU", npc.facing)
                except Exception:
                    pass
        if saved is None:
            self.world.log("Welcome to the Rogue Encampment, %s. Talk to Akara and Kashya." % name, (199, 179, 119))
        else:
            self.world.log("Welcome back, %s (level %d %s)." % (name, self.world.player.level,
                                                              self.world.player.class_name), (199, 179, 119))
        self.save()
        self.world.log("Left click: move / talk / attack. Right click: your skill. Space: end turn. Tab: map.",
                       (170, 170, 170))
        self._start_scene()
        self.prebuild_from(self.world)
        if self.asset_warning:
            self.world.log(self.asset_warning, (230, 160, 90))

    def save(self):
        """Save the hero (on every level change, waypoint, respawn and when quitting)."""
        if getattr(self.world, "level_key", None) is None:
            return
        try:
            from game.save import save_character
            save_character(self.world.player, self.cfg.get("game", "difficulty"))
        except Exception:
            import traceback
            traceback.print_exc()

    def prebuild_from(self, w):
        """Build the dungeons behind this level's entrances in the background (no loading screens)."""
        from game.act1 import WORLD_OF
        for target in sorted(set(t for t in w.exits.values() if t), key=str):
            key = WORLD_OF.get(target, target)
            if key not in self.levels and key not in self._prebuilt and key not in self._build_queue:
                self._build_queue.append(key)
        self._run_builder()

    def _run_builder(self):
        import threading
        if getattr(self, "_builder_thread", None) is not None and self._builder_thread.is_alive():
            return
        if not self._build_queue:
            return
        a = self.assets

        def work():
            from game.actworld import make_world
            from game.units import Player
            while self._build_queue:
                key = self._build_queue.pop(0)
                if key in self.levels or key in self._prebuilt:
                    continue
                try:
                    w = make_world(a.act_kit, a.act_info, a.content, key, player=Player(0, 0))
                    w.events = []
                    self._prebuilt[key] = w
                except Exception:
                    import traceback
                    traceback.print_exc()
        self._builder_thread = threading.Thread(target=work, daemon=True)
        self._builder_thread.start()

    def _get_world(self, key, title):
        from game.actworld import make_world
        if key in self.levels:
            return self.levels[key]
        if key in self._prebuilt:
            return self._prebuilt.pop(key)
        t = getattr(self, "_builder_thread", None)
        if t is not None and t.is_alive() and key in getattr(self, "_build_queue", []) + [None]:
            pass
        if t is not None and t.is_alive():
            self.loading("Entering %s..." % title)
            t.join(timeout=10)
            if key in self._prebuilt:
                return self._prebuilt.pop(key)
        self.loading("Entering %s..." % title)
        a = self.assets
        return make_world(a.act_kit, a.act_info, a.content, key, player=self.world.player)

    def change_level_act(self, target, arrive=None):
        from game.act1 import WORLD_OF
        old = self.world
        old.pending_exit = None
        src_level = old.level_id
        player = old.player
        key = WORLD_OF.get(target, target)
        info = self.assets.act_info
        if key == getattr(old, "level_key", None):
            w = old
        else:
            w = self._get_world(key, info.name(target))
        self.levels[key] = w
        spot = arrive or w.entries.get(src_level) or w.entries.get(target)
        if spot is None:
            spot = w._default_start()
        followers = [a for a in old.allies() if a.ai not in ("turret", "wall")] if w is not old else []
        for a in followers:
            old.monsters.remove(a)
        for m in old.aware_monsters():
            m.aware = False
        old.mode = "explore"
        w.player = player
        w.relocate_player(spot)
        occ = w.occupied()
        for a in followers:
            for r in range(1, 5):
                cands = [(spot[0] + dx, spot[1] + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)]
                c = next((c for c in cands if w.grid.walkable(*c) and c not in occ), None)
                if c:
                    a.x, a.y = c
                    occ.add(c)
                    w.monsters.append(a)
                    break
        w.events = []
        w.update_area()
        from game.actworld import ensure_cain
        ensure_cain(w)
        self.world = w
        self._start_scene()
        self.prebuild_from(w)
        self.save()

    def travel_waypoint(self, lid):
        """Waypoint travel to any activated waypoint of the act."""
        from game.act1 import WORLD_OF
        key = WORLD_OF.get(lid, lid)
        info = self.assets.act_info
        w = self.levels.get(key) or self._get_world(key, info.name(lid))
        self.levels[key] = w
        cell = next((c for c, l in w.waypoints.items() if l == lid), None)
        spot = None
        if cell is not None:
            from game.act1 import arrival_cell
            spot = arrival_cell(w.grid, [cell], set(), w.rng, dist=2)
        if spot is None and lid == 1:
            spot = w._default_start()
        self.change_level_act(lid, arrive=spot)

    def respawn(self):
        """D2: you wake up in the camp (and leave some gold behind)."""
        p = self.world.player
        lost = p.gold // 2
        p.gold -= lost
        p.alive = True
        p.recalc()
        p.hp, p.mana = p.max_hp, p.max_mana
        self.world.game_over = False
        for m in self.world.aware_monsters():
            m.aware = False
        self.world.mode, self.world.turn = "explore", "player"
        wild = self.levels.get("wild")
        if wild is None:
            return
        wild.game_over = False
        if self.world is not wild:
            old = self.world
            self.world = wild
            wild.player = p
            old.player = p
        wild.relocate_player(wild._default_start())
        wild.update_area()
        wild.log("You wake up in the Rogue Encampment. You lost %d gold." % lost, (230, 160, 90))
        self._start_scene()
        self.save()

    def _start_scene(self):
        self._path_cache = {}
        self.walk_queue, self.walk_action, self.walk_goal = [], None, None
        self.scene = Scene(self.world, self.assets, self.fonts)
        self.scene.banner = [self.world.level_name, (199, 179, 119), 2.0]
        self.cam.snap(*self.scene.player_world_pos())

    def prebuild(self, target):
        """Generate a level in the background so entering it needs no loading screen."""
        import random as _r
        import threading
        if target in self.levels or target in self._builders or not hasattr(self.assets, "level_builder"):
            return
        seed = _r.randrange(1 << 30)

        content = getattr(self.assets, "content", None)

        def work():
            try:
                from game.units import Player
                w = World(seed=seed, level_builder=self.assets.level_builder, content=content,
                          level_id=target, level_name="Den of Evil", player=Player(0, 0), exit_to="town")
                w.events = []
                self._prebuilt[target] = w
            except Exception:
                import traceback
                traceback.print_exc()
        t = threading.Thread(target=work, daemon=True)
        self._builders[target] = t
        t.start()

    def change_level(self, target):
        """Walk through an exit: levels are kept, so killed monsters stay dead."""
        if getattr(self.world, "level_key", None) is not None:
            return self.change_level_act(target)
        old = self.world
        old.pending_exit = None
        old.last_pos = old.player.pos
        player = old.player
        if target in self.levels:
            w = self.levels[target]
            w.player = player
            if w.town and getattr(w, "last_pos", None):
                # step back into the camp, away from the exit you used
                near_exit = {(ex + dx, ey + dy) for ex, ey in w.exits for dx in range(-3, 4) for dy in range(-3, 4)}
                from collections import deque
                seen, q, spot = {w.last_pos}, deque([w.last_pos]), w.entry
                while q:
                    c = q.popleft()
                    if c not in near_exit and w.grid.walkable(*c):
                        spot = c
                        break
                    for nb in w.grid.neighbors(*c):
                        if nb not in seen:
                            seen.add(nb)
                            q.append(nb)
            else:
                spot = w.entry
            w.relocate_player(spot)
            w.log("You return to the %s." % w.level_name, (199, 179, 119))
        else:
            builder = self.assets.level_builder
            t = getattr(self, "_builders", {}).get(target)
            if t is not None and t.is_alive():
                self.loading("Entering the Den of Evil...")
                t.join()
            w = getattr(self, "_prebuilt", {}).pop(target, None)
            if w is not None:
                # generated in the background while you were in town: no loading screen
                w.player = player
                w.relocate_player(w.entry)
                w.events = []
                w.enter_message()
            else:
                self.loading("Entering the Den of Evil...")
                w = World(seed=None, level_builder=builder, content=getattr(self.assets, "content", None),
                          level_id=target, level_name="Den of Evil", player=player, exit_to="town")
            self.levels[target] = w
        self.world = w
        self._start_scene()

    # ------------------------------------------------------------ input
    def can_act(self):
        return self.scene.idle() and self.world.player_can_act() and "game_over" not in self.scene.flags

    def can_walk(self):
        """Outside combat you can give new orders while still walking (like D2)."""
        w = self.world
        return (w.mode == "explore" and w.player_can_act() and not w.pending_exit
                and "game_over" not in self.scene.flags and not self.scene.queue
                and self.scene.current is None)

    # ------------------------------------------------------------ D2-style walking
    walk_queue = ()
    walk_goal = None
    walk_action = None

    def walk_to(self, goal, action=None, adjacent=False):
        w = self.world
        p = w.player
        if adjacent:
            path = w.grid.find_path(p.pos, goal, blocked=w.occupied(p), allow_goal_blocked=True)
            path = path[:-1] if path else None
        else:
            path = w.path_for_player(goal)
        self.walk_goal, self.walk_action, self.walk_adjacent = goal, action, adjacent
        if path is None:
            self.walk_queue = []
            return False
        self.walk_queue = list(path)
        if not self.walk_queue and action:
            self._arrive()
        return True

    def _arrive(self):
        act, self.walk_action = self.walk_action, None
        if act:
            kind, target = act[0], act[1]
            w = self.world
            if kind == "attack" and target.alive:
                w.player_attack(target, "attack")
            elif kind == "skill" and target.alive:
                w.use_skill(act[2], target=target)
            elif kind == "talk":
                w.interact(target)
            elif kind == "pickup":
                w.player_pickup(target)
            elif kind == "object":
                w.use_object(target)
            elif kind == "waypoint":
                w.use_waypoint(target)

    def advance_walk(self):
        w = self.world
        if not self.walk_queue:
            return
        if w.mode != "explore" or w.game_over or w.pending_exit:
            self.walk_queue, self.walk_action = [], None
            return
        v = self.scene.view(w.player)
        if len(v.path) > 1 or self.scene.queue or self.scene.current is not None:
            return                  # let the current step play first
        step = self.walk_queue[0]
        if chebyshev(step, w.player.pos) != 1 or step in w.occupied(w.player):
            if not self.walk_to(self.walk_goal, self.walk_action, getattr(self, "walk_adjacent", False)):
                return
            if not self.walk_queue:
                return
            step = self.walk_queue[0]
        self.walk_queue.pop(0)
        last = not self.walk_queue
        w.player_move_to(step, pickup=last and self.walk_action is None)
        if w.mode != "explore":
            self.walk_queue, self.walk_action = [], None
            return
        if last and self.walk_action:
            self._arrive()

    def monster_under_mouse(self, pos):
        """A monster whose sprite is under the mouse (front-most first), else None."""
        W, H = self.screen.get_size()
        wx = (pos[0] - W / 2) / self.cam.scale + self.cam.wx
        wy = (pos[1] - H / 2) / self.cam.scale + self.cam.wy
        for rect, u in reversed(getattr(self.scene, "unit_hits", [])):
            if u.alive and rect.collidepoint((int(wx), int(wy))):
                return u
        return None

    def monster_at(self, cell):
        g = self.world.grid
        if not g.in_bounds(*cell) or not g.visible[cell[1]][cell[0]]:
            return None
        u = self.world.unit_at(cell)
        return u if u is not None and not u.is_player else None

    def make_hud(self):
        """D2's own interface when the UI files are available, otherwise the simple one."""
        if getattr(self.assets, "src", None) is not None:
            try:
                from render.d2hud import D2Hud
                hud = D2Hud(self.fonts, self.assets)
                try:
                    pygame.mouse.set_visible(False)       # D2's hand cursor is drawn instead
                except Exception:
                    pass
                return hud
            except Exception:
                import traceback
                traceback.print_exc()
        return Hud(self.fonts, self.assets)

    def toggle_panel(self, name):
        h = self.hud
        if name == "inv":
            h.show_inv = not h.show_inv
            if h.show_inv:
                h.show_skills = False
        elif name == "char":
            h.show_char = not h.show_char
        elif name == "skills":
            h.show_skills = not getattr(h, "show_skills", False)
            if h.show_skills:
                h.show_inv = False
        elif name == "quests" and hasattr(h, "show_quests"):
            h.show_quests = not h.show_quests
            if h.show_quests:
                h.show_char = False

    def cycle_automap(self):
        h = self.hud
        if hasattr(h, "automap_mode"):
            h.automap_mode = (h.automap_mode + 1) % 3
        else:
            h.show_automap = not h.show_automap

    def handle_click(self, pos, button):
        w = self.world
        h = self.hud
        ui = h.hit(pos)
        if ui:
            action, arg = ui
            if action != "pick_skill" and not str(action).startswith("skill_"):
                h.skill_popup = False if hasattr(h, "skill_popup") else None
            if action == "end_turn" and self.can_act():
                w.end_player_turn()
            elif action in ("inv", "char", "skills", "quests"):
                self.toggle_panel(action)
            elif action == "automap":
                self.cycle_automap()
            elif action == "minipanel":
                h.show_minipanel = not h.show_minipanel
            elif action == "speed":
                self.scene.speed = 1.0 if self.scene.speed > 1 else 2.5
            elif action == "menu":
                h.show_inv = h.show_char = False
                if hasattr(h, "show_skills"):
                    h.show_skills = False
            elif action == "potion" and self.can_act():
                w.use_potion(arg)
            elif action == "item":                      # simple HUD
                if button == 1:
                    w.equip(arg)
                elif button == 3:
                    w.drop_item(arg)
            elif action == "unequip":
                w.unequip(arg)
            elif action == "stat":
                w.add_stat(arg)
            elif action == "waypoint":
                h.show_waypoints = False
                self.travel_waypoint(arg)
                return
            elif action == "waypoints":
                h.show_waypoints = False
            elif action == "skill_right":
                h.skill_popup = not h.skill_popup
            elif action == "pick_skill":
                w.select_right_skill(None if arg == "attack" else arg)
                h.skill_popup = False
            elif action == "skill_page":
                h.skill_page = arg
            elif action == "learn":
                p = w.player
                if button == 3 and p.skills.levels.get(arg) and p.skills.tree[arg].kind != "passive":
                    w.select_right_skill(arg)
                elif p.skills.learn(arg, p.level):
                    p.recalc()
                    if p.right_skill is None and p.skills.tree[arg].kind != "passive":
                        w.select_right_skill(arg)
                    w.log("Learned %s (level %d)." % (p.skills.tree[arg].title, p.skills.levels[arg]), (0, 220, 0))
            elif action == "slot":
                if w.held is not None:
                    w.equip_held(arg)
                elif button == 1:
                    w.pick_from_slot(arg)
                elif button == 3:
                    w.unequip(arg)
            elif action == "grid":
                cell = h.grid_cell_at(pos)
                if cell is None:
                    return
                p = w.player
                if w.held is not None:
                    gx, gy = h._held_anchor(cell, w.held)
                    w.place_held(gx, gy)
                else:
                    it = p.inv_at(*cell)
                    if it is not None:
                        if button == 3:
                            if it.kind == "potion":
                                w.use_inventory_potion(it) if hasattr(w, "use_inventory_potion") else w.equip(it)
                            else:
                                w.equip(it)
                        else:
                            w.pick_from_inventory(it)
            return
        if hasattr(h, "skill_popup"):
            h.skill_popup = False
        if pos[1] > self.screen.get_height() - getattr(h, "BAR_H", 0) and not hasattr(h, "automap_mode"):
            return
        if w.held is not None:
            # D2: clicking the world with an item on the cursor drops it
            w.drop_held()
            return
        cell = self.cam.screen_to_cell(*pos)
        m = self.monster_under_mouse(pos) or self.monster_at(cell)
        if m is not None and getattr(m, "ally", False):
            m = None                      # your own minions can't be attacked
        p = w.player
        if w.mode == "explore" and self.can_walk():
            # D2 style: every click is an order you can change at any time
            if m is not None and getattr(m, "ai", "") == "npc":
                self.walk_to(m.pos, ("talk", m), adjacent=True)
                return
            if m is not None and button == 1:
                self.walk_to(m.pos, ("attack", m), adjacent=True)
                return
            if m is not None and button == 3 and p.right_skill and p.skills.tree[p.right_skill].kind in ("attack", "melee") \
                    and p.right_skill != "Leap Attack":
                self.walk_to(m.pos, ("skill", m, p.right_skill), adjacent=True)
                return
            if button == 1 and m is None:
                g = w.grid
                obj = w.object_at(cell) if hasattr(w, "object_at") else None
                wp = w.waypoint_at(cell) if hasattr(w, "waypoint_at") else None
                if obj is not None and cell not in w.ground:
                    self.walk_to(obj["cell"], ("object", obj), adjacent=True)
                    return
                if wp is not None and cell not in w.ground:
                    if chebyshev(p.pos, wp) <= 2:
                        w.use_waypoint(wp)
                    else:
                        self.walk_to(wp, ("waypoint", wp), adjacent=True)
                    return
                if cell == p.pos and cell in w.ground:
                    w.player_pickup(cell)
                elif cell in w.ground:
                    self.walk_to(cell, ("pickup", cell))
                elif g.in_bounds(*cell) and g.walkable(*cell):
                    self.walk_to(cell)
                return
        if not self.can_act():
            return
        if button == 3:
            skill = p.right_skill
            if skill is None and not getattr(p, "skills", None):
                skill = None
            if skill:
                w.use_skill(skill, target=m, cell=cell if w.grid.in_bounds(*cell) else None)
            elif m:
                # no right skill chosen: Bash if learned (old behaviour), else a normal attack
                if getattr(p, "skills", None) and p.skills.level("Bash"):
                    w.use_skill("Bash", target=m)
                elif not getattr(p, "skills", None) or not hasattr(self.assets, "content"):
                    w.player_attack(m, "bash")
                else:
                    w.player_attack(m)
            return
        if m:
            w.player_attack(m, "attack")
        else:
            g = w.grid
            if cell == p.pos and cell in w.ground:
                w.player_pickup(cell)
            elif g.in_bounds(*cell) and g.walkable(*cell):
                w.player_move_to(cell)

    def handle_key(self, key):
        w = self.world
        h = self.hud
        if key == pygame.K_ESCAPE:
            if w.held is not None:
                w.drop_held()
            elif h.show_inv or h.show_char or getattr(h, "show_skills", False) or getattr(h, "show_quests", False) \
                    or getattr(h, "show_waypoints", False):
                h.show_inv = h.show_char = False
                h.show_waypoints = False
                if hasattr(h, "show_skills"):
                    h.show_skills = False
                if hasattr(h, "show_quests"):
                    h.show_quests = False
            else:
                self.running = False
        elif key in (pygame.K_SPACE, pygame.K_e) and self.can_act():
            w.end_player_turn()
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4) and self.can_act():
            w.use_potion(key - pygame.K_1)
        elif key == pygame.K_i:
            self.toggle_panel("inv")
        elif key == pygame.K_c:
            self.toggle_panel("char")
        elif key == pygame.K_t or key == pygame.K_s:
            self.toggle_panel("skills")
        elif key == pygame.K_q:
            self.toggle_panel("quests")
        elif key == pygame.K_g:
            self.scene.show_grid = not self.scene.show_grid
        elif key == pygame.K_TAB:
            self.cycle_automap()                                   # D2: Tab = automap
        elif key == pygame.K_l:
            self.scene.show_labels = not self.scene.show_labels    # keep item names on
        elif key == pygame.K_f:
            self.scene.speed = 1.0 if self.scene.speed > 1 else 2.5
        elif pygame.K_F1 <= key <= pygame.K_F8:
            p = w.player
            actives = p.skills.actives() if getattr(p, "skills", None) else []
            i = key - pygame.K_F1
            if i == 0:
                w.select_right_skill(None)
            elif i - 1 < len(actives):
                w.select_right_skill(actives[i - 1])
        elif key == pygame.K_r and "game_over" in self.scene.flags and getattr(self.world, "level_key", None) is not None:
            self.respawn()
        elif key == pygame.K_r and ("game_over" in self.scene.flags or "victory" in self.scene.flags):
            self.new_world()
        elif key == pygame.K_n and "victory" in self.scene.flags:
            self.new_world()

    _hold_t = 0.0

    def _hold_walk(self, mouse, dt):
        """Holding the left button keeps walking towards the cursor (D2)."""
        try:
            held = pygame.mouse.get_pressed()[0]
        except Exception:
            held = False
        if not held:
            self._hold_t = 0.0
            return
        self._hold_t += dt
        if self._hold_t < 0.25:
            return
        self._hold_t = 0.15
        w = self.world
        if w.mode != "explore" or self.hud.over_ui(mouse) or getattr(w, "held", None) is not None:
            return
        cell = self.cam.screen_to_cell(*mouse)
        if self.monster_under_mouse(mouse) or not w.grid.walkable(*cell) or cell == w.player.pos:
            return
        if self.walk_action is None and cell != self.walk_goal:
            self.walk_to(cell)

    def _trim_cache(self):
        if len(self._path_cache) > 60:
            self._path_cache = dict(list(self._path_cache.items())[-30:])

    # ------------------------------------------------------------ hover info
    def hover_info(self, mouse):
        """Returns (hover_cell, move_range, path_preview, tooltip)."""
        if self.hud.over_ui(mouse):
            return None, None, None, None
        w = self.world
        cell = self.cam.screen_to_cell(*mouse)
        if not self.can_act():
            return cell, None, None, None
        p = w.player
        highlight = None
        if w.mode == "combat":
            hk = ("r", p.pos, p.ap, w.round, len(w.living_monsters()), tuple(m.pos for m in w.aware_monsters()))
            if hk not in self._path_cache:
                self._trim_cache()
                self._path_cache[hk] = w.reachable_cells()
            highlight = self._path_cache[hk]
        m = self.monster_under_mouse(mouse) or self.monster_at(cell)
        tip = None
        preview = None
        key_base = (p.pos, w.mode, p.ap, w.round, len(w.living_monsters()))
        if m and getattr(m, "ai", "") == "npc":
            return cell, highlight, None, ([m.name, "Click to talk"], [(90, 200, 255), TEXT])
        if m:
            hc, cost = w.preview_attack(m, "attack")
            dist = chebyshev(p.pos, m.pos)
            name_col = GOLD if m.unique else TEXT
            lines = [m.name, f"Level {m.level}   Life {self.scene.view(m).shown_hp}/{m.max_hp}",
                     f"Attack: {int(hc * 100)}% to hit, {cost} AP"]
            rs = getattr(p, "right_skill", None)
            sk = p.skills.tree.get(rs) if rs and getattr(p, "skills", None) else None
            if sk is not None:
                ap, mana = w.skill_cost(rs)
                if sk.kind in ("attack", "melee"):
                    from game.world import hit_chance
                    ar = w._skill_mods(p, rs).get("ar", 0)
                    lines.append(f"{sk.title}: {int(hit_chance(p, m, ar) * 100)}% to hit, {ap} AP")
                else:
                    lines.append(f"{sk.title}: {ap} AP")
            elif not hasattr(self.assets, "content"):
                hb, bcost = w.preview_attack(m, "bash")
                lines.append(f"Bash: {int(hb * 100)}% to hit, {bcost} AP")
            res = getattr(m, "res", {})
            imm = [n for k, n in (("fire", "Fire"), ("cold", "Cold"), ("ltng", "Lightning"), ("pois", "Poison"),
                                  ("mag", "Magic"), ("phys", "Physical")) if res.get(k, 0) >= 100]
            if imm:
                lines.append("Immune to " + ", ".join(imm))
            if dist > 1:
                key = ("m", m.pos) + key_base
                if key not in self._path_cache:
                    self._trim_cache()
                    self._path_cache[key] = w.grid.find_path(p.pos, m.pos, blocked=w.occupied(p), allow_goal_blocked=True)
                path = self._path_cache[key]
                if path:
                    steps = len(path) - 1
                    lines.append(f"Walk {steps} + attack = {steps + cost} AP" if w.mode == "combat" else f"Walk {steps}")
                    preview = [(c, w.mode == "explore" or i < p.ap) for i, c in enumerate(path[:-1])]
            tip = (lines, [name_col] + [TEXT] * (len(lines) - 1))
        else:
            g = w.grid
            if g.in_bounds(*cell) and g.walkable(*cell) and cell != p.pos:
                key = ("c", cell) + key_base
                if key not in self._path_cache:
                    self._trim_cache()
                    self._path_cache[key] = w.path_for_player(cell)
                path = self._path_cache[key]
                if path and w.mode == "combat":      # outside combat you just walk, no AP to plan
                    preview = [(c, i < p.ap) for i, c in enumerate(path)]
                    if w.mode == "combat":
                        tip = ([f"{len(path)} AP" + ("" if len(path) <= p.ap else f"  (only {p.ap} left)")],
                               [TEXT if len(path) <= p.ap else (230, 120, 90)])
            if cell in w.exits and w.exits[cell]:
                names = {"den": "To the Den of Evil", "town": "To the Rogue Encampment"}
                info = getattr(self.assets, "act_info", None)
                t = w.exits[cell]
                label = ("To " + info.name(t)) if info and isinstance(t, int) else names.get(t, "Exit")
                tip = ([label], [(240, 210, 90)])
            obj = w.object_at(cell) if hasattr(w, "object_at") else None
            if obj is not None:
                label = {"cairn": "Cairn Stone", "inifuss": "Tree of Inifuss", "tome": "Moldy Tome",
                         "malus": "Horadric Malus", "cage": "Cain's Cage", "portal": "Portal to Tristram"}
                tip = ([label.get(obj["kind"], obj["kind"]), "Click to use"], [(90, 200, 255), TEXT])
            if hasattr(w, "waypoint_at") and w.waypoint_at(cell) is not None:
                tip = (["Waypoint", "Click to travel"], [(90, 200, 255), TEXT])
            items = w.ground.get(cell)
            if items and g.explored[cell[1]][cell[0]]:
                lines = items[0].describe_lines(p)
                tip = ([t for t, _ in lines], [c for _, c in lines])
        return cell, highlight, preview, tip

    # ------------------------------------------------------------ main loop
    def frame(self, dt):
        mouse = pygame.mouse.get_pos()
        if self.state == "create":
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.VIDEORESIZE:
                    self.cam.resize(ev.w, ev.h)
                else:
                    self.creator.handle(ev)
            if self.state == "create":
                self.creator.update(dt)
                self.creator.draw(self.screen)
                pygame.display.flip()
            return
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.VIDEORESIZE:
                self.cam.resize(ev.w, ev.h)
            elif ev.type == pygame.KEYDOWN:
                self.handle_key(ev.key)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
                self.handle_click(ev.pos, ev.button)
            elif ev.type == pygame.MOUSEWHEEL:
                self.cam.scale = max(1.0, min(3.5, self.cam.scale + ev.y * 0.25))

        try:
            self.scene.alt_held = bool(pygame.key.get_mods() & pygame.KMOD_ALT)
        except Exception:
            self.scene.alt_held = False
        self._hold_walk(mouse, dt)
        self.advance_walk()
        self.scene.update(dt)
        if self.world.pending_exit and self.scene.idle():
            self.change_level(self.world.pending_exit)
        if getattr(self.world, "open_waypoint", None) is not None:
            self.world.open_waypoint = None
            self.hud.show_waypoints = True
        self.cam.resize(*self.screen.get_size())
        self.cam.follow(*self.scene.player_world_pos(), dt)

        cell, highlight, preview, tip = self.hover_info(mouse)
        self.screen.fill((0, 0, 0))
        self.draw_world(cell, highlight, preview)
        self.scene.draw_overlay(self.screen, self.cam)
        self.hud.world_tip = tip
        self.hud.draw(self.screen, self.world, self.scene, mouse)
        if tip and not self.hud.hover_lines and not hasattr(self.hud, "automap_mode"):
            from render.hud import tooltip
            tooltip(self.screen, self.fonts, tip[0], tip[1], mouse)
        self.draw_overlays()
        pygame.display.flip()

    def draw_world(self, cell, highlight, preview):
        """Draw the world 1:1 into a smaller buffer, then scale it up to the window (zoom)."""
        W, H = self.screen.get_size()
        z = self.cam.scale
        ow, oh = max(1, int(W / z + 0.5)), max(1, int(H / z + 0.5))
        if self._offscreen is None or self._offscreen.get_size() != (ow, oh):
            self._offscreen = pygame.Surface((ow, oh))
        off = self._offscreen
        off.fill((0, 0, 0))
        rcam = Camera(ow, oh, 1.0)
        rcam.wx, rcam.wy = self.cam.wx, self.cam.wy
        self.scene.draw(off, rcam, cell, highlight, preview)
        if abs(z - round(z)) < 1e-6:
            img = pygame.transform.scale(off, (int(ow * z), int(oh * z)))
        else:
            img = pygame.transform.smoothscale(off, (int(ow * z), int(oh * z)))
        self.screen.blit(img, (int(W / 2 - ow * z / 2), int(H / 2 - oh * z / 2)))

    def draw_overlays(self):
        W, H = self.screen.get_size()
        if "game_over" in self.scene.flags and self.scene.idle():
            shade = pygame.Surface((W, H), pygame.SRCALPHA)
            shade.fill((40, 0, 0, 150))
            self.screen.blit(shade, (0, 0))
            hint = "Press R to return to the Rogue Encampment" if getattr(self.world, "level_key", None) is not None \
                else "Press R for a new cave, Esc to quit"
            for i, (text, font, col) in enumerate([("You have died", "big", (220, 50, 40)), (hint, "med", TEXT)]):
                img = self.fonts[font].render(text, True, col)
                self.screen.blit(img, (W / 2 - img.get_width() / 2, H / 2 - 40 + i * 50))
        elif "victory" in self.scene.flags:
            if getattr(self.world, "level_key", None) is not None:
                q = getattr(self.world.player, "quests", {})
                if q.get("andariel") in ("cleared", "done"):
                    img = self.fonts["med"].render("Andariel is dead - Act 1 complete!", True, GOLD)
                    self.screen.blit(img, (W / 2 - img.get_width() / 2, 84))
            else:
                img = self.fonts["med"].render("Den of Evil cleared - press N for a new cave", True, GOLD)
                self.screen.blit(img, (W / 2 - img.get_width() / 2, 84))

    def run(self):
        while self.running:
            dt = self.clock.tick(60) / 1000.0
            self.frame(min(dt, 0.05))
        if self.state == "play":
            self.save()
        pygame.quit()


if __name__ == "__main__":
    Game().run()
    sys.exit(0)
