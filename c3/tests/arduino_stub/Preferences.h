// Stand-in for the ESP32 Preferences (NVS) library: key/value pairs kept in the file named by $GG_NVS, values hex-encoded.
// NVS is separate from the LittleFS sprite flash on the real board, so it is a separate file here too.
#pragma once
#include <Arduino.h>
#include <map>

class Preferences {
  std::map<std::string, std::string> kv;
  bool ro = true, open = false;
  static std::string enc(const std::string& v) { std::string o; char b[3]; for (unsigned char c : v) { snprintf(b, 3, "%02x", c); o += b; } return o; }
  static std::string dec(const std::string& h) { std::string o; if (h == "-") return o; for (size_t i = 0; i + 1 < h.size(); i += 2) o += (char)strtol(h.substr(i, 2).c_str(), NULL, 16); return o; }
  void load() {
    kv.clear();
    const char* p = getenv("GG_NVS");
    FILE* f = p ? fopen(p, "r") : NULL;
    if (!f) return;
    char k[128], v[512];
    while (fscanf(f, "%127s %511s", k, v) == 2) kv[k] = dec(v);
    fclose(f);
  }
  void save() {
    const char* p = getenv("GG_NVS");
    FILE* f = p ? fopen(p, "w") : NULL;
    if (!f) return;
    for (auto& e : kv) fprintf(f, "%s %s\n", e.first.c_str(), e.second.empty() ? "-" : enc(e.second).c_str());
    fclose(f);
  }
 public:
  bool begin(const char*, bool readOnly = false) { ro = readOnly; open = true; load(); return true; }
  void end() { open = false; }
  String getString(const char* key, const char* def = "") { auto it = kv.find(key); return String(it == kv.end() ? def : it->second.c_str()); }
  size_t putString(const char* key, const char* v) { if (ro || !open) return 0; kv[key] = v; save(); return strlen(v); }
  bool remove(const char* key) { if (ro || !open) return false; kv.erase(key); save(); return true; }
};
