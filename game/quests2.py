"""Act 2 quests: Radament's Lair, The Horadric Staff, Tainted Sun, Arcane Sanctuary, The Summoner,
The Seven Tombs. State lives on the player (player.quests) like Act 1's.

Story text is written for this project (it paraphrases what happens in D2, it doesn't copy the
game's dialogue).
"""
QUEST_COLOR = (199, 179, 119)
DONE_COLOR = (0, 220, 0)
GREY = (170, 170, 170)
TALK = (220, 210, 170)

ACT2 = [
    ("radament", "Radament's Lair"),
    ("staff", "The Horadric Staff"),
    ("tainted", "Tainted Sun"),
    ("arcane", "Arcane Sanctuary"),
    ("summoner", "The Summoner"),
    ("tombs", "The Seven Tombs"),
]

JOURNAL = {
    "radament": {
        "active": "Atma wants revenge on Radament, who lurks in the sewers beneath Lut Gholein (the entrance is in town).",
        "cleared": "Radament is dead. Return to Atma.",
        "done": "Completed. The Book of Skill Radament guarded teaches you a new skill point.",
    },
    "staff": {
        "active": "Deckard Cain can remake the Horadric Staff. Find the Horadric Cube (Halls of the Dead, "
                  "Dry Hills), the Staff of Kings (Maggot Lair, Far Oasis) and the Amulet of the Viper "
                  "(Claw Viper Temple, Valley of Snakes). Join the staff and the amulet in the cube.",
        "cleared": "You have remade the Horadric Staff. Show it to Cain.",
        "done": "Completed. The Horadric Staff opens the true Tal Rasha's Tomb.",
    },
    "tainted": {
        "active": "Something has blotted out the sun. Drognan thinks a dark altar in the Claw Viper Temple "
                  "(Valley of Snakes, off the Lost City) is to blame.",
        "cleared": "You smashed the altar and the sun shines again. Tell Drognan.",
        "done": "Completed.",
    },
    "arcane": {
        "active": "Drognan says the Summoner hides in the Arcane Sanctuary, whose door is somewhere in the palace. "
                  "Ask Jerhyn to let you in.",
        "palace": "Jerhyn has opened the palace. Search the Palace Cellar for the way into the Arcane Sanctuary.",
        "done": "Completed. You found the Arcane Sanctuary.",
    },
    "summoner": {
        "active": "The Summoner waits somewhere in the Arcane Sanctuary. Kill him.",
        "cleared": "The Summoner is dead. Read Horazon's Journal beside him.",
        "done": "Completed. The journal showed the true tomb's symbol and opened a portal to the Canyon of the Magi.",
    },
    "tombs": {
        "active": "Find the true Tal Rasha's Tomb in the Canyon of the Magi and place the Horadric Staff in its orifice.",
        "placed": "The staff is in place and the way to Duriel's Lair is open. Kill Duriel.",
        "cleared": "Duriel is dead. Talk to Tyrael, then to Jerhyn; Meshif will take you east.",
        "done": "Completed. Act 2 is finished.",
    },
}

NPC_ACT2 = {"atma", "cain2", "drognan", "jerhyn", "meshif1", "greiz", "warriv2", "tyrael1", "fara", "lysander",
            "elzix", "geglash"}


def init(p):
    for q, _ in ACT2:
        p.quests.setdefault(q, "none")


def _start(world, qid):
    q = world.player.quests
    if q.get(qid) == "none":
        q[qid] = "active"
        world.log("New quest: %s (Quest Log: Q)." % dict(ACT2)[qid], QUEST_COLOR)
        world.emit("quest", qid)
        return True
    return False


# ------------------------------------------------------------------ items
def has_item(p, code, world=None):
    pools = list(p.inventory) + [x for x in p.equipment.values() if x] + list(getattr(p, "belt", []))
    if world is not None and getattr(world, "held", None) is not None:
        pools.append(world.held)
    for it in list(pools):
        if getattr(it, "code", "") == code:
            return True
        for c in getattr(it, "contents", None) or []:
            if c.code == code:
                return True
    return False


def take_item(world, code):
    p = world.player
    for it in list(p.inventory):
        if it.code == code:
            p.inventory.remove(it)
            it.inv_pos = None
            return it
        box = getattr(it, "contents", None)
        if box:
            for c in list(box):
                if c.code == code:
                    box.remove(c)
                    c.cube_pos = None
                    return c
    if getattr(world, "held", None) is not None and world.held.code == code:
        it, world.held = world.held, None
        return it
    return None


