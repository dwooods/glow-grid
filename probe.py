"""Wiring probe for the panel.

  python3 probe.py          static markers on raw indexes (find the wiring order)
  python3 probe.py walk     a single dot walks index 0..LED_COUNT-1
  python3 probe.py check    verifies the xy_to_index settings in local_config.py
"""
import sys
import time

from rpi5_ws2812.ws2812 import Color
from grid_common import get_strip, xy_to_index, LED_COUNT, COLS, ROWS

OFF = Color(0, 0, 0)
V = 40  # dim, raw (no gamma)
strip = get_strip()
mode = sys.argv[1] if len(sys.argv) > 1 else "markers"

try:
    if mode == "walk":
        delay = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
        for i in range(LED_COUNT):
            strip.set_all_pixels(OFF)
            strip.set_pixel_color(i, Color(V, V, V))
            strip.show()
            time.sleep(delay)
    else:
        strip.set_all_pixels(OFF)
        if mode == "check":
            for x in range(COLS):
                strip.set_pixel_color(xy_to_index(x, 0), Color(V, 0, 0))   # top row red
            for y in range(ROWS):
                strip.set_pixel_color(xy_to_index(0, y), Color(0, V, 0))   # left column green
            for i in range(min(COLS, ROWS)):
                strip.set_pixel_color(xy_to_index(i, i), Color(0, 0, V))   # diagonal blue
            strip.set_pixel_color(xy_to_index(0, 0), Color(V, V, V))       # top-left white
            print("Expect: white top-left, red along the TOP, green down the LEFT,")
            print("blue diagonal top-left -> bottom-right.")
        else:
            strip.set_pixel_color(0, Color(V, 0, 0))              # red
            strip.set_pixel_color(1, Color(0, V, 0))              # green
            strip.set_pixel_color(COLS - 1, Color(V, V, V))       # white
            strip.set_pixel_color(COLS, Color(V, V, 0))           # yellow
            strip.set_pixel_color(LED_COUNT - 1, Color(0, 0, V))  # blue
            print(f"Index 0 = RED, 1 = GREEN, {COLS - 1} = WHITE, {COLS} = YELLOW, "
                  f"{LED_COUNT - 1} = BLUE")
        strip.show()
        while True:
            time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    strip.clear()
    strip.show()
