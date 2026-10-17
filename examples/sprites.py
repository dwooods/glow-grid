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
    # bat
    "U": (150, 70, 255),   # violet
    "u": (96, 36, 200),    # violet shadow
    # chest
    "w": (150, 72, 18),    # dark wood
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


# ---- frog ----
_FROG = [
    "................",
    "................",
    "....NNN..NNN....",
    "...NWWWNNWWWN...",
    "...NW.WNNW.WN...",
    "..NNNNNNNNNNNN..",
    ".NNNNNNNNNNNNNN.",
    ".NnnnnnnnnnnnnN.",
    ".NNNNNNNNNNNNNN.",
    "NNNNYYYYYYYYNNNN",
    "NNNYYYYYYYYYYNNN",
    "NNNYYYYYYYYYYNNN",
    ".NNNYYYYYYYYNNN.",
    "NNNNN......NNNNN",
    "nnnnn......nnnnn",
    "................",
]


def frog_frames():
    """4 frames: idle, blink, idle, tongue flick."""
    idle = list(_FROG)
    blink = list(_FROG)
    blink[3] = "...NNNNNNNNNN..."
    blink[4] = "...NnnnNNnnnN..."
    tongue = list(_FROG)
    tongue[7] = ".NnnnnnPPnnnnnN."
    tongue[8] = ".NNNNNNPPNNNNNN."
    return [idle, blink, idle, tongue]


# ---- owl ----
_OWL = [
    "................",
    "...LL......LL...",
    "...LLLLLLLLLL...",
    "..LLLLLLLLLLLL..",
    "..LYYYLLLLYYYL..",
    "..LY.YLLLLY.YL..",
    "..LYYYLLLLYYYL..",
    "..LLLLLOOLLLLL..",
    "..LLTTTOOTTTLL..",
    "..LTTLTTTTLTTL..",
    "..LTLTTTTTTLTL..",
    "..LLTTLTTLTTLL..",
    "...LLTTTTTTLL...",
    "....LLLLLLLL....",
    "....OO....OO....",
    "................",
]


def owl_frames():
    """4 frames: idle, look right, idle, blink."""
    look = list(_OWL)
    look[5] = "..LYY.LLLLYY.L.."
    blink = list(_OWL)
    blink[4] = "..LLLLLLLLLLLL.."
    blink[6] = "..LLLLLLLLLLLL.."
    return [list(_OWL), look, list(_OWL), blink]


# ---- coin ----
def _coin(rx, glint):
    rows = []
    for y in range(16):
        r = ""
        for x in range(16):
            dx, dy = (x - 7.5) / rx, (y - 7.5) / 6.4
            d = dx * dx + dy * dy
            if d > 1:
                r += "."
            elif d > 0.62 and rx >= 2:
                r += "o"
            else:
                r += "G"
        rows.append(r)
    if rx >= 4:  # embossed bar in the middle
        for y in range(5, 11):
            rows[y] = rows[y][:7] + "oo" + rows[y][9:]
    if glint:
        rows[3] = rows[3][:5] + "WW" + rows[3][7:]
        rows[4] = rows[4][:4] + "W" + rows[4][5:]
    return rows


def coin_frames():
    """4-frame spin: face, tilting, edge-on, tilting back."""
    return [_coin(6.2, True), _coin(3.6, False), _coin(1.4, False), _coin(3.6, False)]


# ---- lantern ----
_LANTERN_TOP = [
    "................",
    "................",
    "......SSSS......",
    ".....S....S.....",
    "....SSSSSSSS....",
]
_LANTERN_BOTTOM = [
    "....sYYYYYYs....",
    "....SSSSSSSS....",
    ".....ssssss.....",
    "................",
    "................",
    "................",
]
_FLAMES = [
    ["YYGGYY", "YGOOGY", "YGWWGY", "YGWWGY", "YYGGYY"],
    ["YYOOYY", "YGOOGY", "YGOWGY", "YGWOGY", "YYGGYY"],
    ["YYYYYY", "YYGGYY", "YGOOGY", "YGWWGY", "YYGGYY"],
    ["YYGGYY", "YYOOYY", "YGOWGY", "YGOOGY", "YYGGYY"],
]


