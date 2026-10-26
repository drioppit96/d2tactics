"""Read-only MPQ archive reader (format version 0, as used by Diablo 2)."""
import bz2
import struct
import zlib

from .explode import explode

MASK = 0xFFFFFFFF

FLAG_IMPLODE = 0x00000100
FLAG_COMPRESS = 0x00000200
FLAG_ENCRYPTED = 0x00010000
FLAG_FIX_KEY = 0x00020000
FLAG_SINGLE_UNIT = 0x01000000
FLAG_SECTOR_CRC = 0x04000000
FLAG_EXISTS = 0x80000000

COMP_HUFFMAN = 0x01
COMP_ZLIB = 0x02
COMP_PKWARE = 0x08
COMP_BZIP2 = 0x10
COMP_ADPCM_MONO = 0x40
COMP_ADPCM_STEREO = 0x80


def _crypt_table():
    table = [0] * 0x500
    seed = 0x00100001
    for i1 in range(0x100):
        i2 = i1
        for _ in range(5):
            seed = (seed * 125 + 3) % 0x2AAAAB
            t1 = (seed & 0xFFFF) << 0x10
            seed = (seed * 125 + 3) % 0x2AAAAB
            t2 = seed & 0xFFFF
            table[i2] = t1 | t2
            i2 += 0x100
    return table


CRYPT = _crypt_table()


def hash_string(s, kind):
    seed1, seed2 = 0x7FED7FED, 0xEEEEEEEE
    for ch in s.upper().replace("/", "\\"):
        v = ord(ch)
        seed1 = (CRYPT[(kind << 8) + v] ^ (seed1 + seed2)) & MASK
        seed2 = (v + seed1 + seed2 + (seed2 << 5) + 3) & MASK
    return seed1


def decrypt(data, key):
    n = len(data) // 4
    vals = struct.unpack("<%dI" % n, data[:n * 4])
    out = []
    seed = 0xEEEEEEEE
    for v in vals:
        seed = (seed + CRYPT[0x400 + (key & 0xFF)]) & MASK
        ch = (v ^ (key + seed)) & MASK
        out.append(ch)
        key = ((((~key) << 0x15) + 0x11111111) & MASK) | (key >> 0x0B)
        seed = (ch + seed + (seed << 5) + 3) & MASK
    return struct.pack("<%dI" % n, *out) + data[n * 4:]


def encrypt(data, key):
    """Only used by tests to build archives."""
    n = len(data) // 4
    vals = struct.unpack("<%dI" % n, data[:n * 4])
    out = []
    seed = 0xEEEEEEEE
    for v in vals:
        seed = (seed + CRYPT[0x400 + (key & 0xFF)]) & MASK
        out.append((v ^ (key + seed)) & MASK)
        key = ((((~key) << 0x15) + 0x11111111) & MASK) | (key >> 0x0B)
        seed = (v + seed + (seed << 5) + 3) & MASK
    return struct.pack("<%dI" % n, *out) + data[n * 4:]


class MPQError(Exception):
    pass


class UnsupportedCompression(MPQError):
    pass


def decompress_sector(data, expected):
    mask = data[0]
    payload = data[1:]
    if mask & COMP_BZIP2:
        payload = bz2.decompress(payload)
    if mask & COMP_PKWARE:
        payload = explode(payload, expected)
    if mask & COMP_ZLIB:
        payload = zlib.decompress(payload)
    if mask & (COMP_HUFFMAN | COMP_ADPCM_MONO | COMP_ADPCM_STEREO):
        from .wavecomp import decompress_huffman, decompress_adpcm
        if mask & COMP_HUFFMAN:
            payload = decompress_huffman(payload)
        if mask & COMP_ADPCM_STEREO:
            payload = decompress_adpcm(payload, 2)
        elif mask & COMP_ADPCM_MONO:
            payload = decompress_adpcm(payload, 1)
    known = COMP_BZIP2 | COMP_PKWARE | COMP_ZLIB | COMP_HUFFMAN | COMP_ADPCM_MONO | COMP_ADPCM_STEREO
    if mask & ~known:
        raise UnsupportedCompression("compression mask 0x%02x" % mask)
    return payload


