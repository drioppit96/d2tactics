"""NPC speech and quest-log text, read from the player's own D2 string tables at runtime
(data\\local\\lng\\eng\\*.tbl in their MPQs - nothing of Blizzard's ships with this project).

D2's keys:
  introductions   <Npc>Intro<Cls>Gossip1, <Npc>IntroGossip1, <Npc>ActIntroGossip1 ...
  gossip          <Npc>Gossip1..N
  quest speech    A<act>Q<n><Init|AfterInit|EarlyReturn|Successful|QuestSuccessful...><Npc>
  quest log       qstsa<act>q<n><step>
"""
import re

STRINGS = None          # the Strings object (set by d2content when the tables load)

CLS = {"ama": "Ama", "sor": "Sor", "nec": "Nec", "pal": "Pal", "bar": "Bar", "dru": "Dru", "ass": "Ass"}

# npc id -> (prefixes for introductions / gossip, name used in quest speech keys)
NPCS = {
    "akara": (["Akara"], "Akara"), "charsi": (["Charsi"], "Charsi"), "gheed": (["Gheed"], "Gheed"),
    "kashya": (["Kashya"], "Kashya"), "warriv1": (["WarrivAct1", "Warriv"], "Warriv"),
    "cain1": (["Cain"], "Cain"), "rogue1": (["RogueSignpost"], "Rogue"),
    "warriv2": (["WarrivAct2"], "WarrivAct2"), "atma": (["Atma"], "Atma"), "drognan": (["Drognan"], "Drognan"),
    "fara": (["Fara"], "Fara"), "greiz": (["Griez", "Greiz"], "Greiz"), "elzix": (["Elzix"], "Elzix"),
    "lysander": (["Lysander"], "Lysander"), "meshif1": (["Meshif"], "Meshif"), "geglash": (["Geglash"], "Geglash"),
    "jerhyn": (["Jerhyn"], "Jerhyn"), "cain2": (["CainAct2"], "Cain"), "tyrael1": (["Tyrael"], "Tyrael"),
    "cain3": (["CainAct3"], "CainAct3"), "ormus": (["Ormus"], "Ormus"), "alkor": (["Alkor"], "Alkor"),
    "asheara": (["Asheara"], "Asheara"), "hratli": (["Hratli", "HratliAct"], "Hratli"),
    "meshif2": (["MeshifAct3"], "MeshifAct3"), "natalya": (["Natalya"], "Natalya"),
    "tyrael2": (["TyraelAct4", "Tyrael"], "Tyrael"), "cain4": (["CainAct4"], "Cain"),
    "larzuk": (["LarzukAct5", "Larzuk"], "Larzuk"), "malah": (["MalahAct5", "Malah"], "Malah"),
    "qual-kehk": (["QualKehkAct5", "QualKehk"], "QualKehk"), "drehya": (["AnyaAct5", "Anya"], "Anya"),
    "nihlathak": (["NihlathakAct5", "Nihlathak"], "Nihlathak"), "cain6": (["CainAct5"], "Cain"),
    "tyrael3": (["Tyrael"], "Tyrael"),
}

# this game's quest ids -> D2's (act, quest number) - the order of D2's quest log
QUEST_NUM = {"den": (1, 1), "blood_raven": (1, 2), "malus": (1, 3), "cain": (1, 4), "tower": (1, 5), "andariel": (1, 6),
             "radament": (2, 1), "staff": (2, 2), "tainted": (2, 3), "arcane": (2, 4), "summoner": (2, 5), "tombs": (2, 6),
             "lamesen": (3, 1), "khalim": (3, 2), "gidbinn": (3, 3), "bird": (3, 4), "council": (3, 5), "mephisto": (3, 6),
             "izual": (4, 1), "diablo": (4, 2), "forge": (4, 3),
             "shenk": (5, 1), "barbs": (5, 2), "anya": (5, 3), "nihl": (5, 4), "ancients": (5, 5), "baal": (5, 6)}


def _table():
    return getattr(STRINGS, "table", None) or {}


def clean(text):
    """D2's speech: a scroll-speed number on the first line, hard line breaks, ' ' lines between paragraphs."""
    if not text:
        return ""
    lines = text.split("\n")
    if lines and lines[0].strip().isdigit():
        lines = lines[1:]
    text = re.sub(r"\xffc.", "", "\n".join(lines))
    paras, cur = [], []
    for ln in text.split("\n"):
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            paras.append(" ".join(cur))
            cur = []
    if cur:
        paras.append(" ".join(cur))
    return "\n\n".join(paras)


