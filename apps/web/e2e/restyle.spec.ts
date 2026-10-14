import { readFile } from "node:fs/promises";
import { expect, test, type APIRequestContext, type Page, type Route } from "@playwright/test";

/**
 * Step 3 gate (docs/gauntlet/logs/step-3.md): reference 06 look and layout (owner D39, D40), owner's app icon (D41),
 * carry-overs R1-R6 from step 2. Same seeded server as step2.spec.ts.
 */
const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
const BRAND = "../../docs/design/brand/app-icon";

type Team = { abbr: string; name: string };
type Prediction = { pick: string; home_win_prob: number; kind: string; change_note: string | null };
type Game = { game_id: string; kickoff_utc: string; status: string; locked: boolean; time_tbd: boolean; away: Team; home: Team; prediction: Prediction | null; roof: string | null };
type Meta = { current_season: number; current_week: number; server_time: string };

async function api<T>(request: APIRequestContext, path: string): Promise<T> {
  const res = await request.get(`/api${path}`, { headers: AUTH });
  expect(res.ok(), path).toBeTruthy();
  return res.json() as Promise<T>;
}

/** The server has no pick for this game, so no test leaves a pick behind for the next one. */
async function expectServerCleared(request: APIRequestContext, g: Game) {
  await expect.poll(async () => (await api<{ my_pick: string | null }>(request, `/games/${g.game_id}`)).my_pick, `${g.game_id} pick cleared on the server`).toBeNull();
}

