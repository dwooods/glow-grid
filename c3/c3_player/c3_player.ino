// Glow Grid player for the ESP32-C3 SuperMini and the 16x16 WS2812B panel.
// Stores several sprites (.gg files) in the board's flash and plays one at a time.
//
//   Next button (GPIO5 to GND): next sprite.   On/off button (GPIO7 to GND): a short press switches the panel off/on (on release);
//   holding it for 5 seconds opens the Wi-Fi setup network (firmware 14), also when Wi-Fi is off.
//   Panel data: GPIO6 to DIN.
//
// Put sprites on the board over USB with ../tools/gg_tool.py (close the Serial Monitor first).
// Wi-Fi (firmware 9) is set up over USB (WIFI command below), or without USB through the board's own setup page (firmware 13, see
// "Setup mode"); the same operations are then served over HTTP, see "HTTP API". Bluetooth comes later.
//
// Arduino IDE setup (open c3/c3_player/c3_player.ino straight from the repo):
//   Board: ESP32C3 Dev Module, USB CDC On Boot: Enabled,
//   Partition Scheme: Default 4MB with spiffs (about 1.5 MB for sprites; LittleFS uses that partition),
//   Library: Adafruit NeoPixel (Library Manager).
// The first start formats the flash storage; that takes a few seconds.
//
// Serial commands at 115200 baud, one per line (gg_tool.py sends these for you):
//   PING                       -> PONG
//   LIST                       -> FILE <name> <bytes> [<frames> <fps10> <bright_pct> <gamma10>] ..., then OK <n> files, <free> bytes free
//   PUT <name> <bytes> <crc32> -> READY, then the file bytes (an "A" line after every 1024 bytes),
//                                 then OK saved <name> or ERR <reason>
//   DEL <name>                 -> OK deleted <name> or ERR <reason>
//   SHOW <name>                -> OK showing <name> or ERR <reason>
//   OFF / ON                   -> OK panel off / OK panel on (same as the On/off button; off is kept across a power cycle)
//   ROTATE <seconds>           -> OK rotate <seconds>; 0 = off. Cycles the stored sprites in list order, kept across
//                                 a power cycle; each sprite keeps animating for the whole interval (David, 2026-10-15)
//   SHUFFLE <0|1>              -> OK shuffle <0|1>. With 1, rotation picks a random sprite (never the one already playing)
//                                 instead of the next in list order; kept across a power cycle (fw 16). The Next button stays in list order.
//   BRIGHT <pct>               -> OK bright <pct>. 10..40 plays every sprite at that brightness instead of its own;
//                                 0 = each sprite's own setting again. Kept across a power cycle (fw 19). INFO shows bright=<pct>.
//   SCHED <on> <off>           -> OK schedule <on>-<off>. Daily window in 24-hour HHMM, local time (America/Los_Angeles): the panel switches
//                                 on at <on> and off at <off>; overnight windows (2200 0600) work. SCHED OFF removes it. Needs the board on
//                                 Wi-Fi once per power-up to learn the time (NTP); without a time nothing happens. A manual On/Off holds
//                                 until the next change. Kept across a power cycle (fw 20). INFO shows schedule=<on>-<off>|off clock=<HHMM>|-.
//   CRC <name>                 -> OK crc=<8 hex> size=<bytes> of the stored file, so the editor can tell an unchanged
//                                 example from one you replaced (fw 7); ERR no such sprite
//   GET <name>                 -> D <96 hex digits> lines (48 bytes each) with the stored file, then
//                                 OK crc=<8 hex> size=<bytes>; ERR no such sprite. Lets the editor load a sprite
//                                 back into the grid (fw 8). The panel pauses on its current frame while it runs.
//   INFO                       -> OK fw=<n> current=<name> ... rotate=<seconds> shuffle=<0|1> schedule=<HHMM-HHMM|off> clock=<HHMM|-> wifi=<off|connecting|connected> ip=<address or -> gap_ms=<n>
//                                 (gap_ms: the longest the main loop went without running since the last INFO; fw 9)
//   WIFI SET <ssid hex> <password hex, or -> for none>  -> OK wifi saved; joining. Stored in the chip's NVS, joined at every start (fw 9).
//                                 gg_tool.py hex-encodes for you. 2.4 GHz networks only; the board is then http://glowgrid.local
//   WIFI STATUS                -> OK wifi=<state> ip=<address> rssi=<dBm> host=glowgrid.local ssid=<name>   (never the password)
//   WIFI CLEAR                 -> OK wifi cleared
//   WIFI SETUP                 -> OK setup mode ...: the board leaves its network and opens "GlowGrid-Setup" for 5 minutes (fw 13)
//   WIFI KEY                   -> OK key=<10 characters>: the board's setup key (fw 18). It is the WPA2 password of GlowGrid-Setup and the
//                                 code POST /setup asks for. Made once, at random, on first use; print it on the label.
//   WIFI KEY NEW               -> a new random key (refused while setup mode is open)
//   WIFI SCAN                  -> NET <ssid hex> <rssi dBm> <1 if it needs a password, else 0> lines (strongest first, up to 20, one per name,
//                                 hidden networks left out), then OK networks=<n> (fw 10). Takes 2 to 5 seconds; the animation stalls meanwhile.

#include <Adafruit_NeoPixel.h>
#include <LittleFS.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <DNSServer.h>
#include <Preferences.h>
#include <esp_random.h>
#include <time.h>
#include "gg_core.h"
#include "setup_page.h"
// The editor page for http://glowgrid.local/ comes from tools/build_site.py (git-ignored output). Without it the sketch still builds.
#if !defined(GG_NO_SITE) && __has_include("site_data.h")
#include "site_data.h"
#define GG_HAS_SITE 1
#endif

#define DATA_PIN 6
#define BTN_NEXT 5
#define BTN_OFF 7
#define MAX_SPRITES 96           // the list lives in RAM; PUT refuses a new name once it is full (64 until fw 19; 37 examples ship)
#define GG_FW_VERSION 20          // bump on every change pushed to the repo; INFO reports it
#define TMP_PATH "/upload.tmp"
#define SETUP_SSID "GlowGrid-Setup"            // the network the board hosts in setup mode (WPA2; the password is the setup key, fw 18)
#define SETUP_KEY_LEN 10
#define SETUP_TIMEOUT_MS 300000UL              // setup mode ends by itself after 5 minutes
#define JOIN_WAIT_SAVE_MS 30000UL              // after new credentials are saved, this long before setup mode opens again
#define SETUP_SAVE_CLOSE_MS 8000UL             // after Save the setup network stays up this long, so the page can show its countdown and the phone is not dropped mid-reply
#define SETUP_HOLD_MS 5000UL                   // holding the On/off button this long opens setup mode
// Whether setup mode may open by itself (no saved network at power-up, or a network just saved from the setup page did not join). Since
// fw 18 a saved network that merely fails to join after a power-up (router still starting) no longer opens it: that would drop the board
// off the network for 5 minutes after every power cut. The PC test stub overrides this so that only the tests that ask for it see it; on
// the board it is always on. Asking for setup (POST /setup with the key, WIFI SETUP, the button hold) always works.
#ifndef GG_SETUP_AUTO_START
#define GG_SETUP_AUTO_START() true
#endif

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
bool setupOn = false;        // setup mode is running: the board hosts GlowGrid-Setup and a slow blue pulse shows on LED 0
bool dirty = true;           // a still needs drawing
uint32_t rotateSec = 0;      // 0 = stay on one sprite; else move to the next one every rotateSec seconds
uint32_t rotateAt = 0;       // millis() at which the next sprite is due
bool shuffleOn = false;      // rotation picks a random sprite instead of the next in list order
#define ROTATE_MAX 86400UL

