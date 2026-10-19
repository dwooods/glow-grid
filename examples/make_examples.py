"""Write the example sprites into images/ (run automatically by run.sh when
images/ is empty).

Each PNG carries the same `glow-grid` text chunk the editor writes (brightness,
gamma, cols, rows, and for animations frames and fps), so the Pi reads speed and
brightness from the file and the names stay plain: <name>_sprite.png, exactly
as the editor names a saved sprite.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sprites import (  # noqa: E402
    burst_frames, candle_frames, cat_frames, coin_frames, fish_frames, fox_frames, frog_frames, gem_frames,
    ghost_frames, heart_frames, key_frames, knight_frames, lantern_frames, owl_frames, potion_frames,
    rocket_frames, slime_frames, to_image)
from sprites2 import (  # noqa: E402
    bat_frames, black_cat_frames, campfire_frames, cauldron_frames, cow_frames, diamond_frames, duck_frames,
    hedgehog_frames, jack_frames, laser_sword_frames, moon_frames, mushroom_frames, pig_frames, skull_frames,
    spider_frames, tombstone_frames, tree_frames, turtle_frames, witch_hat_frames)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")
BRIGHTNESS, GAMMA = 0.3, 2.2   # the editor's defaults

# name -> (frames, fps); a single frame is a still
EXAMPLES = {
    "knight_still": ([knight_frames()[0]], None),
    "knight": (knight_frames(), 4),
    "slime": (slime_frames(), 3),
    "ghost": (ghost_frames(), 4),
    "gem": (gem_frames(), 4),
    "cat": (cat_frames(), 3),
    "fox": (fox_frames(), 3),
    "fish": (fish_frames(), 4),
    "potion": (potion_frames(), 5),
    "key": (key_frames(), 4),
    "heart": (heart_frames(), 3),
    "frog": (frog_frames(), 3),
    "owl": (owl_frames(), 2),
    "coin": (coin_frames(), 6),
    "lantern": (lantern_frames(), 5),
    "mushroom": (mushroom_frames(), 5),
    "laser_sword": (laser_sword_frames(), 10),
    "campfire": (campfire_frames(), 6),
    "bat": (bat_frames(), 6),
    "rocket": (rocket_frames(), 6),
    "candle": (candle_frames(), 5),
    "pig": (pig_frames(), 8),
    "cow": (cow_frames(), 2),
    "duck": (duck_frames(), 4),
    "hedgehog": (hedgehog_frames(), 3),
    "turtle": (turtle_frames(), 3),
    "diamond": (diamond_frames(), 5),
    "tree": (tree_frames(), 3),
    "jack": (jack_frames(), 3),
    "witch_hat": (witch_hat_frames(), 3),
    "cauldron": (cauldron_frames(), 4),
    "spider": (spider_frames(), 4),
    "skull": (skull_frames(), 4),
    "black_cat": (black_cat_frames(), 3),
    "moon": (moon_frames(), 3),
    "tombstone": (tombstone_frames(), 2),
    "burst": (burst_frames(), 8),
}


def light_json(frames, fps):
    """Same key order and compact form as lightJson() in web/js/export.js."""
    meta = {"brightness": BRIGHTNESS, "gamma": GAMMA, "cols": len(frames[0][0]), "rows": len(frames[0])}
    if len(frames) > 1:
        meta["frames"], meta["fps"] = len(frames), fps
    return json.dumps(meta, separators=(",", ":"))


def save(frames, fps, path):
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo()
    info.add_text("glow-grid", light_json(frames, fps))
    to_image(frames).save(path, pnginfo=info)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for name, (frames, fps) in EXAMPLES.items():
        save(frames, fps, os.path.join(OUT, f"{name}_sprite.png"))
        print(f"wrote images/{name}_sprite.png")
