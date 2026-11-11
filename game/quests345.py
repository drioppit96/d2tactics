"""Act 3-5 quests. State lives on the player (player.quests) like the other acts'.

Act 3: The Golden Bird, Blade of the Old Religion, Khalim's Will, Lam Esen's Tome,
       The Blackened Temple, The Guardian
Act 4: The Fallen Angel, Hell's Forge, Terror's End
Act 5: Siege on Harrogath, Rescue on Mount Arreat, Prison of Ice, Betrayal of Harrogath,
       Rite of Passage, Eve of Destruction

Story text is written for this project (it paraphrases what happens in D2, it doesn't copy the
game's dialogue). Some D2 details are simplified for turn-based play (noted per quest).
"""
from .quests2 import give_item, has_item, take_item, open_portal, _ensure_portal

QUEST_COLOR = (199, 179, 119)
DONE_COLOR = (0, 220, 0)
GREY = (170, 170, 170)
TALK = (220, 210, 170)

ACTS = {
    3: [("bird", "The Golden Bird"), ("gidbinn", "Blade of the Old Religion"), ("khalim", "Khalim's Will"),
        ("lamesen", "Lam Esen's Tome"), ("council", "The Blackened Temple"), ("mephisto", "The Guardian")],
    4: [("izual", "The Fallen Angel"), ("forge", "Hell's Forge"), ("diablo", "Terror's End")],
    5: [("shenk", "Siege on Harrogath"), ("barbs", "Rescue on Mount Arreat"), ("anya", "Prison of Ice"),
        ("nihl", "Betrayal of Harrogath"), ("ancients", "Rite of Passage"), ("baal", "Eve of Destruction")],
}
TITLES = {q: t for lst in ACTS.values() for q, t in lst}
JOURNAL = {
    "bird": {"active": "Somewhere in Lower Kurast or the Kurast Armory a unique monster carries a Jade Figurine. "
                       "Show it to Meshif.",
             "jade": "You have the Jade Figurine. Show it to Meshif.",
             "bird": "Meshif gave you a Golden Bird for the figurine. Alkor wants to see it.",
             "potion": "Alkor brewed you a Potion of Life from the bird's ashes. Drink it.",
             "done": "Completed. The Potion of Life gave you +20 Life."},
    "gidbinn": {"active": "Ormus says the Gidbinn, a sacred blade, is held by the smith of the Kurast Armory "
                           "(east of the Kurast Bazaar). Open the four hellish seals in the armory's corners to call him out.",
                "cleared": "You have the Gidbinn. Bring it to Ormus.",
                "done": "Completed. Ormus gave you a ring."},
    "khalim": {"active": "Remake Khalim's Will: his Eye (Silkmother Vashra, Kurast Armory), Brain (Scribe Ophizek, "
                         "Kurast Scriptorium beside the Bazaar), Heart (Sewers Level 2) and Flail (the High Council "
                         "in Travincal). Join them in the Horadric Cube.",
               "cleared": "Khalim's Will is whole. Smash the Compelling Orb in Travincal with it.",
               "orb": "The Compelling Orb is broken - the way into the Durance of Hate is open.",
               "done": "Completed."},
    "lamesen": {"active": "Alkor wants Lam Esen's Tome. It is in one of the six temples of Kurast.",
                "cleared": "You found Lam Esen's Tome. Bring it to Alkor.",
                "done": "Completed. Alkor's reading gave you +5 stat points."},
    "council": {"active": "The High Council of Zakarum rules Travincal. Kill all of its members you find there.",
                "cleared": "The council in Travincal is dead. Tell Cain.",
                "done": "Completed."},
    "mephisto": {"active": "Mephisto waits in the depths of the Durance of Hate.",
                 "cleared": "Mephisto is dead! His red portal leads to the Pandemonium Fortress.",
                 "done": "Completed. Act 3 is finished."},
    "izual": {"active": "Tyrael asks you to free the soul of the fallen angel Izual, on the Plains of Despair.",
              "cleared": "Izual is free. Talk to Tyrael.",
              "done": "Completed. Tyrael gave you 2 skill points."},
    "forge": {"active": "Cain says Mephisto's Soulstone must be destroyed on the Hellforge in the River of Flame "
                        "(Hephasto the Armorer guards it).",
              "cleared": "The Soulstone is shattered. Tell Cain.",
              "done": "Completed. The Hellforge gave you gems and runes."},
    "diablo": {"active": "Diablo waits in the Chaos Sanctuary at the end of the River of Flame.",
               "cleared": "Diablo is dead! Tyrael can send you to Harrogath.",
               "done": "Completed. Act 4 is finished."},
    "shenk": {"active": "Larzuk asks you to kill Shenk the Overseer, who drives Baal's army in the Bloody Foothills.",
              "cleared": "Shenk is dead. Larzuk will put sockets in one of your items (Imbue Sockets).",
              "done": "Completed. Larzuk socketed an item for you."},
    "barbs": {"active": "Qual-Kehk's soldiers are held in prisons in the Frigid Highlands. Break the prisons.",
              "cleared": "The soldiers are free. Talk to Qual-Kehk.",
              "done": "Completed. Qual-Kehk gave you runes; his soldiers fight for you."},
    "anya": {"active": "Anya is frozen in the Frozen River below the Crystalline Passage. Malah has a potion for her.",
             "cleared": "Anya is free and back in Harrogath. Talk to Malah.",
             "done": "Completed. Malah's scroll gave you +10 to all resistances."},
    "nihl": {"active": "Nihlathak betrayed Harrogath. Anya's portal leads to his temple: kill him in the Halls of Vaught.",
             "cleared": "Nihlathak is dead. Tell Anya.",
             "done": "Completed. Anya gave you an item."},
    "ancients": {"active": "The three Ancients guard the summit of Mount Arreat. Defeat them to enter the Worldstone Keep.",
                 "cleared": "The Ancients let you pass into the Worldstone Keep.",
                 "done": "Completed."},
    "baal": {"active": "Baal is at the top of the Worldstone Keep. Clear his Throne and follow him to the Worldstone.",
             "cleared": "Baal is dead! Talk to Tyrael.",
             "done": "Completed. You have saved Sanctuary."},
}
NPCS = {"cain3", "ormus", "alkor", "meshif2", "asheara", "hratli", "natalya", "tyrael2", "cain4", "jamella", "halbu",
        "larzuk", "malah", "qual-kehk", "drehya", "tyrael3", "cain6", "nihlathak"}
