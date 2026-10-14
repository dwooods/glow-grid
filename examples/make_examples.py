"""Write the example sprites into images/ (run automatically by run.sh when
images/ is empty)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sprites import (  # noqa: E402
    cat_frames, fish_frames, fox_frames, gem_frames, ghost_frames, heart_frames,
    key_frames, knight_frames, potion_frames, slime_frames, to_image)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")
os.makedirs(OUT, exist_ok=True)

outputs = {
    "knight.png": [knight_frames()[0]],
    "knight_4fps.png": knight_frames(),
    "slime_3fps.png": slime_frames(),
    "ghost_4fps.png": ghost_frames(),
    "gem_4fps.png": gem_frames(),
    "cat_3fps.png": cat_frames(),
    "fox_3fps.png": fox_frames(),
    "fish_4fps.png": fish_frames(),
    "potion_4fps.png": potion_frames(),
    "key_4fps.png": key_frames(),
    "heart_3fps.png": heart_frames(),
}
for name, frames in outputs.items():
    to_image(frames).save(os.path.join(OUT, name))
    print(f"wrote images/{name}")
