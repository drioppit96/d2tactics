"""Set up (or refresh) the autobattler's own folder next to this one.

    python tools/install_autobattler.py                  -> ..\\Diablo 2 Auto battler
    python tools/install_autobattler.py "D:\\Some\\Path" -> that folder

The autobattler runs on the same engine as D2 Tactics, so the folder gets a copy of this game's
code. It has its own heroes (saves_auto), its own autobattler.ini and its own error log, and its
"Update D2 Autobattler.bat" keeps it up to date from GitHub on its own.

Copied: the code, the launchers, assets, docs, and settings.ini (only if the folder has none yet,
so it starts with the same Diablo II path). Also the decoded-art cache, if this folder has one,
so the first start is not slow.
Never copied: your D2 Tactics heroes (saves), .git, errors.log, extracted Diablo II files.
"""
import os
import shutil
import sys

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_NAME = "Diablo 2 Auto battler"

SKIP_DIRS = {".git", "saves", "saves_auto", "saves_test", "__pycache__", "d2monsters"}
SKIP_PREFIXES = ("d2samples", "d2act", "d2tables", "d2monsters")
SKIP_FILES = {"errors.log", "options.ini", "autobattler.ini", "github_token.txt", "numpy_skip.txt"}
ONLY_IF_MISSING = {"settings.ini"}


def _skip_dir(name):
    return name in SKIP_DIRS or name.lower().startswith(SKIP_PREFIXES)


def _skip_file(name):
    low = name.lower()
    return name in SKIP_FILES or low.endswith((".zip", ".pyc", ".mpq")) or low.startswith(SKIP_PREFIXES)


def install(dest):
    dest = os.path.abspath(dest)
    if os.path.normcase(dest) == os.path.normcase(SRC):
        raise SystemExit("The autobattler needs its own folder, not this one.")
    os.makedirs(dest, exist_ok=True)
    copied = 0
    for base, dirs, files in os.walk(SRC):
        rel = os.path.relpath(base, SRC)
        dirs[:] = [d for d in dirs if not _skip_dir(d)]
        out_dir = dest if rel == "." else os.path.join(dest, rel)
        os.makedirs(out_dir, exist_ok=True)
        for fn in files:
            if _skip_file(fn):
                continue
            target = os.path.join(out_dir, fn)
            if rel == "." and fn in ONLY_IF_MISSING and os.path.exists(target):
                continue
            shutil.copy2(os.path.join(base, fn), target)
            copied += 1
    os.makedirs(os.path.join(dest, "saves_auto"), exist_ok=True)
    return dest, copied


def main():
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(SRC), DEFAULT_NAME)
    print("Setting up the autobattler in:\n  %s\n" % dest)
    path, n = install(dest)
    print("%d files copied." % n)
    print("Start it with \"Play D2 Autobattler.bat\" in that folder.")
    print("Keep it up to date with \"Update D2 Autobattler.bat\" there.")


if __name__ == "__main__":
    main()