String pathOf(const String& name) { return "/" + name + ".gg"; }
const char* OFF_MARK = "/panel.off";   // exists while the panel is off, so OFF survives a power cycle (David, 2026-10-15)
const char* ROTATE_PATH = "/rotate.txt"; // the rotate interval in seconds, absent or 0 = off
const char* SHUFFLE_MARK = "/shuffle.txt"; // exists while rotation is random
const char* BRIGHT_PATH = "/bright.txt";   // board-wide brightness in percent (10..40); absent or 0 = each sprite's own
uint8_t brightPct = 0;                     // 0 = use the sprite's own bright_pct
#define GG_TZ "PST8PDT,M3.2.0,M11.1.0"     // America/Los_Angeles with daylight saving (David, 2026-10-18)
#ifndef GG_HAVE_STUB_TIME
static inline time_t gg_epoch() { return time(nullptr); }   // the PC test build supplies its own clock
#endif
const char* SCHED_PATH = "/sched.txt";     // "HHMM HHMM": switch on, switch off
bool schedSet = false;                     // a daily schedule is set
uint16_t schedFrom = 0, schedTo = 0;       // minutes after midnight
int8_t schedSeen = -1;                     // -1 not applied yet, 0 outside the window last second, 1 inside
bool ntpStarted = false;
#define BRIGHT_MIN 10
#define BRIGHT_MAX 40
String wifiSsid, wifiPass;   // from NVS (not the sprite flash); empty ssid = Wi-Fi not set up
uint32_t gapMaxMs = 0;       // longest main-loop gap since the last INFO

void rotateReset() { rotateAt = millis() + rotateSec * 1000UL; }
void saveRotate() {
  if (rotateSec == 0) { LittleFS.remove(ROTATE_PATH); return; }
  File f = LittleFS.open(ROTATE_PATH, "w");
  if (f) { f.print(rotateSec); f.close(); }
}
void loadRotate() {
  rotateSec = 0;
  File f = LittleFS.open(ROTATE_PATH, "r");
  if (!f) return;
  rotateSec = (uint32_t)f.parseInt();
  f.close();
  if (rotateSec > ROTATE_MAX) rotateSec = 0;
  rotateReset();
}
void saveShuffle() {
  if (!shuffleOn) { LittleFS.remove(SHUFFLE_MARK); return; }
  File f = LittleFS.open(SHUFFLE_MARK, "w");
  if (f) { f.print((uint32_t)1); f.close(); }
}
void loadShuffle() { shuffleOn = LittleFS.exists(SHUFFLE_MARK); }
void saveBright() {
  if (brightPct == 0) { LittleFS.remove(BRIGHT_PATH); return; }
  File f = LittleFS.open(BRIGHT_PATH, "w");
  if (f) { f.print((uint32_t)brightPct); f.close(); }
}
void loadBright() {
  brightPct = 0;
  File f = LittleFS.open(BRIGHT_PATH, "r");
  if (!f) return;
  long v = f.parseInt();
  f.close();
  if (v >= BRIGHT_MIN && v <= BRIGHT_MAX) brightPct = (uint8_t)v;
}
uint8_t playBright() { return brightPct ? brightPct : hdr.bright_pct; }

// ---- daily schedule (fw 20) ----
String sfmt(const char* f, ...);
bool timeValid() { return (long)gg_epoch() > 1700000000L; }           // false until NTP has set the clock
bool localMinutes(int& mins) {
  if (!timeValid()) return false;
  time_t e = gg_epoch();
  struct tm t;
  localtime_r(&e, &t);
  mins = t.tm_hour * 60 + t.tm_min;
  return true;
}
bool inWindow(int m) { return schedFrom < schedTo ? (m >= schedFrom && m < schedTo) : (m >= schedFrom || m < schedTo); }
void saveSched() {
  if (!schedSet) { LittleFS.remove(SCHED_PATH); return; }
  File f = LittleFS.open(SCHED_PATH, "w");
  if (f) { f.print(sfmt("%02u%02u %02u%02u", schedFrom / 60, schedFrom % 60, schedTo / 60, schedTo % 60).c_str()); f.close(); }
}
void loadSched() {
  schedSet = false;
  File f = LittleFS.open(SCHED_PATH, "r");
  if (!f) return;
  long a = f.parseInt(), b = f.parseInt();
  f.close();
  if (a < 0 || b < 0 || a / 100 > 23 || a % 100 > 59 || b / 100 > 23 || b % 100 > 59 || a == b) return;
  schedFrom = (uint16_t)(a / 100 * 60 + a % 100);
  schedTo = (uint16_t)(b / 100 * 60 + b % 100);
  schedSet = true;
}
String schedText() {
  if (!schedSet) return String("off");
  return sfmt("%02u%02u-%02u%02u", schedFrom / 60, schedFrom % 60, schedTo / 60, schedTo % 60);
}
String clockText() {
  int m;
  if (!localMinutes(m)) return String("-");
  return sfmt("%02d%02d", m / 60, m % 60);
}

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
  gg_make_lut(playBright(), hdr.gamma10, lut);
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
  rotateReset();                     // a new sprite gets a full interval
  return true;
}

bool selectName(const String& name) {
  for (int i = 0; i < nSprites; i++) if (names[i] == name) return selectIndex(i);
  return false;
}

// The setup-mode signal: LED 0 pulses dim blue (about 2 s a cycle), drawn over whatever the panel shows.
uint8_t setupPulse() {
  uint32_t t = millis() % 2000UL;
  uint32_t up = t < 1000 ? t : 2000 - t;
  return (uint8_t)(3 + up * 40 / 1000);
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
  if (setupOn) strip.setPixelColor(0, 0, 0, setupPulse());
  strip.show();
}

// The sprite rotation moves to next: the following one in list order, or (shuffle) a random one other than the current.
int rotateNext() {
  if (!shuffleOn || nSprites < 3) return (cur + 1) % nSprites;   // with two sprites the only other one is also the next one
  int r = (int)random(nSprites - 1);                              // 0..n-2, skipping over the current index
  return r >= cur ? r + 1 : r;
}

void rotateTick() {
  if (!rotateSec || !panelOn || nSprites < 2) return;
  if ((int32_t)(millis() - rotateAt) >= 0) selectIndex(rotateNext());
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
  if (on) { dirty = true; nextFrameAt = millis(); frameNo = 0; rotateReset(); }
  else { strip.clear(); strip.show(); }
}

String opSetup();                              // defined with the setup code below

