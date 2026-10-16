// Glow Grid player for the ESP32-C3 SuperMini and the 16x16 WS2812B panel.
// Stores several sprites (.gg files) in the board's flash and plays one at a time.
//
//   Next button (GPIO5 to GND): next sprite.   On/off button (GPIO7 to GND): panel off/on.
//   Panel data: GPIO6 to DIN.
//
// Put sprites on the board over USB with ../tools/gg_tool.py (close the Serial Monitor first).
// Wi-Fi (firmware 9) is set up over USB (WIFI command below); the same operations are then served over HTTP, see "HTTP API".
// Bluetooth comes later.
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
//   ROTATE <seconds>           -> OK rotate <seconds>; 0 = off. Cycles the stored sprites in list order, kept across
//                                 a power cycle; each sprite keeps animating for the whole interval (David, 2026-10-15)
//   CRC <name>                 -> OK crc=<8 hex> size=<bytes> of the stored file, so the editor can tell an unchanged
//                                 example from one you replaced (fw 7); ERR no such sprite
//   GET <name>                 -> D <96 hex digits> lines (48 bytes each) with the stored file, then
//                                 OK crc=<8 hex> size=<bytes>; ERR no such sprite. Lets the editor load a sprite
//                                 back into the grid (fw 8). The panel pauses on its current frame while it runs.
//   INFO                       -> OK fw=<n> current=<name> ... rotate=<seconds> wifi=<off|connecting|connected> ip=<address or -> gap_ms=<n>
//                                 (gap_ms: the longest the main loop went without running since the last INFO; fw 9)
//   WIFI SET <ssid hex> <password hex, or -> for none>  -> OK wifi saved; joining. Stored in the chip's NVS, joined at every start (fw 9).
//                                 gg_tool.py hex-encodes for you. 2.4 GHz networks only; the board is then http://glowgrid.local
//   WIFI STATUS                -> OK wifi=<state> ip=<address> rssi=<dBm> host=glowgrid.local ssid=<name>   (never the password)
//   WIFI CLEAR                 -> OK wifi cleared
//   WIFI SCAN                  -> NET <ssid hex> <rssi dBm> <1 if it needs a password, else 0> lines (strongest first, up to 20, one per name,
//                                 hidden networks left out), then OK networks=<n> (fw 10). Takes 2 to 5 seconds; the animation stalls meanwhile.

#include <Adafruit_NeoPixel.h>
#include <LittleFS.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include "gg_core.h"

#define DATA_PIN 6
#define BTN_NEXT 5
#define BTN_OFF 7
#define MAX_SPRITES 64           // the list lives in RAM; PUT refuses a new name once it is full
#define GG_FW_VERSION 10          // bump on every change pushed to the repo; INFO reports it
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
uint32_t rotateSec = 0;      // 0 = stay on one sprite; else move to the next one every rotateSec seconds
uint32_t rotateAt = 0;       // millis() at which the next sprite is due
#define ROTATE_MAX 86400UL

String pathOf(const String& name) { return "/" + name + ".gg"; }
const char* OFF_MARK = "/panel.off";   // exists while the panel is off, so OFF survives a power cycle (David, 2026-10-15)
const char* ROTATE_PATH = "/rotate.txt"; // the rotate interval in seconds, absent or 0 = off
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
  rotateReset();                     // a new sprite gets a full interval
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

