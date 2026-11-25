"""Checks for the autobattler that need no Diablo II files (placeholder art, generated cave).

    python tools/test_autobattler.py
"""
import os
import random
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from autobattler import config, roster, timing  # noqa: E402
from autobattler.runs import RunManager         # noqa: E402

FAILS = []


def _tick(mgr):
    """One game frame; floors are built on a background thread, so wait for one being built
    (in the game, frames take real time while it builds)."""
    mgr.tick()
    for r in mgr.active():
        th = getattr(r, "_thread", None)
        if th is not None:
            th.join()


def check(cond, what):
    print(("ok    " if cond else "FAIL  ") + what)
    if not cond:
        FAILS.append(what)


def test_timing():
    # Barbarian hit recovery breakpoints (published table): FHR -> frames
    base = (timing.HERO_GH_FRAMES["bar"] + 1) / 2.0
    table = {0: 9, 6: 9, 7: 8, 14: 8, 15: 7, 27: 6, 48: 5, 86: 4, 200: 3}
    got = {fhr: timing.hit_recovery_frames(base, fhr) for fhr in table}
    check(got == table, "Barbarian FHR breakpoints %s" % got)
    sor = (timing.HERO_GH_FRAMES["sor"] + 1) / 2.0
    check(timing.hit_recovery_frames(sor, 0) == 15, "Sorceress 0% FHR = 15 frames")
    check(timing.attack_frames(15, 0) == 14, "15-frame attack at 0 IAS = 14 frames")
    fast = [timing.attack_frames(15, ias) for ias in (0, 20, 40, 80, 200)]
    check(fast == sorted(fast, reverse=True) and fast[-1] < fast[0], "IAS only ever speeds attacks up %s" % fast)
    check(timing.eias(1000) == 75, "EIAS is capped at 75")
    check(timing.effective(20) == 17 and timing.effective(20, 150) == 17, "diminishing returns")
    check(abs(timing.move_speed(9, 0) - 9.0) < 1e-9, "run speed without FRW")


def _hero(name, cls="bar"):
    from game.units import Player
    p = Player(0, 0, cls=cls, name=name)
    p.recalc()
    return p


class _NoAssets:
    act_kit = None
    content = None


def _cfg():
    c = dict(config.DEFAULTS)
    c["floor_pause"] = 0.2
    return c


def test_runs():
    config.apply_d2_rules()
    random.seed(7)
    mgr = RunManager(_NoAssets(), _cfg())
    a, b = _hero("Alpha"), _hero("Bravo", "pal")
    r = mgr.start([a])
    check(not isinstance(r, str), "a run starts")
    g = mgr.start([b, _hero("Charlie", "ama")])
    check(not isinstance(g, str), "a group run starts")
    again = mgr.start([a])
    check(isinstance(again, str), "a hero can't be on two runs: %r" % again)
    many = [_hero("H%d" % i) for i in range(6)]
    full = mgr.start(many[:4])
    check(not isinstance(full, str), "up to 8 heroes on runs")
    eighth = mgr.start(many[4:5])
    check(not isinstance(eighth, str), "the 8th hero still fits")
    over = mgr.start(many[5:6])
    check(isinstance(over, str), "the 9th hero is refused: %r" % over)
    frames = 0
    floors_seen = 0
    while frames < 25 * 60 * 6:              # six minutes of game time
        _tick(mgr)
        frames += 1
        floors_seen = max(floors_seen, r.floors)
        if r.state == "over" and g.state == "over" and full.state == "over":
            break
    check(r.kills > 0 or r.floors > 0, "the solo run fights: %d kills, %d floors, %s" % (r.kills, r.floors, r.state))
    check(g.kills > 0 or g.floors > 0, "the group run fights: %d kills, %d floors, %s" % (g.kills, g.floors, g.state))
    check(all(x.state != "over" or x.result in ("died", "stopped") for x in (r, g, full)),
          "runs end only by dying or stopping (no errors): %s" % [x.result for x in (r, g, full)])
    print("      solo: floors %d kills %d level %d state %s" % (r.floors, r.kills, a.level, r.state))
    print("      group: floors %d kills %d levels %s" % (g.floors, g.kills, [h.level for h in g.heroes]))


def test_floor_progress():
    """A strong hero clears the placeholder floor and goes on to the next one."""
    config.apply_d2_rules()
    random.seed(3)
    mgr = RunManager(_NoAssets(), _cfg())
    h = _hero("Strong")
    h.level = 30
    h.base_str, h.base_vit, h.base_dex = 150, 200, 80
    h.recalc()
    h.hp = h.max_hp
    r = mgr.start([h])
    for _ in range(25 * 60 * 8):
        _tick(mgr)
        if r.floors >= 2 or r.state == "over":
            break
    check(r.floors >= 2, "floor cleared -> next floor: %d floors, depth %d, %d kills, %s" % (r.floors, r.depth, r.kills, r.state))
    check(int(getattr(h, "rift_depth", 0)) >= 1, "the deepest floor is remembered on the hero")


