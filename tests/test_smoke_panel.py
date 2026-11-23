"""The experimental Bluetooth panel card (web/js/panel.js): off by default, on with ?experimental=panel, and a send over a stubbed Bluetooth device.
Run by hand with the rest of the smoke tests:
    python3 -m unittest tests.test_smoke_panel -v        (from the repo root; needs Playwright)
The Web Bluetooth device is faked in the page, so this proves the card's flow and bytes, not that a real panel accepts them.
"""
import functools, http.server, os, threading, unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAKE = """
(() => {
  const sent = []; let buf = [], need = 0; const listeners = [];
  const reply = (bytes) => { const ab = Uint8Array.from(bytes).buffer; listeners.forEach((fn) => fn({ target: { value: new DataView(ab) } })); };
  const writeChr = { async writeValueWithResponse(data) {
    const d = Array.from(data); sent.push(d);
    if (d[0] === 8 && d[2] === 1 && d[3] === 0x80 && !need) { setTimeout(() => reply([9, 0, 1, 0x80, 129, 0]), 0); return; }   // device info request
    buf = buf.concat(d); if (!need) need = buf[0] | (buf[1] << 8);
    if (buf.length >= need) { buf = []; need = 0; setTimeout(() => reply([5, 0, 3, 0, 3]), 0); }                                // window acknowledged
  } };
  const notifyChr = { async startNotifications() {}, addEventListener(t, fn) { listeners.push(fn); } };
  const svc = { async getCharacteristic(u) { return u.startsWith('0000fa02') ? writeChr : notifyChr; } };
  const dev = { name: 'LED_BLE_TEST', gatt: { connected: false, async connect() { this.connected = true; return { async getPrimaryService() { return svc; } }; }, disconnect() { this.connected = false; } }, addEventListener() {} };
  window.__sent = sent; window.__requested = [];
  Object.defineProperty(navigator, 'bluetooth', { configurable: true, value: { async requestDevice(o) { window.__requested.push(o); return dev; } } });
})();
"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@unittest.skipIf(sync_playwright is None, 'playwright not installed')
class PanelCard(unittest.TestCase):
    def setUp(self):
        self.srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=os.path.join(ROOT, 'web')))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.srv.server_address[1]}/index.html'

    def tearDown(self):
        self.srv.shutdown()

    def page(self, pw, fake=True):
        br = pw.chromium.launch(); ctx = br.new_context(viewport={'width': 1200, 'height': 1400}, service_workers='block'); pg = ctx.new_page()
        if fake:
            pg.add_init_script(FAKE)
        self.errors = []; pg.on('pageerror', lambda e: self.errors.append(str(e)))
        self.requests = []; pg.on('request', lambda r: self.requests.append(r.url))
        return br, pg

    def test_off_by_default_and_nothing_extra_is_fetched(self):
        with sync_playwright() as pw:
            br, pg = self.page(pw)
            pg.goto(self.url); pg.wait_for_timeout(500)
            self.assertEqual(pg.locator('#btPanelCard').count(), 0)
            self.assertFalse([u for u in self.requests if 'panel' in u], 'the panel files are not even fetched')
            self.assertEqual(self.errors, [])
            br.close()

    def test_switching_on_connecting_and_sending(self):
        with sync_playwright() as pw:
            br, pg = self.page(pw)
            pg.goto(self.url + '?experimental=panel'); pg.wait_for_selector('#btPanelCard')
            self.assertEqual(pg.locator('#panelSendDrawing').is_disabled(), True)
            pg.click('#panelConnect'); pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Connected')")
            self.assertIn('LED_BLE_TEST (32 x 32)', pg.inner_text('#panelStatus'))
            self.assertEqual(pg.evaluate("window.__requested[0].filters[0].namePrefix"), 'LED_BLE_')
            # draw one red pixel, send the drawing
            pg.evaluate("document.querySelector('#grid .cell').click()")
            pg.click('#panelSendDrawing'); pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Sent')")
            sent = pg.evaluate("window.__sent")
            win = bytes(b for chunk in sent[1:] for b in chunk)          # after the device-info request
            self.assertEqual(win[2:4], b'\x03\x00', 'GIF window')
            self.assertEqual(len(win), win[0] | (win[1] << 8), 'one window, length prefix right')
            self.assertEqual(win[15:21], b'GIF89a')
            self.assertTrue(all(len(c) <= 244 for c in sent), 'chunks are at most 244 bytes')
            # text, still effect: two cells
            pg.fill('#panelText', 'hi'); pg.select_option('#panelEffect', '5')
            before = len(pg.evaluate("window.__sent"))
            pg.click('#panelSendText'); pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Sent.') && !document.getElementById('panelStatus').textContent.includes('drawing')")
            sent = pg.evaluate("window.__sent")[before:]
            win = bytes(b for chunk in sent for b in chunk)
            self.assertEqual(win[2:4], b'\x00\x01', 'text window')
            self.assertEqual(win[15], 2, 'a still effect sends the whole text as two 16x32 cells')
            self.assertEqual(win[15 + 4], 5, 'effect Blink')
            self.assertEqual(self.errors, [])
            br.close()

    def test_slots_save_show_delete_and_fill(self):
        with sync_playwright() as pw:
            br, pg = self.page(pw)
            pg.goto(self.url + '?experimental=panel'); pg.wait_for_selector('#btPanelCard')
            self.assertTrue(pg.locator('#panelSaveAll').is_disabled())
            pg.click('#panelConnect'); pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Connected')")
            pg.fill('#panelSlot', '4'); pg.click('#panelSaveSlot')
            pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Saved to slot 4')")
            win = bytes(b for chunk in pg.evaluate("window.__sent")[1:] for b in chunk)
            self.assertEqual(win[14], 4, 'saved into slot 4')
            n = len(pg.evaluate("window.__sent")); pg.click('#panelShowSlot')
            pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Asked the panel to show slot 4')")
            self.assertEqual(pg.evaluate("window.__sent")[n], [7, 0, 8, 0x80, 1, 0, 4])
            n = len(pg.evaluate("window.__sent")); pg.click('#panelDeleteSlot')
            pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Asked the panel to clear slot 4')")
            self.assertEqual(pg.evaluate("window.__sent")[n], [7, 0, 2, 1, 1, 0, 4])
            pg.fill('#panelSlot', '10'); pg.fill('#panelSlotCount', '3'); pg.click('#panelSaveAll')
            pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Saved all 3 examples to slots 10 to 12')", timeout=20000)
            pg.click('#panelTour')
            pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Tour finished')", timeout=20000)
            self.assertEqual(self.errors, [])
            br.close()

    def test_a_moving_effect_sends_one_cell_per_character_and_busy_clicks_are_ignored(self):
        with sync_playwright() as pw:
            br, pg = self.page(pw)
            pg.goto(self.url + '?experimental=panel'); pg.wait_for_selector('#btPanelCard')
            pg.click('#panelConnect'); pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Connected')")
            before = len(pg.evaluate("window.__sent"))
            pg.fill('#panelText', 'love you'); pg.select_option('#panelEffect', '1')
            pg.evaluate("document.getElementById('panelSendText').click(); document.getElementById('panelSendText').click()")
            pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Sent') || document.getElementById('panelStatus').textContent.startsWith('Wait')")
            pg.wait_for_function("document.getElementById('panelStatus').textContent.startsWith('Sent')")
            win = bytes(b for chunk in pg.evaluate("window.__sent")[before:] for b in chunk)
            self.assertEqual(win[15], 8, 'eight characters, eight cells')
            self.assertEqual(win[15 + 4], 1, 'effect Move left')
            self.assertEqual(len(win), win[0] | (win[1] << 8), 'only one send went out')
            br.close()

    def test_it_stays_off_without_web_bluetooth_and_can_be_switched_off_again(self):
        with sync_playwright() as pw:
            br, pg = self.page(pw, fake=False)
            pg.add_init_script("Object.defineProperty(navigator, 'bluetooth', { configurable: true, value: undefined });")
            pg.goto(self.url + '?experimental=panel'); pg.wait_for_timeout(500)
            self.assertEqual(pg.locator('#btPanelCard').count(), 0, 'no Web Bluetooth, no card')
            br.close()
            br, pg = self.page(pw)
            pg.goto(self.url + '?experimental=panel'); pg.wait_for_selector('#btPanelCard')
            pg.goto(self.url); pg.wait_for_selector('#btPanelCard')          # remembered in this browser
            pg.goto(self.url + '?experimental=off'); pg.wait_for_timeout(500)
            self.assertEqual(pg.locator('#btPanelCard').count(), 0)
            pg.goto(self.url); pg.wait_for_timeout(500)
            self.assertEqual(pg.locator('#btPanelCard').count(), 0, 'stays off afterwards')
            self.assertEqual(self.errors, [])
            br.close()


if __name__ == '__main__':
    unittest.main()
