// Glow Grid player for the ESP32-C3 SuperMini and the 16x16 WS2812B panel.
// Stores several sprites (.gg files) in the board's flash and plays one at a time.
//
//   Next button (GPIO5 to GND): next sprite.   On/off button (GPIO7 to GND): panel off/on.
//   Panel data: GPIO6 to DIN.
//
// Put sprites on the board over USB with ../tools/gg_tool.py (close the Serial Monitor first).
// Wi-Fi comes next and Bluetooth later; both carry the same files and commands.
//
// Arduino IDE setup (open c3/c3_player/c3_player.ino straight from the repo):
//   Board: ESP32C3 Dev Module, USB CDC On Boot: Enabled,
//   Partition Scheme: Default 4MB with spiffs (about 1.5 MB for sprites; LittleFS uses that partition),
//   Library: Adafruit NeoPixel (Library Manager).
// The first start formats the flash storage; that takes a few seconds.
//
// Serial commands at 115200 baud, one per line (gg_tool.py sends these for you):
//   PING                       -> PONG
//   LIST                       -> FILE <name> <bytes> ..., then OK <n> files, <free> bytes free
//   PUT <name> <bytes> <crc32> -> READY, then the file bytes (an "A" line after every 1024 bytes),
//                                 then OK saved <name> or ERR <reason>
//   DEL <name>                 -> OK deleted <name> or ERR <reason>
//   SHOW <name>                -> OK showing <name> or ERR <reason>
//   OFF / ON                   -> OK panel off / OK panel on (same as the On/off button; off is kept across a power cycle)
//   INFO                       -> OK current=<name> ...

#include <Adafruit_NeoPixel.h>
#include <LittleFS.h>
#include "gg_core.h"

#define DATA_PIN 6
#define BTN_NEXT 5
#define BTN_OFF 7
#define MAX_SPRITES 64           // the list lives in RAM; PUT refuses a new name once it is full
#define GG_FW_VERSION 5           // bump on every change pushed to the repo; INFO reports it
#define TMP_PATH "/upload.tmp"

Adafruit_NeoPixel strip(GG_PIXELS, DATA_PIN, NEO_GRB + NEO_KHZ800);

String names[MAX_SPRITES];   // sprite names without the .gg ending, sorted
int nSprites = 0;
int cur = -1;                // index of the sprite being played

uint8_t* data = nullptr;     // the whole current file in RAM
size_t dataLen = 0;
GGHeader hdr;
uint8_t lut[256];
int frameNo = 0;
uint32_t nextFrameAt = 0;
bool panelOn = true;
bool dirty = true;           // a still needs drawing

String pathOf(const String& name) { return "/" + name + ".gg"; }
const char* OFF_MARK = "/panel.off";   // exists while the panel is off, so OFF survives a power cycle (David, 2026-10-15)

// Keeps the off state in flash. Written only when it changes.
void rememberPanel() {
  bool marked = LittleFS.exists(OFF_MARK);
  if (panelOn && marked) LittleFS.remove(OFF_MARK);
  else if (!panelOn && !marked) { File f = LittleFS.open(OFF_MARK, "w"); if (f) f.close(); }
}

void showEmpty() {           // nothing stored: one dim blue pixel at LED 0
  strip.clear();
  strip.setPixelColor(0, 0, 0, 12);
  strip.show();
}

void freeSprite() {
  if (data) { free(data); data = nullptr; }
  dataLen = 0;
}

// Reads sprite number idx from flash into RAM. Returns an error text, or NULL if fine.
const char* loadSprite(int idx) {
  freeSprite();
  File f = LittleFS.open(pathOf(names[idx]), "r");
  if (!f) return "cannot open";
  size_t size = f.size();
  if (size > GG_MAX_FILE) { f.close(); return "file too big"; }
  data = (uint8_t*)malloc(size);
  if (!data) { f.close(); return "out of memory"; }
  size_t got = f.read(data, size);
  f.close();
  if (got != size) { freeSprite(); return "read failed"; }
  const char* err = gg_parse_header(data, size, &hdr);
  if (err) { freeSprite(); return err; }
  dataLen = size;
  gg_make_lut(hdr.bright_pct, hdr.gamma10, lut);
  frameNo = 0;
  nextFrameAt = millis();
  dirty = true;
  return NULL;
}

