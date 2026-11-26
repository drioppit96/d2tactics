"""A fourth skill tree, after Hell: one tab of any other class's skills.

Clearing Hell's floor 60 (the Torment unlock) lets a hero pick one skill tree - one of the three
tabs of any other class - as his fourth. Its skills join his book as page 4 (copies; their own
class's tree is not touched) and are learned with skill points like his own: the same required
levels and prerequisites, at most 20 points each.

Skill points: one a level as in D2, until he has had SKILL_CAP in all (spent and unspent); the
cap is NORMAL_CAP before he has beaten Hell and SKILL_CAP after (+100 for the new tree).

profile "extra_tree": [class code, tab] once chosen.
"""
import copy

PAGE = 4
NORMAL_CAP = 100
SKILL_CAP = 200


def unlocked(h):
    from .runs import unlocked as diffs
    return "torment" in diffs(h)


def chosen(h):
    from . import brain
    v = brain.profile(h).get("extra_tree")
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return v[0], int(v[1])
    return None


def choices(h):
    """Every tab of every other class: [(class code, class name, tab, tab name)]."""
    from game.skills import CLASSES, DEFAULT_PAGE_NAMES
    out = []
    for code, name, _a, _b, _c in CLASSES:
        if code == getattr(h, "cls", ""):
            continue
        for tab in (1, 2, 3):
            out.append((code, name, tab, DEFAULT_PAGE_NAMES.get(code, {}).get(tab, "Tab %d" % tab)))
    return out


def title(h):
    c = chosen(h)
    if c is None:
        return None
    from game.skills import CLASS_BY_CODE, DEFAULT_PAGE_NAMES
    return "%s: %s" % (CLASS_BY_CODE[c[0]][1], DEFAULT_PAGE_NAMES.get(c[0], {}).get(c[1], "Tab %d" % c[1]))


def source_tree(content, cls):
    from game.skills import load_tree
    src = getattr(content, "src", None) if content is not None else None
    if src is None:
        return {}
    return load_tree(src, cls, getattr(content, "strings", None))


def originals(h, content):
    """The chosen tab's skills as their own class has them (page 1-3): for drawing its tree."""
    c = chosen(h)
    if c is None:
        return {}
    return {k: s for k, s in source_tree(content, c[0]).items() if getattr(s, "page", 0) == c[1]}


def attach(h, content, levels=None):
    """His book with the chosen tab's skills in it, as page 4 (and their saved levels)."""
    book = getattr(h, "skills", None)
    c = chosen(h)
    if book is None or c is None:
        return 0
    if not getattr(book, "_own_tree", False):
        book.tree = dict(book.tree)          # (his own copy: the class's tree is shared)
        book._own_tree = True
    n = 0
    for k, s in originals(h, content).items():
        if k in book.tree and getattr(book.tree[k], "page", 0) == PAGE:
            continue
        cp = copy.copy(s)
        cp.page = PAGE
        cp.origin = c
        book.tree[k] = cp
        try:
            book._by_title[k.lower()] = cp
            book._by_title[cp.title.lower()] = cp
        except Exception:
            pass
        n += 1
    if levels:
        for k, v in levels.items():
            if k in book.tree and k not in book.levels:
                book.levels[k] = v
    return n


def detach(h):
    """The fourth tree out of his book; its points back to spend."""
    book = getattr(h, "skills", None)
    if book is None:
        return 0
    back = 0
    for k in [k for k, s in book.tree.items() if getattr(s, "page", 0) == PAGE]:
        back += book.levels.pop(k, 0)
        book.tree.pop(k, None)
    book.points += back
    return back


def choose(h, content, cls, tab):
    """Pick (or change, giving its points back) the fourth tree."""
    from . import brain
    detach(h)
    brain.profile(h)["extra_tree"] = [cls, int(tab)]
    attach(h, content)
    try:
        h.recalc()
    except Exception:
        pass


def point_cap(h):
    return SKILL_CAP if unlocked(h) else NORMAL_CAP


def total_points(h):
    book = h.skills
    return sum(book.levels.values()) + book.points


def may_get_point(h):
    """D2 gives a skill point every level; here only while he is under his cap."""
    try:
        return total_points(h) < point_cap(h)
    except Exception:
        return True


def spend_auto(h):
    """'Points: by class plan': what the class plan can't use goes into the fourth tree - its
    deepest skill he can reach first, its prerequisites on the way, then the next."""
    book = getattr(h, "skills", None)
    if book is None or book.points <= 0 or chosen(h) is None:
        return False
    from .brain import _learn_chain
    clvl = getattr(h, "level", 1)
    mine = sorted([s for s in book.tree.values() if getattr(s, "page", 0) == PAGE
                   and s.kind != "passive" and clvl >= s.reqlevel],
                  key=lambda s: (-s.reqlevel, s.title))
    mine += sorted([s for s in book.tree.values() if getattr(s, "page", 0) == PAGE and s not in mine],
                   key=lambda s: (-s.reqlevel, s.title))
    changed = False
    guard = 0
    while book.points > 0 and guard < 400:
        guard += 1
        spent = False
        for s in mine:
            if book.levels.get(s.key, 0) < s.maxlvl and _learn_chain(book, s.key, clvl):
                spent = changed = True
                break
        if not spent:
            break
    return changed
