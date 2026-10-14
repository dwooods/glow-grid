"""The example generator (examples/make_examples.py) must write the same
`glow-grid` chunk the editor writes, so the Pi reads frames, speed and
brightness from the file and the names need no _Nfps.

Run from the repo root:  python3 -m unittest tests.test_examples -v   (needs Node and Pillow)
"""
import json, os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'examples'))
from test_parity import gc, node  # noqa: E402  (also stubs the Pi driver)
import make_examples as me  # noqa: E402


class ExampleMetadata(unittest.TestCase):
    def test_chunk_matches_editor_and_pi_reads_it(self):
        with tempfile.TemporaryDirectory() as d:
            for name, (frames, fps) in me.EXAMPLES.items():
                with self.subTest(name=name):
                    p = os.path.join(d, name + '_sprite.png')
                    me.save(frames, fps, p)
                    extra = {'cols': 16, 'rows': 16}
                    if len(frames) > 1:
                        extra.update(frames=len(frames), fps=fps)
                    ref = os.path.join(d, 'ref.png')
                    node(os.path.join(HERE, 'png_text.js'), p, ref,
                         str(me.BRIGHTNESS), str(me.GAMMA), json.dumps(extra))
                    mine = node(os.path.join(HERE, 'png_text.js'), 'read', p)
                    editor = node(os.path.join(HERE, 'png_text.js'), 'read', ref)
                    self.assertEqual(mine, editor)  # byte-identical text
                    self.assertEqual(gc.image_light(p), {'brightness': 0.3, 'gamma': 2.2})
                    self.assertEqual(gc.image_grid(p), (16, 16))
                    out, delays = gc.load_frames(p)
                    self.assertEqual(len(out), len(frames))
                    if len(frames) > 1:
                        self.assertAlmostEqual(delays[0], 1 / fps)

    def test_names_are_plain_and_unique(self):
        for name in me.EXAMPLES:
            self.assertNotRegex(name, r'_\d+fps|_sheet|_sprite')


if __name__ == '__main__':
    unittest.main()
