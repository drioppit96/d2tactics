"""Builds Act VI's waypoint tab (assets/ui/tab_act6_*.png).

Diablo's own tab art (expwaygatetabs.dc6) stops at Act V, so the sixth tab is cut from the real
V and I: the numeral zone of the V tab is covered with plain stone from the same tab, and the two
glyphs are put back side by side, keeping their cap height and baseline. Run it from the repo
root with the game's data available; it only needs rerunning if the tabs are redesigned.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
Y0, Y1 = 5, 27                    # the stone inside the tab's frame
V_GLYPH = (22, 39)                # where the V sits on its tab
I_GLYPH = (26, 33)                # where the I sits on its tab
GAP = 3


def make_vi(v_tab, i_tab, Image):
    out = v_tab.copy()
    src = v_tab.crop((8, Y0, 21, Y1))           # plain stone, left of the numeral
    for n, x in enumerate(range(14, 54, 13)):
        p = src if n % 2 == 0 else src.transpose(Image.FLIP_LEFT_RIGHT)
        out.paste(p.crop((0, 0, min(13, 54 - x), Y1 - Y0)), (x, Y0))
    vw = V_GLYPH[1] - V_GLYPH[0] + 1
    iw = I_GLYPH[1] - I_GLYPH[0] + 1
    x = (63 - (vw + GAP + iw)) // 2             # the pair, centred on the tab
    out.paste(v_tab.crop((V_GLYPH[0] - 1, Y0, V_GLYPH[1] + 2, Y1)), (x - 1, Y0))
    out.paste(i_tab.crop((I_GLYPH[0] - 1, Y0, I_GLYPH[1] + 2, Y1)), (x + vw + GAP - 1, Y0))
    return out


def main():
    from PIL import Image
    import main as game                        # the game, for its asset loader
    g = game.Game(headless=True)
    fr = g.hud.frames["expwaygatetabs"]
    ims = [f.img.convert("RGBA") for f in fr]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(root, "assets", "ui")
    os.makedirs(out, exist_ok=True)
    for name, v, i in (("on", ims[8], ims[0]), ("off", ims[9], ims[1])):
        make_vi(v, i, Image).save(os.path.join(out, "tab_act6_%s.png" % name))
        print("wrote", os.path.join(out, "tab_act6_%s.png" % name))


if __name__ == "__main__":
    main()
