"""The editor's ESP32-C3 export (ggBytes in web/js/export.js) must write exactly the bytes c3/tools/gg_format.py writes,
and c3/c3_player/gg_core.h (the board's check, compiled here) must accept them. Needs Node and g++.
Run from the repo root:  python3 -m unittest discover -s tests -v
"""
import json, os, random, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'c3', 'tools'))
import gg_format as gg  # noqa: E402


def js_gg(frames_hex, fps, b, g):
    d = tempfile.mkdtemp()
    fp, out = os.path.join(d, 'f.json'), os.path.join(d, 'o.gg')
    with open(fp, 'w') as fh:
        json.dump(frames_hex, fh)
    r = subprocess.run(['node', os.path.join(HERE, 'gg_bytes.js'), out, str(fps), str(b), str(g), fp], capture_output=True, text=True)
    if r.returncode:
        return r.stderr.strip()
    with open(out, 'rb') as fh:
        return fh.read()


def frames(seed, n):
    rnd = random.Random(seed)
    return [[(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) if rnd.random() < 0.7 else (0, 0, 0) for _ in range(256)] for _ in range(n)]


hexes = lambda fr: ['#%02x%02x%02x' % px for px in fr]


class GgExportParity(unittest.TestCase):
    def test_editor_bytes_equal_python_bytes(self):
        for seed, n, fps, b, g in [(1, 1, 6, 0.3, 2.2), (2, 4, 8, 0.4, 2.2), (3, 2, 7.25, 0.35, 2.05), (4, 16, 0.5, 0.01, 1.0), (5, 3, 30, 1.0, 3.0), (6, 2, 12.5, 0.125, 2.25)]:
            fr = frames(seed, n)
            want = gg.pack(fr, fps, b, g)
            got = js_gg([hexes(f) for f in fr], fps, b, g)
            self.assertEqual(got, want, f'seed {seed}: {n} frames, {fps} fps, {b}, {g}')

    def test_editor_refuses_what_python_refuses(self):
        fr = [hexes(frames(1, 1)[0])]
        for fps, b, g in [(0.2, 0.3, 2.2), (31, 0.3, 2.2), (6, 0, 2.2), (6, 0.3, 0.9), (6, 0.3, 3.1)]:
            self.assertTrue(str(js_gg(fr, fps, b, g)).startswith('ERR'), (fps, b, g))
            with self.assertRaises(ValueError):
                gg.pack(frames(1, 1), fps, b, g)
        self.assertTrue(str(js_gg(fr * 17, 6, 0.3, 2.2)).startswith('ERR'))

    def test_board_check_accepts_editor_file(self):
        exe = os.path.join(tempfile.mkdtemp(), 'host_gg')
        subprocess.run(['g++', '-std=c++17', '-O1', os.path.join(ROOT, 'c3', 'tests', 'host_gg.cpp'), '-o', exe], check=True)
        fr = frames(7, 3)
        p = os.path.join(tempfile.mkdtemp(), 'e.gg')
        with open(p, 'wb') as fh:
            fh.write(js_gg([hexes(f) for f in fr], 5, 0.3, 2.2))
        out = subprocess.run([exe, 'hdr', p], capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(out, 'OK 3 50 30 22')


def js_decode(blob):
    d = tempfile.mkdtemp()
    fp = os.path.join(d, 'x.gg')
    with open(fp, 'wb') as fh:
        fh.write(blob)
    out = subprocess.run(['node', os.path.join(HERE, 'gg_decode.js'), fp], capture_output=True, text=True, check=True).stdout.strip()
    return out if out.startswith('ERR') else json.loads(out)


class GgDecode(unittest.TestCase):
    """ggDecode (File > Open .gg, and Load from the board) must read back exactly what gg_format.py wrote, light settings included."""
    def test_decodes_what_python_wrote(self):
        for seed, n, fps, b, g in [(1, 1, 6, 0.3, 2.2), (2, 4, 8, 0.45, 2.6), (3, 16, 0.5, 0.01, 1.0), (4, 3, 30, 1.0, 3.0), (5, 2, 7.2, 0.35, 2.05)]:
            fr = frames(seed, n)
            d = js_decode(gg.pack(fr, fps, b, g))
            self.assertEqual((d['cols'], d['rows']), (16, 16))
            self.assertEqual(d['frames'], [hexes(f) for f in fr], f'seed {seed}')
            self.assertAlmostEqual(d['fps'], round(fps * 10) / 10)
            self.assertAlmostEqual(d['brightness'], round(b * 100) / 100)
            self.assertAlmostEqual(d['gamma'], round(g * 10) / 10)

    def test_round_trips_the_editors_own_bytes(self):
        fr = frames(9, 3)
        blob = js_gg([hexes(f) for f in fr], 12, 0.4, 2.2)
        d = js_decode(blob)
        self.assertEqual(d['frames'], [hexes(f) for f in fr])
        self.assertEqual((d['fps'], d['brightness'], d['gamma']), (12, 0.4, 2.2))

    def test_refuses_damaged_files(self):
        good = gg.pack(frames(1, 2), 6, 0.3, 2.2)
        bad = {'empty': b'', 'short': good[:8], 'magic': b'XX' + good[2:], 'version': good[:2] + bytes([9]) + good[3:],
               'truncated': good[:-1], 'extra': good + b'\0', 'zero frames': good[:6] + b'\0\0' + good[8:]}
        for why, blob in bad.items():
            self.assertTrue(str(js_decode(blob)).startswith('ERR'), why)


if __name__ == '__main__':
    unittest.main()
