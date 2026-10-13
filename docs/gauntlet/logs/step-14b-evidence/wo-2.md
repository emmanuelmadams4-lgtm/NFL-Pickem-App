CODEX WORK ORDER 2 (step 14b, lane modelb, idea 5)

GOAL:
Make the three failing tests at the end of backend/tests/test_model.py pass (everything after the comment line
"# ---- Step 14b idea 5"). They add an offence and defence split of EPA per play and success rate as model inputs.

BASELINE:
Worktree /Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-modelb, branch lane/modelb.
`tests/test_model.py`: 3 failed, 31 passed. The 31 must stay green.

ALLOWED SCOPE (edit only these two files):
- backend/nflpi/predictions/features.py
- backend/nflpi/analytics/backtest.py
Do NOT edit tests/test_model.py, anything under docs/, engine.py, jobs.py, api/, apps/, packages/.

REQUIREMENT (the tests are the contract; read them first):

features.py
1. `offence_defence(rows: list[dict]) -> pd.DataFrame`. Each row: game_id, team, plays, epa (sum), success (count).
   Output columns exactly ["game_id", "team", "off_epa", "def_epa", "off_sr", "def_sr"], rows in input order.
   off_epa = epa / plays, off_sr = success / plays. def_epa and def_sr are the OTHER team's off_epa and off_sr in the
   same game. A game is left out for both teams unless it has exactly two rows, two different teams, and plays > 0 and
   finite numbers on both sides. Never invent a value.

backtest.py
2. `SPLIT_HALF_LIVES = (4, 8, 16)` and named constants for the two fixed scales: EPA 10, success rate 20.
3. `split_preds(df, seasons, split, window=10) -> pd.DataFrame`, shaped like `candidate_preds`' EPA branch.
   For each h in SPLIT_HALF_LIVES add to every Elo frame (use `frame.assign`, do not mutate) four columns:
   `off_epa_diff_{h}`, `def_epa_diff_{h}` = 10 * epa_diff(df, <split with that column renamed to "net_epa">, h) for
   split columns "off_epa" and "def_epa"; `off_sr_diff_{h}`, `def_sr_diff_{h}` = 20 * the same for "off_sr", "def_sr".
   (`epa_diff` already returns the pregame home-minus-away rating from earlier games only, NaN when a team has none.)
   For each season: `test = predict_season(frames, season, window)`, `_, train = _train_rows(frames, season, window)`,
   one `LogitModel.fit(train.dropna(subset=["market_logit"]), features)` per column:
   - `p_split_{h}`: features [*BLEND_FEATURES, f"off_epa_diff_{h}", f"def_epa_diff_{h}"]
   - `p_split_sr_{h}`: those plus f"off_sr_diff_{h}", f"def_sr_diff_{h}" (in that order)
   A NaN prediction (no rating) becomes that row's `p_blend` (`.fillna(test["p_blend"])`). Return the seasons
   concatenated with `ignore_index=True`, only rows where `p_market` is not NaN.

FAILING EVIDENCE:
docs/gauntlet/logs/step-14b-evidence/red-2.log (AttributeError: the functions do not exist yet).

PROOF (must pass; never run pytest without that DATABASE_URL: the default points at a live database):
cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15448/nflpi_codex uv run pytest -q tests/test_model.py
cd backend && uvx ruff check nflpi tests
Do not run the full test suite; the coordinator runs it.

CONSTRAINTS:
- Smallest correct diff. No new dependency. Plain functions and module constants.
- Match the surrounding code: type hints, one-line docstrings, lines up to 120 characters, compact style.
- Existing behaviour must not change (every existing function and test).
- No value known only after kickoff may enter a feature or a fit. Missing stays missing.
- No print or debug statements. Do not commit. Never push. Do not touch files outside the allowed scope.
- If a test looks wrong, stop and say which one and why. Do not edit or weaken it.

TASK:
Make the failing evidence pass with the smallest correct diff.

RETURN:
- changed files, a concise summary, the two proof results, any blocker
