# Work order S4-A: pick sheet backend (make backend/tests/test_sheet.py pass)

You are the builder. Repo: /Users/emmanueladams/Projects/NFL-Pickem-App (branch claude/step-4-pick-sheet).
Read first: CLAUDE.md, backend/tests/test_sheet.py (the frozen gate: DO NOT edit it, or any other test),
docs/gauntlet/logs/step-4.md sections 1-2, backend/nflpi/api/views.py, api/main.py, api/schemas.py,
models.py, jobs.py, analytics/metrics.py, analytics/backtest.py, ai/providers.py, config.py,
migrations/versions/0001_initial_schema.py.

Style: /ponytail. Smallest correct diff. Match surrounding code (typed, ruff line 120, small functions,
no new dependency, no speculative abstraction, no comments that restate code). Do not touch apps/ or
packages/ (a later work order regenerates the API types). Do not edit tests. Do not commit.

## What to build

### 1. Labels (analytics/metrics.py, analytics/backtest.py, api/schemas.py)
* `COIN_FLIP_BELOW = 0.55`, `EASY_PICK_FROM = 0.67`, `pick_label(prob: float) -> str` returning
  "coin_flip" | "tough_matchup" | "easy_pick" where prob is the win chance of the picked side.
* `LABEL_HIT_RATE = {"coin_flip": 0.524, "tough_matchup": 0.596, "easy_pick": 0.770}` with a one-line comment:
  measured on the 2012-2025 walk-forward backtest, blend model (docs/gauntlet/logs/step-4-evidence/s4-label-cuts.log).
* `run_backtest` result gains `"labels"`: a list in the order coin_flip, tough_matchup, easy_pick of
  `{"label", "games", "share", "hit_rate"}` computed from `p_blend` over the same `preds` used for `"games"`
  (hit_rate None when games == 0). Also add `"labels_2012_2021"` and `"labels_2022_2025"` next to the existing
  signals_* keys in the same style. `BacktestOut` gains `labels: list[dict] = []` (old stored runs lack the key).
* `jobs.backtest()` prints the three label rows for the three periods (same print style as the signal lines).

### 2. Tables (models.py + migrations/versions/0002_pick_sheet.py)
* `pick_points`: game_id PK FK games.game_id, points Integer, set_at timestamptz. His hand-set number for an
  OPEN game.
* `sheet_entries` (model class `SheetEntry`, must be importable as `nflpi.predictions.sheet.SheetEntry`):
  game_id PK FK, app_pick String(4), app_prob Float, label String(16), app_points Integer nullable,
  my_pick String(4), my_points Integer nullable, pick_by String(8), points_by String(8), locked_at timestamptz.
  Written ONCE when a game kicks off, never updated.
* `weekly_ranks`: season + week composite PK, rank Integer, leader_points Integer nullable, entered_at timestamptz.
* Migration 0002: explicit `op.create_table` calls (never `metadata`/`create_all`), down_revision "0001".
  `alembic check` must be clean against the models.

### 3. The sheet (new module backend/nflpi/predictions/sheet.py)
Pure helpers (unit-tested directly):
* `Ranked` = NamedTuple(game_id: str, prob: float); `Evidence` = NamedTuple(score: float, confidence: float).
* `TIE_BAND = 0.01`, `order(games: list[Ranked], evidence: dict[str, Evidence]) -> list[str]`: sort by prob
  descending (ties by game_id), then ONE pass from the top over neighbour pairs: if the gap is < TIE_BAND and both
  have evidence with confidence >= 0.8 and the lower one's score >= the upper one's score + 1.0, swap them and
  move on past the pair. Returns game ids, surest first.

Week computation (one function used by the API and by `finalize`), for all games of a (season, week):
* N = number of games whose status is not "postponed". A postponed game has app_points = my_points = None and
  takes no number.
* A game is "locked" by `api.views.is_locked(game, now)`. A locked game's values come from its `sheet_entries`
  row (call `finalize` first so the row exists).
* The app's pick and win chance for a game come from its recommendation prediction (the same rule the views use:
  the last snapshot before kickoff). A game with no prediction: no points, label None; it does not take a number.
* App's sheet: open games ordered with `order(...)` on the app pick's win chance, using cached Jev evidence;
  they take the numbers 1..N not used by locked games' `app_points`, highest number to the first.
* His sheet: my_pick = his `user_picks` row if any (pick_by "user", or "csv" if source == "csv") else the app's
  pick (pick_by "app"). Numbers: locked games keep `my_points`; open games with a `pick_points` row keep that
  number (points_by "user"); the remaining open games are ordered with `order(...)` on the win chance of HIS side
  (1 - app prob when he picked the other team) and take the numbers left, highest first (points_by "app").
  If a hand-set number collides with a locked game's number or another hand-set number, or is outside 1..N,
  ignore that hand-set row (treat the game as not hand-set) rather than produce a duplicate.
* `differs` = my_pick != app_pick or my_points != app_points.
* `finalize(session, now) -> int`: for every game where is_locked is true, status != "postponed" and no
  `sheet_entries` row exists, in kickoff order: compute the week as above with that game still treated as open,
  insert its `sheet_entries` row (label from app_prob), and if he has no `user_picks` row insert one with
  picked_team = app pick, source = "auto", pick_by "auto". Delete its `pick_points` row if any (the number now
  lives in the entry). Must be idempotent and safe if the API and the worker run it at the same moment
  (insert with ON CONFLICT DO NOTHING on the primary key, or equivalent). Commit. Return rows written.
  A locked game that has NO prediction gets no entry.
