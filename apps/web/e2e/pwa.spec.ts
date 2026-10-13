import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { expect, test, type APIRequestContext, type BrowserContext, type Page } from "@playwright/test";

/**
 * Step 6 gate (docs/gauntlet/logs/step-6.md): the iPhone app. Production export at 393x852 with the
 * service worker on. Seeded by backend/tests/e2e_seed.py; one worker, so each test leaves the data
 * as the others expect.
 */
test.use({ viewport: { width: 393, height: 852 }, hasTouch: true });

const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
const SW_FILE = path.resolve(__dirname, "../out/sw.js");

type Team = { abbr: string; name: string };
type Game = { game_id: string; kickoff_utc: string; status: string; locked: boolean; time_tbd?: boolean; my_pick: string | null; away: Team; home: Team };
type Meta = { current_season: number; current_week: number; server_time: string };

async function api<T>(request: APIRequestContext, p: string): Promise<T> {
  const res = await request.get(`/api${p}`, { headers: AUTH });
  expect(res.ok(), p).toBeTruthy();
  return res.json() as Promise<T>;
}

async function board(request: APIRequestContext) {
  const meta = await api<Meta>(request, "/meta");
  const week = await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/${meta.current_week}`);
  const games = [...week.games].sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc));
  const open = games.filter((g) => !g.time_tbd && !g.locked && g.status === "scheduled");
  return { meta, games, open };
}

async function signIn(page: Page) {
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
}

const pickGroup = (page: Page, g: Game) => page.getByRole("group", { name: `Your pick: ${g.away.abbr} at ${g.home.abbr}` });

/** 15 s: the first signed-in load on a cold server takes longer than the default 5 s. */
async function boardLoaded(page: Page) {
  await expect(page.getByRole("link", { name: /^Open matchup:/ }).first()).toBeVisible({ timeout: 15_000 });
}

/** The worker is installed (shell and static files cached) and controls this page. */
async function workerControls(page: Page) {
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller), { timeout: 20_000 }).toBe(true);
}

/** The week on screen has reached the persisted query cache (it is saved about a second after it loads). */
async function weekPersisted(page: Page) {
  await expect.poll(() => page.evaluate(() => (localStorage.getItem("nflpi_cache") ?? "").includes('"week"')), { timeout: 10_000 }).toBe(true);
}

const cacheNames = (page: Page) => page.evaluate(() => caches.keys());
const cachedUrls = (page: Page) =>
  page.evaluate(async () => {
    const urls: string[] = [];
    for (const name of await caches.keys()) for (const req of await (await caches.open(name)).keys()) urls.push(req.url);
    return urls;
  });

/**
 * Really offline. Playwright's setOffline does not reach the service worker's own requests, so the
 * worker is cut off too, through the browser's debug protocol. Proven by a request the worker cannot have cached.
 */
async function goOffline(page: Page) {
  const context = page.context();
  await context.setOffline(true);
  const cdp = await context.browser()!.newBrowserCDPSession();
  const { targetInfos } = await cdp.send("Target.getTargets");
  for (const t of targetInfos.filter((x) => x.type === "service_worker")) {
    const { sessionId } = await cdp.send("Target.attachToTarget", { targetId: t.targetId, flatten: false });
    const tell = (id: number, method: string, params = {}) => cdp.send("Target.sendMessageToTarget", { sessionId, message: JSON.stringify({ id, method, params }) });
    await tell(1, "Network.enable");
    await tell(2, "Network.emulateNetworkConditions", { offline: true, latency: 0, downloadThroughput: -1, uploadThroughput: -1 });
  }
  const reached = await page.evaluate(() => fetch(`/_next/static/offline-probe-${Date.now()}.js`).then(() => true, () => false));
  expect(reached, "the worker cannot reach the network either").toBe(false);
}

/** Chunk and module load failures, from page errors and the console. */
function chunkErrors(page: Page): string[] {
  const seen: string[] = [];
  const bad = /ChunkLoadError|Loading chunk|Failed to fetch dynamically imported module|Failed to load chunk/i;
  page.on("pageerror", (e) => bad.test(String(e)) && seen.push(String(e)));
  page.on("console", (m) => m.type() === "error" && bad.test(m.text()) && seen.push(m.text()));
  return seen;
}

/** The API is up but never answers: every call hangs 30 s, then fails. The phone still says it is online. */
async function serverUnreachable(context: BrowserContext) {
  await context.route("**/api/**", async (route) => {
    await new Promise((r) => setTimeout(r, 30_000));
    await route.abort().catch(() => undefined);
  });
  return () => context.unrouteAll({ behavior: "ignoreErrors" });
}

test("P1 manifest: installable, standalone, the owner's icons all load", async ({ page, request }) => {
  const res = await request.get("/manifest.webmanifest");
  expect(res.ok()).toBeTruthy();
  const m = (await res.json()) as { name: string; short_name: string; start_url: string; scope: string; display: string; icons: { src: string; sizes: string; purpose?: string }[] };
  expect(m).toMatchObject({ start_url: "/", scope: "/", display: "standalone" });
  expect(m.name && m.short_name).toBeTruthy();
  expect(m.icons.some((i) => i.sizes === "192x192")).toBe(true);
  expect(m.icons.some((i) => i.sizes === "512x512" && i.purpose === "any")).toBe(true);
  expect(m.icons.some((i) => i.sizes === "512x512" && i.purpose === "maskable")).toBe(true);
  for (const icon of m.icons) {
    const img = await request.get(icon.src);
    expect(img.ok(), icon.src).toBeTruthy();
    expect(img.headers()["content-type"], icon.src).toContain("image/png");
  }
  await page.goto("/");
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute("href", /manifest\.webmanifest/);
  await expect(page.locator('link[rel="apple-touch-icon"]')).toHaveCount(1);
  await expect(page.locator('meta[name="viewport"]')).toHaveAttribute("content", /viewport-fit=cover/);
});

test("P2 one offline layer (S17): the worker controls the page and caches the shell and static files, never API data", async ({ page }) => {
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await workerControls(page);
  await page.reload(); // every request on this load can go through the worker
  await boardLoaded(page);
  // An API call from the controlled page must reach the network without the worker answering it.
  const [apiCall] = await Promise.all([
    page.waitForResponse((r) => new URL(r.url()).pathname === "/api/health"),
    page.evaluate(() => fetch("/api/health").then((r) => r.ok)),
  ]);
  expect(apiCall.fromServiceWorker(), "the worker leaves API calls alone").toBe(false);
  await page.waitForLoadState("networkidle");
  expect(await cacheNames(page), "no API cache").not.toContainEqual(expect.stringMatching(/api/i));
  const urls = await cachedUrls(page);
  expect(urls.length, "shell and static files are cached").toBeGreaterThan(5);
  expect(urls.filter((u) => new URL(u).pathname.startsWith("/api/")), "API responses in the worker's caches").toEqual([]);
});

test("P3 offline reload: the saved week opens and a banner says the phone is offline", async ({ page }) => {
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await workerControls(page);
  await weekPersisted(page);
  await goOffline(page);
  await page.reload();
  await boardLoaded(page);
  await expect(page.getByRole("status").filter({ hasText: /offline/i })).toBeVisible();
});

test("P4 server unreachable while online (B4): saved data and a 'can't reach the server' banner within 6 s; a pick stays queued, then syncs", async ({ page, context, request }) => {
  const { open } = await board(request);
  const g = open[0];
  const serverPick = async () => (await board(request)).games.find((x) => x.game_id === g.game_id)!.my_pick;
  expect(await serverPick(), "starts with no pick").toBeNull();

  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await workerControls(page);
  await weekPersisted(page);

  const restore = await serverUnreachable(context);
  try {
    await page.reload();
    await boardLoaded(page);
    const banner = page.getByRole("status").filter({ hasText: /can.t reach the server/i });
    await expect(banner).toBeVisible({ timeout: 6_000 });
    await expect(banner).toContainText(/Tailscale/);
    await expect(banner, "says how old the data on screen is").toContainText(/showing data from/i);

    await pickGroup(page, g).getByRole("button", { name: `Pick ${g.home.name}` }).click();
    await expect(page.getByText("Waiting to sync")).toBeVisible({ timeout: 6_000 });
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("nflpi_pick_queue") ?? "{}")), "queued on the phone").toEqual({ [g.game_id]: g.home.abbr });
    expect(await serverPick(), "not on the server yet").toBeNull();
  } finally {
    await restore();
  }

  // The server answers again: opening the app sends the queued pick and the banner goes away.
  await page.reload();
  await boardLoaded(page);
  await expect.poll(serverPick, { timeout: 10_000 }).toBe(g.home.abbr);
  await expect(page.getByText("Waiting to sync")).toHaveCount(0);
  await expect(page.getByRole("status").filter({ hasText: /can.t reach the server/i })).toHaveCount(0);

  const cleared = await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH });
  expect(cleared.ok()).toBeTruthy();
});

test("P11 a newer pick wins: sending a pick directly clears that game's older queued pick", async ({ page, context, request }) => {
  const { open } = await board(request);
  const g = open[0];
  const serverPick = async () => (await board(request)).games.find((x) => x.game_id === g.game_id)!.my_pick;
  // An older choice (away) is still queued, and the health check hangs, so nothing flushes it yet.
  await page.addInitScript(([id, team]) => localStorage.setItem("nflpi_pick_queue", JSON.stringify({ [id]: team })), [g.game_id, g.away.abbr]);
  await context.route("**/api/health", async (route) => {
    await new Promise((r) => setTimeout(r, 30_000));
    await route.abort().catch(() => undefined);
  });
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  try {
    await pickGroup(page, g).getByRole("button", { name: `Pick ${g.home.name}` }).click(); // the server is still thought reachable: sent directly
    await expect.poll(serverPick, { timeout: 4_000 }).toBe(g.home.abbr);
    await expect.poll(() => page.evaluate(() => localStorage.getItem("nflpi_pick_queue")), { message: "the older queued pick is gone" }).toBe("{}");
  } finally {
    await context.unrouteAll({ behavior: "ignoreErrors" });
  }
  // The server answers health again; whatever is flushed must not bring the older pick back.
  await expect(page.getByRole("status").filter({ hasText: /can.t reach the server/i })).toHaveCount(0, { timeout: 30_000 });
  expect(await serverPick()).toBe(g.home.abbr);
  expect((await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH })).ok()).toBeTruthy();
});

test("P12 a queued pick the server refuses with an error: he is told, the pick stays queued, and it is sent again", async ({ page, context, request }) => {
  const { open } = await board(request);
  const g = open[0];
  const serverPick = async () => (await board(request)).games.find((x) => x.game_id === g.game_id)!.my_pick;
  await page.addInitScript(([id, team]) => localStorage.setItem("nflpi_pick_queue", JSON.stringify({ [id]: team })), [g.game_id, g.home.abbr]);
  await context.route("**/api/picks/**", (route) => route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"boom"}' }));
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  try {
    await expect(page.getByText(/not saved yet/i)).toBeVisible({ timeout: 8_000 });
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("nflpi_pick_queue") ?? "{}")), "still queued").toEqual({ [g.game_id]: g.home.abbr });
  } finally {
    await context.unrouteAll({ behavior: "ignoreErrors" });
  }
  await expect.poll(serverPick, { message: "sent again without him doing anything", timeout: 25_000 }).toBe(g.home.abbr);
  await expect(page.getByText("Waiting to sync")).toHaveCount(0);
  expect((await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH })).ok()).toBeTruthy();
});

/** Hold the first save of one game's pick for `ms`, then let it through. `seen` resolves when that save starts. */
async function holdFirstSave(context: BrowserContext, gameId: string, ms: number) {
  let started: () => void = () => undefined;
  const seen = new Promise<void>((r) => (started = r));
  let held = false;
  await context.route(`**/api/picks/${gameId}`, async (route) => {
    if (held || route.request().method() !== "PUT") return route.continue();
    held = true;
    started();
    await new Promise((r) => setTimeout(r, ms));
    await route.continue().catch(() => undefined);
  });
  return { seen }; // wrapped: an async function would otherwise wait for it here
}

test("P13 a pick queued while an older one is being sent is kept and sent after it", async ({ page, context, request }) => {
  const { open } = await board(request);
  const g = open[0];
  const serverPick = async () => (await board(request)).games.find((x) => x.game_id === g.game_id)!.my_pick;
  await page.addInitScript(([id, team]) => localStorage.setItem("nflpi_pick_queue", JSON.stringify({ [id]: team })), [g.game_id, g.away.abbr]);
  const { seen: sending } = await holdFirstSave(context, g.game_id, 2_000);
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await sending; // the queued away pick is on its way
  try {
    await context.setOffline(true);
    await pickGroup(page, g).getByRole("button", { name: `Pick ${g.home.name}` }).click(); // offline: queued
    await expect.poll(() => page.evaluate(() => localStorage.getItem("nflpi_pick_queue"))).toContain(g.home.abbr);
    await context.setOffline(false);
    // The older pick may land first for a moment; what matters is where the server and the queue end up.
    await expect.poll(serverPick, { message: "then the newer pick is sent", timeout: 25_000 }).toBe(g.home.abbr);
    await expect(pickGroup(page, g).getByRole("button", { name: `${g.home.name} picked` })).toBeVisible();
    await expect.poll(() => page.evaluate(() => localStorage.getItem("nflpi_pick_queue")), { message: "nothing left waiting" }).toBe("{}");
    await page.waitForTimeout(3_000);
    expect(await serverPick(), "and it stays the newer pick").toBe(g.home.abbr);
  } finally {
    await context.setOffline(false);
    await context.unrouteAll({ behavior: "ignoreErrors" });
    await page.waitForTimeout(2_500); // let a held save finish before the pick is cleared
    expect((await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH })).ok()).toBeTruthy();
  }
});

test("P14 a tap while an older queued pick is being sent: the tap wins on the server", async ({ page, context, request }) => {
  const { open } = await board(request);
  const g = open[0];
  const serverPick = async () => (await board(request)).games.find((x) => x.game_id === g.game_id)!.my_pick;
  await page.addInitScript(([id, team]) => localStorage.setItem("nflpi_pick_queue", JSON.stringify({ [id]: team })), [g.game_id, g.away.abbr]);
  const { seen: sending } = await holdFirstSave(context, g.game_id, 2_000);
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await sending;
  try {
    await pickGroup(page, g).getByRole("button", { name: `Pick ${g.home.name}` }).click(); // online: sent directly
    await page.waitForTimeout(4_000); // both saves have landed, in whatever order the app allowed
    expect(await serverPick(), "the older queued pick must not land after the tap").toBe(g.home.abbr);
    await expect(page.getByText("Waiting to sync")).toHaveCount(0);
  } finally {
    await context.unrouteAll({ behavior: "ignoreErrors" });
    expect((await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH })).ok()).toBeTruthy();
  }
});

test("P16 the app is closed while a tapped pick is still being sent: the pick is kept on the phone and sent on the next open", async ({ page, context, request }) => {
  const { open } = await board(request);
  const g = open[0];
  const serverPick = async () => (await board(request)).games.find((x) => x.game_id === g.game_id)!.my_pick;
  const { seen: sending } = await holdFirstSave(context, g.game_id, 2_000);
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  try {
    await pickGroup(page, g).getByRole("button", { name: `Pick ${g.home.name}` }).click(); // online: sent directly
    await sending;
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("nflpi_pick_queue") ?? "{}")), "on the phone until the server has it").toEqual({ [g.game_id]: g.home.abbr });
    await page.reload(); // the request dies with the page, as when iOS closes the app
    await boardLoaded(page);
    await expect.poll(serverPick, { message: "sent on the next open", timeout: 10_000 }).toBe(g.home.abbr);
    await expect.poll(() => page.evaluate(() => localStorage.getItem("nflpi_pick_queue"))).toBe("{}");
  } finally {
    await context.unrouteAll({ behavior: "ignoreErrors" });
    expect((await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH })).ok()).toBeTruthy();
  }
});

test("P17 a second tap while the first is still being sent is on the phone at once, and survives the app closing", async ({ page, context, request }) => {
  const { open } = await board(request);
  const g = open[0];
  const serverPick = async () => (await board(request)).games.find((x) => x.game_id === g.game_id)!.my_pick;
  const { seen: sending } = await holdFirstSave(context, g.game_id, 2_000);
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  try {
    await pickGroup(page, g).getByRole("button", { name: `Pick ${g.away.name}` }).click(); // first tap: being sent
    await sending;
    await pickGroup(page, g).getByRole("button", { name: `Pick ${g.home.name}` }).click(); // second tap: waits its turn
    await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem("nflpi_pick_queue") ?? "{}")), { message: "the second tap is on the phone before its turn to send", timeout: 1_000 }).toEqual({ [g.game_id]: g.home.abbr });
    await expect(pickGroup(page, g).getByRole("button", { name: `${g.home.name} picked` }), "and the button shows it").toBeVisible();
    await page.reload(); // both requests die with the page, as when iOS closes the app
    await boardLoaded(page);
    await expect.poll(serverPick, { message: "the last tap is sent on the next open", timeout: 10_000 }).toBe(g.home.abbr);
    await expect.poll(() => page.evaluate(() => localStorage.getItem("nflpi_pick_queue"))).toBe("{}");
  } finally {
    await context.unrouteAll({ behavior: "ignoreErrors" });
    expect((await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH })).ok()).toBeTruthy();
  }
});

for (const stored of ["null", "[1]", "7", '{"x":5}', "{not json"]) {
  test(`P18 a damaged saved queue (${stored}) does not break the app: the board opens and a pick still saves`, async ({ page, request }) => {
    const { open } = await board(request);
    const g = open[0];
    const serverPick = async () => (await board(request)).games.find((x) => x.game_id === g.game_id)!.my_pick;
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.addInitScript((v) => {
      if (!sessionStorage.getItem("seeded")) localStorage.setItem("nflpi_pick_queue", v);
      sessionStorage.setItem("seeded", "1");
    }, stored);
    await signIn(page);
    await page.goto("/");
    await boardLoaded(page);
    try {
      await pickGroup(page, g).getByRole("button", { name: `Pick ${g.home.name}` }).click();
      await expect.poll(serverPick, { timeout: 8_000 }).toBe(g.home.abbr);
      await expect.poll(() => page.evaluate(() => localStorage.getItem("nflpi_pick_queue"))).toBe("{}");
      expect(errors, "no script error").toEqual([]);
    } finally {
      expect((await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH })).ok()).toBeTruthy();
    }
  });
}

test("P19 the phone cannot store a waiting pick (storage full): he is told to keep the app open", async ({ page, context }) => {
  const { open } = await board(page.request);
  const g = open[0];
  await page.addInitScript(() => {
    const real = Storage.prototype.setItem;
    Storage.prototype.setItem = function (k: string, v: string) {
      if (k === "nflpi_pick_queue") throw new DOMException("full", "QuotaExceededError");
      return real.call(this, k, v);
    };
  });
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  try {
    await context.setOffline(true);
    await pickGroup(page, g).getByRole("button", { name: `Pick ${g.home.name}` }).click();
    await expect(page.getByText(/keep the app open/i)).toBeVisible();
    await expect(page.getByText("Waiting to sync")).toBeVisible();
  } finally {
    await context.setOffline(false);
  }
});

test("P20 two open copies of the app (Home Screen and a Safari tab) do not overwrite each other's waiting picks", async ({ page, context, request }) => {
  const { open } = await board(request);
  test.setTimeout(90_000); // two page loads, then a wait for the timer that sends waiting picks
  expect(open.length, "needs two open games").toBeGreaterThanOrEqual(2);
  const [g0, g1] = open;
  const serverPick = async (id: string) => (await board(request)).games.find((x) => x.game_id === id)!.my_pick;
  const other = await context.newPage();
  for (const p of [page, other]) {
    await signIn(p);
    await p.goto("/");
    await boardLoaded(p);
  }
  try {
    await context.setOffline(true);
    await page.getByRole("group", { name: `Your pick: ${g0.away.abbr} at ${g0.home.abbr}` }).getByRole("button", { name: `Pick ${g0.home.name}` }).click();
    await expect.poll(() => page.evaluate(() => localStorage.getItem("nflpi_pick_queue"))).toContain(g0.game_id);
    await pickGroup(other, g1).getByRole("button", { name: `Pick ${g1.home.name}` }).click();
    await expect
      .poll(() => other.evaluate(() => JSON.parse(localStorage.getItem("nflpi_pick_queue") ?? "{}")), { message: "both picks are still waiting" })
      .toEqual({ [g0.game_id]: g0.home.abbr, [g1.game_id]: g1.home.abbr });
    await expect(pickGroup(page, g1).getByRole("button", { name: `${g1.home.name} picked` }), "the first copy shows the pick made in the second").toBeVisible();
    await context.setOffline(false);
    for (const g of [g0, g1]) await expect.poll(() => serverPick(g.game_id), { timeout: 25_000 }).toBe(g.home.abbr);
  } finally {
    await context.setOffline(false);
    await other.close();
    for (const g of [g0, g1]) expect((await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH })).ok()).toBeTruthy();
  }
});

test("P21 a waiting pick the server refuses as locked (409): it is dropped, he is told, and it is not sent again", async ({ page, context, request }) => {
  const { open } = await board(request);
  const g = open[0];
  let sends = 0;
  await page.addInitScript(([id, team]) => localStorage.setItem("nflpi_pick_queue", JSON.stringify({ [id]: team })), [g.game_id, g.home.abbr]);
  await context.route(`**/api/picks/${g.game_id}`, (route) => {
    sends++;
    return route.fulfill({ status: 409, contentType: "application/json", body: '{"detail":"Game has kicked off"}' });
  });
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  try {
    await expect(page.getByText(/not saved: locked at kickoff/i)).toBeVisible({ timeout: 8_000 });
    await expect.poll(() => page.evaluate(() => localStorage.getItem("nflpi_pick_queue"))).toBe("{}");
    await expect(page.getByText("Waiting to sync")).toHaveCount(0);
    await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange"))); // a later flush has nothing to send
    await page.waitForLoadState("networkidle");
    expect(sends, "sent once").toBe(1);
  } finally {
    await context.unrouteAll({ behavior: "ignoreErrors" });
  }
});

test("P22 while the phone cannot store the queue, an older stored pick never comes back over a newer one", async ({ page, request }) => {
  const { open } = await board(request);
  expect(open.length, "needs two open games").toBeGreaterThanOrEqual(2);
  const [a, b] = open;
  const serverPick = async (id: string) => (await board(request)).games.find((x) => x.game_id === id)!.my_pick;
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  try {
    // An older waiting pick is in storage, then storage stops taking writes.
    await page.evaluate(([id, team]) => {
      localStorage.setItem("nflpi_pick_queue", JSON.stringify({ [id]: team }));
      const real = Storage.prototype.setItem;
      Storage.prototype.setItem = function (k: string, v: string) {
        if (k === "nflpi_pick_queue") throw new DOMException("full", "QuotaExceededError");
        return real.call(this, k, v);
      };
    }, [a.game_id, a.away.abbr]);
    await pickGroup(page, a).getByRole("button", { name: `Pick ${a.home.name}` }).click();
    await expect.poll(() => serverPick(a.game_id), { message: "the newer pick is saved" }).toBe(a.home.abbr);
    await pickGroup(page, b).getByRole("button", { name: `Pick ${b.home.name}` }).click();
    await expect.poll(() => serverPick(b.game_id)).toBe(b.home.abbr);
    await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange"))); // a later flush
    await page.waitForTimeout(3_000);
    expect(await serverPick(a.game_id), "the older stored pick was not sent over the newer one").toBe(a.home.abbr);
    await expect(pickGroup(page, a).getByRole("button", { name: `${a.home.name} picked` })).toBeVisible();
    await expect(page.getByText("Waiting to sync")).toHaveCount(0);
  } finally {
    for (const g of [a, b]) expect((await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH })).ok()).toBeTruthy();
  }
});

test("P15 one queued pick the server keeps refusing does not hold back the others", async ({ page, context, request }) => {
  const { open } = await board(request);
  expect(open.length, "needs two open games").toBeGreaterThanOrEqual(2);
  const [bad, good] = open;
  const serverPick = async (id: string) => (await board(request)).games.find((x) => x.game_id === id)!.my_pick;
  await page.addInitScript((q) => localStorage.setItem("nflpi_pick_queue", JSON.stringify(q)), { [bad.game_id]: bad.home.abbr, [good.game_id]: good.home.abbr });
  await context.route(`**/api/picks/${bad.game_id}`, (route) => route.fulfill({ status: 500, contentType: "application/json", body: '{"detail":"boom"}' }));
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  try {
    await expect.poll(() => serverPick(good.game_id), { message: "the other pick is saved", timeout: 8_000 }).toBe(good.home.abbr);
    expect(await page.evaluate(() => JSON.parse(localStorage.getItem("nflpi_pick_queue") ?? "{}")), "only the refused pick is still queued").toEqual({ [bad.game_id]: bad.home.abbr });
  } finally {
    await context.unrouteAll({ behavior: "ignoreErrors" });
  }
  await expect.poll(() => serverPick(bad.game_id), { timeout: 25_000 }).toBe(bad.home.abbr);
  for (const g of [bad, good]) expect((await request.delete(`/api/picks/${g.game_id}`, { headers: AUTH })).ok()).toBeTruthy();
});

test("P5 kickoff passes while offline: the pick buttons lock from the saved kickoff time", async ({ page, request }) => {
  const { meta, open } = await board(request);
  const g = open[0];
  await page.clock.install({ time: new Date(meta.server_time) });
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await workerControls(page);
  await page.clock.runFor(2_000); // let the debounced save run
  await weekPersisted(page);
  await goOffline(page);
  await page.reload();
  await boardLoaded(page);
  const buttons = pickGroup(page, g).getByRole("button");
  await expect(buttons.first()).toBeEnabled();
  await page.clock.fastForward(Date.parse(g.kickoff_utc) - Date.parse(meta.server_time) + 1_000);
  await page.clock.runFor(4_000);
  await expect(buttons.first()).toBeDisabled({ timeout: 2_000 });
  await expect(buttons.nth(1)).toBeDisabled();
});

test("P6 new build (B11): sw.js carries the build ID; coming back to the app finds build B, offers Reload, and B takes over", async ({ page }) => {
  const original = await readFile(SW_FILE, "utf8");
  const idA = /const BUILD_ID = "([^"]+)"/.exec(original)?.[1];
  expect(idA, 'out/sw.js has `const BUILD_ID = "<id>"` stamped by the build').toMatch(/^[A-Za-z0-9._-]{6,}$/);
  expect(idA).not.toContain("__");
  const idB = `${idA}-b`;

  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await workerControls(page);
  expect((await cacheNames(page)).filter((n) => n.includes(idA!)).length, "cache names carry build A").toBeGreaterThan(0);

  try {
    await writeFile(SW_FILE, original.replaceAll(idA!, idB)); // build B is deployed
    // He switches back to the app. No navigation: only reg.update() on visibilitychange can find build B.
    await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
    const reload = page.getByRole("button", { name: /reload/i });
    await expect(reload).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(/new version/i)).toBeVisible();
    expect((await cacheNames(page)).some((n) => n.includes(idA!)), "build A keeps serving until he reloads").toBe(true);

    await Promise.all([page.waitForEvent("load"), reload.click()]);
    await boardLoaded(page);
    await expect.poll(async () => (await cacheNames(page)).filter((n) => n.startsWith("nflpi-")).every((n) => n.includes(idB)), { timeout: 15_000 }).toBe(true);
    expect((await cacheNames(page)).filter((n) => n.startsWith("nflpi-")).length).toBeGreaterThan(0);
  } finally {
    await writeFile(SW_FILE, original);
  }
});

test("P7 every tab opens offline: no chunk fails to load, by tapping and by opening each page directly", async ({ page, request }) => {
  const { games } = await board(request);
  const errors = chunkErrors(page);
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await workerControls(page);
  await weekPersisted(page);
  // A matchup he opened while online is saved with the rest; one he never opened has nothing to show.
  await page.goto(`/game/?id=${games[0].game_id}`);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
  await expect.poll(() => page.evaluate((id) => (localStorage.getItem("nflpi_cache") ?? "").includes(`"game","${id}"`), games[0].game_id), { timeout: 10_000 }).toBe(true);
  await page.goto("/");
  await boardLoaded(page);
  await goOffline(page);

  const tabs = page.getByRole("navigation", { name: "Primary" }).last();
  for (const [tab, heading] of [["Results", /results/i], ["Settings", /settings/i], ["Week", /week/i]] as const) {
    await tabs.getByRole("link", { name: tab }).click();
    await expect(page.getByRole("heading", { level: 1, name: heading }), `${tab} tab`).toBeVisible();
  }
  for (const url of ["/", "/sheet/", "/performance/", "/backtest/", "/settings/", `/game/?id=${games[0].game_id}`]) {
    await page.goto(url);
    await expect(page.getByRole("heading", { level: 1 }).first(), url).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: /offline/i }), url).toBeVisible();
  }
  expect(errors).toEqual([]);
});

for (const [granted, text, never] of [[true, /protected from/i, /may clear/i], [false, /may clear/i, /protected from/i]] as const) {
  test(`P9 storage (B5): the app asks the browser to keep its data and Settings says the answer (${granted ? "kept" : "not kept"})`, async ({ page }) => {
    await page.addInitScript((ok) => {
      const w = window as unknown as { __persistAsked: boolean };
      w.__persistAsked = false;
      Object.defineProperty(navigator, "storage", {
        configurable: true,
        value: { persisted: async () => false, persist: async () => ((w.__persistAsked = true), ok), estimate: async () => ({ usage: 0, quota: 0 }) },
      });
    }, granted);
    await signIn(page);
    await page.goto("/settings/");
    const offline = page.locator("#offline");
    await expect(offline.getByText(/storage/i).first()).toBeVisible();
    await expect(offline.getByText(text)).toBeVisible();
    await expect(offline.getByText(never)).toHaveCount(0);
    expect(await page.evaluate(() => (window as unknown as { __persistAsked: boolean }).__persistAsked)).toBe(true);
  });
}

test.describe(() => {
  test.use({ userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1" });
  test("P8 installed app, first open: standalone with empty storage shows the sign-in card, and it works", async ({ page }) => {
    // iOS reports an app opened from the Home Screen through navigator.standalone.
    await page.addInitScript(() => Object.defineProperty(navigator, "standalone", { configurable: true, value: true }));
    await page.goto("/");
    expect(await page.evaluate(() => (navigator as Navigator & { standalone?: boolean }).standalone)).toBe(true);
    expect(await page.evaluate(() => localStorage.length), "a new install starts with empty storage").toBe(0);
    const token = page.getByLabel(/token/i);
    await expect(token).toBeVisible();
    await token.fill(TOKEN);
    await page.getByRole("button", { name: /sign in/i }).click();
    await boardLoaded(page);
    await expect(page.getByText("Install on your iPhone")).toHaveCount(0);
  });

  test("P10 install hint: iPhone Safari shows how to add it to the Home Screen until dismissed", async ({ page }) => {
    await signIn(page);
    await page.goto("/");
    await boardLoaded(page);
    await expect(page.getByText("Install on your iPhone")).toBeVisible();
    await expect(page.getByText(/Add to Home Screen/)).toBeVisible();
    await page.getByRole("button", { name: "Dismiss" }).click();
    await expect(page.getByText("Install on your iPhone")).toHaveCount(0);
    await page.reload();
    await boardLoaded(page);
    await expect(page.getByText("Install on your iPhone")).toHaveCount(0);
  });
});
