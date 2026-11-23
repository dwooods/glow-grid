// EXPERIMENTAL: send the drawing and text to a 32x32 Bluetooth LED panel (the kind that advertises as LED_BLE_xxxxxxxx, for example the
// "iPixel Color" panels). Off by default: main.js loads this file only after the page is opened once with ?experimental=panel.
// Needs desktop Chrome or Edge (Web Bluetooth) on an https page; it never works on iPhone. Nothing here talks to the Glow Grid board.
//
// The panel draws no letters. It stores a picture and plays it back, so everything is drawn here first:
//  - the drawing becomes an animated GIF in which every frame is a complete 32x32 picture. The panel cannot play the usual
//    optimised GIFs that save only the changed part of each frame (tested on a real panel: those do not play);
//  - text becomes a row of 16x32 pixel cells (bitmap fonts in panel_fonts.js, so no letter ever loses a pixel to anti-aliasing).
// Protocol notes: pypixelcolor (MIT, https://github.com/lucagoc/pypixelcolor) and go-ipxl (https://yewolf.fr/projects/go-ipxl) describe it; the code below is written
// from those descriptions and checked against a real panel. See THIRD_PARTY_NOTICES.md.
(function () {
  'use strict';
  const W = 32, H = 32;
  const SVC = '000000fa-0000-1000-8000-00805f9b34fb', CHR_WRITE = '0000fa02-0000-1000-8000-00805f9b34fb', CHR_NOTIFY = '0000fa03-0000-1000-8000-00805f9b34fb';
  const FONT_NAMES = ['DejaVu Bold', 'Press Start 2P', 'Jersey 15', 'Jersey 20'];
  const EFFECTS = [[1, 'Move left'], [2, 'Move right'], [3, 'Up'], [4, 'Down'], [0, 'Fixed'], [5, 'Blink'], [6, 'Breathe'], [7, 'Snowflake']];
  const STILL = [0, 5, 6, 7];    // effects that keep the text in place, so the whole word has to fit on the panel

  /* ---------- pure helpers (also used by tests/test_panel.py through Node) ---------- */
  const crcTable = (() => {
    const t = new Uint32Array(256);
    for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
    return t;
  })();
  function crc32(u8) {
    let c = 0xFFFFFFFF;
    for (let i = 0; i < u8.length; i++) c = crcTable[(c ^ u8[i]) & 255] ^ (c >>> 8);
    return (c ^ 0xFFFFFFFF) >>> 0;
  }
  const le32 = (n) => [n & 255, (n >>> 8) & 255, (n >>> 16) & 255, (n >>> 24) & 255];

  // GIF LZW, variable code size, as in the GIF89a spec.
  function lzw(indices, minBits) {
    const clear = 1 << minBits, eoi = clear + 1, out = [];
    let cur = 0, nbits = 0, size = minBits + 1, next = eoi + 1, table = new Map();
    const emit = (code) => { cur |= code << nbits; nbits += size; while (nbits >= 8) { out.push(cur & 255); cur >>>= 8; nbits -= 8; } };
    emit(clear);
    let w = indices[0];                       // code of the string matched so far
    for (let i = 1; i < indices.length; i++) {
      const k = indices[i], key = w * 256 + k, hit = table.get(key);
      if (hit !== undefined) { w = hit; continue; }
      emit(w);
      table.set(key, next++);
      if (next > (1 << size) && size < 12) size++;
      if (next >= 4095) { emit(clear); table = new Map(); next = eoi + 1; size = minBits + 1; }
      w = k;
    }
    emit(w); emit(eoi);
    if (nbits) out.push(cur & 255);
    return out;
  }
  const subBlocks = (bytes) => { const o = []; for (let i = 0; i < bytes.length; i += 255) { const c = bytes.slice(i, i + 255); o.push(c.length, ...c); } o.push(0); return o; };

  // frames: array of Uint8Array (w*h*3 RGB). Every frame is written as a complete image at (0,0), never as a patch.
  function makeGif(frames, w, h, delayCs) {
    const seen = new Map();
    for (const f of frames) for (let i = 0; i < f.length; i += 3) { const key = (f[i] << 16) | (f[i + 1] << 8) | f[i + 2]; if (!seen.has(key)) seen.set(key, seen.size); }
    let quant = null;
    if (seen.size > 256) {   // more colours than a GIF holds: keep 3 bits red, 3 green, 2 blue
      quant = (r, g, b) => (r >> 5) << 5 | (g >> 5) << 2 | (b >> 6);
      seen.clear();
    }
    const idxOf = (r, g, b) => quant ? quant(r, g, b) : seen.get((r << 16) | (g << 8) | b);
    const palette = new Uint8Array(256 * 3);
    if (quant) { for (let i = 0; i < 256; i++) { palette[i * 3] = Math.round(((i >> 5) & 7) * 255 / 7); palette[i * 3 + 1] = Math.round(((i >> 2) & 7) * 255 / 7); palette[i * 3 + 2] = Math.round((i & 3) * 255 / 3); } }
    else for (const [key, i] of seen) { palette[i * 3] = key >> 16; palette[i * 3 + 1] = (key >> 8) & 255; palette[i * 3 + 2] = key & 255; }
    const n = quant ? 256 : Math.max(2, seen.size);
    const bits = Math.max(1, Math.ceil(Math.log2(n))), psize = 1 << bits, minBits = Math.max(2, bits);
    const out = [0x47, 0x49, 0x46, 0x38, 0x39, 0x61, w & 255, w >> 8, h & 255, h >> 8, 0x80 | ((bits - 1) << 4) | (bits - 1), 0, 0];
    for (let i = 0; i < psize * 3; i++) out.push(palette[i] || 0);
    if (frames.length > 1) out.push(0x21, 0xff, 0x0b, ...Array.from('NETSCAPE2.0', (c) => c.charCodeAt(0)), 3, 1, 0, 0, 0);
    for (const f of frames) {
      const idx = new Uint8Array(w * h);
      for (let i = 0, p = 0; p < idx.length; i += 3, p++) idx[p] = idxOf(f[i], f[i + 1], f[i + 2]);
      out.push(0x21, 0xf9, 4, 4, delayCs & 255, delayCs >> 8, 0, 0, 0x2c, 0, 0, 0, 0, w & 255, w >> 8, h & 255, h >> 8, 0, minBits);
      out.push(...subBlocks(lzw(idx, minBits)));
    }
    out.push(0x3b);
    return Uint8Array.from(out);
  }

  // One editor frame (array of '#rrggbb', cols x rows) to a 32x32 RGB frame: whole-number scale, centred, black around.
  function toPanelFrame(hexFrame, cols, rows, hexToRgb) {
    const s = Math.min(Math.floor(W / cols), Math.floor(H / rows));
    if (s < 1) throw new Error(`the drawing is ${cols} x ${rows}; the panel is ${W} x ${H}`);
    const out = new Uint8Array(W * H * 3), ox = ((W - cols * s) >> 1), oy = ((H - rows * s) >> 1);
    for (let y = 0; y < rows; y++) for (let x = 0; x < cols; x++) {
      const [r, g, b] = hexToRgb(hexFrame[y * cols + x]);
      for (let dy = 0; dy < s; dy++) for (let dx = 0; dx < s; dx++) { const p = ((oy + y * s + dy) * W + ox + x * s + dx) * 3; out[p] = r; out[p + 1] = g; out[p + 2] = b; }
    }
    return out;
  }

  // The panel takes data in windows of up to 12 KB: [length(2)] [kind, 0|1|2, option, size(4), crc(4), tail, slot] payload.
  // slot 0 plays without saving.
  function windowsFor(payload, head, tail, slot) {
    const size = le32(payload.length), crc = le32(crc32(payload)), out = [];
    for (let pos = 0, i = 0; pos < payload.length; i++) {
      const end = Math.min(pos + 12288, payload.length);
      const frame = [...head, i ? 0x02 : 0x00, ...size, ...crc, ...tail, slot, ...payload.subarray(pos, end)];
      const len = frame.length + 2;
      out.push(Uint8Array.from([len & 255, (len >> 8) & 255, ...frame]));
      pos = end;
    }
    return out;
  }
  const gifWindows = (gif, slot = 0) => windowsFor(gif, [0x03, 0x00], [0x02], slot);
  const rev8 = (b) => { let r = 0; for (let i = 0; i < 8; i++) if (b >> i & 1) r |= 1 << (7 - i); return r; };
  // rowsList: one array of 32 sixteen-bit rows per character cell (bit 15 = leftmost pixel); colour is [r,g,b]
  function textPayload(rowsList, anim, speed, rainbow, color) {
    const out = [rowsList.length, 0x00, 0x01, 0x01, anim, speed, rainbow, ...color, 0, 0, 0, 0];
    for (const rows of rowsList) { out.push(0x02, ...color); for (const r of rows) out.push(rev8(r >> 8), rev8(r & 255)); }
    return Uint8Array.from(out);
  }
  const textWindows = (rowsList, anim, speed, rainbow, color, slot = 0) => windowsFor(textPayload(rowsList, anim, speed, rainbow, color), [0x00, 0x01], [0x00], slot);

  // One character as a 16x32 cell, for the moving effects.
  function cellRows(fonts, name, ch) {
    const cell = fonts[name].cell, h = cell[ch] || cell['?'], rows = [];
    for (let y = 0; y < 32; y++) rows.push(parseInt(h.slice(y * 4, y * 4 + 4), 16));
    return rows;
  }

  // The whole text on one 32x32 picture, cut into two cells, for the effects that do not move it. Picks the biggest letters that fit;
  // with oneLine it keeps a single line unless that would make the letters tiny.
  function fitRows(fonts, name, text, oneLine) {
    const FIT = fonts[name].fit, t = text.trim().replace(/[^\x20-\x7e]/g, '?'), words = t.split(/\s+/).filter(Boolean);
    const opts = [[t]];
    for (const n of [2, 3]) {
      if (t.replace(/\s/g, '').length < n * 2) continue;
      if (words.length >= n) { const per = Math.ceil(words.length / n), L = []; for (let i = 0; i < words.length; i += per) L.push(words.slice(i, i + per).join(' ')); opts.push(L); }
      else if (words.length === 1) { const h = Math.ceil(t.length / n), L = []; for (let i = 0; i < t.length; i += h) L.push(t.slice(i, i + h)); opts.push(L); }
    }
    if (words.length > 1) for (let k = 1; k < words.length; k++) opts.push([words.slice(0, k).join(' '), words.slice(k).join(' ')]);
    const glyph = (sz, c) => FIT[sz].g[c] || FIT[sz].g['?'];
    const wid = (sz, l) => [...l].reduce((a, c) => a + glyph(sz, c)[0], 0);
    const pick = (list) => {
      let best = null;
      for (const sz of Object.keys(FIT)) {
        const h = FIT[sz].h;
        for (const lines of list) {
          if (lines.length * h + (lines.length - 1) > H) continue;
          if (Math.max(...lines.map((l) => wid(sz, l))) > W) continue;
          if (!best || h > FIT[best.sz].h || (h === FIT[best.sz].h && lines.length < best.lines.length)) best = { lines, sz };
        }
      }
      return best;
    };
    // Prefer one line when asked, unless the letters would be tiny (under 8 px for one word, under 10 px for several) and splitting gives bigger ones.
    let best = oneLine ? pick([opts[0]]) : null;
    if (!best || FIT[best.sz].h < (words.length > 1 ? 10 : 8)) {
      const all = pick(words.length > 1 && opts.length > 1 ? opts.slice(1) : opts);
      if (all && (!best || FIT[all.sz].h > FIT[best.sz].h || (words.length > 1 && all.lines.length > 1 && FIT[all.sz].h >= FIT[best.sz].h))) best = all;
    }
    if (!best) best = { lines: [t], sz: Object.keys(FIT)[0] };
    const F = FIT[best.sz], h = F.h, grid = Array.from({ length: H }, () => new Array(W).fill(0));
    const total = best.lines.length * h + (best.lines.length - 1), y0 = Math.max(0, (H - total) >> 1);
    best.lines.forEach((l, i) => {
      let x = Math.max(0, (W - wid(best.sz, l)) >> 1);
      for (const c of l) {
        const [a, hx] = glyph(best.sz, c), dg = (a + 3) >> 2;
        for (let y = 0; y < h; y++) {
          const v = parseInt(hx.slice(y * dg, y * dg + dg), 16), yy = y0 + i * (h + 1) + y;
          for (let k = 0; k < a; k++) if ((v >> (a - 1 - k)) & 1 && x + k < W && yy < H) grid[yy][x + k] = 1;
        }
        x += a;
      }
    });
    const cells = [[], []];
    for (let y = 0; y < H; y++) {
      let p = 0, q = 0;
      for (let c = 0; c < 16; c++) { if (grid[y][c]) p |= 1 << (15 - c); if (grid[y][16 + c]) q |= 1 << (15 - c); }
      cells[0].push(p); cells[1].push(q);
    }
    return { cells, lines: best.lines, letterHeight: h };
  }

  // Panel slots (experimental). Saving is the same GIF send with a slot number from 1 up; these two small commands play and clear a slot.
  const showSlotCmd = (n) => Uint8Array.of(7, 0, 8, 0x80, 1, 0, n & 255);
  const deleteSlotCmd = (n) => Uint8Array.of(7, 0, 2, 1, 1, 0, n & 255);
  // A shipped example (GG_EXAMPLES entry: palette char -> colour, one 256-char string per 16x16 frame) as the GIF the panel plays.
  function exampleGif(ex, hexToRgb) {
    const frames = ex.frames.map((f) => toPanelFrame(Array.from(f, (c) => ex.palette[c] || '#000000'), 16, 16, hexToRgb));
    return makeGif(frames, W, H, Math.max(2, Math.round(100 / (ex.fps || 4))));
  }

  const api = { showSlotCmd, deleteSlotCmd, exampleGif, crc32, lzw, makeGif, toPanelFrame, windowsFor, gifWindows, textPayload, textWindows, cellRows, fitRows, FONT_NAMES, EFFECTS, STILL };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document === 'undefined') return;
  window.ggPanel = api;

  /* ---------- the card ---------- */
  const $p = (id) => document.getElementById(id);
  const say = (msg) => { $p('panelStatus').textContent = msg; };
  let dev = null, writeChr = null, notifyChr = null, waiter = null, ackWaiter = null, busy = false, fontsPromise = null;

  function loadFonts() {
    if (window.GG_PANEL_FONTS) return Promise.resolve(window.GG_PANEL_FONTS);
    if (!fontsPromise) fontsPromise = new Promise((ok, fail) => {
      const s = document.createElement('script');
      s.src = 'js/panel_fonts.js';
      s.onload = () => ok(window.GG_PANEL_FONTS);
      s.onerror = () => { fontsPromise = null; fail(new Error('could not load the panel fonts')); };
      document.head.appendChild(s);
    });
    return fontsPromise;
  }

  const timeout = (p, ms, what) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('timed out waiting for ' + what)), ms))]);
  function onNotify(e) {
    const d = new Uint8Array(e.target.value.buffer);
    if (waiter) { const w = waiter; waiter = null; w(d); return; }
    if (d.length === 5 && d[0] === 5 && [0, 1, 3].includes(d[4]) && ackWaiter) { const a = ackWaiter; ackWaiter = null; a(d[4]); }
  }
  async function writeAll(data) { for (let i = 0; i < data.length; i += 244) await writeChr.writeValueWithResponse(data.subarray(i, i + 244)); }
  async function sendWindows(wins) {
    let code = null;
    for (let i = 0; i < wins.length; i++) {
      const ack = new Promise((r) => { ackWaiter = r; });
      await writeAll(wins[i]);
      code = await timeout(ack, 8000, `the panel to confirm part ${i + 1} of ${wins.length}`);
    }
    return code;
  }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  function setConnected(on) {
    for (const id of ['panelDisconnect', 'panelSendDrawing', 'panelSendText', 'panelSaveSlot', 'panelShowSlot', 'panelDeleteSlot', 'panelSaveAll', 'panelTour']) $p(id).disabled = !on;
    $p('panelConnect').disabled = on;
  }
  async function connect() {
    dev = await navigator.bluetooth.requestDevice({ filters: [{ namePrefix: 'LED_BLE_' }], optionalServices: [SVC] });
    dev.addEventListener('gattserverdisconnected', () => { setConnected(false); say('Disconnected.'); });
    const srv = await dev.gatt.connect(), svc = await srv.getPrimaryService(SVC);
    writeChr = await svc.getCharacteristic(CHR_WRITE); notifyChr = await svc.getCharacteristic(CHR_NOTIFY);
    notifyChr.addEventListener('characteristicvaluechanged', onNotify);
    await notifyChr.startNotifications();
    const now = new Date(), reply = new Promise((r) => { waiter = r; });
    await writeAll(Uint8Array.of(8, 0, 1, 0x80, now.getHours(), now.getMinutes(), now.getSeconds(), 0));
    const info = await timeout(reply, 8000, 'the panel to answer');
    setConnected(true);
    say(info[4] === 129 ? `Connected to ${dev.name} (32 x 32).` : `Connected to ${dev.name}, but it reports an unexpected type (${info[4]}); this card is made for 32 x 32 panels.`);
  }
  const guarded = (fn) => async () => {
    if (busy) { say('Wait for the current send to finish.'); return; }
    busy = true;
    try { await fn(); } catch (e) { say(e && e.name === 'NotFoundError' ? 'No panel was picked.' : 'Failed: ' + (e && e.message ? e.message : e)); } finally { busy = false; }
  };
  async function sendDrawing() {
    const fps = state.fps || 6, delay = Math.max(2, Math.round(100 / fps));
    const frames = state.frames.map((f) => toPanelFrame(f, state.cols, state.rows, hexToRgb));
    const gif = makeGif(frames, W, H, delay), wins = gifWindows(gif);
    say(`Sending ${frames.length} frame${frames.length === 1 ? '' : 's'} (${gif.length} bytes)…`);
    await sendWindows(wins);
    say('Sent. The panel plays the drawing now; it is not saved on the panel.');
  }
  async function sendText() {
    const text = $p('panelText').value;
    if (!text.trim()) { say('Type some text first.'); return; }
    const fonts = await loadFonts(), font = $p('panelFont').value, anim = Number($p('panelEffect').value), speed = Number($p('panelSpeed').value);
    const c = $p('panelColor').value, color = [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
    let rowsList, note = '';
    if (STILL.includes(anim)) {
      const fit = fitRows(fonts, font, text, $p('panelLines').value === '1');
      rowsList = fit.cells;
      if (fit.letterHeight < 8) note = ` The letters are only ${fit.letterHeight} px tall; the Move left effect suits long text better.`;
    } else {
      const chars = [...text].filter((ch) => ch >= ' ' && ch <= '~');
      if (anim === 2) chars.reverse();
      rowsList = chars.map((ch) => cellRows(fonts, font, ch));
    }
    say('Sending the text…');
    await sendWindows(textWindows(rowsList, anim, speed, 0, color));
    say('Sent.' + note);
  }

  /* ---------- panel slots (experimental test): save to the panel, play, clear, fill until something fails ---------- */
  let stopFlag = false;
  const slotNames = (() => { try { return JSON.parse(localStorage.getItem('glowgrid-panel-slots') || '{}'); } catch (e) { return {}; } })();
  const rememberSlot = (n, name) => { slotNames[n] = name; try { localStorage.setItem('glowgrid-panel-slots', JSON.stringify(slotNames)); } catch (e) { /* the note is only a convenience */ } };
  const slotNo = () => { const n = Math.floor(Number($p('panelSlot').value)); if (!(n >= 1 && n <= 255)) throw new Error('Slot must be a whole number from 1 to 255.'); return n; };
  const countNo = () => Math.max(1, Math.min(255, Math.floor(Number($p('panelSlotCount').value)) || 40));
  async function saveDrawingSlot() {
    const n = slotNo(), fps = state.fps || 6, delay = Math.max(2, Math.round(100 / fps));
    const gif = makeGif(state.frames.map((f) => toPanelFrame(f, state.cols, state.rows, hexToRgb)), W, H, delay);
    say(`Saving the drawing to slot ${n} (${gif.length} bytes)…`);
    const code = await sendWindows(gifWindows(gif, n));
    rememberSlot(n, 'drawing');
    say(`Saved to slot ${n}; the panel answered with code ${code}. Press Show slot ${n} to check it.`);
  }
  async function showSlot() { const n = slotNo(); await writeAll(showSlotCmd(n)); say(`Asked the panel to show slot ${n}. If it is empty the panel may cycle through what it has.`); }
  async function deleteSlot() { const n = slotNo(); await writeAll(deleteSlotCmd(n)); delete slotNames[n]; say(`Asked the panel to clear slot ${n}.`); }
  async function saveAll() {
    if (typeof GG_EXAMPLES === 'undefined') throw new Error('The example sprites are not loaded.');
    const first = slotNo(), list = GG_EXAMPLES.slice(0, countNo()); let total = 0, last = 0, codes = [];
    stopFlag = false;
    for (let i = 0; i < list.length; i++) {
      const n = first + i;
      if (n > 255) { say(`Stopped at slot 255 (the highest number). Saved ${i} example${i === 1 ? '' : 's'}, slots ${first} to ${last}.`); return; }
      if (stopFlag) { say(`Stopped. Saved ${i} example${i === 1 ? '' : 's'}, slots ${first} to ${last}.`); return; }
      const gif = exampleGif(list[i], hexToRgb);
      say(`Saving ${list[i].name} to slot ${n} (${i + 1} of ${list.length}, ${gif.length} bytes; ${total} bytes so far)…`);
      try {
        codes.push(await sendWindows(gifWindows(gif, n)));
      } catch (e) {
        say(`Slot ${n} (${list[i].name}) failed: ${e.message}. Slots ${first} to ${last} were saved before that (${i} example${i === 1 ? '' : 's'}, ${total} bytes). Now press Tour slots to see which ones really play.`);
        return;
      }
      rememberSlot(n, list[i].name); total += gif.length; last = n;
      await sleep(250);
    }
    say(`Saved all ${list.length} examples to slots ${first} to ${last} (${total} bytes); the panel answered every send. That does not prove they all stayed, so press Tour slots and watch.`);
  }
  async function tour() {
    const first = slotNo(), count = countNo(); stopFlag = false;
    for (let i = 0; i < count; i++) {
      const n = first + i;
      if (n > 255 || stopFlag) break;
      await writeAll(showSlotCmd(n));
      say(`Showing slot ${n}${slotNames[n] ? ' (' + slotNames[n] + ')' : ''}. Watch the panel; ${i + 1} of ${count}. Press Stop to end.`);
      await sleep(2500);
    }
    say(stopFlag ? 'Tour stopped.' : 'Tour finished. Note which slots showed the wrong picture, or the same one as another slot.');
  }

  function build() {
    const after = $p('boardCard'); if (!after || $p('btPanelCard')) return;
    const card = document.createElement('section');
    card.className = 'card'; card.id = 'btPanelCard';
    card.innerHTML = '<h2>Bluetooth panel <small class="board-free">experimental</small></h2>' +
      '<p class="hint">For a 32 x 32 panel that shows up as LED_BLE_… in the Bluetooth list (for example iPixel Color). Close its phone app first. Chrome or Edge on a computer only; this is separate from the Glow Grid board.</p>' +
      '<div class="btn-row"><button id="panelConnect" class="btn" type="button">Connect over Bluetooth</button>' +
      '<button id="panelDisconnect" class="btn btn-quiet" type="button" disabled>Disconnect</button>' +
      '<button id="panelSendDrawing" class="btn" type="button" title="Play the drawing in the editor on the panel, scaled up to fit" disabled>Send drawing</button></div>' +
      '<div class="btn-row"><label class="field-inline">Text <input id="panelText" type="text" value="love you" maxlength="60" size="14" spellcheck="false" autocomplete="off"></label>' +
      '<label class="field-inline">Font <select id="panelFont"></select></label>' +
      '<label class="field-inline">Effect <select id="panelEffect"></select></label>' +
      '<label class="field-inline">Speed <input id="panelSpeed" type="number" min="0" max="100" value="80" style="width:4.5em"></label>' +
      '<label class="field-inline">Colour <input id="panelColor" type="color" value="#ff2020"></label>' +
      '<label class="field-inline" title="Still effects only. One line keeps a short word on one line; Auto picks the biggest letters.">Lines <select id="panelLines"><option value="1">One line</option><option value="0">Auto</option></select></label>' +
      '<button id="panelSendText" class="btn" type="button" disabled>Send text</button></div>' +
      '<div class="btn-row"><span class="hint">Panel slots (test)</span>' +
      '<label class="field-inline">Slot <input id="panelSlot" type="number" min="1" max="255" value="1" style="width:4.5em"></label>' +
      '<button id="panelSaveSlot" class="btn" type="button" title="Store the drawing on the panel in this slot" disabled>Save drawing to slot</button>' +
      '<button id="panelShowSlot" class="btn" type="button" disabled>Show slot</button>' +
      '<button id="panelDeleteSlot" class="btn btn-quiet" type="button" disabled>Delete slot</button></div>' +
      '<div class="btn-row"><label class="field-inline">How many <input id="panelSlotCount" type="number" min="1" max="255" value="40" style="width:4.5em"></label>' +
      '<button id="panelSaveAll" class="btn" type="button" title="Save the shipped examples to consecutive slots starting at Slot, until one fails" disabled>Save examples from slot</button>' +
      '<button id="panelTour" class="btn" type="button" title="Play each slot for a few seconds so you can see which ones are really there" disabled>Tour slots</button>' +
      '<button id="panelStop" class="btn btn-quiet" type="button">Stop</button></div>' +
      '<p class="hint board-status" id="panelStatus" role="status"></p>';
    after.parentNode.insertBefore(card, after.nextSibling);
    for (const n of FONT_NAMES) $p('panelFont').add(new Option(n, n));
    for (const [v, n] of EFFECTS) $p('panelEffect').add(new Option(n, String(v)));
    $p('panelConnect').addEventListener('click', guarded(connect));
    $p('panelDisconnect').addEventListener('click', () => { if (dev && dev.gatt.connected) dev.gatt.disconnect(); });
    $p('panelSendDrawing').addEventListener('click', guarded(sendDrawing));
    $p('panelSendText').addEventListener('click', guarded(sendText));
    $p('panelSaveSlot').addEventListener('click', guarded(saveDrawingSlot));
    $p('panelShowSlot').addEventListener('click', guarded(showSlot));
    $p('panelDeleteSlot').addEventListener('click', guarded(deleteSlot));
    $p('panelSaveAll').addEventListener('click', guarded(saveAll));
    $p('panelTour').addEventListener('click', guarded(tour));
    $p('panelStop').addEventListener('click', () => { stopFlag = true; });
    say('Not connected.');
  }
  build();
})();
