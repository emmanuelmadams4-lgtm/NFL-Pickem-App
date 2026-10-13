import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Step 16b (web) gate, docs/gauntlet/logs/step-16b-web.md § 2 (clauses N1 to PV1): the Group screen.
 * Every member name here is made up. The seed (backend/tests/e2e_seed.py) holds four members, group picks for week 4 and
 * weekly points for weeks 1 to 3. Expected values are read from the API, never copied. Tests that upload come last.
 */
const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
const SEASON = 2023;
const MARKUP_NAME = "Zed <b>Bold</b> & Co";
const NAMES = ["Pat Example", "Sam Sample", "Kit Demo", MARKUP_NAME, "Quin Test"];
const PICKS_HEADER = "Week,Team,Game,Favored,Spread,Underdog,Pick,Side,Confidence,Week_Total_Pts";
const TOO_BIG = "That file is too large. The limit is 1 MB.";

type Side = { team: string; picks: number; share: number | null; avg_confidence: number | null };
type Shares = {
  games: { game_id: string; away_team: string; home_team: string; picked: number; members: number; away: Side; home: Side }[];
};
type Standings = { weeks_counted: number[]; rows: { member: string; points: number; total: number; rank: number | null }[] };
type Week = { games: { game_id: string; sheet: { app_pick: string | null } }[] };

async function get<T>(request: APIRequestContext, path: string): Promise<T> {
  const res = await request.get(`/api${path}`, { headers: AUTH });
  expect(res.ok(), path).toBeTruthy();
  return res.json() as Promise<T>;
}
const shares = (request: APIRequestContext, week: number, season = SEASON) => get<Shares>(request, `/group/shares?season=${season}&week=${week}`);
const standings = (request: APIRequestContext, week: number) => get<Standings>(request, `/group/standings?season=${SEASON}&week=${week}`);

async function open(page: Page, week: number, season = SEASON) {
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  await page.goto(`/group/?season=${season}&week=${week}`);
  await expect(page.getByRole("heading", { level: 1, name: "Group" })).toBeVisible();
}

const csvFile = (name: string, text: string) => ({ name, mimeType: "text/csv", buffer: Buffer.from(text) });
const chooser = (page: Page) => page.getByLabel("Choose a CSV file");
const confirmPanel = (page: Page) => page.getByTestId("upload-confirm");
const sendButton = (page: Page) => page.getByRole("button", { name: "Upload file" });
const gameCard = (page: Page, away: string, home: string) => page.getByTestId("group-game").filter({ has: page.getByRole("heading", { name: `${away} at ${home}` }) });

/** A picks file for one made-up member who picks the home team in every game of a week whose matchup is unique. */
async function picksFor(request: APIRequestContext, week: number, member: string) {
  const { games } = await shares(request, week);
  const key = (g: { away_team: string; home_team: string }) => [g.away_team, g.home_team].sort().join("-");
  const unique = games.filter((g) => games.filter((o) => key(o) === key(g)).length === 1);
  const rows = unique.map((g, i) => `${week},${member},${i + 1},${g.home_team},3.5,${g.away_team},${g.home_team},Favorite,${unique.length - i},0`);
  return { text: [PICKS_HEADER, ...rows, ""].join("\r\n"), unique };
}

