// Adds the simulator's glow-grid text chunk to a PNG using the real web/js/export.js code.
// usage: node png_text.js in.png out.png brightness gamma '{"cols":16,...}'   |   node png_text.js read file.png
const fs = require('fs'), vm = require('vm'), path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'web', 'js', 'export.js'), 'utf8');
const cut = src.indexOf('/* ---------- export');
if (cut < 0) throw new Error('export.js layout changed: update tests/png_text.js');
const sim = { brightness: 0.3, gamma: 2.2 };
const ctx = vm.createContext({ sim, Uint32Array, Uint8Array, DataView, JSON, Math, String });
vm.runInContext(src.slice(0, cut) + '\nthis.api = { withPngText, readPngText, lightJson, LIGHT_KEY };', ctx);
const { withPngText, readPngText, lightJson, LIGHT_KEY } = ctx.api;
if (process.argv[2] === 'read') {
  console.log(readPngText(fs.readFileSync(process.argv[3]), LIGHT_KEY));
} else {
  const [, , inp, outp, b, g, extra] = process.argv;
  sim.brightness = Number(b); sim.gamma = Number(g);
  fs.writeFileSync(outp, withPngText(fs.readFileSync(inp), LIGHT_KEY, lightJson(JSON.parse(extra || '{}'))));
}
