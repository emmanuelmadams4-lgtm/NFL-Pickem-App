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

async function board(request: APIRequestContext) {
  const meta = await api<Meta>(request, "/meta");
  const week = await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/${meta.current_week}`);
  const open = week.games.filter((g) => !g.time_tbd && !g.locked && g.status === "scheduled").sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc));
  return { meta, games: week.games, open };
}

test.use({ serviceWorkers: "block" }); // R1/R6 rewrite API responses; a controlling service worker would bypass page.route

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
});

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
});

const LIME = "rgb(198, 241, 53)";

test("F1 smallest phone (320px): no screen scrolls sideways", async ({ page, request }) => {
  const { open } = await board(request);
  await page.setViewportSize({ width: 320, height: 700 });
  await signIn(page);
  for (const path of ["/", `/game/?id=${open[0].game_id}`, "/performance/", "/backtest/", "/settings/"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    expect(await page.evaluate(() => document.documentElement.scrollWidth), path).toBeLessThanOrEqual(320);
  }
});

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
});

test("F3 win split: lime is mine, never the model's tile; no check mark on it; backfill says so", async ({ page, request }) => {
  const { meta, open } = await board(request);
  const final = (await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/1`)).games[0];
  await signIn(page);
  for (const id of [open[0].game_id, final.game_id]) {
    await page.goto(`/game/?id=${id}`);
    const tile = page.getByTestId("win-tile-model");
    await expect(tile).toContainText("Model pick");
    expect(await tile.evaluate((el) => getComputedStyle(el).backgroundColor), id).not.toBe(LIME);
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
