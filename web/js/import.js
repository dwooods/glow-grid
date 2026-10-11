// Import, photo-to-grid, resize. Classic script: shares one global scope with the other files in js/ (load order is in index.html).
/* ---------- import ---------- */
// Fit like grid_common.fit(): keep aspect, center, composite alpha over black
function fitImage(src, sw, sh, mode) {
  const cols = state.cols, rows = state.rows;
  if (mode === 'auto') mode = (sw > 2 * cols || sh > 2 * rows) ? 'photo' : 'pixel';
  const s = Math.min(cols / sw, rows / sh);
  const nw = Math.max(1, pyRound(sw * s)), nh = Math.max(1, pyRound(sh * s));
  const ox = Math.floor((cols - nw) / 2), oy = Math.floor((rows - nh) / 2);
  const out = newBlankFrame(cols, rows);
  let data;
  if (mode === 'photo') {
    let cur = src, cw = sw, ch = sh;
    while (cw / 2 >= nw && ch / 2 >= nh) { // halve step by step for a true area average
      const c = document.createElement('canvas'); c.width = Math.floor(cw / 2); c.height = Math.floor(ch / 2);
      const x = c.getContext('2d'); x.imageSmoothingEnabled = true; x.imageSmoothingQuality = 'high';
      x.drawImage(cur, 0, 0, cw, ch, 0, 0, c.width, c.height);
      cur = c; cw = c.width; ch = c.height;
    }
    const c = document.createElement('canvas'); c.width = nw; c.height = nh;
    const x = c.getContext('2d'); x.imageSmoothingEnabled = true; x.imageSmoothingQuality = 'high';
    x.drawImage(cur, 0, 0, cw, ch, 0, 0, nw, nh);
    data = x.getImageData(0, 0, nw, nh).data;
    for (let y = 0; y < nh; y++) for (let xx = 0; xx < nw; xx++) put(out, ox + xx, oy + y, data, (y * nw + xx) * 4);
  } else {
    const c = document.createElement('canvas'); c.width = sw; c.height = sh;
    const x = c.getContext('2d'); x.drawImage(src, 0, 0);
    data = x.getImageData(0, 0, sw, sh).data;
    for (let y = 0; y < nh; y++) for (let xx = 0; xx < nw; xx++) {
      const sx = Math.min(sw - 1, Math.floor((xx + 0.5) * sw / nw)), sy = Math.min(sh - 1, Math.floor((y + 0.5) * sh / nh));
      put(out, ox + xx, oy + y, data, (sy * sw + sx) * 4);
    }
  }
  return out;
}
function put(out, x, y, d, i) {
  const a = d[i + 3] / 255;
  out[y * state.cols + x] = toHex(Math.round(d[i] * a), Math.round(d[i + 1] * a), Math.round(d[i + 2] * a));
}
// One import path. Sprite sheets (and single frames saved from here) load straight in; everything else opens the crop dialog.
$('imageInput').addEventListener('change', async (e) => {
  const file = e.target.files[0]; e.target.value = ''; if (!file) return;
  let raw = null, meta = {};
  try { raw = readPngText(await file.arrayBuffer(), LIGHT_KEY); meta = JSON.parse(raw) || {}; } catch (err) { meta = {}; }
  const url = URL.createObjectURL(file), img = new Image();
  img.onerror = () => { URL.revokeObjectURL(url); setStatus('That file couldn’t be read as an image.'); };
  img.onload = () => {
    URL.revokeObjectURL(url);
    const w = img.naturalWidth, h = img.naturalHeight, n = w / state.cols;
    const byMeta = Number.isInteger(meta.frames) && meta.frames > 1 && w === meta.frames * state.cols;
    const isSheet = h === state.rows && Number.isInteger(n) && n > 1 && (byMeta || /_(\d+(\.\d+)?)fps|_sheet/i.test(file.name));
    const isOwnFrame = !isSheet && typeof meta.brightness === 'number' && w === state.cols && h === state.rows;
    if (!isSheet && !isOwnFrame) { openImport(file); return; }
    stopPlay(); pushUndo();
    if (isSheet) {
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      const x = c.getContext('2d'); x.drawImage(img, 0, 0);
      state.frames = []; state.shared = null; state.target = 'frame';
      for (let k = 0; k < n; k++) {
        const piece = document.createElement('canvas'); piece.width = state.cols; piece.height = state.rows;
        piece.getContext('2d').drawImage(c, k * state.cols, 0, state.cols, state.rows, 0, 0, state.cols, state.rows);
        state.frames.push(fitImage(piece, state.cols, state.rows, 'pixel'));
      }
      state.currentFrame = 0;
      const m = /_(\d+)fps/i.exec(file.name);
      if (typeof meta.fps === 'number' && meta.fps > 0) { state.fps = clamp(meta.fps, 1, 30); $('fpsInput').value = state.fps; }
      else if (m) { state.fps = clamp(Number(m[1]), 1, 30); $('fpsInput').value = state.fps; }
      const base = file.name.replace(/\.[^.]+$/, '').replace(/_bright\d+(\.\d+)?_gamma\d+(\.\d+)?(_x\d+)?$/i, '').replace(/_(\d+fps|sheet)$/i, '');
      if (base) { state.name = base; $('nameInput').value = base; }
      setStatus(`Loaded ${n} frames from the sprite sheet. Undo reverts.`);
    } else {
      setEditLayer(fitImage(img, w, h, 'pixel'));
      setStatus(`Frame loaded onto frame ${state.currentFrame + 1}. Undo reverts.`);
    }
    afterFrameChange();
    if (raw && applySavedLight(raw)) setStatus($('statusEl').textContent + ` Loaded its light settings: brightness ${sim.brightness}, gamma ${sim.gamma}.`);
  };
  img.src = url;
});


