CODEX WORK ORDER (WO-4: two missing tests, tests only)

GOAL: add two tests so two mutants die. No production code change.
BASELINE: branch lane/scores at a74ee33, clean tree.
ALLOWED SCOPE: backend/tests/test_scores.py only.
REQUIREMENT:
1. A zero total line with a zero spread is missing, not a 0-0 score: add the case (0, 0) to the parametrize list of test_s1_implied_score_is_missing_when_the_line_is_missing_or_impossible. (Mutant "total_line <= 0" -> "< 0" must now fail.)
2. A row whose status is "scheduled" (not "final") but which carries both scores must not count in scoring_form: add test test_s4_a_scheduled_game_that_carries_scores_is_not_counted next to the other S4 tests, using mini() and the FORM_ROWS pattern (change one earlier row of FORM_ROWS to status "scheduled" with scores, assert the later game's form ignores it, and that a team with only that game still has NaN form). (Mutant dropping `row.status == "final" and` must now fail.)
PROOF: cd backend && DATABASE_URL=postgresql+psycopg://nflpi:test@127.0.0.1:15446/nflpi_wo uv run pytest -q tests/test_scores.py  (all pass) and uvx ruff check tests/test_scores.py (line length 120).
CONSTRAINTS: smallest diff, match surrounding style, no new dependency, no other file, do not commit, never push.
RETURN: changed files, summary, proof result.
