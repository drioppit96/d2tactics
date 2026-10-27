"""DS1 object numbers -> what they are, from D2's obj.txt (Act, Id -> Objects.txt row).

Without obj.txt (not every sample set has it) only Act 1's hand-checked numbers are known;
other acts then get their waypoints placed by the level builders instead.
"""
_cache = {}

# Objects.txt names (lower case, substring) -> our object kinds
KINDS = [("waypoint", "waypoint"), ("orifice", "orifice"), ("holder for horadric staff", "orifice"),
         ("arcane", "arcane_portal"), ("journal", "journal"), ("summoner", "journal")]


def _rows(kit, name):
    from d2.source import read_table
    try:
        return read_table(kit.src, name)
    except Exception:
        return []


def quest_objects(kit, act):
    key = (id(kit.src), act)
    if key in _cache:
        return _cache[key]
    out = {}
    obj = [r for r in _rows(kit, "Obj") if (r.get("act") or "").strip() == str(act)]
    if obj:
        objects = _rows(kit, "Objects")
        by_id = {}
        for i, r in enumerate(objects):
            try:
                by_id[int(r.get("id") or i)] = r
            except ValueError:
                by_id[i] = r
        for r in obj:
            try:
                ds1_id = int(r.get("id"))
                oid = int(r.get("objectid"))
            except (TypeError, ValueError):
                continue
            orow = by_id.get(oid, {})
            text = ((r.get("description") or "") + " " + (orow.get("name") or "") + " " +
                    (orow.get("description - not loaded") or "")).lower()
            for needle, kind in KINDS:
                if needle in text:
                    out[ds1_id] = kind
                    break
    _cache[key] = out
    return out
