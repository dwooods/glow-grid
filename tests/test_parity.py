"""Guards the two places where a silent bug would reach the panel:
 1. the gamma/brightness LUT in web/js/led.js must equal grid_common.py's;
 2. a PNG saved by the simulator (web/js/export.js) must be read back correctly by grid_common.image_light/image_grid.

Run from the repo root:  python3 -m unittest discover -s tests -v
Needs Node and Pillow. The Pi-only driver (rpi5_ws2812) is stubbed, so it runs on any Linux/macOS/WSL box.
"""
import json, os, subprocess, sys, tempfile, types, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# grid_common imports the SPI driver at module level; stub it so tests run off the Pi.
drv = types.ModuleType('rpi5_ws2812.ws2812')
drv.Color = lambda r, g, b: (r, g, b)
drv.WS2812SpiDriver = object
pkg = types.ModuleType('rpi5_ws2812'); pkg.ws2812 = drv
sys.modules.setdefault('rpi5_ws2812', pkg); sys.modules.setdefault('rpi5_ws2812.ws2812', drv)
import grid_common as gc  # noqa: E402
from PIL import Image  # noqa: E402


def node(*args):
    return subprocess.run(['node', *args], check=True, capture_output=True, text=True).stdout.strip()


class LutParity(unittest.TestCase):
    PAIRS = [(0.3, 2.2), (0.4, 2.2), (0.35, 2.0), (0.1, 3.0), (0.01, 1.0), (0.4, 1.0), (0.25, 2.8), (0.05, 2.4)]

    def test_simulator_lut_equals_python_lut(self):
        old = (gc.BRIGHTNESS, gc.GAMMA, gc.MAX_BRIGHTNESS)
        gc.MAX_BRIGHTNESS = 1.0  # test the formula, not the safety cap
        try:
            js = json.loads(node(os.path.join(HERE, 'led_lut.js'), json.dumps(self.PAIRS)))
            for i, (b, g) in enumerate(self.PAIRS):
                gc.set_light(b, g)
                with self.subTest(brightness=b, gamma=g):
                    diff = [c for c in range(256) if js[i][c] != gc._LUT[c]]
                    self.assertEqual(diff, [], f'LUT differs at channel values {diff[:10]}')
        finally:
            gc.MAX_BRIGHTNESS = old[2]; gc.set_light(old[0], old[1])


class PngMetadata(unittest.TestCase):
    def roundtrip(self, brightness, gamma, extra):
        with tempfile.TemporaryDirectory() as d:
            src, out = os.path.join(d, 'in.png'), os.path.join(d, 'out.png')
            Image.new('RGB', (64, 16), (10, 20, 30)).save(src)
            node(os.path.join(HERE, 'png_text.js'), src, out, str(brightness), str(gamma), json.dumps(extra))
            with Image.open(out) as im:  # still a valid PNG with unchanged pixels
                self.assertEqual(im.getpixel((5, 5)), (10, 20, 30))
            return gc.image_light(out), gc.image_grid(out), gc._png_meta(out)

    def test_sheet(self):
        light, grid, meta = self.roundtrip(0.35, 2.2, {'cols': 16, 'rows': 16, 'frames': 4, 'fps': 4})
        self.assertEqual(light, {'brightness': 0.35, 'gamma': 2.2})
        self.assertEqual(grid, (16, 16))
        self.assertEqual((meta['frames'], meta['fps']), (4, 4))

    def test_still_has_no_frames_key(self):
        light, grid, meta = self.roundtrip(0.3, 2.0, {'cols': 16, 'rows': 16})
        self.assertEqual(light, {'brightness': 0.3, 'gamma': 2.0})
        self.assertNotIn('frames', meta)

    def test_js_reader_reads_its_own_chunk(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = os.path.join(d, 'in.png'), os.path.join(d, 'out.png')
            Image.new('RGB', (16, 16)).save(src)
            node(os.path.join(HERE, 'png_text.js'), src, out, '0.4', '2.2', '{}')
            self.assertEqual(json.loads(node(os.path.join(HERE, 'png_text.js'), 'read', out))['brightness'], 0.4)


if __name__ == '__main__':
    unittest.main()