def get(key):
    t = _table()
    return clean(t[key]) if key in t and t[key].strip() else None


# ------------------------------------------------------------------ introductions and gossip
NO_INTRO = {"tyrael1", "tyrael3"}     # (D2's Tyrael introduction is the Pandemonium Fortress one)


def intro_key(npc_id, cls):
    if npc_id in NO_INTRO:
        return None
    pres = NPCS.get(npc_id, ([], ""))[0]
    c = CLS.get(cls, "")
    t = _table()
    for pre in pres:
        for mid in ("Intro%sGossip1" % c, "IntroGossip1", "ActIntro%sGossip1" % c, "ActIntroGossip1"):
            if pre + mid in t:
                return pre + mid
    return None


def gossip_keys(npc_id):
    t = _table()
    for pre in NPCS.get(npc_id, ([], ""))[0]:
        ks = []
        n = 1
        while "%sGossip%d" % (pre, n) in t:
            ks.append("%sGossip%d" % (pre, n))
            n += 1
        if ks:
            return ks
    return []


# ------------------------------------------------------------------ quest speech
def _qkeys(qid, events, qname):
    a, n = QUEST_NUM.get(qid, (0, 0))
    t = _table()
    out = []
    for ev in events:
        k = "A%dQ%d%s%s" % (a, n, ev, qname)
        if k in t:
            out.append(k)
    return out


def init_text_key(qid):
    """What the quest giver said when the quest began (the quest log's Play Quest Dialogue)."""
    a, n = QUEST_NUM.get(qid, (0, 0))
    pre = "A%dQ%dInit" % (a, n)
    ks = sorted(k for k in _table() if k.startswith(pre))
    return ks[0] if ks else None


def _event_keys(qid, before, after, qname):
    if before == "none":
        return _qkeys(qid, ("Init", "Init1"), qname)
    if qid == "cain" and after == "stones":
        return _qkeys(qid, ("Instructions",), qname)
    if after == "done":
        return _qkeys(qid, ("QuestSuccessful", "Successful", "SuccessfulStaff"), qname)
    if after in ("cleared",):
        return _qkeys(qid, ("Successful",), qname)
    return []


def _standing_keys(qid, st, qname):
    if st in ("none",):
        return []
    if st == "done":
        return _qkeys(qid, ("QuestSuccessful", "Successful"), qname)
    if qid == "cain" and st in ("scroll", "stones", "portal"):
        return _qkeys(qid, ("AfterInitScroll", "EarlyReturnS", "AfterInit", "EarlyReturn"), qname)
    return _qkeys(qid, ("AfterInit", "EarlyReturn", "EarlyReturn2"), qname)


def converse(world, npc, before, after, first, fallback):
    """What the NPC says now, as [(speaker, text)] pages - D2's own words when the tables have them.
    before/after: the quest states around this talk; first: the hero's first word with this NPC."""
    p = world.player
    nid = getattr(npc, "npc", "")
    name = getattr(npc, "name", nid)
    qname = NPCS.get(nid, ([], ""))[1]
    seen = p.__dict__.setdefault("_dlg_seen", set())
    pages = []
    if first:
        k = intro_key(nid, getattr(p, "cls", ""))
        if k:
            pages.append((name, get(k), k, nid))
            seen.add(k)
    # what this talk changed
    for qid in QUEST_NUM:
        b, a = before.get(qid, "none"), after.get(qid, "none")
        if b != a:
            for k in _event_keys(qid, b, a, qname):
                if k not in seen:
                    pages.append((name, get(k), k, nid))
                    seen.add(k)
                    break
    if pages:
        return pages
    # something new to say about the act's quests (latest first)
    from .acts import act_of
    act = act_of(world.level_id) if getattr(world, "level_id", None) else 1
    qs = [q for q, (a, n) in sorted(QUEST_NUM.items(), key=lambda kv: -kv[1][1]) if a == act]
    for qid in [q for q in qs if after.get(q) not in ("done", "none")] + [q for q in qs if after.get(q) == "done"]:
        for k in _standing_keys(qid, after.get(qid, "none"), qname):
            if k not in seen:
                seen.add(k)
                return [(name, get(k), k, nid)]
    # gossip, in turn
    gk = gossip_keys(nid)
    if gk:
        idx = p.__dict__.setdefault("_gossip", {})
        i = idx.get(nid, 0)
        idx[nid] = i + 1
        k = gk[i % len(gk)]
        return [(name, get(k), k, nid)]
    return []


