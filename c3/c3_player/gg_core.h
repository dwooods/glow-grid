// Glow Grid sprite file (.gg) logic for the ESP32-C3, with no Arduino dependencies,
// so the same code is compiled and tested on a PC (tests/test_gg.py).
//
// File format, version 1, little-endian. A sprite file is independent of the panel:
// it has no wiring order and no gamma-corrected values.
//   offset size  field
//   0      2     magic "GG"
//   2      1     version (1)
//   3      1     flags (0)
//   4      1     cols (16)
//   5      1     rows (16)
//   6      2     frames (1 to GG_MAX_FRAMES)
//   8      2     fps x 10 (5 to 300, i.e. 0.5 to 30 fps)
//   10     1     brightness, percent (1 to 100; the player caps it at GG_MAX_BRIGHT_PCT)
//   11     1     gamma x 10 (10 to 30)
//   12     ...   frames x 256 pixels x 3 bytes (R, G, B), uncorrected, row by row from the top-left
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <math.h>

#define GG_HEADER_SIZE 12
#define GG_COLS 16
#define GG_ROWS 16
#define GG_PIXELS (GG_COLS * GG_ROWS)
#define GG_FRAME_BYTES (GG_PIXELS * 3)
#define GG_MAX_FRAMES 16        // a 16x16 panel plays simple loops; a cap keeps sprites small (12,300 bytes at most)
#define GG_MAX_FILE (GG_HEADER_SIZE + GG_MAX_FRAMES * GG_FRAME_BYTES)
#define GG_MAX_BRIGHT_PCT 40   // same safety cap as MAX_BRIGHTNESS 0.4 on the Pi

// Panel wiring: same meaning as COLUMN_MAJOR, SERPENTINE, FLIP_X, FLIP_Y in local_config.py.
// Defaults are the tested panel: column-major serpentine, index 0 at the top-left.
#ifndef GG_COLUMN_MAJOR
#define GG_COLUMN_MAJOR 1
#endif
#ifndef GG_SERPENTINE
#define GG_SERPENTINE 1
#endif
#ifndef GG_FLIP_X
#define GG_FLIP_X 0
#endif
#ifndef GG_FLIP_Y
#define GG_FLIP_Y 0
#endif

struct GGHeader {
  uint8_t version, flags, cols, rows;
  uint16_t frames;
  uint16_t fps10;
  uint8_t bright_pct, gamma10;
};

// Checks the 12 header bytes against the whole file size. Returns NULL if fine,
// otherwise a short error text. Fills *h when it is fine.
static inline const char* gg_parse_header(const uint8_t* b, size_t total, GGHeader* h) {
  if (total < GG_HEADER_SIZE) return "too short";
  if (b[0] != 'G' || b[1] != 'G') return "bad magic";
  if (b[2] != 1) return "unknown version";
  if (b[4] != GG_COLS || b[5] != GG_ROWS) return "wrong grid size";
  uint16_t frames = (uint16_t)(b[6] | (b[7] << 8));
  if (frames < 1 || frames > GG_MAX_FRAMES) return "bad frame count";
  uint16_t fps10 = (uint16_t)(b[8] | (b[9] << 8));
  if (fps10 < 5 || fps10 > 300) return "bad fps";
  if (b[10] < 1 || b[10] > 100) return "bad brightness";
  if (b[11] < 10 || b[11] > 30) return "bad gamma";
  if (total != (size_t)GG_HEADER_SIZE + (size_t)frames * GG_FRAME_BYTES) return "size does not match frames";
  if (h) {
    h->version = b[2]; h->flags = b[3]; h->cols = b[4]; h->rows = b[5];
    h->frames = frames; h->fps10 = fps10; h->bright_pct = b[10]; h->gamma10 = b[11];
  }
  return NULL;
}

// LED number for the pixel at column x, row y (0,0 = top-left). Same as grid_common.xy_to_index.
static inline int gg_led_index(int x, int y) {
  if (GG_FLIP_X) x = GG_COLS - 1 - x;
  if (GG_FLIP_Y) y = GG_ROWS - 1 - y;
  if (GG_COLUMN_MAJOR) {
    int pos = (GG_SERPENTINE && (x % 2)) ? (GG_ROWS - 1 - y) : y;
    return x * GG_ROWS + pos;
  }
  int pos = (GG_SERPENTINE && (y % 2)) ? (GG_COLS - 1 - x) : x;
  return y * GG_COLS + pos;
}

// Brightness and gamma table. Same formula as grid_common.set_light: any non-zero
// channel stays at least 1; brightness is capped at GG_MAX_BRIGHT_PCT.
// Uses double precision and the same rounding as the Python and JavaScript versions.
static inline void gg_make_lut(uint8_t bright_pct, uint8_t gamma10, uint8_t lut[256]) {
  int p = bright_pct;
  if (p > GG_MAX_BRIGHT_PCT) p = GG_MAX_BRIGHT_PCT;
  if (p < 1) p = 1;
  double b = p / 100.0;
  double g = gamma10 / 10.0;
  for (int c = 0; c < 256; c++) {
    double v = 255.0 * b * pow(c / 255.0, g);
    int r = (int)nearbyint(v);   // round half to even, like Python's round() (255 * 0.3 = 76.5 -> 76)
    if (c > 0 && r == 0) r = 1;
    lut[c] = (uint8_t)r;
  }
}

// Standard CRC-32 (the same as zlib.crc32 in Python). Call with crc = 0 to start.
static inline uint32_t gg_crc32(uint32_t crc, const uint8_t* data, size_t n) {
  crc = ~crc;
  for (size_t i = 0; i < n; i++) {
    crc ^= data[i];
    for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}

// Sprite names: 1 to 31 characters from A-Z a-z 0-9 _ -
static inline bool gg_name_ok(const char* s) {
  size_t n = strlen(s);
  if (n < 1 || n > 31) return false;
  for (size_t i = 0; i < n; i++) {
    char c = s[i];
    bool ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '-';
    if (!ok) return false;
  }
  return true;
}

// One push button: pin number, last level read, when it last changed (millis).
struct GGButton { uint8_t pin; bool last; uint32_t changed; };

// Hex text to bytes, NUL-terminated, for text that must survive the command line (Wi-Fi name and password may hold
// spaces and any character). Returns the byte count, or -1 for odd length, a non-hex digit or no room (cap includes the NUL).
static inline int gg_hex_decode(const char* hex, char* out, size_t cap) {
  size_t n = strlen(hex);
  if (n % 2 || n / 2 + 1 > cap) return -1;
  for (size_t i = 0; i < n; i += 2) {
    int v = 0;
    for (int k = 0; k < 2; k++) {
      char c = hex[i + k];
      int d = (c >= '0' && c <= '9') ? c - '0' : (c >= 'a' && c <= 'f') ? c - 'a' + 10 : (c >= 'A' && c <= 'F') ? c - 'A' + 10 : -1;
      if (d < 0) return -1;
      v = v * 16 + d;
    }
    out[i / 2] = (char)v;
  }
  out[n / 2] = 0;
  return (int)(n / 2);
}
