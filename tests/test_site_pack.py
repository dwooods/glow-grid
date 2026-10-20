"""The editor the C3 serves (c3/tools/build_site.py) is the web/ editor with comments and indentation stripped.

Run from the repo root:  python3 -m unittest tests.test_site_pack -v   (the parse check needs Node)
"""
import gzip, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'c3', 'tools'))
import build_site, minify  # noqa: E402


class SitePack(unittest.TestCase):
    def test_minifier_self_test(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'c3', 'tools', 'minify.py')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_packed_page_fits_the_budget(self):
        n = len(gzip.compress(build_site.bundle_html().encode('utf-8'), compresslevel=9, mtime=0))
        self.assertLessEqual(n, build_site.GG_SITE_MAX, f'packed page is {n} bytes gzipped')

    def test_minified_scripts_still_parse_and_keep_their_strings(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is not installed')
        js_dir = os.path.join(ROOT, 'web', 'js')
        with tempfile.TemporaryDirectory() as d:
            for name in sorted(os.listdir(js_dir)):
                src = open(os.path.join(js_dir, name), encoding='utf-8').read()
                out = minify.js_minify(src)
                path = os.path.join(d, name)
                open(path, 'w', encoding='utf-8').write(out)
                r = subprocess.run([node, '--check', path], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, f'{name}: {r.stderr[:300]}')
                # every quoted/template string in the source must survive untouched
                for marker in ('Glow Grid', '`'):
                    self.assertEqual(src.count(marker) > 0, out.count(marker) > 0, f'{name}: {marker!r}')

    def test_bundle_carries_no_comments_but_keeps_the_open_menu(self):
        html = build_site.bundle_html()
        self.assertIn('menuOpen', html)
        self.assertNotIn('menuOpenGg', html)
        self.assertNotIn('Make the help easier to scan', html)   # a comment in help.js


if __name__ == '__main__':
    unittest.main()
