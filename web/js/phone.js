// Phone layout (portrait): a bottom dock (tools, color, palette, undo/redo), a one-line frame strip under the grid,
// and a "More" sheet for everything else. It only moves existing nodes, so ids, listeners and the desktop markup are untouched;
// leaving the layout (rotate, resize) puts every node back. Classic script: shares the global scope ($ comes from core.js).
(function () {
  const mq = window.matchMedia('(max-width: 760px) and (min-height: 600px)');
  const root = document.documentElement;
  const sheet = $('sheet'), moreBtn = $('moreBtn'), dock = $('dock');
  const moved = [];
  const put = (node, target) => {
    if (!node) return;
    const ph = document.createComment('');
    node.replaceWith(ph); moved.push([node, ph]); target.appendChild(node);
  };
  const restoreAll = () => { while (moved.length) { const [node, ph] = moved.pop(); ph.replaceWith(node); } };

  function measure() {
    root.style.setProperty('--dock-h', `${dock.offsetHeight}px`);
    root.style.setProperty('--sheet-top', `${Math.round($('device').getBoundingClientRect().bottom + 8)}px`);
  }
  function setSheet(open) {
    sheet.classList.toggle('open', open);
    moreBtn.setAttribute('aria-expanded', String(open));
    if (open) measure();
  }
  const toggleSheet = () => setSheet(!sheet.classList.contains('open'));

  function enter() {
    root.classList.add('phone-dock');
    dock.hidden = false; moreBtn.hidden = false; $('sheetHead').hidden = false; $('frameMore').hidden = false;
    put($('toolRow'), $('dockTools'));
    put($('paletteGroup'), $('dockPalette'));
    put($('historyRow'), $('dockHistory'));
    put($('fpsInput').closest('.field-inline'), $('fmTop'));
    put($('frameReadout'), $('fmTop'));
    ['addBlankFrameBtn', 'clearBtn', 'deleteFrameBtn', 'startOverBtn', 'restoreBtn'].forEach((id) => put($(id), $('fmRow')));
    put($('moveBlock'), $('frameMore'));
    measure();
  }
  function leave() {
    setSheet(false);
    restoreAll();
    dock.hidden = true; moreBtn.hidden = true; $('sheetHead').hidden = true; $('frameMore').hidden = true;
    root.classList.remove('phone-dock');
    root.style.removeProperty('--dock-h'); root.style.removeProperty('--sheet-top');
  }
  const sync = () => { if (mq.matches && !root.classList.contains('phone-dock')) enter(); else if (!mq.matches && root.classList.contains('phone-dock')) leave(); };

  moreBtn.addEventListener('click', toggleSheet);
  $('dockColor').addEventListener('click', () => setSheet(true));
  $('sheetClose').addEventListener('click', () => setSheet(false));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && sheet.classList.contains('open')) setSheet(false); });
  // the dock's color chip mirrors the paint color without touching the editor code
  new MutationObserver(() => { $('dockColor').style.background = $('curSwatch').style.background; })
    .observe($('curSwatch'), { attributes: true, attributeFilter: ['style'] });
  $('dockColor').style.background = $('curSwatch').style.background;
  window.addEventListener('resize', () => { if (root.classList.contains('phone-dock')) measure(); });
  if ('ResizeObserver' in window) new ResizeObserver(() => { if (root.classList.contains('phone-dock')) measure(); }).observe(dock);
  (mq.addEventListener ? mq.addEventListener('change', sync) : mq.addListener(sync));
  sync();
})();
