"""Browser smoke test for the Glow Grid editor (web/). Covers regressions we have already hit:
 import naming (_sprite), the Save button with a stubbed picker, the ESP32-C3 .gg export (plain frames and with a still part), the Board card against a fake board, the Help dialog, and a saved sheet restoring its frames.

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
# A fake ESP32-C3 behind the Board card's transport interface: the same line protocol c3/c3_player.ino speaks,
# with sprites kept in a Map. Installed with page.add_init_script so board.js finds window.__ggFakeSerial at load.
FAKE_BOARD = """() => {
  window.__fakeStore = new Map(); window.__fakePanel = 'on'; window.__fakeCurrent = '-'; window.__fakeLog = []; window.__fakeRotate = 0;
  window.__fakeChunks = []; window.__fakeBreak = null; window.__fakeFw = 7;     // 'full': PUT refused after READY; 'mute': no replies at all
  window.__ggFakeSerial = () => {
    const t = { onLine: null, onClose: null, closed: false, pending: null };
    window.__fakeTransport = t;
    const say = (l) => setTimeout(() => t.onLine && t.onLine(l), 0);
    const crc32 = (b) => { let c = 0xffffffff; for (let i = 0; i < b.length; i++) { c ^= b[i]; for (let k = 0; k < 8; k++) c = (c >>> 1) ^ (0xedb88320 & -(c & 1)); } return (c ^ 0xffffffff) >>> 0; };
    t.open = async () => {};
    t.close = async () => { if (t.closed) return; t.closed = true; if (t.onClose) t.onClose(); };
    t.write = async (bytes) => {
      if (t.pending) {                                   // raw sprite bytes of a PUT in progress
        const p = t.pending; p.buf.set(bytes, p.got); p.got += bytes.length; window.__fakeChunks.push(bytes.length);
        if (window.__fakeBreak === 'full') { t.pending = null; return say('ERR not enough space'); }
        if (p.got < p.size) { if (p.got - p.acked >= 1024) { p.acked = p.got; say('A'); } return; }
        t.pending = null;
        if (crc32(p.buf) !== p.crc) return say('ERR checksum mismatch');
        if (!(p.buf[0] === 0x47 && p.buf[1] === 0x47)) return say('ERR invalid sprite: bad magic');
        window.__fakeStore.set(p.name, p.buf); window.__fakeCurrent = p.name; window.__fakePanel = 'on';
        return say('OK saved ' + p.name);
      }
      const line = new TextDecoder().decode(bytes).trim(); window.__fakeLog.push(line);
      if (window.__fakeBreak === 'mute') return;
      const [cmd, a1, a2, a3] = line.split(' ');
      const names = () => [...window.__fakeStore.keys()].sort();
      switch (cmd) {
        case 'PING': return say('PONG');
        case 'LIST': for (const n of names()) say('FILE ' + n + ' ' + window.__fakeStore.get(n).length); return say('OK ' + names().length + ' files, 1400000 bytes free');
        case 'CRC': if (window.__fakeFw < 7) return say('ERR unknown command'); if (!window.__fakeStore.has(a1)) return say('ERR no such sprite');
          return say('OK crc=' + crc32(window.__fakeStore.get(a1)).toString(16).padStart(8, '0') + ' size=' + window.__fakeStore.get(a1).length);
        case 'INFO': return say('OK fw=' + window.__fakeFw + ' current=' + window.__fakeCurrent + ' sprites=' + names().length + ' panel=' + window.__fakePanel + ' rotate=' + window.__fakeRotate);
        case 'ROTATE': if (!/^\\d+$/.test(a1 || '')) return say('ERR usage: ROTATE <seconds>'); window.__fakeRotate = Number(a1); return say('OK rotate ' + a1);
        case 'PUT': if (!/^[A-Za-z0-9_-]{1,31}$/.test(a1)) return say('ERR bad name');
          if (!window.__fakeStore.has(a1) && window.__fakeStore.size >= 64) return say('ERR board holds 64 sprites; delete one first');
          t.pending = { name: a1, size: Number(a2), crc: parseInt(a3, 16), buf: new Uint8Array(Number(a2)), got: 0, acked: 0 }; return say('READY');
        case 'SHOW': if (!window.__fakeStore.has(a1)) return say('ERR no such sprite'); window.__fakeCurrent = a1; window.__fakePanel = 'on'; return say('OK showing ' + a1);
        case 'DEL': if (!window.__fakeStore.has(a1)) return say('ERR no such sprite'); window.__fakeStore.delete(a1);
          if (window.__fakeCurrent === a1) window.__fakeCurrent = names()[0] || '-'; return say('OK deleted ' + a1);
        case 'OFF': window.__fakePanel = 'off'; return say('OK panel off');
        case 'ON': window.__fakePanel = 'on'; return say('OK panel on');
        default: return say('ERR unknown command');
      }
    };
    return t;
  };
}"""

# A fake Web Serial port built on real browser streams, so SerialTransport's open/read/write/close order is exercised
# for real: like Chrome, close() refuses while a stream is locked. Installed by overriding navigator.serial.requestPort.
FAKE_PORT = """() => {
  window.__port = null;
  const mk = () => {
    let ctrl = null; const enc = new TextEncoder(), dec = new TextDecoder();
    const say = (l) => { try { ctrl.enqueue(enc.encode(l + '\\n')); } catch (e) {} };
    const p = { opened: false, closed: false, signals: null, writes: [] };
    p.readable = new ReadableStream({ start(c) { ctrl = c; }, cancel() { p.readCancelled = true; } });
    p.writable = new WritableStream({ write(chunk) {
      const line = dec.decode(chunk).trim(); p.writes.push(line);
      if (line === 'PING') say('PONG');
      else if (line === 'LIST') say('OK 0 files, 1400000 bytes free');
      else if (line === 'INFO') say('OK fw=3 current=- sprites=0 panel=on');
      else say('ERR unknown command');
    } });
    p.open = async () => { p.opened = true; };
    p.setSignals = async (s) => { p.signals = s; };
    p.close = async () => {
      if (p.readable.locked || p.writable.locked) throw new TypeError('Cannot close a port with a locked stream');
      p.closed = true;
    };
    return p;
  };
  navigator.serial.requestPort = async () => { window.__port = mk(); return window.__port; };
}"""

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

    def test_c3_export_combines_the_still_part(self):
        # Two frames that share a body and differ in one pixel; "Animate one part only" moves the body into the
        # still part and leaves the frames mostly black. The .gg must still carry the combined picture, like the PNG.
        self.pg.evaluate(STUB); self.set_name('parts')
        self.pg.evaluate("""() => { const n = state.cols * state.rows;
            const f0 = new Array(n).fill('#336699'), f1 = new Array(n).fill('#336699');
            f0[5] = '#ff0000'; f1[5] = '#00ff00';
            state.frames = [f0, f1]; state.currentFrame = 0; state.fps = 4; afterFrameChange(); }""")
        self.assertTrue(self.pg.evaluate('separateStill()'))
        self.assertEqual(self.pg.evaluate("state.frames[0].filter((h) => h !== '#000000').length"), 1, 'frame holds only the moving pixel')
        self.set_target('c3')
        self.pg.evaluate("window.__mode = 'ok'"); self.click_save(); self.pg.wait_for_timeout(500)
        px = self.pg.evaluate("(async () => Array.from(new Uint8Array(await window.__w[0].arrayBuffer()).slice(12)))()")
        self.assertEqual(len(px), 2 * 768)
        self.assertEqual(px[0:3], [0x33, 0x66, 0x99], 'body pixel comes from the still part')
        self.assertEqual(px[15:18], [0xff, 0, 0], 'frame 1 moving pixel')
        self.assertEqual(px[768 + 15:768 + 18], [0, 0xff, 0], 'frame 2 moving pixel')
        blacks = sum(1 for i in range(0, len(px), 3) if px[i:i + 3] == [0, 0, 0])
        self.assertEqual(blacks, 0, 'no black pixel anywhere: every pixel is body or the moving one')
        self.set_target('pi')

    def fresh_page(self, *init_scripts):
        """A new page whose init scripts run before board.js, which reads its environment at load."""
        self.ctx.close()
        self.ctx = self.browser.new_context(viewport={'width': 1200, 'height': 1000}, service_workers='block')
        self.pg = self.ctx.new_page(); self.pg.add_init_script('delete window.showSaveFilePicker')
        for js in init_scripts:
            self.pg.add_init_script(js)
        self.pg.on('pageerror', lambda e: self.errors.append(str(e)))
        self.pg.goto(self.url); self.pg.wait_for_timeout(400)

    def test_board_card_with_a_fake_board(self):
        self.fresh_page(f'({FAKE_BOARD})()')
        status = lambda: self.pg.evaluate("document.getElementById('boardStatus').textContent")
        rows = lambda: self.pg.evaluate("Array.from(document.querySelectorAll('#boardList .board-row .board-name')).map((e) => e.textContent)")
        self.assertTrue(self.pg.evaluate("document.getElementById('boardUnsupported').hidden"), 'supported: no warning')
        self.assertFalse(self.pg.evaluate("document.getElementById('boardConnectBtn').disabled"))
        self.assertIn('ESP32-C3', self.pg.evaluate("document.querySelector('#boardCard .board-purpose').textContent"), 'a first-time user is told what the card is for')
        self.assertTrue(self.pg.evaluate("document.getElementById('boardTools').hidden"), 'tools hidden until connected')
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        self.assertEqual(status(), 'Connected. Firmware 7.')
        self.assertEqual(rows(), [])
        self.assertIn('Nothing stored', self.pg.evaluate("document.getElementById('boardList').textContent"))
        # a blank drawing is refused before anything is sent (the page opens on one black frame)
        self.set_name('flower')
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(300)
        self.assertIn('blank', status()); self.assertEqual(self.pg.evaluate("window.__fakeLog.filter((l) => l.startsWith('PUT')).length"), 0)
        # send the drawing: the bytes on the board are exactly what Export for ESP32-C3 would write
        self.pg.evaluate("""() => { const n = state.cols * state.rows; state.frames = [new Array(n).fill('#ff8800'), new Array(n).fill('#0000ff')];
            state.currentFrame = 0; state.fps = 5; afterFrameChange(); }""")
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertIn('Sent flower (2 frames, 1,548 bytes)', status())
        self.assertEqual(rows(), ['flower'])
        stored = self.pg.evaluate("Array.from(window.__fakeStore.get('flower'))")
        want = self.pg.evaluate("Array.from(ggBytes(state.frames.map(flatten), 16, 16, state.fps, sim.brightness, sim.gamma))")
        self.assertEqual(stored, want)
        self.assertTrue(self.pg.evaluate("document.querySelector('#boardList .board-row').classList.contains('playing')"))
        # a second sprite, play the first, panel off and on, delete
        self.set_name('owl'); self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertEqual(rows(), ['flower', 'owl'])
        self.pg.click("#boardList .board-row:nth-child(1) button:has-text('Play')"); self.pg.wait_for_timeout(400)
        self.assertEqual(status(), 'Playing flower.')
        self.assertEqual(self.pg.evaluate('window.__fakeCurrent'), 'flower')
        self.assertTrue(self.pg.evaluate("document.getElementById('boardOnBtn').disabled"), 'already on')
        self.pg.click('#boardOffBtn'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakePanel'), 'off')
        self.assertIn('Lights off', status())
        self.assertTrue(self.pg.evaluate("document.getElementById('boardOffBtn').disabled"))
        self.assertFalse(self.pg.evaluate("document.getElementById('boardOnBtn').disabled"))
        self.pg.click('#boardOnBtn'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakePanel'), 'on')
        # rotate: the select sends ROTATE and then shows what the board reports; an unlisted board value gets its own entry
        self.assertEqual(self.pg.evaluate("document.getElementById('boardRotate').value"), '0')
        self.pg.select_option('#boardRotate', '300'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakeRotate'), 300)
        self.assertIn('Rotating every 5 min', status())
        self.pg.evaluate('window.__fakeRotate = 45'); self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate("document.getElementById('boardRotate').value"), '45')
        self.assertEqual(self.pg.evaluate("document.getElementById('boardRotate').selectedOptions[0].textContent"), 'every 45 s')
        self.pg.select_option('#boardRotate', '0'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakeRotate'), 0); self.assertIn('Rotation off', status())
        self.pg.on('dialog', lambda d: d.accept())
        self.pg.click("#boardList .board-row:nth-child(2) button:has-text('Delete')"); self.pg.wait_for_timeout(400)
        self.assertEqual(rows(), ['flower'])
        self.assertEqual(status(), 'Deleted owl.')
        # the name is the Export name, trimmed to the board's 31-character limit
        self.set_name('a' * 40); self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertIn('a' * 31, rows())
        # wrong grid size is refused before anything is sent
        before = self.pg.evaluate('window.__fakeLog.length')
        self.pg.evaluate("() => { state.cols = 8; state.rows = 32; afterFrameChange(); }")
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(300)
        self.assertIn('16×16', status()); self.assertEqual(self.pg.evaluate('window.__fakeLog.length'), before)
        self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(300)
        self.assertEqual(status(), 'Board disconnected.')
        self.assertTrue(self.pg.evaluate("document.getElementById('boardTools').hidden"))

    SEED = """(n) => { for (const k of n) window.__fakeStore.set(k, new Uint8Array([0x47, 0x47, ...new Array(10 + k.length).fill(1)])); }"""

    def board_helpers(self):
        self.status = lambda: self.pg.evaluate("document.getElementById('boardStatus').textContent")
        self.rows = lambda: self.pg.evaluate("Array.from(document.querySelectorAll('#boardList .board-row .board-name')).map((e) => e.textContent)")
        self.pager = lambda: self.pg.evaluate("""() => ({hidden: document.getElementById('boardPager').hidden, info: document.getElementById('boardPageInfo').textContent,
            prev: document.getElementById('boardPrevBtn').disabled, next: document.getElementById('boardNextBtn').disabled})""")
        self.store = lambda: self.pg.evaluate("[...window.__fakeStore.keys()].sort()")
        self.puts = lambda: self.pg.evaluate("window.__fakeLog.filter((l) => l.startsWith('PUT')).length")

    def connect(self, seed=()):
        self.pg.evaluate(self.SEED, list(seed))
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)

    def test_board_list_pages_of_five(self):
        self.fresh_page(f'({FAKE_BOARD})()'); self.board_helpers()
        self.pg.on('dialog', lambda d: d.accept())
        names = [f's{i:02d}' for i in range(12)]
        self.connect(names)
        self.assertEqual(self.rows(), names[:5], 'five rows, not twelve')
        self.assertEqual(self.pager(), {'hidden': False, 'info': '1–5 of 12', 'prev': True, 'next': False})
        self.pg.click('#boardNextBtn')
        self.assertEqual(self.rows(), names[5:10]); self.assertEqual(self.pager()['info'], '6–10 of 12')
        self.assertFalse(self.pager()['prev'])
        self.pg.click('#boardNextBtn')
        self.assertEqual(self.rows(), names[10:]); self.assertEqual(self.pager(), {'hidden': False, 'info': '11–12 of 12', 'prev': False, 'next': True})
        # Play works on a later page and the page stays put after the refresh
        self.pg.click("#boardList .board-row:nth-child(2) button:has-text('Play')"); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakeCurrent'), 's11')
        self.assertEqual(self.rows(), names[10:])
        self.assertTrue(self.pg.evaluate("document.querySelector('#boardList .board-row.playing .board-name').textContent === 's11'"))
        # deleting everything on the last page falls back to the page before it, not an empty page
        self.pg.click("#boardList .board-row:nth-child(1) button:has-text('Delete')"); self.pg.wait_for_timeout(400)
        self.pg.click("#boardList .board-row:nth-child(1) button:has-text('Delete')"); self.pg.wait_for_timeout(400)
        self.assertEqual(self.rows(), names[5:10])
        self.assertEqual(self.pager()['info'], '6–10 of 10')
        # five or fewer: no pager at all
        for n in names[5:10]:
            self.pg.evaluate("n => window.__fakeStore.delete(n)", n)
        self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.rows(), names[:5]); self.assertTrue(self.pager()['hidden'])
        # Send jumps to the page holding the new sprite (its name sorts last here)
        for n in ['t1', 't2', 't3']:
            self.pg.evaluate("n => window.__fakeStore.set(n, new Uint8Array([0x47, 0x47]))", n)
        self.set_name('zz')
        self.pg.evaluate("""() => { const n = state.cols * state.rows; state.frames = [new Array(n).fill('#ff8800')]; state.currentFrame = 0; afterFrameChange(); }""")
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertEqual(self.rows(), ['t1', 't2', 't3', 'zz'], 'the new sprite sorts last, so the card shows the last page')
        self.assertEqual(self.pager()['info'], '6–9 of 9')
        self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(300)
        self.assertTrue(self.pager()['hidden'], 'no pager once disconnected')

    def test_add_and_remove_examples(self):
        self.fresh_page(f'({FAKE_BOARD})()'); self.board_helpers()
        answer = {'ok': True}
        self.pg.on('dialog', lambda d: d.accept() if answer['ok'] else d.dismiss())
        total = self.pg.evaluate('GG_EXAMPLES.length')
        self.assertEqual(total, 15)
        self.assertTrue(self.pg.evaluate("document.getElementById('boardExamples').hidden"), 'hidden until connected')
        self.connect(['mine'])
        self.assertFalse(self.pg.evaluate("document.getElementById('boardExamples').hidden"))
        self.pg.evaluate("window.__fakeCurrent = 'mine'")
        self.pg.click('#boardRemoveExBtn'); self.pg.wait_for_timeout(300)
        self.assertEqual(self.status(), 'No examples are on the board.')
        # add: every example lands byte-for-byte as Export would write it; the sprite that was playing keeps playing
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(4000)
        self.assertEqual(self.status(), f'Added {total} examples.')
        self.assertEqual(len(self.store()), total + 1)
        self.assertEqual(self.pg.evaluate("GG_EXAMPLES.every((e) => { const b = window.__fakeStore.get(e.name); const w = ggExampleBytes(e); return b && b.length === w.length && b.every((v, i) => v === w[i]); })"), True)
        self.assertEqual(self.pg.evaluate('window.__fakeCurrent'), 'mine')
        self.assertEqual(self.pager()['info'], '1–5 of 16', 'the examples page like everything else')
        # add again: nothing is sent
        before = self.puts()
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.status(), f'All {total} examples are already on the board.'); self.assertEqual(self.puts(), before)
        # you changed one and replaced another with your own drawing: remove deletes the rest and says what it kept
        self.pg.evaluate("""() => { const a = GG_EXAMPLES[0].name, b = GG_EXAMPLES[1].name;
            const x = ggExampleBytes(GG_EXAMPLES[0]).slice(); x[20] ^= 1; window.__fakeStore.set(a, x);
            window.__fakeStore.set(b, new Uint8Array([0x47, 0x47, 1, 2, 3])); }""")
        answer['ok'] = False
        self.pg.click('#boardRemoveExBtn'); self.pg.wait_for_timeout(300)
        self.assertEqual(self.status(), 'Nothing removed.'); self.assertEqual(len(self.store()), total + 1)
        answer['ok'] = True
        self.pg.click('#boardRemoveExBtn'); self.pg.wait_for_timeout(3000)
        kept = self.pg.evaluate('[GG_EXAMPLES[0].name, GG_EXAMPLES[1].name]')
        self.assertEqual(self.store(), sorted(['mine'] + kept))
        self.assertEqual(self.status(), f'Removed {total - 2} examples. Kept 2 you changed: {kept[0]}, {kept[1]}.')
        self.assertEqual(self.pg.evaluate('window.__fakeCurrent'), 'mine')
        # add never replaces: the two changed ones stay as they are
        edited = self.pg.evaluate("Array.from(window.__fakeStore.get(GG_EXAMPLES[0].name))")
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(4000)
        self.assertEqual(self.status(), f'Added {total - 2} examples; 2 already on the board were left alone.')
        self.assertEqual(self.pg.evaluate("Array.from(window.__fakeStore.get(GG_EXAMPLES[0].name))"), edited)

    def test_examples_old_firmware_full_board_and_errors(self):
        self.fresh_page(f'({FAKE_BOARD})()'); self.board_helpers()
        self.pg.on('dialog', lambda d: d.accept())
        # firmware before 7 has no CRC: Add still works, Remove refuses rather than guess, and deletes nothing
        self.pg.evaluate('window.__fakeFw = 6')
        self.connect()
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(4000)
        n = len(self.store()); self.assertEqual(n, 15)
        self.pg.click('#boardRemoveExBtn'); self.pg.wait_for_timeout(400)
        self.assertIn('firmware 7', self.status()); self.assertEqual(len(self.store()), n)
        self.assertEqual(self.pg.evaluate("window.__fakeLog.filter((l) => l.startsWith('CRC') || l.startsWith('DEL')).length"), 0)
        self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(300)
        # a board with no room for all of them: nothing is sent, and the message says why
        self.pg.evaluate("() => { window.__fakeFw = 7; window.__fakeStore.clear(); }")
        self.pg.evaluate(self.SEED, [f'p{i:02d}' for i in range(55)])
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        before = self.puts()
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(400)
        self.assertIn('would not fit', self.status()); self.assertEqual(self.puts(), before); self.assertEqual(len(self.store()), 55)
        self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(300)
        # the board refuses mid-way (no space): the card reports how far it got and shows what is there
        self.pg.evaluate("() => { window.__fakeStore.clear(); window.__fakeBreak = 'full'; }")
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(800)
        self.assertIn('not enough space', self.status()); self.assertIn('Added 0 of 15', self.status())
        self.assertFalse(self.pg.evaluate("document.getElementById('boardAddExBtn').disabled"), 'buttons come back after an error')
        self.assertFalse(self.pg.evaluate("document.getElementById('boardSendBtn').disabled"))

    def test_board_card_long_sprites_replace_and_errors(self):
        self.fresh_page(f'({FAKE_BOARD})()')
        status = lambda: self.pg.evaluate("document.getElementById('boardStatus').textContent")
        rows = lambda: self.pg.evaluate("Array.from(document.querySelectorAll('#boardList .board-row .board-name')).map((e) => e.textContent)")
        frames = lambda n: self.pg.evaluate("""(n) => { const px = state.cols * state.rows; state.frames = Array.from({length: n}, (_, i) => new Array(px).fill(i % 2 ? '#ff0000' : '#00ff00'));
            state.currentFrame = 0; state.fps = 8; afterFrameChange(); }""", n)
        answer = {'ok': True}
        self.pg.on('dialog', lambda d: d.accept() if answer['ok'] else d.dismiss())
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        # a 4-frame sprite is 3,084 bytes: four chunks, three acks, bytes intact
        self.set_name('walk'); frames(4)
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(1000)
        self.assertIn('Sent walk (4 frames, 3,084 bytes)', status())
        self.assertEqual(self.pg.evaluate('window.__fakeChunks'), [1024, 1024, 1024, 12])
        self.assertEqual(self.pg.evaluate("Array.from(window.__fakeStore.get('walk'))"),
                         self.pg.evaluate("Array.from(ggBytes(state.frames.map(flatten), 16, 16, state.fps, sim.brightness, sim.gamma))"))
        # sending the same name again asks first; No sends nothing, Yes replaces: still one row, new bytes
        frames(1); answer['ok'] = False
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(500)
        self.assertEqual(status(), 'Not sent.')
        self.assertEqual(self.pg.evaluate("window.__fakeStore.get('walk').length"), 3084)
        answer['ok'] = True
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertEqual(rows(), ['walk'])
        self.assertEqual(self.pg.evaluate("window.__fakeStore.get('walk').length"), 780)
        # too many frames is refused before anything is sent
        before = self.pg.evaluate('window.__fakeLog.length')
        frames(65); self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(300)
        self.assertIn('up to 64 frames', status()); self.assertEqual(self.pg.evaluate('window.__fakeLog.length'), before)
        # the board refuses mid-upload: its message is shown and the Send button comes back
        frames(1); self.set_name('nope'); self.pg.evaluate("window.__fakeBreak = 'full'")
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertEqual(status(), 'Board said: not enough space')
        self.assertFalse(self.pg.evaluate("document.getElementById('boardSendBtn').disabled"))
        self.assertEqual(rows(), ['walk'])
        # the board goes silent: the command times out with a message instead of hanging
        self.pg.evaluate("window.__fakeBreak = 'mute'")
        self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(4600)
        self.assertEqual(status(), 'Board said: no reply from the board')
        self.pg.evaluate("window.__fakeBreak = null")
        # the cable is pulled in the middle of a Send: the card resets itself, the upload fails at once,
        # and no timer fires later to overwrite the message
        self.set_name('cut'); self.pg.evaluate("window.__fakeBreak = 'mute'")
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(200)
        self.assertIn('Sending cut', status())
        self.pg.evaluate("window.__fakeTransport.close()"); self.pg.wait_for_timeout(300)
        self.assertEqual(status(), 'Board disconnected.')
        self.assertTrue(self.pg.evaluate("document.getElementById('boardTools').hidden"))
        self.assertFalse(self.pg.evaluate("document.getElementById('boardConnectBtn').hidden"))
        self.assertFalse(self.pg.evaluate("document.getElementById('boardSendBtn').disabled"))
        self.pg.wait_for_timeout(4500)
        self.assertEqual(status(), 'Board disconnected.', 'the 4 s command timeout must not fire after a disconnect')
        self.assertEqual(self.errors, [])

    def test_serial_transport_releases_the_port_on_disconnect(self):
        # 2026-10-15: Disconnect left COM3 held until the tab was closed, so the Arduino IDE could not flash.
        self.fresh_page(FAKE_PORT.replace('() => {', '(() => {', 1) + ')()')
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(800)
        self.assertEqual(self.pg.evaluate("document.getElementById('boardStatus').textContent"), 'Connected. Firmware 3.')
        self.assertEqual(self.pg.evaluate('window.__port.signals'), {'dataTerminalReady': True, 'requestToSend': False})
        self.assertEqual(self.pg.evaluate('window.__port.writes.slice(0, 3)'), ['PING', 'LIST', 'INFO'])
        self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(500)
        self.assertTrue(self.pg.evaluate('window.__port.closed'), 'port.close() must succeed: both streams unlocked first')
        self.assertFalse(self.pg.evaluate('window.__port.readable.locked'))
        self.assertFalse(self.pg.evaluate('window.__port.writable.locked'))
        self.assertEqual(self.pg.evaluate("document.getElementById('boardStatus').textContent"), 'Board disconnected.')
        self.assertEqual(self.pg.evaluate("document.getElementById('boardFree').textContent"), '')
        self.assertEqual(self.errors, [])

    def test_board_card_without_web_serial(self):
        # Firefox, Safari and every iPhone browser have no navigator.serial; headless Chromium does, so remove it.
        # The card stays visible but greyed out, with the reason, and the Help says where it works.
        self.fresh_page('delete Navigator.prototype.serial')
        self.assertFalse(self.pg.evaluate("document.getElementById('boardCard').hidden"))
        self.assertTrue(self.pg.evaluate("document.getElementById('boardCard').classList.contains('unsupported')"))
        self.assertTrue(self.pg.evaluate("document.getElementById('boardConnectBtn').disabled"))
        self.assertFalse(self.pg.evaluate("document.getElementById('boardUnsupported').hidden"))
        self.assertIn('Not supported in this browser', self.pg.evaluate("document.getElementById('boardUnsupported').textContent"))
        self.assertEqual(self.pg.evaluate("getComputedStyle(document.querySelector('#boardCard .board-purpose')).opacity"), '0.5')
        self.assertEqual(self.pg.evaluate("getComputedStyle(document.getElementById('boardUnsupported')).opacity"), '1')
        self.pg.click('#helpBtn'); self.pg.wait_for_timeout(200)
        help_text = self.pg.evaluate("document.getElementById('helpBody').textContent")
        for want in ('Where the card works', 'Chrome, Edge', 'Safari', 'Firefox', 'iPhone'):
            self.assertIn(want, help_text)

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

    def test_desktop_layout_board_full_width_restore_button_and_levelled_columns(self):
        # 2026-10-15 layout: Board card under both columns; Restore last session is a button beside + Blank;
        # Frames ends level with Panel settings while both folds are closed (and stops stretching when one is open);
        # the fold is labelled "Panel Check", not all caps.
        self.pg.evaluate("document.getElementById('restoreBtn').hidden = false")
        r = self.pg.evaluate("""() => { const b = (id) => document.getElementById(id).getBoundingClientRect();
            return { board: b('boardCard'), frames: b('framesCard'), panel: b('panelCard'), tools: b('moveCard'), restore: b('restoreBtn'), blank: b('addBlankFrameBtn'),
                     label: document.querySelector('.check-label').textContent, upper: getComputedStyle(document.querySelector('.check-label')).textTransform }; }""")
        self.assertLessEqual(r['board']['left'], r['frames']['left'] + 1); self.assertGreaterEqual(r['board']['right'], r['panel']['right'] - 1)
        self.assertGreater(r['board']['top'], max(r['frames']['bottom'], r['panel']['bottom']) - 1, 'Board sits below both columns')
        self.assertAlmostEqual(r['frames']['bottom'], r['panel']['bottom'], delta=1)
        self.assertAlmostEqual(r['restore']['top'], r['blank']['top'], delta=1); self.assertGreater(r['restore']['left'], r['blank']['left'])
        self.assertEqual((r['label'], r['upper']), ('Panel Check', 'none'))
        self.assertGreater(r['blank']['top'], r['frames']['top'] + 100, 'Duplicate / Blank / Restore sit low in the Frames card, not under the hint')
        self.assertLess(r['blank']['bottom'], r['frames']['bottom'] - 40, 'and above the red row')
        self.pg.evaluate("document.getElementById('diagDetails').open = true")
        r2 = self.pg.evaluate("""() => ({ frames: document.getElementById('framesCard').getBoundingClientRect().bottom, panel: document.getElementById('panelCard').getBoundingClientRect().bottom })""")
        self.assertLess(r2['frames'], r2['panel'] - 50, 'with a fold open the Frames card keeps its own height')

    def test_help_dialog_renders(self):
        self.pg.click('#helpBtn'); self.pg.wait_for_timeout(200)
        self.assertTrue(self.pg.evaluate("document.getElementById('helpDlg').open"))
        heads = self.pg.evaluate("Array.from(document.querySelectorAll('#helpBody h3')).map((h) => h.textContent)")
        for h in ('Works well', 'Drawing tools', 'Drawing on a phone', 'Getting a picture onto the panel', 'Watch out for'):
            self.assertIn(h, heads)
        self.assertGreater(self.pg.evaluate("document.getElementById('helpBody').textContent.length"), 3000)


if __name__ == '__main__':
    unittest.main()