def test_brain():
    """Heroes spend their points by their plan and use their skills in the fight."""
    from autobattler import brain
    config.apply_d2_rules()
    random.seed(11)
    h = _hero("Thinker")
    h.level = 12
    h.skills.points = 12
    h.stat_points = 55
    s0 = (h.base_str, h.base_vit)
    brain.spend_points(h)
    check(h.skills.points == 12 and h.stat_points == 55, "points wait for the player by default")
    from autobattler import points
    points.set_auto(h, True)
    learned = {k: v for k, v in h.skills.levels.items() if v}
    check(h.skills.points == 0 and len(learned) >= 3, "skill points spent by the plan: %s" % learned)
    check(h.stat_points == 0 and h.base_str > s0[0] and h.base_vit > s0[1], "stat points spent")
    check(brain.profile(h)["style"] == "balanced" and brain.cycle_style(h) == "aggressive", "profile and styles")
    brain.profile(h)["style"] = "balanced"
    # a fight with skills: a run on the placeholder floor, counting what was cast
    h.base_str, h.base_vit = 120, 150
    h.recalc()
    h.hp = h.max_hp
    h.mana = h.max_mana = max(h.max_mana, 200)
    mgr = RunManager(_NoAssets(), _cfg())
    r = mgr.start([h])
    used = {}
    for _ in range(25 * 60 * 4):
        _tick(mgr)
        if r.sim is not None:
            for k, v in r.sim.casts.items():
                used[k] = max(used.get(k, 0), v)
        if r.state == "over":
            break
    check(sum(used.values()) > 0, "skills cast during the run: %s" % used)
    check(r.result in (None, "died", "stopped"), "no errors in the run (%s), kills %d" % (r.result, r.kills))


def test_points_by_hand():
    """The Character screen's stat and skill spending (autobattler/points.py)."""
    from autobattler import points
    h = _hero("Chooser")
    h.level = 6
    h.skills.points = 3
    h.stat_points = 10
    s0, hp0 = h.base_str, h.max_hp
    check(points.add_stat(h, "str") == 1 and h.base_str == s0 + 1 and h.stat_points == 9, "one point into Strength")
    check(points.add_stat(h, "vit", 99) == 9 and h.stat_points == 0 and h.max_hp > hp0, "the rest into Vitality")
    check(points.add_stat(h, "dex") == 0, "no points, nothing added")
    check(points.reset_stats(h) == 10 and h.stat_points == 10 and h.base_str == s0, "stats reset")
    first = next(n for n, s in h.skills.tree.items() if s.reqlevel <= 1 and not s.prereqs)
    late = next((n for n, s in h.skills.tree.items() if s.reqlevel > h.level), None)
    check(points.learn(h, first) and h.skills.levels[first] == 1 and h.skills.points == 2, "a skill learned")
    check(late is None or not points.learn(h, late), "a skill above his level is refused")
    check(points.reset_skills(h) == 1 and h.skills.points == 3 and not h.skills.levels.get(first), "skills reset")
    points.set_auto(h, True)
    check(h.skills.points == 0 and h.stat_points == 0, "turning the class plan on spends them")


def test_town_stash():
    """The shared stash: one hero puts an item in, another takes it out (autobattler/gear.py)."""
    from autobattler import gear
    from game import save as gsave
    from game.items import Item
    from game.cube import stash_tab
    st = gsave.load_shared_stash(None)
    st.purse = None
    a, b = _hero("Giver"), _hero("Taker")
    ring = Item("Ring", "rin", "ring")
    a.inv_add(ring)
    ga = gear.Bench(a, None, stash=st)
    stash_tab(st, 1)
    check(ga.backpack_to_stash(ring) and ring in st.contents and ring not in a.inventory,
          "an item goes from the backpack into the stash")
    gsave.save_shared_stash(st)
    st2 = gsave.load_shared_stash(None)
    stash_tab(st2, 1)
    check(len(st2.contents) == 1, "the stash is saved for the whole account")
    gb = gear.Bench(b, None, stash=st)
    check(gb.stash_click(*ring.cube_pos) and gb.held is ring, "another hero picks it up from the stash")
    check(gb.click_cell(0, 0) and ring in b.inventory, "and puts it in his backpack")
    check(a.gold == a._gold and b.gold == b._gold, "gold stays each hero's own")
    big = Item("Plate", "plt", "armor")
    big.invw, big.invh = 2, 3
    b.inv_add(big)
    gb.click_cell(*big.inv_pos)
    for x in range(b.INV_W):
        for y in range(b.INV_H):
            b.inv_add(Item("Stone", "sto", "helm"))
    check(gb.finish() == 0 and any(big in pg for pg in st.pages),
          "with a full backpack the cursor item goes to the stash, not sold")


def test_no_essences():
    from game import essences
    config.apply_d2_rules()
    check(not essences.DROPS and essences.roll_drop(None, None) is None, "no essences drop in the autobattler")


