"""D2 bitmap fonts: data\\local\\font\\latin\\<name>.dc6 + .tbl (character -> frame, width)."""
import struct

from .dc6 import DC6


class FontTable:
    def __init__(self, tbl, dc6_data):
        if tbl[:4] != b"Woo!":
            raise ValueError("not a D2 font table")
        self.line_height = tbl[10]
        self.cap_height = tbl[11]
        self.glyphs = {}
        n = (len(tbl) - 12) // 14
        for i in range(n):
            code, _u0, width, height, _u1, _u2, frame, _u3 = struct.unpack_from("<HBBBBHHI", tbl, 12 + i * 14)
            self.glyphs[code] = (width, height, frame)
        self.dc6 = DC6(dc6_data)

    def glyph(self, ch):
        code = ord(ch)
        g = self.glyphs.get(code) or self.glyphs.get(ord("?"))
        if not g:
            return None
        width, height, frame = g
        if frame >= len(self.dc6.frames):
            return None
        return width, self.dc6.frames[frame]

    def measure(self, text):
        w = 0
        for ch in text:
            g = self.glyph(ch)
            w += g[0] if g else 0
        return w
