"""D2 Tactics' Codex (render/codex.py) in the D2 Autobattler: every runeword, with the same filters
and search, read from the same Runes.txt the game makes them with.

Two things differ here:
  - "Runes I have" counts the selected hero's backpack and the account's stash (the gems & runes
    tab and every item tab), not D2 Tactics' chest;
  - the Horadric Cube tab lists this game's own cube recipes (autobattler/recipes.py: what they
    take, what they make, their cost), not D2's CubeMain.txt ones, which the autobattler's cube
    doesn't run.
"""
import types

from render.codex import Codex, GOLD, WHITE, GREY, BLUE, GREEN, RAIL_W

ROW_H = 86


class AutoCodex(Codex):
    def __init__(self, hud, content, hero, stash=None):
        game = types.SimpleNamespace(hud=hud, world=types.SimpleNamespace(content=content, player=hero))
        Codex.__init__(self, game)
        self.stash = stash

    def set_hero(self, hero):
        self.game.world.player = hero

    # ------------------------------------------------------------ the data
    def held(self, code):
        """How many of an item code the hero carries and the account's stash holds."""
        p = self.game.world.player
        n = 0
        for it in (getattr(p, "inventory", None) or []):
            if getattr(it, "code", None) == code:
                n += max(1, int(getattr(it, "quantity", 1) or 1))
        st = self.stash
        if st is not None:
            n += int((getattr(st, "bank", None) or {}).get(code, 0))
            for key in ("pages", "uniques", "spares"):
                for page in (getattr(st, key, None) or []):
                    for it in page:
                        if getattr(it, "code", None) == code:
                            n += max(1, int(getattr(it, "quantity", 1) or 1))
        return n

    def recipes(self):
        from . import recipes
        return list(recipes.RECIPES)

    def filtered_recipes(self):
        q = self.search.lower().strip()
        out = []
        for r in self.recipes():
            if q and q not in (" ".join([r.name, r.cost_text()] + list(r.lines))).lower():
                continue
            out.append(r)
        return out

    # ------------------------------------------------------------ drawing (the cube tab)
    def _rail(self, surf, W, H):
        if self.tab == "runewords":
            return Codex._rail(self, surf, W, H)
        hud = self.hud
        self._box(surf, 14, 86, RAIL_W, H - 110)
        self._t(surf, "SEARCH", GOLD, 24, 94)
        self._box(surf, 24, 108, 156, 20, (6, 6, 6, 255), GOLD if self.typing else (96, 88, 70))
        hint = self.search or ("|" if self.typing else "name, cost or item")
        self._t(surf, hint[:26], WHITE if self.search else (86, 82, 74), 30, 113)
        self._hit(24, 108, 156, 20, "search")
        y = 140
        self._t(surf, "The cube here runs", GREY, 24, y)
        self._t(surf, "this game's own recipes,", GREY, 24, y + 13)
        self._t(surf, "paid in Rare Fragments", GREY, 24, y + 26)
        self._t(surf, "and Platinum.", GREY, 24, y + 39)
        y += 60
        self._box(surf, 24, y + 4, 156, 20, (28, 25, 20, 255), GOLD)
        self._t(surf, "RESET FILTERS", GOLD, 24, y + 9, hud.f16, "center", 156)
        self._hit(24, y + 4, 156, 20, "reset")

    def _cube(self, surf, W, H):
        from . import account
        hud = self.hud
        rows = self.filtered_recipes()
        self._t(surf, "showing %d of %d" % (len(rows), len(self.recipes())), GREY,
                RAIL_W + 26, 54, hud.f10, "right", W - RAIL_W - 42)
        area = self._clip(surf, W, H)
        self.scroll = max(0.0, min(self.scroll, max(0, len(rows) * (ROW_H + 4) - (H - 112))))
        old = surf.get_clip()
        surf.set_clip(area)
        x, w = RAIL_W + 26, W - RAIL_W - 42
        for i, r in enumerate(rows):
            y = 86 - self.scroll + i * (ROW_H + 4)
            if y > 600 or y + ROW_H < 70:
                continue
            self._box(surf, x, y, w, ROW_H)
            self._t(surf, r.name, GOLD, x + 12, y + 7, hud.f16)
            ok = account.can_pay(r.cost)
            self._t(surf, "Cost: %s" % r.cost_text(), GREEN if ok else BLUE, x, y + 9, hud.f10, "right", w - 12)
            for j, line in enumerate(r.lines[:4]):
                self._t(surf, self._fit(line, hud.f10, w - 24), WHITE, x + 12, y + 30 + j * 13)
        surf.set_clip(old)

    def click(self, pos, button=1):
        # (the autobattler's canvas is already in the HUD's own pixels)
        for r, action, arg in self.rects:
            if r.collidepoint((int(pos[0]), int(pos[1]))):
                self._do(action, arg)
                return True
        self.typing = False
        return True
