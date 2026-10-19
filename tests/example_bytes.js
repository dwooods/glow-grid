// Builds every shipped example (web/js/examples_data.js) into .gg bytes with the real web/js/export.js code, for
// tests/test_web_examples.py (and, with a path argument, an older copy of the data file for examples/make_legacy_examples.py). Prints JSON: [{name, fps, frames, hex, crc}] where crc is what the Board card compares.
const fs = require('fs'), vm = require('vm'), path = require('path');
const web = path.join(__dirname, '..', 'web', 'js');
const exp = fs.readFileSync(path.join(web, 'export.js'), 'utf8');
const cut = exp.indexOf('/* ---------- export');
if (cut < 0) throw new Error('export.js layout changed: update tests/example_bytes.js');
const core = fs.readFileSync(path.join(web, 'core.js'), 'utf8');
const helpers = core.slice(core.indexOf('const clamp'), core.indexOf('const toHex'));
const board = fs.readFileSync(path.join(web, 'board.js'), 'utf8');
const a = board.indexOf('function ggExampleBytes'), b = board.indexOf('const ggExampleCrc');
const c = board.indexOf('\n', b);
if (a < 0 || b < 0) throw new Error('board.js layout changed: update tests/example_bytes.js');
const ctx = vm.createContext({ Uint32Array, Uint8Array, DataView, JSON, Math, String, Error, parseInt, Array });
vm.runInContext(helpers + exp.slice(0, cut) + fs.readFileSync(process.argv[2] || path.join(web, 'examples_data.js'), 'utf8') +
  board.slice(a, c) + '\nthis.api = { GG_EXAMPLES, ggExampleBytes, ggExampleCrc };', ctx);
const { GG_EXAMPLES, ggExampleBytes, ggExampleCrc } = ctx.api;
console.log(JSON.stringify(GG_EXAMPLES.map((e) => ({
  name: e.name, fps: e.fps, frames: e.frames.length,
  hex: Buffer.from(ggExampleBytes(e)).toString('hex'), crc: ggExampleCrc(e),
}))));
