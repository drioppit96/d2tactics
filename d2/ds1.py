"""DS1 level layouts: which tile goes in each 5x5-subtile cell of a room or preset."""
import struct

# orientation lookup for old DS1 versions (< 7)
_DIR_LOOKUP = [0x00, 0x01, 0x02, 0x01, 0x02, 0x03, 0x03, 0x05, 0x05, 0x06, 0x06, 0x07, 0x07,
               0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x14]


class Cell:
    __slots__ = ("prop1", "sub", "main", "orientation", "hidden")

    def __init__(self, dw, orientation=0):
        self.prop1 = dw & 0xFF
        self.sub = (dw >> 8) & 0xFF
        self.main = (dw >> 20) & 0x3F
        self.hidden = bool(dw & 0x80000000)
        self.orientation = orientation

    @property
    def empty(self):
        return self.prop1 == 0 and self.sub == 0 and self.main == 0


class DS1:
    def __init__(self, data, name=""):
        self.name = name
        p = 0

        def i32():
            nonlocal p
            v = struct.unpack_from("<i", data, p)[0]
            p += 4
            return v

        self.version = i32()
        self.width = i32() + 1
        self.height = i32() + 1
        self.act = i32() + 1 if self.version >= 8 else 1
        tag_type = i32() if self.version >= 10 else 0
        self.files = []
        if self.version >= 3:
            for _ in range(i32()):
                end = data.index(b"\0", p)
                self.files.append(data[p:end].decode("latin-1"))
                p = end + 1
        if 9 <= self.version <= 13:
            p += 8
        n_walls, n_floors = 1, 1
        if self.version >= 4:
            n_walls = i32()
            if self.version >= 16:
                n_floors = i32()
        layers = []
        if self.version < 4:
            layers = [("wall", 0), ("floor", 0), ("orient", 0), ("tag", 0), ("shadow", 0)]
        else:
            for i in range(n_walls):
                layers += [("wall", i), ("orient", i)]
            for i in range(n_floors):
                layers.append(("floor", i))
            layers.append(("shadow", 0))
            if tag_type in (1, 2):
                layers.append(("tag", 0))
        n = self.width * self.height
        raw = {}
        for kind, idx in layers:
            vals = struct.unpack_from("<%dI" % n, data, p)
            p += n * 4
            raw[(kind, idx)] = vals
        self.floors = []
        for i in range(n_floors):
            vals = raw[("floor", i)]
            self.floors.append([Cell(v) for v in vals])
        self.walls = []
        for i in range(n_walls):
            vals = raw[("wall", i)]
            ors = raw.get(("orient", i), [0] * n)
            row = []
            for v, o in zip(vals, ors):
                o &= 0xFF
                if self.version < 7:
                    o = _DIR_LOOKUP[o] if o < len(_DIR_LOOKUP) else o
                row.append(Cell(v, o))
            self.walls.append(row)
        self.shadows = [Cell(v, 13) for v in raw[("shadow", 0)]]
        # objects: (type, id, x, y) with x/y in subtiles; type 1 = NPC/monster preset, 2 = object
        self.objects = []
        try:
            if self.version >= 2:
                n_obj = i32()
                for _ in range(n_obj):
                    t, oid, ox, oy = struct.unpack_from("<iiii", data, p)
                    p += 16
                    if self.version > 5:
                        p += 4
                    self.objects.append((t, oid, ox, oy))
        except struct.error:
            pass

    def cell(self, layer, x, y):
        return layer[y * self.width + x]
