// Stand-in for LittleFS, backed by the directory named in $GG_FS_DIR. Capacity is a fixed 1,500,000 bytes.
#pragma once
#include <Arduino.h>
#include <memory>
#include <string>
#include <dirent.h>
#include <sys/stat.h>

class File {
  struct State {
    FILE* fp = nullptr;
    DIR* dir = nullptr;
    std::string path, name;
    bool isDir = false;
    ~State() { if (fp) fclose(fp); if (dir) closedir(dir); }
  };
  std::shared_ptr<State> st;
 public:
  File() {}
  File(std::shared_ptr<State> s) : st(s) {}
  static File make(const std::string& path, const std::string& name, const char* mode) {
    auto s = std::make_shared<State>();
    s->path = path;
    s->name = name;
    struct stat sb;
    if (stat(path.c_str(), &sb) == 0 && S_ISDIR(sb.st_mode)) {
      s->isDir = true;
      s->dir = opendir(path.c_str());
      return s->dir ? File(s) : File();
    }
    s->fp = fopen(path.c_str(), mode[0] == 'w' ? "wb" : "rb");
    return s->fp ? File(s) : File();
  }
  explicit operator bool() const { return (bool)st; }
  size_t read(uint8_t* b, size_t n) { return st && st->fp ? fread(b, 1, n, st->fp) : 0; }
  size_t write(const uint8_t* b, size_t n) { return st && st->fp ? fwrite(b, 1, n, st->fp) : 0; }
  void close() { if (st) { if (st->fp) { fclose(st->fp); st->fp = nullptr; } if (st->dir) { closedir(st->dir); st->dir = nullptr; } } }
  size_t size() {
    struct stat sb;
    if (st && st->fp) fflush(st->fp);
    return st && stat(st->path.c_str(), &sb) == 0 ? (size_t)sb.st_size : 0;
  }
  const char* name() { return st ? st->name.c_str() : ""; }
  // the Stream bits the sketch uses on a File (real Arduino File derives from Stream)
  size_t print(unsigned long v) { if (!st || !st->fp) return 0; return fprintf(st->fp, "%lu", v); }
  size_t print(uint32_t v) { return print((unsigned long)v); }
  long parseInt() { long v = 0; if (st && st->fp && fscanf(st->fp, "%ld", &v) == 1) return v; return 0; }
  bool isDirectory() { return st && st->isDir; }
  File openNextFile() {
    if (!st || !st->dir) return File();
    while (dirent* e = readdir(st->dir)) {
      if (!strcmp(e->d_name, ".") || !strcmp(e->d_name, "..")) continue;
      return make(st->path + "/" + e->d_name, e->d_name, "r");
    }
    return File();
  }
};

class LittleFSStub {
  std::string real(const String& p) const {
    const char* d = getenv("GG_FS_DIR");
    return std::string(d ? d : ".") + (p.s == "/" ? "" : p.s);
  }
 public:
  bool begin(bool = false) { return getenv("GG_FS_DIR") != nullptr; }
  File open(const String& path, const char* mode = "r") { return File::make(real(path), path.s, mode); }
  bool exists(const String& path) { struct stat sb; return stat(real(path).c_str(), &sb) == 0; }
  bool remove(const String& path) { return ::remove(real(path).c_str()) == 0; }
  bool rename(const String& a, const String& b) { return ::rename(real(a).c_str(), real(b).c_str()) == 0; }
  size_t totalBytes() { return 1500000; }
  size_t usedBytes() {
    size_t sum = 0;
    const char* d = getenv("GG_FS_DIR");
    DIR* dir = d ? opendir(d) : nullptr;
    if (!dir) return 0;
    while (dirent* e = readdir(dir)) {
      struct stat sb;
      std::string p = std::string(d) + "/" + e->d_name;
      if (stat(p.c_str(), &sb) == 0 && S_ISREG(sb.st_mode)) sum += (size_t)sb.st_size;
    }
    closedir(dir);
    return sum;
  }
};
static LittleFSStub LittleFS;
