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
  if (sim.view === 'sim') {
    const [r, g, b] = hexToRgb(a.disp);
    const glow = Math.max(r, g, b) / 255;
    cell.style.background = `radial-gradient(circle, ${a.disp} 35%, rgba(${r},${g},${b},0.75) 70%, rgba(${r},${g},${b},0.35) 100%)`;
    cell.style.boxShadow = `0 0 ${Math.round(4 + glow * 10)}px ${Math.round(glow * 3)}px rgba(${r},${g},${b},${(0.25 + glow * 0.45).toFixed(2)})`;
  } else {
    const [r, g, b] = hexToRgb(hex);
    cell.style.background = hex;
    cell.style.boxShadow = `0 0 6px 1px rgba(${r},${g},${b},0.5)`;
  }
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
  const fc = $('faintCount'), sc = $('shiftCount');
  fc.textContent = now.faint + ' px'; fc.classList.toggle('zero', !now.faint);
  sc.textContent = now.shift + ' px'; sc.classList.toggle('zero', !now.shift);
}
function renderFrame() { for (let i = 0; i < cellEls.length; i++) updateCell(i); renderDiagnostics(); }
function renderFrameStrip() {
  const strip = $('frameStrip'); strip.innerHTML = '';
  state.frames.forEach((frame, i) => {
    const t = document.createElement('canvas');
    t.width = state.cols; t.height = state.rows;
    t.className = 'frame-thumb' + (i === state.currentFrame ? ' active' : '');
    t.tabIndex = 0; t.setAttribute('role', 'button'); t.setAttribute('aria-label', 'Frame ' + (i + 1));
    paintCanvas(t.getContext('2d'), flatten(frame), 0);
    t.addEventListener('click', () => selectFrame(i));
    t.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectFrame(i); } });
    strip.appendChild(t);
  });
}
function paintCanvas(ctx, frame, offsetX) {
  const img = ctx.createImageData(state.cols, state.rows);
  for (let p = 0; p < frame.length; p++) {
    const [r, g, b] = hexToRgb(frame[p]);
    img.data.set([r, g, b, 255], p * 4);
  }
  ctx.putImageData(img, offsetX, 0);
}
const updateReadout = () => { $('frameReadout').textContent = `Frame ${state.currentFrame + 1} / ${state.frames.length}`; };
function afterFrameChange() { renderFrame(); renderFrameStrip(); updateReadout(); updateLayerUI(); updateCmd(); saveState(); }
function selectFrame(i) { stopPlay(); state.currentFrame = i; afterFrameChange(); }

/* ---------- frames ---------- */
$('addFrameBtn').addEventListener('click', () => { stopPlay(); pushUndo(); state.frames.splice(state.currentFrame + 1, 0, [...state.frames[state.currentFrame]]); state.currentFrame++; afterFrameChange(); });
$('addBlankFrameBtn').addEventListener('click', () => { stopPlay(); pushUndo(); state.frames.splice(state.currentFrame + 1, 0, newBlankFrame(state.cols, state.rows)); state.currentFrame++; afterFrameChange(); });
$('deleteFrameBtn').addEventListener('click', () => {
  if (state.frames.length <= 1) return;
  stopPlay(); pushUndo();
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
  pushUndo(); painting = true; applyTool(idx); e.preventDefault();
});
window.addEventListener('pointermove', (e) => {
  if (!painting || state.tool === 'fill') return;
  const idx = cellAt(e.clientX, e.clientY); if (idx !== null) applyTool(idx);
});
const endPaint = () => { if (!painting) return; painting = false; renderDiagnostics(); renderFrameStrip(); saveState(); };
window.addEventListener('pointerup', endPaint);
window.addEventListener('pointercancel', endPaint);

document.querySelectorAll('.tool-btn[data-tool]').forEach((btn) => btn.addEventListener('click', () => {
  document.querySelectorAll('.tool-btn[data-tool]').forEach((b) => b.classList.remove('active'));
  btn.classList.add('active'); state.tool = btn.dataset.tool;
}));
function renderSwatches() {
  const el = $('swatches'); el.innerHTML = '';
  [...new Set([...basePalette, ...state.recentColors])].slice(0, 16).forEach((hex) => {
    const sw = document.createElement('button');
    sw.type = 'button'; sw.className = 'swatch'; sw.style.background = hex; sw.title = hex;
    sw.setAttribute('aria-label', 'Use color ' + hex);
    sw.addEventListener('click', () => { state.color = hex; $('colorPicker').value = hex; });
    el.appendChild(sw);
  });
}
$('colorPicker').addEventListener('input', (e) => { state.color = e.target.value; });
$('colorPicker').addEventListener('change', (e) => {
  state.recentColors = [e.target.value, ...state.recentColors.filter((c) => c !== e.target.value)].slice(0, 8);
  renderSwatches(); saveState();
});
$('clearBtn').addEventListener('click', () => { stopPlay(); pushUndo(); setEditLayer(newBlankFrame(state.cols, state.rows)); afterFrameChange(); });
$('undoBtn').addEventListener('click', undo);
$('redoBtn').addEventListener('click', redo);
window.addEventListener('keydown', (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.target.matches('input[type=text], input[type=number]')) return;
  const k = e.key.toLowerCase();
  if (k === 'z' && !e.shiftKey) { e.preventDefault(); undo(); }
  else if (k === 'y' || (k === 'z' && e.shiftKey)) { e.preventDefault(); redo(); }
});

/* ---------- view + LED settings ---------- */
function setView(v) {
  sim.view = v; saveSim();
  $('viewDesign').setAttribute('aria-pressed', String(v === 'design'));
  $('viewSim').setAttribute('aria-pressed', String(v === 'sim'));
  gridEl.classList.toggle('sim', v === 'sim');
  renderFrame();
}
$('viewDesign').addEventListener('click', () => setView('design'));
$('viewSim').addEventListener('click', () => setView('sim'));
$('flagsToggle').addEventListener('change', (e) => { sim.flags = e.target.checked; deviceEl.classList.toggle('flags-on', sim.flags); saveSim(); });
function readLedSettings() {
  sim.brightness = clamp(Number($('brightInput').value) || 0.3, 0.05, 1);
  sim.gamma = clamp(Number($('gammaInput').value) || 2.2, 1, 3);
  sim.psu = clamp(Number($('psuInput').value) || 6, 1, 60);
  saveSim(); buildLut(); renderFrame(); updateCmd();
  if (sim.brightness > 0.4) setStatus(`Note: the Pi caps brightness at MAX_BRIGHTNESS (0.4 unless you raised it in local_config.py), so ${sim.brightness} will play at 0.4.`);
}
['brightInput', 'gammaInput', 'psuInput'].forEach((id) => $(id).addEventListener('change', readLedSettings));

