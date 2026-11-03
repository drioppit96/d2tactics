"""Scrolls, tomes, town portals, identification, sockets and the Act 1 vendors (mixed into World).

Vendors stock what D2's Weapons/Armor/Misc.txt say they sell (CharsiMin/Max, GheedMin/Max,
AkaraMin/Max and their magic columns); Gheed also gambles. Stock is rolled again every time
you come back to the camp.
"""
from .grid import chebyshev
from . import d2items

YELLOW = (255, 230, 90)
GREY = (170, 170, 170)
RED = (255, 80, 80)

VENDORS = {"akara": "akara", "charsi": "charsi", "gheed": "gheed",
           "fara": "fara", "lysander": "lysander", "drognan": "drognan", "elzix": "elzix",
           "ormus": "ormus", "alkor": "alkor", "asheara": "asheara", "hratli": "hralti",      # D2's own spelling
           "jamella": "jamella", "halbu": "halbu", "larzuk": "larzuk", "malah": "malah", "drehya": "drehya"}
NPC_OPTIONS = {
    "akara": ["Talk", "Trade", "Level 99 (test)"],             # TEST ONLY: "Level 99 (test)", remove later
    "charsi": ["Talk", "Trade", "Recharge"], "gheed": ["Talk", "Trade", "Gamble"],
    "kashya": ["Talk", "Hire"], "cain1": ["Talk", "Identify Items"],
    "warriv1": ["Talk", "Go East", "Go East (test)"],          # TEST ONLY: "Go East (test)", remove later
    # Lut Gholein
    "fara": ["Talk", "Trade", "Recharge"], "drognan": ["Talk", "Trade"], "lysander": ["Talk", "Trade"],
    "elzix": ["Talk", "Trade", "Gamble"], "greiz": ["Talk", "Hire"], "atma": ["Talk"], "jerhyn": ["Talk"],
    "geglash": ["Talk"], "meshif1": ["Talk", "Sail East", "Sail East (test)"],   # TEST ONLY: "(test)"
    "tyrael1": ["Talk"], "warriv2": ["Talk", "Go West"], "cain2": ["Talk", "Identify Items"],
    # Kurast Docks
    "ormus": ["Talk", "Trade"], "alkor": ["Talk", "Trade", "Gamble"], "asheara": ["Talk", "Trade", "Hire"],
    "hratli": ["Talk", "Trade", "Recharge"], "cain3": ["Talk", "Identify Items", "To Act 4 (test)"],   # TEST ONLY: "To Act 4 (test)"
    "meshif2": ["Talk", "Sail West"], "natalya": ["Talk"],
    # the Pandemonium Fortress
    "tyrael2": ["Talk", "Travel to Harrogath", "Travel to Harrogath (test)"],             # TEST ONLY: "(test)"
    "jamella": ["Talk", "Trade", "Gamble"], "halbu": ["Talk", "Trade", "Recharge"], "cain4": ["Talk", "Identify Items"],
    # Harrogath
    "larzuk": ["Talk", "Trade", "Recharge", "Imbue Sockets"], "malah": ["Talk", "Trade"], "drehya": ["Talk", "Trade", "Gamble"],
    "qual-kehk": ["Talk", "Hire"], "nihlathak": ["Talk"], "tyrael3": ["Talk"], "cain6": ["Talk", "Identify Items"],
}
STORE_W, STORE_H = 10, 10
TAB_NAMES = {"armo": "Armor", "weap": "Weapons", "misc": "Misc", "gamble": "Gamble"}

def _difficulty(world):
    return {"": "normal", "(n)": "nightmare", "(h)": "hell"}.get(getattr(world.content, "sfx", ""), "normal")


def grant_imbue(world):
    """Tools of the Trade: Charsi imbues one item - once per difficulty (D2)."""
    p = world.player
    im = p.__dict__.setdefault("imbues", {})
    if im.get(_difficulty(world)) != "used":
        im[_difficulty(world)] = "ready"


def imbue_ready(world):
    return (getattr(world.player, "imbues", None) or {}).get(_difficulty(world)) == "ready"


