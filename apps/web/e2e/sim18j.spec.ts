import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { components } from "@nflpi/shared";

/**
 * Step 18j (docs/gauntlet/logs/step-18j.md, S1-S6): the score simulator on the game page and the pick mode on the
 * week board. The e2e seed fits no simulator, so every game's `simulation` is null; the tests that need one add it to
 * the real game reply, typed against the wire type. The numbers are made up.
 */
type Simulation = components["schemas"]["SimulationOut"];
type Game = { game_id: string; status: string; locked: boolean; time_tbd?: boolean; away: { abbr: string }; home: { abbr: string } };
type Week = { games: Game[]; pick_mode: components["schemas"]["PickModeOut"] };

const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
const LABEL = "Score simulator, football-only inputs: not shown to beat the betting market or the win model";

const SIM: Simulation = {
  source: "football_only",
  distribution: "empirical",
  n_simulations: 10000,
  home_points: 24.6,
  away_points: 21.5,
  home_win: 0.58,
  away_win: 0.41,
  tie: 0.01,
  expected_margin: 3.1,
  expected_total: 46.1,
  margin_80: [-9, 15.2],
  total_80: [32.4, 60.8],
  home_spread: -3.5,
  total: 45.5,
  home_cover: 0.4812,
  away_cover: 0.4903,
  spread_push: 0.0285,
  over: 0.5121,
  under: 0.4879,
  total_push: 0,
  label: LABEL,
};

test.use({ viewport: { width: 393, height: 852 }, hasTouch: true, serviceWorkers: "block" });

async function api<T>(request: APIRequestContext, path: string): Promise<T> {
  const res = await request.get(`/api${path}`, { headers: AUTH });
  expect(res.ok(), path).toBeTruthy();
  return res.json() as Promise<T>;
}

async function currentWeek(request: APIRequestContext): Promise<Week> {
  const meta = await api<{ current_season: number; current_week: number }>(request, "/meta");
  return api<Week>(request, `/weeks/${meta.current_season}/${meta.current_week}`);
}

async function openGame(request: APIRequestContext): Promise<Game> {
  const { games } = await currentWeek(request);
  const g = games.find((x) => !x.time_tbd && x.status === "scheduled");
  expect(g, "the seed has a scheduled game this week").toBeTruthy();
  return g!;
}

/** Open the game page, with `sim` added to the real reply (undefined = leave the server's answer as it is). */
async function gamePage(page: Page, g: Game, sim?: Simulation) {
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  if (sim) {
    await page.route(`**/api/games/${g.game_id}`, async (route) => {
      const res = await route.fetch();
      const body = await res.json();
      expect(body.prediction, "the seeded game has a prediction").toBeTruthy();
      body.prediction.simulation = sim;
      await route.fulfill({ response: res, json: body });
    });
  }
  await page.goto(`/game/?id=${g.game_id}`);
  await expect(section(page)).toBeVisible({ timeout: 15_000 });
}

const section = (page: Page) => page.locator("#simulator");

test("S1 S2 S4 the simulator's numbers, labelled as shown only, never a pick", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g, SIM);
  const s = section(page);
  await expect(page.getByRole("navigation", { name: "Sections" }).getByText("Simulator", { exact: true })).toBeVisible();
  await expect(s.getByRole("heading", { name: "Score simulator" })).toBeVisible();
  await expect(s).toContainText(LABEL);
  await expect(s).toContainText("Shown only: not a pick, and it does not change the pick above.");
  await expect(s).toContainText(`${g.away.abbr} 21.5`);
  await expect(s).toContainText(`${g.home.abbr} 24.6`);
  await expect(s).toContainText(`${g.home.abbr} margin`);
  await expect(s).toContainText("+3.1");
  await expect(s).toContainText(/80% of runs: [−-]9\.0 to \+15\.2/);
  await expect(s).toContainText("46.1");
  await expect(s).toContainText("80% of runs: 32.4 to 60.8");
  await expect(s).toContainText("Based on 10,000 simulated games.");

  // S2: against the spread and the total, whole percents, each with its side
  await expect(s).toContainText(new RegExp(`${g.home.abbr} [−-]3\\.5`));
  await expect(s).toContainText(new RegExp(`${g.home.abbr}\\D{0,24}48%`));
  await expect(s).toContainText(new RegExp(`${g.away.abbr}\\D{0,24}49%`));
  await expect(s).toContainText(/Push\D{0,12}3%/);
  await expect(s).toContainText("Over/under 45.5");
  // the simulator's lines can differ from the latest line in Market, so each says which line it used
  await expect(s.getByText("the line the simulator used")).toHaveCount(2);
  await expect(s).toContainText(/Over\D{0,12}51%/);
  await expect(s).toContainText(/Under\D{0,12}49%/);

  // S4: no pick words
  expect(await s.innerText()).not.toMatch(/\block|guaranteed|\bbet\b/i);
});

test("S2 no spread or total yet: each block says so and shows no chances", async ({ page, request }) => {
  const g = await openGame(request);
  const none: Simulation = { ...SIM, home_spread: null, total: null, home_cover: null, away_cover: null, spread_push: null, over: null, under: null, total_push: null };
  await gamePage(page, g, none);
  const s = section(page);
  await expect(s).toContainText("No spread yet.");
  await expect(s).toContainText("No total yet.");
  await expect(s).not.toContainText("Push");
  await expect(s).not.toContainText("Over/under");
  await expect(s).toContainText("+3.1"); // the margin and total still show
});

test("S3 no simulation for the game: one plain sentence", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g); // the seed fits no simulator, so the server says null
  const s = section(page);
  await expect(s).toContainText("No simulation for this game yet.");
  await expect(s).not.toContainText("80% of runs");
  await expect(s).not.toContainText("the line the simulator used");
});

test("S5 the week board names the pick mode the API reports", async ({ page, request }) => {
  const week = await currentWeek(request);
  expect(week.pick_mode.label.length).toBeGreaterThan(0);
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  await page.goto("/");
  await expect(page.getByText(week.pick_mode.label, { exact: true })).toBeVisible({ timeout: 15_000 });
});

test("S5b a saved week reply from before pick_mode existed still shows the board", async ({ page }) => {
  // the phone keeps its query cache for days, so a week reply without pick_mode can be shown after a deploy
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  await page.route("**/api/weeks/**", async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    delete body.pick_mode;
    await route.fulfill({ response: res, json: body });
  });
  await page.goto("/");
  await expect(page.getByTestId("game-card").first()).toBeVisible({ timeout: 15_000 });
});

for (const width of [393, 320]) {
  test(`S6 at ${width} px: no serious axe finding and no sideways scroll with a simulation`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 852 });
    const g = await openGame(request);
    await gamePage(page, g, SIM);
    await section(page).scrollIntoViewIfNeeded();
    const axe = await new AxeBuilder({ page }).include("#simulator").analyze();
    expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
}
