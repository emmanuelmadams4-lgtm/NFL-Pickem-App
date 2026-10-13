import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Step 8a2 gate (docs/gauntlet/logs/step-8a2.md): star players and who is out, on the week board and the game
 * screen. The data is seeded by backend/tests/e2e_seed.py (STAR_LISTS): KC has a list for week 4 with one star
 * Out, one Doubtful and one Questionable; NE's list is a week older; BUF has four stars out and one very long
 * name; MIA and LV have no list. Reports were first seen three hours ago.
 * Wording and states were reviewed before the build (UX critic, step-8a2-evidence/reviews/ux-architect-spec.md).
 */
const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
const SEASON = 2023;

type Team = { abbr: string; name: string };
type Game = { game_id: string; week: number; away: Team; home: Team };

async function games(request: APIRequestContext, week: number): Promise<Game[]> {
  const res = await request.get(`/api/weeks/${SEASON}/${week}`, { headers: AUTH });
  expect(res.ok()).toBeTruthy();
  return (await res.json()).games;
}

async function open(page: Page, path: string) {
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  await page.goto(path);
}

/** The card of one game on the week board: the list item that holds its "Open matchup" link. */
const card = (page: Page, g: Game) =>
  page.getByRole("listitem").filter({ has: page.getByRole("link", { name: `Open matchup: ${g.away.name} at ${g.home.name}` }) });

const find = (all: Game[], away: string, home: string) => all.find((g) => g.away.abbr === away && g.home.abbr === home)!;

