# glow-grid

Pixel art and animations for a **16x16 WS2812B LED panel** on a **Raspberry Pi 5**, driven over hardware SPI, plus **Glow Grid**, a browser-based editor and LED simulator for designing them before they ever touch the panel.

Sister project to [led-strip](https://github.com/dwooods/led-strip), which drives a 1D strip with procedural effects. This one is about 2D images: draw, simulate, copy to the Pi, play.

## The workflow

1. **Design** in the Glow Grid simulator (`web/index.html`, or the hosted/installed version below).
2. **Simulate**: switch to *LED sim* to see what survives the Pi's brightness cap and gamma curve. The *Panel check* flags pixels that will be barely lit or shift color, and estimates current draw against your power supply.
3. **Export** a still PNG or an animation sprite sheet (frames side by side, frame rate in the filename, e.g. `knight_4fps.png`).
4. **Copy** it to the Pi's `images/` folder and pick it from the `glowgrid` menu.

## The simulator

`web/` is a static site with no build step: one `index.html`, plus a manifest and service worker so it can be installed as an app.

- **Open it locally**: double-click `web/index.html`. Everything works except app install.
- **Hosted**: every push to `main` that touches `web/` deploys it to GitHub Pages at `https://dwooods.github.io/glow-grid/` (see `.github/workflows/pages.yml`; app icons are generated in CI from `examples/sprites.py`).
- **Install as an app**: open the hosted page in Chrome or Edge and click *Install app* (or the install icon in the address bar). It then runs in its own window and works offline.
- **Download**: *Download for offline* on the hosted page saves the single-file simulator.

Your drawings are saved in that browser's local storage, so re-import a sprite sheet to move work between browsers.

The LED model matches `grid_common.py` exactly: `round(255 * BRIGHTNESS * (c/255) ** GAMMA)`, with any non-zero channel kept at 1 or above. Keep the simulator's brightness and gamma in sync with `local_config.py`.

## Hardware

- Raspberry Pi 5
- 16x16 WS2812B flexible panel (256 pixels), 5V
- Panel **DIN** → 330Ω resistor → Pi **GPIO10 / MOSI** (physical pin 19). Use the input end: the connector labeled DIN, or the one the printed arrows point away from.
- Panel **GND** → power supply GND **and** a Pi GND pin (common ground)
- Panel **5V** → an external supply only, **never** the Pi's 5V pin
- **Power supply:** 5V, 5–6A or more, sold for addressable LEDs. 256 pixels at full white is about 15A in theory. With brightness capped at 0.3, 5–6A has headroom, but a generic 2A adapter causes random stray pixels because it can't keep up with the current spikes.
- A 1000µF capacitor across 5V/GND at the panel's power input

The panel and the led-strip project both use GPIO10 / MOSI, so only one can be connected at a time.

As with led-strip, the Pi 5's RP1 chip breaks `rpi_ws281x` / Adafruit `neopixel`, so this project drives the panel over SPI with [`rpi5-ws2812`](https://pypi.org/project/rpi5-ws2812/).

## Setup

```bash
sudo raspi-config   # Interface Options -> SPI -> Enable, then reboot

git clone https://github.com/dwooods/glow-grid.git ~/glow-grid
cd ~/glow-grid
./run.sh            # first run: creates venv, installs deps, writes examples, opens menu
ln -s ~/glow-grid/run.sh ~/.local/bin/glowgrid   # then just type: glowgrid
```

On first run `run.sh` creates `local_config.py` from `local_config.example.py`. That's where your panel's wiring order, brightness and gamma live. It's git-ignored, so `git pull` never overwrites it.

### Find your panel's wiring order (do this first)

Panels are wired in different orders, and a wrong mapping scrambles images into noise that looks like a hardware fault.

1. Pick `p` in the menu (or run `python3 probe.py`). Five raw indexes light up: 0 red, 1 green, 15 white, 16 yellow, 255 blue.
2. Set `FLIP_X`, `FLIP_Y`, `COLUMN_MAJOR` and `SERPENTINE` in `local_config.py`. The comments there map what you see to each setting.
3. Pick `c` (or `python3 probe.py check`). You should see white at the top-left, red along the top, green down the left, and a blue diagonal. If so, images will display correctly.

`w` walks a single dot through every index, which helps if the markers are ambiguous.

## The menu

```
Glow Grid (16x16)
  1. knight.png  (still)
  2. knight_4fps.png  (4 frames, 4 fps)
  3. smiley_3fps.png  (4 frames, 3 fps)
  p. Wiring probe (markers)
  w. Wiring probe (walk every index)
  c. Check wiring settings
  r. Rescan images
  o. Turn off
  q. Quit
```

Images in `images/` are numbered automatically. Type a number to play one; add a number after it to override the frame rate (`2 8` plays file 2 at 8 fps). Like led-strip, whatever you pick runs in the background, and picking something else stops it cleanly first (SIGINT, so the panel is always cleared).

Copying a new image over from Windows:

```powershell
scp $HOME\Downloads\knight_4fps.png user@raspberrypi.local:~/glow-grid/images/
```

Then press `r` in the menu.

## Architecture

- **`grid_common.py`**: panel config and defaults, `get_strip()`, `xy_to_index()` (wiring map), `correct()` (gamma/brightness lookup table), `fit()` (fit any image to the grid without stretching; transparency becomes black), `load_frames()` (still PNG, sprite sheet or animated GIF → frames + delays), and `draw()`.
- **`play.py`**: plays one file. A still is held until stopped; an animation loops.
- **`probe.py`**: wiring diagnostics (markers / walk / check).
- **`glowgrid.py`**: the menu/launcher. Scans `images/`, runs `play.py` / `probe.py` as a background subprocess, and runs only one at a time.
- **`off.py`**: clears the panel.
- **`examples/sprites.py`**: the example sprites, drawn as text so they're diffable source rather than binary files. `make_examples.py` renders them into `images/`.
- **`web/`**: the simulator (static site / installable app).

Frame rate for an animation comes from, in order: the menu argument, `_<n>fps` in the filename, the GIF's own timing, then `DEFAULT_FPS` (6).

## Designing for LEDs

Things that look fine on a monitor but fail on the panel (the simulator's Panel check catches the first two):

- **Near-black isn't off.** `#0d1117` lights every pixel faintly. Use pure `#000000` for "off".
- **Dark colors disappear.** After brightness 0.3 and gamma 2.2, anything with a max channel under about 70 ends up at 1–3 out of 255. Separate shapes with contrasting colors instead of dark outlines.
- **16x16 is small.** Downscaled detail (eye highlights, thin lines) usually doesn't survive. Draw at 16x16 rather than shrinking something bigger.

## License

MIT, see [LICENSE](LICENSE).
