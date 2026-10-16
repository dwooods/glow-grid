// Stand-in for ESPmDNS: only logs to $GG_WIFI_LOG so the tests can see that the name was announced.
#pragma once
#include <Arduino.h>
struct MDNSStub {
  void log(const char* what, const char* arg = "") { const char* p = getenv("GG_WIFI_LOG"); if (!p) return; FILE* f = fopen(p, "a"); if (!f) return; fprintf(f, "mdns %s %s\n", what, arg); fclose(f); }
  bool begin(const char* name) { log("begin", name); return true; }
  void addService(const char* s, const char* p, int port) { char b[64]; snprintf(b, sizeof b, "%s.%s %d", s, p, port); log("service", b); }
  void end() { log("end"); }
};
static MDNSStub MDNS;
