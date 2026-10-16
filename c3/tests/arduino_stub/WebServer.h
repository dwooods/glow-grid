// Stand-in for the ESP32 WebServer: a small real HTTP/1.1 server on 127.0.0.1 so the tests can talk to the sketch's routes with
// ordinary HTTP. Same API surface the sketch uses (on, onNotFound, arg, method, upload, send, sendHeader, streamFile, handleClient).
// One request at a time, Connection: close, like the real one. begin() listens on $GG_HTTP_PORT (default: any free port) and writes
// the port it got to the file named by $GG_HTTP_PORT_FILE.
// Like the real core, it parses multipart/form-data and hands each file part to the upload handler in chunks of at most 1436 bytes.
#pragma once
#include <Arduino.h>
#include <LittleFS.h>
#include <functional>
#include <map>
#include <vector>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>

enum HTTPMethod { HTTP_ANY = 0, HTTP_GET, HTTP_POST, HTTP_PUT, HTTP_DELETE, HTTP_OPTIONS, HTTP_HEAD };
enum HTTPUploadStatus { UPLOAD_FILE_START, UPLOAD_FILE_WRITE, UPLOAD_FILE_END, UPLOAD_FILE_ABORTED };
struct HTTPUpload {
  HTTPUploadStatus status;
  String filename, name, type;
  size_t totalSize = 0, currentSize = 0;
  uint8_t buf[1436];
};

class WebServer {
  typedef std::function<void()> Fn;
  struct Route { std::string uri; HTTPMethod method; Fn fn, ufn; };
  std::vector<Route> routes;
  Fn notFound;
  int lfd = -1, cfd = -1;
  HTTPMethod curMethod = HTTP_GET;
  std::string curUri;
  std::map<std::string, std::string> args;
  std::string outHeaders;
  bool responded = false;
  long fixedLen = -1;
  HTTPUpload up;

  static std::string urldecode(const std::string& s) {
    std::string o;
    for (size_t i = 0; i < s.size(); i++) {
      if (s[i] == '+') o += ' ';
      else if (s[i] == '%' && i + 2 < s.size() + 0 && isxdigit((unsigned char)s[i + 1]) && isxdigit((unsigned char)s[i + 2])) { o += (char)strtol(s.substr(i + 1, 2).c_str(), NULL, 16); i += 2; }
      else o += s[i];
    }
    return o;
  }
  void parseQuery(const std::string& q) {
    size_t i = 0;
    while (i <= q.size() && !q.empty()) {
      size_t amp = q.find('&', i);
      std::string kv = q.substr(i, amp == std::string::npos ? std::string::npos : amp - i);
      size_t eq = kv.find('=');
      if (!kv.empty()) args[urldecode(kv.substr(0, eq))] = eq == std::string::npos ? "" : urldecode(kv.substr(eq + 1));
      if (amp == std::string::npos) break;
      i = amp + 1;
    }
  }
  void writeAll(const char* p, size_t n) {
    while (n > 0) { ssize_t w = ::send(cfd, p, n, MSG_NOSIGNAL); if (w <= 0) return; p += w; n -= (size_t)w; }
  }
  static std::string lower(std::string s) { for (auto& c : s) c = (char)tolower((unsigned char)c); return s; }

  void multipart(const std::string& body, const std::string& boundary) {
    std::string delim = "--" + boundary;
    size_t pos = body.find(delim);
    while (pos != std::string::npos) {
      pos += delim.size();
      if (body.compare(pos, 2, "--") == 0) break;
      pos += 2;                                            // CRLF after the boundary
      size_t hend = body.find("\r\n\r\n", pos);
      if (hend == std::string::npos) break;
      std::string heads = body.substr(pos, hend - pos);
      size_t cstart = hend + 4;
      size_t next = body.find("\r\n" + delim, cstart);
      if (next == std::string::npos) break;
      std::string name, filename, type;
      size_t k = heads.find("name=\"");
      if (k != std::string::npos) name = heads.substr(k + 6, heads.find('"', k + 6) - (k + 6));
      k = heads.find("filename=\"");
      bool isFile = k != std::string::npos;
      if (isFile) filename = heads.substr(k + 10, heads.find('"', k + 10) - (k + 10));
      if (!isFile) {
        args[name] = body.substr(cstart, next - cstart);
      } else {
        Route* r = match();
        if (r && r->ufn) {
          size_t total = next - cstart;
          up.name = String(name.c_str()); up.filename = String(filename.c_str()); up.totalSize = 0; up.currentSize = 0;
          up.status = UPLOAD_FILE_START; r->ufn();
          for (size_t off = 0; off < total; off += sizeof(up.buf)) {
            size_t n = total - off < sizeof(up.buf) ? total - off : sizeof(up.buf);
            memcpy(up.buf, body.data() + cstart + off, n);
            up.currentSize = n; up.totalSize += n; up.status = UPLOAD_FILE_WRITE; r->ufn();
          }
          up.currentSize = 0; up.status = UPLOAD_FILE_END; r->ufn();
        }
      }
      pos = next + 2;
    }
  }
  Route* match() {
    for (auto& r : routes) if (r.uri == curUri && (r.method == HTTP_ANY || r.method == curMethod)) return &r;
    return nullptr;
  }

