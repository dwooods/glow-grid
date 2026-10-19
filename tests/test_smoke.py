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
  window.__fakeStore = new Map(); window.__fakePanel = 'on'; window.__fakeCurrent = '-'; window.__fakeLog = []; window.__fakeRotate = 0; window.__fakeShuffle = 0; window.__fakeBright = 0; window.__fakeSched = 'off'; window.__fakeClock = '-';
  window.__fakeWifi = { state: 'off', ip: '-', ssid: '', polls: 0 };
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
        case 'LIST': for (const n of names()) { const b = window.__fakeStore.get(n);       // fw 17 adds frames fps10 bright_pct gamma10 for a real sprite
            say('FILE ' + n + ' ' + b.length + (window.__fakeFw >= 17 && b.length >= 12 && b[10] ? ' ' + (b[6] | (b[7] << 8)) + ' ' + (b[8] | (b[9] << 8)) + ' ' + b[10] + ' ' + b[11] : '')); }
           return say('OK ' + names().length + ' files, 1400000 bytes free');
        case 'CRC': if (window.__fakeFw < 7) return say('ERR unknown command'); if (!window.__fakeStore.has(a1)) return say('ERR no such sprite');
          return say('OK crc=' + crc32(window.__fakeStore.get(a1)).toString(16).padStart(8, '0') + ' size=' + window.__fakeStore.get(a1).length);
        case 'GET': if (window.__fakeFw < 8) return say('ERR unknown command'); if (!window.__fakeStore.has(a1)) return say('ERR no such sprite');
          { const b = window.__fakeStore.get(a1); const out = b.slice(); if (window.__fakeBreak === 'badget') out[20] ^= 1;
            for (let i = 0; i < out.length; i += 48) say('D ' + Array.from(out.subarray(i, i + 48), (v) => v.toString(16).padStart(2, '0')).join(''));
            return say('OK crc=' + crc32(b).toString(16).padStart(8, '0') + ' size=' + b.length); }
        case 'INFO': return say('OK fw=' + window.__fakeFw + ' current=' + window.__fakeCurrent + ' sprites=' + names().length + ' panel=' + window.__fakePanel + ' rotate=' + window.__fakeRotate + (window.__fakeFw >= 16 ? ' shuffle=' + window.__fakeShuffle : '') + (window.__fakeFw >= 19 ? ' bright=' + window.__fakeBright : '') + (window.__fakeFw >= 20 ? ' schedule=' + window.__fakeSched + ' clock=' + window.__fakeClock : '') + (window.__fakeFw >= 9 ? ' wifi=' + window.__fakeWifi.state + ' ip=' + window.__fakeWifi.ip : ''));
        case 'SHUFFLE': if (window.__fakeFw < 16) return say('ERR unknown command'); if (!/^[01]$/.test(a1 || '')) return say('ERR usage: SHUFFLE <0|1> (1 = random order)'); window.__fakeShuffle = Number(a1); return say('OK shuffle ' + a1);
        case 'SCHED': if (window.__fakeFw < 20) return say('ERR unknown command');
          if (/^off$/i.test(a1 || '')) { window.__fakeSched = 'off'; return say('OK schedule off'); }
          if (!/^\\d{4}$/.test(a1 || '') || !/^\\d{4}$/.test(a2 || '') || a1 === a2) return say('ERR usage: SCHED <on HHMM> <off HHMM> (24-hour, different times) or SCHED OFF');
          window.__fakeSched = a1 + '-' + a2; return say('OK schedule ' + window.__fakeSched);
        case 'BRIGHT': if (window.__fakeFw < 19) return say('ERR unknown command'); if (!/^(0|[1-3][0-9]|40)$/.test(a1 || '') || (a1 !== '0' && Number(a1) < 10)) return say('ERR usage: BRIGHT <0|10..40>'); window.__fakeBright = Number(a1); return say('OK bright ' + Number(a1));
        case 'ROTATE': if (!/^\\d+$/.test(a1 || '')) return say('ERR usage: ROTATE <seconds>'); window.__fakeRotate = Number(a1); return say('OK rotate ' + a1);
        case 'PUT': if (!/^[A-Za-z0-9_-]{1,31}$/.test(a1)) return say('ERR bad name');
          if (!window.__fakeStore.has(a1) && window.__fakeStore.size >= 96) return say('ERR board holds 96 sprites; delete one first');
          t.pending = { name: a1, size: Number(a2), crc: parseInt(a3, 16), buf: new Uint8Array(Number(a2)), got: 0, acked: 0 }; return say('READY');
        case 'SHOW': if (!window.__fakeStore.has(a1)) return say('ERR no such sprite'); window.__fakeCurrent = a1; window.__fakePanel = 'on'; return say('OK showing ' + a1);
        case 'DEL': if (!window.__fakeStore.has(a1)) return say('ERR no such sprite'); window.__fakeStore.delete(a1);
          if (window.__fakeCurrent === a1) window.__fakeCurrent = names()[0] || '-'; return say('OK deleted ' + a1);
        case 'WIFI': { const w = window.__fakeWifi;
          if (window.__fakeFw < 9) return say('ERR unknown command');
          if (a1 === 'STATUS') { if (w.state === 'connecting' && ++w.polls >= 2) { w.state = 'connected'; w.ip = '192.168.50.6'; }
            return say('OK wifi=' + w.state + ' ip=' + w.ip + ' rssi=-40 host=glowgrid.local ssid=' + w.ssid); }
          if (a1 === 'SCAN') { if (window.__fakeFw < 10) return say('ERR usage: WIFI STATUS | WIFI SET <ssid hex> <password hex or -> | WIFI CLEAR');
            const hx = (s) => Array.from(new TextEncoder().encode(s), (b) => b.toString(16).padStart(2, '0')).join('');
            for (const n of (window.__fakeScan || [])) say('NET ' + hx(n.ssid) + ' ' + n.rssi + ' ' + (n.secure ? 1 : 0));
            return say('OK networks=' + (window.__fakeScan || []).length); }
          if (a1 === 'KEY' && window.__fakeFw >= 18) return say('OK key=k7m2xq9p4d');
          if (a1 === 'CLEAR') { window.__fakeWifi = { state: 'off', ip: '-', ssid: '', polls: 0 }; return say('OK wifi cleared'); }
          if (a1 === 'SET' && a2) { const dec = (h) => h === '-' ? '' : new TextDecoder().decode(Uint8Array.from(h.match(/../g), (x) => parseInt(x, 16)));
            window.__fakeWifiSet = { ssid: dec(a2), pass: dec(a3 || '-') }; window.__fakeWifi = { state: 'connecting', ip: '-', ssid: dec(a2), polls: 0 };
            return say('OK wifi saved; joining. Check with WIFI STATUS (2.4 GHz networks only)'); }
          return say('ERR usage: WIFI STATUS | WIFI SET <ssid hex> <password hex or -> | WIFI CLEAR'); }
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

    def test_frame_cap_is_16_for_every_target(self):
        """One cap for the Pi and the C3, so the editor never needs to know the target: Duplicate and Blank stop at 16, and say why."""
        self.pg.evaluate("() => { state.frames = [newBlankFrame(state.cols, state.rows)]; state.currentFrame = 0; afterFrameChange(); }")
        dis = lambda i: self.pg.evaluate(f"document.getElementById('{i}').disabled")
        for _ in range(15): self.pg.click('#addFrameBtn')
        self.assertEqual(self.pg.evaluate('state.frames.length'), 16)
        self.assertTrue(dis('addFrameBtn')); self.assertTrue(dis('addBlankFrameBtn'))
        self.assertIn('at most 16', self.pg.evaluate("document.getElementById('addFrameBtn').title"))
        self.pg.evaluate("document.getElementById('addFrameBtn').disabled = false; document.getElementById('addFrameBtn').click()")   # even a forced click adds nothing
        self.assertEqual(self.pg.evaluate('state.frames.length'), 16)
        self.pg.click('#deleteFrameBtn'); self.assertFalse(dis('addFrameBtn')); self.assertFalse(dis('addBlankFrameBtn'))
        self.assertEqual(self.pg.evaluate("(() => { try { ggDecode(ggBytes(Array.from({length: 16}, () => new Array(256).fill('#112233')), 16, 16, 6, 0.3, 2.2)); return 'ok'; } catch (e) { return e.message; } })()"), 'ok')
        self.assertIn('limit is 16', self.pg.evaluate("(() => { const b = ggBytes(Array.from({length: 16}, () => new Array(256).fill('#112233')), 16, 16, 6, 0.3, 2.2); b[6] = 17; b[7] = 0; try { ggDecode(b); return ''; } catch (e) { return e.message; } })()"))

    def test_sprite_names_never_double_the_tail_and_fit_the_board(self):
        names = self.pg.evaluate("""() => ['blue_ghost_sprite (2).png', 'cat_sprite_sprite.png', 'cat_sprite_8fps (3).png', 'my pic_x16.png', 'a'.repeat(60) + '.png', '___.png']
            .map((n) => spriteNameFor({ name: n }))""")
        self.assertEqual(names[:4], ['blue_ghost_sprite', 'cat_sprite', 'cat_sprite', 'my_pic_sprite'])
        self.assertEqual(names[5], 'sprite_sprite')
        self.assertEqual(len(names[4]), 31); self.assertTrue(names[4].endswith('_sprite'))
        for n in names: self.assertRegex(n, r'^[A-Za-z0-9_-]{1,31}$')
        self.assertEqual(self.pg.evaluate("document.getElementById('nameInput').maxLength"), 31)
        self.assertEqual(self.pg.evaluate("document.getElementById('boardName').maxLength"), 31)

    def test_ai_prompt_recipe_loads_here(self):
        """The Help prompt tells an AI to write a one-row PNG with a glow-grid text chunk; that exact file must import."""
        import json
        from PIL.PngImagePlugin import PngInfo
        def make(path, frames, cols, rows, fps=None, bright=0.35, gamma=2.4):
            sheet = Image.new('RGB', (cols * len(frames), rows))
            for i, c in enumerate(frames): sheet.paste(Image.new('RGB', (cols, rows), c), (i * cols, 0))
            meta = {'brightness': bright, 'gamma': gamma, 'cols': cols, 'rows': rows}
            if len(frames) > 1: meta['frames'], meta['fps'] = len(frames), fps
            info = PngInfo(); info.add_text('glow-grid', json.dumps(meta, separators=(',', ':'))); sheet.save(path, pnginfo=info)
        t = self.tmp.name
        sheet = os.path.join(t, 'zap_8fps.png'); make(sheet, [(255, 0, 0), (0, 255, 0), (0, 0, 255)], 16, 16, 8)
        self.import_file(sheet)
        self.assertEqual(self.pg.evaluate('[state.frames.length, state.fps, sim.brightness, sim.gamma, state.name]'), [3, 8, 0.35, 2.4, 'zap_sprite'])
        still = os.path.join(t, 'dot.png'); make(still, [(255, 128, 0)], 16, 16)
        self.import_file(still)
        self.assertEqual(self.pg.evaluate('[state.frames[state.currentFrame][0], state.name]'), ['#ff8000', 'dot_sprite'])
        self.pg.evaluate("() => { document.getElementById('colsInput').value = 8; document.getElementById('rowsInput').value = 32; document.getElementById('resizeBtn').click(); }")
        tall = os.path.join(t, 'tower_5fps.png'); make(tall, [(255, 0, 0), (0, 0, 255)], 8, 32, 5)
        self.import_file(tall)
        self.assertEqual(self.pg.evaluate('[state.cols, state.rows, state.frames.length, state.fps, state.frames[1][0]]'), [8, 32, 2, 5, '#0000ff'])

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
        self.assertEqual(status(), 'Connected. Board software version 7.')
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
        self.assertIn('Sent flower (2 frames, 5 fps, brightness 0.3, gamma 2.2, 1,548 bytes)', status())
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
        # every rotation is random: one flat list (no "list order" group, no checkbox), SHUFFLE 1 + ROTATE on a board with firmware 16+, plain ROTATE (list order) before that
        self.assertEqual(self.pg.evaluate("document.querySelectorAll('#boardRotate optgroup').length"), 0, 'no groups')
        self.assertEqual(self.pg.evaluate("Array.from(document.querySelectorAll('#boardRotate option')).map((o) => o.textContent).filter((t) => /random|list/i.test(t)).length"), 0, 'the word random is not in the list')
        self.assertEqual(self.pg.evaluate("document.getElementById('boardShuffle')"), None, 'the old checkbox is gone')
        self.assertIn('newer board software', self.pg.evaluate("document.getElementById('boardRotate').title"))
        self.pg.evaluate('window.__fakeFw = 16'); self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate("document.getElementById('boardRotate').title"), '')
        self.pg.select_option('#boardRotate', '300'); self.pg.wait_for_timeout(400)
        self.assertEqual((self.pg.evaluate('window.__fakeShuffle'), self.pg.evaluate('window.__fakeRotate')), (1, 300)); self.assertIn('in random order', status())
        self.assertEqual(self.pg.evaluate("document.getElementById('boardRotate').value"), '300', 'follows what the board reports')
        self.pg.evaluate('window.__fakeShuffle = 1; window.__fakeRotate = 45'); self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate("document.getElementById('boardRotate').selectedOptions[0].textContent"), 'every 45 s', 'an unlisted random interval gets its own entry')
        self.assertEqual(self.pg.evaluate("document.getElementById('boardRotate').value"), '45')
        self.pg.select_option('#boardRotate', '0'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakeRotate'), 0); self.assertEqual(self.pg.evaluate("document.getElementById('boardRotate').value"), '0')
        # board brightness: greyed out before firmware 19, then a select that sends BRIGHT and follows the board
        self.assertTrue(self.pg.evaluate("document.getElementById('boardBright').disabled"))
        self.assertIn('newer board software', self.pg.evaluate("document.getElementById('boardBrightLbl').title"))
        self.pg.evaluate('window.__fakeFw = 19'); self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.assertFalse(self.pg.evaluate("document.getElementById('boardBright').disabled"))
        self.assertEqual(self.pg.evaluate("document.getElementById('boardBright').value"), '0')
        self.pg.select_option('#boardBright', '20'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakeBright'), 20); self.assertIn('brightness 0.2', status())
        self.pg.evaluate('window.__fakeBright = 35'); self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate("document.getElementById('boardBright').value"), '35', 'an unlisted board value gets its own entry')
        self.pg.select_option('#boardBright', '0'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakeBright'), 0); self.assertIn('own brightness', status())
        # schedule: greyed out before firmware 20, then a checkbox with two 24-hour times that sends SCHED and follows the board
        dis = "['boardSched', 'boardSchedOn', 'boardSchedOff'].every((i) => document.getElementById(i).disabled)"
        self.assertTrue(self.pg.evaluate(dis)); self.assertIn('newer board software', self.pg.evaluate("document.getElementById('boardSchedHint').textContent"))
        self.pg.evaluate('window.__fakeFw = 20'); self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.assertFalse(self.pg.evaluate(dis)); self.assertFalse(self.pg.evaluate("document.getElementById('boardSched').checked"))
        self.assertIn('no time yet', self.pg.evaluate("document.getElementById('boardSchedHint').textContent"))
        self.assertFalse(self.pg.evaluate("document.getElementById('boardSchedHint').hidden"))
        self.pg.fill('#boardSchedOn', '7:05'); self.pg.fill('#boardSchedOff', '2000'); self.pg.check('#boardSched'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakeSched'), '0705-2000'); self.assertIn('switches on at 07:05 and off at 20:00', status())
        self.assertEqual(self.pg.evaluate("[document.getElementById('boardSchedOn').value, document.getElementById('boardSchedOff').value]"), ['07:05', '20:00'], 'times are tidied')
        self.pg.evaluate("window.__fakeClock = '1432'"); self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.assertTrue(self.pg.evaluate("document.getElementById('boardSchedHint').hidden"), 'no hint once the board knows the time')
        self.pg.fill('#boardSchedOn', '21:30'); self.pg.press('#boardSchedOn', 'Tab'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakeSched'), '2130-2000', 'changing a time while it is ticked sends it at once')
        self.pg.uncheck('#boardSched'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.pg.evaluate('window.__fakeSched'), 'off'); self.assertEqual(status(), 'Schedule off.')
        self.pg.fill('#boardSchedOn', 'abc'); self.pg.click('#boardSched'); self.pg.wait_for_timeout(400)
        self.assertFalse(self.pg.evaluate("document.getElementById('boardSched').checked")); self.assertIn('24-hour', status())
        self.pg.fill('#boardSchedOn', '20:00'); self.pg.click('#boardSched'); self.pg.wait_for_timeout(400)
        self.assertFalse(self.pg.evaluate("document.getElementById('boardSched').checked")); self.assertIn('different times', status())
        self.assertEqual(self.pg.evaluate('window.__fakeSched'), 'off', 'nothing reached the board')
        self.pg.evaluate("window.__fakeSched = '2200-0600'"); self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.assertTrue(self.pg.evaluate("document.getElementById('boardSched').checked"), 'follows what the board reports')
        self.assertEqual(self.pg.evaluate("[document.getElementById('boardSchedOn').value, document.getElementById('boardSchedOff').value]"), ['22:00', '06:00'])
        # the note under the schedule says what the times mean: 24-hour, same day or overnight (off earlier than on), and flags equal times
        note = lambda: self.pg.evaluate("document.getElementById('boardSchedNote').textContent")
        bad = lambda: self.pg.evaluate("document.getElementById('boardSchedNote').classList.contains('board-sched-bad')")
        self.assertIn('overnight', note()); self.assertIn('8 h on, 16 h off', note()); self.assertFalse(bad())
        self.pg.uncheck('#boardSched'); self.pg.wait_for_timeout(400)      # a ticked schedule sends every edit at once and re-reads the board; test the wording unticked
        self.pg.fill('#boardSchedOn', '07:00'); self.pg.fill('#boardSchedOff', '20:00')
        self.assertIn('24-hour clock', note()); self.assertIn('same day', note()); self.assertIn('13 h on, 11 h off', note())
        self.pg.fill('#boardSchedOn', '07:55'); self.pg.fill('#boardSchedOff', '07:52')
        self.assertIn('overnight', note()); self.assertIn('23 h 57 min on, 0 h 3 min off', note())
        self.pg.fill('#boardSchedOff', '07:55'); self.assertIn('different times', note()); self.assertTrue(bad())
        self.pg.fill('#boardSchedOff', 'xx'); self.assertIn('type times like 07:00', note()); self.assertTrue(bad())
        self.assertIn('24 h', self.pg.evaluate("document.querySelector('#boardSchedBox .check').textContent"))
        self.pg.evaluate('window.__fakeFw = 7')
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

    def test_board_name_field_saves_a_copy_or_replaces_and_the_list_shows_settings(self):
        self.fresh_page(f'({FAKE_BOARD})()'); self.board_helpers()
        self.pg.on('dialog', lambda d: d.accept())
        self.pg.evaluate("window.__fakeFw = 17")
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        val = lambda i: self.pg.evaluate(f"document.getElementById('{i}').value")
        hint = lambda: self.pg.evaluate("document.getElementById('boardNameHint').textContent")
        self.pg.evaluate("""() => { const n = state.cols * state.rows; state.frames = [new Array(n).fill('#ff8800'), new Array(n).fill('#0000ff')];
            state.currentFrame = 0; state.fps = 5; afterFrameChange(); }""")
        # one name, two fields: typing in either shows in the other
        self.pg.fill('#boardName', 'x' * 40); self.assertEqual(len(val('boardName')), 31, 'cut at the most a board accepts')
        self.pg.fill('#boardName', 'duck'); self.assertEqual(val('nameInput'), 'duck')
        self.set_name('duck2'); self.assertEqual(val('boardName'), 'duck2')   # Export's field is in a closed dialog, so set through the page
        self.pg.fill('#boardName', 'duck')
        self.assertIn('adds “duck” as a new sprite', hint())
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertEqual(self.rows(), ['duck (2 frames, 5 fps, brightness 0.3, gamma 2.2)'], 'settings in ( ) after the name, from firmware 17')
        self.assertIn('replaces “duck”', hint())
        # same name asks first and replaces; a new name is the save-as path and keeps the old sprite
        self.pg.fill('#boardName', 'duck_b')
        self.assertIn('adds “duck_b”', hint())
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertEqual(sorted(self.pg.evaluate('[...window.__fakeStore.keys()]')), ['duck', 'duck_b'])
        self.assertEqual(self.pg.evaluate("window.__fakeLog.filter((l) => l.startsWith('PUT')).length"), 2)
        # one frame has no speed; an older board gives no settings, so the rows are plain names again
        self.pg.evaluate("() => { state.frames = [new Array(256).fill('#ff0000')]; afterFrameChange(); }")
        self.pg.fill('#boardName', 'dot'); self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertIn('dot (brightness 0.3, gamma 2.2)', self.rows())
        self.pg.evaluate('window.__fakeFw = 16'); self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.assertEqual(self.rows(), ['dot', 'duck', 'duck_b'])
        # Load puts the name in both fields, and the hint says Send will replace that sprite
        self.pg.evaluate('window.__fakeFw = 17'); self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(400)
        self.pg.click("#boardList .board-row:nth-child(2) button:has-text('Load')"); self.pg.wait_for_timeout(600)
        self.assertEqual((val('boardName'), val('nameInput')), ('duck', 'duck'))
        self.assertIn('replaces “duck”', hint())
        self.assertEqual(self.errors, [])

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

    def test_remove_examples_also_removes_older_versions(self):
        """An example we redesigned (old copy on the board, same name) and one we retired (name no longer shipped) are
        recognised from web/js/examples_legacy.js and removed; a sprite you changed is still kept. The legacy list is
        patched in the page with fingerprints of bytes the test makes up, since the real old bytes are not in the repo."""
        self.fresh_page(f'({FAKE_BOARD})()'); self.board_helpers()
        self.pg.on('dialog', lambda d: d.accept())
        self.connect(['mine'])
        self.pg.evaluate("""() => {
            const fp = (bytes) => [crc32(bytes).toString(16).padStart(8, '0'), bytes.length];
            const old = ggExampleBytes(GG_EXAMPLES[0]).slice(); old[30] ^= 1;          // an earlier version of example 0
            const retired = ggExampleBytes(GG_EXAMPLES[1]).slice(); retired[30] ^= 2;   // a retired example under a name nobody ships
            const mine = ggExampleBytes(GG_EXAMPLES[2]).slice(); mine[30] ^= 4;        // your own edit: not in the list
            GG_LEGACY_EXAMPLES.push([GG_EXAMPLES[0].name, ...fp(old)], ['retired_sprite', ...fp(retired)]);
            window.__fakeStore.set(GG_EXAMPLES[0].name, old); window.__fakeStore.set('retired_sprite', retired);
            window.__fakeStore.set(GG_EXAMPLES[2].name, mine);
        }""")
        self.pg.click('#boardRefreshBtn'); self.pg.wait_for_timeout(300)
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(6500)     # the old copy is skipped by name and flagged
        self.assertIn('1 of those is an older version', self.status())
        self.pg.click('#boardRemoveExBtn'); self.pg.wait_for_timeout(5000)
        kept = self.pg.evaluate('GG_EXAMPLES[2].name')
        self.assertEqual(self.store(), sorted(['mine', kept]))
        self.assertEqual(self.status(), f'Removed 37 examples (2 older versions). Kept 1 you changed: {kept}.')
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(6500)     # now the new versions go in
        self.assertEqual(self.pg.evaluate("GG_EXAMPLES.filter((e) => e.name !== GG_EXAMPLES[2].name).every((e) => { const b = window.__fakeStore.get(e.name); const w = ggExampleBytes(e); return b && b.length === w.length && b.every((v, i) => v === w[i]); })"), True)

    def test_add_and_remove_examples(self):
        self.fresh_page(f'({FAKE_BOARD})()'); self.board_helpers()
        answer = {'ok': True}
        self.pg.on('dialog', lambda d: d.accept() if answer['ok'] else d.dismiss())
        total = self.pg.evaluate('GG_EXAMPLES.length')
        self.assertEqual(total, 37)
        self.assertTrue(self.pg.evaluate("document.getElementById('boardExamples').hidden"), 'hidden until connected')
        self.connect(['mine'])
        self.assertFalse(self.pg.evaluate("document.getElementById('boardExamples').hidden"))
        self.pg.evaluate("window.__fakeCurrent = 'mine'")
        self.pg.click('#boardRemoveExBtn'); self.pg.wait_for_timeout(300)
        self.assertEqual(self.status(), 'No examples are on the board.')
        # add: every example lands byte-for-byte as Export would write it; the sprite that was playing keeps playing
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(6500)
        self.assertEqual(self.status(), f'Added {total} examples.')
        self.assertEqual(len(self.store()), total + 1)
        self.assertEqual(self.pg.evaluate("GG_EXAMPLES.every((e) => { const b = window.__fakeStore.get(e.name); const w = ggExampleBytes(e); return b && b.length === w.length && b.every((v, i) => v === w[i]); })"), True)
        self.assertEqual(self.pg.evaluate('window.__fakeCurrent'), 'mine')
        self.assertEqual(self.pager()['info'], '1–5 of 38', 'the examples page like everything else')
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
        self.pg.click('#boardRemoveExBtn'); self.pg.wait_for_timeout(5000)
        kept = self.pg.evaluate('[GG_EXAMPLES[0].name, GG_EXAMPLES[1].name]')
        self.assertEqual(self.store(), sorted(['mine'] + kept))
        self.assertEqual(self.status(), f'Removed {total - 2} examples. Kept 2 you changed: {sorted(kept)[0]}, {sorted(kept)[1]}.')   # in the board's (alphabetical) order
        self.assertEqual(self.pg.evaluate('window.__fakeCurrent'), 'mine')
        # add never replaces: the two changed ones stay as they are
        edited = self.pg.evaluate("Array.from(window.__fakeStore.get(GG_EXAMPLES[0].name))")
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(6500)
        self.assertEqual(self.status(), f'Added {total - 2} examples; 2 already on the board were left alone.')
        self.assertEqual(self.pg.evaluate("Array.from(window.__fakeStore.get(GG_EXAMPLES[0].name))"), edited)

    def test_load_a_board_sprite_into_the_grid_and_open_a_gg_file(self):
        self.fresh_page(f'({FAKE_BOARD})()'); self.board_helpers()
        dialogs = []
        self.pg.on('dialog', lambda d: (dialogs.append(d.message), d.accept() if self.answer else d.dismiss()))
        self.answer = True
        self.pg.evaluate("""() => { window.__fakeFw = 8; const px = (c) => new Array(256).fill(c);
            window.__fakeStore.set('lantern', ggBytes([px('#ff8800'), px('#0000ff')], 16, 16, 5, 0.45, 2.6)); }""")
        self.connect()
        load = "#boardList .board-row:nth-child(1) button:has-text('Load')"
        self.assertFalse(self.pg.evaluate("document.querySelector('#boardList .board-row button').disabled"), 'firmware 8 can Load')
        # the page opens on a blank frame, so nothing is asked; the frames, name, fps, brightness and gamma all come from the file
        self.pg.click(load); self.pg.wait_for_timeout(800)
        got = self.pg.evaluate("""() => ({frames: state.frames.length, a: state.frames[0][0], b: state.frames[1][255], fps: state.fps, name: state.name,
            nameBox: document.getElementById('nameInput').value, bright: document.getElementById('brightInput').value,
            gamma: document.getElementById('gammaInput').value, simB: sim.brightness, simG: sim.gamma, undo: !document.getElementById('undoBtn').disabled})""")
        self.assertEqual(got, {'frames': 2, 'a': '#ff8800', 'b': '#0000ff', 'fps': 5, 'name': 'lantern', 'nameBox': 'lantern',
                               'bright': '0.45', 'gamma': '2.6', 'simB': 0.45, 'simG': 2.6, 'undo': True})
        self.assertEqual(dialogs, [], 'a blank editor is replaced without asking')
        self.assertIn('Loaded lantern into the editor', self.status())
        # change a pixel and Send: same name, so it replaces the sprite on the board (and asks first), keeping 0.45 / 2.6
        self.pg.evaluate("() => { state.frames[0][0] = '#00ff00'; afterFrameChange(); }")
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(900)
        self.assertTrue(any('Replace' in m for m in dialogs))
        stored = self.pg.evaluate("Array.from(window.__fakeStore.get('lantern'))")
        self.assertEqual(stored[10:12], [45, 26]); self.assertEqual(stored[12:15], [0, 255, 0])
        # loading over a drawing asks first; saying no leaves the drawing alone
        dialogs.clear(); self.answer = False
        self.pg.evaluate("() => { state.frames[0][1] = '#123456'; afterFrameChange(); }")
        self.pg.click(load); self.pg.wait_for_timeout(800)
        self.assertTrue(any('Replace the drawing' in m for m in dialogs))
        self.assertEqual(self.pg.evaluate("state.frames[0][1]"), '#123456')
        self.assertEqual(self.pg.evaluate("window.__fakeLog.filter((l) => l.startsWith('GET')).length"), 2)
        self.assertEqual(self.status(), 'Not loaded.')
        self.assertFalse(self.pg.evaluate("document.getElementById('boardSendBtn').disabled"), 'buttons come back')
        # a transfer that arrives damaged is refused and changes nothing
        self.pg.evaluate("window.__fakeBreak = 'badget'"); self.answer = True
        self.pg.click(load); self.pg.wait_for_timeout(800)
        self.assertIn('damaged', self.status()); self.assertEqual(self.pg.evaluate("state.frames[0][1]"), '#123456')
        self.pg.evaluate("window.__fakeBreak = null")
        # a sprite that is not on the board any more
        self.pg.evaluate("window.__fakeStore.delete('lantern')")
        self.pg.click(load); self.pg.wait_for_timeout(600)
        self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(300)
        # older firmware: Load is greyed out, says why, and never sends GET
        self.pg.evaluate("() => { window.__fakeFw = 7; window.__fakeLog.length = 0; }")
        self.pg.evaluate(self.SEED, ['old'])
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        self.assertTrue(self.pg.evaluate("document.querySelector('#boardList .board-row button').disabled"))
        self.assertIn('newer board software', self.pg.evaluate("document.querySelector('#boardList .board-row button').title"))
        self.assertEqual(self.pg.evaluate("window.__fakeLog.filter((l) => l.startsWith('GET')).length"), 0)
        # File > Open .gg sprite: from a file on the computer, named after the file
        blob = self.pg.evaluate("Array.from(ggBytes([new Array(256).fill('#abcdef')], 16, 16, 9, 0.3, 2.2))")
        self.pg.evaluate("() => { state.frames = [new Array(256).fill('#000000')]; state.currentFrame = 0; afterFrameChange(); }")
        self.assertTrue(self.pg.evaluate("!!document.getElementById('menuOpenGg')"))
        self.pg.set_input_files('#ggInput', files=[{'name': 'my sprite.gg', 'mimeType': 'application/octet-stream', 'buffer': bytes(blob)}])
        self.pg.wait_for_timeout(500)
        self.assertEqual(self.pg.evaluate("[state.name, state.fps, state.frames[0][7], sim.brightness]"), ['my_sprite', 9, '#abcdef', 0.3])
        toast = lambda: self.pg.evaluate("document.getElementById('statusEl').textContent")
        self.assertIn('Loaded my_sprite from the file', toast())
        # a file that is not a sprite is refused and the drawing stays
        self.pg.set_input_files('#ggInput', files=[{'name': 'notes.gg', 'mimeType': 'application/octet-stream', 'buffer': b'hello world, not a sprite'}])
        self.pg.wait_for_timeout(400)
        self.assertIn('not a Glow Grid sprite', toast()); self.assertEqual(self.pg.evaluate("state.name"), 'my_sprite')

    def test_load_resizes_the_grid_undo_restores_it_and_fps_rounds(self):
        self.fresh_page(f'({FAKE_BOARD})()'); self.board_helpers()
        self.pg.on('dialog', lambda d: d.accept())
        # the editor is 8 x 32 with a drawing, a name and 1 frame; the board holds a 16 x 16 sprite at 7.2 fps
        self.pg.evaluate("""() => { window.__fakeFw = 8;
            window.__fakeStore.set('odd', ggBytes([new Array(256).fill('#ff0000'), new Array(256).fill('#00ff00')], 16, 16, 7.2, 0.45, 2.6));
            state.cols = 8; state.rows = 32; $('colsInput').value = 8; $('rowsInput').value = 32; buildGridDOM();
            state.frames = [new Array(256).fill('#123456')]; state.currentFrame = 0; state.name = 'mine'; $('nameInput').value = 'mine';
            state.fps = 12; $('fpsInput').value = 12; afterFrameChange(); }""")
        self.connect()
        self.pg.click("#boardList .board-row:nth-child(1) button:has-text('Load')"); self.pg.wait_for_timeout(800)
        got = self.pg.evaluate("""() => ({cols: state.cols, rows: state.rows, cells: document.querySelectorAll('#grid .cell').length, colsBox: $('colsInput').value,
            rowsBox: $('rowsInput').value, frames: state.frames.length, fps: state.fps, name: state.name, bright: sim.brightness, gamma: sim.gamma})""")
        self.assertEqual(got, {'cols': 16, 'rows': 16, 'cells': 256, 'colsBox': '16', 'rowsBox': '16', 'frames': 2, 'fps': 7, 'name': 'odd', 'bright': 0.45, 'gamma': 2.6})
        toast = self.pg.evaluate("document.getElementById('statusEl').textContent")
        self.assertIn('7.2 fps', toast, 'a rounded fps is reported, not hidden')
        # Send writes the editor's whole-number fps and the loaded brightness and gamma; the board keeps 0.45 / 2.6
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(900)
        stored = self.pg.evaluate("Array.from(window.__fakeStore.get('odd'))")
        self.assertEqual((stored[8] | stored[9] << 8, stored[10], stored[11]), (70, 45, 26))
        # Undo puts back the old grid size, frames and the 8 x 32 cells
        self.pg.click('#undoBtn'); self.pg.wait_for_timeout(300)
        back = self.pg.evaluate("""() => ({cols: state.cols, rows: state.rows, cells: document.querySelectorAll('#grid .cell').length, frames: state.frames.length,
            px: state.frames[0][0], colsBox: $('colsInput').value, rowsBox: $('rowsInput').value})""")
        self.assertEqual(back, {'cols': 8, 'rows': 32, 'cells': 256, 'frames': 1, 'px': '#123456', 'colsBox': '8', 'rowsBox': '32'})

    def test_examples_old_firmware_full_board_and_errors(self):
        self.fresh_page(f'({FAKE_BOARD})()'); self.board_helpers()
        self.pg.on('dialog', lambda d: d.accept())
        # firmware before 7 has no CRC: Add still works, Remove refuses rather than guess, and deletes nothing
        self.pg.evaluate('window.__fakeFw = 6')
        self.connect()
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(6500)
        n = len(self.store()); self.assertEqual(n, 37)
        self.pg.click('#boardRemoveExBtn'); self.pg.wait_for_timeout(400)
        self.assertIn('newer board software', self.status()); self.assertEqual(len(self.store()), n)
        self.assertEqual(self.pg.evaluate("window.__fakeLog.filter((l) => l.startsWith('CRC') || l.startsWith('DEL')).length"), 0)
        self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(300)
        # a board with no room for all of them: nothing is sent, and the message says why
        self.pg.evaluate("() => { window.__fakeFw = 7; window.__fakeStore.clear(); }")
        self.pg.evaluate(self.SEED, [f'p{i:02d}' for i in range(70)])       # 70 + 37 examples > the 96 slots
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        before = self.puts()
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(400)
        self.assertIn('would not fit', self.status()); self.assertEqual(self.puts(), before); self.assertEqual(len(self.store()), 70)
        self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(300)
        # the board refuses mid-way (no space): the card reports how far it got and shows what is there
        self.pg.evaluate("() => { window.__fakeStore.clear(); window.__fakeBreak = 'full'; }")
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        self.pg.click('#boardAddExBtn'); self.pg.wait_for_timeout(800)
        self.assertIn('not enough space', self.status()); self.assertIn('Added 0 of 37', self.status())
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
        self.assertIn('Sent walk (4 frames, 8 fps, brightness 0.3, gamma 2.2, 3,084 bytes)', status())
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
        frames(17); self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(300)
        self.assertIn('up to 16 frames', status()); self.assertEqual(self.pg.evaluate('window.__fakeLog.length'), before)
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
        self.assertEqual(self.pg.evaluate("document.getElementById('boardStatus').textContent"), 'Connected. Board software version 3.')
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
        # USB is greyed out with the reason, Wi-Fi stays available, and the Help says where each works.
        self.fresh_page('delete Navigator.prototype.serial')
        self.assertFalse(self.pg.evaluate("document.getElementById('boardCard').hidden"))
        self.assertTrue(self.pg.evaluate("document.getElementById('boardConnectBtn').disabled"), 'USB is greyed out')
        self.assertFalse(self.pg.evaluate("document.getElementById('boardWifiBtn').disabled"), 'Wi-Fi still works')
        self.assertFalse(self.pg.evaluate("document.getElementById('boardUnsupported').hidden"))
        self.assertIn('USB is not supported in this browser', self.pg.evaluate("document.getElementById('boardUnsupported').textContent"))
        self.assertIn('Connect over Wi-Fi', self.pg.evaluate("document.getElementById('boardUnsupported').textContent"))
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

    def test_desktop_layout_board_full_width_restore_button_and_compact_frames_card(self):
        # 2026-10-15 layout: Board card under both columns; Restore last session is a button beside + Blank;
        # the Frames card keeps its own height (no stretching to match Panel settings, so no empty gap above its buttons);
        # the fold is labelled "Panel Check", not all caps.
        self.pg.evaluate("document.getElementById('restoreBtn').hidden = false")
        r = self.pg.evaluate("""() => { const b = (id) => document.getElementById(id).getBoundingClientRect();
            return { board: b('boardCard'), frames: b('framesCard'), panel: b('panelCard'), tools: b('moveCard'), restore: b('restoreBtn'), blank: b('addBlankFrameBtn'),
                     label: document.querySelector('.check-label').textContent, upper: getComputedStyle(document.querySelector('.check-label')).textTransform }; }""")
        self.assertLessEqual(r['board']['left'], r['frames']['left'] + 1); self.assertGreaterEqual(r['board']['right'], r['panel']['right'] - 1)
        self.assertGreater(r['board']['top'], max(r['frames']['bottom'], r['panel']['bottom']) - 1, 'Board sits below both columns')
        self.assertAlmostEqual(r['restore']['top'], r['blank']['top'], delta=1); self.assertGreater(r['restore']['left'], r['blank']['left'])
        self.assertEqual((r['label'], r['upper']), ('Panel Check', 'none'))
        self.assertEqual(self.pg.evaluate("document.getElementById('frameCount').textContent"), '1 of 16 frames')
        rows = self.pg.evaluate("() => { const tops = Array.from(document.querySelectorAll('#frameStrip .frame-cell')).map((c) => Math.round(c.getBoundingClientRect().top)); return [tops.length, new Set(tops).size, tops.filter((x) => x === tops[0]).length]; }")
        self.assertEqual(rows, [16, 2, 8], 'the 16 slots are two rows of 8')
        gap = self.pg.evaluate("() => { const s = document.getElementById('stripHint'), h = (s.hidden ? document.getElementById('frameCount') : s).getBoundingClientRect(), b = document.getElementById('addBlankFrameBtn').getBoundingClientRect(); return b.top - h.bottom; }")
        self.assertLess(gap, 40, 'Duplicate / Blank / Restore sit right under the count and hint, with no empty gap')
        self.assertLess(r['blank']['bottom'], r['frames']['bottom'] - 40, 'and above the red row')

    def test_help_dialog_renders(self):
        self.pg.click('#helpBtn'); self.pg.wait_for_timeout(200)
        self.assertTrue(self.pg.evaluate("document.getElementById('helpDlg').open"))
        heads = self.pg.evaluate("Array.from(document.querySelectorAll('#helpBody h3')).map((h) => h.textContent)")
        for h in ('Works well', 'Drawing tools', 'Drawing on a phone', 'Getting a picture onto the panel', 'Watch out for'):
            self.assertIn(h, heads)
        self.assertGreater(self.pg.evaluate("document.getElementById('helpBody').textContent.length"), 3000)


if __name__ == '__main__':
    unittest.main()