/* ---------- photo to grid: crop, zoom, background-off, dither ---------- */
// Exact area average of a source rectangle onto cols x rows, like PIL's BOX filter.
// Anything outside the photo counts as transparent black. With bg set, pixels near
// bg.rgb (or transparent) are "background": a cell is off if under half foreground,
// otherwise it takes the foreground-only average, so edges don't get a muddy halo.
function boxCrop(d, w, h, view, cols, rows, bg) {
  const out = new Float32Array(cols * rows * 3);
  const cw = view.vw / cols, ch = view.vh / rows;
  const tol2 = bg ? bg.tol * bg.tol : 0;
  for (let cy = 0; cy < rows; cy++) for (let cx = 0; cx < cols; cx++) {
    const x0 = view.x0 + cx * cw, x1 = x0 + cw, y0 = view.y0 + cy * ch, y1 = y0 + ch;
    const ix0 = Math.max(0, Math.floor(x0)), ix1 = Math.min(w, Math.ceil(x1));
    const iy0 = Math.max(0, Math.floor(y0)), iy1 = Math.min(h, Math.ceil(y1));
    let sr = 0, sg = 0, sb = 0, fr = 0, fg = 0, fb = 0, wFg = 0;
    for (let y = iy0; y < iy1; y++) {
      const wy = Math.min(y1, y + 1) - Math.max(y0, y);
      for (let x = ix0; x < ix1; x++) {
        const wgt = (Math.min(x1, x + 1) - Math.max(x0, x)) * wy;
        const i = (y * w + x) * 4, a = d[i + 3] / 255;
        const r = d[i] * a, g = d[i + 1] * a, b = d[i + 2] * a;
        sr += r * wgt; sg += g * wgt; sb += b * wgt;
        if (bg) {
          const dr = d[i] - bg.rgb[0], dg = d[i + 1] - bg.rgb[1], db = d[i + 2] - bg.rgb[2];
          if (bg.mask ? bg.mask[y * w + x] : (a < 0.05 || dr * dr + dg * dg + db * db <= tol2)) continue;
          fr += r * wgt; fg += g * wgt; fb += b * wgt; wFg += wgt;
        }
      }
    }
    const area = cw * ch, o = (cy * cols + cx) * 3;
    if (bg) {
      if (wFg / area < 0.5) { out[o] = out[o + 1] = out[o + 2] = 0; }
      else { out[o] = fr / wFg; out[o + 1] = fg / wFg; out[o + 2] = fb / wFg; }
    } else { out[o] = sr / area; out[o + 1] = sg / area; out[o + 2] = sb / area; }
  }
  return out;
}

