"""DCC animation decoder (unit graphics: one body part, one mode, all directions).

Follows Paul Siramy's DCC format description. The image of each direction is built
from 4x4 pixel cells that are reused between frames, with several bitstreams
describing which cells changed and how.
"""
import struct

_CRAZY = [0, 1, 2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 26, 28, 30, 32]


class BitReader:
    __slots__ = ("data", "pos", "end")

    def __init__(self, data, start_bit=0, end_bit=None):
        self.data = data
        self.pos = start_bit
        self.end = len(data) * 8 if end_bit is None else end_bit

    def read(self, n):
        if n == 0:
            return 0
        p = self.pos
        byte = p >> 3
        shift = p & 7
        need = (shift + n + 7) >> 3
        chunk = int.from_bytes(self.data[byte:byte + need], "little")
        self.pos = p + n
        return (chunk >> shift) & ((1 << n) - 1)

    def read_signed(self, n):
        if n == 0:
            return 0
        v = self.read(n)
        if v & (1 << (n - 1)):
            v -= 1 << n
        return v

    def bit(self):
        p = self.pos
        self.pos = p + 1
        return (self.data[p >> 3] >> (p & 7)) & 1


class Frame:
    __slots__ = ("width", "height", "xoffset", "yoffset", "bottom_up", "xmin", "ymin", "xmax", "ymax",
                 "pixels", "cells")


class Direction:
    """Decoded frames for one direction. frame.pixels is a bytearray (width*height), 0 = transparent;
    frame.xmin / ymin are offsets of the image's top-left from the unit's feet."""

    def __init__(self, frames):
        self.frames = frames


def _cell_sizes(start_in_dir, length):
    """Split a frame span into cells aligned to the direction's 4-pixel grid."""
    first = 4 - (start_in_dir % 4)
    if length - first <= 1:
        return [length]
    tmp = length - first - 1
    n = 2 + tmp // 4
    if tmp % 4 == 0:
        n -= 1
    sizes = [first] + [4] * (n - 2)
    sizes.append(length - sum(sizes))
    return sizes


