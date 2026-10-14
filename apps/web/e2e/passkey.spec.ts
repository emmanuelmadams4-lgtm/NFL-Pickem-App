import { expect, test, type BrowserContext, type CDPSession, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Step 10 web half (docs/gauntlet/logs/step-10-web.md, K1-K11): passkey sign-in and the passkey list, on the real
 * passkey API with Chrome's virtual authenticator. The test server runs with PASSKEY_RP_ID=localhost, so these tests
 * open http://localhost:8123 (a relying-party id cannot be an IP address). Whether passkeys are on is read from
 * /api/health, which every test rewrites, so the tests do not depend on the server field (SEAM in the log).
 */
const ORIGIN = "http://localhost:8123";
const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
const STORE = "nflpi_token";

// One worker, in file order (playwright.config.ts): the tests share the server's passkey table; afterEach empties it.
test.use({ viewport: { width: 393, height: 852 }, hasTouch: true });

type Row = { id: number; label: string | null; created_at: string; last_used_at: string | null };

async function authenticator(context: BrowserContext, page: Page, verified = true): Promise<{ cdp: CDPSession; id: string }> {
  const cdp = await context.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  const { authenticatorId } = await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: verified, automaticPresenceSimulation: true },
  });
  return { cdp, id: authenticatorId };
}

/** Rewrite /api/health so the app sees passkeys on or off (undefined = the field is missing). */
async function passkeys(page: Page, on: boolean | undefined) {
  await page.route("**/api/health", async (route) => {
    try {
      const res = await route.fetch();
      const body = await res.json();
      if (on === undefined) delete body.passkeys;
      else body.passkeys = on;
      await route.fulfill({ response: res, json: body });
    } catch {
      // the page closed with the request in flight
    }
  });
}

async function signedIn(page: Page, value = TOKEN) {
  // once per tab, so a later sign-out in the test is not undone by the next page load
  await page.addInitScript(([k, v]) => {
    if (sessionStorage.getItem("e2e_seeded")) return;
    sessionStorage.setItem("e2e_seeded", "1");
    localStorage.setItem(k, v);
  }, [STORE, value]);
}

async function rows(page: Page): Promise<Row[]> {
  const res = await page.request.get(`${ORIGIN}/api/passkey`, { headers: AUTH });
  expect(res.ok()).toBeTruthy();
  return (await res.json()).passkeys as Row[];
}

const card = (page: Page) => page.locator("form[aria-labelledby='signin-title']");
const section = (page: Page) => page.locator("#passkeys");
const stored = (page: Page) => page.evaluate((k) => localStorage.getItem(k), STORE);

/** Signed in with the token: add a passkey named `name` from Settings, through the real ceremony. */
async function addFromSettings(page: Page, name: string) {
  await page.goto(`${ORIGIN}/settings`);
  await expect(section(page).getByRole("heading", { name: "Passkeys" })).toBeVisible({ timeout: 15_000 });
  await section(page).getByLabel("Passkey name (optional)").fill(name);
  await section(page).getByRole("button", { name: "Add a passkey" }).click();
  await expect(section(page).getByRole("listitem").filter({ hasText: name })).toBeVisible();
}

/** From the sign-in card, sign in with the passkey on the virtual authenticator. */
async function passkeySignIn(page: Page) {
  await card(page).getByRole("button", { name: "Sign in with a passkey" }).click();
  await expect(card(page)).toBeHidden({ timeout: 15_000 });
}

test.afterEach(async ({ page }) => {
  for (const r of await rows(page)) await page.request.delete(`${ORIGIN}/api/passkey/${r.id}`, { headers: AUTH });
});

test("K1 passkeys off: the sign-in card has no passkey button, with the flag false or missing", async ({ page }) => {
  for (const on of [false, undefined]) {
    await page.unrouteAll({ behavior: "ignoreErrors" });
    await passkeys(page, on);
    await page.goto(`${ORIGIN}/`);
    await expect(card(page).getByLabel("Access token")).toBeVisible({ timeout: 15_000 });
    await expect(card(page).getByRole("button", { name: /passkey/i })).toHaveCount(0);
  }
});

