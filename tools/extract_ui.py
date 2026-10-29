"""Pull D2's interface graphics (data\\global\\ui\\...: panels, menus, quest log, waypoint list,
cursors, fonts used by the panels) out of your Diablo II install - a few MB - so the
quest log and other panels can be laid out exactly like D2's.

    py tools\\extract_ui.py ["C:\\GOG Games\\Diablo II"]

Writes d2ui.zip next to the game. Upload it in the chat.
"""
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from d2.source import open_source  # noqa: E402
from extract_tables import find_path  # noqa: E402

# D2's menu files (not all are in every archive's file list)
KNOWN = ["questbackground", "questdone", "questlast", "questsockets", "expquesttabs", "waygatebackground",
         "waygateicons", "expwaygatetabs", "waygatetabs", "questtabs", "scroll", "recipescroll"] + \
        ["a%dq%d" % (a, q) for a in range(1, 6) for q in range(1, 7)]


def main():
    path = find_path()
    if not os.path.isdir(path):
        print("Folder not found:", path)
        return 1
    src = open_source(path, print, os.path.join(ROOT, "cache", "mpq"))
    names = set("data\\global\\ui\\MENU\\%s.dc6" % n for n in KNOWN)
    for _, a in getattr(src, "archives", []):
        try:
            for line in a.read("(listfile)").decode("latin-1").splitlines():
                low = line.strip().lower()
                if low.startswith("data\\global\\ui\\") and low.endswith((".dc6", ".dat", ".pl2")):
                    names.add(line.strip())
        except Exception:
            pass
    zp = os.path.join(ROOT, "d2ui.zip")
    n = 0
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(names, key=str.lower):
            try:
                if not src.has(name):
                    continue
                z.writestr("d2ui/files/" + name.replace("\\", "/").lower(), src.read(name))
                n += 1
            except Exception:
                pass
    print("%d files -> %s (%.1f MB). Upload it in the chat." % (n, zp, os.path.getsize(zp) / 1048576.0))
    return 0


if __name__ == "__main__":
    code = main()
    if os.name == "nt":
        input("\nPress Enter to close...")
    sys.exit(code)
