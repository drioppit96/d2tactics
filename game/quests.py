"""Act 1 quests (Act 2's are in quests2.py). State lives on the player so it follows you between areas.

Story text is written for this project (it paraphrases what happens in D2, it doesn't
copy the game's dialogue).
"""

ACT1 = [
    ("den", "Den of Evil"),
    ("blood_raven", "Sisters' Burial Grounds"),
    ("cain", "The Search for Cain"),
    ("tower", "The Forgotten Tower"),
    ("malus", "Tools of the Trade"),
    ("andariel", "Sisters to the Slaughter"),
]

JOURNAL = {
    "den": {
        "active": "Akara wants the Den of Evil in the Blood Moor cleansed. Kill every monster inside.",
        "cleared": "The Den is clear. Return to Akara.",
        "done": "Completed. Akara granted you a skill point.",
    },
    "blood_raven": {
        "active": "Kashya wants Blood Raven dead. She haunts the Burial Grounds past the Cold Plains.",
        "cleared": "Blood Raven is dead. Return to Kashya.",
        "done": "Completed. A Rogue scout now fights at your side.",
    },
    "cain": {
        "active": "Find the Tree of Inifuss in the Dark Wood and bring Akara its scroll.",
        "scroll": "You found the Scroll of Inifuss. Take it to Akara.",
        "stones": "Touch the five Cairn Stones in the Stony Field to open the way to Tristram.",
        "portal": "The portal to Tristram is open. Free Deckard Cain from his cage.",
        "cleared": "Cain is free and on his way to the camp. Talk to Akara.",
        "done": "Completed. Deckard Cain is safe in the Rogue Encampment.",
    },
    "tower": {
        "active": "The Moldy Tome speaks of the Countess, buried under the Forgotten Tower in the Black Marsh.",
        "cleared": "The Countess is dead. Her treasure is yours.",
        "done": "Completed.",
    },
    "malus": {
        "active": "Charsi needs her Horadric Malus back. It is in the Barracks of the Monastery.",
        "cleared": "You have the Malus. Return it to Charsi.",
        "done": "Completed. Charsi forged you a fine item.",
    },
    "andariel": {
        "active": "Andariel, the Maiden of Anguish, waits in the depths of the Catacombs.",
        "cleared": "Andariel is dead! Talk to Warriv to travel east.",
        "done": "Completed. Act 1 is finished.",
    },
}

QUEST_COLOR = (199, 179, 119)
DONE_COLOR = (0, 220, 0)


def init(player):
    if not hasattr(player, "quests"):
        player.quests = {q: "none" for q, _ in ACT1}
    for q, _ in ACT1:
        player.quests.setdefault(q, "none")
    from . import quests2, quests345
    quests2.init(player)
    quests345.init(player)
    if not hasattr(player, "waypoints"):
        player.waypoints = {1}
    if not hasattr(player, "visited"):
        player.visited = {1}


def _start(world, qid, lines=None):
    q = world.player.quests
    if q.get(qid) == "none":
        q[qid] = "active"
        title = dict(ACT1)[qid]
        world.log("New quest: %s (Quest Log: Q)." % title, QUEST_COLOR)
        world.emit("quest", qid)
        return True
    return False


