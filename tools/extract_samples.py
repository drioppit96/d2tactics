"""Pull a small set of sample files out of your Diablo 2 MPQs into d2samples.zip.

Usage (from the d2tactics folder):
    py tools\\extract_samples.py "C:\\Program Files (x86)\\Diablo II"

If you leave the path out, it uses [diablo2] path from settings.ini, or asks.

The zip contains a palette, Act 1 cave + town tiles, Barbarian and monster
animations, item icons, a few sounds and the game's data tables - only what's
needed to build and test the loader. Every file is saved twice: decoded (if this
script could decompress it) and as the raw stored block, so nothing is lost if a
format turns out different than expected.
"""
import configparser
import json
import os
import sys
import time
import traceback
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from d2.mpq import MPQSet  # noqa: E402

BATCH = 5 if "--batch5" in sys.argv else 4 if "--batch4" in sys.argv else 3 if "--batch3" in sys.argv else \
    2 if "--batch2" in sys.argv else 1
OUT = os.path.join(ROOT, {1: "d2samples", 2: "d2samples2", 3: "d2samples3", 4: "d2samples4", 5: "d2samples5"}[BATCH])
ZIP_PATH = OUT + ".zip"
BUDGET = {1: 45, 2: 30, 3: 40, 4: 45, 5: 45}[BATCH] * 1024 * 1024        # stay well under upload limits

