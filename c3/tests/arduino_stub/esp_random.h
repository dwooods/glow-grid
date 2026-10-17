// Stand-in for the ESP32 hardware random number generator (esp_random.h). The tests only need it to vary between calls.
#pragma once
#include <stdint.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
inline uint32_t esp_random() {
  static bool seeded = false;
  if (!seeded) { seeded = true; timespec ts; clock_gettime(CLOCK_REALTIME, &ts); srand((unsigned)(ts.tv_nsec ^ ts.tv_sec ^ getpid())); }
  return ((uint32_t)rand() << 16) ^ (uint32_t)rand();
}