COUNCIL_LEVEL = 83


def init(p):
    for lst in ACTS.values():
        for q, _ in lst:
            p.quests.setdefault(q, "none")
    if not hasattr(p, "quest_stats"):
        p.quest_stats = {}


def _start(world, qid):
    q = world.player.quests
    if q.get(qid) == "none":
        q[qid] = "active"
        world.log("New quest: %s (Quest Log: Q)." % TITLES[qid], QUEST_COLOR)
        world.emit("quest", qid)
        return True
    return False


def _done(world, qid, extra=""):
    world.player.quests[qid] = "done"
    world.log("Quest completed: %s.%s" % (TITLES[qid], (" " + extra) if extra else ""), DONE_COLOR)


def _hash(text):
    h = 0
    for ch in str(text or ""):
        h = (h * 131 + ord(ch)) & 0xFFFFFF
    return h


def lamesen_temple(player):
    """Which of the six temples holds Lam Esen's Tome (fixed per hero)."""
    return 94 + _hash(getattr(player, "name", "")) % 6


# ------------------------------------------------------------------ talking
def talk(world, npc):
    p = world.player
    q = p.quests
    who = npc.npc
    lines = []
    if who == "meshif2":
        if q["bird"] == "none":
            _start(world, "bird")
        if has_item(p, "j34", world):
            take_item(world, "j34")
            give_item(world, "g34")
            q["bird"] = "bird"
            lines = ["Meshif: A jade figurine! Here - an old golden bird for it. Alkor collects such things."]
        else:
            lines = ["Meshif: The ship can take you back to Lut Gholein whenever you wish."]
    elif who == "alkor":
        if has_item(p, "g34", world):
            take_item(world, "g34")
            give_item(world, "xyz")
            q["bird"] = "potion"
            lines = ["Alkor: The golden bird of the Kurast emperors! I've made you a Potion of Life from its ashes."]
        elif has_item(p, "bbb", world):
            from . import tactics
            take_item(world, "bbb")
            for h in tactics.everyone(world):        # Alkor reads the tome out to the whole party
                h.stat_points += 5
            _done(world, "lamesen", "+5 stat points for every hero.")
            lines = ["Alkor: Lam Esen's Tome! Let me read some of it to you - you'll feel the knowledge in your bones."]
        elif q["lamesen"] == "none":
            _start(world, "lamesen")
            lines = ["Alkor: Lam Esen wrote a tome about the Prime Evils. It's hidden in one of Kurast's temples."]
        else:
            lines = ["Alkor: Potions, poultices... and a little gamble now and then, eh?"]
    elif who == "ormus":
        if q["gidbinn"] == "none":
            _start(world, "gidbinn")
            lines = ["Ormus: The Gidbinn - a sacred blade - is held by the pale smith of the Kurast Armory, east "
                     "of the Bazaar. Open the four hellish seals in its corners and he will come out. Ormus needs the blade."]
        elif has_item(p, "g33", world):
            take_item(world, "g33")
            _done(world, "gidbinn", "A ring for you.")
            from .quests import _reward_item
            _reward_item(world, "ring", "Ormus")
            lines = ["Ormus: The Gidbinn! Its power will keep the docks safe. Take this, with Ormus' thanks."]
        else:
            lines = ["Ormus: Ormus sees much, stranger. Ormus will mend your wounds."]
    elif who == "cain3":
        if q["khalim"] == "none":
            _start(world, "khalim")
            lines = ["Deckard Cain: The Compelling Orb in Travincal bars the way to Mephisto. Only Khalim's Will can "
                     "break it: find his Eye, Brain, Heart and Flail and join them in the Cube."]
        elif q["council"] == "cleared":
            _done(world, "council")
            lines = ["Deckard Cain: The council is dead. Now the Durance of Hate - and Mephisto."]
        elif q["khalim"] == "active":
            parts = [("qey", "the Eye (Silkmother Vashra, Kurast Armory)"),
                     ("qbr", "the Brain (Scribe Ophizek, Kurast Scriptorium)"),
                     ("qhr", "the Heart (Kurast Sewers)"), ("qf1", "the Flail (the High Council)")]
            missing = [n for c, n in parts if not has_item(p, c, world)]
            lines = ["Deckard Cain: You still need %s." % ", ".join(missing)] if missing else \
                ["Deckard Cain: You have them all. Join them in the Horadric Cube."]
    elif who == "tyrael2":
        if q["izual"] == "none":
            _start(world, "izual")
            lines = ["Tyrael: Izual, my lieutenant, fell to Hell. Free his soul - he lurks on the Plains of Despair."]
        elif q["izual"] == "cleared":
            from . import tactics
            for h in tactics.everyone(world):        # Tyrael's gift is for all of you
                h.skills.points += 2
            _done(world, "izual", "+2 skill points for every hero.")
            lines = ["Tyrael: Izual is at peace. Take this gift of knowledge."]
        elif q["diablo"] in ("cleared", "done"):
            lines = ["Tyrael: Diablo is no more. Baal marches on Harrogath - I can send you there."]
        else:
            lines = ["Tyrael: Diablo waits in the Chaos Sanctuary, at the end of the River of Flame."]
    elif who == "cain4":
        if q["forge"] == "none":
            _start(world, "forge")
            if not has_item(p, "mss", world):
                give_item(world, "mss")
            lines = ["Deckard Cain: Mephisto's Soulstone must be destroyed - on the Hellforge, in the River of Flame."]
        elif q["forge"] == "cleared":
            _done(world, "forge")
            lines = ["Deckard Cain: The Soulstone is gone. Mephisto will never return."]
    elif who == "larzuk":
        if q["shenk"] == "none":
            _start(world, "shenk")
            lines = ["Larzuk: Shenk the Overseer drives Baal's army against our walls. Kill him in the foothills."]
        elif q["shenk"] == "cleared":
            lines = ["Larzuk: Shenk's dead! Choose Imbue Sockets and I'll put sockets in one of your items - "
                     "and here, take this: what I know of battle is yours."]
            from . import potions              # Siege on Harrogath: a skill point (once per difficulty)
            diff = {"": "normal", "(n)": "nightmare", "(h)": "hell"}.get(getattr(world.content, "sfx", ""), "normal")
            potions.shenk_reward(world, diff)
    elif who == "qual-kehk":
        if q["barbs"] == "none":
            _start(world, "barbs")
            lines = ["Qual-Kehk: My men are caged in the Frigid Highlands. Break the prisons and set them free."]
        elif q["barbs"] == "cleared":
            for code in ("r08", "r09", "r07"):
                give_item_rune(world, code)
            _done(world, "barbs", "Three runes for you.")
            lines = ["Qual-Kehk: You freed them! Take these runes - and my men will follow you if you hire them."]
    elif who == "malah":
        if q["anya"] == "none":
            _start(world, "anya")
            give_item(world, "ice")
            lines = ["Malah: Anya went after Nihlathak and never came back. She is frozen in the river below the "
                     "Crystalline Passage. Take this potion - it will thaw her."]
        elif q["anya"] == "active" and not has_item(p, "ice", world):
            give_item(world, "ice")
            lines = ["Malah: Here is another potion for Anya."]
        elif q["anya"] == "cleared":
            give_item(world, "tr2")
            _done(world, "anya")
            lines = ["Malah: Anya is home! Take this scroll - read it, and the cold and fire will bite you less."]
    elif who == "drehya":
        if q["nihl"] == "none" and q["anya"] in ("cleared", "done"):
            _start(world, "nihl")
            lines = ["Anya: Nihlathak sold us to Baal. My portal leads to his temple. Kill him."]
        elif q["nihl"] == "cleared":
            from .quests import _reward_item
            _reward_item(world, "weapon", "Anya")
            _done(world, "nihl")
            lines = ["Anya: Nihlathak is dead. Take this - it's the least I can do."]
        else:
            lines = ["Anya: Thank you for freeing me."]
    elif who == "tyrael3":
        if q["baal"] == "cleared":
            _done(world, "baal")
            lines = ["Tyrael: The Worldstone is destroyed, and Baal with it. You have saved Sanctuary - but at a price."]
            world.emit("victory")
        else:
            lines = ["Tyrael: Baal climbs Mount Arreat to corrupt the Worldstone. You must stop him."]
    return lines


