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
    # slime
    "G": (255, 194, 26),
    "N": (70, 235, 95),    # slime green
    "n": (28, 160, 62),    # slime shadow
    "E": (40, 90, 255),    # eye blue
    # ghost
    "C": (205, 232, 255),  # ghost body
    "c": (118, 168, 236),  # ghost shadow
    "P": (255, 90, 160),   # blush / nose pink
    # gem
    "M": (255, 60, 200),   # magenta
    "m": (160, 20, 140),
    "Y": (255, 236, 90),   # yellow / cream
    # cat
    "O": (255, 140, 30),   # orange
    "o": (196, 84, 12),
    "T": (255, 226, 170),  # cream
    "H": (60, 255, 130),   # eye green
    # fish
    "A": (40, 200, 255),   # aqua
    "a": (20, 120, 220),   # stripe blue
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


# ---- original example sprites (our own designs, not anyone's characters) ----

_SLIME = [
    "................",
    "................",
    "................",
    "................",
    ".....NNNNNN.....",
    "...NNNNNNNNNN...",
    "..NNWNNNNNNNNN..",
    "..NWNNNNNNNNNN..",
    ".NNNNEWNNNEWNNN.",
    ".NNNNEENNNEENNN.",
    ".NNNNNNNNNNNNNN.",
    ".NNNNNNNPPNNNNN.",
    ".nNNNNNNNNNNNNn.",
    "..nnNNNNNNNNnn..",
    "...nnnnnnnnnn...",
    "................",
]


def slime_frames():
    """3-frame idle: squash and stretch."""
    base = [list(r) for r in _SLIME]
    # squashed: wider and one row shorter
    sq = [
        "................",
        "................",
        "................",
        "................",
        "................",
        "....NNNNNNNN....",
        "..NNNWNNNNNNNN..",
        ".NNNWNNNNNNNNNN.",
        "NNNNNEWNNNEWNNNN",
        "NNNNNEENNNEENNNN",
        "NNNNNNNNNNNNNNNN",
        "NNNNNNNPPNNNNNNN",
        "nNNNNNNNNNNNNNNn",
        ".nnnnNNNNNNnnnn.",
        "..nnnnnnnnnnnn..",
        "................",
    ]
    tall = [
        "................",
        "................",
        "......NNNN......",
        "....NNNNNNNN....",
        "...NNWNNNNNNN...",
        "...NWNNNNNNNN...",
        "..NNNNNNNNNNNN..",
        "..NNNEWNNNEWNN..",
        "..NNNEENNNEENN..",
        "..NNNNNNNNNNNN..",
        "..NNNNNPPNNNNN..",
        "..nNNNNNNNNNNn..",
        "...nNNNNNNNNn...",
        "...nnnnnnnnnn...",
        "................",
        "................",
    ]
    return [["".join(r) for r in base], sq, ["".join(r) for r in base], tall]


_GHOST = [
    "................",
    "................",
    ".....CCCCCC.....",
    "...CCCCCCCCCC...",
    "..CCCCCCCCCCCC..",
    "..CCCCCCCCCCCC..",
    "..CCEECCCCEECC..",
    "..CCEWCCCCEWCC..",
    "..CCCCCCCCCCCC..",
    "..CCPPCCCCPPCC..",
    "..CCCCCCCCCCCC..",
    "..CCCCCCCCCCCC..",
    "..CCCCCCCCCCCC..",
    "..CCCCCCCCCCCC..",
    "..CC.CCCC.CC.CC.",
    "..C...CC...C..C.",
]


def ghost_frames():
    """4-frame float: bobs up and down while the hem ripples."""
    hems = [
        ("..CC.CCCC.CC.CC.", "..C...CC...C..C."),
        (".CC.CCCC.CC.CC..", ".C...CC...C..C.."),
        ("..CC.CCCC.CC.CC.", "..C...CC...C..C."),
        ("..C.CCCC.CC.CC..", "...C..CC...C.C.."),
    ]
    bob = [0, 0, 1, 1]
    frames = []
    for i in range(4):
        rows = list(_GHOST[:14]) + list(hems[i])
        if bob[i]:  # float up one row; the hem stays whole
            rows = rows[1:] + ["................"]
        frames.append(rows)
    return frames


