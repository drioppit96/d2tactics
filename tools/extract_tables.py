"""Pull every data table (data\\global\\excel\\*.txt) out of your Diablo II install - small
(a few MB). Needed e.g. for obj.txt, which tells what the objects placed in the map pieces are.

    py tools\\extract_tables.py ["C:\\GOG Games\\Diablo II"]

Writes d2tables.zip next to the game.
"""
import configparser
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from d2.source import open_source  # noqa: E402

KNOWN = ["Arena", "ArmType", "Armor", "AutoMagic", "AutoMap", "BodyLocs", "Books", "CharStats", "CharTemplate",
         "Colors", "CompCode", "Composit", "CubeMain", "CubeMod", "DifficultyLevels", "ElemTypes", "Events",
         "Experience", "Gamble", "Gems", "HireDesc", "Hireling", "HitClass", "Inventory", "ItemRatio",
         "ItemStatCost", "ItemTypes", "Levels", "LowQualityItems", "LvlMaze", "LvlPrest", "LvlSub", "LvlTypes",
         "LvlWarp", "MagicPrefix", "MagicSuffix", "Misc", "MissCalc", "Missiles", "MonAI", "MonEquip", "MonItemPercent",
         "MonLvl", "MonMode", "MonPlace", "MonPreset", "MonProp", "MonSeq", "MonSounds", "MonStats", "MonStats2",
         "MonType", "MonUMod", "Npc", "Obj", "ObjGroup", "ObjMode", "ObjType", "Objects", "Overlay", "PetType",
         "PlayerClass", "PlrMode", "PlrType", "Properties", "QualityItems", "RarePrefix", "RareSuffix", "Runes",
         "SetItems", "Sets", "Shrines", "SkillCalc", "SkillDesc", "Skills", "SoundEnviron", "Sounds", "States",
         "StorePage", "SuperUniques", "TreasureClass", "TreasureClassEx", "UniqueAppellation", "UniqueItems",
         "UniquePrefix", "UniqueSuffix", "UniqueTitle", "WanderingMon", "Weapons"]


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
    src = open_source(path, print, os.path.join(ROOT, "cache", "mpq"))
    names = set("data\\global\\excel\\%s.txt" % n for n in KNOWN)
    # plus anything else the archives' file lists name in the excel folder
    for _, a in getattr(src, "archives", []):
        try:
            for line in a.read("(listfile)").decode("latin-1").splitlines():
                low = line.strip().lower()
                if low.startswith("data\\global\\excel\\") and low.endswith(".txt"):
                    names.add(line.strip())
        except Exception:
            pass
    zp = os.path.join(ROOT, "d2tables.zip")
    n = 0
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(names, key=str.lower):
            if not src.has(name):
                continue
            try:
                z.writestr("d2tables/files/" + name.replace("\\", "/").lower(), src.read(name))
                n += 1
            except Exception:
                pass
    print("%d tables -> %s (%.1f MB). Upload it in the chat." % (n, zp, os.path.getsize(zp) / 1048576.0))
    return 0


if __name__ == "__main__":
    code = main()
    if os.name == "nt":
        input("\nPress Enter to close...")
    sys.exit(code)
