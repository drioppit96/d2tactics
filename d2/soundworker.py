"""The sound unpacker: a separate low-priority process, so unpacking D2's Huffman + ADPCM wav files
never slows the game down. It reads each requested file once through the MPQ cache (which keeps a
quick zlib copy) - music also goes to cache\\music as a plain .wav for streaming."""
import hashlib
import os


def music_file(music_dir, path):
    base = os.path.splitext(os.path.basename(path.replace("\\", "/")))[0]
    h = hashlib.md5(path.lower().encode("latin-1")).hexdigest()[:8]
    return os.path.join(music_dir, "%s_%s.wav" % (base, h))


def worker_main(d2_path, mpq_cache, music_dir, inq, outq):
    try:
        from .spritecache import _lower_priority
        _lower_priority()
    except Exception:
        pass
    from .source import open_source
    src = open_source(d2_path, None, mpq_cache)
    while True:
        path = inq.get()
        if path is None:
            return
        good = False
        try:
            data = src.read(path)
            if path.lower().startswith("data\\global\\music\\"):
                out = music_file(music_dir, path)
                tmp = out + ".tmp"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, out)
            good = True
        except Exception:
            good = False
        try:
            outq.put((path, good))
        except Exception:
            return
