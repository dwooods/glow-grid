// LED model (mirrors grid_common.py) and the shared layer. Classic script: shares one global scope with the other files in js/ (load order is in index.html).
/* ---------- LED model: mirrors grid_common.py ---------- */
let LUT = [], cache = new Map();
function buildLut() {
  LUT = new Array(256);
  for (let c = 0; c < 256; c++) {
    const v = pyRound(255 * sim.brightness * Math.pow(c / 255, sim.gamma));
    LUT[c] = (c > 0 && v === 0) ? 1 : v;
  }
  cache = new Map();
}
// Returns what the LED actually receives, a screen color for it, a flag, and est. current
function led(hex) {
  let a = cache.get(hex);
  if (a) return a;
  const rgb = hexToRgb(hex);
  const v = rgb.map((c) => LUT[c]);
  const top = Math.max(1, 255 * sim.brightness);
  const disp = v.map((x) => Math.round(255 * Math.pow(Math.min(1, x / top), 1 / 2.2)));
  let flag = null;
  const isBlack = rgb[0] + rgb[1] + rgb[2] === 0;
  if (!isBlack && Math.max(...v) <= 3) flag = 'faint';
  else if (!isBlack) {
    const [h1, s1] = hueSat(...rgb), [h2, s2] = hueSat(...disp);
    const dh = Math.min(Math.abs(h1 - h2), 360 - Math.abs(h1 - h2));
    if ((s1 > 0.3 && s2 > 0.3 && dh > 15) || Math.abs(s1 - s2) > 0.35) flag = 'shift';
  }
  // ~20 mA per channel at full duty, plus ~0.6 mA idle per LED
  const mA = (v[0] + v[1] + v[2]) / 255 * 20 + 0.6;
  a = { v, disp: toHex(...disp), flag, mA, isBlack };
  cache.set(hex, a);
  return a;
}

/* ---------- layers: an optional shared background under every frame ---------- */
// In a frame, black is see-through when a shared layer exists; playback and export use the combined picture.
const isOff = (h) => !h || h === '#000000';
const layerHex = (frame, i) => { const h = frame[i]; return (state.shared && isOff(h)) ? (state.shared[i] || '#000000') : (h || '#000000'); };
const flatten = (frame) => state.shared ? frame.map((h, i) => isOff(h) ? (state.shared[i] || '#000000') : h) : frame;
const editLayer = () => (state.target === 'shared' && state.shared) ? state.shared : state.frames[state.currentFrame];
function setEditLayer(arr) { if (state.target === 'shared' && state.shared) state.shared = arr; else state.frames[state.currentFrame] = arr; }

