"use strict";

// RecallCheck changes frequently during beta. Do not keep an offline copy of
// HTML, CSS, JavaScript, or recall data because a stale service-worker cache
// can make a newly deployed page appear blank or outdated until a hard refresh.
const RECALLCHECK_CACHE_PREFIX = "recallcheck-";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(key => key.startsWith(RECALLCHECK_CACHE_PREFIX))
          .map(key => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

// Intentionally no fetch handler during beta. Requests use the browser/network
// normally, so Cloudflare deployments become visible without requiring users
// to force-refresh each page.
