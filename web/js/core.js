// Helpers, saved settings, sample frame. Classic script: shares one global scope with the other files in js/ (load order is in index.html).
const $ = (id) => document.getElementById(id);
const basePalette = ['#e63946','#f1c40f','#2a9d8f','#457b9d','#ffffff','#000000','#ff8c1a','#b04cff','#ff6fa8','#8b5a2b'];

const gridEl = $('grid'), deviceEl = $('device');
let cellEls = [];
let downloadsCap = null;
let playing = false, playTimer = null, painting = false, lastPaintIdx = null;

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

const newBlankFrame = (c, r) => new Array(c * r).fill('#000000');

const saved = recall('glowgrid-state');
const blankState = () => ({ cols: 16, rows: 16, frames: [newBlankFrame(16, 16)], currentFrame: 0, recentColors: [], fps: 6, name: 'sprite', shared: null });
const hasArt = (st) => st.frames.length > 1 || st.frames.some((f) => f.some((h) => h !== '#000000')) || !!st.shared;
let state, lastSession = null;
if (saved && Array.isArray(saved.frames) && saved.frames.length && saved.cols && saved.rows) {
  // The page always opens on one blank frame. Last visit's work is kept aside, one click away.
  if (hasArt(saved)) { lastSession = saved; store('glowgrid-last', saved); } else { lastSession = recall('glowgrid-last'); }
  state = Object.assign(blankState(), { cols: saved.cols, rows: saved.rows, recentColors: saved.recentColors || [], fps: saved.fps || 6, name: saved.name || 'sprite' });
  state.frames = [newBlankFrame(state.cols, state.rows)];
} else {
  state = blankState();
  lastSession = recall('glowgrid-last');
}
if (!(lastSession && Array.isArray(lastSession.frames) && lastSession.frames.length && lastSession.cols && lastSession.rows)) lastSession = null;
state.target = 'frame';
state.color = '#e63946'; state.tool = 'paint';
const sim = Object.assign({ brightness: 0.3, gamma: 2.2, psu: 6, target: 'pi', flags: true, pi: 'user@raspberrypi.local', pcDir: '$HOME\\Downloads' }, recall('glowgrid-sim') || {});

function saveState() {
  store('glowgrid-state', { cols: state.cols, rows: state.rows, frames: state.frames, currentFrame: state.currentFrame, recentColors: state.recentColors, fps: state.fps, name: state.name, shared: state.shared });
}
const saveSim = () => store('glowgrid-sim', sim);
