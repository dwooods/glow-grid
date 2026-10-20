"""More example sprites (2026-10-18), generated as text like the ones in sprites.py: the mushroom that shrinks, grows and pops
spores, a green laser sword, a campfire, the bat whose body stays still, and the animals, seasonal and Halloween sets.

These replace the first mushroom, sword, chest, bat and bunny in sprites.py (left there, unused, so that file did not need rewriting
through the GitHub connector; a later whole-file push can fold the two together). Same rules: 16 rows of 16 characters, LED-safe
colours, originals only.
"""
import math

from sprites import PALETTE, _grid, _mirror, _put, _rows  # noqa: F401  (_mirror kept for sprites that may want it)

PALETTE.update({
    # laser sword
    "K": (60, 255, 80),    # blade glow
    "k": (28, 196, 52),
    "j": (14, 128, 36),
    "Z": (214, 255, 220),  # blade core
    # pig
    "I": (255, 150, 170),
    "i": (222, 96, 128),
    "q": (240, 70, 115),   # snout
    # cow patches, cauldron, black cat, spider
    "x": (110, 110, 130),
    # witch hat
    "h": (84, 96, 150),    # hat, lit side
    "d": (46, 52, 96),     # hat, shaded side
    "z": (236, 240, 250),  # full moon
})


# ---- small drawing helpers for the generated examples ----
def _ell(g, cx, cy, rx, ry, c, keep=None):
    """Fill an ellipse (centre may be half-pixel); keep(x, y) can veto a cell."""
    for y in range(16):
        for x in range(16):
            if ((x - cx) / (rx + 0.5)) ** 2 + ((y - cy) / (ry + 0.5)) ** 2 <= 1.0 and (keep is None or keep(x, y)):
                g[y][x] = c


def _paste(g, pic, x0, y0):
    for i, r in enumerate(pic):
        for j, c in enumerate(r):
            if c != ".":
                _put(g, x0 + j, y0 + i, c)


