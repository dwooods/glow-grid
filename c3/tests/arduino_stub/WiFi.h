// Stand-in for the ESP32 WiFi library. With $GG_WIFI_SIM set, begin() "connects" at once (as 127.0.0.1); otherwise the board
// never joins. Every begin() is logged to $GG_WIFI_LOG as "begin <ssid> <password>" so the tests can check what reached it.
#pragma once
#include <Arduino.h>
#define WIFI_STA 1
#define WIFI_AP_STA 3
#define WIFI_POWER_8_5dBm 34
#define WIFI_OFF 0
#define WIFI_AUTH_OPEN 0
#define WIFI_AUTH_WPA2_PSK 3
#define WIFI_AUTH_WPA3_PSK 6
enum wl_status_t { WL_IDLE_STATUS = 0, WL_NO_SSID_AVAIL = 1, WL_CONNECTED = 3, WL_DISCONNECTED = 6 };
enum arduino_event_id_t { ARDUINO_EVENT_WIFI_AP_STACONNECTED = 1, ARDUINO_EVENT_WIFI_AP_STADISCONNECTED = 2 };
struct arduino_event_info_t { struct { int reason; } wifi_ap_stadisconnected; };
// getEfuseMac(): MAC 1a:2b:3c:4d:5e:6f, first byte in the lowest byte as on the chip, so the board is named glowgrid-5e6f in the tests.
struct EspStub { unsigned getFreeHeap() { return 123456; } uint64_t getEfuseMac() { return 0x6F5E4D3C2B1AULL; } };
static EspStub ESP;
struct IPAddress { String toString() const { return String("127.0.0.1"); } };
class WiFiStub {
  bool began = false;
  void log(const char* a, const char* b = "", const char* c = "") { const char* p = getenv("GG_WIFI_LOG"); if (!p) return; FILE* f = fopen(p, "a"); if (!f) return; fprintf(f, "%s %s %s\n", a, b, c); fclose(f); }
 public:
  int m = 0;
  bool mode(int x) { m = x; log("mode", x == 0 ? "off" : x == 1 ? "sta" : "ap_sta"); return true; }
  int getMode() { return m; }
  // $GG_WIFI_SCAN = "name|rssi|secure;name|rssi|secure;..." is what a scan "hears" (an empty name is a hidden network).
  struct Hit { String ssid; int rssi, sec; };
  Hit hits[64]; int nHits = 0;
  int scanNetworks() {
    nHits = 0; log("scan");
    const char* e = getenv("GG_WIFI_SCAN"); if (!e) return 0;
    std::string all(e); size_t pos = 0;
    while (pos <= all.size() && nHits < 64) {
      size_t end = all.find(';', pos); if (end == std::string::npos) end = all.size();
      std::string item = all.substr(pos, end - pos); pos = end + 1;
      size_t a = item.find('|'), b = item.rfind('|'); if (a == std::string::npos || a == b) continue;
      hits[nHits].ssid = String(item.substr(0, a).c_str()); hits[nHits].rssi = atoi(item.substr(a + 1, b - a - 1).c_str()); hits[nHits].sec = atoi(item.substr(b + 1).c_str()); nHits++;
    }
    return nHits;
  }
  String SSID(int i) { return hits[i].ssid; }
  int RSSI(int i) { return hits[i].rssi; }
  int encryptionType(int i) { return hits[i].sec ? 3 : 0; }
  void scanDelete() { nHits = 0; }
  bool setHostname(const char* h) { log("hostname", h); return true; }
  void setAutoReconnect(bool) {}
  void onEvent(void (*)(arduino_event_id_t, arduino_event_info_t)) {}
  // Access point: only logged ("softap <ssid>", "softap off") so the tests can see setup mode start and end.
  // The password and the security mode go to the log too ("softap <ssid> <password> wpa3", or "(open)"), so the tests can check the setup network.
  bool softAP(const char* ssid, const char* pass = NULL, int = 1, int = 0, int = 4, bool = false, int auth = WIFI_AUTH_WPA2_PSK) {
    std::string pw = pass ? pass : "(open)"; pw += auth == WIFI_AUTH_WPA3_PSK ? " wpa3" : auth == WIFI_AUTH_OPEN ? " open" : " wpa2";
    log("softap", ssid, pw.c_str()); return true; }
  bool softAPdisconnect(bool = false) { log("softap", "off"); return true; }
  IPAddress softAPIP() { return IPAddress(); }
  bool setTxPower(int) { return true; }
  bool setSleep(bool s) { log("sleep", s ? "on" : "off"); return true; }
  int begin(const char* ssid, const char* pass = NULL) { began = true; log("begin", ssid, pass ? pass : "(open)"); return 0; }
  bool disconnect(bool = false, bool = false) { if (began) log("disconnect"); began = false; return true; }
  wl_status_t status() { return (began && getenv("GG_WIFI_SIM")) ? WL_CONNECTED : WL_DISCONNECTED; }
  IPAddress localIP() { return IPAddress(); }
  int RSSI() { return -50; }
};
static WiFiStub WiFi;
