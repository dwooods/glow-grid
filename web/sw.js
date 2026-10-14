// Offline support for the installed app: serve from cache, refresh in the
// background. Bump CACHE when the asset list changes.
const CACHE = 'glow-grid-v34';
const FONTS = 'glow-grid-fonts'; // Google Fonts stylesheet and files, cached on first online visit; kept across app versions
const FONT_HOSTS = ['fonts.googleapis.com', 'fonts.gstatic.com'];
const ASSETS = ['./', './index.html', './style.css', './manifest.webmanifest', './icon-192.png', './icon-512.png',
  './js/core.js', './js/led.js', './js/editor.js', './js/loupe.js', './js/import.js', './js/export.js', './js/help.js', './js/tools.js', './js/phone.js', './js/main.js'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE && k !== FONTS).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (FONT_HOSTS.includes(url.hostname)) {
    e.respondWith(caches.open(FONTS).then(async (cache) => {
      const hit = await cache.match(req);
      const fresh = fetch(req)
        .then((res) => { if (res.ok || res.type === 'opaque') cache.put(req, res.clone()); return res; })
        .catch(() => hit || Response.error());
      return hit || fresh;
    }));
    return;
  }
  if (url.origin !== location.origin) return;
  e.respondWith(caches.open(CACHE).then(async (cache) => {
    const hit = await cache.match(req, { ignoreSearch: true });
    const fresh = fetch(req)
      .then((res) => { if (res.ok) cache.put(req, res.clone()); return res; })
      .catch(() => hit);
    return hit || fresh;
  }));
});
