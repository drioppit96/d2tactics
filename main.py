"""D2 Tactics - turn-based tactical combat prototype on a Diablo 2 style isometric grid.

Run:  python main.py
"""
import configparser
import os
import sys
import time

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
                   "diablo2": {"path": ""}, "game": {"difficulty": "normal", "min_hit_chance": "60", "attack_ap_offset": "0"}})
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
            import game.units as _gu
            _gu.ATTACK_AP_OFFSET = max(-4, min(4, self.cfg.getint("game", "attack_ap_offset")))
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
        from render.gamemenu import load_options
        self.opts = load_options()
        self.menu = None
        if getattr(self.assets, "act_kit", None) is not None:
            # D2 files: start at D2's character select screen (creation when there are no heroes yet)
            self.hud = self.make_hud()
            self.open_frontend()
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
        from game import act2 as _act2
        _act2.CURRENT_REAL = _act2.real_tomb(name)          # which of the seven is Tal Rasha's
        player = None
        if saved is not None:
            from game.save import build_player
            player = build_player(saved, a.content)
        import random as _rnd
        base = getattr(player, "map_seed", None) if player is not None else None
        if base is None:
            base = _rnd.randrange(1 << 30)          # the hero's own maps (Esc > Options > same maps)
        if player is not None:
            player.map_seed = base

        class _Seed:
            map_seed = base
        self.world = make_world(a.act_kit, a.act_info, a.content, "wild", char_class=cls, char_name=name, player=player,
                                seed=self._map_seed("wild", _Seed))
        self.world.player.map_seed = base
        self.levels["wild"] = self.world
        if player is not None:
            from game.actworld import ensure_cain
            ensure_cain(self.world)
            from game import quests
            quests.restore(self.world)
            if getattr(player, "merc", None) is not None or getattr(player, "has_hireling", False):
                from game import hireling
                if getattr(player, "merc", None) is None:
                    kind = getattr(player, "hireling_kind", "") or "rogue"
                    player.merc = hireling.new_merc(self.world, kind if kind in hireling.KINDS else "rogue")
                hireling.spawn(self.world)
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
        if saved is not None and int(saved.get("act", 1) or 1) > 1:
            self.travel_act(int(saved.get("act", 1)))   # D2: you continue in the town of the act you were in
        self.prebuild_from(self.world)
        self.start_sprite_prebuild()
        if self.asset_warning:
            self.world.log(self.asset_warning, (230, 160, 90))

    def save(self):
        """Save the hero (on every level change, waypoint, respawn and when quitting)."""
        if getattr(self.world, "level_key", None) is None:
            return
        try:
            from game.save import save_character
            try:
                self.world.player.current_act = self.current_act()      # you continue in this act's town
            except Exception:
                pass
            save_character(self.world.player, self.cfg.get("game", "difficulty"))
        except Exception:
            import traceback
            traceback.print_exc()

    def prebuild_from(self, w):
        """Build the dungeons behind this level's entrances in the background (no loading screens)."""
        from game.acts import world_of
        for target in sorted(set(t for t in w.exits.values() if t), key=str):
            key = world_of(target)
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

        hero = getattr(getattr(self, "world", None), "player", None)

        def work():
            from game.actworld import make_world
            from game.units import Player
            while self._build_queue:
                key = self._build_queue.pop(0)
                if key in self.levels or key in self._prebuilt:
                    continue
                try:
                    w = make_world(a.act_kit, a.act_info, a.content, key, player=Player(0, 0),
                                   seed=self._map_seed(key, hero))
                    w.events = []
                    self._prebuilt[key] = w
                except Exception:
                    import traceback
                    traceback.print_exc()
        self._builder_thread = threading.Thread(target=work, daemon=True)
        self._builder_thread.start()

    def _map_seed(self, key, player=None):
        """With "same maps every game" on, every area is built from the hero's own map seed."""
        if not self.opts.get("fixed_maps", False):
            return None
        p = player or getattr(getattr(self, "world", None), "player", None)
        base = getattr(p, "map_seed", None) if p is not None else None
        if base is None:
            return None
        import zlib
        return zlib.crc32(("%d:%s" % (base, key)).encode()) & 0x3FFFFFFF

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
        return make_world(a.act_kit, a.act_info, a.content, key, player=self.world.player,
                          seed=self._map_seed(key))

    def change_level_act(self, target, arrive=None):
        from game.acts import world_of
        old = self.world
        old.pending_exit = None
        src_level = old.level_id
        player = old.player
        key = world_of(target)
        info = self.assets.act_info
        if key == getattr(old, "level_key", None):
            w = old
        else:
            w = self._get_world(key, info.name(target))
        self.levels[key] = w
        if arrive is not None and (not w.grid.walkable(*arrive) or arrive in w.occupied()):
            arrive = w._free_cell_near(arrive, 5)
        spot = arrive or w.entries.get(src_level) or w.entries.get(target)
        if spot is None:
            spot = w._default_start()
        followers = [a for a in old.allies() if a.ai not in ("turret", "wall")]
        for a in followers:
            old.monsters.remove(a)          # (put back below - also when the level stays the same)
        for m in old.aware_monsters():
            m.aware = False
        old.mode = "explore"
        w.player = player
        w.relocate_player(spot)
        occ = w.occupied()
        for a in followers:
            placed = False
            for r in range(1, 5):
                cands = [(spot[0] + dx, spot[1] + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)]
                c = next((c for c in cands if w.grid.walkable(*c) and c not in occ), None)
                if c:
                    a.x, a.y = c
                    occ.add(c)
                    placed = True
                    break
            if not placed:
                a.x, a.y = w._free_cell_near(spot, 10)
            a.aware = False
            w.monsters.append(a)
        w.events = []
        w.update_area()
        from game.actworld import ensure_cain
        ensure_cain(w)
        from game import quests
        quests.restore(w)
        self.world = w
        self._start_scene()
        self.prebuild_from(w)
        self.save()

    def travel_waypoint(self, lid):
        """Waypoint travel to any activated waypoint of the act."""
        from game.acts import world_of
        key = world_of(lid)
        info = self.assets.act_info
        w = self.levels.get(key) or self._get_world(key, info.name(lid))
        self.levels[key] = w
        cell = next((c for c, l in w.waypoints.items() if l == lid), None)
        spot = None
        if cell is not None:
            from game.act1 import arrival_cell
            spot = arrival_cell(w.grid, [cell], set(), w.rng, dist=2)
        from game.acts import TOWN_IDS
        if spot is None and lid in TOWN_IDS:
            spot = w._default_start()
        self.change_level_act(lid, arrive=spot)

    def npc_option(self, npc, opt):
        w, h = self.world, self.hud
        h.npc_menu = None
        if npc is None:
            return
        if opt == "Talk":
            from game import quests
            lines = quests.talk(w, npc)
            from game.world import NPC_LINES
            for line in lines or [NPC_LINES.get(npc.npc, npc.name + ": Hello.")]:
                w.log(line, (220, 210, 170))
        elif opt in ("Trade", "Gamble"):
            h.store = w.open_store(npc.npc, gamble=opt == "Gamble")
            h.show_inv = True
            h.show_char = h.show_quests = False
            h.show_skills = False
        elif opt == "Identify Items":
            w.identify_all()
        elif opt == "Recharge":
            from game import durability
            durability.recharge_all(w)
        elif opt == "Level 99 (test)":
            # TESTING ONLY: jump to level 99 with every stat and skill point the levels give
            p = w.player
            if p.level >= 99:
                w.log("Akara: You are already as strong as anyone can be.", (220, 210, 170))
            else:
                before = p.level
                p.gain_xp(max(0, p.xp_threshold(98) - p.xp))
                p.recalc()
                p.hp, p.mana = p.max_hp, p.max_mana
                w.emit("levelup", p.level)
                w.log("Akara: Level %d -> 99. You have %d stat points and %d skill points to spend."
                      % (before, p.stat_points, p.skills.points), (199, 179, 119))
                self.save()
        elif opt == "Hire" and npc.npc == "greiz":
            from game import quests2
            quests2.hire_guard(w)
        elif opt == "Sail East":
            q = w.player.quests
            if q.get("tombs") in ("cleared", "done"):
                w.log("Meshif: To Kurast!", (220, 210, 170))
                self.travel_act(3)
            else:
                w.log("Meshif: Not while Duriel's evil holds the seas. Talk to Jerhyn.", (220, 210, 170))
        elif opt == "Hire" and npc.npc in ("asheara", "qual-kehk"):
            from game import quests2
            quests2.hire_guard(w, kind="act3hire" if npc.npc == "asheara" else "act5hire1")
        elif opt == "Hire":
            from game import quests
            q = w.player.quests
            if q.get("blood_raven") != "done":
                w.log("Kashya: Prove yourself first - kill Blood Raven.", (220, 210, 170))
            elif any(getattr(a, "hireling", False) for a in w.allies()):
                w.log("Kashya: You already have one of my scouts.", (220, 210, 170))
            else:
                for line in quests.talk(w, npc):
                    w.log(line, (220, 210, 170))
        elif opt == "Go East":
            q = w.player.quests
            if q.get("andariel") in ("cleared", "done"):
                q["andariel"] = "done"
                w.log("Warriv: To Lut Gholein!", (220, 210, 170))
                self.travel_act(2)
            else:
                w.log("Warriv: The pass is blocked until Andariel falls.", (220, 210, 170))
        elif opt == "Go East (test)":
            # TESTING ONLY: travel to Act 2 without killing Andariel
            w.log("Warriv: To Lut Gholein!", (220, 210, 170))
            self.travel_act(2)
        elif opt == "Go West":
            w.log("Warriv: Back to the Rogue Encampment.", (220, 210, 170))
            self.travel_act(1)
        elif opt in ("Sail East (test)", "To Act 4 (test)", "Travel to Harrogath (test)"):
            # TESTING ONLY: travel on without the act's last quest
            self.travel_act({"Sail East (test)": 3, "To Act 4 (test)": 4, "Travel to Harrogath (test)": 5}[opt])
        elif opt == "Sail West":
            w.log("Meshif: Back to Lut Gholein, then.", (220, 210, 170))
            self.travel_act(2)
        elif opt == "Travel to Harrogath":
            q = w.player.quests
            if q.get("diablo") in ("cleared", "done"):
                q["diablo"] = "done"
                w.log("Tyrael: Go now - Harrogath needs you.", (220, 210, 170))
                self.travel_act(5)
            else:
                w.log("Tyrael: Diablo still lives. The way to Harrogath stays closed.", (220, 210, 170))
        elif opt == "Imbue Sockets":
            from game import quests345
            quests345.larzuk_sockets(w)

    def current_act(self):
        from game.acts import act_of
        w = self.world
        return act_of(w.level_id if getattr(w, "level_id", None) else getattr(w, "level_key", 1))

    def town_world(self, act):
        """The (built) world holding the town of an act."""
        from game.acts import TOWNS, world_of
        town = TOWNS.get(act, 1)
        key = world_of(town)
        w = self.levels.get(key)
        if w is None:
            w = self._get_world(key, self.assets.act_info.name(town))
            self.levels[key] = w
        return town, w

    def travel_act(self, act):
        """Warriv / Meshif: to the town of another act (you arrive next to the caravan / ship)."""
        town, w = self.town_world(act)
        self.change_level_act(town, arrive=w._default_start())
        self._prebuild_proc = None if not getattr(self, "_prebuild_proc", None) or \
            not self._prebuild_proc.is_alive() else self._prebuild_proc
        self.start_sprite_prebuild()          # the new act's monsters and missiles

    def portal_to_town(self):
        """Through your Town Portal: you arrive next to its twin in the town of this act."""
        town, wild = self.town_world(self.current_act())
        base = wild._default_start()
        cell = wild._free_cell_near((base[0] + 2, base[1] - 2), 4)
        wild.objects = [o for o in wild.objects if o["kind"] != "tp_back"]
        wild.objects.append(dict(kind="tp_back", cell=cell, level=town, oid=0, used=False, target=None))
        spot = wild._free_cell_near((cell[0] + 1, cell[1] + 2), 3)
        self.change_level_act(town, arrive=spot)

    def portal_back(self):
        p = self.world.player
        info = getattr(p, "portal", None)
        if not info:
            return
        key, cell, lid = info
        self.change_level_act(lid, arrive=(cell[0] + 1, cell[1] + 1))
        # the portal closes once you have used it to go back
        for w in list(self.levels.values()):
            w.objects = [o for o in w.objects if o["kind"] not in ("tp", "tp_back")]
        p.portal = None

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
        town, wild = self.town_world(self.current_act())
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
        wild.log("You wake up in %s. You lost %d gold." % (self.assets.act_info.name(town), lost), (230, 160, 90))
        self._start_scene()
        self.save()

    def _start_scene(self):
        if hasattr(self.assets, "set_act"):
            try:
                self.assets.set_act(self.current_act())
            except Exception:
                pass
        self._path_cache = {}
        self.walk_queue, self.walk_action, self.walk_goal = [], None, None
        self.scene = Scene(self.world, self.assets, self.fonts)
        self.scene.banner = [self.world.level_name, (199, 179, 119), 2.0]
        self.scene.opts = self.opts
        self.cam.snap(*self.scene.player_world_pos())

    # ------------------------------------------------------------ sprite cache prebuild
    def sprite_plan(self):
        """What the act needs, most urgent first (cheap: the background process works out the
        files itself): your look, the monsters near you, the rest of the act's monsters, then the
        missiles of your skills and of the monsters."""
        a = self.assets
        w = self.world
        p = w.player
        plan = {"player": None, "monsters": [], "missiles": []}
        try:
            arms, hide, wclass = a.player_look(p)
            plan["player"] = (getattr(p, "token", "BA") or "BA", [wclass, "HTH"] if wclass != "HTH" else ["HTH"],
                              {k: list(v) for k, v in arms.items()})
        except Exception:
            pass
        ids = []
        for m in sorted([m for m in w.monsters if getattr(m, "d2id", None)], key=lambda m: abs(m.x - p.x) + abs(m.y - p.y)):
            if m.d2id not in ids:
                ids.append(m.d2id)
        info = getattr(a, "act_info", None)
        if info is not None:
            from game.acts import ACT_RANGES
            for lid in ACT_RANGES.get(self.current_act(), range(1, 40)):
                for mid in info.roster(lid):
                    if mid not in ids:
                        ids.append(mid)
        bosses = {1: ("andariel", "bloodraven", "corpsefire", "smith", "griswold", "countess"),
                  2: ("radament", "duriel", "summoner"),
                  3: ("mephisto", "councilmember1", "councilmember2", "councilmember3", "fetishshaman4"),
                  4: ("diablo", "izual", "hephasto", "fingermage3", "doomknight3", "megademon3"),
                  5: ("baalcrab", "nihlathakboss", "ancientbarb1", "ancientbarb2", "ancientbarb3", "overseer1")}
        for mid in bosses.get(self.current_act(), ()):
            if mid not in ids:
                ids.append(mid)
        plan["monsters"] = ids
        names = []
        tree = getattr(getattr(p, "skills", None), "tree", {})
        for sk in tree.values():
            d = sk.data or {}
            for col in ("cltmissile", "srvmissile", "cltmissilea", "srvmissilea", "cltmissileb"):
                if d.get(col):
                    names.append(d[col])
            if hasattr(w, "ground_missile"):
                names.append(w.ground_missile(sk))
        names += ["arrow", "bolt", "javelin", "frozenorbbolt"]
        plan["missiles"] = [n for n in names if n]
        return plan

    def start_sprite_prebuild(self):
        """Fill the sprite cache in a separate low-priority process while you play."""
        a = self.assets
        old = getattr(self, "_prebuild_proc", None)
        if not hasattr(a, "cache_root") or (old is not None and old.is_alive()):
            return
        try:
            plan = self.sprite_plan()
        except Exception:
            import traceback
            traceback.print_exc()
            return
        import multiprocessing
        from d2 import spritecache
        prog = os.path.join(a.cache_root, "sprites", "progress.txt")
        try:
            os.remove(prog)
        except OSError:
            pass
        try:
            ctx = multiprocessing.get_context("spawn")
            proc = ctx.Process(target=spritecache.worker_main,
                               args=(a.d2_path, os.path.join(a.cache_root, "sprites"), os.path.join(a.cache_root, "mpq"),
                                     plan, prog),
                               daemon=True)
            proc.start()
            self._prebuild_proc = proc
        except Exception:
            import traceback
            traceback.print_exc()

    def prebuild_progress(self):
        """(done, total) of the background sprite preparation, or None when it isn't running."""
        proc = getattr(self, "_prebuild_proc", None)
        if proc is None:
            return None
        try:
            with open(os.path.join(self.assets.cache_root, "sprites", "progress.txt")) as f:
                n, total = [int(v) for v in f.read().split()[:2]]
        except Exception:
            n, total = 0, 0
        return n, total

    def _warm_skill_art(self):
        """Decode the selected skill's missiles / overlays in spare frame time, before you cast."""
        a = self.assets
        if not hasattr(a, "pump"):
            return
        p = self.world.player
        rs = getattr(p, "right_skill", None)
        if rs != getattr(self, "_warmed_skill", 0):
            self._warmed_skill = rs
            sk = p.skills.tree.get(rs) if rs and getattr(p, "skills", None) else None
            w = self.world
            if sk is not None:
                d = sk.data or {}
                for col in ("cltmissile", "srvmissile", "cltmissilea", "srvmissilea", "cltmissileb", "cltmissilec"):
                    a.warm_missile(d.get(col))
                if hasattr(w, "ground_missile"):
                    a.warm_missile(w.ground_missile(sk))
                if sk.key == "Frozen Orb":
                    a.warm_missile("frozenorbbolt")
                if d.get("castoverlay"):
                    a.warm_missile(d["castoverlay"], overlay=True)
            if hasattr(w, "weapon_missile"):
                a.warm_missile(w.weapon_missile(p))
        self._warm_tick = getattr(self, "_warm_tick", 0) + 1
        w = self.world
        if self._warm_tick % 30 == 0 and w.mode == "combat" and hasattr(w, "weapon_missile"):
            for m in w.aware_monsters():          # what the monsters will shoot at you
                if m.range > 1:
                    a.warm_missile(w.weapon_missile(m))
        a.pump(0.006)

    def apply_options(self):
        if getattr(self, "scene", None) is not None:
            self.scene.opts = self.opts
        self._path_cache = {}

    def open_menu(self):
        from render.gamemenu import GameMenu
        self.menu = GameMenu(self)

    def save_and_exit(self):
        """D2: Save and Exit Game -> back to the hero select screen."""
        self.save()
        self.menu = None
        self.open_frontend(select=True)
        if self.state != "create":
            self.running = False

    def open_frontend(self, select=None):
        """Character select (if you have heroes, or select=True) or character creation."""
        from game.save import list_saves
        if select is None:
            try:
                select = bool(list_saves())
            except Exception:
                select = False
        if hasattr(self.assets, "set_act"):
            self.assets.set_act(1)
        try:
            if select:
                from render.charselect import CharSelect
                self.creator = CharSelect(self)
            else:
                from render.charcreate import CharCreate
                self.creator = CharCreate(self)
            self.state = "create"
        except Exception:
            import traceback
            traceback.print_exc()
            if select:
                return self.open_frontend(select=False)
            self.creator = None

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
            u = w.unit_at(goal)
            if u is not None and getattr(u, "radius", 0) and hasattr(w, "attack_path"):
                path = w.attack_path(p, u)
            else:
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

    def object_under_mouse(self, pos):
        """A chest / shrine / door ... whose picture is under the mouse (front-most first)."""
        from game.objects import clickable
        W, H = self.screen.get_size()
        wx = (pos[0] - W / 2) / self.cam.scale + self.cam.wx
        wy = (pos[1] - H / 2) / self.cam.scale + self.cam.wy
        for rect, o in reversed(getattr(self.scene, "object_hits", [])):
            if clickable(o) and rect.collidepoint((int(wx), int(wy))):
                return o
        return None

    def _skill_area(self, cell):
        """Tiles your right-click skill would cover at `cell` (missile paths, blast areas)."""
        w = self.world
        p = w.player
        rs = getattr(p, "right_skill", None)
        if not rs or rs == "throw" or not self.opts.get("show_skill_area", True) or not hasattr(w, "skill_preview"):
            return None
        g = w.grid
        if cell is None or not g.in_bounds(*cell) or not g.explored[cell[1]][cell[0]] or cell == p.pos:
            return None
        key = ("sk", rs, cell, p.pos, w.round, p.skills.level(rs),
               tuple(m.pos for m in w.monsters if m.alive), len(getattr(w, "corpses", ())))
        if key not in self._path_cache:
            self._trim_cache()
            try:
                pv = w.skill_preview(rs, cell)
            except Exception:
                pv = None
            if pv is not None:
                from game.skillcast import SPELL_RANGE
                kind = p.skills.tree[rs].kind
                far = kind != "nova" and chebyshev(cell, p.pos) > SPELL_RANGE
                pv = (pv[0], pv[1], far)
            self._path_cache[key] = pv
        return self._path_cache[key]

    def loot_on_screen(self):
        """[(cell, item)] for every item lying on the visible part of the map, nearest first."""
        w = self.world
        g = w.grid
        W, H = self.screen.get_size()
        p = w.player
        out = []
        for cell, items in w.ground.items():
            x, y = cell
            if not g.in_bounds(x, y) or not g.explored[y][x]:
                continue
            sx, sy = self.cam.cell_to_screen(x, y)
            if -20 <= sx <= W + 20 and -20 <= sy <= H + 20:
                for it in items:
                    out.append((cell, it))
        out.sort(key=lambda ci: (chebyshev(ci[0], p.pos), ci[1].kind == "gold"))
        return out

    def unit_screen_rect(self, u):
        """Where a unit's sprite is on the window (from the last drawn frame), or None."""
        W, H = self.screen.get_size()
        z = self.cam.scale
        for rect, v in getattr(self.scene, "unit_hits", []):
            if v is u:
                x = (rect.x - self.cam.wx) * z + W / 2
                y = (rect.y - self.cam.wy) * z + H / 2
                return pygame.Rect(int(x), int(y), int(rect.w * z), int(rect.h * z))
        return None

    def monster_at(self, cell):
        g = self.world.grid
        if not g.in_bounds(*cell):
            return None
        u = self.world.unit_at(cell)
        if u is None or u.is_player or getattr(u, "hidden", False):
            return None
        if not g.visible[cell[1]][cell[0]] and not any(v is u for _, v in getattr(self.scene, "unit_hits", [])):
            return None         # only what is drawn on screen can be picked
        return u

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

    def open_cube(self, box):
        h = self.hud
        h.cube_item = box
        h.show_cube = True
        h.show_inv = True
        h.show_char = h.show_quests = h.show_skills = False
        h.show_waypoints = False
        h.store = None

    def toggle_merc(self):
        h = self.hud
        if getattr(self.world.player, "merc", None) is None:
            self.world.log("You have no hireling.", (160, 160, 160))
            return
        h.show_merc = not getattr(h, "show_merc", False)
        if h.show_merc:
            h.show_char = h.show_quests = h.show_cube = False
            h.show_waypoints = False
            h.store = None
            h.show_inv = True

    def open_stash(self):
        p = self.world.player
        if getattr(p, "stash", None) is None:
            from game.cube import make_stash
            p.stash = make_stash()
        self.open_cube(p.stash)

    def toggle_panel(self, name):
        h = self.hud
        if name == "inv":
            h.show_inv = not h.show_inv
            if h.show_inv:
                h.show_skills = False
            else:
                h.show_cube = False
        elif name == "char":
            h.show_char = not h.show_char
            h.show_cube = False
        elif name == "skills":
            h.show_skills = not getattr(h, "show_skills", False)
            if h.show_skills:
                h.show_inv = False
        elif name == "quests" and hasattr(h, "show_quests"):
            h.show_quests = not h.show_quests
            h.show_cube = False
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
        if getattr(h, "npc_menu", None) is not None and not (ui and ui[0] == "npc_opt"):
            h.npc_menu = None
        if ui:
            action, arg = ui
            if action != "pick_skill" and not str(action).startswith("skill_"):
                h.skill_popup = False if hasattr(h, "skill_popup") else None
            if action == "npc_opt":
                self.npc_option(h.npc_menu, arg)
                return
            if action == "store_tab":
                h.store.tab = arg
                return
            if action == "store_close":
                h.store = None
                return
            if action == "store_item":
                if w.held is not None:
                    return
                if button == 1:
                    w.buy(h.store, arg)
                return
            if action == "store_grid":
                if w.held is not None and w.held in ():
                    pass
                return
            if action == "end_turn" and self.can_act():
                w.end_player_turn()
            elif action in ("inv", "char", "skills", "quests"):
                self.toggle_panel(action)
            elif action == "cube_close":
                h.show_cube = False
            elif action == "merc_close":
                h.show_merc = False
            elif action == "merc_slot":
                from game import hireling
                if getattr(w.player, "merc", None) is None:
                    return
                if w.held is not None:
                    back = hireling.equip(w, arg, w.held)
                    if back is not w.held:
                        w.held = back
                else:
                    w.held = hireling.unequip(w, arg)
                return
            elif action == "stash_gold":
                w.stash_gold(deposit=(button == 1))
            elif action == "transmute":
                if h.cube_item is not None and w.held is None:
                    w.transmute(h.cube_item)
            elif action == "cube_grid":
                cell = h.cube_cell_at(pos)
                box = h.cube_item
                if cell is None or box is None:
                    return
                from game import cube as cb
                if w.held is not None:
                    ax, ay = h.cube_anchor(w.held)
                    w.cube_place(box, ax, ay)
                else:
                    it = cb.at(box, *cell)
                    if it is not None:
                        w.cube_pick(box, it)
                return
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
                self.open_menu()
            elif action == "loot_pick":
                cell, it = arg
                if w.pickup_item(cell, it):
                    self._path_cache = {}
            elif action == "loot_close":
                h.show_loot = False
            elif action == "loot_panel":
                pass
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
            elif action == "wp_tab":
                h.wp_act = arg
            elif action == "q_tab":
                h.q_act = arg
            elif action == "waypoint":
                h.show_waypoints = False
                self.travel_waypoint(arg)
                return
            elif action == "waypoints":
                h.show_waypoints = False
            elif action == "wp_all":                      # TEST ONLY: remove later
                from game.acts import WAYPOINTS
                p = w.player
                p.waypoints = set(getattr(p, "waypoints", {1})) | {l for lst in WAYPOINTS.values() for l in lst}
                w.log("Test: every waypoint of Acts 1-5 is now active.", (199, 179, 119))
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
                eq = w.player.equipment.get(arg)
                if getattr(w, "cursor_mode", None) and w.cursor_mode[0] == "identify":
                    w.identify_with(w.cursor_mode[1], eq)
                elif w.held is not None and getattr(w.held, "gem", None) is not None and eq is not None:
                    w.insert_into(eq, w.held)
                elif w.held is not None:
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
                target = p.inv_at(*cell)
                if getattr(w, "cursor_mode", None) and w.cursor_mode[0] == "identify":
                    w.identify_with(w.cursor_mode[1], target)
                elif w.held is not None and getattr(w.held, "gem", None) is not None and target is not None \
                        and getattr(target, "sockets", 0) and target is not w.held:
                    w.insert_into(target, w.held)
                elif w.held is not None and target is not None and getattr(target, "code", "") == "box" \
                        and target is not w.held:
                    w.cube_insert(target)
                elif w.held is not None:
                    gx, gy = h._held_anchor(cell, w.held)
                    w.place_held(gx, gy)
                else:
                    it = target
                    if it is not None:
                        if button == 3:
                            if getattr(h, "store", None) is not None:
                                w.sell(it)
                            elif getattr(it, "use", None) == "cube":
                                self.open_cube(it)
                            elif it.kind == "potion" or getattr(it, "use", None):
                                w.use_item(it) if hasattr(w, "use_item") else w.use_inventory_potion(it)
                            elif getattr(it, "gem", None) is None:
                                w.equip(it)
                        else:
                            if it is getattr(h, "cube_item", None):
                                h.show_cube = False
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
            if getattr(m, "hireling", False) and button == 1:
                self.toggle_merc()        # click your hireling: its inventory
                return
            m = None                      # your own minions can't be attacked
        p = w.player
        if w.mode == "explore" and self.can_walk():
            # D2 style: every click is an order you can change at any time
            if m is not None and getattr(m, "ai", "") == "npc":
                self.walk_to(m.pos, ("talk", m), adjacent=True)
                return
            if m is not None and button == 1:
                if getattr(p, "ranged", False) and w.udist(p, m) <= p.range and w.grid.line_of_sight(p.pos, m.pos):
                    w.player_attack(m, "attack")          # bows shoot from where you stand
                    return
                self.walk_to(m.pos, ("attack", m), adjacent=True)
                return
            if m is not None and button == 3 and p.right_skill in ("throw", "Double Throw") and getattr(p, "throwing", False):
                w.use_skill(p.right_skill, target=m)    # throws from where you stand (walks into range if needed)
                return
            if m is not None and button == 3 and p.right_skill and p.skills.tree.get(p.right_skill) is not None \
                    and p.skills.tree[p.right_skill].kind in ("attack", "melee") and p.right_skill != "Leap Attack":
                self.walk_to(m.pos, ("skill", m, p.right_skill), adjacent=True)
                return
            if button == 1 and m is None:
                g = w.grid
                obj = self.object_under_mouse(pos) or (w.object_at(cell) if hasattr(w, "object_at") else None)
                wp = w.waypoint_at(cell) if hasattr(w, "waypoint_at") else None
                if obj is not None and cell not in w.ground:
                    if obj.get("generic"):
                        stand = w.object_stand_cell(obj)
                        if stand == p.pos:
                            w.use_object(obj)
                        elif stand is not None:
                            self.walk_to(stand, ("object", obj))
                        return
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
        if self.menu is not None:
            self.menu.key(key)
            return
        if key == pygame.K_ESCAPE:
            if getattr(h, "store", None) is not None or getattr(h, "npc_menu", None) is not None:
                h.store = None
                h.npc_menu = None
            elif getattr(w, "cursor_mode", None):
                w.cursor_mode = None
            elif w.held is not None:
                w.drop_held()
            elif h.show_inv or h.show_char or getattr(h, "show_skills", False) or getattr(h, "show_quests", False) \
                    or getattr(h, "show_waypoints", False) or getattr(h, "show_cube", False):
                h.show_inv = h.show_char = False
                h.show_cube = False
                h.show_waypoints = False
                if hasattr(h, "show_skills"):
                    h.show_skills = False
                if hasattr(h, "show_quests"):
                    h.show_quests = False
            elif getattr(h, "show_loot", False):
                h.show_loot = False
            else:
                self.open_menu()
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
        elif key == pygame.K_F11:
            self.show_perf = not getattr(self, "show_perf", False)   # performance readout
        elif key == pygame.K_v:
            h.show_loot = not getattr(h, "show_loot", False)        # loot window
        elif key == pygame.K_l:
            self.scene.show_labels = not self.scene.show_labels    # keep item names on
        elif key == pygame.K_o:
            self.toggle_merc()
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
        self._tip_unit = None
        if getattr(self, "scene", None) is not None:
            self.scene.selected = None
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
            if not self.opts.get("show_move_range", True):
                highlight = None
        m = self.monster_under_mouse(mouse) or self.monster_at(cell)
        self.scene.skill_area = self._skill_area(m.pos if m is not None and m.ai != "npc" else cell)
        tip = None
        preview = None
        key_base = (p.pos, w.mode, p.ap, w.round, len(w.living_monsters()))
        if m and getattr(m, "ai", "") == "npc":
            return cell, highlight, None, ([m.name, "Click to talk"], [(90, 200, 255), TEXT])
        if m:
            hc, cost = w.preview_attack(m, "attack")
            dist = w.udist(p, m) if hasattr(w, "udist") else chebyshev(p.pos, m.pos)
            name_col = GOLD if m.unique else ((110, 110, 255) if getattr(m, "champion", False) else TEXT)
            lines = [m.name, f"Level {m.level}   Life {self.scene.view(m).shown_hp}/{m.max_hp}",
                     f"Attack: {int(hc * 100)}% to hit, {cost} AP"]
            if getattr(m, "mod_names", None):
                lines.insert(1, ", ".join(m.mod_names))
            rs = getattr(p, "right_skill", None)
            sk = p.skills.tree.get(rs) if rs and getattr(p, "skills", None) else None
            if rs == "throw" and getattr(p, "throwing", False):
                lines.append(f"Throw: {int(hc * 100)}% to hit, {cost} AP (range {p.throw_range})")
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
                    self._path_cache[key] = w.attack_path(p, m) if hasattr(w, "attack_path") else \
                        (w.grid.find_path(p.pos, m.pos, blocked=w.occupied(p), allow_goal_blocked=True) or [None])[:-1]
                path = self._path_cache[key]
                if path:
                    steps = len(path)
                    lines.append(f"Walk {steps} + attack = {steps + cost} AP" if w.mode == "combat" else f"Walk {steps}")
                    preview = [(c, w.mode == "explore" or i < p.ap) for i, c in enumerate(path)]
            cols = [name_col] + [TEXT] * (len(lines) - 1)
            if getattr(m, "mod_names", None):
                cols[1] = (110, 110, 255)
            tip = (lines, cols)
            self._tip_unit = m
            self.scene.selected = m
        else:
            g = w.grid
            if g.in_bounds(*cell) and g.walkable(*cell) and cell != p.pos and w.mode == "combat":
                key = ("c", cell) + key_base
                if key not in self._path_cache:
                    self._trim_cache()
                    # a short, capped search: a cell you can't reach (inside a closed house, across a
                    # river) must not make the game search the whole map every time the mouse moves
                    blocked = w.occupied(p)
                    path = w._straight_path(p.pos, cell, blocked)
                    if path is None:
                        path = g.find_path(p.pos, cell, blocked=blocked, max_cost=max(30, p.ap * 2), limit=6000)
                    self._path_cache[key] = path
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
            obj = self.object_under_mouse(mouse) or (w.object_at(cell) if hasattr(w, "object_at") else None)
            if obj is not None:
                label = {"cairn": "Cairn Stone", "inifuss": "Tree of Inifuss", "tome": "Moldy Tome",
                         "malus": "Horadric Malus", "cage": "Cain's Cage", "portal": "Portal to Tristram",
                         "tp": "Town Portal (to the Rogue Encampment)", "tp_back": "Town Portal (back)"}
                if obj.get("generic"):
                    from game.objects import tooltip as _otip
                    lines = _otip(obj)
                    tip = (lines, [(90, 200, 255)] + [TEXT] * (len(lines) - 1))
                else:
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
        t_frame = time.perf_counter()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.VIDEORESIZE:
                self.cam.resize(ev.w, ev.h)
            elif ev.type == pygame.KEYDOWN:
                self.handle_key(ev.key)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3) and self.menu is not None:
                self.menu.click(ev.pos, ev.button)
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
                self.handle_click(ev.pos, ev.button)
            elif ev.type == pygame.MOUSEWHEEL and self.menu is None:
                self.cam.scale = max(1.0, min(3.5, self.cam.scale + ev.y * 0.25))
        if self.state == "create":
            return
        if self.menu is not None:
            # single player: the game waits while the menu is open (like D2)
            self.menu.update(dt)
            self.screen.fill((0, 0, 0))
            self.draw_world(None, None, None)
            self.scene.draw_overlay(self.screen, self.cam)
            self.hud.world_tip = None
            self.hud.draw(self.screen, self.world, self.scene, (-100, -100))
            if self.menu is not None:
                self.menu.draw(self.screen, mouse)
            pygame.display.flip()
            return

        try:
            self.scene.alt_held = bool(pygame.key.get_mods() & pygame.KMOD_ALT)
        except Exception:
            self.scene.alt_held = False
        self._hold_walk(mouse, dt)
        self.advance_walk()
        if getattr(self.world, "open_stash", False):
            self.world.open_stash = False
            self.open_stash()
        h = self.hud
        if getattr(h, "show_cube", False) and getattr(getattr(h, "cube_item", None), "code", "") == "stash":
            from game.grid import chebyshev as _cheb
            pp = self.world.player.pos
            if not any(o.get("kind") == "stash" and _cheb(o["cell"], pp) <= 5 for o in self.world.objects):
                h.show_cube = False         # walked away from the stash
        if getattr(self, "scene", None) is not None:
            self.scene.walk_target = self.walk_goal if self.walk_queue and self.world.mode == "explore" else None
        tp = time.perf_counter()
        self._warm_skill_art()
        self._perf_mark("prep", tp)
        self.scene.update(dt)
        if self.world.pending_exit and self.scene.idle():
            w = self.world
            kind = getattr(w, "pending_portal", None)
            arrive = getattr(w, "pending_arrive", None)
            w.pending_portal = w.pending_arrive = None
            if kind == "tp":
                self.portal_to_town()
            elif kind == "tp_back":
                self.portal_back()
            elif arrive is not None:
                self.change_level_act(w.pending_exit, arrive=arrive)
            else:
                self.change_level(w.pending_exit)
        if getattr(self.world, "open_npc", None) is not None:
            self.hud.npc_menu = self.world.open_npc
            self.world.open_npc = None
        if getattr(self.world, "open_waypoint", None) is not None:
            self.world.open_waypoint = None
            self.hud.show_waypoints = True
        self.cam.resize(*self.screen.get_size())
        self.cam.follow(*self.scene.player_world_pos(), dt)

        self._perf_mark("logic", t_frame, minus=("prep",))
        t1 = time.perf_counter()
        cell, highlight, preview, tip = self.hover_info(mouse)
        self._perf_mark("hover", t1)
        t1 = time.perf_counter()
        self.screen.fill((0, 0, 0))
        self.draw_world(cell, highlight, preview)
        self._perf_mark("world", t1)
        t1 = time.perf_counter()
        self.scene.draw_overlay(self.screen, self.cam)
        self.hud.world_tip = tip
        self.hud.loot_list = self.loot_on_screen() if getattr(self.hud, "show_loot", False) else None
        self.hud.world_tip_anchor = self.unit_screen_rect(self._tip_unit) if getattr(self, "_tip_unit", None) else None
        self.hud.draw(self.screen, self.world, self.scene, mouse)
        if tip and not self.hud.hover_lines and not hasattr(self.hud, "automap_mode"):
            from render.hud import tooltip
            tooltip(self.screen, self.fonts, tip[0], tip[1], mouse)
        self.draw_overlays()
        self._perf_mark("hud", t1)
        if getattr(self, "show_perf", False):
            self.draw_perf()
        t1 = time.perf_counter()
        pygame.display.flip()
        self._perf_mark("flip", t1)
        self._perf_frame(t_frame)

    # ------------------------------------------------------------ performance readout (F11)
    PERF_KEYS = ("logic", "prep", "hover", "world", "hud", "flip")

    def _perf_mark(self, key, t_start, minus=()):
        ms = (time.perf_counter() - t_start) * 1000.0
        cur = self.__dict__.setdefault("_perf_cur", {})
        for k in minus:
            ms -= cur.get(k, 0.0)
        cur[key] = cur.get(key, 0.0) + ms

    def _perf_frame(self, t_frame):
        from d2 import dcc
        cur = self.__dict__.setdefault("_perf_cur", {})
        cur["frame"] = (time.perf_counter() - t_frame) * 1000.0
        dec = dcc.STATS["decode_ms"]
        cur["decode"] = dec - getattr(self, "_perf_dec0", 0.0)
        self._perf_dec0 = dec
        avg = self.__dict__.setdefault("_perf_avg", {})
        peak = self.__dict__.setdefault("_perf_peak", {})
        for k, v in cur.items():
            avg[k] = avg.get(k, v) * 0.9 + v * 0.1
            peak[k] = max(v, peak.get(k, 0.0) * 0.995)    # slowly fading worst frame
        self._perf_cur = {}

    def draw_perf(self):
        from d2 import dcc
        avg = getattr(self, "_perf_avg", {})
        peak = getattr(self, "_perf_peak", {})
        fr = avg.get("frame", 16.7)
        lines = ["FPS %.0f   frame %.1f ms (worst %.0f)" % (1000.0 / max(1.0, fr), fr, peak.get("frame", 0)),
                 "  ".join("%s %.1f" % (k, avg.get(k, 0.0)) for k in self.PERF_KEYS),
                 "sprite decoding %.1f ms/frame (worst %.0f), %d animations decoded"
                 % (avg.get("decode", 0.0), peak.get("decode", 0.0), dcc.STATS["decoded"])]
        pr = self.prebuild_progress()
        if pr:
            n, total = pr
            lines.append("background preparation: %d / %d files%s" % (n, total, " - done" if n >= total else ""))
        f = self.fonts["small"]
        imgs = [f.render(t, True, (230, 230, 200)) for t in lines]
        W = self.screen.get_size()[0]
        w = max(i.get_width() for i in imgs) + 12
        h = sum(i.get_height() for i in imgs) + 8
        box = pygame.Surface((w, h), pygame.SRCALPHA)
        box.fill((0, 0, 0, 190))
        x, y = W - w - 8, 64
        self.screen.blit(box, (x, y))
        for img in imgs:
            self.screen.blit(img, (x + 6, y + 4))
            y += img.get_height()

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
                act = self.current_act()
                late = {3: ("mephisto", "Mephisto is dead - Act 3 complete!"),
                        4: ("diablo", "Diablo is dead - Act 4 complete!"),
                        5: ("baal", "Baal is dead - you have saved Sanctuary!")}.get(act)
                if late and q.get(late[0]) in ("cleared", "done"):
                    img = self.fonts["med"].render(late[1], True, GOLD)
                    self.screen.blit(img, (W / 2 - img.get_width() / 2, 84))
                elif self.current_act() == 2 and q.get("tombs") in ("cleared", "done"):
                    img = self.fonts["med"].render("Duriel is dead - Act 2 complete!", True, GOLD)
                    self.screen.blit(img, (W / 2 - img.get_width() / 2, 84))
                elif q.get("andariel") in ("cleared", "done") and self.current_act() == 1:
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


def log_error(text):
    """Everything that goes wrong ends up in errors.log next to the game (send it to me)."""
    try:
        with open(os.path.join(HERE, "errors.log"), "a") as f:
            f.write("---- %s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text.rstrip()))
    except Exception:
        pass


if __name__ == "__main__":
    try:
        Game().run()
    except Exception:
        import traceback
        log_error(traceback.format_exc())
        traceback.print_exc()
        print("\nThe error was also written to errors.log in the game folder.")
        sys.exit(1)
    sys.exit(0)
