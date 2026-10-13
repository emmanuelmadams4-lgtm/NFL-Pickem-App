import { expect, test, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Step 15 web gate (docs/gauntlet/logs/step-15-web.md): live scores on the game card and the game screen.
 * No game is in progress in the fixture, and no real network call is allowed, so the API's answers are replaced in
 * the browser: one seeded game is made "started" and /api/live answers what each test says. Criteria L1 to L11 and
 * the state table S1 to S6 are in the step log, section 2.
 */
const TOKEN = "e2e-token";
const ID = "2023_04_NE_KC"; // away NE, home KC; the model picks KC
const WORST = "2023_04_BUF_MIA"; // three-letter clubs, a QB alert, stars out

type Row = {
  game_id: string; state: "in" | "post" | "lost"; home_team: string; away_team: string;
  home_score: number | null; away_score: number | null; period: number | null; clock: string | null;
  home_win_prob: number | null; kalshi_home_prob: number | null; updated_at: string;
};
type Reply = { games: Row[]; stale: boolean; last_confirmed_at: string | null };
type Fake = {
  /** What /api/live answers: a reply, or an HTTP status for a failure. */
  live: Reply | number;
  /** Fields laid over the seeded game in the week and game answers. */
  game: Record<string, unknown>;
  calls: number;
};

/** One "now" for the fixtures and the page clock, so a slow machine cannot age a fixture between the two. */
const T0 = Date.now();
const agoIso = (ms: number) => new Date(T0 - ms).toISOString();
const row = (over: Partial<Row> = {}): Row => ({
  game_id: ID, state: "in", home_team: "KC", away_team: "NE", home_score: 21, away_score: 14, period: 3, clock: "4:12",
  home_win_prob: 0.71, kalshi_home_prob: 0.68, updated_at: agoIso(20_000), ...over,
});
const reply = (rows: Row[] = [row()], over: Partial<Reply> = {}): Reply => ({ games: rows, stale: false, last_confirmed_at: agoIso(20_000), ...over });
const started = () => ({ status: "in_progress", kickoff_utc: agoIso(90 * 60_000), time_tbd: false, locked: true, home_score: null, away_score: null });

/** Replace the API's answers for one game and for /api/live. The page clock is ours, so 30 seconds take no time. */
async function fake(page: Page, live: Reply | number = reply(), game: Record<string, unknown> = started(), id = ID, deviceSkewMs = 0): Promise<Fake> {
  const f: Fake = { live, game, calls: 0 };
  await page.clock.install({ time: T0 + deviceSkewMs });
  await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
  await page.route("**/api/{weeks,games}/**", async (route) => {
    try {
      const res = await route.fetch();
      const body = await res.json();
      for (const g of body.games ?? [body]) if (g.game_id === id) Object.assign(g, f.game);
      await route.fulfill({ response: res, json: body });
    } catch {
      // a request still in flight when the test ends: the page is gone, nothing to answer
    }
  });
  // the server's clock is T0-based too, so the fixtures' stamps keep their age however slow the machine is
  const installedAt = Date.now();
  await page.route("**/api/meta", async (route) => {
    try {
      const res = await route.fetch();
      await route.fulfill({ response: res, json: { ...(await res.json()), server_time: new Date(T0 + Date.now() - installedAt).toISOString() } });
    } catch {
      // as above
    }
  });
  await page.route("**/api/live", async (route) => {
    f.calls += 1;
    if (typeof f.live === "number") await route.fulfill({ status: f.live, json: { detail: "no" } });
    else await route.fulfill({ json: f.live });
  });
  return f;
}

const card = (page: Page, away = "NE", home = "KC") =>
  page.getByRole("listitem").filter({ has: page.getByRole("link", { name: `Open matchup: ${away} Team at ${home} Team` }) });

/** The words as the log writes them; the page may put each part in its own element. */
const words = (s: string) => new RegExp(s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/ · /g, "\\s*·\\s*").replace(/ /g, "\\s*"));