test("K2 K4 K5 K8 K10 add with the token, sign out, sign in with the passkey, it is sent and listed, sign out ends it", async ({ context, page }) => {
  await authenticator(context, page);
  await passkeys(page, true);
  await signedIn(page);
  await addFromSettings(page, "Test phone");
  const row = section(page).getByRole("listitem").filter({ hasText: "Test phone" });
  await expect(row).toContainText("Never used");
  expect((await rows(page)).map((r) => r.label)).toEqual(["Test phone"]);

  // K8: sign-out with the app token makes no passkey call
  const calls: string[] = [];
  page.on("request", (r) => calls.push(`${r.method()} ${new URL(r.url()).pathname}`));
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await expect(card(page)).toBeVisible({ timeout: 15_000 });
  expect(calls).not.toContain("POST /api/passkey/signout");

  // K2, K10: sign in with the passkey; the value is stored and sent like the token
  await expect(card(page).getByLabel("Access token")).toBeVisible();
  const sent = page.waitForRequest((r) => r.url().includes("/api/meta") && (r.headers()["authorization"] ?? "").startsWith("Bearer pks_"));
  await passkeySignIn(page);
  await sent;
  const value = await stored(page);
  expect(value).toMatch(/^pks_/);

  // K4: the row now says when it was last used
  await page.goto(`${ORIGIN}/settings`);
  await expect(section(page).getByRole("listitem").filter({ hasText: "Test phone" })).toContainText("Last used", { timeout: 15_000 });

  // K8: sign-out with a passkey session calls the server first, and the old value is refused afterwards
  const signout = page.waitForResponse((r) => r.url().endsWith("/api/passkey/signout") && r.request().method() === "POST");
  await page.getByRole("button", { name: "Sign out" }).first().click();
  expect((await signout).status()).toBe(204);
  await expect(card(page)).toBeVisible({ timeout: 15_000 });
  expect(await stored(page)).toBeNull();
  const after = await page.request.get(`${ORIGIN}/api/meta`, { headers: { Authorization: `Bearer ${value}` } });
  expect(after.status()).toBe(401);
});

test("K5 a passkey session cannot add a passkey: the 403 is explained and nothing is added", async ({ context, page }) => {
  await authenticator(context, page);
  await passkeys(page, true);
  await signedIn(page);
  await addFromSettings(page, "First");
  await page.evaluate((k) => localStorage.removeItem(k), STORE);
  await page.goto(`${ORIGIN}/`);
  await passkeySignIn(page);
  await page.goto(`${ORIGIN}/settings`);
  await expect(section(page).getByRole("heading", { name: "Passkeys" })).toBeVisible({ timeout: 15_000 });
  await section(page).getByRole("button", { name: "Add a passkey" }).click();
  await expect(section(page).getByRole("alert")).toContainText("Adding a passkey needs the access token");
  expect(await rows(page)).toHaveLength(1);
});

test("K6 K9 removing the passkey this device signed in with ends its session and returns to the sign-in card", async ({ context, page }) => {
  await authenticator(context, page);
  await passkeys(page, true);
  await signedIn(page);
  await addFromSettings(page, "This phone");
  await page.evaluate((k) => localStorage.removeItem(k), STORE);
  await page.goto(`${ORIGIN}/`);
  await passkeySignIn(page);
  await page.goto(`${ORIGIN}/settings`);
  const row = section(page).getByRole("listitem").filter({ hasText: "This phone" });
  await row.getByRole("button", { name: "Remove" }).click();
  await row.getByRole("button", { name: "Confirm remove" }).click();
  await expect(card(page)).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Your passkey sign-in has ended. Sign in again.")).toBeVisible();
  expect(await rows(page)).toHaveLength(0);
});

test("K6 removing a passkey with the token: two steps, the row goes, the app stays signed in", async ({ context, page }) => {
  await authenticator(context, page);
  await passkeys(page, true);
  await signedIn(page);
  await addFromSettings(page, "Old laptop");
  const row = section(page).getByRole("listitem").filter({ hasText: "Old laptop" });
  await row.getByRole("button", { name: "Remove" }).click();
  expect(await rows(page)).toHaveLength(1); // the first press only asks
  await row.getByRole("button", { name: "Confirm remove" }).click();
  await expect(section(page).getByRole("listitem").filter({ hasText: "Old laptop" })).toHaveCount(0);
  expect(await rows(page)).toHaveLength(0);
  await expect(card(page)).toHaveCount(0);
});

test("K3 sign-in refusals are words on the card and the token form keeps working", async ({ context, page }) => {
  // a passkey on this device first (with the token), so the server refusals below are reached after the prompt
  const a = await authenticator(context, page);
  await passkeys(page, true);
  await signedIn(page);
  await addFromSettings(page, "Refusals");
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await expect(card(page)).toBeVisible({ timeout: 15_000 });

  await a.cdp.send("WebAuthn.setUserVerified", { authenticatorId: a.id, isUserVerified: false }); // Face ID refused or cancelled
  await card(page).getByRole("button", { name: "Sign in with a passkey" }).click();
  await expect(card(page).getByRole("alert")).toContainText("No passkey was used.", { timeout: 15_000 });

  await a.cdp.send("WebAuthn.setUserVerified", { authenticatorId: a.id, isUserVerified: true });
  for (const [path, status, detail, shown] of [
    ["finish", 401, "Passkey sign-in failed", "Passkey sign-in failed."],
    ["begin", 429, "Too many attempts, try again in a minute", "Too many attempts, try again in a minute"],
    ["begin", 503, "Passkey sign-in is not configured", "Passkey sign-in is not configured"],
  ] as const) {
    await page.route(`**/api/passkey/signin/${path}`, (route) => route.fulfill({ status, json: { detail } }));
    await card(page).getByRole("button", { name: "Sign in with a passkey" }).click();
    await expect(card(page).getByRole("alert")).toContainText(shown);
    await page.unroute(`**/api/passkey/signin/${path}`);
  }
  await card(page).getByLabel("Access token").fill(TOKEN);
  await card(page).getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(card(page)).toBeHidden({ timeout: 15_000 });
});