def give_item(world, code, near=None, quiet=False):
    """A quest item into the backpack (or onto the ground next to you if it's full)."""
    c = world.content
    if c is None or code not in c.base_by_code:
        return None
    it = c.make_item(c.base_by_code[code], 1, world.rng)
    if it is None:
        return None
    p = world.player
    if near is None and p.inv_add(it):
        if not quiet:
            world.log("You receive %s." % it.name, it.color)
        return it
    cell = world._drop_cell(near or p.pos)
    world.ground.setdefault(cell, []).append(it)
    world.emit("drop", cell, it)
    return it


# ------------------------------------------------------------------ talking
def talk(world, npc):
    p = world.player
    q = p.quests
    who = npc.npc
    lines = []
    if who == "atma":
        if q["radament"] == "none":
            _start(world, "radament")
            lines = ["Atma: A monster called Radament crawls in the sewers below the city. He killed my family.",
                     "Atma: Find him down there and end him. The way in is here in town."]
        elif q["radament"] == "active":
            lines = ["Atma: Radament still lives. Please - the sewers."]
        elif q["radament"] == "cleared":
            q["radament"] = "done"
            lines = ["Atma: He's dead? Then my family can rest. Thank you, stranger.",
                     "Atma: Whatever he guarded down there is yours by right."]
            world.log("Quest completed: Radament's Lair.", DONE_COLOR)
        elif q["tombs"] in ("cleared", "done"):
            lines = ["Atma: The whole city is talking about you. Duriel - dead!"]
    elif who == "cain2":
        if q["staff"] == "none":
            _start(world, "staff")
            lines = ["Deckard Cain: Tal Rasha's Tomb is sealed, and only the Horadric Staff opens it.",
                     "Deckard Cain: The staff was broken in two - the Staff of Kings and the Amulet of the Viper.",
                     "Deckard Cain: Find both, and the Horadric Cube to join them. The Cube lies in the Halls of the Dead."]
        elif q["staff"] == "cleared":
            q["staff"] = "done"
            lines = ["Deckard Cain: The Horadric Staff, whole again! Take it to the true Tal Rasha's Tomb.",
                     "Deckard Cain: Seven tombs lie in the Canyon of the Magi; only one is real. The Summoner's "
                     "notes might tell which."]
            world.log("Quest completed: The Horadric Staff.", DONE_COLOR)
            if q["tombs"] == "none":
                _start(world, "tombs")
        elif q["staff"] == "active":
            parts = [("box", "the Horadric Cube"), ("msf", "the Staff of Kings"), ("vip", "the Amulet of the Viper")]
            missing = [n for c, n in parts if not has_item(p, c, world)]
            if missing:
                lines = ["Deckard Cain: You still need %s." % ", ".join(missing)]
            else:
                lines = ["Deckard Cain: You have everything! Put the staff and the amulet in the Cube and transmute them."]
        elif q["summoner"] == "done" and q["tombs"] in ("none", "active"):
            lines = ["Deckard Cain: Horazon's journal points to the true tomb. Its symbol matches the one in your log."]
    elif who == "drognan":
        if q["tainted"] == "active":
            lines = ["Drognan: The sun has gone dark! A ritual is to blame - seek the Claw Viper Temple in the Valley "
                     "of Snakes and break the altar there."]
        elif q["tainted"] == "cleared":
            q["tainted"] = "done"
            lines = ["Drognan: The sun is back. You have my thanks."]
            world.log("Quest completed: Tainted Sun.", DONE_COLOR)
        if q["tainted"] in ("done", "none") and q["arcane"] == "none" and (q["tainted"] == "done" or
                                                                           q["staff"] in ("cleared", "done")):
            _start(world, "arcane")
            lines = lines + ["Drognan: The Summoner knows where Tal Rasha's true tomb lies. He hides in Horazon's "
                             "Arcane Sanctuary - its door is beneath the palace. Ask Jerhyn to let you in."]
    elif who == "jerhyn":
        if q["arcane"] in ("none", "active"):
            if q["arcane"] == "none":
                _start(world, "arcane")
            q["arcane"] = "palace"
            lines = ["Jerhyn: Drognan sent you? Then go - my guards will let you into the palace.",
                     "Jerhyn: Whatever crawls in the cellars below, end it."]
            world.log("The palace is open. Its stairs lead down to the Palace Cellar.", QUEST_COLOR)
        elif q["tombs"] == "cleared":
            q["tombs"] = "done"
            lines = ["Jerhyn: Duriel is dead and the palace is ours again. Meshif's ship can take you east, to Kurast."]
            world.log("Quest completed: The Seven Tombs. Act 2 is finished!", DONE_COLOR)
    elif who == "meshif1":
        if q["tombs"] in ("cleared", "done"):
            lines = ["Meshif: The seas are open again. Say the word and we sail for Kurast."]
        else:
            lines = ["Meshif: My ship stays in port until Jerhyn says the way is safe."]
    elif who == "tyrael1":
        if q["tombs"] in ("cleared", "done"):
            lines = ["Tyrael: You have freed me. Diablo and Baal have gone east to free their brother, Mephisto.",
                     "Tyrael: Go to Kurast and stop them. I will open the way back to Lut Gholein."]
            open_portal(world, world.player.pos, 40, "portal")
        else:
            lines = ["Tyrael: Destroy Duriel, and quickly!"]
    elif who == "greiz":
        lines = ["Greiz: My desert guards fight for gold. Choose Hire if you want one."]
    elif who == "warriv2":
        lines = ["Warriv: Lut Gholein. Mind your purse in the market."]
    return lines


