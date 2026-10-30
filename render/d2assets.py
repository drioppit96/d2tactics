"""Diablo 2 asset provider: real tiles and unit animations from your own install.

Nothing from the game is stored in this project: everything is read from the MPQs
(or an extracted-files folder) each time the game starts.
"""
import math

import pygame

from d2.cof import COF
from d2.dcc import DCC
from d2.palette import load_palette
from d2.source import open_source, read_table
from game.d2level import CaveKit, build_cave
from .assets import AssetProvider, PlaceholderAssets

# D2 sprite direction index for each screen direction, clockwise from south (every 22.5 deg)
_DIR16 = [4, 8, 0, 9, 5, 10, 1, 11, 6, 12, 2, 13, 7, 14, 3, 15]
# D2's 32-direction order (every second entry is the 16-direction order)
_DIR32 = [4, 16, 8, 17, 0, 18, 9, 19, 5, 20, 10, 21, 1, 22, 11, 23, 6, 24, 12, 25, 2, 26, 13, 27, 7, 28, 14, 29,
          3, 30, 15, 31]


def screen_direction(dx, dy, n_dirs):
    """Sprite direction for a screen-space vector (dx right, dy down)."""
    if n_dirs <= 1:
        return 0
    ang = math.degrees(math.atan2(dy, dx))              # 90 = straight down (south)
    if n_dirs >= 32:
        return _DIR32[int(round((ang - 90) / 11.25)) % 32] % n_dirs
    pos = int(round((ang - 90) / 22.5)) % 16
    if n_dirs == 16:
        return _DIR16[pos]
    if n_dirs == 8:
        return _DIR16[(pos // 2) * 2] % 8
    if n_dirs == 4:
        return [0, 1, 2, 3][((pos + 2) // 4) % 4]
    return 0


class DccAnim:
    """A one-layer DCC (missile / overlay): frames decoded per direction on first use."""

    def __init__(self, assets, dcc, trans=False, fps=25.0):
        self.a, self.dcc, self.trans, self.fps = assets, dcc, trans, fps
        self.cache = {}
        self.n_dirs = dcc.n_dirs
        self.length = dcc.frames_per_dir

    def frames(self, d):
        d = max(0, min(self.n_dirs - 1, d))
        if d not in self.cache:
            out = []
            for fr in self.dcc.direction(d).frames:
                if not fr.width or not fr.height:
                    out.append((None, 0, 0))
                    continue
                img = self.a.indexed_surface(fr.width, fr.height, fr.pixels)
                out.append((img, fr.xmin, fr.ymin))
            self.cache[d] = out
        return self.cache[d]

    def duration(self):
        return self.length / self.fps

# our animation names -> D2 mode codes to try, in order
MODE_MAP = {
    "NU": ["NU"], "WL": ["WL"], "A1": ["A1"], "SC": ["SC", "A2", "A1"],
    "GH": ["GH", "NU"], "DD": ["DT"], "DT": ["DD", "DT"],
}

MONSTER_IDS = {"ZM": "zombie1", "FA": "fallen1", "FS": "fallenshaman1", "SI": "quillrat1", "SK": "skeleton1"}


def d2_direction(facing, n_dirs):
    """Grid facing (dx, dy) -> sprite direction index for a COF with 8 or 16 directions."""
    fx, fy = facing
    sx, sy = fx - fy, fx + fy            # screen vector with the iso squash undone
    if sx == 0 and sy == 0:
        sy = 1
    ang = math.degrees(math.atan2(sy, sx))   # 90 = south, 180 = west ...
    pos = int(round((ang - 90) / 22.5)) % 16
    if n_dirs == 16:
        return _DIR16[pos]
    if n_dirs == 8:
        return _DIR16[(pos // 2) * 2]
    return 0


class UnitSprites:
    """All animations of one unit look (token + chosen armour/weapon types)."""

    def __init__(self, assets, folder, token, arms, weapon_class="HTH", hide=()):
        self.a = assets
        self.hide = set(hide)
        self.folder = folder
        self.token = token.upper()
        self.arms = arms            # component -> preferred armtype list
        self.wclass = weapon_class
        self.cache = {}             # (mode, dir) -> [(surface, x0, y0)]
        self.cofs = {}
        self.dccs = {}

    def _cof(self, mode):
        """First weapon class whose COF exists and whose torso graphics exist too."""
        for wc in (self.wclass, "HTH"):
            key = (mode, wc)
            if key not in self.cofs:
                name = "data\\global\\%s\\%s\\COF\\%s%s%s.cof" % (self.folder, self.token, self.token, mode, wc)
                cof = COF(self.a.src.read(name)) if self.a.src.has(name) else None
                if cof:
                    comps = [L for L in cof.layers if L.component not in self.hide]
                    main = [L for L in comps if L.component == "TR"] or comps[:1]
                    if not main or not self._dcc(main[0].component, mode, main[0].weapon_class or wc):
                        cof = None
                self.cofs[key] = (cof, wc) if cof else None
            if self.cofs[key]:
                return self.cofs[key]
        return None

    def _dcc(self, comp, mode, wc):
        key = (comp, mode, wc)
        if key in self.dccs:
            return self.dccs[key]
        found = None
        for arm in self.arms.get(comp, []) + ["LIT", "MED", "HVY"]:
            name = "data\\global\\%s\\%s\\%s\\%s%s%s%s%s.dcc" % (
                self.folder, self.token, comp, self.token, comp, arm.upper(), mode, wc)
            if self.a.src.has(name):
                try:
                    found = DCC(self.a.src.read(name))
                except Exception:
                    found = None
                break
        self.dccs[key] = found
        return found

    def frames(self, our_mode, facing):
        for mode in MODE_MAP.get(our_mode, [our_mode]):
            res = self._cof(mode)
            if not res:
                continue
            cof, wc = res
            d = d2_direction(facing, cof.n_dirs)
            key = (mode, d)
            if key not in self.cache:
                self.cache[key] = self._build(cof, mode, wc, d)
            return self.cache[key]
        return None

    def _build(self, cof, mode, wc, d):
        layers = {}
        for L in cof.layers:
            if L.component in self.hide:
                continue        # e.g. no shield equipped
            dcc = self._dcc(L.component, mode, L.weapon_class or wc)
            if dcc:
                layers[L.component] = (dcc, L)
        out = []
        for f in range(cof.frames):
            parts = []
            for comp in cof.priority[d][f]:
                if comp in layers:
                    dcc, L = layers[comp]
                    dd = d * dcc.n_dirs // cof.n_dirs if dcc.n_dirs != cof.n_dirs else d
                    fr = dcc.direction(dd).frames[f % dcc.frames_per_dir]
                    if fr.width and fr.height:
                        parts.append((fr, L))
            if not parts:
                out.append((None, 0, 0))
                continue
            x0 = min(p.xmin for p, _ in parts)
            y0 = min(p.ymin for p, _ in parts)
            x1 = max(p.xmax for p, _ in parts)
            y1 = max(p.ymax for p, _ in parts)
            comp_surf = pygame.Surface((x1 - x0 + 1, y1 - y0 + 1), pygame.SRCALPHA)
            for fr, L in parts:
                img = self.a.indexed_surface(fr.width, fr.height, fr.pixels)
                if L.transparent:
                    img.set_alpha(150)
                comp_surf.blit(img, (fr.xmin - x0, fr.ymin - y0))
            out.append((comp_surf, x0, y0))
        return out


class D2Assets(AssetProvider):
    name = "diablo2"
    native_scale = 1.5     # D2 art is drawn for 800x600; 1.5x zoom gives a similar view
    bar_lift = 34          # D2 monsters are taller than the placeholder figures

    def __init__(self, d2_path, difficulty="normal", progress=None):
        say = progress or (lambda msg: None)
        import os
        cache = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache", "mpq")
        self.src = open_source(d2_path, say, cache)
        from d2 import spritecache
        spritecache.configure(os.path.join(os.path.dirname(cache), "sprites"))
        self.cache_root = os.path.dirname(cache)
        self.d2_path = d2_path
        self.palette = load_palette(self.src.read("data\\global\\palette\\act1\\pal.dat"))
        self.ui_palette = self.palette          # the interface and item pictures always use Act 1's
        self.act = 1
        say("Reading cave tiles")
        self.kit = CaveKit(self.src)
        say("Reading the Rogue Encampment")
        from game.d2level import TownKit
        try:
            self.town_kit = TownKit(self.src)
        except Exception:
            self.town_kit = None
        self.placeholder = PlaceholderAssets()
        self.tile_cache = {}
        self.sprites = {}
        self.flash_cache = {}
        self.item_cache = {}
        try:
            self.monstats = {r.get("id", "").lower(): r for r in read_table(self.src, "MonStats")}
            self.monstats2 = {r.get("id", "").lower(): r for r in read_table(self.src, "MonStats2")}
        except Exception:
            self.monstats, self.monstats2 = {}, {}
        from game.d2content import D2Content
        say("Reading items and monsters")
        self.content = D2Content(self.src, difficulty)
        say("Reading the Act 1 layouts")
        self.act_kit = self.act_info = None
        try:
            from game.act1 import OutdoorKit
            from game.actworld import ActInfo
            self.act_kit = OutdoorKit(self.src, read_table(self.src, "Levels"), read_table(self.src, "LvlTypes"))
            self.act_info = ActInfo(self.act_kit, self.content)
        except Exception:
            import traceback
            traceback.print_exc()

    # ---------------------------------------------------------------- level
    def level_builder(self, seed):
        return build_cave(self.kit, seed)

    def town_builder(self, seed):
        from game.d2level import build_town
        return build_town(self.town_kit, seed)

    # ---------------------------------------------------------------- helpers
    def set_act(self, act):
        """Each act's terrain, monsters and missiles are drawn with that act's palette (Lut Gholein's
        sand isn't Act 1's grass colours). Switching drops the pictures made with the old one."""
        if act == self.act:
            return
        path = "data\\global\\palette\\act%d\\pal.dat" % act
        if not self.src.has(path):
            return
        self.act = act
        self.palette = load_palette(self.src.read(path))
        self.tile_cache.clear()
        self.sprites.clear()
        self.flash_cache.clear()
        self.__dict__.pop("_tint_cache", None)
        for k in [k for k in self.item_cache if isinstance(k, tuple) and k and k[0] in ("mis", "ovl")]:
            del self.item_cache[k]
        self.__dict__.pop("_warm_seen", None)
        self.__dict__.pop("_warm_q", None)

    def indexed_surface_ui(self, w, h, pixels):
        s = pygame.image.frombuffer(bytes(pixels), (w, h), "P")
        s.set_palette(self.ui_palette)
        s.set_colorkey(0)
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        out.fill((0, 0, 0, 0))
        out.blit(s, (0, 0))
        return out

    def indexed_surface(self, w, h, pixels):
        s = pygame.image.frombuffer(bytes(pixels), (w, h), "P")
        s.set_palette(self.palette)
        s.set_colorkey(0)
        out = pygame.Surface((w, h), pygame.SRCALPHA)   # index 0 -> fully transparent
        out.fill((0, 0, 0, 0))
        out.blit(s, (0, 0))
        return out

    def tile_surface(self, ref):
        f, t = ref
        key = id(t)
        if key not in self.tile_cache:
            w, h, px, x0, y0 = f.decode(t)
            self.tile_cache[key] = (self.indexed_surface(w, h, px), x0, y0) if w else None
        return self.tile_cache[key]

    def tile_rect(self, ref, tx, ty, cam):
        ts = self.tile_surface(ref)
        if not ts:
            return None
        img, x0, y0 = ts
        sx, sy = cam.to_screen((tx - ty) * 80 - 80 + x0, (tx + ty) * 40 - 8 + y0 - self._roof_lift(ref))
        return pygame.Rect(int(sx), int(sy), img.get_width(), img.get_height())

    lift_roofs = True      # kept for the scene; roofs are lifted everywhere, like D2

    @staticmethod
    def _roof_lift(ref):
        """How far up a tile is drawn from its floor anchor (D2's YAdjust):
        roofs (orientation 15) sit RoofHeight pixels up; walls hang from the bottom corner of
        their floor diamond, so their block y = 0 is 80 pixels below the anchor."""
        t = ref[1]
        o = getattr(t, "orientation", 0)
        if o == 15:
            return getattr(t, "roof_y", 0)
        if o in (0, 13):
            return 0
        return -80

    def draw_tile(self, surf, ref, tx, ty, cam, alpha=None, lit=False):
        ts = self.tile_surface(ref)
        if not ts:
            return
        img, x0, y0 = ts
        if lit:
            key = (id(ref[1]), "lit")
            if key not in self.tile_cache:
                bright = img.copy()
                try:
                    bright.fill((55, 50, 40), special_flags=pygame.BLEND_RGB_ADD)
                except Exception:
                    pass
                self.tile_cache[key] = bright
            img = self.tile_cache[key]
        if alpha is not None:
            key = (id(ref[1]), "a")
            if key not in self.tile_cache:
                faded = img.copy()
                faded.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
                self.tile_cache[key] = faded
            img = self.tile_cache[key]
        sx, sy = cam.to_screen((tx - ty) * 80 - 80 + x0, (tx + ty) * 40 - 8 + y0 - self._roof_lift(ref))
        surf.blit(img, (int(sx), int(sy)))

    def player_look(self, p):
        """Barbarian armour/weapon graphics from what is equipped (D2's component system)."""
        eq = p.equipment
        tiers = ["LIT", "MED", "HVY"]
        arms = {c: ["LIT"] for c in ("HD", "TR", "LG", "RA", "LA", "S1", "S2")}
        hide = {"LH", "SH", "RH"}
        wclass = "HTH"
        helm, armor, weapon, shield = eq.get("helm"), eq.get("armor"), eq.get("weapon"), eq.get("shield")
        if helm and helm.gfx:
            arms["HD"] = [helm.gfx, "LIT"]
        if armor and armor.look:
            lk = armor.look
            arms["TR"] = [tiers[min(2, lk.get("torso", 0))]]
            arms["LG"] = [tiers[min(2, lk.get("legs", 0))]]
            arms["RA"] = [tiers[min(2, lk.get("rarm", 0))]]
            arms["LA"] = [tiers[min(2, lk.get("larm", 0))]]
            arms["S1"] = [tiers[min(2, lk.get("rspad", 0))]]
            arms["S2"] = [tiers[min(2, lk.get("lspad", 0))]]
        if weapon and weapon.gfx:
            wclass = (weapon.wclass or "1hs").upper()
            if wclass in ("BOW", "XBW"):
                arms["LH"] = [weapon.gfx]
                hide.discard("LH")
            else:
                arms["RH"] = [weapon.gfx]
                hide.discard("RH")
        if shield and shield.gfx:
            arms["SH"] = [shield.gfx]
            hide.discard("SH")
        return arms, tuple(sorted(hide)), wclass

    def warm(self, unit, progress=None):
        """Decode a unit's common animations up front (loading screen) instead of mid-game."""
        sprites = self._sprites_for(unit)
        facings = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
        for mode in ("NU", "WL", "A1", "GH"):
            if progress:
                progress("Preparing animations (%s)" % {"NU": "standing", "WL": "walking", "A1": "attacking",
                                                         "GH": "getting hit"}[mode])
            for f in facings:
                try:
                    sprites.frames(mode, f)
                except Exception:
                    pass

    SHAPES = {"wolf": ("40", "wolf", "Wearwolf"), "bear": ("TG", "bear", "Wearbear")}

    def _shape_sprites(self, unit):
        """Druid Werewolf / Werebear: D2's wolf (40) and bear (TG) graphics while the form lasts."""
        sh = self.SHAPES.get(getattr(unit, "shape", None) or "")
        if not sh or sh[2] not in (getattr(unit, "buffs", None) or {}):
            return None
        token, mid, _ = sh
        key = ("shape", token)
        if key not in self.sprites:
            self.sprites[key] = self._monster_sprites(token, mid, False)
        return self.sprites[key]

    def _monster_sprites(self, token, mid, unique):
        arms = {}
        ms = self.monstats.get((mid or "").lower(), {})
        ms2 = self.monstats2.get((ms.get("monstatsex") or mid or "").lower(), {})
        for comp in ("HD", "TR", "LG", "RA", "LA", "RH", "LH", "SH",
                     "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"):
            v = ms2.get(comp.lower() + "v", "").replace('"', "")
            opts = [x.strip().upper() for x in v.split(",") if x.strip() and x.strip() != "0"]
            if unique and len(opts) > 1:
                opts = opts[1:] + opts[:1]    # a different look for the boss
            arms[comp] = opts
        # MonStats2 BaseW: Moon Clan use 2hs, Dark Hunters 1hs, archers bow (their bow is a layer
        # of the bow COFs) - with HTH they only had death animations
        wc = (ms2.get("basew") or "hth").replace('"', "").strip().upper() or "HTH"
        return UnitSprites(self, "monsters", token, arms, wc)

    def _sprites_for_human(self, unit):
        arms, hide, wclass = self.player_look(unit)
        key = ("player", getattr(unit, "token", "BA"), wclass, hide, tuple(sorted((k, tuple(v)) for k, v in arms.items())))
        if key not in self.sprites:
            self.sprites[key] = UnitSprites(self, "chars", getattr(unit, "token", "BA") or "BA", arms, wclass, hide=hide)
        return self.sprites[key]

    def _sprites_for(self, unit):
        if unit.is_player:
            shp = self._shape_sprites(unit)
            if shp is not None:
                return shp
            arms, hide, wclass = self.player_look(unit)
            key = ("player", getattr(unit, "token", "BA"), wclass, hide, tuple(sorted((k, tuple(v)) for k, v in arms.items())))
            if key not in self.sprites:
                self.sprites[key] = UnitSprites(self, "chars", getattr(unit, "token", "BA") or "BA", arms, wclass, hide=hide)
            return self.sprites[key]
        key = (unit.token, unit.unique, getattr(unit, "d2id", None))
        if key not in self.sprites:
            mid = getattr(unit, "d2id", None) or MONSTER_IDS.get(unit.token, "")
            self.sprites[key] = self._monster_sprites(unit.token, mid, unit.unique)
        return self.sprites[key]

    # ---------------------------------------------------------------- items
    def _dc6(self, name):
        key = ("dc6", name.lower())
        if key not in self.item_cache:
            path = "data\\global\\items\\%s.dc6" % name
            frames = None
            if name and self.src.has(path):
                try:
                    from d2.dc6 import DC6
                    dc = DC6(self.src.read(path))
                    frames = [(self.indexed_surface_ui(f.width, f.height, f.pixels), f.xoff, f.yoff)
                              for f in dc.frames if f.width and f.height]
                except Exception:
                    frames = None
            self.item_cache[key] = frames
        return self.item_cache[key]

    def _inv_name(self, item):
        if item.kind == "gold":
            n = item.amount
            return "invgld1" if n < 30 else "invgld2" if n < 100 else "invgld3" if n < 500 else "invgld4"
        return item.invfile

    def draw_item_icon(self, surf, item, rect):
        frames = self._dc6(self._inv_name(item)) if getattr(item, "invfile", "") or item.kind == "gold" else None
        if not frames:
            return self.placeholder.draw_item_icon(surf, item, rect)
        img = frames[0][0]
        key = ("fit", id(img), rect.w, rect.h)
        if key not in self.item_cache:
            w, h = img.get_size()
            k = min(rect.w / float(w), rect.h / float(h), 1.0 if max(w, h) <= 30 else 2.0)
            self.item_cache[key] = pygame.transform.smoothscale(img, (max(1, int(w * k)), max(1, int(h * k)))) \
                if abs(k - 1.0) > 0.01 else img
        fit = self.item_cache[key]
        surf.blit(fit, (rect.centerx - fit.get_width() // 2, rect.centery - fit.get_height() // 2))

    def draw_ground_item(self, surf, item, pos, s, b, t=10.0):
        frames = self._dc6(item.flippy) if getattr(item, "flippy", "") else None
        if not frames:
            return self.placeholder.draw_ground_item(surf, item, pos, s, b)
        i = min(len(frames) - 1, int(t * 25))       # D2 plays the drop "flip" at 25 fps
        img, xo, yo = frames[i]
        surf.blit(img, (int(pos[0] + xo), int(pos[1] + yo)))

    # ---------------------------------------------------------------- AssetProvider
    def draw_unit(self, surf, unit, pose, pos, s, b):
        sprites = self._sprites_for(unit)
        mode = pose["mode"]
        frames = sprites.frames(mode, pose.get("facing", unit.facing))
        if not frames and unit.is_player and getattr(unit, "shape", None):
            # an animation the wolf / bear doesn't have (dying, ...): the druid's own one
            frames = self._sprites_for_human(unit).frames(mode, pose.get("facing", unit.facing))
        if not frames:
            return self.placeholder.draw_unit(surf, unit, pose, pos, s, b)
        n = len(frames)
        phase = pose.get("phase", 0.0)
        if mode == "NU":
            i = int(phase * 10) % n
        elif mode == "WL":
            i = int(phase * 9) % n
        elif mode == "DT":
            i = n - 1
        else:
            i = min(n - 1, int(phase * n))
        img, x0, y0 = frames[i]
        if img is None:
            return
        cx, cy = pos
        if mode not in ("DD", "DT") and not pose.get("no_shadow"):
            sh = self.placeholder._shadow(1, 16 if unit.token != "SI" else 20)
            surf.blit(sh, (cx - sh.get_width() / 2, cy - sh.get_height() / 2))
        if unit.unique and mode not in ("DD", "DT"):
            glow = pygame.Surface((70, 30), pygame.SRCALPHA)
            pygame.draw.ellipse(glow, (255, 220, 120, 55), glow.get_rect())
            surf.blit(glow, (cx - 35, cy - 15))
        flash = pose.get("flash", 0)
        if flash > 0.05:
            k = (id(img), int(flash * 4))
            if k not in self.flash_cache:
                if len(self.flash_cache) > 64:
                    self.flash_cache.clear()
                f = img.copy()
                v = int(140 * (int(flash * 4) / 4))
                f.fill((v, v, v, 0), special_flags=pygame.BLEND_RGBA_ADD)
                self.flash_cache[k] = f
            img = self.flash_cache[k]
        tint = pose.get("tint")
        outline = pose.get("outline")
        if tint or outline:
            tc = self.__dict__.setdefault("_tint_cache", {})
            if len(tc) > 400:
                tc.clear()
            if outline:
                k = ("sil", id(img), outline)
                sil = tc.get(k)
                if sil is None:
                    sil = img.copy()
                    sil.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
                    sil.fill(tuple(outline[:3]) + (0,), special_flags=pygame.BLEND_RGBA_ADD)
                    tc[k] = sil
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    surf.blit(sil, (int(cx + x0 + dx), int(cy + y0 + dy)))
            if tint:
                k = ("tint", id(img), tint)
                t_img = tc.get(k)
                if t_img is None:
                    t_img = img.copy()
                    t_img.fill(tint, special_flags=pygame.BLEND_RGBA_MULT)
                    tc[k] = t_img
                img = t_img
        surf.blit(img, (int(cx + x0), int(cy + y0)))
        return pygame.Rect(int(cx + x0), int(cy + y0), img.get_width(), img.get_height())

    OBJECT_TOKENS = {"cairn": ["S1", "S2", "S3", "S4", "S5"], "inifuss": ["IT"], "tome": ["TT"], "malus": ["HM"],
                     "cage": ["GI"], "waypoint": ["WN", "WP", "W7"], "portal": ["PP", "TP"], "tp": ["TP"], "tp_back": ["TP"],
                     "arcane_portal": ["AY", "PP"], "duriel_portal": ["PP"], "orifice": ["HA"],
                     "cube_chest": ["XK"], "staff_chest": ["XK"], "scroll_chest": ["XK"], "viper_altar": ["ZA"],
                     "journal": ["TT"], "wirt": ["BP"],
                     "eye_chest": ["XK"], "brain_chest": ["XK"], "heart_chest": ["XK"], "gidbinn": ["GA"],
                     "lamtome": ["AB"], "orb": ["55"], "hellforge": ["UX"], "prison": ["GI"], "anya": ["2N"]}
    USED_ON = ("waypoint", "cage", "inifuss", "cube_chest", "staff_chest", "scroll_chest", "viper_altar",
               "orifice", "journal", "eye_chest", "brain_chest", "heart_chest", "gidbinn", "lamtome", "orb",
               "hellforge", "prison")

    def _obj_frames(self, tok, mode):
        key = ("obj", tok)
        sp = self.sprites.get(key)
        if sp is None:
            sp = self.sprites[key] = UnitSprites(self, "objects", tok, {}, "HTH")
        try:
            fr = sp.frames(mode, (0, 1))
        except Exception:
            fr = None
        return [f for f in fr if f[0] is not None] if fr else None

    def draw_gen_object(self, surf, o, pos, s, clock=0.0):
        """Chests, barrels, shrines, doors, torches...: neutral, operating (played once) and opened."""
        tok = o["token"]
        mode = o.get("mode", "NU")
        fr, idx = None, 0
        if mode == "NU":
            fr = self._obj_frames(tok, "NU")
            if fr and o.get("cycle"):
                idx = int(clock * 12) % len(fr)
        else:
            op = self._obj_frames(tok, "OP")
            t = clock - o["op_t"] if o.get("op_t") is not None else 1e9
            if op and t * 15 < len(op):
                fr, idx = op, int(t * 15)
            else:
                on = self._obj_frames(tok, "ON")
                if on:
                    fr, idx = on, (int(clock * 12) % len(on) if len(on) > 1 else 0)
                elif op:
                    fr, idx = op, len(op) - 1
                else:
                    fr = self._obj_frames(tok, "NU")
        if not fr:
            return
        img, x0, y0 = fr[idx % len(fr)]
        surf.blit(img, (int(pos[0] + x0), int(pos[1] + y0)))
        return pygame.Rect(int(pos[0] + x0), int(pos[1] + y0), img.get_width(), img.get_height())

    def draw_object(self, surf, kind, oid, pos, s, clock=0.0, used=False):
        """Quest objects and waypoints with D2's object graphics (placeholder marker if missing)."""
        toks = self.OBJECT_TOKENS.get(kind, [])
        if kind == "waypoint":
            from game.acts import WAYPOINT_TOKEN
            if oid in WAYPOINT_TOKEN:
                toks = [WAYPOINT_TOKEN[oid]] + [t for t in toks if t != WAYPOINT_TOKEN[oid]]
        if kind == "cairn" and isinstance(oid, int) and 7 <= oid <= 11:
            toks = [toks[oid - 7]]
        mode = "ON" if used and kind in self.USED_ON else "NU"
        for tok in toks:
            key = ("obj", tok)
            sp = self.sprites.get(key)
            if sp is None:
                sp = self.sprites[key] = UnitSprites(self, "objects", tok, {}, "HTH")
            frames = None
            for m in ((mode, "NU") if mode != "NU" else ("NU",)):
                try:
                    frames = sp.frames(m, (0, 1))
                except Exception:
                    frames = None
                if frames:
                    break
            if frames:
                img, x0, y0 = frames[int(clock * 12) % len(frames)]
                if img is not None:
                    surf.blit(img, (int(pos[0] + x0), int(pos[1] + y0)))
                    return
        # placeholder: a glowing marker
        col = {"waypoint": (90, 140, 255), "portal": (255, 60, 40), "cairn": (200, 200, 220), "tp": (80, 120, 255),
               "tp_back": (80, 120, 255)}.get(kind, (230, 200, 90))
        pulse = 0.6 + 0.4 * abs(((clock * 1.5) % 2) - 1)
        w, h = int(30 * s), int(15 * s)
        g = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.ellipse(g, col + (int(120 * pulse),), g.get_rect())
        pygame.draw.ellipse(g, col + (220,), g.get_rect(), 2)
        surf.blit(g, (int(pos[0] - w / 2), int(pos[1] - h / 2)))
        if kind in ("tp", "tp_back", "portal"):
            pw, ph = int(26 * s), int(54 * s)
            gate = pygame.Surface((pw, ph), pygame.SRCALPHA)
            pygame.draw.ellipse(gate, col + (int(110 * pulse),), gate.get_rect())
            pygame.draw.ellipse(gate, (230, 240, 255, 200), gate.get_rect(), 2)
            surf.blit(gate, (int(pos[0] - pw / 2), int(pos[1] - ph + 4)), special_flags=pygame.BLEND_RGBA_ADD)
        if kind in ("cairn", "tome", "inifuss", "cage", "malus"):
            pygame.draw.rect(surf, col, (int(pos[0] - 4 * s), int(pos[1] - 26 * s), int(8 * s), int(24 * s)))

    # ---------------------------------------------------------------- missiles and overlays
    def _missile_rows(self):
        if not hasattr(self, "_mrows"):
            try:
                self._mrows = {r.get("missile", "").lower(): r for r in read_table(self.src, "Missiles")}
            except Exception:
                self._mrows = {}
        return self._mrows

    def missile_anim(self, name, depth=0):
        """The graphic of a Missiles.txt entry (follows sub-missiles when it has none itself)."""
        if not name:
            return None
        key = ("mis", name.lower())
        if key in self.item_cache:
            return self.item_cache[key]
        anim = None
        r = self._missile_rows().get(name.lower())
        if r is not None:
            cel = r.get("celfile", "")
            if cel and cel.lower() != "null":
                for ext in (".dcc", ".DCC"):
                    path = "data\\global\\missiles\\%s%s" % (cel, ext)
                    if self.src.has(path):
                        try:
                            speed = int(r.get("animspeed") or 16)
                        except ValueError:
                            speed = 16
                        anim = DccAnim(self, DCC(self.src.read(path)), trans=r.get("trans") not in ("", "0"),
                                       fps=max(8.0, 25.0 * speed / 16.0))
                        break
            if anim is None and depth < 3:
                for col in ("cltsubmissile1", "submissile1", "clthitsubmissile1", "hitsubmissile1"):
                    if r.get(col):
                        anim = self.missile_anim(r[col], depth + 1)
                        if anim:
                            break
        self.item_cache[key] = anim
        return anim

    # ---------------------------------------------------------------- warming up animations
    def warm_missile(self, name, overlay=False):
        """Queue a missile / overlay animation to be decoded a little at a time in spare frame time
        (decoding a 32-direction missile in one go makes the game stutter on the first cast)."""
        if not name:
            return
        q = self.__dict__.setdefault("_warm_q", [])
        seen = self.__dict__.setdefault("_warm_seen", set())
        key = (name.lower(), overlay)
        if key in seen:
            return
        seen.add(key)
        anim = self.overlay_anim(name) if overlay else self.missile_anim(name)
        if anim is None:
            return
        # the most used directions first: the 8 main ones, then the rest
        n = anim.n_dirs
        order = sorted(range(n), key=lambda d: (d % max(1, n // 8) != 0, d))
        q.extend((anim, d) for d in order)
        if not overlay:
            self.warm_missile(self.missile_explosion(name))

    def pump(self, budget=0.006):
        """Decode queued animation directions until `budget` seconds are used."""
        q = self.__dict__.get("_warm_q")
        if not q:
            return
        import time
        t0 = time.time()
        while q and time.time() - t0 < budget:
            anim, d = q.pop(0)
            try:
                anim.frames(d)
            except Exception:
                pass

    def missile_explosion(self, name):
        r = self._missile_rows().get((name or "").lower())
        return (r or {}).get("explosionmissile", "") or None

    def draw_missile(self, surf, name, pos, vec, t, loop=True):
        anim = self.missile_anim(name)
        if anim is None:
            return False
        d = screen_direction(vec[0], vec[1], anim.n_dirs)
        frames = anim.frames(d)
        if not frames:
            return False
        i = int(t * anim.fps)
        i = i % len(frames) if loop else min(len(frames) - 1, i)
        img, x0, y0 = frames[i]
        if img is not None:
            surf.blit(img, (int(pos[0] + x0), int(pos[1] + y0)),
                      special_flags=pygame.BLEND_RGB_ADD if anim.trans else 0)
        return True

    def _overlay_rows(self):
        if not hasattr(self, "_orows"):
            try:
                self._orows = {r.get("overlay", "").lower(): r for r in read_table(self.src, "Overlay")}
                self._srows = {r.get("state", "").lower(): r for r in read_table(self.src, "States")}
            except Exception:
                self._orows, self._srows = {}, {}
        return self._orows

    def overlay_anim(self, name):
        if not name:
            return None
        key = ("ovl", name.lower())
        if key in self.item_cache:
            return self.item_cache[key]
        anim = None
        r = self._overlay_rows().get(name.lower())
        if r is not None and r.get("filename", "null").lower() != "null":
            for path in ("data\\global\\overlays\\%s.dcc" % r["filename"],
                         "data\\global\\overlays\\Expansion\\%s.dcc" % r["filename"]):
                if self.src.has(path):
                    try:
                        rate = int(r.get("animrate") or 1024)
                    except ValueError:
                        rate = 1024
                    anim = DccAnim(self, DCC(self.src.read(path)), trans=r.get("trans") not in ("", "0"),
                                   fps=max(8.0, 25.0 * rate / 1024.0))
                    try:
                        anim.yoff = -int(r.get("yoffset") or 0)
                        anim.xoff = int(r.get("xoffset") or 0)
                    except ValueError:
                        anim.xoff = anim.yoff = 0
                    break
        self.item_cache[key] = anim
        return anim

    def state_overlays(self, state):
        self._overlay_rows()
        r = getattr(self, "_srows", {}).get((state or "").lower())
        if not r:
            return []
        return [r[k] for k in ("overlay1", "overlay2", "overlay3", "overlay4") if r.get(k)]

    def draw_overlay(self, surf, name, pos, t, loop=False):
        """-> False once a one-shot overlay has finished (or there is no graphic)."""
        anim = self.overlay_anim(name)
        if anim is None:
            return False
        frames = anim.frames(0)
        if not frames:
            return False
        i = int(t * anim.fps)
        if not loop and i >= len(frames):
            return False
        img, x0, y0 = frames[i % len(frames)]
        if img is not None:
            surf.blit(img, (int(pos[0] + x0 + getattr(anim, "xoff", 0)), int(pos[1] + y0 + getattr(anim, "yoff", 0))),
                      special_flags=pygame.BLEND_RGB_ADD if anim.trans else 0)
        return True

    def draw_floor(self, *a, **k):
        return self.placeholder.draw_floor(*a, **k)

    def draw_wall(self, *a, **k):
        return self.placeholder.draw_wall(*a, **k)

    def draw_projectile(self, *a, **k):
        return self.placeholder.draw_projectile(*a, **k)