def talk(world, npc):
    """Extra lines when talking to an NPC, plus quest progress. Returns a list of lines or []."""
    p = world.player
    init(p)
    q = p.quests
    lines = []
    who = npc.npc
    from . import quests2, quests345
    if who in quests2.NPC_ACT2:
        return quests2.talk(world, npc)
    if who in quests345.NPCS:
        return quests345.talk(world, npc)
    if who == "akara":
        if q["den"] == "none":
            _start(world, "den")
            lines = ["Akara: A cave in the Blood Moor - the Den of Evil - festers with demons.",
                     "Akara: Cleanse it of every last one, and I will teach you something of value."]
        elif q["den"] == "active":
            lines = ["Akara: The Den still breathes evil. Clear out every creature in it."]
        elif q["den"] == "cleared":
            q["den"] = "done"
            p.skills.points += 1
            lines = ["Akara: The Den is quiet at last. You have our thanks.",
                     "Akara: Take this knowledge as your reward."]
            world.log("Quest completed: Den of Evil. +1 skill point!", DONE_COLOR)
        elif q["cain"] == "none":
            _start(world, "cain")
            lines = ["Akara: Deckard Cain, the last of the Horadrim, is held in Tristram.",
                     "Akara: The way there is sealed. Find the Tree of Inifuss in the Dark Wood - its scroll holds the key."]
        elif q["cain"] == "scroll":
            q["cain"] = "stones"
            lines = ["Akara: The scroll shows the order of the Cairn Stones in the Stony Field.",
                     "Akara: Touch them, and the way to Tristram will open."]
            world.log("The Cairn Stones in the Stony Field will open a portal to Tristram.", QUEST_COLOR)
        elif q["cain"] == "cleared":
            q["cain"] = "done"
            _reward_item(world, "ring", "Akara")
            lines = ["Akara: Cain is safe! You have done the Sisterhood a great service."]
            world.log("Quest completed: The Search for Cain.", DONE_COLOR)
    elif who == "kashya":
        if q["blood_raven"] == "none":
            _start(world, "blood_raven")
            lines = ["Kashya: Blood Raven was one of us. Now she raises the dead in the Burial Grounds.",
                     "Kashya: Put her down, and I'll lend you one of my scouts."]
        elif q["blood_raven"] == "cleared":
            q["blood_raven"] = "done"
            hire_rogue(world)
            lines = ["Kashya: Blood Raven is gone. You have earned my respect - and a Rogue to watch your back."]
            world.log("Quest completed: Sisters' Burial Grounds. A Rogue scout joins you.", DONE_COLOR)
        elif q["blood_raven"] == "done" and getattr(getattr(p, "merc", None), "get", lambda k: None)("dead"):
            from . import hireling
            cost = hireling.resurrect_cost(p.merc)
            if hireling.resurrect(world):
                lines = ["Kashya: Back on your feet, %s. Don't waste her again." % p.merc["name"]]
            else:
                lines = ["Kashya: I can bring %s back for %d gold." % (p.merc["name"], cost)]
        elif q["den"] == "done":
            lines = ["Kashya: So you cleared the Den. Maybe you're worth something after all."]
    elif who == "charsi":
        if q["malus"] == "none" and (q["den"] == "done" or 27 in getattr(p, "visited", ())):
            _start(world, "malus")
            lines = ["Charsi: When we fled the Monastery I left my Horadric Malus in the Barracks.",
                     "Charsi: Bring it back and I'll make something special for you."]
        elif q["malus"] == "cleared":
            q["malus"] = "done"
            _reward_item(world, "weapon", "Charsi")
            lines = ["Charsi: My Malus! Here - I made this for you."]
            world.log("Quest completed: Tools of the Trade.", DONE_COLOR)
    elif who == "cain1":
        if q["andariel"] == "none":
            _start(world, "andariel")
        lines = ["Deckard Cain: Andariel holds the Monastery. Her lair lies deep in the Catacombs, below the Cathedral.",
                 "Deckard Cain: Stay awhile and listen... and then go and end her."]
    elif who == "warriv1":
        if q["andariel"] in ("cleared", "done"):
            q["andariel"] = "done"
            lines = ["Warriv: The pass is clear! The caravan leaves for Lut Gholein - Act 2 is coming in a later update."]
            world.emit("victory")
        else:
            lines = ["Warriv: The pass east is held by the Maiden. Until she falls, the caravan stays."]
    return lines


def hire_rogue(world):
    """Kashya's reward: a Rogue scout (D2's hireling) who follows, fights, levels up and wears gear."""
    from . import hireling
    p = world.player
    merc = getattr(p, "merc", None)
    if merc is not None and merc["kind"] != "rogue" and not merc.get("dead"):
        return hireling.spawn(world)
    if merc is not None and merc.get("dead"):
        merc["dead"] = False
    hireling.spawn(world, "rogue")


