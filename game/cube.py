"""The Horadric Cube: D2's own recipes (CubeMain.txt) run on the items you put in.

    inputs   "code[,qualifier...]" - an item code ("gpr"), an item type ("weap", "gem4", "hpot") or
             "any"; qualifiers nor/mag/rar/set/uni/crf (quality), nos (no sockets), sock (has
             sockets), bas/exc/eli (base tier), qty=N (how many)
    output   an item code / type, "usetype" (a new item of the first input's base), "useitem" (the
             first input itself, changed) or a portal ("Cow Portal"); qualifiers as above plus
             pre=N / suf=N (a fixed MagicPrefix / MagicSuffix row), sock=N, uns (empty sockets)
    level    lvl + plvl% of your level + ilvl% of the first input's item level
    mods     mod 1-5 (code, chance, param, min, max) are added to the output (sock = sockets)

Recipes whose items can't exist in this game yet (uniques, sets, jewels, keys) simply never match.
"""
import random

W, H = 3, 4                      # the cube's grid (D2: 3 x 4)

QUALITY = {"nor": "normal", "mag": "magic", "rar": "rare", "set": "set", "uni": "unique", "crf": "crafted"}
SPECIAL_OUT = {"cow portal": "cow", "pandemonium portal": "pandemonium", "pandemonium finale portal": "finale",
               "red portal": "red"}


def _int(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


class Spec:
    """One input or the output of a recipe."""

    def __init__(self, text):
        parts = [p.strip() for p in text.strip().strip('"').split(",")]
        self.raw = text
        self.code = parts[0]
        self.quals = set()
        self.qty = 1
        self.sock = None
        self.pre = self.suf = None
        for q in parts[1:]:
            k, _, v = q.partition("=")
            k = k.lower()
            if k == "qty":
                self.qty = max(1, _int(v, 1))
            elif k == "sock":
                self.sock = _int(v, 0) if v else -1      # -1: "has sockets"
            elif k == "pre":
                self.pre = _int(v)
            elif k == "suf":
                self.suf = _int(v)
            else:
                self.quals.add(k)


class Recipe:
    def __init__(self, row, idx):
        self.idx = idx
        self.desc = row.get("description", "")
        self.inputs = []
        for i in range(1, 8):
            t = (row.get("input %d" % i) or "").strip()
            if t:
                self.inputs.append(Spec(t))
        self.output = Spec(row.get("output", "") or "")
        self.lvl, self.plvl, self.ilvl = _int(row.get("lvl")), _int(row.get("plvl")), _int(row.get("ilvl"))
        self.mods = []
        for i in range(1, 6):
            code = (row.get("mod %d" % i) or "").strip()
            if code:
                self.mods.append((code, _int(row.get("mod %d chance" % i)), row.get("mod %d param" % i, ""),
                                  _int(row.get("mod %d min" % i)), _int(row.get("mod %d max" % i))))
        self.count = sum(s.qty for s in self.inputs)


_recipes = {}


def recipes(content):
    key = id(content)
    if key not in _recipes:
        from d2.source import read_table
        out = []
        try:
            rows = read_table(content.src, "CubeMain")
        except Exception:
            rows = []
        for i, r in enumerate(rows):
            if (r.get("enabled") or "") != "1" or (r.get("ladder") or "") == "1":
                continue                   # ladder-only recipes are off in single player, like D2
            rec = Recipe(r, i)
            if rec.inputs and rec.output.code:
                out.append(rec)
        _recipes[key] = out
    return _recipes[key]


# ------------------------------------------------------------------ matching
def _anc(it):
    b = it.base if isinstance(getattr(it, "base", None), dict) else {}
    return b.get("ancestors", set()) | {it.code}


def _tier(it):
    b = it.base if isinstance(getattr(it, "base", None), dict) else {}
    t = b.get("tiers") or ("", "", "")
    for i, c in enumerate(t):
        if c and c == it.code:
            return ("bas", "exc", "eli")[i]
    return "bas"


def item_matches(it, spec):
    code = spec.code.lower()
    if it.kind in ("gold",):
        return False
    if code == "any":
        if it.kind not in ("equip",):
            return False
    elif code not in _anc(it):
        # a named unique / set item ("The Stone of Jordan")
        names = {str(getattr(it, "unique_name", "") or "").lower(), str(getattr(it, "set_item", "") or "").lower()}
        if not (code in names or (it.rarity in ("unique", "set") and it.name.lower() == code)):
            return False
    q = spec.quals
    rarity = it.rarity if it.kind == "equip" else "normal"
    if getattr(it, "runeword", None):
        rarity = "runeword"
    for k, want in QUALITY.items():
        if k in q and rarity != want:
            return False
    if "low" in q or "hiq" in q or "eth" in q:
        return False                       # no low quality / superior / ethereal items in this game
    if "nos" in q and getattr(it, "sockets", 0):
        return False
    if spec.sock == -1 and not getattr(it, "sockets", 0):
        return False
    if spec.sock is not None and spec.sock > 0 and getattr(it, "sockets", 0) != spec.sock:
        return False
    for t in ("bas", "exc", "eli"):
        if t in q and _tier(it) != t:
            return False
    return True


def match(recipe, items):
    """Assign the items to the recipe's inputs. -> list of (spec, [items]) or None."""
    if len(items) != recipe.count:
        return None
    specs = sorted(range(len(recipe.inputs)), key=lambda i: recipe.inputs[i].code == "any")
    left = list(items)
    picked = {}

    def go(k):
        if k == len(specs):
            return not left
        spec = recipe.inputs[specs[k]]
        cands = [it for it in left if item_matches(it, spec)]
        if len(cands) < spec.qty:
            return False
        # quantities: try the first fitting combination (items of one kind are interchangeable)
        from itertools import combinations
        for combo in combinations(cands, spec.qty):
            for it in combo:
                left.remove(it)
            picked[specs[k]] = list(combo)
            if go(k + 1):
                return True
            for it in combo:
                left.append(it)
        return False
    if go(0):
        return [(recipe.inputs[i], picked[i]) for i in range(len(recipe.inputs))]
    return None


def find(content, items):
    for r in recipes(content):
        m = match(r, items)
        if m is not None:
            return r, m
    return None, None


# ------------------------------------------------------------------ making the output
def _item_level(recipe, player, first):
    lvl = recipe.lvl + recipe.plvl * player.level // 100 + recipe.ilvl * max(1, getattr(first, "ilvl", 0) or
                                                                              first.levelreq or 1) // 100
    if not (recipe.lvl or recipe.plvl or recipe.ilvl):
        lvl = getattr(first, "ilvl", 0) or player.level
    return max(1, lvl)


