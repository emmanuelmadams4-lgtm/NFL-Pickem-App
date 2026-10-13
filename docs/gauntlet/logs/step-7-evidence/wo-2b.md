# CODEX WORK ORDER 2b — step 7, lane alerts: a first-named starter is not a QB change

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: make `backend/tests/test_alerts.py::test_n3_a_first_named_starter_is_not_a_qb_change` pass and keep every other backend test green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit named in the hive message.

ALLOWED SCOPE: `backend/nflpi/predictions/engine.py`, the block in `refresh_predictions` that works out `qb_team` (near line 292), only.

REQUIREMENT: a starting QB change is alert-worthy only when the previous snapshot named a starter for that side and the new snapshot names a different one. No starter before and one named now is not a change (my work order 2 text allowed it; that was my mistake, it would send one alert per game when the week's starters are first posted). A named starter that becomes empty is still not a QB change, as today.

FAILING EVIDENCE: `docs/gauntlet/logs/step-7-evidence/red-wo2b.log` (`['QB change: MIA @ LV'] == []`).

PROOF (the coordinator reruns it): `cd backend && uvx ruff check nflpi tests migrations` (or your cached ruff); the test database is out of your reach, so say so.

CONSTRAINTS: smallest correct diff, one condition. No other file. Do not edit tests. Do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): the changed lines, the proof command with its exit code, any blocker.
