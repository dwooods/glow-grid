// Undo, rendering, frames, drawing, view. Classic script: shares one global scope with the other files in js/ (load order is in index.html).
/* ---------- undo / redo ---------- */
const undoStack = [], redoStack = [];
const snapshot = () => JSON.stringify({ cols: state.cols, rows: state.rows, frames: state.frames, currentFrame: state.currentFrame, shared: state.shared });
function pushUndo() {
  undoStack.push(snapshot()); if (undoStack.length > 100) undoStack.shift();
  redoStack.length = 0; updateUndoBtns();
}
function restore(snap) {
  const s = JSON.parse(snap); if (s.shared === undefined) s.shared = null;
  const resized = s.cols !== state.cols || s.rows !== state.rows;
  Object.assign(state, s);
  if (!state.shared) state.target = 'frame';
  if (resized) { $('colsInput').value = state.cols; $('rowsInput').value = state.rows; buildGridDOM(); }
  afterFrameChange();
}
function undo() { if (!undoStack.length) return; stopPlay(); redoStack.push(snapshot()); restore(undoStack.pop()); updateUndoBtns(); }
function redo() { if (!redoStack.length) return; stopPlay(); undoStack.push(snapshot()); restore(redoStack.pop()); updateUndoBtns(); }
function updateUndoBtns() { $('undoBtn').disabled = !undoStack.length; $('redoBtn').disabled = !redoStack.length; }

/* ---------- rendering ---------- */
function buildGridDOM() {
  gridEl.style.setProperty('--cols', state.cols);
  gridEl.style.setProperty('--rows', state.rows);
  gridEl.innerHTML = ''; cellEls = [];
  for (let i = 0; i < state.cols * state.rows; i++) {
    const c = document.createElement('div');
    c.className = 'cell'; c.dataset.index = i;
    gridEl.appendChild(c); cellEls.push(c);
  }
}
function updateCell(idx) {
  const hex = layerHex(state.frames[state.currentFrame], idx);
  const cell = cellEls[idx]; if (!cell) return;
  const a = led(hex);
  cell.classList.toggle('flag-faint', a.flag === 'faint');
  cell.classList.toggle('flag-shift', a.flag === 'shift');
  if (a.isBlack) {
    cell.style.background = 'var(--grid-off)';
    cell.style.boxShadow = 'none'; return;
  }
  const [r, g, b] = hexToRgb(hex);
  cell.style.background = hex;
  cell.style.boxShadow = `0 0 6px 1px rgba(${r},${g},${b},0.5)`;
}
function frameStats(frame) {
  let mA = 0, faint = 0, shift = 0;
  for (const hex of frame) { const a = led(hex); mA += a.mA; if (a.flag === 'faint') faint++; else if (a.flag === 'shift') shift++; }
  return { amps: mA / 1000, faint, shift };
}
function renderDiagnostics() {
  const now = frameStats(flatten(state.frames[state.currentFrame]));
  let peak = 0; for (const f of state.frames) peak = Math.max(peak, frameStats(flatten(f)).amps);
  $('ampNow').textContent = now.amps.toFixed(2) + ' A';
  $('ampPeak').innerHTML = peak.toFixed(2) + ' A <small>of ' + sim.psu + ' A</small>';
  const pct = peak / sim.psu;
  const meter = $('ampMeter');
  meter.firstElementChild.style.width = clamp(pct * 100, 0, 100) + '%';
  meter.classList.toggle('hot', pct > 0.6 && pct <= 0.85);
  meter.classList.toggle('over', pct > 0.85);
  const flagged = now.faint + now.shift, ds = $('diagSum');
  ds.textContent = flagged ? flagged + ' px flagged, open to fix' : 'all clear';
  ds.classList.toggle('warn', flagged > 0 || pct > 0.85);
}
function renderFrame() { for (let i = 0; i < cellEls.length; i++) updateCell(i); renderDiagnostics(); }
function renderFrameStrip() {
  renderImgSwatches();
  const strip = $('frameStrip'); strip.innerHTML = '';
  $('stripHint').hidden = hasArt(state);
  state.frames.forEach((frame, i) => {
    const cell = document.createElement('span'); cell.className = 'frame-cell';
    const t = document.createElement('canvas');
    t.width = state.cols; t.height = state.rows;
    t.className = 'frame-thumb' + (i === state.currentFrame ? ' active' : '');
    t.tabIndex = 0; t.setAttribute('role', 'button'); t.setAttribute('aria-label', 'Frame ' + (i + 1));
    paintCanvas(t.getContext('2d'), flatten(frame), 0);
    t.addEventListener('click', () => selectFrame(i));
    t.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectFrame(i); } });
    const n = document.createElement('span'); n.className = 'frame-n'; n.textContent = i + 1; n.setAttribute('aria-hidden', 'true');
    cell.append(t, n);
    strip.appendChild(cell);
  });
  for (let i = state.frames.length; i < GG_MAX_FRAMES; i++) {      // empty slots show the cap: a sprite holds at most GG_MAX_FRAMES frames
    const cell = document.createElement('span'); cell.className = 'frame-cell frame-empty'; cell.setAttribute('aria-hidden', 'true');
    const slot = document.createElement('span'); slot.className = 'frame-slot';
    const n = document.createElement('span'); n.className = 'frame-n'; n.textContent = i + 1;
    cell.append(slot, n);
    strip.appendChild(cell);
  }
}
function paintCanvas(ctx, frame, offsetX) {
  const img = ctx.createImageData(state.cols, state.rows);
  for (let p = 0; p < frame.length; p++) {
    const [r, g, b] = hexToRgb(frame[p]);
    img.data.set([r, g, b, 255], p * 4);
  }
  ctx.putImageData(img, offsetX, 0);
}
const updateReadout = () => { $('frameCount').textContent = `${state.frames.length} of ${GG_MAX_FRAMES} frames`; const r = $('frameReadout'); r.textContent = `Frame ${state.currentFrame + 1} / ${state.frames.length}`; r.hidden = state.frames.length < 2;
  const full = state.frames.length >= GG_MAX_FRAMES;       // the cap is the same for the Pi and the C3
  for (const id of ['addFrameBtn', 'addBlankFrameBtn']) { $(id).disabled = full; $(id).title = full ? `A sprite has at most ${GG_MAX_FRAMES} frames` : ''; }
};
function afterFrameChange() { syncRestoreBtn(); renderFrame(); renderFrameStrip(); updateReadout(); updateLayerUI(); updateCmd(); saveState(); }
function selectFrame(i) { stopPlay(); state.currentFrame = i; afterFrameChange(); }

