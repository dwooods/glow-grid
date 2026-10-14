// Runs c3_player.ino's setup() and loop() on a PC. Serial is stdin/stdout. Used by tests/test_gg.py.
#include <Arduino.h>
void setup();
void loop();
int main() {
  setup();
  for (;;) {
    loop();
    usleep(300);
  }
}
