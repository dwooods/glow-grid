// Phone layout (portrait; a desktop window only gets it when it is 900 px tall or less, a touch device always does): a bottom dock (tools, color, palette), a frame strip under the grid with Play, Undo, Redo, + and More,
// and the rest of the controls below the strip in normal flow (the page scrolls; More jumps to them). It only moves existing nodes, so ids, listeners and the desktop markup are untouched;
// leaving the layout (rotate, resize) puts every node back. Classic script: shares the global scope ($ comes from core.js).
(function () {
  const mq = window.matchMedia('(max-width: 760px) and (min-height: 600px) and ((max-height: 900px) or (pointer: coarse))');
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
  // One line of thumbnails fits beside Play, + and More; with more frames the strip drops to its own full-width row and wraps as tall as it needs (the page scrolls)
  const strip = $('frameStrip'), card = $('framesCard');
  function layoutStrip() {
    if (!root.classList.contains('phone-dock')) return;
    card.classList.remove('stack');
    const first = strip.firstElementChild;
    if (first) {
      const cell = first.offsetWidth + 8, fits = Math.max(1, Math.floor((strip.clientWidth - 8 + 8) / cell));
      card.classList.toggle('stack', strip.querySelectorAll('.frame-cell:not(.frame-empty)').length > fits);
    }
    measure();
  }
  // More and the color chip jump to the controls below the strip
  const jump = () => sheet.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });

  function enter() {
    root.classList.add('phone-dock');
    dock.hidden = false; moreBtn.hidden = false; $('frameMore').hidden = false;
    put($('toolRow'), $('dockTools'));
    put($('paletteGroup'), $('dockPalette'));
    put($('imgSwatchGroup'), $('dockPalette'));
    put($('historyRow'), card);
    put($('fpsInput').closest('.field-inline'), $('fmTop'));
    put($('frameReadout'), $('fmTop'));
    ['addBlankFrameBtn', 'clearBtn', 'deleteFrameBtn', 'startOverBtn', 'restoreBtn'].forEach((id) => put($(id), $('fmRow')));
    put($('moveBlock'), $('frameMore'));
    layoutStrip();
  }
  function leave() {
    card.classList.remove('stack');
    restoreAll();
    dock.hidden = true; moreBtn.hidden = true; $('frameMore').hidden = true;
    root.classList.remove('phone-dock');
    root.style.removeProperty('--dock-h'); root.style.removeProperty('--sheet-top');
  }
  const sync = () => { if (mq.matches && !root.classList.contains('phone-dock')) enter(); else if (!mq.matches && root.classList.contains('phone-dock')) leave(); };

  moreBtn.addEventListener('click', jump);
  $('dockColor').addEventListener('click', jump);
  // the dock's color chip mirrors the paint color without touching the editor code
  new MutationObserver(() => { $('dockColor').style.background = $('curSwatch').style.background; })
    .observe($('curSwatch'), { attributes: true, attributeFilter: ['style'] });
  $('dockColor').style.background = $('curSwatch').style.background;
  window.addEventListener('resize', layoutStrip);
  window.addEventListener('load', layoutStrip);
  new MutationObserver(layoutStrip).observe(strip, { childList: true });
  if ('ResizeObserver' in window) new ResizeObserver(() => { if (root.classList.contains('phone-dock')) measure(); }).observe(dock);
  (mq.addEventListener ? mq.addEventListener('change', sync) : mq.addListener(sync));
  sync();
})();
