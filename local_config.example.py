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

# Keep these the same as the LED settings in the Glow Grid simulator
BRIGHTNESS = 0.3
GAMMA = 2.2