test("N1 a Group entry in the main navigation opens the page, on the desktop bar and the phone tab bar", async ({ page }) => {
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  for (const size of [{ width: 1440, height: 900 }, { width: 375, height: 812 }]) {
    await page.setViewportSize(size);
    await page.goto("/");
    await page.getByRole("link", { name: "Group", exact: true }).click();
    await expect(page).toHaveURL(/\/group\/(\?.*)?$/);
    await expect(page.getByRole("heading", { level: 1, name: "Group" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Group", exact: true })).toHaveAttribute("aria-current", "page");
  }
});

test("S1 standings list rank, member, the week's points and the running total, and say which weeks are counted", async ({ page, request }) => {
  const api = await standings(request, 3);
  expect(api.rows.length).toBeGreaterThanOrEqual(4);
  await open(page, 3);
  const table = page.getByRole("table", { name: "Standings for week 3" });
  await expect(table.getByRole("columnheader")).toHaveText(["Rank", "Member", "Week", "Total"]);
  const body = table.getByRole("row").filter({ hasNot: page.getByRole("columnheader") });
  await expect(body).toHaveCount(api.rows.length);
  for (const [i, r] of api.rows.entries()) {
    await expect(body.nth(i).getByRole("cell")).toHaveText([r.rank === null ? "–" : String(r.rank), r.member, String(r.points), String(r.total)]);
  }
  await expect(page.getByText(`Totals count weeks ${api.weeks_counted.join(", ")}.`)).toBeVisible();
});

test("S2 a week with no standings says so in words", async ({ page }) => {
  await open(page, 4);
  await expect(page.getByText("No standings for week 4 yet")).toBeVisible();
  await expect(page.getByRole("table", { name: /Standings/ })).toHaveCount(0);
});

test("S3 a member name is shown as plain text, never as markup", async ({ page }) => {
  await open(page, 3);
  const table = page.getByRole("table", { name: "Standings for week 3" });
  await expect(table.getByRole("cell", { name: MARKUP_NAME, exact: true })).toBeVisible();
  await expect(table.locator("b")).toHaveCount(0);
});

test("P1 each game shows how many members picked each side, the share and the mean confidence points", async ({ page, request }) => {
  const api = await shares(request, 4);
  const withPicks = api.games.filter((g) => g.picked > 0);
  expect(withPicks.length).toBeGreaterThanOrEqual(2);
  await open(page, 4);
  await expect(page.getByTestId("group-game")).toHaveCount(api.games.length);
  for (const g of withPicks) {
    for (const s of [g.away, g.home]) {
      const row = gameCard(page, g.away_team, g.home_team).getByTestId(`side-${s.team}`);
      await expect(row).toContainText(new RegExp(`(^|\\D)${s.picks} of ${g.picked}(\\D|$)`));
      await expect(row).toContainText(s.share === null ? "–" : `${Math.round(s.share * 100)}%`);
      await expect(row).toContainText(s.avg_confidence === null ? "avg –" : `avg ${s.avg_confidence.toFixed(1)} pts`);
    }
  }
});

test("P2 next to each game stands the app's own pick, from data the page already loads", async ({ page, request }) => {
  const picks = await get<Week>(request, `/weeks/${SEASON}/4`);
  const api = await shares(request, 4);
  await open(page, 4);
  for (const g of api.games) {
    const app = picks.games.find((w) => w.game_id === g.game_id)?.sheet.app_pick ?? null;
    await expect(gameCard(page, g.away_team, g.home_team)).toContainText(`App pick: ${app ?? "–"}`);
  }
});

test("P3 empty states: a game nobody picked, a season with no group data, a week with no games", async ({ page, request }) => {
  const api = await shares(request, 4);
  const none = api.games.find((g) => g.picked === 0);
  expect(none).toBeTruthy();
  await open(page, 4);
  const card = gameCard(page, none!.away_team, none!.home_team);
  await expect(card).toContainText("No group picks for this game yet");
  await expect(card.getByTestId(/^side-/)).toHaveCount(0);

  await page.goto(`/group/?season=2022&week=1`);
  expect((await shares(request, 1, 2022)).games.every((g) => g.picked === 0)).toBe(true);
  await expect(page.getByText("No group picks for week 1 yet")).toBeVisible(); // one message, not a wall of empty cards
  await expect(page.getByTestId("group-game")).toHaveCount(0);
  await expect(page.getByText("No standings for week 1 yet")).toBeVisible();

  await page.route("**/api/group/shares*", (route) => route.fulfill({ json: { season: SEASON, week: 4, games: [] } }));
  await page.goto(`/group/?season=${SEASON}&week=4`);
  await expect(page.getByText("No games this week")).toBeVisible();
});

test("X1 the spread is never shown or used as a score", async ({ page }) => {
  await open(page, 4);
  await expect(page.getByTestId("group-game").first()).toBeVisible();
  await chooser(page).setInputFiles(csvFile("a.csv", "x"));
  await expect(confirmPanel(page)).toBeVisible();
  expect(await page.evaluate(() => document.body.innerText + document.documentElement.outerHTML.replace(/<script[\s\S]*?<\/script>/g, ""))).not.toMatch(/spread/i);
  await page.goto(`/group/?season=${SEASON}&week=3`);
  await expect(page.getByRole("table", { name: "Standings for week 3" })).toBeVisible();
  expect(await page.evaluate(() => document.body.innerText)).not.toMatch(/spread/i);
});

test("PV1 member names never reach the console or browser storage", async ({ page }) => {
  const logs: string[] = [];
  page.on("console", (m) => logs.push(m.text()));
  page.on("pageerror", (e) => logs.push(String(e)));
  await open(page, 3);
  await expect(page.getByRole("table", { name: "Standings for week 3" })).toBeVisible();
  await page.goto(`/group/?season=${SEASON}&week=4`);
  await expect(page.getByTestId("group-game").first()).toBeVisible();
  await page.evaluate(() => window.dispatchEvent(new Event("pagehide")));
  await page.waitForTimeout(1500); // the app's cache saver waits about a second
  const stored = await page.evaluate(() => JSON.stringify([{ ...localStorage }, { ...sessionStorage }]));
  for (const name of NAMES) {
    expect(stored, `storage holds ${name.length} chars of a name`).not.toContain(name);
    expect(logs.join("\n")).not.toContain(name);
  }
  expect(stored).not.toContain("Bold");
});

test("U1 a picks file is shown for confirmation with its season, sent as raw bytes only after confirming, and the screen refreshes", async ({ page, request }) => {
  const { text, unique } = await picksFor(request, 5, "Quin Test");
  expect(unique.length).toBeGreaterThanOrEqual(1);
  const posts: { url: string; type: string; body: Buffer | null }[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST" && r.url().includes("/api/group/import")) posts.push({ url: r.url(), type: r.headers()["content-type"] ?? "", body: r.postDataBuffer() });
  });
  await open(page, 5);
  await chooser(page).setInputFiles(csvFile("picks-week-5.csv", text));
  await expect(confirmPanel(page)).toContainText("picks-week-5.csv");
  await expect(confirmPanel(page)).toContainText("the server cannot tell if the year is wrong");
  await expect(page.getByLabel("Season for this file")).toHaveValue(String(SEASON));
  expect(posts).toHaveLength(0);

  await sendButton(page).click();
  await expect(page.getByTestId("upload-result")).toHaveText(`Picks file saved: ${unique.length} picks for the ${SEASON} season.`);
  expect(posts).toHaveLength(1);
  expect(new URL(posts[0].url).searchParams.get("season")).toBe(String(SEASON));
  expect(posts[0].type).not.toContain("multipart");
  expect(posts[0].body?.toString()).toBe(text);
  const g = unique[0];
  await expect(gameCard(page, g.away_team, g.home_team).getByTestId(`side-${g.home_team}`)).toContainText("1 of 1");
  await expect(confirmPanel(page)).toHaveCount(0);
  await chooser(page).setInputFiles(csvFile("picks-week-5.csv", text)); // the same file again must work
  await expect(confirmPanel(page)).toContainText("picks-week-5.csv");
  await expect(page.getByTestId("upload-result")).toHaveCount(0); // a new choice clears the old result
});

test("U2 the season can be changed in the confirm step and the chosen season is the one sent", async ({ page, request }) => {
  const { text } = await picksFor(request, 5, "Quin Test");
  const seen: string[] = [];
  await page.route("**/api/group/import*", (route) => {
    seen.push(route.request().url());
    return route.fulfill({ json: { season: 2022, kind: "picks", rows: 7 } });
  });
  await open(page, 5);
  await chooser(page).setInputFiles(csvFile("picks.csv", text));
  await page.getByLabel("Season for this file").selectOption("2022");
  await expect(confirmPanel(page)).toContainText("Saving to the 2022 season");
  await sendButton(page).dblclick(); // a double tap must send once
  await expect(page.getByTestId("upload-result")).toContainText("Picks file saved: 7 picks for the 2022 season.");
  expect(seen.map((u) => new URL(u).searchParams.get("season"))).toEqual(["2022"]);
  // The page shows 2023; a link says where the saved data went, so a wrong year cannot hide.
  await expect(page.getByRole("link", { name: "Show the 2022 season" })).toHaveAttribute("href", /season=2022/);
});

test("U3 a weekly performance file is described in words and the standings show it", async ({ page, request }) => {
  await open(page, 3);
  await chooser(page).setInputFiles(csvFile("weekly.csv", "Rank,Team,Wk1,Wk2,Wk3,Total_Pts\r\n1,Quin Test,9,9,9,27\r\n"));
  await sendButton(page).click();
  await expect(page.getByTestId("upload-result")).toHaveText(`Weekly performance file saved: 3 member-weeks for the ${SEASON} season.`);
  const api = await standings(request, 3);
  const mine = api.rows.find((r) => r.member === "Quin Test")!;
  const row = page.getByRole("table", { name: "Standings for week 3" }).getByRole("row", { name: /Quin Test/ });
  await expect(row.getByRole("cell")).toHaveText([mine.rank === null ? "–" : String(mine.rank), "Quin Test", "9", "27"]);
});

test("E1 the server's own 422 message is shown as is, and the file stays ready for another try", async ({ page, request }) => {
  const bad = Buffer.from(`${PICKS_HEADER}\r\n`);
  const direct = await request.post(`/api/group/import?season=${SEASON}`, { headers: AUTH, data: bad });
  expect(direct.status()).toBe(422);
  const detail = (await direct.json()).detail as string;
  await open(page, 4);
  await chooser(page).setInputFiles(csvFile("empty.csv", bad.toString()));
  await sendButton(page).click();
  await expect(page.getByTestId("upload-error")).toHaveText(detail);
  await expect(page.getByTestId("upload-error")).toHaveAttribute("role", "alert");
  await expect(sendButton(page)).toBeEnabled();
});

test("E2 a 413 and a 500 get their own plain messages, and a retry after a 500 works", async ({ page }) => {
  let status = 413;
  await page.route("**/api/group/import*", (route) =>
    status === 200
      ? route.fulfill({ json: { season: SEASON, kind: "standings", rows: 6 } })
      : route.fulfill({ status, json: { detail: status === 413 ? "file is too large" : "group import failed: database error" } }),
  );
  await open(page, 4);
  await chooser(page).setInputFiles(csvFile("a.csv", "Rank,Team,Wk1,Total_Pts\r\n1,Pat Example,5,5\r\n"));
  await sendButton(page).click();
  await expect(page.getByTestId("upload-error")).toHaveText(TOO_BIG);
  status = 500;
  await sendButton(page).click();
  await expect(page.getByTestId("upload-error")).toHaveText("The server could not save this file. Try again.");
  status = 200;
  await sendButton(page).click();
  await expect(page.getByTestId("upload-result")).toContainText("Weekly performance file saved: 6 member-weeks");
  await expect(page.getByTestId("upload-error")).toHaveCount(0);
});

test("E3 a file over the 1,000,000 byte cap is refused on the page without being sent", async ({ page }) => {
  let sent = 0;
  await page.route("**/api/group/import*", (route) => {
    sent += 1;
    return route.abort();
  });
  await open(page, 4);
  await chooser(page).setInputFiles({ name: "big.csv", mimeType: "text/csv", buffer: Buffer.alloc(1_000_001, "a") });
  await expect(page.getByTestId("upload-error")).toHaveText(TOO_BIG);
  await expect(sendButton(page)).toHaveCount(0);
  expect(sent).toBe(0);
});

test("L1 each section fails on its own with a retry, and an error is never shown as 'no data'", async ({ page }) => {
  await page.route("**/api/group/standings*", (route) => route.fulfill({ status: 500, json: { detail: "boom" } }));
  await open(page, 3);
  await expect(page.getByRole("alert").filter({ hasText: "Could not load" })).toHaveCount(1);
  await expect(page.getByText("No standings for week 3 yet")).toHaveCount(0);
  await expect(page.getByTestId("group-game")).not.toHaveCount(0); // the other section still works
  await page.unroute("**/api/group/standings*");
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByRole("table", { name: "Standings for week 3" })).toBeVisible();
});

test("L2 a late answer for an earlier week never replaces the week now shown", async ({ page }) => {
  await page.route("**/api/group/standings?*week=3*", async (route) => {
    await new Promise((r) => setTimeout(r, 1500));
    await route.continue();
  });
  await open(page, 3);
  await page.getByRole("button", { name: "Next week" }).click();
  await expect(page.getByText("No standings for week 4 yet")).toBeVisible();
  await page.waitForTimeout(2200);
  await expect(page.getByText("No standings for week 4 yet")).toBeVisible();
  await expect(page.getByRole("table", { name: /Standings/ })).toHaveCount(0);
});

test("R2 thirty-two members with a very long name fit a phone and clear the tab bar", async ({ page }) => {
  const rows = Array.from({ length: 32 }, (_, i) => ({
    member: i === 5 ? "Averyveryverylongmadeupnamewithoutanyspacesatall Placeholderson-Examplesmith" : `Member ${String(i + 1).padStart(2, "0")} Example`,
    points: 40 - i, total: 400 - i * 7, rank: i + 1,
  }));
  await page.route("**/api/group/standings*", (route) => route.fulfill({ json: { season: SEASON, week: 3, weeks_counted: [1, 2, 3], rows } }));
  await page.setViewportSize({ width: 375, height: 812 });
  await open(page, 3);
  const table = page.getByRole("table", { name: "Standings for week 3" });
  await expect(table.getByRole("row")).toHaveCount(33);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  await table.getByRole("row").last().scrollIntoViewIfNeeded();
  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
  const last = await table.getByRole("row").last().boundingBox();
  const bar = await page.getByRole("navigation", { name: "Primary" }).last().boundingBox();
  expect((last?.y ?? 0) + (last?.height ?? 0)).toBeLessThanOrEqual(bar?.y ?? 0);
});

for (const scheme of ["dark", "light"] as const) {
  test(`A1 the page has no accessibility violations (${scheme}): data, confirm step, error`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await page.route("**/api/group/import*", (route) => route.fulfill({ status: 422, json: { detail: "line 2: pick is invalid" } }));
    await open(page, 4);
    await expect(page.getByTestId("group-game").first()).toBeVisible();
    const clean = async () => expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await clean();
    await chooser(page).setInputFiles(csvFile("a.csv", "x"));
    await expect(confirmPanel(page)).toBeVisible();
    await clean();
    await sendButton(page).click();
    await expect(page.getByTestId("upload-error")).toBeVisible();
    await clean();
    await page.goto(`/group/?season=${SEASON}&week=3`);
    await expect(page.getByRole("table", { name: "Standings for week 3" })).toBeVisible();
    await clean();
  });
}

test("R1 on a phone nothing scrolls sideways and the controls are thumb-sized", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await open(page, 3);
  await chooser(page).setInputFiles(csvFile("a.csv", "x"));
  await expect(confirmPanel(page)).toBeVisible();
  for (const week of [3, 4]) {
    await page.goto(`/group/?season=${SEASON}&week=${week}`);
    await expect(page.getByRole("heading", { level: 1, name: "Group" })).toBeVisible();
    await expect(page.getByText(/^(Totals count weeks|No standings for week)/)).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(0);
  }
  await chooser(page).setInputFiles(csvFile("a.csv", "x"));
  for (const name of ["Upload file", "Choose another file"]) {
    const box = await page.getByRole("button", { name }).boundingBox();
    expect(box?.height ?? 0, name).toBeGreaterThanOrEqual(44);
  }
  await expect(page.getByLabel("Season for this file")).toBeVisible();
});
