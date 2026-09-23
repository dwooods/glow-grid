"""Show a still image or play an animation on the panel.

Usage: python3 play.py <image> [fps]
  <image>  PNG/JPG/WEBP still, sprite sheet (name it *_8fps.png or *_sheet.png),
           or animated GIF. A bare filename is looked up in images/.
  [fps]    optional frame-rate override
"""
import os
import sys
import time

import grid_common
from grid_common import get_strip, draw, load_frames, resolve_path

if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

path = resolve_path(sys.argv[1])
if not os.path.exists(path):
    print(f"Image not found: {path}")
    sys.exit(1)

if not getattr(grid_common, "WIRING_CONFIRMED", False) and not os.environ.get("GLOWGRID_MENU"):
    print("Note: wiring not confirmed yet (run probe.py, then set WIRING_CONFIRMED = True "
          "in local_config.py). The image may look scrambled.")

fps = float(sys.argv[2]) if len(sys.argv) > 2 else None
frames, delays = load_frames(path, fps)

strip = get_strip()
try:
    if len(frames) == 1:
        draw(strip, frames[0])
        while True:          # hold the still until stopped
            time.sleep(1)
    while True:
        for frame, d in zip(frames, delays):
            draw(strip, frame)
            time.sleep(d)
except KeyboardInterrupt:
    pass
finally:
    strip.clear()
    strip.show()