test("K3 a browser without the passkey JSON helpers says so and keeps the token form", async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(PublicKeyCredential, "parseRequestOptionsFromJSON", { value: undefined, configurable: true });
  });
  await passkeys(page, true);
  await page.goto(`${ORIGIN}/`);
  await card(page).getByRole("button", { name: "Sign in with a passkey" }).click();
  await expect(card(page).getByRole("alert")).toContainText("This browser cannot use a passkey here. Use your access token.");
  await expect(card(page).getByLabel("Access token")).toBeEnabled();
});

test("K5 the name stops at 64 characters; refusals while adding are words", async ({ context, page }) => {
  const a = await authenticator(context, page, false);
  await passkeys(page, true);
  await signedIn(page);
  await page.goto(`${ORIGIN}/settings`);
  const name = section(page).getByLabel("Passkey name (optional)");
  await name.fill("x".repeat(70));
  expect(await name.inputValue()).toHaveLength(64);
  await name.fill("Kitchen iPad");
  await section(page).getByRole("button", { name: "Add a passkey" }).click();
  await expect(section(page).getByRole("alert")).toContainText("No passkey was added.", { timeout: 15_000 });

  await a.cdp.send("WebAuthn.setUserVerified", { authenticatorId: a.id, isUserVerified: true });
  await page.route("**/api/passkey/register/finish", (route) =>
    route.fulfill({ status: 409, json: { detail: "Passkey limit reached (10). Remove one first." } }),
  );
  await section(page).getByRole("button", { name: "Add a passkey" }).click();
  await expect(section(page).getByRole("alert")).toContainText("Passkey limit reached (10). Remove one first.");
  expect(await rows(page)).toHaveLength(0);
});

test("K5 a second passkey from the same device is refused in plain words, not the browser's own text", async ({ context, page }) => {
  await authenticator(context, page);
  await passkeys(page, true);
  await signedIn(page);
  await addFromSettings(page, "Only one");
  await section(page).getByRole("button", { name: "Add a passkey" }).click();
  await expect(section(page).getByRole("alert")).toHaveText("This device already has a passkey for this app.");
  expect(await rows(page)).toHaveLength(1);
});

test("K7 passkeys off: Settings still lists passkeys (so one can be removed) and offers no add", async ({ context, page }) => {
  await authenticator(context, page);
  await passkeys(page, true);
  await signedIn(page);
  await addFromSettings(page, "Spare");
  await page.unrouteAll({ behavior: "ignoreErrors" });
  await passkeys(page, false);
  await page.goto(`${ORIGIN}/settings`);
  await expect(section(page).getByRole("listitem").filter({ hasText: "Spare" })).toBeVisible({ timeout: 15_000 });
  await expect(section(page).getByRole("button", { name: "Add a passkey" })).toHaveCount(0);
  await expect(section(page).getByRole("listitem").filter({ hasText: "Spare" }).getByRole("button", { name: "Remove" })).toBeVisible();
});

for (const width of [393, 320]) {
  test(`K11 at ${width} px: no serious axe finding and no sideways scroll on the card and the Passkeys section`, async ({ context, page }) => {
    await page.setViewportSize({ width, height: 852 });
    await authenticator(context, page);
    await passkeys(page, true);
    await page.goto(`${ORIGIN}/`);
    await expect(card(page).getByRole("button", { name: "Sign in with a passkey" })).toBeVisible({ timeout: 15_000 });
    const scroll = () => page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    const serious = async () =>
      (await new AxeBuilder({ page }).analyze()).violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id);
    expect(await serious()).toEqual([]);
    expect(await scroll()).toBeLessThanOrEqual(0);

    await signedIn(page);
    await addFromSettings(page, "A long passkey name for a narrow phone screen, sixty-four chars");
    await section(page).scrollIntoViewIfNeeded();
    expect(await new AxeBuilder({ page }).include("#passkeys").analyze().then((r) => r.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id))).toEqual([]);
    expect(await scroll()).toBeLessThanOrEqual(0);
  });
}
