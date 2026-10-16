// The Board card: talk to the ESP32-C3 player from the editor. Classic script (load order in index.html).
//
// Two ways to reach the board; the card above them does not know which one it has:
//   * USB: SerialTransport (Web Serial, Chrome and Edge on a computer; tests pass a fake one) carries the text lines, and
//       GgBoard speaks the line protocol c3/c3_player.ino answers (PING, LIST, PUT, DEL, SHOW, OFF, ON, ROTATE, INFO, CRC, GET),
//       the same one c3/tools/gg_tool.py uses. It also sets the board's Wi-Fi (WIFI SET), which only works over USB.
//   * Wi-Fi: HttpBoard calls the board's HTTP API with fetch (firmware 9 and later). Any browser that lets the page reach the board.
// The card lists what is on the board, sends the current drawing as a .gg sprite (the bytes ggBytes() makes,
// same as Export for ESP32-C3), plays or deletes a stored sprite, and turns the panel off and on.

const BOARD_BAUD = 115200;
const BOARD_PAGE = 5;                // rows per page in the list
const BOARD_MAX_SPRITES = 64;        // the firmware's MAX_SPRITES
const BOARD_CRC_FW = 7;              // the first firmware with the CRC command (Remove examples needs it)
const BOARD_GET_FW = 8;              // the first firmware with the GET command (Load needs it)
const BOARD_CHUNK = 1024;            // the firmware answers "A" after every 1024 bytes of a PUT

class SerialTransport {
  constructor(port) { this.port = port; this.onLine = null; this.onClose = null; this.buf = ''; this.writer = null; this.reader = null; this.closed = false; }
  async open() {
    await this.port.open({ baudRate: BOARD_BAUD });
    // The C3's native USB port only takes data while DTR is asserted; DTR on with RTS off is plain "connected", not a reset.
    try { await this.port.setSignals({ dataTerminalReady: true, requestToSend: false }); } catch (e) { /* some adapters have no control lines */ }
    this.writer = this.port.writable.getWriter();
    this.readLoop();
  }
  async readLoop() {
    const dec = new TextDecoder();
    try {
      this.reader = this.port.readable.getReader();
      for (;;) {
        const { value, done } = await this.reader.read();
        if (done) break;
        this.buf += dec.decode(value, { stream: true });
        let nl;
        while ((nl = this.buf.indexOf('\n')) >= 0) {
          const line = this.buf.slice(0, nl).replace(/\r$/, '');
          this.buf = this.buf.slice(nl + 1);
          if (line && this.onLine) this.onLine(line);
        }
      }
    } catch (e) { /* read error: the device was unplugged; fall through to close */ }
    finally {
      try { if (this.reader) this.reader.releaseLock(); } catch (e) { /* already released */ }
      this.reader = null;
      this.close();
    }
  }
  async write(bytes) { await this.writer.write(bytes); }
  // Web Serial refuses to close a port while either stream is locked, so cancel the reader (which ends readLoop)
  // and release the writer first. Getting this wrong leaves the COM port held until the tab is closed (2026-10-15).
  async close() {
    if (this.closed) return;
    this.closed = true;
    try { if (this.reader) { await this.reader.cancel(); this.reader.releaseLock(); } } catch (e) { /* already gone */ }
    this.reader = null;
    try { if (this.writer) { await this.writer.close(); } } catch (e) { /* already gone */ }
    try { if (this.writer) this.writer.releaseLock(); } catch (e) { /* already released */ }
    this.writer = null;
    try { await this.port.close(); } catch (e) { console.warn('port.close failed', e); }
    if (this.onClose) this.onClose();
  }
}

