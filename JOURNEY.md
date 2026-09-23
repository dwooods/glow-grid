# Pixel Art on a 16x16 LED Panel with a Raspberry Pi 5: A Journey

*Repo: [github.com/dwooods/glow-grid](https://github.com/dwooods/glow-grid) · Sister project: [led-strip](https://github.com/dwooods/led-strip)*

This is the story of turning a flexible 16x16 WS2812B panel and a Raspberry Pi 5 into a pixel-art player, and of building **Glow Grid**, a browser simulator that shows what a design will really look like on the LEDs before it ever touches them. Along the way: a wiring order you have to discover rather than assume, colors that look fine on a monitor and vanish on an LED, and one design detour that got undone.

## The starting point

The led-strip project had already solved the hard Pi 5 problem: the Pi 5's GPIO lives on the **RP1** chip, so the classic `rpi_ws281x` / Adafruit `neopixel` libraries don't work, and the fix is to drive the LEDs over **hardware SPI** with [`rpi5-ws2812`](https://pypi.org/project/rpi5-ws2812/). A 256-LED panel uses exactly the same wiring:

- Panel **DIN** → 330Ω resistor → Pi **GPIO10 / MOSI** (physical pin 19)
- Panel **GND** → the power supply's ground **and** a Pi ground pin (common ground)
- Panel **5V** → an external 5V supply, never the Pi

What changed was the job. A strip plays procedural effects; a panel shows *pictures*. So instead of one Python file per effect, this project needed one player that can show any image, plus a way to design images that survive the trip to real LEDs.

## Two tools, one hand-off

The project ended up as two deliberately separate pieces:

1. **Glow Grid (the simulator)** runs in a browser. You draw or import pixel art, switch to *LED sim* to see what the panel will actually show, and adjust brightness and gamma until it looks right. It never talks to the panel.
2. **The Pi program** runs from the terminal: a `glow-grid` menu that lists everything in `images/`, and `play.py`, which shows one file.

The hand-off between them is a plain PNG. A still is a 16x16 PNG; an animation is a sprite sheet (frames side by side) with the frame rate in the name, like `knight_4fps.png`.

That separation was a decision, not an accident. Midway through, I built a version where the Pi served the simulator as a web page with a "Send to panel" button. It worked, but it blurred the line between *checking a design* and *running the panel*, so it came out again. The simulator is where you decide what looks right; the Pi faithfully plays what you decided. Keeping those apart made both simpler.

## The first surprise: you have to find your panel's wiring order

A 16x16 panel is one long chain of 256 LEDs folded into a square, and manufacturers fold it differently. Index 0 can be in any corner. The chain can run along rows or down columns. It can snake back and forth (serpentine) or jump back to the same edge each row. Get it wrong and a picture turns into noise that looks exactly like a hardware fault.

So the project never assumes. `probe.py` lights five raw indexes in distinct colors: 0 red, 1 green, 15 white, 16 yellow, 255 blue. Where those land tells you four facts, and four settings cover every common layout:

| What you see | Setting |
|---|---|
| Which corner red is in | `FLIP_X`, `FLIP_Y` |
| Green beside red, or above/below it | `COLUMN_MAJOR` |
| Yellow next to white, or back on red's edge | `SERPENTINE` |

A `check` pattern (white top-left, red along the top, green down the left, blue diagonal) confirms it. Until you press `k` to confirm, the menu shows a "wiring not checked yet" warning, so a scrambled image never becomes a mystery. WLED's 2D matrix settings ask for the same four facts, which was a nice confirmation that this is the right model.

## Why a simulator at all

The honest answer: my first designs looked great on screen and bad on the panel.

**Near-black is not off.** A dark background like `#0d1117` looks black on a monitor, but on the panel it lights every one of the 256 LEDs a faint gray. Only `#000000` is off.

**Dark colors vanish.** LEDs need gamma correction so colors match what you drew, and the brightness has to be capped (more on power below). Put those together and anything dark ends up at 1–3 out of 255: a smudge, or nothing. My first instinct was "more gamma will fix it." It doesn't; gamma makes dark colors *darker*. The real fix was a floor that keeps any non-black channel at least 1, plus a warning in the simulator.

**Detail doesn't survive shrinking.** A 50x50 drawing shrunk to 16x16 loses eye highlights, thin lines and outlines. Drawing at 16x16 with saturated colors and contrasting edges works; dark outlines don't.

So Glow Grid's *LED sim* view runs the exact same math as the Pi:

```
value = round(255 × brightness × (c / 255) ^ gamma), with any non-zero channel kept at 1 or above
```

It even copies Python's round-half-to-even behavior in JavaScript, so the preview is what the Pi sends, not an approximation. A **Panel check** outlines pixels that will be barely lit or will shift color, and estimates the current draw against your power supply.

## Light settings that travel with the image

Once the simulator was where you tuned brightness and gamma, the Pi needed to use the same numbers. Keeping a config file on the Pi in sync by hand was guaranteed to drift.

The fix: when Glow Grid saves a PNG, it writes the brightness and gamma into the file as a small PNG text chunk (the pixels are untouched). `play.py` reads it and says what it used:

```
knight_4fps.png: 4 frame(s), brightness 0.35, gamma 2.2 from the image
```

Images without it (Piskel exports, GIFs, photos) fall back to the defaults in `local_config.py`. Importing a saved PNG back into the simulator restores its settings too.

## Power: the cap that makes this safe

256 LEDs at full white can pull around 15 A in theory. The panel runs from a 5V 6A supply, and at brightness 0.3 full white is about 4.7 A. Once brightness lives inside image files, though, one design saved at 0.9 could ask for about 14 A. So the Pi enforces `MAX_BRIGHTNESS` (default 0.4, roughly 6 A at full white), tells you when it capped an image, and the simulator warns you above 0.4 before you even save.

A related lesson from the 8x32 panel in the led-strip project: undersized supplies don't fail cleanly. They cause random stray pixels that look like software bugs.

## Feeding it images

The player accepts more than Glow Grid output, and the README documents what to expect so nobody has to guess:

- **Pixel art at 16x16** is pixel-perfect, and so is pixel art at an exact 2×, 3×, 4× upscale.
- **Photos and large images** (more than 2× the grid) are averaged per cell, so they come out smooth instead of noisy. Smaller images keep exact pixels, which keeps pixel-art edges hard.
- **Animations**: animated GIFs, or sprite sheets named with the speed (`walk_8fps.png`) or `_sheet`. That naming rule is on purpose: a wide 16-px banner shouldn't accidentally become an animation.
- **Transparency** becomes "off", and non-square images are centered without stretching.

For designing, [Piskel](https://www.piskelapp.com/) is the richer editor (layers, onion skinning). Its exports work directly, and Glow Grid is where you check them.

## Export size: 1× for the Pi, bigger to share

The simulator's exports are 16x16: one pixel per LED. That's exactly what the Pi wants, but it's a thumbnail in any image viewer. So the export has a **Scale** option: 1× for the Pi, or 8×/16×/32× for a sharp, blocky copy to view and share (named `_x16` etc.). A scaled still still plays correctly on the Pi; a scaled animation doesn't, so the rule is simple: 1× for the panel.

## The software shape

It follows the led-strip pattern that already worked:

- **`grid_common.py`**: the wiring map, the gamma/brightness table, image fitting, frame loading, and a small **panel lock** so two programs can never drive the SPI line at the same time.
- **`play.py`**: shows one file; a still is held, an animation loops, and the panel is always cleared on exit.
- **`glowgrid.py`**: the menu. It numbers whatever is in `images/`, runs one thing at a time in the background, and stops the old one cleanly before starting the next.
- **`local_config.py`**: your panel's wiring and defaults, git-ignored so `git pull` never overwrites it.
- **`run.sh`**, symlinked as `glow-grid`: creates the venv on first run and opens the menu.
- **`examples/sprites.py`**: the example sprites (an original knight and a smiley) stored as text grids, so they're diffable source instead of binary files.
- **`web/`**: the simulator, a single HTML file that also installs as an offline app.

## Small things that cost time

- **`git pull` refused to run** because of `chmod +x run.sh`. Git counts a permission change as an edit. `git config core.fileMode false` on the Pi stops that.
- **Bookworm blocks bare `pip install`**, which is why `run.sh` builds a venv.
- **A screenshot of transparency isn't transparency.** An editor's gray checkerboard gets imported as gray pixels.
- **JPEG noise becomes pixels.** Compression speckles in a downloaded image turn into off-color LEDs after fitting. Start from PNG, or clean the background to pure black.

## What's next

- First run on the real panel: probe the wiring, confirm it, then play a Glow Grid PNG and check the printed brightness.
- A 3D-printed grid and diffuser, so each LED reads as a square pixel instead of a dot.
- A "WLED JSON" export, so the same art can run on an ESP32 with [WLED](https://kno.wled.ge/).
- A current limiter that dims a frame based on its actual estimated draw rather than a flat cap.
