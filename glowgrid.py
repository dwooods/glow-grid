"""Glow Grid menu: pick an image or animation from images/ and it plays in the
background until you pick something else, turn the panel off, or quit.

Type a number to play that file; add a number after it to override the frame
rate (e.g. "2 10" plays file 2 at 10 fps). "d 3 5 7-9" deletes those files
(after a y/N check); "e" writes the example sprites into images/.
"""
import os
import re
import signal
import subprocess
import sys

import grid_common
from grid_common import IMAGES_DIR, load_frames, image_light, image_grid, COLS, ROWS

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CONFIG = os.path.join(SCRIPT_DIR, "local_config.py")
IMAGE_EXTS = (".png", ".gif", ".jpg", ".jpeg", ".webp", ".bmp")

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
            parts = ["still" if len(frames) == 1 else f"{len(frames)} frames, {1 / delays[0]:g} fps"]
            light = image_light(os.path.join(IMAGES_DIR, f))  # saved inside the PNG by the simulator
            if "brightness" in light:
                parts.append(f"bright {light['brightness']:g}")
            if "gamma" in light:
                parts.append(f"gamma {light['gamma']:g}")
            grid = image_grid(os.path.join(IMAGES_DIR, f))
            if grid and grid != (COLS, ROWS):
                parts.append(f"! made for {grid[0]}x{grid[1]}, panel is {COLS}x{ROWS}")
            info = ", ".join(parts)
        except Exception as e:  # unreadable file: still list it, flag why
            info = f"can't read: {e.__class__.__name__}"
        items.append((f, info))
    return items


def parse_selection(tokens, count):
    """Turn ["1", "4", "6-8"] into [1, 4, 6, 7, 8] (1-based, sorted, no repeats).
    Raises ValueError with a readable message for anything that is not a number
    or range inside 1..count."""
    picked = set()
    for tok in tokens:
        lo, sep, hi = tok.partition("-")
        if not (lo.isdigit() and (not sep or hi.isdigit())):
            raise ValueError(f"'{tok}' is not a number or a range like 7-9")
        a, b = int(lo), int(hi) if sep else int(lo)
        if a > b:
            raise ValueError(f"'{tok}' runs backwards")
        for n in range(a, b + 1):
            if not 1 <= n <= count:
                raise ValueError(f"{n} is not in the list (1 to {count})")
            picked.add(n)
    if not picked:
        raise ValueError("no numbers given")
    return sorted(picked)


def delete_images(names):
    """Delete the named files from images/. Returns (deleted, failed) name lists."""
    deleted, failed = [], []
    for name in names:
        try:
            os.remove(os.path.join(IMAGES_DIR, name))
            deleted.append(name)
        except OSError:
            failed.append(name)
    return deleted, failed


def show_menu(images, running_name):
    print(f"\nGlow Grid ({COLS}x{ROWS})")
    if not wiring_confirmed:
        print("  ! Wiring not checked yet: images may look scrambled.")
        print("    Quit, run `glow-grid probe`, set the flags in local_config.py, run")
        print("    `glow-grid probe check`, then come back and press k if it looks right.")
    if images:
        for i, (f, info) in enumerate(images, 1):
            print(f"  {i}. {f}  ({info})")
    else:
        print("  (no images in images/ yet; copy a PNG there and press r)")
    if not wiring_confirmed:
        print("  k. Wiring looks right: mark it confirmed")
    print("  r. Rescan images")
    print("  e. Write the example sprites into images/")
    if images:
        print("  d. Delete images (d 3 5 7-9)")
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
            if key == "e":
                print("\nThis writes the example sprites (knight, cat, fox, ...) into images/,")
                print("replacing any file that has the same name (e.g. cat_sprite.png).")
                if input("Write them? [y/N] ").strip().lower() != "y":
                    print("Cancelled.")
                    continue
                subprocess.run([sys.executable, os.path.join("examples", "make_examples.py")], cwd=SCRIPT_DIR)
                images = scan_images()
                continue
            if key == "d":
                if not extra:
                    print("Say which ones, e.g. 'd 3' or 'd 1 4 7-9'.")
                    continue
                try:
                    picked = parse_selection(extra, len(images))
                except ValueError as e:
                    print(f"Nothing deleted: {e}.")
                    continue
                names = [images[n - 1][0] for n in picked]
                print("\nDelete permanently:")
                for n in names:
                    print(f"  {n}")
                if input("Delete these? [y/N] ").strip().lower() != "y":
                    print("Cancelled, nothing deleted.")
                    continue
                if current_name in names:
                    stop_process(current_proc)
                    subprocess.run([sys.executable, "off.py"], cwd=SCRIPT_DIR)
                    current_proc, current_name = None, None
                deleted, failed = delete_images(names)
                print(f"Deleted {len(deleted)} file(s).")
                if failed:
                    print("Couldn't delete: " + ", ".join(failed))
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
