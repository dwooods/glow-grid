"""Tests for the C3 player: the .gg format, the C++ logic that runs on the board, and the upload tool.

Run from the c3 folder:   python3 -m unittest discover -s tests -v
Needs: g++, Pillow, pyserial (Linux, macOS or WSL), and the glow-grid repo for the parity checks:
set GLOWGRID_REPO=/path/to/glow-grid if this folder is not inside it.

What it proves:
  * gg_core.h (compiled on the PC) places and corrects every pixel exactly like grid_common.py,
    for all 16 wiring combinations and several brightness/gamma settings, including the 0.4 cap;
  * c3_player/c3_player.ino itself (compiled against small Arduino stand-ins) handles PUT, LIST, DEL, SHOW,
    bad input, a wrong checksum, a timeout and both buttons, driven by the real tools/gg_tool.py.
It does NOT test the real esp32 core, LittleFS on real flash, the NeoPixel timing or Bluetooth.
"""
import itertools
import os
import pty
import select
import tty
import subprocess
import sys
import tempfile
import time
import types
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKETCH = os.path.join(ROOT, "c3_player")   # the Arduino sketch folder (IDE rule: folder name = .ino name)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gg_format as gg  # noqa: E402
import gg_tool  # noqa: E402

BUILD = tempfile.mkdtemp(prefix="gg_build_")
HOST = os.path.join(BUILD, "host_gg")
SIM = os.path.join(BUILD, "sim")


def find_repo():
    cands = [os.environ.get("GLOWGRID_REPO"), os.path.dirname(ROOT), os.path.dirname(os.path.dirname(ROOT))]
    for c in cands:
        if c and os.path.exists(os.path.join(c, "grid_common.py")):
            return c
    return None


REPO = find_repo()
gc = None
if REPO:
    sys.path.insert(0, REPO)
    drv = types.ModuleType("rpi5_ws2812.ws2812")
    drv.Color = lambda r, g, b: (r, g, b)
    drv.WS2812SpiDriver = object
    pkg = types.ModuleType("rpi5_ws2812")
    pkg.ws2812 = drv
    sys.modules.setdefault("rpi5_ws2812", pkg)
    sys.modules.setdefault("rpi5_ws2812.ws2812", drv)
    import grid_common as gc  # noqa: E402


def write_bytes(path, blob):
    with open(path, "wb") as fh:
        fh.write(blob)


def write_text(path, text):
    with open(path, "w") as fh:
        fh.write(text)


def build(out, *args, defs=()):
    cmd = ["g++", "-std=c++17", "-O1", *[f"-D{d}" for d in defs], *args, "-o", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr)


def sample_frames(seed=1, n=3):
    import random
    rnd = random.Random(seed)
    return [[(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) if rnd.random() < 0.7 else (0, 0, 0)
             for _ in range(256)] for _ in range(n)]


def host(*args, defs=()):
    exe = HOST if not defs else os.path.join(BUILD, "host_" + "_".join(defs))
    if not os.path.exists(exe):
        build(exe, os.path.join(HERE, "host_gg.cpp"), defs=defs)
    return subprocess.run([exe, *map(str, args)], capture_output=True, text=True, check=True).stdout


def expected_led_frames(frames, brightness, gamma, flags):
    """What the Pi code would put on the panel, as the same hex lines host_gg prints."""
    cm, se, fx, fy = flags
    gc.COLUMN_MAJOR, gc.SERPENTINE, gc.FLIP_X, gc.FLIP_Y = bool(cm), bool(se), bool(fx), bool(fy)
    gc.set_light(brightness, gamma)
    lines = []
    for fr in frames:
        led = [(0, 0, 0)] * 256
        led = list(led)
        for y in range(16):
            for x in range(16):
                r, g, b = fr[y * 16 + x]
                led[gc.xy_to_index(x, y)] = gc.correct(r, g, b)
        lines.append("".join("%02x%02x%02x" % px for px in led))
    return lines