// On/off: a short press switches the panel on release; holding it SETUP_HOLD_MS opens the setup network instead (and the release then
// does nothing). Held while powering up counts too. Reuses the WIFI SETUP / POST /setup path, so it works with Wi-Fi off.
void handleOffButton() {
  static bool down = false, fired = false;
  static uint32_t downAt = 0;
  bool wasUp = btnOff.last;
  pressed(btnOff);                               // updates btnOff.last after the 40 ms debounce
  bool isUp = btnOff.last;
  uint32_t now = millis();
  if (wasUp && !isUp) { down = true; fired = false; downAt = now; }
  else if (down && !isUp && !fired && now - downAt >= SETUP_HOLD_MS) { fired = true; opSetup(); }
  else if (down && isUp) { down = false; if (!fired) setPanel(!panelOn); }
}

void handleButtons() {
  if (pressed(btnNext)) {
    if (!panelOn) setPanel(true);
    else if (nSprites > 0) selectIndex((cur + 1) % nSprites);
  }
  handleOffButton();
}

// ---- commands shared by USB and Wi-Fi ----
// Each returns the reply line(s) as text ("OK ..." or "ERR ..."); USB prints it, HTTP sends it. Nothing here touches Serial.
String sfmt(const char* f, ...) {
  char b[320];
  va_list ap;
  va_start(ap, f);
  vsnprintf(b, sizeof b, f, ap);
  va_end(ap);
  return String(b);
}

uint32_t freeBytes() { return (uint32_t)(LittleFS.totalBytes() - LittleFS.usedBytes()); }

String wifiState() {
  if (setupOn) return String("setup");
  if (wifiSsid.length() == 0) return String("off");
  return String(WiFi.status() == WL_CONNECTED ? "connected" : "connecting");
}

String listText() {
  String out;
  for (int i = 0; i < nSprites; i++) {
    File f = LittleFS.open(pathOf(names[i]), "r");
    size_t sz = f ? f.size() : 0;
    uint8_t hb[GG_HEADER_SIZE];
    GGHeader lh;
    // fw 17: a valid sprite adds "frames fps10 bright_pct gamma10" after the size (an editor that does not know them ignores them)
    bool ok = f && f.read(hb, GG_HEADER_SIZE) == GG_HEADER_SIZE && gg_parse_header(hb, sz, &lh) == NULL;
    if (ok) out += sfmt("FILE %s %u %u %u %u %u\n", names[i].c_str(), (unsigned)sz, (unsigned)lh.frames, (unsigned)lh.fps10, (unsigned)lh.bright_pct, (unsigned)lh.gamma10);
    else out += sfmt("FILE %s %u\n", names[i].c_str(), (unsigned)sz);
    if (f) f.close();
  }
  out += sfmt("OK %d files, %u bytes free", nSprites, (unsigned)freeBytes());
  return out;
}

String infoText() {
  uint32_t gap = gapMaxMs;
  gapMaxMs = 0;                      // gap_ms = the longest the main loop went without running since the last INFO
  String ip = (wifiSsid.length() && WiFi.status() == WL_CONNECTED) ? WiFi.localIP().toString() : String("-");
  return sfmt("OK fw=%d current=%s sprites=%d panel=%s frames=%d fps10=%d bright_pct=%d gamma10=%d free=%u rotate=%lu shuffle=%d bright=%d schedule=%s clock=%s wifi=%s ip=%s gap_ms=%lu",
              GG_FW_VERSION, cur >= 0 ? names[cur].c_str() : "-", nSprites, panelOn ? "on" : "off",
              data ? hdr.frames : 0, data ? hdr.fps10 : 0, data ? hdr.bright_pct : 0, data ? hdr.gamma10 : 0,
              (unsigned)freeBytes(), (unsigned long)rotateSec, shuffleOn ? 1 : 0, (int)brightPct, schedText().c_str(), clockText().c_str(), wifiState().c_str(), ip.c_str(), (unsigned long)gap);
}

String opShow(const String& name) {
  if (selectName(name)) return "OK showing " + name;
  return String("ERR no such sprite");
}

String opDel(const String& name) {
  if (!gg_name_ok(name.c_str()) || !LittleFS.exists(pathOf(name))) return String("ERR no such sprite");
  bool wasCurrent = (cur >= 0 && names[cur] == name);
  LittleFS.remove(pathOf(name));
  if (wasCurrent) { freeSprite(); cur = -1; }
  scanSprites();
  if (wasCurrent) { if (nSprites > 0) selectIndex(0); else showEmpty(); }
  return "OK deleted " + name;
}

String opPower(bool on) {
  setPanel(on);
  if (!on) return String("OK panel off");
  return String(data ? "OK panel on" : "OK panel on (nothing stored)");
}

String opRotate(const char* arg) {
  char* end = NULL;
  long v = (arg && *arg) ? strtol(arg, &end, 10) : -1;
  if (!arg || !*arg || *end != 0 || v < 0 || v > (long)ROTATE_MAX) return sfmt("ERR usage: ROTATE <seconds 0..%lu> (0 = off)", ROTATE_MAX);
  rotateSec = (uint32_t)v;
  saveRotate();
  rotateReset();
  return sfmt("OK rotate %lu", (unsigned long)rotateSec);
}

String opShuffle(const char* arg) {
  if (!arg || (strcmp(arg, "0") != 0 && strcmp(arg, "1") != 0)) return String("ERR usage: SHUFFLE <0|1> (1 = random order)");
  shuffleOn = arg[0] == '1';
  saveShuffle();
  return sfmt("OK shuffle %d", shuffleOn ? 1 : 0);
}

String opBright(const char* arg) {
  char* end = NULL;
  long v = (arg && *arg) ? strtol(arg, &end, 10) : -1;
  if (!arg || !*arg || *end != 0 || v < 0 || (v != 0 && (v < BRIGHT_MIN || v > BRIGHT_MAX)))
    return sfmt("ERR usage: BRIGHT <0|%d..%d> (percent; 0 = each sprite's own)", BRIGHT_MIN, BRIGHT_MAX);
  brightPct = (uint8_t)v;
  saveBright();
  if (data) { gg_make_lut(playBright(), hdr.gamma10, lut); dirty = true; }   // the playing sprite changes at once
  return sfmt("OK bright %d", (int)brightPct);
}

bool parseHhmm(const char* s, uint16_t& mins) {
  if (!s || strlen(s) != 4) return false;
  for (int i = 0; i < 4; i++) if (s[i] < '0' || s[i] > '9') return false;
  int h = (s[0] - '0') * 10 + (s[1] - '0'), m = (s[2] - '0') * 10 + (s[3] - '0');
  if (h > 23 || m > 59) return false;
  mins = (uint16_t)(h * 60 + m);
  return true;
}

String opSched(const char* on, const char* off) {
  if (on && strcasecmp(on, "OFF") == 0) { schedSet = false; saveSched(); return String("OK schedule off"); }
  uint16_t a, b;
  if (!parseHhmm(on, a) || !parseHhmm(off, b) || a == b) return String("ERR usage: SCHED <on HHMM> <off HHMM> (24-hour, different times) or SCHED OFF");
  schedFrom = a; schedTo = b; schedSet = true;
  saveSched();
  schedSeen = -1;                        // apply the window at once if the time is known
  return "OK schedule " + schedText();
}

