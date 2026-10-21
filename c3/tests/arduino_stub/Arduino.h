// Minimal stand-in for the Arduino core, just enough to compile and run c3_player.ino on a PC.
// It is NOT the real API: it checks the sketch's logic and types, not esp32 core version differences.
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <time.h>
#include <unistd.h>
#include <poll.h>
#include <string>
#include <strings.h>

#define INPUT_PULLUP 2
#define OUTPUT 1
#define HIGH 1
#define LOW 0

// $GG_TIME_SCALE (e.g. 100) makes millis() run that many times faster, so the tests can sit through the setup-mode timeouts (90 s, 5 min).
inline uint32_t millis() {
  timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  static const char* sc = getenv("GG_TIME_SCALE");
  static const double scale = sc ? atof(sc) : 1.0;
  return (uint32_t)((double)(ts.tv_sec * 1000UL + ts.tv_nsec / 1000000UL) * scale);
}
// The clock (fw 20). $GG_FAKE_EPOCH = the UNIX time at start; it then advances with millis() (so $GG_TIME_SCALE speeds it up). Without it the
// board has no time, as before the first NTP answer. configTzTime() only records the zone and servers in $GG_WIFI_LOG ("ntp <tz> <server>").
#define GG_HAVE_STUB_TIME 1
#include <time.h>
inline time_t gg_epoch() {
  static const char* e = getenv("GG_FAKE_EPOCH");
  static const uint32_t t0 = millis();
  if (!e) return 0;
  return (time_t)atol(e) + (time_t)((millis() - t0) / 1000);
}
inline void configTzTime(const char* tz, const char* server1, const char* = NULL, const char* = NULL) {
  setenv("TZ", tz, 1);
  tzset();
  const char* p = getenv("GG_WIFI_LOG");
  if (p) { FILE* f = fopen(p, "a"); if (f) { fprintf(f, "ntp %s %s\n", tz, server1); fclose(f); } }
}
// Setup mode opens by itself on the board; here only when a test asks ($GG_SETUP_AUTO set), so the other tests see the old behaviour.
#define GG_SETUP_AUTO_START() (getenv("GG_SETUP_AUTO") != NULL)
inline long random(long m) { return m > 0 ? rand() % m : 0; }   // the real core uses the hardware RNG; tests only need it to vary
inline void delay(uint32_t ms) { usleep(ms * 1000); }
inline void pinMode(int, int) {}

// Buttons: the test writes a file of 40 characters, one per pin, '0' = pressed (pulled to ground).
inline int digitalRead(int pin) {
  static uint32_t lastRead = 0;
  static char pins[41] = "1111111111111111111111111111111111111111";
  uint32_t now = millis();
  if (now - lastRead >= 5) {
    lastRead = now;
    const char* path = getenv("GG_PINS");
    if (path) {
      FILE* f = fopen(path, "r");
      if (f) {
        char buf[64] = {0};
        size_t n = fread(buf, 1, 40, f);
        fclose(f);
        if (n == 40) memcpy(pins, buf, 40);
      }
    }
  }
  return pins[pin] == '0' ? 0 : 1;
}

class String {
 public:
  std::string s;
  String() {}
  String(const char* c) : s(c ? c : "") {}
  String(const std::string& x) : s(x) {}
  const char* c_str() const { return s.c_str(); }
  size_t length() const { return s.size(); }
  bool operator==(const String& o) const { return s == o.s; }
  bool operator==(const char* o) const { return s == o; }
  bool operator!=(const char* o) const { return s != o; }
  bool startsWith(const char* p) const { return s.rfind(p, 0) == 0; }
  int indexOf(const char* p) const { size_t k = s.find(p); return k == std::string::npos ? -1 : (int)k; }
  String& operator+=(const String& o) { s += o.s; return *this; }
  String& operator+=(const char* o) { s += o; return *this; }
  int compareTo(const String& o) const { return s.compare(o.s); }
  bool endsWith(const char* e) const {
    size_t n = strlen(e);
    return s.size() >= n && s.compare(s.size() - n, n, e) == 0;
  }
  int lastIndexOf(char c) const { size_t p = s.rfind(c); return p == std::string::npos ? -1 : (int)p; }
  String substring(unsigned from) const { return String(s.substr(from)); }
  String substring(unsigned from, unsigned to) const { return String(s.substr(from, to - from)); }
  void replace(const String& from, const String& to) { if (from.s.empty()) return; size_t k = 0; while ((k = s.find(from.s, k)) != std::string::npos) { s.replace(k, from.s.size(), to.s); k += to.s.size(); } }
  void toUpperCase() { for (auto& ch : s) ch = (char)toupper((unsigned char)ch); }
  String operator+(const String& o) const { return String(s + o.s); }
  String operator+(const char* o) const { return String(s + o); }
  friend String operator+(const char* a, const String& b) { return String(std::string(a) + b.s); }
};

class HWSerialStub {
  uint8_t buf[8192];
  size_t head = 0, tail = 0;
  void fill() {
    if (head < tail) return;
    head = tail = 0;
    pollfd p = {0, POLLIN, 0};
    if (poll(&p, 1, 0) > 0) {
      ssize_t n = ::read(0, buf, sizeof buf);
      if (n > 0) tail = (size_t)n;
    }
  }
 public:
  size_t setRxBufferSize(size_t n) { return n; }
  void begin(unsigned long) {}
  int available() { fill(); return (int)(tail - head); }
  int read() { fill(); return head < tail ? buf[head++] : -1; }
  size_t readBytes(uint8_t* out, size_t n) {
    size_t k = 0;
    while (k < n) { int c = read(); if (c < 0) break; out[k++] = (uint8_t)c; }
    return k;
  }
  void print(const char* t) { fputs(t, stdout); fflush(stdout); }
  void println(const char* t) { fputs(t, stdout); fputc('\n', stdout); fflush(stdout); }
  int printf(const char* fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    int r = vprintf(fmt, ap);
    va_end(ap);
    fflush(stdout);
    return r;
  }
};
static HWSerialStub Serial;
