import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { components } from "@nflpi/shared";

/**
 * Step 8g web (docs/gauntlet/logs/step-8g-web.md, N1-N6): the game's latest news on the game page, from
 * GET /api/news?game_id=. The e2e seed has no news rows, so the real reply is empty; the tests that need items rewrite
 * the reply in the browser, typed against the wire type. Headlines are made up.
 */
type News = components["schemas"]["NewsOut"];
type Item = components["schemas"]["NewsItemOut"];
type Game = { game_id: string; status: string; time_tbd?: boolean };

const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
const hoursAgo = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();

test.use({ viewport: { width: 393, height: 852 }, hasTouch: true, serviceWorkers: "block" });

async function openGame(request: APIRequestContext): Promise<Game> {
  const meta = await (await request.get("/api/meta", { headers: AUTH })).json();
  const week = await (await request.get(`/api/weeks/${meta.current_season}/${meta.current_week}`, { headers: AUTH })).json();
  const g = (week.games as Game[]).find((x) => !x.time_tbd && x.status === "scheduled");
  expect(g, "the seed has a scheduled game this week").toBeTruthy();
  return g!;
}

/** Open the game page; `reply` replaces the news answer (a number = that HTTP status), undefined = the real server. */
async function gamePage(page: Page, g: Game, reply?: Item[] | number) {
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  if (reply !== undefined) {
    await page.route("**/api/news?*", (route) =>
      typeof reply === "number"
        ? route.fulfill({ status: reply, json: { detail: "boom" } })
        : route.fulfill({ json: { game_id: g.game_id, items: reply } satisfies News }),
    );
  }
  await page.goto(`/game/?id=${g.game_id}`);
  await expect(news(page)).toBeVisible({ timeout: 15_000 });
}

const news = (page: Page) => page.locator("#news");

const ITEMS: Item[] = [
  { title: "Starting quarterback limited in practice", source: "ESPN", published_at: hoursAgo(3), url: "https://www.espn.com/nfl/story/_/id/1", tags: ["injury"] },
  { title: "Coordinator to call plays this week", source: "CBS Sports", published_at: null, url: null, tags: ["coach", "playcaller"] },
  { title: "Odd &lt;b&gt; headline", source: "ESPN", published_at: hoursAgo(26), url: "javascript:alert(1)", tags: [] },
];

test("N1 N2 N3 each item: title as text, safe link only, source, age and tags", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g, ITEMS);
  const s = news(page);
  await expect(page.getByRole("navigation", { name: "Sections" }).getByText("News", { exact: true })).toBeVisible();
  await expect(s.getByRole("heading", { name: "News" })).toBeVisible();
  const rows = s.getByRole("listitem");
  await expect(rows).toHaveCount(3);

  // N1: order, source, age, tags; no age when published_at is null
  await expect(rows.nth(0)).toContainText("Starting quarterback limited in practice");
  await expect(rows.nth(0)).toContainText("ESPN");
  await expect(rows.nth(0)).toContainText("3h ago");
  await expect(rows.nth(0)).toContainText("injury");
  await expect(rows.nth(1)).toContainText("CBS Sports");
  await expect(rows.nth(1)).toContainText("coach");
  await expect(rows.nth(1)).toContainText("playcaller");
  await expect(rows.nth(1)).not.toContainText(/ago|never/);
  await expect(rows.nth(2)).toContainText("26h ago");

  // N2: the https link exactly, opened apart; no link for null or javascript:
  const link = rows.nth(0).getByRole("link", { name: "Starting quarterback limited in practice" });
  await expect(link).toHaveAttribute("href", "https://www.espn.com/nfl/story/_/id/1");
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  await expect(rows.nth(1).getByRole("link")).toHaveCount(0);
  await expect(rows.nth(2).getByRole("link")).toHaveCount(0);
  expect(await s.locator('a[href^="javascript"]').count()).toBe(0);

  // N3: markup-looking text stays text
  await expect(rows.nth(2)).toContainText("Odd &lt;b&gt; headline");
  expect(await s.locator("b").count()).toBe(0);
});

test("N4 no news for the game (the real server reply): one plain sentence", async ({ page, request }) => {
  const g = await openGame(request);
  const res = await request.get(`/api/news?game_id=${g.game_id}`, { headers: AUTH });
  expect(res.status()).toBe(200);
  expect((await res.json()).items).toEqual([]);
  const asked = page.waitForRequest((r) => r.url().includes(`/api/news?game_id=${g.game_id}`));
  await gamePage(page, g);
  await asked;
  await expect(news(page)).toContainText("No news for this game yet.");
  await expect(news(page).getByRole("listitem")).toHaveCount(0);
});

test("N5 the news request fails: the section says so and the page still works", async ({ page, request }) => {
  const g = await openGame(request);
  await gamePage(page, g, 500);
  await expect(news(page)).toContainText("Could not load news");
  await expect(page.locator("#market")).toBeVisible();
});

const LONG: Item[] = Array.from({ length: 5 }, (_, i) => ({
  title: `Long headline ${i + 1} ${"about the injury report and the depth chart ".repeat(4)}`.slice(0, 200),
  source: i % 2 ? "CBS Sports" : "ESPN",
  published_at: hoursAgo(i + 1),
  url: i % 2 ? null : `https://www.espn.com/nfl/story/_/id/${i}`,
  tags: ["coach", "injury", "playcaller", "trade"],
}));

for (const width of [393, 320]) {
  test(`N6 at ${width} px: no serious axe finding and no sideways scroll with five long items`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 852 });
    const g = await openGame(request);
    await gamePage(page, g, LONG);
    await expect(news(page).getByRole("listitem")).toHaveCount(5);
    await news(page).scrollIntoViewIfNeeded();
    const axe = await new AxeBuilder({ page }).include("#news").analyze();
    expect(axe.violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => v.id)).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  });
}