# ---- mushroom: shrinks, grows past its size, and pops spores ----
def _mushroom(s):
    """One mushroom at scale s, centred; returns a grid. Cap radius 5 px at s=1, stem 4 px."""
    g = _grid()
    cw = max(2, round(5 * s)); ch = max(2, round(4 * s))
    sw = 2 if s < 0.7 else (4 if s < 1.1 else 4); sh = max(2, round(4 * s))
    top = max(0, (16 - (ch + sh) + 1) // 2)
    for i in range(ch):                                   # cap: top half of an ellipse
        k = ((ch - 1 - i + 0.5) / ch)
        half = max(1, int(round(cw * (1 - k * k) ** 0.5 + 0.0)))
        for x in range(8 - half, 8 + half):
            g[top + i][x] = "R"
    for x in range(8 - cw, 8 + cw):                       # underside of the cap
        if 0 <= x < 16:
            g[top + ch - 1][x] = "r"
    for i in range(sh):
        for x in range(8 - sw // 2, 8 + sw // 2):
            g[top + ch + i][x] = "T"
    if ch >= 4:                                           # spots
        _put(g, 8 - cw // 2 - 1, top + 1, "W"); _put(g, 8 + cw // 2, top + 2, "W")
        if cw >= 5:
            _put(g, 8, top + 1, "W")
    return g, top


def mushroom_frames():
    """11 frames: it shrinks to a stub, grows back past its first size, then pops three rings of spores."""
    frames = []
    for s in (1.0, 0.8, 0.6, 0.4, 0.6, 0.8, 1.0):
        frames.append(_rows(_mushroom(s)[0]))
    big = []
    for stage, ring in enumerate((0, 2, 4, 6)):           # full size, then spores flying outward and fading
        g, top = _mushroom(1.2)
        if ring:
            cy = top + 1
            n = {2: 7, 4: 7, 6: 5}[ring]
            for k in range(n):
                a = math.radians(-165 + k * (150 / (n - 1)))
                dx, dy = {2: (3, 2), 4: (5, 3), 6: (7, 4)}[ring]
                x, y = round(7.5 + math.cos(a) * dx), round(cy + math.sin(a) * dy)
                _put(g, x, y, "Y" if k % 2 == 0 else "W")
        big.append(_rows(g))
    return frames + big


# ---- laser sword: a green blade swinging left to right, glow changing ----
def laser_sword_frames():
    """12 frames: a green energy blade swings from the hilt at the bottom, and its glow pulses."""
    frames = []
    angles = (-60, -40, -20, 0, 20, 40, 60, 40, 20, 0, -20, -40)
    glow = ("K", "K", "k", "j", "k", "K", "K", "k", "j", "k", "K", "K")
    for ang, hal in zip(angles, glow):
        g = _grid()
        a = math.radians(ang)
        core = set()
        for t in range(0, 45):
            d = t / 4
            core.add((round(7.5 + math.sin(a) * d), round(12.5 - math.cos(a) * d)))
        for x, y in core:                                  # halo first, then the white-green core on top
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    _put(g, x + dx, y + dy, hal)
        for x, y in core:
            _put(g, x, y, "Z")
        for y, row in zip(range(13, 16), ("SS", "ss", "GG")):          # hilt
            _put(g, 7, y, row[0]); _put(g, 8, y, row[1])
        frames.append(_rows(g))
    return frames


# ---- campfire ----
def campfire_frames():
    """4 frames: logs on the ground and a fire that flickers, with sparks."""
    logs = ["...ww......ww...", "....Lw....wL....", ".....LLwwLL.....", ".TTLLLLLLLLLLTT.", ".TToooooooooTT.."]
    heights = (
        (2, 4, 6, 8, 7, 5, 3, 2),
        (3, 5, 7, 9, 6, 8, 4, 2),
        (2, 6, 8, 7, 9, 6, 3, 3),
        (3, 4, 7, 9, 8, 5, 5, 2),
    )
    sparks = (((5, 1),), ((10, 2), (4, 3)), ((7, 0), (11, 3)), ((6, 1), (9, 0)))
    frames = []
    for hs, sp in zip(heights, sparks):
        g = _grid()
        base = 10
        for i, h in enumerate(hs):
            x = 4 + i
            for k in range(h):                              # k = rows above the base
                y = base - k
                depth = h - k                               # 1 at the tip
                inner = 2 <= i <= 5
                c = "R" if depth <= 2 else ("O" if depth <= 4 or not inner else "Y")
                if inner and k <= 2:
                    c = "W" if k <= 1 else "Y"
                _put(g, x, y, c)
        _paste(g, logs, 0, 11)
        for x, y in sp:
            _put(g, x, y, "Y")
        frames.append(_rows(g))
    return frames


# ---- bat: the body stays put, only the wings move ----
_BAT_BODY = [
    "......U..U......",
    "......UUUU......",
    "......URRU......",
    "......UUUU......",
    "......UUUU......",
    ".......UU.......",
    ".......uu.......",
]
_BAT_WING_UP = [       # left wing, 6 wide, rows 1.. ; the right wing is its mirror image
    "U.....",
    "UU....",
    "UUU...",
    "UUUU..",
    "uUUUUU",
    ".uuUUU",
    "...uUU",
]
_BAT_WING_MID = [
    "......",
    "......",
    "U.....",
    "UUUU..",
    "uUUUUU",
    ".uuuUU",
    "....uU",
]
_BAT_WING_DOWN = [
    "......",
    "......",
    "......",
    ".....U",
    "U...UU",
    "UUUUUU",
    "uuUUUU",
    ".uuuUU",
    "....uU",
]


def bat_frames():
    """4 frames: the wings go up, level, down, level while the body does not move."""
    frames = []
    for wing in (_BAT_WING_UP, _BAT_WING_MID, _BAT_WING_DOWN, _BAT_WING_MID):
        g = _grid()
        for i, r in enumerate(wing):
            for j, c in enumerate(r):
                if c != ".":
                    _put(g, j, 3 + i, c); _put(g, 15 - j, 3 + i, c)
        _paste(g, _BAT_BODY, 0, 3)
        frames.append(_rows(g))
    return frames


# ---- pig: walks, with a curly tail and a twitching snout ----
def _pig_small(g, ox, oy, step, tucked=False):
    """A small pig facing right, about 11 wide, body centre at (ox, oy). step 0/1 picks the leg pose; tucked pulls the legs in."""
    _ell(g, ox, oy, 3, 2, "I")                                        # body
    _ell(g, ox + 4, oy - 0.5, 2, 2, "I")                              # head
    for dx in range(-3, 4):                                           # belly shade
        _put(g, ox + dx, oy + 2, "i")
    _put(g, ox + 7, oy, "q"); _put(g, ox + 7, oy + 1, "q")             # snout
    _put(g, ox + 4, oy - 3, "i"); _put(g, ox + 5, oy - 3, "i")        # ear
    _put(g, ox + 5, oy - 1, "E")                                      # eye
    _put(g, ox - 4, oy - 1, "i"); _put(g, ox - 5, oy - 2, "i")        # curly tail
    if tucked:
        legs = ((ox - 2, oy + 3), (ox + 2, oy + 3))
        for x, y in legs:
            _put(g, x, y, "i")
    else:
        front, back = ((ox + 3, ox - 2), (ox + 2, ox - 3))[step % 2]
        for x in (front, back):
            _put(g, x, oy + 3, "i"); _put(g, x, oy + 4, "i")


def _rotate(g, ang, px, py, lift):
    """Rotate grid g by ang degrees (counter-clockwise on screen) about (px, py), then move it up by lift rows."""
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    out = _grid()
    for y in range(16):
        for x in range(16):
            dx, dy = x - px, y - py + lift
            sx = round(px + dx * c - dy * s)                          # counter-clockwise with y pointing down
            sy = round(py + dx * s + dy * c)
            if 0 <= sx < 16 and 0 <= sy < 16 and g[sy][sx] != ".":
                out[y][x] = g[sy][sx]
    return out


def pig_frames():
    """11 frames: a small pig trots in place (4 frames), then jumps and does a backflip (6 frames), lands, and trots again."""
    frames = []
    for k in range(4):                                                # trot
        g = _grid()
        _pig_small(g, 7, 9 + (1 if k in (1, 3) else 0) - 1, k % 2)
        frames.append(_rows(g))
    for i in range(1, 7):                                             # backflip: 6 steps round a full turn, up and down in an arc
        t = i / 7
        g = _grid()
        _pig_small(g, 7, 8, 0, tucked=True)
        lift = round(4 * 3 * t * (1 - t))
        frames.append(_rows(_rotate(g, 360 * t, 7, 8, lift)))
    g = _grid(); _pig_small(g, 7, 9, 1)                               # landing
    frames.append(_rows(g))
    return frames


# ---- cow: says moo ----
_MOO = {
    "M": ["X.X", "XXX", "XXX", "X.X", "X.X"],
    "O": ["XXX", "X.X", "X.X", "X.X", "XXX"],
}


def cow_frames():
    """4 frames: a cow's face, then a speech bubble reading MOO while its mouth opens, then quiet again."""
    frames = []
    for k in range(4):
        g = _grid()
        speak = k in (1, 2)
        if speak:
            for y in range(0, 7):                          # bubble 13 x 7, rounded corners
                for x in range(1, 14):
                    if (y in (0, 6) and x in (1, 13)):
                        continue
                    g[y][x] = "W"
            for x, y in ((4, 7), (5, 7), (5, 8)):          # tail of the bubble
                g[y][x] = "W"
            for i, ch in enumerate("MOO"):
                for yy, row in enumerate(_MOO[ch]):
                    for xx, c in enumerate(row):
                        if c == "X":
                            g[1 + yy][2 + i * 4 + xx] = "a"
        top = 8
        ear = 1 if k == 2 else 0
        for x, y in ((3, top), (12, top)):                 # horns
            _put(g, x, y, "Y")
        for x, y in ((2, top + 1 + ear), (3, top + 1 + ear), (12, top + 1 + ear), (13, top + 1 + ear)):   # ears
            _put(g, x, y, "P")
        for y in range(top + 1, 16):                       # face
            for x in range(4, 12):
                g[y][x] = "W"
        for x, y in ((4, top + 1), (5, top + 1), (10, top + 2), (11, top + 2), (4, top + 2)):             # patches
            _put(g, x, y, "x")
        _put(g, 5, top + 3, "E"); _put(g, 10, top + 3, "E")                                              # eyes
        for y in range(top + 4, 16):                       # muzzle
            for x in range(5, 11):
                g[y][x] = "P"
        _put(g, 6, top + 5, "m"); _put(g, 9, top + 5, "m")                                               # nostrils
        if speak:
            for x in range(6, 10):
                _put(g, x, 14, "r"); _put(g, x, 15, "r")   # open mouth
        frames.append(_rows(g))
    return frames


# ---- duck: waddles ----
def duck_frames():
    """4 frames: a duckling waddling right, bobbing, with a flapping wing."""
    frames = []
    for k in range(4):
        g = _grid()
        bob = 1 if k % 2 else 0
        _ell(g, 6.5, 9 + bob, 5, 3, "Y")
        _ell(g, 11, 5 + bob, 2, 2, "Y")
        for x, y in ((14, 5), (15, 5), (14, 6), (13, 6)):                   # beak
            _put(g, x, y + bob, "O")
        _put(g, 11, 4 + bob, "E")
        for x, y in ((1, 7), (0, 6), (1, 6)):                              # tail tuft
            _put(g, x, y + bob, "G")
        wing = ((4, 9), (5, 9), (6, 9), (5, 10)) if k < 2 else ((4, 8), (5, 8), (6, 8), (5, 9), (4, 9))
        for x, y in wing:
            _put(g, x, y + bob, "G")
        feet = ((5, 7), (8, 6)) if k % 2 == 0 else ((6, 7), (8, 9))
        for x0, x1 in (feet,):
            pass
        fx = (5, 8) if k % 2 == 0 else (6, 9)
        for x in fx:
            _put(g, x, 13, "O"); _put(g, x + 1, 13, "O"); _put(g, x, 14, "O"); _put(g, x + 1, 14, "O")
        frames.append(_rows(g))
    return frames


# ---- hedgehog ----
def hedgehog_frames():
    """4 frames: a hedgehog snuffling right; its spikes bristle and relax."""
    frames = []
    for k in range(4):
        g = _grid()
        _ell(g, 7, 9, 6, 4, "L")
        for x in range(16):                                              # spike tips on the upper rim
            for y in range(16):
                if g[y][x] == "L" and (y < 9) and ((x + y + (k % 2)) % 2 == 0) and (y == 5 or y == 6 or x < 3):
                    g[y][x] = "o"
        if k % 2:
            for x in range(3, 11, 2):
                _put(g, x, 4, "o")
        _ell(g, 13, 11, 2, 2, "T")                                       # face
        for x, y in ((15, 11 + (k == 2)), (15, 12 + (k == 2))):          # nose
            _put(g, x, y, "w")
        _put(g, 13, 10, "w")                                             # eye
        for x in (4, 10):                                                # feet
            for y in (13, 14):
                _put(g, x, y, "w"); _put(g, x + 1, y, "w")
        frames.append(_rows(g))
    return frames


# ---- turtle ----
def turtle_frames():
    """6 frames: a turtle walks right, pulls its head in, and puts it out again."""
    frames = []
    for k in range(6):
        g = _grid()
        _ell(g, 7, 10, 6, 5, "n", keep=lambda x, y: y <= 10)
        for x, y in ((4, 7), (7, 6), (10, 7), (5, 9), (9, 9), (7, 8)):  # shell pattern
            _put(g, x, y, "N")
        for x in range(2, 13):
            _put(g, x, 11, "T")
        out = k not in (2, 3)
        if out:
            _ell(g, 13, 9, 1, 1, "N")
            _put(g, 14, 9, "E")
            if k == 5:
                _put(g, 15, 9, "N")
        elif k == 3:
            _put(g, 13, 10, "N")
        walk = k in (0, 1, 4, 5)
        for x in ((3, 9) if k % 2 == 0 else (4, 8)) if walk else (3, 9):
            for y in (12, 13):
                _put(g, x, y, "N"); _put(g, x + 1, y, "N")
        frames.append(_rows(g))
    return frames


# ---- diamond ----
def diamond_frames():
    """6 frames: a cut diamond with a shine that sweeps across it and sparkles that twinkle."""
    frames = []
    spark_sets = (((2, 2), (13, 4)), ((13, 3), (1, 10)), ((14, 11), (3, 3)), ((1, 9), (12, 2)), ((13, 4), (2, 12)), ((3, 3), (14, 10)))
    for k in range(6):
        g = _grid()
        for y in range(4, 8):                                            # crown (a wide trapezoid)
            for x in range(2 - (y - 4) // 2 + 1, 14 + (y - 4) // 2 - 1):
                g[y][x] = "C" if (x + y) % 3 else "A"
        for y in range(8, 15):                                           # pavilion (a point downward)
            half = max(0, 6 - (y - 8))
            for x in range(8 - half, 8 + half):
                g[y][x] = "A" if x < 8 else "a"
        for x in range(3, 13):
            g[7][x] = "W"                                                # girdle line
        for y in range(4, 8):
            g[y][7] = "W"; g[y][8] = "W"
        sx = 3 + k * 2                                                   # shine sweeps left to right along the crown
        for i in range(4):
            _put(g, sx + i // 2, 4 + i, "W")
        for cx, cy in spark_sets[k]:
            for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                if g[min(15, max(0, cy + dy))][min(15, max(0, cx + dx))] == ".":
                    _put(g, cx + dx, cy + dy, "W" if (dx, dy) == (0, 0) else "Y")
        frames.append(_rows(g))
    return frames


# ---- christmas tree: twinkling lights and a star ----
def tree_frames():
    """6 frames: a small fir tree whose lights twinkle in turn, with a little star sitting on its tip that flashes."""
    lights = ((6, 8, "R"), (9, 8, "E"), (7, 9, "Y"), (5, 10, "M"), (10, 10, "R"), (8, 11, "E"), (5, 12, "Y"), (10, 12, "M"), (6, 13, "R"), (9, 13, "E"))
    frames = []
    for k in range(6):
        g = _grid()
        for y in range(5, 14):                                        # three short tiers of green
            tier = 0 if y < 8 else (1 if y < 11 else 2)
            w = (y - (5, 8, 11)[tier]) + 1 + tier
            for x in range(8 - w, 8 + w):
                _put(g, x, y, "N" if (x + y) % 3 else "n")
        for x in range(6, 10):
            _put(g, x, 14, "w"); _put(g, x, 15, "w")                  # trunk
        for i, (x, y, c) in enumerate(lights):                        # each light is bright on 2 of 3 beats
            on = (i + k) % 3 != 0
            _put(g, x, y, c if on else "n")
        star = "W" if k % 2 else "G"
        for x, y in ((7, 2), (8, 2), (6, 3), (7, 3), (8, 3), (9, 3), (7, 4), (8, 4)):   # a small star resting on the tip
            _put(g, x, y, star)
        frames.append(_rows(g))
    return frames


# ---- jack o'lantern ----
def jack_frames():
    """4 frames: a carved pumpkin whose candle flickers: the carved face stays the same and only its glow changes colour."""
    frames = []
    for k in range(4):
        g = _grid()
        _ell(g, 7.5, 9, 7, 5, "o")                                     # a darker body so the carved glow shows
        for x in range(16):                                           # lighter ribs
            for y in range(16):
                if g[y][x] == "o" and x in (1, 7, 8, 14) and 5 <= y <= 13:
                    g[y][x] = "O"
        for x, y in ((7, 2), (8, 2), (8, 3), (7, 3)):
            _put(g, x, y, "n")                                        # stem
        _put(g, 9, 2, "N")
        glow = ("Y", "W", "Y", "W")[k]
        for x, y in ((3, 7), (4, 7), (5, 7), (4, 6), (5, 6), (5, 5), (10, 7), (11, 7), (12, 7), (10, 6), (11, 6), (10, 5)):   # eyes
            _put(g, x, y, glow)
        _put(g, 7, 9, glow); _put(g, 8, 9, glow); _put(g, 7, 10, glow); _put(g, 8, 10, glow)                        # nose
        for x in range(3, 13):                                        # grin (fixed shape), black gaps are teeth
            _put(g, x, 12, "." if x in (6, 9) else glow)
        for x in range(5, 11):
            _put(g, x, 13, "." if x in (7, 8) else glow)
        _put(g, 3, 11, glow); _put(g, 12, 11, glow)                   # grin corners
        frames.append(_rows(g))
    return frames


# ---- halloween set ----
_HAT_TIPS = {            # rows 1-3: the curved tip of the hat flops left, stands up with a small curl, flops right
    "left":  ["..hhh...........", ".hhhhh..........", "...hhhhhh......."],
    "up":    [".......hh.......", "......hhhh......", "......hhhhh....."],
    "right": ["...........hhh..", "..........hhhhh.", ".......hhhhhh..."],
}
_HAT_BODY = [            # rows 4-13: cone (lit left, shaded right), violet band with a gold buckle, wide brim
    "......hhhd......",
    "......hhhd......",
    ".....hhhhdd.....",
    ".....hhhhdd.....",
    "....hhhhhddd....",
    "....hhhhhddd....",
    "...UUUUGGuuuu...",
    "...uuuuGGuuuu...",
    ".hhhhhhhhdddddd.",
    "dddddddddddddddd",
]


def witch_hat_frames():
    """4 frames: a witch's hat with a gold buckle; the tip of the hat goes left, up, right, up."""
    frames = []
    for pose in ("left", "up", "right", "up"):
        rows = ["................"] + _HAT_TIPS[pose] + _HAT_BODY + ["................"] * 2
        rows = [r[:16].ljust(16, ".") for r in rows]
        frames.append(rows)
    return frames


def cauldron_frames():
    """6 frames: a small black cauldron over coals; the green brew boils and six bubbles of different sizes rise, wobble and pop."""
    frames = []
    bubbles = ((5, 0, "H"), (7, 2, "N"), (9, 4, "H"), (6, 3, "N"), (10, 1, "N"), (8, 5, "H"))   # (x, phase, colour)
    for k in range(6):
        g = _grid()
        for y, (a, b) in zip(range(9, 14), ((3, 12), (2, 13), (2, 13), (3, 12), (4, 11))):   # pot belly
            for x in range(a, b + 1):
                _put(g, x, y, "x")
        for x in range(2, 14):
            _put(g, x, 8, "s")                                        # rim
        _put(g, 1, 10, "s"); _put(g, 14, 10, "s")                     # handles
        _put(g, 3, 10, "s"); _put(g, 3, 11, "s")                      # lit edge on the left
        for x in range(3, 13):                                        # brew surface
            _put(g, x, 8, "N" if (x + k) % 3 else "H")
        for x, y in ((4, 14), (11, 14)):                              # feet
            _put(g, x, y, "x")
        for x in range(4, 12):                                        # coals
            _put(g, x, 15, "R" if (x + k) % 2 else "O")
        for x, ph, col in bubbles:
            t = (k + ph) % 6                                          # 0 = just formed on the surface, 5 = popping
            y = 7 - t
            sway = (1 if t % 2 else 0) if x % 2 else 0
            if t == 5:                                                # pop: a little ring of specks
                for dx, dy in ((-1, 0), (1, 0), (0, -1)):
                    _put(g, x + dx, y + dy, "W")
            else:
                _put(g, x + sway, y, col)
                if t in (2, 3) and col == "H":                        # bigger bubbles at mid height
                    _put(g, x + sway + 1, y, col)
        frames.append(_rows(g))
    return frames


_FW_RISE = (9, 7, 5, 3, 1)                                              # rocket head, rows below the burst centre
_FW_AGE = {                                                             # spark colours by age, one set per shell
    "gold": ("W", "Y", "G", "O", "O", "R", "r"),
    "ice":  ("W", "C", "A", "A", "a", "E", "E"),
    "rose": ("W", "P", "P", "M", "M", "m", "m"),
}


def _firework(g, t, cx, cy, tone):
    """One shell at step t (0-15): rises, flashes, throws sixteen sparks that spread, fall and fade."""
    if t < 5:                                                           # the rocket, with a short tail
        y = cy + _FW_RISE[t]
        _put(g, cx, y, "W"); _put(g, cx, y + 1, "Y"); _put(g, cx, y + 2, "r")
    elif t == 5:                                                        # the flash
        _put(g, cx, cy, "W")
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            _put(g, cx + dx, cy + dy, "Y")
    elif t <= 12:
        a = t - 6                                                       # spark age 0-6
        col = _FW_AGE[tone][a]
        r = min(a + 1, 4)
        drop = max(0, a - 3)                                            # gravity pulls the late sparks down
        d = max(1, int(r * 0.7 + 0.5))
        spokes = [(r, 0), (-r, 0), (0, r), (0, -r), (d, d), (-d, d), (d, -d), (-d, -d)]
        if r >= 3:                                                      # a second ring of sparks between the first
            spokes += [(r, 1), (-r, 1), (r - 1, -2), (-(r - 1), -2), (1, r), (-1, r), (2, -(r - 1)), (-2, -(r - 1))]
        for i, (dx, dy) in enumerate(spokes):
            if a >= 5 and i % 2:                                        # thin out as they die
                continue
            _put(g, cx + dx, cy + dy + drop, col)
    elif t <= 15:                                                       # a few dim embers drift down
        e = t - 13
        for dx, dy in ((-3, 3), (3, 3), (0, 4), (-2, 4), (2, 4)):
            if (dx + e) % 2 == 0:
                _put(g, cx + dx, cy + dy + 1 + e, "r")


def fireworks_frames():
    """16 frames: three shells fired a third of a loop apart, a gold one on the left, an ice-blue one on the right and a rose one
    higher up in the middle; each rises, flashes, bursts into a ring of sparks that spread, fall and fade, and the rest of the
    grid stays dark."""
    frames = []
    for k in range(16):
        g = _grid()
        _firework(g, (k + 5) % 16, 8, 4, "rose")                         # the middle shell goes first so the side ones draw over it
        _firework(g, k, 4, 5, "gold")
        _firework(g, (k + 11) % 16, 11, 6, "ice")
        frames.append(_rows(g))
    return frames


# ---- meteor shower: two streaks with fading tails cross a starry sky ----
_METEORS = (            # (x, y at u=0, dx per step down the line, offset in frames); dy is always +1, so the line is a clean diagonal
    (-3, 0, 1, 0),      # down and to the right
    (19, 4, -1, 8),     # down and to the left, half a loop later
)
_TAIL = ("W", "C", "c", "a")
_STARS = ((2, 2), (13, 1), (6, 6), (14, 9), (3, 12), (10, 14))


def meteor_frames():
    """16 frames: two meteors, each a white head with a short pale-blue tail on a clean diagonal, streak across a dark sky one
    after the other; a handful of steady stars sit behind them and one at a time dims for a moment."""
    frames = []
    for k in range(16):
        g = _grid()
        for i, (x, y) in enumerate(_STARS):                              # steady stars, one dimmed at a time
            _put(g, x, y, "." if (k // 2) % 6 == i and k % 2 == 0 else "s")
        for x0, y0, dx, off in _METEORS:
            u = 2 * ((k + off) % 16) - 8                                 # head steps 2 cells a frame along its diagonal, then waits off-screen
            for j, col in enumerate(_TAIL):
                _put(g, x0 + dx * (u - j), y0 + (u - j), col)
        frames.append(_rows(g))
    return frames


# ---- lightning storm: a dark cloud, rain, and two strikes ----
_CLOUD = (
    "...ssssss...",
    ".sssssssssss",
    "ssssssssssss",
    ".ssssssssss.",
)
_BOLT_A = ((8, 4), (8, 5), (7, 6), (7, 7), (8, 8), (8, 9), (7, 10), (6, 11), (6, 12), (5, 13))
_FORK_A = ((8, 7), (9, 8), (10, 9), (10, 10))
_BOLT_B = ((3, 4), (3, 5), (4, 6), (3, 7), (3, 8), (2, 9), (2, 10))
_RAIN_COLS = (0, 2, 4, 6, 10, 12, 14, 15)


def lightning_frames():
    """16 frames: a small dark cloud with rain falling past it; a forked bolt strikes and lights the cloud, then a second smaller
    bolt strikes on the left, with quiet gaps in between."""
    frames = []
    for k in range(16):
        g = _grid()
        strike = {4: "lead", 5: "full", 6: "dim", 10: "small", 11: "dim2"}.get(k)
        lit = strike in ("full", "dim", "small")
        for y, row in enumerate(_CLOUD):                                 # the cloud, brighter in the flash
            for x, c in enumerate(row):
                if c != ".":
                    _put(g, 2 + x, y, ("S" if lit else "s"))
        for i, x in enumerate(_RAIN_COLS):                               # rain: two-pixel streaks falling one row a frame
            y = (k + 5 * i) % 16
            for d, col in ((0, "a"), (-1, "E")):
                yy = y + d
                if 5 <= yy <= 15 and g[yy][x] == ".":
                    _put(g, x, yy, col)
        if strike == "lead":
            for x, y in _BOLT_A[:4]:
                _put(g, x, y, "Y")
        elif strike == "full":
            for x, y in _BOLT_A + _FORK_A:
                _put(g, x, y, "W")
        elif strike == "dim":
            for x, y in _BOLT_A[:7]:
                _put(g, x, y, "Y")
        elif strike == "small":
            for x, y in _BOLT_B:
                _put(g, x, y, "W")
        elif strike == "dim2":
            for x, y in _BOLT_B[:4]:
                _put(g, x, y, "Y")
        frames.append(_rows(g))
    return frames


_SPIDER_LEGS = (      # per side: one leg angled back, one straight out, one angled forward; (dx, dy) from the body's centre, two poses
    (((3, -1), (4, -2), (5, -3)), ((3, 0), (4, 0), (5, 0)), ((3, 1), (4, 2), (5, 3))),
    (((3, -1), (4, -2), (4, -3)), ((3, 0), (4, 1), (5, 1)), ((3, 1), (4, 2), (4, 3))),
)


def spider_frames():
    """6 frames: a spider drops on its thread, pauses, and climbs back up; its three pairs of legs (angled back, straight out,
    angled forward) twitch between two poses."""
    frames = []
    for k, drop in enumerate((3, 5, 8, 9, 6, 4)):
        g = _grid()
        for y in range(0, drop + 1):                                  # thread
            _put(g, 7, y, "s")
        cy = drop + 3
        _ell(g, 7, cy, 2, 1, "x")                                     # body
        _put(g, 7, cy - 1, "x"); _put(g, 7, cy + 1, "x")
        _put(g, 6, cy - 1, "R"); _put(g, 8, cy - 1, "R")              # eyes
        for leg in _SPIDER_LEGS[k % 2]:
            for dx, dy in leg:
                for sgn in (-1, 1):
                    if 0 <= cy + dy < 16:
                        _put(g, 7 + sgn * dx, cy + dy, "x")
        frames.append(_rows(g))
    return frames


def skull_frames():
    """4 frames: a skull whose jaw chatters and whose eye sockets flash."""
    frames = []
    for k in range(4):
        g = _grid()
        _ell(g, 7.5, 6, 6, 5, "W")
        for y in range(9, 12):                                        # cheeks narrow
            for x in range(16):
                if g[y][x] == "W" and (x < 3 or x > 12):
                    g[y][x] = "."
        for x, y in ((4, 5), (5, 5), (6, 5), (4, 6), (5, 6), (6, 6), (9, 5), (10, 5), (11, 5), (9, 6), (10, 6), (11, 6)):
            _put(g, x, y, "." if k != 2 else "R")                     # eye sockets, red flash on frame 3
        _put(g, 7, 8, "."); _put(g, 8, 8, ".")                        # nose
        jaw = (12, 13, 12, 14)[k]                                     # jaw drops
        for x in range(4, 12):
            _put(g, x, 11, "W" if x % 2 == 0 else "S")                # upper teeth
        for y in range(12, jaw):                                      # jaw hinge sides stay joined to the skull
            _put(g, 3, y, "S"); _put(g, 12, y, "S")
        for y in range(jaw, min(16, jaw + 2)):
            for x in range(3, 13):
                _put(g, x, y, "W" if (x % 2 == 1 and y == jaw and 4 <= x <= 11) else "S")
        frames.append(_rows(g))
    return frames


def black_cat_frames():
    """4 frames: a black cat arches its back high and bristles its tail, eyes glowing."""
    frames = []
    for k in range(4):
        g = _grid()
        arch = (0, 2, 4, 2)[k]
        for x in range(3, 12):                                        # body: flat, then a high arch
            lift = arch * (1 - ((x - 7) / 4.5) ** 2)
            top = 10 - lift
            for y in range(round(top), 13):
                _put(g, x, y, "x")
        _ell(g, 12.5, 9 - arch // 2, 2, 2, "x")                       # head rises a little with the arch
        hy = 9 - arch // 2
        _put(g, 11, hy - 3, "x"); _put(g, 14, hy - 3, "x"); _put(g, 11, hy - 2, "x"); _put(g, 14, hy - 2, "x")   # ears
        eye = "H" if k % 2 == 0 else "Y"
        _put(g, 12, hy, eye); _put(g, 14, hy, eye)
        tail = (((2, 11), (1, 10), (1, 9), (1, 8), (2, 7)), ((2, 10), (1, 9), (1, 8), (1, 7), (1, 6), (2, 5)),
                ((2, 9), (1, 8), (1, 7), (1, 6), (1, 5), (1, 4), (2, 3)), ((2, 10), (1, 9), (1, 8), (1, 7), (1, 6), (2, 5)))[k]
        for x, y in tail:
            _put(g, x, y, "x")
        if arch == 4:
            for x, y in ((0, 5), (2, 4), (0, 7)):                     # bristled tail
                _put(g, x, y, "x")
        for x in (4, 10):                                             # legs
            for y in (13, 14):
                _put(g, x, y, "x"); _put(g, x + 1, y, "x")
        frames.append(_rows(g))
    return frames


def moon_frames():
    """8 frames: a light grey-white full moon, three dark clouds drifting across (they wrap round, so the loop is seamless), and six
    yellow and gold stars that twinkle."""
    frames = []
    for k in range(8):
        g = _grid()
        for x, y in ((1, 1), (13, 1), (2, 12), (14, 13), (1, 7), (14, 5)):
            _put(g, x, y, "Y" if (k + x + y) % 3 else "G")            # twinkle between yellow and gold
        _ell(g, 8, 7, 4, 4, "z")                                      # moon
        for x, y in ((6, 4), (7, 4), (5, 5)):                         # bright rim
            _put(g, x, y, "W")
        for x, y in ((6, 6), (9, 8), (7, 9), (10, 6)):                # craters
            _put(g, x, y, "S")
        for off, cy, w in ((0, 6, 6), (8, 10, 5), (16, 2, 5)):        # three clouds, 3 px a frame: 8 frames = one 24 px lap
            cx = (3 * k + off) % 24 - 6
            for x in range(cx, cx + w):
                _put(g, x, cy, "x"); _put(g, x, cy + 1, "x")
            _put(g, cx + 1, cy - 1, "x"); _put(g, cx + 2, cy - 1, "x"); _put(g, cx + w - 2, cy - 1, "x")
        frames.append(_rows(g))
    return frames


def tombstone_frames():
    """4 frames: a tombstone on a grassy mound; a ghost peeks up behind it."""
    frames = []
    for k in range(4):
        g = _grid()
        peek = (0, 1, 2, 1)[k]
        if peek:
            _ell(g, 12, 7 - peek, 2, 2, "C")
            for x in range(10, 15):
                _put(g, x, 8 - peek, "C")
            _put(g, 11, 6 - peek, "E"); _put(g, 13, 6 - peek, "E")
        _ell(g, 6.5, 6, 4, 3, "s")                                    # rounded top
        for y in range(6, 14):
            for x in range(2, 11):
                _put(g, x, y, "s")
        for x in (3, 10):
            for y in range(6, 14):
                _put(g, x, y, "x")
        _put(g, 6, 7, "W"); _put(g, 7, 7, "W"); _put(g, 6, 8, "W"); _put(g, 7, 8, "W")   # R.I.P. cross
        for x in range(5, 9):
            _put(g, x, 9, "W")
        for x in range(16):                                            # mound
            _put(g, x, 14, "n"); _put(g, x, 15, "n")
        for x in (1, 5, 9, 13):
            _put(g, x, 13, "N")
        frames.append(_rows(g))
    return frames
