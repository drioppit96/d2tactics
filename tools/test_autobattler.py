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


def test_skill_bar():
    """The 8-slot skill bar: buffs first, then the slots in order; skills not on it unused."""
    from autobattler import brain, points
    config.apply_d2_rules()
    random.seed(5)
    h = _hero("Barred")
    h.level = 12
    h.skills.points = 10
    for n in ("Bash", "Howl", "Shout", "Double Swing"):
        points.learn(h, n)
    h.base_eng = 200
    h.recalc()
    h.mana = h.max_mana
    brain.profile(h)["slots"] = ["Double Swing", "Shout", "", "", "", "", "", ""]
    mgr = RunManager(_NoAssets(), _cfg())
    r = mgr.start([h])
    used = {}
    for _ in range(25 * 60):
        _tick(mgr)
        if r.sim is not None:
            for k, v in r.sim.casts.items():
                used[k] = max(used.get(k, 0), v)
        if r.state == "over":
            break
    check(used.get("Shout", 0) >= 1 and used.get("Double Swing", 0) >= 1, "the bar's skills are used: %s" % used)
    check(not used.get("Bash") and not used.get("Howl"), "skills not on the bar are not used")
    # Attack ahead of the skills: he swings instead of casting Double Swing (buffs still first)
    brain.profile(h)["slots"] = ["Shout", "attack", "Double Swing", "", "", "", "", ""]
    r.finish("stopped")
    h.mana = h.max_mana
    r = mgr.start([h])
    used = {}
    for _ in range(25 * 30):
        _tick(mgr)
        if r.sim is not None:
            for k, v in r.sim.casts.items():
                used[k] = max(used.get(k, 0), v)
    check(not used.get("Double Swing") and used.get("Shout", 0) >= 1,
          "Attack in an earlier slot comes before the skills after it: %s" % used)
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
    r.finish("stopped")


def test_belt_columns():
    """Healing potions in belt columns 1-2, mana in 3-4; picked up while there is a place."""
    from autobattler import brain
    from game import potions
    from game.items import Item
    config.apply_d2_rules()
    h = _hero("Belted")

    def pot(kind, code):
        it = Item(kind, code, None, kind="potion")
        it.potion = kind
        return it
    for _ in range(3):
        potions.belt_add(h, pot("heal", "hp1"))
        potions.belt_add(h, pot("mana", "mp1"))
    cols = {c: [x.potion for x in potions.column(h, c)] for c in range(4)}
    check(all(k == "heal" for c in (0, 1) for k in cols[c]) and all(k == "mana" for c in (2, 3) for k in cols[c])
          and sum(len(v) for v in cols.values()) == min(6, 4 * potions.belt_rows(h)),
          "healing in columns 1-2, mana in 3-4: %s" % cols)
    brain.pickup_rules(h)["potions"] = False
    full = potions._free_column(h, pot("heal", "hp1")) is None
    check(brain.wants(h, pot("mana", "mp1")) == (potions._free_column(h, pot("mana", "mp1")) is not None)
          and (not brain.wants(h, pot("heal", "hp1")) if full else True),
          "potions are picked up while the belt has a place for them")
    potions.COLUMN_RULE = None


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
    test_skill_bar()
    test_town_and_back()
    test_belt_columns()
    test_inventory_screen()
    print("\n%s" % ("all passed" if not FAILS else "%d FAILED" % len(FAILS)))
    sys.exit(1 if FAILS else 0)