async function board(request: APIRequestContext) {
  const meta = await api<Meta>(request, "/meta");
  const week = await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/${meta.current_week}`);
  const open = week.games.filter((g) => !g.time_tbd && !g.locked && g.status === "scheduled").sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc));
  return { meta, games: week.games, open };
}

const signIn = (page: Page) => page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
const card = (page: Page, g: Game) => page.getByTestId("game-card").filter({ has: page.getByRole("link", { name: `Open matchup: ${g.away.name} at ${g.home.name}` }) });
const cardsLoaded = (page: Page) => expect(page.getByTestId("game-card").first()).toBeVisible();

/** Rewrite one game inside a JSON API response. */
async function patchGames(page: Page, pattern: string, edit: (g: Game) => void) {
  await page.route(pattern, async (route: Route) => {
    const res = await route.fetch();
    const body = await res.json();
    (body.games ?? [body]).forEach(edit);
    await route.fulfill({ response: res, json: body });
  });
}

test("S1 week board: one card per game with both teams and a VS badge", async ({ page, request }) => {
  const { games } = await board(request);
  await signIn(page);
  await page.goto("/");
  await cardsLoaded(page);
  await expect(page.getByTestId("game-card")).toHaveCount(games.length);
  for (const g of games) {
    const c = card(page, g);
    await expect(c, g.game_id).toContainText(g.away.abbr);
    await expect(c, g.game_id).toContainText(g.home.abbr);
    await expect(c.getByText("VS", { exact: true }), g.game_id).toBeVisible();
  }
});

test("S2 tokens and type: near-black page, lime accent, condensed uppercase titles", async ({ page }) => {
  await signIn(page);
  await page.goto("/");
  await cardsLoaded(page);
  const css = await page.evaluate(() => {
    const probe = document.body.appendChild(document.createElement("i"));
    const read = (v: string) => ((probe.style.color = `var(${v})`), getComputedStyle(probe).color);
    const h1 = getComputedStyle(document.querySelector("h1")!);
    const out = { bg: read("--bg"), accent: read("--accent"), ink: read("--accent-ink"), font: h1.fontFamily, transform: h1.textTransform };
    probe.remove();
    return out;
  });
  expect(css.bg).toBe("rgb(10, 10, 10)");
  expect(css.accent).toBe("rgb(198, 241, 53)");
  expect(css.ink).toBe("rgb(10, 10, 10)");
  expect(css.font).toMatch(/^"?Barlow Condensed/);
  expect(css.transform).toBe("uppercase");
  expect(await page.evaluate(() => document.fonts.check('700 48px "Barlow Condensed"') && [...document.fonts].some((f) => f.family.includes("Barlow Condensed") && f.status === "loaded"))).toBe(true);
  const activeNav = page.getByRole("navigation", { name: "Primary" }).locator('[aria-current="page"]').first();
  expect(await activeNav.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(198, 241, 53)");
});

test("S3 phone: floating pill tab bar, active tab is a labeled pill, no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 852 });
  await signIn(page);
  await page.goto("/");
  await cardsLoaded(page);
  const nav = page.getByRole("navigation", { name: "Primary" });
  await expect(nav).toBeVisible();
  expect(await nav.evaluate((el) => getComputedStyle(el).position)).toBe("fixed");
  const active = nav.locator('[aria-current="page"]');
  await expect(active).toHaveCount(1);
  expect((await active.innerText()).trim().length).toBeGreaterThan(0);
  for (const other of await nav.locator('a:not([aria-current="page"])').all()) {
    expect((await other.innerText()).trim(), "inactive tabs are icon-only").toBe("");
    expect(await other.getAttribute("aria-label"), "icon-only tabs keep a name").toBeTruthy();
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("S4 app icon and manifest use the owner's P logo", async ({ request }) => {
  for (const name of ["icon-512.png", "icon-192.png", "apple-touch-icon.png", "maskable-512.png"]) {
    const served = await (await request.get(`/icons/${name}`)).body();
    expect(Buffer.compare(served, await readFile(`${BRAND}/${name}`)), name).toBe(0);
  }
  const manifest = await (await request.get("/manifest.webmanifest")).json();
  expect(manifest.theme_color.toLowerCase()).toBe("#0a0a0a");
  expect(manifest.background_color.toLowerCase()).toBe("#0a0a0a");
});

test("S5 matchup: split win-chance tiles, the model's side labeled, pill section tabs jump to sections", async ({ page, request }) => {
  const { open } = await board(request);
  const g = open[0];
  await signIn(page);
  await page.goto(`/game/?id=${g.game_id}`);
  const split = page.getByTestId("win-split");
  await expect(split).toBeVisible();
  const text = await split.innerText();
  const pcts = [...text.matchAll(/(\d+)%/g)].map((m) => Number(m[1]));
  expect(pcts.length, text).toBeGreaterThanOrEqual(2);
  expect(Math.abs(pcts[0] + pcts[1] - 100), text).toBeLessThanOrEqual(1);
  await expect(split).toContainText(g.away.abbr);
  await expect(split).toContainText(g.home.abbr);
  await expect(split).toContainText("Model pick");
  const tabs = page.getByRole("navigation", { name: "Sections" });
  for (const name of ["Factors", "Teams", "Injuries", "Conditions", "Market", "AI", "History", "Meetings"]) await expect(tabs.getByRole("link", { name })).toBeVisible();
  await tabs.getByRole("link", { name: "Market" }).click();
  await expect(page.locator("#market")).toBeInViewport();
});

test.describe(() => {
  test.use({ serviceWorkers: "block" }); // rewrites API responses with page.route
test("R1 what changed shows on the game card and in the pick panel", async ({ page, request }) => {
  const { open } = await board(request);
  const g = open[0];
  const note = "Pick flipped after a QB change (test note)";
  const edit = (x: Game) => {
    if (x.game_id === g.game_id && x.prediction) x.prediction.change_note = note;
  };
  await patchGames(page, "**/api/weeks/**", edit);
  await patchGames(page, `**/api/games/${g.game_id}`, edit);
  await signIn(page);
  await page.goto("/");
  await cardsLoaded(page);
  await expect(card(page, g)).toContainText(note);
  await page.goto(`/game/?id=${g.game_id}`);
  await expect(page.locator("aside")).toContainText(note);
});});


test("R2 a pick against the model shows 'Differs from model' on the card", async ({ page, request }) => {
  const { open } = await board(request);
  const g = open.find((x) => x.prediction)!;
  const against = g.prediction!.pick === g.home.abbr ? g.away : g.home;
  await signIn(page);
  await page.goto("/");
  await cardsLoaded(page);
  const c = card(page, g);
  await expect(c).not.toContainText("Differs from model");
  await c.getByRole("button", { name: new RegExp(`^Pick ${against.name}`) }).click();
  await expect(c).toContainText("Differs from model");
  await c.getByRole("button", { name: new RegExp(`^${against.name} picked`) }).click();
  await expect(c).not.toContainText("Differs from model");
  await expectServerCleared(request, g);
});

test("R3 weather outage: the matchup says the weather source is down, not 'No forecast yet'", async ({ page, request }) => {
  const { open } = await board(request);
  await signIn(page);
  await page.goto(`/game/?id=${open[0].game_id}`);
  const conditions = page.locator("#conditions");
  await expect(conditions).toContainText(/weather (source|data) (is )?(down|unavailable|unreachable)/i);
  await expect(conditions).not.toContainText("No forecast yet");
});

test("R4 backfill never reads as live: Week KPI, Results table, chart labels, matchup panel and history", async ({ page, request }) => {
  const { meta } = await board(request);
  const week1 = (await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/1`)).games;
  await signIn(page);
  await page.goto(`/?season=${meta.current_season}&week=1`);
  await cardsLoaded(page);
  await expect(page.getByTestId("kpi-model")).toContainText("–");
  await page.goto("/performance/");
  const row1 = page.locator("tr").filter({ has: page.locator("th[scope=row]", { hasText: /^1$/ }) });
  await expect(row1).toContainText("–");
  await expect(row1).toContainText("backfilled");
  const weekly = page.getByRole("img", { name: /weekly accuracy/i });
  await expect(weekly).toHaveAttribute("aria-label", /W1: [^;]*model live –[^;]*model backfilled \d+%/i);
  const calibration = page.getByRole("img", { name: /calibration/i }).first();
  await expect(calibration).toHaveAttribute("aria-label", /live: 0 games[^]*backfilled: \d+ games/i);
  await page.goto(`/game/?id=${week1[0].game_id}`);
  await expect(page.locator("aside")).toContainText("Backfilled");
  await expect(page.locator("aside")).not.toContainText(/\bLive\b/, { useInnerText: true });
  await expect(page.locator("#history")).not.toContainText(/\bLive\b/, { useInnerText: true });
});