String opCrc(const String& name) {
  File f = gg_name_ok(name.c_str()) ? LittleFS.open(pathOf(name), "r") : File();
  if (!f) return String("ERR no such sprite");
  uint8_t buf[256];
  uint32_t crc = 0;
  size_t total = 0, r;
  while ((r = f.read(buf, sizeof(buf))) > 0) { crc = gg_crc32(crc, buf, r); total += r; }
  f.close();
  return sfmt("OK crc=%08x size=%u", (unsigned)crc, (unsigned)total);
}

// The checks before a new file is accepted (USB and Wi-Fi alike). NULL = fine, else the error text.
const char* putPrecheck(const String& name, size_t size) {
  static char msg[64];
  if (!gg_name_ok(name.c_str())) return "bad name (A-Z a-z 0-9 _ - up to 31)";
  if (size < GG_HEADER_SIZE + GG_FRAME_BYTES || size > GG_MAX_FILE) return "bad size";
  size_t oldSize = 0;
  if (LittleFS.exists(pathOf(name))) { File o = LittleFS.open(pathOf(name), "r"); oldSize = o.size(); o.close(); }
  if ((size_t)freeBytes() + oldSize < size + 8192) return "not enough space";
  if (oldSize == 0 && nSprites >= MAX_SPRITES) { snprintf(msg, sizeof msg, "board holds %d sprites; delete one first", MAX_SPRITES); return msg; }
  return NULL;
}

// The last step of every upload: the bytes are in TMP_PATH and their checksum matched. Checks the file as a sprite, moves it
// into place, rescans and plays it. NULL = saved, else the error text. On an error TMP_PATH is gone.
const char* putCommit(const String& name, size_t size) {
  static char msg[64];
  File chk = LittleFS.open(TMP_PATH, "r");
  uint8_t h[GG_HEADER_SIZE] = {0};
  size_t hr = chk ? chk.read(h, GG_HEADER_SIZE) : 0;
  size_t onDisk = chk ? chk.size() : 0;
  if (chk) chk.close();
  const char* err = (hr == GG_HEADER_SIZE && onDisk == size) ? gg_parse_header(h, size, NULL) : "readback failed";
  if (err) { LittleFS.remove(TMP_PATH); snprintf(msg, sizeof msg, "invalid sprite: %s", err); return msg; }
  String dst = pathOf(name);
  if (!LittleFS.rename(TMP_PATH, dst)) {          // some versions refuse to replace: remove, then rename
    LittleFS.remove(dst);
    if (!LittleFS.rename(TMP_PATH, dst)) { LittleFS.remove(TMP_PATH); return "rename failed"; }
  }
  scanSprites();
  selectName(name);
  return NULL;
}

// ---- Wi-Fi (firmware 9): credentials in NVS, set over USB; the board then serves the HTTP API below ----
// No password on the API for now (David, 2026-10-15): anyone on the home network can list, send and delete sprites. Add a token before
// this goes beyond a home network. What fw 18 adds (security review, 2026-10-17): a web page on another site cannot drive the board
// (Origin and Host are checked on every route, see httpGuard) and the one route that opens a network, POST /setup, needs the setup key.
#define HOSTNAME "glowgrid"
WebServer server(80);
Preferences prefs;
bool serverUp = false, mdnsUp = false, wifiWasUp = false;
// Setup mode state (see "Setup mode" below).
WebServer setupServer(80);
DNSServer dnsServer;
uint32_t setupAt = 0;                          // when setup mode started
bool setupRequested = false; uint32_t setupReqAt = 0;     // POST /setup or WIFI SETUP: starts a moment after the reply went out
bool setupSavePending = false; uint32_t setupSaveAt = 0;  // credentials saved from the page: join a moment after the reply went out
bool joinWatch = false; uint32_t joinWatchAt = 0, joinWatchMs = 0;   // a network just saved is joining; if it does not, setup opens again
String setupScanText;                          // the last scan, served to the setup page without scanning again
String setupKey;                               // the WPA2 password of GlowGrid-Setup and the code POST /setup needs; NVS key "key"
uint8_t keyFails = 0; uint32_t keyLockUntil = 0;   // wrong keys in a row; after 5 the check is locked for a minute

void wifiBegin() {
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(HOSTNAME);
  WiFi.setAutoReconnect(true);
  WiFi.setTxPower(WIFI_POWER_8_5dBm);          // the usual fix for the weak-Wi-Fi SuperMini batches (the probe ran fine at this setting)
  WiFi.begin(wifiSsid.c_str(), wifiPass.length() ? wifiPass.c_str() : NULL);
}

void wifiLoad() {
  prefs.begin("gg", true);
  wifiSsid = prefs.getString("ssid", "");
  wifiPass = prefs.getString("pass", "");
  prefs.end();
  if (wifiSsid.length()) wifiBegin();            // joins in the background; WiFi.setAutoReconnect keeps trying (no setup mode for this, fw 18)
}

// ---- Setup key (firmware 18) ----
// 10 characters from a 32-symbol alphabet (no l, o, 0, 1; lower case so a phone keyboard types it as printed): 50 bits, made once from the
// hardware random number generator and kept in NVS. It is the WPA2 password of GlowGrid-Setup, and POST /setup (the editor's "Change the
// board's Wi-Fi") must send it. Read it over USB with WIFI KEY and print it on the board's label. It is created on first use, not at
// boot, so the radio is already on (the generator is only fully random while it runs).
void keyMake() {
  static const char ALPHA[] = "abcdefghijkmnpqrstuvwxyz23456789";
  bool wasOff = (WiFi.getMode() == WIFI_OFF);
  if (wasOff) WiFi.mode(WIFI_STA);
  char k[SETUP_KEY_LEN + 1];
  for (int i = 0; i < SETUP_KEY_LEN; i++) k[i] = ALPHA[esp_random() & 31];
  k[SETUP_KEY_LEN] = 0;
  if (wasOff) WiFi.mode(WIFI_OFF);
  setupKey = String(k);
  prefs.begin("gg", false);
  prefs.putString("key", k);
  prefs.end();
}

const String& keyGet() {
  if (setupKey.length() != SETUP_KEY_LEN) {
    prefs.begin("gg", true);
    setupKey = prefs.getString("key", "");
    prefs.end();
    if (setupKey.length() != SETUP_KEY_LEN) keyMake();
  }
  return setupKey;
}

// Compares what was typed with the key (case, spaces and dashes ignored, same time for every wrong guess). "" = right, else the ERR text.
String keyCheck(const String& typed) {
  uint32_t now = millis();
  if (keyLockUntil && (int32_t)(keyLockUntil - now) > 0) return String("ERR too many wrong setup keys; wait a minute");
  const char* key = keyGet().c_str();
  char t[SETUP_KEY_LEN + 1];
  size_t n = 0;
  bool good = true;
  for (const char* s = typed.c_str(); *s; s++) {
    char c = *s;
    if (c == ' ' || c == '-') continue;
    if (c >= 'A' && c <= 'Z') c = (char)(c - 'A' + 'a');
    if (n >= SETUP_KEY_LEN) { good = false; break; }
    t[n++] = c;
  }
  if (n != SETUP_KEY_LEN) good = false;
  uint8_t diff = 0;
  for (size_t i = 0; i < SETUP_KEY_LEN; i++) diff |= (uint8_t)((i < n ? t[i] : 0) ^ key[i]);
  if (good && diff == 0) { keyFails = 0; return String(""); }
  if (++keyFails >= 5) { keyFails = 0; keyLockUntil = now + 60000UL; if (keyLockUntil == 0) keyLockUntil = 1; }
  return String("ERR wrong setup key");
}

