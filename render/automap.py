"""D2's automap: every explored floor tile and wall drawn with Diablo II's own automap pieces
(data\\global\\ui\\automap\\maximap.dc6, chosen per tile by Automap.txt: level type, tile kind,
style and sequence - exactly how the game picks them), at D2's scale of 16 x 8 pixels a tile.

Tab cycles: full map over the screen (centred on you, like D2) -> small map in the corner -> off.
Without the D2 files (or for a tile Automap.txt has no piece for) thin lines along the walls are
drawn instead. The map is kept in 512 x 512 chunks, so only what you explored costs memory.
"""
import pygame

from game.grid import WALL

LINE = (210, 200, 175, 235)
EXIT_C = (240, 210, 90)
NPC_C = (90, 170, 255)
WP_C = (120, 160, 255)
TW, TH = 16, 8                  # a D2 floor tile on the automap
HW, HH = TW / 10.0, TH / 10.0   # half a cell (a tile is 5 x 5 cells)
CHUNK = 512
CODES = {0: "fl", 1: "wl", 2: "wr", 3: "wtlr", 4: "wtll", 5: "wtr", 6: "wbl", 7: "wbr", 8: "wld", 9: "wrd",
         10: "wle", 11: "wre", 12: "co", 14: "tr"}
_TABLES = {}


def _automap_table(assets):
    """(level type name, code, style) -> [(start, end, [cels])] from Automap.txt, and the cel pictures."""
    src = getattr(assets, "src", None)
    if src is None:
        return None
    key = id(src)
    if key in _TABLES:
        return _TABLES[key]
    out = None
    try:
        from d2.source import read_table
        from d2.dc6 import DC6
        table = {}
        for r in read_table(src, "Automap"):
            try:
                style = int(r.get("style") or 0)
                a = int(r.get("startsequence") or -1)
                b = int(r.get("endsequence") or -1)
            except ValueError:
                continue
            cels = []
            for k in ("cel1", "cel2", "cel3", "cel4"):
                try:
                    c = int(r.get(k) or -1)
                except ValueError:
                    c = -1
                if c >= 0:
                    cels.append(c)
            if cels:
                table.setdefault((r.get("levelname", ""), r.get("tilename", ""), style), []).append((a, b, cels))
        dc = DC6(src.read("data\\global\\ui\\automap\\maximap.dc6"))
        lvltypes = {}
        for i, r in enumerate(read_table(src, "LvlTypes")):
            try:
                lvltypes[int(r.get("id") or "")] = r.get("name", "")
            except ValueError:
                pass
        # which level types list each DT1 file (a tile's automap piece belongs to its file's type)
        by_file = {}
        for r in read_table(src, "LvlTypes"):
            nm = _amap_name(r.get("name", ""))
            for k, v in r.items():
                if k.startswith("file") and v and v != "0":
                    by_file.setdefault(v.replace("/", "\\").lower(), []).append(nm)
        out = dict(table=table, dc6=dc, lvltypes=lvltypes, surf={}, by_file=by_file)
    except Exception:
        out = None
    _TABLES[key] = out
    return out


def _amap_name(lvltype):
    """'Act 1 - Wilderness' -> '1 Wilderness' (Automap.txt's names); Harrogath is 'Expansion'."""
    if lvltype in ("Act 5 - Town", "Expansion"):
        return "Expansion"
    if not lvltype.startswith("Act "):
        return lvltype
    act, _, rest = lvltype[4:].partition(" - ")
    return "%s %s" % (act.strip(), rest.split(" ")[0])


