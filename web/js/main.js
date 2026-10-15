// Website/installable app and boot. Classic script: shares one global scope with the other files in js/ (load order is in index.html).
/* ---------- website / installable app (not inside a Claude artifact) ---------- */
const onWeb = !window.claude && /^https?:$/.test(location.protocol);
if (onWeb) {
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
  let deferredInstall = null;
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferredInstall = e; $('installBtn').hidden = false; });
  window.addEventListener('appinstalled', () => { $('installBtn').hidden = true; setStatus('Glow Grid installed as an app.'); });
  $('installBtn').addEventListener('click', async () => {
    if (!deferredInstall) return;
    deferredInstall.prompt();
    await deferredInstall.userChoice.catch(() => null);
    deferredInstall = null; $('installBtn').hidden = true;
  });
}

/* ---------- help dialog ---------- */
const helpDlg = $('helpDlg');
$('helpBtn').addEventListener('click', () => { if (helpDlg.showModal) helpDlg.showModal(); else helpDlg.setAttribute('open', ''); });
$('helpClose').addEventListener('click', () => helpDlg.close());
helpDlg.addEventListener('click', (e) => { if (e.target === helpDlg) helpDlg.close(); });

/* ---------- File menu (native popover) and export dialog ---------- */
const fileMenu = $('fileMenu'), fileBtn = $('fileBtn'), exportDlg = $('exportDlg');
fileMenu.addEventListener('beforetoggle', (e) => {
  if (e.newState !== 'open') return;
  const r = fileBtn.getBoundingClientRect();
  fileMenu.style.top = `${r.bottom + 6}px`;
  fileMenu.style.left = `${Math.max(8, Math.min(r.right - 240, window.innerWidth - 248))}px`;
});
fileMenu.addEventListener('toggle', (e) => fileBtn.setAttribute('aria-expanded', e.newState === 'open'));
fileBtn.addEventListener('click', () => { if (fileMenu.togglePopover) fileMenu.togglePopover(); });
$('menuImport').addEventListener('click', () => { fileMenu.hidePopover(); $('imageInput').click(); });
$('menuOpenGg').addEventListener('click', () => { fileMenu.hidePopover(); $('ggInput').click(); });
$('menuExport').addEventListener('click', () => { fileMenu.hidePopover(); updateCmd(); if (exportDlg.showModal) exportDlg.showModal(); else exportDlg.setAttribute('open', ''); });
$('exportClose').addEventListener('click', () => exportDlg.close());
exportDlg.addEventListener('click', (e) => { if (e.target === exportDlg) exportDlg.close(); });
$('exportBtn').addEventListener('click', () => exportDlg.close());

/* ---------- boot ---------- */
$('brightInput').value = sim.brightness; $('gammaInput').value = sim.gamma; $('psuInput').value = sim.psu;
$('flagsToggle').checked = sim.flags; deviceEl.classList.toggle('flags-on', sim.flags);
$('targetInput').value = exportTarget();
$('colsInput').value = state.cols; $('rowsInput').value = state.rows;
$('fpsInput').value = state.fps; $('nameInput').value = state.name;
buildLut(); buildGridDOM(); renderSwatches(); setColor(state.color, false); updateUndoBtns();
afterFrameChange();
