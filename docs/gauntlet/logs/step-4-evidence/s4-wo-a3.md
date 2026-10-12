# Work order S4-A3: games that kick off together must each keep their own points (bug found by the coordinator)

Repo /Users/emmanueladams/Projects/NFL-Pickem-App, branch claude/step-4-pick-sheet, uncommitted S4-A/A2 work in the
tree. Only edit backend/nflpi/predictions/sheet.py. Do NOT edit tests. Do not commit. /ponytail: smallest diff.
Another builder is working in apps/ and packages/ at the same time: do not touch those.

Failing test: backend/tests/test_sheet.py::test_games_that_kick_off_together_each_keep_their_own_points.

Cause: `finalize` writes games one at a time and `compute_week(..., writing=g.game_id)` treats every OTHER locked
game without an entry as history (no number). When several games lock in the same pass (the Sunday 1:00 slate),
the first one is ranked alone and takes the highest number left.

Fix: while writing game g, every game of this pass that has not been written yet (g itself and the ones after it
in kickoff order) is still treated as open. Change `writing` to a set of game ids (`writing: frozenset[str] =
frozenset()` or similar) and pass the not-yet-written ids from `finalize`. Games that are history (final before
the sheet start, so never in the pass) keep getting no number.

Proof (paste the tails): cd backend && uv run pytest -q   (all pass; expect 91)
                         cd backend && uvx ruff check nflpi tests migrations
