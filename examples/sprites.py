"""Example sprites, drawn as text so they live in git as source rather than
binary PNGs. One character per pixel; see PALETTE.

Colors are chosen for LEDs: saturated, nothing near-black except pure black
(which means "off"), so everything survives the brightness cap and gamma.
"""

PALETTE = {
    ".": (0, 0, 0),
    "S": (200, 208, 220),  # steel
    "s": (127, 142, 163),  # steel shadow
    "W": (255, 255, 255),
    "R": (255, 42, 58),    # plume
    "r": (176, 16, 31),
    "G": (255, 194, 26),   # gold
    "V": (48, 224, 255),   # visor glow
    "B": (31, 191, 159),   # shield
    "L": (192, 106, 40),   # leather
    "Y": (245, 197, 66),   # smiley
    "E": (40, 40, 110),    # smiley eyes (deep blue, still visible on LEDs)
    "M": (230, 57, 70),    # smiley mouth
}

_KNIGHT = [
    "......RR.....W..",
    ".....RRr.....S..",
    ".....Rr......S..",
    "....SSSSs....S..",
    "...SWSSSSs...S..",
    "...SVsVsss...S..",
    "...SSSSSSs..GGG.",
    "....sSSSs...sSs.",
    ".BBBBSSSSSSSSs..",
    "BBGBBSSSSSs.....",
    "BGGGBSSSSSs.....",
    "BBGBBGGGGGG.....",
    ".BBB.sSSSSs.....",
    ".B...sS..Ss.....",
    ".....LL..LL.....",
    "....LLL..LLL....",
]


def knight_frames():
    """4-frame idle: a glint runs down the blade, the plume sways, a blink."""
    frames = []
    for i in range(4):
        g = [list(r) for r in _KNIGHT]
        g[i + 1][13] = "W"
        if i >= 2:
            g[0][:13] = list(".......RR....")
            g[1][:13] = list("......RRr....")
            g[2][:13] = list("......Rr.....")
        if i == 3:
            g[5][4] = g[5][6] = "s"
        frames.append(["".join(r) for r in g])
    return frames


_SMILEY = [
    "................",
    ".....YYYYYY.....",
    "...YYYYYYYYYY...",
    "..YYYYYYYYYYYY..",
    "..YYYYYYYYYYYY..",
    ".YYYYEYYYYEYYYY.",
    ".YYYYEYYYYEYYYY.",
    ".YYYYYYYYYYYYYY.",
    ".YYYYYYYYYYYYYY.",
    ".YYYMYYYYYYMYYY.",
    ".YYYYMYYYYMYYYY.",
    "..YYYYMMMMYYYY..",
    "..YYYYYYYYYYYY..",
    "...YYYYYYYYYY...",
    ".....YYYYYY.....",
    "................",
]


def smiley_frames():
    """3 open-eye frames then a blink."""
    blink = [list(r) for r in _SMILEY]
    for x in (5, 10):
        blink[5][x] = "Y"
        blink[6][x - 1] = blink[6][x] = blink[6][x + 1] = "E"
    return [_SMILEY] * 3 + [["".join(r) for r in blink]]


def to_image(frames):
    """Render frames side by side as a sprite sheet (a single frame is a still)."""
    from PIL import Image
    h, w = len(frames[0]), len(frames[0][0])
    img = Image.new("RGB", (w * len(frames), h))
    for k, f in enumerate(frames):
        assert len(f) == h and all(len(r) == w for r in f), "ragged sprite"
        for y, row in enumerate(f):
            for x, c in enumerate(row):
                img.putpixel((k * w + x, y), PALETTE[c])
    return img
