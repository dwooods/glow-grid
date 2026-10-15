// The Board card: talk to the ESP32-C3 player from the editor. Classic script (load order in index.html).
//
// Two layers, so a second transport (Wi-Fi) can reuse everything above the wire:
//   * a transport: writes bytes, delivers the board's text lines, can close.
//       SerialTransport uses Web Serial (Chrome and Edge on a computer). Tests pass a fake one.
//   * GgBoard: the line protocol c3/c3_player.ino speaks (PING, LIST, PUT, DEL, SHOW, OFF, ON, INFO),
//       the same one c3/tools/gg_tool.py uses.
// The card lists what is on the board, sends the current drawing as a .gg sprite (the bytes ggBytes() makes,
// same as Export for ESP32-C3), plays or deletes a stored sprite, and turns the panel off and on.

const BOARD_BAUD = 115200;
const BOARD_CHUNK = 1024;            // the firmware answers "A" after every 1024 bytes of a PUT

class SerialTransport {
  constructor(port) { this.port = port; this.onLine = null; this.onClose = null; this.buf = ''; this.writer = null; this.closed = false; }
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
      while (this.port.readable && !this.closed) {
        const reader = this.port.readable.getReader();
        try {
          for (;;) {
            const { value, done } = await reader.read();
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
        finally { reader.releaseLock(); }
        break;
      }
    } finally { this.close(); }
  }
  async write(bytes) { await this.writer.write(bytes); }
  async close() {
    if (this.closed) return;
    this.closed = true;
    try { if (this.writer) { this.writer.releaseLock(); } } catch (e) { /* already gone */ }
    try { await this.port.close(); } catch (e) { /* already gone */ }
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
  async close() { await this.t.close(); }
}

/* ---------- the card ---------- */
let board = null;
let boardFw = '';                  // from INFO fw=; '' means a build older than the version field
let boardNames = [];               // what the board listed last, so Send can warn before replacing one
const boardSupported = () => !!(window.__ggFakeSerial || navigator.serial);

function boardSay(msg, kind) {
  const el = $('boardStatus'); el.textContent = msg || ''; el.dataset.kind = kind || '';
}
function boardUi(connected) {
  $('boardConnectBtn').hidden = connected;
  $('boardDisconnectBtn').hidden = !connected;
  $('boardTools').hidden = !connected;
  $('boardAs').hidden = !connected;
  $('boardList').hidden = !connected;
  if (!connected) { $('boardList').innerHTML = ''; boardNames = []; }
  boardShowName();
}
function boardSendName() { return safeName().slice(0, 31); }
function boardShowName() {
  if (!board) return;
  const name = boardSendName();
  $('boardAs').textContent = `Send stores the drawing as “${name}”` + (boardNames.includes(name) ? ' and replaces the one on the board.' : '.') + ' Change the name under File ▸ Export.';
}
async function boardRefresh() {
  if (!board) return;
  const [{ files, free }, info] = [await board.list(), await board.info()];
  const ul = $('boardList'); ul.innerHTML = '';
  if (!files.length) { const li = document.createElement('li'); li.className = 'hint'; li.textContent = 'Nothing stored yet. Draw something and press Send to board.'; ul.appendChild(li); }
  for (const f of files) {
    const li = document.createElement('li');
    const playing = info.current === f.name;
    li.className = 'board-row' + (playing ? ' playing' : '');
    const nm = document.createElement('span'); nm.className = 'board-name'; nm.textContent = f.name;
    const sz = document.createElement('small'); sz.textContent = `${(f.size / 1024).toFixed(1)} KB` + (playing ? ' · playing' : '');
    const play = document.createElement('button'); play.type = 'button'; play.className = 'btn btn-quiet'; play.textContent = 'Play';
    play.disabled = playing;
    play.addEventListener('click', () => boardAct(() => board.show(f.name), `Playing ${f.name}.`));
    const del = document.createElement('button'); del.type = 'button'; del.className = 'btn btn-quiet danger'; del.textContent = 'Delete';
    del.addEventListener('click', () => { if (confirm(`Delete ${f.name} from the board? This cannot be undone.`)) boardAct(() => board.del(f.name), `Deleted ${f.name}.`); });
    li.append(nm, sz, play, del);
    ul.appendChild(li);
  }
  $('boardFree').textContent = free == null ? '' : `${(free / 1024).toFixed(0)} KB free`;
  $('boardOnBtn').disabled = info.panel !== 'off';
  $('boardOffBtn').disabled = info.panel === 'off';
  boardFw = info.fw || '';
  boardNames = files.map((f) => f.name);
  boardShowName();
}
async function boardAct(fn, doneMsg) {
  if (!board) return;
  try { await fn(); boardSay(doneMsg, 'ok'); await boardRefresh(); }
  catch (err) { if (board) boardSay(`Board said: ${err.message}`, 'err'); }
}
async function boardConnect() {
  if (!boardSupported()) { boardSay('Connecting a board needs Chrome or Edge on a computer. From a phone, export a .gg file instead.', 'err'); return; }
  let transport;
  try {
    if (window.__ggFakeSerial) transport = window.__ggFakeSerial();
    else {
      const port = await navigator.serial.requestPort({ filters: [{ usbVendorId: 0x303a }] });
      transport = new SerialTransport(port);
    }
    transport.onClose = () => { board = null; boardUi(false); boardSay('Board disconnected.', ''); };
    await transport.open();
  } catch (err) {
    boardSay(err && err.name === 'NotFoundError' ? 'No board chosen.' : `Could not open the port: ${err.message}. Close the Arduino Serial Monitor or any other program using it.`, 'err');
    return;
  }
  const b = new GgBoard(transport);
  try { await b.hello(); } catch (err) { boardSay(err.message, 'err'); await transport.close(); return; }
  board = b;
  boardUi(true);
  try { await boardRefresh(); boardSay(`Connected. Firmware ${boardFw || 'older than 3 (re-flash from the repo)'}.`, 'ok'); }
  catch (err) { boardSay(`Board said: ${err.message}`, 'err'); }
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
    await boardRefresh();
  } catch (err) { if (board) boardSay(`Board said: ${err.message}`, 'err'); }   // after an unplug the card already says so
  finally { btn.disabled = false; }
}
$('boardConnectBtn').addEventListener('click', boardConnect);
$('boardDisconnectBtn').addEventListener('click', async () => { if (board) await board.close(); });
$('boardSendBtn').addEventListener('click', boardSend);
$('boardOnBtn').addEventListener('click', () => boardAct(() => board.on(), 'Lights on.'));
$('boardOffBtn').addEventListener('click', () => boardAct(() => board.off(), 'Lights off. The panel stays dark until Lights on, even after a power cycle.'));
$('nameInput').addEventListener('input', boardShowName);
$('boardRefreshBtn').addEventListener('click', () => boardAct(async () => {}, 'List refreshed.'));
boardUi(false);
if (!boardSupported()) $('boardUnsupported').hidden = false;
if (navigator.serial) navigator.serial.addEventListener('disconnect', () => { if (board) board.close(); });
