"""Write the example sprites into images/ (run automatically by run.sh when
images/ is empty)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sprites import knight_frames, smiley_frames, to_image  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images")
os.makedirs(OUT, exist_ok=True)

outputs = {
    "knight.png": [knight_frames()[0]],
    "knight_4fps.png": knight_frames(),
    "smiley_3fps.png": smiley_frames(),
}
for name, frames in outputs.items():
    to_image(frames).save(os.path.join(OUT, name))
    print(f"wrote images/{name}")
