// Drives the REAL firmware (the compiled simulator, reached over its loopback HTTP server) with the REAL editor code:
// HttpBoard and crc32 from web/js/board.js and export.js, ggBytes / ggDecode from export.js. Node's own fetch stands in for the browser's.
// usage: node board_http_e2e.js <host:port>      prints one JSON line of results for tests/test_gg.py
const fs = require('fs'), vm = require('vm'), path = require('path');
const web = path.join(__dirname, '..', '..', 'web', 'js');
const read = (f) => fs.readFileSync(path.join(web, f), 'utf8');
const exp = read('export.js'), brd = read('board.js'), core = read('core.js');
const cut = (s, mark) => { const i = s.indexOf(mark); if (i < 0) throw new Error(`web layout changed: no "${mark}"; update c3/tests/board_http_e2e.js`); return s.slice(0, i); };
const helpers = core.slice(core.indexOf('const clamp'), core.indexOf('function hueSat'));   // pyRound, hexToRgb, toHex
const ctx = vm.createContext({ sim: { brightness: 0.3, gamma: 2.2 }, Uint32Array, Uint8Array, DataView, JSON, Math, String, Error, parseInt, Promise, setTimeout, clearTimeout,
  TextEncoder, TextDecoder, console, fetch, FormData, Blob, AbortController, encodeURIComponent, Number });
vm.runInContext(helpers + cut(exp, '/* ---------- export') + cut(brd, '/* ---------- the shipped example') + '\nthis.api = { HttpBoard, ggBytes, ggDecode, crc32 };', ctx);
const { HttpBoard, ggBytes, ggDecode, crc32 } = ctx.api;

const host = process.argv[2];
const frame = (seed) => { let x = seed; const f = []; for (let i = 0; i < 256; i++) { x = (x * 1103515245 + 12345) & 0x7fffffff; f.push('#' + (x & 0xffffff).toString(16).padStart(6, '0')); } return f; };
const same = (a, b) => a.length === b.length && Buffer.compare(Buffer.from(a), Buffer.from(b)) === 0;
const err = (p) => p.then(() => 'no error', (e) => e.message);

(async () => {
  const out = {};
  const board = new HttpBoard(host);
  out.hello = await board.hello();
  const small = ggBytes([frame(1), frame(2)], 16, 16, 7, 0.45, 2.6);
  const big = ggBytes(Array.from({ length: 64 }, (_, i) => frame(100 + i)), 16, 16, 12, 0.3, 2.2);   // the largest the format allows; has zero bytes
  out.bigHasZero = big.includes(0);
  const prog = [];
  await board.put('small', small, (d, t) => prog.push([d, t]));
  out.progress = prog;
  await board.put('big', big);
  const l = await board.list();
  out.listed = l.files.map((f) => `${f.name}:${f.size}`);
  out.freeIsNumber = typeof l.free === 'number' && l.free > 0;
  const info = await board.info();
  out.info = { fw: Number(info.fw), current: info.current, sprites: info.sprites, panel: info.panel, wifi: info.wifi, ip: info.ip };
  out.smallBack = same(await board.get('small'), small);
  out.bigBack = same(await board.get('big'), big);
  const crc = await board.crc('big');
  out.crcMatches = crc.crc === crc32(big).toString(16).padStart(8, '0') && crc.size === big.length;
  const d = ggDecode(await board.get('small'));
  out.decoded = { fps: d.fps, brightness: d.brightness, gamma: d.gamma, frames: d.frames.length, first: d.frames[0][0] === frame(1)[0] };
  out.missingGet = await err(board.get('nope'));
  out.missingShow = await err(board.show('nope'));
  out.missingDel = await err(board.del('nope'));
  out.badSprite = await err(board.put('junk', new Uint8Array(2000)));          // not a sprite: the firmware refuses it, and the message is its own
  out.badName = await err(board.put('bad name', small));
  out.afterBad = (await board.list()).files.map((f) => f.name);                // nothing leaked into storage
  out.show = await board.show('small');
  out.currentAfterShow = (await board.info()).current;
  out.off = await board.off(); out.panelOff = (await board.info()).panel;
  out.on = await board.on(); out.panelOn = (await board.info()).panel;
  out.rotate = await board.rotate(300); out.rotateInfo = (await board.info()).rotate;
  out.rotateOff = await board.rotate(0);
  out.del = await board.del('small');
  out.afterDel = (await board.list()).files.map((f) => f.name);
  let closed = 0; board.onClose = () => { closed++; };
  await board.close(); await board.close();
  out.closedOnce = closed === 1;
  out.unreachable = await err(new HttpBoard('127.0.0.1:1').hello());           // nothing listens there
  console.log(JSON.stringify(out));
  process.exit(0);
})().catch((e) => { console.log('FAIL ' + (e && e.stack || e)); process.exit(1); });