for (const size of [
  { name: "phone", width: 393, height: 852 },
  { name: "desktop", width: 1280, height: 800 },
]) {
  test.describe(`${size.name}`, () => {
    test.use({ viewport: { width: size.width, height: size.height } });

    test("ST1 the row names the stars who are out or doubtful, with how long ago that was seen", async ({ page, request }) => {
      const g = find(await games(request, 4), "NE", "KC");
      await open(page, "/");
      const line = card(page, g).getByRole("group", { name: "Stars out" });
      await expect(line).toBeVisible({ timeout: 15_000 });
      await expect(line).toContainText("Cory Corner");
      await expect(line).toContainText("CB");
      await expect(line).toContainText("Out");
      await expect(line).toContainText("Cal Catch");
      await expect(line).toContainText("Doubtful");
      await expect(line).toContainText(/latest seen 3h ago/i);
      await expect(line, "Questionable is not on the row").not.toContainText("Ron Runner");
      await expect(line, "a player who is out but not a star").not.toContainText("Not A Star");
    });

    test("ST2 more than three: three names, then how many more; a QB already in the QB alert is not repeated; a long name never widens the page", async ({ page, request }) => {
      const g = find(await games(request, 4), "BUF", "MIA");
      await open(page, "/");
      const line = card(page, g).getByRole("group", { name: "Stars out" });
      await expect(line).toBeVisible({ timeout: 15_000 });
      await expect(card(page, g), "the QB alert that was there before").toContainText("Jo Thrower");
      await expect(line, "the same man is not shown twice on one card").not.toContainText("Jo Thrower");
      await expect(line).toContainText("Maximilian Featherstonehaugh-Smythe III");
      await expect(line).toContainText("Dee Deep");
      await expect(line).toContainText("Ed Edge");
      await expect(line).not.toContainText("Nick Nickel");
      await expect(line).toContainText("+1 more");
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth), "no sideways scroll").toBeLessThanOrEqual(0);
    });

    test("ST3 the row is silent only when it is known that no star is out; not known is said", async ({ page, request }) => {
      const week4 = await games(request, 4);
      await open(page, "/");
      const noList = card(page, find(week4, "MIA", "LV"));
      await expect(noList).toBeVisible({ timeout: 15_000 });
      await expect(noList.getByRole("group", { name: "Stars out" })).toHaveCount(0);
      await expect(noList, "neither club has a star list").toContainText("No star list yet");

      const week5 = await games(request, 5);
      const next = week5.find((x) => ["KC", "NE", "BUF"].includes(x.home.abbr) && ["KC", "NE", "BUF"].includes(x.away.abbr));
      if (next) {
        await open(page, `/?season=${SEASON}&week=5`);
        await expect(card(page, next), "lists exist, the week's report does not").toContainText("Injury report not in yet", { timeout: 15_000 });
      }
      const past = (await games(request, 3))[0];
      await open(page, `/?season=${SEASON}&week=3`);
      await expect(card(page, past)).toBeVisible({ timeout: 15_000 });
      await expect(card(page, past), "a finished game carries no stars line").not.toContainText(/star list|report not in/i);
    });

    test("ST4 the game screen lists both clubs' five stars with each one's status, and says when a list is older", async ({ page, request }) => {
      const g = find(await games(request, 4), "NE", "KC");
      await open(page, `/game/?id=${g.game_id}`);
      const section = page.locator("#injuries");
      await expect(section.getByRole("heading", { name: "Star players" })).toBeVisible({ timeout: 15_000 });

      const kc = section.getByRole("list", { name: `${g.home.name} star players` }).getByRole("listitem");
      await expect(kc).toHaveCount(5);
      await expect(kc.nth(0)).toContainText("Pat Passer");
      await expect(kc.nth(0)).toContainText("Not on injury report");
      await expect(kc.nth(1)).toContainText("Ron Runner");
      await expect(kc.nth(1)).toContainText("Questionable");
      await expect(kc.nth(2)).toContainText("Cal Catch");
      await expect(kc.nth(2)).toContainText("Doubtful");
      await expect(kc.nth(3)).toContainText("Cory Corner");
      await expect(kc.nth(3)).toContainText("Out");
      await expect(kc.nth(3)).toContainText("Knee");
      await expect(kc.nth(3)).toContainText(/seen 3h ago/i);
      await expect(kc.nth(4)).toContainText("Russ Rush");

      const ne = section.getByRole("list", { name: `${g.away.name} star players` }).getByRole("listitem");
      await expect(ne).toHaveCount(5);
      await expect(section.getByText("Star list from week 3"), "NE's list is a week older than the game").toBeVisible();
      await expect(section.getByText("Star list from week 4")).toHaveCount(0);
      await expect(section.getByText(/does not change the pick/i), "D24, D27: said on the screen").toBeVisible();
      await expect(section.getByText(/when this app first saw/i), "what the age counts from").toBeVisible();
    });

    test("ST5 a club with no star list says so", async ({ page, request }) => {
      const g = find(await games(request, 4), "MIA", "LV");
      await open(page, `/game/?id=${g.game_id}`);
      const section = page.locator("#injuries");
      await expect(section.getByRole("heading", { name: "Star players" })).toBeVisible({ timeout: 15_000 });
      await expect(section.getByText("No star list yet")).toHaveCount(2);
      await expect(section.getByRole("list", { name: /star players/ })).toHaveCount(0);
    });

    test("ST6 before the week's first injury report, the screen says the report is not out yet", async ({ page, request }) => {
      const next = (await games(request, 5)).find((x) => ["KC", "NE", "BUF"].some((t) => t === x.home.abbr || t === x.away.abbr));
      expect(next, "a week 5 game with a club that has a star list").toBeTruthy();
      await open(page, `/game/?id=${next!.game_id}`);
      const section = page.locator("#injuries");
      await expect(section.getByRole("heading", { name: "Star players" })).toBeVisible({ timeout: 15_000 });
      await expect(section.getByText("No injury report yet this week")).toBeVisible();
      await expect(section.getByText("Not on injury report"), "not known is never shown as available").toHaveCount(0);
    });

    for (const scheme of ["dark", "light"] as const) {
      test(`ST7 accessibility (${scheme}): no serious or critical axe issue on the board or the game screen`, async ({ page, request }) => {
        await page.emulateMedia({ colorScheme: scheme });
        const g = find(await games(request, 4), "NE", "KC");
        for (const path of ["/", `/game/?id=${g.game_id}`]) {
          await open(page, path);
          await expect(page.getByText("Cory Corner").first()).toBeVisible({ timeout: 15_000 });
          const { violations } = await new AxeBuilder({ page }).analyze();
          expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.nodes[0]?.target}`), path).toEqual([]);
        }
      });
    }
  });
}

test("ST8 Settings shows when the star list and the head coaches were last refreshed", async ({ page }) => {
  await open(page, "/settings/");
  const rows = page.getByRole("listitem");
  await expect(rows.filter({ hasText: /^injuries/i })).toHaveCount(1, { timeout: 15_000 });
  await expect(rows.filter({ hasText: /^stars/i }), "the star list has its own row").toHaveCount(1);
  await expect(rows.filter({ hasText: /^head.coaches/i }), "so does the head-coach refresh").toHaveCount(1);
});