void rotateTick() {
  if (!rotateSec || !panelOn || nSprites < 2) return;
  if ((int32_t)(millis() - rotateAt) >= 0) selectIndex((cur + 1) % nSprites);
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

void handleButtons() {
  if (pressed(btnNext)) {
    if (!panelOn) setPanel(true);
    else if (nSprites > 0) selectIndex((cur + 1) % nSprites);
  }
  if (pressed(btnOff)) setPanel(!panelOn);
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
  if (wifiSsid.length() == 0) return String("off");
  return String(WiFi.status() == WL_CONNECTED ? "connected" : "connecting");
}

String listText() {
  String out;
  for (int i = 0; i < nSprites; i++) {
    File f = LittleFS.open(pathOf(names[i]), "r");
    out += sfmt("FILE %s %u\n", names[i].c_str(), (unsigned)(f ? f.size() : 0));
    if (f) f.close();
  }
  out += sfmt("OK %d files, %u bytes free", nSprites, (unsigned)freeBytes());
  return out;
}

String infoText() {
  uint32_t gap = gapMaxMs;
  gapMaxMs = 0;                      // gap_ms = the longest the main loop went without running since the last INFO
  String ip = (wifiSsid.length() && WiFi.status() == WL_CONNECTED) ? WiFi.localIP().toString() : String("-");
  return sfmt("OK fw=%d current=%s sprites=%d panel=%s frames=%d fps10=%d bright_pct=%d gamma10=%d free=%u rotate=%lu wifi=%s ip=%s gap_ms=%lu",
              GG_FW_VERSION, cur >= 0 ? names[cur].c_str() : "-", nSprites, panelOn ? "on" : "off",
              data ? hdr.frames : 0, data ? hdr.fps10 : 0, data ? hdr.bright_pct : 0, data ? hdr.gamma10 : 0,
              (unsigned)freeBytes(), (unsigned long)rotateSec, wifiState().c_str(), ip.c_str(), (unsigned long)gap);
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
// this goes beyond a home network.
#define HOSTNAME "glowgrid"
WebServer server(80);
Preferences prefs;
bool serverUp = false, mdnsUp = false, wifiWasUp = false;

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
  if (wifiSsid.length()) wifiBegin();
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

// WIFI SET <ssid hex> <password hex, or - for an open network> | WIFI STATUS | WIFI CLEAR.
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
  if (n >= 2 && s == "SET") {
    char ssid[40], pass[72];
    int sl = gg_hex_decode(h1, ssid, sizeof ssid);
    if (sl < 1 || sl > 32) return String("ERR usage: WIFI SET <ssid as hex, 1 to 32 bytes> <password as hex or ->");
    int pl = 0;
    pass[0] = 0;
    if (n >= 3 && strcmp(h2, "-") != 0) pl = gg_hex_decode(h2, pass, sizeof pass);
    if (pl < 0 || pl > 63 || (pl > 0 && pl < 8)) return String("ERR password must be 8 to 63 characters (or - for an open network)");
    prefs.begin("gg", false);
    prefs.putString("ssid", ssid);
    prefs.putString("pass", pass);
    prefs.end();
    wifiStop();
    wifiSsid = String(ssid);
    wifiPass = String(pass);
    wifiBegin();
    return String("OK wifi saved; joining. Check with WIFI STATUS (2.4 GHz networks only)");
  }
  return String("ERR usage: WIFI STATUS | WIFI SCAN | WIFI SET <ssid hex> <password hex or -> | WIFI CLEAR");
}

// ---- HTTP API ----
//   GET  /ping /info /list            same text as PING, INFO, LIST
//   GET  /crc?name=X   GET /get?name=X (the file's bytes)
//   POST /show?name=X  /del?name=X  /off  /on  /rotate?s=N
//   POST /put?name=X[&crc=hex]        the file as multipart/form-data (field "file"): binary-safe, and a plain "simple" request,
//                                      so a browser sends no pre-flight. Raw POST bodies do not work: the ESP32 core cuts them at the first zero byte.
// Replies are the same "OK ..." / "ERR ..." text as USB. Every reply carries CORS headers, and the pre-flight a browser sends before a
// request from the https editor page to a private address is answered (Access-Control-Allow-Private-Network).
void httpCors() {
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  server.sendHeader("Access-Control-Allow-Headers", "*");
  server.sendHeader("Access-Control-Allow-Private-Network", "true");
  server.sendHeader("Access-Control-Max-Age", "600");
  server.sendHeader("Cache-Control", "no-store");
}

void httpReply(const String& msg) {
  int code = 200;
  if (msg.startsWith("ERR")) code = (msg.indexOf("no such") >= 0) ? 404 : 400;
  httpCors();
  server.send(code, "text/plain", msg + "\n");
}

void httpGetFile() {
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
    size_t want = (size_t)strtoul(server.arg("size").c_str(), NULL, 10);   // optional: lets the space check run before any byte is written
    const char* e = putPrecheck(putName, want ? want : (size_t)(GG_HEADER_SIZE + GG_FRAME_BYTES));
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
  httpCors();
  if (server.method() == HTTP_OPTIONS) { server.send(204); return; }   // the browser's pre-flight for the private-network and POST requests
  server.send(404, "text/plain", "ERR not found\n");
}

void httpBegin() {
  server.on("/ping", HTTP_GET, []() { httpReply("PONG"); });
  server.on("/info", HTTP_GET, []() { httpReply(infoText()); });
  server.on("/list", HTTP_GET, []() { httpReply(listText()); });
  server.on("/crc", HTTP_GET, []() { httpReply(opCrc(server.arg("name"))); });
  server.on("/get", HTTP_GET, httpGetFile);
  server.on("/show", HTTP_POST, []() { httpReply(opShow(server.arg("name"))); });
  server.on("/del", HTTP_POST, []() { httpReply(opDel(server.arg("name"))); });
  server.on("/off", HTTP_POST, []() { httpReply(opPower(false)); });
  server.on("/on", HTTP_POST, []() { httpReply(opPower(true)); });
  server.on("/rotate", HTTP_POST, []() { httpReply(opRotate(server.arg("s").c_str())); });
  server.on("/put", HTTP_POST, httpPutDone, httpPutData);
  server.onNotFound(httpNotFound);
  server.begin();
}

// Called every pass of loop(): starts the server and mDNS when the Wi-Fi comes up (again), serves requests while it is up.
void wifiTick() {
  if (wifiSsid.length() == 0) return;
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
  wifiLoad();                        // joins the saved network in the background; nothing waits for it
  scanSprites();
  Serial.printf("Glow Grid player fw %d ready: %d sprite(s), %u bytes free\n", GG_FW_VERSION, nSprites,
                (unsigned)(LittleFS.totalBytes() - LittleFS.usedBytes()));
  bool wasOff = LittleFS.exists(OFF_MARK);
  if (nSprites > 0) selectIndex(0); else showEmpty();
  if (wasOff) { setPanel(false); Serial.println("panel off (as left)"); }
}

void loop() {
  uint32_t now = millis();
  static uint32_t lastLoop = 0;
  if (lastLoop && now - lastLoop > gapMaxMs) gapMaxMs = now - lastLoop;
  lastLoop = now;
  handleSerial();
  wifiTick();
  handleButtons();
  rotateTick();
  playTick();
  delay(1);                          // lets the Wi-Fi tasks run
}