/* ---------- frames ---------- */
$('addFrameBtn').addEventListener('click', () => { if (state.frames.length >= GG_MAX_FRAMES) return; stopPlay(); pushUndo(); state.frames.splice(state.currentFrame + 1, 0, [...state.frames[state.currentFrame]]); state.currentFrame++; afterFrameChange(); });
$('addBlankFrameBtn').addEventListener('click', () => { if (state.frames.length >= GG_MAX_FRAMES) return; stopPlay(); pushUndo(); state.frames.splice(state.currentFrame + 1, 0, newBlankFrame(state.cols, state.rows)); state.currentFrame++; afterFrameChange(); });
$('deleteFrameBtn').addEventListener('click', () => {
  stopPlay(); pushUndo();
  if (state.frames.length <= 1) {            // the last frame can't go, so blank it instead of doing nothing
    state.frames[0] = newBlankFrame(state.cols, state.rows); state.shared = null; state.target = 'frame';
    afterFrameChange(); setStatus('That was the only frame, so it was cleared instead. Undo reverts.'); return;
  }
  state.frames.splice(state.currentFrame, 1);
  state.currentFrame = clamp(state.currentFrame - 1, 0, state.frames.length - 1);
  afterFrameChange();
});

/* ---------- drawing ---------- */
function floodFill(start, color) {
  const f = editLayer(), target = f[start];
  if (target === color) return;
  const stack = [start];
  while (stack.length) {
    const i = stack.pop();
    if (f[i] !== target) continue;
    f[i] = color; updateCell(i);
    const x = i % state.cols, y = Math.floor(i / state.cols);
    if (x > 0) stack.push(i - 1);
    if (x < state.cols - 1) stack.push(i + 1);
    if (y > 0) stack.push(i - state.cols);
    if (y < state.rows - 1) stack.push(i + state.cols);
  }
}
function applyTool(idx) {
  const f = editLayer();
  if (state.tool === 'fill') { floodFill(idx, state.color); return; }
  const c = state.tool === 'erase' ? '#000000' : state.color;
  if (f[idx] !== c) { f[idx] = c; updateCell(idx); }
}
function cellAt(x, y) {
  const el = document.elementFromPoint(x, y);
  return el && el.classList && el.classList.contains('cell') ? Number(el.dataset.index) : null;
}
gridEl.addEventListener('pointerdown', (e) => {
  if (playing) return;
  const idx = cellAt(e.clientX, e.clientY); if (idx === null) return;
  if (state.tool === 'pick' || e.altKey) { pickAt(idx, state.tool === 'pick'); e.preventDefault(); return; }
  pushUndo(); painting = true; lastPaintIdx = idx; applyTool(idx); e.preventDefault();
});
// Cell under a point by geometry, so the gaps between cells still count and fast strokes don't drop pixels
function cellNear(x, y) {
  const r = gridEl.getBoundingClientRect();
  const cx = Math.floor((x - r.left) / r.width * state.cols), cy = Math.floor((y - r.top) / r.height * state.rows);
  return cx < 0 || cy < 0 || cx >= state.cols || cy >= state.rows ? null : cy * state.cols + cx;
}
// Paint every cell on the straight line between two cells (Bresenham)
function paintLine(a, b) {
  let x0 = a % state.cols, y0 = Math.floor(a / state.cols);
  const x1 = b % state.cols, y1 = Math.floor(b / state.cols);
  const dx = Math.abs(x1 - x0), dy = -Math.abs(y1 - y0), sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  let err = dx + dy;
  for (;;) {
    applyTool(y0 * state.cols + x0);
    if (x0 === x1 && y0 === y1) break;
    const e2 = 2 * err;
    if (e2 >= dy) { err += dy; x0 += sx; }
    if (e2 <= dx) { err += dx; y0 += sy; }
  }
}
window.addEventListener('pointermove', (e) => {
  if (!painting || state.tool === 'fill') return;
  // Touch and pen deliver several samples per frame; use all of them
  const pts = e.getCoalescedEvents ? e.getCoalescedEvents() : [];
  for (const pt of (pts.length ? pts : [e])) {
    const idx = cellNear(pt.clientX, pt.clientY);
    if (idx === null) continue;
    if (lastPaintIdx === null) applyTool(idx); else if (idx !== lastPaintIdx) paintLine(lastPaintIdx, idx);
    lastPaintIdx = idx;
  }
});
const endPaint = () => { lastPaintIdx = null; if (!painting) return; painting = false; syncRestoreBtn(); renderDiagnostics(); renderFrameStrip(); saveState(); };
window.addEventListener('pointerup', endPaint);
window.addEventListener('pointercancel', endPaint);