def give_item_rune(world, code):
    c = world.content
    if c is None or code not in c.base_by_code:
        return
    it = c.make_item(c.base_by_code[code], 30, world.rng)
    p = world.player
    if not p.inv_add(it):
        cell = world._drop_cell(p.pos)
        world.ground.setdefault(cell, []).append(it)
        world.emit("drop", cell, it)
    world.log("You receive %s." % it.name, it.color)


def larzuk_sockets(world):
    """Siege on Harrogath's reward: Larzuk socketing one item (the first unsocketed equipped one)."""
    p = world.player
    q = p.quests
    if q.get("shenk") != "cleared":
        world.log("Larzuk: Kill Shenk first, then we'll talk about sockets.", TALK)
        return False
    c = world.content
    for slot in ("weapon", "armor", "helm", "shield"):
        it = p.equipment.get(slot)
        if it is None or getattr(it, "sockets", 0) or it.rarity not in ("normal", "unique", "set", "rare", "magic"):
            continue
        base = it.base if isinstance(it.base, dict) else None
        n = c.max_sockets(base, max(getattr(it, "ilvl", 1), 40)) if base and c is not None else 0
        if it.rarity in ("magic",):
            n = min(n, 2)
        elif it.rarity in ("rare", "unique", "set"):
            n = 1
        if n <= 0:
            continue
        it.sockets = n
        q["shenk"] = "done"
        world.log("Larzuk: Done - your %s has %d socket%s now." % (it.shown_name, n, "" if n == 1 else "s"), TALK)
        world.log("Quest completed: Siege on Harrogath.", DONE_COLOR)
        return True
    world.log("Larzuk: Wear the item you want socketed (no sockets yet), then ask me again.", TALK)
    return False