class MPQ:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        self.base = self._find_header()
        self.f.seek(self.base)
        hdr = self.f.read(32)
        (magic, self.header_size, self.archive_size, self.version, shift,
         ht_off, bt_off, ht_n, bt_n) = struct.unpack("<4sIIHHIIII", hdr)
        self.sector_size = 512 << shift
        self.f.seek(self.base + ht_off)
        ht = decrypt(self.f.read(ht_n * 16), hash_string("(hash table)", 3))
        self.hash_table = [struct.unpack_from("<IIHHI", ht, i * 16) for i in range(ht_n)]
        self.f.seek(self.base + bt_off)
        bt = decrypt(self.f.read(bt_n * 16), hash_string("(block table)", 3))
        self.block_table = [struct.unpack_from("<IIII", bt, i * 16) for i in range(bt_n)]

    def _find_header(self):
        self.f.seek(0, 2)
        size = self.f.tell()
        off = 0
        while off < size:
            self.f.seek(off)
            magic = self.f.read(4)
            if magic == b"MPQ\x1a":
                return off
            if magic == b"MPQ\x1b":   # user data header points at the real one
                self.f.seek(off + 8)
                return off + struct.unpack("<I", self.f.read(4))[0]
            off += 512
        raise MPQError("not an MPQ archive: %s" % self.path)

    def close(self):
        self.f.close()

    def _find(self, name):
        n = len(self.hash_table)
        if not n:
            return None
        start = hash_string(name, 0) % n
        a, b = hash_string(name, 1), hash_string(name, 2)
        i = start
        while True:
            h1, h2, locale, platform, block = self.hash_table[i]
            if block == 0xFFFFFFFF:
                return None
            if h1 == a and h2 == b and block != 0xFFFFFFFE:
                return block
            i = (i + 1) % n
            if i == start:
                return None

    def has(self, name):
        b = self._find(name)
        return b is not None and self.block_table[b][3] & FLAG_EXISTS

    def block_info(self, name):
        b = self._find(name)
        if b is None:
            return None
        off, csize, fsize, flags = self.block_table[b]
        return {"offset": off, "csize": csize, "fsize": fsize, "flags": flags}

    def read_raw(self, name):
        info = self.block_info(name)
        if info is None:
            raise KeyError(name)
        self.f.seek(self.base + info["offset"])
        return self.f.read(info["csize"]), info

    def read(self, name):
        b = self._find(name)
        if b is None:
            raise KeyError(name)
        off, csize, fsize, flags = self.block_table[b]
        if not flags & FLAG_EXISTS:
            raise KeyError(name)
        self.f.seek(self.base + off)
        raw = self.f.read(csize)
        key = 0
        if flags & FLAG_ENCRYPTED:
            key = hash_string(name.replace("/", "\\").split("\\")[-1], 3)
            if flags & FLAG_FIX_KEY:
                key = ((key + off) ^ fsize) & MASK
        if flags & FLAG_SINGLE_UNIT:
            data = decrypt(raw, key) if key else raw
            if flags & FLAG_COMPRESS and csize < fsize:
                data = decompress_sector(data, fsize)
            elif flags & FLAG_IMPLODE and csize < fsize:
                data = explode(data, fsize)
            return data[:fsize]
        ss = self.sector_size
        n_sectors = (fsize + ss - 1) // ss
        compressed = flags & (FLAG_COMPRESS | FLAG_IMPLODE)
        if compressed:
            n_off = n_sectors + 1 + (1 if flags & FLAG_SECTOR_CRC else 0)
            table = raw[:n_off * 4]
            if key:
                table = decrypt(table, (key - 1) & MASK)
            offsets = struct.unpack("<%dI" % n_off, table)
        else:
            offsets = [i * ss for i in range(n_sectors)] + [csize]
        out = bytearray()
        for i in range(n_sectors):
            sec = raw[offsets[i]:offsets[i + 1]]
            if key:
                sec = decrypt(sec, (key + i) & MASK)
            want = min(ss, fsize - i * ss)
            if len(sec) < want:
                if flags & FLAG_COMPRESS:
                    sec = decompress_sector(sec, want)
                else:
                    sec = explode(sec, want)
            out += sec[:want]
        return bytes(out[:fsize])


class MPQSet:
    """Several archives searched in priority order (patch_d2 first, like the game)."""
    ORDER = ["patch_d2.mpq", "d2exp.mpq", "d2data.mpq", "d2char.mpq", "d2sfx.mpq",
             "d2xtalk.mpq", "d2speech.mpq", "d2music.mpq", "d2xmusic.mpq"]

    def __init__(self, folder, progress=None, cache_dir=None):
        import os
        self.archives = []
        self.cache_dir = cache_dir
        if cache_dir:
            try:
                os.makedirs(cache_dir, exist_ok=True)
            except OSError:
                self.cache_dir = None
        files = {f.lower(): f for f in os.listdir(folder)}
        for name in self.ORDER:
            if name in files:
                if progress:
                    progress("Opening %s" % name)
                try:
                    self.archives.append((name, MPQ(os.path.join(folder, files[name]))))
                except Exception as e:
                    print("  could not open %s: %s" % (name, e))
        if not self.archives:
            raise MPQError("no Diablo 2 .mpq files found in " + folder)

    def locate(self, name):
        for an, a in self.archives:
            if a.has(name):
                return an, a
        return None, None

    def has(self, name):
        return self.locate(name)[1] is not None

    def read(self, name):
        an, a = self.locate(name)
        if a is None:
            raise KeyError(name)
        if not self.cache_dir:
            return a.read(name)
        # decompressing in Python is slow: keep a zlib copy of every file we have read once
        import hashlib
        import os
        info = a.block_info(name)
        stamp = "%s|%s|%d|%d|%d" % (an, name.lower().replace("/", "\\"), info["offset"], info["csize"], info["fsize"])
        path = os.path.join(self.cache_dir, hashlib.md5(stamp.encode("latin-1")).hexdigest() + ".z")
        try:
            with open(path, "rb") as f:
                return zlib.decompress(f.read())
        except Exception:
            pass
        data = a.read(name)
        try:
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(zlib.compress(data, 1))
            os.replace(tmp, path)
        except Exception:
            pass
        return data
