"""DT1 tile libraries (floors, walls, roofs, shadows).

A floor tile is a 160x80 diamond made of 25 small 32x15 isometric blocks; walls are
taller images made of 32x32 RLE blocks. Each decoded tile is an 8-bit image (palette
indices, 0 = transparent) plus the offset of its top-left corner relative to the
tile's anchor (the top corner of the floor diamond's bounding box).
"""
import struct

FLOOR = 0
ROOF = 15
SHADOW = 13

# isometric block row layout (15 rows): x start and pixel count
_ISO_X = [14, 12, 10, 8, 6, 4, 2, 0, 2, 4, 6, 8, 10, 12, 14]
_ISO_N = [4, 8, 12, 16, 20, 24, 28, 32, 28, 24, 20, 16, 12, 8, 4]


class Tile:
    __slots__ = ("direction", "roof_y", "animated", "height", "width", "orientation",
                 "main", "sub", "rarity", "flags", "blocks", "_data", "_bh", "image")

    def key(self):
        return (self.orientation, self.main, self.sub)


class DT1:
    def __init__(self, data, name=""):
        self.name = name
        self.data = data
        v1, v2 = struct.unpack_from("<ii", data, 0)
        if v1 != 7:
            raise ValueError("unsupported DT1 version %d" % v1)
        n, ptr = struct.unpack_from("<ii", data, 268)
        self.tiles = []
        for i in range(n):
            o = ptr + i * 96
            t = Tile()
            (t.direction, t.roof_y, _snd, t.animated, t.height, t.width, _z, t.orientation,
             t.main, t.sub, t.rarity) = struct.unpack_from("<iHBBiiiiiii", data, o)
            t.flags = data[o + 40:o + 65]
            t._bh, _blen, nb = struct.unpack_from("<iii", data, o + 72)
            t.blocks = []
            for b in range(nb):
                x, y, _, gx, gy, fmt, ln, _, doff = struct.unpack_from("<hhHBBHiHi", data, t._bh + b * 20)
                t.blocks.append((x, y, fmt, ln, t._bh + doff))
            t.image = None
            self.tiles.append(t)

    def decode(self, t):
        """Decode a tile -> (width, height, bytearray pixels, x0, y0). Cached on the tile."""
        if t.image is not None:
            return t.image
        if not t.blocks:
            t.image = (0, 0, bytearray(), 0, 0)
            return t.image
        xs, ys, xe, ye = [], [], [], []
        for x, y, fmt, ln, off in t.blocks:
            xs.append(x)
            ys.append(y)
            xe.append(x + 32)
            ye.append(y + (15 if fmt == 1 else 32))
        x0, y0 = min(xs), min(ys)
        w, h = max(xe) - x0, max(ye) - y0
        px = bytearray(w * h)
        d = self.data
        for x, y, fmt, ln, off in t.blocks:
            bx, by = x - x0, y - y0
            if fmt == 1:   # raw isometric block
                p = off
                for row in range(15):
                    n = _ISO_N[row]
                    start = (by + row) * w + bx + _ISO_X[row]
                    px[start:start + n] = d[p:p + n]
                    p += n
            else:          # RLE block
                p, end = off, off + ln
                cx, cy = 0, 0
                while p < end:
                    b1, b2 = d[p], d[p + 1]
                    p += 2
                    if b1 == 0 and b2 == 0:
                        cx = 0
                        cy += 1
                        continue
                    cx += b1
                    start = (by + cy) * w + bx + cx
                    px[start:start + b2] = d[p:p + b2]
                    p += b2
                    cx += b2
        t.image = (w, h, px, x0, y0)
        return t.image


class TileSet:
    """Several DT1 files merged; lookup by (orientation, main, sub) with rarity weighting."""

    def __init__(self, dt1s):
        self.by_key = {}
        for f in dt1s:
            for t in f.tiles:
                self.by_key.setdefault(t.key(), []).append((f, t))

    def pick(self, orientation, main, sub, rnd=0):
        cands = self.by_key.get((orientation, main, sub))
        if not cands:
            return None
        total = sum(max(0, t.rarity) for _, t in cands)
        if total <= 0:
            return cands[0]
        r = rnd % total
        for f, t in cands:
            r -= max(0, t.rarity)
            if r < 0:
                return f, t
        return cands[0]
