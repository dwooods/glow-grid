#!/usr/bin/env python3
"""Manage sprites on the ESP32-C3 player over USB.

    python3 gg_tool.py list
    python3 gg_tool.py put fire_flower.gg lantern.gg      # add, or replace a sprite with the same name
    python3 gg_tool.py get lantern                        # save lantern.gg from the board (firmware 8 or later)
    python3 gg_tool.py show lantern                       # play this one now
    python3 gg_tool.py del lantern
    python3 gg_tool.py off                                # panel dark, board keeps running
    python3 gg_tool.py on
    python3 gg_tool.py rotate 300                       # next sprite every 5 minutes; 0 = stay on one
    python3 gg_tool.py bright 20                        # play every sprite at 0.2; 0 = each sprite's own brightness
    python3 gg_tool.py shuffle 1                        # rotation picks a random sprite (0 = list order; firmware 16)
    python3 gg_tool.py sched 07:00 20:00                # panel on at 07:00 and off at 20:00 every day (firmware 20); sched off removes it
    python3 gg_tool.py info
    python3 gg_tool.py --port COM3 list                   # name the port if it is not found automatically

Wi-Fi (firmware 9). Set it up once over USB, then the same commands work over the network with --host:
    python3 gg_tool.py wifi set "My Network" "my password"   # the board joins in a few seconds (2.4 GHz only); "" = open network
    python3 gg_tool.py wifi scan                              # the networks the board can hear (firmware 10)
    python3 gg_tool.py wifi status                            # connected? which address?
    python3 gg_tool.py wifi clear
    python3 gg_tool.py --host glowgrid.local list            # or the board's address, e.g. --host 192.168.1.50
    python3 gg_tool.py --host glowgrid.local put lantern.gg  # every command except wifi works this way
    python3 gg_tool.py wifi key                               # the stored setup key (firmware 18 to 20 only; firmware 21 shows a new key on the panel instead); over USB only
The network side has no password yet: anyone on your home network can change the sprites (other websites cannot, from firmware 18).

Close the Arduino Serial Monitor first: only one program can use the port.
Needs pyserial for USB:  pip install pyserial   (not needed with --host)
"""
import argparse
import os
import sys
import time
import zlib

import urllib.error
import urllib.parse
import urllib.request
import uuid

try:
    import serial
    import serial.tools.list_ports
except ImportError:                      # fine for --host; USB use then says so
    serial = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gg_format as gg  # noqa: E402

BLOCK = 1024


