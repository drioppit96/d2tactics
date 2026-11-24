"""The inventory screen's item handling: equip, unequip, move, identify, belt, sell.

A Bench stands in for the game World for one hero. It borrows the World's own item methods
(equip_held, place_held, _put_on, slot_accepts, can_offhand, identify_with, ...), so the rules are
the game's: two-handed weapons take the shield off, rings go in either ring slot, requirements
are checked, a second claw or one-handed weapon goes in the off hand for the classes that can.

The item on the mouse cursor lives in bench.held. Anything a swap pushes out with no room left
goes to bench.ground (shown as "Floor" on the screen). finish() puts both back in the backpack
when the screen closes; what still does not fit is sold.

The hero's backpack is 10 x 8 here: twice D2's 10 x 4 (game.units.Player.INV_H reads
qol["inv_rows"]).
"""
import random

from game import d2items
from game.itemactions import ItemActions
from game.world import World

ROWS = 8
CHARM_W, CHARM_H = 4, 8     # the charm inventory beside the backpack
GREY = (170, 170, 170)


def is_charm(it):
    return bool(getattr(it, "charm", False))


class CharmBox:
    """The charm inventory as a grid the cube helpers understand (positions in it.cube_pos)."""
    def __init__(self, hero):
        if getattr(hero, "charm_inv", None) is None:
            hero.charm_inv = []
        self.contents = hero.charm_inv
        self.grid_size = (CHARM_W, CHARM_H)
        self.code = "charms"


def prepare(p):
    """Give an autobattler hero the double backpack and the charm inventory (only charms in it
    work). The first time, the charms in his backpack move into it."""
    if p is None:
        return p
    q = getattr(p, "qol", None)
    if not isinstance(q, dict):
        q = p.qol = {}
    q["big_inv"] = True
    q["inv_rows"] = ROWS
    if getattr(p, "charm_inv", None) is None:
        p.charm_inv = []
    if not q.get("charm_grid"):
        q["charm_grid"] = True
        from game import cube as cb
        box = CharmBox(p)
        for it in [x for x in p.inventory if is_charm(x)]:
            p.inventory.remove(it)
            pos, it.inv_pos = it.inv_pos, None
            if not cb.cube_add(box, it):
                it.inv_pos = pos
                p.inventory.append(it)
        try:
            p.recalc()
        except Exception:
            pass
    return p