/* ---------- keyboard drawing: arrows move a cursor, Space or Enter applies the tool ---------- */
let kbIdx = null, kbHeld = false;
const kbRefresh = () => { syncRestoreBtn(); renderDiagnostics(); renderFrameStrip(); saveState(); };
function kbMark() {
  cellEls.forEach((c) => c.classList.remove('kb'));
  if (kbIdx !== null && cellEls[kbIdx]) cellEls[kbIdx].classList.add('kb');
}
function kbSay() {
  if (kbIdx === null) return;
  const hex = layerHex(state.frames[state.currentFrame], kbIdx);
  $('gridSay').textContent = `Row ${Math.floor(kbIdx / state.cols) + 1}, column ${kbIdx % state.cols + 1}, ${isOff(hex) ? 'off' : hex}`;
}
function kbApply(repeat) {
  if (playing || kbIdx === null) return;
  if (state.tool === 'pick') { pickAt(kbIdx, true); kbSay(); return; }
  if (!repeat) pushUndo();
  applyTool(kbIdx); kbRefresh(); kbSay();
}
gridEl.addEventListener('focus', () => {
  if (kbIdx === null || kbIdx >= state.cols * state.rows) kbIdx = Math.floor(state.rows / 2) * state.cols + Math.floor(state.cols / 2);
  if (gridEl.matches(':focus-visible')) { gridEl.classList.add('kb-on'); kbMark(); kbSay(); }   // keyboard focus only; a tap or click shows no cursor
});
gridEl.addEventListener('pointerdown', () => gridEl.classList.remove('kb-on'));
gridEl.addEventListener('blur', () => { gridEl.classList.remove('kb-on'); kbHeld = false; });
gridEl.addEventListener('keydown', (e) => {
  if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey || kbIdx === null) return;
  const d = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] }[e.key];
  if (d || e.key === ' ' || e.key === 'Enter') gridEl.classList.add('kb-on');
  if (d) {
    e.preventDefault();
    const x = clamp(kbIdx % state.cols + d[0], 0, state.cols - 1), y = clamp(Math.floor(kbIdx / state.cols) + d[1], 0, state.rows - 1);
    kbIdx = y * state.cols + x; kbMark();
    if (kbHeld && state.tool !== 'pick' && state.tool !== 'fill') { applyTool(kbIdx); kbRefresh(); }
    kbSay();
  } else if (e.key === ' ' || e.key === 'Enter') {
    e.preventDefault(); kbMark(); kbHeld = e.key === ' '; kbApply(e.repeat);
  } else if (e.key === 'Escape') gridEl.blur();
});
gridEl.addEventListener('keyup', (e) => { if (e.key === ' ') kbHeld = false; });

