const CACHE_NAME = 'pickaladder-cache-v1';
const ASSETS_TO_CACHE = [
  '/static/css/layout-utils.css',
  '/static/js/main.js',
  '/static/img/logo.png',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(ASSETS_TO_CACHE);
      })
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Network First for HTML/Data (non-static)
  if (event.request.mode === 'navigate' || !url.pathname.startsWith('/static/')) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
  } else {
    // Cache First for Static Assets
    event.respondWith(
      caches.match(event.request)
        .then(response => {
          return response || fetch(event.request);
        })
    );
  }
});
