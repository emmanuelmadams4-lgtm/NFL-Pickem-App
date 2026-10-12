/* Pick'em Intel service worker. Hand-written, no dependencies.
 *
 *  /_next/static/* and /icons/*      cache-first (content-hashed, safe to keep)
 *  page navigations and other pages  network-first, cache fallback (so the app opens offline)
 *  GET /api/*                        network-first, cache fallback (replays are tagged x-sw-cache)
 *  team logos (cross-origin images)  stale-while-revalidate (opaque responses are fine)
 *  anything that is not a GET        never touched
 *
 * Bump VERSION to invalidate every cache; old ones are removed on activate.
 */
const VERSION = "v2"; // v2: owner app icon (D41) replaced the cache-first icons
const STATIC = `nflpi-static-${VERSION}`;
const PAGES = `nflpi-pages-${VERSION}`;
const API = `nflpi-api-${VERSION}`;
const IMAGES = `nflpi-img-${VERSION}`;
const CURRENT = [STATIC, PAGES, API, IMAGES];

// Pages whose HTML (and the /_next/static assets it names) are fetched at install so the app opens offline on first run.
const PRECACHE_PAGES = ["/", "/performance/", "/backtest/", "/settings/", "/game/"];
const PRECACHE_FILES = ["/manifest.webmanifest", "/icons/favicon-32.png", "/icons/icon-192.png", "/icons/icon-512.png", "/icons/apple-touch-icon.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const pages = await caches.open(PAGES);
      const statics = await caches.open(STATIC);
      const assets = new Set(PRECACHE_FILES.filter((f) => f.startsWith("/icons/")));
      // Best effort: one missing page must not block installing the worker.
      await Promise.all(
        PRECACHE_PAGES.map(async (url) => {
          try {
            const res = await fetch(url, { cache: "reload" });
            if (!res.ok) return;
            await pages.put(url, res.clone());
            const html = await res.text();
            for (const m of html.matchAll(/\/_next\/static\/[^"'\\\s<>)]+/g)) assets.add(m[0]);
          } catch {
            /* offline during install: the runtime handlers will fill the cache later */
          }
        }),
      );
      await pages.add("/manifest.webmanifest").catch(() => undefined);
      await Promise.all([...assets].map((a) => statics.add(a).catch(() => undefined)));
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(names.filter((n) => n.startsWith("nflpi-") && !CURRENT.includes(n)).map((n) => caches.delete(n)));
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("message", (event) => {
  const data = event.data;
  if (data === "SKIP_WAITING") self.skipWaiting();
  // Assets the page loaded before this worker took control would otherwise never be cached.
  if (data && data.type === "CACHE_URLS" && Array.isArray(data.urls)) {
    event.waitUntil(
      (async () => {
        const cache = await caches.open(STATIC);
        await Promise.all(
          data.urls
            .filter((u) => typeof u === "string" && new URL(u, self.location.origin).origin === self.location.origin)
            .map((u) => cache.match(u).then((hit) => hit || cache.add(u)).catch(() => undefined)),
        );
      })(),
    );
  }
});

async function trim(cacheName, max) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  for (let i = 0; i < keys.length - max; i++) await cache.delete(keys[i]);
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const res = await fetch(request);
  if (res.ok) {
    const cache = await caches.open(cacheName);
    await cache.put(request, res.clone());
    trim(cacheName, 250);
  }
  return res;
}

async function networkFirst(request, cacheName, { ignoreSearch = false, tagReplay = false, fallbackUrl } = {}) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(request);
    if (res.ok) {
      cache.put(request, res.clone()).then(() => trim(cacheName, 120));
      return res;
    }
    if (res.status >= 500) {
      const cached = await cache.match(request, { ignoreSearch });
      if (cached) return tagReplay ? replay(cached) : cached;
    }
    return res;
  } catch (err) {
    let cached = await cache.match(request, { ignoreSearch });
    if (!cached && fallbackUrl) cached = await cache.match(fallbackUrl);
    if (cached) return tagReplay ? replay(cached) : cached;
    throw err;
  }
}

/** Mark a cached API response so the app can tell it is not fresh from the server. */
function replay(response) {
  const headers = new Headers(response.headers);
  headers.set("x-sw-cache", "1");
  headers.set("x-sw-cached-at", response.headers.get("date") || "");
  return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
}

async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);
  const network = fetch(request)
    .then((res) => {
      if (res.ok || res.type === "opaque") {
        cache.put(request, res.clone()).then(() => trim(cacheName, 150));
      }
      return res;
    })
    .catch(() => undefined);
  if (cached) {
    network.catch(() => undefined);
    return cached;
  }
  const res = await network;
  return res || Response.error();
}

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return; // never cache or alter writes

  const url = new URL(request.url);

  if (url.origin !== self.location.origin) {
    if (url.hostname === "a.espncdn.com" || request.destination === "image") {
      event.respondWith(staleWhileRevalidate(request, IMAGES));
    }
    return;
  }

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(networkFirst(request, API, { tagReplay: true }));
    return;
  }

  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(cacheFirst(request, STATIC));
    return;
  }

  // Pages, route payloads and the manifest. Query strings (?id=, ?season=) vary, the shell does not.
  event.respondWith(networkFirst(request, PAGES, { ignoreSearch: true, fallbackUrl: request.mode === "navigate" ? "/" : undefined }));
});

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "Pick'em Intel";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || "",
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      tag: data.tag || undefined,
      data: { url: data.url || "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin).href;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      const open = windows.find((w) => new URL(w.url).origin === self.location.origin);
      if (open) {
        await open.focus();
        if ("navigate" in open && open.url !== target) {
          try {
            await open.navigate(target);
          } catch {
            /* navigation can be refused; focusing is enough */
          }
        }
        return;
      }
      await self.clients.openWindow(target);
    })(),
  );
});
