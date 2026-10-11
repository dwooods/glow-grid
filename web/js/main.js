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

/* ---------- boot ---------- */
$('brightInput').value = sim.brightness; $('gammaInput').value = sim.gamma; $('psuInput').value = sim.psu;
$('flagsToggle').checked = sim.flags; deviceEl.classList.toggle('flags-on', sim.flags);
$('piInput').value = sim.pi; $('pcDirInput').value = sim.pcDir; $('targetInput').value = exportTarget();
$('colsInput').value = state.cols; $('rowsInput').value = state.rows;
$('fpsInput').value = state.fps; $('nameInput').value = state.name;
buildLut(); buildGridDOM(); renderSwatches(); setColor(state.color, false); updateUndoBtns();
afterFrameChange();