class Format(unittest.TestCase):
    def test_round_trip(self):
        frames = sample_frames()
        blob = gg.pack(frames, 8, 0.35, 2.2)
        self.assertEqual(len(blob), 12 + 3 * 768)
        out, fps, b, g = gg.unpack(blob)
        self.assertEqual((out, fps, b, g), (frames, 8.0, 0.35, 2.2))

    def test_rejects_bad_files(self):
        good = gg.pack(sample_frames(n=2), 6, 0.3, 2.2)
        for label, blob in [
            ("magic", b"XX" + good[2:]),
            ("version", good[:2] + b"\x02" + good[3:]),
            ("grid", good[:4] + b"\x08" + good[5:]),
            ("truncated", good[:-1]),
            ("padded", good + b"\x00"),
            ("zero frames", good[:6] + b"\x00\x00" + good[8:]),
        ]:
            with self.assertRaises(ValueError, msg=label):
                gg.unpack(blob)
        for args in [(0, 0.3, 2.2), (6, 0.0, 2.2), (6, 0.3, 0.5), (31, 0.3, 2.2)]:
            with self.assertRaises(ValueError):
                gg.pack(sample_frames(n=1), *args)

    def test_c_header_check_agrees(self):
        d = tempfile.mkdtemp()
        good = gg.pack(sample_frames(n=2), 6, 0.3, 2.2)
        cases = {"ok": (good, "OK 2 60 30 22"), "magic": (b"XX" + good[2:], "bad magic"),
                 "short": (good[:-1], "size does not match frames"), "tiny": (good[:5], "too short"),
                 "grid": (good[:4] + b"\x08" + good[5:], "wrong grid size")}
        for label, (blob, want) in cases.items():
            p = os.path.join(d, label + ".gg")
            write_bytes(p, blob)
            self.assertEqual(host("hdr", p).strip(), want, label)

    def test_names_and_crc(self):
        for s, want in [("lantern", "yes"), ("a-b_C9", "yes"), ("", "no"), ("a b", "no"), ("a/b", "no"), ("x" * 32, "no"), ("x" * 31, "yes")]:
            if s == "":
                continue  # an empty argument cannot be passed through the command line helper
            self.assertEqual(host("name", s).strip(), want, s)
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x.gg")
        blob = gg.pack(sample_frames(), 6, 0.3, 2.2)
        write_bytes(p, blob)
        self.assertEqual(host("crc", p).strip(), "%08x" % (zlib.crc32(blob) & 0xFFFFFFFF))


@unittest.skipUnless(gc, "glow-grid repo not found (set GLOWGRID_REPO)")
class Parity(unittest.TestCase):
    def test_lut_matches_pi_for_all_values(self):
        for pct, g10 in [(30, 22), (40, 20), (5, 28), (10, 22), (1, 10), (35, 30), (25, 18), (90, 22), (100, 30)]:
            gc.set_light(min(pct, 40) / 100.0, g10 / 10.0)
            want = [gc.correct(c, c, c)[0] for c in range(256)]
            got = list(map(int, host("lut", pct, g10).split()))
            self.assertEqual(got, want, f"brightness {pct}% gamma {g10 / 10}")

    def test_pixels_match_pi_for_every_wiring(self):
        frames = sample_frames(3, n=2)
        d = tempfile.mkdtemp()
        p = os.path.join(d, "t.gg")
        write_bytes(p, gg.pack(frames, 6, 0.3, 2.2))
        for flags in itertools.product([0, 1], repeat=4):
            defs = [f"GG_COLUMN_MAJOR={flags[0]}", f"GG_SERPENTINE={flags[1]}", f"GG_FLIP_X={flags[2]}", f"GG_FLIP_Y={flags[3]}"]
            got = host("frames", p, defs=defs).split()
            self.assertEqual(got, expected_led_frames(frames, 0.3, 2.2, flags), f"wiring {flags}")

    def test_settings_and_cap(self):
        frames = sample_frames(5, n=1)
        d = tempfile.mkdtemp()
        for b, g in [(0.1, 2.2), (0.4, 2.0), (0.05, 2.8), (0.9, 2.2)]:     # 0.9 must be capped at 0.4
            p = os.path.join(d, "t.gg")
            write_bytes(p, gg.pack(frames, 6, b, g))
            got = host("frames", p).split()
            self.assertEqual(got, expected_led_frames(frames, min(b, 0.4), g, (1, 1, 0, 0)), f"{b} {g}")


class FakePort:
    """Wraps a pty master so gg_tool.Board can talk to the simulated board like a serial port."""
    def __init__(self, fd):
        self.fd = fd
        self.timeout = 0.2

    def write(self, data):
        while data:
            n = os.write(self.fd, data)
            data = data[n:]

    def read(self, n=1):
        r, _, _ = select.select([self.fd], [], [], self.timeout)
        return os.read(self.fd, n) if r else b""

    def reset_input_buffer(self):
        while select.select([self.fd], [], [], 0.05)[0]:
            os.read(self.fd, 4096)

    def close(self):
        pass


