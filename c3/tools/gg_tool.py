#!/usr/bin/env python3
"""Manage sprites on the ESP32-C3 player over USB.

    python3 gg_tool.py list
    python3 gg_tool.py put fire_flower.gg lantern.gg      # add, or replace a sprite with the same name
    python3 gg_tool.py show lantern                       # play this one now
    python3 gg_tool.py del lantern
    python3 gg_tool.py info
    python3 gg_tool.py --port COM3 list                   # name the port if it is not found automatically

Close the Arduino Serial Monitor first: only one program can use the port.
Needs pyserial:  pip install pyserial
"""
import argparse
import os
import sys
import time
import zlib

import serial
import serial.tools.list_ports

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gg_format as gg  # noqa: E402

BLOCK = 1024


class Board:
    def __init__(self, port=None, baud=115200, timeout=5.0, ser=None):
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
                _, name, size = line.split()
                files.append((name, int(size)))
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

    def simple(self, command):
        self.send(command)
        return self.expect(["OK"])


def find_port():
    ports = list(serial.tools.list_ports.comports())
    esp = [p.device for p in ports if p.vid == 0x303A]    # Espressif's USB vendor id
    if len(esp) == 1:
        return esp[0]
    if not esp and len(ports) == 1:
        return ports[0].device
    names = ", ".join(p.device for p in ports) or "none found"
    raise SystemExit(f"Could not pick a port automatically (found: {names}). Use --port COM3.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("info")
    p = sub.add_parser("put")
    p.add_argument("files", nargs="+")
    for c in ("show", "del"):
        s = sub.add_parser(c)
        s.add_argument("name")
    a = ap.parse_args()

    board = Board(a.port or find_port())
    try:
        if a.cmd == "list":
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
        elif a.cmd == "del":
            print(board.simple(f"DEL {a.name}"))
        elif a.cmd == "info":
            print(board.simple("INFO"))
    except (RuntimeError, TimeoutError, ValueError) as e:
        raise SystemExit(f"error: {e}")
    finally:
        board.close()


if __name__ == "__main__":
    main()
