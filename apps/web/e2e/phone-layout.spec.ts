import { expect, test, type Page, type Route } from "@playwright/test";

/**
 * Step 6 gate, phone layout (docs/gauntlet/logs/step-6.md, L1-L7): the polish carried from step 3,
 * measured at the owner's iPhone size (393x852) and the smallest phone (320x568).
 */
test.use({ viewport: { width: 393, height: 852 }, hasTouch: true, serviceWorkers: "block", contextOptions: { reducedMotion: "reduce" } });

const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };
const LIME = "rgb(198, 241, 53)"; // --color-accent
const NOTE = "Changed: QB status. BUF win chance 54% → 49%.";

const signIn = (page: Page) => page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);
const cards = (page: Page) => page.getByTestId("game-card");
const tabBarTop = (page: Page) => page.getByRole("navigation", { name: "Primary" }).last().evaluate((n) => n.getBoundingClientRect().top);

async function openWeek(page: Page) {
  await signIn(page);
  await page.goto("/");
  await expect(cards(page).first()).toBeVisible({ timeout: 15_000 });
  await page.waitForLoadState("networkidle");
}

async function openGame(page: Page) {
  await signIn(page);
  const meta = await (await page.request.get("/api/meta", { headers: AUTH })).json();
  const week = await (await page.request.get(`/api/weeks/${meta.current_season}/${meta.current_week}`, { headers: AUTH })).json();
  await page.goto(`/game/?id=${week.games[0].game_id}`);
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible({ timeout: 15_000 });
  await page.waitForLoadState("networkidle");
}

/** Give every prediction in API responses the note the engine writes when a pick moves. */
async function withChangeNote(page: Page) {
  await page.route("**/api/{weeks,games}/**", async (route: Route) => {
    const res = await route.fetch();
    const body = await res.json();
    for (const g of body.games ?? [body]) if (g.prediction) g.prediction.change_note = NOTE;
    await route.fulfill({ response: res, json: body });
  });
}

test("L1 density: the first game's pick buttons are on the first screen and no card is taller than 400px", async ({ page }) => {
  await openWeek(page);
  const pickBottom = await cards(page).first().getByRole("group", { name: /^Your pick:/ }).evaluate((g) => g.getBoundingClientRect().bottom);
  expect(pickBottom, "first pick buttons end above the tab bar without scrolling").toBeLessThanOrEqual(await tabBarTop(page));
  const heights = await cards(page).evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().height)));
  expect(Math.max(...heights), `card heights ${heights.join(", ")}`).toBeLessThanOrEqual(400);
});

test("L2 smallest phone: no summary caption wraps past two lines and nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 });
  await openWeek(page);
  const lines = await page.getByRole("region", { name: "Week summary" }).locator("dt, dd").evaluateAll((els) =>
    els.filter((e) => e.getBoundingClientRect().height > 0).map((e) => [e.textContent, Math.round(e.getBoundingClientRect().height / parseFloat(getComputedStyle(e).lineHeight))] as const),
  );
  expect(lines.filter(([, n]) => n > 2), "captions over two lines").toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
});

test("L3 section tabs: the row fades at the right edge while more tabs are off screen", async ({ page }) => {
  await openGame(page);
  const row = page.getByRole("navigation", { name: "Sections" }).getByRole("list");
  const m = await row.evaluate((ul) => ({ more: ul.scrollWidth > ul.clientWidth, mask: getComputedStyle(ul).maskImage || getComputedStyle(ul).webkitMaskImage }));
  expect(m.more, "the seeded game page has more tabs than fit").toBe(true);
  expect(m.mask, "mask-image on the tab row").toMatch(/gradient/);
});

test("L4 lime means mine: the 'next kickoff' note is not lime", async ({ page }) => {
  await openWeek(page);
  const note = page.getByText(/next kickoff/).first();
  await expect(note).toBeVisible();
  expect(await note.evaluate((e) => getComputedStyle(e).color)).not.toBe(LIME);
  // It sits on the dark card body beside the date, so it reads like the date (critic round 1: it was near-black on dark).
  expect(await note.evaluate((e) => getComputedStyle(e).color), "same ink as the date beside it").toBe(await note.evaluate((e) => getComputedStyle(e.parentElement!).color));
});

test("L5 disabled is not lime: no disabled button on the game page keeps the lime fill", async ({ page }) => {
  await openGame(page);
  const lime = await page.locator("button:disabled").evaluateAll((els, c) => els.filter((b) => getComputedStyle(b).backgroundColor === c).map((b) => b.textContent), LIME);
  expect(await page.locator("button:disabled").count(), "the seeded server has no AI keys, so AI buttons are disabled").toBeGreaterThan(0);
  expect(lime).toEqual([]);
});