def npc_options(world, npc_id):
    """The NPC's menu, with what the story has unlocked (Charsi's Imbue)."""
    opts = list(NPC_OPTIONS.get(npc_id, ["Talk"]))
    p = world.player
    if npc_id == "charsi" and (getattr(p, "quests", {}) or {}).get("malus") == "done" and \
            _difficulty(world) not in (getattr(p, "imbues", None) or {}):
        grant_imbue(world)              # (heroes who returned the Malus before Imbue existed)
    if npc_id == "charsi" and imbue_ready(world):
        opts.insert(2, "Imbue")
    return opts


# the blacksmiths: their trade screen has the Socket Item button
SMITHS = ("charsi", "fara", "hratli", "halbu", "larzuk")


class Store:
    def __init__(self, npc, tabs):
        self.npc = npc
        self.tabs = tabs              # [(page, [items with .store_pos])]
        self.tab = 0

    def items(self):
        return self.tabs[self.tab][1] if self.tabs else []

    def at(self, x, y):
        for it in self.items():
            sx, sy = it.store_pos
            if sx <= x < sx + max(1, it.invw) and sy <= y < sy + max(1, it.invh):
                return it
        return None


def _pack(items):
    """Place items in a 10x10 store grid (columns left to right); extras are dropped."""
    taken = set()
    out = []
    for it in sorted(items, key=lambda i: (-(i.invw * i.invh), i.name)):
        w, h = max(1, it.invw), max(1, it.invh)
        placed = False
        for x in range(STORE_W - w + 1):
            for y in range(STORE_H - h + 1):
                cells = {(x + i, y + j) for i in range(w) for j in range(h)}
                if not cells & taken:
                    taken |= cells
                    it.store_pos = (x, y)
                    out.append(it)
                    placed = True
                    break
            if placed:
                break
    return out