def _apply_mods(content, it, recipe, rng):
    from . import props
    for code, chance, param, lo, hi in recipe.mods:
        if chance and rng.randrange(100) >= chance:
            continue
        if code == "sock":
            cap = content.max_sockets(it.base, getattr(it, "ilvl", 1)) if isinstance(it.base, dict) else hi
            n = rng.randint(min(lo, hi), max(lo, hi))
            it.sockets = max(getattr(it, "sockets", 0), min(n, cap or n))
        elif code == "levelreq":
            it.levelreq += hi
        else:
            props.apply(it, [(code, param, lo, hi)], rng)


def _new_item(content, base, ilvl, quality, spec, rng):
    force = {}
    if spec.pre is not None:
        force["pre"] = content.affix_by_row("MagicPrefix", spec.pre)
    if spec.suf is not None:
        force["suf"] = content.affix_by_row("MagicSuffix", spec.suf)
    force = {k: v for k, v in force.items() if v}
    if force:
        quality = "magic"
    return content.make_item(base, ilvl, rng, quality, sockets=0, identified=True, force=force)


def transmute(world, cube):
    """Run the recipe that fits what is in the cube. -> (True, message) or (False, reason)."""
    content = world.content
    p = world.player
    items = list(getattr(cube, "contents", []) or [])
    if not items:
        return False, "The cube is empty."
    if content is None:
        return False, "Nothing happens."
    recipe, m = find(content, items)
    if recipe is None:
        return False, "Nothing happens."
    rng = getattr(world, "rng", random)
    out = recipe.output
    first = m[0][1][0]
    oc = out.code.lower()
    quality = next((QUALITY[q] for q in out.quals if q in QUALITY), None)
    if quality in ("set", "unique"):
        return False, "Nothing happens."
    results = []
    if oc in SPECIAL_OUT:
        what = SPECIAL_OUT[oc]
        if what != "cow":
            return False, "Nothing happens."
        msg = world.cube_portal(what) if hasattr(world, "cube_portal") else None
        if not msg:
            return False, "The portal can only be opened in the Rogue Encampment."
        cube.contents = []
        return True, msg
    ilvl = _item_level(recipe, p, first)
    if oc == "useitem":
        it = first
        if "uns" in out.quals or "rem" in out.quals:
            it.socketed = []
            it.runeword = None
            if it.rarity == "unique" and not getattr(it, "unique_name", None):
                it.rarity = "normal"
        if out.sock:
            it.sockets = max(getattr(it, "sockets", 0), out.sock)
        if "exc" in out.quals or "eli" in out.quals:
            tiers = it.base.get("tiers", ("", "", "")) if isinstance(it.base, dict) else ("", "", "")
            new = tiers[1 if "exc" in out.quals else 2]
            nb = content.base_by_code.get(new)
            if nb is not None:
                _rebase(it, nb, rng)
        _apply_mods(content, it, recipe, rng)
        results.append(it)
    else:
        if oc == "usetype":
            base = first.base if isinstance(first.base, dict) else None
        else:
            base = content.base_by_code.get(out.code) or content.base_of_type(oc, ilvl, rng)
        if base is None:
            return False, "Nothing happens."
        q = quality or ("normal" if not base.get("magic_only") else "magic")
        it = _new_item(content, base, ilvl, q, out, rng)
        if it is None:
            return False, "Nothing happens."
        _apply_mods(content, it, recipe, rng)
        if quality == "crafted" and it.rarity not in ("crafted",):
            it.rarity = "crafted"
        results.append(it)
    # everything that went in is used up; the result appears in the cube
    cube.contents = []
    for it in results:
        it.inv_pos = None
        cube_add(cube, it)
    p.recalc()
    return True, "Transmuted: %s." % (results[0].shown_name if results else recipe.desc)


