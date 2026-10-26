"""COF files: which body-part layers make up a unit animation, and their draw order."""
import struct

COMPONENTS = ["HD", "TR", "LG", "RA", "LA", "RH", "LH", "SH",
              "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]


class Layer:
    __slots__ = ("component", "shadow", "selectable", "transparent", "draw_effect", "weapon_class")


class COF:
    def __init__(self, data):
        self.n_layers, self.frames, self.n_dirs = data[0], data[1], data[2]
        self.xmin, self.xmax, self.ymin, self.ymax = struct.unpack_from("<iiii", data, 8)
        self.anim_rate = struct.unpack_from("<h", data, 24)[0]
        self.layers = []
        p = 28
        for _ in range(self.n_layers):
            L = Layer()
            L.component = COMPONENTS[data[p]] if data[p] < len(COMPONENTS) else str(data[p])
            L.shadow, L.selectable, L.transparent, L.draw_effect = data[p + 1], data[p + 2], data[p + 3], data[p + 4]
            L.weapon_class = data[p + 5:p + 9].split(b"\0")[0].decode("latin-1")
            self.layers.append(L)
            p += 9
        self.keyframes = list(data[p:p + self.frames])
        p += self.frames
        n = self.n_dirs * self.frames * self.n_layers
        order = data[p:p + n]
        # priority[dir][frame] = list of component names, back to front
        self.priority = []
        i = 0
        for d in range(self.n_dirs):
            per_dir = []
            for f in range(self.frames):
                per_dir.append([COMPONENTS[c] if c < len(COMPONENTS) else None
                                for c in order[i:i + self.n_layers]])
                i += self.n_layers
            self.priority.append(per_dir)