class ItemActions:
    # ------------------------------------------------------------ vendors
    def open_store(self, npc_id, gamble=False, refresh=False):
        c = self.content
        if c is None:
            return None
        p = self.player
        cache = getattr(p, "_stores", None)
        if cache is None:
            cache = p._stores = {}
        key = (npc_id, gamble)
        if not refresh and key in cache and cache[key][1] == getattr(p, "_town_visit", 0):
            from .qol import stock
            stock(cache[key][0], p)
            return cache[key][0]
        rng = self.rng
        ilvl = min(p.level + 5, 30)
        pages = {"armo": [], "weap": [], "misc": []}
        if gamble:
            # D2: what Gamble.txt lists, up to your level; rings and amulets always among them;
            # every item will be rolled at item level (your level -5 .. +4) when you buy it
            codes = getattr(c, "_gamble_codes", None)
            if codes is None:
                try:
                    from d2.source import read_table
                    codes = {(r.get("code") or "").strip().lower() for r in read_table(c.src, "Gamble")} - {""}
                except Exception:
                    codes = set()
                c._gamble_codes = codes
            pool = [b for b in c.bases if (b["code"].lower() in codes if codes else
                    (b["kind"] in ("weapon", "armor", "misc") and b.get("slot") and "use" not in b
                     and "gem" not in b and "potion" not in b)) and b["qlvl"] <= max(1, p.level)]
            jewel = [b for b in pool if b["code"] in ("rin", "amu")]
            rest = [b for b in pool if b["code"] not in ("rin", "amu")]
            rng.shuffle(rest)
            chosen = [b for b in jewel for _ in range(2)] + rest[:24]
            items = []
            for b in chosen:
                gl = rng.randint(max(1, p.level - 5), p.level + 4)
                it = c.make_item(b, gl, rng, sockets=0)
                it.gamble = True
                it.gamble_base = b
                it.gamble_ilvl = gl
                it.name = c.strings.get(b.get("namestr") or "", None) or b.get("name", it.name)
                items.append(it)
            store = Store(npc_id, [("gamble", _pack(items))])
        else:
            col = VENDORS.get(npc_id)
            for b in c.bases:
                sh = b.get("shop", {}).get(col)
                if not sh or b["qlvl"] > ilvl:
                    continue
                mn, mx, mmn, mmx, mlvl = sh
                page = b.get("page", "misc")
                page = page if page in pages else "misc"
                n = rng.randint(mn, max(mn, mx)) if mx else 0
                if "potion" in b or "use" in b:
                    n = 1 if mx else 0          # potions / scrolls never run out
                for _ in range(n):
                    it = c.make_item(b, ilvl, rng, sockets=0)
                    if "potion" in b or "use" in b:
                        it.infinite = True
                    pages[page].append(it)
                m = rng.randint(mmn, max(mmn, mmx)) if mmx else 0
                for _ in range(m):
                    pages[page].append(c.make_item(b, max(ilvl, mlvl), rng, "magic", identified=True))
            tabs = [(pg, _pack(pages[pg])) for pg in ("armo", "weap", "misc") if pages[pg]]
            store = Store(npc_id, tabs)
        cache[key] = (store, getattr(p, "_town_visit", 0))
        from .qol import stock
        stock(store, p)
        return store

    def socket_cost(self, it):
        """Each socket costs twice the item's price (its price without sockets: every one the same)."""
        had = getattr(it, "sockets", 0)
        it.sockets = 0
        try:
            return 2 * max(1, self.price_of(it))
        finally:
            it.sockets = had

    def imbue_item(self, it):
        """Charsi's Imbue (D2): a normal (white) weapon or armor becomes a rare item of item level
        character level + 4. Once per difficulty."""
        p = self.player
        c = self.content
        if not imbue_ready(self):
            return False
        if it is None or getattr(it, "kind", "") != "equip" or not isinstance(getattr(it, "base", None), dict) \
                or it.rarity not in ("normal", "superior", "low") or getattr(it, "runeword", None) \
                or getattr(it, "socketed", None):
            self.log("Charsi: I can only imbue a plain (white) weapon or armor with nothing in its sockets.", GREY)
            return False
        new = c.make_item(it.base, p.level + 4, self.rng, "rare", sockets=0, identified=True)
        if new is None:
            return False
        if getattr(it, "ethereal", False):
            new.ethereal = True
        if it in p.inventory:
            new.inv_pos = it.inv_pos
            p.inventory[p.inventory.index(it)] = new
        else:
            slot = next((k for k, v in p.equipment.items() if v is it), None)
            if slot is None:
                return False
            p.equipment[slot] = new
        p.imbues[_difficulty(self)] = "used"
        p.recalc()
        self.log("Charsi imbues it: %s!" % new.name, new.color)
        return True

    def socket_item(self, it):
        """The blacksmith adds one socket to an item (up to its D2 maximum) for twice its price."""
        p = self.player
        c = self.content
        if it is None or getattr(it, "kind", "") != "equip" or not isinstance(getattr(it, "base", None), dict):
            self.log("Only weapons and armor can be socketed.", GREY)
            return False
        if getattr(it, "runeword", None):
            self.log("A runeword item can't get more sockets.", GREY)
            return False
        cap = c.max_sockets(it.base, getattr(it, "ilvl", 1) or 1) if c is not None else it.base.get("maxsock", 0)
        have = getattr(it, "sockets", 0) or 0
        if cap <= 0:
            self.log("%s can't have sockets." % getattr(it, "shown_name", it.name), GREY)
            return False
        if have >= cap:
            self.log("%s already has its most sockets (%d)." % (getattr(it, "shown_name", it.name), cap), GREY)
            return False
        cost = self.socket_cost(it)
        if p.gold < cost:
            self.log("A socket costs %d gold - you have %d." % (cost, p.gold), RED)
            return False
        p.gold -= cost
        it.sockets = have + 1
        if getattr(it, "socketed", None) is None:
            it.socketed = []
        p.recalc()
        self.log("%s now has %d socket%s (-%d gold)%s." % (getattr(it, "shown_name", it.name), it.sockets,
                 "" if it.sockets == 1 else "s", cost, "" if it.sockets < cap else ", the most it can have"),
                 (199, 179, 119))
        return True

    def price_of(self, it, store=None):
        from .qol import is_goblin, GOBLIN_PRICE
        if is_goblin(it):
            return GOBLIN_PRICE
        if getattr(it, "gamble", False):
            b = it.gamble_base
            return min(50000, 150 + 60 * self.player.level + 2 * max(10, b.get("cost", 50)))
        return d2items.price(it)

    def buy(self, store, it):
        p = self.player
        cost = self.price_of(it, store)
        if p.gold < cost:
            self.log("You don't have enough gold (%d needed)." % cost, RED)
            return False
        if getattr(it, "gamble", False):
            # D2's gambling odds: mostly magic, 10% rare, now and then a set or unique item
            ilvl = getattr(it, "gamble_ilvl", None) or self.rng.randint(max(1, p.level - 5), p.level + 4)
            r = self.rng.random()
            c = self.content
            q = "unique" if r < 0.005 and c.uniques_for(it.gamble_base, ilvl) else \
                "set" if r < 0.015 and c.set_items_for(it.gamble_base, ilvl) else \
                "rare" if r < 0.115 else "magic"
            new = c.make_item(it.gamble_base, ilvl, self.rng, q, identified=True)
            if not p.inv_add(new):
                self.log("Your inventory is full.", GREY)
                return False
            p.gold -= cost
            self.log("Gambled: %s." % new.name, new.color)
            return True
        if it.use in ("tp", "id") and not (it.base or {}).get("tome"):
            # a scroll goes into a matching tome if you have one (D2)
            from .items import TOME_MAX
            tome = next((t for t in p.inventory if t.use == it.use and (t.base or {}).get("tome") and t.quantity < TOME_MAX), None)
            if tome is not None:
                p.gold -= cost
                tome.quantity += 1
                self.log("%s: %d scrolls." % (tome.name, tome.quantity), GREY)
                return True
        from .qol import is_goblin, make_goblin, ensure_pet
        if is_goblin(it):
            new = make_goblin()
        elif getattr(it, "infinite", False):
            new = self.content.make_item(it.base, it.base.get("qlvl", 1) or 1, self.rng, sockets=0)
        else:
            new = it
        if new.kind == "potion" and len(p.belt) < 4:
            p.belt.append(new)
        elif not p.inv_add(new):
            self.log("Your inventory is full.", GREY)
            return False
        p.gold -= cost
        if new is it:
            for _, lst in store.tabs:
                if it in lst:
                    lst.remove(it)
        self.log("Bought %s for %d gold." % (new.name, cost), new.color)
        if is_goblin(new):
            ensure_pet(self)
        return True

    def sell(self, it):
        p = self.player
        held = it is self.held
        if it not in p.inventory and not held:
            return False
        from .qol import is_goblin
        if it.kind == "quest" or is_goblin(it):
            self.log("You can't sell %s." % ("quest items" if it.kind == "quest" else "the Loot Goblin"), GREY)
            return False
        if held:
            self.held = None
            p.inventory.append(it)
        value = d2items.sell_price(it)
        p.inventory.remove(it)
        it.inv_pos = None
        p.gold += value
        self.log("Sold %s for %d gold." % (it.shown_name, value), GREY)
        return True

    def identify_all(self, free=True, quiet=False):
        """Deckard Cain identifies everything you own: backpack, equipment, the other weapon set,
        what's in your Horadric Cube and in the stash."""
        p = self.player
        n = 0
        items = list(p.inventory) + [x for x in p.equipment.values() if x] + \
            [x for x in (getattr(p, "swap_gear", None) or {}).values() if x]
        for it in list(items):
            items += list(getattr(it, "contents", None) or [])          # the cube
        st = getattr(p, "stash", None)
        if st is not None:
            for page in getattr(st, "pages", None) or [getattr(st, "contents", None) or []]:
                items += list(page)
        for it in items:
            if d2items.identify(it):
                n += 1
        p.recalc()
        if n or not quiet:
            self.log("Deckard Cain identifies %d item%s." % (n, "" if n == 1 else "s") if n else
                     "Deckard Cain: You have nothing I need to look at.", YELLOW)
        return n

    # ------------------------------------------------------------ using items
    def use_item(self, it):
        """Right click on a backpack item."""
        p = self.player
        if it.kind == "potion":
            if it.potion in ("heal", "mana", "rejuv"):
                return self.use_inventory_potion(it)
            return self._drink_special(it)
        if it.use == "tp":
            if self._consume(it):
                return self.town_portal()
            return False
        if it.kind == "quest":
            return self.read_quest_item(it)
        if it.use == "id":
            if not any(not getattr(x, "identified", True) for x in list(p.inventory) + list(p.equipment.values()) if x):
                self.log("You have nothing to identify.", GREY)
                return False
            self.cursor_mode = ("identify", it)
            self.log("Click the item to identify.", GREY)
            return True
        return False

    # ------------------------------------------------------------ quest items
    def read_quest_item(self, it):
        p = self.player
        from . import quests
        if it.use == "book_skill":
            p.inventory.remove(it)
            it.inv_pos = None
            p.skills.points += 1
            self.log("You read the Book of Skill. +1 skill point!", (0, 220, 0))
            return True
        if it.use == "horadric_scroll":
            quests.read_horadric_scroll(self, it)
            return True
        from . import quests345
        quests.init(p)
        return quests345.read_item(self, it)

    # ------------------------------------------------------------ the Horadric Cube
    def cube_insert(self, box, it=None):
        """Put the cursor item into the cube (dropped on the cube in the backpack)."""
        from . import cube as cb
        it = it if it is not None else self.held
        if it is None or it is box:
            return False
        if not cb.cube_add(box, it):
            self.log("The cube is full.", GREY)
            return False
        if it is self.held:
            self.held = None
        return True

    def cube_place(self, box, x0, y0):
        """Drop the cursor item into the cube's grid (swaps with one item, like the backpack)."""
        from . import cube as cb
        it = self.held
        if it is None or it is box or (getattr(it, "code", "") == "box" and getattr(box, "code", "") == "box"):
            return False
        ok, over = cb.fits(box, it, x0, y0)
        if not ok or len(over) > 1:
            return False
        swap = over[0] if over else None
        if swap is not None:
            box.contents.remove(swap)
            swap.cube_pos = None
        it.cube_pos = (x0, y0)
        box.contents.append(it)
        self.held = swap
        return True

    def cube_pick(self, box, it):
        if self.held is not None or it not in (getattr(box, "contents", None) or []):
            return False
        box.contents.remove(it)
        it.cube_pos = None
        self.held = it
        return True

    def bank_deposit(self, it):
        """A gem or rune goes onto its stack in the stash's first tab."""
        from . import cube as cb
        st = getattr(self.player, "stash", None)
        if st is None or not cb.bankable(it):
            return False
        p = self.player
        if it is self.held:
            self.held = None
        elif it in p.inventory:
            p.inventory.remove(it)
            it.inv_pos = None
        else:
            return False
        st.bank[it.code] = st.bank.get(it.code, 0) + 1
        return True

    def bank_take(self, code, to_inventory=False):
        """One gem or rune off its stack: onto the cursor, or (right click) into the backpack."""
        st = getattr(self.player, "stash", None)
        c = self.content
        if st is None or c is None or st.bank.get(code, 0) <= 0:
            return None
        if not to_inventory and self.held is not None:
            return None
        base = c.base_by_code.get(code)
        if base is None:
            return None
        it = c.make_item(base, 1, self.rng)
        if it is None:
            return None
        if to_inventory:
            if not self.player.inv_add(it):
                self.log("No room in your backpack.", GREY)
                return None
        else:
            self.held = it
        st.bank[code] -= 1
        if st.bank[code] <= 0:
            del st.bank[code]
        return it

    def stash_gold(self, deposit=True):
        p = self.player
        st = getattr(p, "stash", None)
        if st is None:
            return False
        if deposit:
            st.gold += p.gold
            p.gold = 0
        else:
            p.gold += st.gold
            st.gold = 0
        return True

    def transmute(self, box):
        from . import cube as cb
        ok, msg = cb.transmute(self, box)
        self.log(msg, (199, 179, 119) if ok else GREY)
        if ok:
            self.emit("transmute", box)
            from . import quests
            quests.on_transmute(self, box)
        return ok

    def cube_portal(self, what):
        """Wirt's Leg + a Tome of Town Portal in the Rogue Encampment: the Secret Cow Level."""
        if what != "cow" or self.level_id != 1:
            return None
        p = self.player
        cell = self._free_cell_near((p.x + 2, p.y + 1), 4)
        self.objects.append(dict(kind="portal", cell=cell, level=1, oid=0, used=False, target=39))
        self.emit("nova", p, cell, 3, "fire")
        return "A red portal opens... Moo?"

    def _consume(self, it):
        p = self.player
        if (it.base or {}).get("tome"):
            if it.quantity <= 0:
                self.log("The tome is empty. Buy scrolls from Akara.", GREY)
                return False
            it.quantity -= 1
            return True
        if it in p.inventory:
            p.inventory.remove(it)
            it.inv_pos = None
        return True

    def identify_with(self, scroll, target):
        if target is None or getattr(target, "identified", True):
            self.cursor_mode = None
            return False
        if not self._consume(scroll):
            self.cursor_mode = None
            return False
        d2items.identify(target)
        self.player.recalc()
        self.cursor_mode = None
        self.log("Identified: %s." % target.name, target.color)
        return True

    def _drink_special(self, it):
        p = self.player
        if self.mode == "combat":
            if p.ap < 2:
                self.log("Not enough AP to drink.", GREY)
                return False
            p.ap -= 2
        if it in p.inventory:
            p.inventory.remove(it)
        elif it in p.belt:
            p.belt.remove(it)
        if it.potion == "antidote":
            p.effects.pop("poison", None)
            p.buffs["Antidote"] = {"turns": 15, "stats": {"res_pois": 50}, "title": "Antidote"}
        elif it.potion == "thawing":
            p.effects.pop("chill", None)
            p.buffs["Thawing"] = {"turns": 15, "stats": {"res_cold": 50}, "title": "Thawing"}
        elif it.potion == "stamina":
            p.frenzy = max(p.frenzy, 2)
        p.recalc()
        self.log("You drink a %s." % it.name, YELLOW)
        return True

    def insert_into(self, host, filler):
        """Socket a gem / rune (held on the cursor) into an item."""
        if host is None or filler is None or getattr(filler, "gem", None) is None:
            return False
        if self.player.level < filler.levelreq:
            self.log("You need level %d for this." % filler.levelreq, RED)
            return False
        msg = d2items.insert(self.content, host, filler, self.rng)
        if msg is None:
            self.log("No free socket." if getattr(host, "sockets", 0) else "That item has no sockets.", GREY)
            return False
        if self.held is filler:
            self.held = None
        self.player.recalc()
        self.log(msg, YELLOW if not host.runeword else (199, 179, 119))
        return True

    # ------------------------------------------------------------ town portal
    def town_portal(self):
        """Open a blue portal next to you; its twin waits in the camp."""
        p = self.player
        if self.town:
            self.log("You are already in town.", GREY)
            return False
        cell = self._free_cell_near((p.x + 1, p.y + 1), 3)
        self.objects = [o for o in self.objects if o["kind"] != "tp"]
        self.objects.append(dict(kind="tp", cell=cell, level=self.level_id, oid=0, used=False, target=1))
        p.portal = (self.level_key, cell, self.level_id)
        self.emit("nova", p, cell, 1, "mag")
        self.log("A Town Portal opens.", (120, 160, 255))
        return True

    def portal_target(self, obj):
        """-> (target level, arrival cell) for a portal object."""
        if obj["kind"] == "tp":
            return 1, None
        if obj["kind"] == "tp_back":
            info = getattr(self.player, "portal", None)
            if info:
                return info[2], info[1]
        return obj.get("target"), None