class GgBoard {
  constructor(transport) {
    this.t = transport;
    this.waiters = [];                 // {prefixes, resolve, reject, timer}
    this.log = [];
    transport.onLine = (line) => this.gotLine(line);
    const prevClose = transport.onClose;
    transport.onClose = () => { this.dropAll('Board disconnected'); if (prevClose) prevClose(); };
  }
  dropAll(why) {                      // the link is gone: every waiting command fails now, not at its timeout
    const ws = this.waiters; this.waiters = [];
    for (const w of ws) { clearTimeout(w.timer); w.reject(new Error(why)); }
  }
  gotLine(line) {
    this.log.push(line); if (this.log.length > 50) this.log.shift();
    const w = this.waiters[0];
    if (!w) return;
    if (line.startsWith('ERR')) { this.waiters.shift(); clearTimeout(w.timer); w.reject(new Error(line.replace(/^ERR\s*/, ''))); return; }
    if (w.prefixes.some((p) => line.startsWith(p))) { this.waiters.shift(); clearTimeout(w.timer); w.resolve(line); }
    else if (w.collect) w.collect.push(line);
  }
  expect(prefixes, ms, collect) {
    return new Promise((resolve, reject) => {
      const w = { prefixes, resolve, reject, collect };
      w.timer = setTimeout(() => { const i = this.waiters.indexOf(w); if (i >= 0) this.waiters.splice(i, 1); reject(new Error('no reply from the board')); }, ms);
      this.waiters.push(w);
    });
  }
  async send(text) { await this.t.write(new TextEncoder().encode(text + '\n')); }
  async cmd(text, prefixes, ms, collect) { const p = this.expect(prefixes, ms || 4000, collect); await this.send(text); return p; }
  async ping() { return this.cmd('PING', ['PONG'], 1500); }
  async hello() {                      // a few tries: the board may still be printing its boot line
    for (let i = 0; i < 4; i++) { try { return await this.ping(); } catch (e) { if (i === 3) throw new Error('the board did not answer. Is it running the Glow Grid player?'); } }
  }
  async list() {
    const files = [];
    const summary = await this.cmd('LIST', ['OK'], 4000, files);
    const m = /^OK (\d+) files?, (\d+) bytes free/.exec(summary);
    return { files: files.filter((l) => l.startsWith('FILE ')).map((l) => { const [, name, size] = l.split(' '); return { name, size: Number(size) }; }), free: m ? Number(m[2]) : null };
  }
  async info() {
    const line = await this.cmd('INFO', ['OK']);
    const out = {};
    line.replace(/(\w+)=(\S+)/g, (_, k, v) => { out[k] = v; return ''; });
    return out;
  }
  async put(name, bytes, onProgress) {
    const crc = crc32(bytes).toString(16).padStart(8, '0');
    await this.cmd(`PUT ${name} ${bytes.length} ${crc}`, ['READY']);
    for (let pos = 0; pos < bytes.length; pos += BOARD_CHUNK) {
      const chunk = bytes.subarray(pos, pos + BOARD_CHUNK);
      const last = pos + chunk.length >= bytes.length;
      const ack = last ? this.expect(['OK'], 10000) : this.expect(['A'], 5000);
      await this.t.write(chunk);
      await ack;
      if (onProgress) onProgress(Math.min(pos + chunk.length, bytes.length), bytes.length);
    }
  }
  async show(name) { return this.cmd(`SHOW ${name}`, ['OK']); }
  async del(name) { return this.cmd(`DEL ${name}`, ['OK']); }
  async off() { return this.cmd('OFF', ['OK']); }
  async on() { return this.cmd('ON', ['OK']); }
  async rotate(sec) { return this.cmd(`ROTATE ${sec}`, ['OK']); }
  async crc(name) {                   // checksum and size of the file stored under `name` (firmware 7 and later)
    const line = await this.cmd(`CRC ${name}`, ['OK']);
    const m = /crc=([0-9a-f]{8}) size=(\d+)/.exec(line);
    if (!m) throw new Error(`unexpected reply: ${line}`);
    return { crc: m[1], size: Number(m[2]) };
  }
  async get(name) {                   // the stored file as bytes, read back as hex lines and checked against the board's own CRC (firmware 8 and later)
    const lines = [];
    const end = await this.cmd(`GET ${name}`, ['OK'], 20000, lines);
    const hex = lines.filter((l) => l.startsWith('D ')).map((l) => l.slice(2).trim()).join('');
    const m = /crc=([0-9a-f]{8}) size=(\d+)/.exec(end);
    if (!m || hex.length % 2) throw new Error(`unexpected reply: ${end}`);
    const bytes = new Uint8Array(hex.length / 2);
    for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(hex.substr(2 * i, 2), 16);
    if (bytes.length !== Number(m[2]) || crc32(bytes).toString(16).padStart(8, '0') !== m[1]) throw new Error('the sprite came through damaged; try Load again');
    return bytes;
  }
  async wifiStatus() {                // firmware 9 and later: "OK wifi=connected ip=192.168.1.50 rssi=-40 host=glowgrid.local ssid=<name>"
    const line = await this.cmd('WIFI STATUS', ['OK']);
    const m = /wifi=(\w+) ip=(\S+)/.exec(line);
    if (!m) throw new Error(`unexpected reply: ${line}`);
    return { state: m[1], ip: m[2] === '-' ? '' : m[2] };
  }
  // The name and password go as hex, so spaces and symbols survive the command line. The password is never echoed by the board.
  async wifiSet(ssid, password) {
    const hex = (s) => Array.from(new TextEncoder().encode(s), (b) => b.toString(16).padStart(2, '0')).join('');
    return this.cmd(`WIFI SET ${hex(ssid)} ${password ? hex(password) : '-'}`, ['OK']);
  }
  async wifiScan() {                  // firmware 10 and later: NET <name hex> <rssi> <1 = needs a password> lines, then "OK networks=<n>"
    const lines = [];
    await this.cmd('WIFI SCAN', ['OK'], 15000, lines);
    return lines.filter((l) => l.startsWith('NET ')).map((l) => {
      const [, h, rssi, sec] = l.split(' ');
      const bytes = new Uint8Array((h || '').match(/../g).map((x) => parseInt(x, 16)));
      return { ssid: new TextDecoder().decode(bytes), rssi: Number(rssi), secure: sec === '1' };
    });
  }
  async wifiClear() { return this.cmd('WIFI CLEAR', ['OK']); }
  async close() { await this.t.close(); }
}

