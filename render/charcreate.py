"""D2's character creation screen: the seven heroes around the campfire.

Art comes from data\\global\\ui\\FrontEnd (background, campfire and each class's idle /
walk-forward / selected / walk-back animations). Click a hero to step them forward, type a
name, press OK (or Enter).
"""
import pygame

from d2.dc6 import DC6
from d2.palette import load_palette

FE = "data\\global\\ui\\FrontEnd\\"
# class code, folder, file prefix, position in D2's 800x600 screen (feet of the hero)
HEROES = [
    ("ama", "amazon", "am", (100, 339)),
    ("ass", "assassin", "as", (231, 365)),
    ("nec", "necromancer", "ne", (300, 335)),
    ("bar", "barbarian", "ba", (400, 330)),
    ("pal", "paladin", "pa", (521, 338)),
    ("sor", "sorceress", "so", (626, 352)),
    ("dru", "druid", "dz", (720, 370)),
]
NAMES = {"ama": "Amazon", "ass": "Assassin", "nec": "Necromancer", "bar": "Barbarian", "pal": "Paladin",
         "sor": "Sorceress", "dru": "Druid"}
BLURB = {
    "ama": "Skilled with the spear and the bow, she is a very versatile fighter.",
    "ass": "Schooled in the Martial Arts, her mind and body are deadly weapons.",
    "nec": "Summoning undead minions and cursing his enemies are his specialties.",
    "bar": "He is unequaled in close-quarters combat and mastery of weapons.",
    "pal": "He is a natural party leader, holy man, and blessed warrior.",
    "sor": "She has mastered the elemental magicks - fire, lightning, and ice.",
    "dru": "Commanding the forces of nature, he summons wild beasts and raging storms to his side.",
}
GOLD = (199, 179, 119)
WHITE = (255, 255, 255)
GREY = (160, 160, 160)


class Anim:
    def __init__(self, frames, fps=20):
        self.frames = frames          # [(surface, xoff, yoff)]
        self.fps = fps

    def frame(self, t, loop=True):
        if not self.frames:
            return None
        i = int(t * self.fps)
        i = i % len(self.frames) if loop else min(len(self.frames) - 1, i)
        return self.frames[i]

    def duration(self):
        return len(self.frames) / float(self.fps) if self.frames else 0.0


