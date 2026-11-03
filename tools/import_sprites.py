"""Cuts the hand-made decoration sprite sheets (assets/decor_src/sheet*.png) into the game's sprites
(assets/decor/<name>.png + their ground points in anchors.json):

    python tools/import_sprites.py [Diablo II folder]

With the Diablo II folder (or the extracted samples) the colours are graded and snapped to Act 3's
palette, so the sprites sit in with the game's own tiles and objects.

sheet1: 4 x 3 on a black ground, a label above each.  sheet2: 4 x 3 on a white/grey checkerboard.
sheet3 (buildings, floors, fences) and sheet4 (props): many pieces on a checkerboard, cut blob by blob;
how much ground each blocks goes to blocks.json.
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
SCALE1, SCALE2 = 0.5, 0.4

# sheet3 / sheet4: many pieces on a checkerboard, cut by connected blobs in reading order
SHEET3 = ["cathedral", "demon_shrine", "fortress", "blood_spire_shrine", "banner_gate", "watchtower", "ruined_arch",
          "altar_pyramid", "ritual_dais", "arch_colonnade", "lava_cave", "floor_slab", "floor_cobble",
          ("rug_small", "floor_cracked"), "floor_cross", "floor_broken", "skull_heap", "post_short", "post",
          "pillar_small", "pillar_round", "pillar_tall", "spire_small", "spire", "urn_stone", "gallows_double",
          "floor_dark", "bone_heap", "rug_large", "floor_mosaic", "floor_sigil", "bone_scatter", "floor_grate",
          "gore_pile", "floor_rune", "goblet_brazier", "brazier_bronze", ("banner_grey", "banner_red2"),
          "banner_red3", "banner_tattered", "iron_fence_gate", "iron_fence_short", "shrine_gate", "iron_fence",
          "iron_fence_ruin", "fence_wall_ruin", "ruin_arch_wall", "rubble_wall", "wall_ruin", "hooded_statue_small",
          "stone_block", "candelabra_great"]
SPLIT3 = {13: 503, 37: 1272}          # two pieces touching: split at this x
BIG3 = set(SHEET3[:11])                # the buildings: drawn bigger
SHEET4 = ["pillar_square", "pillar_hollow", "pillar_carved", "zealot_statue", "hooded_statue", "gargoyle", "obelisk",
          "obelisk_small", "cross_monument", "banner_red", "banner_rag", "banner_bone", "lantern_post", "stake",
          "skeleton_cage", "brazier", "brazier_tall", "cauldron_tripod", "brazier_wide", "brazier_goblet",
          "brazier_bowl", "brazier_tower", "cauldron_big", "torch_stand", "candles", "candelabra", "vase_small", "vase",
          "amphora", "reliquary", "stone_chest", "candle_arch", "feast_table", "bench_table", "throne", "lectern",
          "bookcase", "wardrobe", "barrels_stack", "chests_stack", "trunk", "open_crate", "stool", "round_table", "beds",
          "cabinet", "crate", "barrel", "bucket", "low_bench", "jug", "pots", "bone_cart", "firewood", "bone_spread",
          "skull", "sarcophagus", "stone_pile", "pedestal", "urn", "washbasin", "font", "tile_slab", "tile_worn",
          "tile_dark", "dirt_patch", "gravel_patch", "blood_tile", "rug_red", "rug_torn", "web_patch", "rock_pile",
          "grate_large", "grate", "chalice_font", "rack_frame", "torture_ladder", "hanging_cage", "pillory",
          "iron_chair", "breaking_wheel", "spear_rack", "chopping_block", "bloody_table", "meat_rack",
          "hanged_skeleton", "hook_gallows", "spike_tripod", "bone", "skull_small", None, "skeleton", "skeletons",
          "skulls_small", None, "skull_heap2", "candle", "skulls", "dead_tree", "brambles", "stone_arch", "ruin_chunk",
          "well", "pot", "rubble"]
SCALE3, SCALE4, SCALE_BIG = 1.1, 0.75, 1.6       # (sheet4 is drawn bigger than sheet3)
# lie flat on the ground: walked over, their ground point in the middle
FLAT = {"blood_tile", "bone_scatter", "bone_spread", "gore_pile", "skull", "skull_small", "skulls", "skulls_small",
        "skull_heap", "skull_heap2", "bone", "bone_heap", "firewood", "skeleton", "skeletons"}


def is_flat(name):
    return name in FLAT or name.startswith(("floor_", "tile_", "rug_", "grate")) or name.endswith("_patch")


def blobs(im):
    """The pieces of a checkerboard sheet: (box, mask) per connected blob, in reading order."""
    import numpy as np
    from scipy import ndimage
    a = np.asarray(im).astype(np.int32)
    lum = (a[..., 0] * 30 + a[..., 1] * 59 + a[..., 2] * 11) / 100.0
    sat = a.max(2) - a.min(2)
    fg = ndimage.binary_opening(~((lum > 200) & (sat < 16)), iterations=1)
    lab, n = ndimage.label(ndimage.binary_dilation(fg, iterations=1))
    objs = ndimage.find_objects(lab)
    sizes = ndimage.sum(fg, lab, range(1, n + 1))
    items = [((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop), i + 1) for i, sl in enumerate(objs) if sizes[i] >= 120]
    items.sort(key=lambda it: (it[0][1] + it[0][3]) / 2.0)
    rows = []
    for it in items:
        cy = (it[0][1] + it[0][3]) / 2.0
        if rows and abs(cy - rows[-1][0]) < 45:
            rows[-1][1].append(it)
            rows[-1][0] = (rows[-1][0] * (len(rows[-1][1]) - 1) + cy) / len(rows[-1][1])
        else:
            rows.append([cy, [it]])
    out = []
    for _, r in rows:
        for box, k in sorted(r, key=lambda it: it[0][0]):
            out.append((box, (lab == k) & fg))
    return out


def save_piece(im, mask, box, name, scale, anchors, blocks, pal):
    import numpy as np
    x0, y0, x1, y1 = box
    alpha = Image.fromarray((mask[y0:y1, x0:x1] * 255).astype("uint8"))
    piece = im.crop(box).convert("RGBA")
    piece.putalpha(alpha)
    w, h = max(1, int(piece.width * scale)), max(1, int(piece.height * scale))
    piece = piece.resize((w, h), Image.LANCZOS)
    a = piece.split()[3].point(lambda v: 255 if v > 120 else 0)
    piece.putalpha(a)
    piece = to_palette(piece.crop(a.getbbox() or (0, 0, w, h)), pal)
    piece.save(os.path.join(OUT, name + ".png"))
    W, H = piece.size
    if is_flat(name):
        anchors[name] = [W // 2, H // 2]
        blocks[name] = 0
    else:                               # the middle of its footprint (a diamond about half as deep as wide)
        anchors[name] = [W // 2, max(0, H - int(min(W * 0.24, H * 0.45)))]
        blocks[name] = max(1, int(round(W / 45.0)))


def cut_many(sheet, names, splits, big, scale, anchors, blocks, pal):
    f = os.path.join(SRC, sheet)
    if not os.path.exists(f):
        return
    im = Image.open(f).convert("RGB")
    pieces = blobs(im)
    if len(pieces) != len(names):
        print("%s: %d pieces, %d names - not cut" % (sheet, len(pieces), len(names)))
        return
    for i, ((box, mask), name) in enumerate(zip(pieces, names)):
        if name is None:
            continue
        parts = [(box, mask, name)]
        if isinstance(name, tuple):
            sx = splits[i]
            left, right = mask.copy(), mask.copy()
            left[:, sx:] = False
            right[:, :sx] = False
            parts = [((box[0], box[1], sx, box[3]), left, name[0]), ((sx, box[1], box[2], box[3]), right, name[1])]
        for b, m, nm in parts:
            save_piece(im, m, b, nm, SCALE_BIG if nm in big else scale, anchors, blocks, pal)
            print("cut", nm)


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


def to_palette(piece, pal):
    """D2's look: a little less saturated and darker (the game's art is low key, lit by torches),
    then every pixel snapped to the act's 256 colours. The alpha is kept as it is."""
    if not pal:
        return piece
    import numpy as np
    a = piece.split()[3]
    rgb = np.asarray(piece.convert("RGB"), dtype=np.float32)
    grey = rgb.mean(axis=2, keepdims=True)
    red = (rgb[..., :1] > rgb[..., 1:2] * 1.6) & (rgb[..., :1] > 60)   # blood and cloth keep their red
    rgb = grey + (rgb - grey) * np.where(red, 1.0, 0.72)  # desaturate
    rgb = rgb * 0.82 + np.array([4.0, 2.0, 0.0])         # darker, a touch warm (torch light)
    rgb = 255.0 * (np.clip(rgb, 0, 255) / 255.0) ** 1.12  # deeper shadows
    img = Image.fromarray(np.clip(rgb, 0, 255).astype("uint8"), "RGB")
    flat = []
    for c in pal[1:256]:                                 # 0 is D2's transparent black
        flat += list(c[:3])
    flat += flat[:3] * (256 - len(flat) // 3)
    pimg = Image.new("P", (1, 1))
    pimg.putpalette(flat)
    out = img.quantize(palette=pimg, dither=Image.Dither.NONE).convert("RGBA")
    out.putalpha(a)
    return out


def save(im, alpha, box, name, scale, anchors, pal=None):
    x0, y0, x1, y1 = box
    piece = im.crop(box).convert("RGBA")
    piece.putalpha(alpha.crop(box))
    w, h = max(1, int(piece.width * scale)), max(1, int(piece.height * scale))
    piece = piece.resize((w, h), Image.LANCZOS)
    a = piece.split()[3].point(lambda v: 255 if v > 120 else 0)
    piece.putalpha(a)
    bb = a.getbbox() or (0, 0, w, h)
    piece = to_palette(piece.crop(bb), pal)
    piece.save(os.path.join(OUT, name + ".png"))
    # the ground point: under the middle, a little up from the lowest pixel (the footprint's centre)
    anchors[name] = [piece.width // 2, max(0, piece.height - min(28, int(piece.height * 0.16)))]


def load_pal(d2_path):
    if not d2_path:
        return None
    import sys
    sys.path.insert(0, ROOT)
    from d2.source import open_source
    from d2.palette import load_palette
    return load_palette(open_source(d2_path).read("data\\global\\palette\\act3\\pal.dat"))


def main(d2_path=""):
    pal = load_pal(d2_path)
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
                save(im, alpha, box, name, scale, anchors, pal)
                print("cut", name)
    bpath = os.path.join(OUT, "blocks.json")
    blocks = json.load(open(bpath)) if os.path.exists(bpath) else {}
    cut_many("sheet3.png", SHEET3, SPLIT3, BIG3, SCALE3, anchors, blocks, pal)
    cut_many("sheet4.png", SHEET4, {}, set(), SCALE4, anchors, blocks, pal)
    with open(path, "w") as fh:
        json.dump(anchors, fh, indent=1)
    with open(bpath, "w") as fh:
        json.dump(blocks, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "")