// The same operations as GgBoard, over Wi-Fi (firmware 9 and later; the HTTP API in c3/README.md). The replies are the same
// OK / ERR text as USB, so the card above cannot tell the two apart. There is no connection to lose: close() only forgets it.
class HttpBoard {
  constructor(host) {
    this.host = host;
    this.base = 'http://' + host;
    this.onClose = null; this.closed = false;
    this.via = 'wifi';
  }
  async call(method, path, body, ms, asBytes) {
    const ac = new AbortController();
    const timer = setTimeout(() => ac.abort(), ms || 6000);
    let res;
    try { res = await fetch(this.base + path, { method, body, signal: ac.signal }); }
    catch (e) {
      throw new Error(e && e.name === 'AbortError' ? `no reply from the board at ${this.host}`
        : `cannot reach the board at ${this.host}. Is it on the same Wi-Fi as this device, and did the browser allow this page to reach devices on your network?`);
    } finally { clearTimeout(timer); }
    if (!res.ok) { const t = (await res.text()).trim(); throw new Error(t.replace(/^ERR\s*/, '') || `HTTP ${res.status}`); }
    return asBytes ? new Uint8Array(await res.arrayBuffer()) : (await res.text()).trim();
  }
  async ping() { return this.call('GET', '/ping', null, 3000); }
  async hello() {
    let last;
    for (let i = 0; i < 2; i++) { try { return await this.ping(); } catch (e) { last = e; } }
    throw last;
  }
  async list() {
    const files = []; let summary = '';
    for (const l of (await this.call('GET', '/list')).split('\n')) {
      if (l.startsWith('FILE ')) { const [, name, size] = l.split(' '); files.push({ name, size: Number(size) }); }
      else if (l.startsWith('OK')) summary = l;
    }
    const m = /^OK (\d+) files?, (\d+) bytes free/.exec(summary);
    return { files, free: m ? Number(m[2]) : null };
  }
  async info() {
    const out = {};
    (await this.call('GET', '/info')).replace(/(\w+)=(\S+)/g, (_, k, v) => { out[k] = v; return ''; });
    return out;
  }
  async put(name, bytes, onProgress) {
    const crc = crc32(bytes).toString(16).padStart(8, '0');
    const fd = new FormData();                       // multipart, not a raw body: the board's web server cuts a raw body at the first zero byte
    fd.append('file', new Blob([bytes]), name + '.gg');
    if (onProgress) onProgress(0, bytes.length);
    await this.call('POST', `/put?name=${encodeURIComponent(name)}&size=${bytes.length}&crc=${crc}`, fd, 30000);
    if (onProgress) onProgress(bytes.length, bytes.length);
  }
  async show(name) { return this.call('POST', `/show?name=${encodeURIComponent(name)}`); }
  async del(name) { return this.call('POST', `/del?name=${encodeURIComponent(name)}`); }
  async off() { return this.call('POST', '/off'); }
  async on() { return this.call('POST', '/on'); }
  async rotate(sec) { return this.call('POST', `/rotate?s=${encodeURIComponent(sec)}`); }
  async crc(name) {
    const line = await this.call('GET', `/crc?name=${encodeURIComponent(name)}`);
    const m = /crc=([0-9a-f]{8}) size=(\d+)/.exec(line);
    if (!m) throw new Error(`unexpected reply: ${line}`);
    return { crc: m[1], size: Number(m[2]) };
  }
  async get(name) {                                   // the file's bytes, checked against the board's own CRC
    const bytes = await this.call('GET', `/get?name=${encodeURIComponent(name)}`, null, 20000, true);
    const want = await this.crc(name);
    if (bytes.length !== want.size || crc32(bytes).toString(16).padStart(8, '0') !== want.crc) throw new Error('the sprite came through damaged; try Load again');
    return bytes;
  }
  async close() { if (this.closed) return; this.closed = true; if (this.onClose) this.onClose(); }
}

/* ---------- the shipped example sprites (web/js/examples_data.js, generated from examples/sprites.py) ---------- */
function ggExampleBytes(ex) {         // exactly the bytes File ▸ Export for ESP32-C3 would write for this drawing
  const frames = ex.frames.map((f) => Array.from(f, (ch) => ex.palette[ch]));
  return ggBytes(frames, 16, 16, ex.fps, GG_EXAMPLE_BRIGHTNESS, GG_EXAMPLE_GAMMA);
}
const ggExampleCrc = (ex) => crc32(ggExampleBytes(ex)).toString(16).padStart(8, '0');


