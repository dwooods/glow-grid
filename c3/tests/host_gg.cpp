// Runs the C3 player's real logic (gg_core.h) on a PC so tests/test_gg.py can compare it with the Pi code.
//   host_gg frames <file.gg>     LED-ordered, corrected pixels of every frame, hex, one line per frame
//   host_gg lut <pct> <gamma10>  the 256-entry table
//   host_gg crc <file>           CRC-32 of the file, 8 hex digits
//   host_gg hdr <file>           "OK <frames> <fps10> <bright> <gamma10>" or the error text
//   host_gg name <text>          "yes" or "no"
//   host_gg b64 <text>           the decoded bytes as hex, or "no"
//   host_gg hex <hex> <cap>      the decoded text as "OK <n> <text>", or "no" (cap = room incl. the NUL)
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <string>
#include <vector>
#include "../c3_player/gg_core.h"

static std::vector<uint8_t> slurp(const char* path) {
  std::vector<uint8_t> v;
  FILE* f = fopen(path, "rb");
  if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(2); }
  uint8_t buf[4096];
  size_t n;
  while ((n = fread(buf, 1, sizeof buf, f)) > 0) v.insert(v.end(), buf, buf + n);
  fclose(f);
  return v;
}

int main(int argc, char** argv) {
  if (argc < 3) return 2;
  std::string cmd = argv[1];
  if (cmd == "lut") {
    uint8_t lut[256];
    gg_make_lut((uint8_t)atoi(argv[2]), (uint8_t)atoi(argv[3]), lut);
    for (int i = 0; i < 256; i++) printf("%d%c", lut[i], i == 255 ? '\n' : ' ');
    return 0;
  }
  if (cmd == "name") { printf("%s\n", gg_name_ok(argv[2]) ? "yes" : "no"); return 0; }
  if (cmd == "b64") {
    std::vector<uint8_t> out(strlen(argv[2]) + 4);
    int n = gg_b64_decode(argv[2], strlen(argv[2]), out.data());
    if (n < 0) { printf("no\n"); return 0; }
    for (int i = 0; i < n; i++) printf("%02x", out[i]);
    printf("\n");
    return 0;
  }
  if (cmd == "hex") {
    char out[256];
    int n = gg_hex_decode(argv[2], out, argc > 3 ? (size_t)atoi(argv[3]) : sizeof out);
    if (n < 0) printf("no\n"); else printf("OK %d %s\n", n, out);
    return 0;
  }
  std::vector<uint8_t> d = slurp(argv[2]);
  if (cmd == "crc") { printf("%08x\n", gg_crc32(0, d.data(), d.size())); return 0; }
  GGHeader h;
  const char* err = gg_parse_header(d.data(), d.size(), &h);
  if (cmd == "hdr") {
    if (err) printf("%s\n", err);
    else printf("OK %d %d %d %d\n", h.frames, h.fps10, h.bright_pct, h.gamma10);
    return 0;
  }
  if (err) { printf("%s\n", err); return 1; }
  uint8_t lut[256];
  gg_make_lut(h.bright_pct, h.gamma10, lut);
  for (int f = 0; f < h.frames; f++) {
    static uint8_t led[GG_PIXELS][3];
    memset(led, 0, sizeof led);
    const uint8_t* px = d.data() + GG_HEADER_SIZE + (size_t)f * GG_FRAME_BYTES;
    for (int y = 0; y < GG_ROWS; y++)
      for (int x = 0; x < GG_COLS; x++) {
        const uint8_t* p = px + (y * GG_COLS + x) * 3;
        int i = gg_led_index(x, y);
        led[i][0] = lut[p[0]]; led[i][1] = lut[p[1]]; led[i][2] = lut[p[2]];
      }
    for (int i = 0; i < GG_PIXELS; i++) printf("%02x%02x%02x", led[i][0], led[i][1], led[i][2]);
    printf("\n");
  }
  return 0;
}
