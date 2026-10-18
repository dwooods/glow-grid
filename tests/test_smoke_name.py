"""Start over resets the sprite name, and Undo/Redo move it with the drawing (web/js/editor.js). Run by hand with the rest of the smoke tests:
    python3 -m unittest tests.test_smoke_name -v        (from the repo root; needs Playwright)
"""
import functools, http.server, os, threading, unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SET_NAME = "v => { const e = document.getElementById('nameInput'); e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); }"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@unittest.skipIf(sync_playwright is None, 'playwright not installed')
class StartOverName(unittest.TestCase):
    def test_start_over_resets_the_name_and_undo_brings_it_back(self):
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=os.path.join(ROOT, 'web')))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        with sync_playwright() as pw:
            br = pw.chromium.launch(); ctx = br.new_context(viewport={'width': 1200, 'height': 1000}, service_workers='block'); pg = ctx.new_page()
            errors = []; pg.on('pageerror', lambda e: errors.append(str(e)))
            pg.goto(f'http://127.0.0.1:{srv.server_address[1]}/index.html'); pg.wait_for_timeout(400)
            val = lambda i: pg.evaluate(f"document.getElementById('{i}').value")
            click = lambda i: pg.evaluate(f"document.getElementById('{i}').click()")
            pg.evaluate(SET_NAME, 'penguin')
            click('startOverBtn')
            self.assertEqual((val('nameInput'), val('boardName')), ('sprite', 'sprite'), 'both name fields reset')
            click('undoBtn'); self.assertEqual(val('nameInput'), 'penguin', 'Undo brings the old name back')
            click('redoBtn'); self.assertEqual(val('nameInput'), 'sprite')
            # Undo of a paint stroke must not revert a name typed afterwards
            pg.evaluate(SET_NAME, 'duck')
            pg.click('#grid .cell >> nth=0'); click('undoBtn')
            self.assertEqual(val('nameInput'), 'duck')
            self.assertEqual(errors, [])
            br.close()
        srv.shutdown()
