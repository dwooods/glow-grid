// Stand-in for the ESP32 DNSServer: only logs to $GG_WIFI_LOG so the tests can see that the catch-all DNS started and stopped.
#pragma once
#include <Arduino.h>
#include <WiFi.h>
struct DNSServer {
  void log(const char* what) { const char* p = getenv("GG_WIFI_LOG"); if (!p) return; FILE* f = fopen(p, "a"); if (!f) return; fprintf(f, "dns %s\n", what); fclose(f); }
  bool start(int, const char*, const IPAddress&) { log("start"); return true; }
  void stop() { log("stop"); }
  void processNextRequest() {}
};
