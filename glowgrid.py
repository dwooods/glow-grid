"""Glow Grid menu: pick an image or animation from images/ and it plays in the
background until you pick something else, turn the panel off, or quit.

Type a number to play that file; add a number after it to override the frame
rate (e.g. "2 10" plays file 2 at 10 fps).
"""
import os
import re
import signal
import subprocess
import sys

import grid_common
from grid_common import IMAGES_DIR, load_frames, COLS, ROWS

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CONFIG = os.path.join(SCRIPT_DIR, "local_config.py")
IMAGE_EXTS = (".png", ".gif", ".jpg", ".jpeg", ".webp", ".bmp")

# Letter commands. Images are numbered 1, 2, 3, ... so they never collide.
COMMANDS = [
    ("p", "Wiring probe (markers)", ["probe.py"]),
    ("w", "Wiring probe (walk every index)", ["probe.py", "walk"]),
    ("c", "Check wiring settings", ["probe.py", "check"]),
]
COMMAND_MAP = {key: (name, args) for key, name, args in COMMANDS}

wiring_confirmed = bool(getattr(grid_common, "WIRING_CONFIRMED", False))


def confirm_wiring():
    """Set WIRING_CONFIRMED = True in local_config.py (add the line if missing)."""
    text = ""
    if os.path.exists(LOCAL_CONFIG):
        with open(LOCAL_CONFIG) as f:
            text = f.read()
    pattern = re.compile(r"^WIRING_CONFIRMED\s*=.*$", re.MULTILINE)
    if pattern.search(text):
        text = pattern.sub("WIRING_CONFIRMED = True", text)
    else:
        text = text.rstrip("\n") + "\n\nWIRING_CONFIRMED = True\n"
    with open(LOCAL_CONFIG, "w") as f:
        f.write(text)


def scan_images():
    if not os.path.isdir(IMAGES_DIR):
        return []
    files = sorted(f for f in os.listdir(IMAGES_DIR) if f.lower().endswith(IMAGE_EXTS))
    items = []
    for f in files:
        try:
            frames, delays = load_frames(os.path.join(IMAGES_DIR, f))
            info = "still" if len(frames) == 1 else f"{len(frames)} frames, {1 / delays[0]:.0f} fps"
        except Exception as e:  # unreadable file: still list it, flag why
            info = f"can't read: {e.__class__.__name__}"
        items.append((f, info))
    return items


def show_menu(images, running_name):
    print(f"\nGlow Grid ({COLS}x{ROWS})")
    if not wiring_confirmed:
        print("  ! Wiring not checked yet: images may look scrambled.")
        print("    Run p, set the flags in local_config.py, then c. If c looks right, press k.")
    if images:
        for i, (f, info) in enumerate(images, 1):
            print(f"  {i}. {f}  ({info})")
    else:
        print("  (no images in images/ yet; copy a PNG there and press r)")
    for key, name, _ in COMMANDS:
        print(f"  {key}. {name}")
    if not wiring_confirmed:
        print("  k. Wiring looks right: mark it confirmed")
    print("  r. Rescan images")
    print("  o. Turn off")
    print("  q. Quit")
    if running_name:
        print(f"\n  (currently running: {running_name}; pick another option to switch, or o/q to stop)")


def stop_process(proc):
    if proc is not None and proc.poll() is None:
        proc.send_signal(signal.SIGINT)
        proc.wait()


def start(args):
    env = dict(os.environ, GLOWGRID_MENU="1")  # the menu shows its own wiring warning
    return subprocess.Popen([sys.executable, *args], cwd=SCRIPT_DIR, env=env)


def main():
    global wiring_confirmed
    images = scan_images()
    current_proc, current_name = None, None
    try:
        while True:
            show_menu(images, current_name)
            parts = input("\nSelect an option: ").split()
            if not parts:
                continue
            key, extra = parts[0].lower(), parts[1:]

            if key == "q":
                stop_process(current_proc)
                break
            if key == "r":
                images = scan_images()
                continue
            if key == "k" and not wiring_confirmed:
                confirm_wiring()
                wiring_confirmed = True
                print("\nWiring marked as confirmed in local_config.py.")
                continue
            if key == "o":
                stop_process(current_proc)
                subprocess.run([sys.executable, "off.py"], cwd=SCRIPT_DIR)
                current_proc, current_name = None, None
                continue
            if key in COMMAND_MAP:
                name, args = COMMAND_MAP[key]
                stop_process(current_proc)
                current_proc, current_name = start([*args, *extra]), name
                continue
            if key.isdigit() and 1 <= int(key) <= len(images):
                f = images[int(key) - 1][0]
                stop_process(current_proc)
                print(f"\nPlaying {f} in the background...")
                current_proc, current_name = start(["play.py", os.path.join(IMAGES_DIR, f), *extra]), f
                continue
            print("Invalid choice, try again.")
    except (KeyboardInterrupt, EOFError):
        stop_process(current_proc)
        print("\nQuitting.")


if __name__ == "__main__":
    main()