void scanSprites() {
  String keep = (cur >= 0 && cur < nSprites) ? names[cur] : String("");
  nSprites = 0;
  File root = LittleFS.open("/");
  File f = root.openNextFile();
  while (f && nSprites < MAX_SPRITES) {
    String n = String(f.name());
    int slash = n.lastIndexOf('/');
    if (slash >= 0) n = n.substring(slash + 1);
    if (!f.isDirectory() && n.endsWith(".gg") && n.length() > 3) {
      names[nSprites++] = n.substring(0, n.length() - 3);
    }
    f = root.openNextFile();
  }
  for (int i = 1; i < nSprites; i++) {          // sort by name
    String x = names[i];
    int j = i - 1;
    while (j >= 0 && names[j].compareTo(x) > 0) { names[j + 1] = names[j]; j--; }
    names[j + 1] = x;
  }
  cur = -1;
  for (int i = 0; i < nSprites; i++) if (names[i] == keep) cur = i;
}

bool selectIndex(int idx) {
  if (idx < 0 || idx >= nSprites) return false;
  const char* err = loadSprite(idx);
  if (err) { Serial.printf("ERR %s: %s\n", names[idx].c_str(), err); return false; }
  cur = idx;
  panelOn = true;
  rememberPanel();
  return true;
}

bool selectName(const String& name) {
  for (int i = 0; i < nSprites; i++) if (names[i] == name) return selectIndex(i);
  return false;
}

// Applies the wiring order and the brightness/gamma table, then sends one frame to the panel.
void render(int frame) {
  const uint8_t* px = data + GG_HEADER_SIZE + (size_t)frame * GG_FRAME_BYTES;
  for (int y = 0; y < GG_ROWS; y++) {
    for (int x = 0; x < GG_COLS; x++) {
      const uint8_t* p = px + (y * GG_COLS + x) * 3;
      strip.setPixelColor(gg_led_index(x, y), lut[p[0]], lut[p[1]], lut[p[2]]);
    }
  }
  strip.show();
}

void playTick() {
  if (!panelOn || !data) return;
  if (hdr.frames == 1) {
    if (dirty) { render(0); dirty = false; }
    return;
  }
  uint32_t now = millis();
  if ((int32_t)(now - nextFrameAt) >= 0) {
    render(frameNo);
    frameNo = (frameNo + 1) % hdr.frames;
    nextFrameAt = now + 10000UL / hdr.fps10;
  }
}

// ---- buttons (active low, internal pull-up, 40 ms debounce) ----
// GGButton is defined in gg_core.h: the Arduino IDE puts function prototypes above this
// file, so a struct used in a parameter list must come from an included header.
GGButton btnNext = {BTN_NEXT, true, 0};
GGButton btnOff = {BTN_OFF, true, 0};

bool pressed(GGButton& b) {  // true once per press
  bool now = digitalRead(b.pin);
  if (now != b.last && millis() - b.changed > 40) {
    b.last = now;
    b.changed = millis();
    return !now;
  }
  return false;
}

// Panel off (all LEDs dark, playback paused) or on (resume from frame 0). Same as the On/off button.
// Off is remembered in flash: after a power cycle the panel stays dark until ON, SHOW, PUT or a button.
void setPanel(bool on) {
  panelOn = on;
  rememberPanel();
  if (on) { dirty = true; nextFrameAt = millis(); frameNo = 0; }
  else { strip.clear(); strip.show(); }
}

void handleButtons() {
  if (pressed(btnNext)) {
    if (!panelOn) setPanel(true);
    else if (nSprites > 0) selectIndex((cur + 1) % nSprites);
  }
  if (pressed(btnOff)) setPanel(!panelOn);
}

