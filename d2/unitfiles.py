"""Which DCC files a unit / missile needs (for preparing them ahead of time).

A unit's COF for a mode lists its layers (body parts) and their weapon class; each layer is
one DCC named <token><part><armtype><mode><wclass>.dcc.
"""
from .cof import COF

MONSTER_MODES = ["NU", "WL", "A1", "A2", "GH", "DT", "DD", "SC", "S1", "S2", "S3", "S4", "BL", "KB", "RN"]
PLAYER_MODES = ["NU", "WL", "RN", "A1", "A2", "GH", "DT", "DD", "SC", "TN", "TW", "S1", "S2", "S3", "S4", "BL", "KK"]


def unit_dccs(src, folder, token, wclasses, armtypes, modes):
    """Every DCC that the given look can use. folder = "monsters" or "chars"."""
    out = []
    tok = token.upper()
    base = "data\\global\\%s\\%s\\" % (folder, tok.lower())
    for mode in modes:
        for wc in wclasses:
            path = base + "cof\\%s%s%s.cof" % (tok, mode, wc)
            if not src.has(path):
                continue
            try:
                cof = COF(src.read(path))
            except Exception:
                continue
            for L in cof.layers:
                comp = L.component
                lwc = L.weapon_class or wc
                found = 0
                # the first two armour types that exist: what normal monsters and their bosses wear
                for arm in list(armtypes.get(comp, [])) + ["LIT", "MED", "HVY"]:
                    p = base + "%s\\%s%s%s%s%s.dcc" % (comp, tok, comp, arm.upper(), mode, lwc)
                    if src.has(p):
                        if p not in out:
                            out.append(p)
                        found += 1
                        if found >= 2:
                            break
    return out


def variants(ms2, comp):
    v = (ms2.get(comp.lower() + "v") or "").replace('"', "")
    return [x.strip().upper() for x in v.split(",") if x.strip() and x.strip() != "0"]


def monster_dccs(src, monstats, monstats2, mid):
    r = monstats.get((mid or "").lower())
    if not r:
        return []
    tok = (r.get("code") or "").upper()
    if not tok:
        return []
    m2 = monstats2.get((r.get("monstatsex") or mid).lower(), {})
    wc = ((m2.get("basew") or "hth").replace('"', "").strip() or "hth").upper()
    arms = {c: variants(m2, c) for c in ("HD", "TR", "LG", "RA", "LA", "RH", "LH", "SH",
                                         "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8")}
    return unit_dccs(src, "monsters", tok, [wc, "HTH"] if wc != "HTH" else ["HTH"], arms, MONSTER_MODES)


def missile_dccs(src, missile_rows, names, depth=0):
    """Missiles.txt names -> their DCCs (following explosions and sub-missiles)."""
    out = []
    seen = set()
    todo = [(n.lower(), 0) for n in names if n]
    while todo:
        name, dep = todo.pop()
        if name in seen or dep > 3:
            continue
        seen.add(name)
        r = missile_rows.get(name)
        if not r:
            continue
        cel = (r.get("celfile") or "").strip()
        if cel and cel.lower() != "null":
            p = "data\\global\\missiles\\%s.dcc" % cel
            if src.has(p) and p not in out:
                out.append(p)
        for col in ("explosionmissile", "submissile1", "cltsubmissile1", "hitsubmissile1", "clthitsubmissile1"):
            v = (r.get(col) or "").strip().lower()
            if v:
                todo.append((v, dep + 1))
    return out
