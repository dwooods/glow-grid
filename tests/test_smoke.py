"""Browser smoke test for the Glow Grid editor (web/). Covers regressions we have already hit:
 import naming (_sprite), the Save button with a stubbed picker, the ESP32-C3 .gg export, the Help dialog, and a saved sheet restoring its frames.

Run by hand before pushing a web/ change (not in CI):
    pip install playwright pillow && playwright install chromium
    python3 -m unittest tests.test_smoke -v        (from the repo root)
Skips itself if Playwright is missing. The service worker is blocked so tests always see the files on disk.
"""
import functools, http.server, os, tempfile, threading, unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAME_COLORS = [(200, 30, 30), (30, 200, 30), (30, 30, 200), (200, 200, 30)]

STUB = """() => { window.__w = []; window.__calls = 0;
  window.showSaveFilePicker = async (o) => { window.__calls++; window.__opts = o;
    if (window.__mode === 'abort') { const e = new Error('x'); e.name = 'AbortError'; throw e; }
    if (window.__mode === 'err') throw new Error('nope');
    return { name: o.suggestedName, createWritable: async () => ({ write: async (b) => { window.__w.push(b); }, close: async () => {} }) }; } }"""
SET_NAME = "v => { const e = document.getElementById('nameInput'); e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); }"


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@unittest.skipIf(sync_playwright is None, 'playwright not installed')
class Smoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=os.path.join(ROOT, 'web')))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.srv.server_address[1]}/index.html'
        cls.tmp = tempfile.TemporaryDirectory()
        t = cls.tmp.name
        cls.photo = os.path.join(t, 'sunset.png')   # smooth gradient, larger than the grid: opens the crop dialog
        im = Image.new('RGB', (120, 120)); im.putdata([(x * 2, y * 2, 120) for y in range(120) for x in range(120)]); im.save(cls.photo)
        cls.cat = os.path.join(t, 'cat_sprite.png'); im.save(cls.cat)
        cls.walk = os.path.join(t, 'walk_4fps.png')  # sheet recognised by its name
        sheet = Image.new('RGB', (64, 16))
        for i, c in enumerate(FRAME_COLORS):
            sheet.paste(Image.new('RGB', (16, 16), c), (i * 16, 0))
        sheet.save(cls.walk)
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.srv.shutdown(); cls.tmp.cleanup()

    def setUp(self):
        self.ctx = self.browser.new_context(viewport={'width': 1200, 'height': 1000}, accept_downloads=True, service_workers='block')
        self.pg = self.ctx.new_page()
        self.pg.add_init_script('delete window.showSaveFilePicker')  # Chromium has a real picker that would hang; the stub test adds its own
        self.errors = []
        self.pg.on('pageerror', lambda e: self.errors.append(str(e)))
        self.pg.goto(self.url); self.pg.wait_for_timeout(400)

    def tearDown(self):
        self.assertEqual(self.errors, [], 'page errors')
        self.ctx.close()

    # helpers
    def name(self): return self.pg.evaluate("document.getElementById('nameInput').value")
    def set_name(self, v): self.pg.evaluate(SET_NAME, v)
    def status(self): return self.pg.evaluate("document.getElementById('statusEl').textContent")
    def import_file(self, path):
        self.pg.set_input_files('#imageInput', path); self.pg.wait_for_timeout(500)
    def dialog_open(self): return self.pg.evaluate("document.getElementById('photoDlg').open")
    def click_save(self): self.pg.evaluate("document.getElementById('exportBtn').click()")
    def set_target(self, v): self.pg.evaluate("v => { const e = document.getElementById('targetInput'); e.value = v; e.dispatchEvent(new Event('change', {bubbles: true})); }", v)

    def test_photo_names_sprite_on_apply_and_cancel_keeps_name(self):
        self.set_name('mine')
        self.import_file(self.photo)
        self.assertTrue(self.dialog_open())
        self.assertEqual(self.name(), 'mine', 'name must not change while the crop dialog is open')
        self.pg.click('#photoCancel'); self.pg.wait_for_timeout(200)
        self.assertEqual(self.name(), 'mine', 'Cancel keeps the name')
        self.import_file(self.photo); self.pg.click('#photoApply'); self.pg.wait_for_timeout(300)
        self.assertEqual(self.name(), 'sunset_sprite')

    def test_sheet_by_filename_and_no_double_suffix(self):
        self.import_file(self.walk)
        self.assertEqual(self.name(), 'walk_sprite')
        self.assertEqual(self.pg.evaluate('state.frames.length'), 4)
        self.import_file(self.cat)
        if self.dialog_open():
            self.pg.click('#photoApply'); self.pg.wait_for_timeout(300)
        self.assertEqual(self.name(), 'cat_sprite')

    def test_save_with_stubbed_picker(self):
        self.pg.evaluate(STUB); self.set_name('custom')
        self.pg.evaluate("window.__mode = 'ok'"); self.click_save(); self.pg.wait_for_timeout(500)
        self.assertEqual(self.pg.evaluate('window.__calls'), 1)
        self.assertEqual(self.pg.evaluate('window.__opts.suggestedName'), 'custom.png')
        self.assertIn('Saved custom.png', self.status())
        written = self.pg.evaluate("(async () => { const a = new Uint8Array(await window.__w[0].arrayBuffer()); return [Array.from(a.slice(1, 4)), new TextDecoder('latin1').decode(a).includes('glow-grid')]; })()")
        self.assertEqual(written, [[0x50, 0x4e, 0x47], True], 'a PNG carrying the glow-grid chunk')
        self.pg.evaluate("window.__w = []; window.__mode = 'abort'"); self.click_save(); self.pg.wait_for_timeout(400)
        self.assertEqual(self.status(), 'Save cancelled.')
        self.assertEqual(self.pg.evaluate('window.__w.length'), 0)
        self.pg.evaluate("window.__mode = 'err'")  # picker failure falls back to a plain download
        with self.pg.expect_download() as d: self.click_save()
        self.assertEqual(d.value.suggested_filename, 'custom.png')
        self.pg.evaluate("delete window.showSaveFilePicker")  # no picker (Firefox, Safari): plain download
        with self.pg.expect_download() as d: self.click_save()
        self.assertEqual(d.value.suggested_filename, 'custom.png')

    def test_c3_target_saves_gg_file(self):
        self.pg.evaluate(STUB); self.set_name('custom')
        self.pg.evaluate("""() => { const n = state.cols * state.rows; state.frames = [new Array(n).fill('#ff8800'), new Array(n).fill('#000000')];
            state.currentFrame = 0; state.fps = 7.25; afterFrameChange(); }""")
        self.set_target('c3')  # the select lives in the Export dialog, which is closed here
        self.pg.evaluate("window.__mode = 'ok'"); self.click_save(); self.pg.wait_for_timeout(500)
        self.assertEqual(self.pg.evaluate('window.__opts.suggestedName'), 'custom.gg')
        self.assertIn('Saved custom.gg (2 frames, 1,548 bytes)', self.status())
        head = self.pg.evaluate("(async () => Array.from(new Uint8Array(await window.__w[0].arrayBuffer()).slice(0, 15)))()")
        self.assertEqual(head, [0x47, 0x47, 1, 0, 16, 16, 2, 0, 72, 0, 30, 22, 0xff, 0x88, 0x00], 'header: 2 frames, 72 (7.25 fps rounds half to even), 30%, 2.2; first pixel')
        self.pg.evaluate("delete window.showSaveFilePicker")  # no picker: plain download, .gg name
        with self.pg.expect_download() as d: self.click_save()
        self.assertEqual(d.value.suggested_filename, 'custom.gg')
        self.pg.evaluate("() => { state.cols = 8; state.rows = 32; afterFrameChange(); }")  # wrong size is refused, nothing saved
        self.pg.evaluate("window.__w = []"); self.pg.evaluate(STUB); self.click_save(); self.pg.wait_for_timeout(300)
        self.assertIn('16×16', self.status()); self.assertEqual(self.pg.evaluate('window.__w.length'), 0)
        self.set_target('pi')

    def test_saved_sheet_restores_frames_under_another_name(self):
        self.pg.evaluate("""() => { const n = state.cols * state.rows; const cols = ['#ff0000', '#00ff00', '#0000ff'];
            state.frames = cols.map((c) => new Array(n).fill(c)); state.currentFrame = 0; state.fps = 5; afterFrameChange(); }""")
        self.set_name('trio')
        with self.pg.expect_download() as d: self.click_save()
        saved = os.path.join(self.tmp.name, 'renamed_anything.png'); d.value.save_as(saved)
        self.pg.evaluate("() => { state.frames = [state.frames[0]]; state.currentFrame = 0; state.fps = 6; afterFrameChange(); }")
        self.import_file(saved)
        self.assertEqual(self.pg.evaluate('state.frames.length'), 3, 'frame count comes from inside the PNG, not the file name')
        self.assertEqual(self.pg.evaluate('state.fps'), 5)
        self.assertEqual(self.pg.evaluate('state.frames.map((f) => f[0])'), ['#ff0000', '#00ff00', '#0000ff'])
        self.assertEqual(self.name(), 'renamed_anything_sprite')

    def test_help_dialog_renders(self):
        self.pg.click('#helpBtn'); self.pg.wait_for_timeout(200)
        self.assertTrue(self.pg.evaluate("document.getElementById('helpDlg').open"))
        heads = self.pg.evaluate("Array.from(document.querySelectorAll('#helpBody h3')).map((h) => h.textContent)")
        for h in ('Works well', 'Drawing tools', 'Drawing on a phone', 'Getting a picture onto the panel', 'Watch out for'):
            self.assertIn(h, heads)
        self.assertGreater(self.pg.evaluate("document.getElementById('helpBody').textContent.length"), 3000)


if __name__ == '__main__':
    unittest.main()