COMPONENTS = ["HD", "TR", "LG", "RA", "LA", "RH", "LH", "SH",
              "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
MONSTER_IDS = ["zombie1", "fallen1", "fallenshaman1", "quillrat1", "skeleton1"]
MONSTER_MODES = ["NU", "WL", "A1", "GH", "DT", "DD", "SC", "A2"]
PLAYER_MODES = ["NU", "WL", "A1", "GH", "DT", "DD", "TN", "TW", "SC"]
PLAYER_CLASSES = ["HTH", "1HS"]
ITEM_CODES = ["clb", "hax", "ssd", "scm", "mac", "axe", "lsd", "cap", "skp", "qui", "lea",
              "hla", "lgl", "lbt", "rin", "amu", "hp1", "hp2", "gld", "buc"]
SOUND_PREFIXES = ["zombie", "fallen", "shaman", "quill", "barbarian", "player_", "item_",
                  "cursor", "gold", "potion", "weapon", "hit", "bash", "door"]
EXCEL = ["LvlTypes", "LvlPrest", "Levels", "LvlMaze", "LvlSub", "LvlWarp", "MonStats", "MonStats2",
         "MonLvl", "MonProp", "SuperUniques", "Weapons", "Armor", "Misc", "ItemTypes",
         "MagicPrefix", "MagicSuffix", "Skills", "SkillDesc", "CharStats", "Experience",
         "Sounds", "Missiles", "TreasureClassEx", "UniqueItems", "SetItems", "Runes",
         "MonSounds", "Overlay", "ObjMode", "Objects", "ItemStatCost", "Properties"]


class Extractor:
    def __init__(self, d2_path):
        print("Opening archives in", d2_path)
        self.mpq = MPQSet(d2_path)
        for name, a in self.mpq.archives:
            print("  %-14s %6d files" % (name, len([h for h in a.hash_table if h[4] < 0xFFFFFFFE])))
        self.total = 0
        self.manifest = []
        self.tried_missing = []
        self.done = set()
        self.tables = {}

    # ------------------------------------------------------------ saving
    def grab(self, name, required=False):
        """Save one file (decoded + raw). Returns decoded bytes or None."""
        name = name.replace("/", "\\").strip()
        key = name.lower()
        if key in self.done:
            return self._cached(key)
        an, arc = self.mpq.locate(name)
        if arc is None:
            self.tried_missing.append(name)
            if required:
                print("  missing:", name)
            return None
        if self.total > BUDGET:
            print("  size budget reached, skipping", name)
            return None
        self.done.add(key)
        rel = key.replace("\\", "/")
        raw, info = arc.read_raw(name)
        entry = {"name": name, "archive": an, "block": info}
        raw_path = os.path.join(OUT, "raw", rel + ".blk")
        os.makedirs(os.path.dirname(raw_path), exist_ok=True)
        with open(raw_path, "wb") as f:
            f.write(raw)
        self.total += len(raw)
        data = None
        try:
            data = arc.read(name)
            path = os.path.join(OUT, "files", rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            self.total += len(data)
            entry["decoded"] = len(data)
        except Exception as e:
            entry["error"] = "%s: %s" % (type(e).__name__, e)
        self.manifest.append(entry)
        return data

    def _cached(self, key):
        path = os.path.join(OUT, "files", key.replace("\\", "/"))
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
        return None

    # ------------------------------------------------------------ data tables
    def table(self, name):
        if name in self.tables:
            return self.tables[name]
        rows = []
        data = self.grab("data\\global\\excel\\%s.txt" % name)
        if data:
            lines = data.decode("latin-1").splitlines()
            if lines:
                header = lines[0].split("\t")
                for line in lines[1:]:
                    cells = line.split("\t")
                    rows.append({header[i].strip().lower(): (cells[i].strip() if i < len(cells) else "")
                                 for i in range(len(header))})
        self.tables[name] = rows
        return rows

    # ------------------------------------------------------------ steps
    def step_basics(self):
        print("Listfiles, palettes and data tables...")
        for _, a in self.mpq.archives:
            pass
        self.grab("(listfile)")
        for act in range(1, 6):
            self.grab("data\\global\\palette\\act%d\\pal.dat" % act, required=(act == 1))
            self.grab("data\\global\\palette\\act%d\\pal.pl2" % act)
        self.grab("data\\global\\palette\\units\\pal.dat")
        for t in EXCEL:
            self.table(t)
        found = sum(1 for t in EXCEL if self.tables.get(t))
        print("  %d of %d tables found" % (found, len(EXCEL)))

    def step_tiles(self):
        print("Act 1 tiles and level layouts...")
        n = 0
        for row in self.table("LvlTypes"):
            nm = row.get("name", "").lower()
            if nm in ("act 1 - town", "act 1 - cave", "act 1 - wilderness"):
                for k, v in row.items():
                    if k.startswith("file") and v and v != "0":
                        if self.grab("data\\global\\tiles\\" + v) is not None:
                            n += 1
        ds1 = 0
        for row in self.table("LvlPrest"):
            nm = row.get("name", "").lower()
            if not (nm.startswith("act 1 - town") or nm.startswith("act 1 - cave")):
                continue
            for k in ("file1", "file2", "file3", "file4", "file5", "file6"):
                v = row.get(k, "")
                if v and v != "0" and ds1 < 40:
                    if self.grab("data\\global\\tiles\\" + v) is not None:
                        ds1 += 1
        print("  %d tile files, %d layouts" % (n, ds1))

    def _unit(self, folder, token, modes, wclasses, armtypes_by_comp):
        got = 0
        for wc in wclasses:
            for mode in modes:
                cof_name = "data\\global\\%s\\%s\\COF\\%s%s%s.cof" % (folder, token, token, mode, wc)
                cof = self.grab(cof_name)
                if not cof or len(cof) < 28:
                    continue
                got += 1
                n_layers = cof[0]
                for i in range(n_layers):
                    off = 28 + i * 9
                    if off + 9 > len(cof):
                        break
                    comp_idx = cof[off]
                    if comp_idx >= len(COMPONENTS):
                        continue
                    comp = COMPONENTS[comp_idx]
                    lwc = cof[off + 5:off + 9].split(b"\0")[0].decode("latin-1") or wc
                    for arm in armtypes_by_comp.get(comp, ["LIT"]):
                        for ext in (".dcc", ".dc6"):
                            fn = "data\\global\\%s\\%s\\%s\\%s%s%s%s%s%s" % (
                                folder, token, comp, token, comp, arm.upper(), mode, lwc, ext)
                            if self.grab(fn) is not None:
                                got += 1
                                break
        return got

    def step_units(self):
        print("Monster and Barbarian animations...")
        stats = {r.get("id", "").lower(): r for r in self.table("MonStats")}
        stats2 = {r.get("id", "").lower(): r for r in self.table("MonStats2")}
        for mid in MONSTER_IDS:
            row = stats.get(mid)
            token = (row or {}).get("code", "")
            if not token:
                print("  no MonStats row for", mid)
                continue
            ex = stats2.get((row.get("monstatsex") or mid).lower(), {})
            arms = {}
            for comp in COMPONENTS:
                v = ex.get(comp.lower() + "v", "")
                vals = [x.strip() for x in v.replace('"', "").split(",") if x.strip() and x.strip() != "0"]
                arms[comp] = (vals or []) + [a for a in ("lit", "med", "hvy") if a not in vals]
            n = self._unit("monsters", token.upper(), MONSTER_MODES, ["HTH"], arms)
            print("  %-14s %-3s %3d files" % (mid, token, n))
        weapon_gfx = set()
        for t in ("Weapons", "Armor"):
            for r in self.table(t):
                if r.get("code", "").lower() in ITEM_CODES:
                    for col in ("alternategfx", "code"):
                        if r.get(col):
                            weapon_gfx.add(r[col].upper())
        arms = {c: ["LIT", "MED", "HVY"] for c in COMPONENTS}
        arms["RH"] = sorted(weapon_gfx) + ["LIT"]
        arms["LH"] = sorted(weapon_gfx) + ["LIT"]
        arms["SH"] = ["BUC", "LIT"]
        n = self._unit("chars", "BA", PLAYER_MODES, PLAYER_CLASSES, arms)
        print("  barbarian          %3d files" % n)

    def step_items(self):
        print("Item icons...")
        n = 0
        for t in ("Weapons", "Armor", "Misc"):
            for r in self.table(t):
                if r.get("code", "").lower() not in ITEM_CODES:
                    continue
                for col in ("invfile", "flippyfile", "uniqueinvfile", "setinvfile"):
                    v = r.get(col, "")
                    if v and v != "0":
                        if self.grab("data\\global\\items\\%s.dc6" % v) is not None:
                            n += 1
        for v in ("invgld1", "invgld2", "invgld3", "invgld4", "flpgld"):
            if self.grab("data\\global\\items\\%s.dc6" % v) is not None:
                n += 1
        print("  %d item graphics" % n)

    def step_missiles_ui(self):
        print("Missiles and UI bits...")
        n = 0
        for r in self.table("Missiles"):
            name = r.get("missile", "").lower()
            if any(k in name for k in ("shaman", "quill", "fire")) and n < 12:
                cel = r.get("celfile", "")
                if cel:
                    for ext in (".dcc", ".dc6"):
                        if self.grab("data\\global\\missiles\\%s%s" % (cel, ext)) is not None:
                            n += 1
                            break
        for f in ["data\\global\\ui\\PANEL\\800ctrlpnl7.dc6", "data\\global\\ui\\PANEL\\hlthmana.dc6",
                  "data\\global\\ui\\PANEL\\overlap.dc6", "data\\global\\ui\\PANEL\\level.dc6",
                  "data\\global\\ui\\PANEL\\invchar6.dc6", "data\\global\\ui\\PANEL\\inv_belt.dc6",
                  "data\\global\\ui\\CURSOR\\ohand.dc6", "data\\local\\font\\latin\\font16.dc6",
                  "data\\local\\font\\latin\\font16.tbl", "data\\local\\font\\latin\\font30.dc6",
                  "data\\local\\font\\latin\\font30.tbl", "data\\local\\font\\latin\\fontexocet10.dc6",
                  "data\\local\\font\\latin\\fontexocet10.tbl"]:
            if self.grab(f) is not None:
                n += 1
        print("  %d files" % n)

    def step_sounds(self):
        print("Sounds...")
        n = 0
        for r in self.table("Sounds"):
            nm = r.get("sound", "").lower()
            fn = r.get("filename", "")
            if fn and any(nm.startswith(p) for p in SOUND_PREFIXES) and n < 45:
                if self.grab("data\\global\\sfx\\" + fn) is not None:
                    n += 1
        print("  %d sounds" % n)

    # ------------------------------------------------------------ batch 2: the rest of Act 1
    def step2_listfiles(self):
        print("File lists...")
        self.known = set()
        for an, a in self.mpq.archives:
            try:
                data = a.read("(listfile)")
            except Exception:
                continue
            names = data.decode("latin-1").splitlines()
            self.known.update(n.strip() for n in names if n.strip())
            p = os.path.join(OUT, "listfiles", an + ".txt")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "wb") as f:
                f.write(data)
        print("  %d names known" % len(self.known))

    def _grab_pattern(self, prefix, limit_bytes, exts=None):
        start = self.total
        n = 0
        for name in sorted(self.known):
            low = name.lower()
            if low.startswith(prefix) and (exts is None or low.endswith(exts)):
                if self.total - start > limit_bytes:
                    break
                if self.grab(name) is not None:
                    n += 1
        return n

    def step2_monsters(self):
        print("Act 1 monsters, bosses and town NPCs (standing pose)...")
        stats = {r.get("id", "").lower(): r for r in self.table("MonStats")}
        stats2 = {r.get("id", "").lower(): r for r in self.table("MonStats2")}
        ids = set()
        for r in self.table("Levels"):
            if r.get("act") == "0":
                for k, v in r.items():
                    if k[:3] in ("mon", "nmo", "umo") and k[-1:].isdigit() and v:
                        ids.add(v.lower())
        # Act 1 bosses (Griswold, the Smith, Blood Raven, Andariel) and the town NPCs
        ids |= {"griswold", "smith", "bloodraven", "andariel", "akara", "charsi", "gheed", "kashya",
                "warriv1", "cain1", "rogue1"}
        done_tokens = {"ZM", "FA", "FS", "SI", "SK"}
        tokens = {}
        for i in sorted(ids):
            row = stats.get(i)
            if row and row.get("code") and row["code"].upper() not in done_tokens:
                tokens.setdefault(row["code"].upper(), row)
        for tok, row in sorted(tokens.items()):
            ex = stats2.get((row.get("monstatsex") or row.get("id", "")).lower(), {})
            arms = {}
            for comp in COMPONENTS:
                v = ex.get(comp.lower() + "v", "").replace('"', "")
                vals = [x.strip() for x in v.split(",") if x.strip() and x.strip() != "0"]
                arms[comp] = vals[:1] + [a for a in ("lit",) if a not in vals[:1]]
            modes = ["NU", "DT", "DD"] if len(tokens) > 20 else ["NU", "WL", "A1", "DT", "DD"]
            n = self._unit("monsters", tok, modes, ["HTH"], arms)
            print("  %-4s %-18s %3d files" % (tok, row.get("id", ""), n))

    def step2_objects(self):
        print("Objects (chests, barrels, shrines...)...")
        keys = ("chest", "barrel", "urn", "casket", "shrine", "torch", "waypoint", "door", "stone",
                "fire", "bonfire", "corpse", "body", "sarcophagus", "stash", "well", "gibbet", "banner")
        seen = 0
        for r in self.table("Objects"):
            name, tok = r.get("name", "").lower(), r.get("token", "").upper()
            if not tok or len(tok) > 3 or not any(k in name for k in keys) or seen >= 30:
                continue
            arms = {c: ["LIT"] for c in COMPONENTS}
            n = self._unit("objects", tok, ["NU", "OP", "ON"], ["HTH"], arms)
            if n:
                seen += 1
                print("  %-4s %-18s %3d files" % (tok, name, n))

    def step2_items(self):
        print("All item graphics...")
        n = 0
        for t in ("Weapons", "Armor", "Misc"):
            for r in self.table(t):
                for col in ("invfile", "flippyfile", "uniqueinvfile", "setinvfile"):
                    v = r.get(col, "")
                    if v and v != "0" and self.grab("data\\global\\items\\%s.dc6" % v) is not None:
                        n += 1
        for v in ("invgld1", "invgld2", "invgld3", "invgld4", "flpgld"):
            if self.grab("data\\global\\items\\%s.dc6" % v) is not None:
                n += 1
        for f in ("data\\global\\items\\Palette\\GreyBrown.dat", "data\\global\\monsters\\RandTransforms.dat",
                  "data\\global\\items\\palette\\invgreybrown.dat"):
            self.grab(f)
        print("  %d item graphics" % n)

    def step2_ui(self):
        print("Interface, fonts and cursors...")
        n = self._grab_pattern("data\\global\\ui\\panel\\", 6 * 1024 * 1024)
        n += self._grab_pattern("data\\global\\ui\\cursor\\", 1024 * 1024)
        n += self._grab_pattern("data\\local\\font\\latin\\", 3 * 1024 * 1024)
        for f in ["data\\global\\ui\\PANEL\\ctrlpnl7.dc6", "data\\global\\ui\\PANEL\\hlthmana.dc6",
                  "data\\global\\ui\\PANEL\\overlap.dc6", "data\\global\\ui\\PANEL\\invchar6.dc6",
                  "data\\global\\ui\\PANEL\\800ctrlpnl7.dc6", "data\\global\\ui\\CURSOR\\ohand.dc6",
                  "data\\local\\font\\latin\\font16.dc6", "data\\local\\font\\latin\\font16.tbl",
                  "data\\local\\font\\latin\\font8.dc6", "data\\local\\font\\latin\\font8.tbl",
                  "data\\local\\font\\latin\\font30.dc6", "data\\local\\font\\latin\\font30.tbl",
                  "data\\local\\font\\latin\\fontexocet10.dc6", "data\\local\\font\\latin\\fontexocet10.tbl"]:
            if self.grab(f) is not None:
                n += 1
        print("  %d files" % n)

    def step2_missiles_sounds(self):
        print("Missiles and a few sounds...")
        n = 0
        want = ("arrow", "shaman", "fire", "spike", "quill", "cold", "bolt", "blood", "poison")
        for r in self.table("Missiles"):
            name = r.get("missile", "").lower()
            cel = r.get("celfile", "")
            if cel and any(k in name for k in want) and n < 25:
                for ext in (".dcc", ".dc6"):
                    if self.grab("data\\global\\missiles\\%s%s" % (cel, ext)) is not None:
                        n += 1
                        break
        s = 0
        for r in self.table("Sounds"):
            nm = r.get("sound", "").lower()
            fn = r.get("filename", "")
            if fn and any(nm.startswith(p) for p in ("zombie", "fallen", "barbarian", "item_", "cursor")) and s < 15:
                if self.grab("data\\global\\sfx\\" + fn) is not None:
                    s += 1
        print("  %d missiles, %d sounds" % (n, s))

    # ------------------------------------------------------------ batch 3: skills, automap, strings, outdoor maps
    def step3_ui(self):
        print("Skill icons, skill trees, automap and string tables...")
        n = self._grab_pattern("data\\global\\ui\\spells\\", 12 * 1024 * 1024)
        n += self._grab_pattern("data\\global\\ui\\automap\\", 3 * 1024 * 1024)
        n += self._grab_pattern("data\\local\\ui\\eng\\automap", 1024 * 1024)
        for t in ("AutoMap", "LvlTypes", "LvlPrest", "Levels", "LvlMaze", "LvlSub", "LvlWarp", "Objects", "ObjGroup",
                  "MonPreset", "SuperUniques", "Skills", "SkillDesc", "Missiles", "Overlay", "States", "Sounds"):
            self.table(t)
        for f in ("data\\local\\lng\\eng\\string.tbl", "data\\local\\lng\\eng\\expansionstring.tbl",
                  "data\\local\\lng\\eng\\patchstring.tbl"):
            if self.grab(f) is not None:
                n += 1
        print("  %d files" % n)

    def step3_act1_maps(self):
        print("Act 1 outdoor and dungeon layouts...")
        n = self._grab_pattern("data\\global\\tiles\\act1\\", 10 * 1024 * 1024, exts=(".ds1",))
        print("  %d layouts" % n)
        tiles = 0
        wanted = set()
        for row in self.table("LvlTypes"):
            if row.get("name", "").lower().startswith("act 1"):
                for k, v in row.items():
                    if k.startswith("file") and v and v != "0":
                        wanted.add(v)
        for v in sorted(wanted):
            if self.total > BUDGET - 2 * 1024 * 1024:
                break
            if self.grab("data\\global\\tiles\\" + v) is not None:
                tiles += 1
        print("  %d tile libraries" % tiles)

    # ------------------------------------------------------------ batch 4: all classes + character creation
    CLASSES = ["AM", "SO", "NE", "PA", "BA", "DZ", "AI"]

    def step4_frontend(self):
        print("Character creation / select screens...")
        n = self._grab_pattern("data\\global\\ui\\frontend\\", 12 * 1024 * 1024)
        print("  %d files" % n)

    def step4_classes(self):
        print("All seven classes (standing, walking, attacking, hit, casting, dying)...")
        modes = ("NU", "WL", "A1", "GH", "SC", "DT", "DD", "TN")
        wclasses = ("HTH", "1HS")
        per_class = 4 * 1024 * 1024
        for cls in self.CLASSES:
            start = self.total
            n = 0
            prefix = "data\\global\\chars\\%s\\" % cls.lower()
            for name in sorted(self.known):
                low = name.lower()
                if not low.startswith(prefix) or self.total - start > per_class:
                    continue
                base = low.rsplit("\\", 1)[-1]
                stem = base.rsplit(".", 1)[0]
                if low.endswith(".cof"):
                    ok = stem[2:4].upper() in modes and stem[4:].upper() in wclasses
                elif low.endswith(".dcc"):
                    # <cls><comp><armtype><mode><wclass>: keep light armour + a few weapons
                    arm, mode, wc = stem[4:7].upper(), stem[7:9].upper(), stem[9:].upper()
                    ok = mode in modes and wc in wclasses and (arm in ("LIT", "HAX", "SSD", "BUC", "CLB", "SST", "WND", "KTR", "JAV", "SBW") )
                else:
                    ok = False
                if ok and self.grab(name) is not None:
                    n += 1
            print("  %s %4d files" % (cls, n))

    # ------------------------------------------------------------ batch 5: hero select art, palettes, objects
    FE_CLASSES = [("amazon", "am"), ("assassin", "as"), ("necromancer", "ne"), ("barbarian", "ba"),
                  ("paladin", "pa"), ("sorceress", "so"), ("druid", "dz")]

    def step5_frontend(self):
        print("Character creation: every hero, the campfire, the LoD background...")
        n = 0
        for f in ("charactercreationscreenEXP.dc6", "CharacterCreate.dc6", "fire.dc6", "TextBox2.dc6",
                  "MediumButtonBlank.dc6", "charactercreationscreenEXP.DC6", "Fire.DC6"):
            if self.grab("data\\global\\ui\\FrontEnd\\" + f) is not None:
                n += 1
        for folder, pre in self.FE_CLASSES:
            for suffix in ("nu1", "nu2", "nu3", "fw", "bw", "fws", "bws", "nu3s", "nu1s", "nu2s"):
                if self.grab("data\\global\\ui\\FrontEnd\\%s\\%s%s.dc6" % (folder, pre, suffix)) is not None:
                    n += 1
        print("  %d files" % n)

    def step5_palettes(self):
        print("All palettes...")
        n = 0
        for name in ("act1", "act2", "act3", "act4", "act5", "endgame", "endgame2", "fechar", "loading",
                     "menu0", "menu1", "menu2", "menu3", "menu4", "sky", "static", "trademark", "units"):
            for f in ("pal.dat", "Pal.PL2"):
                if self.grab("data\\global\\palette\\%s\\%s" % (name, f)) is not None:
                    n += 1
        print("  %d files" % n)

    def step5_objects(self):
        print("Quest objects and waypoints (Cairn Stones, Inifuss tree, Malus, cage, portals)...")
        n = 0
        tokens = ("S1", "S2", "S3", "S4", "S5", "S6", "IT", "TT", "HM", "GI", "PP", "TP", "WP", "WN", "W7")
        for tok in tokens:
            prefix = "data\\global\\objects\\%s\\" % tok.lower()
            for name in sorted(self.known):
                if name.lower().startswith(prefix) and self.grab(name) is not None:
                    n += 1
            for mode in ("NU", "OP", "ON"):
                cof = "data\\global\\objects\\%s\\COF\\%s%sHTH.cof" % (tok, tok, mode)
                if self.grab(cof) is not None:
                    n += 1
                for comp in ("TR", "S1", "S2", "S3", "LG", "HD"):
                    dcc = "data\\global\\objects\\%s\\%s\\%s%sLIT%sHTH.dcc" % (tok, comp, tok, comp, mode)
                    if self.grab(dcc) is not None:
                        n += 1
        print("  %d files" % n)

    def finish(self):
        with open(os.path.join(OUT, "manifest.json"), "w") as f:
            json.dump({"files": self.manifest, "missing": self.tried_missing[:3000],
                       "archives": [a for a, _ in self.mpq.archives]}, f, indent=1)
        errors = [e for e in self.manifest if "error" in e]
        print("\nSaved %d files (%d could not be decoded here - that's fine, raw copies are kept)."
              % (len(self.manifest), len(errors)))
        print("Zipping...")
        with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _, files in os.walk(OUT):
                for fn in files:
                    full = os.path.join(base, fn)
                    z.write(full, os.path.relpath(full, ROOT))
        mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
        print("\nDone: %s (%.1f MB)" % (ZIP_PATH, mb))
        print("Upload that zip in the chat.")


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


def main():
    path = find_path()
    if not os.path.isdir(path):
        print("Folder not found:", path)
        return 1
    t0 = time.time()
    ex = Extractor(path)
    if os.path.isdir(OUT):
        import shutil
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    log = []
    if BATCH == 1:
        steps = (ex.step_basics, ex.step_tiles, ex.step_units, ex.step_items, ex.step_missiles_ui, ex.step_sounds)
    elif BATCH == 2:
        steps = (ex.step2_listfiles, ex.step2_items, ex.step2_ui, ex.step2_missiles_sounds,
                 ex.step2_objects, ex.step2_monsters)
    elif BATCH == 3:
        steps = (ex.step2_listfiles, ex.step3_ui, ex.step3_act1_maps)
    elif BATCH == 4:
        steps = (ex.step2_listfiles, ex.step4_frontend, ex.step4_classes)
    else:
        steps = (ex.step2_listfiles, ex.step5_palettes, ex.step5_frontend, ex.step5_objects)
    for step in steps:
        try:
            step()
        except Exception:
            tb = traceback.format_exc()
            log.append(tb)
            print("  step failed (continuing):\n" + tb)
    with open(os.path.join(OUT, "errors.log"), "w") as f:
        f.write("\n".join(log))
    ex.finish()
    print("Took %.0f seconds." % (time.time() - t0))
    return 0


if __name__ == "__main__":
    code = main()
    if os.name == "nt":
        input("\nPress Enter to close...")
    sys.exit(code)