void wifiStop() {
  if (mdnsUp) { MDNS.end(); mdnsUp = false; }
  WiFi.disconnect(true);
  wifiWasUp = false;
}

// WIFI SCAN: the networks the board can hear. Names come back as hex, like WIFI SET takes them.
String wifiScanText() {
  if (WiFi.getMode() == WIFI_OFF) WiFi.mode(WIFI_STA);
  int found = WiFi.scanNetworks();
  const int MAXN = 20;
  String names[MAXN];
  int rssi[MAXN], sec[MAXN], n = 0;
  for (int i = 0; i < found; i++) {
    String name = WiFi.SSID(i);
    if (name.length() == 0 || name.length() > 32) continue;       // hidden (or not a legal name)
    int r = WiFi.RSSI(i), s = WiFi.encryptionType(i) != WIFI_AUTH_OPEN ? 1 : 0, at = -1;
    for (int j = 0; j < n; j++) if (names[j] == name) { at = j; break; }
    if (at >= 0) { if (r > rssi[at]) { rssi[at] = r; sec[at] = s; } continue; }   // several access points, one name: keep the strongest
    if (n < MAXN) { names[n] = name; rssi[n] = r; sec[n] = s; n++; }
  }
  WiFi.scanDelete();
  for (int a = 1; a < n; a++)                                      // insertion sort, strongest first
    for (int b = a; b > 0 && rssi[b] > rssi[b - 1]; b--) { String t = names[b]; names[b] = names[b - 1]; names[b - 1] = t; int x = rssi[b]; rssi[b] = rssi[b - 1]; rssi[b - 1] = x; x = sec[b]; sec[b] = sec[b - 1]; sec[b - 1] = x; }
  String out;
  for (int i = 0; i < n; i++) {
    out += "NET ";
    const char* cs = names[i].c_str();
    for (size_t k = 0; k < names[i].length(); k++) out += sfmt("%02x", (unsigned)(uint8_t)cs[k]);
    out += sfmt(" %d %d\n", rssi[i], sec[i]);
  }
  out += sfmt("OK networks=%d", n);
  return out;
}

// Checks a network name and password (both as hex; the password "-" or empty = an open network) and stores them in NVS and RAM.
// Returns "" when stored, else the ERR text. It does not join: the caller decides when.
String wifiStore(const char* h1, const char* h2) {
  char ssid[40], pass[72];
  int sl = gg_hex_decode(h1, ssid, sizeof ssid);
  if (sl < 1 || sl > 32) return String("ERR usage: WIFI SET <ssid as hex, 1 to 32 bytes> <password as hex or ->");
  int pl = 0;
  pass[0] = 0;
  if (h2 && h2[0] && strcmp(h2, "-") != 0) pl = gg_hex_decode(h2, pass, sizeof pass);
  if (pl < 0 || pl > 63 || (pl > 0 && pl < 8)) return String("ERR password must be 8 to 63 characters (or - for an open network)");
  prefs.begin("gg", false);
  prefs.putString("ssid", ssid);
  prefs.putString("pass", pass);
  prefs.end();
  wifiSsid = String(ssid);
  wifiPass = String(pass);
  return String("");
}

// Leave the current network (if any) and join the stored one; if it has not joined after watchMs, setup mode opens by itself.
void wifiJoinNow(uint32_t watchMs) {
  wifiStop();
  wifiBegin();
  joinWatch = true; joinWatchAt = millis(); joinWatchMs = watchMs;
}

void setupFinish();                            // defined with the setup code below
String opSetup();

// WIFI SET <ssid hex> <password hex, or - for an open network> | WIFI STATUS | WIFI CLEAR | WIFI SETUP.
// Hex because a name or password can hold spaces and anything else; gg_tool.py does the encoding. The password is never printed.
String opWifi(const char* rest) {
  char sub[8] = "", h1[66] = "", h2[130] = "";
  int n = sscanf(rest, "%7s %65s %129s", sub, h1, h2);
  String s = String(sub);
  s.toUpperCase();
  if (n >= 1 && s == "STATUS") {
    String ip = (wifiSsid.length() && WiFi.status() == WL_CONNECTED) ? WiFi.localIP().toString() : String("-");
    int rssi = (wifiSsid.length() && WiFi.status() == WL_CONNECTED) ? WiFi.RSSI() : 0;
    return sfmt("OK wifi=%s ip=%s rssi=%d host=" HOSTNAME ".local ssid=%s", wifiState().c_str(), ip.c_str(), rssi, wifiSsid.c_str());
  }
  if (n >= 1 && s == "SCAN") return wifiScanText();
  if (n >= 1 && s == "CLEAR") {
    prefs.begin("gg", false);
    prefs.remove("ssid");
    prefs.remove("pass");
    prefs.end();
    wifiSsid = "";
    wifiPass = "";
    wifiStop();
    return String("OK wifi cleared");
  }
  if (n >= 1 && s == "SETUP") return opSetup();
  if (n >= 1 && s == "KEY") {
    String a = String(n >= 2 ? h1 : "");
    a.toUpperCase();
    if (n >= 2) {
      if (a != "NEW") return String("ERR usage: WIFI KEY | WIFI KEY NEW");
      if (setupOn) return String("ERR close setup mode first: it is using the current key");
      keyMake();
    }
    return sfmt("OK key=%s", keyGet().c_str());
  }
  if (n >= 2 && s == "SET") {
    String e = wifiStore(h1, n >= 3 ? h2 : "");
    if (e.length()) return e;
    if (setupOn) { setupFinish(); return String("OK wifi saved; setup mode closed, joining. Check with WIFI STATUS (2.4 GHz networks only)"); }
    wifiJoinNow(JOIN_WAIT_SAVE_MS);
    return String("OK wifi saved; joining. Check with WIFI STATUS (2.4 GHz networks only)");
  }
  return String("ERR usage: WIFI STATUS | WIFI SCAN | WIFI SET <ssid hex> <password hex or -> | WIFI CLEAR | WIFI SETUP | WIFI KEY [NEW]");
}