def _reward_item(world, kind, who):
    c = world.content
    p = world.player
    if c is None:
        return
    import random as _r
    rng = world.rng
    bases = [b for b in c.bases if (b.get("slot") == "ring" if kind == "ring" else b.get("slot") == "weapon")
             and b.get("qlvl", 1) <= p.level + 3]
    if not bases:
        return
    base = rng.choice(bases)
    it = c.make_item(base, p.level + 3, rng, quality="magic", identified=True)
    if it is None:
        return
    if not p.inv_add(it):
        world.ground.setdefault(p.pos, []).append(it)
        world.emit("drop", p.pos, it)
    world.log("%s gives you %s." % (who, it.name), it.color)


def on_enter(world, lid):
    """Entering an area (seamless outdoors or a dungeon)."""
    p = world.player
    init(p)
    p.visited.add(lid)
    q = p.quests
    if lid == 8 and q["den"] == "none":
        _start(world, "den")
    if lid == 17 and q["blood_raven"] == "none":
        _start(world, "blood_raven")
    if lid == 28 and q["malus"] == "none":
        _start(world, "malus")
    if lid in (34, 35, 36, 37) and q["andariel"] == "none":
        _start(world, "andariel")
    from . import quests2, quests345
    quests2.on_enter(world, lid)
    quests345.on_enter(world, lid)


def restore(world):
    init(world.player)
    from . import quests2, quests345
    quests2.restore(world)
    quests345.restore(world)


def read_horadric_scroll(world, it):
    init(world.player)
    from . import quests2
    quests2.read_horadric_scroll(world, it)


def on_transmute(world, box):
    init(world.player)
    from . import quests2, quests345
    quests2.on_transmute(world, box)
    quests345.on_transmute(world, box)


def blocked(world, target):
    init(world.player)
    from . import quests2, quests345
    return quests2.blocked(world, target) or quests345.blocked(world, target)


def on_object(world, obj):
    """Using a quest object. Returns True if something happened."""
    p = world.player
    init(p)
    q = p.quests
    k = obj["kind"]
    from . import quests2, quests345
    r = quests2.on_object(world, obj)
    if r is None:
        r = quests345.on_object(world, obj)
    if r is not None:
        return r
    if k == "inifuss":
        if q["cain"] in ("none", "active"):
            q["cain"] = "scroll"
            world.log("You take the Scroll of Inifuss from the tree. Bring it to Akara.", QUEST_COLOR)
            obj["used"] = True
            return True
        world.log("The tree is silent now.", (170, 170, 170))
    elif k == "cairn":
        if q["cain"] not in ("stones", "scroll"):
            world.log("A strange stone. Akara might know more about it.", (170, 170, 170))
            return False
        if obj["used"]:
            return False
        obj["used"] = True
        world.emit("nova", p, obj["cell"], 1, "ltng")
        left = [o for o in world.objects if o["kind"] == "cairn" and not o["used"]]
        if left:
            world.log("The stone hums. %d more to go." % len(left), QUEST_COLOR)
        else:
            q["cain"] = "portal"
            stones = [o["cell"] for o in world.objects if o["kind"] == "cairn"]
            cx = sum(c[0] for c in stones) // len(stones)
            cy = sum(c[1] for c in stones) // len(stones)
            from .actworld import _free_near
            cell = _free_near(world.grid, (cx, cy), 6) or obj["cell"]
            world.objects.append(dict(kind="portal", cell=cell, level=4, oid=0, used=False, target=38))
            world.entries[38] = cell
            world.log("A portal to Tristram opens in the middle of the stones!", QUEST_COLOR)
            world.emit("nova", p, cell, 3, "fire")
        return True
    elif k == "cage":
        if q["cain"] in ("portal", "stones", "scroll", "active"):
            q["cain"] = "cleared"
            obj["used"] = True
            p.cain_rescued = True
            world.log("You break the cage. Deckard Cain: 'Thank you! I will meet you at the Rogue camp.'", QUEST_COLOR)
            return True
    elif k == "wirt":
        if obj["used"]:
            return False
        obj["used"] = True
        from . import quests2
        quests2.give_item(world, "leg", near=obj["cell"])
        if world.content is not None:
            g = world.content.make_gold(20, world.rng)
            cell = world._drop_cell(obj["cell"])
            world.ground.setdefault(cell, []).append(g)
            world.emit("drop", cell, g)
        world.log("Poor Wirt. His wooden leg comes loose...", (170, 170, 170))
        return True
    elif k == "tome":
        if q["tower"] == "none":
            _start(world, "tower")
            world.log("The tome tells of the Countess and the riches buried below the Forgotten Tower.", QUEST_COLOR)
        obj["used"] = True
        return True
    elif k == "malus":
        if q["malus"] in ("none", "active"):
            q["malus"] = "cleared"
            obj["used"] = True
            world.log("You take the Horadric Malus. Return it to Charsi.", QUEST_COLOR)
            return True
    elif k in ("portal", "arcane_portal", "duriel_portal"):
        msg = blocked(world, obj.get("target"))
        if msg:
            world.log(msg, (220, 210, 170))
            return False
        world.pending_exit = obj.get("target")
        return True
    elif k in ("tp", "tp_back"):
        target, cell = world.portal_target(obj)
        if target:
            world.pending_exit = target
            world.pending_arrive = cell
            world.pending_portal = obj["kind"]
        return True
    return False


