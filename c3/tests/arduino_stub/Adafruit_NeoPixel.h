// Stand-in for Adafruit_NeoPixel: logs every show() as one line of hex (LED order, R G B) to $GG_LED_LOG.
#pragma once
#include <Arduino.h>

#define NEO_GRB 0x52
#define NEO_KHZ800 0x0000

class Adafruit_NeoPixel {
  uint16_t n;
  uint8_t* px;
 public:
  Adafruit_NeoPixel(uint16_t count, int16_t, uint16_t) : n(count), px((uint8_t*)calloc(count, 3)) {}
  void begin() {}
  void setBrightness(uint8_t) {}
  void clear() { memset(px, 0, (size_t)n * 3); }
  void setPixelColor(uint16_t i, uint8_t r, uint8_t g, uint8_t b) {
    if (i < n) { px[i * 3] = r; px[i * 3 + 1] = g; px[i * 3 + 2] = b; }
  }
  void show() {
    const char* path = getenv("GG_LED_LOG");
    if (!path) return;
    FILE* f = fopen(path, "a");
    if (!f) return;
    for (int i = 0; i < n * 3; i++) fprintf(f, "%02x", px[i]);
    fputc('\n', f);
    fclose(f);
  }
};
