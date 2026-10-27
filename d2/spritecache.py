"""On-disk cache of decoded DCC animations (units, missiles, overlays).

Decoding a DCC direction is slow in Python (the format is a chain of small variable-length
codes). Every decoded direction is stored once in cache\\sprites, keyed by a checksum of the
DCC file itself - so a different install or a mod never gets stale pictures - and loaded from
there afterwards (a few milliseconds instead of up to a second).

A background process (prebuild) fills the cache for everything the act needs while you play.
"""
import os
import struct
import zlib

MAGIC = b"D2TC1"
_FRAME = struct.Struct("<9i")
_dir = None


def configure(path):
    """Turn the cache on (path = folder for the files). Safe to call more than once."""
    global _dir
    try:
        os.makedirs(path, exist_ok=True)
        _dir = path
    except Exception:
        _dir = None


def enabled():
    return _dir is not None


def key_for(data):
    return "%08x%07x" % (zlib.crc32(data) & 0xFFFFFFFF, len(data) & 0xFFFFFFF)


def _path(key, d):
    return os.path.join(_dir, key[:2], "%s_%d.bin" % (key, d))


def has(key, d):
    return _dir is not None and os.path.isfile(_path(key, d))


def load(key, d, frame_cls):
    """Decoded frames of one direction, or None when not cached (or unreadable)."""
    if _dir is None:
        return None
    p = _path(key, d)
    try:
        with open(p, "rb") as f:
            blob = f.read()
    except OSError:
        return None
    try:
        if not blob.startswith(MAGIC):
            return None
        raw = zlib.decompress(blob[len(MAGIC):])
        n = struct.unpack_from("<I", raw, 0)[0]
        o = 4
        frames = []
        for _ in range(n):
            (fr_w, fr_h, xo, yo, bu, x0, y0, x1, y1) = _FRAME.unpack_from(raw, o)
            o += _FRAME.size
            fr = frame_cls()
            fr.width, fr.height, fr.xoffset, fr.yoffset = fr_w, fr_h, xo, yo
            fr.bottom_up, fr.xmin, fr.ymin, fr.xmax, fr.ymax = bu, x0, y0, x1, y1
            size = fr_w * fr_h
            fr.pixels = bytearray(raw[o:o + size])
            fr.cells = None
            o += size
            frames.append(fr)
        return frames
    except Exception:
        return None


def save(key, d, frames):
    if _dir is None:
        return
    p = _path(key, d)
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        parts = [struct.pack("<I", len(frames))]
        for fr in frames:
            parts.append(_FRAME.pack(fr.width, fr.height, fr.xoffset, fr.yoffset, int(fr.bottom_up),
                                     fr.xmin, fr.ymin, fr.xmax, fr.ymax))
            parts.append(bytes(fr.pixels))
        blob = MAGIC + zlib.compress(b"".join(parts), 1)
        tmp = p + ".%d.tmp" % os.getpid()
        with open(tmp, "wb") as f:
            f.write(blob)
        os.replace(tmp, p)          # atomic: the game never reads a half-written file
    except Exception:
        pass


# ---------------------------------------------------------------- background prebuild
def plan_jobs(src, plan):
    """plan (from the game) -> DCC paths, in order: player, monsters, missiles."""
    from .source import read_table
    from .unitfiles import unit_dccs, monster_dccs, missile_dccs, PLAYER_MODES
    jobs = []
    seen = set()

    def add(paths):
        for x in paths:
            if x not in seen:
                seen.add(x)
                jobs.append(x)
    pl = plan.get("player")
    if pl:
        tok, wcs, arms = pl
        add(unit_dccs(src, "chars", tok, wcs, arms, PLAYER_MODES))
    try:
        ms = {r.get("id", "").lower(): r for r in read_table(src, "MonStats")}
        ms2 = {r.get("id", "").lower(): r for r in read_table(src, "MonStats2")}
    except Exception:
        ms, ms2 = {}, {}
    names = list(plan.get("missiles", []))
    for mid in plan.get("monsters", []):
        add(monster_dccs(src, ms, ms2, mid))
        r = ms.get(mid.lower(), {})
        for col in ("missa1", "missa2", "misss1", "missc"):
            if r.get(col):
                names.append(r[col])
    try:
        rows = {r.get("missile", "").lower(): r for r in read_table(src, "Missiles")}
    except Exception:
        rows = {}
    add(missile_dccs(src, rows, names))
    return jobs


def worker_main(d2_path, cache_dir, mpq_cache, plan, done_file=None):
    """Runs in a separate process: decode every direction of every DCC the plan needs into the cache."""
    _lower_priority()
    configure(cache_dir)
    from .source import open_source
    from .dcc import DCC
    src = open_source(d2_path, None, mpq_cache)
    jobs = plan if isinstance(plan, list) else plan_jobs(src, plan)
    if done_file:
        _progress(done_file, 0, len(jobs))
    n = 0
    for path in jobs:
        try:
            if not src.has(path):
                continue
            data = src.read(path)
            dcc = DCC(data)
            key = key_for(data)
            for d in range(dcc.n_dirs):
                if not has(key, d):
                    dcc.direction(d)      # decodes and saves
            n += 1
        except Exception:
            continue
        if done_file and n % 25 == 0:
            _progress(done_file, n, len(jobs))
    if done_file:
        _progress(done_file, len(jobs), len(jobs))


def _progress(path, n, total):
    try:
        with open(path, "w") as f:
            f.write("%d %d" % (n, total))
    except Exception:
        pass


def _lower_priority():
    """Keep the game smooth: the prebuild only uses spare CPU."""
    try:
        if os.name == "nt":
            import ctypes
            BELOW_NORMAL = 0x00004000
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), BELOW_NORMAL)
        else:
            os.nice(10)
    except Exception:
        pass
