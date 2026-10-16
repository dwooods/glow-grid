// Stand-in for the ESP32 WiFi library. With $GG_WIFI_SIM set, begin() "connects" at once (as 127.0.0.1); otherwise the board
// never joins. Every begin() is logged to $GG_WIFI_LOG as "begin <ssid> <password>" so the tests can check what reached it.
#pragma once
#include <Arduino.h>
#define WIFI_STA 1
#define WIFI_POWER_8_5dBm 34
enum wl_status_t { WL_IDLE_STATUS = 0, WL_NO_SSID_AVAIL = 1, WL_CONNECTED = 3, WL_DISCONNECTED = 6 };
struct IPAddress { String toString() const { return String("127.0.0.1"); } };
class WiFiStub {
  bool began = false;
  void log(const char* a, const char* b = "", const char* c = "") { const char* p = getenv("GG_WIFI_LOG"); if (!p) return; FILE* f = fopen(p, "a"); if (!f) return; fprintf(f, "%s %s %s\n", a, b, c); fclose(f); }
 public:
  bool mode(int) { return true; }
  bool setHostname(const char* h) { log("hostname", h); return true; }
  void setAutoReconnect(bool) {}
  bool setTxPower(int) { return true; }
  bool setSleep(bool s) { log("sleep", s ? "on" : "off"); return true; }
  int begin(const char* ssid, const char* pass = NULL) { began = true; log("begin", ssid, pass ? pass : "(open)"); return 0; }
  bool disconnect(bool = false, bool = false) { if (began) log("disconnect"); began = false; return true; }
  wl_status_t status() { return (began && getenv("GG_WIFI_SIM")) ? WL_CONNECTED : WL_DISCONNECTED; }
  IPAddress localIP() { return IPAddress(); }
  int RSSI() { return -50; }
};
static WiFiStub WiFi;
