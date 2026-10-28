"""Pull every monster's animations out of your Diablo II files - every normal monster, boss,
super unique (they use their base monster's art), all five acts - so they can be checked.

    py tools\\extract_monsters.py ["C:\\GOG Games\\Diablo II"] [--no-files] [--no-sheets]

Writes, next to the game:
  d2monsters_check.zip     report.txt + picture sheets of every monster drawn the way the game
                           draws them (small - upload this first)
  d2monsters_partN.zip     the monster files themselves (COF/DCC + their missiles), split into
                           parts of about 40 MB so each can be uploaded

The game itself always reads straight from your MPQs; this is only for checking.
Nothing is sent anywhere - you decide what to upload.
"""
import configparser
import os
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from d2.source import open_source, read_table  # noqa: E402
from d2.cof import COF  # noqa: E402

OUT = os.path.join(ROOT, "d2monsters")
PART_MB = 40
MODES = ["NU", "WL", "A1", "A2", "GH", "DT", "DD", "SC", "S1", "S2", "S3", "S4", "BL", "KB", "RN", "SQ"]
NEEDED = ["NU", "WL", "A1", "GH"]
COMPONENTS = ["HD", "TR", "LG", "RA", "LA", "RH", "LH", "SH", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
SHEET_COLS, SHEET_ROWS, CELL_W, CELL_H = 8, 5, 160, 190


def find_path():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        return args[0]
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(ROOT, "settings.ini"))
    p = cfg.get("diablo2", "path", fallback="").strip()
    if p:
        return p
    return input("Path to your Diablo II folder: ").strip().strip('"')


def variants(ms2, comp):
    v = (ms2.get(comp.lower() + "v") or "").replace('"', "")
    return [x.strip().upper() for x in v.split(",") if x.strip() and x.strip() != "0"]


class MonsterFiles:
    def __init__(self, src):
        self.src = src
        self.files = {}           # path -> bytes
        self.missing = []

    def take(self, path):
        key = path.lower()
        if key in self.files:
            return self.files[key]
        if not self.src.has(path):
            return None
        try:
            data = self.src.read(path)
        except Exception:
            self.missing.append(path + " (unreadable)")
            return None
        self.files[key] = data
        return data

    def token(self, tok, wclasses, armtypes):
        """Every COF of a monster token and the DCCs its layers use. -> {mode: [wclass found]}"""
        found = {}
        base = "data\\global\\monsters\\%s\\" % tok.lower()
        for mode in MODES:
            for wc in wclasses:
                data = self.take(base + "cof\\%s%s%s.cof" % (tok, mode, wc))
                if data is None:
                    continue
                found.setdefault(mode, []).append(wc)
                try:
                    cof = COF(data)
                except Exception:
                    continue
                for L in cof.layers:
                    comp = L.component
                    lwc = L.weapon_class or wc
                    for arm in armtypes.get(comp, []) + ["LIT", "MED", "HVY"]:
                        self.take(base + "%s\\%s%s%s%s%s.dcc" % (comp, tok, comp, arm, mode, lwc))
        return found


def missile_files(mf, src):
    """Monster missiles (Missiles.txt CelFile + explosions) for every missile a monster uses."""
    try:
        rows = {r.get("missile", "").lower(): r for r in read_table(src, "Missiles")}
    except Exception:
        return 0
    try:
        mons = read_table(src, "MonStats")
    except Exception:
        return 0
    names = set()
    for r in mons:
        for col in ("missa1", "missa2", "misss1", "misss2", "misss3", "misss4", "missc", "missdd", "misssq"):
            v = (r.get(col) or "").strip().lower()
            if v:
                names.add(v)
    n = 0
    seen = set()
    todo = list(names)
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        seen.add(name)
        r = rows.get(name)
        if not r:
            continue
        cel = (r.get("celfile") or "").strip()
        if cel and mf.take("data\\global\\missiles\\%s.dcc" % cel) is not None:
            n += 1
        for col in ("explosionmissile", "submissile1", "submissile2", "submissile3", "cltsubmissile1",
                    "cltsubmissile2", "cltsubmissile3", "hitsubmissile1", "clthitsubmissile1"):
            v = (r.get(col) or "").strip().lower()
            if v:
                todo.append(v)
    return n


def write_parts(files):
    """d2monsters/files/... and zips of about PART_MB each."""
    for f in os.listdir(ROOT):
        if f.startswith("d2monsters_part") and f.endswith(".zip"):
            os.remove(os.path.join(ROOT, f))
    parts = []
    cur, size = [], 0
    for path in sorted(files):
        data = files[path]
        if cur and size + len(data) > PART_MB * 1024 * 1024:
            parts.append(cur)
            cur, size = [], 0
        cur.append(path)
        size += len(data)
    if cur:
        parts.append(cur)
    names = []
    for i, part in enumerate(parts, 1):
        zp = os.path.join(ROOT, "d2monsters_part%d.zip" % i)
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for path in part:
                z.writestr("d2monsters/files/" + path.replace("\\", "/"), files[path])
        names.append((zp, os.path.getsize(zp) / 1024.0 / 1024.0, len(part)))
    return names