class Board:
    def __init__(self, port=None, baud=115200, timeout=5.0, ser=None):
        if ser is None and serial is None:
            raise SystemExit("USB needs pyserial:  pip install pyserial   (or use --host for Wi-Fi)")
        if ser is not None:             # a ready-made port object (the tests pass a fake board)
            self.ser = ser
        else:
            # Control lines, set before opening so they do not toggle: the C3's native USB port only
            # accepts data while DTR is asserted (otherwise every write blocks for good), and
            # DTR high with RTS low is the ordinary "terminal connected" state, not a reset.
            self.ser = serial.Serial()
            self.ser.port = port
            self.ser.baudrate = baud
            self.ser.timeout = 0.2
            self.ser.write_timeout = 2.0
            self.ser.dtr = True
            self.ser.rts = False
            self.ser.open()
        self.timeout = timeout
        self._handshake()

    def close(self):
        self.ser.close()

    def send(self, text):
        try:
            self.ser.write(text.encode() + b"\n")
        except serial.SerialTimeoutException:
            raise TimeoutError("the board is not taking data on this port. Unplug it, plug it back in, and try again.")

    def readline(self, timeout):
        end = time.time() + timeout
        buf = b""
        while time.time() < end:
            ch = self.ser.read(1)
            if not ch:
                continue
            if ch == b"\n":
                return buf.decode(errors="replace").strip()
            buf += ch
        return None

    def expect(self, prefixes, timeout=None):
        """Read lines until one starts with a wanted prefix. Other lines (boot messages) are skipped.
        An ERR line raises. Returns the matching line."""
        end = time.time() + (timeout or self.timeout)
        lines = []
        while time.time() < end:
            line = self.readline(0.3)
            if line is None or not line:
                continue
            if line.startswith("ERR"):
                raise RuntimeError(line)
            if any(line.startswith(p) for p in prefixes):
                return line
            lines.append(line)
        raise TimeoutError(f"no reply from the board (wanted {prefixes}); heard: {lines[-3:]}")

    def _handshake(self):
        time.sleep(0.3)
        self.ser.reset_input_buffer()
        for _ in range(6):
            self.send("PING")
            try:
                self.expect(["PONG"], timeout=1.5)
                return
            except TimeoutError:
                continue
        raise TimeoutError("the board did not answer PING. Is c3_player.ino uploaded, and the Serial Monitor closed?")

    def list(self):
        self.send("LIST")
        files = []
        while True:
            line = self.expect(["FILE", "OK"])
            if line.startswith("FILE"):
                parts = line.split()             # fw 17 adds frames, fps10, bright_pct, gamma10 after the size
                files.append((parts[1], int(parts[2])))
            else:
                return files, line

    def put(self, path):
        with open(path, "rb") as fh:
            blob = fh.read()
        gg.unpack(blob)  # refuse a bad file before sending anything
        name = os.path.splitext(os.path.basename(path))[0]
        crc = zlib.crc32(blob) & 0xFFFFFFFF
        self.ser.reset_input_buffer()
        self.send(f"PUT {name} {len(blob)} {crc:08x}")
        self.expect(["READY"])
        pos = 0
        while pos < len(blob):
            chunk = blob[pos:pos + BLOCK]
            self.ser.write(chunk)
            pos += len(chunk)
            if pos < len(blob):
                self.expect(["A"], timeout=5.0)
        return self.expect(["OK"], timeout=10.0)

    def get(self, name):
        """The stored file as bytes, checked against the board's own CRC. Needs firmware 8 or later."""
        self.ser.reset_input_buffer()
        self.send(f"GET {name}")
        chunks, end = [], time.time() + 20.0
        while time.time() < end:
            line = self.readline(0.5)
            if not line:
                continue
            if line.startswith("ERR"):
                raise RuntimeError(line)
            if line.startswith("D "):
                chunks.append(bytes.fromhex(line[2:]))
            elif line.startswith("OK"):
                blob = b"".join(chunks)
                want = f"OK crc={zlib.crc32(blob) & 0xFFFFFFFF:08x} size={len(blob)}"
                if line != want:
                    raise RuntimeError(f"the file came through damaged (board said {line}, got {want})")
                return blob
        raise TimeoutError("no answer to GET. This board may be running firmware older than 8; re-flash c3_player.ino.")

    def simple(self, command):
        self.send(command)
        return self.expect(["OK"])

    def wifi_set(self, ssid, password=""):
        """Store the Wi-Fi name and password on the board (USB only). Sent as hex so spaces and symbols survive."""
        pw = password.encode().hex() if password else "-"
        return self.simple(f"WIFI SET {ssid.encode().hex()} {pw}")

    def wifi_status(self):
        return self.simple("WIFI STATUS")

    def wifi_scan(self):
        """Networks the board can hear, strongest first, as [(name, rssi, needs_password)]. USB only; firmware 10 or later."""
        self.send("WIFI SCAN")
        nets = []
        while True:
            line = self.expect(["NET", "OK"], timeout=15.0)
            if line.startswith("NET"):
                _, h, rssi, sec = line.split()
                nets.append((bytes.fromhex(h).decode("utf-8", "replace"), int(rssi), sec == "1"))
            else:
                return nets

    def wifi_clear(self):
        return self.simple("WIFI CLEAR")

    def wifi_key(self, new=False):
        """The board's stored setup key (firmware 18 to 20 only; 21 has none, its key is shown on the panel). USB only. new=True makes a fresh one."""
        return self.simple("WIFI KEY NEW" if new else "WIFI KEY")