/* ---------- the card ---------- */
let board = null;
let boardFw = '';                  // from INFO fw=; '' means a build older than the version field
let boardNames = [];               // what the board listed last, so Send can warn before replacing one
let boardFiles = [];               // the last LIST, in the board's order; the pager slices this
let boardPage = 0;                 // 0-based page of the list
let boardCurrent = '';             // the sprite playing, from INFO
let boardVia = '';                 // 'usb' or 'wifi' while connected
let boardInfo = {};                // the last INFO, parsed (the Network dialog shows the board's Wi-Fi state from it)
const boardSupported = () => !!(window.__ggFakeSerial || navigator.serial);       // USB (Web Serial)
const BOARD_WIFI_FW = 9;           // the first firmware with Wi-Fi
const BOARD_SCAN_FW = 10;          // the first firmware that can list nearby networks (WIFI SCAN)
const BOARD_HOST_KEY = 'ggBoardHost';
const BOARD_HOST_DEFAULT = 'glowgrid.local';
function boardSavedHost() { try { return localStorage.getItem(BOARD_HOST_KEY) || BOARD_HOST_DEFAULT; } catch (e) { return BOARD_HOST_DEFAULT; } }
function boardSaveHost(h) { try { localStorage.setItem(BOARD_HOST_KEY, h); } catch (e) { /* private window: just forget it */ } }
// Accepts glowgrid.local, 192.168.1.50, or either with http:// or a trailing slash pasted in. Returns '' for something that cannot be an address.
function boardCleanHost(raw) {
  const h = String(raw || '').trim().replace(/^https?:\/\//i, '').replace(/\/.*$/, '');
  return /^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:\d{1,5})?$/.test(h) ? h : '';
}