async function board(page: Page) {
  await page.goto("/");
  await expect(card(page)).toBeVisible({ timeout: 15_000 });
}

test.describe("phone", () => {
  test.use({ viewport: { width: 393, height: 852 } });

  test("L1 no started game on screen: the web never asks for live scores", async ({ page }) => {
    const f = await fake(page, reply(), {});
    await board(page);
    await page.clock.fastForward(125_000);
    await page.goto(`/game/?id=${ID}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible({ timeout: 15_000 });
    await page.clock.fastForward(125_000);
    expect(f.calls).toBe(0);
    await expect(page.getByText(/to win now|No live score/)).toHaveCount(0);
  });

  test("L2 polling: at once, then every 30 seconds; a failed poll is followed by the next; nothing live goes into the offline cache", async ({ page }) => {
    const f = await fake(page);
    await board(page);
    await expect(card(page)).toContainText(words("Live · Q3 4:12"));
    expect(f.calls).toBe(1);
    await page.clock.fastForward(29_000);
    expect(f.calls, "not before 30 seconds").toBe(1);
    await page.clock.fastForward(2_000);
    await expect.poll(() => f.calls).toBe(2);
    f.live = 503;
    await page.clock.fastForward(31_000);
    await expect.poll(() => f.calls).toBeGreaterThanOrEqual(3);
    f.live = reply([row({ home_score: 28 })]);
    await page.clock.fastForward(31_000);
    await expect(card(page), "the poll after a failure still happens").toContainText("28");
    await page.clock.runFor(3_000); // let the debounced cache save run
    const saved = await page.evaluate(() => localStorage.getItem("nflpi_cache") ?? "");
    expect(saved, "the week is saved for offline use").toContain('"week"');
    expect(saved, "live scores are not: an old score must never open as current").not.toContain("kalshi_home_prob");
  });

  test("L2 polling stops while the page is hidden", async ({ page }) => {
    const f = await fake(page);
    await board(page);
    await expect.poll(() => f.calls).toBe(1);
    await page.evaluate(() => {
      Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await page.clock.fastForward(95_000);
    expect(f.calls).toBe(1);
  });

  test("L2 every started game has ended: one call every 120 seconds, so a reversal is still seen", async ({ page }) => {
    const f = await fake(page, reply([row({ state: "post", period: 4, clock: "0:00" })]));
    await board(page);
    await expect(card(page)).toContainText(words("Ended · result pending"));
    await page.clock.fastForward(95_000);
    expect(f.calls, "not every 30 seconds").toBe(1);
    await page.clock.fastForward(30_000);
    await expect.poll(() => f.calls).toBe(2);
  });

  test("L2 a board left open across a kickoff starts asking without a reload", async ({ page }) => {
    const f = await fake(page, reply(), { status: "scheduled", kickoff_utc: new Date(T0 + 60_000).toISOString(), time_tbd: false, locked: false });
    await board(page);
    await page.clock.fastForward(30_000);
    expect(f.calls).toBe(0);
    await page.clock.fastForward(40_000);
    await page.clock.runFor(3_000);
    await expect.poll(() => f.calls).toBeGreaterThanOrEqual(1);
    await expect(card(page)).toContainText(words("Live · Q3 4:12"));
  });

  test("L7 it ends: when the week says final the live block is gone and the asking stops", async ({ page }) => {
    const f = await fake(page);
    await board(page);
    await expect(card(page)).toContainText(words("Live · Q3 4:12"));
    f.game = { ...started(), status: "final", home_score: 27, away_score: 17 };
    await page.clock.fastForward(125_000); // the week data refetches every 120 seconds
    await expect(card(page)).toContainText("27");
    await expect(card(page)).not.toContainText(/Live|to win now|Pregame/);
    const before = f.calls;
    await page.clock.fastForward(125_000);
    expect(f.calls).toBe(before);
  });
});

/** S2 to S6 and the rules for missing numbers: what the card must say, and what it must not. */
const states: { name: string; live: Reply | number; game?: Record<string, unknown>; has: string[]; hasNot: RegExp; reader?: string }[] = [
  {
    name: "S5 live", live: reply(),
    has: ["Live · Q3 4:12", "KC to win now · ESPN 71% · Kalshi 68%", "Pregame model pick", "Pregame line"],
    hasNot: /In progress|have won|Not updating|Started|Ended/, reader: "Live score NE 14, KC 21, third quarter, 4:12 left.",
  },
  {
    name: "S2 ended", live: reply([row({ state: "post", period: 4, clock: "0:00" })], { stale: true, last_confirmed_at: agoIso(300_000) }),
    has: ["Ended · result pending"], hasNot: /to win now|Not updating|Live|ESPN|Q4|Final/, reader: "Ended, result pending: NE 14, KC 21.",
  },
  { name: "S2 ended, no score", live: reply([row({ state: "post", home_score: null, away_score: null })]), has: ["Ended · score not in yet"], hasNot: /result pending|to win now|Live/ },
  {
    name: "S3 lost", live: reply([row({ state: "lost", home_win_prob: null, kalshi_home_prob: null })], { stale: true }),
    has: ["Not updating · last seen Q3 4:12"], hasNot: /to win now|ESPN|Kalshi|Live ·|Last update/, reader: "Score may be out of date: NE 14, KC 21.",
  },
  {
    name: "S4 not updating", live: reply([row()], { stale: true, last_confirmed_at: agoIso(3 * 60_000) }),
    has: ["Not updating · Q3 4:12", "Last update 3m ago"], hasNot: /to win now|ESPN|Kalshi|71%|Live ·/, reader: "Score may be out of date, last update 3 minutes ago: NE 14, KC 21.",
  },
  { name: "S4 one minute is singular", live: reply([row()], { stale: true, last_confirmed_at: agoIso(60_000) }), has: ["Last update 1m ago"], hasNot: /to win now/, reader: "Score may be out of date, last update 1 minute ago: NE 14, KC 21." },
  { name: "S4 not updating, never confirmed", live: reply([row()], { stale: true, last_confirmed_at: null }), has: ["Not updating · Q3 4:12", "No update yet"], hasNot: /Last update|to win now/ },
  { name: "S6 no row for the game", live: reply([]), has: ["Started", "No live score right now"], hasNot: /Live ·|to win now|Not updating|In progress|\d:\d\d [AP]M/, reader: "Game started, no live score right now." },
  { name: "S6 the request fails from the start (503)", live: 503, has: ["Started", "No live score right now"], hasNot: /Live ·|to win now|Not updating/ },
  { name: "one score missing: no score at all", live: reply([row({ away_score: null })]), has: ["Live · Q3 4:12", "No live score right now"], hasNot: /\b21\b/ },
  { name: "no ESPN number", live: reply([row({ home_win_prob: null })]), has: ["KC to win now · ESPN – · Kalshi 68%"], hasNot: /ESPN 0%|ESPN 50%/ },
  { name: "no Kalshi price", live: reply([row({ kalshi_home_prob: null })]), has: ["KC to win now · ESPN 71% · Kalshi –"], hasNot: /Kalshi 0%/ },
  { name: "neither number", live: reply([row({ home_win_prob: null, kalshi_home_prob: null })]), has: ["Live · Q3 4:12", "No live win chance right now"], hasNot: /to win now|ESPN|Kalshi/ },
  { name: "no period: no period text, no clock", live: reply([row({ period: null })]), has: ["Live"], hasNot: /Live ·|4:12|Q\d/ },
  { name: "no clock", live: reply([row({ clock: null })]), has: ["Live · Q3"], hasNot: /Q3 \d|null/ },
  { name: "halftime", live: reply([row({ period: 2, clock: "0:00" })]), has: ["Live · Halftime"], hasNot: /Q2|0:00/, reader: "Live score NE 14, KC 21, halftime." },
  { name: "end of a quarter", live: reply([row({ period: 1, clock: "0:00" })]), has: ["Live · End of Q1"], hasNot: /0:00/ },
  { name: "end of the fourth", live: reply([row({ period: 4, clock: "0:00" })]), has: ["Live · End of Q4"], hasNot: /0:00/ },
  { name: "overtime", live: reply([row({ period: 5, clock: "8:00" })]), has: ["Live · OT 8:00"], hasNot: /Q5/ },
  { name: "second overtime", live: reply([row({ period: 6, clock: "2:00" })]), has: ["Live · 2OT 2:00"], hasNot: /Q6/ },
  { name: "a clock the app does not know is shown as it arrives", live: reply([row({ clock: "End of 3rd" })]), has: ["Live · Q3 End of 3rd"], hasNot: /null/ },
  { name: "almost certain is never 100%", live: reply([row({ home_win_prob: 0.997, kalshi_home_prob: 0.999 })]), has: ["KC to win now · ESPN >99% · Kalshi >99%"], hasNot: /100%/ },
  { name: "almost lost is never 0%", live: reply([row({ home_win_prob: 0.004, kalshi_home_prob: 0.0 })]), has: ["KC to win now · ESPN <1% · Kalshi <1%"], hasNot: /\b0%/ },
  {
    name: "no prediction: the chance is stated for my pick, as 100 minus the home figure", live: reply(), game: { ...started(), prediction: null, my_pick: "NE" },
    has: ["NE to win now · ESPN 29% · Kalshi 32%"], hasNot: /KC to win/,
  },
  { name: "no prediction and no pick: the home club", live: reply(), game: { ...started(), prediction: null, my_pick: null }, has: ["KC to win now · ESPN 71% · Kalshi 68%"], hasNot: /NE to win/ },
];

for (const size of [{ name: "phone", width: 393, height: 852 }, { name: "desktop", width: 1280, height: 800 }]) {
  test.describe(`${size.name}`, () => {
    test.use({ viewport: { width: size.width, height: size.height } });

    for (const s of states) {
      test(`L3 L4 L10 card: ${s.name}`, async ({ page }) => {
        await fake(page, s.live, s.game ?? started());
        await board(page);
        const c = card(page);
        for (const text of s.has) await expect(c, text).toContainText(words(text), { timeout: 15_000 });
        await expect(c).not.toContainText(s.hasNot);
        if (s.reader) await expect(c.getByText(s.reader, { exact: true }), "one sentence for a screen reader").toHaveCount(1);
        await expect(c.locator("[aria-live]"), "not a live region: no speech every 30 seconds").toHaveCount(0);
        await expect(page.getByRole("status").filter({ hasText: /live|score|fail|error/i }), "no error toast").toHaveCount(0);
      });
    }

    test("polish: a screen reader gets the missing-chance words, 'Not updating' is in the warning ink, pregame star news is gone once a game has started", async ({ page }) => {
      const f = await fake(page, reply([row({ home_win_prob: null, kalshi_home_prob: null })]), { ...started(), status: "scheduled", stars_out: { out: [], no_list: ["NE"], reports_seen: 0, checked_at: null } });
      await board(page);
      const c = card(page);
      await expect(c).toContainText("No live win chance right now", { timeout: 15_000 });
      await expect(c.locator(".sr-only").filter({ hasText: "No live win chance right now" })).toHaveCount(1);
      await expect(c, "a game that has kicked off shows no pregame injury note").not.toContainText(/No star list yet|Injury report not in yet/);
      f.live = reply([row()], { stale: true, last_confirmed_at: agoIso(60_000) });
      await page.clock.fastForward(31_000);
      await expect(c.locator(".text-warn").filter({ hasText: /^Not updating/ })).toHaveCount(1, { timeout: 15_000 });
    });

    test("L10 a refused request (401) follows the app's standing rule: the token is dropped and the sign-in card shows", async ({ page }) => {
      await fake(page, 401);
      await page.goto("/");
      await expect(page.locator("#signin-title")).toBeVisible({ timeout: 15_000 });
    });

    test("L3 the chance line sits after the uncertainty row, away from the model's bar; the score is where the kickoff time was", async ({ page }) => {
      await fake(page);
      await board(page);
      const c = card(page);
      const y = async (text: RegExp) => (await c.getByText(text).first().boundingBox())!.y;
      await expect(c).toContainText("to win now", { timeout: 15_000 });
      expect(await y(/to win now/)).toBeGreaterThan(await y(/^Uncertainty/));
      expect((await c.locator('[aria-hidden="true"]').filter({ hasText: /^Live/ }).first().boundingBox())!.y).toBeLessThan(await y(/^Uncertainty/));
      await expect(c.getByText(/^(8|9|10|11|12|[1-7]):\d\d [AP]M$/), "no kickoff time on a started game").toHaveCount(0);
      if (size.width < 500) expect((await c.boundingBox())!.height, "an ordinary live card keeps the board's density limit").toBeLessThanOrEqual(400);
    });

    test("L4 not updating by age: one failed poll changes nothing; after 120 seconds without a good reply the card says so", async ({ page }) => {
      const f = await fake(page);
      await board(page);
      const c = card(page);
      await expect(c).toContainText(words("Live · Q3 4:12"), { timeout: 15_000 });
      f.live = 503;
      await page.clock.fastForward(31_000);
      await page.clock.runFor(2_000);
      await expect(c, "one failed poll alone").toContainText(words("Live · Q3 4:12"));
      await expect(c).toContainText("ESPN 71%");
      await page.clock.fastForward(95_000);
      await page.clock.runFor(2_000);
      await expect(c).toContainText(words("Not updating · Q3 4:12"));
      await expect(c).toContainText(/Last update \dm ago/);
      await expect(c).not.toContainText(/to win now|71%/);
    });

    test("S2 held: an ended game that leaves the live reply keeps 'Ended' and its score until the week says final", async ({ page }) => {
      const f = await fake(page, reply([row({ state: "post", period: 4, clock: "0:00" })]));
      await board(page);
      const c = card(page);
      await expect(c).toContainText(words("Ended · result pending"), { timeout: 15_000 });
      f.live = reply([]);
      await page.clock.fastForward(125_000);
      await expect.poll(() => f.calls).toBeGreaterThanOrEqual(2);
      await page.clock.runFor(2_000);
      await expect(c).toContainText(words("Ended · result pending"));
      await expect(c.getByText("Ended, result pending: NE 14, KC 21.", { exact: true })).toHaveCount(1);
      await expect(c).not.toContainText("Started");
    });

    test("L5 the game screen: label above the score, reasons for a missing number, when it was checked, what Kalshi is", async ({ page }) => {
      const f = await fake(page, reply([row({ kalshi_home_prob: null })]));
      await page.goto(`/game/?id=${ID}`);
      const main = page.getByRole("main");
      await expect(main).toContainText(words("Live · Q3 4:12"), { timeout: 15_000 });
      await expect(main.getByText("Live score NE 14, KC 21, third quarter, 4:12 left.", { exact: true })).toHaveCount(1);
      await expect(main.getByText("In progress", { exact: true }), "the chip gives way to the label").toHaveCount(0);
      await expect(main.getByRole("heading", { name: "Model pick", exact: true }).locator("..").getByText("Live", { exact: true }), "the pick panel's 'Live' chip (a pregame prediction that is not backfilled) is not shown beside live scores").toHaveCount(0);
      await expect(main).toContainText(words("KC to win now · ESPN 71%"));
      await expect(main).toContainText(words("Kalshi – · no fresh price"));
      await expect(main).toContainText(/Checked (just now|1m ago)/);
      await expect(main).toContainText("Kalshi is a prediction market. The figure is the price of a KC win, not this app's forecast.");
      await expect(main).toContainText("Model win chance before kickoff. It does not change during the game.");
      const label = (await main.locator('[aria-hidden="true"]').filter({ hasText: /^Live/ }).first().boundingBox())!;
      const score = (await main.getByText("21", { exact: true }).first().boundingBox())!;
      expect(label.y, "the label is above the score").toBeLessThan(score.y);
      f.live = reply([row({ home_win_prob: null })]);
      await page.clock.fastForward(31_000);
      await expect(main).toContainText(words("ESPN – · none right now"));
      // the page clock is 62 seconds ahead of this process by now: 3 minutes here is 4 on the page
      f.live = reply([row()], { stale: true, last_confirmed_at: agoIso(3 * 60_000) });
      await page.clock.fastForward(31_000);
      await expect(main).toContainText(words("Not updating · Q3 4:12"));
      await expect(main).toContainText("Last update 4m ago");
      await expect(main.getByText("Last update 4m ago", { exact: true }), "the age is said once: the header's sentence already carries it for a screen reader").toHaveCount(1);
      await expect(main.locator(".text-warn").filter({ hasText: /^Not updating/ }), "not updating is marked, in words and in the warning ink").toHaveCount(1);
      await expect(main).not.toContainText(/to win now|ESPN 71%/);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth), "no sideways scroll").toBeLessThanOrEqual(0);
    });

    test("L4 a phone whose clock is five minutes behind the server still says Live: the age of a reply is measured on one clock", async ({ page }) => {
      await fake(page, reply(), started(), ID, -5 * 60_000);
      await board(page);
      await expect(card(page)).toContainText(words("Live · Q3 4:12"), { timeout: 15_000 });
      await page.clock.runFor(4_000);
      await expect(card(page)).toContainText(words("KC to win now · ESPN 71%"));
      await expect(card(page)).not.toContainText("Not updating");
      await page.goto(`/game/?id=${ID}`);
      await expect(page.getByRole("main")).toContainText("Checked just now", { timeout: 15_000 });
    });

    test("L5 the game screen with no live reply says the game has started, not its kickoff as if it were to come", async ({ page }) => {
      await fake(page, 503);
      await page.goto(`/game/?id=${ID}`);
      const main = page.getByRole("main");
      await expect(main).toContainText("No live score right now", { timeout: 15_000 });
      await expect(main).toContainText("Started");
      await expect(main).not.toContainText(/to win now|Not updating|Checked/);
    });

    test("L6 never moves a pick: with and without live numbers the model's pick, its chance, the label, the points and the pick buttons are the same", async ({ page }) => {
      const read = async () => {
        const c = card(page);
        await expect(c).toContainText("Pregame model pick", { timeout: 15_000 });
        return {
          model: await c.getByText("Pregame model pick").locator("..").innerText(),
          label: await c.getByTestId("pick-label").innerText(),
          points: await c.getByLabel("Points for NE at KC").inputValue(),
          buttons: await c.getByRole("group", { name: "Your pick: NE at KC" }).evaluate((g) => [...g.querySelectorAll("button")].map((b) => `${b.textContent}|${b.disabled}|${b.getAttribute("aria-pressed")}`)),
        };
      };
      await fake(page, 503);
      await board(page);
      const without = await read();
      expect(without.model).toContain("87%");
      await page.unroute("**/api/live");
      await page.route("**/api/live", (route) => route.fulfill({ json: reply([row({ home_win_prob: 0.03, home_score: 0, away_score: 35 })]) }));
      await page.reload();
      await expect(card(page)).toContainText("ESPN 3%", { timeout: 15_000 });
      expect(await read()).toEqual(without);
    });

    test("L11 text from the feed is text: a clock full of markup is shown as letters and reaches no attribute", async ({ page }) => {
      const nasty = `"><img src=x onerror=alert(1)>`;
      await fake(page, reply([row({ clock: nasty })]));
      await board(page);
      const c = card(page);
      await expect(c).toContainText(nasty, { timeout: 15_000 });
      await expect(c.locator("img[src='x']")).toHaveCount(0);
      const inAttribute = await c.evaluate((el, text) => [...el.querySelectorAll("*")].some((e) => [...e.attributes].some((a) => a.value.includes(text))), "onerror");
      expect(inAttribute).toBe(false);
    });

    for (const scheme of ["dark", "light"] as const) {
      test(`L9 accessibility (${scheme}): no serious or critical axe issue with a live game on the board and on the game screen`, async ({ page }) => {
        await page.emulateMedia({ colorScheme: scheme, reducedMotion: "reduce" });
        await fake(page, reply([row()], { stale: false }));
        for (const path of ["/", `/game/?id=${ID}`]) {
          await page.goto(path);
          await expect(page.getByText(/to win now/).first()).toBeVisible({ timeout: 15_000 });
          const { violations } = await new AxeBuilder({ page }).analyze();
          expect(violations.filter((v) => v.impact === "serious" || v.impact === "critical").map((v) => `${v.id}: ${v.nodes[0]?.target}`), path).toEqual([]);
        }
      });
    }
  });
}