test.describe(() => {
  test.use({ serviceWorkers: "block" }); // rewrites API responses with page.route
test("R6 the client lock follows the server rule: a TBD or postponed game stays open after its placeholder time", async ({ page, request }) => {
  const { open } = await board(request);
  const [tbd, postponed] = open;
  const past = new Date(Date.now() - 3_600_000).toISOString();
  await patchGames(page, "**/api/weeks/**", (g) => {
    if (g.game_id === tbd.game_id) Object.assign(g, { kickoff_utc: past, time_tbd: true, locked: false });
    if (g.game_id === postponed.game_id) Object.assign(g, { kickoff_utc: past, status: "postponed", locked: false });
  });
  await signIn(page);
  await page.goto("/");
  await cardsLoaded(page);
  for (const g of [tbd, postponed]) {
    await expect(card(page, g).getByRole("button", { name: new RegExp(`^Pick ${g.home.name}`) }), g.game_id).toBeEnabled();
  }
});});


const LIME = "rgb(198, 241, 53)";

test.describe(() => {
test.use({ serviceWorkers: "block" }); // F1 routes logo images with page.route
test("F1 smallest phone (320px): no screen scrolls sideways", async ({ page, request }) => {
  const { meta, open } = await board(request);
  const finals = (await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/1`)).games;
  await page.setViewportSize({ width: 320, height: 700 });
  await page.route(/example\.test/, (route) => route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="#0b6"/></svg>' }));
  await signIn(page);
  for (const path of ["/", `/game/?id=${open[0].game_id}`, ...finals.map((g) => `/game/?id=${g.game_id}`), "/performance/", "/backtest/", "/settings/"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    expect(await page.evaluate(() => document.documentElement.scrollWidth), path).toBeLessThanOrEqual(320);
  }
});});


test("F2 matchup: a pick against the model says 'Differs from model' in the pick panel", async ({ page, request }) => {
  const { open } = await board(request);
  const g = open.find((x) => x.prediction)!;
  const against = g.prediction!.pick === g.home.abbr ? g.away : g.home;
  await signIn(page);
  await page.goto(`/game/?id=${g.game_id}`);
  const panel = page.locator("aside");
  await panel.getByRole("button", { name: new RegExp(`^Pick ${against.name}`) }).click();
  await expect(panel).toContainText("Differs from model");
  await panel.getByRole("button", { name: new RegExp(`^${against.name} picked`) }).click();
  await expect(panel).not.toContainText("Differs from model");
  await expectServerCleared(request, g);
});

test("F3 win split: lime is mine, never the model's tile; no check mark on it; backfill says so", async ({ page, request }) => {
  const { meta, open } = await board(request);
  const final = (await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/1`)).games[0];
  await signIn(page);
  for (const id of [open[0].game_id, final.game_id]) {
    await page.goto(`/game/?id=${id}`);
    const tile = page.getByTestId("win-tile-model");
    await expect(tile).toContainText("Model pick");
    const paint = await tile.evaluate((el) =>
      [el, ...el.querySelectorAll("*")].flatMap((n) => {
        const c = getComputedStyle(n);
        return [c.backgroundColor, c.color, c.borderTopColor, c.borderRightColor, c.borderBottomColor, c.borderLeftColor];
      }),
    );
    expect(paint, id).not.toContain(LIME);
    await expect(tile).not.toContainText(/[✓✔]/);
    await expect(tile.locator("svg"), "no check icon on the model tile").toHaveCount(0);
  }
  await expect(page.getByTestId("win-split")).toContainText("Backfilled");
});

test("F4 week board: filter chips sit right under the title, above the summary and the cards, all visible on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 852 });
  await signIn(page);
  await page.goto("/");
  await cardsLoaded(page);
  const top = async (sel: string) => (await page.locator(sel).first().boundingBox())!.y;
  const chips = await top('[data-testid="filter-chips"]');
  expect(chips).toBeGreaterThan(await top("h1"));
  expect(chips).toBeLessThan(await top('[data-testid="kpi-model"]'));
  expect(chips).toBeLessThan(await top('[data-testid="game-card"]'));
  for (const name of ["All games", "Open to pick"]) await expect(page.getByTestId("filter-chips").getByRole("button", { name: new RegExp(name) })).toBeInViewport({ ratio: 1 });
});

