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
**Red in CI** (draft PR #47, run 38763658932, backend job 116521164110, on `dbdb27b`): 22 failed, 2,366 passed, 1 skipped.
The 18 F tests fail on `ImportError` (no `fresh_line`); D1 (market prob stays nflverse 0.420 vs quote 0.470), D3
(import), D3b (pick unchanged 'LV') and D4 (20 min instead of 11) fail for the intended reasons; the three D2 cases pass
before the build because they assert today's behaviour (nflverse kept).

## 3. IMPLEMENTATION

- WO1 (Ryan, try 1): `fresh_line.py` (new), `engine.load_frame(session, now)` fresh-quote choice, the two feature keys,
  the line-only ChangeEvent rule, `jobs.next_interval` targets. Coordinator rerun locally: 18 pure tests passed, ruff 0.
  Database clauses: PR CI on the pushed commit (below).
- **CI on `aa5a7a1`** (run 38764870378, backend job 116525334435): 2 failed, 2,386 passed, 1 skipped. D1, D2 (x3), D4
  green. D3 failed for a real defect: an unchanged quote wrote a new row, because the first run used the raw quote
  probability and the churn rule then kept the previous line rebuilt from the 4-place `market_prob`, so `market_logit`
  differed in its 4th digit and the hash changed. D3b failed on its own precondition (a 0.19 shift did not flip the
  fixture model's pick): a test defect.
- Spec additions (frozen before the fix): F1b quote probabilities are used rounded to 4 places (the precision the
  features keep). F3 now also requires `choose_line` to return the refused quote itself (second value), so the engine
  logs it without re-deriving it (the cleanup finding). D3b sets `SANITY_GAP = 1.0` (F3 covers the gap) and uses a
  decisive 0.03/0.97 quote so the pick flips. Red locally: F1b and F3 fail; 17 pure tests pass. → WO2.
- WO2 (Ryan, try 1) `759c455`: quote probabilities rounded to 4 places; `choose_line` returns `(line, refused quote)`;
  the engine logs the returned quote. Coordinator rerun: 19 pure tests passed, ruff 0.
- **CI on `759c455`** (run 38766072714, backend job 116529470545): 1 failed, 2,388 passed, 1 skipped. D3b now green
  (the decisive line flips the pick and is alerted). D3 failed on a test defect: its second quote had the same source
  and the same `fetched_at` as the first, so the newest-then-source tie kept the first quote and nothing changed. Test
  fix `c3d9775` (second quote 3 minutes old, so it is newer). No production change.
- Moved onto origin/main `62ecf35` (18m landed) under `res:git-integrate`: clean, 7 commits, HEAD `0297dfb`. Pure
  tests 19 passed (`--noconftest`; the DB clauses run in PR CI), ruff 0. Pushed to draft PR #47.

## 4. CLEANUP

Scope-locked `/refactor` read of `git diff origin/main HEAD -- backend/nflpi` (jobs.py, engine.py, fresh_line.py):
- `fresh_line.py` (105 lines): pure functions, frozen dataclasses, named constants; the refused quote already comes back
  from `choose_line` (the earlier cleanup finding, done in WO2). No change.
- `engine.load_frame`: the row dict keeps its old 16-space indent inside the new `row = {`; ruff accepts it, and
  reindenting 20 lines would add noise to the diff. No change.
- `engine.refresh_predictions`: `line_keys` is rebuilt per row; a module constant would read slightly better but it is
  7 strings in one place. The `latest_week_prediction` subquery groups every stored prediction before the week filter
  (a max per game; the table holds a few rows per game). Both LOW, carried. No change.
- `jobs.next_interval`: `<` became `<=` 6 hours, matching the kickoff query's `<= now + 6h`. No change.
- Tie note: two quotes with the same source and the same time keep the first one read (stable sort). Real feeds do not
  repeat a timestamp within one source; LOW, carried.
Result: no change needed; proof unchanged. (Superseded below: critic 1 found the read thin; WO3 carries real cleanup.)

### Critic 1 (fresh python-reviewer, no transcript) on `2b8100c`: FAIL
Its gate: 19 pure passed, 7 DB errors (expected); its ruff run was blocked by its sandbox (coordinator ruff: 0).
- HIGH: churn rule untested for "previous nflverse, first quote within 0.01" (mutating the condition to
  `previous.source != "nflverse"` passed every test). → spec F4c (test-only).
- Unpinned boundaries: a quote exactly 30 min old; a target at exactly `now`. → F2b, F8 extra assertion (test-only).
- MEDIUM: the rank guard compares each game against the week's OLD chances, so when one quote refresh moves several
  games in one run (the usual case) a game is judged against a half-updated week. → spec D3c, WO3.
- MEDIUM: CLEANUP thin (the misindented `row = {` block is this diff's own). → WO3 cleanup: `LINE_KEYS` module
  constant, reindent the row dict.
- MEDIUM naive/aware datetimes: downgraded to LOW: every datetime column is `DateTime(timezone=True)` and
  `market_seen_at` is written from an aware value, so `fromisoformat` returns aware. NaN nflverse prob behaves as None
  (no sanity compare), same as F3's "nothing to compare". LOW, carried.
- LOW carried: `market_kind` still names the snapshot (the `market_source` key labels the quote); spread/total stay
  nflverse (19a is the win line only, by spec); same-source same-time ties by read order; `load_frame` two extra queries
  for every caller.

Spec additions (frozen before WO3):
- F4c: previous nflverse 0.64, first quote 0.645: keep the previous line; quote 0.655: switch.
- F2b: a quote exactly 30 min old is fresh; 30 min 1 s is not.
- F8+: a kickoff target at exactly `now` is passed (next target counts).
- D3c: in one run, every rank check compares the week before the run with the week after it: `old` holds each game's
  chance before the run, `new` each game's chance written by the run.
Local: 21 pure passed (F4c, F2b, F8+ hold on today's code: test gaps, not defects), ruff 0. D3c is red in CI.

### Dwight on `2b8100c`: PASS, 2 MEDIUM (inbox d64b28)
- M1: the line-only rule also catches an nflverse-only line move (no quote on either row), dropping today's move and
  label alerts; breaks F4b/D3 "non-quote changes keep today's behaviour". → spec D3d: an nflverse-only line move with
  `alert_move_threshold = 0` is alerted. Fix in WO3: the line-only rule applies only when `market_source` is on the new
  row or the previous one.
- M2: same as critic 1's rank finding → D3c / WO3. His "minimum gap before a rank swap alerts" is not in the owner's
  guard 3; carried to god as an option.
- LOW carried: L1 churn may keep a previous quote older than 30 min (labelled with its time, move < 0.01); L2 sanity
  only on the newest quote; L3 a sub-0.01 move near 50% keeps the old pick (F4 by design); L4 a `pregame_quotes` DB
  error fails the run (worker retries); L5 the last target is kickoff - 20 min, so the lock row's quote can be up to
  ~49 min old at kickoff; L6 NaN nflverse prob (= critic's); L7 unguarded `fromisoformat` on our own value.