HIRELINGS = {"act2hire": ("Desert Guard", "Greiz", "melee"), "act3hire": ("Iron Wolf", "Asheara", "ranged"),
             "act5hire1": ("Barbarian", "Qual-Kehk", "melee")}


def hire_guard(world, free=False, kind="act2hire"):
    """A hireling of the act (D2's act2hire / act3hire / act5hire1) for gold - or your dead one back."""
    from . import hireling
    p = world.player
    title, boss, style = HIRELINGS.get(kind, HIRELINGS["act2hire"])
    merc = getattr(p, "merc", None)
    if free:
        return hireling.spawn(world, kind) is not None
    if merc is not None and merc.get("dead"):
        cost = hireling.resurrect_cost(merc)
        if not hireling.resurrect(world):
            world.log("%s: I can bring %s back for %d gold." % (boss, merc["name"], cost), TALK)
            return False
        return True
    if any(getattr(a, "hireling", False) and a.alive for a in world.allies()) and merc is not None \
            and merc["kind"] == kind:
        world.log("%s: You already have one of mine at your side." % boss, TALK)
        return False
    cost = 60 * p.level + 100
    if p.gold < cost:
        world.log("%s: %d gold, and one of mine is yours." % (boss, cost), TALK)
        return False
    p.gold -= cost
    # the old hireling leaves; whatever they wore goes back to you
    for a in list(world.allies()):
        if getattr(a, "hireling", False):
            a.alive = False
            world.emit("death", a)
    if merc is not None:
        for it in (merc.get("items") or {}).values():
            if it is not None and not p.inv_add(it):
                world.ground.setdefault(p.pos, []).append(it)
                world.emit("drop", p.pos, it)
    p.merc = hireling.new_merc(world, kind)
    m = hireling.spawn(world, kind)
    if m is not None:
        world.log("%s: %s will fight for you. Keep them alive." % (boss, p.merc["name"]), TALK)
    return m is not None


# ------------------------------------------------------------------ places
def blocked(world, target):
    """A message if the way into `target` is closed (the palace before Jerhyn opens it)."""
    q = world.player.quests
    if target == 50 and q.get("arcane") not in ("palace", "done") and q.get("summoner") != "done":
        return "A guard: Nobody enters the palace without Jerhyn's word."
    return None


def on_enter(world, lid):
    q = world.player.quests
    if lid == 47 and q["radament"] == "none":
        _start(world, "radament")
    if lid in (44, 45, 58, 61) and q["tainted"] == "none":
        _start(world, "tainted")
        world.log("The sun goes dark...", (200, 120, 120))
    if lid in (60, 62, 61) and q["staff"] == "none":
        _start(world, "staff")
    if lid == 74:
        if q["arcane"] != "done":
            q["arcane"] = "done"
            world.log("Quest completed: Arcane Sanctuary.", DONE_COLOR)
        if q["summoner"] == "none":
            _start(world, "summoner")
    if lid == 46 and q["tombs"] == "none":
        _start(world, "tombs")
    restore(world)