def on_monster_killed(world, unit=None):
    """Called after a death; bosses and 'clear the level' quests."""
    p = world.player
    init(p)
    q = p.quests
    boss = getattr(unit, "boss", None) if unit is not None else None
    if unit is not None:
        from . import quests2, quests345
        quests2.on_killed(world, unit)
        quests345.on_killed(world, unit)
    if boss == "blood_raven" and q["blood_raven"] in ("none", "active"):
        q["blood_raven"] = "cleared"
        world.log("Blood Raven is slain! Return to Kashya.", QUEST_COLOR)
    elif boss == "countess" and q["tower"] in ("none", "active"):
        q["tower"] = "cleared"
        world.log("The Countess is dead!", QUEST_COLOR)
        _countess_gold(world, unit)
    elif boss == "andariel":
        q["andariel"] = "cleared"
        world.log("Andariel, the Maiden of Anguish, is dead! Return to the camp and talk to Warriv.", QUEST_COLOR)
        world.emit("victory")
    elif boss == "smith" and q["malus"] in ("none", "active"):
        world.log("The Smith falls. The Malus must be close by.", QUEST_COLOR)
    if getattr(world, "level_key", None) == 8 or world.level_id == "den":
        if q["den"] in ("none", "active"):
            left = [m for m in world.monsters if m.alive and getattr(m, "ai", "") != "npc" and not m.ally]
            if not left:
                q["den"] = "cleared"
                world.log("The Den of Evil has been cleansed! Return to Akara.", QUEST_COLOR)
                world.emit("quest", "den")
            elif len(left) <= 5 and not getattr(world, "_den_hint", False):
                world._den_hint = True
                world.log("Only a few monsters remain in the Den...", (170, 170, 170))


def _countess_gold(world, unit):
    c = world.content
    if c is None:
        return
    for _ in range(4):
        cell = world._drop_cell(unit.pos)
        g = c.make_gold(unit.level * 8, world.rng)
        world.ground.setdefault(cell, []).append(g)
        world.emit("drop", cell, g)


def journal(player, act=1):
    init(player)
    out = []
    from . import quests2
    from . import quests345
    table, texts = {1: (ACT1, JOURNAL), 2: (quests2.ACT2, quests2.JOURNAL)}.get(
        act, (quests345.ACTS.get(act, []), quests345.JOURNAL))
    for qid, title in table:
        st = player.quests.get(qid, "none")
        text = texts.get(qid, {}).get(st, "")
        if st == "none":
            text = "Not started."
        out.append((title, "active" if st not in ("none", "done", "cleared") else st, text or ""))
    return out
