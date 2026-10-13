# CODEX WORK ORDER 3 — step 8a2, lane web: freshness lists the star list and the head coaches

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: make `backend/tests/test_api.py::test_freshness_lists_the_star_list_and_the_head_coaches` green (and with it browser ST8), without changing any test, and keep every other test green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, commit `4657935` or later.

ALLOWED SCOPE: `backend/nflpi/config.py` and `backend/nflpi/ingestion/service.py` only. `service.py` belongs to another lane; the integrator granted exactly this edit (hive message 08276f, 2026-10-13): two entries in the `STALE_HOURS` dict, nothing else in that file.

REQUIRED BEHAVIOUR
1. `config.py`, next to the existing `stale_hours_*` settings: `stale_hours_stars: float = 24 * 8` (the list is weekly) and `stale_hours_head_coaches: float = 24 * 30` (as `teams`).
2. `service.py`, in `STALE_HOURS`, after `weather`: `"stars": lambda s: s.stale_hours_stars,` and `"head_coaches": lambda s: s.stale_hours_head_coaches,`.

FAILING EVIDENCE: `docs/gauntlet/logs/step-8a2-evidence/red-1-api.log` (F1) and `wo2-e2e.log` (ST8).

PROOF (the coordinator reruns it): `cd backend && uvx ruff check nflpi tests` and `DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_test uv run pytest tests/test_api.py -q -p no:cacheprovider`.

CONSTRAINTS: /ponytail: four lines in total. No new dependency, no other file, no test edit, no `.env.example` change. Do not build the web app, do not start a server, do not run the full test suite. Do not commit; report the diff.
