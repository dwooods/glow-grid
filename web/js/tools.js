// Move, still part, playback. Classic script: shares one global scope with the other files in js/ (load order is in index.html).
/* ---------- move and still part ---------- */
function updateLayerUI() {
  const has = !!state.shared, sh = state.target === 'shared' && has;
  $('stillOn').checked = has;
  $('stillOn').disabled = !has && state.frames.length < 2;
  $('layerRow').hidden = !has;
  $('targetFrame').classList.toggle('active', !sh); $('targetFrame').setAttribute('aria-pressed', String(!sh));
  $('targetShared').classList.toggle('active', sh); $('targetShared').setAttribute('aria-pressed', String(sh));
  deviceEl.classList.toggle('edit-shared', sh);
  $('layerHint').innerHTML = has
    ? 'Everything that was identical in every frame is now the <strong>still part</strong>. With <em>Moving part</em> selected, paint only what changes. Pick <em>Still part</em> to edit the body for all frames at once. On a frame, black means see-through. Untick to join it back. Saved files always combine both, so the Pi needs nothing new.'
    : 'The arrows (or Shift+arrow keys) move this frame one pixel. To animate just one part (eyes, a hand, legs) while the rest stays put: draw the whole picture, press <em>+ Duplicate</em> once per extra frame, then tick <em>Animate one part only</em>. It is optional: you can also just paint each frame.';
}
function shiftArr(arr, dx, dy, wrap) {
  const { cols, rows } = state, out = new Array(arr.length).fill('#000000');
  for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
    let nx = x + dx, ny = y + dy;
    if (wrap) { nx = (nx + cols) % cols; ny = (ny + rows) % rows; }
    else if (nx < 0 || ny < 0 || nx >= cols || ny >= rows) continue;
    out[ny * cols + nx] = arr[y * cols + x];
  }
  return out;
}
function nudge(dx, dy) {
  if (playing) return;
  pushUndo();
  if (state.target === 'shared' && state.shared) state.shared = shiftArr(state.shared, dx, dy, false);
  else state.frames[state.currentFrame] = shiftArr(state.frames[state.currentFrame], dx, dy, false);
  afterFrameChange();
}
$('nudgeUp').addEventListener('click', () => nudge(0, -1));
$('nudgeDown').addEventListener('click', () => nudge(0, 1));
$('nudgeLeft').addEventListener('click', () => nudge(-1, 0));
$('nudgeRight').addEventListener('click', () => nudge(1, 0));
window.addEventListener('keydown', (e) => {
  if (!e.shiftKey || e.ctrlKey || e.metaKey || e.altKey || e.target.matches('input, select, textarea') || $('photoDlg').open) return;
  const d = { ArrowUp: [0, -1], ArrowDown: [0, 1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] }[e.key];
  if (d) { e.preventDefault(); nudge(d[0], d[1]); }
});
function setTarget(t) {
  if (t === 'shared' && !state.shared) return;
  state.target = t; afterFrameChange();
  setStatus(t === 'shared' ? 'Editing the still part: it sits under every frame.' : 'Editing the moving part of this frame only.');
}
$('targetFrame').addEventListener('click', () => setTarget('frame'));
$('targetShared').addEventListener('click', () => setTarget('shared'));
function separateStill() {
  if (state.shared || state.frames.length < 2) return false;
  stopPlay(); pushUndo();
  const n = state.cols * state.rows, sh = newBlankFrame(state.cols, state.rows);
  let moved = 0;
  for (let i = 0; i < n; i++) {
    const v = state.frames[0][i];
    if (!isOff(v) && state.frames.every((f) => f[i] === v)) { sh[i] = v; moved++; }
  }
  if (!moved) { undoStack.pop(); updateUndoBtns(); setStatus('No pixel is the same in every frame, so there is no still part yet. Duplicate your picture into more frames first.'); return false; }
  state.shared = sh; state.target = 'frame';
  state.frames = state.frames.map((f) => f.map((v, i) => (sh[i] !== '#000000' && v === sh[i]) ? '#000000' : v));
  afterFrameChange();
  setStatus(`Moved ${moved} unchanging pixels into the still part. Each frame now holds only what moves. Undo reverts.`);
  return true;
}
function joinStill() {
  if (!state.shared) return;
  stopPlay(); pushUndo();
  state.frames = state.frames.map((f) => flatten(f).slice());
  state.shared = null; state.target = 'frame';
  afterFrameChange();
  setStatus('Joined the still part back into every frame. Undo reverts.');
}
$('stillOn').addEventListener('change', (e) => {
  if (e.target.checked) { if (!separateStill()) e.target.checked = false; }
  else joinStill();
});

/* ---------- playback ---------- */
function startPlay() {
  if (playTimer) clearInterval(playTimer);
  playTimer = setInterval(() => {
    state.currentFrame = (state.currentFrame + 1) % state.frames.length;
    renderFrame(); updateReadout();
    document.querySelectorAll('.frame-thumb').forEach((t, i) => t.classList.toggle('active', i === state.currentFrame));
  }, 1000 / state.fps);
}
function stopPlay() {
  if (playTimer) clearInterval(playTimer);
  playTimer = null; playing = false; $('playBtn').textContent = '▶ Play';
}
$('playBtn').addEventListener('click', () => {
  if (playing) { stopPlay(); renderFrameStrip(); saveState(); return; }
  if (state.frames.length < 2) { setStatus('Add a second frame to play an animation.'); return; }
  playing = true; $('playBtn').textContent = '⏸ Pause'; startPlay();
});
$('fpsInput').addEventListener('change', (e) => {
  state.fps = clamp(Math.round(Number(e.target.value)) || 6, 1, 30); e.target.value = state.fps;
  if (playing) startPlay(); updateCmd(); saveState();
});

