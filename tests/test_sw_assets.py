"""The service worker's cache list matches the page.

`sw.js` installs by fetching every entry in ASSETS; one missing file fails the whole install, and a
script left out of the list works online and breaks offline, which nothing else would notice.
"""
import os
import re
import unittest

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def read(name):
    with open(os.path.join(WEB, name), encoding="utf-8") as fh:
        return fh.read()


class ServiceWorkerAssets(unittest.TestCase):
    def setUp(self):
        sw = read("sw.js")
        m = re.search(r"const ASSETS = \[(.*?)\];", sw, re.S)
        self.assertIsNotNone(m, "sw.js has no ASSETS list")
        self.assets = re.findall(r"'([^']+)'", m.group(1))
        self.version = re.search(r"const CACHE = 'glow-grid-v(\d+)'", sw).group(1)
        self.html = read("index.html")

    def test_every_local_script_and_stylesheet_is_cached(self):
        refs = re.findall(r'<script src="([^"]+)"', self.html)
        refs += [h for h in re.findall(r'<link[^>]*href="([^"]+)"', self.html) if not h.startswith("http")]
        missing = [r for r in refs if "./" + r not in self.assets]
        self.assertEqual(missing, [], f"referenced by index.html but not in sw.js ASSETS (bump CACHE v{self.version} too)")

    def test_every_cached_asset_exists(self):
        gone = [a for a in self.assets if a != "./" and not os.path.isfile(os.path.join(WEB, a))]
        self.assertEqual(gone, [], "in sw.js ASSETS but not on disk: the install would fail")


if __name__ == "__main__":
    unittest.main()
