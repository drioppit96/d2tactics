"""HD sprites: D2's art enlarged by a small neural net before it is drawn.

The nets are Anime4K's upscaling GANs (MIT, bloc97, see assets/upscale/LICENSE-Anime4K.txt),
converted to ONNX. They were trained on hand-drawn art rather than photographs, which is what
D2's sprites are, so they keep an edge hard instead of smearing it the way a plain resize does.
They are tiny - 37 KB and 117 KB - and run on the processor through onnxruntime.

    quality("fast" | "best" | "off")   pick the net
    scale_surface(img, k)              img enlarged k times, AI if it can, a plain resize if not

Nothing is enlarged twice: every frame is written to cache/sprites/hd the first time it is drawn
and read back from there afterwards, so a monster costs its moment of work once and is free for
the rest of the game. The cache is made from the player's own MPQ art and never leaves their disk.

Without onnxruntime (or on a machine where it won't load) everything here still works - it just
falls back to a high quality resize, which is what the game did before.
"""
import hashlib
import os

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "assets", "upscale")
CACHE = os.path.join(ROOT, "cache", "sprites", "hd")
NETS = {"fast": ("Anime4K_Upscale_GAN_x2_M.onnx", 2), "best": ("Anime4K_Upscale_GAN_x4_UL.onnx", 4)}
MAX_SIDE = 512            # past this the net costs more than it gives back

_state = {"quality": "off", "session": None, "net": None, "fails": 0, "np": None}


def quality(name=None):
    """Read or set which net to use: "off", "fast" (2x) or "best" (4x)."""
    if name is not None and name != _state["quality"]:
        _state["quality"] = name if name in NETS else "off"
        _state["session"] = _state["net"] = None
        _state["fails"] = 0
    return _state["quality"]


def available():
    """Can we actually run a net on this machine?"""
    if _state["quality"] == "off" or _state["fails"] > 3:
        return False
    if _state["session"] is not None:
        return True
    name, k = NETS[_state["quality"]]
    path = os.path.join(MODELS, name)
    if not os.path.exists(path):
        return False
    try:
        import numpy as np
        import onnxruntime as rt
        rt.set_default_logger_severity(3)          # (Windows 7 prints a version warning; it still runs)
        so = rt.SessionOptions()
        so.intra_op_num_threads = max(1, min(4, (os.cpu_count() or 2)))
        s = rt.InferenceSession(path, so, providers=["CPUExecutionProvider"])
        inp = s.get_inputs()[0]
        _state["np"] = np
        _state["session"] = s
        _state["net"] = (inp.name, np.float16 if "float16" in inp.type else np.float32, k)
        return True
    except Exception:
        _state["fails"] = 99
        return False


def _to_array(img):
    np = _state["np"]
    if hasattr(img, "img"):                        # headless: a PIL image behind the Surface
        return np.asarray(img.img.convert("RGBA"), np.float32) / 255.0
    w, h = img.get_size()
    buf = pygame.image.tostring(img, "RGBA")
    return np.frombuffer(buf, np.uint8).reshape(h, w, 4).astype(np.float32) / 255.0


def _to_surface(a):
    np = _state["np"]
    a = np.ascontiguousarray(np.clip(a * 255.0, 0, 255).astype(np.uint8))
    h, w = a.shape[:2]
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    if hasattr(out, "img"):
        from PIL import Image
        out.img = Image.fromarray(a, "RGBA")
        return out
    return pygame.image.fromstring(a.tobytes(), (w, h), "RGBA").convert_alpha()


def _plain(img, size):
    """The fallback: a smooth resize with the colour premultiplied, so the transparent black
    around a D2 sprite can't bleed a dark fringe into its edge."""
    if hasattr(img, "img"):
        from PIL import Image
        out = pygame.Surface(size, pygame.SRCALPHA)
        out.img = img.img.resize(size, Image.LANCZOS)
        return out
    try:
        return pygame.transform.smoothscale(img, size)
    except Exception:
        return pygame.transform.scale(img, size)


def _net_upscale(img):
    """Run the net. Returns the enlarged array (the net's own factor), or None."""
    np = _state["np"]
    a = _to_array(img)
    rgb, al = a[:, :, :3], a[:, :, 3:4]
    x = (rgb * al).transpose(2, 0, 1)[None]        # premultiplied, so the edges stay clean
    name, dt, k = _state["net"]
    y = _state["session"].run(None, {name: x.astype(dt)})[0]
    big = np.clip(y[0].transpose(1, 2, 0).astype(np.float32), 0, 1)
    h, w = big.shape[:2]
    ab = _resize_alpha(al[:, :, 0], w, h)[:, :, None]
    out = np.where(ab > 0.004, big / np.maximum(ab, 0.004), 0.0)
    return np.dstack([np.clip(out, 0, 1), ab])


def _resize_alpha(al, w, h):
    np = _state["np"]
    from PIL import Image
    im = Image.fromarray(np.clip(al * 255, 0, 255).astype(np.uint8), "L").resize((w, h), Image.LANCZOS)
    return np.asarray(im, np.float32) / 255.0


def _cache_path(img, k):
    try:
        if hasattr(img, "img"):
            raw = img.img.convert("RGBA").tobytes()
        else:
            raw = pygame.image.tostring(img, "RGBA")
    except Exception:
        return None
    h = hashlib.md5(raw).hexdigest()
    return os.path.join(CACHE, _state["quality"], "%.3f" % k, h[:2], h[2:] + ".png")


def scale_surface(img, k):
    """img at k times its size. The net runs once per picture; after that it comes off disk."""
    w, h = img.get_size()
    size = (max(1, int(round(w * k))), max(1, int(round(h * k))))
    if size == (w, h) or not w or not h:
        return img
    if k <= 1.0 or max(w, h) > MAX_SIDE or not available():
        return _plain(img, size)
    path = _cache_path(img, k)
    if path and os.path.exists(path):
        got = _load(path)
        if got is not None:
            return got
    try:
        big = _net_upscale(img)
        out = _to_surface(big)
        if out.get_size() != size:                 # the net's factor is 2 or 4: fit to what we need
            out = _plain(out, size)
    except Exception:
        _state["fails"] += 1
        return _plain(img, size)
    _save(out, path)
    return out


def _load(path):
    try:
        got = pygame.image.load(path)
        return got.convert_alpha() if pygame.display.get_surface() else got
    except Exception:
        pass
    try:                                           # headless, or a pygame without image support
        from PIL import Image
        im = Image.open(path).convert("RGBA")
        out = pygame.Surface(im.size, pygame.SRCALPHA)
        if hasattr(out, "img"):
            out.img = im
            return out
    except Exception:
        pass
    return None


def _save(surf, path):
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        return
    try:
        pygame.image.save(surf, path)
        return
    except Exception:
        pass
    try:
        if hasattr(surf, "img"):
            surf.img.save(path)
    except Exception:
        pass


def clear_cache():
    """Throw the enlarged pictures away (after changing quality, or to reclaim the space)."""
    import shutil
    try:
        shutil.rmtree(CACHE)
    except Exception:
        pass