class Bench:
    """Just enough World for the item methods, acting on one hero."""
    mode = "explore"
    turn = "player"

    def __init__(self, hero, content=None, stash=None):
        self.player = hero
        self.content = content
        self.stash = stash          # the account's shared stash (town only), or None
        self.rng = random.Random()
        self.held = None
        self.cursor_mode = None
        self.ground = {}
        self.messages = []
        self.changed = False

    # what World's methods expect
    def log(self, text, color=GREY):
        self.messages.append((text, color))
        del self.messages[:-6]

    def emit(self, *args, **kw):
        pass

    _inv_index = World._inv_index
    equip = World.equip
    _put_on = World._put_on
    can_offhand = World.can_offhand
    slot_accepts = World.slot_accepts
    pick_from_inventory = World.pick_from_inventory
    pick_from_slot = World.pick_from_slot
    place_held = World.place_held
    equip_held = World.equip_held
    use_inventory_potion = World.use_inventory_potion
    # the vendors (town): D2's own stock rules, prices and gambling odds
    open_store = ItemActions.open_store
    buy = ItemActions.buy
    price_of = ItemActions.price_of

    def select_right_skill(self, name):
        self.player.right_skill = name

    # ------------------------------------------------------------ the floor (overflow)
    def floor(self):
        out = []
        for items in self.ground.values():
            out.extend(items)
        return out

    def take_from_floor(self, it):
        if self.held is not None:
            return False
        for items in self.ground.values():
            if it in items:
                items.remove(it)
                self.held = it
                return True
        return False

    def drop_held(self):
        """Put the cursor item on the floor (it goes back in the backpack when the screen closes)."""
        if self.held is None:
            return False
        self.ground.setdefault(self.player.pos, []).append(self.held)
        self.held = None
        return True

    # ------------------------------------------------------------ clicks
    def click_slot(self, slot):
        """Left click on an equipment slot: pick up what is there, or wear / swap the cursor item."""
        p = self.player
        if self.cursor_mode:
            return self.identify_target(p.equipment.get(slot))
        if self.held is None:
            ok = self.pick_from_slot(slot)
        else:
            ok = self.equip_held(slot)
            if not ok and not self.slot_accepts(self.held, slot):
                self.log("That does not go there.", GREY)
        self.changed |= bool(ok)
        return ok

    def click_cell(self, cx, cy):
        """Left click on a backpack cell. With an item on the cursor, (cx, cy) is its top-left cell."""
        p = self.player
        if self.held is None:
            it = p.inv_at(cx, cy)
            if it is None:
                return False
            if self.cursor_mode:
                return self.identify_target(it)
            ok = self.pick_from_inventory(it)
        else:
            ok = self.place_held(cx, cy)
            if not ok:
                self.log("No room there.", GREY)
        self.changed |= bool(ok)
        return ok

    def right_click(self, it, sell=False):
        """Right click on a backpack item: potions go to the belt, identify scrolls and tomes pick
        a target, equipment is worn. With sell, the item is sold."""
        if it is None or self.held is not None:
            return False
        if sell:
            return self.sell(it)
        if is_charm(it):
            return self.backpack_to_charms(it)
        if it.kind == "potion":
            ok = self.use_inventory_potion(it)
        elif getattr(it, "use", None) == "id":
            if not any(not getattr(x, "identified", True) for x in self.all_items()):
                self.log("Everything is identified.", GREY)
                return False
            if (it.base or {}).get("tome") and getattr(it, "quantity", 1) <= 0:
                self.log("The tome is empty.", GREY)
                return False
            self.cursor_mode = ("identify", it)
            self.log("Click the item to identify.", GREY)
            return True
        elif it.kind == "equip" and getattr(it, "slot", None):
            ok = self.equip(it)
        else:
            return False
        self.changed |= bool(ok)
        return ok

    def unequip(self, slot):
        """Right click on a worn item: into the backpack."""
        p = self.player
        it = p.equipment.get(slot)
        if it is None or self.held is not None:
            return False
        if not p.inv_add(it):
            self.log("The backpack is full.", GREY)
            return False
        p.equipment[slot] = None
        p.recalc()
        self.changed = True
        return True

    # ------------------------------------------------------------ identify
    def all_items(self):
        p = self.player
        return list(p.inventory) + [x for x in p.equipment.values() if x] + \
            [x for x in (getattr(p, "swap_gear", None) or {}).values() if x]

    def identify_target(self, target):
        mode, self.cursor_mode = self.cursor_mode, None
        if not mode or target is None:
            return False
        if getattr(target, "identified", True):
            self.log("That is already identified.", GREY)
            return False
        scroll = mode[1]
        p = self.player
        if (scroll.base or {}).get("tome"):
            if getattr(scroll, "quantity", 0) <= 0:
                return False
            scroll.quantity -= 1
        elif scroll in p.inventory:
            p.inventory.remove(scroll)
            scroll.inv_pos = None
        else:
            return False
        d2items.identify(target)
        p.recalc()
        self.log("Identified: %s." % target.name, getattr(target, "color", GREY))
        self.changed = True
        return True

    def identify_all(self):
        """Identify every item the hero carries and wears (free, like Deckard Cain in town)."""
        n = sum(1 for it in self.all_items() if d2items.identify(it))
        self.player.recalc()
        self.log("Identified %d item%s." % (n, "" if n == 1 else "s") if n else "Nothing to identify.", GREY)
        self.changed |= bool(n)
        return n

    def unidentified(self):
        return sum(1 for it in self.all_items() if not getattr(it, "identified", True))

    # ------------------------------------------------------------ gold
    def sellable(self, it):
        from game.qol import is_goblin
        return it is not None and it.kind not in ("quest", "gold") and not is_goblin(it)

    def sell(self, it):
        p = self.player
        if not self.sellable(it):
            self.log("That can't be sold.", GREY)
            return False
        value = d2items.sell_price(it)
        if it is self.held:
            self.held = None
        elif it in p.inventory:
            p.inventory.remove(it)
        else:
            return False
        it.inv_pos = None
        p.gold += value
        self.log("Sold %s for %d gold." % (getattr(it, "shown_name", it.name), value), GREY)
        self.changed = True
        return True

    # ------------------------------------------------------------ weapon sets
    def swap_weapons(self):
        """D2's weapon swap (W): weapon set I and II change places."""
        p = self.player
        if not hasattr(p, "swap_gear") or p.swap_gear is None:
            p.swap_gear, p.weapon_set = {"weapon": None, "shield": None}, 0
        for slot in ("weapon", "shield"):
            p.equipment[slot], p.swap_gear[slot] = p.swap_gear.get(slot), p.equipment.get(slot)
        p.weapon_set = 1 - getattr(p, "weapon_set", 0)
        hp = p.hp / float(max(1, p.max_hp))
        p.recalc()
        p.hp = min(p.max_hp, max(1, int(round(p.max_hp * hp))))
        self.changed = True
        return True

    # ------------------------------------------------------------ the charm inventory
    def charm_box(self):
        return CharmBox(self.player)

    def charm_click(self, cx, cy):
        """Click on the charm inventory: pick up the charm there, or put the cursor charm down
        (centred on the mouse, the caller gives its top-left cell). Only charms go in."""
        from game import cube as cb
        box = self.charm_box()
        p = self.player
        if self.held is None:
            it = cb.at(box, cx, cy)
            if it is None:
                return False
            box.contents.remove(it)
            it.cube_pos = None
            self.held = it
            p.recalc()
            self.changed = True
            return True
        if not is_charm(self.held):
            self.log("Only charms go in the charm inventory.", GREY)
            return False
        ok, over = cb.fits(box, self.held, cx, cy)
        if not ok or len(over) > 1:
            self.log("No room there.", GREY)
            return False
        swap = over[0] if over else None
        if swap is not None:
            box.contents.remove(swap)
            swap.cube_pos = None
        self.held.cube_pos = (cx, cy)
        box.contents.append(self.held)
        self.held = swap
        p.recalc()
        self.changed = True
        return True

    def charm_to_backpack(self, it):
        p = self.player
        box = self.charm_box()
        if it not in box.contents or self.held is not None:
            return False
        box.contents.remove(it)
        pos, it.cube_pos = it.cube_pos, None
        if not p.inv_add(it):
            it.cube_pos = pos
            box.contents.append(it)
            self.log("The backpack is full.", GREY)
            return False
        p.recalc()
        self.changed = True
        return True

    def backpack_to_charms(self, it):
        from game import cube as cb
        p = self.player
        if it not in p.inventory or not is_charm(it):
            return False
        p.inventory.remove(it)
        pos, it.inv_pos = it.inv_pos, None
        if not cb.cube_add(self.charm_box(), it):
            it.inv_pos = pos
            p.inventory.append(it)
            self.log("The charm inventory is full.", GREY)
            return False
        p.recalc()
        self.changed = True
        return True

    # ------------------------------------------------------------ town: the shop
    #: Sanctuary's three traders (game/itemactions.py VENDORS: their stock is Malah's, Gheed's
    #: and Halbu's), and Hadriel's gambling
    SHOPS = [("tyrael3", "Tyrael", False), ("malachai", "Hadriel", False), ("izualghost", "Izual", False),
             ("malachai", "Gamble", True)]

    def store(self, npc, gamble=False):
        """The trader's shelves. The potions he sells follow the act of the hero's deepest floor."""
        if self.content is None:
            return None
        p = self.player
        from game import rift
        p.current_act = rift.act_of_depth(max(1, int(getattr(p, "rift_depth", 0) or 0)))
        try:
            return self.open_store(npc, gamble=gamble)
        except Exception:
            import traceback
            traceback.print_exc()
            return None

    def buy_item(self, store, it):
        if self.held is not None or store is None:
            return False
        ok = self.buy(store, it)
        self.changed |= bool(ok)
        return ok

    # ------------------------------------------------------------ town: the shared stash
    def stash_page(self):
        st = self.stash
        return None if st is None or st.tab == 0 else st

    def stash_click(self, cx, cy):
        """Click on the stash grid: pick up the item there, or put the cursor item down (with it
        centred on the mouse, the caller gives its top-left cell); swaps with one item, like D2."""
        from game import cube as cb
        st = self.stash_page()
        if st is None:
            return False
        if self.held is None:
            it = cb.at(st, cx, cy)
            if it is None:
                return False
            st.contents.remove(it)
            it.cube_pos = None
            self.held = it
            return True
        ok, over = cb.fits(st, self.held, cx, cy)
        if not ok or len(over) > 1:
            self.log("No room there.", GREY)
            return False
        swap = over[0] if over else None
        if swap is not None:
            st.contents.remove(swap)
            swap.cube_pos = None
        self.held.cube_pos = (cx, cy)
        st.contents.append(self.held)
        self.held = swap
        return True

    def stash_to_backpack(self, it):
        st = self.stash_page()
        if st is None or it not in st.contents or self.held is not None:
            return False
        it.cube_pos = None
        if not self.player.inv_add(it):
            it.cube_pos = None
            from game.cube import cube_add
            st.contents.remove(it)
            cube_add(st, it)
            self.log("The backpack is full.", GREY)
            return False
        st.contents.remove(it)
        self.changed = True
        return True

    def backpack_to_stash(self, it):
        """Ctrl + click in the backpack with the stash open: straight into the stash."""
        from game import cube as cb
        st = self.stash
        p = self.player
        if st is None or it not in p.inventory:
            return False
        if cb.bankable(it):
            p.inventory.remove(it)
            it.inv_pos = None
            st.bank[it.code] = st.bank.get(it.code, 0) + 1
            self.changed = True
            return True
        page = self.stash_page()
        if page is None:
            return False
        p.inventory.remove(it)
        pos, it.inv_pos = it.inv_pos, None
        if not cb.cube_add(page, it):
            it.inv_pos = pos
            p.inventory.append(it)
            self.log("This stash tab is full.", GREY)
            return False
        self.changed = True
        return True

    def bank_deposit(self):
        from game import cube as cb
        st, it = self.stash, self.held
        if st is None or it is None or not cb.bankable(it):
            return False
        self.held = None
        st.bank[it.code] = st.bank.get(it.code, 0) + 1
        return True

    def bank_take(self, code, to_backpack=False):
        st, c = self.stash, self.content
        if st is None or c is None or st.bank.get(code, 0) <= 0:
            return None
        if not to_backpack and self.held is not None:
            return None
        base = c.base_by_code.get(code)
        it = c.make_item(base, 1, self.rng) if base is not None else None
        if it is None:
            return None
        if to_backpack:
            if not self.player.inv_add(it):
                self.log("The backpack is full.", GREY)
                return None
            self.changed = True
        else:
            self.held = it
        st.bank[code] -= 1
        if st.bank[code] <= 0:
            del st.bank[code]
        return it

    # ------------------------------------------------------------ closing the screen
    def _into_stash(self, it):
        from game import cube as cb
        st = self.stash
        if st is None:
            return False
        if cb.bankable(it):
            st.bank[it.code] = st.bank.get(it.code, 0) + 1
            return True
        for i, page in enumerate(st.pages):
            box = type("Page", (), {})()
            box.contents, box.grid_size = page, st.grid_size
            if cb.cube_add(box, it):
                return True
        return False

    def finish(self):
        """The cursor item and the floor go back into the backpack (in town, else into the stash);
        what has no room is sold.
        Returns how many items were sold that way."""
        p = self.player
        self.cursor_mode = None
        loose = ([self.held] if self.held is not None else []) + self.floor()
        self.held, self.ground = None, {}
        sold = 0
        from game import cube as cb
        for it in loose:
            it.inv_pos = None
            if is_charm(it) and cb.cube_add(self.charm_box(), it):
                continue
            if p.inv_add(it):
                continue
            if self._into_stash(it):
                continue
            if self.sellable(it):
                p.gold += d2items.sell_price(it)
                sold += 1
                self.log("No room: sold %s." % getattr(it, "shown_name", it.name), GREY)
            else:
                p.inventory.append(it)          # quest items are never lost: kept, unplaced
        if loose:
            self.changed = True
        return sold