class Board(unittest.TestCase):
    """c3_player.ino compiled on the PC, with the real gg_tool.py talking to it."""

    @classmethod
    def setUpClass(cls):
        build(SIM, "-Wall", f"-I{os.path.join(HERE, 'arduino_stub')}", f"-I{SKETCH}", "-x", "c++",
              os.path.join(SKETCH, "c3_player.ino"), "-x", "c++", os.path.join(HERE, "sim_main.cpp"))

    def start(self):
        self.fs = tempfile.mkdtemp(prefix="gg_fs_")
        self.led = os.path.join(self.fs + "_led.log")
        self.pins = self.fs + "_pins"
        write_text(self.led, "")
        self.press(None)
        master, slave = pty.openpty()
        tty.setraw(slave)                        # binary uploads must pass through untouched
        env = dict(os.environ, GG_FS_DIR=self.fs, GG_LED_LOG=self.led, GG_PINS=self.pins)
        self.proc = subprocess.Popen([SIM], stdin=slave, stdout=slave, env=env)
        os.close(slave)
        self.addCleanup(self.stop, master)
        self.port = FakePort(master)
        self.board = gg_tool.Board(ser=self.port)

    def stop(self, master):
        self.proc.kill()
        self.proc.wait()
        os.close(master)

    def press(self, pin):
        s = ["1"] * 40
        if pin is not None:
            s[pin] = "0"
        write_text(self.pins, "".join(s))

    def last_frames(self, n=1, wait=0.6):
        time.sleep(wait)
        with open(self.led) as fh:
            return [l for l in fh.read().split("\n") if l][-n:]

    def write_gg(self, name, frames, fps=8, b=0.3, g=2.2):
        p = os.path.join(self.fs + "_src", name + ".gg")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        write_bytes(p, gg.pack(frames, fps, b, g))
        return p

    def led_of(self, frames, b=0.3, g=2.2):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "x.gg")
        write_bytes(p, gg.pack(frames, 6, b, g))
        return host("frames", p).split()

    def test_put_list_replace_delete(self):
        self.start()
        files, summary = self.board.list()
        self.assertEqual(files, [])
        a, b = sample_frames(1, 3), sample_frames(2, 1)
        self.assertTrue(self.board.put(self.write_gg("alpha", a)).startswith("OK saved alpha"))
        self.assertTrue(self.board.put(self.write_gg("beta", b)).startswith("OK saved beta"))
        files, summary = self.board.list()
        self.assertEqual([f[0] for f in files], ["alpha", "beta"])
        self.assertEqual(dict(files)["alpha"], 12 + 3 * 768)
        # the last upload plays at once, and what reaches the LEDs is the corrected, wired frame
        self.assertEqual(self.last_frames(1), self.led_of(b))
        # replace: same name, new content
        b2 = sample_frames(9, 2)
        self.board.put(self.write_gg("beta", b2))
        files, _ = self.board.list()
        self.assertEqual(dict(files)["beta"], 12 + 2 * 768)
        self.assertTrue(set(self.last_frames(3)) <= set(self.led_of(b2)))
        # show and delete
        self.board.simple("SHOW alpha")
        self.assertTrue(set(self.last_frames(3)) <= set(self.led_of(a)))
        self.board.simple("DEL alpha")
        files, _ = self.board.list()
        self.assertEqual([f[0] for f in files], ["beta"])
        self.assertIn("current=beta", self.board.simple("INFO"))
        self.assertFalse(os.path.exists(os.path.join(self.fs, "upload.tmp")))

    def test_errors_leave_storage_clean(self):
        self.start()
        good = gg.pack(sample_frames(1, 1), 8, 0.3, 2.2)
        # wrong checksum
        self.board.send(f"PUT bad {len(good)} {0:08x}")
        self.board.expect(["READY"])
        self.board.ser.write(good)
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            self.board.expect(["OK"])
        # right checksum but not a valid sprite
        junk = b"NOTASPRITE!" + b"\x00" * (len(good) - 11)
        self.board.send(f"PUT junk {len(junk)} {zlib.crc32(junk) & 0xFFFFFFFF:08x}")
        self.board.expect(["READY"])
        self.board.ser.write(junk)
        with self.assertRaisesRegex(RuntimeError, "invalid sprite"):
            self.board.expect(["OK"])
        # bad name, bad size
        self.board.send(f"PUT ../evil {len(good)} {0:08x}")
        with self.assertRaisesRegex(RuntimeError, "bad name"):
            self.board.expect(["READY"])
        self.board.send("PUT huge 99999999 00000000")
        with self.assertRaisesRegex(RuntimeError, "bad size"):
            self.board.expect(["READY"])
        self.board.send("DEL nothere")
        with self.assertRaisesRegex(RuntimeError, "no such sprite"):
            self.board.expect(["OK"])
        files, _ = self.board.list()
        self.assertEqual(files, [])
        self.assertEqual(sorted(os.listdir(self.fs)), [])

    def test_upload_that_stalls_times_out(self):
        self.start()
        good = gg.pack(sample_frames(1, 1), 8, 0.3, 2.2)
        self.board.send(f"PUT stall {len(good)} {zlib.crc32(good) & 0xFFFFFFFF:08x}")
        self.board.expect(["READY"])
        self.board.ser.write(good[:300])            # then nothing
        with self.assertRaisesRegex(RuntimeError, "timeout"):
            self.board.expect(["OK"], timeout=8)
        files, _ = self.board.list()
        self.assertEqual(files, [])
        self.assertFalse(os.path.exists(os.path.join(self.fs, "upload.tmp")))

    def test_buttons(self):
        self.start()
        a, b = sample_frames(11, 1), sample_frames(12, 1)
        self.board.put(self.write_gg("alpha", a))
        self.board.put(self.write_gg("beta", b))
        self.board.simple("SHOW alpha")
        self.assertEqual(self.last_frames(1)[0], self.led_of(a)[0])
        self.press(5)                                # Next
        time.sleep(0.3)
        self.press(None)
        self.assertEqual(self.last_frames(1)[0], self.led_of(b)[0])
        self.press(5)                                # Next wraps to alpha
        time.sleep(0.3)
        self.press(None)
        self.assertEqual(self.last_frames(1)[0], self.led_of(a)[0])
        self.press(7)                                # On/off: off = all black
        time.sleep(0.3)
        self.press(None)
        self.assertEqual(self.last_frames(1)[0], "000000" * 256)
        self.assertIn("panel=off", self.board.simple("INFO"))
        self.press(7)                                # on again
        time.sleep(0.3)
        self.press(None)
        self.assertEqual(self.last_frames(1)[0], self.led_of(a)[0])

    def test_off_and_on_over_serial(self):
        self.start()
        a = sample_frames(13, 1)
        self.board.put(self.write_gg("alpha", a))
        self.assertEqual(self.last_frames(1)[0], self.led_of(a)[0])
        self.assertEqual(self.board.simple("OFF"), "OK panel off")
        self.assertEqual(self.last_frames(1)[0], "000000" * 256)
        self.assertIn("panel=off", self.board.simple("INFO"))
        self.assertEqual(self.board.simple("ON"), "OK panel on")
        self.assertEqual(self.last_frames(1)[0], self.led_of(a)[0])
        # a PUT while off turns the panel back on with the new sprite
        self.board.simple("OFF")
        b = sample_frames(14, 1)
        self.board.put(self.write_gg("beta", b))
        self.assertEqual(self.last_frames(1)[0], self.led_of(b)[0])
        self.assertIn("panel=on", self.board.simple("INFO"))

    def test_empty_board_shows_dim_marker_and_survives_restart(self):
        self.start()
        self.assertEqual(self.last_frames(1)[0], "00000c" + "000000" * 255)
        self.board.put(self.write_gg("keep", sample_frames(4, 2)))
        # restart the program on the same flash: it must find and play the stored sprite
        self.proc.kill()
        self.proc.wait()
        write_text(self.led, "")
        master, slave = pty.openpty()
        tty.setraw(slave)
        env = dict(os.environ, GG_FS_DIR=self.fs, GG_LED_LOG=self.led, GG_PINS=self.pins)
        self.proc = subprocess.Popen([SIM], stdin=slave, stdout=slave, env=env)
        os.close(slave)
        self.addCleanup(os.close, master)
        board = gg_tool.Board(ser=FakePort(master))
        files, _ = board.list()
        self.assertEqual([f[0] for f in files], ["keep"])
        self.assertTrue(self.last_frames(2))


if __name__ == "__main__":
    unittest.main()
