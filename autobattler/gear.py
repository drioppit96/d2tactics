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
from game import d2items
from game.world import World

ROWS = 8
GREY = (170, 170, 170)


def prepare(p):
    """Give an autobattler hero the double backpack."""
    if p is None:
        return p
    q = getattr(p, "qol", None)
    if not isinstance(q, dict):
        q = p.qol = {}
    q["big_inv"] = True
    q["inv_rows"] = ROWS
    return p


class Bench:
    """Just enough World for the item methods, acting on one hero."""
    mode = "explore"
    turn = "player"

    def __init__(self, hero, content=None):
        self.player = hero
        self.content = content
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

    # ------------------------------------------------------------ closing the screen
    def finish(self):
        """The cursor item and the floor go back into the backpack; what has no room is sold.
        Returns how many items were sold that way."""
        p = self.player
        self.cursor_mode = None
        loose = ([self.held] if self.held is not None else []) + self.floor()
        self.held, self.ground = None, {}
        sold = 0
        for it in loose:
            it.inv_pos = None
            if p.inv_add(it):
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