_GEM = [
    "................",
    "................",
    "................",
    "....MMMMMMMM....",
    "...MYYMMMMMMM...",
    "..MYMMMMMMMMMM..",
    ".MMMMMMMMMMMMMM.",
    ".MMMMMMMMMMMMmM.",
    "..MMMMMMMMMMmm..",
    "...MMMMMMMMmm...",
    "....MMMMMMmm....",
    ".....MMMMmm.....",
    "......MMmm......",
    ".......mm.......",
    "................",
    "................",
]


def gem_frames():
    """4-frame sparkle: a white star blinks at a different corner each frame."""
    spots = [(2, 11), (6, 2), (2, 3), (9, 13)]
    frames = []
    for i, (y, x) in enumerate(spots):
        g = [list(r) for r in _GEM]
        g[y][x] = "W"
        if 0 < x < 15:
            for dx in (-1, 1):
                if g[y][x + dx] == ".":
                    g[y][x + dx] = "Y"
        if 0 < y < 15 and g[y + 1][x] == "." and i % 2 == 0:
            g[y + 1][x] = "Y"
        frames.append(["".join(r) for r in g])
    return frames


_CAT = [
    "................",
    "..O..........O..",
    "..OO........OO..",
    "..OOO......OOO..",
    "..OOOOOOOOOOOO..",
    "..OOOOOOOOOOOO..",
    "..OHHOOOOOHHOO..",
    "..OHEOOOOOHEOO..",
    "..OOOOOPPOOOOO..",
    "..OOTOOTTOOTOO..",
    "...OOTTTTTTOO...",
    "...OOOTTTTOOO...",
    "..OOOOTTTTOOOO..",
    "..OOOOOOOOOOOOo.",
    "..OOOOOOOOOOOoo.",
    "...ooo....ooo...",
]


def cat_frames():
    """4-frame idle: a blink, and the tail flicks."""
    frames = []
    for i in range(4):
        g = [list(r) for r in _CAT]
        if i == 2:  # blink
            g[6][3:5] = list("OO")
            g[6][10:12] = list("OO")
            g[7][3:5] = list("oo")
            g[7][10:12] = list("oo")
        # tail on the right side of the lower body
        tail = [(13, 14), (14, 14)]
        if i in (1, 2):
            g[13][14] = "o"
            g[12][14] = "o"
            g[14][14] = "O"
        frames.append(["".join(r) for r in g])
    return frames


_FOX = [
    "................",
    "..OO........OO..",
    "..OOO......OOO..",
    "..OoOO....OOoO..",
    "..OooOOOOOOooO..",
    "..OOOOOOOOOOOO..",
    "..OEOOOOOOOOEO..",
    "..WWOOOOOOOOWW..",
    "...WWWOOOOWWW...",
    "....WWWWWWWW....",
    ".....WWrrWW.....",
    "......WWWW......",
    "...OOOWWWWOOO...",
    "...OOOWWWWOOO...",
    "...OOOOOOOOOO...",
    "...ooo....ooo...",
]


def fox_frames():
    """4-frame idle: the bushy tail swishes (white tip) and the fox blinks."""
    tails = [
        [(10, 14, "W"), (11, 14, "O"), (12, 13, "O"), (12, 14, "O"),
         (13, 13, "O"), (13, 14, "O"), (14, 13, "O"), (14, 14, "O")],
        [(12, 15, "W"), (13, 15, "W"), (12, 13, "O"), (12, 14, "O"),
         (13, 13, "O"), (13, 14, "O"), (14, 13, "O"), (14, 14, "O")],
    ]
    frames = []
    for i in range(4):
        g = [list(r) for r in _FOX]
        if i == 2:  # blink
            g[6][3] = g[6][12] = "O"
        for y, x, c in tails[i % 2]:
            g[y][x] = c
        frames.append(["".join(r) for r in g])
    return frames


