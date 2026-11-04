"""Why a monster has no picture: looks for every file of a monster token in your MPQs and writes
what it finds to check_<token>.txt next to the game (paste or upload that file).

    py tools\\check_unit.py MP          (MP = Mephisto)
"""
import configparser
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from d2.source import open_source, read_table  # noqa: E402
from d2.cof import COF  # noqa: E402

MODES = ["NU", "WL", "A1", "A2", "GH", "DT", "DD", "SC", "S1", "S2", "S3", "S4", "BL", "KB", "RN"]
ARMS = ["LIT", "MED", "HVY", "HTH", "BHM", "BSD", "CAP", "CRN", "FHM", "GHM", "HLM", "MSK", "SKP", "LHT"]
COMPS = ["HD", "TR", "LG", "RA", "LA", "RH", "LH", "SH", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]


def main():
    tok = (sys.argv[1] if len(sys.argv) > 1 else "MP").upper()
    cfg = configparser.ConfigParser()
    cfg.read(os.path.join(ROOT, "settings.ini"))
    path = sys.argv[2] if len(sys.argv) > 2 else cfg.get("diablo2", "path", fallback="").strip()
    out = ["D2 Tactics file check for token %s" % tok, "Diablo II folder: %s" % path]
    src = open_source(path)
    archives = getattr(src, "archives", None)
    if archives is None:                     # (an extracted-files folder: one "archive")
        class _F:
            def _find(self, n):
                return 1 if src.has(n) else None

            def block_info(self, n):
                return {} if src.has(n) else None

            def read(self, n):
                return src.read(n)
        archives = [("folder", _F())]
    out.append("archives: %s" % ", ".join(n for n, _ in archives))
    try:
        for r in read_table(src, "MonStats2"):
            if (r.get("code") or r.get("id") or "").upper() == tok or r.get("id", "").lower().startswith("mephisto"):
                out.append("MonStats2 %s: %s" % (r.get("id"), {k: v for k, v in r.items() if k.endswith("v") and v}))
    except Exception as e:
        out.append("MonStats2: %s" % e)
    base = "data\\global\\monsters\\%s\\" % tok.lower()
    found = 0
    for mode in MODES:
        for wc in ("HTH", "1HS", "2HS", "1HT", "2HT", "BOW", "XBW", "STF", "HT1", "HT2"):
            name = base + "cof\\%s%s%s.cof" % (tok, mode, wc)
            if not src.has(name):
                continue
            try:
                cof = COF(src.read(name))
                out.append("COF %s: layers %s" % (name, [(L.component, L.weapon_class) for L in cof.layers]))
            except Exception as e:
                out.append("COF %s: unreadable %s" % (name, e))
                continue
            for L in cof.layers:
                lwc = L.weapon_class or wc
                for arm in ARMS:
                    dn = base + "%s\\%s%s%s%s%s.dcc" % (L.component, tok, L.component, arm, mode, lwc)
                    where = [n for n, a in archives if a._find(dn) is not None]
                    if not where:
                        continue
                    for n, a in archives:
                        info = a.block_info(dn)
                        if info is None:
                            continue
                        line = "  %s in %s: %s" % (dn, n, info)
                        try:
                            data = a.read(dn)
                            line += " read OK %d bytes" % len(data)
                            found += 1
                        except Exception:
                            line += " READ FAILED: " + traceback.format_exc().strip().splitlines()[-1]
                        out.append(line)
    # same names with other extensions / folders, in case they live somewhere unusual
    for comp in COMPS:
        for ext in ("dcc", "dc6"):
            dn = base + "%s\\%s%sLITNUHTH.%s" % (comp, tok, comp, ext)
            hits = [n for n, a in archives if a._find(dn) is not None]
            if hits:
                out.append("found %s in %s" % (dn, hits))
    out.append("readable DCC files: %d" % found)
    dest = os.path.join(ROOT, "check_%s.txt" % tok.lower())
    with open(dest, "w") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))
    print("\nWritten to", dest)


if __name__ == "__main__":
    main()
