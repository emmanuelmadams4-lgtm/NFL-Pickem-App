# Work order S4-C: CLEANUP (scope-locked refactor, no behaviour change) + one label fix

Repo /Users/emmanueladams/Projects/NFL-Pickem-App, branch claude/step-4-pick-sheet (clean tree at HEAD).
Touch only: backend/nflpi/predictions/sheet.py, backend/nflpi/api/main.py (set_points only),
apps/web/components/week/game-card.tsx. Do NOT edit tests or specs. Do not commit. /ponytail: delete and
simplify; no new abstraction beyond what is listed; behaviour must stay identical (91 backend tests).

Backend (sheet.py):
1. The expression "win chance of a side" (`p.home_win_prob if team == g.home_team else 1 - p.home_win_prob`) is
   written five times. Add one small helper `_chance(p: Prediction, g: Game, team: str) -> float` and use it
   everywhere, including `finalize` and `refresh_tiebreaks`.
2. `compute_week` is 59 lines. Split it so no function is over 50 lines: keep `compute_week` as the reader of
   data and assembler; move "row for one game before numbers are handed out" and/or "hand out the numbers" into
   one or two private helpers. Keep names plain.
3. `refresh_tiebreaks` is 50 lines: move building the Jev `state` text and `questions` into one private helper
   (`_jev_request(games, preds, ranked) -> tuple[str, dict]`), with the four criteria as a module constant.
4. `main.set_points` recomputes N with its own query. Use the rows it already has: N = number of rows in
   `rows` whose game is not postponed (or expose N from the sheet module in the simplest way). Keep the 422.
If any of these would change behaviour or make the code longer overall, skip it and say why.

Web (game-card.tsx), a visible bug: the label and its hit rate run together as one sentence
("Coin flip won 52% of the time, 2012-2025"). Render the label as a neutral `Chip` (keep
`data-testid="pick-label"` on the element whose text is exactly the label words) and the hit rate as separate
small text after it: "Won 52% of the time, 2012–2025" (capital W, en dash between the years). Keep them on one
wrapping line with the Uncertainty chip.

Proof (paste tails): cd backend && uv run pytest -q && uvx ruff check nflpi tests migrations
                     npm run typecheck && npm run web:build