// Exact pixels: sample the middle of each cell, no averaging (pixel art). Same background rule as boxCrop.
function pointCrop(d, w, h, view, cols, rows, bg) {
  const out = new Float32Array(cols * rows * 3);
  const cw = view.vw / cols, ch = view.vh / rows, tol2 = bg ? bg.tol * bg.tol : 0;
  for (let cy = 0; cy < rows; cy++) for (let cx = 0; cx < cols; cx++) {
    const x = Math.floor(view.x0 + (cx + 0.5) * cw), y = Math.floor(view.y0 + (cy + 0.5) * ch);
    if (x < 0 || y < 0 || x >= w || y >= h) continue;
    const i = (y * w + x) * 4, a = d[i + 3] / 255;
    if (bg) {
      const dr = d[i] - bg.rgb[0], dg = d[i + 1] - bg.rgb[1], db = d[i + 2] - bg.rgb[2];
      if (bg.mask ? bg.mask[y * w + x] : (a < 0.05 || dr * dr + dg * dg + db * db <= tol2)) continue;
    }
    const o = (cy * cols + cx) * 3;
    out[o] = d[i] * a; out[o + 1] = d[i + 1] * a; out[o + 2] = d[i + 2] * a;
  }
  return out;
}

// Turn float RGB (0..255) into a frame of hex colors. Dithering works in LED space:
// the target is what the LED should emit (brightness and gamma applied, not rounded),
// and each channel is snapped to a level the LED can really produce, with the error
// spread to neighbors. Pure black stays black so "off" LEDs never speckle.
const BAYER4 = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5];
function ditherFrame(rgb, cols, rows, mode, lut, brightness, gamma) {
  const levels = [], rep = [];
  for (let v = 0; v < 256; v++) {
    const L = lut[v], k = levels.length - 1;
    if (k >= 0 && levels[k] === L) rep[k].push(v); else { levels.push(L); rep.push([v]); }
  }
  const repV = rep.map((a) => a[a.length >> 1]);
  const top = levels.length - 1;
  const nearest = (X) => { // index of the achievable level closest to X
    let lo = 0, hi = top;
    while (lo < hi) { const m = (lo + hi) >> 1; if (levels[m] < X) lo = m + 1; else hi = m; }
    return lo > 0 && X - levels[lo - 1] <= levels[lo] - X ? lo - 1 : lo;
  };
  const target = (c) => 255 * brightness * Math.pow(Math.max(0, Math.min(255, c)) / 255, gamma);
  const frame = new Array(cols * rows);
  const n = cols * rows;
  if (mode === 'none') {
    for (let p = 0; p < n; p++) frame[p] = toHex(...[0, 1, 2].map((k) => Math.max(0, Math.min(255, Math.round(rgb[p * 3 + k])))));
    return frame;
  }
  const T = new Float32Array(n * 3);
  const black = new Uint8Array(n);
  for (let p = 0; p < n; p++) {
    const r = Math.round(rgb[p * 3]), g = Math.round(rgb[p * 3 + 1]), b = Math.round(rgb[p * 3 + 2]);
    black[p] = (r + g + b === 0) ? 1 : 0;
    T[p * 3] = target(rgb[p * 3]); T[p * 3 + 1] = target(rgb[p * 3 + 1]); T[p * 3 + 2] = target(rgb[p * 3 + 2]);
  }
  const res = new Uint8Array(n * 3);
  if (mode === 'bayer') {
    for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
      const p = y * cols + x; if (black[p]) continue;
      const th = (BAYER4[(y & 3) * 4 + (x & 3)] + 0.5) / 16;
      for (let k = 0; k < 3; k++) {
        const X = T[p * 3 + k];
        let i = 0; while (i < top && levels[i + 1] <= X) i++;      // largest level <= X
        const j = Math.min(top, i + 1);
        const frac = j === i ? 0 : (X - levels[i]) / (levels[j] - levels[i]);
        res[p * 3 + k] = repV[frac > th ? j : i];
      }
    }
  } else { // Floyd–Steinberg, serpentine
    for (let y = 0; y < rows; y++) {
      const ltr = (y & 1) === 0;
      for (let xi = 0; xi < cols; xi++) {
        const x = ltr ? xi : cols - 1 - xi, p = y * cols + x;
        if (black[p]) continue;
        const dir = ltr ? 1 : -1;
        for (let k = 0; k < 3; k++) {
          const X = T[p * 3 + k], li = nearest(X), e = X - levels[li];
          res[p * 3 + k] = repV[li];
          const push = (xx, yy, wgt) => {
            if (xx < 0 || xx >= cols || yy >= rows) return;
            const q = yy * cols + xx; if (black[q]) return;
            T[q * 3 + k] += e * wgt;
          };
          push(x + dir, y, 7 / 16); push(x - dir, y + 1, 3 / 16); push(x, y + 1, 5 / 16); push(x + dir, y + 1, 1 / 16);
        }
      }
    }
  }
  for (let p = 0; p < n; p++) frame[p] = black[p] ? '#000000' : toHex(res[p * 3], res[p * 3 + 1], res[p * 3 + 2]);
  return frame;
}
window.GlowPhoto = { boxCrop, ditherFrame }; // exposed so the Pi-parity test can call it

