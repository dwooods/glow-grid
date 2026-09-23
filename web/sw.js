// Offline support for the installed app: serve from cache, refresh in the
// background. Bump CACHE when the asset list changes.
const CACHE = 'glow-grid-v2';
const ASSETS = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png'];

self.addEventListener('install', (e) => {
  // One at a time so a missing icon (e.g. when served by the Pi) doesn't block install
  e.waitUntil(caches.open(CACHE)
    .then((c) => Promise.allSettled(ASSETS.map((a) => c.add(a))))
    .then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/')) return; // live panel state from the Pi: never cache
  e.respondWith(caches.open(CACHE).then(async (cache) => {
    const hit = await cache.match(req, { ignoreSearch: true });
    const fresh = fetch(req)
      .then((res) => { if (res.ok) cache.put(req, res.clone()); return res; })
      .catch(() => hit);
    return hit || fresh;
  }));
});
