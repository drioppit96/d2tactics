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


def keeps(it):
    """What the trip home puts in the stash: gems, runes, unique and set items."""
    from game.cube import bankable
    return bankable(it) or getattr(it, "rarity", "") in ("unique", "set")


def deposit(hero, st):
    """-> how many items went from his backpack into the stash."""
    from game import cube as cb
    n = 0
    for it in list(hero.inventory):
        if not keeps(it):
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