class HttpBoard:
    """The same operations as Board, over Wi-Fi (firmware 9). host is a name or address, optionally with :port."""

    def __init__(self, host, timeout=10.0):
        self.base = "http://" + host
        self.timeout = timeout
        self.simple("PING")

    def close(self):
        pass

    def _call(self, method, path, body=None, headers=None, raw=False):
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = r.read()
        except urllib.error.HTTPError as e:                  # the board's own ERR text comes with the 4xx
            raise RuntimeError(e.read().decode(errors="replace").strip() or f"HTTP {e.code}")
        except (urllib.error.URLError, OSError) as e:
            raise TimeoutError(f"cannot reach the board at {self.base} ({getattr(e, 'reason', e)}). Is it on the same Wi-Fi? "
                               "Check with:  gg_tool.py wifi status  (over USB)")
        return data if raw else data.decode(errors="replace").strip()

    def simple(self, command):
        verb, _, arg = command.partition(" ")
        verb = verb.upper()
        q = urllib.parse.quote(arg)
        if verb == "PING":
            return self._call("GET", "/ping")
        if verb == "INFO":
            return self._call("GET", "/info")
        if verb == "CRC":
            return self._call("GET", "/crc?name=" + q)
        if verb in ("SHOW", "DEL"):
            return self._call("POST", f"/{verb.lower()}?name={q}")
        if verb in ("OFF", "ON"):
            return self._call("POST", "/" + verb.lower())
        if verb == "ROTATE":
            return self._call("POST", "/rotate?s=" + q)
        if verb == "SHUFFLE":
            return self._call("POST", "/shuffle?on=" + q)
        if verb == "BRIGHT":
            return self._call("POST", "/bright?pct=" + q)
        if verb == "SCHED":                          # "SCHED 0700 2000" or "SCHED OFF" -> /sched?v=0700-2000 or v=off
            parts = arg.split()
            return self._call("POST", "/sched?v=" + (parts[0].lower() if len(parts) < 2 else parts[0] + "-" + parts[1]))
        raise ValueError("not available over Wi-Fi: " + command)

    def list(self):
        files, summary = [], ""
        for line in self._call("GET", "/list").splitlines():
            if line.startswith("FILE"):
                parts = line.split()             # fw 17 adds frames, fps10, bright_pct, gamma10 after the size
                files.append((parts[1], int(parts[2])))
            elif line.startswith("OK"):
                summary = line
        return files, summary

    def put(self, path):
        with open(path, "rb") as fh:
            blob = fh.read()
        gg.unpack(blob)  # refuse a bad file before sending anything
        name = os.path.splitext(os.path.basename(path))[0]
        crc = zlib.crc32(blob) & 0xFFFFFFFF
        boundary = "----gg" + uuid.uuid4().hex
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}.gg\"\r\n"
                "Content-Type: application/octet-stream\r\n\r\n").encode() + blob + f"\r\n--{boundary}--\r\n".encode()
        return self._call("POST", f"/put?name={urllib.parse.quote(name)}&size={len(blob)}&crc={crc:08x}", body,
                          {"Content-Type": "multipart/form-data; boundary=" + boundary})

    def get(self, name):
        """The stored file as bytes, checked against the board's own CRC."""
        blob = self._call("GET", "/get?name=" + urllib.parse.quote(name), raw=True)
        want = self.simple(f"CRC {name}")
        got = f"OK crc={zlib.crc32(blob) & 0xFFFFFFFF:08x} size={len(blob)}"
        if want != got:
            raise RuntimeError(f"the file came through damaged (board said {want}, got {got})")
        return blob


def find_port():
    if serial is None:
        raise SystemExit("USB needs pyserial:  pip install pyserial   (or use --host for Wi-Fi)")
    ports = list(serial.tools.list_ports.comports())
    esp = [p.device for p in ports if p.vid == 0x303A]    # Espressif's USB vendor id
    if len(esp) == 1:
        return esp[0]
    if not esp and len(ports) == 1:
        return ports[0].device
    names = ", ".join(p.device for p in ports) or "none found"
    raise SystemExit(f"Could not pick a port automatically (found: {names}). Use --port COM3.")


