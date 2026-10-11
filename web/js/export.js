// PNG metadata and Export image. Classic script: shares one global scope with the other files in js/ (load order is in index.html).
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

/* ---------- export ---------- */
function setStatus(msg) { $('statusEl').textContent = msg; }
const safeName = () => (state.name || '').trim().replace(/[^a-z0-9_-]+/gi, '_').replace(/^_+|_+$/g, '') || 'sprite';
// File name is just the sprite's name. Frames, fps, brightness and gamma live inside the PNG (text chunk).
const frameFile = () => `${safeName()}.png`;
const sheetFile = () => `${safeName()}.png`;
const exportTarget = () => (sim.target === 'view' ? 'view' : 'pi');
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
  const t = exportTarget(), n = state.frames.length, k = exportScale();
  const f = scaledName(sheetFile());
  const pi = (sim.pi || '').trim() || 'user@raspberrypi.local';
  const dir = ((sim.pcDir || '').trim() || '$HOME\\Downloads').replace(/[\\/]+$/, '');
  document.querySelectorAll('.only-pi').forEach((el) => { el.hidden = t !== 'pi'; });
  document.querySelectorAll('.only-view').forEach((el) => { el.hidden = t !== 'view'; });
  $('exportBtn').textContent = t === 'pi' ? 'Save for the Pi' : 'Save to view';
  // Quoted so folders with spaces work; PowerShell still expands $HOME inside double quotes
  if (t === 'pi') $('cmdOut').textContent =
    `scp "${dir}\\${f}" ${pi}:~/glow-grid/images/\n` +
    `# then run glow-grid, press r to rescan, and pick ${f}`;
  const w = state.cols * n * k, h = state.rows * k;
  $('exportInfo').textContent = t === 'pi'
    ? (n > 1 ? `Saves one ${w}×${h} sprite sheet: ${n} frames of ${state.cols}×${state.rows} at ${state.fps} fps.` : `Saves one ${w}×${h} still image.`)
    : `Saves one ${w}×${h} enlarged PNG (${k}× per LED) to look at or share. It isn't meant for the Pi.`;
}
async function saveCanvas(canvas, filename, extra) {
  const png = await new Promise((res) => canvas.toBlob(res, 'image/png'));
  const blob = new Blob([withPngText(await png.arrayBuffer(), LIGHT_KEY, lightJson(extra))], { type: 'image/png' });
  if (!downloadsCap && !window.claude) {
    // Opened as a plain file (web/index.html from the repo): ordinary browser download
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    setStatus(`Saved ${filename} (${canvas.width}×${canvas.height}).`);
    return;
  }
  if (!downloadsCap) { setStatus('Saving files isn’t available in this view.'); return; }
  try {
    const r = await downloadsCap.save({ filename, data: blob });
    if (r && r.status === 'saved') setStatus(`Saved ${filename} (${canvas.width}×${canvas.height}).`);
    else setStatus('Handed off to the destination you picked.');
  } catch (err) {
    const code = err && err.code;
    if (code === 'declined') setStatus('Save cancelled.');
    else if (code === 'rate_limited') setStatus('A save prompt is already open. Finish that one first.');
    else if (code === 'unavailable') { downloadsCap = null; setStatus('Saving files isn’t available in this view.'); }
    else setStatus('The file couldn’t be saved.');
  }
}
// One Save button: 1 frame saves a still, 2 or more save a sprite sheet. Settings go inside the PNG.
$('exportBtn').addEventListener('click', () => {
  const n = state.frames.length;
  const c = document.createElement('canvas'); c.width = state.cols * n; c.height = state.rows;
  const ctx = c.getContext('2d');
  state.frames.forEach((f, i) => paintCanvas(ctx, flatten(f), i * state.cols));
  const meta = n > 1 ? { cols: state.cols, rows: state.rows, frames: n, fps: state.fps } : { cols: state.cols, rows: state.rows };
  saveCanvas(scaled(c), scaledName(sheetFile()), meta);
});
$('scaleInput').addEventListener('change', updateCmd);
$('targetInput').addEventListener('change', (e) => { sim.target = e.target.value; saveSim(); updateCmd(); });
$('nameInput').addEventListener('input', (e) => { state.name = e.target.value; updateCmd(); saveState(); });
$('piInput').addEventListener('input', (e) => { sim.pi = e.target.value; updateCmd(); saveSim(); });
$('pcDirInput').addEventListener('input', (e) => { sim.pcDir = e.target.value; updateCmd(); saveSim(); });
$('copyCmdBtn').addEventListener('click', async () => {
  const text = $('cmdOut').textContent;
  try { await navigator.clipboard.writeText(text); setStatus('Commands copied.'); }
  catch (e) {
    const r = document.createRange(); r.selectNodeContents($('cmdOut'));
    const s = getSelection(); s.removeAllRanges(); s.addRange(r);
    setStatus('Clipboard is blocked here. The text is selected, so press Ctrl+C.');
  }
});

