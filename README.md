# glow-grid

Pixel art and animations for a **16x16 WS2812B LED panel** on a **Raspberry Pi 5**, driven over hardware SPI, plus **Glow Grid**, a browser-based editor and LED simulator for designing them before they ever touch the panel.

Sister project to [led-strip](https://github.com/dwooods/led-strip), which drives a 1D strip with procedural effects. This one is about 2D images: draw, simulate, copy to the Pi, play.

## The workflow

1. **Design** in the Glow Grid simulator (`web/index.html`, or the hosted/installed version below), or in [Piskel](#piskel).
2. **Simulate and adjust**: switch to *LED sim* to see what survives on real LEDs, and tune *Brightness* and *Gamma* until it looks right. The *Panel check* flags pixels that will be barely lit or shift color, and estimates current draw against your power supply.
3. **Export** a still PNG or an animation sprite sheet (frames side by side, frame rate in the filename, e.g. `knight_4fps.png`). The PNG remembers the brightness and gamma you picked.
4. **Copy** it to the Pi's `images/` folder and play it from the terminal: pick it in the `glow-grid` menu, or run `python3 play.py knight_4fps.png`. The Pi uses the same math and the image's own light settings, so the panel shows what the simulator showed.

The simulator never talks to the panel. It's a preview tool; the Pi's Python program is what lights the LEDs.

## The simulator

`web/` is a static site with no build step: one `index.html`, plus a manifest and service worker so it can be installed as an app.

- **Open it locally**: double-click `web/index.html`. Everything works except app install.
- **Hosted**: every push to `main` that touches `web/` deploys it to GitHub Pages at `https://dwooods.github.io/glow-grid/` (see `.github/workflows/pages.yml`; app icons are generated in CI from `examples/sprites.py`). One-time setup: *Settings → Pages → Build and deployment → Source: GitHub Actions*.
- **Install as an app**: open the hosted page in Chrome or Edge and click *Install app* (or the install icon in the address bar). It then runs in its own window and works offline.
- **Download**: *Download for offline* on the hosted page saves the single-file simulator.

Your drawings are saved in that browser's local storage, so re-import a sprite sheet to move work between browsers.

The LED model matches `grid_common.py` exactly: `round(255 * BRIGHTNESS * (c/255) ** GAMMA)`, with any non-zero channel kept at 1 or above.

### Light settings travel with the image

When you save a PNG, Glow Grid writes its current *Brightness* and *Gamma* into the file (a PNG text chunk named `glow-grid`; the pixels are unchanged). On the Pi, `play.py` reads them and uses them for that image, and prints what it used:

```
knight_4fps.png: 4 frame(s), brightness 0.35, gamma 2.2 from the image
```

- Images without them (Piskel exports, GIFs, photos, older Glow Grid saves) use `BRIGHTNESS` and `GAMMA` from `local_config.py`.
- `MAX_BRIGHTNESS` in `local_config.py` (default 0.4) caps every image, so a design saved at 0.9 can't overload a 6A supply. The Pi says when it capped one. Raise it only with a bigger supply.
- `USE_IMAGE_LIGHT = False` ignores the saved settings and always uses `local_config.py`.
- Importing a Glow Grid PNG back into the simulator restores its brightness and gamma too.
- Editing the PNG in another app may drop the settings; it then falls back to `local_config.py`.

### Export size: 1× for the Pi, bigger to share

Exports are 16×16 by default: one pixel per LED, which is exactly what the Pi plays. The *Scale* option in the export card also saves 8×, 16× or 32× copies for viewing and sharing: each pixel becomes a sharp block, and the name gets `_x16` etc. Copy the **1×** file to the Pi. A scaled still plays the same on the panel, but a scaled animation plays as one squashed still because it isn't 16 px tall.

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
git config core.fileMode false   # so the chmod doesn't block future git pulls
./run.sh            # first run: creates venv, installs deps, writes examples, opens menu
ln -s ~/glow-grid/run.sh ~/.local/bin/glow-grid  # then just type: glow-grid
```

On first run `run.sh` creates `local_config.py` from `local_config.example.py`. That's where your panel's wiring order, brightness and gamma live. It's git-ignored, so `git pull` never overwrites it.

### Find your panel's wiring order (do this first)

Panels are wired in different orders, and a wrong mapping scrambles images into noise that looks like a hardware fault.

1. Pick `p` in the menu (or run `python3 probe.py`). Five raw indexes light up: 0 red, 1 green, 15 white, 16 yellow, 255 blue.
2. Set `FLIP_X`, `FLIP_Y`, `COLUMN_MAJOR` and `SERPENTINE` in `local_config.py`. The comments there map what you see to each setting.
3. Pick `c` (or `python3 probe.py check`). You should see white at the top-left, red along the top, green down the left, and a blue diagonal. If so, images will display correctly.
4. Press `k` in the menu to mark the wiring as confirmed. This sets `WIRING_CONFIRMED = True` in `local_config.py`. Until then the menu (and `play.py`) show a "wiring not checked yet" warning, so a scrambled image never looks like a mystery.

`w` walks a single dot through every index, which helps if the markers are ambiguous.

## The menu

```
Glow Grid (16x16)
  ! Wiring not checked yet: images may look scrambled.
    Run p, set the flags in local_config.py, then c. If c looks right, press k.
  1. knight.png  (still)
  2. knight_4fps.png  (4 frames, 4 fps)
  3. smiley_3fps.png  (4 frames, 3 fps)
  p. Wiring probe (markers)
  w. Wiring probe (walk every index)
  c. Check wiring settings
  k. Wiring looks right: mark it confirmed
  r. Rescan images
  o. Turn off
  q. Quit
```

The warning and `k` disappear once the wiring is confirmed. Images in `images/` are numbered automatically. Type a number to play one; add a number after it to override the frame rate (`2 8` plays file 2 at 8 fps). Like led-strip, whatever you pick runs in the background, and picking something else stops it cleanly first (SIGINT, so the panel is always cleared).

To add your own images, see the next section.

## Using your own images

Put images in **`~/glow-grid/images/`** on the Pi. The menu lists every `.png`, `.gif`, `.jpg`/`.jpeg`, `.webp` and `.bmp` there, numbered.

**Copy from Windows** (PowerShell, not the SSH window):

```powershell
scp $HOME\Downloads\walk_8fps.png user@raspberrypi.local:~/glow-grid/images/
scp $HOME\Downloads\*.png user@raspberrypi.local:~/glow-grid/images/   # several at once
```

Then press `r` in the menu (or restart `glow-grid`) and type the file's number.

### What to expect when you give it an image

The Pi fits any image to the grid and plays it. How good it looks depends on what you give it.

**Works well**

- **Pixel art at 16×16** (Glow Grid exports, Piskel sprites, the examples) comes out pixel-perfect. So does pixel art at an exact 2×, 3×, 4×… upscale.
- **Photos and large images:** anything more than 2× the grid in either direction is averaged per cell, so photos come out smooth instead of noisy. Smaller images keep exact pixels, which keeps pixel-art edges hard. Change this with `RESIZE` in `local_config.py` (`"auto"`, `"nearest"` or `"average"`).
- **Animations:** an animated GIF, or a sprite sheet (frames side by side, 16 px tall) whose name contains the speed or `_sheet`: `walk_8fps.png`, `walk_sheet.png`. Sheets saved from Glow Grid are already named this way.
- **Transparency** becomes "off" LEDs.
- **Non-square images** are centered and fitted without stretching.
- **Formats:** PNG, GIF, JPG, WEBP and BMP all show in the menu.

**Things to watch**

1. **Name your sprite sheets.** A 16-px-tall strip *without* `_8fps` or `_sheet` in its name is treated as one wide still and squashed to fit. (This rule stops ordinary wide images from turning into accidental animations.)
2. **Mid-size pixel art** (between 1× and 2× the grid, e.g. a 24×24 sprite) keeps exact pixels, so some detail is dropped. Draw at 16×16, or export at an exact multiple.
3. **Wiring comes first.** Until the probe settings are set and confirmed (`p`, `c`, then `k`), images may look scrambled; the menu warns you.
4. **Near-black isn't off, and dark shades can vanish.** See *Designing for LEDs*; the simulator's Panel check flags both.

Tip: avoid spaces in filenames (`my_sprite.png`), since they complicate `scp`.

**Without the menu:** `play.py` is what the menu runs for each image, and you can call it directly to test one file:

```bash
cd ~/glow-grid && source venv/bin/activate
python3 play.py knight.png           # bare names are looked up in images/
python3 play.py knight_4fps.png 10   # override the frame rate
python3 play.py images/photo.jpg     # photos are averaged automatically
```

A still stays up until you press Ctrl+C; an animation loops. Either way the panel is cleared on exit.

## Architecture

- **`grid_common.py`**: panel config and defaults, `get_strip()` (also takes a lock so only one glow-grid program drives the panel at a time), `xy_to_index()` (wiring map), `correct()` (gamma/brightness lookup table), `set_light()` / `image_light()` (per-image brightness and gamma, capped by `MAX_BRIGHTNESS`), `fit()` (fit any image to the grid without stretching, averaging large images and keeping pixel art exact; transparency becomes black), `load_frames()` (still, named sprite sheet or animated GIF → frames + delays), and `draw()`.
- **`play.py`**: plays one file with its saved light settings. A still is held until stopped; an animation loops.
- **`probe.py`**: wiring diagnostics (markers / walk / check).
- **`glowgrid.py`**: the menu/launcher. Scans `images/`, runs `play.py` / `probe.py` as a background subprocess, runs only one at a time, and warns until the wiring is confirmed.
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
   - **Animation:** Export → PNG as a spritesheet laid out in **one row**, so it's 16 px tall with frames side by side. Rename it to add the frame rate, e.g. `walk_8fps.png` (required: without `_8fps` or `_sheet` in the name it plays as one squashed still). Or export a **GIF**; `play.py` uses the GIF's own timing.
4. Import the file into Glow Grid and switch to *LED sim* to check it before copying it to the Pi. A named one-row spritesheet loads back as separate frames.

### WLED

[WLED](https://kno.wled.ge/) is popular open-source firmware for driving addressable LEDs from an **ESP32** over Wi-Fi. It has a web UI, a phone app, 2D matrix support, and (since v16) GIF and pixel-art playback. It runs on the ESP32, not on the Pi, so it's an alternative way to drive this same panel rather than part of this project.

- To use WLED with a 16×16 panel, set *LED Preferences → 2D configuration* (panel size, first LED corner, orientation, serpentine). These are the same four facts `probe.py` finds.
- Glow Grid's LED sim is still useful for WLED art: it shows what survives on real LEDs regardless of which board drives them.
- Possible future directions (not built yet): a "Send to WLED" button in Glow Grid using WLED's JSON API, streaming animations from the Pi to WLED over DDP, and a standalone port of glow-grid to an ESP32-C3 board.

## License

MIT, see [LICENSE](LICENSE).

The build story, decisions and lessons are in [JOURNEY.md](JOURNEY.md).