def restore(world):
    """Quest objects that exist because of what you did (portals opened in earlier visits)."""
    p = world.player
    q = getattr(p, "quests", {})
    key = getattr(world, "level_key", None)
    if key == 74 and q.get("summoner") == "done":
        j = next((o for o in world.objects if o["kind"] == "journal"), None)
        if j is not None:
            j["used"] = True
            _ensure_portal(world, j["cell"], 46, "portal")
    from . import act2
    real = act2.CURRENT_REAL
    if key == real and q.get("tombs") in ("placed", "cleared", "done"):
        o = next((o for o in world.objects if o["kind"] == "orifice"), None)
        if o is not None:
            o["used"] = True
            _ensure_portal(world, o["cell"], 73, "duriel_portal")
    if key == 38 and not any(o["kind"] == "wirt" for o in world.objects):
        cage = next((o for o in world.objects if o["kind"] == "cage"), None)
        if cage is not None:
            cell = world._free_cell_near((cage["cell"][0] - 10, cage["cell"][1] + 8), 8)
            world.objects.append(dict(kind="wirt", cell=cell, level=38, oid=0, used=False))
    if key == 39:
        start = world.entries.get(1) or world._default_start()
        _ensure_portal(world, (start[0] - 6, start[1] - 3), 1, "portal")
    if key == 73 and q.get("tombs") in ("cleared", "done"):
        _ensure_tyrael(world)
    # Tainted Sun: the sky stays dark outdoors in Act 2 while the altar stands
    world.sun_dark = q.get("tainted") == "active"
    from .acts import ACT2_OUTDOOR
    lid = getattr(world, "level_id", None)
    if lid in ACT2_OUTDOOR or lid == 46:
        if world.sun_dark:
            world.ambient = max(getattr(world, "ambient", 0), 190)
        elif lid not in (40,):
            world.ambient = min(getattr(world, "ambient", 120), 120)


def _ensure_portal(world, near, target, kind):
    if any(o["kind"] == kind and o.get("target") == target for o in world.objects):
        return
    open_portal(world, near, target, kind, quiet=True)


def open_portal(world, near, target, kind="portal", quiet=False):
    cell = world._free_cell_near((near[0] + 2, near[1] + 1), 5)
    world.objects.append(dict(kind=kind, cell=cell, level=world.level_id, oid=0, used=False, target=target))
    world.entries.setdefault(target, world._free_cell_near((cell[0] + 1, cell[1] + 2), 4))
    if not quiet:
        world.emit("nova", world.player, cell, 3, "fire")
    return cell


def _ensure_tyrael(world):
    if any(getattr(n, "npc", "") == "tyrael1" for n in world.npcs):
        return
    from .world import NPC_NAMES
    from .units import Monster
    c = world.content
    p = world.player
    cell = world._free_cell_near((p.x + 3, p.y - 2), 6)
    t = c.monster_template("tyrael1") if c is not None and "tyrael1" in c.monstats else None
    m = Monster("zombie", *cell, rng=world.rng, template=t)
    m.npc = "tyrael1"
    m.name = NPC_NAMES.get("tyrael1", "Tyrael")
    m.ai = "npc"
    m.aware = False
    world.npcs.append(m)
    world.monsters.append(m)


