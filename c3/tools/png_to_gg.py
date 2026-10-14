#!/usr/bin/env python3
"""Turn a Glow Grid PNG (a still, or a sprite sheet with frames side by side) into a .gg sprite file.

    python3 png_to_gg.py fire_flower_sprite.png              # writes fire_flower.gg next to the PNG
    python3 png_to_gg.py a.png b.png c.png                   # several at once
    python3 png_to_gg.py flower.png --fps 8 --brightness 0.3

Brightness, gamma and fps come from the PNG's own `glow-grid` chunk (defaults 0.3, 2.2, 6).
The .gg file keeps the pixels as drawn: no wiring order and no gamma correction. The C3 player
applies both, and caps brightness at 0.4. Transparent pixels become black (LED off).
Needs Pillow:  pip install pillow
"""
import argparse
import json
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gg_format as gg  # noqa: E402


def convert(path, out=None, fps=None, brightness=None, gamma=None):
    img = Image.open(path)
    img.load()
    meta = {}
    try:
        meta = json.loads(img.text.get("glow-grid", "{}"))
    except (AttributeError, ValueError):
        pass
    w, h = img.size
    if h != gg.ROWS or w % gg.COLS:
        raise SystemExit(f"{path} is {w}x{h}; expected 16 px tall and a multiple of 16 wide (a Glow Grid export).")
    n = w // gg.COLS
    if "frames" in meta and meta["frames"] != n:
        raise SystemExit(f"{path}: PNG says {meta['frames']} frames but is {n} frames wide.")
    if not meta:
        print(f"note: {os.path.basename(path)} has no glow-grid metadata; using brightness 0.3, gamma 2.2, 6 fps", file=sys.stderr)
    b = brightness if brightness is not None else meta.get("brightness", 0.3)
    g = gamma if gamma is not None else meta.get("gamma", 2.2)
    f = fps if fps is not None else meta.get("fps", 6)
    rgba = img.convert("RGBA")
    frames = []
    for k in range(n):
        fr = []
        for y in range(gg.ROWS):
            for x in range(gg.COLS):
                r, gg_, bl, a = rgba.getpixel((k * gg.COLS + x, y))
                fr.append((0, 0, 0) if a < 128 else (r, gg_, bl))
        frames.append(fr)
    blob = gg.pack(frames, f, b, g)
    if out is None:
        stem = os.path.splitext(os.path.basename(path))[0]
        stem = re.sub(r"_sprite$", "", stem)
        stem = re.sub(r"[^A-Za-z0-9_-]", "_", stem)[:31] or "sprite"
        out = os.path.join(os.path.dirname(os.path.abspath(path)), stem + ".gg")
    with open(out, "wb") as fh:
        fh.write(blob)
    print(f"wrote {out}: {n} frame(s), {f} fps, brightness {b}, gamma {g}, {len(blob)} bytes")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("png", nargs="+")
    ap.add_argument("-o", "--out", help="output file (only with a single input)")
    ap.add_argument("--fps", type=float)
    ap.add_argument("--brightness", type=float)
    ap.add_argument("--gamma", type=float)
    a = ap.parse_args()
    if a.out and len(a.png) > 1:
        ap.error("--out works with one input only")
    for p in a.png:
        convert(p, a.out, a.fps, a.brightness, a.gamma)


if __name__ == "__main__":
    main()