def _rebase(it, nb, rng):
    """Exceptional / elite upgrade: same item, better base."""
    it.base = nb
    it.code = nb["code"]
    if nb.get("dmg"):
        it.dmg = nb["dmg"]
    if nb.get("defense"):
        lo, hi = nb["defense"]
        it.base_defense = rng.randint(min(lo, hi), max(lo, hi))
        it.defense = it.base_defense * (100 + it.mods.get("edef", 0)) // 100 + it.mods.get("def", 0)
    it.reqstr, it.reqdex = nb["reqstr"], nb["reqdex"]
    it.levelreq = max(it.levelreq, nb["levelreq"])
    it.invfile, it.flippy = nb["invfile"], nb["flippyfile"]
    it.gfx = nb.get("gfx", it.gfx)
    if it.rarity == "normal":
        it.name = nb["name"]


# ------------------------------------------------------------------ the cube's grid
def _size(it):
    return max(1, getattr(it, "invw", 1) or 1), max(1, getattr(it, "invh", 1) or 1)


def cells(cube, ignore=None):
    taken = {}
    for it in getattr(cube, "contents", []) or []:
        if it is ignore or getattr(it, "cube_pos", None) is None:
            continue
        w, h = _size(it)
        x0, y0 = it.cube_pos
        for y in range(y0, y0 + h):
            for x in range(x0, x0 + w):
                taken[(x, y)] = it
    return taken


def fits(cube, it, x0, y0):
    w, h = _size(it)
    if x0 < 0 or y0 < 0 or x0 + w > W or y0 + h > H:
        return False, []
    taken = cells(cube)
    over = []
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            o = taken.get((x, y))
            if o is not None and o not in over:
                over.append(o)
    return True, over


def cube_add(cube, it):
    if getattr(cube, "contents", None) is None:
        cube.contents = []
    if it is cube or getattr(it, "code", "") == "box":
        return False
    w, h = _size(it)
    for x0 in range(W - w + 1):
        for y0 in range(H - h + 1):
            ok, over = fits(cube, it, x0, y0)
            if ok and not over:
                it.cube_pos = (x0, y0)
                cube.contents.append(it)
                return True
    return False


def at(cube, x, y):
    return cells(cube).get((x, y))
