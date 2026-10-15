# Step 18l: value ratings on screen — step log (lane web)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · coordinator Jim · builder Ryan (Codex) · integrator god.
Worktree `.claude/worktrees/lane-web`, branch `lane/web`, fast-forwarded to origin/main `521e8ad` (13b landed) under
`res:git-integrate`. Coord task #38. Grant: lanes.md lane web, 2026-10-15 04:58 UTC.

## 1. PLANNING

**Goal (god b0a8c6).** Finish step 18 by showing the 18i value rating. API: the rating per market (win, spread, total
where prices exist) in the game reply, filled from `load_snapshots` + `rate_price`. Web: show it on the game page with the
PLAN 18j wording "not yet shown to beat the market".

**What exists (read on `521e8ad`).**
- `nflpi.value.load_snapshots(session, game_id, market_type, as_of=)`: per book, the newest complete pair of sides at
  or before `as_of`. The spread line is the HOME spread on both selections; the total line is the total on both.
- `nflpi.value.rate_price(snapshot, probs, now=)`: `betting_advice` with no rubric, so `NO_BET` for a stale price
  (older than `value_max_price_age_minutes`, default 30) or nonpositive expected value, else `UNRATED`
  (`NO_VALIDATION_HISTORY`). The note says "Price seen at ... UTC by <book>; it may no longer be offered."
- Chances: the win market uses the game's newest prediction `home_win_prob` (the number the page leads with; a tie
  counts as a loss, push 0). Spread and total use the newest prediction's `features.simulation` cover and over chances,
  which hold only at the simulator's own line (`home_spread`, `total`).

**Done when.** The spec below holds: `backend/tests/test_value_api.py` and `apps/web/e2e/value18l.spec.ts` green on a
fresh build; ruff and typecheck 0; Dwight PASS; a fresh critic PASS; PR CI runs the full suite (D71).

**Tier T2.** Prior decisions: D74 (the simulator never picks); CLAUDE.md (never invent data; missing shown as missing);
PLAN 18i "no price is ever shown as still available"; PLAN 18j wording; the 18j cache lesson (an old cached game reply
has no `value_ratings`).

**Pre-flight.** (1) Problem: the 18i ratings exist but no screen shows them, so the owner cannot see whether a price has
value. (2) Why now: 18i, 18j and 18k landed; this is the last piece of step 18. (3) Scope: one list on the game reply,
one section on the game page; cut: ratings on the week board, prices at lines the simulator did not use, a rubric
(stars stay off until PLAN 3.4). (4) Success: for each stored book price the owner sees its status and why
(qualitative). (5) Two-way door: add-only fields, no migration.

**Assumptions.** validated: shapes and rules (code read above). assumed: a price at a line other than the simulator's
is left out rather than rated against the wrong line (told god in the done report). unknown: none.

**Instrumentation.** N/A. **Skills.** grep/read of `value/`, `picks/advice.py`, `api/readmodels.py:game_detail` pinned
the seam; `/jevgrep` N/A (exact symbols); TDD: pytest at `game_detail` and the route, Playwright at the page;
`/ponytail` in each work order; Design Gauntlet: one new section in an existing page; security review: yes (database
query, new reply fields).

**Test data.** Backend: one made-up game, prediction and book prices in the test DB. Web: the real game reply with
`value_ratings` replaced, typed against the wire type. Made-up values; no names.

## 2. SPECIFICATION (frozen before production code)

API (`GameDetail.value_ratings: list[ValueRatingOut]`, default `[]`). Each item: `market_type` (moneyline, spread,
total), `selection`, `sportsbook`, `line`, `price`, `observed_at`, `status` (RATED, UNRATED, NO_BET), `stars`,
`expected_value`, `reasons`, `note`, all from `rate_price` on the snapshots of `load_snapshots(..., as_of=now)`.
- A1 a price older than the max age: `NO_BET`, `STALE_PRICE` in reasons, no stars, the "may no longer be offered" note.
- A2 nonpositive expected value: `NO_BET`, reasons exactly `NONPOSITIVE_EV`.
- A3 positive value with no validation history: `UNRATED`, `NO_VALIDATION_HISTORY`, no stars; expected value from the
  prediction's win chance; book, price, line as stored. Nothing is `RATED`.
- A4 spread and total are rated only at the simulator's line; a book at another line is left out. A push refunds.
- A5 no simulation: only the win market is rated.
- A6 empty list with no prediction, after kickoff, or with no prices.
- A7 `GET /api/games/{id}` serves the list.
- A8 (added after WO1, coordinator finding: the engine stores simulator chances rounded to 4 places, so a set can sum
  to 0.9999 and `SettlementProbs` raised, a 500 for the whole game page): a set within 0.001 of 1 is scaled to sum to 1
  and rated; a set further off, or with a value outside [0, 1], leaves that price out. The game reply never fails. Severity corrected by Dwight: the real engine path stores k/10000 chances that sum
  exactly, so this is reachable only with another simulation count or an older stored run (his V1, MEDIUM).
  A8 correction (Ryan via god 80152c): the first A8 used sums 0.9987/1.0013, outside the 0.001 band its own spec
  names; three 4-place values are off by at most 0.00015, so A8 now uses 0.5499/0.5501 (sums 0.9999/1.0001). Test-only.

Web (`#value`, title "Value", a "Value" section tab after Simulator):
- W1 the line "not yet shown to beat the market"; per price: market (Win, Spread, Total), side, price (+120), book,
  status (Unrated), "Expected value +32%", the server note word for word.
- W2 a stale price: "No bet", "price too old to rate", the note; the word "available" never appears.
- W3 spread sides read "BUF -3.5" / "MIA +3.5", totals "Over 47.5" / "Under 47.5"; NONPOSITIVE_EV = "no value at this
  price"; RATED with stars = "3 of 5 stars"; an unknown reason code shows as the code.
- W4 an empty or absent list: "No book prices to rate for this game."
- W5 markup in a book name renders as text.
- W6 at 320 px: no serious axe finding in `#value`, no sideways scroll.

Gate: `uv run pytest tests/test_value_api.py tests/test_value.py`, `uvx ruff check nflpi tests`, `npm run typecheck`,
`e2e/value18l.spec.ts` plus `e2e/sim18j.spec.ts` and `e2e/check18k.spec.ts` on a fresh build; PR CI the full suite.

**Red.** Backend: 9 failed (`'GameDetail' object has no attribute 'value_ratings'`, A7 `KeyError`). Browser
(`v18l-red`): the build stops on `ValueRatingOut` missing from the wire types (expected until `gen:api`), and against
the last build 7 of 7 fail on `#value` not found.