test("F5 matchup: my pick buttons are on screen without scrolling (phone and desktop)", async ({ page, request }) => {
  const { open } = await board(request);
  const g = open[0];
  await signIn(page);
  for (const [w, h] of [[393, 852], [1440, 900]]) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(`/game/?id=${g.game_id}`);
    await expect(page.locator("aside").getByRole("button", { name: new RegExp(`^Pick ${g.home.name}`) }), `${w}x${h}`).toBeInViewport({ ratio: 1 });
  }
});

test("F6 section tabs: the tab you jump to is the one marked current", async ({ page, request }) => {
  const { open } = await board(request);
  await signIn(page);
  await page.goto(`/game/?id=${open[0].game_id}`);
  const tabs = page.getByRole("navigation", { name: "Sections" });
  for (const name of ["Injuries", "Market", "History"]) {
    await tabs.getByRole("link", { name }).click();
    await expect(tabs.getByRole("link", { name }), name).toHaveAttribute("aria-current", "true");
  }
  await expect(tabs.getByRole("link", { name: "Ask" })).toBeVisible();
});

test("G1 week-1 matchup: every en dash in Teams has a reason (no games played yet)", async ({ page, request }) => {
  const { meta } = await board(request);
  const g = (await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/1`)).games[0];
  await signIn(page);
  await page.goto(`/game/?id=${g.game_id}`);
  const teams = page.locator("#teams");
  await expect(teams).toContainText(/no games (played )?yet this season/i);
  const bare = await teams.evaluate((el) => [...el.querySelectorAll("*")].filter((n) => [...n.childNodes].some((c) => c.nodeType === 3 && c.textContent!.trim() === "–")).length);
  expect(bare, "no row is a bare en dash; the reason replaces or sits in it").toBe(0);
});

test("G2 lime paints what is mine: a picked pill, the selected chip, the primary button, active tabs", async ({ page, request }) => {
  const { open } = await board(request);
  const bg = (l: ReturnType<Page["locator"]>) => l.evaluate((el) => getComputedStyle(el).backgroundColor);
  await page.goto("/");
  expect(await bg(page.getByRole("button", { name: "Sign in", exact: true }))).toBe(LIME);
  await page.goto(`/game/?id=${open[0].game_id}`);
  await page.evaluate((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  await page.reload();
  const sectionsNav = page.getByRole("navigation", { name: "Sections" });
  await sectionsNav.getByRole("link", { name: "Market" }).click();
  await expect.poll(() => bg(sectionsNav.getByRole("link", { name: "Market" }))).toBe(LIME);
  await page.setViewportSize({ width: 393, height: 852 });
  await page.goto("/");
  await expect.poll(() => bg(page.getByRole("navigation", { name: "Primary" }).locator('[aria-current="page"]').first())).toBe(LIME);
  await page.setViewportSize({ width: 1440, height: 900 });
  const g = open[open.length - 1];
  await signIn(page);
  await page.goto("/");
  await cardsLoaded(page);
  expect(await page.getByTestId("filter-chips").getByRole("button", { name: /All games/ }).evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(LIME);
  const c = card(page, g);
  await c.getByRole("button", { name: new RegExp(`^Pick ${g.home.name}`) }).click();
  const picked = c.getByRole("button", { name: new RegExp(`^${g.home.name} picked`) });
  await page.mouse.move(0, 0);
  try {
    await expect.poll(() => picked.evaluate((el) => getComputedStyle(el).backgroundColor)).toBe(LIME);
  } finally {
    await picked.click();
    await expectServerCleared(request, g);
  }
});

test("G3 keyboard focus is visible and never hidden under the tab bar (phone, real Tab key)", async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 852 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await signIn(page);
  await page.goto("/");
  await cardsLoaded(page);
  const bar = (await page.getByRole("navigation", { name: "Primary" }).boundingBox())!;
  let checked = 0;
  for (let i = 0; i < 80 && checked < 4; i++) {
    await page.keyboard.press("Tab");
    const f = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el.closest('nav[aria-label="Primary"]')) return null;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return { name: el.getAttribute("aria-label") ?? el.textContent ?? "", bottom: r.bottom, top: r.top, outline: parseFloat(cs.outlineWidth), style: cs.outlineStyle, pick: !!el.closest('[role="group"]') };
    });
    if (!f || !f.pick) continue;
    checked++;
    expect(f.style, f.name).not.toBe("none");
    expect(f.outline, f.name).toBeGreaterThanOrEqual(2);
    expect(f.bottom, `${f.name} is not hidden under the tab bar`).toBeLessThanOrEqual(bar.y);
  }
  expect(checked, "tabbed through at least four pick buttons").toBeGreaterThanOrEqual(4);
});


test.describe(() => {
  test.use({ serviceWorkers: "block" }); // rewrites an API response with page.route
  test("G4 stale weather with no logged error never claims the source is down", async ({ page, request }) => {
    const { open } = await board(request);
    await page.route("**/api/freshness", async (route) => {
      const res = await route.fetch();
      const body = (await res.json()).map((d: { dataset: string }) => (d.dataset === "weather" ? { ...d, last_error: null } : d));
      await route.fulfill({ response: res, json: body });
    });
    await signIn(page);
    await page.goto(`/game/?id=${open[0].game_id}`);
    const conditions = page.locator("#conditions");
    await expect(conditions).toContainText(/not updated/i);
    await expect(conditions).not.toContainText(/down|unreachable|unavailable/i);
  });
});

for (const scheme of ["dark", "light"] as const) {
  test(`G5 accessibility on the phone layout (${scheme}): no serious or critical axe issues`, async ({ page, request }) => {
    const { open } = await board(request);
    await page.setViewportSize({ width: 393, height: 852 });
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await signIn(page);
    const AxeBuilder = (await import("@axe-core/playwright")).default;
    for (const path of ["/", `/game/?id=${open[0].game_id}`, "/performance/", "/backtest/", "/settings/"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const { violations } = await new AxeBuilder({ page }).analyze();
      const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.nodes.slice(0, 2).map((n) => n.target.join(" ")).join(" | ")}`);
      expect(bad, `${path} (${scheme})`).toEqual([]);
    }
  });
}
