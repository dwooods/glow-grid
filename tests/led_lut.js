// Prints the simulator's gamma/brightness LUT for each (brightness, gamma) pair given as JSON on argv[2].
// Loads the real web/js/led.js; only the pure helpers it needs from core.js are pulled in.
const fs = require('fs'), vm = require('vm'), path = require('path');
const js = (f) => fs.readFileSync(path.join(__dirname, '..', 'web', 'js', f), 'utf8');
const core = js('core.js');
const start = core.indexOf('function pyRound'), end = core.indexOf('function hueSat');
if (start < 0 || end < 0) throw new Error('core.js layout changed: update tests/led_lut.js');
const ctx = vm.createContext({ Math, sim: { brightness: 0.3, gamma: 2.2 } });
vm.runInContext(core.slice(start, end) + '\n' + js('led.js').split('/* ---------- layers')[0], ctx);
const out = [];
// one LUT per pair, in order
for (const [b, g] of JSON.parse(process.argv[2])) {
  ctx.sim.brightness = b; ctx.sim.gamma = g;
  vm.runInContext('buildLut()', ctx);
  out.push(Array.from(vm.runInContext('LUT', ctx)));
}
console.log(JSON.stringify(out));
