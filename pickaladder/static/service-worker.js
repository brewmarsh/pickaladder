const CACHE_NAME = 'pickaladder-cache-v16.0.1';
const OFFLINE_URL = '/offline';

// Import Firebase Scripts
importScripts('https://www.gstatic.com/firebasejs/8.10.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/8.10.1/firebase-messaging.js');

// Initialize Firebase in Service Worker
firebase.initializeApp({
  apiKey: "AIzaSyB...", // This should ideally be passed in, but FCM only strictly needs messagingSenderId for background messages
  authDomain: "pickaladder.firebaseapp.com",
  projectId: "pickaladder",
  storageBucket: "pickaladder.appspot.com",
  messagingSenderId: "402457219675",
  appId: "1:402457219675:web:a346e2dc0dfa732d31e57e",
  measurementId: "G-E28CXCXTSK"
});

const messaging = firebase.messaging();

// Handle background messages
messaging.setBackgroundMessageHandler(function(payload) {
  console.log('[service-worker.js] Received background message ', payload);
  const notificationTitle = payload.notification.title;
  const notificationOptions = {
    body: payload.notification.body,
    icon: '/static/pickaladder_logo_64.png',
    data: payload.data
  };

  return self.registration.showNotification(notificationTitle, notificationOptions);
});

const ASSETS_TO_CACHE = [
  OFFLINE_URL,
  '/static/css/variables.css',
  '/static/css/layout-utils.css',
  '/static/css/buttons.css',
  '/static/css/avatars.css',
  '/static/css/cards.css',
  '/static/css/data-displays.css',
  '/static/css/layout.css',
  '/static/style.css',
  '/static/dark.css',
  '/static/mobile.css',
  '/static/js/main.js',
  '/static/js/navbar.js',
  '/static/js/notifications.js',
  '/static/pickaladder_logo_64.png',
  '/static/img/pwa/icon-192.png',
  '/static/img/pwa/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Oswald:wght@300;400;500;600;700&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(ASSETS_TO_CACHE);
      })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Navigation: Network First, then Offline Fallback
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(OFFLINE_URL);
      })
    );
    return;
  }

  // Static Assets: Stale-While-Revalidate
  if (url.pathname.startsWith('/static/') ||
      url.hostname.includes('fonts.googleapis.com') ||
      url.hostname.includes('fonts.gstatic.com') ||
      url.hostname.includes('cdnjs.cloudflare.com')) {
    event.respondWith(
      caches.open(CACHE_NAME).then(cache => {
        return cache.match(event.request).then(cachedResponse => {
          const fetchPromise = fetch(event.request).then(networkResponse => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          });
          return cachedResponse || fetchPromise;
        });
      })
    );
    return;
  }

  // Default: Network First
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
