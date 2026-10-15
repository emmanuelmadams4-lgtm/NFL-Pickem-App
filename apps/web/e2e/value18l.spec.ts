import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { components } from "@nflpi/shared";

/**
 * Step 18l (docs/gauntlet/logs/step-18l.md, W1-W6): the 18i value rating of each book price, in a Value section of
 * the game page. The e2e seed has no book prices, so the tests replace `value_ratings` in the real game reply, typed
 * against the wire type. The values are made up.
 */
type Rating = components["schemas"]["ValueRatingOut"];
type Game = { game_id: string; status: string; time_tbd?: boolean; home: { abbr: string }; away: { abbr: string } };

const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
const SEEN = "2026-10-17T14:55:00Z";
const NOTE = "Price seen at 2026-10-17 14:55 UTC by bookone; it may no longer be offered.";

test.use({ viewport: { width: 393, height: 852 }, hasTouch: true, serviceWorkers: "block" });

function rating(over: Partial<Rating>): Rating {
  return {
    market_type: "moneyline", selection: "home", sportsbook: "bookone", line: null, price: 120, observed_at: SEEN,
    status: "UNRATED", stars: null, expected_value: 0.32, reasons: ["NO_VALIDATION_HISTORY"], note: NOTE, ...over,
  };
}

async function openGame(request: APIRequestContext): Promise<Game> {
  const meta = await (await request.get("/api/meta", { headers: AUTH })).json();
  const week = await (await request.get(`/api/weeks/${meta.current_season}/${meta.current_week}`, { headers: AUTH })).json();
  const g = (week.games as Game[]).find((x) => !x.time_tbd && x.status === "scheduled");
  expect(g, "the seed has a scheduled game this week").toBeTruthy();
  return g!;
}

/** Open the game page with `value_ratings` set in the real reply (`undefined` = key removed, an old cached reply). */
async function gamePage(page: Page, g: Game, ratings: Rating[] | undefined) {
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  await page.route(`**/api/games/${g.game_id}`, async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    if (ratings === undefined) delete body.value_ratings;
    else body.value_ratings = ratings;
    await route.fulfill({ response: res, json: body });
  });
  await page.goto(`/game/?id=${g.game_id}`);
  await expect(section(page)).toBeVisible({ timeout: 15_000 });
}

const section = (page: Page) => page.locator("#value");
const WORDING = "not yet shown to beat the market";

test("W1 unrated win price: market, side, price, book, status, reason, seen-at note and the PLAN wording", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g, [rating({})]);
  const s = section(page);
  await expect(s.getByRole("heading", { name: "Value" })).toBeVisible();
  await expect(s).toContainText(WORDING);
  await expect(s).toContainText("Win");
  await expect(s).toContainText(g.home.abbr);
  await expect(s).toContainText("+120");
  await expect(s).toContainText("bookone");
  await expect(s).toContainText("Unrated");
  await expect(s).toContainText("Expected value +32%");
  await expect(s).toContainText(NOTE);
  await expect(page.locator('a[href="#value"]')).toHaveText("Value"); // the section tab
});

test("W2 stale price: No bet, the reason in words, and never shown as available", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g, [rating({ status: "NO_BET", reasons: ["STALE_PRICE"] })]);
  const s = section(page);
  await expect(s).toContainText("No bet");
  await expect(s).toContainText("price too old to rate");
  await expect(s).toContainText("may no longer be offered");
  await expect(s).not.toContainText(/available|Unrated/i);
});

test("W3 spread and total sides read as lines; nonpositive value says why; a stars rating reads as n of 5", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g, [
    rating({ market_type: "spread", selection: "home", line: -3.5, price: 110 }),
    rating({ market_type: "spread", selection: "away", line: -3.5, price: -130, status: "NO_BET", expected_value: -0.1,
      reasons: ["NONPOSITIVE_EV"] }),
    rating({ market_type: "total", selection: "over", line: 47.5, price: 105, status: "RATED", stars: 3, reasons: [] }),
    rating({ market_type: "total", selection: "under", line: 47.5, price: -125, reasons: ["MYSTERY_CODE"] }),
  ]);
  const s = section(page);
  await expect(s).toContainText(`${g.home.abbr} -3.5`);
  await expect(s).toContainText(`${g.away.abbr} +3.5`);
  await expect(s).toContainText("Over 47.5");
  await expect(s).toContainText("Under 47.5");
  await expect(s).toContainText("no value at this price");
  await expect(s).toContainText("Expected value -10%");
  await expect(s).toContainText("3 of 5 stars");
  await expect(s).toContainText("MYSTERY_CODE");
});

for (const [name, ratings] of [["empty", []], ["absent (an old cached reply)", undefined]] as const) {
  test(`W4 ratings ${name}: the section says there is nothing to rate`, async ({ page, request }) => {
    const g = await openGame(request);
    await gamePage(page, g, ratings as Rating[] | undefined);
    await expect(section(page)).toContainText("No book prices to rate for this game.");
  });
}

test("W5 a book name with markup renders as plain text", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g, [rating({ sportsbook: "<img src=x onerror=alert(1)>book" })]);
  await expect(section(page)).toContainText("<img src=x onerror=alert(1)>book");
  await expect(section(page).locator("img")).toHaveCount(0);
});

test("W6 at 320 px: no serious axe finding and no sideways scroll", async ({ page, request }) => {
  await page.setViewportSize({ width: 320, height: 852 });
  const g = await openGame(request);
  await gamePage(page, g, [
    rating({}),
    rating({ market_type: "spread", selection: "away", line: -3.5, price: -130, status: "NO_BET", reasons: ["STALE_PRICE"] }),
  ]);
  await section(page).scrollIntoViewIfNeeded();
  const axe = await new AxeBuilder({ page }).include("#value").analyze();
  expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
