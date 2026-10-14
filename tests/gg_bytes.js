// Builds a .gg sprite file with the real web/js/export.js code (ggBytes) so tests can compare it with c3/tools/gg_format.py.
// usage: node gg_bytes.js out.gg fps brightness gamma frames.json     (frames.json: array of frames, each 256 "#rrggbb" strings)
const fs = require('fs'), vm = require('vm'), path = require('path');
const web = path.join(__dirname, '..', 'web', 'js');
const src = fs.readFileSync(path.join(web, 'export.js'), 'utf8');
const cut = src.indexOf('/* ---------- export');
if (cut < 0) throw new Error('export.js layout changed: update tests/gg_bytes.js');
const core = fs.readFileSync(path.join(web, 'core.js'), 'utf8');
const helpers = core.slice(core.indexOf('const clamp'), core.indexOf('const toHex'));   // pyRound, hexToRgb
const ctx = vm.createContext({ sim: { brightness: 0.3, gamma: 2.2 }, Uint32Array, Uint8Array, DataView, JSON, Math, String, Error, parseInt });
vm.runInContext(helpers + src.slice(0, cut) + '\nthis.api = { ggBytes };', ctx);
const [, , outp, fps, b, g, framesPath] = process.argv;
const frames = JSON.parse(fs.readFileSync(framesPath, 'utf8'));
try {
  fs.writeFileSync(outp, ctx.api.ggBytes(frames, 16, 16, Number(fps), Number(b), Number(g)));
} catch (e) { console.error('ERR ' + e.message); process.exit(1); }
