"""The account's stash: one for every hero (saves_auto/_stash.json), held here so the screens
and the runs use the same one. Gold is not in it: each hero keeps his own.

Its parts:
  bank      gems and runes, one stack per kind (the Gems tab)
  pages     the 29 ordinary tabs (Stash), filled by hand
  uniques   UNIQUE_PAGES tabs for unique items
  sets      one page per set (32 in D2): every set item has its own place on its set's page
  spares    SPARE_PAGES ordinary tabs for kept socketed bases and set items already on their page

deposit(hero, stash) is the trip home: everything stash.keeps() goes where place() sends it.
"""
_STASH = [None]

UNIQUE_PAGES = 10
SPARE_PAGES = 10
SPARE_NAME = "Spares"         # (the tab has no name of its own yet)


def get(content=None):
    st = _STASH[0]
    if st is None:
        from game import save as gsave
        try:
            st = gsave.load_shared_stash(content)
        except Exception:
            import traceback
            traceback.print_exc()
            from game.cube import make_stash
            st = make_stash()
        st.purse = None
        ensure(st)
        _STASH[0] = st
    return st


def ensure(st):
    """The autobattler's own parts of the stash (an older save has none of them)."""
    if getattr(st, "uniques", None) is None:
        st.uniques = []
    while len(st.uniques) < UNIQUE_PAGES:
        st.uniques.append([])
    if getattr(st, "spares", None) is None:
        st.spares = []
    while len(st.spares) < SPARE_PAGES:
        st.spares.append([])
    if getattr(st, "sets", None) is None:
        st.sets = {}
    if getattr(st, "view", None) is None:
        st.view = ("stash", max(1, getattr(st, "tab", 1) or 1))
    return st


def save():
    if _STASH[0] is None:
        return
    from game import save as gsave
    try:
        gsave.save_shared_stash(_STASH[0])
    except Exception:
        import traceback
        traceback.print_exc()


PLAIN = ("normal", "superior", "low")


def good_base(it, content=None):
    """A plain (white or grey) socketed base worth keeping: elite (tier III), or ethereal."""
    from game.items import tier_index
    if getattr(it, "kind", "") != "equip" or getattr(it, "rarity", "") not in PLAIN or getattr(it, "runeword", None):
        return False
    if int(getattr(it, "sockets", 0) or 0) <= 0:
        return False
    return (tier_index(it) or 0) >= 2 or bool(getattr(it, "ethereal", False))


def keeps(it, content=None):
    """What the trip home puts in the stash: gems, runes, unique and set items, and plain
    socketed bases that are elite or ethereal."""
    from game.cube import bankable
    return bankable(it) or getattr(it, "rarity", "") in ("unique", "set") or good_base(it, content)


# ------------------------------------------------------------------ where things go
def _box(page, st):
    box = type("Page", (), {})()
    box.contents, box.grid_size = page, st.grid_size
    return box


def into_pages(st, pages, it):
    """Into the first of these grid pages with room. -> True if it went in."""
    from game import cube as cb
    for page in pages:
        if cb.cube_add(_box(page, st), it):
            return True
    return False


def set_of(it):
    """(set index, set item index) of a set item, or None."""
    if getattr(it, "rarity", "") != "set":
        return None
    s, i = getattr(it, "set_name", None), getattr(it, "set_item", None)
    return (s, i) if s and i else None


def into_set(st, it):
    """A set item into its own place on its set's page. -> True if that place was free."""
    key = set_of(it)
    if key is None:
        return False
    page = st.sets.setdefault(key[0], {})
    if page.get(key[1]) is not None:
        return False
    it.cube_pos = None
    page[key[1]] = it
    return True


def place(st, it):
    """Where a kept item goes: gems and runes onto their stacks, a set item onto its place on its
    set's page (one already there: Spares), uniques into the Uniques tabs, socketed bases into
    Spares, anything else into the ordinary tabs. -> True if it went in."""
    from game import cube as cb
    ensure(st)
    if cb.bankable(it):
        st.bank[it.code] = st.bank.get(it.code, 0) + 1
        return True
    rarity = getattr(it, "rarity", "")
    if rarity == "set":
        return into_set(st, it) or into_pages(st, st.spares, it)
    if rarity == "unique":
        return into_pages(st, st.uniques, it)
    if good_base(it):
        return into_pages(st, st.spares, it)
    return into_pages(st, st.pages, it)


def deposit(hero, st, content=None):
    """-> how many items went from his backpack into the stash."""
    n = 0
    for it in list(hero.inventory):
        if not keeps(it, content):
            continue
        pos = it.inv_pos
        hero.inventory.remove(it)
        it.inv_pos = None
        if not place(st, it):
            it.inv_pos = pos
            hero.inventory.append(it)
            continue
        n += 1
    return n


def where(st, it):
    """The name of the tab an item in the stash is in."""
    from game import cube as cb
    if cb.bankable(it):
        return "Gems"
    key = set_of(it)
    if key is not None and (st.sets.get(key[0]) or {}).get(key[1]) is it:
        return "Sets"
    for name, pages in (("Uniques", st.uniques), (SPARE_NAME, st.spares), ("Stash", st.pages)):
        for i, page in enumerate(pages):
            if it in page:
                return "%s %d" % (name, i + 1)
    return "Stash"


# ------------------------------------------------------------------ the screen's views
VIEWS = ("bank", "stash", "uniques", "sets", "spares")


def set_list(content):
    """The sets in D2's own order (Sets.txt): [(set index, name, [set item index...])]."""
    if content is None:
        return []
    try:
        content._load_uniques()
    except Exception:
        return []
    out = []
    for idx, d in (getattr(content, "sets", None) or {}).items():
        members = [m for m in d.get("members", []) if m in content.set_item_by_index]
        if members:
            out.append((idx, d.get("name", idx), members))
    return out


def page_count(st, view, content=None):
    if view == "stash":
        return len(st.pages)
    if view == "uniques":
        return len(st.uniques)
    if view == "spares":
        return len(st.spares)
    if view == "sets":
        return max(1, len(set_list(content)))
    return 1


def show(st, view, page=1, content=None):
    """Look at a view of the stash (page from 1, wraps round). Grid views point st.contents at
    the page, so the grid's clicks work on it; the bank and the set pages aren't grids (tab 0)."""
    ensure(st)
    n = page_count(st, view, content)
    page = (int(page) - 1) % n + 1
    st.view = (view, page)
    if view == "stash":
        st.tab = page
        st.contents = st.pages[page - 1]
    elif view in ("uniques", "spares"):
        st.tab = page
        st.contents = (st.uniques if view == "uniques" else st.spares)[page - 1]
    else:
        st.tab = 0
        st.contents = []
    return st.view