const photo = { w: 0, h: 0, data: null, canvas: null, cx: 0, cy: 0, vw: 1, vwMin: 1, vwMax: 1, bg: { on: false, rgb: [0, 0, 0], tol: 45 }, picking: false, dither: 'none', exact: false, queued: false };
const cropCv = $('cropCanvas'), cropCtx = cropCv.getContext('2d');
const viewH = () => photo.vw * state.rows / state.cols;

async function decodeFile(file) {
  let src;
  try { src = await createImageBitmap(file); } // honors EXIF rotation
  catch (e) {
    src = await new Promise((res, rej) => { const u = URL.createObjectURL(file), im = new Image(); im.onload = () => { URL.revokeObjectURL(u); res(im); }; im.onerror = rej; im.src = u; });
  }
  const sw = src.width || src.naturalWidth, sh = src.height || src.naturalHeight;
  const k = Math.min(1, 1400 / Math.max(sw, sh));
  const w = Math.max(1, Math.round(sw * k)), h = Math.max(1, Math.round(sh * k));
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const x = c.getContext('2d', { willReadFrequently: true }); x.imageSmoothingQuality = 'high'; x.drawImage(src, 0, 0, w, h);
  if (src.close) src.close();
  return { canvas: c, w, h, data: x.getImageData(0, 0, w, h).data };
}
function setZoomFromSlider() {
  const t = Number($('photoZoom').value) / 100;
  photo.vw = Math.exp(Math.log(photo.vwMax) * (1 - t) + Math.log(photo.vwMin) * t);
  schedulePhoto();
}
function syncSlider() {
  const t = (Math.log(photo.vwMax) - Math.log(photo.vw)) / (Math.log(photo.vwMax) - Math.log(photo.vwMin));
  $('photoZoom').value = String(Math.round(clamp(t, 0, 1) * 100));
}
function fitView(fill) {
  const need = [photo.w, photo.h * state.cols / state.rows];
  photo.vw = fill ? Math.min(...need) : Math.max(...need);
  photo.cx = photo.w / 2; photo.cy = photo.h / 2; syncSlider(); schedulePhoto();
}
function schedulePhoto() { if (photo.queued) return; photo.queued = true; requestAnimationFrame(() => { photo.queued = false; renderPhoto(); }); }
const viewRect = () => ({ x0: photo.cx - photo.vw / 2, y0: photo.cy - viewH() / 2, vw: photo.vw, vh: viewH() });

