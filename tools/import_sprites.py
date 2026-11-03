"""Cuts the hand-made decoration sprite sheets (assets/decor_src/sheet*.png) into the game's sprites
(assets/decor/<name>.png + their ground points in anchors.json):

    python tools/import_sprites.py

sheet1: 4 x 3 on a black ground, a label above each.  sheet2: 4 x 3 on a white/grey checkerboard.
The background is keyed out, each piece cropped and scaled to the game's size (a man is ~90 px).
"""
import json
import os

from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets", "decor_src")
OUT = os.path.join(ROOT, "assets", "decor")

SHEET1 = ["anvil", "armorstand", "arrows", "banner", "blood", "bones", "cart", "crates",
          "debris", "dummy", "forge", "weaponrack"]
SHEET2 = ["statue", "bunks", "table", "kegs", "grindstone", "target", "shieldrack", "chest",
          "cauldron", "gibbet", "spikes", "sacks"]
SCALE1, SCALE2 = 0.74, 0.6


def key_dark(im):
    """Black ground -> transparent. What is clearly lit (props, pebbles) stays, with the dark parts of
    the props next to it (dark iron, shadows inside a crate); the soft soil halo far from anything goes."""
    import numpy as np
    from scipy import ndimage
    a = np.asarray(im, dtype=np.float32)
    lum = (a[..., 0] * 30 + a[..., 1] * 59 + a[..., 2] * 11) / 100.0
    red = (a[..., 0] > 24) & (a[..., 0] > a[..., 1] * 2.0) & (a[..., 0] > a[..., 2] * 2.0)          # blood is dark, but red
    core = (lum > 42) | red
    near = ndimage.binary_dilation(core, iterations=6)
    keep = ((lum > 13) | red) & near
    keep = ndimage.binary_fill_holes(ndimage.binary_closing(keep, iterations=2)) & ((lum > 6) | red)
    return Image.fromarray((keep * 255).astype("uint8"))


def key_checker(im):
    """White/grey checkerboard -> transparent: bright, colourless pixels."""
    px = im.load()
    a = Image.new("L", im.size, 0)
    pa = a.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y][:3]
            lum = (r * 30 + g * 59 + b * 11) / 100.0
            sat = max(r, g, b) - min(r, g, b)
            pa[x, y] = 0 if (lum > 196 and sat < 18) else 255
    return a


def clean(alpha, min_px=6):
    """Drop isolated specks: a pixel needs a few opaque neighbours."""
    return alpha.filter(ImageFilter.MedianFilter(3))


def boxes_of(alpha, rows, cols, skip_top=0, row_ranges=None):
    """The pieces in reading order: big blobs of the mask (pieces joined by their scattered
    pebbles), the n largest, sorted into rows and then left to right."""
    import numpy as np
    from scipy import ndimage
    a = np.array(alpha) > 0
    if row_ranges:
        keep = np.zeros_like(a)
        for y0, y1 in row_ranges:
            keep[y0:y1] = True
        a &= keep
    lab, n = ndimage.label(ndimage.binary_dilation(a, iterations=14))
    objs = ndimage.find_objects(lab)
    sizes = ndimage.sum(a, lab, range(1, n + 1))
    best = sorted(range(n), key=lambda i: -sizes[i])[:rows * cols]
    boxes = []
    for i in best:
        sl = objs[i]
        sub = a[sl] & (lab[sl] == i + 1)
        ys, xs = np.nonzero(sub)
        boxes.append((sl[1].start + xs.min(), sl[0].start + ys.min(), sl[1].start + xs.max() + 1, sl[0].start + ys.max() + 1))
    H = alpha.size[1]

    def row_of(b):
        cy = (b[1] + b[3]) / 2.0
        if row_ranges:
            return min(range(len(row_ranges)), key=lambda k: abs((row_ranges[k][0] + row_ranges[k][1]) / 2.0 - cy))
        return int(cy / (H / float(rows)))
    boxes.sort(key=lambda b: (row_of(b), b[0]))
    return boxes


def save(im, alpha, box, name, scale, anchors):
    x0, y0, x1, y1 = box
    piece = im.crop(box).convert("RGBA")
    piece.putalpha(alpha.crop(box))
    w, h = max(1, int(piece.width * scale)), max(1, int(piece.height * scale))
    piece = piece.resize((w, h), Image.LANCZOS)
    a = piece.split()[3].point(lambda v: 255 if v > 120 else 0)
    piece.putalpha(a)
    bb = a.getbbox() or (0, 0, w, h)
    piece = piece.crop(bb)
    piece.save(os.path.join(OUT, name + ".png"))
    # the ground point: under the middle, a little up from the lowest pixel (the footprint's centre)
    anchors[name] = [piece.width // 2, max(0, piece.height - min(28, int(piece.height * 0.16)))]


def main():
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "anchors.json")
    anchors = json.load(open(path)) if os.path.exists(path) else {}
    for sheet, names, keyer, rr, scale in (("sheet1.png", SHEET1, key_dark, [(45, 360), (395, 680), (712, 1054)], SCALE1),
                                           ("sheet2.png", SHEET2, key_checker, None, SCALE2)):
        f = os.path.join(SRC, sheet)
        if not os.path.exists(f):
            continue
        im = Image.open(f).convert("RGB")
        alpha = clean(keyer(im))
        for name, box in zip(names, boxes_of(alpha, 3, 4, row_ranges=rr)):
            if box:
                save(im, alpha, box, name, scale, anchors)
                print("cut", name)
    with open(path, "w") as fh:
        json.dump(anchors, fh, indent=1)


if __name__ == "__main__":
    main()
