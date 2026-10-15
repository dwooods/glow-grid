// Decodes a .gg file with the real web/js/export.js code (ggDecode) so tests can check it against c3/tools/gg_format.py.
// usage: node gg_decode.js file.gg      prints JSON {cols, rows, frames, fps, brightness, gamma} or "ERR <message>"
const fs = require('fs'), vm = require('vm'), path = require('path');
const web = path.join(__dirname, '..', 'web', 'js');
const src = fs.readFileSync(path.join(web, 'export.js'), 'utf8');
const cut = src.indexOf('/* ---------- export');
if (cut < 0) throw new Error('export.js layout changed: update tests/gg_decode.js');
const core = fs.readFileSync(path.join(web, 'core.js'), 'utf8');
const helpers = core.slice(core.indexOf('const clamp'), core.indexOf('function hueSat'));   // pyRound, hexToRgb, toHex
const ctx = vm.createContext({ sim: { brightness: 0.3, gamma: 2.2 }, Uint32Array, Uint8Array, DataView, JSON, Math, String, Error, parseInt });
vm.runInContext(helpers + src.slice(0, cut) + '\nthis.api = { ggDecode };', ctx);
try { console.log(JSON.stringify(ctx.api.ggDecode(new Uint8Array(fs.readFileSync(process.argv[2]))))); }
catch (e) { console.log('ERR ' + e.message); }
