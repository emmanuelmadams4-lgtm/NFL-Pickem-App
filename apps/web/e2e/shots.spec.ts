import { mkdir } from "node:fs/promises";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";

/**
 * Design evidence for the step log, not a gate: phone screenshots of the main screens.
 * Skipped unless SHOT_TAG is set:  SHOT_TAG=before npx playwright test e2e/shots.spec.ts
 */
const TAG = process.env.SHOT_TAG;
const DIR = path.resolve(__dirname, "../../../docs/gauntlet/logs/step-6-evidence/shots");
const TOKEN = "e2e-token";
const AUTH = { Authorization: `Bearer ${TOKEN}` };

test.skip(!TAG, "set SHOT_TAG to capture");
test.use({ hasTouch: true, serviceWorkers: "block" });

async function shoot(page: Page, name: string) {
  await mkdir(DIR, { recursive: true });
  await page.waitForLoadState("networkidle");
  await page.screenshot({ path: path.join(DIR, `${TAG}-${name}.png`) });
}

for (const [w, h] of [[393, 852], [320, 568]] as const) {
  test(`shots ${w}x${h}`, async ({ page, request }) => {
    await page.setViewportSize({ width: w, height: h });
    const meta = await (await request.get("/api/meta", { headers: AUTH })).json();
    const week = await (await request.get(`/api/weeks/${meta.current_season}/${meta.current_week}`, { headers: AUTH })).json();
    const games = week.games as { game_id: string; status: string }[];
    const open = games.find((g) => g.status === "scheduled") ?? games[0];
    const final = games.find((g) => g.status === "final") ?? games[0];
    await page.addInitScript((t) => localStorage.setItem("nflpi_token", t), TOKEN);

    await page.goto("/");
    await expect(page.getByTestId("game-card").first()).toBeVisible({ timeout: 15_000 });
    await shoot(page, `week-${w}`);
    await page.screenshot({ path: path.join(DIR, `${TAG}-week-full-${w}.png`), fullPage: true });
    for (const [name, url] of [["game-open", `/game/?id=${open.game_id}`], ["game-final", `/game/?id=${final.game_id}`], ["sheet", "/sheet/"], ["results", "/performance/"], ["settings", "/settings/"]] as const) {
      await page.goto(url);
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible({ timeout: 15_000 });
      await shoot(page, `${name}-${w}`);
    }
  });
}
