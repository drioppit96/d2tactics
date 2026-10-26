"""Where D2 files come from: your install's MPQs, or a folder of already-extracted files."""
import os

from .mpq import MPQSet


class FolderSource:
    """Extracted files laid out as data/global/... (e.g. the d2samples folder)."""

    def __init__(self, root):
        self.root = root
        self.index = {}
        for base, _, files in os.walk(root):
            for fn in files:
                full = os.path.join(base, fn)
                rel = os.path.relpath(full, root).replace("/", "\\").lower()
                self.index[rel] = full

    def has(self, name):
        return name.replace("/", "\\").lower() in self.index

    def read(self, name):
        path = self.index.get(name.replace("/", "\\").lower())
        if path is None:
            raise KeyError(name)
        with open(path, "rb") as f:
            return f.read()


def open_source(path, progress=None, cache_dir=None):
    """Accepts a Diablo II install folder or an extracted-files folder."""
    if not os.path.isdir(path):
        raise FileNotFoundError("folder not found: " + path)
    names = {n.lower() for n in os.listdir(path)}
    if "d2data.mpq" in names:
        return MPQSet(path, progress, cache_dir)
    for cand in (path, os.path.join(path, "files"), os.path.join(path, "d2samples", "files")):
        if os.path.isdir(os.path.join(cand, "data")):
            return FolderSource(cand)
    raise FileNotFoundError("no Diablo II files (d2data.mpq) in " + path)


def read_table(src, name):
    """D2 .txt data table -> list of dicts with lower-case column names."""
    data = src.read("data\\global\\excel\\%s.txt" % name).decode("latin-1")
    lines = data.splitlines()
    header = [h.strip().lower() for h in lines[0].split("\t")]
    rows = []
    for line in lines[1:]:
        cells = line.split("\t")
        rows.append({header[i]: (cells[i].strip() if i < len(cells) else "") for i in range(len(header))})
    return rows
