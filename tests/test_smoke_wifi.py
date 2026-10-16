"""Browser smoke tests for the editor's Wi-Fi side: the Board card over Wi-Fi (against a fake of the firmware's HTTP API, answered by
Playwright's request routing) and the Network dialog's Wi-Fi setup over USB (against the fake USB board in test_smoke.py).
Split from test_smoke.py to keep each file small enough to push.

Run by hand before pushing a change under web/ (not in CI), from the repo root:
    python3 -m unittest tests.test_smoke_wifi -v
Skips itself if Playwright is missing. The service worker is blocked so tests always see the files on disk.
"""
import functools, http.server, os, threading, unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None
try:
    from tests.test_smoke import ROOT, FAKE_BOARD, SET_NAME, Handler
except ImportError:                                  # run with tests/ as the discovery directory
    from test_smoke import ROOT, FAKE_BOARD, SET_NAME, Handler


class FakeHttpBoard:
    """The firmware's HTTP API (c3/README.md) answered by Playwright's request routing, so the editor's HttpBoard runs for real."""
    HOST = 'glowgrid.local'

    def __init__(self, fw=9):
        self.store, self.log, self.fw = {}, [], fw
        self.panel, self.current, self.rotate = 'on', '-', 0
        self.fail_put = None                      # an ERR text to answer a /put with
        self.damage_get = False

    def install(self, ctx, host=None):
        ctx.route(f'http://{host or self.HOST}/**', self.handle)

    def reply(self, route, status, body, ctype='text/plain'):
        route.fulfill(status=status, body=body, content_type=ctype, headers={'access-control-allow-origin': '*'})

    def handle(self, route):
        import re, urllib.parse, zlib
        req = route.request
        u = urllib.parse.urlparse(req.url); q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        self.log.append(f'{req.method} {u.path}' + (f'?{u.query}' if u.query else ''))
        name = q.get('name', '')
        def err(text):
            self.reply(route, 404 if 'no such' in text else 400, 'ERR ' + text)
        if u.path == '/ping': return self.reply(route, 200, 'PONG\n')
        if u.path == '/list':
            lines = [f'FILE {n} {len(b)}' for n, b in sorted(self.store.items())] + [f'OK {len(self.store)} files, 1400000 bytes free']
            return self.reply(route, 200, '\n'.join(lines) + '\n')
        if u.path == '/info':
            return self.reply(route, 200, f'OK fw={self.fw} current={self.current} sprites={len(self.store)} panel={self.panel} rotate={self.rotate} wifi=connected ip=192.168.50.6 gap_ms=3\n')
        if u.path == '/crc':
            if name not in self.store: return err('no such sprite')
            b = self.store[name]; return self.reply(route, 200, f'OK crc={zlib.crc32(b) & 0xffffffff:08x} size={len(b)}\n')
        if u.path == '/get':
            if name not in self.store: return err('no such sprite')
            b = bytearray(self.store[name])
            if self.damage_get: b[20] ^= 1
            return self.reply(route, 200, bytes(b), 'application/octet-stream')
        if req.method != 'POST': return err('unknown command')
        if u.path == '/show':
            if name not in self.store: return err('no such sprite')
            self.current, self.panel = name, 'on'; return self.reply(route, 200, f'OK showing {name}\n')
        if u.path == '/del':
            if name not in self.store: return err('no such sprite')
            del self.store[name]; self.current = sorted(self.store)[0] if self.store else '-'; return self.reply(route, 200, f'OK deleted {name}\n')
        if u.path in ('/off', '/on'):
            self.panel = u.path[1:]; return self.reply(route, 200, f'OK panel {self.panel}\n')
        if u.path == '/rotate': self.rotate = int(q['s']); return self.reply(route, 200, f'OK rotate {self.rotate}\n')
        if u.path == '/put':
            if self.fail_put: return err(self.fail_put)
            ct = req.headers.get('content-type', '')
            if not ct.startswith('multipart/form-data'): return err('upload as multipart/form-data')
            body = req.post_data_buffer; boundary = ct.split('boundary=')[1].encode()
            start = body.index(b'\r\n\r\n') + 4; end = body.rindex(b'\r\n--' + boundary)
            blob = body[start:end]
            if len(blob) != int(q['size']): return err('size mismatch')
            if zlib.crc32(blob) & 0xffffffff != int(q['crc'], 16): return err('checksum mismatch')
            if blob[:2] != b'GG': return err('invalid sprite: bad magic')
            self.store[name] = blob; self.current, self.panel = name, 'on'
            return self.reply(route, 200, f'OK saved {name}\n')
        return err('unknown command')