# ------------------------------------------------------------------ places
def blocked(world, target):
    q = world.player.quests
    if target == 100 and q.get("khalim") not in ("orb", "done") and q.get("mephisto") not in ("cleared", "done"):
        return "The Compelling Orb's power seals the Durance of Hate. Smash it with Khalim's Will."
    if target == 132 and getattr(world, "level_key", None) == 131:
        from .bosses import waves_done
        if not waves_done(world):
            n = getattr(world, "baal_wave", 0)
            return "Baal laughs from his throne: defeat his minions first (wave %d of 5)." % max(1, n)
    if target == 128 and q.get("ancients") not in ("cleared", "done") and q.get("baal") == "none":
        return "The Ancients bar the way into the Worldstone Keep. Prove yourself first."
    return None


def on_enter(world, lid):
    q = world.player.quests
    if lid == 76 and any(o["kind"] == "armory_altar" and not o["used"] for o in world.objects):
        world.player.armory_lit = False          # (a fresh armory: its altars are dark again)
    if lid in (79, 76) and q["bird"] == "none":
        _start(world, "bird")
    if lid == 83:
        _start(world, "council")
    if lid in (100, 101, 102):
        _start(world, "mephisto")
    if lid == 103 and q["mephisto"] == "cleared":
        _done(world, "mephisto")
    if lid in (107, 108):
        _start(world, "diablo")
    if lid == 105:
        _start(world, "izual")
    if lid == 83 and (q.get("khalim") in ("orb", "done") or q.get("mephisto") in ("cleared", "done")):
        for o in world.objects:
            if o.get("kind") == "durance_gate":
                o["used"] = True              # (the orb is already broken: the gate stands open)
    if lid in (110,) and q["shenk"] == "none":
        _start(world, "shenk")
    if lid == 111 and q["barbs"] == "none":
        _start(world, "barbs")
    if lid == 111:
        setup_prisons(world)
    if lid == 114 and q["anya"] == "none":
        _start(world, "anya")
    if lid == 120:
        _start(world, "ancients")
    if lid in (128, 129, 130, 131, 132):
        if q["ancients"] == "cleared":
            _done(world, "ancients")
        _start(world, "baal")
    restore(world)


def _baal_portal(world, quiet=True):
    """Baal's portal to the Worldstone Chamber, by his throne (D2 opens it after the fifth wave)."""
    from .quests2 import open_portal
    if any(o.get("kind") == "portal" and o.get("target") == 132 for o in world.objects):
        return
    tc = getattr(world, "throne_cell", None) or world.player.pos
    cell = open_portal(world, tc, 132, "portal", quiet=quiet)
    world.entries[132] = world._free_cell_near((cell[0] + 1, cell[1] + 2), 4)


