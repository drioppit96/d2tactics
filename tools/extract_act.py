"""Pull one act's map files out of your Diablo II install so the act can be built and checked:
every room / area layout (DS1) the act's levels use, every tile library (DT1) they need, the
act's palette, its objects (doors, chests, waypoints, quest objects) and the tables.

    py tools\\extract_act.py --act 2 ["C:\\GOG Games\\Diablo II"] [--no-objects]

(The object animations of all acts come with every pack unless --no-objects is given; the
Act 3-5 batch files leave them out because the Act 2 pack already has them.)

Writes d2act<N>_part1.zip, part2 ... (about 40 MB each) next to the game. The game itself always
reads straight from your MPQs; this is only so the levels can be built and tested.
"""
import configparser
import os
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from d2.source import open_source, read_table  # noqa: E402

PART_MB = 40
TABLES = ["Levels", "LvlPrest", "LvlTypes", "LvlMaze", "LvlSub", "LvlWarp", "MonPreset", "Objects", "ObjMode",
          "ObjType", "ObjGroup", "AutoMap", "SuperUniques", "MonStats", "MonStats2", "TreasureClassEx", "Npc",
          "Weapons", "Armor", "Misc", "ItemTypes", "Missiles", "Sounds", "States", "Overlay"]


def find_path():
    args = [a for a in sys.argv[1:] if not a.startswith("--") and not a.isdigit()]
    if args:
        return args[0]
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(ROOT, "settings.ini"))
    p = cfg.get("diablo2", "path", fallback="").strip()
    if p:
        return p
    return input("Path to your Diablo II folder: ").strip().strip('"')


def act_number():
    for i, a in enumerate(sys.argv):
        if a == "--act" and i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
        if a.startswith("--act="):
            return int(a.split("=", 1)[1])
    return 2


def norm(p):
    p = p.replace("/", "\\").lstrip("\\")
    if p.lower().startswith("d2\\"):
        p = p[3:]
    return p


class Grabber:
    def __init__(self, src):
        self.src = src
        self.files = {}
        self.missing = []

    def take(self, path):
        path = norm(path)
        key = path.lower()
        if key in self.files:
            return self.files[key]
        if not self.src.has(path):
            self.missing.append(path)
            return None
        try:
            data = self.src.read(path)
        except Exception:
            self.missing.append(path + " (unreadable)")
            return None
        self.files[key] = data
        return data


def main():
    act = act_number()
    path = find_path()
    if not os.path.isdir(path):
        print("Folder not found:", path)
        return 1
    t0 = time.time()
    print("Opening", path)
    src = open_source(path, print, os.path.join(ROOT, "cache", "mpq"))
    gr = Grabber(src)
    for t in TABLES:
        gr.take("data\\global\\excel\\%s.txt" % t)
    levels = read_table(src, "Levels")
    act_levels = [r for r in levels if (r.get("act") or "").strip() == str(act - 1) and (r.get("id") or "").isdigit()]
    ids = {int(r["id"]) for r in act_levels}
    print("Act %d: %d levels" % (act, len(ids)))
    lvltypes = {}
    for r in read_table(src, "LvlTypes"):
        lvltypes[(r.get("name") or "").strip()] = [v for k, v in r.items() if k.startswith("file") and v and v != "0"]
    type_by_id = {}
    for r in read_table(src, "LvlTypes"):
        if (r.get("id") or "").isdigit():
            type_by_id[int(r["id"])] = (r.get("name") or "").strip()
    # DS1 layouts: every LvlPrest row of the act's levels (+ the act's own folder)
    ds1s = []
    for r in read_table(src, "LvlPrest"):
        try:
            lid = int(r.get("levelid") or 0)
        except ValueError:
            lid = 0
        name = (r.get("name") or "").lower()
        if lid in ids or name.startswith("act %d" % act):
            for k in ("file1", "file2", "file3", "file4", "file5", "file6"):
                v = (r.get(k) or "").strip()
                if v and v != "0":
                    ds1s.append("data\\global\\tiles\\" + v)
    print("Room / area layouts listed: %d" % len(ds1s))
    from d2.ds1 import DS1
    dt1s = set()
    n_ds1 = 0
    for p in ds1s:
        data = gr.take(p)
        if data is None:
            continue
        n_ds1 += 1
        try:
            ds = DS1(data, p.rsplit("\\", 1)[-1])
            for f in ds.files:
                dt1s.add(norm(f).rsplit(".", 1)[0] + ".dt1")
        except Exception:
            pass
    # tile libraries: LvlTypes of the act's levels + every DT1 a layout names
    for r in act_levels:
        try:
            tname = type_by_id.get(int(r.get("leveltype") or 0), "")
        except ValueError:
            tname = ""
        for f in lvltypes.get(tname, []):
            dt1s.add("data\\global\\tiles\\" + f.replace("/", "\\"))
    for tname, files in lvltypes.items():
        if tname.lower().startswith("act %d" % act):
            for f in files:
                dt1s.add("data\\global\\tiles\\" + f.replace("/", "\\"))
    n_dt1 = sum(1 for p in sorted(dt1s) if gr.take(p) is not None)
    print("Layouts: %d   tile libraries: %d" % (n_ds1, n_dt1))
    for name in ("act%d" % act, "units"):
        gr.take("data\\global\\palette\\%s\\pal.dat" % name)
    # objects of the act (doors, chests, waypoints, shrines, quest objects): Objects.txt tokens
    tokens = set()
    try:
        for r in read_table(src, "Objects"):
            tok = (r.get("token") or "").strip()
            if tok and len(tok) == 2:
                tokens.add(tok)
    except Exception:
        pass
    n_obj = 0
    if "--no-objects" in sys.argv:
        tokens = set()          # every act's objects already came with the Act 2 pack
    for tok in sorted(tokens):
        for mode in ("NU", "OP", "ON", "S1", "S2", "S3", "S4", "S5"):
            cof = "data\\global\\objects\\%s\\COF\\%s%sHTH.cof" % (tok, tok, mode)
            if gr.take(cof) is None:
                continue
            n_obj += 1
            for comp in ("TR", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "LG", "HD"):
                gr.take("data\\global\\objects\\%s\\%s\\%s%sLIT%sHTH.dcc" % (tok, comp, tok, comp, mode))
    print("Object animations: %d" % n_obj)
    total = sum(len(v) for v in gr.files.values()) / 1048576.0
    print("Packing %d files (%.0f MB)..." % (len(gr.files), total))
    for f in os.listdir(ROOT):
        if f.startswith("d2act%d_part" % act) and f.endswith(".zip"):
            os.remove(os.path.join(ROOT, f))
    parts, cur, size = [], [], 0
    for key in sorted(gr.files):
        n = len(gr.files[key])
        if cur and size + n > PART_MB * 1024 * 1024:
            parts.append(cur)
            cur, size = [], 0
        cur.append(key)
        size += n
    if cur:
        parts.append(cur)
    for i, part in enumerate(parts, 1):
        zp = os.path.join(ROOT, "d2act%d_part%d.zip" % (act, i))
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for key in part:
                z.writestr("d2act%d/files/%s" % (act, key.replace("\\", "/")), gr.files[key])
            if i == 1:
                z.writestr("d2act%d/missing.txt" % act, "\n".join(gr.missing))
        print("  %s  %.1f MB" % (zp, os.path.getsize(zp) / 1048576.0))
    print("Upload every part in the chat.  Took %.0f seconds." % (time.time() - t0))
    return 0


if __name__ == "__main__":
    code = main()
    if os.name == "nt":
        input("\nPress Enter to close...")
    sys.exit(code)
