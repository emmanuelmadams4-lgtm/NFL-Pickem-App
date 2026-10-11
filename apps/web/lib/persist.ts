import { dehydrate, hydrate, type QueryClient } from "@tanstack/react-query";

/**
 * Persist the React Query cache to localStorage so the app opens offline with the last data it saw.
 * No extra dependency: dehydrate/hydrate come with @tanstack/react-query.
 */
export const CACHE_KEY = "nflpi_cache";
const VERSION = 1;
const MAX_CHARS = 3_500_000; // localStorage is about 5MB of UTF-16; stay well under

export const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

export function restoreCache(client: QueryClient): void {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as { version: number; savedAt: number; state: Parameters<typeof hydrate>[1] };
    if (parsed.version !== VERSION || Date.now() - parsed.savedAt > WEEK_MS) {
      localStorage.removeItem(CACHE_KEY);
      return;
    }
    hydrate(client, parsed.state);
  } catch {
    /* unreadable cache: start fresh */
  }
}

function save(client: QueryClient): void {
  try {
    const state = dehydrate(client, { shouldDehydrateQuery: (q) => q.state.status === "success" });
    // newest first, then keep as many as fit
    state.queries.sort((a, b) => b.state.dataUpdatedAt - a.state.dataUpdatedAt);
    let size = 0;
    const kept = [];
    for (const q of state.queries) {
      const n = JSON.stringify(q).length;
      if (size + n > MAX_CHARS) continue;
      size += n;
      kept.push(q);
    }
    localStorage.setItem(CACHE_KEY, JSON.stringify({ version: VERSION, savedAt: Date.now(), state: { ...state, queries: kept } }));
  } catch {
    // quota exceeded or storage blocked: drop the stale copy rather than keep a half-written one
    try {
      localStorage.removeItem(CACHE_KEY);
    } catch {
      /* ignore */
    }
  }
}

/** Save on cache changes, debounced to about a second. Returns a stop function. */
export function startPersisting(client: QueryClient): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const unsubscribe = client.getQueryCache().subscribe(() => {
    clearTimeout(timer);
    timer = setTimeout(() => save(client), 1000);
  });
  const flush = () => {
    clearTimeout(timer);
    save(client);
  };
  window.addEventListener("pagehide", flush);
  return () => {
    unsubscribe();
    clearTimeout(timer);
    window.removeEventListener("pagehide", flush);
  };
}

export function clearPersistedCache(): void {
  try {
    localStorage.removeItem(CACHE_KEY);
  } catch {
    /* ignore */
  }
  if (typeof caches !== "undefined") {
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => n.startsWith("nflpi-api-")).map((n) => caches.delete(n))))
      .catch(() => {});
  }
}
