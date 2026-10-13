import { expect, test, type APIRequestContext, type BrowserContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Step 7 gate (docs/gauntlet/logs/step-7.md): alerts on the phone. Production export at 393x852 with
 * the service worker on. Headless Chromium has no push service, so the device's subscription is a
 * stand-in kept in localStorage, and a push reaches the worker through the browser's debug protocol.
 * Real signing and encryption are proven on the server (backend/tests/test_alerts.py, N7).
 */
// channel "chromium" = the full browser in its new headless mode. The default headless shell refuses notifications.
test.use({ viewport: { width: 393, height: 852 }, hasTouch: true, channel: "chromium" });

const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
/** A key the server does not have: 65 bytes, base64url, like a real VAPID public key. */
const OTHER_KEY = `B${"A".repeat(86)}`;

type Meta = { current_season: number; current_week: number; push_public_key: string | null; push_subscriptions: number };
type Game = { game_id: string; kickoff_utc: string; away: { abbr: string }; home: { abbr: string } };
type Stored = { endpoint: string; key: string } | null;
/** The part of the worker's global scope these tests use (the project's type library has no worker types). */
type WorkerScope = { registration: ServiceWorkerRegistration; dispatchEvent: (e: Event) => boolean };
declare const NotificationEvent: new (type: string, init: { notification: Notification }) => Event;

async function meta(request: APIRequestContext): Promise<Meta> {
  const res = await request.get("/api/meta", { headers: AUTH });
  expect(res.ok()).toBeTruthy();
  return res.json() as Promise<Meta>;
}

const endpointFor = (name: string) => `https://fcm.googleapis.com/fcm/send/e2e-${name}`;
const forget = (request: APIRequestContext, endpoint: string) => request.delete(`/api/push/subscribe?endpoint=${encodeURIComponent(endpoint)}`, { headers: AUTH });
const stored = (page: Page) => page.evaluate(() => JSON.parse(localStorage.getItem("e2e_push") ?? "null") as Stored);

/**
 * Signed in, notifications allowed, and a stand-in for the push service: getSubscription, subscribe
 * and unsubscribe read and write localStorage "e2e_push". `seed` is what the device holds on first open.
 */
async function phone(context: BrowserContext, page: Page, seed: Stored) {
  await context.grantPermissions(["notifications"]);
  await page.addInitScript(
    ({ token, seed }) => {
      localStorage.setItem("nflpi_token", token);
      if (seed && !localStorage.getItem("e2e_push_seeded")) localStorage.setItem("e2e_push", JSON.stringify(seed));
      localStorage.setItem("e2e_push_seeded", "1");
      if (!("PushManager" in window)) return;
      const bytes = (b64: string) => Uint8Array.from(atob(b64.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
      const b64 = (v: BufferSource | string) => {
        if (typeof v === "string") return v;
        const u = v instanceof ArrayBuffer ? new Uint8Array(v) : new Uint8Array(v.buffer, v.byteOffset, v.byteLength);
        return btoa(String.fromCharCode(...u)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
      };
      const read = () => JSON.parse(localStorage.getItem("e2e_push") ?? "null") as { endpoint: string; key: string } | null;
      const make = (s: { endpoint: string; key: string } | null) =>
        s && {
          endpoint: s.endpoint,
          expirationTime: null,
          options: { userVisibleOnly: true, applicationServerKey: bytes(s.key).buffer },
          getKey: () => null,
          toJSON: () => ({ endpoint: s.endpoint, expirationTime: null, keys: { p256dh: `B${"E".repeat(86)}`, auth: "e2e-auth-0123456789abc" } }),
          unsubscribe: async () => {
            if (read()?.endpoint === s.endpoint) localStorage.removeItem("e2e_push");
            return true;
          },
        };
      PushManager.prototype.getSubscription = (async () => make(read())) as unknown as PushManager["getSubscription"];
      PushManager.prototype.subscribe = (async (o?: PushSubscriptionOptionsInit) => {
        const s = { endpoint: `https://fcm.googleapis.com/fcm/send/e2e-new-${Date.now()}`, key: b64(o?.applicationServerKey ?? "") };
        localStorage.setItem("e2e_push", JSON.stringify(s));
        return make(s);
      }) as unknown as PushManager["subscribe"];
    },
    { token: TOKEN, seed },
  );
}

async function workerControls(page: Page) {
  await expect.poll(() => page.evaluate(() => !!navigator.serviceWorker.controller), { timeout: 20_000 }).toBe(true);
}

const subscribePost = (page: Page) => page.waitForRequest((r) => r.method() === "POST" && new URL(r.url()).pathname === "/api/push/subscribe", { timeout: 15_000 });

test("A1 opening the app with alerts on re-sends the subscription; a row the server lost is re-created", async ({ page, context, request }) => {
  const m = await meta(request);
  expect(m.push_public_key, "the test server has push keys").toBeTruthy();
  const endpoint = endpointFor("a1");
  await forget(request, endpoint);
  const before = (await meta(request)).push_subscriptions;
  await phone(context, page, { endpoint, key: m.push_public_key! });
  try {
    const first = subscribePost(page);
    await page.goto("/");
    expect((await first).postDataJSON(), "the app sent this device's subscription on open").toMatchObject({ endpoint });
    await expect.poll(async () => (await meta(request)).push_subscriptions, { message: "the server holds it" }).toBe(before + 1);

    const again = subscribePost(page);
    await page.reload();
    expect((await again).postDataJSON(), "sent again on the next open, though the server already had it").toMatchObject({ endpoint });

    expect((await forget(request, endpoint)).ok()).toBeTruthy();
    expect((await meta(request)).push_subscriptions).toBe(before);
    await page.reload();
    await expect.poll(async () => (await meta(request)).push_subscriptions, { message: "the next open re-created the row" }).toBe(before + 1);
    expect((await stored(page))?.endpoint, "the device kept its subscription").toBe(endpoint);
  } finally {
    await forget(request, endpoint);
  }
});

test("A1b with alerts off, opening the app sends no subscription", async ({ page, context, request }) => {
  const before = (await meta(request)).push_subscriptions;
  await phone(context, page, null);
  let sent = 0;
  page.on("request", (r) => r.method() === "POST" && new URL(r.url()).pathname === "/api/push/subscribe" && sent++);
  await page.goto("/");
  await expect(page.getByRole("link", { name: /^Open matchup:/ }).first()).toBeVisible({ timeout: 15_000 });
  await page.waitForTimeout(2_000);
  expect(sent).toBe(0);
  expect((await meta(request)).push_subscriptions).toBe(before);
});

test("A2 when the server's key changed, the app subscribes again with the new key and drops the old address", async ({ page, context, request }) => {
  const m = await meta(request);
  expect(m.push_public_key).toBeTruthy();
  const old = endpointFor("a2-old");
  await forget(request, old);
  const before = (await meta(request)).push_subscriptions;
  const put = await request.post("/api/push/subscribe", { headers: AUTH, data: { endpoint: old, keys: { p256dh: `B${"E".repeat(86)}`, auth: "e2e-auth-0123456789abc" } } });
  expect(put.ok()).toBeTruthy();
  await phone(context, page, { endpoint: old, key: OTHER_KEY });
  let fresh: string | undefined;
  try {
    const dropped = page.waitForRequest((r) => r.method() === "DELETE" && r.url().includes(encodeURIComponent(old)), { timeout: 15_000 });
    await page.goto("/");
    await expect.poll(async () => (await stored(page))?.key, { message: "subscribed with the server's key" }).toBe(m.push_public_key);
    fresh = (await stored(page))?.endpoint;
    expect(fresh).not.toBe(old);
    await dropped;
    await expect.poll(async () => (await meta(request)).push_subscriptions, { message: "the new address replaced the old one" }).toBe(before + 1);
  } finally {
    await forget(request, old);
    if (fresh) await forget(request, fresh);
  }
});

test("A3 a push that reaches the phone shows the alert, and tapping it opens the game", async ({ page, context, request }) => {
  const m = await meta(request);
  const week = (await (await request.get(`/api/weeks/${m.current_season}/${m.current_week}`, { headers: AUTH })).json()) as { games: Game[] };
  const g = week.games[0];
  const alert = { title: `Pick flipped: ${g.away.abbr} @ ${g.home.abbr}`, body: `Now ${g.home.abbr} 58% (was ${g.away.abbr} 53%).`, url: `/game/?id=${g.game_id}` };
  await phone(context, page, null);
  await page.goto("/");
  await workerControls(page);
  const worker = context.serviceWorkers()[0] ?? (await context.waitForEvent("serviceworker"));

  const cdp = await context.newCDPSession(page);
  const registered = new Promise<string>((resolve) =>
    cdp.on("ServiceWorker.workerRegistrationUpdated", (e) => {
      const r = e.registrations.find((x) => !x.isDeleted);
      if (r) resolve(r.registrationId);
    }),
  );
  await cdp.send("ServiceWorker.enable");
  await cdp.send("ServiceWorker.deliverPushMessage", { origin: new URL(page.url()).origin, registrationId: await registered, data: JSON.stringify(alert) });

  const shown = () => worker.evaluate(async () => (await (self as unknown as WorkerScope).registration.getNotifications()).map((n) => ({ title: n.title, body: n.body, url: (n.data as { url: string }).url })));
  await expect.poll(shown, { message: "the worker showed the alert" }).toEqual([alert]);

  await worker.evaluate(async () => {
    const sw = self as unknown as WorkerScope;
    const [notification] = await sw.registration.getNotifications();
    sw.dispatchEvent(new NotificationEvent("notificationclick", { notification }));
  });
  await expect(page, "tapping the alert opened the game").toHaveURL(new RegExp(`/game/\\?id=${g.game_id}$`), { timeout: 10_000 });
  await expect.poll(shown, { message: "the alert closed" }).toEqual([]);
});

test("A4 Settings: Send test alert says what happened in words; the reminder reads as one per game day", async ({ page, context, request }) => {
  const m = await meta(request);
  expect(m.push_public_key).toBeTruthy();
  const endpoint = endpointFor("a4");
  await phone(context, page, { endpoint, key: m.push_public_key! });
  const reply = { configured: true, devices: 1, delivered: 1, results: [{ host: "fcm.googleapis.com", ok: true, status: 201, error: null as string | null }] };
  let calls = 0;
  // The reply is fixed here: the real route, against a real push exchange, is tests N6 and N7 on the server.
  await page.route("**/api/push/test", async (route) => {
    calls++;
    expect(route.request().method()).toBe("POST");
    expect(route.request().headers().authorization).toBe(`Bearer ${TOKEN}`);
    await route.fulfill({ json: reply });
  });
  try {
    await page.goto("/settings/#alerts");
    const section = page.locator("#alerts");
    await expect(section.getByText("Alerts on")).toBeVisible({ timeout: 15_000 });

    await expect(section.getByText("Game day reminder")).toBeVisible();
    await expect(section.getByText("One alert on each game day, before that day's first kickoff.")).toBeVisible();
    await expect(section).not.toContainText("No pick yet");
    await expect(section.getByLabel("Remind me").locator("option")).toHaveText(["Off", "30 minutes before", "1 hour before", "3 hours before"]);

    const send = section.getByRole("button", { name: "Send test alert" });
    await send.click();
    const result = section.getByRole("status");
    await expect(result).toHaveText("Delivered to 1 device.");
    expect(calls).toBe(1);

    Object.assign(reply, { delivered: 0, results: [{ host: "fcm.googleapis.com", ok: false, status: 403, error: "The push service refused the alert." }] });
    await send.click();
    await expect(result).toContainText("Not delivered.");
    await expect(result).toContainText("fcm.googleapis.com: The push service refused the alert. (403)");

    Object.assign(reply, { devices: 0, delivered: 0, results: [] });
    await send.click();
    await expect(result).toHaveText("The server has no device to send to. Turn alerts off and on again.");

    await page.unroute("**/api/push/test");
    await page.route("**/api/push/test", (route) => route.abort());
    await send.click();
    await expect(section.getByRole("alert")).toContainText("Could not send the test alert.");
  } finally {
    await forget(request, endpoint);
  }
});

test("A4b with alerts off there is no Send test alert button", async ({ page, context }) => {
  await phone(context, page, null);
  await page.goto("/settings/#alerts");
  const section = page.locator("#alerts");
  await expect(section.getByRole("button", { name: "Turn on alerts" })).toBeVisible({ timeout: 15_000 });
  await expect(section.getByRole("button", { name: "Send test alert" })).toHaveCount(0);
});

for (const scheme of ["dark", "light"] as const) {
  test(`A5 accessibility (${scheme}): no serious or critical axe issues on Settings with a test alert result showing`, async ({ page, context, request }) => {
    const m = await meta(request);
    const endpoint = endpointFor(`a5-${scheme}`);
    await page.emulateMedia({ colorScheme: scheme });
    await phone(context, page, { endpoint, key: m.push_public_key! });
    await page.route("**/api/push/test", (route) => route.fulfill({ json: { configured: true, devices: 1, delivered: 1, results: [{ host: "fcm.googleapis.com", ok: true, status: 201, error: null }] } }));
    try {
      await page.goto("/settings/#alerts");
      const section = page.locator("#alerts");
      await section.getByRole("button", { name: "Send test alert" }).click();
      await expect(section.getByRole("status")).toHaveText("Delivered to 1 device.");
      await page.waitForLoadState("networkidle");
      const { violations } = await new AxeBuilder({ page }).analyze();
      const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => `${v.id}: ${v.nodes.length}`)).toEqual([]);
    } finally {
      await forget(request, endpoint);
    }
  });
}