def lantern_frames():
    """4-frame flicker of the flame inside a steel lantern."""
    frames = []
    for fl in _FLAMES:
        mid = ["....s" + r + "s...." for r in fl]
        frames.append(_LANTERN_TOP + mid + _LANTERN_BOTTOM)
    return frames


# ---- six more originals, a bunny flip and a rainbow burst (all generated or drawn as text) ----

def _mirror(half):
    """Rows hold the left half of a left-right symmetric 16-wide picture."""
    return [r + r[::-1] for r in half]


def _put(g, x, y, c):
    if 0 <= y < len(g) and 0 <= x < len(g[0]):
        g[y][x] = c


def _grid():
    return [["."] * 16 for _ in range(16)]


def _rows(g):
    return ["".join(r) for r in g]


# ---- mushroom ----
_MUSHROOM_CAP = [
    "......RRRR",
    "....RRRRWW",
    "...RRWWRRW",
    "..RRWWWRRR",
    ".RRRWWRRRR",
    ".RRRRRRRRR",
    "RRRRRRRWWR",
    "rrrrrrrrrr",
]
_MUSHROOM_STEM = [
    "......TTTT",
    "......TTTT",
    ".....TTTTT",
    ".....TTTTT",
    ".....TTTTT",
    "....TTTTTT",
]


def mushroom_frames():
    """4 frames: the cap bobs down and up, and spores drift off it."""
    cap, stem = _mirror(_MUSHROOM_CAP), _mirror(_MUSHROOM_STEM)
    frames = []
    for dy, spores in ((0, []), (1, []), (0, [(5, 3), (11, 2)]), (-1, [(4, 1), (11, 0), (8, 2)])):
        top = 3 + dy                      # row where the cap starts
        g = _grid()
        for i, r in enumerate(cap):
            for x, c in enumerate(r):
                if c != ".":
                    _put(g, x, top + i, c)
        for i, r in enumerate(stem):
            for x, c in enumerate(r):
                if c != ".":
                    _put(g, x, 3 + len(cap) + i, c)
        for x, y in spores:
            _put(g, x, y, "Y")
        frames.append(_rows(g))
    return frames


# ---- sword ----
def sword_frames():
    """4 frames: a diagonal sword with a glint that runs up the blade."""
    frames = []
    for glint in (3, 5, 7, 9):
        g = _grid()
        for i in range(10):               # blade, bottom-left to top-right
            x, y = 5 + i, 10 - i
            _put(g, x, y, "S")
            _put(g, x, y + 1, "s")
        _put(g, 14, 0, "W"); _put(g, 15, 0, "S")        # tip
        for i in range(-2, 3):            # cross-guard, perpendicular to the blade
            _put(g, 4 + i, 11 + i, "G"); _put(g, 5 + i, 11 + i, "G")
        for i in range(3):                # grip and pommel
            _put(g, 3 - i, 12 + i, "L"); _put(g, 2 - i, 12 + i, "L")
        _put(g, 0, 15, "G"); _put(g, 1, 15, "G")
        x, y = 5 + glint, 10 - glint
        _put(g, x, y, "W")
        if glint in (7, 9):
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                if g[y + dy][x + dx] == ".":
                    _put(g, x + dx, y + dy, "Y")
        frames.append(_rows(g))
    return frames


