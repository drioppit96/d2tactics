"""The Codex: every runeword and every Horadric Cube recipe, with filters.

A page of the Esc menu. Nothing here is written by hand - the runewords come from the same
Runes.txt the game makes them with, and the recipes from the same CubeMain.txt the cube runs on,
so what the Codex says and what the game does cannot drift apart.

    RUNEWORDS       name, the runes in socket order, what it goes in, the level it needs, what
                    it gives, and whether the account holds the runes for it
    HORADRIC CUBE   D2's own description of each recipe, what goes in and what comes out

Filters are chips down the left: click to turn one on, click again to turn it off, and several
in a group are an "any of these". The search box takes typing.
"""
import pygame

GOLD = (199, 179, 119)
WHITE = (235, 235, 235)
GREY = (124, 120, 112)
DIM = (86, 82, 74)
BLUE = (108, 108, 255)
GREEN = (120, 200, 120)
DARKER = (58, 54, 46)

RAIL_W = 176
CARD_H = 170
MAX_PROPS = 5
ROW_H = 54

#: D2's item type codes, as a reader would name them
ITYPE = {"tors": "Body Armor", "helm": "Helm", "shld": "Shield", "weap": "Weapon",
         "swor": "Sword", "axe": "Axe", "staf": "Staff", "h2h": "Claw", "bow": "Bow",
         "mele": "Melee Weapon", "miss": "Missile Weapon", "pole": "Polearm", "club": "Club",
         "hamm": "Hammer", "mace": "Mace", "scep": "Scepter", "wand": "Wand", "knif": "Dagger",
         "spea": "Spear", "xbow": "Crossbow", "orb": "Orb", "ashd": "Auric Shield",
         "phlm": "Barbarian Helm", "pelt": "Druid Pelt", "head": "Shrunken Head"}

#: the groups the item-group filter offers, and which type codes each one covers
GROUPS = [("Body Armor", {"tors"}), ("Helm", {"helm", "phlm", "pelt"}), ("Shield", {"shld", "ashd", "head"}),
          ("Weapon", {"weap"}), ("Sword", {"swor"}), ("Axe", {"axe"}), ("Mace", {"mace", "club", "hamm", "scep"}),
          ("Staff", {"staf", "orb", "wand"}), ("Claw", {"h2h"}), ("Polearm", {"pole", "spea"}),
          ("Bow", {"bow", "xbow", "miss"}), ("Melee", {"mele"})]

#: what a cube recipe makes, by the first letters of its output code
MAKES = [("Runes", lambda code: code.startswith("r") and code[1:].isdigit()),
         ("Gems", lambda code: code[:3] in ("gcv", "gcw", "gcg", "gcr", "gcb", "gcy", "gsv", "gsw",
                                            "gsg", "gsr", "gsb", "gsy", "gzv", "gzw", "glg", "glr",
                                            "glb", "gly", "gpv", "gpw", "gpg", "gpr", "gpb", "gpy",
                                            "skc", "sku", "skl", "skz", "skr")),
         ("Rings", lambda code: code == "rin"), ("Amulets", lambda code: code == "amu"),
         ("Potions", lambda code: code in ("rvs", "rvl") or code.endswith("pot")),
         ("Portals", lambda code: "portal" in code.lower()),
         ("Quest", lambda code: code in ("hst", "qf2", "msf", "vip")),
         ("An item", lambda code: code in ("usetype", "useitem"))]