function boardSay(msg, kind) {
  const el = $('boardStatus'); el.textContent = msg || ''; el.dataset.kind = kind || '';
}
function boardUi(connected) {
  $('boardConnectBtn').hidden = connected;
  $('boardWifiBtn').hidden = connected;
  if (!connected) { boardVia = ''; boardInfo = {}; $('boardLink').textContent = ''; }
  $('boardDisconnectBtn').hidden = !connected;
  $('boardTools').hidden = !connected;
  $('boardExamples').hidden = !connected;
  $('boardList').hidden = !connected;
  if (!connected) { $('boardList').innerHTML = ''; boardNames = []; boardFiles = []; boardPage = 0; $('boardPager').hidden = true; $('boardFree').textContent = ''; }
}
function boardSendName() { return safeName().slice(0, 31); }
function boardShowRotate(sec) {       // the select shows the board's own setting; an unlisted value gets its own entry
  const sel = $('boardRotate');
  const v = String(parseInt(sec, 10) || 0);
  if (!Array.from(sel.options).some((o) => o.value === v)) { const o = document.createElement('option'); o.value = v; o.textContent = `every ${v} s`; sel.appendChild(o); }
  sel.value = v;
  sel.disabled = false;
}
async function boardRefresh(showName) {            // showName: jump to the page holding this sprite (after a Send)
  if (!board) return;
  const [{ files, free }, info] = [await board.list(), await board.info()];
  boardFiles = files; boardCurrent = info.current || '';
  boardInfo = info;
  $('boardLink').textContent = boardVia === 'wifi' ? `· Wi-Fi ${board.host}` : boardVia === 'usb' ? '· USB' : '';
  boardFw = info.fw || '';           // before the list is drawn: Load greys itself out on a firmware without GET
  boardNames = files.map((f) => f.name);
  if (showName && boardNames.includes(showName)) boardPage = Math.floor(boardNames.indexOf(showName) / BOARD_PAGE);
  boardRenderList();
  $('boardFree').textContent = free == null ? '' : `${(free / 1024).toFixed(0)} KB free`;
  $('boardOnBtn').disabled = info.panel !== 'off';
  $('boardOffBtn').disabled = info.panel === 'off';
  boardShowRotate(info.rotate);
}
function boardRenderList() {
  const files = boardFiles;
  const pages = Math.max(1, Math.ceil(files.length / BOARD_PAGE));
  boardPage = Math.min(Math.max(boardPage, 0), pages - 1);     // a delete can leave the last page empty
  const ul = $('boardList'); ul.innerHTML = '';
  if (!files.length) { const li = document.createElement('li'); li.className = 'hint'; li.textContent = 'Nothing stored yet. Draw something and press Send to board, or Add examples.'; ul.appendChild(li); }
  for (const f of files.slice(boardPage * BOARD_PAGE, (boardPage + 1) * BOARD_PAGE)) {
    const li = document.createElement('li');
    const playing = boardCurrent === f.name;
    li.className = 'board-row' + (playing ? ' playing' : '');
    const nm = document.createElement('span'); nm.className = 'board-name'; nm.textContent = f.name;
    const sz = document.createElement('small'); sz.textContent = `${(f.size / 1024).toFixed(1)} KB` + (playing ? ' · playing' : '');
    const load = document.createElement('button'); load.type = 'button'; load.className = 'btn btn-quiet'; load.textContent = 'Load';
    const canGet = Number(boardFw) >= BOARD_GET_FW;
    load.disabled = !canGet;
    load.title = canGet ? 'Put this sprite in the editor grid to change it' : `Load needs firmware ${BOARD_GET_FW} or later (this board has ${boardFw || 'an older one'}). Re-flash c3_player.ino from the repo.`;
    load.addEventListener('click', () => boardLoad(f.name));
    const play = document.createElement('button'); play.type = 'button'; play.className = 'btn btn-quiet'; play.textContent = 'Play';
    play.disabled = playing;
    play.addEventListener('click', () => boardAct(() => board.show(f.name), `Playing ${f.name}.`));
    const del = document.createElement('button'); del.type = 'button'; del.className = 'btn btn-quiet danger'; del.textContent = 'Delete';
    del.addEventListener('click', () => { if (confirm(`Delete ${f.name} from the board? This cannot be undone.`)) boardAct(() => board.del(f.name), `Deleted ${f.name}.`); });
    li.append(nm, sz, load, play, del);
    ul.appendChild(li);
  }
  $('boardPager').hidden = files.length <= BOARD_PAGE;
  $('boardPageInfo').textContent = `${boardPage * BOARD_PAGE + 1}–${Math.min((boardPage + 1) * BOARD_PAGE, files.length)} of ${files.length}`;
  $('boardPrevBtn').disabled = boardPage <= 0;
  $('boardNextBtn').disabled = boardPage >= pages - 1;
}
async function boardLoad(name) {       // read the sprite back from the board into the editor grid
  if (!board) return;
  boardBusy(true);
  try {
    boardSay(`Reading ${name} from the board…`, '');
    const d = ggDecode(await board.get(name));
    if (!needsReplaceOk()) { boardSay('Not loaded.', ''); return; }
    loadGgSprite(d, name, 'the board');
    boardSay(`Loaded ${name} into the editor. Change it, then Send to board (the Export name is now “${name}”, so Send replaces it).`, 'ok');
  } catch (err) { if (board) boardSay(`Could not load ${name}: ${err.message}`, 'err'); }
  finally { boardBusy(false); }
}
async function boardAct(fn, doneMsg) {
  if (!board) return;
  try { await fn(); boardSay(doneMsg, 'ok'); await boardRefresh(); }
  catch (err) { if (board) boardSay(`Board said: ${err.message}`, 'err'); }
}
async function boardConnect() {
  if (!boardSupported()) { boardSay('USB needs Chrome or Edge on a computer. Use Connect over Wi-Fi, or export a .gg file.', 'err'); return; }
  let transport;
  try {
    if (window.__ggFakeSerial) transport = window.__ggFakeSerial();
    else {
      const port = await navigator.serial.requestPort({ filters: [{ usbVendorId: 0x303a }] });
      transport = new SerialTransport(port);
    }
    transport.onClose = () => { board = null; boardUi(false); boardSay('Board disconnected.', ''); netSync(); };
    await transport.open();
  } catch (err) {
    boardSay(err && err.name === 'NotFoundError' ? 'No board chosen.' : `Could not open the port: ${err.message}. Close the Arduino Serial Monitor or any other program using it.`, 'err');
    return;
  }
  const b = new GgBoard(transport);
  b.via = 'usb';
  try { await b.hello(); } catch (err) { boardSay(err.message, 'err'); await transport.close(); return; }
  await boardAttach(b);
}
async function boardConnectWifi(rawHost) {
  const host = boardCleanHost(rawHost || boardSavedHost());
  if (!host) { boardSay('That does not look like a board address. Use glowgrid.local or the IP address, like 192.168.1.50.', 'err'); return false; }
  const b = new HttpBoard(host);
  boardSay(`Looking for the board at ${host}…`, '');
  $('boardWifiBtn').disabled = true;
  try { await b.hello(); }
  catch (err) { boardSay(`${err.message} The Network button at the top sets the address.`, 'err'); return false; }
  finally { $('boardWifiBtn').disabled = false; }
  b.onClose = () => { board = null; boardUi(false); boardSay('Board disconnected.', ''); netSync(); };
  boardSaveHost(host);
  await boardAttach(b);
  return true;
}
async function boardAttach(b) {
  board = b; boardVia = b.via;
  boardUi(true);
  try {
    await boardRefresh();
    const fwNote = boardFw ? `Firmware ${boardFw}.` : 'Firmware older than 3 (re-flash from the repo).';
    boardSay(`Connected${b.via === 'wifi' ? ` over Wi-Fi (${b.host})` : ''}. ${fwNote}` + (b.via === 'wifi' && Number(boardFw) && Number(boardFw) < BOARD_WIFI_FW ? ' (Wi-Fi needs firmware 9, so this will not last.)' : ''), 'ok');
  } catch (err) { boardSay(`Board said: ${err.message}`, 'err'); }
  netSync();
}
async function boardSend() {
  if (!board) return;
  const n = state.frames.length;
  if (state.cols !== 16 || state.rows !== 16) { boardSay(`The C3 player is 16×16; this picture is ${state.cols}×${state.rows}.`, 'err'); return; }
  if (n > GG_MAX_FRAMES) { boardSay(`The C3 player takes up to ${GG_MAX_FRAMES} frames; this has ${n}.`, 'err'); return; }
  const flat = state.frames.map(flatten);
  if (flat.every((f) => f.every((h) => h === '#000000'))) { boardSay('The drawing is blank; nothing sent. Draw something or File ▸ Import image first.', 'err'); return; }
  let bytes;
  try { bytes = ggBytes(flat, state.cols, state.rows, state.fps, sim.brightness, sim.gamma); }
  catch (err) { boardSay(`Can’t send: ${err.message}.`, 'err'); return; }
  const name = boardSendName();
  if (boardNames.includes(name) && !confirm(`Replace “${name}” on the board? The old sprite is lost.`)) { boardSay('Not sent.', ''); return; }
  const btn = $('boardSendBtn'); btn.disabled = true;
  try {
    boardSay(`Sending ${name}…`, '');
    await board.put(name, bytes, (done, total) => boardSay(`Sending ${name}… ${Math.round(100 * done / total)}%`, ''));
    boardSay(`Sent ${name} (${n} frame${n === 1 ? '' : 's'}, ${bytes.length.toLocaleString()} bytes). It is playing now.`, 'ok');
    await boardRefresh(name);
  } catch (err) { if (board) boardSay(`Board said: ${err.message}`, 'err'); }   // after an unplug the card already says so
  finally { btn.disabled = false; }
}
// Add examples: store every shipped example the board does not already have. Never replaces anything, so a sprite of
// yours that happens to share an example's name is left alone. Remove examples: delete only the examples that are
// still byte-for-byte what we shipped (checked with the board's CRC command); anything changed is kept and reported.
async function boardAddExamples() {
  if (!board) return;
  const have = new Set(boardNames);
  const todo = GG_EXAMPLES.filter((e) => !have.has(e.name));
  const there = GG_EXAMPLES.length - todo.length;
  if (!todo.length) { boardSay(`All ${GG_EXAMPLES.length} examples are already on the board.`, 'ok'); return; }
  if (boardNames.length + todo.length > BOARD_MAX_SPRITES) {
    boardSay(`The board holds ${BOARD_MAX_SPRITES} sprites and has ${boardNames.length}; adding ${todo.length} examples would not fit. Delete some first. Nothing was sent.`, 'err'); return;
  }
  boardBusy(true);
  let sent = 0, before = '';
  try {
    before = (await board.info()).current || '';       // ask now: the board's own button may have changed it since the last refresh
    for (const e of todo) {
      const bytes = ggExampleBytes(e);
      boardSay(`Adding examples… ${sent + 1} of ${todo.length} (${e.name})`, '');
      await board.put(e.name, bytes);
      sent++;
    }
    if (before && before !== '-') { try { await board.show(before); } catch (err) { /* the old sprite is gone: leave the last example playing */ } }
    boardSay(`Added ${sent} example${sent === 1 ? '' : 's'}` + (there ? `; ${there} already on the board were left alone` : '') + '.', 'ok');
    await boardRefresh();
  } catch (err) {
    if (board) { boardSay(`Board said: ${err.message}. Added ${sent} of ${todo.length}.`, 'err'); try { await boardRefresh(); } catch (e2) { /* link is gone */ } }
  } finally { boardBusy(false); }
}
async function boardRemoveExamples() {
  if (!board) return;
  const mine = GG_EXAMPLES.filter((e) => boardNames.includes(e.name));
  if (!mine.length) { boardSay('No examples are on the board.', 'ok'); return; }
  if (!(Number(boardFw) >= BOARD_CRC_FW)) { boardSay(`Remove examples needs firmware ${BOARD_CRC_FW} or later (this board has ${boardFw || 'an older one'}), so it can tell your own sprites from the examples. Re-flash c3_player.ino from the repo.`, 'err'); return; }
  if (!confirm(`Remove ${mine.length} example sprite${mine.length === 1 ? '' : 's'} from the board? Any you changed are kept.`)) { boardSay('Nothing removed.', ''); return; }
  boardBusy(true);
  const removed = [], kept = [];
  try {
    for (const e of mine) {
      boardSay(`Removing examples… ${removed.length + kept.length + 1} of ${mine.length}`, '');
      const got = await board.crc(e.name);
      if (got.crc === ggExampleCrc(e) && got.size === ggExampleBytes(e).length) { await board.del(e.name); removed.push(e.name); }
      else kept.push(e.name);
    }
    boardSay(`Removed ${removed.length} example${removed.length === 1 ? '' : 's'}.` + (kept.length ? ` Kept ${kept.length} you changed: ${kept.join(', ')}.` : ''), 'ok');
    await boardRefresh();
  } catch (err) {
    if (board) { boardSay(`Board said: ${err.message}. Removed ${removed.length} of ${mine.length}.`, 'err'); try { await boardRefresh(); } catch (e2) { /* link is gone */ } }
  } finally { boardBusy(false); }
}
function boardBusy(on) { for (const id of ['boardAddExBtn', 'boardRemoveExBtn', 'boardSendBtn']) $(id).disabled = on; }
$('boardAddExBtn').addEventListener('click', boardAddExamples);
$('boardRemoveExBtn').addEventListener('click', boardRemoveExamples);
$('boardPrevBtn').addEventListener('click', () => { boardPage--; boardRenderList(); });
$('boardNextBtn').addEventListener('click', () => { boardPage++; boardRenderList(); });
$('boardConnectBtn').addEventListener('click', boardConnect);
$('boardWifiBtn').addEventListener('click', () => boardConnectWifi());
$('boardDisconnectBtn').addEventListener('click', async () => { if (board) await board.close(); });
$('boardSendBtn').addEventListener('click', boardSend);
$('boardOnBtn').addEventListener('click', () => boardAct(() => board.on(), 'Lights on.'));
$('boardOffBtn').addEventListener('click', () => boardAct(() => board.off(), 'Lights off. The panel stays dark until Lights on, even after a power cycle.'));
$('boardRotate').addEventListener('change', () => {
  const sec = Number($('boardRotate').value);
  const label = $('boardRotate').selectedOptions[0].textContent;
  boardAct(() => board.rotate(sec), sec ? `Rotating ${label}. Each sprite keeps playing for the whole interval; the board remembers this after a power cycle.` : 'Rotation off; the board stays on one sprite.');
});
$('boardRefreshBtn').addEventListener('click', () => boardAct(async () => {}, 'List refreshed.'));
boardUi(false);
if (!boardSupported()) {            // Firefox, Safari, iPhone: no Web Serial. USB is greyed out with the reason; Wi-Fi still works.
  $('boardUnsupported').hidden = false;
  $('boardConnectBtn').disabled = true;
  $('boardConnectBtn').title = 'USB needs Chrome or Edge on a computer';
}
if (navigator.serial) navigator.serial.addEventListener('disconnect', () => { if (board) board.close(); });