test("L6 one label: a changed pick reads 'What changed:' once, on the card and on the game page", async ({ page }) => {
  await withChangeNote(page);
  await openWeek(page);
  await expect(cards(page).first()).toContainText("QB status");
  await expect(cards(page).first()).not.toContainText(/What changed:\s*Changed:/);
  await openGame(page);
  await expect(page.getByText(/QB status/).first()).toBeVisible();
  await expect(page.locator("main")).not.toContainText(/What changed:\s*Changed:/);
});

test("L7 keyboard, backwards: Shift+Tab never leaves a focused pick button under the top bar", async ({ page }) => {
  await openWeek(page);
  const barBottom = await page.locator("header").first().evaluate((h) => h.getBoundingClientRect().bottom);
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await page.getByRole("navigation", { name: "Primary" }).last().getByRole("link").last().focus();
  const hidden: string[] = [];
  let seen = 0;
  for (let i = 0; i < 80 && seen < 8; i++) {
    await page.keyboard.press("Shift+Tab");
    const f = await page.evaluate(() => {
      const e = document.activeElement as HTMLElement;
      return { pick: !!e.closest('[role="group"][aria-label^="Your pick:"]'), name: e.getAttribute("aria-label") ?? e.textContent ?? "", top: e.getBoundingClientRect().top };
    });
    if (!f.pick) continue;
    seen++;
    if (f.top < barBottom) hidden.push(`${f.name} top ${Math.round(f.top)} < bar ${Math.round(barBottom)}`);
  }
  expect(seen, "pick buttons reached with Shift+Tab").toBeGreaterThan(0);
  expect(hidden).toEqual([]);
});

for (const [w, h] of [[393, 852], [320, 568]] as const) {
  test(`L8 week arrows at ${w}: previous and next week are real 44px bordered buttons`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await openWeek(page);
    for (const name of ["Previous week", "Next week"]) {
      const b = page.getByRole("button", { name }).locator("visible=true");
      await expect(b, name).toHaveCount(1);
      const m = await b.evaluate((e) => ({ w: e.getBoundingClientRect().width, h: e.getBoundingClientRect().height, border: parseFloat(getComputedStyle(e).borderTopWidth), color: getComputedStyle(e).borderTopColor }));
      expect(Math.min(m.w, m.h), `${name} ${m.w}x${m.h}`).toBeGreaterThanOrEqual(44);
      expect(m.border, `${name} border`).toBeGreaterThanOrEqual(1);
      expect(m.color, `${name} border color`).not.toMatch(/rgba\(0, 0, 0, 0\)|transparent/);
    }
  });

  test(`L9 first screen at ${w}: the Yahoo sheet link and the data's age are visible without scrolling either way`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: h });
    await openWeek(page);
    const bar = await tabBarTop(page);
    for (const item of [page.getByRole("link", { name: /Yahoo sheet/ }), page.getByText(/^Updated /)]) {
      const visible = item.locator("visible=true");
      await expect(visible).toHaveCount(1);
      const r = await visible.evaluate((e) => e.getBoundingClientRect().toJSON());
      expect(r.left, "inside the left edge").toBeGreaterThanOrEqual(0);
      expect(r.right, "inside the right edge").toBeLessThanOrEqual(w);
      expect(r.bottom, "above the tab bar").toBeLessThanOrEqual(bar);
    }
  });
}

test("L10 section tabs, scrolled to the end: the last tab is clear of the fade", async ({ page }) => {
  await openGame(page);
  const row = page.getByRole("navigation", { name: "Sections" }).getByRole("list");
  const gap = await row.evaluate((ul) => {
    ul.scrollLeft = ul.scrollWidth;
    return ul.getBoundingClientRect().right - ul.lastElementChild!.getBoundingClientRect().right;
  });
  expect(gap, "space between the last tab and the row's right edge").toBeGreaterThanOrEqual(40);
});

test("L11 true captions: with nothing graded yet, the Model cell says so and does not say there are no live picks", async ({ page }) => {
  await openWeek(page);
  const caption = await page.getByTestId("kpi-model").evaluate((n) => (n as HTMLElement).innerText);
  expect(caption, "the cards below each show a live model pick").not.toMatch(/no live picks(?! graded)/i);
  expect(caption).toMatch(/graded/i);
});