_FISH_BODY = [
    "...AAAAAA...",
    ".AAAAAAAAAA.",
    "AAWEAAAAAAAA",
    "AAAAAAAAAAAA",
    "AAaAAaAAaAAA",
    "AAAAAAAAAAAA",
    ".AAAAAAAAAA.",
    "...AAAAAA...",
]
_FISH_TAIL = ["...O", "..OO", ".OOO", "OOO.", "OOO.", ".OOO", "..OO", "...O"]


def fish_frames():
    """4-frame swim: the tail waves and a bubble rises in front."""
    frames = []
    for i, dy in enumerate([0, -1, 0, 1]):
        g = [list("." * 16) for _ in range(16)]
        for k, row in enumerate(_FISH_BODY):
            g[4 + k][0:12] = list(row)
        for k, row in enumerate(_FISH_TAIL):
            for j, c in enumerate(row):
                if c != ".":
                    g[4 + dy + k][12 + j] = c
        g[3][4:7] = list("OOO")   # top fin
        g[12][5:7] = list("OO")   # belly fin
        g[3 - i][1] = "W"         # bubble
        frames.append(["".join(r) for r in g])
    return frames


_POTION = [
    "................",
    "......LLLL......",
    "......LLLL......",
    ".....CCCCCC.....",
    "......CCCC......",
    "......CCCC......",
    ".....CCCCCC.....",
    "...CCMMMMMMCC...",
    "..CMMMMMMMMMMC..",
    "..WMMMMMMMMMMC..",
    "..WMMMMMMMMMMC..",
    "..CMMMMMMMMMMC..",
    "..CMMMMMMMMmmC..",
    "..CmmmmmmmmmmC..",
    "...CCmmmmmmCC...",
    "....CCCCCCCC....",
]


def potion_frames():
    """4-frame brew: two bubbles rise through the liquid."""
    frames = []
    for i in range(4):
        g = [list(r) for r in _POTION]
        g[13 - i][5] = "W"
        g[13 - (i + 2) % 4][9] = "W"
        frames.append(["".join(r) for r in g])
    return frames


_KEY = [
    "................",
    "......GGGG......",
    ".....GGooGG.....",
    ".....GG..GG.....",
    ".....GG..GG.....",
    ".....GGooGG.....",
    "......GGGG......",
    ".......GG.......",
    ".......Go.......",
    ".......GG.......",
    ".......Go.......",
    ".......GGGGG....",
    ".......GG.......",
    ".......GGGGG....",
    ".......Go.......",
    ".......GG.......",
]


def key_frames():
    """4-frame glint: a white spark travels along the key."""
    frames = []
    for y, x in [(2, 6), (5, 10), (9, 7), (13, 9)]:
        g = [list(r) for r in _KEY]
        g[y][x] = "W"
        frames.append(["".join(r) for r in g])
    return frames


_HEART = [
    "................",
    "................",
    "...RRRR..RRRR...",
    "..RRWRRRRRRRRR..",
    ".RRWRRRRRRRRRRR.",
    ".RRRRRRRRRRRRRR.",
    ".RRRRRRRRRRRRRR.",
    "..RRRRRRRRRRRR..",
    "...RRRRRRRRRR...",
    "....RRRRRRRR....",
    ".....RRRRRR.....",
    "......RRRR......",
    ".......RR.......",
    "................",
    "................",
    "................",
]
_HEART_SMALL = [
    "................",
    "................",
    "................",
    "....RRR..RRR....",
    "...RWRRRRRRRR...",
    "...RRRRRRRRRR...",
    "...RRRRRRRRRR...",
    "....RRRRRRRR....",
    ".....RRRRRR.....",
    "......RRRR......",
    ".......RR.......",
    "................",
    "................",
    "................",
    "................",
    "................",
]


def _shade(rows):
    """Darken the right-most red pixel of each lower row for a bit of volume."""
    out = []
    for y, r in enumerate(rows):
        if y >= 5 and "R" in r:
            i = r.rindex("R")
            r = r[:i] + "r" + r[i + 1:]
        out.append(r)
    return out


def heart_frames():
    """4-frame heartbeat: small, full, full, small."""
    big, small = _shade(_HEART), _shade(_HEART_SMALL)
    return [small, big, big, small]


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