 public:
  explicit WebServer(int = 80) {}
  void on(const char* uri, HTTPMethod m, Fn fn) { routes.push_back({uri, m, fn, nullptr}); }
  void on(const char* uri, HTTPMethod m, Fn fn, Fn ufn) { routes.push_back({uri, m, fn, ufn}); }
  void onNotFound(Fn fn) { notFound = fn; }
  void begin() {
    lfd = socket(AF_INET, SOCK_STREAM, 0);
    int one = 1;
    setsockopt(lfd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    sockaddr_in a = {};
    a.sin_family = AF_INET;
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    const char* want = getenv("GG_HTTP_PORT");
    a.sin_port = htons(want ? atoi(want) : 0);
    if (bind(lfd, (sockaddr*)&a, sizeof a) != 0 || listen(lfd, 4) != 0) { perror("WebServer stub"); exit(3); }
    socklen_t len = sizeof a;
    getsockname(lfd, (sockaddr*)&a, &len);
    fcntl(lfd, F_SETFL, O_NONBLOCK);
    const char* pf = getenv("GG_HTTP_PORT_FILE");
    if (pf) { FILE* f = fopen(pf, "w"); if (f) { fprintf(f, "%d", ntohs(a.sin_port)); fclose(f); } }
  }

  String arg(const char* name) { auto it = args.find(name); return String(it == args.end() ? "" : it->second.c_str()); }
  bool hasArg(const char* name) { return args.count(name) > 0; }
  HTTPMethod method() { return curMethod; }
  String uri() { return String(curUri.c_str()); }
  HTTPUpload& upload() { return up; }
  void sendHeader(const String& n, const String& v, bool = false) { outHeaders += n.s + ": " + v.s + "\r\n"; }
  // Like the real core: setContentLength(n) before send(code, type, "") fixes the Content-Length for a body written with sendContent().
  void setContentLength(size_t n) { fixedLen = (long)n; }
  void sendContent(const char* p, size_t n) { writeAll(p, n); }
  void send(int code, const char* type = NULL, const String& content = String("")) {
    std::string h = "HTTP/1.1 " + std::to_string(code) + " X\r\n";
    if (type) h += std::string("Content-Type: ") + type + "\r\n";
    h += "Content-Length: " + std::to_string(fixedLen >= 0 ? (size_t)fixedLen : content.s.size()) + "\r\nConnection: close\r\n" + outHeaders + "\r\n";
    writeAll(h.data(), h.size());
    writeAll(content.s.data(), content.s.size());
    responded = true;
  }
  size_t streamFile(File& f, const String& type, int code = 200) {
    std::string all;
    uint8_t b[1024];
    size_t r;
    while ((r = f.read(b, sizeof b)) > 0) all.append((char*)b, r);
    std::string h = "HTTP/1.1 " + std::to_string(code) + " X\r\nContent-Type: " + type.s + "\r\nContent-Length: " + std::to_string(all.size()) + "\r\nConnection: close\r\n" + outHeaders + "\r\n";
    writeAll(h.data(), h.size());
    writeAll(all.data(), all.size());
    responded = true;
    return all.size();
  }

  void handleClient() {
    if (lfd < 0) return;
    cfd = accept(lfd, NULL, NULL);
    if (cfd < 0) return;
    timeval tv = {2, 0};
    setsockopt(cfd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof tv);
    std::string req;
    char buf[4096];
    size_t hend = std::string::npos;
    while (hend == std::string::npos) {
      ssize_t n = recv(cfd, buf, sizeof buf, 0);
      if (n <= 0) { close(cfd); cfd = -1; return; }
      req.append(buf, (size_t)n);
      hend = req.find("\r\n\r\n");
    }
    std::string head = req.substr(0, hend), body = req.substr(hend + 4);
    std::map<std::string, std::string> hd;
    size_t eol = head.find("\r\n");
    std::string line = head.substr(0, eol);
    for (size_t p = eol; p != std::string::npos && p < head.size();) {
      size_t q = head.find("\r\n", p + 2);
      std::string l = head.substr(p + 2, q == std::string::npos ? std::string::npos : q - p - 2);
      size_t c = l.find(':');
      if (c != std::string::npos) { std::string v = l.substr(c + 1); while (!v.empty() && v[0] == ' ') v.erase(0, 1); hd[lower(l.substr(0, c))] = v; }
      p = q;
    }
    size_t clen = hd.count("content-length") ? (size_t)atol(hd["content-length"].c_str()) : 0;
    while (body.size() < clen) {
      ssize_t n = recv(cfd, buf, sizeof buf, 0);
      if (n <= 0) break;
      body.append(buf, (size_t)n);
    }
    std::string m = line.substr(0, line.find(' '));
    curMethod = m == "GET" ? HTTP_GET : m == "POST" ? HTTP_POST : m == "OPTIONS" ? HTTP_OPTIONS : m == "PUT" ? HTTP_PUT : m == "DELETE" ? HTTP_DELETE : HTTP_HEAD;
    std::string target = line.substr(line.find(' ') + 1);
    target = target.substr(0, target.find(' '));
    size_t qm = target.find('?');
    curUri = target.substr(0, qm);
    args.clear();
    outHeaders.clear();
    fixedLen = -1;
    responded = false;
    if (qm != std::string::npos) parseQuery(target.substr(qm + 1));
    std::string ct = hd.count("content-type") ? hd["content-type"] : "";
    Route* r = match();
    if (curMethod == HTTP_POST && ct.find("multipart/form-data") == 0) {
      size_t b = ct.find("boundary=");
      if (b != std::string::npos) multipart(body, ct.substr(b + 9));
    } else if (curMethod == HTTP_POST && !body.empty()) {
      args["plain"] = std::string(body.c_str());           // like the real core: a String, so it stops at the first zero byte
    }
    if (r) r->fn();
    else if (notFound) notFound();
    if (!responded) send(500, "text/plain", "no reply\n");
    close(cfd);
    cfd = -1;
  }
};
