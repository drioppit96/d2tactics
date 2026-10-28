"""What D2's act bosses do besides fighting:

* Mephisto stays on his side of the moat: he won't chase you around the Durance, he casts instead
* the Chaos Sanctuary's five seals: opening them calls the Grand Vizier, Lord De Seis and the
  Infector of Souls; with all five open Diablo comes
* the Throne of Destruction: Baal sends five waves of minions before he flees to the Worldstone
* in the Worldstone Chamber Baal makes a clone of himself when he is hurt
* the Ancients sleep as statues until you touch the altar on Arreat Summit
(Nihlathak's corpse explosions, Diablo's lightning and the rest of the spells are game.monskills.)
"""
from .grid import chebyshev

SEAL_BOSS = {392: "Grand Vizier of Chaos", 394: "Lord De Seis", 396: "Infector of Souls"}
DEFERRED_108 = ("diablo", "Grand Vizier of Chaos", "Lord De Seis", "Infector of Souls")
WAVES = ["Baal Subject 1", "Baal Subject 2", "Baal Subject 3", "Baal Subject 4", "Baal Subject 5"]
GOLD = (199, 179, 119)
RED = (255, 90, 90)


def defer_preset(world, name, cell, owner):
    """Presets that only appear later (Diablo and the seal bosses). True = held back."""
    if owner == 108 and name in DEFERRED_108:
        world.deferred = getattr(world, "deferred", [])
        world.deferred.append((name, cell, owner))
        return True
    if name == "baalthrone":
        world.throne_cell = cell
        world.baal_wave = 0
        return True
    return False


def _spawn_deferred(world, name, near=None):
    lst = getattr(world, "deferred", [])
    cands = [d for d in lst if d[0] == name]
    if not cands:
        return False
    if near is not None:
        cands.sort(key=lambda d: chebyshev(d[1], near))
    d = cands[0]
    lst.remove(d)
    taken = world.occupied()
    world.deferred_off = True
    try:
        before = len(world.monsters)
        from . import actworld
        actworld._spawn_preset(world, d[0], d[1], d[2], set(taken), world.info)
        for m in world.monsters[before:]:
            m.aware = True
            world.emit("place", m, m.pos)
    finally:
        world.deferred_off = False
    return True


# ---------------------------------------------------------------- objects: seals and the altar
def operate(world, o):
    if o["kind"] == "seal":
        if o.get("open"):
            return False
        o["open"] = True
        o["used"] = True
        o["mode"] = "OP"
        o["op_t"] = None
        world.emit("object", o)
        n_open = sum(1 for x in world.objects if x.get("kind") == "seal" and x.get("open"))
        n_all = sum(1 for x in world.objects if x.get("kind") == "seal")
        world.log("You open a seal (%d of %d)." % (n_open, n_all), GOLD)
        boss = SEAL_BOSS.get(o["oid"])
        if boss and _spawn_deferred(world, boss, near=o["cell"]):
            world.log("%s appears to guard the seal!" % world.content.strings.get(boss, boss), RED)
        if n_open >= n_all and _spawn_deferred(world, "diablo"):
            world.log("Diablo: 'Not even death can save you from me!'", RED)
            world.emit("area", "Diablo")
        return True
    if o["kind"] == "altar":
        if o.get("used"):
            return False
        o["used"] = True
        o["mode"] = "OP"
        o["op_t"] = None
        world.emit("object", o)
        wake_ancients(world)
        return True
    return False


def wake_ancients(world):
    woke = False
    for m in world.monsters:
        if m.alive and getattr(m, "dormant", False):
            m.dormant = False
            m.invulnerable = False
            if "sight" in m.__dict__:
                del m.sight
            m.aware = True
            woke = True
    if woke:
        world.log("The Ancients rise: 'Prove yourself worthy!'", RED)
        if world.mode == "explore":
            world.check_awareness_force()


def make_dormant(m):
    m.dormant = True
    m.invulnerable = True
    m.aware = False
    m.sight = -1


# ---------------------------------------------------------------- per turn / per step
def on_player_move(world):
    """Checked as you walk: the Throne's waves, the Ancients waking without an altar."""
    p = world.player
    tc = getattr(world, "throne_cell", None)
    if tc is not None and getattr(world, "baal_wave", 5) < 5 and chebyshev(p.pos, tc) <= 24:
        alive = [m for m in world.monsters if m.alive and getattr(m, "wave", None) is not None]
        if not alive:
            _next_wave(world)
    if any(getattr(m, "dormant", False) for m in world.monsters) and \
            not any(o.get("kind") == "altar" for o in world.objects):
        for m in world.monsters:
            if getattr(m, "dormant", False) and chebyshev(m.pos, p.pos) <= 8:
                wake_ancients(world)
                break


def _next_wave(world):
    from . import actworld
    n = world.baal_wave
    if n >= len(WAVES):
        return
    name = WAVES[n]
    world.baal_wave = n + 1
    tc = world.throne_cell
    c = world.content
    shown = c.strings.get(name, name) if c is not None else name
    # they come out in front of the throne
    spot = actworld._free_near(world.grid, (tc[0] + 6, tc[1] + 6), 10) or tc
    before = len(world.monsters)
    lvl = world.info.monster_level(131) if getattr(world, "info", None) else 40
    actworld._spawn_preset(world, name, spot, 131, set(world.occupied()), world.info)
    for m in world.monsters[before:]:
        m.wave = n + 1
        m.aware = True
        m.level = max(m.level, lvl)
        world.emit("place", m, m.pos)
    world.log("Baal: 'Now you face %s!' (wave %d of 5)" % (shown, n + 1), RED)
    world.emit("area", "Wave %d" % (n + 1))
    if world.mode == "explore":
        world.check_awareness_force()


def waves_done(world):
    if getattr(world, "throne_cell", None) is None:
        return True
    return world.baal_wave >= 5 and not any(m.alive and getattr(m, "wave", None) for m in world.monsters)


def turn_pre(world, m):
    """Before a boss acts. True = its turn is over."""
    boss = getattr(m, "boss", None)
    p = world.player
    if getattr(m, "dormant", False):
        return True
    if boss == "mephisto":
        # D2: Mephisto keeps to his platform; across the moat he only casts
        if chebyshev(p.pos, m.home) > 14:
            from . import monskills
            if not monskills.try_cast(world, m):
                m.ap = 0
            return True
    if boss == "baal" and getattr(world, "level_key", None) == 132 and not getattr(m, "cloned", False) \
            and m.hp < m.max_hp // 2:
        m.cloned = True
        _clone(world, m)
    return False


def _clone(world, baal):
    from .actworld import _spawn, _spots
    spots = _spots(world, baal.pos, 1, world.occupied(), radius=4)
    if not spots or world.content is None or "baalclone" not in world.content.monstats:
        return
    k = _spawn(world, "baalclone", spots[0], baal.level, set(world.occupied()), unique=True, name=baal.name)
    if k is None:
        return
    k.max_hp = k.hp = max(1, baal.hp)
    k.aware = True
    world.emit("place", k, k.pos)
    world.log("Baal splits in two - one of them is an illusion!", RED)