def render_sheets(src, entries, out_dir):
    """Picture sheets: every monster standing (and its first attack frame) as the game draws it."""
    try:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        pygame.init()
        pygame.display.set_mode((1, 1))
        from d2.palette import load_palette
        from render.d2assets import UnitSprites
    except Exception as e:
        print("  pictures skipped (%s)" % e)
        return []

    class Lite:
        pass
    lite = Lite()
    lite.src = src
    lite.palette = load_palette(src.read("data\\global\\palette\\act1\\pal.dat"))

    def indexed_surface(w, h, pixels):
        s = pygame.image.frombuffer(bytes(pixels), (w, h), "P")
        s.set_palette(lite.palette)
        s.set_colorkey(0)
        o = pygame.Surface((w, h), pygame.SRCALPHA)
        o.fill((0, 0, 0, 0))
        o.blit(s, (0, 0))
        return o
    lite.indexed_surface = indexed_surface
    font = pygame.font.SysFont("arial,helvetica,sans", 11)
    per = SHEET_COLS * SHEET_ROWS
    paths = []
    for si in range(0, len(entries), per):
        sheet = pygame.Surface((SHEET_COLS * CELL_W, SHEET_ROWS * CELL_H))
        sheet.fill((24, 22, 20))
        for j, e in enumerate(entries[si:si + per]):
            cx, cy = (j % SHEET_COLS) * CELL_W, (j // SHEET_COLS) * CELL_H
            pygame.draw.rect(sheet, (60, 55, 45), (cx, cy, CELL_W, CELL_H), 1)
            ok_modes = []
            for mode, fx in (("NU", cx + CELL_W * 0.32), ("A1", cx + CELL_W * 0.72)):
                try:
                    us = UnitSprites(lite, "monsters", e["token"], e["arms"], e["wclass"])
                    frames = us.frames(mode, (1, 1))
                except Exception:
                    frames = None
                if frames:
                    img, x0, y0 = frames[len(frames) // 3 if mode == "A1" else 0]
                    if img is not None:
                        k = min(1.0, (CELL_H - 44) / float(max(1, img.get_height())),
                                (CELL_W / 2 - 4) / float(max(1, img.get_width())))
                        if k < 1.0:
                            img = pygame.transform.smoothscale(img, (max(1, int(img.get_width() * k)),
                                                                     max(1, int(img.get_height() * k))))
                        sheet.blit(img, (int(fx - img.get_width() / 2), int(cy + CELL_H - 40 - img.get_height())))
                        ok_modes.append(mode)
            col = (230, 220, 190) if ok_modes else (255, 90, 70)
            lines = ["%s  [%s %s]" % (e["id"], e["token"], e["wclass"]), e["name"][:26],
                     "OK" if len(ok_modes) == 2 else ("missing " + ",".join(m for m in ("NU", "A1") if m not in ok_modes))]
            for li, t in enumerate(lines):
                sheet.blit(font.render(t, True, col if li != 1 else (199, 179, 119)), (cx + 4, cy + CELL_H - 38 + li * 12))
        p = os.path.join(out_dir, "monsters_%02d.png" % (si // per + 1))
        pygame.image.save(sheet, p)
        paths.append(p)
    return paths


def main():
    path = find_path()
    if not os.path.isdir(path):
        print("Folder not found:", path)
        return 1
    t0 = time.time()
    print("Opening", path)
    src = open_source(path, print, os.path.join(ROOT, "cache", "mpq"))
    mons = read_table(src, "MonStats")
    ms2 = {r.get("id", "").lower(): r for r in read_table(src, "MonStats2")}
    try:
        from d2.strings import Strings
        strings = Strings(src)
    except Exception:
        strings = None
    try:
        supers = read_table(src, "SuperUniques")
    except Exception:
        supers = []
    mf = MonsterFiles(src)
    for t in ("MonStats", "MonStats2", "SuperUniques", "MonUMod", "MonProp", "MonLvl", "Missiles", "MonMode"):
        mf.take("data\\global\\excel\\%s.txt" % t)
    mf.take("data\\global\\palette\\act1\\pal.dat")

    # every monster row -> its look (token, weapon class, armour variants)
    entries = []
    by_token = {}
    for r in mons:
        mid = (r.get("id") or "").strip()
        tok = (r.get("code") or "").strip().upper()
        if not mid or not tok or tok == "NONE":          # XX = the Minions of Destruction (dummies just have no files)
            continue
        m2 = ms2.get((r.get("monstatsex") or mid).lower(), {})
        wc = ((m2.get("basew") or "hth").replace('"', "").strip() or "hth").upper()
        arms = {c: variants(m2, c) for c in COMPONENTS}
        key = r.get("namestr") or ""
        name = key
        if strings is not None:
            try:
                name = strings.get(key) or key
            except Exception:
                pass
        e = dict(id=mid, token=tok, wclass=wc, arms=arms, name=name or mid,
                 boss=r.get("boss") == "1", npc=r.get("npc") == "1", size=m2.get("sizex", ""))
        entries.append(e)
        t = by_token.setdefault(tok, {"wclasses": {"HTH"}, "arms": {}, "ids": []})
        t["wclasses"].add(wc)
        t["ids"].append(mid)
        for c, vs in arms.items():
            lst = t["arms"].setdefault(c, [])
            for v in vs:
                if v not in lst:
                    lst.append(v)
    print("%d monster rows, %d different looks (tokens)" % (len(entries), len(by_token)))

    found = {}
    for i, (tok, t) in enumerate(sorted(by_token.items()), 1):
        found[tok] = mf.token(tok, sorted(t["wclasses"]), t["arms"])
        if i % 25 == 0:
            print("  %d / %d tokens, %d files, %.0f MB" % (i, len(by_token), len(mf.files),
                                                          sum(len(v) for v in mf.files.values()) / 1048576.0))
    nm = missile_files(mf, src)
    print("Monster missiles: %d" % nm)

    # report
    lines = ["D2 Tactics monster sprite check", "source: " + path, ""]
    bad = 0
    for e in entries:
        f = found.get(e["token"], {})
        have = [m for m in NEEDED if e["wclass"] in f.get(m, []) or "HTH" in f.get(m, [])]
        own = [m for m in NEEDED if e["wclass"] in f.get(m, [])]
        miss = [m for m in NEEDED if m not in have]
        dead = "DT" in f or "DD" in f
        tag = "OK " if not miss else "!! "
        note = ""
        if not miss and len(own) < len(NEEDED):
            tag = "~  "
            note = "  (no %s files for %s - drawn bare-handed)" % (e["wclass"], ",".join(m for m in NEEDED if m not in own))
        if miss:
            bad += 1
        lines.append("%s%-18s %-3s %-4s size %-2s %-28s modes %s%s%s%s" % (
            tag, e["id"], e["token"], e["wclass"], e["size"], e["name"][:28],
            ",".join(sorted(f)), ("  MISSING " + ",".join(miss)) if miss else "", note,
            "" if dead else "  (no death anim)"))
    lines.append("")
    lines.append("Super uniques (they use their base monster's art):")
    for s in supers:
        lines.append("  %-28s base %s" % (s.get("name") or s.get("superunique", ""), s.get("class", "")))
    lines.insert(2, "%d of %d monsters are missing a standing / walking / attacking / hit animation" % (bad, len(entries)))
    os.makedirs(OUT, exist_ok=True)
    rep = os.path.join(OUT, "report.txt")
    with open(rep, "w") as fh:
        fh.write("\n".join(lines))
    print("Report:", rep)

    check_files = [rep]
    if "--no-sheets" not in sys.argv:
        print("Drawing every monster (this takes a minute)...")
        sheet_dir = os.path.join(OUT, "sheets")
        os.makedirs(sheet_dir, exist_ok=True)
        check_files += render_sheets(src, [e for e in entries if not e["npc"]] + [e for e in entries if e["npc"]],
                                     sheet_dir)
    cz = os.path.join(ROOT, "d2monsters_check.zip")
    with zipfile.ZipFile(cz, "w", zipfile.ZIP_DEFLATED) as z:
        for p in check_files:
            z.write(p, os.path.relpath(p, ROOT))
    print("\nCheck file: %s (%.1f MB) - upload this one first." % (cz, os.path.getsize(cz) / 1048576.0))

    if "--no-files" not in sys.argv:
        total = sum(len(v) for v in mf.files.values()) / 1048576.0
        print("Packing %d monster files (%.0f MB)..." % (len(mf.files), total))
        for zp, mb, n in write_parts(mf.files):
            print("  %s  %.1f MB  (%d files)" % (zp, mb, n))
        print("Upload the parts too if I ask for them.")
    print("Took %.0f seconds." % (time.time() - t0))
    return 0


if __name__ == "__main__":
    code = main()
    if os.name == "nt":
        input("\nPress Enter to close...")
    sys.exit(code)
