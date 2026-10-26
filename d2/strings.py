"""D2 string tables (data\\local\\lng\\eng\\*.tbl): display names for items, monsters, etc."""
import re
import struct

TABLES = ["data\\local\\lng\\eng\\string.tbl", "data\\local\\lng\\eng\\expansionstring.tbl",
          "data\\local\\lng\\eng\\patchstring.tbl"]


def parse_tbl(data):
    """-> {key: text}"""
    crc, n, hsize, ver, dstart, maxtries, fsize = struct.unpack_from("<HHIBIII", data, 0)
    p = 21 + n * 2
    out = {}
    for i in range(hsize):
        used, idx, hval, koff, soff, slen = struct.unpack_from("<BHIIIH", data, p + i * 17)
        if not used:
            continue
        kend = data.index(b"\0", koff)
        key = data[koff:kend].decode("latin-1")
        text = data[soff:soff + slen].split(b"\0")[0].decode("latin-1")
        out[key] = text
    return out


def _clean(text):
    text = re.sub(r"\xffc.", "", text)            # D2 colour codes
    return text.split("\n")[-1].strip()


class Strings:
    def __init__(self, src):
        self.table = {}
        for name in TABLES:            # later tables override earlier ones, like the game
            try:
                if src.has(name):
                    self.table.update(parse_tbl(src.read(name)))
            except Exception:
                pass

    def get(self, key, fallback=None):
        if key in self.table:
            return _clean(self.table[key])
        return fallback if fallback is not None else key


def tidy_internal_name(name):
    """Fallback when no string table: 'Cap/hat' -> 'Cap', 'Sash(L)' -> 'Sash'."""
    name = name.split("/")[0]
    name = re.sub(r"\s*\(.*?\)", "", name)
    return name.strip()
