# Step 19a: a fresh pregame line in the predictions before kickoff — step log (lane web)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · coordinator Jim · builder Ryan (Codex) · security Dwight ·
integrator god. Worktree `.claude/worktrees/lane-web`, branch `lane/web-19a` from origin/main `325f541` (lane/web carries
PR #46; rebase onto main after it merges). Coord task #40. Grants: god 57e1b4 and 44fe51 (`predictions/fresh_line.py`
new; `engine.py` load_frame, the two feature keys and the refresh_predictions ChangeEvent block; `jobs.py`
next_interval; `tests/test_fresh_line.py` new; this log and evidence). No web, no migration, no extra Odds API credits.

## 1. PLANNING

**Goal (god bf613c, ba7b86).** First deliverable of step 19: a fresh line before each kickoff window (after inactives
about 90 minutes out, and 15-30 minutes out). Owner: picks and points lock per game at its kickoff.

**Found (main `325f541`).** The prediction's market input is the no-vig moneyline of the newest `MarketSnapshot`, which
only nflverse schedule ingestion writes (`ingestion/service.py:94`). Kalshi pregame quotes are already polled free every
120 s from 2 h before kickoff (`live_worker.py` KALSHI_EVERY/KALSHI_LEAD) and Odds API h2h every 6 h within 24 h, both into
`market_quotes` (home-side probability mapped to the game's home team at save: `_save_kalshi` by team code, `_save_odds`
by team name). Neither reaches the predictions. Predictions re-run every 20 min inside 6 h, measured after each cycle.
Today a line-driven row can push through a label change or a 7-point move (`notify/push.alert_prediction_changes`).

**Tier T2.** Prior decisions: CLAUDE.md data integrity (predictions insert-only; a new row only when inputs change; the
recommendation is the last snapshot before kickoff), D71 (PR CI is the full gate), D72, god's three guards.
**Pre-flight.** (1) Problem: the model prices games on a line that can be hours old at lock time. (2) Why now: owner
card; picks lock per game. (3) Scope: use the free quotes already stored; cut: extra Odds API pulls (owner question),
showing the line source on screen. (4) Success: the newest prediction before each kickoff uses a quote under 30 minutes
old when one exists. (5) Two-way door (no schema change; one constant each).

**Assumptions.** validated: data paths above. unknown: whether fresher lines raise points per week; no stored quote
history exists to bench it, so the argument is that the model's market weight was fit on closing lines and a quote
minutes before kickoff is closer to that than the nflverse line. A later step-19 bench can measure it once our own
snapshots cover a season.

**Skills.** grep/read pinned the seams; `/jevgrep` N/A; TDD (pure functions locally, database clauses in PR CI);
`/ponytail` in each work order; Design Gauntlet N/A; security review: Dwight (database read, alert path).

## 2. SPECIFICATION (frozen before production code)

`backend/nflpi/predictions/fresh_line.py` (pure unless noted): `Line(prob, source, seen_at)`, `Quote(source, home_prob,
seen_at)`, `FRESH_MAX_AGE = 30 min`, `SANITY_GAP = 0.20`, `CHURN_GAP = 0.01`.
- F1 `choose_line(nflverse, quotes, previous, now=, kickoff=)` returns `(line, reason)`; a pregame quote seen at or before
  `now`, before kickoff, at most 30 minutes old, with a probability strictly inside (0, 1), and newer than the nflverse
  line is used, with its source and seen time.
- F2 otherwise the nflverse line (after kickoff, older than 30 min, from the future, not a probability, NaN, older than
  the nflverse snapshot).
- F3 sanity (guard 1): a quote 0.20 or more from the nflverse probability is refused (`reason = "sanity"`; the engine
  logs it once per game per run); with no nflverse probability the quote is used.
- F4 churn (guard 2): when the chosen or the previous line is a fresh quote and it is within 0.01 of the previous line,
  the previous line is returned unchanged (no new row). F4b nflverse-only moves behave as today.
- F5 the newest fresh quote wins; equal times go by source name.
- F6 `fair_moneylines(p)` gives home/away American odds whose no-vig probability is exactly p (the frame keeps its
  moneyline columns; the quote's probability flows through the existing feature code).
- F7 `rank_changed(old, new, game_id)`: rank by max(p, 1 - p), descending, game id breaks ties (as
  `picks.pool.confidence_pool`); True when the game's position changes.
- F8 `until_next_target(kickoffs, now)`: time to the earliest of kickoff - 90 min and kickoff - 20 min still ahead, plus
  1 minute; None when there is none.

Wiring (database; PR CI):
- D1 `engine.load_frame`/`refresh_predictions` use the chosen fresh quote: `market_home_prob` is its probability and the
  features carry `market_source` and `market_seen_at` (only when a fresh quote is used, so rows on nflverse keep their
  hash and deploying writes no new rows).
- D2 a live quote, a quote older than 30 minutes, or one 0.20+ from nflverse leaves the prediction on nflverse.
- D3 guard 3: a new row whose changed features are only the market keys creates a ChangeEvent only if the pick flips or
  the game's points rank in its week changes (`fresh_line.rank_changed` over the week's newest predictions); an unchanged
  quote writes no row. D3b a line that flips the pick is alerted. Non-line changes keep today's behaviour.
- D4 `jobs.next_interval` inside 6 h waits `min(20 min, until_next_target)`.

Gate: local `uv run pytest tests/test_fresh_line.py -k "test_f1 or ... test_f8" --noconftest` (pure); the whole file and
the full suite on a draft PR's CI from `lane/web-19a` (Mac test database off; Docker stays off: god 57e1b4).
**Red (local, pure):** 18 failed (ImportError: no `fresh_line`), 7 database tests left for CI.