// ---- serial commands ----
void drainSerial() {
  delay(300);
  while (Serial.available()) Serial.read();
}

void putFail(File& f, const char* why) {
  f.close();
  LittleFS.remove(TMP_PATH);
  drainSerial();
  Serial.printf("ERR %s\n", why);
}

void doPut(const String& name, size_t size, uint32_t crcWant) {
  if (!gg_name_ok(name.c_str())) { Serial.println("ERR bad name (A-Z a-z 0-9 _ - up to 31)"); return; }
  if (size < GG_HEADER_SIZE + GG_FRAME_BYTES || size > GG_MAX_FILE) { Serial.println("ERR bad size"); return; }
  size_t oldSize = 0;
  if (LittleFS.exists(pathOf(name))) { File o = LittleFS.open(pathOf(name), "r"); oldSize = o.size(); o.close(); }
  size_t freeBytes = LittleFS.totalBytes() - LittleFS.usedBytes();
  if (freeBytes + oldSize < size + 8192) { Serial.println("ERR not enough space"); return; }
  if (oldSize == 0 && nSprites >= MAX_SPRITES) { Serial.printf("ERR board holds %d sprites; delete one first\n", MAX_SPRITES); return; }
  File f = LittleFS.open(TMP_PATH, "w");
  if (!f) { Serial.println("ERR cannot create file"); return; }
  Serial.println("READY");

  uint8_t buf[256];
  size_t got = 0, sinceAck = 0;
  uint32_t crc = 0, last = millis();
  while (got < size) {
    int avail = Serial.available();
    if (avail <= 0) {
      if (millis() - last > 4000) { putFail(f, "timeout waiting for data"); return; }
      delay(1);
      continue;
    }
    size_t want = size - got;
    if (want > sizeof(buf)) want = sizeof(buf);
    if (want > (size_t)avail) want = avail;
    size_t r = Serial.readBytes(buf, want);
    if (r == 0) continue;
    if (f.write(buf, r) != r) { putFail(f, "flash write failed"); return; }
    crc = gg_crc32(crc, buf, r);
    got += r;
    sinceAck += r;
    last = millis();
    if (sinceAck >= 1024 && got < size) { Serial.print("A\n"); sinceAck = 0; }
  }
  f.close();
  if (crc != crcWant) { LittleFS.remove(TMP_PATH); Serial.println("ERR checksum mismatch"); return; }

  File chk = LittleFS.open(TMP_PATH, "r");
  uint8_t h[GG_HEADER_SIZE] = {0};
  size_t hr = chk ? chk.read(h, GG_HEADER_SIZE) : 0;
  size_t onDisk = chk ? chk.size() : 0;
  if (chk) chk.close();
  const char* err = (hr == GG_HEADER_SIZE && onDisk == size) ? gg_parse_header(h, size, NULL) : "readback failed";
  if (err) { LittleFS.remove(TMP_PATH); Serial.printf("ERR invalid sprite: %s\n", err); return; }

  String dst = pathOf(name);
  if (!LittleFS.rename(TMP_PATH, dst)) {          // some versions refuse to replace: remove, then rename
    LittleFS.remove(dst);
    if (!LittleFS.rename(TMP_PATH, dst)) { LittleFS.remove(TMP_PATH); Serial.println("ERR rename failed"); return; }
  }
  scanSprites();
  selectName(name);
  Serial.printf("OK saved %s\n", name.c_str());
}