class Automap:
    def __init__(self, world, assets=None):
        self.world = world
        self.assets = assets
        g = world.grid
        self.ox = g.h * HW + 20
        self.chunks = {}
        self.done_tiles = set()
        self.t = _automap_table(assets) if assets is not None else None
        self.tm = getattr(world, "tilemap", None)
        self._lt_cache = {}
        cells = getattr(g, "explored_cells", None)
        if cells is None:
            cells = [(x, y) for y in range(g.h) for x in range(g.w) if g.explored[y][x]]
        self._add(cells)
        g.new_explored = []

    # ------------------------------------------------------------ geometry
    def to_map(self, x, y):
        return (x - y) * HW + self.ox, (x + y) * HH + 40

    def _chunk(self, key):
        c = self.chunks.get(key)
        if c is None:
            c = self.chunks[key] = pygame.Surface((CHUNK, CHUNK), pygame.SRCALPHA)
            c.fill((0, 0, 0, 0))
        return c

    def _blit(self, img, x, y):
        w, h = img.get_size()
        for kx in range(int(x) // CHUNK, int(x + w) // CHUNK + 1):
            for ky in range(int(y) // CHUNK, int(y + h) // CHUNK + 1):
                self._chunk((kx, ky)).blit(img, (int(x) - kx * CHUNK, int(y) - ky * CHUNK))

    def _line(self, a, b):
        keys = {(int(a[0]) // CHUNK, int(a[1]) // CHUNK), (int(b[0]) // CHUNK, int(b[1]) // CHUNK)}
        for kx, ky in keys:
            surf = self._chunk((kx, ky))
            ox, oy = kx * CHUNK, ky * CHUNK
            pygame.draw.line(surf, LINE, (a[0] - ox, a[1] - oy), (b[0] - ox, b[1] - oy), 1)

    # ------------------------------------------------------------ D2 pieces
    def _cel(self, i):
        t = self.t
        s = t["surf"].get(i)
        if s is None and 0 <= i < len(t["dc6"].frames):
            f = t["dc6"].frames[i]
            pal = getattr(self.assets, "ui_palette", None)
            # D2 draws the automap pieces as light lines over the game: each pixel's brightness
            # (in the act palette) becomes how strongly it shows
            s = pygame.Surface((f.width, f.height), pygame.SRCALPHA)
            s.fill((0, 0, 0, 0))
            for y in range(f.height):
                row = y * f.width
                for x in range(f.width):
                    v = f.pixels[row + x]
                    if v:
                        if pal is not None:
                            c = pal[v]
                            lum = (c[0] * 30 + c[1] * 59 + c[2] * 11) / 100.0
                        else:
                            lum = 128
                        a = int(min(255, 90 + lum * 2.2))
                        s.set_at((x, y), (230, 220, 200, a))
            t["surf"][i] = s
        return s

    def _lvltype(self, tx, ty):
        """Automap.txt's level name for the level a tile belongs to."""
        lid = self.world.area_at((tx * 5 + 2, ty * 5 + 2)) if hasattr(self.world, "area_at") else None
        if lid is None:
            lid = getattr(self.world, "level_id", None)
        if lid in self._lt_cache:
            return self._lt_cache[lid]
        name = ""
        try:
            info = getattr(self.world, "info", None)
            kit = getattr(info, "kit", None)
            look = lid
            sa = info._side(lid) if info is not None and hasattr(info, "_side") else None
            if lid == 76:
                name = "-outline-"           # (the Kurast Armory: hand-laid walls, drawn as outlines)
            else:
                if sa:
                    look = sa["like"]
                row = (kit.levels.get(look) or {}) if kit is not None else {}
                i = int(row.get("leveltype") or 0)
                name = _amap_name(self.t["lvltypes"].get(i, ""))
        except Exception:
            name = ""
        self._lt_cache[lid] = name
        return name

    # towns are built from their act's outdoor tiles too: those pieces come from that list
    ALSO = {"2 Town": ["2 Desert"], "1 Town": ["1 Wilderness"], "4 Town": ["4 Mesa"], "Expansion": ["5 Siege"]}

    def _piece(self, lvl, ref, tx, ty):
        tile = ref[1]
        o, main, sub = tile.key() if hasattr(tile, "key") else (getattr(tile, "orientation", 0), 0, 0)
        code = CODES.get(o)
        if code is None:
            return None
        names = [lvl] + self.ALSO.get(lvl, [])
        fn = (getattr(ref[0], "name", "") or "").lower().replace("/", "\\")
        if "tiles\\" in fn:
            own = self.t["by_file"].get(fn.split("tiles\\", 1)[1], [])
            if own:
                names = ([lvl] if lvl in own else []) + [n for n in own if n != lvl]
        for name in names:
            rows = self.t["table"].get((name, code, main))
            if not rows:
                continue
            for a, b, cels in rows:
                if (a == -1 or sub >= a) and (b == -1 or sub <= b):
                    return cels[(tx * 7 + ty * 13) % len(cels)]
            return None
        return None

    def _known(self, lvl):
        k = self.t.setdefault("known", {})
        if lvl not in k:
            k[lvl] = any(key[0] == lvl for key in self.t["table"])
        return k[lvl]

    def _tile(self, tx, ty):
        """Draw one tile's automap pieces like D2 (plain ground stays blank); False when D2 has no
        automap for this kind of level at all (then the outline is drawn instead)."""
        tm = self.tm
        if self.t is None or tm is None:
            return False
        lvl = self._lvltype(tx, ty)
        if not self._known(lvl):
            return False
        refs = []
        f = tm.floor.get((tx, ty))
        if f:
            refs.append(f)
        refs += [w for w in tm.walls.get((tx, ty), ()) if getattr(w[1], "orientation", 0) in CODES]
        if not refs:
            return True
        X, Y = (tx - ty) * (TW // 2) + self.ox - TW // 2, (tx + ty) * (TH // 2) + 40 - 24
        missed_wall = False
        for ref in refs:
            c = self._piece(lvl, ref, tx, ty)
            if c is not None:
                img = self._cel(c)
                if img is not None:
                    self._blit(img, X, Y)
            elif getattr(ref[1], "orientation", 0) not in (0, 12, 14):
                missed_wall = True
        # a wall D2 has no piece for (Lut Gholein's, the Fortress's...): its outline instead
        return not missed_wall

    def _lines(self, tx, ty):
        g = self.world.grid
        for y in range(ty * 5, ty * 5 + 5):
            for x in range(tx * 5, tx * 5 + 5):
                if not g.in_bounds(x, y) or g.cells[y][x] == WALL or not g.explored[y][x]:
                    continue
                cx, cy = self.to_map(x, y)
                top, right, bottom, left = (cx, cy - HH), (cx + HW, cy), (cx, cy + HH), (cx - HW, cy)
                for (nx, ny), a, b in (((x, y - 1), top, right), ((x + 1, y), right, bottom),
                                       ((x, y + 1), bottom, left), ((x - 1, y), left, top)):
                    if not g.walkable(nx, ny):
                        self._line(a, b)

    def _add(self, cells):
        tiles = {(x // 5, y // 5) for x, y in cells}
        lt = self.__dict__.setdefault("line_tiles", set())
        for t in tiles:
            if t in lt:
                self._lines(*t)              # outlined tiles fill in as more of them is explored
                for n in ((t[0] + 1, t[1]), (t[0] - 1, t[1]), (t[0], t[1] + 1), (t[0], t[1] - 1)):
                    if n in lt:
                        self._lines(*n)
                continue
            if t in self.done_tiles:
                continue
            self.done_tiles.add(t)
            if not self._tile(*t):
                lt.add(t)
                self._lines(*t)

    def update(self):
        g = self.world.grid
        if g.new_explored:
            self._add(g.new_explored)
            g.new_explored = []

    # ------------------------------------------------------------ drawing
    def _blit_region(self, surf, ox, oy, view):
        """Blit the chunks overlapping view (map-space rect) at screen offset (ox, oy)."""
        x0, y0 = int(view.x) // CHUNK, int(view.y) // CHUNK
        x1, y1 = int(view.right) // CHUNK, int(view.bottom) // CHUNK
        for ky in range(y0, y1 + 1):
            for kx in range(x0, x1 + 1):
                c = self.chunks.get((kx, ky))
                if c is not None:
                    surf.blit(c, (int(ox + kx * CHUNK), int(oy + ky * CHUNK)))

    def _markers(self, surf, ox, oy, k, clip):
        w = self.world
        done = set()
        for (x, y), target in w.exits.items():
            if not target or not w.grid.explored[y][x]:
                continue
            key = (x // 8, y // 8)
            if key in done:
                continue
            done.add(key)
            mx, my = self.to_map(x, y)
            p = (int(ox + mx * k), int(oy + my * k))
            if clip.collidepoint(p):
                pygame.draw.circle(surf, EXIT_C, p, max(2, int(2.5 * k)), 1)
        for (x, y) in getattr(w, "waypoints", {}):
            if w.grid.explored[y][x]:
                mx, my = self.to_map(x, y)
                p = (int(ox + mx * k), int(oy + my * k))
                if clip.collidepoint(p):
                    pygame.draw.rect(surf, WP_C, (p[0] - 3, p[1] - 2, 7, 5), 1)
        if getattr(w, "reveal_monsters", False):        # the last few monsters of a "clear it" quest
            for m in w.monsters:
                if m.alive and not m.ally and m.ai != "npc" and not getattr(m, "hidden", False):
                    mx, my = self.to_map(m.x, m.y)
                    p = (int(ox + mx * k), int(oy + my * k))
                    if clip.collidepoint(p):
                        pygame.draw.circle(surf, (255, 40, 40), p, max(2, int(2.5 * k)))
        for m in w.npcs:
            if w.grid.explored[m.y][m.x]:
                mx, my = self.to_map(m.x, m.y)
                p = (int(ox + mx * k), int(oy + my * k))
                if clip.collidepoint(p):
                    pygame.draw.circle(surf, NPC_C, p, max(1, int(1.5 * k)))
        # you: D2's little cross
        mx, my = self.to_map(*w.player.pos)
        px, py = int(ox + mx * k), int(oy + my * k)
        r = max(3, int(4 * k))
        pygame.draw.line(surf, (255, 255, 255), (px - r, py), (px + r, py), 2)
        pygame.draw.line(surf, (255, 255, 255), (px, py - r // 2 - 1), (px, py + r // 2 + 1), 2)

    def draw_full(self, surf, centre, k=1.0):
        self.update()
        mx, my = self.to_map(*self.world.player.pos)
        if k == 1.0:
            ox, oy = centre[0] - mx, centre[1] - my
            W, H = surf.get_size()
            self._blit_region(surf, ox, oy, pygame.Rect(int(-ox), int(-oy), W, H))
            self._markers(surf, ox, oy, 1.0, surf.get_rect())
            return
        W, H = surf.get_size()
        src = pygame.Rect(int(mx - centre[0] / k), int(my - centre[1] / k), int(W / k) + 2, int(H / k) + 2)
        part = pygame.Surface(src.size, pygame.SRCALPHA)
        part.fill((0, 0, 0, 0))
        self._blit_region(part, -src.x, -src.y, src)
        surf.blit(pygame.transform.scale(part, (int(src.w * k), int(src.h * k))), (0, 0))
        self._markers(surf, -src.x * k, -src.y * k, k, surf.get_rect())

    def draw_mini(self, surf, rect, k=1.0):
        self.update()
        mx, my = self.to_map(*self.world.player.pos)
        src = pygame.Rect(int(mx - rect.w / k / 2), int(my - rect.h / k / 2), int(rect.w / k), int(rect.h / k))
        part = pygame.Surface(src.size, pygame.SRCALPHA)
        part.fill((0, 0, 0, 0))
        self._blit_region(part, -src.x, -src.y, src)
        small = part if k == 1.0 else pygame.transform.scale(part, rect.size)
        bg = pygame.Surface(rect.size, pygame.SRCALPHA)
        bg.fill((0, 0, 0, 110))
        surf.blit(bg, rect.topleft)
        surf.blit(small, rect.topleft)
        old = surf.get_clip()
        surf.set_clip(rect)
        self._markers(surf, rect.x - src.x * k, rect.y - src.y * k, k, rect)
        surf.set_clip(old)
