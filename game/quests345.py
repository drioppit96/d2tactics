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
    "bird": {"active": "Somewhere in the jungle a unique monster carries a Jade Figurine. Show it to Meshif.",
             "jade": "You have the Jade Figurine. Show it to Meshif.",
             "bird": "Meshif gave you a Golden Bird for the figurine. Alkor wants to see it.",
             "potion": "Alkor brewed you a Potion of Life from the bird's ashes. Drink it.",
             "done": "Completed. The Potion of Life gave you +20 Life."},
    "gidbinn": {"active": "Ormus says the Gidbinn, a sacred blade, lies on an altar in the Flayer Jungle.",
                "cleared": "You have the Gidbinn. Bring it to Ormus.",
                "done": "Completed. Ormus gave you a ring."},
    "khalim": {"active": "Remake Khalim's Will: his Eye (Spider Cavern), Brain (Flayer Dungeon 3), Heart (Sewers "
                         "Level 2) and Flail (the High Council in Travincal). Join them in the Horadric Cube.",
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
            take_item(world, "bbb")
            p.stat_points += 5
            _done(world, "lamesen", "+5 stat points.")
            lines = ["Alkor: Lam Esen's Tome! Let me read some of it to you - you'll feel the knowledge in your bones."]
        elif q["lamesen"] == "none":
            _start(world, "lamesen")
            lines = ["Alkor: Lam Esen wrote a tome about the Prime Evils. It's hidden in one of Kurast's temples."]
        else:
            lines = ["Alkor: Potions, poultices... and a little gamble now and then, eh?"]
    elif who == "ormus":
        if q["gidbinn"] == "none":
            _start(world, "gidbinn")
            lines = ["Ormus: The Gidbinn - a sacred blade - lies on an altar in the Flayer Jungle. Ormus needs it."]
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
            parts = [("qey", "the Eye (Spider Cavern)"), ("qbr", "the Brain (Flayer Dungeon)"),
                     ("qhr", "the Heart (Kurast Sewers)"), ("qf1", "the Flail (the High Council)")]
            missing = [n for c, n in parts if not has_item(p, c, world)]
            lines = ["Deckard Cain: You still need %s." % ", ".join(missing)] if missing else \
                ["Deckard Cain: You have them all. Join them in the Horadric Cube."]
    elif who == "tyrael2":
        if q["izual"] == "none":
            _start(world, "izual")
            lines = ["Tyrael: Izual, my lieutenant, fell to Hell. Free his soul - he lurks on the Plains of Despair."]
        elif q["izual"] == "cleared":
            p.skills.points += 2
            _done(world, "izual", "+2 skill points.")
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
            lines = ["Larzuk: Shenk's dead! Choose Imbue Sockets and I'll put sockets in one of your items."]
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
        left = [m for m in world.monsters if m.alive and not m.ally and getattr(m, "ai", "") != "npc"]
        if left:
            return "Baal laughs from his throne: kill his minions first (%d left)." % len(left)
    if target == 128 and q.get("ancients") not in ("cleared", "done") and q.get("baal") == "none":
        return "The Ancients bar the way into the Worldstone Keep. Prove yourself first."
    return None


def on_enter(world, lid):
    q = world.player.quests
    if lid in (76, 77, 78) and q["bird"] == "none":
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
    if lid in (110,) and q["shenk"] == "none":
        _start(world, "shenk")
    if lid == 111 and q["barbs"] == "none":
        _start(world, "barbs")
    if lid == 114 and q["anya"] == "none":
        _start(world, "anya")
    if lid == 120:
        _start(world, "ancients")
    if lid in (128, 129, 130, 131, 132):
        if q["ancients"] == "cleared":
            _done(world, "ancients")
        _start(world, "baal")
    restore(world)


def restore(world):
    p = world.player
    q = getattr(p, "quests", {})
    key = getattr(world, "level_key", None)
    lid = getattr(world, "level_id", None)
    if key == 102 and q.get("mephisto") in ("cleared", "done"):
        spot = getattr(world, "_meph_spot", None) or world._default_start()
        _ensure_portal(world, spot, 103, "portal")
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
        world.emit("nova", p, obj["cell"], 2, "fire")
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
    if boss and q["bird"] in ("none", "active") and lid in (76, 77, 78) and not has_item(p, "j34", world) \
            and not has_item(p, "g34", world) and not has_item(p, "xyz", world):
        _start(world, "bird")
        q["bird"] = "jade"
        give_item(world, "j34", near=unit.pos)
        world.log("%s dropped a Jade Figurine. Show it to Meshif." % unit.name, QUEST_COLOR)
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
        world.emit("victory")
    if getattr(world, "level_key", None) == 131:
        left = [m for m in world.monsters if m.alive and not m.ally and getattr(m, "ai", "") != "npc"]
        if not left:
            world.log("The throne room is clear. Baal flees into the Worldstone Chamber - follow him!", QUEST_COLOR)


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
        p.inventory.remove(it)
        it.inv_pos = None
        p.quest_stats["life"] = p.quest_stats.get("life", 0) + 20
        p.recalc()
        if q["bird"] != "done":
            _done(world, "bird", "+20 Life.")
        return True
    if it.use == "scroll_resist":
        p.inventory.remove(it)
        it.inv_pos = None
        p.quest_stats["res_all"] = p.quest_stats.get("res_all", 0) + 10
        p.recalc()
        world.log("You read the scroll: +10 to all resistances.", DONE_COLOR)
        return True
    return False
