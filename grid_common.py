"""Shared helpers for the 16x16 panel: strip setup, wiring map, color
correction, and image/animation loading. Every script imports from here.

Per-panel settings (wiring order, brightness, gamma) belong in
local_config.py, which is git-ignored so `git pull` never overwrites them.
Copy local_config.example.py to local_config.py and edit that.
"""
import fcntl
import json
import os
import re
import sys

from PIL import Image, ImageSequence
from rpi5_ws2812.ws2812 import Color, WS2812SpiDriver

# ---- Defaults (override any of these in local_config.py) ----
ROWS = 16
COLS = 16

COLUMN_MAJOR = False  # True if index 1 is above/below index 0, False if beside it
SERPENTINE = True     # True if index 16 sits right next to index 15
FLIP_X = False        # True if index 0 is on the right side
FLIP_Y = False        # True if index 0 is on the bottom

BRIGHTNESS = 0.3      # overall cap; keeps current draw sane
GAMMA = 2.2           # makes LED colors match what you drew on screen
DEFAULT_FPS = 6

# How images are shrunk to the grid:
#   "auto"    average each cell when the image is much bigger than the grid
#             (photos), pick single pixels otherwise (pixel art)
#   "nearest" always pick single pixels
#   "average" always average
RESIZE = "auto"
AVERAGE_ABOVE = 2     # "auto" averages when width or height > this many times the grid

# Set to True once `probe.py check` shows the expected pattern
# (the menu's "k" option does this for you).
WIRING_CONFIRMED = False

# Images saved from Glow Grid carry the simulator's brightness and gamma, and
# play.py uses them for that image. BRIGHTNESS/GAMMA above are the defaults for
# images without them (Piskel, GIFs, photos).
USE_IMAGE_LIGHT = True
MAX_BRIGHTNESS = 0.4  # safety cap on any image's brightness; 0.4 = ~6 A for full white

try:
    from local_config import *  # noqa: F401,F403
except ImportError:
    pass

LED_COUNT = ROWS * COLS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(BASE_DIR, "images")


# ---- Panel lock: only one program may drive the panel at a time ----
LOCK_PATH = "/tmp/glow-grid-panel.lock"
_lock_handle = None


class PanelBusy(RuntimeError):
    pass


def acquire_panel():
    """Take the panel lock (no-op if this process already holds it)."""
    global _lock_handle
    if _lock_handle is not None:
        return
    handle = open(LOCK_PATH, "w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        raise PanelBusy(
            "The panel is already in use by another glow-grid program (the menu, or\n"
            "play.py in another terminal). Stop that one first (Ctrl+C, or q in the menu)."
        )
    _lock_handle = handle


def release_panel():
    global _lock_handle
    if _lock_handle is not None:
        _lock_handle.close()  # closing the file releases the lock
        _lock_handle = None


def get_strip():
    """Open the panel. Exits with a clear message if another program holds it."""
    try:
        acquire_panel()
    except PanelBusy as e:
        print(e)
        sys.exit(1)
    strip = WS2812SpiDriver(spi_bus=0, spi_device=0, led_count=LED_COUNT).get_strip()
    strip.set_brightness(1.0)  # brightness is applied in correct() instead
    return strip


def xy_to_index(x, y):
    """x=0, y=0 is the top-left pixel, matching image/editor coordinates."""
    if FLIP_X:
        x = COLS - 1 - x
    if FLIP_Y:
        y = ROWS - 1 - y
    if COLUMN_MAJOR:
        pos = (ROWS - 1 - y) if (SERPENTINE and x % 2) else y
        return x * ROWS + pos
    pos = (COLS - 1 - x) if (SERPENTINE and y % 2) else x
    return y * COLS + pos


# Gamma + brightness lookup table; any non-zero channel stays at least 1.
# The Glow Grid simulator (web/index.html) uses this exact formula.
_LUT = []


def set_light(brightness=None, gamma=None):
    """Set brightness/gamma (None keeps the current value) and rebuild the
    lookup table. Brightness is capped at MAX_BRIGHTNESS."""
    global BRIGHTNESS, GAMMA
    if brightness is not None:
        BRIGHTNESS = max(0.01, min(float(MAX_BRIGHTNESS), float(brightness)))
    if gamma is not None:
        GAMMA = max(1.0, min(3.0, float(gamma)))
    table = []
    for c in range(256):
        v = round(255 * BRIGHTNESS * (c / 255) ** GAMMA)
        table.append(1 if (c > 0 and v == 0) else v)
    _LUT[:] = table


