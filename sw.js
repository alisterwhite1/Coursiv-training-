const CACHE_NAME = 'sitesnag-v19';
const APP_SHELL = [
  './sitesnag.html',
  './manifest.json',
  'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.49.2/dist/umd/supabase.min.js',
  'https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
  'https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(names =>
      Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const isAppHtml = req.mode === 'navigate' || req.url.includes('sitesnag.html');
  const isKnownCDN = APP_SHELL.includes(req.url);

  // Only manage the app's own HTML and the explicitly pinned CDN libraries above.
  // Everything else (R2 photos, Supabase API calls, etc.) is left completely alone —
  // routing it through this service worker's fetch() forces CORS enforcement that
  // breaks plain cross-origin <img> loads even when they'd work fine natively.
  if (!isAppHtml && !isKnownCDN) return;

  if (isAppHtml) {
    // Network-first for the app itself — always get the latest version when online,
    // fall back to cache only when offline so the app still opens.
    event.respondWith(
      fetch(req).then(res => {
        const copy = res.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
        return res;
      }).catch(() => caches.match(req).then(r => r || caches.match('./sitesnag.html')))
    );
    return;
  }

  // Cache-first for pinned CDN libraries — they don't change under a fixed URL.
  event.respondWith(
    caches.match(req).then(cached => cached || fetch(req).then(res => {
      const copy = res.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
      return res;
    }).catch(() => cached))
  );
});