def restore(world):
    p = world.player
    q = getattr(p, "quests", {})
    if getattr(world, "level_key", None) == 131 and (q.get("baal") in ("cleared", "done") or
                                                     (getattr(p, "quest_stats", None) or {}).get("throne_cleared")):
        world.baal_wave = 5                   # the throne was cleared already: its portal stands open
        _baal_portal(world)
    if getattr(world, "level_key", None) == "siege":
        setup_prisons(world)
    if getattr(world, "level_key", None) == 114 and q.get("anya") in ("cleared", "done"):
        world.objects = [o for o in world.objects if o.get("kind") != "anya"]     # she is home already
    key = getattr(world, "level_key", None)
    lid = getattr(world, "level_id", None)
    if key == 102 and q.get("mephisto") in ("cleared", "done"):
        spot = getattr(world, "_meph_spot", None) or world._default_start()
        _ensure_portal(world, spot, 103, "portal")
    if key == "siege" and q.get("baal") in ("cleared", "done") and \
            not any(getattr(n, "npc", "") == "tyrael3" for n in world.npcs):
        _add_town_npc(world, "tyrael3")       # Tyrael comes to Harrogath once Baal is dead
    if key == "siege":
        # Anya home in Harrogath once freed, with her red portal to Nihlathak's Temple
        if q.get("anya") in ("cleared", "done") and not any(getattr(n, "npc", "") == "drehya" for n in world.npcs):
            _add_town_npc(world, "drehya")
        if q.get("anya") in ("cleared", "done"):
            a = next((n for n in world.npcs if getattr(n, "npc", "") == "drehya"), None)
            if a is not None:
                _ensure_portal(world, a.pos, 121, "portal")
    if key in (121, 122, 123, 124) and q.get("anya") in ("cleared", "done"):
        if key == 121:
            _ensure_portal(world, world._default_start(), 109, "portal")


# ------------------------------------------------------------------ the Barricade Prisons (Frigid Highlands)
def _pen_gap(grid, c):
    """A Barricade Prison's pen around cell c (D2's "caged fellow" marker in its middle): the
    fence's four lines and the cells of its opening - where D2 puts the breakable pen gate."""
    def reach(dx, dy):
        hits = []
        for off in range(-5, 6):
            x, y = (c[0] + off, c[1]) if dx == 0 else (c[0], c[1] + off)
            for d in range(1, 16):
                if not grid.walkable(x + dx * d, y + dy * d):
                    hits.append(d)
                    break
        # the fence line: the distance most lines stop at (the posts stick in here and there)
        return max(set(hits), key=hits.count) if hits else None
    up, down, left, right = reach(0, -1), reach(0, 1), reach(-1, 0), reach(1, 0)
    if None in (up, down, left, right):
        return None
    y0, y1, x0, x1 = c[1] - up, c[1] + down, c[0] - left, c[0] + right
    sides = [[(x, y) for y in range(y0 + 1, y1) if grid.walkable(x, y)] for x in (x0, x1)] + \
            [[(x, y) for x in range(x0 + 1, x1) if grid.walkable(x, y)] for y in (y0, y1)]
    gap = max(sides, key=len)
    if not gap or len(gap) > 9:
        return None
    out = {0: (-1, 0), 1: (1, 0), 2: (0, -1), 3: (0, 1)}[sides.index(gap)]
    return gap, (x0, y0, x1, y1), out