# ---- treasure chest ----
def chest_frames():
    """4 frames: closed, cracked, open with gold, cracked again."""
    lid_closed = _mirror(["..wwwwww", ".wLLLLLL", ".wLLLLLL", ".wGGGGGG"])
    # closed lid sits on rows 5-8; open lid stands up behind (rows 1-4)
    base = _mirror(["..LLLLLL", ".wLLGGGG", ".wLLGGGG", ".wLLLLLL", ".wLLLLLL", ".woooooo"])
    frames = []
    for state in (0, 1, 2, 1):
        g = _grid()
        for i, r in enumerate(base):                      # box on rows 9-14
            for x, c in enumerate(r):
                if c != ".":
                    _put(g, x, 9 + i, c)
        if state == 0:
            for i, r in enumerate(lid_closed):
                for x, c in enumerate(r):
                    if c != ".":
                        _put(g, x, 5 + i, c)
        elif state == 1:                                   # lid tipped up a little, a slit of gold
            for i, r in enumerate(lid_closed):
                for x, c in enumerate(r):
                    if c != ".":
                        _put(g, x, 4 + i, c)
            for x in range(3, 13):
                _put(g, x, 8, "Y")
        else:                                              # lid standing open behind, gold heaped on top
            lid = _mirror(["..wwwwww", ".wLLLLLL", ".wLLLLLL", ".wGGGGGG"])
            for i, r in enumerate(lid):
                for x, c in enumerate(r):
                    if c != ".":
                        _put(g, x, 1 + i, c)
            for x in range(2, 14):
                _put(g, x, 8, "G")
            for x in range(3, 13):
                _put(g, x, 7, "Y")
            for x in range(5, 11):
                _put(g, x, 6, "Y")
            _put(g, 7, 5, "W"); _put(g, 4, 6, "W"); _put(g, 11, 7, "W")
        frames.append(_rows(g))
    return frames


# ---- bat ----
_BAT_UP = [
    "U.....U.",
    "UU....U.",
    "UUU..UUU",
    "UUUUURUU",
    "uUUUUUUU",
    ".uUUUUUU",
    "..uuUUUU",
    "....uUUU",
    ".....UUW",
    "......UU",
]
_BAT_MID = [
    "......U.",
    "......U.",
    ".....UUU",
    "UUUUURUU",
    "UUUUUUUU",
    "uUuUUUUU",
    ".u.uUUUU",
    ".....UUW",
    "......UU",
]
_BAT_DOWN = [
    "......U.",
    "......U.",
    ".....UUU",
    "U....URU",
    "UU..UUUU",
    "UUUUUUUU",
    "uUUUUUUU",
    ".uUUUUUU",
    "..uuUUUW",
    "....uUUU",
]


def bat_frames():
    """4 frames: wings up, level, down, level."""
    frames = []
    for half in (_BAT_UP, _BAT_MID, _BAT_DOWN, _BAT_MID):
        g = _grid()
        for i, r in enumerate(_mirror(half)):
            for x, c in enumerate(r):
                if c != ".":
                    _put(g, x, 3 + i, c)
        frames.append(_rows(g))
    return frames


# ---- rocket ----
_ROCKET = [
    ".......R",
    "......RR",
    "......RR",
    ".....RRR",
    ".....SSS",
    ".....SVV",
    ".....SVV",
    ".....SSS",
    ".....SSS",
    "....sSSS",
    "....RRSS",
    "...RRRSS",
]
_FLAME_ROWS = [["....OOYY", "....OYYY", "......YY"], ["....OOYY", ".....OYY", ".....YYY", "......YY"],
               ["....OOYY", "....OYYY", "....OYYY", ".....OYY"], ["....OOYY", ".....OYY", "......YY"]]


def rocket_frames():
    """4 frames: the flame flickers and the stars drift past, so it looks like it is climbing."""
    stars = [(1, 2), (13, 5), (2, 10), (14, 12)]
    frames = []
    for t, fl in enumerate(_FLAME_ROWS):
        g = _grid()
        for x, y in stars:
            _put(g, x, (y + 3 * t) % 16, "W" if (x + y) % 2 else "A")
        body = _mirror(_ROCKET)
        for i, r in enumerate(body):
            for x, c in enumerate(r):
                if c != ".":
                    _put(g, x, 1 + i, c)
        for i, r in enumerate(_mirror(fl)):
            for x, c in enumerate(r):
                if c != ".":
                    _put(g, x, 13 + i, c)
        frames.append(_rows(g))
    return frames


