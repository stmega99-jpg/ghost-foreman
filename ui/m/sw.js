// Service worker for Ghost Foreman's own phone page (scope: /api/apps/ghost-foreman/m/).
//
// Why it exists: the page lives under the Gateway's authenticated /api namespace. When the 20-hour access cookie has
// expired, the server answers the page itself with 403 and the page never gets the chance to renew the session with
// its refresh cookie. This worker keeps the last good copy of the page and its two modules and serves them when the
// network answer is not OK; the page then calls /api/auth/refresh and carries on.
//
// It only ever caches these three static files. API data is never cached and never touched.
const CACHE = "gf-phone-v1";
const BASE = "/api/apps/ghost-foreman/m/";
const FILES = [BASE, BASE + "sdk.mjs", BASE + "app.mjs"];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches
      .open(CACHE)
      .then((c) => Promise.all(FILES.map((u) => fetch(u, { credentials: "same-origin" }).then((r) => (r.ok ? c.put(u, r) : null)).catch(() => null))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("gf-phone-") && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;
  // The page (any query string, e.g. ?q=… from a notification or ?token=… from the sign-in link) or one of its modules.
  const key = url.pathname === BASE || url.pathname === BASE.slice(0, -1) ? BASE : FILES.includes(url.pathname) ? url.pathname : null;
  if (!key) return; // API calls and everything else go straight to the network
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(key, copy));
          return res;
        }
        return caches.match(key).then((hit) => hit || res);
      })
      .catch(() => caches.match(key).then((hit) => hit || Response.error()))
  );
});
