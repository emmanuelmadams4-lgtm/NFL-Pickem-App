import { readFile } from "node:fs/promises";
import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Step 2 gate (docs/gauntlet/logs/step-2.md): desktop flows on the production export, Eastern time,
 * seeded by backend/tests/e2e_seed.py. One worker, so tests share the server and run in file order;
 * each one leaves the data as the others expect.
 */
const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };

type Team = { abbr: string; name: string; logo_url: string };
type Game = {
  game_id: string;
  kickoff_utc: string;
  status: string;
  locked: boolean;
  time_tbd?: boolean;
  my_pick: string | null;
  away: Team;
  home: Team;
  prediction: { home_win_prob: number } | null;
};
type Meta = { current_season: number; current_week: number; server_time: string };
type Tally = { correct: number; total: number };

async function api<T>(request: APIRequestContext, path: string): Promise<T> {
  const res = await request.get(`/api${path}`, { headers: AUTH });
  expect(res.ok(), path).toBeTruthy();
  return res.json() as Promise<T>;
}

async function board(request: APIRequestContext) {
  const meta = await api<Meta>(request, "/meta");
  const week = await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/${meta.current_week}`);
  const games = [...week.games].sort((a, b) => a.kickoff_utc.localeCompare(b.kickoff_utc));
  const open = games.filter((g) => !g.time_tbd && !g.locked && g.status === "scheduled");
  return { meta, games, open };
}

async function signIn(page: Page) {
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
}

const matchupName = (g: Game) => `Open matchup: ${g.away.name} at ${g.home.name}`;
const pickGroup = (page: Page, g: Game) => page.getByRole("group", { name: `Your pick: ${g.away.abbr} at ${g.home.abbr}` });
const gameRow = (page: Page, g: Game) => page.locator("li").filter({ has: page.getByRole("link", { name: matchupName(g) }) });
const eastern = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" });

async function boardLoaded(page: Page) {
  await expect(page.getByRole("link", { name: /^Open matchup:/ }).first()).toBeVisible();
}

test("E1 sign in: a wrong token is refused, the right one opens the current week", async ({ page, request }) => {
  const { meta } = await board(request);
  await page.goto("/");
  await page.getByLabel("Access token").fill("wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("#token-error")).toHaveText("Wrong token");
  await page.getByLabel("Access token").fill(TOKEN);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { level: 1, name: `Week ${meta.current_week}` })).toBeVisible();
});

test("E2 sort: the chosen order is applied and kept after a reload", async ({ page, request }) => {
  const { games } = await board(request);
  const prob = (g: Game) => (g.prediction ? Math.max(g.prediction.home_win_prob, 1 - g.prediction.home_win_prob) : 0.5);
  const expected = [...games].sort((a, b) => prob(b) - prob(a)).map(matchupName);
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await page.getByLabel("Sort by").selectOption({ label: "Most confident" });
  const order = () => page.getByRole("link", { name: /^Open matchup:/ }).evaluateAll((els) => els.map((e) => e.getAttribute("aria-label")));
  await expect.poll(order).toEqual(expected);
  await page.reload();
  await boardLoaded(page);
  await expect(page.getByLabel("Sort by")).toHaveValue("confidence_desc");
  await expect.poll(order).toEqual(expected);
  await page.getByLabel("Sort by").selectOption({ label: "Kickoff" });
});

test("E3 pick and clear: one tap saves to the server, a second tap clears it", async ({ page, request }) => {
  const { meta, open } = await board(request);
  const g = open[open.length - 1];
  const serverPick = async () =>
    (await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/${meta.current_week}`)).games.find((x) => x.game_id === g.game_id)!.my_pick;
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  const group = pickGroup(page, g);
  await group.getByRole("button", { name: new RegExp(`^Pick ${g.home.name}`) }).click();
  await expect(group.getByRole("button", { name: new RegExp(`^${g.home.name} picked`) })).toHaveAttribute("aria-pressed", "true");
  await expect.poll(serverPick).toBe(g.home.abbr);
  await page.reload();
  const picked = pickGroup(page, g).getByRole("button", { name: new RegExp(`^${g.home.name} picked`) });
  await expect(picked).toHaveAttribute("aria-pressed", "true");
  await picked.click();
  await expect.poll(serverPick).toBeNull();
  await page.reload();
  await expect(pickGroup(page, g).getByRole("button", { name: new RegExp(`^Pick ${g.home.name}`) })).toHaveAttribute("aria-pressed", "false");
});

test("E4 lock: a game locks on screen within 5 s of kickoff, without a reload, and looks locked", async ({ page, request }) => {
  const { meta, open } = await board(request);
  const g = open[0];
  await page.clock.install({ time: new Date(meta.server_time) });
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  const buttons = pickGroup(page, g).getByRole("button");
  await expect(buttons.first()).toBeEnabled();
  await page.clock.fastForward(Date.parse(g.kickoff_utc) - Date.parse(meta.server_time) - 1_000);
  await expect(buttons.first()).toBeEnabled();
  await page.clock.runFor(5_000);
  await expect(buttons.first()).toBeDisabled({ timeout: 2_000 });
  await expect(buttons.nth(1)).toBeDisabled();
  await expect(buttons.first().locator("svg"), "lock icon (design.md § 8)").toBeVisible();
  await expect(gameRow(page, g)).toContainText("Locked");
});

