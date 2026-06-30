// static/sw.js
const CACHE_VERSION = 'elemes-v10';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const API_CACHE = `${CACHE_VERSION}-api`;
const ASSET_CACHE = `${CACHE_VERSION}-assets`;

// Assets yang di-precache (Vite immutable + critical)
const PRECACHE_URLS = [
  '/',
  '/manifest.json',
];

// Install: precache minimal assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then(cache => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  );
});

// Activate: hapus cache lama
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys
        .filter(k => k.startsWith('elemes-') && k !== STATIC_CACHE && k !== API_CACHE && k !== ASSET_CACHE)
        .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Hanya handle GET
  if (request.method !== 'GET') return;

  // NetworkOnly: API yang tidak boleh di-cache
  if (url.pathname.startsWith('/api/compile') ||
      url.pathname.startsWith('/api/track-progress') ||
      url.pathname.startsWith('/api/login') ||
      url.pathname.startsWith('/api/logout')) {
    return; // biarkan browser handle
  }

  // CacheFirst: Static assets (Vite immutable dengan hash)
  if (url.pathname.startsWith('/_app/immutable/')) {
    event.respondWith(cacheFirst(request, STATIC_CACHE, 365));
    return;
  }

  // CacheFirst: Gambar lesson (assets)
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(request, ASSET_CACHE, 7));
    return;
  }

  // CacheFirst: Font files (immutable)
  if (url.hostname === 'fonts.gstatic.com') {
    event.respondWith(cacheFirst(request, STATIC_CACHE, 365));
    return;
  }

  // NetworkFirst: API lesson data (cache 6 jam)
  if (url.pathname.startsWith('/api/lesson/') && url.pathname.endsWith('.json')) {
    event.respondWith(networkFirst(request, API_CACHE, 6 * 60));
    return;
  }

  // NetworkFirst: API lesson list (cache 1 jam)
  if (url.pathname.startsWith('/api/lessons')) {
    event.respondWith(networkFirst(request, API_CACHE, 60));
    return;
  }

  // StaleWhileRevalidate: HTML pages
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
    return;
  }

  // StaleWhileRevalidate: Google Fonts CSS, KaTeX
  if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'cdn.jsdelivr.net') {
    event.respondWith(staleWhileRevalidate(request, STATIC_CACHE));
    return;
  }
});

// ── Helpers ──────────────────────────────────────────────────────

async function cacheFirst(request, cacheName, maxAgeDays = 7) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) cache.put(request, response.clone());
  return response;
}

async function networkFirst(request, cacheName, maxAgeMinutes = 60) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ error: 'Offline', cached: false }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const networkFetch = fetch(request).then(response => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  }).catch(() => null);
  return cached || (await networkFetch) ||
    new Response('Offline — halaman ini belum pernah dibuka sebelumnya.', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' }
    });
}
