"""DC6 images: item icons, item drop animations, interface panels, fonts, some missiles."""
import struct


class DC6Frame:
    __slots__ = ("width", "height", "xoff", "yoff", "pixels")


class DC6:
    def __init__(self, data):
        ver, flags, enc = struct.unpack_from("<iii", data, 0)
        if ver != 6:
            raise ValueError("not a DC6 file (version %d)" % ver)
        self.n_dirs, self.frames_per_dir = struct.unpack_from("<ii", data, 16)
        n = self.n_dirs * self.frames_per_dir
        ptrs = struct.unpack_from("<%dI" % n, data, 24)
        self.frames = []
        for p in ptrs:
            flip, w, h, xo, yo, _unk, _nxt, ln = struct.unpack_from("<iiiiiiii", data, p)
            f = DC6Frame()
            f.width, f.height, f.xoff, f.yoff = w, h, xo, yo
            px = bytearray(w * h)
            d = p + 32
            end = d + ln
            x = 0
            y = 0 if flip else h - 1
            step = 1 if flip else -1
            while d < end:
                b = data[d]
                d += 1
                if b == 0x80:          # end of scanline
                    x = 0
                    y += step
                elif b & 0x80:         # transparent run
                    x += b & 0x7F
                else:                  # b opaque pixels follow
                    if 0 <= y < h:
                        o = y * w + x
                        px[o:o + b] = data[d:d + b]
                    d += b
                    x += b
            f.pixels = px
            self.frames.append(f)

    def frame(self, direction=0, index=0):
        return self.frames[direction * self.frames_per_dir + index]
