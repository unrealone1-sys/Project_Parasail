/* ParaSail service worker - offline app shell for the mobile web app.
 *
 * Strategy:
 *  - "/" (the app shell): NETWORK-FIRST - page updates propagate
 *    immediately on every deployment; the cache is the offline fallback,
 *    never the primary source.
 *  - "/static/*" (Leaflet, Lora fonts, icons): CACHE-FIRST - immutable
 *    per release; bump CACHE below when they change.
 *  - data APIs: never cached (advisories must be fresh; the app already
 *    degrades with visible data-age flags when offline).
 * Served at /sw.js so its scope covers the app. */
const CACHE = "parasail-shell-v2";
const SHELL = [
  "/",
  "/static/leaflet.css",
  "/static/leaflet.js",
  "/static/manifest.webmanifest",
  "/static/fonts/lora-normal-latin.woff2",
  "/static/fonts/lora-normal-latin-ext.woff2",
  "/static/fonts/lora-italic-latin.woff2",
  "/static/fonts/lora-italic-latin-ext.woff2",
  "/static/icons/icon-192.png",
  "/static/icons/favicon-32.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;          // POSTs carry live actions
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;  // let map tiles pass through

  if (url.pathname === "/") {
    // network-first: freshness wins; cache keeps the app open offline
    e.respondWith(
      fetch(e.request)
        .then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return resp;
        })
        .catch(() =>
          caches.match(e.request).then((hit) => hit || Response.error()))
    );
    return;
  }

  if (url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(e.request).then((hit) =>
        hit ||
        fetch(e.request).then((resp) => {
          const copy = resp.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return resp;
        }))
    );
  }
});
