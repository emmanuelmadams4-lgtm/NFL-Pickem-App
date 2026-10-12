# Work order S4-A2: correction to the pick sheet backend (spec amendments by the coordinator, not builder faults)

Repo /Users/emmanueladams/Projects/NFL-Pickem-App, branch claude/step-4-pick-sheet. Uncommitted S4-A work is in the
tree; build on it. Read backend/tests/test_sheet.py again: it changed (kick_off now backdates the game's
predictions; three new tests). Do NOT edit tests. /ponytail: smallest correct diff, no new abstraction. Do not
commit. Do not touch apps/, packages/, scripts/, docs/.

1. `sheet.recommendations`: remove the `g.updated_at > p.created_at` fallback. The recommendation is only the last
   snapshot made before kickoff, or a backfill row (CLAUDE.md data integrity rule). The tests now create
   predictions before kickoff, so the fallback is not needed.

2. History guard in `sheet.finalize`. Without it every past game in the real database (thousands) gets an entry
   and an invented "auto" pick. Rule: a game is written down only if it is locked, not postponed, has a
   recommendation, has no entry, AND (its status is not "final" OR its kickoff_utc >= the sheet start).
   The sheet start is `app_settings["sheet_start"]` = `{"at": <ISO timestamp>}`; when the key is missing,
   `finalize` writes it once with `now` before selecting games. Put the kickoff/status condition in the SQL query
   so the scan stays small.

3. `sheet.compute_week`: a locked game with NO entry is history (or about to be written). It gets
   app_points = my_points = None, takes no number, and its my_pick is his `user_picks` team or None
   (pick_by "csv"/"user" from the row, else "app"); `differs` is False for such a row. The one exception is the
   game `finalize` is writing right now: give `compute_week` an optional parameter (for example
   `writing: str | None = None`) naming the game to treat as still open, and use it from `finalize`.
   `label` / `label_hit_rate` still come from its recommendation.
   N stays "games in the week that are not postponed".

4. `views.scorecard`: a week that has a `weekly_ranks` row but no counted games is still listed, with zeros and
   its rank / leader_points.

5. Small cleanups while there: `finalize` calls `recommendations(session, [g])` twice and `compute_week` once per
   game; fetch the recommendation once per game. Keep `finalize` under 40 lines.

Proof (paste the tails): cd backend && uv run pytest -q   (all pass; expect 90)
                         cd backend && uvx ruff check nflpi tests migrations
Report: files changed, the two tails, anything in this order that is wrong or impossible.
