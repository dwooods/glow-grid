"""Generate the app icons (run in CI before deploying web/ to GitHub Pages;
the PNGs are not committed). Draws the example knight as glowing LED dots."""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "examples"))
from sprites import PALETTE, knight_frames  # noqa: E402

BG = (10, 12, 16)
OFF = (27, 32, 40)


def icon(size, pad_ratio):
    sprite = knight_frames()[0]
    img = Image.new("RGB", (size, size), BG)
    pad = int(size * pad_ratio)
    cell = (size - 2 * pad) / 16
    r = cell * 0.42
    dots = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(dots)
    for y, row in enumerate(sprite):
        for x, c in enumerate(row):
            cx, cy = pad + (x + 0.5) * cell, pad + (y + 0.5) * cell
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=OFF if c == "." else PALETTE[c])
    glow = dots.filter(ImageFilter.GaussianBlur(cell * 0.35))
    img = Image.blend(glow, dots, 0.65)
    return img


for name, size, pad in [("icon-192.png", 192, 0.08), ("icon-512.png", 512, 0.08),
                        ("icon-maskable-512.png", 512, 0.18), ("apple-touch-icon.png", 180, 0.1)]:
    icon(size, pad).save(os.path.join(HERE, name))
    print("wrote web/" + name)