class CharCreate:
    def __init__(self, game):
        self.game = game
        self.assets = game.assets
        self.src = self.assets.src
        self.palette = None
        for p in ("data\\global\\palette\\fechar\\pal.dat", "data\\global\\palette\\sky\\pal.dat",
                  "data\\global\\palette\\units\\pal.dat", "data\\global\\palette\\act1\\pal.dat"):
            if self.src.has(p):
                try:
                    self.palette = load_palette(self.src.read(p))
                    break
                except Exception:
                    pass
        self.unit_palette = self.palette
        for p in ("data\\global\\palette\\units\\pal.dat", "data\\global\\palette\\act1\\pal.dat"):
            if self.src.has(p):
                self.unit_palette = load_palette(self.src.read(p))
                break
        self.bg = self._background()
        self.fire = self._anim(FE + "fire.dc6", pal=self.unit_palette)
        self.anims = {}
        for code, folder, pre, pos in HEROES:
            base = FE + folder + "\\" + pre
            a = {k: self._anim(base + suffix + ".dc6", pal=self.unit_palette)
                 for k, suffix in (("idle", "nu1"), ("hover", "nu2"), ("forward", "fw"), ("selected", "nu3"),
                                   ("back", "bw"))}
            a["forward_fx"] = self._anim(base + "fws.dc6", pal=self.unit_palette)
            a["selected_fx"] = self._anim(base + "nu3s.dc6", pal=self.unit_palette)
            a["back_fx"] = self._anim(base + "bws.dc6", pal=self.unit_palette)
            self.anims[code] = a
        self.state = {c: ("idle", 0.0) for c, _, _, _ in HEROES}
        try:
            from game.save import list_saves
            self.saves = list_saves()[:8]
        except Exception:
            self.saves = []
        self.selected = None
        self.hover = None
        self.name = ""
        self.t = 0.0
        self.buttons = self._frames(FE + "mediumbuttonblank.dc6") or self._frames("data\\global\\ui\\PANEL\\mediumbuttonblank.dc6")
        hud = getattr(game, "hud", None)
        self.f30 = getattr(hud, "f30", None)
        self.f16 = getattr(hud, "f16", None)
        self.f10 = getattr(hud, "f10", None)

    # ------------------------------------------------------------ loading
    def _frames(self, path, pal=None):
        if not self.src.has(path):
            return None
        try:
            dc = DC6(self.src.read(path))
        except Exception:
            return None
        pal = pal or self.palette
        out = []
        for f in dc.frames:
            if not f.width or not f.height:
                out.append((None, 0, 0))
                continue
            s = pygame.image.frombuffer(bytes(f.pixels), (f.width, f.height), "P")
            s.set_palette(pal)
            s.set_colorkey(0)
            img = pygame.Surface((f.width, f.height), pygame.SRCALPHA)
            img.fill((0, 0, 0, 0))
            img.blit(s, (0, 0))
            out.append((img, f.xoff, f.yoff))
        return out

    def _anim(self, path, pal=None):
        fr = self._frames(path, pal)
        return Anim(fr) if fr else None

    def _background(self):
        for name in ("charactercreationscreenEXP.dc6", "charactercreate.dc6", "CharacterCreate.dc6"):
            fr = self._frames(FE + name)
            if fr:
                bg = pygame.Surface((800, 600))
                bg.fill((0, 0, 0))
                x = y = row_h = 0
                for img, _, _ in fr:
                    if img is None:
                        continue
                    if x >= 800:
                        x = 0
                        y += row_h
                        row_h = 0
                    bg.blit(img, (x, y))
                    x += img.get_width()
                    row_h = max(row_h, img.get_height())
                return bg
        return None

    # ------------------------------------------------------------ layout helpers
    def _scale(self):
        W, H = self.game.screen.get_size()
        k = min(W / 800.0, H / 600.0)
        return k, (W - 800 * k) / 2, (H - 600 * k) / 2

    def _to_logical(self, pos):
        k, ox, oy = self._scale()
        return (pos[0] - ox) / k, (pos[1] - oy) / k

    def _hero_rect(self, code, pos):
        a = self.anims.get(code, {})
        an = a.get("idle")
        fr = an.frame(0) if an else None
        if fr and fr[0] is not None:
            img, xo, yo = fr
            return pygame.Rect(pos[0] + xo, pos[1] + yo - img.get_height(), img.get_width(), img.get_height())
        return pygame.Rect(pos[0] - 30, pos[1] - 110, 60, 110)

    def save_rect(self, i):
        return pygame.Rect(14, 120 + i * 30, 250, 26)

    def ok_rect(self):
        return pygame.Rect(627, 552, 128, 35)

    def exit_rect(self):
        return pygame.Rect(33, 552, 128, 35)

    # ------------------------------------------------------------ input
    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            lx, ly = self._to_logical(ev.pos)
            if self.ok_rect().collidepoint((lx, ly)):
                self.confirm()
                return
            if self.exit_rect().collidepoint((lx, ly)):
                self.game.running = False
                return
            for i, d in enumerate(self.saves):
                if self.save_rect(i).collidepoint((lx, ly)):
                    self.game.start_act(d.get("cls", "bar"), d.get("name", "Hero"), saved=d)
                    return
            for code, _, _, pos in sorted(HEROES, key=lambda h: -h[3][1]):
                if self._hero_rect(code, pos).collidepoint((lx, ly)):
                    self.select(code)
                    return
        elif ev.type == pygame.MOUSEMOTION:
            lx, ly = self._to_logical(ev.pos)
            self.hover = None
            for code, _, _, pos in sorted(HEROES, key=lambda h: -h[3][1]):
                if self._hero_rect(code, pos).collidepoint((lx, ly)):
                    self.hover = code
                    break
        elif ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.confirm()
            elif ev.key == pygame.K_ESCAPE:
                if self.selected:
                    self.select(None)
                else:
                    self.game.running = False
            elif ev.key == pygame.K_BACKSPACE:
                self.name = self.name[:-1]
            else:
                ch = getattr(ev, "unicode", "")
                if ch and (ch.isalpha() or ch in "-_") and len(self.name) < 15:
                    self.name += ch

    def select(self, code):
        if code == self.selected:
            return
        if self.selected:
            self.state[self.selected] = ("back", 0.0)
        self.selected = code
        if code:
            self.state[code] = ("forward", 0.0)

    def confirm(self):
        if not self.selected:
            return
        name = self.name.strip() or NAMES[self.selected]
        self.game.start_act(self.selected, name[:1].upper() + name[1:])

    # ------------------------------------------------------------ drawing
    def update(self, dt):
        self.t += dt
        for code in list(self.state):
            mode, t = self.state[code]
            t += dt
            a = self.anims.get(code, {})
            an = a.get(mode)
            if mode == "forward" and (an is None or t >= an.duration()):
                mode, t = "selected", 0.0
            elif mode == "back" and (an is None or t >= an.duration()):
                mode, t = "idle", 0.0
            self.state[code] = (mode, t)

    def draw(self, screen):
        k, ox, oy = self._scale()
        canvas = pygame.Surface((800, 600))
        canvas.fill((0, 0, 0))
        if self.bg is not None:
            canvas.blit(self.bg, (0, 0))
        if self.fire:
            fr = self.fire.frame(self.t)
            if fr and fr[0] is not None:
                canvas.blit(fr[0], (380 + fr[1], 335 + fr[2] - fr[0].get_height()))
        for code, _, _, pos in sorted(HEROES, key=lambda h: h[3][1]):
            mode, t = self.state[code]
            a = self.anims.get(code, {})
            show = mode
            if mode == "idle" and self.hover == code and a.get("hover"):
                show = "hover"
            an = a.get(show) or a.get("idle")
            drawn = False
            if an:
                fr = an.frame(t, loop=show in ("idle", "hover", "selected"))
                if fr and fr[0] is not None:
                    img, xo, yo = fr
                    canvas.blit(img, (pos[0] + xo, pos[1] + yo - img.get_height()))
                    drawn = True
                fx = a.get(show + "_fx")
                if fx:
                    f2 = fx.frame(t, loop=show == "selected")
                    if f2 and f2[0] is not None:
                        canvas.blit(f2[0], (pos[0] + f2[1], pos[1] + f2[2] - f2[0].get_height()),
                                    special_flags=pygame.BLEND_RGB_ADD)
            if not drawn:
                r = self._hero_rect(code, pos)
                pygame.draw.rect(canvas, GOLD if code == self.selected else (90, 80, 60), r, 1)
                self._text(canvas, self.f16, NAMES[code], WHITE, r.centerx, r.centery, center=True)
        # class name and description at the top
        show = self.selected or self.hover
        if show:
            self._text(canvas, self.f30, NAMES[show], WHITE, 400, 24, center=True)
            self._text(canvas, self.f16, BLURB[show], GOLD, 400, 64, center=True)
        else:
            self._text(canvas, self.f30, "Select Hero Class", WHITE, 400, 24, center=True)
        # saved heroes (click to continue)
        if self.saves:
            self._text(canvas, self.f16, "Continue:", GOLD, 18, 96)
            lx, ly = self._to_logical(pygame.mouse.get_pos())
            for i, d in enumerate(self.saves):
                r = self.save_rect(i)
                bg = pygame.Surface(r.size, pygame.SRCALPHA)
                bg.fill((70, 56, 30, 210) if r.collidepoint((lx, ly)) else (0, 0, 0, 170))
                canvas.blit(bg, r.topleft)
                pygame.draw.rect(canvas, (120, 110, 80), r, 1)
                label = "%s - level %d %s" % (d.get("name", "?"), d.get("level", 1), NAMES.get(d.get("cls"), "?"))
                self._text(canvas, self.f16, label, WHITE, r.x + 6, r.y + 5)
        # name box, OK / EXIT
        if self.selected:
            self._text(canvas, self.f16, "Character Name", GOLD, 400, 488, center=True)
            box = pygame.Rect(318, 508, 164, 26)
            pygame.draw.rect(canvas, (0, 0, 0), box)
            pygame.draw.rect(canvas, (120, 110, 80), box, 1)
            cursor = "_" if int(self.t * 2) % 2 == 0 else ""
            self._text(canvas, self.f16, self.name + cursor, WHITE, box.x + 6, box.y + 5)
        for rect, label in ((self.exit_rect(), "EXIT"), (self.ok_rect(), "OK")):
            if self.buttons and self.buttons[0][0] is not None:
                canvas.blit(self.buttons[0][0], rect.topleft)
            else:
                pygame.draw.rect(canvas, (40, 34, 26), rect)
                pygame.draw.rect(canvas, (120, 110, 80), rect, 1)
            col = WHITE if label == "EXIT" or self.selected else GREY
            self._text(canvas, self.f16, label, col, rect.centerx, rect.y + 10, center=True)
        img = pygame.transform.smoothscale(canvas, (int(800 * k), int(600 * k))) if abs(k - 1) > 0.01 else canvas
        screen.fill((0, 0, 0))
        screen.blit(img, (int(ox), int(oy)))
        hud = getattr(self.game, "hud", None)
        if hud is not None and getattr(hud, "cursor", None):
            mx, my = pygame.mouse.get_pos()
            cur = hud.cursor[0]
            if cur is not None:
                screen.blit(pygame.transform.smoothscale(cur, (int(cur.get_width() * k), int(cur.get_height() * k))), (mx, my))

    def _text(self, surf, font, text, color, x, y, center=False):
        if font is None:
            f = self.game.fonts["med"]
            img = f.render(text, True, color)
        else:
            img = font.render(text, color, self.assets.indexed_surface)
        if center:
            x -= img.get_width() / 2
        surf.blit(img, (int(x), int(y)))
