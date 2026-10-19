# Third-party notices

glow-grid's own code, firmware, editor, example sprites and enclosure generator are by David Woods (dwooods), MIT licensed (see [LICENSE](LICENSE)). This file lists everything that is not his: what is used, under what licence, and what is only mentioned.

Licences below are as published by each project when this file was written. Check them again before a release.

## 1. Libraries that are used

### Raspberry Pi side (Python)

| Library | Licence | Used for |
|---|---|---|
| [rpi5-ws2812](https://github.com/niklasr22/rpi5-ws2812) (Niklas Rousset) | MIT | Sends LED data to the panel over SPI on a Pi 5. The only way glow-grid talks to the panel on a Pi. |
| [Pillow](https://python-pillow.org/) | HPND (permissive) | Reading and writing PNG and GIF files. |
| [pyserial](https://github.com/pyserial/pyserial) | BSD-3-Clause | `c3/tools/gg_tool.py`, USB serial to the ESP32-C3. |

### ESP32-C3 firmware (Arduino C++)

| Library | Licence | Used for |
|---|---|---|
| [Adafruit NeoPixel](https://github.com/adafruit/Adafruit_NeoPixel) | LGPL-3.0 | Drives the WS2812B panel from the C3. The one library in the firmware that is not permissively licensed. |
| [arduino-esp32 core](https://github.com/espressif/arduino-esp32) (WiFi, WebServer, LittleFS, Preferences, ESPmDNS, DNSServer) | LGPL-2.1-or-later | The board support the sketch is built on. |
| [ESP-IDF](https://github.com/espressif/esp-idf) (underneath the core) | Apache-2.0 | Wi-Fi stack, RTOS, flash filesystem, random numbers. |

**If you sell a board with this firmware on it** (the LGPL parts above):

- Keep the firmware source public, as it is now. That, with this file, covers the source and notice duties for the application code.
- Ship or link to this file with the product (a card in the box or a URL on the product page is enough).
- Do not lock the board: leave USB flashing open and do not enable secure boot or flash encryption. LGPL-3.0 expects a user to be able to install a modified version of the library on the device.
- If you would rather not carry the Adafruit NeoPixel obligation at all, replace it with a short driver written directly on the ESP-IDF RMT peripheral (Apache-2.0). That is a code change and a retest of LED timing, not a licence workaround.

### Test and build tools (not shipped)

| Tool | Licence | Used for |
|---|---|---|
| numpy, shapely | BSD-3-Clause | `enclosure/build.py` geometry. |
| trimesh | MIT | `enclosure/build.py` mesh handling and STL export. |
| manifold3d | Apache-2.0 | Boolean operations in `enclosure/build.py`. |
| Playwright | Apache-2.0 | Browser smoke tests (`tests/test_smoke*.py`). |
| Node.js | MIT | Parity and schedule-parsing tests. |

### Editor (web/)

The editor is plain HTML, CSS and JavaScript with no bundled libraries, fonts or run-time requests to other sites. It uses each device's own system fonts (the installed UI and monospace fonts), so nothing is downloaded.

## 2. The enclosure descends from three CC BY designs

The case grid and one-part-frame idea come from a chain of Creative Commons Attribution designs on Thingiverse:

1. **"16x16 RGB Matrix"** by The_Wrench_DIY, January 2020, CC BY: https://www.thingiverse.com/thing:4127683 (video: https://youtu.be/Cz694aEhIKQ)
2. **"16x16 LED matrix grid with diffuser and one-part frame"** by chummer, June 2020, CC BY, a remix of 1: https://www.thingiverse.com/thing:4459985
3. **"16x16 LED matrix grid with diffuser and one-part frame (with hole for panel mount DC power adapter)"** by makeitworktech (Make It Work), December 2022, CC BY, a remix of 2: https://www.thingiverse.com/thing:5737371 (video: https://www.youtube.com/watch?v=WSex5f1qzH8, channel: https://www.youtube.com/@makeitworktech)

**What was taken from them:** the 10 mm LED pitch and the 1 mm grid wall thickness, measured from the cell grid, and the idea of printing the grid and diffuser as one part. **What was not:** no mesh or STL file from these designs is in this repository or used by `enclosure/build.py`. The frame, holder, cap, cover and cradle are generated from code in this repository.

The generated STL files (`glow-grid_*.stl`, as published on Printables) are released under **CC BY 4.0**, with the credit above. CC BY 4.0 allows printing, modifying and selling prints, including commercially, as long as the credit stays and changes are marked.

## 3. Mentioned, but not used

These appear in the README or JOURNEY as tools you can use alongside glow-grid or that the author read about. None of their code, firmware, assets or user interface is in this repository.

- **[Piskel](https://www.piskelapp.com/)** (Apache-2.0): a separate sprite editor. glow-grid can read its PNG and GIF exports, the same as any other PNG or GIF. Nothing of it is bundled.
- **[WLED](https://kno.wled.ge/)** (open source; see its repository for the current licence): a separate ESP32 firmware. The author read its public documentation while researching how Wi-Fi control of an LED board could work, and WLED's 2D matrix settings turned out to ask for the same four wiring facts `probe.py` finds. The one behaviour carried over is sending permissive CORS headers so a web page can talk to the board, which is a standard web feature. No WLED code is used, and glow-grid is not compatible with WLED's API or app.
- **Home Assistant, Pipplee, WLED Native, PixelForge:** read about during research. Not used.

## 4. Names

"Raspberry Pi", "ESP32", "WLED", "Piskel", "Adafruit", "Thingiverse", "Printables" and similar names belong to their owners and appear here only to say what glow-grid works with. They are not part of glow-grid's name.

## Open items before selling a product

Plan (2026-10-19): US only, a boxed kit, marketed to makers 14+, a pre-certified Wi-Fi module, and a listed (UL) power supply. These are decisions or checks that are not code:

- **Name check:** search "glow grid", "glowgrid", "glo grid" and "glow-grid" separately in trademark databases (USPTO, EUIPO, TMview, WIPO), live marks in classes 9, 11 and 28, before putting the name on a product or packaging. Not cleared.
- **Example sprites:** all are drawn in `examples/sprites.py` and `examples/sprites2.py`. Confirm none was traced from, or generated to resemble, someone else's character.
- **Radio:** the ESP32-C3 SuperMini is not a certified module. A sold kit should use a board built on a pre-certified module (for example an ESP32-C3-MINI-1 board), installed as its FCC grant requires, with the host device tested to FCC Part 15B. Not done.
- **Power supply:** ship a UL-listed 5 V Class 2 adapter rated for the panel; not assembled by the seller.
- **Age grade and marketing:** keep the product and packaging aimed at makers 14+; Prop 65 and product-liability checks not done.