* Call `finalize` at the start of `views.week_view`, of the two points endpoints, of the scorecard, and in
  `jobs.tick` (inside its own try/except like reminders, after the heartbeat).

Jev tie-break (D43):
* New module backend/nflpi/ai/jev.py: `decide(state: str, questions: dict) -> dict` posting
  `{"model": settings.openrouter_model, "state": state, "questions": questions}` to
  `https://openrouter.ai/api/alpha/decisions` (new setting `openrouter_decisions_url` in config.py) with the
  Bearer key, timeout 30, returning the response's `answers` dict; raise `AIError` on any failure or when the key
  is empty. This is the documented way to call Jev (docs.typesafe.ai): state + typed questions, never a chat.
* `sheet.refresh_tiebreaks(session, season, week) -> None`: look at OPEN games with a prediction, ordered by app
  win chance. If no neighbour pair is within TIE_BAND, return without calling Jev. Otherwise build ONE request:
  `state` = a short plain-text block per game (id, matchup, picked team, win chance as a whole percent, whether
  the stats model and the betting line favour the same team, whether either team has a starting-QB change, the
  uncertainty grade and its reasons) and one question per game keyed by game_id:
  `{"type": "score", "instructions": "How strong is the evidence in the state for the pick in game `<game_id>`?",
    "criteria": [four levels from weak to strong, each a standalone concrete situation, no numerals]}`.
  Cache the answers in `app_settings` under key `jev_tiebreak_<season>_<week>` as
  `{game_id: {"hash": <prediction inputs_hash>, "score": ..., "confidence": ...}}`. Skip the call entirely when
  every open game's current inputs_hash already has a cached answer. Evidence is only used when its hash matches
  the game's current recommendation. Any exception from `decide` is caught and logged; the sheet then uses win
  chance alone. Count the call with the existing daily cap helper (`ai/research.py:_reserve_call`); a cap error
  is treated like Jev being down.
* Call `refresh_tiebreaks` for the current week at the end of `jobs.predict` (never from a request handler).
  Tests monkeypatch `nflpi.ai.jev.decide` and `sheet.TIE_BAND`, so read both at call time
  (`jev.decide(...)`, module-level `TIE_BAND` looked up inside the function).

### 4. API (api/schemas.py, api/main.py, api/views.py)
* `GameSummary.sheet: SheetOut` with fields: label (str | None), label_hit_rate (float | None), app_pick
  (str | None), app_points (int | None), my_pick (str | None), my_points (int | None),
  pick_by ("app" | "user" | "auto" | "csv"), points_by ("app" | "user"), differs (bool).
  For a locked game pick_by comes from the entry.
* `PUT /api/picks/{game_id}/points` body `{"points": int}` -> 200 with the week (`WeekOut`). 404 unknown game.
  409 if the game is locked. 422 if points is outside 1..N. If another game currently holds that number in his
  sheet: 409 if that game is locked; otherwise both games get a `pick_points` row (the other game takes this
  game's current number). `DELETE /api/picks/{game_id}/points` -> 200 with the week; 409 if locked; removes his
  hand-set row for that game only.
* `PUT /api/ranks/{season}/{week}` body `{"rank": int >= 1, "leader_points": int >= 0 | null}` -> 204 (upsert).
* `GET /api/scorecard/{season}` -> `ScorecardOut {season, weeks: [ScorecardWeek], totals: ScorecardWeek,
  by_label: [{label, games, my_correct, app_correct}]}`. `ScorecardWeek`: week, games, max_points, my_points,
  app_points, my_correct, app_correct, changed, changed_right, changed_wrong, auto, rank, leader_points.
  Built from `sheet_entries` of REG games with status "final": games = entries counted; max_points = sum of
  1..games per week; a side's points count when its pick is the winner; a tied game (winner None) counts in
  games and gives zero points and zero correct to both; changed = my_pick != app_pick; changed_right = changed
  and his pick won; changed_wrong = changed and the app's pick won; auto = pick_by == "auto". `totals` sums the
  weeks (week = 0, rank and leader_points None). Weeks with no entries are left out. by_label always lists the
  three labels in order.
* Results: in `views.performance`, picks whose `user_picks.source == "auto"` are NOT counted in `my_total` /
  `my_correct`; count them in new `auto_total` / `auto_correct` on `WeekPerformance` and a new
  `PerformanceOut.auto: Tally`. Do the same wherever the week summary counts "my" accuracy (`week_view`
  summary: picks_made and my accuracy count only non-auto picks).
* `GameSummary.my_pick` keeps its current meaning (his `user_picks` team, including an auto row).

## Proof you must run and paste the tail of
cd backend && uv run pytest -q            (all tests pass, including the 21 in tests/test_sheet.py and A12)
cd backend && uvx ruff check nflpi tests migrations
The test database is Postgres on localhost:5432 (already running). If a command cannot run in your sandbox,
say exactly which one and why; never claim a pass you did not see.

## Report back
Files changed, the two command tails, anything in this order you found wrong or impossible (say so plainly
instead of working around it), and every simplification you made on purpose.
