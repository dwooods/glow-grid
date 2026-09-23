"""Glow Grid web control: serves the simulator from web/ and a small JSON API
that plays images on the panel.

    python3 server.py            # then open http://raspberrypi.local:8080

Meant to run as a systemd service (see install-service.sh). LAN use only:
there is no login, so anyone on your network can change the lights.

API
  GET  /api/status                 panel state, brightness, image list
  POST /api/play        {"name": "knight_4fps.png", "fps": 8}   play a file in images/
  POST /api/show?name=smiley_6fps.png&save=0   body = image bytes; play it now
                                   (save=1 also keeps it in images/)
  POST /api/stop                   stop and clear the panel
  POST /api/brightness  {"value": 0.3}          runtime brightness (not saved)
"""
import json
import os
import re
import shutil
import signal
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import grid_common as gc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(BASE_DIR, "web")
LIVE_DIR = os.path.join(tempfile.gettempdir(), "glow-grid-live")
IMAGE_EXTS = (".png", ".gif", ".jpg", ".jpeg", ".webp", ".bmp")
MAX_UPLOAD = 5 * 1024 * 1024
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")


class Player:
    """Owns the panel while something is playing; releases it when stopped so
    the glow-grid menu can use the panel again."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._stop = threading.Event()
        self._strip = None
        self.current = None
        self.error = None

    def play(self, path, name, fps=None):
        frames, delays = gc.load_frames(path, fps)  # raises on a bad file
        with self._lock:
            self._stop_locked(clear=False)
            if self._strip is None:
                self._strip = gc.get_strip(exit_if_busy=False)  # may raise PanelBusy
            self._stop = threading.Event()
            self.current = {"name": name, "frames": len(frames),
                            "fps": round(1 / delays[0], 2) if len(frames) > 1 else None}
            self.error = None
            self._thread = threading.Thread(
                target=self._run, args=(self._strip, frames, delays, self._stop), daemon=True)
            self._thread.start()

    def _run(self, strip, frames, delays, stop):
        try:
            if len(frames) == 1:
                while not stop.is_set():   # redraw so brightness changes apply
                    gc.draw(strip, frames[0])
                    stop.wait(1.0)
            else:
                while not stop.is_set():
                    for frame, d in zip(frames, delays):
                        if stop.is_set():
                            break
                        gc.draw(strip, frame)
                        stop.wait(d)
        except Exception as e:  # keep the server alive; report through /api/status
            self.error = f"{e.__class__.__name__}: {e}"

    def _stop_locked(self, clear=True):
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=5)
            self._thread = None
        self.current = None
        if clear and self._strip is not None:
            try:
                self._strip.clear()
                self._strip.show()
            finally:
                self._strip = None
                gc.release_panel()

    def stop(self):
        with self._lock:
            self._stop_locked(clear=True)


player = Player()


def list_images():
    items = []
    if os.path.isdir(gc.IMAGES_DIR):
        for f in sorted(os.listdir(gc.IMAGES_DIR)):
            if not f.lower().endswith(IMAGE_EXTS):
                continue
            try:
                frames, delays = gc.load_frames(os.path.join(gc.IMAGES_DIR, f))
                items.append({"name": f, "frames": len(frames),
                              "fps": round(1 / delays[0], 2) if len(frames) > 1 else None})
            except Exception as e:
                items.append({"name": f, "error": e.__class__.__name__})
    return items


def valid_name(name):
    return bool(name) and SAFE_NAME.match(name) and name.lower().endswith(IMAGE_EXTS)


class Handler(SimpleHTTPRequestHandler):
    server_version = "GlowGrid/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, fmt, *args):  # quieter journal: only API calls
        if "/api/" in (args[0] if args else ""):
            super().log_message(fmt, *args)

    # ---- helpers ----
    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD:
            raise ValueError(f"upload too large (max {MAX_UPLOAD // 1024 // 1024} MB)")
        return self.rfile.read(length) if length else b""

    def read_json(self):
        raw = self.read_body()
        return json.loads(raw) if raw else {}

    def status(self):
        return {
            "grid": {"cols": gc.COLS, "rows": gc.ROWS},
            "brightness": gc.BRIGHTNESS,
            "gamma": gc.GAMMA,
            "wiring_confirmed": bool(getattr(gc, "WIRING_CONFIRMED", False)),
            "playing": player.current,
            "error": player.error,
            "images": list_images(),
        }

    # ---- routes ----
    def do_GET(self):
        if urlparse(self.path).path == "/api/status":
            return self.send_json(self.status())
        return super().do_GET()  # static files from web/

    def do_POST(self):
        url = urlparse(self.path)
        try:
            if url.path == "/api/play":
                data = self.read_json()
                name = str(data.get("name", ""))
                path = os.path.join(gc.IMAGES_DIR, name)
                if not valid_name(name) or not os.path.isfile(path):
                    return self.send_json({"error": f"no such image: {name}"}, 404)
                player.play(path, name, data.get("fps"))
                return self.send_json(self.status())

            if url.path == "/api/show":
                q = parse_qs(url.query)
                name = q.get("name", ["live.png"])[0]
                save = q.get("save", ["0"])[0] == "1"
                if not valid_name(name):
                    return self.send_json({"error": "bad file name"}, 400)
                body = self.read_body()
                if not body:
                    return self.send_json({"error": "empty upload"}, 400)
                os.makedirs(LIVE_DIR, exist_ok=True)
                live = os.path.join(LIVE_DIR, name)
                with open(live, "wb") as f:
                    f.write(body)
                if save:
                    os.makedirs(gc.IMAGES_DIR, exist_ok=True)
                    shutil.copyfile(live, os.path.join(gc.IMAGES_DIR, name))
                player.play(live, name)
                return self.send_json(self.status())

            if url.path == "/api/stop":
                player.stop()
                return self.send_json(self.status())

            if url.path == "/api/brightness":
                gc.set_brightness(self.read_json().get("value", gc.BRIGHTNESS))
                return self.send_json(self.status())

            return self.send_json({"error": "not found"}, 404)
        except gc.PanelBusy as e:
            return self.send_json({"error": str(e)}, 409)
        except Exception as e:
            return self.send_json({"error": f"{e.__class__.__name__}: {e}"}, 400)


def _on_sigterm(*_):
    raise KeyboardInterrupt


def main():
    port = int(os.environ.get("GLOWGRID_PORT", gc.WEB_PORT))
    startup = getattr(gc, "STARTUP_IMAGE", None)
    if startup:
        path = os.path.join(gc.IMAGES_DIR, startup)
        try:
            player.play(path, startup)
            print(f"Playing {startup}")
        except Exception as e:
            print(f"Couldn't play STARTUP_IMAGE {startup}: {e}")
    # systemctl stop sends SIGTERM: treat it like Ctrl+C so the panel is cleared
    signal.signal(signal.SIGTERM, _on_sigterm)
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Glow Grid web control on http://0.0.0.0:{port}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        player.stop()
        server.server_close()


if __name__ == "__main__":
    # small delay lets systemd's network settle before binding on first boot
    if os.environ.get("INVOCATION_ID"):
        time.sleep(1)
    main()