def sched_args(times):
    """'07:00' '20:00' (or 0700 2000) -> '0700 2000'; 'off' -> 'OFF'. The board checks the values; this only fixes the spelling."""
    if len(times) == 1 and times[0].lower() == "off":
        return "OFF"
    if len(times) != 2:
        raise ValueError("sched needs two times, like: sched 07:00 20:00 (or: sched off)")
    return " ".join(t.replace(":", "").zfill(4) for t in times)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    ap.add_argument("--host", help="use Wi-Fi instead of USB: glowgrid.local or the board's address")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("info")
    sub.add_parser("off")
    sub.add_parser("on")
    r = sub.add_parser("rotate")
    r.add_argument("seconds", type=int)
    sh = sub.add_parser("shuffle")
    sh.add_argument("on", type=int, choices=[0, 1])
    sc = sub.add_parser("sched")
    sc.add_argument("times", nargs="+", help="ON OFF as 24-hour times (07:00 20:00), or the word off")
    br = sub.add_parser("bright")
    br.add_argument("pct", type=int, help="10..40 percent for every sprite; 0 = each sprite's own")
    p = sub.add_parser("put")
    p.add_argument("files", nargs="+")
    w = sub.add_parser("wifi")
    ws = w.add_subparsers(dest="wcmd", required=True)
    wset = ws.add_parser("set")
    wset.add_argument("ssid")
    wset.add_argument("password", nargs="?", default="")
    ws.add_parser("status")
    ws.add_parser("scan")
    ws.add_parser("clear")
    wk = ws.add_parser("key")
    wk.add_argument("--new", action="store_true", help="make a new key (only while setup mode is off)")
    for c in ("show", "del", "get"):
        s = sub.add_parser(c)
        s.add_argument("name")
    a = ap.parse_args()

    if a.cmd == "wifi" and a.host:
        raise SystemExit("error: wifi settings go over USB (leave out --host)")
    try:
        board = HttpBoard(a.host) if a.host else Board(a.port or find_port())
    except (RuntimeError, TimeoutError) as e:
        raise SystemExit(f"error: {e}")
    try:
        if a.cmd == "wifi":
            if a.wcmd == "set":
                print(board.wifi_set(a.ssid, a.password))
            elif a.wcmd == "scan":
                for name, rssi, secure in board.wifi_scan():
                    print(f"  {name:<34} {rssi:>4} dBm  {'password' if secure else 'open'}")
            elif a.wcmd == "key":
                try:
                    print(board.wifi_key(a.new))
                except RuntimeError as e:
                    if "usage" not in str(e):
                        raise
                    print("This firmware (21 or later) has no stored setup key: the setup network's password is the 8 digits shown on the board's panel.")
            else:
                print(board.wifi_status() if a.wcmd == "status" else board.wifi_clear())
        elif a.cmd == "list":
            files, summary = board.list()
            for name, size in files:
                print(f"  {name:<32} {size:>7} bytes")
            print(summary)
        elif a.cmd == "put":
            for f in a.files:
                print(f"{os.path.basename(f)}: ", end="", flush=True)
                print(board.put(f))
        elif a.cmd == "show":
            print(board.simple(f"SHOW {a.name}"))
        elif a.cmd == "get":
            blob = board.get(a.name)
            gg.unpack(blob)
            with open(a.name + ".gg", "wb") as fh:
                fh.write(blob)
            print(f"saved {a.name}.gg ({len(blob)} bytes)")
        elif a.cmd == "del":
            print(board.simple(f"DEL {a.name}"))
        elif a.cmd == "info":
            print(board.simple("INFO"))
        elif a.cmd in ("off", "on"):
            print(board.simple(a.cmd.upper()))
        elif a.cmd == "rotate":
            print(board.simple(f"ROTATE {a.seconds}"))
        elif a.cmd == "shuffle":
            print(board.simple(f"SHUFFLE {a.on}"))
        elif a.cmd == "bright":
            print(board.simple(f"BRIGHT {a.pct}"))
        elif a.cmd == "sched":
            print(board.simple("SCHED " + sched_args(a.times)))
    except (RuntimeError, TimeoutError, ValueError) as e:
        raise SystemExit(f"error: {e}")
    finally:
        board.close()


if __name__ == "__main__":
    main()