void doCommand(char* line) {
  char cmd[8] = "", a1[48] = "", a2[16] = "", a3[16] = "";
  int n = sscanf(line, "%7s %47s %15s %15s", cmd, a1, a2, a3);
  if (n < 1) return;
  String c = String(cmd);
  c.toUpperCase();
  if (c == "PING") {
    Serial.println("PONG");
  } else if (c == "LIST") {
    for (int i = 0; i < nSprites; i++) {
      File f = LittleFS.open(pathOf(names[i]), "r");
      Serial.printf("FILE %s %u\n", names[i].c_str(), (unsigned)(f ? f.size() : 0));
      if (f) f.close();
    }
    Serial.printf("OK %d files, %u bytes free\n", nSprites, (unsigned)(LittleFS.totalBytes() - LittleFS.usedBytes()));
  } else if (c == "PUT") {
    if (n < 4) { Serial.println("ERR usage: PUT <name> <bytes> <crc32 hex>"); return; }
    doPut(String(a1), (size_t)strtoul(a2, NULL, 10), (uint32_t)strtoul(a3, NULL, 16));
  } else if (c == "DEL") {
    if (n < 2 || !gg_name_ok(a1) || !LittleFS.exists(pathOf(String(a1)))) { Serial.println("ERR no such sprite"); return; }
    bool wasCurrent = (cur >= 0 && names[cur] == String(a1));
    LittleFS.remove(pathOf(String(a1)));
    if (wasCurrent) { freeSprite(); cur = -1; }
    scanSprites();
    if (wasCurrent) { if (nSprites > 0) selectIndex(0); else showEmpty(); }
    Serial.printf("OK deleted %s\n", a1);
  } else if (c == "SHOW") {
    if (n >= 2 && selectName(String(a1))) Serial.printf("OK showing %s\n", a1);
    else Serial.println("ERR no such sprite");
  } else if (c == "OFF") {
    setPanel(false);
    Serial.println("OK panel off");
  } else if (c == "ON") {
    setPanel(true);
    Serial.println(data ? "OK panel on" : "OK panel on (nothing stored)");
  } else if (c == "INFO") {
    Serial.printf("OK fw=%d current=%s sprites=%d panel=%s frames=%d fps10=%d bright_pct=%d gamma10=%d free=%u\n",
                  GG_FW_VERSION, cur >= 0 ? names[cur].c_str() : "-", nSprites, panelOn ? "on" : "off",
                  data ? hdr.frames : 0, data ? hdr.fps10 : 0, data ? hdr.bright_pct : 0, data ? hdr.gamma10 : 0,
                  (unsigned)(LittleFS.totalBytes() - LittleFS.usedBytes()));
  } else {
    Serial.println("ERR unknown command");
  }
}

void handleSerial() {
  static char line[96];
  static size_t len = 0;
  static bool tooLong = false;       // a line that overflowed is ignored up to its newline, tail included
  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      line[len] = 0;
      if (!tooLong) doCommand(line);
      len = 0;
      tooLong = false;
    } else if (tooLong) {
      continue;
    } else if (len < sizeof(line) - 1) {
      line[len++] = ch;
    } else {
      tooLong = true;
    }
  }
}

void setup() {
  Serial.setRxBufferSize(2048);      // must come before begin()
  Serial.begin(115200);
  delay(1200);
  pinMode(BTN_NEXT, INPUT_PULLUP);
  pinMode(BTN_OFF, INPUT_PULLUP);
  strip.begin();
  strip.setBrightness(255);          // brightness comes from each sprite and its table
  strip.clear();
  strip.show();
  if (!LittleFS.begin(true)) {       // true = format on first use
    Serial.println("ERR flash storage failed to start");
    return;
  }
  LittleFS.remove(TMP_PATH);         // an upload cut off by a power loss leaves this behind
  scanSprites();
  Serial.printf("Glow Grid player fw %d ready: %d sprite(s), %u bytes free\n", GG_FW_VERSION, nSprites,
                (unsigned)(LittleFS.totalBytes() - LittleFS.usedBytes()));
  bool wasOff = LittleFS.exists(OFF_MARK);
  if (nSprites > 0) selectIndex(0); else showEmpty();
  if (wasOff) { setPanel(false); Serial.println("panel off (as left)"); }
}

void loop() {
  handleSerial();
  handleButtons();
  playTick();
}