def setup_prisons(world):
    """D2's Rescue on Mount Arreat: each Barricade Prison is a pen with Qual-Kehk's men inside and
    a gate you break (the only gates in the game you can use)."""
    if getattr(world, "_pens_ready", False):
        return
    world._pens_ready = True
    pens = [o for o in world.objects if o.get("kind") == "prison"]
    if not pens:
        return
    p = world.player
    q = getattr(p, "quests", {}) or {}
    done = q.get("barbs") in ("cleared", "done")
    broken = int(((getattr(p, "quest_stats", None) or {}).get("prisons_broken")) or 0)
    c = world.content
    for i, o in enumerate(pens):
        found = _pen_gap(world.grid, o["cell"])
        if found is None:
            continue
        gap, (x0, y0, x1, y1), out = found
        o["pen"] = list(o["cell"])
        o["cell"] = gap[len(gap) // 2]
        o["block"] = gap
        o["out"] = out
        o["name"] = "Prison Gate"
        o["pen_id"] = i
        if done or i < broken:
            o["used"] = True
            continue
        if c is None or "act5pow" not in c.monstats:
            continue
        from .units import Monster
        inside = [(x, y) for y in range(y0 + 2, y1 - 1) for x in range(x0 + 2, x1 - 1)
                  if world.grid.walkable(x, y) and abs(x - o["pen"][0]) + abs(y - o["pen"][1]) <= 5]
        world.rng.shuffle(inside)
        occ = world.occupied()
        for cell in [x for x in inside if x not in occ][:4]:
            m = Monster("zombie", *cell, rng=world.rng, template=c.monster_template("act5pow"))
            m.npc, m.name, m.ai, m.aware = "act5pow", "Barbarian Prisoner", "npc", False
            m.pen_id = i
            world.npcs.append(m)
            world.monsters.append(m)
    from .objects import rebuild_blocks
    rebuild_blocks(world)


def _free_pows(world, gate):
    """The gate breaks: the prisoners run out of the pen (and home to Harrogath)."""
    ox, oy = gate.get("out", (1, 0))
    gx, gy = gate["cell"]
    for m in [n for n in world.npcs if getattr(n, "pen_id", None) == gate.get("pen_id")]:
        goal = world._free_cell_near((gx + ox * 6 + world.rng.randint(-2, 2), gy + oy * 6 + world.rng.randint(-2, 2)), 4)
        path = world.grid.find_path(m.pos, goal, blocked=world.occupied(m)) if goal else None
        if path and len(path) > 1:
            steps = path[1:]
            m.x, m.y = steps[-1]
            world.emit("move", m, steps)
        m.npc = "act5pow_free"
        m.name = "Barbarian"


def _add_town_npc(world, npc_id):
    from .world import NPC_NAMES
    from .units import Monster
    c = world.content
    x0, y0, x1, y1 = world.town_rect or (0, 0, world.grid.w, world.grid.h)
    cell = world._free_cell_near(((x0 + x1) // 2 + 6, (y0 + y1) // 2 + 4), 30)
    t = c.monster_template(npc_id) if c is not None and npc_id in c.monstats else None
    m = Monster("zombie", *cell, rng=world.rng, template=t)
    m.npc, m.name, m.ai, m.aware = npc_id, NPC_NAMES.get(npc_id, npc_id), "npc", False
    world.npcs.append(m)
    world.monsters.append(m)


# ------------------------------------------------------------------ objects
def on_object(world, obj):
    p = world.player
    q = p.quests
    k = obj["kind"]
    chests = {"eye_chest": ("qey", "Khalim's Eye"), "brain_chest": ("qbr", "Khalim's Brain"),
              "heart_chest": ("qhr", "Khalim's Heart")}
    if k in chests:
        if obj["used"]:
            return False
        obj["used"] = True
        code, name = chests[k]
        if q["khalim"] in ("none", "active") and not has_item(p, code, world) and not has_item(p, "qf2", world):
            _start(world, "khalim")
            give_item(world, code, near=obj["cell"])
            world.log("You found %s!" % name, QUEST_COLOR)
        else:
            world.log("The chest is empty.", GREY)
        return True
    if k == "armory_altar":
        if obj["used"]:
            return False
        obj["used"] = True
        world.emit("nova", p, obj["cell"], 1, "fire")
        left = [o for o in world.objects if o["kind"] == "armory_altar" and not o["used"]]
        if left:
            world.log("The seal breaks open. %d more to open." % len(left), QUEST_COLOR)
        else:
            from .act3 import summon_smith, SMITH_NAME
            if summon_smith(world) is not None:
                world.log("All four seals are open! %s strides out of the forge court." % SMITH_NAME, QUEST_COLOR)
        return True
    if k == "gidbinn":
        if obj["used"]:
            return False
        obj["used"] = True
        if q["gidbinn"] in ("none", "active") and not has_item(p, "g33", world):
            _start(world, "gidbinn")
            q["gidbinn"] = "cleared"
            give_item(world, "g33", near=obj["cell"])
            world.log("The Gidbinn lies on the altar. Bring it to Ormus.", QUEST_COLOR)
        return True
    if k == "lamtome":
        if obj["used"]:
            return False
        obj["used"] = True
        if getattr(world, "level_key", None) != lamesen_temple(p):
            world.log("An old lectern. The book on it crumbles to dust - not the one Alkor wants.", GREY)
            return True
        if q["lamesen"] in ("none", "active"):
            _start(world, "lamesen")
            q["lamesen"] = "cleared"
            give_item(world, "bbb", near=obj["cell"])
            world.log("Lam Esen's Tome! Bring it to Alkor.", QUEST_COLOR)
        return True
    if k == "durance_gate":
        if not obj["used"]:
            world.log("The gate to the Durance of Hate is sealed. Smash the Compelling Orb with Khalim's Will.", GREY)
            return False
        grp = next((g_ for g_ in world.warp_groups if g_.get("target") == 100), None)
        return world.enter_warp(grp) if grp is not None else False
    if k == "orb":
        if obj["used"]:
            return False
        if not has_item(p, "qf2", world):
            world.log("The Compelling Orb hums with Mephisto's power. Only Khalim's Will can break it.", GREY)
            return False
        take_item(world, "qf2")
        obj["used"] = True
        q["khalim"] = "orb"
        world.emit("nova", p, obj["cell"], 4, "ltng")
        world.log("You smash the Compelling Orb! The way into the Durance of Hate is open.", QUEST_COLOR)
        for o in world.objects:
            if o.get("kind") == "durance_gate":
                o["used"] = True              # the gate by the back wall opens
        world.log("Quest completed: Khalim's Will.", DONE_COLOR)
        q["khalim"] = "done"
        return True
    if k == "hellforge":
        if obj["used"] or q["forge"] in ("cleared", "done"):
            return False
        if not has_item(p, "mss", world):
            world.log("The Hellforge. Mephisto's Soulstone belongs on it - Cain has it.", GREY)
            return False
        if not has_item(p, "hfh", world):
            world.log("You need the Hellforge Hammer to smash the Soulstone (Hephasto the Armorer has it).", GREY)
            return False
        take_item(world, "mss")
        obj["used"] = True
        q["forge"] = "cleared"
        world.emit("nova", p, obj["cell"], 4, "fire")
        world.log("The Soulstone shatters on the Hellforge! Gems and runes spill out.", QUEST_COLOR)
        c = world.content
        if c is not None:
            for code in ("gpr", "gpb", "gpy", "gpg", "gpw", "gpv"):
                if world.rng.random() < 0.5 and code in c.base_by_code:
                    it = c.make_item(c.base_by_code[code], 40, world.rng)
                    cell = world._drop_cell(obj["cell"])
                    world.ground.setdefault(cell, []).append(it)
                    world.emit("drop", cell, it)
            for _ in range(2):
                n = world.rng.randint(1, 12)
                code = "r%02d" % n
                if code in c.base_by_code:
                    it = c.make_item(c.base_by_code[code], 40, world.rng)
                    cell = world._drop_cell(obj["cell"])
                    world.ground.setdefault(cell, []).append(it)
                    world.emit("drop", cell, it)
        return True
    if k == "prison":
        if obj["used"]:
            return False
        obj["used"] = True
        obj["mode"] = "OP"
        world.emit("object", obj)
        from .objects import rebuild_blocks
        rebuild_blocks(world)
        _free_pows(world, obj)
        st = p.quest_stats if isinstance(getattr(p, "quest_stats", None), dict) else {}
        st["prisons_broken"] = sum(1 for o in world.objects if o["kind"] == "prison" and o["used"])
        left = [o for o in world.objects if o["kind"] == "prison" and not o["used"]]
        if q["barbs"] in ("none", "active"):
            _start(world, "barbs")
            if left:
                world.log("You break the prison. %d more to go." % len(left), QUEST_COLOR)
            else:
                q["barbs"] = "cleared"
                world.log("The last prison is open! The soldiers run back to Harrogath. Talk to Qual-Kehk.", QUEST_COLOR)
        return True
    if k == "anya":
        if obj["used"]:
            return False
        if not has_item(p, "ice", world):
            world.log("Anya, frozen solid. Malah has a potion that could thaw her.", GREY)
            return False
        take_item(world, "ice")
        obj["used"] = True
        if obj in world.objects:
            world.objects.remove(obj)          # the ice is gone: Anya goes home to Harrogath
        q["anya"] = "cleared"
        world.log("The ice melts. Anya: 'Thank you! I'll go home to Harrogath.' Talk to Malah.", QUEST_COLOR)
        return True
    return None


# ------------------------------------------------------------------ deaths
def on_killed(world, unit):
    p = world.player
    q = p.quests
    boss = getattr(unit, "boss", None)
    lid = world.area_at(unit.pos) or world.level_id
    if boss and q["bird"] in ("none", "active") and lid in (79, 76, 77) and not has_item(p, "j34", world) \
            and not has_item(p, "g34", world) and not has_item(p, "xyz", world):
        _start(world, "bird")
        q["bird"] = "jade"
        give_item(world, "j34", near=unit.pos)
        world.log("%s dropped a Jade Figurine. Show it to Meshif." % unit.name, QUEST_COLOR)
    # this game's Kurast Armory / Scriptorium: the named uniques carry the quest items
    drops = {"armory_smith": ("g33", "gidbinn", "the Gidbinn"), "silkmother": ("qey", "khalim", "Khalim's Eye"),
             "scribe": ("qbr", "khalim", "Khalim's Brain")}
    if boss in drops:
        code, qid, what = drops[boss]
        if qid == "gidbinn":
            if q["gidbinn"] in ("none", "active") and not has_item(p, "g33", world):
                _start(world, "gidbinn")
                q["gidbinn"] = "cleared"
                give_item(world, code, near=unit.pos)
                world.log("%s dropped the Gidbinn! Bring it to Ormus." % unit.name, QUEST_COLOR)
        elif q["khalim"] in ("none", "active") and not has_item(p, code, world) and not has_item(p, "qf2", world):
            _start(world, "khalim")
            give_item(world, code, near=unit.pos)
            world.log("%s dropped %s!" % (unit.name, what), QUEST_COLOR)
    if boss == "council":
        if q["khalim"] in ("none", "active") and not has_item(p, "qf1", world) and not has_item(p, "qf2", world):
            give_item(world, "qf1", near=unit.pos)
            world.log("%s dropped Khalim's Flail!" % unit.name, QUEST_COLOR)
        left = [m for m in world.monsters if m.alive and getattr(m, "boss", None) == "council"
                and (world.area_at(m.pos) or world.level_id) == COUNCIL_LEVEL]
        if not left and q["council"] in ("none", "active"):
            q["council"] = "cleared"
            world.log("The High Council of Travincal is dead! Tell Cain.", QUEST_COLOR)
    elif boss == "mephisto":
        q["mephisto"] = "cleared"
        world._meph_spot = unit.pos
        if not has_item(p, "mss", world):
            give_item(world, "mss", near=unit.pos)
        open_portal(world, unit.pos, 103, "portal")
        world.log("Mephisto is dead! His red portal leads to the Pandemonium Fortress.", QUEST_COLOR)
        world.emit("victory")
    elif boss == "izual":
        q["izual"] = "cleared"
        world.log("Izual's soul is free: 'Tell Tyrael... the soulstones...' Talk to Tyrael.", QUEST_COLOR)
    elif boss == "hephasto":
        give_item(world, "hfh", near=unit.pos)
        world.log("Hephasto drops the Hellforge Hammer.", QUEST_COLOR)
    elif boss == "diablo":
        q["diablo"] = "cleared"
        world.log("Diablo, the Lord of Terror, is dead! Talk to Tyrael to go on to Harrogath.", QUEST_COLOR)
        world.emit("victory")
    elif boss == "shenk":
        if q["shenk"] in ("none", "active"):
            q["shenk"] = "cleared"
            world.log("Shenk the Overseer is dead! Talk to Larzuk.", QUEST_COLOR)
    elif boss == "nihlathak":
        q["nihl"] = "cleared"
        world.log("Nihlathak is dead! Tell Anya.", QUEST_COLOR)
    elif boss == "ancients":
        left = [m for m in world.monsters if m.alive and getattr(m, "boss", None) == "ancients"]
        if not left:
            q["ancients"] = "cleared"
            p.gain_xp(p.xp_threshold(p.level) // 10)
            world.log("The Ancients bow to you. The Worldstone Keep is open!", QUEST_COLOR)
    elif boss == "baal":
        q["baal"] = "cleared"
        world.log("Baal, the Lord of Destruction, is dead! Talk to Tyrael in Harrogath.", QUEST_COLOR)
        # D2: beating Baal opens the next difficulty (Normal -> Nightmare -> Hell)
        cur = getattr(p, "difficulty", "normal")
        nxt = {"normal": "nightmare", "nightmare": "hell"}.get(cur)
        got = p.__dict__.setdefault("diff_unlocked", ["normal"])
        if nxt and nxt not in got:
            got.append(nxt)
            world.log("%s difficulty unlocked!" % nxt.title(), (255, 120, 80))
        if nxt:
            import types
            world.open_npc = types.SimpleNamespace(npc="difficulty", name="%s awaits" % nxt.title(),
                                                   pos=p.pos, facing=(1, 1))
        world.emit("victory")
    if getattr(world, "level_key", None) == 131 and getattr(unit, "wave", None):
        from .bosses import waves_done
        if waves_done(world):
            world.log("The last wave falls. Baal flees into the Worldstone Chamber - follow him!", QUEST_COLOR)
            world.player.quest_stats["throne_cleared"] = 1
            _baal_portal(world, quiet=False)


def on_transmute(world, box):
    q = world.player.quests
    if any(c.code == "qf2" for c in getattr(box, "contents", []) or []) and q["khalim"] in ("none", "active"):
        q["khalim"] = "cleared"
        world.log("Khalim's Will is whole! Smash the Compelling Orb in Travincal with it.", QUEST_COLOR)


def read_item(world, it):
    """Quest items you use: the Potion of Life, Malah's Scroll of Resistance."""
    p = world.player
    q = p.quests
    if it.use == "potion_of_life":
        from . import tactics
        p.inventory.remove(it)
        it.inv_pos = None
        for h in tactics.everyone(world):           # Alkor brews enough for the whole party
            h.quest_stats = getattr(h, "quest_stats", None) or {}
            h.quest_stats["life"] = h.quest_stats.get("life", 0) + 20
            h.recalc()
        if q["bird"] != "done":
            _done(world, "bird", "+20 Life.")
        return True
    if it.use == "scroll_resist":
        from . import tactics
        p.inventory.remove(it)
        it.inv_pos = None
        for h in tactics.everyone(world):           # Malah's scroll is read out to everyone
            h.quest_stats = getattr(h, "quest_stats", None) or {}
            h.quest_stats["res_all"] = h.quest_stats.get("res_all", 0) + 10
            h.recalc()
        world.log("You read the scroll: +10 to all resistances for every hero.", DONE_COLOR)
        return True
    return False
