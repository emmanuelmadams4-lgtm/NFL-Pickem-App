CODEX WORK ORDER 2 (step 9, lane scores): review fixes and one rounding amendment

GOAL:
Make the 12 failing tests in `backend/tests/test_scores.py` pass without breaking the other 38.

BASELINE:
Worktree: this directory (branch lane/scores), HEAD = the commit that adds this file. Do not create another worktree.

ALLOWED SCOPE (edit only these two files):
- backend/nflpi/predictions/scores.py
- backend/nflpi/analytics/score_backtest.py

REQUIREMENT:

scores.py
1. New `entry_pair(home: float, away: float) -> tuple[int, int]`: `(entry(home), entry(away))`, except when BOTH numbers end in exactly .5 (fractional part == 0.5): then the home number rounds up and the road number rounds down (`entry(home), floor(away)`), so a whole-number line total stays the same. Never below zero.
2. `tiebreak_score` uses `entry_pair`.

score_backtest.py
3. `predict_season` builds every method's two entries with `entry_pair` (a row where either number is missing gets NaN for both).
4. New constant `MIN_SHIP_GAMES = 200`. In `summary`, `wins` is also False when there are fewer than `MIN_SHIP_GAMES` games.
5. `summary` raises `ValueError` (message contains the word "missing") when any of the six `pred_*` columns or `home_score` / `away_score` holds a missing value.
6. `run_score_backtest`:
   - raises `ValueError` (message contains the word "seasons") when `seasons` is empty or has a repeated season;
   - puts the games in order itself before building features: `df.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)` (same keys as `features.games_frame`); the caller's frame is not changed;
   - returns one more key, `"excluded"`: the number of tested games (rows returned by `predict_season`) left out because some method had no prediction for them (int).

FAILING EVIDENCE:
`uv run pytest -q tests/test_scores.py` -> 12 failed, 38 passed (list in docs/gauntlet/logs/step-9-evidence/s9-red-2.log).

PROOF (run from backend/; the test database is already running on this machine):
DATABASE_URL=postgresql+psycopg://nflpi:test@127.0.0.1:15446/nflpi_wo uv run pytest -q tests/test_scores.py
uvx ruff check nflpi tests
NEVER run pytest without that DATABASE_URL. Run only this one test file, never the whole suite.

CONSTRAINTS:
- smallest correct diff; keep the style of the two files (ruff, line length 120, typed signatures)
- no new dependency, no new public name beyond `entry_pair` and `MIN_SHIP_GAMES`
- no file, network, database or environment access; the strings "sqlalchemy", "httpx", "requests", "urllib", "open(", "os.environ", "subprocess", "socket" must not appear in either module
- do not mutate the caller's DataFrame
- do not edit the test file or any other file; do not commit; never push

TASK:
Make the failing evidence pass.

RETURN:
- changed files
- concise implementation summary
- proof command result
- blocker if one remains