function setTool(t) {
  state.tool = t;
  document.querySelectorAll('.tool-btn[data-tool]').forEach((b) => b.classList.toggle('active', b.dataset.tool === t));
  gridEl.classList.toggle('picking', t === 'pick');
  if (t !== 'pick') hideHover();
}
document.querySelectorAll('.tool-btn[data-tool]').forEach((btn) => btn.addEventListener('click', () => setTool(btn.dataset.tool)));

/* ---------- color: wheel, value slider, hex, swatches ---------- */
function rgbToHsv(r, g, b) {
  r /= 255; g /= 255; b /= 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
  let h = 0;
  if (d) { if (mx === r) h = ((g - b) / d) % 6; else if (mx === g) h = (b - r) / d + 2; else h = (r - g) / d + 4; h *= 60; if (h < 0) h += 360; }
  return [h, mx ? d / mx : 0, mx];
}
function hsvToRgb(h, s, v) {
  const c = v * s, x = c * (1 - Math.abs(((h / 60) % 2) - 1)), m = v - c;
  let r = 0, g = 0, b = 0;
  if (h < 60) [r, g, b] = [c, x, 0]; else if (h < 120) [r, g, b] = [x, c, 0]; else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c]; else if (h < 300) [r, g, b] = [x, 0, c]; else [r, g, b] = [c, 0, x];
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
}
const wheelCv = $('wheel'), wheelCtx = wheelCv.getContext('2d');
const hsv = { h: 0, s: 1, v: 1 };          // the wheel's own state; state.color is derived from it
let wheelDrawnV = -1, wheelBase = null;
function drawWheel() {
  const W = wheelCv.width, R = W / 2, v = hsv.v;
  if (wheelDrawnV !== v) {
    const img = wheelCtx.createImageData(W, W), d = img.data;
    for (let y = 0; y < W; y++) for (let x = 0; x < W; x++) {
      const dx = x + 0.5 - R, dy = y + 0.5 - R, r = Math.hypot(dx, dy);
      if (r > R) continue;
      let h = Math.atan2(dy, dx) * 180 / Math.PI; if (h < 0) h += 360;
      const [cr, cg, cb] = hsvToRgb(h, Math.min(1, r / (R - 1)), v);
      const i = (y * W + x) * 4; d[i] = cr; d[i + 1] = cg; d[i + 2] = cb; d[i + 3] = Math.round(255 * Math.min(1, R - r));
    }
    wheelBase = img; wheelDrawnV = v;
  }
  wheelCtx.putImageData(wheelBase, 0, 0);
  const a = hsv.h * Math.PI / 180, mr = hsv.s * (R - 1), mx = R + Math.cos(a) * mr, my = R + Math.sin(a) * mr;
  wheelCtx.beginPath(); wheelCtx.arc(mx, my, 6, 0, Math.PI * 2);
  wheelCtx.lineWidth = 3; wheelCtx.strokeStyle = '#000'; wheelCtx.stroke();
  wheelCtx.lineWidth = 1.5; wheelCtx.strokeStyle = '#fff'; wheelCtx.stroke();
}
// Set the paint color. commit=true also records it in the recent swatches (end of a drag, hex entry, pick, swatch click).
function setColor(hex, commit) {
  hex = hex.toLowerCase(); state.color = hex;
  const [h, s, v] = rgbToHsv(...hexToRgb(hex));
  if (s > 0 && v > 0) hsv.h = h;     // keep the hue when the color is gray or black
  if (v > 0) hsv.s = s;
  hsv.v = v;
  $('curSwatch').style.background = hex; $('hexInput').value = hex;
  $('valInput').value = String(Math.round(v * 100));
  drawWheel();
  if (commit) {
    state.recentColors = [hex, ...state.recentColors.filter((c) => c !== hex)].slice(0, 8);
    renderSwatches(); saveState();
  }
}
function colorFromWheel() { const [r, g, b] = hsvToRgb(hsv.h, hsv.s, hsv.v); setColor(toHex(r, g, b), false); }
let wheelDrag = false;
function wheelPoint(e) {
  const rc = wheelCv.getBoundingClientRect(), R = wheelCv.width / 2;
  const x = (e.clientX - rc.left) / rc.width * wheelCv.width - R, y = (e.clientY - rc.top) / rc.height * wheelCv.height - R;
  let h = Math.atan2(y, x) * 180 / Math.PI; if (h < 0) h += 360;
  hsv.h = h; hsv.s = Math.min(1, Math.hypot(x, y) / (R - 1));
  if (hsv.v === 0) hsv.v = 1;   // picking on the wheel from black: bring the brightness up so a color shows
  colorFromWheel();
}
wheelCv.addEventListener('pointerdown', (e) => { wheelCv.setPointerCapture(e.pointerId); wheelDrag = true; wheelPoint(e); e.preventDefault(); });
wheelCv.addEventListener('pointermove', (e) => { if (wheelDrag) wheelPoint(e); });
const endWheel = () => { if (!wheelDrag) return; wheelDrag = false; setColor(state.color, true); };
wheelCv.addEventListener('pointerup', endWheel); wheelCv.addEventListener('pointercancel', endWheel);
$('valInput').addEventListener('input', (e) => { hsv.v = Number(e.target.value) / 100; colorFromWheel(); });
$('valInput').addEventListener('change', () => setColor(state.color, true));
$('hexInput').addEventListener('change', (e) => {
  const m = /^#?([0-9a-f]{6})$/i.exec(e.target.value.trim());
  if (m) setColor('#' + m[1], true); else e.target.value = state.color;
});
function swatchButton(hex) {
  const sw = document.createElement('button');
  sw.type = 'button'; sw.className = 'swatch'; sw.style.background = hex; sw.title = hex;
  sw.setAttribute('aria-label', 'Use color ' + hex);
  sw.addEventListener('click', () => { setColor(hex, true); if (state.tool === 'pick') setTool('paint'); });
  return sw;
}
function renderSwatches() {
  const el = $('swatches'); el.innerHTML = '';
  // recents that are almost the same as a swatch already shown are skipped (near-duplicates just add noise)
  const near = (a, b) => { const p = hexToRgb(a), q = hexToRgb(b); return Math.hypot(p[0] - q[0], p[1] - q[1], p[2] - q[2]) < 24; };
  const shown = [];
  for (const hex of [...basePalette, ...state.recentColors]) if (!shown.some((s) => s === hex || near(s, hex))) shown.push(hex);
  shown.slice(0, 16).forEach((hex) => el.appendChild(swatchButton(hex)));
}
// "In this picture": the colors used across every frame (and the still part), most used first
let imgSwatchKey = '';
function renderImgSwatches() {
  const counts = new Map();
  for (const f of state.frames) for (const h of flatten(f)) if (!isOff(h)) counts.set(h, (counts.get(h) || 0) + 1);
  // imported or hand-shaded art holds many almost-identical shades; fold each into the most used one within a small RGB distance
  const reps = [];
  for (const [hex, n] of [...counts.entries()].sort((x, y) => y[1] - x[1])) {
    const c = hexToRgb(hex), hit = reps.find((r) => Math.hypot(r.c[0] - c[0], r.c[1] - c[1], r.c[2] - c[2]) < 48);
    if (hit) hit.n += n; else reps.push({ hex, c, n });
  }
  const list = reps.sort((x, y) => y.n - x.n).slice(0, 16).map((r) => r.hex);
  const key = list.join(',');
  if (key === imgSwatchKey) return;
  imgSwatchKey = key;
  const el = $('imgSwatches'); el.innerHTML = '';
  list.forEach((hex) => el.appendChild(swatchButton(hex)));
  $('imgSwatchGroup').hidden = !list.length;
}