// Background = pixels near the background color (or transparent) that connect to the picture's edge.
// White inside the subject (a face, an eye) is enclosed by other colors, so it is kept.
function bgMask() {
  const { w, h, data } = photo, key = photo.bg.rgb.join(',') + '|' + photo.bg.tol;
  if (photo.maskKey === key && photo.mask) return photo.mask;
  const tol2 = photo.bg.tol * photo.bg.tol, c = photo.bg.rgb;
  const near = new Uint8Array(w * h);
  for (let p = 0; p < w * h; p++) {
    const i = p * 4, dr = data[i] - c[0], dg = data[i + 1] - c[1], db = data[i + 2] - c[2];
    near[p] = (data[i + 3] < 13 || dr * dr + dg * dg + db * db <= tol2) ? 1 : 0;
  }
  const mask = new Uint8Array(w * h), stack = [];
  const seed = (p) => { if (near[p] && !mask[p]) { mask[p] = 1; stack.push(p); } };
  for (let x = 0; x < w; x++) { seed(x); seed((h - 1) * w + x); }
  for (let y = 0; y < h; y++) { seed(y * w); seed(y * w + w - 1); }
  while (stack.length) {
    const p = stack.pop(), x = p % w;
    if (x > 0) seed(p - 1);
    if (x < w - 1) seed(p + 1);
    if (p >= w) seed(p - w);
    if (p < w * (h - 1)) seed(p + w);
  }
  photo.mask = mask; photo.maskKey = key;
  return mask;
}
function renderPhoto() {
  if (!photo.data || !$('photoDlg').open) return;
  const cols = state.cols, rows = state.rows;
  const W = 480, H = Math.round(480 * rows / cols);
  if (cropCv.width !== W || cropCv.height !== H) { cropCv.width = W; cropCv.height = H; }
  const v = viewRect(), s = W / v.vw;
  cropCtx.setTransform(1, 0, 0, 1, 0, 0);
  cropCtx.fillStyle = '#15181f'; cropCtx.fillRect(0, 0, W, H);
  cropCtx.setTransform(s, 0, 0, s, -v.x0 * s, -v.y0 * s);
  cropCtx.imageSmoothingEnabled = s < 3; cropCtx.imageSmoothingQuality = 'high';
  cropCtx.drawImage(photo.canvas, 0, 0);
  cropCtx.setTransform(1, 0, 0, 1, 0, 0);
  cropCtx.strokeStyle = 'rgba(255,255,255,.2)'; cropCtx.lineWidth = 1; cropCtx.beginPath();
  for (let i = 1; i < cols; i++) { const x = Math.round(i * W / cols) + .5; cropCtx.moveTo(x, 0); cropCtx.lineTo(x, H); }
  for (let j = 1; j < rows; j++) { const y = Math.round(j * H / rows) + .5; cropCtx.moveTo(0, y); cropCtx.lineTo(W, y); }
  cropCtx.stroke();

  const bg = photo.bg.on ? { rgb: photo.bg.rgb, tol: photo.bg.tol, mask: bgMask() } : null;
  const rgb = (photo.exact ? pointCrop : boxCrop)(photo.data, photo.w, photo.h, v, cols, rows, bg);
  photo.result = ditherFrame(rgb, cols, rows, photo.exact ? 'none' : photo.dither, LUT, sim.brightness, sim.gamma);
  const pv = $('photoPreview'); pv.width = cols; pv.height = rows;
  const px = pv.getContext('2d'), img = px.createImageData(cols, rows), asLed = $('photoLed').checked;
  photo.result.forEach((hex, p) => { img.data.set([...hexToRgb(asLed ? led(hex).disp : hex), 255], p * 4); });
  px.putImageData(img, 0, 0);
  $('bgSwatch').style.background = toHex(...photo.bg.rgb);
}