def test_smart_ai():
    """Builds, Throw first with a javelin, kiting, and the retreat home with no potions left."""
    import types
    from autobattler import brain
    config.apply_d2_rules()
    random.seed(9)

    def fake_book(levels, kinds):
        tree = {n: types.SimpleNamespace(kind=k, weapon=(k == "melee")) for n, k in kinds.items()}
        return types.SimpleNamespace(levels=levels, tree=tree)

    def role(levels, kinds, **kw):
        b = brain.Brain.__new__(brain.Brain)
        b.h = types.SimpleNamespace(level=10, equipment={}, skills=fake_book(levels, kinds), **kw)
        b.sim = types.SimpleNamespace(frame=0)
        return b.role()
    check(role({"Bash": 5}, {"Bash": "melee"}) == "melee", "points in weapon skills: melee")
    check(role({"Fire Bolt": 6, "Warmth": 1}, {"Fire Bolt": "missile", "Warmth": "passive"}) == "caster",
          "points in damage spells: caster")
    check(role({"Raise Skeleton": 8, "Teeth": 1}, {"Raise Skeleton": "raise", "Teeth": "missile"}) == "summoner",
          "points in summons: summoner")
    check(role({"Jab": 5}, {"Jab": "melee"}, throwing=True) == "thrower", "a javelin in hand: thrower")
    check(role({}, {}, ranged=True) == "ranged", "a bow in hand: ranged")
    # a run: Throw first for a thrower, kiting, and home with no potions
    h = _hero("Clever")
    h.base_vit = 150
    h.recalc()
    h.hp = h.max_hp
    mgr = RunManager(_NoAssets(), _cfg())
    r = mgr.start([h])
    for _ in range(30):
        _tick(mgr)
    sim = r.sim
    foe = min(sim.foes(), key=lambda m: abs(m.x - h.x) + abs(m.y - h.y))
    h.throwing = True
    b = sim.brain(h)
    b._role_key = None
    far = types.SimpleNamespace(pos=(h.x + 4, h.y), hp=999, max_hp=999, alive=True, res={}, defense=0,
                                radius=0, curses={}, level=1)
    plan = b.decide(far, [far])
    check(plan is not None and plan.skill == "throw", "with a javelin, Throw comes first at range: %s" % (plan and plan.why))
    h.throwing = False
    b._role_key = None
    del h.belt[:]
    h.hp = max(1, h.max_hp // 10)
    foe.aware = True
    foe.x, foe.y = h.x + 1, h.y
    sim._rebuild_occ()
    st = sim._state(h)
    sim._survive(h, st, b)
    check(sim.need_town, "nearly dead with no potions: he retreats")
    _tick(mgr)
    check(r.state == "town" and h.hp == h.max_hp, "and the run takes him home to be mended")
    r.finish("stopped")


def test_town_and_back():
    """To town: the run waits on its floor; Continue run goes on from the same floor."""
    h = _hero("Traveller")
    mgr = RunManager(_NoAssets(), _cfg())
    r = mgr.start([h])
    for _ in range(100):
        _tick(mgr)
    w, depth = r.world, r.depth
    h.hp = 1
    check(r.go_town() and r.state == "town" and h.hp == h.max_hp, "to town: the run waits, Tyrael mends him")
    check(h.name in mgr.busy_names() and h.name not in mgr.on_floor_names(), "he is in town, his run still going")
    f0 = r.sim.frame
    for _ in range(50):
        _tick(mgr)
    check(r.sim.frame == f0 and r.state == "town", "the floor waits while he is in town")
    check(r.resume() and r.state == "fight" and r.world is w and r.depth == depth, "continue: the same floor")
    _tick(mgr)
    check(r.sim.frame == f0 + 1, "and it plays on")
    check(not r.go_town() and r.state == "fight", "one trip to town per floor: the second is refused")
    r.sim.at_portal = True
    _tick(mgr)
    check(not r.town_used, "a cleared floor gives the trip back")
    r.finish("stopped")


def test_belt_columns():
    """Four belt rows: 1-2 healing, 3-4 mana; any row can be drunk from."""
    import types
    from autobattler import brain
    from game import potions
    from game.items import Item
    config.apply_d2_rules()
    h = _hero("Belted")

    def pot(kind, code):
        it = Item(kind, code, None, kind="potion")
        it.potion = kind
        return it
    check(potions.belt_rows(h) == 4, "every hero's belt has 4 rows")
    for _ in range(8):
        potions.belt_add(h, pot("mana", "mp1"))
        potions.belt_add(h, pot("heal", "hp1"))
    rows = [[getattr(x, "potion", "") for x in potions.column(h, c)] for c in range(4)]
    check(all(col == ["heal", "heal", "mana", "mana"] for col in rows), "rows 1-2 healing, 3-4 mana: %s" % rows)
    check(not potions.has_room(h, pot("mana", "mp1")), "full belt: no more room")
    potions.drink(types.SimpleNamespace(player=h, mode="explore", player_can_act=lambda: True,
                                        emit=lambda *a: None, log=lambda *a: None,
                                        _maybe_auto_end=lambda: None), 0, 2)
    col = [x.potion for x in potions.column(h, 0)]
    check(col == ["heal", "heal", "mana"], "after drinking a mana potion the rows stay in order: %s" % col)
    check(potions.has_room(h, pot("mana", "mp1")) and not potions.has_room(h, pot("heal", "hp1")),
          "and the free place takes mana only")
    potions.ROW_RULE = None
    potions.ROWS_OVERRIDE = None


def test_full_bag_trip():
    """A full backpack: home, gems / runes / unique / set items into the stash, back to the floor."""
    from autobattler import stash
    from game.items import Item
    h = _hero("Hoarder")
    st = stash.get(None)
    for i in range(80):
        if i % 3 == 0:
            it = Item("Chipped Ruby", "gcr", None, kind="misc")
            it.gem, it.base = ("gem", "ruby", 0), {"code": "gcr"}
        elif i % 3 == 1:
            it = Item("Unique Cap", "cap", "helm", rarity="unique")
        elif i % 2:
            it = Item("Magic Cap", "cap", "helm", rarity="magic")
        else:
            it = Item("Stone", "sto", "helm")
        if not h.inv_add(it):
            break
    mgr = RunManager(_NoAssets(), _cfg())
    r = mgr.start([h])
    for _ in range(60):
        _tick(mgr)
    bank0, items0 = st.bank.get("gcr", 0), sum(len(p) for p in st.pages)
    worn = Item("Magic Boots", "lbt", "boots", rarity="magic")
    h.equipment["boots"] = worn
    gold0 = h.gold
    r.sim.no_room = True
    _tick(mgr)
    check(r.state == "town", "a full backpack sends him home")
    check(st.bank.get("gcr", 0) > bank0 and sum(len(p) for p in st.pages) > items0
          and not any(stash.keeps(it) for it in h.inventory), "gems and unique items go to the stash")
    check(not any(it.rarity in ("magic", "rare") for it in h.inventory) and h.gold > gold0
          and h.equipment["boots"] is worn, "magic and rare items in the backpack are sold, worn ones kept")
    for _ in range(int(r.AUTO_TOWN_SECONDS * 25) + 2):
        _tick(mgr)
    check(r.state == "fight", "and he goes back to the floor by himself")
    r.sim.no_room = True
    _tick(mgr)
    check(r.state == "fight", "nothing the stash takes: he stays on the floor")
    r.finish("stopped")


def test_d2_difficulty():
    """D2's own monsters: /players 1 for one hero, +50% life and experience per extra hero."""
    import types
    from game import actworld, rift, tactics
    from autobattler.runs import scale_for_players
    config.apply_d2_rules()
    check(actworld.BOSS_LIFE_NORMAL == 1.0 and rift.KEEPER_LIFE == 1.0 and not tactics.ACTIVE,
          "no D2 Tactics life changes on bosses, keepers or parties")
    mk = lambda: types.SimpleNamespace(max_hp=100, hp=100, xp_value=10, ally=False, is_player=False, ai="")
    one, three = [mk()], [mk()]
    scale_for_players(types.SimpleNamespace(monsters=one), 1)
    scale_for_players(types.SimpleNamespace(monsters=three), 3)
    check(one[0].max_hp == 100 and three[0].max_hp == 200 and three[0].xp_value == 20,
          "one hero: /players 1; three heroes: /players 3 (x2 life and experience)")


def test_summons_once():
    """A summon that is up is not cast again; once it dies, it is."""
    import types
    from autobattler import brain
    b = brain.Brain.__new__(brain.Brain)
    h = types.SimpleNamespace()
    golem = types.SimpleNamespace(alive=True, ally=True, summon_skill="Clay Golem", summoner=h)
    other = types.SimpleNamespace(alive=True, ally=True, summon_skill="Clay Golem", summoner=object())
    b.h, b.sim = h, types.SimpleNamespace(w=types.SimpleNamespace(monsters=[golem, other]))
    s = types.SimpleNamespace(data=None)
    check(b._summons_full("IronGolem", s), "his golem is up: no other golem")
    golem.alive = False
    check(not b._summons_full("Clay Golem", s), "his golem died: he summons one (another hero's golem doesn't count)")


def test_act_levels():
    """Monster levels follow the acts: each act climbs to its boss's level; 51-60 go on past Baal."""
    from game import rift
    keep = rift.SIXTH
    rift.SIXTH = True
    try:
        lv = [rift.act_level(d) for d in (1, 10, 11, 20, 21, 30, 31, 40, 41, 50, 51, 60, 61)]
        check(lv == [1, 12, 13, 22, 23, 26, 27, 40, 41, 60, 61, 70, 71],
              "floor levels (1, 10, 11, 20, 21, 30, 31, 40, 41, 50, 51, 60, 61): %s" % lv)
        check(all(rift.act_level(d) <= rift.act_level(d + 1) for d in range(1, 119)), "they never go down")
        check(rift.act_of_depth(60) == 5 and rift.act_of_depth(61) == 1, "floor 60 is Act 5's (Baal), 61 starts over")
    finally:
        rift.SIXTH = keep


def test_charm_inventory():
    """Only charms go in the charm inventory, only the charms there work, and they aren't sold."""
    from autobattler import gear
    from autobattler.runs import sell_magic_and_rare
    from game.items import Item
    h = _hero("Charmed")
    charm = Item("Small Charm of Life", "cm1", None, rarity="magic", kind="misc")
    charm.charm, charm.mod_list, charm.levelreq = True, [], 1
    h.inv_add(charm)
    h.qol = {}
    h.charm_inv = None
    gear.prepare(h)
    check(charm in h.charm_inv and charm not in h.inventory, "charms in the backpack move to the charm inventory")
    check(charm in h._charms(), "a charm in the charm inventory works")
    b = gear.Bench(h)
    check(b.charm_to_backpack(charm) and charm in h.inventory and charm not in h._charms(),
          "a charm in the backpack doesn't work")
    check(b.right_click(charm) and charm in h.charm_inv, "right click puts it back in the charm inventory")
    ring = Item("Ring", "rin", "ring", rarity="magic")
    h.inv_add(ring)
    b.click_cell(*ring.inv_pos)
    check(not b.charm_click(0, 4) and b.held is ring, "only charms go in")
    b.finish()
    loose = Item("Grand Charm", "cm3", None, rarity="magic", kind="misc")
    loose.charm = True
    h.inv_add(loose)
    sold, _ = sell_magic_and_rare(h)
    check(loose in h.inventory and ring not in h.inventory and charm in h.charm_inv,
          "the trip home sells the ring, never a charm")


def test_skill_animations():
    """Each skill plays D2's own animation: Skills.txt anim, Throw throws, weapon skills swing."""
    import types
    from autobattler.realtime import Sim
    sk = lambda anim, kind="missile", weapon=False: types.SimpleNamespace(data={"anim": anim}, kind=kind, weapon=weapon)
    check(Sim.skill_anim(None, "throw") == "TH", "Throw: TH")
    check(Sim.skill_anim(sk("TH")) == "TH", "a javelin skill (anim TH): TH")
    check(Sim.skill_anim(sk("A1", weapon=True)) == "A1", "a bow skill (anim A1): A1")
    check(Sim.skill_anim(sk("", weapon=True)) == "A1", "a weapon skill without anim: A1")
    check(Sim.skill_anim(sk("SC")) == "SC" and Sim.skill_anim(sk("")) == "SC", "a spell: SC")


def test_farms():
    """What a run farms: the rift goes on from his deepest floor; the Black Road and the Countess
    start from the beginning, and the tower goes round levels 1-5."""
    from autobattler import brain
    from autobattler.runs import Run, TOWER
    from game import arena
    h = _hero("Farmer")
    h.rift_depth = 7
    r = Run([h], _NoAssets(), _cfg(), None)
    check(r.farm == "rift" and r.depth == 8, "rift: goes on from floor 8")
    brain.profile(h)["farm"] = "boss"
    r = Run([h], _NoAssets(), _cfg(), None)
    check(r.depth == 1 and r.level_key() == arena.BOSS_LEVEL and r.where() == "Black Road 1", "Black Road")
    brain.profile(h)["farm"] = "runes"
    r = Run([h], _NoAssets(), _cfg(), None)
    keys = []
    for d in range(1, 8):
        r.depth = d
        keys.append(r.level_key())
    check(keys == [21, 22, 23, 24, 25, 21, 22] and "Tower Cellar 5" in (lambda: (setattr(r, "depth", 5), r.where())[1])(),
          "runes: Tower Cellar 1-5, then again: %s" % keys)
    brain.profile(h)["farm"] = "rift"


def test_d2_quality():
    """D2's item quality (ItemRatio.txt): rates, magic find with diminishing returns, TC ratios."""
    import types
    from game.d2content import D2Content
    c = D2Content.__new__(D2Content)
    c.src = None
    c.D2_DROPS = True
    c.uniques_for = lambda b, l: [1]
    c.set_items_for = lambda b, l: [1]
    base = {"code": "cap", "qlvl": 1, "tiers": ("cap", "xap", "uap")}
    rng = random.Random(1)

    def rates(mf, tcq=(0, 0, 0, 0), n=40000):
        c._tcq = tcq
        out = {}
        for _ in range(n):
            q = c.roll_quality(base, 1, rng, mf)
            out[q] = out.get(q, 0) + 1
        c._tcq = (0, 0, 0, 0)
        return {k: v / float(n) for k, v in out.items()}
    r0, r3 = rates(0), rates(300)
    check(0.001 < r0.get("unique", 0) < 0.005 and r0.get("magic", 0) > r0.get("rare", 0) > r0.get("unique", 0),
          "D2 base rates: %s" % {k: round(v, 4) for k, v in sorted(r0.items())})
    check(r3.get("magic", 0) > 2.5 * r0.get("magic", 0) and 1.6 * r0.get("unique", 0) < r3.get("unique", 0) < 3.2 * r0.get("unique", 0),
          "300 MF: magic x%.1f, unique x%.1f (diminishing)" % (r3.get("magic", 0) / max(1e-9, r0.get("magic", 0)),
                                                            r3.get("unique", 0) / max(1e-9, r0.get("unique", 0))))
    rb = rates(0, (983, 983, 983, 1024))
    check(rb.get("unique", 0) > 10 * r0.get("unique", 0), "a boss class's ratios: far better odds")


def test_summons_fight():
    """Summons walk with their summoner and fight in real time; his own side never blocks his way."""
    import copy
    from game.grid import chebyshev
    config.apply_d2_rules()
    random.seed(4)
    h = _hero("Necro")
    h.base_vit = 300
    h.recalc()
    h.hp = h.max_hp
    mgr = RunManager(_NoAssets(), _cfg())
    r = mgr.start([h])
    _tick(mgr)
    _tick(mgr)
    w = r.world
    proto = [f for f in r.sim.foes() if not getattr(f, "rift_boss", False)][0]
    pets = []
    for _ in range(3):
        m = copy.copy(proto)
        m.effects, m.curses = {}, {}
        m.ally, m.ai, m.aware, m.summoner, m.summon_skill, m.life_turns = True, "ally", False, h, "Raise Skeleton", None
        m.x, m.y = w._free_cell_near(h.pos, 3)
        m.hp = m.max_hp = 200
        m.tc, m.unique, m.rift_boss = None, False, False
        w.monsters.append(m)
        pets.append(m)
    attacks, far = 0, 0
    for _ in range(25 * 40):
        _tick(mgr)
        if r.state != "fight" or r.world is not w:
            break
        for p in pets:
            if p.alive:
                attacks += r.sim._state(p).mode == "attack"
                far = max(far, chebyshev(p.pos, h.pos))
    check(attacks > 50, "skeletons fight (%d frames of attacking)" % attacks)
    check(r.floors == 0 or attacks > 0, "his skeletons don't end the floor by standing round him")
    r.finish("stopped")


def test_ready_skeletons():
    """A necromancer starts every floor with his skeletons already raised, as many as he may have."""
    from game.skills import Skill
    config.apply_d2_rules()
    h = _hero("Necro2")
    sk = Skill("Raise Skeleton", 1, 1, 1, 1, [], 6, 0, "raise")
    sk.data = {"summon": "skeleton1", "petmax": "3"}
    h.skills.tree["Raise Skeleton"] = sk
    h.skills.levels["Raise Skeleton"] = 4
    mgr = RunManager(_NoAssets(), _cfg())
    r = mgr.start([h])
    _tick(mgr)
    _tick(mgr)
    pets = [a for a in r.world.monsters if getattr(a, "ally", False) and a.alive and getattr(a, "summoner", None) is h]
    check(len(pets) == 3, "the floor starts with his 3 skeletons up (%d)" % len(pets))
    r.finish("stopped")


def test_line_of_fire():
    """A shot needs open floor all the way: a pillar between stops it, so he walks round."""
    import types
    from autobattler.realtime import Sim
    from game.grid import Grid, FLOOR, WALL
    g = Grid(20, 20, FLOOR)
    g.cells[5][7] = WALL                       # a pillar between (5, 5) and (9, 5)
    sim = Sim.__new__(Sim)
    sim.w = types.SimpleNamespace(grid=g)
    a, b, c = (types.SimpleNamespace(pos=p) for p in ((5, 5), (9, 5), (5, 9)))
    check(not sim._can_shoot(a, b), "a pillar in the way: no shot")
    check(sim._can_shoot(a, c), "open floor: a clear shot")


def test_runeword_bases():
    """Home: exceptional / elite plain items with all their sockets go to the stash; other plain
    gear is sold with the magic and rare items."""
    from autobattler import stash
    from autobattler.runs import sell_magic_and_rare
    from game.items import Item

    def gear(code, tiers, sockets, maxsock=4):
        it = Item(code, code, "armor", rarity="normal")
        it.base = {"code": code, "tiers": tiers, "maxsock": maxsock}
        it.sockets = sockets
        return it
    elite4 = gear("uar", ("aar", "xar", "uar"), 4)          # an elite 4-socket armor: a base
    exc3 = gear("xar", ("aar", "xar", "uar"), 3)            # exceptional, one socket short
    norm4 = gear("aar", ("aar", "xar", "uar"), 4)           # normal tier: no
    check(stash.keeps(elite4) and not stash.keeps(exc3) and not stash.keeps(norm4),
          "only tier II / III with all their sockets are kept")
    h = _hero("Sorter")
    for it in (elite4, exc3, norm4):
        h.inv_add(it)
    st = stash.get(None)
    stash.deposit(h, st)
    sold, _ = sell_magic_and_rare(h)
    check(any(elite4 in p for p in st.pages) and exc3 not in h.inventory and norm4 not in h.inventory and sold == 2,
          "the base goes to the stash, the rest is sold")


def test_rare_cores():
    """Each rare item sold gives one Rare Core: by hand, and on the trip home."""
    from autobattler import gear
    from autobattler.runs import sell_magic_and_rare
    from game.items import Item
    h = _hero("Crafter")
    c0 = gear.rare_cores(h)
    b = gear.Bench(h)
    r1, m1 = Item("Rare Ring", "rin", "ring", rarity="rare"), Item("Magic Ring", "rin", "ring", rarity="magic")
    h.inv_add(r1)
    h.inv_add(m1)
    b.sell(r1)
    b.sell(m1)
    check(gear.rare_cores(h) == c0 + 1, "selling a rare by hand: +1 core, a magic one: none")
    for _ in range(3):
        h.inv_add(Item("Rare Cap", "cap", "helm", rarity="rare"))
    sell_magic_and_rare(h)
    check(gear.rare_cores(h) == c0 + 4, "three rares sold on the trip home: +3 cores")


def test_horadric_cube():
    """The cube menu: Craft Rare takes one white or blue item and a Rare Core (account-wide)."""
    import types
    from autobattler import gear, account, recipes
    from game.items import Item
    h = _hero("Cuber")
    box = Item("Horadric Cube", "box", None, kind="misc")
    inside = Item("Gem", "gcr", None, kind="misc")
    box.contents = [inside]
    h.inv_add(box)
    h.qol = {}
    h.cube_inv = None
    gear.prepare(h)
    check(box not in h.inventory and inside in h.cube_inv, "a carried cube becomes the cube menu (its contents kept)")
    h.cube_inv[:] = []

    def make_item(base, ilvl, rng, quality="normal", sockets=None, identified=None):
        it = Item("Grim Visage", base["code"], "helm", rarity=quality)
        it.base, it.ilvl = base, ilvl
        return it
    content = types.SimpleNamespace(make_item=make_item)
    b = gear.Bench(h, content)
    cap = Item("Cap of the Fox", "cap", "helm", rarity="magic")
    cap.base = {"code": "cap"}
    h.inv_add(cap)
    check(b.backpack_to_cube(cap) and cap in h.cube_inv, "into the cube")
    rare = recipes.RECIPES[0]
    account.data()["rare_cores"] = 0
    check(not b.transmute(rare) and cap in h.cube_inv, "no Rare Core: nothing happens")
    account.add("rare_cores", 2)
    check(b.transmute(rare) and len(h.cube_inv) == 1 and h.cube_inv[0].rarity == "rare"
          and h.cube_inv[0].ilvl == h.level and account.amount("rare_cores") == 1,
          "Craft Rare: a rare of the same base at his level, one core paid")
    ring_unique = Item("Unique Ring", "rin", "ring", rarity="unique")
    h.cube_inv[:] = [ring_unique]
    check(rare.check(h.cube_inv, h) is not None, "a unique can't be crafted")


def test_socketing():
    """A rune dropped on an item with a free socket goes into it."""
    import types
    from autobattler import gear
    from game.items import Item
    h = _hero("Socketer")
    msgs = []
    sword = Item("Long Sword", "lsd", "weapon")
    sword.sockets, sword.socketed = 2, []
    h.inv_add(sword)
    rune = Item("El Rune", "r01", None, kind="misc")
    rune.gem, rune.levelreq = ("rune", "el", 0), 1
    import game.d2items as d2i
    old = d2i.insert
    d2i.insert = lambda content, host, filler, rng: (host.socketed.append(filler), "Inserted El Rune.")[1]
    try:
        b = gear.Bench(h, types.SimpleNamespace())
        b.held = rune
        check(b.click_cell(*sword.inv_pos) and rune in sword.socketed and b.held is None,
              "the rune goes into the socket")
    finally:
        d2i.insert = old


def test_boss_gate_and_difficulty():
    """Before every act boss the run waits in town until the player sends it in; floor 60 opens the
    next difficulty; each difficulty keeps its own depth."""
    from autobattler import brain
    from autobattler.runs import unlocked, difficulty_of, set_rift_cleared, cleared
    config.apply_d2_rules()
    random.seed(3)
    h = _hero("Gatekeeper")
    h.base_vit, h.base_str = 400, 300
    h.recalc()
    h.hp = h.max_hp
    set_rift_cleared(h, "normal", 8)
    h.rift_depth = 8
    mgr = RunManager(_NoAssets(), _cfg())
    r = mgr.start([h])
    check(r.depth == 9, "starts on floor 9")
    for _ in range(10):
        _tick(mgr)
    r.sim.at_portal = True                       # (floor 9 done)
    _tick(mgr)
    check(r.state == "gate" and r.depth == 10, "floor 9 cleared: back in town, the floor 10 boss waits (%s, %d)" % (r.state, r.depth))
    for _ in range(50):
        _tick(mgr)
    check(r.state == "gate", "it waits for the player")
    check(r.fight_boss() and r.state == "build", "Fight boss: into floor 10")
    r.finish("stopped")
    # unlocks and depth by difficulty
    check(unlocked(h) == ["normal"] and difficulty_of(h) == "normal", "only Normal at first")
    brain.profile(h)["unlocked"] = ["normal", "nightmare"]
    brain.profile(h)["difficulty"] = "nightmare"
    set_rift_cleared(h, "nightmare", 3)
    r2 = mgr.start([h])
    check(r2.difficulty == "nightmare" and r2.depth == 4 and "Nightmare" in r2.where(),
          "Nightmare goes on from its own depth: %s" % r2.where())
    r2.finish("stopped")
    brain.profile(h)["difficulty"] = "normal"


def test_cast_breakpoints():
    from autobattler.brain import CAST_FRAMES0
    sor = [timing.cast_frames(CAST_FRAMES0["sor"] + 1, f) for f in (0, 9, 20, 37, 63, 105, 200)]
    check(sor == [13, 12, 11, 10, 9, 8, 7], "Sorceress FCR breakpoints %s" % sor)
    nec = [timing.cast_frames(CAST_FRAMES0["nec"] + 1, f) for f in (0, 9, 18, 30, 48, 75, 125)]
    check(nec == [15, 14, 13, 12, 11, 10, 9], "Necromancer FCR breakpoints %s" % nec)


def test_acts():
    """Floors 1-10 Act 1 ... 41-50 Act 5, the act's boss on every tenth floor (big floors only)."""
    from game import rift
    rift.BIG = True
    rift.forget(None)
    acts = [rift.act_of_depth(d) for d in (1, 10, 11, 20, 21, 31, 41, 50, 51)]
    check(acts == [1, 1, 2, 2, 3, 4, 5, 5, 1], "act of each floor %s" % acts)
    bosses = {d: rift.plan(rift.level_id(d))["actboss"] for d in (9, 10, 20, 30, 40, 50)}
    check(bosses == {9: None, 10: "andariel", 20: "duriel", 30: "mephisto", 40: "diablo", 50: "baalcrab"},
          "act bosses %s" % bosses)
    places = {rift.plan(rift.level_id(d))["act"] for d in range(31, 41)}
    check(places == {4}, "floors 31-40 are all Act 4 places: %s" % places)
    rift.BIG = False
    rift.forget(None)


def test_death_and_potions():
    """A wiped run starts again from floor 1; belts are filled; potions are drunk."""
    config.apply_d2_rules()
    random.seed(21)
    mgr = RunManager(_NoAssets(), _cfg())
    h = _hero("Fragile", "sor")
    h.rift_depth = 4
    r = mgr.start([h])
    check(r.depth == 5, "a run starts after the deepest floor cleared (%d)" % r.depth)
    _tick(mgr)                                   # starts building the floor (fills the belt)
    check(len(h.belt) > 0, "the belt is filled before the floor: %d potions" % len(h.belt))
    drunk = 0
    belt_before = len(h.belt)
    for _ in range(25 * 60 * 3):
        _tick(mgr)
        if r.sim is not None and len(h.belt) < belt_before:
            drunk += belt_before - len(h.belt)
        belt_before = len(h.belt)
        if getattr(r, "deaths", 0) >= 1 and r.state in ("pause", "build", "fight") and r.depth == 1:
            break
    check(drunk > 0, "potions drunk in the fight: %d" % drunk)
    check(r.deaths >= 1 and r.depth == 1 and h.rift_depth == 0 and r.state != "over",
          "after dying the run goes on from floor 1 (deaths %d, depth %d, state %s)" % (r.deaths, r.depth, r.state))
    from autobattler import brain
    check(brain.profile(h).get("best", 0) >= 4, "his best floor is kept: %s" % brain.profile(h).get("best"))


def test_roster():
    from game import save as gsave
    old = (roster.SAVE_DIR, gsave.SAVE_DIR, gsave.NORMAL_DIR)
    with tempfile.TemporaryDirectory() as tmp:
        roster.SAVE_DIR = os.path.join(tmp, "saves_auto")
        roster.use_folder()
        for i in range(3):
            roster.create("bar", "Tester", None, max_heroes=3)
        check(roster.count() == 3, "three heroes made, names kept apart")
        check(roster.create("bar", "One more", None, max_heroes=3) is None, "the roster cap holds")
        check(os.path.isdir(roster.SAVE_DIR), "heroes go to saves_auto")
    roster.SAVE_DIR, gsave.SAVE_DIR, gsave.NORMAL_DIR = old


def test_big_maps():
    from game import rift

    class _MK:
        rw = rh = 8

    class _Kit:
        mazes = {"cave": _MK()}
    rift.BIG = False
    small = rift._fit(_Kit(), "cave", 6, False)
    rift.BIG = True
    big = rift._fit(_Kit(), "cave", 12, False)
    rift.BIG = False
    check(big["grid"] ** 2 >= 2 * small["grid"] ** 2 and big["rooms"] >= 2 * small["rooms"] - 2,
          "big floors: grid %d -> %d, rooms %d -> %d" % (small["grid"], big["grid"], small["rooms"], big["rooms"]))


def test_gear():
    """The inventory screen's item handling (autobattler/gear.py)."""
    from autobattler import gear
    from game.items import Item
    p = roster.create("bar", "Gear", None, max_heroes=99)
    check(p.INV_H == 8 and p.INV_W == 10, "backpack is 10 x 8, twice D2's 10 x 4")
    loaded = roster.load(next(d for d in roster.list_heroes() if d.get("name") == p.name), None)
    check(loaded.INV_H == 8, "the double backpack stays after loading")
    b = gear.Bench(p)
    for it in list(p.inventory):
        p.inventory.remove(it)
    for s in list(p.equipment):
        p.equipment[s] = None
    helm = Item("Cap", "cap", "helm", defense=5)
    helm2 = Item("Skull Cap", "skp", "helm", defense=9)
    ring = Item("Ring", "rin", "ring")
    check(p.inv_add(helm) and p.inv_add(helm2) and p.inv_add(ring), "items go in")
    low = Item("Stone", "sto", "helm")
    low.inv_pos = (0, 7)
    p.inventory.append(low)
    check(p.inv_at(0, 7) is low, "the eighth row holds items")
    p.inventory.remove(low)
    check(b.right_click(helm) and p.equipment["helm"] is helm, "right click wears an item")
    x, y = helm2.inv_pos
    check(b.click_cell(x, y) and b.held is helm2, "click picks an item up")
    check(b.click_slot("helm") and p.equipment["helm"] is helm2 and b.held is helm,
          "click on the slot wears it and the old one comes onto the cursor")
    check(not b.click_slot("boots") and b.held is helm, "a helm does not go on the feet")
    check(b.click_cell(5, 6) and b.held is None and helm.inv_pos == (5, 6), "it goes down where clicked")
    check(b.click_cell(ring.inv_pos[0], ring.inv_pos[1]) and b.click_slot("ring2") and
          p.equipment["ring2"] is ring, "rings go in either ring slot")
    check(b.unequip("ring2") and ring in p.inventory, "right click on a worn item takes it off")
    unid = Item("Hat", "hat", "helm")
    unid.identified = False
    scroll = Item("Scroll of Identify", "isc", None, kind="misc")
    scroll.use = "id"
    p.inv_add(unid)
    p.inv_add(scroll)
    check(b.unidentified() == 1, "one item to identify")
    check(b.right_click(scroll) and b.cursor_mode, "right click on the scroll picks a target")
    check(b.click_cell(*unid.inv_pos) and unid.identified and scroll not in p.inventory,
          "the scroll identifies the item and is used up")
    unid.identified = False
    check(b.identify_all() == 1 and unid.identified, "identify all")
    gold = p.gold
    check(b.right_click(helm, sell=True) and p.gold > gold and helm not in p.inventory, "ctrl + right click sells")
    b.click_cell(*ring.inv_pos)
    b.drop_held()
    check(b.floor() == [ring], "items can be put on the floor")
    b.take_from_floor(ring)
    check(b.finish() == 0 and ring in p.inventory and ring.inv_pos is not None,
          "closing the screen puts the cursor item back in the backpack")
    b.swap_weapons()
    check(getattr(p, "weapon_set", 0) == 1, "weapon swap")
    roster.delete(p.name)


def test_inventory_screen():
    """The screen draws and takes clicks (placeholder art)."""
    import autobattler_main as am
    import pygame
    app = am.App.__new__(am.App)
    pygame.init()
    from autobattler.ui import Look
    from autobattler.runs import RunManager
    serif = "serif"
    fonts = {k: pygame.font.SysFont(serif, 14) for k in ("small", "med", "big", "title")}
    app.sysfonts = fonts
    app.canvas = pygame.Surface((800, 600))
    app.window = pygame.display.set_mode((800, 600))
    app.look = Look(None, fonts)
    app.content = None
    app.cfg = config.load()
    app.mgr = RunManager(None, app.cfg, timing.Timings(None))
    p = roster.create("sor", "Screen", None, max_heroes=99)
    from game.items import Item
    p.inv_add(Item("Cap", "cap", "helm", defense=5))
    app.heroes = {p.name: p}
    app.selected = [p.name]
    app.screen_name = "inventory"
    app.bench, app.regions, app.message, app._tip, app.mouse, app.down = None, [], "", None, (0, 0), None
    app.show_perf, app._dt = False, 0.0
    app.perf = am.Perf()
    app.views = {}
    app.focus = None
    app.loot_page = 0
    app.search, app.filter = "", "All"
    app.draw_inventory()
    first = next((it for it in p.inventory if it.inv_pos), None)
    slots, gx, gy, ic = app._inv_geometry()
    check(first is not None, "the screen shows the backpack")
    if first is not None:
        x, y = first.inv_pos
        app.mouse = (app.INV_X + gx + x * ic + 3, app.INV_Y + gy + y * ic + 3)
        app.inv_click()
        check(app.bench.held is first, "clicking the panel's backpack picks the item up")
        app.regions = []
        app.draw_inventory()
        app.mouse = (app.INV_X + gx + 9 * ic + 3, app.INV_Y + gy + 7 * ic + 3)
        app.inv_click()
        check(app.bench.held is None and first.inv_pos[1] + p._size(first)[1] == 8,
              "and puts it down in the bottom row")
    app.go("roster")
    check(app.bench is None, "leaving the screen closes the bench")
    roster.delete(p.name)


if __name__ == "__main__":
    _tmp = tempfile.TemporaryDirectory()        # nothing a test makes lands among your real heroes
    roster.SAVE_DIR = os.path.join(_tmp.name, "saves_auto")
    roster.use_folder()
    test_timing()
    test_big_maps()
    test_roster()
    test_runs()
    test_floor_progress()
    test_cast_breakpoints()
    test_brain()
    test_acts()
    test_death_and_potions()
    test_gear()
    test_points_by_hand()
    test_town_stash()
    test_no_essences()
    test_smart_ai()
    test_town_and_back()
    test_belt_columns()
    test_full_bag_trip()
    test_d2_difficulty()
    test_summons_once()
    test_act_levels()
    test_charm_inventory()
    test_skill_animations()
    test_farms()
    test_d2_quality()
    test_summons_fight()
    test_ready_skeletons()
    test_line_of_fire()
    test_runeword_bases()
    test_rare_cores()
    test_horadric_cube()
    test_socketing()
    test_boss_gate_and_difficulty()
    test_inventory_screen()
    print("\n%s" % ("all passed" if not FAILS else "%d FAILED" % len(FAILS)))
    sys.exit(1 if FAILS else 0)
