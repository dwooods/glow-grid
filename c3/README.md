# Glow Grid player for the ESP32-C3 (USB and Wi-Fi, several sprites)

Stores several Glow Grid sprites in the board's flash and plays one at a time. Sprites go on and off the board over USB with a small PC tool. The Next button changes the sprite, the On/off button blanks the panel. The editor's Board card does the same jobs from Chrome or Edge over Web Serial, or over Wi-Fi from any browser on your network (its Network button sets the address and, over USB, the board's Wi-Fi). Since firmware 9 the board can also join your Wi-Fi and take the same files and commands over HTTP (see Wi-Fi below); Bluetooth is step 3.

**Status:** tested on a PC (the tests compile the real firmware logic against stand-ins for the Arduino core) and once on a C3 SuperMini: two sprites uploaded and played, and the player came back on its own after a power cycle. Firmware 9 (Wi-Fi) was tested on the board on 2026-10-15 with `gg_tool.py` over USB and `--host`; the editor's Wi-Fi side passed on the real board from Chrome on Windows (a tab and the installed app) on 2026-10-15; the network scan (firmware 10) is tested on a PC only. Buttons and Bluetooth are untested.

## Files

| File | Job |
|---|---|
| `c3_player/c3_player.ino` | the firmware: flash storage, serial commands, buttons, playback. The folder is named after the sketch because the Arduino IDE insists on it, so it opens straight from the clone |
| `c3_player/gg_core.h` | the parts with no Arduino dependency: the `.gg` file check, the wiring map, the brightness/gamma table (same maths as `grid_common.py`), CRC-32 |
| `tools/png_to_gg.py` | turns a Glow Grid PNG into a `.gg` sprite file (the editor's *Export for: ESP32-C3* writes the same file directly) |
| `tools/gg_tool.py` | `list`, `put`, `get`, `show`, `del`, `off`, `on`, `rotate`, `info` on the board over USB, or over Wi-Fi with `--host`; `wifi scan/set/status/clear` over USB (the firmware also answers `CRC <name>`: the checksum and size of a stored file, which the editor's Remove examples uses; and `GET <name>`: the file as `D <hex>` lines then `OK crc=… size=…`, fw 8, which `gg_tool.py get` and the editor's Load button use) |
| `tools/gg_format.py` | reads and writes `.gg` files (used by the two tools and the tests) |
| `tests/` | 38 tests; see below |

## The `.gg` sprite file

12-byte header (`GG`, version, flags, cols, rows, frames, fps×10, brightness %, gamma×10), then the frames as raw RGB, 768 bytes each, row by row from the top-left, exactly as drawn. The file carries **no wiring order and no gamma correction**: the board applies its own wiring setting (`GG_COLUMN_MAJOR` etc. in `c3_player/gg_core.h`, same meaning as `local_config.py`) and the brightness table, and caps brightness at 0.4 (`GG_MAX_BRIGHT_PCT`). So a sprite file works on any panel, and a buggy app cannot overload the LEDs.

A 4-frame sprite is 3,084 bytes. The default partition leaves about 1.5 MB for sprites, so roughly 400 of them; `MAX_SPRITES` (64) is the list limit in RAM; a 65th new name is refused with a message (replacing one of the 64 is fine).

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
python3 tools/gg_tool.py rotate 300   # next sprite every 5 minutes, in list order; 0 = stay on one
python3 tools/gg_tool.py info         # fw=<n> says which firmware is on the board
```

**Is the board current?** `info` prints `fw=<n>`; the Serial Monitor shows the same number in the boot line (`Glow Grid player fw 3 ready`). Compare it with `GG_FW_VERSION` at the top of `c3_player.ino` in your clone; smaller (or an `INFO` line without `fw=`) means re-flash. The number goes up with every firmware change pushed to the repo.

Close the Arduino Serial Monitor first; only one program can use the port. `gg_tool.py` finds the C3's port by its USB id; if it cannot, add `--port COM3`.

Add = `put` a new name. Replace = `put` the same name. The upload goes to a temporary file, is checked (size, CRC-32, valid header) and only then swapped in, so a cable pulled mid-upload cannot leave a broken sprite; a power loss mid-upload leaves a temp file that the next boot removes. The last uploaded sprite plays at once. Sprites survive a power cycle, and so does `off`: a board that was off comes back dark until `on`, `show`, `put`, the Board card or a button. `rotate <seconds>` makes the board move to the next sprite on its own (list order; each sprite keeps animating for the whole interval; Next, `show` and `put` restart the interval; `off` pauses it); that setting survives a power cycle too.

## Wi-Fi (firmware 9; scan is firmware 10)

Set the network once over USB, with the Serial Monitor closed:

```
python3 tools/gg_tool.py wifi scan                              # networks the board can hear, strongest first (firmware 10)
python3 tools/gg_tool.py wifi set "My Network" "my password"   # "" for an open network; 2.4 GHz only
python3 tools/gg_tool.py wifi status                           # wifi=connected ip=... when it has joined
python3 tools/gg_tool.py wifi clear
```

The name and password are stored in the chip's NVS (not in the sprite flash, and not in the sketch, so nothing secret is in the repo). **The password is stored as plain text:** the chip does not encrypt its flash by default, so anyone who can plug into the board's USB port can read it back with a flash tool. Nothing over the network can: `WIFI STATUS` never prints it, no HTTP route returns it, and the editor empties its password box after saving and keeps no copy. Use a guest or IoT network, or a password you use nowhere else, if the board will sit where others can reach it. The board joins by itself at every start and answers at `http://glowgrid.local` (mDNS) or its address. Then unplug USB and use the same commands over the network:

```
python3 tools/gg_tool.py --host glowgrid.local put lantern.gg
python3 tools/gg_tool.py --host 192.168.1.50 list
```

**No password on the network side for now:** anyone on the home network can list, send and delete sprites (the 0.4 brightness cap still applies). Add a token before this goes anywhere less trusted.

HTTP API (all replies are the same `OK ...` / `ERR ...` text as USB, with status 200, 404 for a missing sprite, 400 otherwise; every reply carries CORS headers, and the browser's pre-flight for a request from the https editor page to a private address is answered):

| Request | Same as |
|---|---|
| `GET /ping`, `/info`, `/list` | `PING`, `INFO`, `LIST` |
| `GET /crc?name=X`, `GET /get?name=X` | `CRC X`; the file's bytes |
| `POST /show?name=X`, `/del?name=X`, `/off`, `/on`, `/rotate?s=N` | `SHOW`, `DEL`, `OFF`, `ON`, `ROTATE` |
| `POST /put?name=X[&size=N][&crc=hex]` | `PUT`; the file as `multipart/form-data`, field `file` |

Uploads must be multipart: the ESP32 web server hands a raw POST body over as a text string that stops at the first zero byte (the probe cut a 49,164-byte sprite to 231 bytes), and multipart is binary-safe and is a plain "simple" request, so the browser sends no pre-flight. While a file is being received or stored the board is busy for a fraction of a second, so the animation may hitch; `INFO` reports `gap_ms`, the longest the main loop stalled since the last `INFO`.

## Tests

```
python3 -m unittest discover -s tests -v      # needs g++, Pillow, pyserial; Linux, macOS or WSL
```

Set `GLOWGRID_REPO=/path/to/glow-grid` if this folder is not inside the repo (the parity tests import `grid_common.py`).

- **Parity:** `gg_core.h`, compiled on the PC, places and corrects every pixel exactly as `grid_common.py` does, for all 16 wiring combinations and nine brightness/gamma settings, including the 0.4 cap.
- **Board:** `c3_player.ino` itself, compiled against small stand-ins for the Arduino core (`tests/arduino_stub/`), driven by the real `gg_tool.py` through a pseudo-terminal: add, list, replace, delete, show, a wrong checksum, an invalid file, a bad name, a stalled upload, both buttons, `OFF`/`ON` over serial, and a restart that finds the stored sprite.
- **Editor against firmware:** `tests/board_e2e.js` runs the editor's real `SerialTransport` and `GgBoard` (and `ggBytes`, `ggDecode`) through Node against the compiled firmware: Send, List, CRC, Load (`GET`) of a 2-frame and a 64-frame sprite, Delete. Catches the two sides drifting apart.
- **Format:** round trip and rejection of bad files, in both the Python and the C check. The repo's own `tests/test_gg_export.py` adds that the editor writes byte-identical files.
- **Playback and edges:** frames advance at the stored fps and wrap, a still renders once; replacing the sprite that is playing; Next while the panel is off; `CRC`; `GET` returning the stored file byte for byte; over-long and malformed serial lines; a 31-character name; the `MAX_SPRITES` limit; `ROTATE` cycling in list order, paused by `OFF`, restarted by Next, kept across a power cycle, switched off with 0.
- **Converter and tool:** `png_to_gg.py` writes the same bytes as `gg_format.pack` (metadata, defaults, overrides, transparency, wrong sizes refused); `gg_tool.py` turns a dead or silent port into a plain message and picks the Espressif device among several ports.
- **Wi-Fi:** `WIFI SCAN/SET/STATUS/CLEAR` with names holding spaces and symbols (hex on the wire), the password never printed, rejoining after a power cycle, the longest legal name and password; `WIFI SCAN` (duplicates merged to the strongest, hidden and over-long names left out, sorted, capped at 20, empty result, saved network undisturbed); the HTTP API against the compiled firmware through a real loopback server (stand-in `WebServer.h`): every route, a 64-frame upload with zero bytes intact, CORS and the private-network pre-flight, every error path leaving the flash clean; `gg_tool.py --host` doing the same jobs.
- **Editor over Wi-Fi:** `tests/board_http_e2e.js` runs the editor's real `HttpBoard` through Node against the compiled firmware's loopback HTTP server: multipart Send of a 64-frame sprite with zero bytes, List, Info, Load with CRC check, Play, lights, rotate, Delete, and the firmware's own refusals. Catches the editor and the HTTP API drifting apart.
- **IDE build:** the sketch is compiled with the function prototypes the Arduino IDE generates, so a definition order the IDE rejects fails here too.

Two deliberate breaks (wrong wiring default; checksum not checked) each made the suite fail. The first real IDE compile failed on an Arduino quirk the PC build could not see then (auto-generated prototypes above a struct); fixed by moving the struct into `gg_core.h`, and the IDE build test now covers it. The serial-line test found that an over-long line used to run its tail as a command; fixed.

**Not tested:** `WIFI SCAN` on the real board (how long the panel pauses, hidden and duplicate names), mDNS after a router reconnect (a power cycle is tested), Safari, Firefox, Android and iPhone talking to the board, NeoPixel timing with 256 LEDs, serial throughput on the real USB port, Bluetooth.

## Next

**Step 2, Wi-Fi:** firmware, tool and the editor (Network button, Connect over Wi-Fi in the Board card) are done; the editor over Wi-Fi works from Chrome on Windows (tab and installed app), while Safari on an iPhone is untested, and the network scan is PC-tested only. **Step 3, Bluetooth:** the same messages over a BLE service for the Capacitor phone app (Web Bluetooth is absent from iOS Safari, which is why Wi-Fi comes first).