# ------------------------------------------------------------------ the quest log
LOG = {   # (quest, state) -> D2 qsts key, or a function of the player giving one
    ("den", "active"): lambda p: "qstsa1q12" if 8 in _visited(p) else "qstsa1q11",
    ("den", "cleared"): "qstsa1q15",
    ("blood_raven", "active"): lambda p: "qstsa1q22" if 17 in _visited(p) else "qstsa1q21",
    ("blood_raven", "cleared"): "qstsa1q23",
    ("malus", "active"): "qstsa1q31", ("malus", "cleared"): "qstsa1q32",
    ("cain", "active"): "qstsa1q41", ("cain", "scroll"): "qstsa1q42", ("cain", "stones"): "qstsa1q43",
    ("cain", "portal"): lambda p: "qstsa1q44" if 38 in _visited(p) else "qstsa1q43",
    ("cain", "cleared"): "qstsa1q46",
    ("tower", "active"): lambda p: "qstsa1q52" if 25 in _visited(p) else ("qstsa1q51a" if 21 in _visited(p) else "qstsa1q51"),
    ("andariel", "active"): lambda p: "qstsa1q62" if 37 in _visited(p) else "qstsa1q61",
    ("andariel", "cleared"): "qstsa1q63",
    ("radament", "active"): "qstsa2q11", ("radament", "cleared"): "qstsa2q13",
    ("staff", "active"): "qstsa2q22", ("staff", "cleared"): "qstsa2q24",
    ("tainted", "active"): "qstsa2q32", ("tainted", "cleared"): "qstsa2q33",
    ("arcane", "active"): "qstsa2q41", ("arcane", "palace"): "qstsa2q41",
    ("summoner", "active"): lambda p: "qstsa2q52" if 74 in _visited(p) else "qstsa2q51",
    ("summoner", "cleared"): "qstsa2q53",
    ("tombs", "active"): "qstsa2q61", ("tombs", "placed"): "qstsa2q62", ("tombs", "cleared"): "qstsa2q64",
    ("lamesen", "active"): "qstsa3q11", ("lamesen", "cleared"): "qstsa3q12",
    ("khalim", "active"): "qstsa3q21", ("khalim", "cleared"): "qstsa3q26",
    ("gidbinn", "active"): "qstsa3q31", ("gidbinn", "cleared"): "qstsa3q33",
    ("bird", "active"): "qstsa3q41", ("bird", "jade"): "qstsa3q42", ("bird", "bird"): "qstsa3q44",
    ("council", "active"): lambda p: "qstsa3q52" if 83 in _visited(p) else "qstsa3q51",
    ("council", "cleared"): "qstsa3q53",
    ("mephisto", "active"): lambda p: "qstsa3q63" if 102 in _visited(p) else (
        "qstsa3q62" if p.quests.get("khalim") in ("orb", "done") else "qstsa3q61"),
    ("izual", "active"): lambda p: "qstsa4q12" if 105 in _visited(p) else "qstsa4q11",
    ("izual", "cleared"): "qstsa4q13",
    ("forge", "active"): "qstsa4q31", ("forge", "cleared"): "qstsa4q34",
    ("diablo", "active"): "qstsa4q21",
    ("barbs", "active"): "qstsa5q21", ("barbs", "cleared"): "qstsa5q23",
    ("anya", "active"): "qstsa5q31", ("anya", "cleared"): "qstsa5q34",
    ("nihl", "active"): lambda p: "qstsa5q42" if 124 in _visited(p) else "qstsa5q41",
    ("nihl", "cleared"): "qstsa5q43",
    ("ancients", "active"): lambda p: "qstsa5q52" if 120 in _visited(p) else "qstsa5q51",
    ("baal", "active"): "qstsa5q61a", ("baal", "cleared"): "qstsa5q63",
}


def _visited(p):
    return getattr(p, "visited", ()) or ()


