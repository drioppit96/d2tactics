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
        self.palette = load_palette(self.src.read("data\\global\\palette\\act1\\pal.dat"))
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

    # ---------------------------------------------------------------- level
    def level_builder(self, seed):
        return build_cave(self.kit, seed)

    def town_builder(self, seed):
        from game.d2level import build_town
        return build_town(self.town_kit, seed)

    # ---------------------------------------------------------------- helpers
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
        sx, sy = cam.to_screen((tx - ty) * 80 - 80 + x0, (tx + ty) * 40 - 8 + y0)
        return pygame.Rect(int(sx), int(sy), img.get_width(), img.get_height())

    def draw_tile(self, surf, ref, tx, ty, cam, alpha=None):
        ts = self.tile_surface(ref)
        if not ts:
            return
        img, x0, y0 = ts
        if alpha is not None:
            key = (id(ref[1]), "a")
            if key not in self.tile_cache:
                faded = img.copy()
                faded.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
                self.tile_cache[key] = faded
            img = self.tile_cache[key]
        sx, sy = cam.to_screen((tx - ty) * 80 - 80 + x0, (tx + ty) * 40 - 8 + y0)
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

    def _sprites_for(self, unit):
        if unit.is_player:
            arms, hide, wclass = self.player_look(unit)
            key = ("player", wclass, hide, tuple(sorted((k, tuple(v)) for k, v in arms.items())))
            if key not in self.sprites:
                self.sprites[key] = UnitSprites(self, "chars", "BA", arms, wclass, hide=hide)
            return self.sprites[key]
        key = (unit.token, unit.unique, getattr(unit, "d2id", None))
        if key not in self.sprites:
            arms = {}
            mid = getattr(unit, "d2id", None) or MONSTER_IDS.get(unit.token, "")
            ms = self.monstats.get((mid or "").lower(), {})
            ms2 = self.monstats2.get((ms.get("monstatsex") or mid or "").lower(), {})
            for comp in ("HD", "TR", "LG", "RA", "LA", "RH", "LH", "SH",
                         "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"):
                v = ms2.get(comp.lower() + "v", "").replace('"', "")
                opts = [x.strip().upper() for x in v.split(",") if x.strip() and x.strip() != "0"]
                if unit.unique and len(opts) > 1:
                    opts = opts[1:] + opts[:1]    # a different look for the boss
                arms[comp] = opts
            self.sprites[key] = UnitSprites(self, "monsters", unit.token, arms, "HTH")
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
                    frames = [(self.indexed_surface(f.width, f.height, f.pixels), f.xoff, f.yoff)
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
        if mode not in ("DD", "DT"):
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
        surf.blit(img, (int(cx + x0), int(cy + y0)))
        return pygame.Rect(int(cx + x0), int(cy + y0), img.get_width(), img.get_height())

    def draw_floor(self, *a, **k):
        return self.placeholder.draw_floor(*a, **k)

    def draw_wall(self, *a, **k):
        return self.placeholder.draw_wall(*a, **k)

    def draw_projectile(self, *a, **k):
        return self.placeholder.draw_projectile(*a, **k)
