# Step lock-lead: picks lock 15 minutes before kickoff + 19a SEA@DEN fresh-line fix — step log (lane web)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · coordinator Jim · builder Ryan (Codex) · integrator god.
Worktree `.claude/worktrees/lane-web`, branch `lane/web-lock15` from origin/main `17ada83` (upstream unset).
Grant: god 015f8e + addendum 1ff282 (2026-10-16). Database tests prove in draft-PR CI (Docker stays off on the Mac).
Deadline: land by Saturday (owner: before Sunday 1 pm ET games). Owner said god may deploy after landing.

## 1. PLANNING

**Goal.** (B) Yahoo locks picks 15 minutes before kickoff (owner). The app locks at kickoff − lead everywhere: pick
and points edits, the on-screen lock, the sheet freeze, prediction alerts, and the game-day reminder (counts down to the
lock, god b2f114 (a)). The fresh-line refresh targets move to −90 and −30 so the last refresh lands 15 minutes before
the lock. The lead is one setting (default 15). (A) 19a did not switch to the Kalshi line for SEA@DEN on 2026-10-16.
**Done when:** every clause below is green locally (pure) and in draft-PR CI (database, web, e2e), critic and Dwight
PASS.
**Tier T2** (user-facing behaviour). Pre-flight: problem: the app said "open" for 15 minutes when Yahoo was already
locked, and a fresh market line never reached the picks; why now: owner, Sunday games; scope: one lock rule + one
setting + three fresh-line rule fixes, no migration; success: picks lock and the last refresh land before Yahoo's lock,
a fresh Kalshi line 1+ point away from nflverse reaches the prediction; reversibility: two-way (setting, code).
**Assumptions.** validated: every lock check goes through `sheet.is_locked` except `sheet.finalize` (SQL) and
`push.alert_prediction_changes` (its own check); `live/store.add_quote` stores a quote only when its price changes.
assumed: Yahoo's 15 minutes is fixed per game (setting covers a change).
**A: investigation** (god ran read-only Q0-Q5 on the PC; results `hive/research/nfl-pickem/19a-sea-den-queries.txt`,
game `2026_06_SEA_DEN`, kickoff 00:15 UTC). Kalshi was polled every 2 minutes, but this game's pregame price changed
only twice (22:15:04 at 0.4350, 00:09:26 at 0.4307); nflverse moved at 22:37:26 (0.4279) and 00:09:36 (0.4170);
refreshes ran at 22:47 and 23:57 near the targets. Three causes:
- **C1** quotes are stored only on a price change, so `fetched_at` is when the price was first seen; the 30-minute
  freshness check dropped a stable, still-current price (32 min old at 22:47, 102 min at 23:57).
- **C2** a quote had to be newer than the nflverse line, but nflverse's time is our ingest time; every refresh ingests
  nflverse just before predicting, so a moved nflverse line beat every quote (00:10: by 10 seconds).
- **C3** the churn guard compared the quote with the previous row's line (0.4279); when that row was nflverse the
  engine then used the current nflverse line (0.4170), so a quote 1.4 points from the line in use was dropped.
**Decisions.** D80 (owner/integrator, god b2f114): drop the "newer than nflverse" rule (C2). Reminders count down to
the lock; CSV import backfill unchanged (god 015f8e). C1 fix as proposed (seen_at = latest ok poll of that source).
C3 is in the granted `fresh_line.py`; reported to god with this log.
**Skills.** grep/graft pinned each seam (sheet.is_locked callers, finalize SQL, push checks, clock.ts callers,
add_quote); TDD (`tests/test_lock_lead.py`); `/ponytail` per work order; security review: Dwight (user input lock
rule, database reads).

## 2. SPECIFICATION (frozen before production code)

- L-P1 `Settings.pick_lock_minutes`: int, default 15, 0..120.
- L-P2 `sheet.is_locked(game, now)`: final, or (not postponed, known time, `kickoff − lead <= now`). The lead follows
  the setting.
