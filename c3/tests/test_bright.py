"""Firmware 19: BRIGHT <pct> plays every stored sprite at one brightness without re-sending (0 = each sprite's own).
Runs the compiled firmware simulator from test_gg.py:   python3 -m unittest tests.test_bright -v   (from the c3 folder)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_gg as _tg  # noqa: E402  (a module, not the classes: unittest must not collect test_gg's own tests twice)

sample_frames = _tg.sample_frames


class Bright(_tg.Board):
    def test_bright_overrides_every_sprite_and_survives_a_power_cycle(self):
        self.start()
        fr = sample_frames(81, 1)
        self.board.put(self.write_gg("lamp", fr, b=0.3))
        self.board.simple("SHOW lamp")
        self.assertIn("bright=0", self.board.simple("INFO"))
        self.assertEqual(self.last_frames(1)[0], self.led_of(fr, b=0.3)[0], "its own 0.3 to start with")
        for bad in ("BRIGHT", "BRIGHT 5", "BRIGHT 41", "BRIGHT x", "BRIGHT -1", "BRIGHT 2x"):
            self.board.send(bad)
            with self.assertRaisesRegex(RuntimeError, "usage"):
                self.board.expect(["OK"])
        self.assertIn("bright=0", self.board.simple("INFO"), "a refused value changes nothing")
        # the playing sprite changes at once, with no re-send
        self.assertEqual(self.board.simple("BRIGHT 20"), "OK bright 20")
        self.assertIn("bright=20", self.board.simple("INFO"))
        self.assertEqual(self.last_frames(1)[0], self.led_of(fr, b=0.2)[0])
        self.assertIn("bright_pct=30", self.board.simple("INFO"), "the file itself is untouched")
        # a sprite shown later gets the same brightness, including one that asked for more
        fr2 = sample_frames(82, 1)
        self.board.put(self.write_gg("sun", fr2, b=0.4))
        self.board.simple("SHOW sun")
        self.assertEqual(self.last_frames(1)[0], self.led_of(fr2, b=0.2)[0])
        # kept across a power cycle; the setting file is not a sprite
        board = self.restart()
        self.assertIn("bright=20", board.simple("INFO"))
        self.assertEqual([f[0] for f in board.list()[0]], ["lamp", "sun"])
        self.assertEqual(self.last_frames(1)[0], self.led_of(fr, b=0.2)[0], "after a restart the first sprite plays, still at 0.2")
        # 0 = each sprite's own again
        self.assertEqual(board.simple("BRIGHT 0"), "OK bright 0")
        self.assertEqual(self.last_frames(1)[0], self.led_of(fr, b=0.3)[0])
        board = self.restart()
        self.assertIn("bright=0", board.simple("INFO"))

    def test_bright_over_http(self):
        self.start(wifi=True)
        self.board.wifi_set("Net", "password1")
        self.board.put(self.write_gg("lamp", sample_frames(83, 1), b=0.3))
        self.http_base()
        self.assertEqual(self.http("POST", "/bright?pct=25")[2], b"OK bright 25\n")
        self.assertIn("bright=25", self.board.simple("INFO"))
        self.assertEqual(self.http("POST", "/bright?pct=0")[2], b"OK bright 0\n")
        self.assertEqual(self.http("POST", "/bright?pct=7")[0], 400)
        # the Host/Origin guard covers the new route like every other POST
        st, hd, out = self.http("POST", "/bright?pct=20", b"", {"Origin": "https://evil.example"})
        self.assertEqual((st, out), (403, b"ERR not allowed from this page or address\n"))
        self.assertIn("bright=0", self.board.simple("INFO"))


for _n in dir(_tg.Board):                 # inherit the harness (start, put, restart, http), not test_gg's own tests
    if _n.startswith("test_"):
        setattr(Bright, _n, None)


if __name__ == "__main__":
    unittest.main()
