# CODEX WORK ORDER 1 — step 19a: fresh pregame line (F1-F8, D1-D4)

Try 1 of 2. Worktree `.claude/worktrees/lane-web`, branch **`lane/web-19a`** (not lane/web) at `dbdb27b` (red). Spec:
`docs/gauntlet/logs/step-19a.md` §2. Tests: `backend/tests/test_fresh_line.py`.

ALLOWED: `backend/nflpi/predictions/fresh_line.py` (new); `backend/nflpi/predictions/engine.py`: `load_frame`, the
feature-building lines for `market_source`/`market_seen_at`, and the ChangeEvent block in `refresh_predictions` only;
`backend/nflpi/jobs.py`: `next_interval` only. Nothing else (no push.py, no models, no migration, no test edits).

REQUIRED:
- `fresh_line.py`: frozen dataclasses `Line(prob: float | None, source: str, seen_at: datetime | None)` and
  `Quote(source: str, home_prob: float, seen_at: datetime)`; constants `FRESH_MAX_AGE`, `SANITY_GAP`, `CHURN_GAP`,
  `TARGETS = (90 min, 20 min)`, `TARGET_SLACK = 1 min`; pure `choose_line`, `fair_moneylines`, `rank_changed`,
  `until_next_target` exactly as F1-F8; one DB helper `pregame_quotes(session, game_ids, now) -> dict[str, list[Quote]]`
  (market_quotes, kind 'pregame', fetched_at in [now - FRESH_MAX_AGE, now], seen_at = fetched_at; one query).
- `engine.load_frame(session, now=None)`: for games with kickoff > now (default now = utcnow) build the nflverse Line
  (no-vig of the snapshot moneylines, observed_at), the previous Line from the newest prediction's features
  (`market_prob`, `market_source` default "nflverse", `market_seen_at` ISO), call `choose_line`; if a fresh quote wins,
  set the row's `home_ml`/`away_ml` to `fair_moneylines(p)` and add `market_source` / `market_seen_at` (ISO) to the row;
  if `reason == "sanity"`, `log.warning` once per game per call with the game id, both probabilities and the source.
  `refresh_predictions` passes its `now`. Rows without a fresh quote are exactly as today.
- Features: add `market_source` and `market_seen_at` to `features` ONLY when the row has them (so nflverse rows keep
  their hash and a deploy writes no new rows). Add both keys to `CHANGE_WORDS` as "betting line".
- ChangeEvent block (guard 3): `LINE_KEYS = {"market_prob", "market_logit", "market_source", "market_seen_at",
  "used_market", "market_kind", "upset_flags"}`; when the keys whose values changed vs `prev.features` are all in
  LINE_KEYS (and the model version is the same), append the ChangeEvent only if the pick flips or
  `fresh_line.rank_changed(old, new, game_id)` (old = newest home_win_prob of every game in that season and week before
  this refresh, new = old with this game's new prob). Call it as `fresh_line.rank_changed` (tests monkeypatch it).
  Other rows: unchanged behaviour.
- `jobs.next_interval`: inside 6 h, return `min(20 min, fresh_line.until_next_target(<kickoffs of games with kickoff in
  (now, now + 6 h]>, now))` (20 min when None). Outside 6 h unchanged.

PROOF: `cd backend && uv run pytest tests/test_fresh_line.py -q --noconftest -k "test_f1 or test_f2 or test_f3 or test_f4
or test_f5 or test_f6 or test_f7 or test_f8"` (all pass) and `uvx ruff check nflpi tests`. The database tests (D1-D4) run
only in PR CI (draft PR #47; the Mac test DB is off; do NOT start Docker). The coordinator pushes and reads CI.
CONSTRAINTS: /ponytail; reuse `novig_home_prob`; no test edits; do not commit or push; report to jim-mv5mje0k.
