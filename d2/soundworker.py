"""The sound unpacker: separate low-priority processes, so unpacking D2's Huffman + ADPCM wav files
never slows the game down. Each file is read once through the MPQ cache (which keeps a quick zlib
copy) - music also goes to cache\\music as a plain .wav for streaming.

Requests (what the game wants right now) always come first; when there are none, the worker works
through its sweep list (every sound of the game, most likely first), so after a while everything
plays instantly."""
import hashlib
import os
import time


def music_file(music_dir, path):
    base = os.path.splitext(os.path.basename(path.replace("\\", "/")))[0]
    h = hashlib.md5(path.lower().encode("latin-1")).hexdigest()[:8]
    return os.path.join(music_dir, "%s_%s.wav" % (base, h))


def _unpack(src, music_dir, path):
    if path.lower().startswith("data\\global\\music\\"):
        out = music_file(music_dir, path)
        if os.path.exists(out):
            return True
        data = src.read(path)
        tmp = out + ".%d.tmp" % os.getpid()
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, out)
        return True
    if hasattr(src, "cached") and src.cached(path):
        return True
    src.read(path)
    return True


def worker_main(d2_path, mpq_cache, music_dir, inq, outq, sweep=None):
    try:
        from .spritecache import _lower_priority
        _lower_priority()
    except Exception:
        pass
    from .source import open_source
    src = open_source(d2_path, None, mpq_cache)
    sweep = list(sweep or [])
    import queue as _q
    while True:
        try:
            path = inq.get(timeout=0.05) if sweep else inq.get()
        except _q.Empty:
            path = ""
        except Exception:
            return
        if path is None:
            return
        if path:
            try:
                good = _unpack(src, music_dir, path)
            except Exception:
                good = False
            try:
                outq.put((path, good))
            except Exception:
                return
            continue
        # nothing wanted right now: unpack the next sound of the sweep, quietly
        p = sweep.pop(0)
        try:
            _unpack(src, music_dir, p)
        except Exception:
            pass
        time.sleep(0.005)
