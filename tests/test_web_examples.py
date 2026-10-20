"""The example sprites the Board card ships (web/js/examples_data.js) must be the ones in examples/sprites.py, and the
.gg bytes the editor builds from them must be what the Python side (c3/tools/gg_format.py) builds.

Run from the repo root:  python3 -m unittest tests.test_web_examples -v   (needs Node)
"""
import json, os, re, subprocess, sys, unittest, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'examples'))
sys.path.insert(0, os.path.join(ROOT, 'c3', 'tools'))
import make_examples as me  # noqa: E402
import make_web_examples as mw  # noqa: E402
import gg_format as gg  # noqa: E402
from sprites import PALETTE  # noqa: E402

MAX_SPRITES = 96     # the firmware's limit (fw 19); the examples must leave room for the user's own


def shipped():
    out = subprocess.run(['node', os.path.join(HERE, 'example_bytes.js')], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


class WebExamples(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = shipped()

    def test_data_file_is_up_to_date(self):
        with open(mw.OUT, newline='') as fh:
            self.assertEqual(fh.read(), mw.render(), 'run: python3 examples/make_web_examples.py')

    def test_every_repo_example_is_shipped_once(self):
        self.assertEqual([d['name'] for d in self.data], [mw.board_name(n) for n in me.EXAMPLES])
        self.assertEqual(len(set(d['name'] for d in self.data)), len(self.data))

    def test_names_are_legal_board_names(self):          # same rule as the firmware's gg_name_ok
        for d in self.data:
            self.assertRegex(d['name'], r'^[A-Za-z0-9_-]{1,31}$')

    def test_every_frame_is_16_rows_of_16_pixels(self):  # a row typed one dot short must fail here, not on a panel
        for name, (frames, fps) in me.EXAMPLES.items():
            for i, f in enumerate(frames):
                with self.subTest(name=name, frame=i):
                    self.assertEqual(len(f), 16, 'rows')
                    self.assertEqual([len(r) for r in f], [16] * 16, 'pixels per row')
                    self.assertLessEqual(set(''.join(f)), set(PALETTE), 'every character is in the palette')
        for d in self.data:
            self.assertEqual(len(bytes.fromhex(d['hex'])), 12 + d['frames'] * 768, d['name'])

    def test_bytes_equal_the_python_packer(self):
        for d, (name, (frames, fps)) in zip(self.data, me.EXAMPLES.items()):
            with self.subTest(name=name):
                px = [[PALETTE[c] for row in f for c in row] for f in frames]
                want = gg.pack(px, fps or mw.STILL_FPS, me.BRIGHTNESS, me.GAMMA)
                self.assertEqual(bytes.fromhex(d['hex']), want)
                self.assertEqual(d['crc'], '%08x' % (zlib.crc32(want) & 0xFFFFFFFF))
                gg.unpack(want)                            # a file the board would accept
                self.assertEqual(d['frames'], len(frames))

    def test_frames_are_16_by_16(self):
        for e in mw.entries():
            for f in e['frames']:
                self.assertEqual(len(f), 256, e['name'])
                self.assertLessEqual(set(f), set(e['palette']), e['name'])

    def test_examples_leave_room_on_the_board(self):
        self.assertLessEqual(len(self.data), MAX_SPRITES // 2)
        total = sum(len(d['hex']) // 2 for d in self.data)
        self.assertLess(total, 190 * 1024, 'the whole set should be a small part of the ~1.5 MB sprite partition')

    def test_still_uses_a_legal_speed(self):
        for d in self.data:
            self.assertTrue(0.5 <= d['fps'] <= 30)


if __name__ == '__main__':
    unittest.main()


class LegacyExamples(unittest.TestCase):
    """web/js/examples_legacy.js: fingerprints of earlier example versions, so Remove examples can delete old copies."""

    def test_legacy_file_is_up_to_date(self):
        if not os.path.isdir(os.path.join(ROOT, '.git')):
            self.skipTest('needs the git history')
        import make_legacy_examples as ml
        with open(ml.OUT, newline='') as fh:
            self.assertEqual(fh.read(), ml.render(ml.collect()), 'run: python3 examples/make_legacy_examples.py')

    def test_no_legacy_entry_is_a_current_example(self):
        now = {(d['name'], d['crc'], len(d['hex']) // 2) for d in shipped()}
        with open(os.path.join(ROOT, 'web', 'js', 'examples_legacy.js')) as fh:
            old = [tuple(json.loads('[' + m + ']')) for m in re.findall(r'^\s*\[(.*)\],$', fh.read(), re.M)]
        self.assertTrue(old, 'the list is not empty')
        self.assertFalse(now & set(old))
        for n in ('bunny_sprite', 'chest_sprite', 'sword_sprite'):      # examples retired in the 2026-10-18 overhaul
            self.assertIn(n, [o[0] for o in old])
