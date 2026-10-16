"""Tests for the C3 player: the .gg format, the C++ logic that runs on the board, and the upload tool.

Run from the c3 folder:   python3 -m unittest discover -s tests -v
Needs: g++, Pillow, pyserial (Linux, macOS or WSL), and the glow-grid repo for the parity checks:
set GLOWGRID_REPO=/path/to/glow-grid if this folder is not inside it.

What it proves:
  * gg_core.h (compiled on the PC) places and corrects every pixel exactly like grid_common.py,
    for all 16 wiring combinations and several brightness/gamma settings, including the 0.4 cap;
  * c3_player/c3_player.ino itself (compiled against small Arduino stand-ins) handles PUT, LIST, DEL, SHOW,
    bad input, a wrong checksum, a timeout and both buttons, driven by the real tools/gg_tool.py.
  * tools/png_to_gg.py converts a PNG into the same bytes gg_format.pack makes; gg_tool.py turns port failures into
    plain messages and picks the right COM port; the sketch compiles with the prototypes the Arduino IDE generates.
It does NOT test the real esp32 core, LittleFS on real flash, the real USB port (DTR), the NeoPixel timing or Bluetooth.
"""
import itertools
import os
import re
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


class IdeBuild(unittest.TestCase):
    """The Arduino IDE rewrites a sketch before compiling: it generates a prototype for every function and inserts
    them after the includes. A struct or typedef used in a parameter list must therefore come from a header, and
    a function may not be defined after its first use only by luck of the IDE. Mimic that rewrite and compile."""

    def test_compiles_with_generated_prototypes(self):
        src = open(os.path.join(SKETCH, "c3_player.ino")).read()
        import re
        protos = [m.group(1) + ";" for m in re.finditer(r"^((?:const char\*|void|bool|String|int)\s+\w+\([^)]*\))\s*\{", src, re.M)]
        self.assertGreater(len(protos), 10)
        cut = src.index("\n", src.rfind("#include")) + 1
        d = tempfile.mkdtemp()
        p = os.path.join(d, "ide_like.cpp")
        write_text(p, src[:cut] + "\n".join(protos) + "\n" + src[cut:])
        r = subprocess.run(["g++", "-std=c++17", "-fsyntax-only", f"-I{os.path.join(HERE, 'arduino_stub')}", f"-I{SKETCH}", "-x", "c++", p],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_compiles_without_the_editor_files(self):
        """The generated site files are git-ignored; a fresh clone must still build (and serve a not-built note at /)."""
        r = subprocess.run(["g++", "-std=c++17", "-fsyntax-only", "-DGG_NO_SITE", f"-I{os.path.join(HERE, 'arduino_stub')}", f"-I{SKETCH}",
                            "-x", "c++", os.path.join(SKETCH, "c3_player.ino")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)


class PngToGg(unittest.TestCase):
    """tools/png_to_gg.py: the converter cloners use for existing Glow Grid PNGs."""

    def setUp(self):
        try:
            from PIL import Image
            from PIL.PngImagePlugin import PngInfo
        except ImportError:
            self.skipTest("Pillow not installed")
        self.Image, self.PngInfo = Image, PngInfo
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import png_to_gg
        self.conv = png_to_gg
        self.d = tempfile.mkdtemp()

    def png(self, frames, meta=None, name="t_sprite.png"):
        img = self.Image.new("RGB", (16 * len(frames), 16))
        for k, fr in enumerate(frames):
            for i, px in enumerate(fr):
                img.putpixel((k * 16 + i % 16, i // 16), px)
        p = os.path.join(self.d, name)
        info = self.PngInfo()
        if meta is not None:
            import json
            info.add_text("glow-grid", json.dumps(meta, separators=(",", ":")))
        img.save(p, pnginfo=info)
        return p

    def test_round_trip_with_metadata(self):
        fr = sample_frames(21, 3)
        p = self.png(fr, {"brightness": 0.35, "gamma": 2.0, "cols": 16, "rows": 16, "frames": 3, "fps": 5})
        out = self.conv.convert(p)
        self.assertEqual(os.path.basename(out), "t.gg")          # _sprite dropped, like a board name
        with open(out, "rb") as fh:
            self.assertEqual(fh.read(), gg.pack(fr, 5, 0.35, 2.0))

    def test_defaults_without_metadata_and_overrides(self):
        fr = sample_frames(22, 2)
        p = self.png(fr, None, "plain.png")
        out = self.conv.convert(p)
        with open(out, "rb") as fh:
            self.assertEqual(fh.read(), gg.pack(fr, 6, 0.3, 2.2))
        out = self.conv.convert(p, fps=8, brightness=0.1)
        with open(out, "rb") as fh:
            self.assertEqual(fh.read(), gg.pack(fr, 8, 0.1, 2.2))

    def test_transparent_becomes_black_and_wrong_size_refused(self):
        img = self.Image.new("RGBA", (16, 16), (200, 100, 50, 0))
        img.putpixel((3, 3), (10, 20, 30, 255))
        p = os.path.join(self.d, "alpha.png")
        img.save(p)
        out = self.conv.convert(p)
        frames, fps, b, g = gg.unpack(open(out, "rb").read())
        self.assertEqual(frames[0][3 * 16 + 3], (10, 20, 30))
        self.assertEqual(frames[0][0], (0, 0, 0))
        self.assertEqual(sum(1 for px in frames[0] if px != (0, 0, 0)), 1)
        bad = os.path.join(self.d, "bad.png")
        self.Image.new("RGB", (20, 16)).save(bad)
        with self.assertRaises(SystemExit):
            self.conv.convert(bad)
        tall = os.path.join(self.d, "tall.png")
        self.Image.new("RGB", (16, 32)).save(tall)
        with self.assertRaises(SystemExit):
            self.conv.convert(tall)


class ToolErrors(unittest.TestCase):
    """gg_tool.py's handling around the real serial port, with the port faked (the real DTR behaviour is hardware-only)."""

    def test_write_timeout_becomes_a_plain_message(self):
        import serial as pyserial

        class DeadPort:
            timeout = 0.2
            def write(self, b): raise pyserial.SerialTimeoutException("Write timeout")
            def read(self, n=1): return b""
            def reset_input_buffer(self): pass
            def close(self): pass
        with self.assertRaisesRegex(TimeoutError, "not taking data"):
            gg_tool.Board(ser=DeadPort())

    def test_silent_board_times_out_with_a_hint(self):
        class SilentPort:
            timeout = 0.2
            def write(self, b): pass
            def read(self, n=1): time.sleep(0.01); return b""
            def reset_input_buffer(self): pass
            def close(self): pass
        with self.assertRaisesRegex(TimeoutError, "did not answer PING"):
            gg_tool.Board(ser=SilentPort())

    def test_find_port_prefers_the_espressif_device(self):
        import serial.tools.list_ports as lp

        class P:
            def __init__(self, device, vid): self.device, self.vid = device, vid
        orig = lp.comports
        try:
            lp.comports = lambda: [P("COM1", 0x1234), P("COM3", 0x303A)]
            self.assertEqual(gg_tool.find_port(), "COM3")
            lp.comports = lambda: [P("COM7", None)]            # only one port: take it
            self.assertEqual(gg_tool.find_port(), "COM7")
            lp.comports = lambda: [P("COM1", 0x1234), P("COM2", 0x5678)]   # ambiguous: refuse, name them
            with self.assertRaisesRegex(SystemExit, "COM1, COM2"):
                gg_tool.find_port()
            lp.comports = lambda: [P("COM3", 0x303A), P("COM4", 0x303A)]   # two boards: refuse
            with self.assertRaises(SystemExit):
                gg_tool.find_port()
        finally:
            lp.comports = orig


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
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_site.py")], check=True, capture_output=True)
        build(SIM, "-Wall", f"-I{os.path.join(HERE, 'arduino_stub')}", f"-I{SKETCH}", "-x", "c++",
              os.path.join(SKETCH, "c3_player.ino"), "-x", "c++", os.path.join(HERE, "sim_main.cpp"))

    def sim_env(self, wifi=False):
        """wifi=True lets the stand-in Wi-Fi library "join" at once (as 127.0.0.1) so the HTTP server starts."""
        env = dict(os.environ, GG_FS_DIR=self.fs, GG_LED_LOG=self.led, GG_PINS=self.pins, GG_NVS=self.fs + "_nvs",
                   GG_WIFI_LOG=self.fs + "_wifi.log", GG_HTTP_PORT_FILE=self.fs + "_port", GG_SETUP_PORT_FILE=self.fs + "_setupport")
        env.pop("GG_WIFI_SIM", None)
        env.pop("GG_SETUP_AUTO", None)
        env.pop("GG_TIME_SCALE", None)
        env.update(getattr(self, "extra_env", {}))
        env.pop("GG_WIFI_SCAN", None)
        if getattr(self, "scan_env", None) is not None:
            env["GG_WIFI_SCAN"] = self.scan_env
        if wifi or getattr(self, "wifi_sim", False):
            env["GG_WIFI_SIM"] = "1"
        return env

    def start(self, wifi=False):
        self.wifi_sim = wifi
        self.fs = tempfile.mkdtemp(prefix="gg_fs_")
        self.led = os.path.join(self.fs + "_led.log")
        self.pins = self.fs + "_pins"
        write_text(self.led, "")
        self.press(None)
        master, slave = pty.openpty()
        tty.setraw(slave)                        # binary uploads must pass through untouched
        self.proc = subprocess.Popen([SIM], stdin=slave, stdout=slave, env=self.sim_env(wifi))
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
        info = self.board.simple("INFO")
        self.assertIn("current=beta", info)
        # INFO carries the firmware version #defined in the sketch, so a board can be checked against the repo
        with open(os.path.join(SKETCH, "c3_player.ino")) as fh:
            fw = re.search(r"#define GG_FW_VERSION (\d+)", fh.read()).group(1)
        self.assertIn(f"OK fw={fw} ", info)
        self.assertFalse(os.path.exists(os.path.join(self.fs, "upload.tmp")))

    def test_crc_command_reports_the_stored_file(self):
        self.start()
        a = sample_frames(41, 3)
        path = self.write_gg("alpha", a)
        self.board.put(path)
        with open(path, "rb") as fh:
            blob = fh.read()
        want = f"OK crc={zlib.crc32(blob) & 0xFFFFFFFF:08x} size={len(blob)}"
        self.assertEqual(self.board.simple("CRC alpha"), want)
        # a different drawing under the same name gives a different checksum; the old one is gone
        self.board.put(self.write_gg("alpha", sample_frames(42, 3)))
        self.assertNotEqual(self.board.simple("CRC alpha"), want)
        # unknown and unsafe names are refused, and CRC leaves the panel and the list alone
        for bad in ("CRC nope", "CRC ../alpha", "CRC"):
            with self.assertRaises(RuntimeError, msg=bad):
                self.board.simple(bad)
        files, _ = self.board.list()
        self.assertEqual([f[0] for f in files], ["alpha"])

    def test_get_returns_the_stored_file_byte_for_byte(self):
        self.start()
        a = sample_frames(51, 5)
        path = self.write_gg("alpha", a, fps=12, b=0.45, g=2.6)
        self.board.put(path)
        with open(path, "rb") as fh:
            blob = fh.read()
        self.assertEqual(self.board.get("alpha"), blob)
        # the header (fps, brightness, gamma) comes back as stored, and the panel and list are untouched
        self.assertEqual(self.board.get("alpha")[8:12], blob[8:12])
        files, _ = self.board.list()
        self.assertEqual([f[0] for f in files], ["alpha"])
        for bad in ("nope", "../alpha", ""):
            with self.assertRaises(RuntimeError, msg=bad):
                self.board.get(bad)

    def test_real_editor_code_against_real_firmware(self):
        """web/js/board.js (SerialTransport + GgBoard) and export.js (ggBytes, ggDecode) driven through Node against the
        compiled firmware: Send, List, CRC, Load (GET) of a 2-frame and a 16-frame sprite, Delete. Catches the two sides drifting apart."""
        fs = tempfile.mkdtemp(prefix="gg_fs_")
        r = subprocess.run(["node", os.path.join(HERE, "board_e2e.js"), SIM, fs], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        import json
        o = json.loads(r.stdout.strip().splitlines()[-1])
        with open(os.path.join(SKETCH, "c3_player.ino")) as fh:
            fw = int(re.search(r"#define GG_FW_VERSION (\d+)", fh.read()).group(1))
        self.assertEqual(o["fw"], fw)
        self.assertEqual(o["listed"], ["big:12300", "small:1548"])
        self.assertTrue(o["smallBack"] and o["bigBack"], "GET must return exactly the bytes PUT stored")
        self.assertEqual(o["bigBytes"], 12 + 16 * 768, "the largest sprite the format allows")
        self.assertLess(o["bigMs"], 15000, "the editor gives up after 20 s")
        self.assertTrue(o["crcMatches"])
        self.assertEqual(o["decoded"], {"fps": 7, "brightness": 0.45, "gamma": 2.6, "frames": 2, "first": True})
        self.assertEqual((o["missing"], o["afterDelete"]), ("no such sprite", "no such sprite"))
        self.assertTrue(o["stillPlaysAfterGet"])

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
        self.press(7)                                # On/off: off = all black (acts on release since firmware 14)
        time.sleep(0.3)
        self.press(None)
        time.sleep(0.3)
        self.assertEqual(self.last_frames(1)[0], "000000" * 256)
        self.assertIn("panel=off", self.board.simple("INFO"))
        self.press(7)                                # on again; a 1 s hold is still a short press (the setup hold is 5 s)
        time.sleep(1.0)
        self.press(None)
        time.sleep(0.3)
        self.assertEqual(self.last_frames(1)[0], self.led_of(a)[0])
        self.assertEqual(self.log_count("softap GlowGrid-Setup"), 0, "a short press never opens setup")

    def test_holding_on_off_for_five_seconds_opens_setup_with_wifi_off(self):
        """Hold On/off (GPIO7) for 5 s: the setup network opens even with nothing saved and Wi-Fi off; the release does not switch the panel.
        Time runs 50x here, so a 0.4 s hold is 20 s."""
        self.extra_env = {"GG_TIME_SCALE": "50"}
        self.start()
        self.board.put(self.write_gg("alpha", sample_frames(31, 1)))
        self.assertIn("panel=on", self.board.simple("INFO"))
        self.assertNotIn("softap", self.wifi_log())
        self.press(7)
        self.wait_for(lambda: "softap GlowGrid-Setup" in self.wifi_log(), "setup mode after the hold", timeout=6)
        self.press(None)
        time.sleep(0.5)
        info = self.board.simple("INFO")
        self.assertIn("wifi=setup", info)
        self.assertIn("panel=on", info, "the release after a setup hold does not switch the panel")
        self.assertEqual(self.log_count("softap GlowGrid-Setup"), 1)

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

    def test_playback_speed_and_wrap(self):
        self.start()
        fr = sample_frames(31, 3)
        self.board.put(self.write_gg("anim", fr, fps=10))     # 100 ms per frame
        expected = self.led_of(fr)
        write_text(self.led, "")
        time.sleep(1.05)
        with open(self.led) as fh:
            shown = [l for l in fh.read().split("\n") if l]
        self.assertTrue(8 <= len(shown) <= 12, f"{len(shown)} frames in 1 s at 10 fps")
        for k in range(len(shown) - 1):                       # 0,1,2,0,1,2: each frame is the next one
            self.assertEqual(expected.index(shown[k + 1]), (expected.index(shown[k]) + 1) % 3)
        # a still renders once, then nothing more
        still = sample_frames(32, 1)
        self.board.put(self.write_gg("still", still))
        time.sleep(0.5)
        write_text(self.led, "")
        time.sleep(0.6)
        with open(self.led) as fh:
            self.assertEqual(fh.read(), "")

    def test_replace_the_playing_sprite_and_next_while_off(self):
        self.start()
        a, b = sample_frames(41, 1), sample_frames(42, 1)
        self.board.put(self.write_gg("alpha", a))
        self.board.put(self.write_gg("beta", b))
        self.board.simple("SHOW beta")
        b2 = sample_frames(43, 1)
        self.board.put(self.write_gg("beta", b2))             # replace what is on screen right now
        self.assertEqual(self.last_frames(1)[0], self.led_of(b2)[0])
        self.assertIn("current=beta", self.board.simple("INFO"))
        self.board.simple("OFF")
        self.press(5)                                         # Next while off: back on, same sprite
        time.sleep(0.3)
        self.press(None)
        self.assertEqual(self.last_frames(1)[0], self.led_of(b2)[0])
        self.assertIn("current=beta", self.board.simple("INFO"))

    def test_odd_input_on_the_serial_line(self):
        self.start()
        self.board.send("WHATEVER")
        with self.assertRaisesRegex(RuntimeError, "unknown command"):
            self.board.expect(["OK"])
        self.board.ser.write(b"X" * 300 + b"\n")              # too long: dropped, not executed, board still answers
        self.board.send("PING")
        self.assertEqual(self.board.expect(["PONG"]), "PONG")
        self.board.send("put")                                # lower case and missing arguments
        with self.assertRaisesRegex(RuntimeError, "usage"):
            self.board.expect(["OK"])
        self.board.send("show")
        with self.assertRaisesRegex(RuntimeError, "no such sprite"):
            self.board.expect(["OK"])
        long_name = "n" * 31
        self.board.put(self.write_gg(long_name, sample_frames(44, 1)))
        files, _ = self.board.list()
        self.assertEqual([f[0] for f in files], [long_name])
        self.board.send(f"PUT {'n' * 32} 780 00000000")
        with self.assertRaisesRegex(RuntimeError, "bad name"):
            self.board.expect(["READY"])

    def test_sprite_list_limit(self):
        self.start()
        fr = sample_frames(51, 1)
        for i in range(64):                                   # MAX_SPRITES is 64
            self.board.put(self.write_gg(f"s{i:02d}", fr))
        files, summary = self.board.list()
        self.assertEqual(len(files), 64)
        self.assertIn("64 files", summary)
        # a 65th name is refused before any bytes are sent, and nothing is stored
        self.board.send(f"PUT s64 780 00000000")
        with self.assertRaisesRegex(RuntimeError, "holds 64 sprites"):
            self.board.expect(["READY"])
        self.assertEqual(len(os.listdir(self.fs)), 64, "nothing stored unseen")
        # replacing one of the 64 is still allowed
        self.assertTrue(self.board.put(self.write_gg("s10", sample_frames(52, 1))).startswith("OK saved s10"))
        self.assertEqual(len(self.board.list()[0]), 64)

    def test_empty_board_shows_dim_marker_and_survives_restart(self):
        self.start()
        self.assertEqual(self.last_frames(1)[0], "00000c" + "000000" * 255)
        self.board.put(self.write_gg("keep", sample_frames(4, 2)))
        # restart the program on the same flash: it must find and play the stored sprite
        board = self.restart()
        files, _ = board.list()
        self.assertEqual([f[0] for f in files], ["keep"])
        self.assertTrue(self.last_frames(2))

    def restart(self):
        """Power cycle: the program starts again on the same flash. Returns a fresh Board."""
        self.proc.kill()
        self.proc.wait()
        write_text(self.led, "")
        for suffix in ("_port", "_setupport"):
            if os.path.exists(self.fs + suffix):
                os.remove(self.fs + suffix)
        master, slave = pty.openpty()
        tty.setraw(slave)
        self.proc = subprocess.Popen([SIM], stdin=slave, stdout=slave, env=self.sim_env())
        os.close(slave)
        self.addCleanup(os.close, master)
        return gg_tool.Board(ser=FakePort(master))

    def test_power_loss_mid_upload_leaves_no_temp_file(self):
        self.start()
        self.board.put(self.write_gg("keep", sample_frames(23, 1)))
        good = gg.pack(sample_frames(24, 2), 8, 0.3, 2.2)
        self.board.send(f"PUT half {len(good)} {zlib.crc32(good) & 0xFFFFFFFF:08x}")
        self.board.expect(["READY"])
        self.board.ser.write(good[:900])                      # power goes while the rest is in flight
        time.sleep(0.3)
        self.assertTrue(os.path.exists(os.path.join(self.fs, "upload.tmp")), "the partial file exists at the moment of the cut")
        board = self.restart()
        self.assertFalse(os.path.exists(os.path.join(self.fs, "upload.tmp")), "boot clears a leftover temp file")
        self.assertEqual([f[0] for f in board.list()[0]], ["keep"])
        self.assertIn("panel=on", board.simple("INFO"))

    def test_rotate_cycles_sprites_and_survives_a_power_cycle(self):
        self.start()
        a, b, c = sample_frames(61, 2), sample_frames(62, 1), sample_frames(63, 1)
        self.board.put(self.write_gg("alpha", a, fps=10))
        self.board.put(self.write_gg("beta", b))
        self.board.put(self.write_gg("gamma", c))
        self.board.simple("SHOW alpha")
        want_b = self.led_of(b)[0]                            # built now, not inside the timed sequence
        self.assertIn("rotate=0", self.board.simple("INFO"))
        # bad values are refused
        for bad in ("ROTATE", "ROTATE -1", "ROTATE x", "ROTATE 99999999"):
            self.board.send(bad)
            with self.assertRaisesRegex(RuntimeError, "usage"):
                self.board.expect(["OK"])
        # every second: alpha -> beta -> gamma -> alpha, in list order; alpha keeps animating meanwhile
        self.assertEqual(self.board.simple("ROTATE 1"), "OK rotate 1")
        self.assertIn("rotate=1", self.board.simple("INFO"))
        write_text(self.led, "")
        time.sleep(0.7)
        self.assertIn("current=alpha", self.board.simple("INFO"))
        self.assertGreater(len(self.last_frames(50, wait=0)), 4, "the animation runs during the interval")
        time.sleep(0.6)
        self.assertIn("current=beta", self.board.simple("INFO"))
        self.assertEqual(self.last_frames(1, wait=0)[0], want_b)
        time.sleep(1.0)
        self.assertIn("current=gamma", self.board.simple("INFO"))
        time.sleep(1.0)
        self.assertIn("current=alpha", self.board.simple("INFO"))
        # Next (or Play) restarts the interval for the sprite it lands on
        self.press(5); time.sleep(0.3); self.press(None)
        self.assertIn("current=beta", self.board.simple("INFO"))
        time.sleep(0.5)
        self.assertIn("current=beta", self.board.simple("INFO"), "a fresh interval after Next")
        # off pauses rotation; on restarts the interval
        self.board.simple("OFF")
        time.sleep(1.3)
        self.assertIn("current=beta", self.board.simple("INFO"))
        self.board.simple("ON")
        time.sleep(1.3)
        self.assertIn("current=gamma", self.board.simple("INFO"))
        # a power cycle keeps the setting and keeps cycling
        board = self.restart()
        self.assertIn("rotate=1", board.simple("INFO"))
        self.assertEqual([f[0] for f in board.list()[0]], ["alpha", "beta", "gamma"], "the setting file is not a sprite")
        time.sleep(1.3)
        self.assertIn("current=beta", board.simple("INFO"))
        # 0 switches it off, also across a restart
        self.assertEqual(board.simple("ROTATE 0"), "OK rotate 0")
        time.sleep(1.3)
        self.assertIn("current=beta", board.simple("INFO"))
        board = self.restart()
        self.assertIn("rotate=0", board.simple("INFO"))

    def test_off_survives_a_power_cycle(self):
        # Decided 2026-10-15: an unplugged-and-replugged board that was off comes back dark.
        self.start()
        a = sample_frames(21, 1)
        self.board.put(self.write_gg("alpha", a))
        self.assertEqual(self.board.simple("OFF"), "OK panel off")
        board = self.restart()
        self.assertIn("panel=off", board.simple("INFO"))
        self.assertTrue(all(f == "000000" * 256 for f in self.last_frames(5)), "nothing lit after the restart")
        self.assertEqual([f[0] for f in board.list()[0]], ["alpha"], "the marker is not a sprite")
        board.simple("ON")
        self.assertEqual(self.last_frames(1)[0], self.led_of(a)[0])
        board = self.restart()                                 # and ON is remembered too
        self.assertIn("panel=on", board.simple("INFO"))
        self.assertEqual(self.last_frames(1)[0], self.led_of(a)[0])
        # SHOW, PUT and the Next button while off also clear the remembered off
        board.simple("OFF"); board.simple("SHOW alpha")
        board = self.restart()
        self.assertIn("panel=on", board.simple("INFO"))
        board.simple("OFF")
        self.press(5); time.sleep(0.3); self.press(None)
        board = self.restart()
        self.assertIn("panel=on", board.simple("INFO"))
        board.simple("OFF")
        board.put(self.write_gg("beta", sample_frames(22, 1)))
        board = self.restart()
        self.assertIn("panel=on", board.simple("INFO"))


    # ---- Wi-Fi (firmware 9) ----
    def wifi_log(self):
        p = self.fs + "_wifi.log"
        return open(p).read() if os.path.exists(p) else ""

    def wait_for(self, fn, what, timeout=6.0):
        end = time.time() + timeout
        while time.time() < end:
            v = fn()
            if v:
                return v
            time.sleep(0.05)
        self.fail("timed out waiting for " + what)

    def http_base(self):
        """Waits until the board's HTTP server is up (the simulator writes its port to a file)."""
        def port():
            p = self.fs + "_port"
            return open(p).read().strip() if os.path.exists(p) and open(p).read().strip() else None
        return "127.0.0.1:" + self.wait_for(port, "the HTTP server to start")

    def http(self, method, path, body=None, headers=None, base=None):
        """-> (status, headers, body bytes); the 4xx/5xx body is returned too."""
        import urllib.request, urllib.error
        req = urllib.request.Request("http://" + (base or self.http_base()) + path, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_wifi_credentials_over_usb(self):
        self.start(wifi=True)
        self.assertTrue(self.board.wifi_status().startswith("OK wifi=off "))
        self.assertIn("wifi=off ip=-", self.board.simple("INFO"))
        self.assertEqual(self.wifi_log(), "", "nothing joins until credentials are set")
        # a name with spaces and a password with symbols survive the trip (hex on the wire)
        ssid, pw = "My Home Net", 'p@ss "word" #1'
        self.assertTrue(self.board.wifi_set(ssid, pw).startswith("OK wifi saved"))
        st = self.wait_for(lambda: "wifi=connected" in self.board.wifi_status() and self.board.wifi_status(), "joining")
        self.assertIn("ip=127.0.0.1", st)
        self.assertIn("host=glowgrid.local", st)
        self.assertTrue(st.endswith("ssid=" + ssid))
        self.assertNotIn("p@ss", st, "the password is never printed")
        self.assertNotIn("p@ss", self.board.simple("INFO"))
        log = self.wifi_log()
        self.assertIn(f"begin {ssid} {pw}", log)
        self.assertIn("hostname glowgrid", log)
        self.assertIn("mdns begin glowgrid", log)
        self.assertIn("mdns service http.tcp 80", log)
        self.assertIn("wifi=connected ip=127.0.0.1", self.board.simple("INFO"))
        self.assertRegex(self.board.simple("INFO"), r"gap_ms=\d+")
        # stored in NVS, so a power cycle joins again by itself
        os.remove(self.fs + "_wifi.log")
        board = self.restart()
        st = self.wait_for(lambda: "wifi=connected" in board.wifi_status() and board.wifi_status(), "rejoining after a power cycle")
        self.assertTrue(st.endswith("ssid=" + ssid))
        self.assertIn(f"begin {ssid} {pw}", self.wifi_log())
        # the sprites are not touched by any of this
        self.assertEqual(board.list()[0], [])
        # an open network, then clear
        self.assertTrue(board.wifi_set("Cafe", "").startswith("OK wifi saved"))
        self.assertIn("begin Cafe (open)", self.wifi_log())
        self.assertTrue(board.wifi_clear().startswith("OK wifi cleared"))
        self.assertTrue(board.wifi_status().startswith("OK wifi=off "))
        board = self.restart()
        self.assertTrue(board.wifi_status().startswith("OK wifi=off "))

    def test_wifi_command_errors(self):
        self.start(wifi=True)
        for line, why in [("WIFI SET", "usage"), ("WIFI SET zz -", "usage"), ("WIFI SET 4142 abc", "usage|password"), ("WIFI SET 4142 6162", "password"),
                          ("WIFI NOPE", "usage"), ("WIFI", "usage"), ("WIFI SET " + "41" * 33 + " -", "usage")]:
            self.board.send(line)
            with self.assertRaisesRegex(RuntimeError, why, msg=line):
                self.board.expect(["OK"])
        self.assertEqual(self.wifi_log(), "", "a bad command stores and joins nothing")
        self.assertTrue(self.board.wifi_status().startswith("OK wifi=off "))
        # the longest legal name and password fit on one command line
        self.assertTrue(self.board.wifi_set("n" * 32, "p" * 63).startswith("OK wifi saved"))
        self.assertIn("begin " + "n" * 32 + " " + "p" * 63, self.wifi_log())

    def test_wifi_scan(self):
        # one name heard twice (keep the strongest), a hidden network, an open one, a name with spaces and non-ASCII, an illegal 33-byte name
        self.scan_env = ";".join(["Home Net|-70|1", "Cafe Open|-55|0", "|-30|1", "Café ☕|-80|1", "Home Net|-42|1", "x" * 33 + "|-20|1", "Far|-91|1"])
        self.start(wifi=True)
        nets = self.board.wifi_scan()
        self.assertEqual(nets, [("Home Net", -42, True), ("Cafe Open", -55, False), ("Café ☕", -80, True), ("Far", -91, True)])
        self.assertIn("scan", self.wifi_log())
        self.assertTrue(self.board.wifi_status().startswith("OK wifi=off "), "scanning saves and joins nothing")
        self.assertNotIn("begin", self.wifi_log())
        # a scan does not disturb a saved network
        self.board.wifi_set("Home Net", "password1")
        self.wait_for(lambda: "wifi=connected" in self.board.wifi_status() and self.board.wifi_status(), "joining")
        self.assertEqual(len(self.board.wifi_scan()), 4)
        self.assertIn("ssid=Home Net", self.board.wifi_status())
        self.assertIn("wifi=connected", self.board.simple("INFO"))

    def test_wifi_scan_edges(self):
        self.scan_env = ""
        self.start(wifi=True)
        self.assertEqual(self.board.wifi_scan(), [], "nothing heard is an empty list, not an error")

    def test_wifi_scan_is_capped_and_sorted(self):
        self.scan_env = ";".join(f"net{i:02d}|{-30 - i}|1" for i in range(30))
        self.start(wifi=True)
        nets = self.board.wifi_scan()
        self.assertEqual(len(nets), 20, "capped at 20")
        self.assertEqual([n[1] for n in nets], sorted((n[1] for n in nets), reverse=True))

    def multipart(self, blob, name="x.gg", field="file"):
        b = "----t" + os.urandom(6).hex()
        body = (f'--{b}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode() \
            + blob + f"\r\n--{b}--\r\n".encode()
        return body, {"Content-Type": "multipart/form-data; boundary=" + b}

    def test_http_api(self):
        self.start(wifi=True)
        self.board.wifi_set("Net", "password1")
        base = self.http_base()
        st, hd, body = self.http("GET", "/ping")
        self.assertEqual((st, body), (200, b"PONG\n"))
        # every reply is readable from the https editor page (CORS), and a private-network pre-flight is answered
        self.assertEqual(hd["Access-Control-Allow-Origin"], "*")
        st, hd, body = self.http("OPTIONS", "/put?name=a", headers={"Origin": "https://dwooods.github.io", "Access-Control-Request-Method": "POST",
                                                                  "Access-Control-Request-Private-Network": "true"})
        self.assertEqual((st, body), (204, b""))
        self.assertEqual(hd["Access-Control-Allow-Private-Network"], "true")
        self.assertEqual(hd["Access-Control-Allow-Origin"], "*")
        st, _, body = self.http("GET", "/info")
        self.assertEqual(st, 200)
        self.assertIn(b"wifi=connected ip=127.0.0.1", body)
        self.assertEqual(self.http("GET", "/list")[2].decode(), "OK 0 files, 1500000 bytes free\n")
        # a full 16-frame sprite (12,300 bytes, zero bytes included) goes in intact through multipart, with and without the optional checks
        frames = [[(((i * 7 + f) & 255), ((i * 3) & 255), 0) for i in range(256)] for f in range(16)]
        blob = gg.pack(frames, 12, 0.3, 2.2)
        self.assertEqual(len(blob), 12300)
        crc = zlib.crc32(blob) & 0xFFFFFFFF
        body, h = self.multipart(blob)
        st, _, out = self.http("POST", f"/put?name=big&size={len(blob)}&crc={crc:08x}", body, h)
        self.assertEqual((st, out), (200, b"OK saved big\n"))
        with open(os.path.join(self.fs, "big.gg"), "rb") as fh:
            self.assertEqual(fh.read(), blob)
        small = gg.pack(sample_frames(5, 2), 8, 0.3, 2.2)
        body, h = self.multipart(small)
        self.assertEqual(self.http("POST", "/put?name=small", body, h)[2], b"OK saved small\n")
        self.assertEqual(self.last_frames(2)[-1] in self.led_of(sample_frames(5, 2)), True, "an HTTP upload plays at once, like USB")
        files, _ = self.board.list()                         # USB and Wi-Fi see the same flash
        self.assertEqual(dict(files), {"big": 12300, "small": len(small)})
        self.assertEqual(self.http("GET", "/list")[2].decode().splitlines()[:2], ["FILE big 12300", f"FILE small {len(small)}"])
        # download byte for byte, with the board's own CRC
        st, hd, got = self.http("GET", "/get?name=big")
        self.assertEqual((st, got), (200, blob))
        self.assertEqual(hd["Content-Length"], "12300")
        self.assertEqual(self.http("GET", "/crc?name=big")[2].decode(), f"OK crc={crc:08x} size=12300\n")
        # the other commands
        self.assertEqual(self.http("POST", "/show?name=big")[2], b"OK showing big\n")
        self.assertIn("current=big", self.board.simple("INFO"))
        self.assertEqual(self.http("POST", "/off")[2], b"OK panel off\n")
        self.assertIn("panel=off", self.board.simple("INFO"))
        self.assertEqual(self.http("POST", "/on")[2], b"OK panel on\n")
        self.assertEqual(self.http("POST", "/rotate?s=30")[2], b"OK rotate 30\n")
        self.assertIn("rotate=30", self.board.simple("INFO"))
        self.assertEqual(self.http("POST", "/rotate?s=0")[2], b"OK rotate 0\n")
        self.assertEqual(self.http("POST", "/del?name=big")[2], b"OK deleted big\n")
        self.assertFalse(os.path.exists(os.path.join(self.fs, "big.gg")))
        # errors come back as the same ERR text with a 4xx status, and leave the flash clean
        for method, path, body_, hd_, code, text in [
            ("GET", "/get?name=nope", None, None, 404, b"ERR no such sprite"),
            ("GET", "/crc?name=../x", None, None, 404, b"ERR no such sprite"),
            ("POST", "/show?name=nope", None, None, 404, b"ERR no such sprite"),
            ("POST", "/del?name=nope", None, None, 404, b"ERR no such sprite"),
            ("POST", "/rotate?s=-1", None, None, 400, b"ERR usage: ROTATE"),
            ("POST", "/rotate", None, None, 400, b"ERR usage: ROTATE"),
            ("GET", "/nothing", None, None, 404, b"ERR not found"),
            ("GET", "/put?name=a", None, None, 404, b"ERR not found"),      # PUT is POST-only
            ("POST", "/put?name=a", b"\x00\x01raw", {"Content-Type": "application/octet-stream"}, 400, b"ERR send the sprite as multipart"),
        ]:
            st, _, out = self.http(method, path, body_, hd_)
            self.assertEqual(st, code, path)
            self.assertTrue(out.startswith(text), (path, out))
        body, h = self.multipart(small)
        self.assertEqual(self.http("POST", "/put?name=bad%20name", body, h)[2][:7], b"ERR bad")
        body, h = self.multipart(small)
        self.assertEqual(self.http("POST", f"/put?name=a&crc=00000000", body, h)[2], b"ERR checksum mismatch\n")
        body, h = self.multipart(b"XX" + small[2:])                     # right size, wrong magic
        self.assertIn(b"ERR invalid sprite: bad magic", self.http("POST", "/put?name=a", body, h)[2])
        body, h = self.multipart(small + b"\0")                         # not a whole number of frames
        self.assertIn(b"ERR invalid sprite", self.http("POST", "/put?name=a", body, h)[2])
        body, h = self.multipart(b"\0" * 60000)                         # bigger than any sprite
        self.assertIn(b"ERR bad size", self.http("POST", "/put?name=a", body, h)[2])
        body, h = self.multipart(small)
        self.assertEqual(self.http("POST", "/put?name=a&size=999999999", body, h)[2], b"ERR bad size\n")
        self.assertEqual(sorted(os.listdir(self.fs)), ["small.gg"], "no temp file or half-saved sprite left behind")
        # and the board still answers on USB afterwards
        self.board.send("PING")
        self.assertEqual(self.board.expect(["PONG"]), "PONG")

    def test_http_tool_mode(self):
        """gg_tool.HttpBoard (the --host mode) does what the USB Board does, against the same firmware."""
        self.start(wifi=True)
        self.board.wifi_set("Net", "password1")
        hb = gg_tool.HttpBoard(self.http_base())
        self.assertEqual(hb.list()[0], [])
        a = self.write_gg("alpha", sample_frames(21, 3))
        self.assertTrue(hb.put(a).startswith("OK saved alpha"))
        files, summary = hb.list()
        self.assertEqual(files, [("alpha", 12 + 3 * 768)])
        self.assertEqual(hb.get("alpha"), open(a, "rb").read())
        self.assertIn("fw=", hb.simple("INFO"))
        self.assertEqual(hb.simple("SHOW alpha"), "OK showing alpha")
        self.assertEqual(hb.simple("OFF"), "OK panel off")
        self.assertEqual(hb.simple("ON"), "OK panel on")
        self.assertEqual(hb.simple("ROTATE 5"), "OK rotate 5")
        self.assertEqual(hb.simple("DEL alpha"), "OK deleted alpha")
        with self.assertRaisesRegex(RuntimeError, "no such sprite"):
            hb.simple("DEL alpha")
        with self.assertRaisesRegex(RuntimeError, "no such sprite"):
            hb.get("alpha")
        with self.assertRaises(ValueError):
            hb.simple("WIFI STATUS")                    # Wi-Fi settings are USB-only
        with self.assertRaisesRegex(TimeoutError, "cannot reach the board"):
            gg_tool.HttpBoard("127.0.0.1:1")


    def test_editor_http_board_against_the_firmware(self):
        """web/js/board.js HttpBoard (the Board card's Wi-Fi side) driven through Node against the compiled firmware's real HTTP
        server: Send (multipart, 16 frames with zero bytes), List, Info, Load with CRC check, Play, lights, rotate, Delete, and the
        board's own error messages. Catches the editor and the firmware API drifting apart."""
        self.start(wifi=True)
        self.board.wifi_set("Net", "password1")
        base = self.http_base()
        r = subprocess.run(["node", os.path.join(HERE, "board_http_e2e.js"), base], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        import json
        o = json.loads(r.stdout.strip().splitlines()[-1])
        with open(os.path.join(SKETCH, "c3_player.ino")) as fh:
            fw = int(re.search(r"#define GG_FW_VERSION (\d+)", fh.read()).group(1))
        self.assertEqual(o["hello"], "PONG")
        self.assertTrue(o["bigHasZero"], "the test file must contain zero bytes: that is what a raw POST body loses")
        self.assertEqual(o["progress"], [[0, 1548], [1548, 1548]])
        self.assertEqual(o["listed"], ["big:12300", "small:1548"])
        self.assertTrue(o["freeIsNumber"])
        self.assertEqual(o["info"], {"fw": fw, "current": "big", "sprites": "2", "panel": "on", "wifi": "connected", "ip": "127.0.0.1"})
        self.assertTrue(o["smallBack"] and o["bigBack"], "GET must return exactly the bytes PUT stored")
        self.assertTrue(o["crcMatches"])
        self.assertEqual(o["decoded"], {"fps": 7, "brightness": 0.45, "gamma": 2.6, "frames": 2, "first": True})
        for k in ("missingGet", "missingShow", "missingDel"):
            self.assertEqual(o[k], "no such sprite", k)
        self.assertNotEqual(o["badSprite"], "no error"); self.assertNotEqual(o["badName"], "no error")
        self.assertEqual(o["afterBad"], ["big", "small"], "a refused upload leaves storage as it was")
        self.assertTrue(o["show"].startswith("OK showing")); self.assertEqual(o["currentAfterShow"], "small")
        self.assertEqual((o["panelOff"], o["panelOn"]), ("off", "on"))
        self.assertEqual(o["rotateInfo"], "300")
        self.assertTrue(o["del"].startswith("OK deleted")); self.assertEqual(o["afterDel"], ["big"])
        self.assertTrue(o["closedOnce"])
        self.assertIn("cannot reach the board at 127.0.0.1:1", o["unreachable"])

    def test_firmware_serves_the_editor_page(self):
        """GET / (and /index.html) returns the gzipped editor generated by tools/build_site.py, with the exact length and CRC the generated
        header promises, decoded on the fly from base64 text. iPhone Safari needs the editor to come from the board itself."""
        import gzip
        self.start(wifi=True)
        self.board.wifi_set("Net", "password1")
        base = self.http_base()
        with open(os.path.join(SKETCH, "site_data.h")) as fh:
            hdr = fh.read()
        want_len = int(re.search(r"#define GG_SITE_LEN (\d+)", hdr).group(1))
        want_crc = int(re.search(r"#define GG_SITE_CRC 0x([0-9a-f]+)UL", hdr).group(1), 16)
        for path in ("/", "/index.html"):
            status, headers, body = self.http("GET", path, base=base)
            self.assertEqual(status, 200, path)
            self.assertEqual(headers["Content-Encoding"], "gzip")
            self.assertTrue(headers["Content-Type"].startswith("text/html"))
            self.assertEqual(int(headers["Content-Length"]), want_len)
            self.assertEqual(len(body), want_len)
            self.assertEqual(zlib.crc32(body) & 0xFFFFFFFF, want_crc, "the bytes the board sends must be exactly the generated gzip")
            html = gzip.decompress(body).decode("utf-8")
            self.assertIn("<title>Glow Grid</title>", html)
            self.assertIn("class HttpBoard", html)             # board.js is inlined
            self.assertIn('<meta name="gg-site" content="glow-grid-v', html)
            self.assertNotIn('src="js/', html)                 # nothing left to fetch: one page, one request
            self.assertNotIn('rel="manifest"', html)
        status, _, _ = self.http("POST", "/", body=b"", base=base)
        self.assertEqual(status, 404)
        status, _, body = self.http("GET", "/ping", base=base)  # the API next to it is unchanged
        self.assertEqual((status, body.strip()), (200, b"PONG"))


    # ---- setup mode (firmware 13): the board hosts GlowGrid-Setup and a page to pick a network ----
    def setup_base(self):
        def port():
            p = self.fs + "_setupport"
            return open(p).read().strip() if os.path.exists(p) and open(p).read().strip() else None
        return "127.0.0.1:" + self.wait_for(port, "the setup page's server to start")

    def log_count(self, text):
        return self.wifi_log().count(text)

    def pixel0(self):
        with open(self.led) as fh:
            lines = [l for l in fh.read().split("\n") if l]
        return lines[-1][:6] if lines else ""

    def test_setup_mode_serves_a_page_and_saves_a_network(self):
        """WIFI SETUP (the USB form of the editor's button) opens GlowGrid-Setup with a catch-all DNS and the setup page; the page lists the
        scan, saves a network, and the board then closes the setup network and joins it. The API is not served on the setup network."""
        self.scan_env = ";".join(["Home Net|-42|1", "Cafe Open|-60|0"])
        self.start(wifi=True)
        self.board.put(self.write_gg("alpha", sample_frames(31, 1)))
        self.board.wifi_set("Old Net", "password1")
        self.wait_for(lambda: "wifi=connected" in self.board.wifi_status() and self.board.wifi_status(), "joining the old network")
        api = self.http_base()
        self.assertEqual(self.http("GET", "/ping", base=api)[2], b"PONG\n")
        self.assertEqual(self.log_count("softap GlowGrid-Setup"), 0, "setup mode does not start by itself in this test")
        self.board.send("WIFI SETUP")
        self.assertIn("OK setup mode starts", self.board.expect(["OK"]))
        self.wait_for(lambda: "softap GlowGrid-Setup" in self.wifi_log(), "the setup network")
        self.assertIn("dns start", self.wifi_log())
        self.assertIn("wifi=setup ip=-", self.board.simple("INFO"))
        base = self.setup_base()
        # the page: the real one, at / and at any other address (a phone's "is there internet" check lands on it)
        for path in ("/", "/generate_204", "/hotspot-detect.html"):
            st, hd, body = self.http("GET", path, base=base)
            self.assertEqual(st, 200, path)
            self.assertTrue(hd["Content-Type"].startswith("text/html"))
            self.assertIn(b"Glow Grid Wi-Fi setup", body)
        self.assertLess(len(body), 5000, "the setup page stays small")
        self.assertIn(b"closes in", body, "the page counts the close down after Save")
        # the scan the page shows, in the same text form WIFI SCAN uses (name as hex)
        st, _, scan = self.http("GET", "/scan", base=base)
        self.assertEqual(st, 200)
        self.assertEqual(scan.decode().splitlines(), ["NET " + b"Home Net".hex() + " -42 1", "NET " + b"Cafe Open".hex() + " -60 0", "OK networks=2"])
        # the API is not on the setup network, and the old API port no longer answers
        self.assertEqual(self.http("GET", "/list", base=base)[2].count(b"Glow Grid Wi-Fi setup"), 1, "/list on the setup network is just the page")
        import urllib.error
        with self.assertRaises(Exception):
            self.http("GET", "/ping", base=api)
        # the panel shows the pulse on LED 0 (blue only, dim) while the sprite carries on
        time.sleep(0.4)
        p0 = self.pixel0()
        self.assertTrue(p0.startswith("0000") and 3 <= int(p0[4:], 16) <= 43, p0)
        # a bad password is refused with the board's words and nothing is stored
        form = {"Content-Type": "application/x-www-form-urlencoded"}
        st, _, body = self.http("POST", "/save", ("s=" + b"Home Net".hex() + "&p=" + b"short".hex()).encode(), form, base=base)
        self.assertEqual(st, 400)
        self.assertIn(b"password must be 8 to 63", body)
        self.assertNotIn("begin Home Net", self.wifi_log())
        # a good one: stored, then the setup network goes away and the board joins it
        st, _, body = self.http("POST", "/save", ("s=" + b"Home Net".hex() + "&p=" + "p@ss word 1".encode().hex()).encode(), form, base=base)
        self.assertEqual((st, body), (200, b"OK saved\n"))
        # the setup network stays up for 8 s after Save so the page can count down; it is still there after 3 s
        time.sleep(3.0)
        self.assertNotIn("softap off", self.wifi_log(), "the setup network must not close within 3 s of Save")
        self.assertNotIn("begin Home Net", self.wifi_log(), "joining waits for the setup network to close")
        self.wait_for(lambda: "softap off" in self.wifi_log() and "dns stop" in self.wifi_log(), "setup mode to close", timeout=12)
        self.wait_for(lambda: "begin Home Net p@ss word 1" in self.wifi_log(), "joining the new network")
        st = self.wait_for(lambda: "wifi=connected" in self.board.wifi_status() and self.board.wifi_status(), "connected")
        self.assertTrue(st.endswith("ssid=Home Net"))
        self.assertEqual(self.http("GET", "/ping", base=self.http_base())[2], b"PONG\n", "the API is back")
        self.assertEqual([f[0] for f in self.board.list()[0]], ["alpha"], "the sprites were not touched")
        time.sleep(0.4)
        self.assertEqual(self.pixel0(), self.led_of(sample_frames(31, 1))[0][:6], "LED 0 is the sprite's again")
        # an open network goes through with "-" as the password; and a second WIFI SETUP while on says so
        self.board.send("WIFI SETUP"); self.board.expect(["OK"])
        self.wait_for(lambda: self.log_count("softap GlowGrid-Setup") == 2, "setup mode again")
        self.board.send("WIFI SETUP")
        self.assertIn("already on", self.board.expect(["OK"]))

    def test_the_editor_button_starts_setup_over_http(self):
        """POST /setup (the editor's 'Change the board's Wi-Fi') answers first and starts setup mode a moment later."""
        self.start(wifi=True)
        self.board.wifi_set("Net", "password1")
        api = self.http_base()
        st, hd, body = self.http("POST", "/setup", b"", base=api)
        self.assertEqual(st, 200)
        self.assertIn(b"OK setup mode starts", body)
        self.assertEqual(hd["Access-Control-Allow-Origin"], "*")
        self.wait_for(lambda: "softap GlowGrid-Setup" in self.wifi_log(), "setup mode")
        self.assertIn("wifi=setup", self.board.simple("INFO"))
        self.assertEqual(self.http("GET", "/", base=self.setup_base())[0], 200)

    def test_a_save_just_before_the_timeout_still_gets_the_join_watch(self):
        """Save 6 s (sped-up) before the 5-minute timeout: the 8 s close delay runs past it. The save must still finish through the join
        watch, so a network that does not join reopens setup, instead of the timeout ending setup with nothing watching."""
        self.extra_env = {"GG_SETUP_AUTO": "1", "GG_TIME_SCALE": "20"}
        self.start()
        self.wait_for(lambda: "softap GlowGrid-Setup" in self.wifi_log(), "setup mode at power-up with nothing saved")
        t0 = time.time()
        base = self.setup_base()
        time.sleep(max(0.0, 14.7 - (time.time() - t0)))          # 294 s of sped-up time; the timeout is at 300 s
        form = {"Content-Type": "application/x-www-form-urlencoded"}
        st, _, body = self.http("POST", "/save", ("s=" + b"Late Net".hex() + "&p=" + "password3".encode().hex()).encode(), form, base=base)
        self.assertEqual((st, body), (200, b"OK saved\n"))
        self.wait_for(lambda: "softap off" in self.wifi_log(), "setup mode to close", timeout=6)
        self.wait_for(lambda: "begin Late Net password3" in self.wifi_log(), "joining the saved network")
        self.wait_for(lambda: self.log_count("softap GlowGrid-Setup") == 2, "setup reopening because it did not join", timeout=8)

    def test_a_second_save_replaces_the_first_and_a_bad_one_changes_nothing(self):
        """Two good Saves inside the 8 s window: only the second network is joined, and the close waits 8 s from the second. A refused
        Save in between (400) neither cancels nor restarts the close."""
        self.extra_env = {"GG_SETUP_AUTO": "1"}
        self.start()
        self.wait_for(lambda: "softap GlowGrid-Setup" in self.wifi_log(), "setup mode at power-up with nothing saved")
        base = self.setup_base()
        form = {"Content-Type": "application/x-www-form-urlencoded"}
        def save(name, pw):
            return self.http("POST", "/save", ("s=" + name.encode().hex() + "&p=" + pw.encode().hex()).encode(), form, base=base)[0]
        self.assertEqual(save("First Net", "password1"), 200)
        time.sleep(2.0)
        self.assertEqual(save("Second Net", "password2"), 200)
        t2 = time.time()
        time.sleep(1.0)
        self.assertEqual(save("Third Net", "short"), 400)
        self.assertNotIn("softap off", self.wifi_log())
        self.wait_for(lambda: "softap off" in self.wifi_log(), "setup mode to close", timeout=12)
        self.assertGreaterEqual(time.time() - t2, 7.0, "the close waits 8 s from the second Save, not the first")
        self.wait_for(lambda: "begin Second Net password2" in self.wifi_log(), "joining the second network")
        self.assertNotIn("begin First Net", self.wifi_log())
        self.assertNotIn("begin Third Net", self.wifi_log())

    def test_setup_mode_times_out_and_returns_to_the_saved_network(self):
        """No saved network: setup opens by itself at power-up and ends after 5 minutes (time sped up 50x here) with Wi-Fi left off."""
        self.extra_env = {"GG_SETUP_AUTO": "1", "GG_TIME_SCALE": "50"}
        self.start()
        self.wait_for(lambda: "softap GlowGrid-Setup" in self.wifi_log(), "setup mode at power-up with nothing saved")
        self.assertIn("wifi=setup", self.board.simple("INFO"))
        self.wait_for(lambda: "softap off" in self.wifi_log(), "the 5-minute timeout", timeout=12)
        self.assertIn("wifi=off", self.board.simple("INFO"))
        time.sleep(1.0)
        self.assertEqual(self.log_count("softap GlowGrid-Setup"), 1, "it does not open again by itself")
        self.assertNotIn("begin", self.wifi_log(), "nothing saved, nothing to join")

    def test_setup_mode_opens_when_the_saved_network_will_not_join(self):
        """A saved network that has not joined 90 s after power-up opens setup once; after its timeout the saved network is tried again
        and kept. A newly saved network that does not join in 30 s opens setup again. A network that joins never opens it."""
        self.start(wifi=True)
        self.board.wifi_set("Home Net", "password1")
        self.wait_for(lambda: "wifi=connected" in self.board.wifi_status() and self.board.wifi_status(), "joining")
        # power-up with the network joining: no setup
        self.extra_env = {"GG_SETUP_AUTO": "1", "GG_TIME_SCALE": "50"}
        os.remove(self.fs + "_wifi.log")
        board = self.restart()
        self.wait_for(lambda: "wifi=connected" in board.wifi_status() and board.wifi_status(), "rejoining")
        time.sleep(3.0)                                         # well past 90 s of sped-up time
        self.assertNotIn("softap", self.wifi_log())
        # power-up with the network out of reach: setup opens after the 90 s, then ends after 5 minutes and the saved network is tried again
        self.wifi_sim = False
        os.remove(self.fs + "_wifi.log")
        board = self.restart()
        self.assertIn("begin Home Net password1", self.wifi_log())
        self.wait_for(lambda: "softap GlowGrid-Setup" in self.wifi_log(), "setup after the failed join", timeout=8)
        self.wait_for(lambda: "softap off" in self.wifi_log(), "setup timeout", timeout=12)
        self.wait_for(lambda: self.log_count("begin Home Net password1") == 2, "the saved network tried again")
        self.assertEqual(board.simple("INFO").count("wifi=connecting"), 1, "still saved, still trying")
        time.sleep(1.5)
        self.assertEqual(self.log_count("softap GlowGrid-Setup"), 1, "automatic setup runs once per power-up")
        # new credentials that do not join (this board never joins here): setup opens again after 30 s
        board.wifi_set("Wrong Net", "password2")
        self.wait_for(lambda: self.log_count("softap GlowGrid-Setup") == 2, "setup after a network that does not join", timeout=6)
        self.assertIn("wifi=setup", board.simple("INFO"))

    def test_nothing_opens_setup_without_the_test_switch(self):
        """The other tests rely on this: with the stub's switch off, a board with no network or one that never joins stays as before."""
        self.start()
        time.sleep(1.0)
        self.assertNotIn("softap", self.wifi_log())
        self.assertIn("wifi=off", self.board.simple("INFO"))


class Base64(unittest.TestCase):
    def test_b64_decode(self):
        """The firmware decodes the stored page with gg_b64_decode. Compared with Python's base64, plus the malformed cases."""
        import base64
        for raw in (b"", b"f", b"fo", b"foo", b"foob", b"fooba", b"foobar", bytes(range(256)), bytes([0, 255, 0, 255, 1])):
            self.assertEqual(host("b64", base64.b64encode(raw).decode()).strip(), raw.hex(), raw)
        for bad in ("Zm9", "Zm9v=A==", "Z=9v", "****", "Zm9v Zg==", "=m9v"):
            self.assertEqual(host("b64", bad).strip(), "no", bad)


class Hex(unittest.TestCase):
    def test_hex_decode(self):
        for text, cap, want in [("4142", 8, "OK 2 AB"), ("41 42", 8, "no"), ("414", 8, "no"), ("4g", 8, "no"), ("", 8, "OK 0 "),
                                ("48656c6c6f", 6, "OK 5 Hello"), ("48656c6c6f", 5, "no"), ("4A4b", 8, "OK 2 JK")]:
            self.assertEqual(host("hex", text, cap).rstrip("\n"), want, text)


if __name__ == "__main__":
    unittest.main()
