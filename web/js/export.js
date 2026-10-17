// PNG metadata, the .gg sprite file and Export. Classic script: shares one global scope with the other files in js/ (load order is in index.html).
/* ---------- light settings stored in the PNG (read by grid_common.image_light) ---------- */
const LIGHT_KEY = 'glow-grid';
const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
  return t;
})();
function crc32(bytes) {
  let c = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) c = CRC_TABLE[(c ^ bytes[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
const ascii = (str) => Uint8Array.from(str, (ch) => ch.charCodeAt(0) & 0xff);
// Stored in the PNG: light settings always; for an animation also the frame count and speed, so a renamed sheet still plays
const lightJson = (extra) => JSON.stringify(Object.assign({ brightness: Math.round(sim.brightness * 1000) / 1000, gamma: Math.round(sim.gamma * 1000) / 1000 }, extra || {}));
// Insert a tEXt chunk right after IHDR (8-byte signature + 25-byte IHDR chunk)
function withPngText(buf, key, text) {
  const src = new Uint8Array(buf);
  const data = ascii(key + '\0' + text), type = ascii('tEXt');
  const chunk = new Uint8Array(12 + data.length);
  const view = new DataView(chunk.buffer);
  view.setUint32(0, data.length);
  chunk.set(type, 4); chunk.set(data, 8);
  const body = new Uint8Array(4 + data.length); body.set(type, 0); body.set(data, 4);
  view.setUint32(8 + data.length, crc32(body));
  const out = new Uint8Array(src.length + chunk.length);
  out.set(src.subarray(0, 33), 0); out.set(chunk, 33); out.set(src.subarray(33), 33 + chunk.length);
  return out;
}
function readPngText(buf, key) {
  const b = new Uint8Array(buf), view = new DataView(b.buffer);
  if (b.length < 8 || b[1] !== 0x50 || b[2] !== 0x4e || b[3] !== 0x47) return null; // not a PNG
  for (let off = 8; off + 12 <= b.length;) {
    const len = view.getUint32(off), type = String.fromCharCode(...b.subarray(off + 4, off + 8));
    if (type === 'IEND') break;
    if (type === 'tEXt') {
      const text = String.fromCharCode(...b.subarray(off + 8, off + 8 + len));
      const nul = text.indexOf('\0');
      if (text.slice(0, nul) === key) return text.slice(nul + 1);
    }
    off += 12 + len;
  }
  return null;
}
function applySavedLight(raw) {
  let l; try { l = JSON.parse(raw); } catch (e) { return false; }
  if (typeof l.brightness !== 'number' && typeof l.gamma !== 'number') return false;
  if (typeof l.brightness === 'number') $('brightInput').value = l.brightness;
  if (typeof l.gamma === 'number') $('gammaInput').value = l.gamma;
  readLedSettings();
  return true;
}

/* ---------- .gg sprite file for the ESP32-C3 player (read by c3/gg_core.h) ---------- */
// 12-byte header: "GG", version 1, flags, cols, rows, frames (u16), fps x10 (u16), brightness %, gamma x10; then raw RGB
// per frame, row by row from the top-left, exactly as drawn. The board applies wiring, gamma and the brightness cap itself.
const GG_MAX_FRAMES = 16;      // frames per sprite for every target (Pi and C3): a 16x16 panel plays simple loops. Same number in c3/c3_player/gg_core.h and c3/tools/gg_format.py
function ggBytes(frames, cols, rows, fps, brightness, gamma) {
  const n = frames.length;
  if (n < 1 || n > GG_MAX_FRAMES) throw new Error(`1 to ${GG_MAX_FRAMES} frames`);
  const fps10 = pyRound(fps * 10), bright = pyRound(brightness * 100), gamma10 = pyRound(gamma * 10);
  if (fps10 < 5 || fps10 > 300) throw new Error('fps 0.5 to 30');
  if (bright < 1 || bright > 100) throw new Error('brightness 0.01 to 1');
  if (gamma10 < 10 || gamma10 > 30) throw new Error('gamma 1.0 to 3.0');
  const out = new Uint8Array(12 + n * cols * rows * 3);
  out.set([0x47, 0x47, 1, 0, cols, rows, n & 0xff, n >> 8, fps10 & 0xff, fps10 >> 8, bright, gamma10], 0);
  let p = 12;
  frames.forEach((f) => {
    for (let i = 0; i < cols * rows; i++) { const [r, g, b] = hexToRgb(f[i]); out[p++] = r; out[p++] = g; out[p++] = b; }
  });
  return out;
}

// The reverse of ggBytes: a .gg file (from File ▸ Open, or read back from the board with GET) to frames and light settings.
// Throws an Error with a plain message for anything that is not a sprite this editor can show.
function ggDecode(b) {
  if (b.length < 12 || b[0] !== 0x47 || b[1] !== 0x47) throw new Error('that is not a Glow Grid sprite file');
  if (b[2] !== 1) throw new Error(`sprite file version ${b[2]} is newer than this editor understands`);
  const cols = b[4], rows = b[5], n = b[6] | (b[7] << 8), fps10 = b[8] | (b[9] << 8), bright = b[10], gamma10 = b[11];
  if (n > GG_MAX_FRAMES) throw new Error(`the sprite has ${n} frames; the limit is ${GG_MAX_FRAMES}`);
  if (!cols || !rows || n < 1) throw new Error('the sprite file header is not valid');
  if (b.length !== 12 + n * cols * rows * 3) throw new Error(`the sprite file is ${b.length} bytes but its header says ${12 + n * cols * rows * 3}; it was cut off or damaged`);
  const frames = [];
  let p = 12;
  for (let k = 0; k < n; k++) {
    const f = new Array(cols * rows);
    for (let i = 0; i < f.length; i++, p += 3) f[i] = toHex(b[p], b[p + 1], b[p + 2]);
    frames.push(f);
  }
  return { cols, rows, frames, fps: fps10 / 10, brightness: bright / 100, gamma: gamma10 / 10 };
}
/* ---------- export ---------- */
let toastTimer = 0;
function setStatus(msg) {
  const t = $('statusEl'); t.textContent = msg; t.classList.toggle('show', !!msg);
  clearTimeout(toastTimer); if (msg) toastTimer = setTimeout(() => t.classList.remove('show'), 5000);
}
const safeName = () => (state.name || '').trim().replace(/[^a-z0-9_-]+/gi, '_').replace(/^_+|_+$/g, '') || 'sprite';
// File name is just the sprite's name. Frames, fps, brightness and gamma live inside the PNG (text chunk).
const frameFile = () => `${safeName()}.png`;
const sheetFile = () => `${safeName()}.png`;
const exportTarget = () => (sim.target === 'view' || sim.target === 'c3' ? sim.target : 'pi');
const exportScale = () => exportTarget() === 'view' ? (Number($('scaleInput').value) || 16) : 1;
const scaledName = (file) => exportScale() > 1 ? file.replace(/\.png$/, `_x${exportScale()}.png`) : file;
// Enlarge each pixel into a sharp block (no smoothing) for viewing/sharing
function scaled(canvas) {
  const k = exportScale(); if (k === 1) return canvas;
  const c = document.createElement('canvas'); c.width = canvas.width * k; c.height = canvas.height * k;
  const x = c.getContext('2d'); x.imageSmoothingEnabled = false;
  x.drawImage(canvas, 0, 0, c.width, c.height);
  return c;
}
function updateCmd() {
  const t = exportTarget();
  document.querySelectorAll('.only-view').forEach((el) => { el.hidden = t !== 'view'; });
}
// Save a file: Chrome and Edge on desktop ask where (File System Access API), asked first while the click still counts as a
// user gesture; other browsers download. makeBlob builds the file after the picker so the picker never waits on it.
async function saveFile(filename, type, makeBlob, detail) {
  let handle = null;
  if (window.showSaveFilePicker && !downloadsCap) {
    try { handle = await window.showSaveFilePicker({ suggestedName: filename, types: [type] }); }
    catch (err) { if (err && err.name === 'AbortError') { setStatus('Save cancelled.'); return; } handle = null; } // any other error: plain download below
  }
  const blob = await makeBlob();
  if (handle) {
    try {
      const w = await handle.createWritable(); await w.write(blob); await w.close();
      setStatus(`Saved ${handle.name} (${detail}).`);
      return;
    } catch (err) { setStatus('The file couldn’t be saved.'); return; }
  }
  if (!downloadsCap && !window.claude) {
    // Opened as a plain file (web/index.html from the repo): ordinary browser download
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    setStatus(`Saved ${filename} (${detail}).`);
    return;
  }
  if (!downloadsCap) { setStatus('Saving files isn’t available in this view.'); return; }
  try {
    const r = await downloadsCap.save({ filename, data: blob });
    if (r && r.status === 'saved') setStatus(`Saved ${filename} (${detail}).`);
    else setStatus('Handed off to the destination you picked.');
  } catch (err) {
    const code = err && err.code;
    if (code === 'declined') setStatus('Save cancelled.');
    else if (code === 'rate_limited') setStatus('A save prompt is already open. Finish that one first.');
    else if (code === 'unavailable') { downloadsCap = null; setStatus('Saving files isn’t available in this view.'); }
    else setStatus('The file couldn’t be saved.');
  }
}
const PNG_TYPE = { description: 'PNG image', accept: { 'image/png': ['.png'] } };
const GG_TYPE = { description: 'Glow Grid sprite', accept: { 'application/octet-stream': ['.gg'] } };
function saveCanvas(canvas, filename, extra) {
  saveFile(filename, PNG_TYPE, async () => {
    const png = await new Promise((res) => canvas.toBlob(res, 'image/png'));
    return new Blob([withPngText(await png.arrayBuffer(), LIGHT_KEY, lightJson(extra))], { type: 'image/png' });
  }, `${canvas.width}×${canvas.height}`);
}
// ESP32-C3: a .gg sprite file for the C3 player (c3/). Put it on the board with c3/tools/gg_tool.py put <file>.
function saveGg() {
  const n = state.frames.length;
  if (state.cols !== 16 || state.rows !== 16) { setStatus(`The C3 player is 16×16; this picture is ${state.cols}×${state.rows}.`); return; }
  if (n > GG_MAX_FRAMES) { setStatus(`The C3 player takes up to ${GG_MAX_FRAMES} frames; this has ${n}.`); return; }
  let bytes;
  try { bytes = ggBytes(state.frames.map(flatten), state.cols, state.rows, state.fps, sim.brightness, sim.gamma); }
  catch (err) { setStatus(`Can’t save for the C3: ${err.message}.`); return; }
  const detail = `${n} frame${n === 1 ? '' : 's'}, ${bytes.length.toLocaleString()} bytes`;
  saveFile(`${safeName()}.gg`, GG_TYPE, async () => new Blob([bytes], { type: 'application/octet-stream' }), detail);
}
// One Save button: 1 frame saves a still, 2 or more save a sprite sheet. Settings go inside the PNG.
$('exportBtn').addEventListener('click', () => {
  if (exportTarget() === 'c3') { saveGg(); return; }
  const n = state.frames.length;
  const c = document.createElement('canvas'); c.width = state.cols * n; c.height = state.rows;
  const ctx = c.getContext('2d');
  state.frames.forEach((f, i) => paintCanvas(ctx, flatten(f), i * state.cols));
  const meta = n > 1 ? { cols: state.cols, rows: state.rows, frames: n, fps: state.fps } : { cols: state.cols, rows: state.rows };
  saveCanvas(scaled(c), scaledName(sheetFile()), meta);
});
$('scaleInput').addEventListener('change', updateCmd);
$('targetInput').addEventListener('change', (e) => { sim.target = e.target.value; saveSim(); updateCmd(); });
// Two fields show the sprite's name (Export and the Board card); every change goes through here so they never disagree.
function setNameField(v, fromId) {
  state.name = v;
  for (const id of ['nameInput', 'boardName']) if (id !== fromId) $(id).value = v;
  if (typeof boardNameHint === 'function') boardNameHint();
}
$('nameInput').addEventListener('input', (e) => { setNameField(e.target.value, 'nameInput'); updateCmd(); saveState(); });
$('boardName').addEventListener('input', (e) => { setNameField(e.target.value, 'boardName'); updateCmd(); saveState(); });

// Put a decoded sprite into the editor: frames, size, name, fps, and the file's own brightness and gamma. Undo brings the old drawing back.
function loadGgSprite(d, name, from) {
  stopPlay(); pushUndo();
  const resized = d.cols !== state.cols || d.rows !== state.rows;
  state.cols = d.cols; state.rows = d.rows; state.frames = d.frames; state.currentFrame = 0; state.shared = null; state.target = 'frame';
  if (resized) { $('colsInput').value = state.cols; $('rowsInput').value = state.rows; buildGridDOM(); }
  state.fps = clamp(Math.round(d.fps), 1, 30); $('fpsInput').value = state.fps;
  setNameField(name);
  $('brightInput').value = d.brightness; $('gammaInput').value = d.gamma;
  readLedSettings();
  afterFrameChange();
  const n = d.frames.length;
  setStatus(`Loaded ${name} from ${from}: ${n} frame${n === 1 ? '' : 's'}, ${state.fps} fps, brightness ${d.brightness}, gamma ${d.gamma}.` + (Math.abs(d.fps - state.fps) > 0.01 ? ` The file plays at ${d.fps} fps; the editor uses whole numbers.` : '') + ' Undo reverts.');
}
const needsReplaceOk = () => !hasArt(state) || confirm('Replace the drawing in the editor with this sprite? Undo brings the old one back.');
async function openGgFile(file) {
  let d;
  try { d = ggDecode(new Uint8Array(await file.arrayBuffer())); } catch (err) { setStatus(`Can’t open ${file.name}: ${err.message}.`); return; }
  if (!needsReplaceOk()) return;
  loadGgSprite(d, ((file.name || '').replace(/\.[^.]+$/, '').replace(/[^a-z0-9_-]+/gi, '_').replace(/^_+|_+$/g, '') || 'sprite').slice(0, 31), 'the file');
}
$('ggInput').addEventListener('change', (e) => { const f = e.target.files[0]; e.target.value = ''; if (f) openGgFile(f); });