- L-P3 `fresh_line` targets are `(90 min, lead + 15 min)`: −90 and −30 by default.
- L-P4 (C2, C3; SEA@DEN numbers) at 00:10:28 Kalshi 0.4307 (seen 00:09:26) wins over nflverse 0.4170 (ingested
  00:09:36) with previous row nflverse 0.4279; at 23:57 Kalshi 0.4350 vs nflverse 0.4279 keeps nflverse (under a
  point, by design); the churn guard compares a quote with the current nflverse line when the previous row was
  nflverse (a quote 1.5 points from nflverse wins even if 0.5 from the older row).
- L-D1 (DB) a pick or points change at kickoff − 14 min is 409 and the detail says "15 minutes before kickoff"; at
  −16 min it is allowed.
- L-D2 (DB) the week view marks the game `locked`; `/api/meta` has `pick_lock_minutes` (the one new API field).
- L-D3 (DB) `sheet.finalize` freezes a game at kickoff − 15, not at − 16.
- L-D4 (DB) the game-day reminder window is [lock − reminder_minutes, lock); its text names the lock time ("12:45")
  and says lock.
- L-D5 (DB) no prediction alert for a game past its lock (−10 min none, −20 min sent).
- L-D6 (DB, C1) a stored Kalshi pregame quote's `seen_at` is the latest ok `market_quotes` poll of that source after
  it was stored and not after now; a failed poll does not count; with no such poll a 97-minute-old price is not fresh.
- L-web `clock.isLocked` uses the same lead (from meta); week board, game card and pick buttons follow it; wording
  "Locked at kickoff" becomes the lead wording (pick buttons, 409 toast, and the offline-queue 409 toast in
  `lib/sync.ts:239` with pwa P21, granted by god 24b286). Proven by typecheck + e2e in CI.
- Expected test expectation edits (approved 1ff282, listed at landing): `test_fresh_line.py` F8 (−20 → −30),
  `test_alerts.py` N2 window, `test_api.py` lock test, e2e `sheet.spec.ts` / `pwa.spec.ts` wording.

Gate: `uv run pytest --noconftest -q tests/test_lock_lead.py -k test_p` (7 pure) locally; `uvx ruff check nflpi
tests`; `npm run typecheck`; full suite, web and e2e in draft-PR CI (D71).
**Red (local, pure):** `6 failed, 1 passed` — P1 `KeyError: 'pick_lock_minutes'`; P2 locked at −15 is False; P2b no
setting; P3 the −20 target (16 min); P4 `(0.417, 'nflverse')` (C2); P4c `(0.61, 'nflverse')` (C3). P4b passes (the
guard it pins holds today). DB tests run in CI.
**Red (CI, draft PR #50, run 38834921703 on `3f84d34`, backend job 116761779518):** `12 failed, 2453 passed,
1 skipped`; the 12 are exactly `test_lock_lead.py` (P4b passes by design), each for its intended reason: D1 `200 ==
409`; D2 `locked` False; D3 no sheet entry at −15; D4 reminder `0 == 1` at lock − 74; D5 alert sent at −10; D6
`KeyError` (the stable price is dropped). docker, web, e2e green.

## 3. IMPLEMENTATION

Provider: Codex (Ryan), Build Ladder rung 1; coordinator commits his diffs.
- **WO1** (all items) → `e5571b6`. Review: only granted files (+ `lib/sync.ts:239` wording, god 24b286); test edits
  are expectation-only: `test_fresh_line.py` (F2 `older_than_nflverse` now uses the quote per D80; F8 and D4 −30
  target), `test_alerts.py` (N2 window and titles, pre-lock alert time), `test_api.py` (test name), e2e
  `sheet.spec.ts` U1c and `pwa.spec.ts` P5/P21 (lock time and wording). `openapi.json` + `api-types.ts` regenerated
  with the cached openapi-typescript CLI (`npm run gen:api` stalled offline); not hand-edited. Proof (coordinator):
  7 pure passed; `test_fresh_line -k "not test_d"` 21 passed; ruff clean; `npm run typecheck` clean; `git diff
  --check` clean. DB, web and e2e: CI below.