# ------------------------------------------------------------------ objects
def on_object(world, obj):
    p = world.player
    q = p.quests
    k = obj["kind"]
    if k == "scroll_chest":
        if obj["used"]:
            return False
        obj["used"] = True
        if not has_item(p, "tr1", world) and q["staff"] in ("none", "active"):
            give_item(world, "tr1", near=obj["cell"])
            world.log("Inside the chest: a Horadric Scroll.", QUEST_COLOR)
        else:
            world.log("The chest is empty.", GREY)
        return True
    if k == "cube_chest":
        if obj["used"]:
            return False
        obj["used"] = True
        if not has_item(p, "box", world):
            give_item(world, "box", near=obj["cell"])
            world.log("You found the Horadric Cube! Right click it in your backpack to open it.", QUEST_COLOR)
            if q["staff"] == "none":
                _start(world, "staff")
        else:
            world.log("The chest is empty.", GREY)
        return True
    if k == "staff_chest":
        if obj["used"]:
            return False
        obj["used"] = True
        if q["staff"] in ("none", "active") and not has_item(p, "msf", world) and not has_item(p, "hst", world):
            give_item(world, "msf", near=obj["cell"])
            world.log("You found the Staff of Kings!", QUEST_COLOR)
            if q["staff"] == "none":
                _start(world, "staff")
        else:
            world.log("The chest is empty.", GREY)
        return True
    if k == "viper_altar":
        if obj["used"]:
            return False
        obj["used"] = True
        world.emit("nova", p, obj["cell"], 3, "ltng")
        if q["tainted"] in ("none", "active"):
            q["tainted"] = "cleared"
            world.sun_dark = False
            world.log("You smash the altar. Light floods back into the world! Tell Drognan.", QUEST_COLOR)
        if q["staff"] in ("none", "active") and not has_item(p, "vip", world) and not has_item(p, "hst", world):
            give_item(world, "vip", near=obj["cell"])
            world.log("The Amulet of the Viper lay on the altar.", QUEST_COLOR)
            if q["staff"] == "none":
                _start(world, "staff")
        return True
    if k == "journal":
        if q["summoner"] in ("none", "active"):
            world.log("Horazon's Journal. Its pages are sealed by the Summoner's magic - kill him first.", GREY)
            return False
        if q["summoner"] == "cleared":
            q["summoner"] = "done"
            obj["used"] = True
            world.log("Horazon's Journal shows the symbol of the true Tal Rasha's Tomb...", QUEST_COLOR)
            world.log("Quest completed: The Summoner. A portal to the Canyon of the Magi opens.", DONE_COLOR)
            open_portal(world, obj["cell"], 46, "portal")
            if q["tombs"] == "none":
                _start(world, "tombs")
            from . import act2
            if act2.CURRENT_REAL:
                info = getattr(world, "info", None)
                name = info.name(act2.CURRENT_REAL) if info else "the tomb"
                world.log("The symbol marks %s." % name, QUEST_COLOR)
            return True
        _ensure_portal(world, obj["cell"], 46, "portal")
        return True
    if k == "orifice":
        if obj["used"]:
            return False
        if q["tombs"] in ("placed", "cleared", "done"):
            return False
        if not has_item(p, "hst", world):
            if has_item(p, "msf", world) or has_item(p, "vip", world):
                world.log("The orifice needs the whole Horadric Staff. Join its parts in the Horadric Cube.", GREY)
            else:
                world.log("An empty orifice. Something long and Horadric belongs in it.", GREY)
            return False
        take_item(world, "hst")
        obj["used"] = True
        q["tombs"] = "placed"
        if q["staff"] != "done":
            q["staff"] = "done"
        world.emit("nova", p, obj["cell"], 4, "ltng")
        open_portal(world, obj["cell"], 73, "duriel_portal")
        world.log("You place the Horadric Staff in the orifice. The floor shakes - the way to Duriel's Lair opens!",
                  QUEST_COLOR)
        return True
    return None


def read_horadric_scroll(world, it):
    p = world.player
    q = p.quests
    if it in p.inventory:
        p.inventory.remove(it)
        it.inv_pos = None
    world.log("The Horadric Scroll tells of the Horadric Staff and the Cube that can restore it.", QUEST_COLOR)
    if q["staff"] == "none":
        _start(world, "staff")
    else:
        world.log("Take the knowledge to Deckard Cain.", GREY)


def on_transmute(world, box):
    q = world.player.quests
    if any(c.code == "hst" for c in getattr(box, "contents", []) or []) and q["staff"] in ("none", "active"):
        q["staff"] = "cleared"
        world.log("The Horadric Staff is whole again! Show it to Deckard Cain.", QUEST_COLOR)


def on_killed(world, unit):
    p = world.player
    q = p.quests
    boss = getattr(unit, "boss", None)
    if boss == "radament":
        if q["radament"] in ("none", "active"):
            q["radament"] = "cleared"
            world.log("Radament is slain! Return to Atma.", QUEST_COLOR)
        give_item(world, "ass", near=unit.pos)
        world.log("Radament dropped a Book of Skill.", QUEST_COLOR)
    elif boss == "summoner":
        if q["summoner"] in ("none", "active"):
            q["summoner"] = "cleared"
            world.log("The Summoner is dead! Read Horazon's Journal.", QUEST_COLOR)
    elif boss == "duriel":
        if q["tombs"] in ("none", "active", "placed"):
            q["tombs"] = "cleared"
            world.log("Duriel, the Lord of Pain, is dead! Tyrael is free.", QUEST_COLOR)
            world.emit("victory")
        _ensure_tyrael(world)
    elif boss == "coldworm":
        world.log("Coldworm falls. The Staff of Kings must be in the chest nearby.", QUEST_COLOR)