for (const width of [393, 320]) {
  test(`L8 phone fit at ${width} px: going live adds no height to the worst card, nothing in the live block is cut, no sideways scroll`, async ({ page }) => {
    await page.setViewportSize({ width, height: 852 });
    const live = reply([row({ game_id: WORST, home_team: "MIA", away_team: "BUF", home_score: 31, away_score: 34, period: 4, clock: "12:34", home_win_prob: 0.997, kalshi_home_prob: null })]);
    const alerts = { qb_alerts: ["BUF QB Jo Thrower: Out", "MIA QB Second Passer: Doubtful"] };
    const f = await fake(page, live, { status: "scheduled", kickoff_utc: new Date(T0 + 60_000).toISOString(), time_tbd: false, locked: false, ...alerts }, WORST);
    await page.unroute("**/api/{weeks,games}/**");
    await page.route("**/api/{weeks,games}/**", async (route) => {
      const res = await route.fetch();
      const body = await res.json();
      for (const g of body.games ?? [body]) {
        if (g.game_id !== WORST) continue;
        Object.assign(g, f.game);
        if (g.prediction) Object.assign(g.prediction, { upset_flags: ["Stats model and market differ"], change_note: "Changed: the line moved two points toward MIA since Tuesday and the BUF quarterback is out" });
      }
      await route.fulfill({ response: res, json: body });
    });
    await page.goto("/");
    const c = card(page, "BUF", "MIA");
    await expect(c).toContainText("What changed", { timeout: 15_000 });
    const before = (await c.boundingBox())!.height;
    f.game = { ...started(), ...alerts };
    await page.clock.fastForward(125_000);
    await expect(c).toContainText(words("Live · Q4 12:34"), { timeout: 15_000 });
    await expect(c).toContainText("34");
    await expect(c).toContainText("31");
    await expect(c).toContainText(words("to win now · ESPN"));
    // the worst card (every warning at once) is over the board's 400 px rule before kickoff too: live must not make it taller
    if (process.env.SHOT_DIR) await c.screenshot({ path: `${process.env.SHOT_DIR}/l8-${width}.png` });
    expect((await c.boundingBox())!.height, `no taller live than before kickoff (${before} px)`).toBeLessThanOrEqual(before);
    // the visible parts only: the screen-reader sentence also starts with "Live"
    for (const text of [/^Live/, /to win now/]) {
      const part = c.locator('[aria-hidden="true"]').filter({ hasText: text }).first();
      await expect(part).toBeVisible();
      expect(await part.evaluate((e) => e.scrollWidth <= e.clientWidth), `${text} is whole`).toBe(true);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth), "no sideways scroll").toBeLessThanOrEqual(0);
  });
}
