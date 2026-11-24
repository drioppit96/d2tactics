"""The account's stash: one for every hero (saves_auto/_stash.json), held here so the screens
and the runs use the same one. Gold is not in it: each hero keeps his own.

deposit(hero, stash) is the trip home with a full backpack: gems and runes onto their stacks in
the gems & runes tab, unique and set items into the first item tabs with room.
"""
_STASH = [None]


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
        _STASH[0] = st
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
    """An exceptional or elite (tier II / III) plain item with all the sockets its base can have at
    its item level - a runeword base."""
    from game.items import tier_index
    if getattr(it, "kind", "") != "equip" or getattr(it, "rarity", "") not in PLAIN or getattr(it, "runeword", None):
        return False
    if (tier_index(it) or 0) < 1:
        return False
    base = getattr(it, "base", None)
    if not isinstance(base, dict):
        return False
    have = int(getattr(it, "sockets", 0) or 0)
    if have <= 0:
        return False
    try:
        cap = content.max_sockets(base, getattr(it, "ilvl", 1) or 1) if content is not None else base.get("maxsock", 0)
    except Exception:
        cap = base.get("maxsock", 0)
    return cap > 0 and have >= cap


def keeps(it, content=None):
    """What the trip home puts in the stash: gems, runes, unique and set items, and exceptional or
    elite plain items with all their sockets."""
    from game.cube import bankable
    return bankable(it) or getattr(it, "rarity", "") in ("unique", "set") or good_base(it, content)


def deposit(hero, st, content=None):
    """-> how many items went from his backpack into the stash."""
    from game import cube as cb
    n = 0
    for it in list(hero.inventory):
        if not keeps(it, content):
            continue
        if cb.bankable(it):
            st.bank[it.code] = st.bank.get(it.code, 0) + 1
        else:
            placed = False
            for page in st.pages:
                box = type("Page", (), {})()
                box.contents, box.grid_size = page, st.grid_size
                if cb.cube_add(box, it):
                    placed = True
                    break
            if not placed:
                continue
        hero.inventory.remove(it)
        it.inv_pos = None
        n += 1
    return n