// ---- HTTP API ----
//   GET  /ping /info /list            same text as PING, INFO, LIST
//   GET  /crc?name=X   GET /get?name=X (the file's bytes)
//   POST /show?name=X  /del?name=X  /off  /on  /rotate?s=N  /shuffle?on=0|1  /bright?pct=N  /sched?v=HHMM-HHMM|off
//   POST /setup                       leave this network and open setup mode (fw 13)
//   POST /put?name=X[&crc=hex]        the file as multipart/form-data (field "file"): binary-safe, and a plain "simple" request,
//                                      so a browser sends no pre-flight. Raw POST bodies do not work: the ESP32 core cuts them at the first zero byte.
//   POST /setup?key=K                 the key is the board's setup key (fw 18)
// Replies are the same "OK ..." / "ERR ..." text as USB. A reply to a browser page carries CORS headers for that page's own origin, and the
// pre-flight a browser sends before a request from the https editor page to a private address is answered (Access-Control-Allow-Private-Network).
//
// Who may call (fw 18; before this every page on the internet could, with CORS "*" and a multipart POST that needs no pre-flight):
//   * Host must be this board's name (glowgrid.local, glowgrid) or an IP address: a name an attacker controls that was re-pointed at the
//     board (DNS rebinding) arrives with its own name in Host and is refused.
//   * Origin, when a browser sends one, must be the hosted editor, this board's own page, or the developer's localhost. curl, gg_tool.py
//     and a same-origin GET send none and pass. Checked before any POST does anything, so a cross-site form cannot delete or upload.
bool httpHostOk() {
  String h = server.header("Host");
  if (h.length() == 0) return true;
  const char* p = h.c_str();
  size_t n = strcspn(p, ":");                    // the name without a port
  char name[40];
  if (n == 0 || n >= sizeof name) return false;
  bool numeric = true;
  for (size_t i = 0; i < n; i++) {
    char c = p[i];
    if (c >= 'A' && c <= 'Z') c = (char)(c + 32);
    name[i] = c;
    if (!((c >= '0' && c <= '9') || c == '.')) numeric = false;
  }
  name[n] = 0;
  return numeric || strcmp(name, HOSTNAME ".local") == 0 || strcmp(name, HOSTNAME) == 0;
}

bool httpOriginOk(const String& o) {
  if (o.length() == 0) return true;
  const char* s = o.c_str();
  if (strcmp(s, "https://dwooods.github.io") == 0) return true;      // the hosted editor (and the installed app)
  if (strncmp(s, "http://", 7) != 0) return false;                   // also "null" (file:// pages, sandboxed frames)
  s += 7;
  size_t n = strcspn(s, ":");
  if (n == 9 && (strncmp(s, "localhost", 9) == 0 || strncmp(s, "127.0.0.1", 9) == 0)) return true;   // a developer's own server
  return strcmp(s, server.header("Host").c_str()) == 0;              // this board's own page (Host was checked first)
}

bool httpGuard() {
  if (httpHostOk() && httpOriginOk(server.header("Origin"))) return true;
  server.send(403, "text/plain", "ERR not allowed from this page or address\n");
  return false;
}

void httpCors() {
  String o = server.header("Origin");            // only an origin httpGuard() let through gets here
  if (o.length()) {
    server.sendHeader("Access-Control-Allow-Origin", o);
    server.sendHeader("Vary", "Origin");
    server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    server.sendHeader("Access-Control-Allow-Headers", "*");
    server.sendHeader("Access-Control-Allow-Private-Network", "true");
    server.sendHeader("Access-Control-Max-Age", "600");
  }
  server.sendHeader("Cache-Control", "no-store");
}

void httpReply(const String& msg) {
  int code = 200;
  if (msg.startsWith("ERR")) code = (msg.indexOf("no such") >= 0) ? 404 : (msg.indexOf("setup key") >= 0) ? 403 : 400;
  httpCors();
  server.send(code, "text/plain", msg + "\n");
}

void httpGetFile() {
  if (!httpGuard()) return;
  String name = server.arg("name");
  File f = gg_name_ok(name.c_str()) ? LittleFS.open(pathOf(name), "r") : File();
  if (!f) { httpReply("ERR no such sprite"); return; }
  httpCors();
  server.streamFile(f, "application/octet-stream");
  f.close();
}

File putFile;
String putName, putErr;
size_t putGot = 0;
uint32_t putCrc = 0;
bool putSeen = false;

void httpPutData() {
  HTTPUpload& up = server.upload();
  if (up.status == UPLOAD_FILE_START) {
    putSeen = true;
    putErr = "";
    putGot = 0;
    putCrc = 0;
    putName = server.arg("name");
    if (!(httpHostOk() && httpOriginOk(server.header("Origin")))) { putErr = "not allowed from this page or address"; return; }   // before any byte is written
    size_t want = (size_t)strtoul(server.arg("size").c_str(), NULL, 10);   // optional: lets the space check run before any byte is written
    const char* e = putPrecheck(putName, want ? want : (size_t)GG_MAX_FILE);   // no size given: room for the biggest sprite, so a full flash is caught here
    if (e) { putErr = e; return; }
    putFile = LittleFS.open(TMP_PATH, "w");
    if (!putFile) putErr = "cannot create file";
  } else if (up.status == UPLOAD_FILE_WRITE) {
    if (putErr.length()) return;
    if (putGot + up.currentSize > GG_MAX_FILE) { putErr = "bad size"; putFile.close(); return; }
    if (putFile.write(up.buf, up.currentSize) != up.currentSize) { putErr = "flash write failed"; putFile.close(); return; }
    putCrc = gg_crc32(putCrc, up.buf, up.currentSize);
    putGot += up.currentSize;
  } else {                                      // END or ABORTED
    putFile.close();
    if (up.status == UPLOAD_FILE_ABORTED) { putErr = "upload aborted"; }
  }
}

void httpPutDone() {
  if (!httpGuard()) { LittleFS.remove(TMP_PATH); putSeen = false; putErr = ""; return; }
  String msg;
  if (!putSeen) {
    msg = "ERR send the sprite as multipart/form-data with the file in a field named file";
  } else if (putErr.length()) {
    LittleFS.remove(TMP_PATH);
    msg = "ERR " + putErr;
  } else {
    String c = server.arg("crc");
    if (c.length() && (uint32_t)strtoul(c.c_str(), NULL, 16) != putCrc) {
      LittleFS.remove(TMP_PATH);
      msg = "ERR checksum mismatch";
    } else {
      const char* err = putCommit(putName, putGot);
      msg = err ? "ERR " + String(err) : "OK saved " + putName;
    }
  }
  putSeen = false;
  putErr = "";
  httpReply(msg);
}

void httpNotFound() {
  if (!httpGuard()) return;
  httpCors();
  if (server.method() == HTTP_OPTIONS) { server.send(204); return; }   // the browser's pre-flight for the private-network and POST requests
  server.send(404, "text/plain", "ERR not found\n");
}

// The editor itself, so a phone can load it from the board over plain http (iPhone Safari will not let the https site call this board).
// The page is gzip stored as base64; it is decoded 1024 characters at a time into a small buffer and sent with its exact length.
#ifndef GG_HAS_SITE
void httpSite() {
  if (!httpGuard()) return;
  server.send(404, "text/plain", "The editor is not built into this firmware. Run c3/tools/build_site.py, then flash c3_player.ino again.");
}
#else
void httpSite() {
  if (!httpGuard()) return;
  server.sendHeader("Content-Encoding", "gzip");
  server.sendHeader("Cache-Control", "no-store");
  server.setContentLength(GG_SITE_LEN);
  server.send(200, "text/html", "");
  const size_t total = sizeof(GG_SITE_B64) - 1;
  uint8_t buf[768];
  for (size_t i = 0; i < total; i += 1024) {
    size_t n = total - i < 1024 ? total - i : 1024;
    int m = gg_b64_decode(GG_SITE_B64 + i, n, buf);
    if (m <= 0) return;
    server.sendContent((const char*)buf, (size_t)m);
  }
}
#endif

