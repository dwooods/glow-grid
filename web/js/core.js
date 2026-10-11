// Helpers, saved settings, sample frame. Classic script: shares one global scope with the other files in js/ (load order is in index.html).
const $ = (id) => document.getElementById(id);
const basePalette = ['#e63946','#f1c40f','#2a9d8f','#457b9d','#ffffff','#000000','#ff8c1a','#b04cff'];

const gridEl = $('grid'), deviceEl = $('device');
let cellEls = [];
let downloadsCap = null;
let playing = false, playTimer = null, painting = false;

(async () => {
  try { if (window.claude && window.claude.use) downloadsCap = await window.claude.use('downloads'); }
  catch (e) { downloadsCap = null; }
  if (!downloadsCap && window.claude) setStatus('Saving files isn’t available in this view.');
})();

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
// Python's round(): half-to-even, so the sim matches grid_common.py exactly
function pyRound(x) {
  const f = Math.floor(x), d = x - f;
  if (Math.abs(d - 0.5) < 1e-9) return f % 2 === 0 ? f : f + 1;
  return Math.round(x);
}
function hexToRgb(hex) {
  const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '#000000');
  return m ? [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)] : [0, 0, 0];
}
const toHex = (r, g, b) => '#' + [r, g, b].map((v) => v.toString(16).padStart(2, '0')).join('');
function hueSat(r, g, b) {
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  const s = mx ? d / mx : 0;
  let h = 0;
  if (d) {
    if (mx === r) h = ((g - b) / d) % 6; else if (mx === g) h = (b - r) / d + 2; else h = (r - g) / d + 4;
    h *= 60; if (h < 0) h += 360;
  }
  return [h, s];
}

/* ---------- persistence (per-browser convenience only) ---------- */
function store(key, val) { try { localStorage.setItem(key, JSON.stringify(val)); } catch (e) {} }
function recall(key) { try { const r = localStorage.getItem(key); return r ? JSON.parse(r) : null; } catch (e) { return null; } }

/* ---------- sample: a blinking smiley on true black ---------- */
const newBlankFrame = (c, r) => new Array(c * r).fill('#000000');
function sampleFrame(cols, rows, blink) {
  const f = newBlankFrame(cols, rows);
  const cx = (cols - 1) / 2, cy = (rows - 1) / 2, rad = Math.min(cols, rows) / 2 - 1;
  const set = (x, y, hex) => { x = Math.round(x); y = Math.round(y); if (x >= 0 && y >= 0 && x < cols && y < rows) f[y * cols + x] = hex; };
  for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) if (Math.hypot(x - cx, y - cy) <= rad) f[y * cols + x] = '#f5c542';
  const ink = '#1a1208'; // near-black on purpose: shows up as "barely lit" in the checker
  const eyeY = cy - rad * 0.35, off = rad * 0.4;
  if (blink) { for (const ex of [cx - off, cx + off]) { set(ex - 1, eyeY, ink); set(ex, eyeY, ink); set(ex + 1, eyeY, ink); } }
  else { for (const ex of [cx - off, cx + off]) { set(ex, eyeY, ink); set(ex, eyeY - 1, ink); } }
  const span = Math.round(rad * 0.45);
  for (let dx = -span; dx <= span; dx++) set(cx + dx, cy + rad * 0.2 + (span ? (Math.abs(dx) / span) * rad * -0.25 + rad * 0.25 : 0), '#e63946');
  return f;
}

const saved = recall('glowgrid-state');
let state;
if (saved && Array.isArray(saved.frames) && saved.frames.length && saved.cols && saved.rows) {
  state = Object.assign({ recentColors: [], fps: 6, name: 'smiley' }, saved);
  state.currentFrame = clamp(state.currentFrame || 0, 0, state.frames.length - 1);
  if (!(Array.isArray(state.shared) && state.shared.length === state.cols * state.rows)) state.shared = null;
} else {
  state = { cols: 16, rows: 16, frames: [sampleFrame(16, 16, false), sampleFrame(16, 16, false), sampleFrame(16, 16, false), sampleFrame(16, 16, true)], currentFrame: 0, recentColors: [], fps: 6, name: 'smiley', shared: null };
}
state.target = 'frame';
state.color = '#e63946'; state.tool = 'paint';
const sim = Object.assign({ brightness: 0.3, gamma: 2.2, psu: 6, target: 'pi', view: 'design', flags: true, pi: 'user@raspberrypi.local', pcDir: '$HOME\\Downloads' }, recall('glowgrid-sim') || {});

function saveState() {
  store('glowgrid-state', { cols: state.cols, rows: state.rows, frames: state.frames, currentFrame: state.currentFrame, recentColors: state.recentColors, fps: state.fps, name: state.name, shared: state.shared });
}
const saveSim = () => store('glowgrid-sim', sim);

