const CACHE_NAME = "recallcheck-shell-v3";
const APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./assets/icons/recallcheck.svg",
  "./recallcheck-v3.css",
  "./recallcheck-v3-responsive.css",
  "./trust-v4-1.css",
  "./v4-1-1-mobile.css",
  "./pwa-share.css",
  "./pwa-share.js"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Safety-critical recall/source JSON bypasses the service worker completely.
  // This prevents Safari service-worker fetch/cache-mode compatibility issues
  // and guarantees Cache Storage is never used for live recall status data.
  if (url.pathname.includes("/data/") || /(?:recalls|source-status)\.json$/i.test(url.pathname)) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match("./index.html")));
    return;
  }

  event.respondWith(
    caches.match(request).then(cached => cached || fetch(request).then(response => {
      if (response.ok && ["style", "script", "image", "font"].includes(request.destination)) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(request, copy));
      }
      return response;
    }))
  );
});