test("E5 matchup: every section renders and kickoff is in Eastern time", async ({ page, request }) => {
  const { open } = await board(request);
  const g = open[0];
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await expect(gameRow(page, g)).toContainText(eastern(g.kickoff_utc));
  await page.getByRole("link", { name: matchupName(g) }).click();
  for (const id of ["factors", "teams", "injuries", "conditions", "market", "ai", "ask", "history", "meetings"]) {
    await expect(page.locator(`#${id}`), id).toBeVisible();
  }
  await expect(page.getByText(eastern(g.kickoff_utc)).first()).toBeVisible();
  await expect(page.locator("aside").getByRole("meter").first(), "the pick panel's probability has a bar (design.md § 2)").toBeVisible();
});

test("E6 time TBD: a game with no kickoff time says so instead of showing midnight", async ({ page, request }) => {
  const { games } = await board(request);
  const tbd = games.find((g) => g.time_tbd);
  expect(tbd, "the API exposes time_tbd").toBeTruthy();
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  const row = gameRow(page, tbd!);
  await expect(row).toContainText("Time TBD");
  await expect(row).not.toContainText("12:00 AM");
  await page.goto(`/game/?id=${tbd!.game_id}`);
  await expect(page.getByText("Time TBD").first()).toBeVisible();
  await expect(page.getByText("12:00 AM")).toHaveCount(0);
});

test("E7 results: the model headline counts live picks only; backfill is shown apart", async ({ page, request }) => {
  const { meta } = await board(request);
  const perf = await api<{ model: Tally; model_backfill: Tally }>(request, `/performance/${meta.current_season}`);
  expect(perf.model.total, "no live prediction has been graded in the seed").toBe(0);
  expect(perf.model_backfill?.total, "backfilled games are counted separately").toBeGreaterThan(0);
  await signIn(page);
  await page.goto("/performance/");
  await expect(page.getByTestId("tally-model-live")).toContainText("No graded live picks yet");
  await expect(page.getByTestId("tally-model-backfill")).toContainText(
    `${perf.model_backfill.correct} of ${perf.model_backfill.total} correct`,
  );
});

test("E8 CSV: import a past pick, export it back, and Results counts it", async ({ page, request }) => {
  const { meta } = await board(request);
  const past = (await api<{ games: Game[] }>(request, `/weeks/${meta.current_season}/1`)).games[0];
  await signIn(page);
  await page.goto("/settings/");
  await page.locator("#csv-file").setInputFiles({
    name: "picks.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(`game_id,my_pick\n${past.game_id},${past.home.abbr}\n`),
  });
  await expect(page.getByText("Imported 1 pick")).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download CSV" }).click();
  const csv = await readFile((await (await download).path())!, "utf8");
  expect(csv).toContain(past.game_id);
  expect(csv).toContain(past.home.abbr);
  await page.goto("/performance/");
  await expect(page.getByTestId("tally-me")).toContainText("of 1 correct");
});

test("E9 weather outage: no banner on the board; Settings notes it is not a model input", async ({ page }) => {
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await expect(page.getByText(/Stale data/)).toHaveCount(0);
  await page.goto("/settings/");
  const fresh = page.locator("#freshness");
  await expect(fresh).toContainText(/weather/i);
  await expect(fresh).toContainText(/not a model input/i);
});

test("E9b stale model input: the board banner still shows for stale schedules", async ({ page }) => {
  await page.route("**/api/weeks/**", async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    body.freshness = body.freshness.map((d: { dataset: string }) => (d.dataset === "schedules" ? { ...d, stale: true } : d));
    await route.fulfill({ response: res, json: body });
  });
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  await expect(page.getByText(/Stale data: schedules/)).toBeVisible();
});