/* ---------- the Network dialog: the board's address, and setting its Wi-Fi over USB ---------- */
const netDlg = $('netDlg');
function netSay(msg, kind) { const el = $('netStatus'); el.textContent = msg || ''; el.dataset.kind = kind || ''; }
function netSync() {                  // enable the Wi-Fi setup form only while a firmware-9 board is on USB, and show what it reports
  const usb = !!board && boardVia === 'usb';
  const fw9 = usb && Number(boardFw) >= BOARD_WIFI_FW;
  for (const id of ['netSsid', 'netPass', 'netSaveBtn', 'netClearBtn']) $(id).disabled = !fw9;
  const canScan = usb && Number(boardFw) >= BOARD_SCAN_FW;
  $('netScanBtn').disabled = !canScan;
  $('netPick').disabled = !canScan || $('netPick').options.length < 2;
  $('netScanRow').hidden = !fw9;
  $('netScanHint').textContent = fw9 && !canScan ? `Scanning needs firmware ${BOARD_SCAN_FW} (this board has ${boardFw}). Type the name below, or re-flash c3_player.ino.` : '';
  $('netConnectBtn').disabled = !!board && boardVia === 'wifi';
  $('netSetupHint').textContent = !board ? 'Connect the board over USB first (the Board card, Connect over USB). Then its Wi-Fi can be set here.'
    : boardVia === 'wifi' ? 'The board is connected over Wi-Fi. To change its network, disconnect and connect it over USB.'
    : !fw9 ? `Wi-Fi needs firmware ${BOARD_WIFI_FW} or later (this board has ${boardFw || 'an older one'}). Re-flash c3_player.ino from the repo.`
    : '2.4 GHz networks only. The name and password are stored on the board, not in this page.';
}
function netOpen() {
  $('netHost').value = boardSavedHost();
  netSay('', '');
  netSync();
  if (board && boardVia === 'usb' && boardInfo.wifi) netSay(`Board Wi-Fi: ${boardInfo.wifi}` + (boardInfo.ip && boardInfo.ip !== '-' ? `, address ${boardInfo.ip}` : '') + '.', '');
  if (netDlg.showModal) netDlg.showModal(); else netDlg.setAttribute('open', '');
}
async function netConnect() {
  const host = boardCleanHost($('netHost').value);
  if (!host) { netSay('That does not look like an address. Use glowgrid.local or the IP address, like 192.168.1.50.', 'err'); return; }
  $('netConnectBtn').disabled = true;
  netSay(`Looking for the board at ${host}…`, '');
  const ok = await boardConnectWifi(host);
  if (ok) netDlg.close(); else netSay($('boardStatus').textContent, 'err');
  netSync();
}
async function netSave() {
  const ssid = $('netSsid').value, pass = $('netPass').value;
  const n = new TextEncoder().encode(ssid).length;
  if (n < 1 || n > 32) { netSay('The network name must be 1 to 32 characters.', 'err'); return; }
  if (pass && (pass.length < 8 || pass.length > 63)) { netSay('A password is 8 to 63 characters. Leave it empty for an open network.', 'err'); return; }
  if (!board || boardVia !== 'usb') { netSay('The board is not connected over USB.', 'err'); return; }
  const b = board;
  $('netSaveBtn').disabled = true;
  try {
    netSay(`Saving ${ssid} to the board…`, '');
    await b.wifiSet(ssid, pass);
    $('netPass').value = '';
    let st = { state: '', ip: '' };
    for (let i = 0; i < 12 && board === b; i++) {
      await new Promise((r) => setTimeout(r, NET_POLL_MS));
      st = await b.wifiStatus();
      if (st.state === 'connected') break;
    }
    if (st.state === 'connected') netSay(`Joined ${ssid}. The board's address is ${st.ip} (or glowgrid.local). You can unplug USB, power the board, then Connect over Wi-Fi.`, 'ok');
    else netSay(`Saved, but the board has not joined yet (${st.state || 'no answer'}). Check the name and password, and that it is a 2.4 GHz network.`, 'err');
  } catch (err) { if (board) netSay(`Board said: ${err.message}`, 'err'); }
  finally { netSync(); }
}
async function netScan() {
  if (!board || boardVia !== 'usb') return;
  const b = board, pick = $('netPick');
  $('netScanBtn').disabled = true;
  netSay('Scanning… the panel pauses for a few seconds.', '');
  try {
    const nets = await b.wifiScan();
    pick.replaceChildren(new Option(nets.length ? 'Choose a network…' : 'No networks found', ''));
    for (const n of nets) {
      const o = new Option(`${n.ssid}  (${n.rssi} dBm, ${n.secure ? 'password' : 'open'})`, n.ssid);
      o.dataset.secure = n.secure ? '1' : '0';
      pick.append(o);
    }
    netSay(nets.length ? `${nets.length} network${nets.length === 1 ? '' : 's'} found, strongest first. Only 2.4 GHz networks show up. A hidden network is not listed: type its name below.` : 'The board heard no networks. Type the name below, or move the board closer to the router.', nets.length ? 'ok' : 'err');
  } catch (err) { if (board) netSay(`Board said: ${err.message}`, 'err'); }
  finally { netSync(); }
}
function netPicked() {
  const o = $('netPick').selectedOptions[0];
  if (!o || !o.value) return;
  $('netSsid').value = o.value;
  $('netPass').value = '';
  $('netPass').placeholder = o.dataset.secure === '0' ? 'empty: this network is open' : '';
  $('netPass').focus();
}
async function netClear() {
  if (!board || boardVia !== 'usb') return;
  try { await board.wifiClear(); netSay('The board forgot its network.', 'ok'); } catch (err) { netSay(`Board said: ${err.message}`, 'err'); }
}
const NET_POLL_MS = window.__ggNetPollMs || 1500;       // tests shorten the wait between Wi-Fi status checks
$('netScanBtn').addEventListener('click', netScan);
$('netPick').addEventListener('change', netPicked);
$('netBtn').addEventListener('click', netOpen);
$('netClose').addEventListener('click', () => netDlg.close());
netDlg.addEventListener('click', (e) => { if (e.target === netDlg) netDlg.close(); });
$('netConnectBtn').addEventListener('click', netConnect);
$('netSaveBtn').addEventListener('click', netSave);
$('netClearBtn').addEventListener('click', netClear);
$('netHost').addEventListener('keydown', (e) => { if (e.key === 'Enter') netConnect(); });