void httpBegin() {
  static bool routesAdded = false;              // the server can be stopped for setup mode and begun again; the routes stay
  if (routesAdded) { server.begin(); return; }
  routesAdded = true;
  static const char* keepHeaders[] = {"Origin", "Host"};     // the core drops request headers it was not asked to keep
  server.collectHeaders(keepHeaders, 2);
  server.on("/", HTTP_GET, httpSite);
  server.on("/index.html", HTTP_GET, httpSite);
  server.on("/ping", HTTP_GET, []() { if (httpGuard()) httpReply("PONG"); });
  server.on("/info", HTTP_GET, []() { if (httpGuard()) httpReply(infoText()); });
  server.on("/list", HTTP_GET, []() { if (httpGuard()) httpReply(listText()); });
  server.on("/crc", HTTP_GET, []() { if (httpGuard()) httpReply(opCrc(server.arg("name"))); });
  server.on("/get", HTTP_GET, httpGetFile);
  server.on("/show", HTTP_POST, []() { if (httpGuard()) httpReply(opShow(server.arg("name"))); });
  server.on("/del", HTTP_POST, []() { if (httpGuard()) httpReply(opDel(server.arg("name"))); });
  server.on("/off", HTTP_POST, []() { if (httpGuard()) httpReply(opPower(false)); });
  server.on("/on", HTTP_POST, []() { if (httpGuard()) httpReply(opPower(true)); });
  server.on("/rotate", HTTP_POST, []() { if (httpGuard()) httpReply(opRotate(server.arg("s").c_str())); });
  server.on("/shuffle", HTTP_POST, []() { if (httpGuard()) httpReply(opShuffle(server.arg("on").c_str())); });
  server.on("/bright", HTTP_POST, []() { if (httpGuard()) httpReply(opBright(server.arg("pct").c_str())); });
  server.on("/sched", HTTP_POST, []() {            // v=off, or v=HHMM-HHMM
    if (!httpGuard()) return;
    String v = server.arg("v");
    int dash = v.indexOf("-");
    if (dash < 0) { httpReply(opSched(v.c_str(), NULL)); return; }
    String a = v.substring(0, dash), b = v.substring(dash + 1);
    httpReply(opSched(a.c_str(), b.c_str()));
  });
  server.on("/put", HTTP_POST, httpPutDone, httpPutData);
  server.on("/setup", HTTP_POST, []() {
    if (!httpGuard()) return;
    String e = keyCheck(server.arg("key"));
    httpReply(e.length() ? e : opSetup());
  });
  server.onNotFound(httpNotFound);
  server.begin();
}

// Called every pass of loop(): starts the server and mDNS when the Wi-Fi comes up (again), serves requests while it is up.
void wifiTick() {
  if (setupOn || wifiSsid.length() == 0) return;
  bool up = (WiFi.status() == WL_CONNECTED);
  if (up && !wifiWasUp) {
    WiFi.setSleep(false);                       // no modem sleep: steadier latency (the probe's setting)
    if (mdnsUp) MDNS.end();
    mdnsUp = MDNS.begin(HOSTNAME);
    if (mdnsUp) MDNS.addService("http", "tcp", 80);
    if (!serverUp) { httpBegin(); serverUp = true; }
  }
  if (!up && wifiWasUp && mdnsUp) { MDNS.end(); mdnsUp = false; }
  wifiWasUp = up;
  if (up && serverUp) server.handleClient();
}


// ---- Setup mode (firmware 13) ----
// Puts the board on a home network without USB. The board hosts the WPA2 network "GlowGrid-Setup" whose password is the board's setup key
// (fw 18; before that it was open, so anyone in range during the 5 minutes could have pointed the board at their own network) and answers
// every DNS name with its own address, so a phone opens the page by itself as a "sign in" screen. It serves one small page at
// http://192.168.4.1/: pick a network from a scan, type the password, Save. LED 0 pulses dim blue while it runs. It starts when
//   * there is no saved network at power-up,
//   * a network just saved did not join within 30 s,
//   * it is asked for: POST /setup?key=<setup key> (the editor's "Change the board's Wi-Fi" button), the USB command WIFI SETUP, or a
//     5-second hold of the On/off button.
// A saved network that does not join after a power-up does NOT open it (fw 18): a router that is slow to start after a power cut would
// take the board off the network for 5 minutes. Use the button hold or USB if the network really changed.
// It ends after 5 minutes (the board goes back to the saved network, which is kept) or when a network is saved.
// The API is not served on the setup network: only this page and its scan and save are reachable.

void setupPage() {
  setupServer.sendHeader("Cache-Control", "no-store");
  setupServer.send(200, "text/html", SETUP_PAGE);
}

void setupScanSend() {
  if (setupServer.arg("fresh").length() || setupScanText.length() == 0) setupScanText = wifiScanText();
  setupServer.sendHeader("Cache-Control", "no-store");
  setupServer.send(200, "text/plain", setupScanText);
}

void setupSave() {
  String e = wifiStore(setupServer.arg("s").c_str(), setupServer.arg("p").c_str());
  if (e.length()) { setupServer.send(400, "text/plain", e + "\n"); return; }
  setupServer.send(200, "text/plain", "OK saved\n");
  setupSavePending = true;
  setupSaveAt = millis();                       // the join starts after SETUP_SAVE_CLOSE_MS; the page counts it down
}

void setupStart() {
  if (setupOn) { setupAt = millis(); return; }
  setupOn = true;
  setupAt = millis();
  setupSavePending = false;
  joinWatch = false;
  if (serverUp) { server.close(); serverUp = false; }
  wifiStop();                                    // mDNS off, station off
  WiFi.mode(WIFI_STA);
  setupScanText = wifiScanText();                // scan first, while no phone is attached: the page then shows the list at once
  WiFi.mode(WIFI_AP_STA);
  WiFi.setTxPower(WIFI_POWER_8_5dBm);
  WiFi.softAP(SETUP_SSID, keyGet().c_str());     // WPA2: the setup key is the password
  dnsServer.start(53, "*", WiFi.softAPIP());
  static bool routesAdded = false;
  if (!routesAdded) {
    routesAdded = true;
    setupServer.on("/", HTTP_GET, setupPage);
    setupServer.on("/scan", HTTP_GET, setupScanSend);
    setupServer.on("/save", HTTP_POST, setupSave);
    setupServer.onNotFound(setupPage);           // every other address (the phone's "is there internet" checks) shows the page too
  }
  setupServer.begin();
  Serial.println("setup mode: join the Wi-Fi network " SETUP_SSID " (password: the setup key, see WIFI KEY) and open http://192.168.4.1/ (5 minutes)");
}

// Ends setup mode: the setup network and its server go away and the panel goes back to what it was showing.
void setupEnd() {
  if (!setupOn) return;
  setupServer.close();
  dnsServer.stop();
  WiFi.softAPdisconnect(true);
  setupOn = false;
  setupSavePending = false;
  if (!panelOn) { strip.clear(); strip.show(); }
  else if (data) { dirty = true; nextFrameAt = millis(); }
  else showEmpty();
  if (wifiSsid.length()) wifiBegin(); else WiFi.mode(WIFI_OFF);
  Serial.println("setup mode ended");
}

// Ends setup mode and joins the network that was just saved; if it does not join in 30 s, setup mode opens again.
void setupFinish() {
  setupEnd();
  joinWatch = true; joinWatchAt = millis(); joinWatchMs = JOIN_WAIT_SAVE_MS;
}