test("E10 design: the app renders in Geist", async ({ page }) => {
  await signIn(page);
  await page.goto("/");
  await boardLoaded(page);
  expect(await page.evaluate(() => getComputedStyle(document.body).fontFamily)).toMatch(/^"?Geist/);
  await page.evaluate(() => document.fonts.ready);
  expect(await page.evaluate(() => [...document.fonts].some((f) => /^"?Geist/.test(f.family) && f.status === "loaded"))).toBe(true);
});

test("E10b chart colors: no purple, and every series is at least 3:1 on its surface in both themes", async ({ page }) => {
  await signIn(page);
  for (const scheme of ["dark", "light"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto("/");
    await boardLoaded(page);
    const colors = await page.evaluate(() => {
      const probe = document.body.appendChild(document.createElement("i"));
      const read = (v: string) => {
        probe.style.color = `var(${v})`;
        return getComputedStyle(probe).color; // "rgb(r, g, b)" whatever the token's format
      };
      const names = ["me", "model", "market", "stats", "elo", "home"];
      const out = { surface: read("--surface"), series: names.map((n) => [n, read(`--series-${n}`)]) };
      probe.remove();
      return out;
    });
    const rgb = (c: string) => c.match(/[\d.]+/g)!.slice(0, 3).map((x) => Number(x) / 255);
    const lum = (hex: string) => {
      const [r, g, b] = rgb(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const hue = (hex: string) => {
      const [r, g, b] = rgb(hex);
      const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
      if (d === 0) return -1;
      const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4;
      return (h * 60 + 360) % 360;
    };
    for (const [name, hex] of colors.series) {
      const [hi, lo] = [lum(hex), lum(colors.surface)].sort((x, y) => y - x);
      expect((hi + 0.05) / (lo + 0.05), `${scheme} --series-${name} ${hex} contrast`).toBeGreaterThanOrEqual(3);
      const h = hue(hex);
      expect(h >= 250 && h <= 330, `${scheme} --series-${name} ${hex} is purple (hue ${Math.round(h)})`).toBe(false);
    }
  }
});

test("E12 logos and type floor: team logos come only from the API's logo_url, and no visible text under 11px", async ({ page, request }) => {
  const { games, open } = await board(request);
  const logos = new Set(games.flatMap((g) => [g.away.logo_url, g.home.logo_url]));
  const images: string[] = [];
  page.on("request", (r) => r.resourceType() === "image" && !r.url().startsWith("data:") && images.push(r.url()));
  await signIn(page);
  for (const path of ["/", `/game/?id=${open[0].game_id}`, "/performance/", "/backtest/", "/settings/"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const small = await page.evaluate(() =>
      [...document.querySelectorAll("body *")]
        .filter((el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent!.trim()))
        .filter((el) => (el as HTMLElement).getClientRects().length > 0 && getComputedStyle(el).visibility !== "hidden")
        .filter((el) => !el.closest(".sr-only") && parseFloat(getComputedStyle(el).fontSize) < 11)
        .map((el) => `${el.tagName.toLowerCase()} "${el.textContent!.trim().slice(0, 20)}" ${getComputedStyle(el).fontSize}`),
    );
    expect(small, `${path}: text under 11px (design.md § 4)`).toEqual([]);
  }
  expect(images.length, "the board shows team logos (owner decision 2026-10-12)").toBeGreaterThan(0);
  expect(images.filter((u) => !logos.has(u)), "only team logos from the API are fetched as images").toEqual([]);
});

test("E13 backfill stays labeled: week rows, the Results table and the weekly chart", async ({ page, request }) => {
  const { meta } = await board(request);
  const season = meta.current_season;
  const week1 = (await api<{ games: (Game & { prediction: { kind: string } | null })[] }>(request, `/weeks/${season}/1`)).games;
  expect(week1.every((g) => g.prediction?.kind === "backfill"), "seed: week 1 is all backfill").toBe(true);
  await signIn(page);
  await page.goto(`/?season=${season}&week=1`);
  await boardLoaded(page);
  for (const g of week1) await expect(gameRow(page, g), g.game_id).toContainText("Backfilled");
  await page.goto("/performance/");
  const row1 = page.locator("tr").filter({ has: page.locator("th[scope=row]", { hasText: /^1$/ }) });
  await expect(row1, "week 1 Model cell: no live figure, backfill noted").toContainText("backfilled");
  await expect(page.getByText("Model, backfilled").first()).toBeVisible();
});

test("E14 missing is drawn as missing: an en dash, never a bare hyphen", async ({ page, request }) => {
  const { open } = await board(request);
  await signIn(page);
  for (const path of ["/", `/game/?id=${open[0].game_id}`, "/performance/", "/settings/"]) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const bare = await page.evaluate(() =>
      [...document.querySelectorAll("main *")].filter((el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent!.trim() === "-")).length,
    );
    expect(bare, `${path}: bare "-" used for a missing value (design.md § 2.5)`).toBe(0);
  }
});

async function axe(page: Page, name: string) {
  await expect(page.locator('[aria-busy="true"]')).toHaveCount(0);
  const { violations } = await new AxeBuilder({ page }).analyze();
  const bad = violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`);
  expect(bad, name).toEqual([]);
}

for (const scheme of ["dark", "light"] as const) {
  test(`E11 accessibility (${scheme}): no serious or critical axe issues on any screen`, async ({ page, request }) => {
    const { open } = await board(request);
    await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
    await page.goto("/");
    await expect(page.getByLabel("Access token")).toBeVisible();
    await axe(page, "sign-in");
    await page.evaluate((t) => localStorage.setItem("nflpi_token", t), TOKEN);
    const screens: [string, string, () => Promise<void>][] = [
      ["week", "/", () => boardLoaded(page)],
      ["matchup", `/game/?id=${open[0].game_id}`, () => expect(page.locator("#meetings")).toBeVisible()],
      ["results", "/performance/", () => expect(page.getByTestId("tally-me")).toBeVisible()],
      ["backtest", "/backtest/", () => expect(page.getByRole("heading", { level: 1 })).toBeVisible()],
      ["settings", "/settings/", () => expect(page.locator("#freshness")).toBeVisible()],
    ];
    for (const [name, path, ready] of screens) {
      await page.goto(path);
      await ready();
      await axe(page, `${name} (${scheme})`);
    }
  });
}
