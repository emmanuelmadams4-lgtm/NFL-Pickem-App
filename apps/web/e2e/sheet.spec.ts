import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Step 4 gate (docs/gauntlet/logs/step-4.md § 2, U1-U4): the pick sheet on screen. Same server, seed and
 * conventions as step2.spec.ts. Each test leaves the sheet as it found it.
 */
const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
const LABELS = /Easy pick|Tough matchup|Coin flip/;

type Team = { abbr: string; name: string };
type Sheet = {
  label: string | null;
  app_pick: string | null;
  app_points: number | null;
  my_pick: string | null;
  my_points: number | null;
  pick_by: string;
  points_by: string;
  differs: boolean;
};
type Game = { game_id: string; kickoff_utc: string; status: string; locked: boolean; time_tbd?: boolean; away: Team; home: Team; sheet: Sheet };
type Meta = { current_season: number; current_week: number; server_time: string; pick_lock_minutes: number };

async function api<T>(request: APIRequestContext, path: string): Promise<T> {
  const res = await request.get(`/api${path}`, { headers: AUTH });
  expect(res.ok(), path).toBeTruthy();
  return res.json() as Promise<T>;
}

async function board(request: APIRequestContext) {
  const meta = await api<Meta>(request, "/meta");
  const week = await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/${meta.current_week}`);
  const games = [...week.games].sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc) || a.game_id.localeCompare(b.game_id));
  const open = games.filter((g) => !g.locked && g.status === "scheduled" && g.sheet.my_points !== null);
  return { meta, games, open };
}

async function signIn(page: Page) {
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
}

const card = (page: Page, g: Game) =>
  page.getByTestId("game-card").filter({ has: page.getByRole("link", { name: `Open matchup: ${g.away.name} at ${g.home.name}` }) });
const points = (page: Page, g: Game) => page.getByRole("combobox", { name: `Points for ${g.away.abbr} at ${g.home.abbr}` });

async function boardLoaded(page: Page) {
  await expect(page.getByRole("link", { name: /^Open matchup:/ }).first()).toBeVisible();
}

test("U1 every open game shows its label, its points and whose pick it is", async ({ page, request }) => {
  const { open } = await board(request);
  expect(open.length).toBeGreaterThanOrEqual(3);
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  for (const g of open) {
    await expect(card(page, g).getByTestId("pick-label")).toHaveText(LABELS);
    await expect(points(page, g)).toHaveValue(String(g.sheet.my_points));
    await expect(points(page, g).locator("option")).toHaveCount(open.length);
    if (g.sheet.pick_by === "app") await expect(card(page, g)).toContainText(`Counts as ${g.sheet.app_pick}, the model's pick`);
  }
});