def quest_log(player, qid, state):
    """D2's quest log line for this step, or None (keep this game's own text)."""
    if state == "done":
        return get("qstsComplete")
    k = LOG.get((qid, state))
    if callable(k):
        try:
            k = k(player)
        except Exception:
            k = None
    return get(k) if k else None


def quest_title(qid, fallback):
    a, n = QUEST_NUM.get(qid, (0, 0))
    return get("qstsa%dq%d" % (a, n)) or fallback


def qid_of(title):
    from . import quests, quests2, quests345
    for q, t in list(quests.ACT1) + list(quests2.ACT2) + list(quests345.TITLES.items()):
        if t == title:
            return q
    return None


# ------------------------------------------------------------------ voices (D2's speech files)
_VOICE = {"Akara": ("akara", 1), "Charsi": ("charsi", 1), "Gheed": ("gheed", 1), "Kashya": ("kashya", 1),
          "Warriv": ("warriv", 1), "Cain": ("cain", 1), "Atma": ("atma", 2), "Drognan": ("drognan", 2),
          "Fara": ("fara", 2), "Greiz": ("greiz", 2), "Griez": ("greiz", 2), "Elzix": ("elzix", 2),
          "Lysander": ("lysander", 2), "Meshif": ("meshif", 2), "Geglash": ("geglash", 2), "Jerhyn": ("jerhyn", 2),
          "Ormus": ("ormus", 3), "Alkor": ("alkor", 3), "Asheara": ("asheara", 3), "Hratli": ("hratli", 3),
          "Natalya": ("natalya", 3), "Tyrael": ("tyrael", 4), "Larzuk": ("larzuk", 5), "Malah": ("malah", 5),
          "QualKehk": ("qualkehk", 5), "Anya": ("anya", 5), "Nihlathak": ("nihlathak", 5)}
_NPC_ACT = {"cain2": 2, "cain3": 3, "cain4": 4, "cain6": 5, "warriv2": 2, "meshif2": 3, "tyrael1": 2,
            "tyrael2": 4, "tyrael3": 5}
_EV = {"Init": "init", "Init1": "init", "AfterInit": "after", "AfterInitScroll": "after_scroll",
       "EarlyReturn": "early", "EarlyReturnS": "early_scroll", "EarlyReturn2": "early2", "Successful": "success",
       "QuestSuccessful": "success", "SuccessfulScroll": "success_scroll", "Instructions": "instructions",
       "RescuedByHero": "rescued_hero", "SuccessfulStaff": "success_staff"}


def greeting_name(npc_id):
    pre = NPCS.get(npc_id, ([], ""))[1]
    for k, (sp, _) in _VOICE.items():
        if pre.startswith(k):
            return sp + "_greeting"
    return None


def voice_names(key, npc_id=None, cls=""):
    """D2's speech sound names for a string key (A1Q1InitAkara -> akara_act1_q1_init ...), best first."""
    if not key:
        return []
    m = re.match(r"A(\d)Q(\d)(.+)$", key)
    pres = sorted(_VOICE, key=len, reverse=True)
    if m:
        a, q, rest = m.group(1), m.group(2), m.group(3)
        rest = re.sub(r"(Act\d)$", "", rest)
        for pre in pres:
            if rest.endswith(pre):
                ev = rest[:-len(pre)]
                sp = _VOICE[pre][0]
                e = _EV.get(ev, ev.lower())
                return ["%s_act%s_q%s_%s" % (sp, a, q, e)]
        return []
    for pre in pres:
        if key.startswith(pre):
            sp, act = _VOICE[pre]
            act = _NPC_ACT.get(npc_id, act)
            rest = key[len(pre):]
            ma = re.match(r"Act(\d)(.*)$", rest)
            if ma:
                act, rest = int(ma.group(1)), ma.group(2)
            rest = re.sub(r"^Act", "", rest)
            mi = re.match(r"Intro(Ama|Sor|Nec|Pal|Bar|Dru|Ass)?(More)?Gossip1$", rest)
            if mi:
                base = "%s_act%d_intro" % (sp, act)
                if mi.group(1):
                    return [base + "_" + mi.group(1).lower(), base]
                if mi.group(2):
                    return [base + "_more", base]
                return [base]
            mg = re.match(r"Gossip(\d+)$", rest)
            if mg:
                return ["%s_act%d_gossip_%s" % (sp, act, mg.group(1))]
            return []
    return []