function sampleAt(clientX, clientY) {
  const r = cropCv.getBoundingClientRect(), v = viewRect();
  const x = Math.floor(v.x0 + (clientX - r.left) / r.width * v.vw), y = Math.floor(v.y0 + (clientY - r.top) / r.height * v.vh);
  if (x < 0 || y < 0 || x >= photo.w || y >= photo.h) return null;
  const i = (y * photo.w + x) * 4; return [photo.data[i], photo.data[i + 1], photo.data[i + 2]];
}
function cornerColor() {
  const m = 3, pts = [];
  for (const [x0, y0] of [[0, 0], [photo.w - m, 0], [0, photo.h - m], [photo.w - m, photo.h - m]]) {
    let r = 0, g = 0, b = 0;
    for (let y = 0; y < m; y++) for (let x = 0; x < m; x++) { const i = ((y0 + y) * photo.w + x0 + x) * 4; r += photo.data[i]; g += photo.data[i + 1]; b += photo.data[i + 2]; }
    pts.push([r / (m * m), g / (m * m), b / (m * m)]);
  }
  return [0, 1, 2].map((k) => { const a = pts.map((p) => p[k]).sort((p, q) => p - q); return Math.round((a[1] + a[2]) / 2); });
}

// Pointer gestures on the crop window: one finger pans, two pinch-zoom, wheel zooms
const ptrs = new Map(); let gesture = null;
cropCv.addEventListener('pointerdown', (e) => {
  cropCv.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, { x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY });
  gesture = { moved: false };
});
cropCv.addEventListener('pointermove', (e) => {
  const p = ptrs.get(e.pointerId); if (!p) return;
  const r = cropCv.getBoundingClientRect(), k = photo.vw / r.width;
  if (ptrs.size === 1) {
    photo.cx -= (e.clientX - p.x) * k; photo.cy -= (e.clientY - p.y) * k;
    if (Math.hypot(e.clientX - p.sx, e.clientY - p.sy) > 5) gesture.moved = true;
  } else if (ptrs.size === 2) {
    const [a, b] = [...ptrs.values()], d0 = Math.hypot(a.x - b.x, a.y - b.y);
    const o = ptrs.get(e.pointerId); const other = a === o ? b : a;
    const nx = e.clientX, ny = e.clientY, d1 = Math.hypot(nx - other.x, ny - other.y);
    if (d0 > 0 && d1 > 0) photo.vw = clamp(photo.vw * d0 / d1, photo.vwMin, photo.vwMax);
    photo.cx -= ((nx - p.x) / 2) * k; photo.cy -= ((ny - p.y) / 2) * k;
    gesture.moved = true;
  }
  p.x = e.clientX; p.y = e.clientY; syncSlider(); schedulePhoto();
});
const endPtr = (e) => {
  const was = ptrs.size; ptrs.delete(e.pointerId);
  if (was === 1 && gesture && !gesture.moved && photo.picking && e.type === 'pointerup') {
    const c = sampleAt(e.clientX, e.clientY);
    if (c) { photo.bg.rgb = c; photo.bg.on = true; photo.bgSet = true; $('bgOn').checked = true; setPick(false); schedulePhoto(); }
  }
};
cropCv.addEventListener('pointerup', endPtr); cropCv.addEventListener('pointercancel', endPtr);
cropCv.addEventListener('wheel', (e) => {
  e.preventDefault();
  photo.vw = clamp(photo.vw * Math.exp(e.deltaY * 0.0015), photo.vwMin, photo.vwMax); syncSlider(); schedulePhoto();
}, { passive: false });