class Codex:
    def __init__(self, game):
        self.game = game
        self.hud = game.hud
        self.tab = "runewords"
        self.scroll = 0.0
        self.search = ""
        self.typing = False
        self.on = set()              # which filter chips are lit, as "group:label"
        self.sort = "level"
        self.rects = []              # [(pygame.Rect, action, arg)]
        self._rw = None
        self._rec = None

    # ------------------------------------------------------------ the data
    def runewords(self):
        if self._rw is None:
            c = self.game.world.content
            out = []
            for r in (getattr(c.sockets, "runewords", None) or []):
                lvl = 0
                for code in r["runes"]:
                    b = (c.base_by_code or {}).get(code) or {}
                    lvl = max(lvl, int(b.get("levelreq") or b.get("qlvl") or 0))
                out.append(dict(r, lvl=lvl, sockets=len(r["runes"])))
            out.sort(key=lambda r: (r["lvl"], r["name"]))
            self._rw = out
        return self._rw

    def recipes(self):
        if self._rec is None:
            from game import cube
            self._rec = list(cube.recipes(self.game.world.content))
        return self._rec

    def rune_name(self, code):
        b = (self.game.world.content.base_by_code or {}).get(code) or {}
        return (b.get("name") or code).replace(" Rune", "")

    def code_name(self, code):
        """An item code or an item type, named the way a reader would name it.

        A recipe's input is often a whole type ("hpot", "gem2") rather than one item, and those
        names live in ItemTypes.txt, which is where D2 keeps them.
        """
        b = (self.game.world.content.base_by_code or {}).get(code) or {}
        if b.get("name"):
            return b["name"]
        return self._types().get(code.lower(), code)

    def _types(self):
        c = self.game.world.content
        got = getattr(c, "_codex_itypes", None)
        if got is None:
            got = {}
            try:
                from d2.source import read_table
                for r in read_table(c.src, "ItemTypes"):
                    code = (r.get("code") or "").strip().lower()
                    name = (r.get("itemtype") or "").strip()
                    if code and name and name != "None":
                        got[code] = name
            except Exception:
                got = {}
            try:
                c._codex_itypes = got
            except Exception:
                pass
        return got

    def held(self, code):
        """How many of an item code the hero and the shared chest hold between them."""
        p = self.game.world.player
        n = 0
        for it in (p.inventory or []):
            if getattr(it, "code", None) == code:
                n += max(1, int(getattr(it, "quantity", 1) or 1))
        st = getattr(p, "stash", None)
        if st is not None:
            n += int((getattr(st, "bank", None) or {}).get(code, 0))
            for page in (getattr(st, "pages", None) or []):
                for it in page:
                    if getattr(it, "code", None) == code:
                        n += max(1, int(getattr(it, "quantity", 1) or 1))
        return n

    def missing_runes(self, r):
        """How many of the runeword's runes the account has not got."""
        need = {}
        for code in r["runes"]:
            need[code] = need.get(code, 0) + 1
        return sum(max(0, n - self.held(code)) for code, n in need.items())

    # ------------------------------------------------------------ filtering
    def _lit(self, group):
        return {k.split(":", 1)[1] for k in self.on if k.startswith(group + ":")}

    def filtered_runewords(self):
        groups = self._lit("group")
        socks = self._lit("sock")
        bands = self._lit("level")
        make = self._lit("make")
        q = self.search.lower().strip()
        out = []
        for r in self.runewords():
            if groups:
                covered = set()
                for name, codes in GROUPS:
                    if name in groups:
                        covered |= codes
                if not (r["itypes"] & covered):
                    continue
            if socks and str(r["sockets"]) not in socks:
                continue
            if bands:
                lo_hi = {"1-25": (0, 25), "26-50": (26, 50), "51+": (51, 99)}
                if not any(lo_hi[b][0] <= r["lvl"] <= lo_hi[b][1] for b in bands if b in lo_hi):
                    continue
            if make:
                short = self.missing_runes(r)
                if "can make now" in make and short:
                    continue
                if "one rune short" in make and short != 1:
                    continue
            if q:
                hay = " ".join([r["name"]] + [self.rune_name(c) for c in r["runes"]]
                               + self._lines(r)).lower()
                if q not in hay:
                    continue
            out.append(r)
        if self.sort == "name":
            out = sorted(out, key=lambda r: r["name"])
        return out

    def filtered_recipes(self):
        makes = self._lit("makes")
        q = self.search.lower().strip()
        out = []
        for r in self.recipes():
            code = r.output.code
            if makes:
                hit = False
                for name, test in MAKES:
                    if name in makes:
                        try:
                            hit = hit or test(code)
                        except Exception:
                            pass
                if not hit:
                    continue
            if q and q not in (r.desc + " " + code + " " +
                               " ".join(self.code_name(s.code) for s in r.inputs)).lower():
                continue
            out.append(r)
        return out

    def _lines(self, r):
        """What the runeword actually says, in the game's own words.

        The properties are put on a throwaway item and read back through the same code that
        writes an item's tooltip, so the Codex and the item in your hands cannot word the same
        property two different ways. Reading the table directly loses the parameter, which is
        what turns "+2 to Amazon Skill Levels" into "ama 2".
        """
        cache = self.__dict__.setdefault("_line_cache", {})
        key = r["name"]
        if key not in cache:
            out = []
            try:
                from game.items import Item
                from game import props as P
                it = Item(r["name"], "rwx", None, kind="equip")
                it.mod_list, it.mods = [], {}
                P.apply(it, list(r["props"]), roll=False)
                for line in it.describe_lines(self.game.world.player):
                    txt, col = line[0], line[1]
                    if txt and txt != r["name"]:
                        out.append(txt)
            except Exception:
                out = []
            cache[key] = out
        return cache[key]

    # ------------------------------------------------------------ input
    def update(self, dt):
        pass

    def key(self, key, unicode=""):
        if key == pygame.K_ESCAPE:
            if self.typing:
                self.typing = False
            else:
                return False               # the menu takes it: back to the main page
            return True
        if self.typing:
            if key == pygame.K_BACKSPACE:
                self.search = self.search[:-1]
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
                self.typing = False
            elif unicode and unicode.isprintable() and len(self.search) < 28:
                self.search += unicode
            self.scroll = 0.0
            return True
        if key in (pygame.K_DOWN, pygame.K_s):
            self.scroll += 40
        elif key in (pygame.K_UP, pygame.K_w):
            self.scroll = max(0.0, self.scroll - 40)
        elif key == pygame.K_PAGEDOWN:
            self.scroll += 320
        elif key == pygame.K_PAGEUP:
            self.scroll = max(0.0, self.scroll - 320)
        elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_TAB):
            self.tab = "cube" if self.tab == "runewords" else "runewords"
            self.scroll = 0.0
        return True

    def wheel(self, dy):
        self.scroll = max(0.0, self.scroll - dy * 60)

    def click(self, pos, button=1):
        lx, ly = self.hud.logical(pos)
        for r, action, arg in self.rects:
            if r.collidepoint((lx, ly)):
                self._do(action, arg)
                return True
        self.typing = False
        return True

    def _do(self, action, arg):
        if action == "tab":
            self.tab, self.scroll = arg, 0.0
        elif action == "chip":
            self.on.symmetric_difference_update({arg})
            self.scroll = 0.0
        elif action == "sort":
            self.sort = arg
        elif action == "search":
            self.typing = True
        elif action == "reset":
            self.on.clear()
            self.search = ""
            self.scroll = 0.0

    # ------------------------------------------------------------ drawing
    def _box(self, surf, x, y, w, h, fill=(18, 17, 15, 240), border=(70, 64, 52)):
        b = pygame.Surface(self.hud.P(w, h), pygame.SRCALPHA)
        b.fill(fill)
        surf.blit(b, self.hud.P(x, y))
        if border:
            pygame.draw.rect(surf, border, self.hud.R(x, y, w, h), 1)

    def _t(self, surf, txt, col, x, y, font=None, align="left", box=None):
        self.hud.text(surf, font or self.hud.f10, txt, col, x, y, align, box)

    def _fit(self, txt, font, px):
        """Trim text until it actually fits, measured rather than guessed at so many pixels
        a letter: D2's fonts are not fixed width and the guess was always wrong somewhere."""
        if px <= 0:
            return ""
        try:
            while txt and font.render(txt, WHITE, self.hud.ind).get_width() / max(0.01, self.hud.s) > px:
                txt = txt[:-1]
        except Exception:
            pass
        return txt

    def _hit(self, x, y, w, h, action, arg=None):
        self.rects.append((pygame.Rect(int(x), int(y), int(w), int(h)), action, arg))

    def draw(self, surf, mouse):
        hud = self.hud
        W, H = hud.lw, 600
        self.rects = []
        bg = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        bg.fill((8, 7, 6, 246))
        surf.blit(bg, (0, 0))
        self._t(surf, "CODEX", GOLD, 0, 14, hud.f30, "center", W)

        rw_n, rec_n = len(self.runewords()), len(self.recipes())
        tw = 250
        tx = W / 2 - tw - 2
        for key, label, n in (("runewords", "RUNEWORDS", rw_n), ("cube", "HORADRIC CUBE", rec_n)):
            on = self.tab == key
            self._box(surf, tx, 48, tw, 26, (34, 31, 26, 255) if on else (16, 15, 14, 255),
                      GOLD if on else DIM)
            self._t(surf, "%s  (%d)" % (label, n), WHITE if on else GREY, tx, 53, hud.f16, "center", tw)
            self._hit(tx, 48, tw, 26, "tab", key)
            tx += tw + 4

        self._rail(surf, W, H)
        if self.tab == "runewords":
            self._runewords(surf, W, H)
        else:
            self._cube(surf, W, H)
        self._t(surf, "Esc to go back     wheel or arrows to scroll", GREY, 14, H - 20)

    def _chips(self, surf, title, group, labels, y, cols=2, w=156, x0=24):
        self._t(surf, title, GOLD, x0, y)
        y += 14
        cw = w // cols
        for i, lab in enumerate(labels):
            gx, gy = x0 + (i % cols) * cw, y + (i // cols) * 18
            key = "%s:%s" % (group, lab)
            lit = key in self.on
            self._box(surf, gx, gy, cw - 4, 15, (40, 36, 28, 255) if lit else (10, 10, 10, 255),
                      GOLD if lit else DARKER)
            self._t(surf, lab, WHITE if lit else GREY, gx + 4, gy + 2)
            self._hit(gx, gy, cw - 4, 15, "chip", key)
        return y + ((len(labels) + cols - 1) // cols) * 18 + 10

    def _rail(self, surf, W, H):
        hud = self.hud
        self._box(surf, 14, 86, RAIL_W, H - 110)
        self._t(surf, "SEARCH", GOLD, 24, 94)
        self._box(surf, 24, 108, 156, 20, (6, 6, 6, 255), GOLD if self.typing else (96, 88, 70))
        hint = self.search or ("|" if self.typing else
                               ("rune, name or stat..." if self.tab == "runewords"
                                else "what goes in, or comes out"))
        self._t(surf, hint[:26], WHITE if self.search else DIM, 30, 113)
        self._hit(24, 108, 156, 20, "search")
        y = 140
        if self.tab == "runewords":
            y = self._chips(surf, "ITEM GROUP", "group", [n for n, _ in GROUPS], y)
            y = self._chips(surf, "SOCKETS", "sock", ["2", "3", "4", "5", "6"], y, 3)
            y = self._chips(surf, "REQUIRED LEVEL", "level", ["1-25", "26-50", "51+"], y, 3)
            y = self._chips(surf, "RUNES I HAVE", "make", ["can make now", "one rune short"], y, 1)
            self._t(surf, "SORT", GOLD, 24, y)
            y += 14
            for i, lab in enumerate(("by level", "by name")):
                gx = 24 + i * 78
                lit = self.sort == lab.split()[-1]
                self._box(surf, gx, y, 74, 15, (40, 36, 28, 255) if lit else (10, 10, 10, 255),
                          GOLD if lit else DARKER)
                self._t(surf, lab, WHITE if lit else GREY, gx + 4, y + 2)
                self._hit(gx, y, 74, 15, "sort", lab.split()[-1])
            y += 26
        else:
            y = self._chips(surf, "WHAT IT MAKES", "makes", [n for n, _ in MAKES], y)
        self._box(surf, 24, y + 4, 156, 20, (28, 25, 20, 255), GOLD)
        self._t(surf, "RESET FILTERS", GOLD, 24, y + 9, hud.f16, "center", 156)
        self._hit(24, y + 4, 156, 20, "reset")

    def _clip(self, surf, W, H):
        """The scrolling area, so a card half off the bottom is cut rather than drawn over."""
        return self.hud.R(RAIL_W + 26, 86, W - RAIL_W - 42, H - 112)

    def _runewords(self, surf, W, H):
        hud = self.hud
        rows = self.filtered_runewords()
        self._t(surf, "showing %d of %d" % (len(rows), len(self.runewords())), GREY,
                RAIL_W + 26, 54, hud.f10, "right", W - RAIL_W - 42)
        area = self._clip(surf, W, H)
        # two columns where there is room for them, and the cards share out whatever width the
        # window has rather than being a fixed size that may not fit twice
        avail = W - RAIL_W - 42
        cols = 2 if avail >= 480 else 1
        cw = int((avail - 8 * (cols - 1)) // cols)
        pages = (len(rows) + cols - 1) // cols
        self.scroll = max(0.0, min(self.scroll, max(0, pages * (CARD_H + 8) - (H - 112))))
        old = surf.get_clip()
        surf.set_clip(area)
        x0, y0 = RAIL_W + 26, 86 - self.scroll
        for i, r in enumerate(rows):
            x = x0 + (i % cols) * (cw + 8)
            y = y0 + (i // cols) * (CARD_H + 8)
            if y > 600 or y + CARD_H < 70:
                continue
            self._card(surf, r, x, y, cw)
        surf.set_clip(old)

    def _card(self, surf, r, x, y, CARD_W):
        hud = self.hud
        self._box(surf, x, y, CARD_W, CARD_H)
        self._t(surf, r["name"], GOLD, x, y + 6, hud.f16, "center", CARD_W)
        runes = r["runes"]
        rw = min(44, (CARD_W - 24) // max(1, len(runes)))
        for j, code in enumerate(runes):
            rx = x + (CARD_W - rw * len(runes)) / 2.0 + j * rw
            have = self.held(code) > 0
            self._box(surf, rx, y + 26, rw - 3, 18, (30, 26, 18, 255) if have else (14, 12, 10, 255),
                      (120, 98, 58) if have else (60, 54, 44))
            self._t(surf, self.rune_name(code), (226, 184, 74) if have else DIM,
                    rx, y + 30, hud.f10, "center", rw - 3)
        groups = sorted({ITYPE.get(t, t) for t in r["itypes"]})
        self._t(surf, "%d socket  %s" % (r["sockets"], ", ".join(groups[:2])[:22]), WHITE, x + 10, y + 50)
        self._t(surf, "Req level %d" % r["lvl"], GREY, x, y + 50, hud.f10, "right", CARD_W - 10)
        pygame.draw.line(surf, (54, 50, 42), hud.P(x + 8, y + 66), hud.P(x + CARD_W - 8, y + 66))
        lines = self._lines(r)
        shown = 0
        for txt in lines[:MAX_PROPS]:
            self._t(surf, self._fit(txt, hud.f10, CARD_W - 12), BLUE, x, y + 72 + shown * 13,
                    hud.f10, "center", CARD_W)
            shown += 1
        more = len(lines) - shown
        if more > 0:
            self._t(surf, "and %d more" % more, DIM, x, y + 72 + shown * 13, hud.f10, "center", CARD_W)
        short = self.missing_runes(r)
        self._t(surf, "you have every rune" if not short else
                ("one rune short" if short == 1 else "%d runes short" % short),
                GREEN if not short else DIM, x, y + CARD_H - 15, hud.f10, "center", CARD_W)

    def _cube(self, surf, W, H):
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
            self._t(surf, self._fit(r.desc, hud.f16, w - 24), WHITE, x + 12, y + 7, hud.f16)
            ins = " + ".join("%s%s" % ("%d " % s.qty if s.qty > 1 else "", self.code_name(s.code))
                             for s in r.inputs)
            out = "makes %s" % self.code_name(r.output.code)
            try:
                ow = out and hud.f10.render(out, GOLD, hud.ind).get_width() / max(0.01, hud.s)
            except Exception:
                ow = 120
            self._t(surf, self._fit(ins, hud.f10, w - 36 - ow), GREY, x + 12, y + 30)
            self._t(surf, out, GOLD, x, y + 29, hud.f10, "right", w - 12)
        surf.set_clip(old)