test("U1b changing a game's points swaps with the game that had them, says so, and the model's number can be taken back", async ({ page, request }) => {
  const { open } = await board(request);
  const low = open.reduce((a, b) => (a.sheet.my_points! < b.sheet.my_points! ? a : b));
  const high = open.reduce((a, b) => (a.sheet.my_points! > b.sheet.my_points! ? a : b));
  const serverPoints = async () => {
    const now = (await board(request)).games;
    return [low, high].map((g) => now.find((x) => x.game_id === g.game_id)!.sheet.my_points);
  };
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);

  await points(page, low).selectOption(String(high.sheet.my_points));

  await expect.poll(serverPoints).toEqual([high.sheet.my_points, low.sheet.my_points]);
  await expect(points(page, high)).toHaveValue(String(low.sheet.my_points));
  await expect(page.getByText(`${high.away.abbr} @ ${high.home.abbr} is now ${low.sheet.my_points}`)).toBeVisible();
  await expect(card(page, low)).toContainText("Your number");
  await expect(card(page, low)).toContainText(`Model says ${low.sheet.app_points}`);

  await card(page, low).getByRole("button", { name: /Use the model's number/ }).click();
  await card(page, high).getByRole("button", { name: /Use the model's number/ }).click();
  await expect.poll(serverPoints).toEqual([low.sheet.my_points, high.sheet.my_points]);
  await expect(card(page, low)).not.toContainText("Your number");
});

test("U1c the points lock on screen before kickoff, without a reload", async ({ page, request }) => {
  const { meta, open } = await board(request);
  const g = open.filter((x) => !x.time_tbd)[0]; // a game with no kickoff time never locks from its placeholder
  await page.clock.install({ time: new Date(meta.server_time) });
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await expect(points(page, g)).toBeEnabled();
  await page.clock.fastForward(Date.parse(g.kickoff_utc) - meta.pick_lock_minutes * 60_000 - Date.parse(meta.server_time) - 1_000);
  await page.clock.runFor(4_000);
  await expect(points(page, g)).toBeDisabled({ timeout: 2_000 });
});

test("U2 copy sheet: every game in kickoff order with the winner and points, and one button copies it", async ({ page, request, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const { games } = await board(request);
  const listed = games.filter((g) => g.sheet.my_points !== null);
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);

  await page.getByRole("link", { name: "Yahoo sheet" }).click();

  await expect(page.getByRole("heading", { level: 1 })).toContainText(/copy sheet/i);
  const rows = page.getByTestId("sheet-row");
  await expect(rows).toHaveCount(listed.length);
  for (const [i, g] of listed.entries()) {
    await expect(rows.nth(i)).toContainText(`${g.away.abbr} @ ${g.home.abbr}`);
    await expect(rows.nth(i).getByTestId("sheet-winner")).toHaveText(g.sheet.my_pick!);
    await expect(rows.nth(i).getByTestId("sheet-points")).toHaveText(String(g.sheet.my_points));
  }

  await page.getByRole("button", { name: "Copy as text" }).click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  const lines = copied.trim().split("\n");
  expect(lines).toHaveLength(listed.length);
  for (const [i, g] of listed.entries()) {
    expect(lines[i]).toBe(`${g.away.abbr} @ ${g.home.abbr}: ${g.sheet.my_pick} ${g.sheet.my_points}`);
  }
  await expect(page.getByRole("status")).toContainText(/copied/i);
});

test("U3b results: a rank typed before the scorecard has loaded is not wiped when it arrives", async ({ page }) => {
  await page.route("**/api/scorecard/**", async (route) => {
    await new Promise((r) => setTimeout(r, 1_500));
    await route.continue().catch(() => undefined);
  });
  await signIn(page);
  const scorecard = page.waitForResponse((r) => r.url().includes("/api/scorecard/"));
  await page.goto("/performance/");
  const form = page.getByRole("group", { name: "Your Yahoo rank" });
  await form.getByLabel("Your rank").fill("9");
  await form.getByLabel("Leader's points").fill("77");
  await scorecard;
  await page.waitForLoadState("networkidle");
  await expect(form.getByLabel("Your rank")).toHaveValue("9");
  await expect(form.getByLabel("Leader's points")).toHaveValue("77");
});

test("U3 results: he enters his Yahoo rank for a week and the scorecard shows it", async ({ page, request }) => {
  const { meta } = await board(request);
  await signIn(page);
  await page.goto("/performance/");
  const form = page.getByRole("group", { name: "Your Yahoo rank" });
  await form.getByLabel("Week").selectOption(String(meta.current_week));
  await form.getByLabel("Your rank").fill("4");
  await form.getByLabel("Leader's points").fill("61");
  await form.getByRole("button", { name: "Save rank" }).click();

  await expect(page.getByText("Rank saved")).toBeVisible();
  const card = await expect
    .poll(async () => {
      const weeks = (await api<{ weeks: { week: number; rank: number | null; leader_points: number | null }[] }>(request, `/scorecard/${meta.current_season}`)).weeks;
      return weeks.find((w) => w.week === meta.current_week);
    })
    .toMatchObject({ rank: 4, leader_points: 61 });
  void card;
  const table = page.getByRole("table", { name: "Scorecard" });
  for (const head of ["Week", "You", "Model", "Rank"]) await expect(table.getByRole("columnheader", { name: head, exact: true })).toBeVisible();
  await expect(table.getByRole("row").filter({ hasText: `Week ${meta.current_week}` })).toContainText("4");
});

test("U3c results: a rank saved before the scorecard has loaded still shows in the scorecard", async ({ page, request }) => {
  const { meta } = await board(request);
  await signIn(page);
  // The page's first scorecard answer is read from the server at once but handed over only after the save.
  let release: () => void = () => undefined;
  const afterSave = new Promise<void>((r) => (release = r));
  let held = false;
  await page.route("**/api/scorecard/**", async (route) => {
    if (held) return route.continue();
    held = true;
    const response = await route.fetch();
    await afterSave;
    await route.fulfill({ response });
  });
  await page.goto("/performance/");
  const form = page.getByRole("group", { name: "Your Yahoo rank" });
  try {
    await form.getByLabel("Week").selectOption(String(meta.current_week));
    await form.getByLabel("Your rank").fill("6");
    await form.getByLabel("Leader's points").fill("55");
    const put = page.waitForResponse((r) => r.url().includes("/api/ranks/") && r.request().method() === "PUT");
    await form.getByRole("button", { name: "Save rank" }).click();
    expect((await put).ok()).toBeTruthy();
  } finally {
    release();
  }
  await expect(page.getByText("Rank saved")).toBeVisible();
  const row = page.getByRole("table", { name: "Scorecard" }).getByRole("row").filter({ hasText: `Week ${meta.current_week}` });
  await expect(row, "the scorecard shows what was just saved, not the answer from before the save").toContainText("Leader 55 points");
});

for (const scheme of ["dark", "light"] as const) {
  test(`U4 accessibility (${scheme}): no serious or critical axe issues on the board, the copy sheet and Results`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    await signIn(page);
    for (const path of ["/", "/sheet/", "/performance/"]) {
      await page.goto(path);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await page.waitForLoadState("networkidle");
      const { violations } = await new AxeBuilder({ page }).analyze();
      const bad = violations.filter((v) => v.impact === "serious" || v.impact === "critical");
      expect(bad.map((v) => `${path} ${v.id}: ${v.nodes.length}`), `axe on ${path}`).toEqual([]);
    }
  });
}

test("U4b phone (375px): the board with points and the copy sheet do not scroll sideways", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await signIn(page);
  for (const path of ["/", "/sheet/", "/performance/"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow, `${path} sideways scroll`).toBeLessThanOrEqual(0);
  }
});