@unittest.skipIf(sync_playwright is None, 'playwright not installed')
class SmokeWifi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=os.path.join(ROOT, 'web')))
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.srv.server_address[1]}/index.html'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.srv.shutdown()

    def setUp(self):
        self.ctx = None
        self.errors = []

    def tearDown(self):
        if self.ctx: self.ctx.close()

    def fresh_page(self, *init_scripts):
        """A new page whose init scripts run before board.js, which reads its environment at load."""
        if self.ctx: self.ctx.close()
        self.ctx = self.browser.new_context(viewport={'width': 1200, 'height': 1000}, service_workers='block')
        self.pg = self.ctx.new_page(); self.pg.add_init_script('delete window.showSaveFilePicker')
        for js in init_scripts:
            self.pg.add_init_script(js)
        self.pg.on('pageerror', lambda e: self.errors.append(str(e)))
        self.pg.goto(self.url); self.pg.wait_for_timeout(400)

    def set_name(self, v): self.pg.evaluate(SET_NAME, v)

    def board_helpers(self):
        self.status = lambda: self.pg.evaluate("document.getElementById('boardStatus').textContent")
        self.rows = lambda: self.pg.evaluate("Array.from(document.querySelectorAll('#boardList .board-row .board-name')).map((e) => e.textContent)")

    def test_board_card_over_wifi(self):
        """Connect over Wi-Fi from the Network dialog and use the whole card against the firmware's HTTP API. Web Serial is removed
        first (the iPhone case): Wi-Fi must not depend on it."""
        self.fresh_page('delete Navigator.prototype.serial'); self.board_helpers()
        hb = FakeHttpBoard(); hb.install(self.ctx)
        dialogs = []
        self.pg.on('dialog', lambda d: (dialogs.append(d.message), d.accept()))
        el = lambda i, prop='textContent': self.pg.evaluate(f"document.getElementById('{i}').{prop}")
        self.assertTrue(el('boardConnectBtn', 'disabled')); self.assertFalse(el('boardWifiBtn', 'disabled'))
        # the Network dialog: the default address, and the Wi-Fi form is off until a firmware 9 board is on USB
        self.pg.click('#netBtn'); self.pg.wait_for_timeout(200)
        self.assertTrue(self.pg.evaluate("document.getElementById('netDlg').open"))
        self.assertEqual(el('netHost', 'value'), 'glowgrid.local')
        self.assertTrue(el('netSaveBtn', 'disabled')); self.assertIn('over USB first', el('netSetupHint'))
        # a bad address is refused without a request; an unreachable one says what to check
        self.pg.fill('#netHost', 'not an address!'); self.pg.click('#netConnectBtn'); self.pg.wait_for_timeout(200)
        self.assertIn('does not look like an address', el('netStatus')); self.assertEqual(hb.log, [])
        self.ctx.route('http://nowhere.local/**', lambda r: r.abort())
        self.pg.fill('#netHost', 'http://nowhere.local/'); self.pg.click('#netConnectBtn'); self.pg.wait_for_timeout(500)
        self.assertIn('cannot reach the board at nowhere.local', el('netStatus')); self.assertTrue(el('boardList', 'hidden'), 'still not connected')
        self.assertTrue(self.pg.evaluate("document.getElementById('netDlg').open"), 'the dialog stays open to fix the address')
        # connect: pasted http:// and a trailing slash are tolerated; the dialog closes; the address is remembered
        self.pg.fill('#netHost', 'http://glowgrid.local/'); self.pg.click('#netConnectBtn'); self.pg.wait_for_timeout(700)
        self.assertFalse(self.pg.evaluate("document.getElementById('netDlg').open"))
        self.assertEqual(self.status(), 'Connected over Wi-Fi (glowgrid.local). Firmware 9.')
        self.assertIn('Wi-Fi glowgrid.local', el('boardLink')); self.assertEqual(self.rows(), [])
        self.assertEqual(self.pg.evaluate("localStorage.getItem('ggBoardHost')"), 'glowgrid.local')
        self.assertFalse(el('boardTools', 'hidden')); self.assertTrue(el('boardConnectBtn', 'hidden')); self.assertTrue(el('boardWifiBtn', 'hidden'))
        # send: multipart upload whose bytes are exactly what Export for ESP32-C3 writes
        self.pg.evaluate("""() => { const n = state.cols * state.rows; state.frames = [new Array(n).fill('#ff8800'), new Array(n).fill('#0000ff')];
            state.currentFrame = 0; state.fps = 5; afterFrameChange(); }""")
        self.set_name('flower'); self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertIn('Sent flower (2 frames, 1,548 bytes)', self.status()); self.assertEqual(self.rows(), ['flower'])
        want = bytes(self.pg.evaluate("Array.from(ggBytes(state.frames.map(flatten), 16, 16, state.fps, sim.brightness, sim.gamma))"))
        self.assertEqual(hb.store['flower'], want)
        self.assertTrue(self.pg.evaluate("document.querySelector('#boardList .board-row').classList.contains('playing')"))
        # replace asks first; a second sprite; play, lights, rotate, delete go out as the matching requests
        self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertEqual(len(dialogs), 1); self.assertIn('Replace', dialogs[0])
        self.set_name('owl'); self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(800)
        self.assertEqual(self.rows(), ['flower', 'owl'])
        self.pg.click("#boardList .board-row:nth-child(1) button:has-text('Play')"); self.pg.wait_for_timeout(400)
        self.assertEqual(hb.current, 'flower')
        self.pg.click('#boardOffBtn'); self.pg.wait_for_timeout(400); self.assertEqual(hb.panel, 'off')
        self.pg.click('#boardOnBtn'); self.pg.wait_for_timeout(400); self.assertEqual(hb.panel, 'on')
        self.pg.select_option('#boardRotate', '300'); self.pg.wait_for_timeout(400); self.assertEqual(hb.rotate, 300)
        self.pg.click("#boardList .board-row:nth-child(2) button:has-text('Delete')"); self.pg.wait_for_timeout(400)
        self.assertEqual(self.rows(), ['flower']); self.assertEqual(sorted(hb.store), ['flower'])
        # load reads the bytes back and checks them against the board's CRC; a damaged transfer is refused
        self.pg.click("#boardList .board-row:nth-child(1) button:has-text('Load')"); self.pg.wait_for_timeout(700)
        self.assertIn('Loaded flower into the editor', self.status())
        hb.damage_get = True
        self.pg.click("#boardList .board-row:nth-child(1) button:has-text('Load')"); self.pg.wait_for_timeout(700)
        self.assertIn('came through damaged', self.status()); hb.damage_get = False
        # the board's own refusal reaches the status line in its words
        hb.fail_put = 'not enough space'
        self.set_name('big'); self.pg.click('#boardSendBtn'); self.pg.wait_for_timeout(600)
        self.assertEqual(self.status(), 'Board said: not enough space'); self.assertFalse(el('boardSendBtn', 'disabled')); hb.fail_put = None
        # the Network dialog while connected over Wi-Fi: no second connection, and the setup form says why it is off
        self.pg.click('#netBtn'); self.pg.wait_for_timeout(200)
        self.assertTrue(el('netConnectBtn', 'disabled')); self.assertIn('connected over Wi-Fi', el('netSetupHint'))
        self.pg.click('#netClose')
        self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(300)
        self.assertEqual(self.status(), 'Board disconnected.'); self.assertTrue(el('boardTools', 'hidden')); self.assertEqual(el('boardLink'), '')
        self.assertFalse(el('boardWifiBtn', 'hidden'))
        self.assertTrue(all(l.split(' ')[0] in ('GET', 'POST') for l in hb.log))
        self.assertEqual(self.errors, [])

    def test_wifi_setup_over_usb_in_the_network_dialog(self):
        self.fresh_page(f'({FAKE_BOARD})()', 'window.__ggNetPollMs = 30;'); self.board_helpers()
        el = lambda i, prop='textContent': self.pg.evaluate(f"document.getElementById('{i}').{prop}")
        self.pg.evaluate('window.__fakeFw = 9')
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        self.assertEqual(self.status(), 'Connected. Firmware 9.'); self.assertIn('USB', el('boardLink'))
        self.pg.click('#netBtn'); self.pg.wait_for_timeout(200)
        self.assertFalse(el('netSaveBtn', 'disabled')); self.assertIn('Board Wi-Fi: off', el('netStatus'))
        self.assertIn('2.4 GHz', el('netSetupHint')); self.assertFalse(el('netConnectBtn', 'disabled'))
        # checks before anything is sent
        self.pg.click('#netSaveBtn'); self.assertIn('1 to 32', el('netStatus'))
        self.pg.fill('#netSsid', 'x' * 33); self.pg.click('#netSaveBtn'); self.assertIn('1 to 32', el('netStatus'))
        self.pg.fill('#netSsid', 'My Home Net'); self.pg.fill('#netPass', 'short'); self.pg.click('#netSaveBtn'); self.assertIn('8 to 63', el('netStatus'))
        self.assertEqual(self.pg.evaluate("window.__fakeLog.filter((l) => l.startsWith('WIFI SET')).length"), 0)
        # save: the name (with spaces) and the password (with symbols) go as hex and arrive intact; the password field is emptied
        self.pg.fill('#netPass', 'p@ss "word" #1'); self.pg.click('#netSaveBtn'); self.pg.wait_for_timeout(500)
        self.assertEqual(self.pg.evaluate("window.__fakeWifiSet"), {'ssid': 'My Home Net', 'pass': 'p@ss "word" #1'})
        line = self.pg.evaluate("window.__fakeLog.find((l) => l.startsWith('WIFI SET'))")
        self.assertRegex(line, r'^WIFI SET [0-9a-f]+ [0-9a-f]+$'); self.assertNotIn('p@ss', line)
        self.assertEqual(el('netPass', 'value'), '')
        self.assertIn("Joined My Home Net. The board's address is 192.168.50.6", el('netStatus'))
        # an open network sends "-" for the password; Forget network clears
        self.pg.fill('#netSsid', 'Cafe'); self.pg.click('#netSaveBtn'); self.pg.wait_for_timeout(500)
        self.assertEqual(self.pg.evaluate("window.__fakeLog.filter((l) => l.startsWith('WIFI SET')).pop().endsWith(' -')"), True)
        self.pg.click('#netClearBtn'); self.pg.wait_for_timeout(300)
        self.assertIn('forgot', el('netStatus')); self.assertEqual(self.pg.evaluate("window.__fakeWifi.state"), 'off')
        # an older board: the form is off and says which firmware it needs
        self.pg.click('#netClose'); self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(300)
        self.pg.evaluate('window.__fakeFw = 8'); self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        self.pg.click('#netBtn'); self.pg.wait_for_timeout(200)
        self.assertTrue(el('netSaveBtn', 'disabled')); self.assertIn('firmware 9', el('netSetupHint'))
        self.assertEqual(self.errors, [])

    def test_scan_and_pick_a_network(self):
        self.fresh_page(f'({FAKE_BOARD})()', 'window.__ggNetPollMs = 30;'); self.board_helpers()
        el = lambda i, prop='textContent': self.pg.evaluate(f"document.getElementById('{i}').{prop}")
        self.pg.evaluate("window.__fakeFw = 10; window.__fakeScan = [{ssid: 'Home Net', rssi: -42, secure: true}, {ssid: 'Cafe Open', rssi: -60, secure: false}]")
        self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        self.pg.click('#netBtn'); self.pg.wait_for_timeout(200)
        self.assertFalse(el('netScanBtn', 'disabled')); self.assertTrue(el('netPick', 'disabled'))   # nothing to pick before a scan
        self.pg.click('#netScanBtn'); self.pg.wait_for_timeout(400)
        self.assertIn('2 networks found', el('netStatus')); self.assertFalse(el('netPick', 'disabled'))
        self.assertEqual(self.pg.evaluate("Array.from(document.getElementById('netPick').options, (o) => o.value)"), ['', 'Home Net', 'Cafe Open'])
        # picking fills the name and moves to the password; saving sends exactly that name and password
        self.pg.select_option('#netPick', 'Home Net')
        self.assertEqual(el('netSsid', 'value'), 'Home Net')
        self.pg.fill('#netPass', 'hunter2hunter2'); self.pg.click('#netSaveBtn'); self.pg.wait_for_timeout(500)
        self.assertEqual(self.pg.evaluate('window.__fakeWifiSet'), {'ssid': 'Home Net', 'pass': 'hunter2hunter2'})
        self.assertIn('Joined Home Net', el('netStatus'))
        # an open network: the password box says so, and an empty password goes as "-"
        self.pg.select_option('#netPick', 'Cafe Open')
        self.assertEqual(el('netSsid', 'value'), 'Cafe Open'); self.assertIn('open', el('netPass', 'placeholder'))
        self.pg.click('#netSaveBtn'); self.pg.wait_for_timeout(500)
        self.assertEqual(self.pg.evaluate('window.__fakeWifiSet'), {'ssid': 'Cafe Open', 'pass': ''})
        # typing a name by hand still works (hidden networks), and an empty scan says so
        self.pg.fill('#netSsid', 'Hidden One'); self.pg.fill('#netPass', 'password123'); self.pg.click('#netSaveBtn'); self.pg.wait_for_timeout(500)
        self.assertEqual(self.pg.evaluate('window.__fakeWifiSet.ssid'), 'Hidden One')
        self.pg.evaluate('window.__fakeScan = []'); self.pg.click('#netScanBtn'); self.pg.wait_for_timeout(300)
        self.assertIn('heard no networks', el('netStatus')); self.assertTrue(el('netPick', 'disabled'))
        # firmware 9: scanning is off and says which firmware it needs; the typed form still works
        self.pg.click('#netClose'); self.pg.click('#boardDisconnectBtn'); self.pg.wait_for_timeout(300)
        self.pg.evaluate('window.__fakeFw = 9'); self.pg.click('#boardConnectBtn'); self.pg.wait_for_timeout(600)
        self.pg.click('#netBtn'); self.pg.wait_for_timeout(200)
        self.assertTrue(el('netScanBtn', 'disabled')); self.assertIn('firmware 10', el('netScanHint')); self.assertFalse(el('netSaveBtn', 'disabled'))
        self.assertEqual(self.errors, [])


if __name__ == '__main__':
    unittest.main()
