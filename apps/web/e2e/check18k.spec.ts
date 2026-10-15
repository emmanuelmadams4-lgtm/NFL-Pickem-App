import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { components } from "@nflpi/shared";

/**
 * Step 18k web (docs/gauntlet/logs/step-18k-web.md, C1-C5): the run check's verdict on the game's simulation, shown in
 * the Score simulator section. The e2e seed has no check, so the tests replace `simulation` and `simulation_check` in
 * the real game reply, typed against the wire types. The values are made up.
 */
type Simulation = components["schemas"]["SimulationOut"];
type Check = components["schemas"]["SimulationCheckOut"];
type Game = { game_id: string; status: string; time_tbd?: boolean };

const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };

const SIM: Simulation = {
  source: "football_only", distribution: "empirical", n_simulations: 10000, home_points: 24.6, away_points: 21.5,
  home_win: 0.58, away_win: 0.41, tie: 0.01, expected_margin: 3.1, expected_total: 46.1, margin_80: [-9, 15.2],
  total_80: [32.4, 60.8], home_spread: -3.5, total: 45.5, home_cover: 0.4812, away_cover: 0.4903, spread_push: 0.0285,
  over: 0.5121, under: 0.4879, total_push: 0,
  label: "Score simulator, football-only inputs: not shown to beat the betting market or the win model",
};

test.use({ viewport: { width: 393, height: 852 }, hasTouch: true, serviceWorkers: "block" });

async function openGame(request: APIRequestContext): Promise<Game> {
  const meta = await (await request.get("/api/meta", { headers: AUTH })).json();
  const week = await (await request.get(`/api/weeks/${meta.current_season}/${meta.current_week}`, { headers: AUTH })).json();
  const g = (week.games as Game[]).find((x) => !x.time_tbd && x.status === "scheduled");
  expect(g, "the seed has a scheduled game this week").toBeTruthy();
  return g!;
}

/** Open the game page with `simulation` and `simulation_check` set in the real reply (`undefined` check = key removed). */
async function gamePage(page: Page, g: Game, sim: Simulation | null, check: Check | null | undefined) {
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  await page.route(`**/api/games/${g.game_id}`, async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    expect(body.prediction, "the seeded game has a prediction").toBeTruthy();
    body.prediction.simulation = sim;
    if (check === undefined) delete body.prediction.simulation_check;
    else body.prediction.simulation_check = check;
    await route.fulfill({ response: res, json: body });
  });
  await page.goto(`/game/?id=${g.game_id}`);
  await expect(section(page)).toBeVisible({ timeout: 15_000 });
}

const section = (page: Page) => page.locator("#simulator");

const FAILED_NOTE = "The run check failed for 2023_04_BUF_MIA. This run is not used; showing the last checked simulation.";
const NO_VERDICT_NOTE = "The run check gave no verdict (cap). This run is not used; no checked simulation yet.";
const BACKFILL_NOTE = "A backfill run is not sent to the run check, so it has no simulation.";

test("C1 failed: plain words, the server's note, and the last checked numbers still shown", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g, SIM, { status: "failed", note: FAILED_NOTE });
  const s = section(page);
  await expect(s).toContainText("Run check failed");
  await expect(s).toContainText(FAILED_NOTE);
  await expect(s).toContainText("Based on 10,000 simulated games.");
  await expect(s).not.toContainText("Cause:");
});

const CAUSES: Record<string, string> = {
  cap: "the daily check limit was reached",
  provider: "Claude could not be reached",
  unparsed: "the check's answer could not be read",
  error: "the check hit an error",
};

for (const [cause, words] of Object.entries(CAUSES)) {
  test(`C2 no verdict (${cause}): plain words, the note, the cause in words, no simulation`, async ({ page, request }) => {
    const g = await openGame(request);
    await gamePage(page, g, null, { status: "no_verdict", note: NO_VERDICT_NOTE, cause });
    const s = section(page);
    await expect(s).toContainText("Run check gave no verdict");
    await expect(s).toContainText(NO_VERDICT_NOTE);
    await expect(s).toContainText(`Cause: ${words}`);
    await expect(s).toContainText("No simulation for this game yet.");
  });
}

test("C6 design critic 1: the notice is the app's Notice and never touches the line below it", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g, null, { status: "no_verdict", note: NO_VERDICT_NOTE, cause: "cap" });
  const note = section(page).getByRole("note");
  await expect(note).toHaveClass(/\brounded-ctl\b/); // the shared Notice (ui.tsx), like every other notice
  const box = (await note.boundingBox())!;
  const next = (await section(page).getByText("No simulation for this game yet.").boundingBox())!;
  expect(next.y - (box.y + box.height), "a gap of at least 8 px under the notice").toBeGreaterThanOrEqual(8);
});

test("C3 not checked (a backfill run): plain words and the note", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g, null, { status: "not_checked", note: BACKFILL_NOTE });
  const s = section(page);
  await expect(s).toContainText("Not checked");
  await expect(s).toContainText(BACKFILL_NOTE);
});

for (const [name, check] of [["null (a passed run)", null], ["absent (an old cached reply)", undefined]] as const) {
  test(`C4 check ${name}: no notice, the section as before`, async ({ page, request }) => {
    const g = await openGame(request);
    await gamePage(page, g, SIM, check);
    const s = section(page);
    await expect(s).toContainText("Based on 10,000 simulated games.");
    await expect(s).not.toContainText(/Run check|Not checked|Cause:/);
  });
}

test("C5 at 320 px: no serious axe finding and no sideways scroll with a no-verdict notice", async ({ page, request }) => {
  await page.setViewportSize({ width: 320, height: 852 });
  const g = await openGame(request);
  await gamePage(page, g, SIM, { status: "no_verdict", note: NO_VERDICT_NOTE, cause: "provider" });
  await section(page).scrollIntoViewIfNeeded();
  const axe = await new AxeBuilder({ page }).include("#simulator").analyze();
  expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
