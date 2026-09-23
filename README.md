# glow-grid

Pixel art and animations for a **16x16 WS2812B LED panel** on a **Raspberry Pi 5**, driven over hardware SPI, plus **Glow Grid**, a browser-based editor and LED simulator for designing them before they ever touch the panel.

Sister project to [led-strip](https://github.com/dwooods/led-strip), which drives a 1D strip with procedural effects. This one is about 2D images: draw, simulate, copy to the Pi, play.

## The workflow

1. **Design** in the Glow Grid simulator (`web/index.html`, or the hosted/installed version below), or in [Piskel](#piskel).
2. **Simulate**: switch to *LED sim* to see what survives the Pi's brightness cap and gamma curve. The *Panel check* flags pixels that will be barely lit or shift color, and estimates current draw against your power supply.
3. **Export** a still PNG or an animation sprite sheet (frames side by side, frame rate in the filename, e.g. `knight_4fps.png`).
4. **Copy** it to the Pi's `images/` folder and pick it from the `glow-grid` menu.

## The simulator

`web/` is a static site with no build step: one `index.html`, plus a manifest and service worker so it can be installed as an app.

- **Open it locally**: double-click `web/index.html`. Everything works except app install.
- **Hosted**: every push to `main` that touches `web/` deploys it to GitHub Pages at `https://dwooods.github.io/glow-grid/` (see `.github/workflows/pages.yml`; app icons are generated in CI from `examples/sprites.py`). One-time setup: *Settings → Pages → Build and deployment → Source: GitHub Actions*.
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
chmod +x run.sh
./run.sh            # first run: creates venv, installs deps, writes examples, opens menu
ln -s ~/glow-grid/run.sh ~/.local/bin/glow-grid  # then just type: glow-grid
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

To add your own images, see the next section.

## Using your own images

Put images in **`~/glow-grid/images/`** on the Pi. The menu lists every `.png` and `.gif` there, numbered.

**Copy from Windows** (PowerShell, not the SSH window):

```powershell
scp $HOME\Downloads\walk_8fps.png user@raspberrypi.local:~/glow-grid/images/
scp $HOME\Downloads\*.png user@raspberrypi.local:~/glow-grid/images/   # several at once
```

Then press `r` in the menu (or restart `glow-grid`) and type the file's number.

### What to expect when you give it an image

The Pi fits any image to the grid and plays it. How good it looks depends on what you give it.

**Works well**

- **Pixel art at or near 16×16** (Glow Grid exports, Piskel sprites, the examples) comes out pixel-perfect.
- **Animations:** a sprite sheet (frames side by side, 16 px tall) or an animated GIF. Put the speed in the name: `walk_8fps.png`.
- **Transparency** becomes "off" LEDs.
- **Non-square images** are centered and fitted without stretching.

**Current limits**

1. **Photos and large images look messy.** The Pi shrinks images by picking single pixels, which keeps pixel art sharp but makes a big photo noisy. Workaround: import the photo into the Glow Grid simulator with Import mode set to **Photo** (averages each cell), check it in *LED sim*, then save the 16×16 PNG and copy that.
2. **The menu lists only `.png` and `.gif`.** `play.py` opens JPG and WEBP directly (`python3 play.py images/photo.jpg`), but those files won't appear in the `glow-grid` menu.
3. **Wide strips play as animations.** An image exactly 16 px tall and 32, 48… px wide is split into frames, one per 16 px. That's only a surprise if you meant it as a single wide still.
4. **Wiring comes first.** Until the probe settings are in `local_config.py`, every image looks scrambled on the real panel.
5. **Near-black isn't off, and dark shades can vanish.** See *Designing for LEDs*; the simulator's Panel check flags both.

Tip: avoid spaces in filenames (`my_sprite.png`), since they complicate `scp`.

**Without the menu:** `play.py` is what the menu runs for each image, and you can call it directly to test one file:

```bash
cd ~/glow-grid && source venv/bin/activate
python3 play.py knight.png           # bare names are looked up in images/
python3 play.py knight_4fps.png 10   # override the frame rate
python3 play.py images/photo.jpg     # any format Pillow opens
```

A still stays up until you press Ctrl+C; an animation loops. Either way the panel is cleared on exit.

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

## Related tools

### Piskel

[Piskel](https://www.piskelapp.com/) is a free, open-source ([source on GitHub](https://github.com/piskelapp/piskel), Apache-2.0) sprite editor with layers, onion skinning and frame-by-frame animation. It runs in the browser, and offline desktop builds are available from its repo. It's a good choice when you want more drawing tools than Glow Grid has, and its exports work here directly:

1. Create a sprite, then **Resize** the canvas to **16×16**.
2. Draw. Leave the background transparent (it becomes "off" on the panel) or use pure black.
3. Export:
   - **Still:** Export → PNG, one frame.
   - **Animation:** Export → PNG as a spritesheet laid out in **one row**, so it's 16 px tall with frames side by side. Rename it to add the frame rate, e.g. `walk_8fps.png`. Or export a **GIF**; `play.py` uses the GIF's own timing.
4. Import the file into Glow Grid and switch to *LED sim* to check it before copying it to the Pi. A one-row spritesheet loads back as separate frames.

### WLED

[WLED](https://kno.wled.ge/) is popular open-source firmware for driving addressable LEDs from an **ESP32** over Wi-Fi. It has a web UI, a phone app, 2D matrix support, and (since v16) GIF and pixel-art playback. It runs on the ESP32, not on the Pi, so it's an alternative way to drive this same panel rather than part of this project.

- To use WLED with a 16×16 panel, set *LED Preferences → 2D configuration* (panel size, first LED corner, orientation, serpentine). These are the same four facts `probe.py` finds.
- Glow Grid's LED sim is still useful for WLED art: it shows what survives on real LEDs regardless of which board drives them.
- Possible future directions (not built yet): a "Send to WLED" button in Glow Grid using WLED's JSON API, streaming animations from the Pi to WLED over DDP, and a standalone port of glow-grid to an ESP32-C3 board.

## License

MIT, see [LICENSE](LICENSE).