function setPick(on) { photo.picking = on; $('bgPick').setAttribute('aria-pressed', String(on)); $('bgPick').classList.toggle('btn-quiet', !on); cropCv.classList.toggle('picking', on); }
$('bgPick').addEventListener('click', () => setPick(!photo.picking));
$('bgCorners').addEventListener('click', () => { photo.bg.rgb = cornerColor(); photo.bg.on = true; photo.bgSet = true; $('bgOn').checked = true; schedulePhoto(); });
$('bgOn').addEventListener('change', (e) => { photo.bg.on = e.target.checked; if (photo.bg.on && !photo.bgSet) { photo.bg.rgb = cornerColor(); photo.bgSet = true; } schedulePhoto(); });
$('bgTol').addEventListener('input', (e) => { photo.bg.tol = Number(e.target.value); schedulePhoto(); });
$('exactOn').addEventListener('change', (e) => { photo.exact = e.target.checked; $('ditherMode').disabled = photo.exact; schedulePhoto(); });
$('ditherMode').addEventListener('change', (e) => { photo.dither = e.target.value; schedulePhoto(); });
$('photoLed').addEventListener('change', schedulePhoto);
$('photoZoom').addEventListener('input', setZoomFromSlider);
$('photoFit').addEventListener('click', () => fitView(false));
$('photoFill').addEventListener('click', () => fitView(true));
$('photoCancel').addEventListener('click', () => $('photoDlg').close());
$('photoDlg').addEventListener('close', () => { setPick(false); ptrs.clear(); photo.data = null; photo.canvas = null; });
function applyPhoto(asNew) {
  if (!photo.result) return;
  stopPlay(); pushUndo();
  if (asNew) { state.target = 'frame'; state.frames.splice(state.currentFrame + 1, 0, photo.result); state.currentFrame++; }
  else setEditLayer(photo.result);
  afterFrameChange();
  const how = photo.exact ? 'exact pixels' : photo.dither === 'none' ? 'no dithering' : (photo.dither === 'fs' ? 'Floyd–Steinberg' : 'ordered') + ' dithering';
  setStatus((asNew ? `Image added as frame ${state.currentFrame + 1}` : `Image applied to frame ${state.currentFrame + 1}`) + ` (${how}${photo.bg.on ? ', background off' : ''}). Undo reverts.`);
  $('photoDlg').close();
}
$('photoApply').addEventListener('click', () => applyPhoto(false));
$('photoAdd').addEventListener('click', () => applyPhoto(true));
async function openImport(file) {
  try {
    const d = await decodeFile(file);
    Object.assign(photo, { w: d.w, h: d.h, data: d.data, canvas: d.canvas, result: null, mask: null, maskKey: null });
    const small = d.w <= 2 * state.cols && d.h <= 2 * state.rows; // same rule the Pi uses for pixel art vs photo
    photo.exact = small; $('exactOn').checked = small;
    photo.dither = 'none'; $('ditherMode').value = 'none'; $('ditherMode').disabled = small;
    // background off by default when the corners are a solid, non-black color
    const px = [[0, 0], [d.w - 1, 0], [0, d.h - 1], [d.w - 1, d.h - 1]].map(([x, y]) => d.data[(y * d.w + x) * 4 + 3]);
    const cc = cornerColor(), solid = px.every((a) => a >= 250) && (cc[0] + cc[1] + cc[2]) > 0;
    photo.bg.rgb = cc; photo.bg.on = solid; photo.bgSet = solid; $('bgOn').checked = solid;
    photo.vwMax = Math.max(d.w, d.h * state.cols / state.rows) * 3; photo.vwMin = Math.max(state.cols, Math.min(d.w, d.h * state.cols / state.rows) / 40);
    $('photoDlg').showModal(); fitView(!small);
  } catch (err) { setStatus('That file couldn’t be read as an image.'); }
}

/* ---------- resize ---------- */
$('resizeBtn').addEventListener('click', () => {
  const nc = clamp(Number($('colsInput').value) || 16, 1, 64), nr = clamp(Number($('rowsInput').value) || 16, 1, 64);
  if (nc === state.cols && nr === state.rows) return;
  stopPlay(); pushUndo();
  state.frames = state.frames.map((f) => {
    const out = newBlankFrame(nc, nr);
    for (let y = 0; y < Math.min(state.rows, nr); y++) for (let x = 0; x < Math.min(state.cols, nc); x++) out[y * nc + x] = f[y * state.cols + x];
    return out;
  });
  if (state.shared) {
    const sh = newBlankFrame(nc, nr);
    for (let y = 0; y < Math.min(state.rows, nr); y++) for (let x = 0; x < Math.min(state.cols, nc); x++) sh[y * nc + x] = state.shared[y * state.cols + x];
    state.shared = sh;
  }
  state.cols = nc; state.rows = nr; $('colsInput').value = nc; $('rowsInput').value = nr;
  buildGridDOM(); afterFrameChange();
});

