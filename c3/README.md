# Glow Grid player for the ESP32-C3 (step 1: USB, several sprites)

Stores several Glow Grid sprites in the board's flash and plays one at a time. Sprites go on and off the board over USB with a small PC tool. The Next button changes the sprite, the On/off button blanks the panel. Bluetooth is step 2 and will carry the same files.

**Status:** tested on a PC (the tests compile the real firmware logic against stand-ins for the Arduino core) and once on a C3 SuperMini: two sprites uploaded and played, and the player came back on its own after a power cycle. Buttons and Bluetooth are untested.

## Files

| File | Job |
|---|---|
| `c3_player/c3_player.ino` | the firmware: flash storage, serial commands, buttons, playback. The folder is named after the sketch because the Arduino IDE insists on it, so it opens straight from the clone |
| `c3_player/gg_core.h` | the parts with no Arduino dependency: the `.gg` file check, the wiring map, the brightness/gamma table (same maths as `grid_common.py`), CRC-32 |
| `tools/png_to_gg.py` | turns a Glow Grid PNG into a `.gg` sprite file (the editor's *Export for: ESP32-C3* writes the same file directly) |
| `tools/gg_tool.py` | `list`, `put`, `show`, `del`, `off`, `on`, `info` on the board over USB |
| `tools/gg_format.py` | reads and writes `.gg` files (used by the two tools and the tests) |
| `tests/` | 24 tests; see below |

## The `.gg` sprite file

12-byte header (`GG`, version, flags, cols, rows, frames, fps×10, brightness %, gamma×10), then the frames as raw RGB, 768 bytes each, row by row from the top-left, exactly as drawn. The file carries **no wiring order and no gamma correction**: the board applies its own wiring setting (`GG_COLUMN_MAJOR` etc. in `c3_player/gg_core.h`, same meaning as `local_config.py`) and the brightness table, and caps brightness at 0.4 (`GG_MAX_BRIGHT_PCT`). So a sprite file works on any panel, and a buggy app cannot overload the LEDs.

A 4-frame sprite is 3,084 bytes. The default partition leaves about 1.5 MB for sprites, so roughly 400 of them; `MAX_SPRITES` (48) is the list limit in RAM and is easy to raise.

## Install on the board

1. Arduino IDE: board **ESP32C3 Dev Module**, **USB CDC On Boot: Enabled**, **Partition Scheme: Default 4MB with spiffs**. Library: **Adafruit NeoPixel**. (LittleFS and the serial port are part of the esp32 core.)
2. Open `c3_player/c3_player.ino` (File > Open in the IDE, straight from the clone) and upload. The first start formats the flash storage (a few seconds). With nothing stored, LED 0 glows dim blue.
3. Wiring for the bench: GPIO6 to DIN, the C3's G to the panel GND and the supply GND, panel 5V from the supply only, C3 on USB. Buttons: GPIO5 and GPIO7 to GND (optional for this test; the serial `SHOW` command does the same).

## Use

```
pip install pillow pyserial
python3 tools/png_to_gg.py ../images/lantern_sprite.png  # writes lantern.gg (or use Export for: ESP32-C3 in the editor)
python3 tools/gg_tool.py put lantern.gg
python3 tools/gg_tool.py list
python3 tools/gg_tool.py show lantern
python3 tools/gg_tool.py del lantern
python3 tools/gg_tool.py off          # panel dark, board keeps running; `on` resumes
```

Close the Arduino Serial Monitor first; only one program can use the port. `gg_tool.py` finds the C3's port by its USB id; if it cannot, add `--port COM3`.

Add = `put` a new name. Replace = `put` the same name. The upload goes to a temporary file, is checked (size, CRC-32, valid header) and only then swapped in, so a cable pulled mid-upload cannot leave a broken sprite. The last uploaded sprite plays at once. Sprites survive a power cycle.

## Tests

```
python3 -m unittest discover -s tests -v      # needs g++, Pillow, pyserial; Linux, macOS or WSL
```

Set `GLOWGRID_REPO=/path/to/glow-grid` if this folder is not inside the repo (the parity tests import `grid_common.py`).

- **Parity:** `gg_core.h`, compiled on the PC, places and corrects every pixel exactly as `grid_common.py` does, for all 16 wiring combinations and nine brightness/gamma settings, including the 0.4 cap.
- **Board:** `c3_player.ino` itself, compiled against small stand-ins for the Arduino core (`tests/arduino_stub/`), driven by the real `gg_tool.py` through a pseudo-terminal: add, list, replace, delete, show, a wrong checksum, an invalid file, a bad name, a stalled upload, both buttons, `OFF`/`ON` over serial, and a restart that finds the stored sprite.
- **Format:** round trip and rejection of bad files, in both the Python and the C check. The repo's own `tests/test_gg_export.py` adds that the editor writes byte-identical files.
- **Playback and edges:** frames advance at the stored fps and wrap, a still renders once; replacing the sprite that is playing; Next while the panel is off; over-long and malformed serial lines; a 31-character name; the `MAX_SPRITES` limit.
- **Converter and tool:** `png_to_gg.py` writes the same bytes as `gg_format.pack` (metadata, defaults, overrides, transparency, wrong sizes refused); `gg_tool.py` turns a dead or silent port into a plain message and picks the Espressif device among several ports.
- **IDE build:** the sketch is compiled with the function prototypes the Arduino IDE generates, so a definition order the IDE rejects fails here too.

Two deliberate breaks (wrong wiring default; checksum not checked) each made the suite fail. The first real IDE compile failed on an Arduino quirk the PC build could not see then (auto-generated prototypes above a struct); fixed by moving the struct into `gg_core.h`, and the IDE build test now covers it. The serial-line test found that an over-long line used to run its tail as a command; fixed.

**Not tested:** the real esp32 core and LittleFS on real flash, NeoPixel timing with 256 LEDs, serial throughput on the real USB port, Bluetooth.

## Next (step 2)

Bluetooth: the same `PUT`/`LIST`/`DEL`/`SHOW` messages over a BLE service, accepted only for a short window after a button press; the web app sends them from Chrome (Android, desktop); iPhone needs the Capacitor app.