/* ---------- eyedropper ---------- */
function pickAt(idx, backToPaint) {
  const hex = layerHex(state.frames[state.currentFrame], idx);
  setColor(hex, true);
  if (backToPaint) setTool('paint'); else hideHover();
  setStatus(`Picked ${hex}.`);
}
function showHover(idx) {
  const hex = layerHex(state.frames[state.currentFrame], idx), chip = $('hoverChip');
  chip.hidden = false; chip.firstElementChild.style.background = hex; chip.lastElementChild.textContent = hex;
}
function hideHover() { $('hoverChip').hidden = true; }
gridEl.addEventListener('pointermove', (e) => {
  if (painting || !(state.tool === 'pick' || e.altKey)) return;
  const idx = cellAt(e.clientX, e.clientY);
  if (idx === null) hideHover(); else showHover(idx);
});
gridEl.addEventListener('pointerleave', hideHover);
$('clearBtn').addEventListener('click', () => { stopPlay(); pushUndo(); setEditLayer(newBlankFrame(state.cols, state.rows)); afterFrameChange(); });
$('startOverBtn').addEventListener('click', () => {
  stopPlay(); pushUndo();
  state.frames = [newBlankFrame(state.cols, state.rows)]; state.currentFrame = 0; state.shared = null; state.target = 'frame';
  afterFrameChange(); setStatus('Started over with one blank frame. Undo brings everything back.');
});
const syncRestoreBtn = () => { $('restoreBtn').hidden = !(lastSession && !hasArt(state)); };
$('restoreBtn').addEventListener('click', () => {
  if (!lastSession) return;
  stopPlay(); pushUndo();
  const l = lastSession;
  restore(JSON.stringify({ cols: l.cols, rows: l.rows, frames: l.frames, currentFrame: clamp(l.currentFrame || 0, 0, l.frames.length - 1), shared: (Array.isArray(l.shared) && l.shared.length === l.cols * l.rows) ? l.shared : null }));
  setStatus('Restored your last session. Undo goes back to blank.');
});
$('undoBtn').addEventListener('click', undo);
$('redoBtn').addEventListener('click', redo);
window.addEventListener('keydown', (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.target.matches('input[type=text], input[type=number]')) return;
  const k = e.key.toLowerCase();
  if (k === 'z' && !e.shiftKey) { e.preventDefault(); undo(); }
  else if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); redo(); }
});

/* ---------- LED settings ---------- */
$('flagsToggle').addEventListener('change', (e) => { sim.flags = e.target.checked; deviceEl.classList.toggle('flags-on', sim.flags); saveSim(); });
function readLedSettings() {
  sim.brightness = clamp(Number($('brightInput').value) || 0.3, 0.05, 1);
  sim.gamma = clamp(Number($('gammaInput').value) || 2.2, 1, 3);
  sim.psu = clamp(Number($('psuInput').value) || 6, 1, 60);
  saveSim(); buildLut(); renderFrame(); updateCmd();
  if (sim.brightness > 0.4) setStatus(`Note: the Pi caps brightness at MAX_BRIGHTNESS (0.4 unless you raised it in local_config.py), so ${sim.brightness} will play at 0.4.`);
}
['brightInput', 'gammaInput', 'psuInput'].forEach((id) => $(id).addEventListener('change', readLedSettings));
