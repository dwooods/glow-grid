// Drives the REAL firmware (the compiled simulator) with the REAL editor code: SerialTransport and GgBoard from web/js/board.js,
// ggBytes / ggDecode / crc32 from web/js/export.js. The only fake is the port: Node streams on the simulator's stdin and stdout.
// usage: node board_e2e.js <sim binary> <fs dir>      prints one JSON line of results for tests/test_gg.py
const fs = require('fs'), vm = require('vm'), path = require('path'), cp = require('child_process');
const { Readable } = require('stream');
const web = path.join(__dirname, '..', '..', 'web', 'js');
const read = (f) => fs.readFileSync(path.join(web, f), 'utf8');
const exp = read('export.js'), brd = read('board.js'), core = read('core.js');
const cut = (s, mark) => { const i = s.indexOf(mark); if (i < 0) throw new Error(`web layout changed: no "${mark}"; update c3/tests/board_e2e.js`); return s.slice(0, i); };
const helpers = core.slice(core.indexOf('const clamp'), core.indexOf('function hueSat'));   // pyRound, hexToRgb, toHex
const ctx = vm.createContext({ sim: { brightness: 0.3, gamma: 2.2 }, Uint32Array, Uint8Array, DataView, JSON, Math, String, Error, parseInt, Promise, setTimeout, clearTimeout, TextEncoder, TextDecoder, console });
vm.runInContext(helpers + cut(exp, '/* ---------- export') + cut(brd, '/* ---------- the shipped example') + '\nthis.api = { GgBoard, SerialTransport, ggBytes, ggDecode, crc32 };', ctx);
const { GgBoard, SerialTransport, ggBytes, ggDecode } = ctx.api;

const [, , SIM, FS] = process.argv;
const child = cp.spawn(SIM, [], { env: Object.assign({}, process.env, { GG_FS_DIR: FS, GG_LED_LOG: FS + '_led.log', GG_PINS: FS + '_pins' }) });
fs.writeFileSync(FS + '_led.log', ''); fs.writeFileSync(FS + '_pins', '1'.repeat(40));
const port = {
  open: async () => {}, setSignals: async () => {}, close: async () => { child.kill(); },
  readable: Readable.toWeb(child.stdout),
  writable: new WritableStream({ write(chunk) { return new Promise((res, rej) => child.stdin.write(chunk, (e) => (e ? rej(e) : res()))); } }),
};
const frame = (seed) => { let x = seed; const f = []; for (let i = 0; i < 256; i++) { x = (x * 1103515245 + 12345) & 0x7fffffff; f.push('#' + (x & 0xffffff).toString(16).padStart(6, '0')); } return f; };
const same = (a, b) => a.length === b.length && Buffer.compare(Buffer.from(a), Buffer.from(b)) === 0;

(async () => {
  const out = {};
  const t = new SerialTransport(port);
  await t.open();
  const board = new GgBoard(t);
  await board.hello();
  const small = ggBytes([frame(1), frame(2)], 16, 16, 7, 0.45, 2.6);
  const big = ggBytes(Array.from({ length: 16 }, (_, i) => frame(100 + i)), 16, 16, 12, 0.3, 2.2);   // the largest the format allows
  out.bigBytes = big.length;
  await board.put('small', small);
  await board.put('big', big);
  const l = await board.list();
  out.listed = l.files.map((f) => `${f.name}:${f.size}`);
  const info = await board.info();
  out.fw = Number(info.fw);
  out.smallBack = same(await board.get('small'), small);
  const t0 = Date.now();
  const got = await board.get('big');
  out.bigMs = Date.now() - t0;
  out.bigBack = same(got, big);
  const crc = await board.crc('big');
  out.crcMatches = crc.crc === ctx.api.crc32(big).toString(16).padStart(8, '0') && crc.size === big.length;
  const d = ggDecode(await board.get('small'));
  out.decoded = { fps: d.fps, brightness: d.brightness, gamma: d.gamma, frames: d.frames.length, first: d.frames[0][0] === frame(1)[0] && d.frames[1][255] === frame(2)[255] };
  out.missing = await board.get('nope').then(() => 'no error', (e) => e.message);
  await board.del('small');
  out.afterDelete = await board.get('small').then(() => 'no error', (e) => e.message);
  out.stillPlaysAfterGet = (await board.show('big')).startsWith('OK showing');
  await board.close();
  console.log(JSON.stringify(out));
  process.exit(0);
})().catch((e) => { console.log('FAIL ' + (e && e.stack || e)); process.exit(1); });