# ---- candle ----
_CANDLE_BODY = [
    "......s.........",
    ".....TTTT.......",
    ".....TWTT.......",
    ".....TWTT.......",
    ".....TWTTT......",
    ".....TTTT.......",
    ".....TTTT.......",
]
_CANDLE_DISH = [
    "...GGGGGGGGGG...",
    "..GYYYYYYYYYYG..",
]
_CANDLE_FLAMES = [
    ["..Y.", ".YY.", "YOOY", ".OO."],
    [".Y..", ".YY.", "YOOY", ".OO."],
    ["..Y.", ".YYY", "YOOY", ".OO."],
    ["...Y", ".YY.", "YOOY", ".OO."],
]


def candle_frames():
    """4 frames: the flame sways left, upright, right and flares."""
    frames = []
    for fl in _CANDLE_FLAMES:
        g = _grid()
        for i, r in enumerate(fl):
            for j, c in enumerate(r):
                if c != ".":
                    _put(g, 5 + j, 3 + i, c)
        for i, r in enumerate(_CANDLE_BODY):
            for x, c in enumerate(r):
                if c != ".":
                    _put(g, x + 1, 7 + i, c)
        for i, r in enumerate(_CANDLE_DISH):
            for x, c in enumerate(r):
                if c != ".":
                    _put(g, x, 14 + i, c)
        frames.append(_rows(g))
    return frames


# ---- bunny: jump and forward flip ----
_BUNNY = [          # 8x8, facing right; rotated a quarter turn at a time for the flip, so no pixel is smeared
    "..LL.LL.",
    "..LT.LT.",
    "..LT.LT.",
    ".LLLLLLL",
    "LLLLLELP",
    "LLLLLLLL",
    "TTLLLLLL",
    ".LL..LL.",
]


def _rot(rows):
    """One quarter turn clockwise (a forward flip when the bunny faces right)."""
    n = len(rows)
    return ["".join(rows[n - 1 - y][x] for y in range(n)) for x in range(n)]


def bunny_frames():
    """10 frames: crouch, launch, a full forward flip in the air, land, settle."""
    base = _BUNNY
    turns = [base]
    for _ in range(3):
        turns.append(_rot(turns[-1]))
    squash = base[:3] + base[5:]                       # 6 rows tall: crouched
    stretch = base[:4] + [base[4]] + base[4:]           # 9 rows tall: reaching up
    ground = 15
    seq = [               # (picture, x of left edge, y of top row)
        (squash, 4, ground - 6),
        (stretch, 4, ground - 9 - 1),
        (turns[0], 4, 3),
        (turns[1], 4, 1),
        (turns[2], 4, 1),
        (turns[3], 4, 3),
        (turns[0], 4, 5),
        (stretch, 4, ground - 9),
        (squash, 4, ground - 6),
        (base, 4, ground - 8),
    ]
    frames = []
    for pic, x0, y0 in seq:
        g = _grid()
        for x in range(16):
            _put(g, x, 15, "n" if x % 2 == 0 else ".")
        for i, r in enumerate(pic):
            for j, c in enumerate(r):
                if c != ".":
                    _put(g, x0 + j, y0 + i, c)
        frames.append(_rows(g))
    return frames


# ---- rainbow star burst ----
_RAINBOW = "ROYNAEUM"      # red, orange, yellow, green, aqua, blue, violet, magenta


def burst_frames():
    """8 frames: a four-point star of rainbow rings pours out of the middle and flashes white at the heart."""
    frames = []
    for t in range(8):
        g = _grid()
        for y in range(16):
            for x in range(16):
                dx, dy = abs(x - 7.5), abs(y - 7.5)
                d = (dx ** 0.6 + dy ** 0.6) ** (1 / 0.6)     # a concave four-point star: rings keep its shape
                ring = int(d * 0.9)
                if ring > 9 - (t % 2):                       # the whole star breathes in and out, so it flashes
                    continue
                g[y][x] = _RAINBOW[(ring - t) % 8]
        if t % 2 == 0:
            for x, y in ((7, 7), (8, 7), (7, 8), (8, 8)):
                g[y][x] = "W"
        frames.append(_rows(g))
    return frames


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