class DCC:
    def __init__(self, data):
        self.data = data
        sig, ver, ndirs = struct.unpack_from("<BBB", data, 0)
        if sig != 0x74:
            raise ValueError("not a DCC file")
        self.n_dirs = ndirs
        self.frames_per_dir = struct.unpack_from("<I", data, 3)[0]
        self.dir_offsets = list(struct.unpack_from("<%dI" % ndirs, data, 15))
        self._dirs = {}

    def direction(self, d):
        if d not in self._dirs:
            self._dirs[d] = self._decode_direction(d)
        return self._dirs[d]

    def _decode_direction(self, d):
        data = self.data
        start = self.dir_offsets[d] * 8
        end = (self.dir_offsets[d + 1] * 8) if d + 1 < self.n_dirs else len(data) * 8
        br = BitReader(data, start, end)
        br.read(32)  # outsize_coded
        comp = br.read(2)
        b_var0 = _CRAZY[br.read(4)]
        b_w = _CRAZY[br.read(4)]
        b_h = _CRAZY[br.read(4)]
        b_x = _CRAZY[br.read(4)]
        b_y = _CRAZY[br.read(4)]
        b_opt = _CRAZY[br.read(4)]
        b_coded = _CRAZY[br.read(4)]
        frames = []
        opt_total = 0
        for _ in range(self.frames_per_dir):
            f = Frame()
            br.read(b_var0)
            f.width = br.read(b_w)
            f.height = br.read(b_h)
            f.xoffset = br.read_signed(b_x)
            f.yoffset = br.read_signed(b_y)
            opt = br.read(b_opt)
            br.read(b_coded)
            f.bottom_up = br.bit()
            opt_total += opt
            f.xmin = f.xoffset
            f.xmax = f.xmin + f.width - 1
            if f.bottom_up:
                f.ymin = f.yoffset
                f.ymax = f.ymin + f.height - 1
            else:
                f.ymax = f.yoffset
                f.ymin = f.ymax - f.height + 1
            frames.append(f)
        if opt_total:
            br.pos = (br.pos + 7) & ~7
            br.pos += opt_total * 8

        eq_size = br.read(20) if comp & 2 else 0
        mask_size = br.read(20)
        enc_size = raw_size = 0
        if comp & 1:
            enc_size = br.read(20)
            raw_size = br.read(20)
        pixel_values = []
        for i in range(256):
            if br.bit():
                pixel_values.append(i)
        pixel_values += [0] * (256 - len(pixel_values))

        p = br.pos
        eq_br = BitReader(data, p, p + eq_size)
        p += eq_size
        mask_br = BitReader(data, p, p + mask_size)
        p += mask_size
        enc_br = BitReader(data, p, p + enc_size)
        p += enc_size
        raw_br = BitReader(data, p, p + raw_size)
        p += raw_size
        code_br = BitReader(data, p, end)

        # direction bounding box
        dxmin = min(f.xmin for f in frames)
        dymin = min(f.ymin for f in frames)
        dxmax = max(f.xmax for f in frames)
        dymax = max(f.ymax for f in frames)
        dw, dh = dxmax - dxmin + 1, dymax - dymin + 1
        ncw = 1 + (dw - 1) // 4
        nch = 1 + (dh - 1) // 4

        # frame cells: (x0, y0 in direction space, w, h, buffer cell index)
        for f in frames:
            fx, fy = f.xmin - dxmin, f.ymin - dymin
            ws = _cell_sizes(fx, f.width)
            hs = _cell_sizes(fy, f.height)
            cells = []
            cy = fy
            for h in hs:
                cx = fx
                for w in ws:
                    cells.append([cx, cy, w, h, (cy // 4) * ncw + (cx // 4), None])
                    cx += w
                cy += h
            f.cells = cells

        # stage 1: pixel buffer entries
        last = [None] * (ncw * nch)
        for f in frames:
            for cell in f.cells:
                ci = cell[4]
                old = last[ci]
                if old is not None:
                    tmp = eq_br.bit() if eq_size else 0
                    if tmp:
                        continue           # equal cell: reuse previous pixels
                    mask = mask_br.read(4)
                else:
                    mask = 0x0F
                read = []
                if mask:
                    nbits = (mask & 1) + ((mask >> 1) & 1) + ((mask >> 2) & 1) + ((mask >> 3) & 1)
                    last_pix = 0
                    enc = enc_br.bit() if enc_size else 0   # one flag per cell
                    for _ in range(nbits):
                        if enc:
                            val = raw_br.read(8)
                        else:
                            val = last_pix
                            while True:
                                disp = code_br.read(4)
                                val += disp
                                if disp != 15:
                                    break
                        if val == last_pix:
                            break
                        read.append(val)
                        last_pix = val
                vals = [0, 0, 0, 0]
                idx = len(read) - 1
                for i in range(4):
                    if mask & (1 << i):
                        vals[i] = pixel_values[read[idx] & 0xFF] if idx >= 0 else 0
                        idx -= 1
                    else:
                        vals[i] = old[i] if old is not None else 0
                cell[5] = vals
                last[ci] = vals

        # stage 2: paint cells into a persistent direction bitmap
        bitmap = bytearray(dw * dh)
        seen = [None] * (ncw * nch)   # last (x0, y0, w, h) painted in each buffer cell
        for f in frames:
            for cx, cy, w, h, ci, vals in f.cells:
                prev = seen[ci]
                if vals is None:
                    if prev is None or prev[2] != w or prev[3] != h:
                        for yy in range(h):
                            o = (cy + yy) * dw + cx
                            bitmap[o:o + w] = bytes(w)
                    elif prev[0] != cx or prev[1] != cy:
                        px0, py0 = prev[0], prev[1]
                        rows = [bytes(bitmap[(py0 + yy) * dw + px0:(py0 + yy) * dw + px0 + w]) for yy in range(h)]
                        for yy in range(h):
                            o = (cy + yy) * dw + cx
                            bitmap[o:o + w] = rows[yy]
                else:
                    if vals[0] == vals[1]:
                        for yy in range(h):
                            o = (cy + yy) * dw + cx
                            bitmap[o:o + w] = bytes([vals[0]]) * w
                    else:
                        nb = 1 if vals[1] == vals[2] else 2
                        rd = code_br.read
                        for yy in range(h):
                            o = (cy + yy) * dw + cx
                            for xx in range(w):
                                bitmap[o + xx] = vals[rd(nb)]
                seen[ci] = (cx, cy, w, h)
            # cut this frame out of the direction bitmap
            fx, fy = f.xmin - dxmin, f.ymin - dymin
            px = bytearray(f.width * f.height)
            for yy in range(f.height):
                o = (fy + yy) * dw + fx
                px[yy * f.width:(yy + 1) * f.width] = bitmap[o:o + f.width]
            f.pixels = px
            f.cells = None
        return Direction(frames)