set_light(BRIGHTNESS, GAMMA)


def correct(r, g, b):
    return Color(_LUT[r], _LUT[g], _LUT[b])


def resize_method(w, h):
    """Which resampling fit() uses for a w x h image (see RESIZE)."""
    if RESIZE == "average":
        return "average"
    if RESIZE == "nearest":
        return "nearest"
    return "average" if (w > AVERAGE_ABOVE * COLS or h > AVERAGE_ABOVE * ROWS) else "nearest"


def fit(src):
    """Fit an image to the grid without stretching, centered, with transparent
    areas composited onto black. Pixel art keeps hard edges (nearest); large
    images such as photos are averaged per cell (see RESIZE)."""
    src = src.convert("RGBA")
    w, h = src.size
    s = min(COLS / w, ROWS / h)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    method = Image.Resampling.BOX if resize_method(w, h) == "average" else Image.Resampling.NEAREST
    src = src.resize((nw, nh), method)
    canvas = Image.new("RGBA", (COLS, ROWS), (0, 0, 0, 255))
    canvas.alpha_composite(src, ((COLS - nw) // 2, (ROWS - nh) // 2))
    return canvas.convert("RGB")


def resolve_path(path):
    """Accept an absolute path, a path relative to the project, or a bare
    filename inside images/."""
    if os.path.isabs(path):
        return path
    for candidate in (os.path.join(BASE_DIR, path), os.path.join(IMAGES_DIR, path)):
        if os.path.exists(candidate):
            return candidate
    return os.path.join(BASE_DIR, path)


SHEET_NAME = re.compile(r"_(\d+(?:\.\d+)?)fps|_sheet", re.IGNORECASE)


def is_sheet_name(path):
    """Sprite sheets are opted in by name: "_8fps" or "_sheet" in the filename."""
    return bool(SHEET_NAME.search(os.path.basename(path)))


def load_frames(path, fps=None):
    """Return (frames, delays) for a still image, a sprite sheet (frames side by
    side, each COLS x ROWS, named with "_<n>fps" or "_sheet"), or an animated GIF.

    Frame rate, in priority order: the fps argument, "_<n>fps" in the
    filename, the GIF's own timing, DEFAULT_FPS."""
    img = Image.open(path)
    frames, delays = [], []
    if getattr(img, "is_animated", False):
        for f in ImageSequence.Iterator(img):
            frames.append(fit(f))
            delays.append(max(0.02, f.info.get("duration", 100) / 1000))
    else:
        sheet = img.convert("RGBA")
        w, h = sheet.size
        if h == ROWS and w % COLS == 0 and w > COLS and is_sheet_name(path):
            for i in range(w // COLS):
                frames.append(fit(sheet.crop((i * COLS, 0, (i + 1) * COLS, ROWS))))
        else:
            frames.append(fit(sheet))

    if fps is None:
        m = re.search(r"_(\d+(?:\.\d+)?)fps", os.path.basename(path), re.IGNORECASE)
        if m:
            fps = float(m.group(1))
    if fps or not delays:
        delays = [1 / (fps or DEFAULT_FPS)] * len(frames)
    return frames, delays


LIGHT_KEY = "glow-grid"  # PNG text chunk written by the Glow Grid simulator


def image_light(path):
    """Return {"brightness": b, "gamma": g} saved in a Glow Grid PNG, or {}."""
    try:
        with Image.open(path) as img:
            raw = getattr(img, "text", {}).get(LIGHT_KEY) or img.info.get(LIGHT_KEY)
        data = json.loads(raw) if raw else {}
    except (OSError, ValueError):
        return {}
    out = {}
    for key in ("brightness", "gamma"):
        if isinstance(data.get(key), (int, float)):
            out[key] = float(data[key])
    return out


def draw(strip, img):
    px = img.load()
    for x in range(COLS):
        for y in range(ROWS):
            strip.set_pixel_color(xy_to_index(x, y), correct(*px[x, y]))
    strip.show()
