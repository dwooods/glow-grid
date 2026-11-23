"""The experimental Bluetooth panel card's pure code (web/js/panel.js): the GIF it makes, the packets it frames, and the text it lays out.
Needs Node and Pillow. Run from the repo root:  python3 -m unittest tests.test_panel -v

What this proves and what it does not: every frame of every example is written as a complete 32x32 picture (the panel cannot play the
usual patch-only GIFs; tested on a real panel) and decodes back to the source pixels; the packet framing follows the layout in panel.js;
text lands inside the panel. It does not prove the panel accepts the bytes: that was checked by hand on a real panel.
"""
import base64, io, json, os, shutil, struct, subprocess, sys, tempfile, unittest, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'examples'))
PANEL = os.path.join(ROOT, 'web', 'js', 'panel.js')
FONTS = os.path.join(ROOT, 'web', 'js', 'panel_fonts.js')
NODE = shutil.which('node')

PRELUDE = f"""
const P = require({json.dumps(PANEL)});
global.window = {{}}; require({json.dumps(FONTS)}); const FONTS = window.GG_PANEL_FONTS;
const hexToRgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
"""


def run_node(body, stdin=''):
    r = subprocess.run([NODE, '-e', PRELUDE + body], input=stdin, capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise AssertionError(r.stderr[:2000])
    return json.loads(r.stdout)


def gif_images(g):
    """Every image descriptor in a GIF as (left, top, width, height), read from the bytes (no library)."""
    pos = 13
    if g[10] & 0x80:
        pos += 3 * (1 << ((g[10] & 7) + 1))
    out = []
    while g[pos] != 0x3b:
        if g[pos] == 0x21:
            pos += 2
            while g[pos]:
                pos += g[pos] + 1
            pos += 1
        elif g[pos] == 0x2c:
            out.append(struct.unpack('<HHHH', g[pos + 1:pos + 9]))
            assert g[pos + 9] == 0, 'local palette or interlace'
            pos += 10 + 1
            while g[pos]:
                pos += g[pos] + 1
            pos += 1
        else:
            raise AssertionError(f'unexpected GIF block {g[pos]:#x}')
    return out


@unittest.skipIf(NODE is None, 'Node is not installed')
class PanelGif(unittest.TestCase):
    def test_every_example_becomes_full_frames_that_decode_to_the_source_pixels(self):
        from PIL import Image
        import make_examples as m
        from sprites import PALETTE
        examples = {}
        for name, (frames, fps) in m.EXAMPLES.items():
            hexed = [['#%02x%02x%02x' % PALETTE[c] for row in f for c in row] for f in frames]
            examples[name] = {'frames': hexed, 'fps': fps or 6, 'cols': len(frames[0][0]), 'rows': len(frames[0])}
        out = run_node("""
const ex = JSON.parse(require('fs').readFileSync(0, 'utf8')), res = {};
for (const [n, e] of Object.entries(ex)) {
  const fr = e.frames.map((f) => P.toPanelFrame(f, e.cols, e.rows, hexToRgb));
  res[n] = Buffer.from(P.makeGif(fr, 32, 32, Math.max(2, Math.round(100 / e.fps)))).toString('base64');
}
console.log(JSON.stringify(res));""", json.dumps(examples))
        self.assertGreaterEqual(len(out), 30)
        for name, b64 in out.items():
            with self.subTest(name=name):
                g = base64.b64decode(b64)
                imgs = gif_images(g)
                e = examples[name]
                self.assertEqual(len(imgs), len(e['frames']))
                self.assertTrue(all(i == (0, 0, 32, 32) for i in imgs), 'every frame is a complete picture at (0,0), never a patch')
                dec = Image.open(io.BytesIO(g))
                self.assertEqual(dec.n_frames, len(e['frames']))
                for k, hexed in enumerate(e['frames']):
                    dec.seek(k)
                    src = Image.new('RGB', (e['cols'], e['rows']))
                    src.putdata([tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in hexed])
                    s = 32 // e['cols']
                    expect = Image.new('RGB', (32, 32)); expect.paste(src.resize((e['cols'] * s, e['rows'] * s), Image.NEAREST), ((32 - e['cols'] * s) // 2, (32 - e['rows'] * s) // 2))
                    self.assertEqual(dec.convert('RGB').tobytes(), expect.tobytes(), f'frame {k}')
                self.assertEqual(dec.info.get('duration'), max(2, int(100 / e['fps'] + 0.5)) * 10)   # JavaScript's Math.round, not Python's half-to-even

    def test_more_than_256_colours_are_reduced_not_rejected(self):
        from PIL import Image
        hexed = ['#%02x%02x%02x' % ((i * 7) % 256, (i * 13) % 256, (i * 29) % 256) for i in range(256)]
        out = run_node("const f = JSON.parse(require('fs').readFileSync(0, 'utf8')); console.log(JSON.stringify(Buffer.from(P.makeGif([P.toPanelFrame(f, 16, 16, hexToRgb)], 32, 32, 10)).toString('base64')));", json.dumps(hexed))
        # 256 distinct colours fit as they are, so also try 300 by adding a second frame of other colours
        hexed2 = ['#%02x%02x%02x' % ((i * 11 + 3) % 256, (i * 5 + 9) % 256, (i * 17 + 1) % 256) for i in range(256)]
        out = run_node("const [a, b] = JSON.parse(require('fs').readFileSync(0, 'utf8')); const fr = [a, b].map((f) => P.toPanelFrame(f, 16, 16, hexToRgb)); console.log(JSON.stringify(Buffer.from(P.makeGif(fr, 32, 32, 10)).toString('base64')));", json.dumps([hexed, hexed2]))
        dec = Image.open(io.BytesIO(base64.b64decode(out)))
        self.assertEqual(dec.n_frames, 2)
        dec.seek(1)
        px = dec.convert('RGB').getpixel((2, 2))   # pixel (1,1) of the drawing is index 17
        want = tuple(int(hexed2[17][i:i + 2], 16) for i in (1, 3, 5))
        self.assertTrue(all(abs(a - b) <= 40 for a, b in zip(px, want)), (px, want))

    def test_a_drawing_larger_than_the_panel_is_refused(self):
        out = run_node("try { P.toPanelFrame(new Array(33 * 33).fill('#000000'), 33, 33, hexToRgb); console.log('false'); } catch (e) { console.log(JSON.stringify(e.message)); }")
        self.assertIn('33 x 33', out)

    def test_a_drawing_smaller_than_the_panel_is_scaled_by_a_whole_number_and_centred(self):
        out = run_node("const f = new Array(10 * 10).fill('#000000'); f[0] = '#ff0000'; const r = P.toPanelFrame(f, 10, 10, hexToRgb); const lit = []; for (let i = 0; i < r.length; i += 3) if (r[i]) lit.push((i / 3) % 32 + ',' + Math.floor(i / 3 / 32)); console.log(JSON.stringify(lit));")
        # 10x10 scales by 3 (30 px), offset 1; the first drawing pixel covers x,y 1..3
        self.assertEqual(sorted(out), sorted(f'{x},{y}' for x in range(1, 4) for y in range(1, 4)))


@unittest.skipIf(NODE is None, 'Node is not installed')
class PanelPackets(unittest.TestCase):
    def test_window_framing_and_splitting(self):
        payload = bytes((i * 7) % 256 for i in range(30000))
        wins = run_node("const p = Uint8Array.from(JSON.parse(require('fs').readFileSync(0, 'utf8'))); console.log(JSON.stringify(P.gifWindows(p, 0).map((w) => Array.from(w))));", json.dumps(list(payload)))
        self.assertEqual(len(wins), 3, '12288 + 12288 + 5424')
        rebuilt = b''
        for i, w in enumerate(wins):
            w = bytes(w)
            self.assertEqual(struct.unpack('<H', w[:2])[0], len(w), 'the length prefix counts the whole packet, itself included')
            self.assertEqual(w[2:4], b'\x03\x00')
            self.assertEqual(w[4], 0 if i == 0 else 2, 'option: 0 for the first window, 2 after')
            self.assertEqual(struct.unpack('<I', w[5:9])[0], len(payload))
            self.assertEqual(struct.unpack('<I', w[9:13])[0], zlib.crc32(payload))
            self.assertEqual(w[13], 0x02, 'GIF tail byte')
            self.assertEqual(w[14], 0, 'slot 0: play without saving')
            rebuilt += w[15:]
        self.assertEqual(rebuilt, payload)

    def test_saving_to_a_slot_and_the_slot_commands(self):
        out = run_node("console.log(JSON.stringify([Array.from(P.gifWindows(Uint8Array.of(1,2,3), 7)[0]), Array.from(P.showSlotCmd(3)), Array.from(P.deleteSlotCmd(300))]));")
        self.assertEqual(out[0][14], 7, 'the slot byte follows the GIF tail byte')
        self.assertEqual(out[1], [7, 0, 8, 0x80, 1, 0, 3])
        self.assertEqual(out[2], [7, 0, 2, 1, 1, 0, 300 & 255], 'a slot number is one byte')

    def test_every_example_has_a_slot_gif(self):
        sizes = run_node("""
const fs = require('fs'); const src = fs.readFileSync(require('path').join(__dirname || '.', 'x'), 'utf8');
""".replace("const fs", "const fs") if False else "const m = {exports:{}}; new Function('module', require('fs').readFileSync(" + json.dumps(os.path.join(ROOT, 'web', 'js', 'examples_data.js')) + ", 'utf8') + ';module.exports={GG_EXAMPLES};')(m); console.log(JSON.stringify(m.exports.GG_EXAMPLES.map((e) => P.exampleGif(e, hexToRgb).length)));")
        self.assertGreaterEqual(len(sizes), 40)
        self.assertTrue(all(0 < n < 20000 for n in sizes))

    def test_text_windows_use_the_text_header(self):
        w = bytes(run_node("console.log(JSON.stringify(Array.from(P.textWindows([new Array(32).fill(0x8001)], 5, 80, 0, [255, 32, 32])[0])));"))
        self.assertEqual(w[2:4], b'\x00\x01')
        self.assertEqual(w[13], 0x00, 'text tail byte')

    def test_text_payload_layout(self):
        rows = [0x8001] + [0] * 31
        p = bytes(run_node("console.log(JSON.stringify(Array.from(P.textPayload([JSON.parse(process.argv[1])], 5, 80, 0, [255, 32, 16]))));".replace('process.argv[1]', json.dumps(json.dumps(rows)))))
        self.assertEqual(p[0], 1, 'one character cell')
        self.assertEqual(list(p[1:14]), [0, 1, 1, 5, 80, 0, 255, 32, 16, 0, 0, 0, 0], 'properties: anim 5, speed 80, colour')
        self.assertEqual(list(p[14:18]), [2, 255, 32, 16], 'character block: opcode, colour')
        self.assertEqual(list(p[18:20]), [0x01, 0x80], 'row 0 = 0x8001: each byte has its bits reversed')
        self.assertEqual(len(p), 14 + 4 + 64)


@unittest.skipIf(NODE is None, 'Node is not installed')
class PanelText(unittest.TestCase):
    def test_every_font_has_every_printable_character(self):
        r = run_node("""
const bad = [];
for (const n of P.FONT_NAMES) {
  const f = FONTS[n]; if (!f) { bad.push('missing ' + n); continue; }
  for (let c = 32; c < 127; c++) {
    const ch = String.fromCharCode(c);
    if (typeof f.cell[ch] !== 'string' || f.cell[ch].length !== 128) bad.push(n + ' cell ' + ch);
    for (const [sz, t] of Object.entries(f.fit)) { const g = t.g[ch]; if (!g || g[1].length !== t.h * ((g[0] + 3) >> 2)) bad.push(n + ' ' + sz + ' ' + ch); }
  }
}
console.log(JSON.stringify(bad));""")
        self.assertEqual(r, [])

    def test_still_text_fits_on_the_panel_in_every_font(self):
        r = run_node("""
const out = {};
for (const n of P.FONT_NAMES) for (const t of ['hi', 'happy', 'love you', 'Welcome home', 'abcdefghijklmnop', 'a very long sentence that cannot fit nicely']) {
  const f = P.fitRows(FONTS, n, t, true);
  out[n + '|' + t] = { rows: f.cells.map((c) => c.length), max: Math.max(...f.cells.flat()), lit: f.cells.flat().filter((v) => v).length, lines: f.lines, h: f.letterHeight };
}
console.log(JSON.stringify(out));""")
        for key, v in r.items():
            with self.subTest(key=key):
                self.assertEqual(v['rows'], [32, 32])
                self.assertLessEqual(v['max'], 0xffff)
                self.assertGreater(v['lit'], 0, 'something is drawn')

    def test_love_you_is_two_lines_and_a_short_word_is_one(self):
        r = run_node("console.log(JSON.stringify([P.fitRows(FONTS, 'DejaVu Bold', 'love you', true).lines, P.fitRows(FONTS, 'DejaVu Bold', 'happy', true).lines, P.fitRows(FONTS, 'DejaVu Bold', 'happy', false).lines]));")
        self.assertEqual(r[0], ['love', 'you'])
        self.assertEqual(r[1], ['happy'])
        self.assertEqual(r[2], ['hap', 'py'], 'Auto picks the bigger letters over one line')

    def test_a_moving_character_is_a_16x32_cell(self):
        r = run_node("console.log(JSON.stringify(P.cellRows(FONTS, 'Jersey 15', 'h')));")
        self.assertEqual(len(r), 32)
        self.assertTrue(all(0 <= v <= 0xffff for v in r))
        self.assertTrue(any(r))


if __name__ == '__main__':
    unittest.main()
