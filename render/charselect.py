"""D2's character select screen: your heroes in two columns of four, standing in their gear.

Click a hero to select it, double click / OK / Enter to play. Create New Character opens the
creation screen, Delete Character asks first (deleted heroes are moved to saves\\deleted, so a
mistake can still be undone by moving the file back).
"""
import pygame

from .charcreate import FrontEnd, NAMES, FE, GOLD, WHITE, GREY

CS = "data\\global\\ui\\CharSelect\\"


def _log(text):
    try:
        import os
        import time
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "errors.log"), "a") as f:
            f.write("---- %s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), text.rstrip()))
    except Exception:
        pass
GREEN = (24, 255, 0)
SLOT_W, SLOT_H = 272, 93
COLS_X = (37, 309)
ROW_Y = (86, 181, 276, 371)
PER_PAGE = 8


class CharSelect(FrontEnd):
    PALETTES = ("sky", "fechar", "units", "act1")

    def __init__(self, game):
        self._setup(game)
        self.bg = self._tiled([CS + "characterselectscreenEXP.dc6", CS + "characterselectscreen.dc6",
                               FE + "charactercreationscreenEXP.dc6"])
        self.fallback_bg = self.bg is not None and not self.src.has(CS + "characterselectscreenEXP.dc6") \
            and not self.src.has(CS + "characterselectscreen.dc6")
        box = self._frames(CS + "charselectbox.dc6", pal=self.unit_palette)
        self.selbox = box[0][0] if box and box[0][0] is not None else None
        up = self.unit_palette
        self.medium = self._frames(FE + "mediumbuttonblank.dc6", pal=up)
        self.wide = self._strip(self._frames(FE + "widebuttonblank.dc6", pal=up), (0, 1))
        self.popup = self._strip(self._frames(FE + "popup_340x224.dc6", pal=up), (0, 1))
        small = self._frames(FE + "okcancelbuttonblank.dc6", pal=up)
        self.small = small[0][0] if small and small[0][0] is not None else None
        self.heroes = []
        self.players = {}
        self.selected = 0
        self.scroll = 0
        self.confirm_delete = False
        self._last_click = (-1, 0.0)
        self.reload()

    # ------------------------------------------------------------ data
    def reload(self):
        from game.save import list_saves
        try:
            self.heroes = list_saves()
        except Exception:
            self.heroes = []
        self.heroes.sort(key=lambda d: d.get("name", "").lower())
        self.selected = min(self.selected, max(0, len(self.heroes) - 1))
        self.players = {}

    def _player(self, d):
        """The hero as a game unit, for its standing animation in its own gear."""
        key = d.get("name")
        if key not in self.players:
            p = None
            try:
                from game.save import build_player
                p = build_player(d, self.assets.content)
                p.facing = (1, 1)
            except Exception:
                import traceback
                _log("character select: could not load %s\n%s" % (key, traceback.format_exc()))
                p = None
            self.players[key] = p
        return self.players[key]

    # ------------------------------------------------------------ layout
    def _to_logical(self, pos):
        lx, ly = FrontEnd._to_logical(self, pos)
        return int(lx), int(ly)

    def slot_rect(self, i):
        j = i - self.scroll
        if not 0 <= j < PER_PAGE:
            return None
        return pygame.Rect(COLS_X[j % 2], ROW_Y[j // 2], SLOT_W, SLOT_H)

    def create_rect(self):
        return pygame.Rect(33, 468, 272, 35)

    def delete_rect(self):
        return pygame.Rect(433, 468, 272, 35)

    def exit_rect(self):
        return pygame.Rect(33, 537, 128, 35)

    def ok_rect(self):
        return pygame.Rect(627, 537, 128, 35)

    def popup_rect(self):
        return pygame.Rect(230, 190, 340, 224)

    def yes_rect(self):
        return pygame.Rect(304, 368, 96, 32)      # side by side over the popup's button well

    def no_rect(self):
        return pygame.Rect(400, 368, 96, 32)

    # ------------------------------------------------------------ actions
    def play(self):
        if not self.heroes:
            return
        d = self.heroes[self.selected]
        self.game.start_act(d.get("cls", "bar"), d.get("name", "Hero"), saved=d)

    def create(self):
        self.game.open_frontend(select=False)

    def delete(self):
        if not self.heroes:
            return
        from game.save import delete_character
        delete_character(self.heroes[self.selected].get("name", ""))
        self.confirm_delete = False
        self.reload()
        if not self.heroes:
            self.create()

    def _keep_visible(self):
        if self.selected < self.scroll:
            self.scroll = self.selected - self.selected % 2
        elif self.selected >= self.scroll + PER_PAGE:
            self.scroll = self.selected - self.selected % 2 - (PER_PAGE - 2)
        self.scroll = max(0, self.scroll)

    # ------------------------------------------------------------ input
    def handle(self, ev):
        if self.confirm_delete:
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                lp = self._to_logical(ev.pos)
                if self.yes_rect().collidepoint(lp):
                    self.delete()
                elif self.no_rect().collidepoint(lp):
                    self.confirm_delete = False
            elif ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_y):
                    self.delete()
                elif ev.key in (pygame.K_ESCAPE, pygame.K_n):
                    self.confirm_delete = False
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            lp = self._to_logical(ev.pos)
            if self.ok_rect().collidepoint(lp):
                self.play()
            elif self.exit_rect().collidepoint(lp):
                self.game.running = False
            elif self.create_rect().collidepoint(lp):
                self.create()
            elif self.delete_rect().collidepoint(lp) and self.heroes:
                self.confirm_delete = True
            else:
                for i in range(len(self.heroes)):
                    r = self.slot_rect(i)
                    if r is not None and r.collidepoint(lp):
                        last_i, last_t = self._last_click
                        self.selected = i
                        if last_i == i and self.t - last_t < 0.45:
                            self.play()        # double click
                            return
                        self._last_click = (i, self.t)
                        break
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (4, 5):
            self._scroll(-2 if ev.button == 4 else 2)
        elif ev.type == getattr(pygame, "MOUSEWHEEL", -1):
            self._scroll(-2 * getattr(ev, "y", 0))
        elif ev.type == pygame.KEYDOWN:
            n = len(self.heroes)
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.play()
            elif ev.key == pygame.K_ESCAPE:
                self.game.running = False
            elif ev.key == pygame.K_DELETE and n:
                self.confirm_delete = True
            elif n and ev.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                step = {pygame.K_LEFT: -1, pygame.K_RIGHT: 1, pygame.K_UP: -2, pygame.K_DOWN: 2}[ev.key]
                self.selected = max(0, min(n - 1, self.selected + step))
                self._keep_visible()

    def _scroll(self, d):
        top = max(0, len(self.heroes) - PER_PAGE + (len(self.heroes) % 2))
        self.scroll = max(0, min(top, self.scroll + d))

    # ------------------------------------------------------------ drawing
    def update(self, dt):
        self.t += dt

    def _strip(self, frames, idx):
        """Join DC6 frames that D2 stores side by side (wide buttons, popups) into one image."""
        if not frames:
            return None
        parts = [frames[i][0] for i in idx if i < len(frames) and frames[i][0] is not None]
        if not parts:
            return None
        w = sum(p.get_width() for p in parts)
        h = max(p.get_height() for p in parts)
        out = pygame.Surface((w, h), pygame.SRCALPHA)
        out.fill((0, 0, 0, 0))
        x = 0
        for p in parts:
            out.blit(p, (x, 0))
            x += p.get_width()
        return out

    def _wide_button(self, canvas, rect, label, enabled=True):
        if self.wide is not None:
            canvas.blit(self.wide, rect.topleft)
        else:
            pygame.draw.rect(canvas, (40, 34, 26), rect)
            pygame.draw.rect(canvas, (120, 110, 80), rect, 1)
        self._text(canvas, self.f16, label, WHITE if enabled else GREY, rect.centerx, rect.y + 10, center=True)

    def draw(self, screen):
        canvas = pygame.Surface((800, 600))
        canvas.fill((0, 0, 0))
        if self.bg is not None:
            canvas.blit(self.bg, (0, 0))
            if self.fallback_bg:
                shade = pygame.Surface((800, 600), pygame.SRCALPHA)
                shade.fill((0, 0, 0, 170))
                canvas.blit(shade, (0, 0))
        lp = self._to_logical(pygame.mouse.get_pos())
        # name of the selected hero at the top, like D2
        if self.heroes:
            title = self.heroes[self.selected].get("name", "")
            self._text(canvas, self.f42 or self.f30, title, GOLD, 400, 18, center=True)
        else:
            self._text(canvas, self.f30, "No heroes yet", GOLD, 400, 24, center=True)
        for i, d in enumerate(self.heroes):
            r = self.slot_rect(i)
            if r is None:
                continue
            if self.fallback_bg or self.bg is None:
                pygame.draw.rect(canvas, (70, 62, 44), r, 1)
            if i == self.selected:
                if self.selbox is not None:
                    canvas.blit(self.selbox, r.topleft)
                else:
                    pygame.draw.rect(canvas, GOLD, r, 2)
            p = self._player(d)
            feet = (r.x + 46, r.y + 84)
            drawn = False
            if p is not None and hasattr(self.assets, "draw_unit"):
                try:
                    drawn = self.assets.draw_unit(canvas, p, {"mode": "NU", "phase": self.t, "facing": (1, 1),
                                                              "flash": 0}, feet, 1.0, 1.0) is not None
                except Exception:
                    if not getattr(self, "_draw_err_logged", False):
                        self._draw_err_logged = True
                        import traceback
                        _log("character select: drawing a hero failed\n" + traceback.format_exc())
                    drawn = False
            if not drawn:
                pygame.draw.ellipse(canvas, (60, 50, 30), pygame.Rect(feet[0] - 16, feet[1] - 6, 32, 10))
            cls = NAMES.get(d.get("cls"), "?")
            self._text(canvas, self.f16, d.get("name", "?"), GOLD, r.x + 96, r.y + 22)
            self._text(canvas, self.f16, "Level %d %s" % (d.get("level", 1), cls), WHITE, r.x + 96, r.y + 40)
            self._text(canvas, self.f16, "Expansion Character", GREEN, r.x + 96, r.y + 58)
        if len(self.heroes) > PER_PAGE:
            pages = "%d-%d of %d (mouse wheel / arrows)" % (self.scroll + 1, min(len(self.heroes), self.scroll + PER_PAGE),
                                                           len(self.heroes))
            self._text(canvas, self.f16, pages, GREY, 400, 448, center=True)
        self._wide_button(canvas, self.create_rect(), "CREATE NEW CHARACTER")
        self._wide_button(canvas, self.delete_rect(), "DELETE CHARACTER", bool(self.heroes))
        self._button(canvas, self.medium, self.exit_rect(), "EXIT")
        self._button(canvas, self.medium, self.ok_rect(), "OK", bool(self.heroes))
        if self.confirm_delete and self.heroes:
            shade = pygame.Surface((800, 600), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 120))
            canvas.blit(shade, (0, 0))
            pr = self.popup_rect()
            if self.popup is not None:
                canvas.blit(self.popup, pr.topleft)
            else:
                pygame.draw.rect(canvas, (20, 18, 14), pr)
                pygame.draw.rect(canvas, (120, 110, 80), pr, 1)
            name = self.heroes[self.selected].get("name", "")
            lines = ["Are you sure that you want", "to delete %s?" % name, "(moved to saves\\deleted)"]
            for j, line in enumerate(lines):
                self._text(canvas, self.f16, line, GOLD if j < 2 else GREY, 400, pr.y + 50 + j * 24, center=True)
            for rect, label in ((self.yes_rect(), "YES"), (self.no_rect(), "NO")):
                if self.small is not None:
                    canvas.blit(self.small, rect.topleft)
                else:
                    pygame.draw.rect(canvas, (40, 34, 26), rect)
                    pygame.draw.rect(canvas, (120, 110, 80), rect, 1)
                hot = rect.collidepoint(lp)
                self._text(canvas, self.f16, label, WHITE if hot else (230, 220, 190), rect.centerx, rect.y + 9, center=True)
        self._present(screen, canvas)
