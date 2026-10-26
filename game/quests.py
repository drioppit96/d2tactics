"""Act 1 quests. State lives on the player so it follows you between areas.

Story text is written for this project (it paraphrases what happens, it doesn't
copy D2's dialogue).
"""

ACT1 = [
    ("den", "Den of Evil"),
    ("blood_raven", "Sisters' Burial Grounds"),
    ("cain", "The Search for Cain"),
    ("tower", "The Forgotten Tower"),
    ("malus", "Tools of the Trade"),
    ("andariel", "Sisters to the Slaughter"),
]

# per quest: status -> journal text
JOURNAL = {
    "den": {
        "none": "",
        "active": "Akara wants the Den of Evil cleansed. Kill every monster inside.",
        "cleared": "The Den is clear. Return to Akara.",
        "done": "Completed. Akara granted you a skill point.",
    },
}


def init(player):
    if not hasattr(player, "quests"):
        player.quests = {q: "none" for q, _ in ACT1}


def talk(world, npc):
    """Extra lines when talking to an NPC, plus quest progress. Returns list of lines or []."""
    p = world.player
    init(p)
    q = p.quests
    lines = []
    if npc.npc == "akara":
        if q["den"] == "none":
            q["den"] = "active"
            lines = ["Akara: A dark place to the north - the Den of Evil - festers with demons.",
                     "Akara: Cleanse it of every last one, and I will teach you something of value."]
            world.log("New quest: Den of Evil (see the Quest Log, Q).", (199, 179, 119))
        elif q["den"] == "active":
            lines = ["Akara: The Den still breathes evil. Clear out every creature in it."]
        elif q["den"] == "cleared":
            q["den"] = "done"
            if hasattr(p, "skills"):
                p.skills.points += 1
            lines = ["Akara: The Den is quiet at last. You have our thanks.",
                     "Akara: Take this knowledge as your reward."]
            world.log("Quest completed: Den of Evil. +1 skill point!", (0, 220, 0))
    elif npc.npc == "kashya" and q["den"] == "done":
        lines = ["Kashya: So you cleared the Den. Maybe you're worth something after all."]
    return lines


def on_monster_killed(world):
    """Called after a death; finishes 'clear the level' quests."""
    p = world.player
    init(p)
    if world.level_id == "den" and p.quests.get("den") in ("none", "active"):
        left = [m for m in world.monsters if m.alive and getattr(m, "ai", "") != "npc"]
        if not left:
            p.quests["den"] = "cleared"
            world.log("The Den of Evil has been cleansed! Return to Akara.", (199, 179, 119))
            world.emit("quest", "den")
        elif len(left) <= 5 and not getattr(world, "_den_hint", False):
            world._den_hint = True
            world.log("Only a few monsters remain in the Den...", (170, 170, 170))


def journal(player):
    init(player)
    out = []
    for qid, title in ACT1:
        st = player.quests.get(qid, "none")
        text = JOURNAL.get(qid, {}).get(st, "")
        if st == "none":
            text = "Not started."
        out.append((title, st, text or "Coming soon."))
    return out
