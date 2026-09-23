# Copy this file to local_config.py and edit it for your panel.
# local_config.py is git-ignored, so `git pull` never overwrites your settings.
#
# Find the wiring values with:  python3 probe.py   (then: python3 probe.py check)
#
#   Index 0 (red) in top-left / top-right / bottom-left / bottom-right
#       -> no flips / FLIP_X = True / FLIP_Y = True / both True
#   Index 1 (green) beside index 0          -> COLUMN_MAJOR = False
#   Index 1 (green) above/below index 0     -> COLUMN_MAJOR = True
#   Index 16 (yellow) next to index 15 (white) -> SERPENTINE = True
#   Index 16 back on index 0's edge            -> SERPENTINE = False

COLUMN_MAJOR = False
SERPENTINE = True
FLIP_X = False
FLIP_Y = False

# Default light for images that don't carry their own. PNGs saved from the
# Glow Grid simulator include its brightness/gamma, and play.py uses those.
BRIGHTNESS = 0.3
GAMMA = 2.2

# Set False to ignore the settings saved in Glow Grid images.
USE_IMAGE_LIGHT = True

# Safety cap on brightness from any source. With a 5V 6A supply, 0.4 keeps
# even a full-white frame near 6 A. Raise it only with a bigger supply.
MAX_BRIGHTNESS = 0.4

# How images are shrunk: "auto" (average photos, keep pixel art sharp),
# "nearest", or "average"
RESIZE = "auto"

# Set to True after `python3 probe.py check` (menu option c) shows white
# top-left, red along the top, green down the left and a blue diagonal.
# The menu's "k" option sets this for you.
WIRING_CONFIRMED = False
