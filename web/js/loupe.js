// Touch magnifier: a finger hides the pixels it paints, so while a finger or pen draws, show a 7x7 close-up of the
// neighbourhood in a floating loupe beside the touch point. Mouse input never shows it. Classic script, shares the global scope.
const LOUPE_N = 7, LOUPE_SIZE = 124, LOUPE_GAP = 56;
const loupeEl = document.createElement('div');
loupeEl.id = 'loupe'; loupeEl.hidden = true; loupeEl.setAttribute('aria-hidden', 'true');
const loupeCells = [];
for (let i = 0; i < LOUPE_N * LOUPE_N; i++) { const c = document.createElement('i'); loupeEl.appendChild(c); loupeCells.push(c); }
loupeCells[(LOUPE_N * LOUPE_N - 1) / 2].className = 'center';
document.body.appendChild(loupeEl);

let loupeOn = false;
function drawLoupe(idx, x, y) {
  const f = state.frames[state.currentFrame], half = (LOUPE_N - 1) / 2;
  const cx = idx % state.cols, cy = Math.floor(idx / state.cols);
  for (let dy = -half; dy <= half; dy++) for (let dx = -half; dx <= half; dx++) {
    const gx = cx + dx, gy = cy + dy, el = loupeCells[(dy + half) * LOUPE_N + dx + half];
    if (gx < 0 || gy < 0 || gx >= state.cols || gy >= state.rows) { el.style.background = 'transparent'; el.classList.add('out'); continue; }
    el.classList.remove('out');
    const hex = layerHex(f, gy * state.cols + gx);
    el.style.background = led(hex).isBlack ? '' : hex;
  }
  // Above the finger when there is room, otherwise to the side away from it, so the hand never covers it
  const vw = window.innerWidth, vh = window.innerHeight;
  let left = x - LOUPE_SIZE / 2, top = y - LOUPE_SIZE - LOUPE_GAP;
  if (top < 8) { left = x < vw / 2 ? x + LOUPE_GAP : x - LOUPE_SIZE - LOUPE_GAP; top = y - LOUPE_SIZE / 2; }
  loupeEl.style.left = clamp(left, 8, vw - LOUPE_SIZE - 8) + 'px';
  loupeEl.style.top = clamp(top, 8, vh - LOUPE_SIZE - 8) + 'px';
  loupeEl.hidden = false;
}
const hideLoupe = () => { loupeOn = false; loupeEl.hidden = true; };
const loupeWanted = (e) => e.pointerType !== 'mouse' && !playing && (state.tool === 'paint' || state.tool === 'erase') && !e.altKey;

// Runs after editor.js has handled the same event, so the cell under the finger is already painted
gridEl.addEventListener('pointerdown', (e) => {
  if (!loupeWanted(e)) return;
  const idx = cellAt(e.clientX, e.clientY); if (idx === null) return;
  loupeOn = true; drawLoupe(idx, e.clientX, e.clientY);
});
window.addEventListener('pointermove', (e) => {
  if (!loupeOn) return;
  const idx = cellAt(e.clientX, e.clientY);
  if (idx !== null) drawLoupe(idx, e.clientX, e.clientY);
});
window.addEventListener('pointerup', hideLoupe);
window.addEventListener('pointercancel', hideLoupe);