String opSetup() {
  if (setupOn) return String("OK setup mode is already on: join the Wi-Fi network " SETUP_SSID " (password: the setup key) and open http://192.168.4.1/");
  setupRequested = true;
  setupReqAt = millis();
  return String("OK setup mode starts in a moment: join the Wi-Fi network " SETUP_SSID " (password: the setup key on the board's label) and open http://192.168.4.1/ (5 minutes; this connection ends)");
}

// Called every pass of loop().
void setupTick() {
  uint32_t now = millis();
  if (setupRequested && now - setupReqAt >= 800) { setupRequested = false; setupStart(); }
  if (!setupOn) {
    if (!joinWatch) return;
    if (WiFi.status() == WL_CONNECTED || wifiSsid.length() == 0) { joinWatch = false; return; }
    if (now - joinWatchAt < joinWatchMs) return;
    joinWatch = false;
    if (GG_SETUP_AUTO_START()) setupStart();     // a network just saved did not join
    return;
  }
  dnsServer.processNextRequest();
  setupServer.handleClient();
  static uint32_t lastPulse = 0;
  if (now - lastPulse >= 50) {
    lastPulse = now;
    strip.setPixelColor(0, 0, 0, setupPulse());
    strip.show();
  }
  // millis() again, not `now`: handleClient() above may just have set setupSaveAt, and `now - setupSaveAt` would wrap to a huge number
  // and close the setup network on the same pass as the reply (which is what fw 13 and 14 did, whatever the delay was meant to be).
  if (setupSavePending && millis() - setupSaveAt >= SETUP_SAVE_CLOSE_MS) { setupFinish(); return; }
  // A Save in the last seconds must still go through setupFinish() (which watches the join and reopens setup if it fails), not setupEnd().
  if (!setupSavePending && now - setupAt >= SETUP_TIMEOUT_MS) setupEnd();
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
  const char* pre = putPrecheck(name, size);
  if (pre) { Serial.printf("ERR %s\n", pre); return; }
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
  const char* err = putCommit(name, size);
  if (err) { Serial.printf("ERR %s\n", err); return; }
  Serial.printf("OK saved %s\n", name.c_str());
}

void say(const String& text) { Serial.println(text.c_str()); }

void doCommand(char* line) {
  if (strncasecmp(line, "WIFI", 4) == 0 && (line[4] == 0 || line[4] == ' ')) { say(opWifi(line + 4)); return; }
  char cmd[8] = "", a1[48] = "", a2[16] = "", a3[16] = "";
  int n = sscanf(line, "%7s %47s %15s %15s", cmd, a1, a2, a3);
  if (n < 1) return;
  String c = String(cmd);
  c.toUpperCase();
  if (c == "PING") {
    Serial.println("PONG");
  } else if (c == "LIST") {
    say(listText());
  } else if (c == "PUT") {
    if (n < 4) { Serial.println("ERR usage: PUT <name> <bytes> <crc32 hex>"); return; }
    doPut(String(a1), (size_t)strtoul(a2, NULL, 10), (uint32_t)strtoul(a3, NULL, 16));
  } else if (c == "DEL") {
    say(n < 2 ? String("ERR no such sprite") : opDel(String(a1)));
  } else if (c == "SHOW") {
    say(n < 2 ? String("ERR no such sprite") : opShow(String(a1)));
  } else if (c == "OFF") {
    say(opPower(false));
  } else if (c == "ON") {
    say(opPower(true));
  } else if (c == "ROTATE") {
    say(opRotate(n >= 2 ? a1 : NULL));
  } else if (c == "SHUFFLE") {
    say(opShuffle(n >= 2 ? a1 : NULL));
  } else if (c == "BRIGHT") {
    say(opBright(n >= 2 ? a1 : NULL));
  } else if (c == "SCHED") {
    say(opSched(n >= 2 ? a1 : NULL, n >= 3 ? a2 : NULL));
  } else if (c == "CRC") {
    say(n < 2 ? String("ERR no such sprite") : opCrc(String(a1)));
  } else if (c == "GET") {
    File f = (n >= 2 && gg_name_ok(a1)) ? LittleFS.open(pathOf(String(a1)), "r") : File();
    if (!f) { Serial.println("ERR no such sprite"); return; }
    uint8_t buf[48];
    char hex[2 * sizeof(buf) + 1];
    uint32_t crc = 0;
    size_t total = 0, r;
    while ((r = f.read(buf, sizeof(buf))) > 0) {
      crc = gg_crc32(crc, buf, r);
      total += r;
      for (size_t i = 0; i < r; i++) sprintf(hex + 2 * i, "%02x", buf[i]);
      Serial.print("D ");
      Serial.println(hex);
    }
    f.close();
    Serial.printf("OK crc=%08x size=%u\n", (unsigned)crc, (unsigned)total);
  } else if (c == "INFO") {
    say(infoText());
  } else {
    Serial.println("ERR unknown command");
  }
}

void handleSerial() {
  static char line[256];       // WIFI SET carries the name and password as hex: up to 200 characters
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

// Called every pass of loop(), acts once a second: starts NTP when the Wi-Fi is up, then keeps the panel inside the schedule.
// Acts on changes only (switching on at <on>, off at <off>), so a manual On or Off holds until the next change; right after a
// power-up, or when the schedule is saved, the first pass with a known time applies the state the window calls for.
void scheduleTick() {
  static uint32_t lastCheck = 0;
  uint32_t now = millis();
  if (now - lastCheck < 1000) return;
  lastCheck = now;
  if (!ntpStarted && !setupOn && wifiSsid.length() && WiFi.status() == WL_CONNECTED) { configTzTime(GG_TZ, "pool.ntp.org", "time.google.com"); ntpStarted = true; }
  if (!schedSet) return;
  int m;
  if (!localMinutes(m)) return;
  int8_t inside = inWindow(m) ? 1 : 0;
  if (inside == schedSeen) return;
  schedSeen = inside;
  setPanel(inside == 1);
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
  loadRotate();
  loadShuffle();
  loadBright();
  loadSched();
  wifiLoad();                        // joins the saved network in the background; nothing waits for it
  scanSprites();
  Serial.printf("Glow Grid player fw %d ready: %d sprite(s), %u bytes free\n", GG_FW_VERSION, nSprites,
                (unsigned)(LittleFS.totalBytes() - LittleFS.usedBytes()));
  bool wasOff = LittleFS.exists(OFF_MARK);
  if (nSprites > 0) selectIndex(0); else showEmpty();
  if (wasOff) { setPanel(false); Serial.println("panel off (as left)"); }
  if (wifiSsid.length() == 0 && GG_SETUP_AUTO_START()) setupStart();   // nothing saved: offer setup
}

void loop() {
  uint32_t now = millis();
  static uint32_t lastLoop = 0;
  if (lastLoop && now - lastLoop > gapMaxMs) gapMaxMs = now - lastLoop;
  lastLoop = now;
  handleSerial();
  wifiTick();
  setupTick();
  handleButtons();
  rotateTick();
  scheduleTick();
  playTick();
  delay(1);                          // lets the Wi-Fi tasks run
}
