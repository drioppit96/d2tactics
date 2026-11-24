"""How long things take in real time, by Diablo II's own frame rules.

D2 runs at 25 frames a second. An animation has a number of frames per direction and an
animation speed (256 = one animation frame per game frame). Attack speed, cast rate and hit
recovery speed the animation up, with diminishing returns on the item bonus:

    effective bonus = floor(k * bonus / (k + bonus))      k = 120 (IAS, FCR, FHR), 150 (FRW)

    attack:        frames = ceil(256 * FPD / floor(speed * (100 + EIAS) / 100)) - 1
                   EIAS = effective IAS - weapon speed modifier + skill IAS, between -85 and 75
    cast:          the same with effective FCR in place of EIAS (at most 75)
    hit recovery:  the same with 50 + effective FHR

FPD and speed are read from the unit's COF file in your own install (the frame count and the
animation rate in its header). When a file can't be read, FALLBACK_FPD is used instead.
"""
import math

FPS = 25

# A hero's hit recovery is not timed by his get-hit animation's frame count but by a class base:
# these are D2's hit recovery frames at 0% FHR (one-handed / most weapons). With the formula
# above, base = (frames + 1) / 2 reproduces the published breakpoints (Barbarian 0% 9 frames,
# 7% 8, 15% 7, 27% 6, 48% 5, 86% 4, 200% 3).
HERO_GH_FRAMES = {"ama": 11, "ass": 9, "bar": 9, "dru": 14, "nec": 13, "pal": 9, "sor": 15}

# frames per direction used when the COF can't be read (no install, an unusual weapon class)
FALLBACK_FPD = {"A1": 15, "A2": 15, "SC": 14, "GH": 8, "S1": 14, "TH": 15, "KK": 13}
MONSTER_FALLBACK_FPD = {"A1": 12, "A2": 12, "SC": 12, "GH": 6, "S1": 12}


def effective(bonus, k=120):
    """Diminishing returns on an item bonus (IAS, FCR, FHR: k=120; FRW: k=150)."""
    bonus = int(bonus or 0)
    if bonus <= 0:
        return bonus
    return (k * bonus) // (k + bonus)


def _frames(fpd, speed, pct):
    step = int(speed * pct / 100.0)
    if step <= 0:
        return int(fpd) * 8
    return max(1, int(math.ceil(256.0 * fpd / step)) - 1)


def eias(ias=0, wsm=0, skill_ias=0):
    return max(-85, min(75, effective(ias) - int(wsm or 0) + int(skill_ias or 0)))


def attack_frames(fpd, ias=0, wsm=0, skill_ias=0, speed=256):
    return _frames(fpd, speed, 100 + eias(ias, wsm, skill_ias))


def cast_frames(fpd, fcr=0, speed=256):
    return _frames(fpd, speed, 100 + min(75, effective(fcr)))


def hit_recovery_frames(fpd, fhr=0, speed=256):
    return _frames(fpd, speed, 50 + effective(fhr))


def move_speed(velocity, frw=0, scale=1.0):
    """Cells a second: D2's velocity (CharStats walk/run, MonStats Velocity/Run) times `scale`,
    raised by Faster Run/Walk (k = 150)."""
    return max(0.1, float(velocity) * scale * (100 + effective(frw, 150)) / 100.0)


class Timings:
    """Reads (frames per direction, animation rate) from COF files, once per animation."""

    def __init__(self, src=None):
        self.src = src
        self._cache = {}

    def anim(self, folder, token, mode, wclass="HTH"):
        """folder: "chars" or "monsters". Returns (fpd, speed) or None."""
        key = (folder, token, mode, wclass)
        if key in self._cache:
            return self._cache[key]
        out = None
        if self.src is not None and token:
            t = token.upper()
            name = "data\\global\\%s\\%s\\cof\\%s%s%s.cof" % (folder, t, t, mode, wclass.upper())
            try:
                if self.src.has(name):
                    from d2.cof import COF
                    c = COF(self.src.read(name))
                    out = (max(1, int(c.frames)), int(c.anim_rate) or 256)
            except Exception:
                out = None
        self._cache[key] = out
        return out

    def fpd(self, unit, mode):
        """Frames per direction and speed for this unit's animation `mode` (A1, SC, GH ...)."""
        if getattr(unit, "is_player", False) and mode == "GH":
            f0 = HERO_GH_FRAMES.get(getattr(unit, "cls", ""), 9)
            return ((f0 + 1) / 2.0, 256)
        if getattr(unit, "is_player", False):
            got = self.anim("chars", unit.token, mode, weapon_class(unit))
            if got is None and weapon_class(unit) != "HTH":
                got = self.anim("chars", unit.token, mode, "HTH")
            return got or (FALLBACK_FPD.get(mode, 14), 256)
        got = self.anim("monsters", getattr(unit, "token", ""), mode, "HTH")
        return got or (MONSTER_FALLBACK_FPD.get(mode, 12), 256)


# D2 weapon classes by item type (Weapons.txt "wclass"); the engine's items carry the code
_WCLASS_BY_TYPE = {
    "axe": "1HS", "swor": "1HS", "mace": "1HS", "club": "1HS", "hamm": "1HS", "scep": "1HS",
    "wand": "1HS", "knif": "1HS", "tkni": "1HT", "taxe": "1HT", "jave": "1HT", "spea": "2HT",
    "pole": "STF", "staf": "STF", "bow": "BOW", "xbow": "XBW", "h2h": "HT1", "h2h2": "HT1",
    "orb": "1HS", "abow": "BOW", "aspe": "2HT", "ajav": "1HT",
}


def weapon_class(unit):
    """The animation set the hero uses with his weapon (HTH when unarmed)."""
    eq = getattr(unit, "equipment", None) or {}
    w = eq.get("rhand") or eq.get("weapon")
    if w is None:
        return "HTH"
    wc = getattr(w, "wclass", None)
    if wc:
        return str(wc).upper()
    t = str(getattr(w, "type", "") or getattr(w, "itype", "") or "").lower()
    if getattr(w, "two_handed", False) and t in ("swor", "axe"):
        return "2HS"
    return _WCLASS_BY_TYPE.get(t, "1HS")
