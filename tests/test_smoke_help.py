"""The Help dialog's folds and jump chips (web/js/help.js). Run by hand with the rest of the smoke tests:
    python3 -m unittest tests.test_smoke_help -v        (from the repo root; needs Playwright)
"""
import functools, http.server, os, threading, unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@unittest.skipIf(sync_playwright is None, 'playwright not installed')
class HelpFolds(unittest.TestCase):
    def test_sections_fold_and_chips_jump(self):
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=os.path.join(ROOT, 'web')))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        with sync_playwright() as pw:
            br = pw.chromium.launch(); ctx = br.new_context(viewport={'width': 1200, 'height': 900}, service_workers='block'); pg = ctx.new_page()
            errors = []; pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.goto(f'http://127.0.0.1:{srv.server_address[1]}/index.html'); pg.wait_for_timeout(400)
            pg.click('#helpBtn'); pg.wait_for_timeout(200)
            ev = lambda js: pg.evaluate(js)
            self.assertEqual(ev("document.querySelectorAll('#helpBody details.help-sec').length"), 8)
            self.assertEqual(ev("document.querySelectorAll('#helpBody .help-chip').length"), 8, 'one chip per section')
            self.assertEqual(ev("Array.from(document.querySelectorAll('#helpBody details.help-sec')).map((d) => d.open)"), [True] + [False] * 7, 'only the first is open')
            self.assertEqual(ev("document.querySelectorAll('#helpBody > h3').length"), 0, 'every h3 sits inside a fold')
            self.assertEqual(ev("document.querySelectorAll('#helpBody summary h3').length"), 8)
            self.assertNotEqual(ev("getComputedStyle(document.getElementById('helpBody')).fontFamily.includes('Plex')"), True, 'prose is not monospace')
            self.assertEqual(ev("getComputedStyle(document.querySelector('#helpBody code')).fontFamily.includes('Plex')"), True, 'code stays monospace')
            pg.click("#helpBody .help-chip:has-text('Phone')"); pg.wait_for_timeout(400)
            self.assertEqual(ev("Array.from(document.querySelectorAll('#helpBody details.help-sec')).map((d) => d.open)"), [True, False, False, False, True, False, False, False])
            vis = ev("(() => { const r = document.querySelector('#helpBody details.help-sec:nth-of-type(5) summary').getBoundingClientRect(), b = document.getElementById('helpBody').getBoundingClientRect(); return r.top >= b.top && r.bottom <= b.bottom; })()")
            self.assertTrue(vis, 'the chosen section header is in view')
            self.assertEqual(errors, [])
            br.close()
        srv.shutdown()


if __name__ == '__main__':
    unittest.main()
