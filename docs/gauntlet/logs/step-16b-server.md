# Step 16b (server) of 17: Group routes (upload, standings, shares)

Session: owner's Mac, 2026-10-13, lane `groupwire` (worktree `.claude/worktrees/lane-groupwire`, branch `lane/groupwire`, base `main@e51ac48`), wave 5, SERVER ONLY.
Coordinator: Claude (hive temp "Phyllis"). Builder: Codex. coord task #20. Evidence folder: `docs/gauntlet/logs/step-16b-server-evidence/`.
No real member name appears in this file, the tests, the fixtures or any log. The real files under `research/group-data/` were never opened.

## 1. PLANNING
* **In the owner's words (D56):** his group's picks and confidence points come into the app from files he exports from his own signed-in browser; scoring is straight winners with confidence points only. Step 16a built the tables, the checked importer and two queries. This step puts three token-protected doors on them: send a file in, ask for the standings of a week, ask how the group split on each game of a week. It replaces nothing. It is not: a screen (the web lead builds it on these replies), group shares as model input or AI evidence, scraping, a migration.
* **Roadmap row:** PLAN.md row 16 (D56), server half of 16b.
* **Tier:** T2 (new API behaviour on untrusted file input). Reversibility: two-way (one new router file, one import line, one include line). Security review required (file input, auth, database queries).
* **Decisions relied on:** D56; `CLAUDE.md` (every `/api` route behind the bearer token, never invent data, missing stays null); step-16a log (all-or-nothing import, `GroupImportError` messages carry no cell text, `RuntimeError` for database faults, `MAX_BYTES`); lanes.md "Wire lanes" seam grant (one import line and one `include_router` line in `api/main.py`, regenerated `openapi.json` and `api-types.ts`, nothing else).
* **Pre-flight:** Problem: the importer from 16a has no way in from the app. Why now: the owner has the files and the web lead waits on these replies. Scope: three routes, one batched query, tests; cut: any screen, any change to `schemas.py`/`views.py`/`client.ts`, run-log row per import (carried), rate limiting (single-user app, and the cap bounds the work). Success signal: his file imports through the route and the screen can read both questions in one request each; no usage metric (one user). Reversibility: two-way.
* **Assumptions:** `validated` the `api` router in `api/main.py` already applies `require_token` to every route added with `include_router(api)`; I mount a second router with the same dependency (`Depends(require_token)`), so the check is the same function; `validated` `python-multipart` is not installed and not a dependency: the upload is the raw request body, so no new dependency; `validated` the 16a importer already refuses a file over `MAX_BYTES` (1,000,000) but only after the whole body was read into memory: the route must cap before reading; `assumed` a standings or shares question for a week with no data is an empty answer, not an error (the screen shows "nothing yet").
* **Interpretations:** upload as multipart form vs raw body. Chosen: raw body (no dependency, simplest to cap while streaming, one `fetch(url, {method:"POST", body:file})` on the web side). Cost: the web lead sends the `File` object as the body, not a `FormData`. Rejected alternative: multipart (needs `python-multipart`, new dependency, SEAM on `pyproject.toml`).
* **Skills:** `/jevgrep`: N/A (file homes, importer and router pattern are fixed by the lane map and read directly). `tdd`: no project tdd skill; the coordinator wrote the failing tests first. `ponytail`: in every work order. Design Gauntlet: N/A (no screen). `harness-engineering`: N/A.
* **Tools:** Codex: `codex-cli` (probe below). Test database `nflpi-lane-group-db` on `127.0.0.1:15445`. The Bash sandbox blocks docker and `~/.claude/plans` writes, so those few commands ran unsandboxed.
* **Baseline at `e51ac48`:** `tests/test_group.py` 137 passed (DB 15445). Full gate numbers in section 5.
* EFFORT: PLANNING and SPECIFICATION high; IMPLEMENTATION low; VERIFICATION high.

## 2. SPECIFICATION (frozen)
Router: `backend/nflpi/api/group.py`, `router = APIRouter(prefix="/api/group", dependencies=[Depends(_token)])`, mounted in `main.py` by one import line and one `include_router` line. `_token` is a small dependency in the router file that calls `nflpi.api.main.require_token` (imported inside the function, so there is no import cycle and the router carries its own protection). The module imports `import_group_csv` into its own namespace (`nflpi.api.group.import_group_csv`) so the tests can replace it. Season is a query integer 2000 to 2100; week is a query integer 1 to 22. A bad query value is FastAPI's own 422.

### Routes and reply shapes
`POST /api/group/import?season=<year>` body: the raw CSV bytes (any content type).
* 200 `{"season": int, "kind": "picks" | "standings", "rows": int}`
* 413 `{"detail": "file is too large"}` — Content-Length above the cap, or the streamed body passes the cap; the importer is not called and nothing is decoded. The cap is `nflpi.group.importer.MAX_BYTES`, read at request time (exactly the cap is allowed).
* 422 `{"detail": "<the importer's own GroupImportError message>"}` (a string, no cell text, no member name); or FastAPI's 422 for a bad `season`.
* 500 `{"detail": "group import failed: database error"}` when the importer raises `RuntimeError`.
* 401 / 503: the shared token check.

`GET /api/group/standings?season=&week=` → 200 `{"season": int, "week": int, "rows": [{"member": str, "points": int, "total": int, "rank": int | null}]}`, rows in `queries.standings` order; empty `rows` when none.

`GET /api/group/shares?season=&week=` → 200 `{"season": int, "week": int, "games": [{"game_id": str, "away_team": str, "home_team": str, "kickoff_utc": datetime string, "members": int, "picked": int, "away": {"team": str, "picks": int, "share": float | null, "avg_confidence": float | null}, "home": {same}}]}`; every game of that season and week appears (zero counts and null share when nobody picked); ordered by `kickoff_utc` then `game_id`; empty `games` for a week with no games.

### Clauses (each has a test in `backend/tests/test_group_api.py`)
| # | Clause | Layer |
|---|---|---|
| R1 | All three routes answer 401 without a token, with a wrong token or a non-Bearer scheme; an upload with no token is never read or imported | functional (security) |
| U1 | A picks file posted as the body is stored, reply `kind picks` and the row count | functional |
| U2 | A weekly file posted as the body is stored, reply `kind standings`, rank only on the file's last week | functional |
| U3 | The same file posted twice leaves the same stored rows and the same reply | functional |
| U4 | The body is read as raw bytes whatever the Content-Type (`text/csv`, `application/octet-stream`, `multipart/form-data`) | functional |
| U5 | A body over the cap is 413 and the importer is never called, with or without a Content-Length header; the cap is `importer.MAX_BYTES` at request time; exactly the cap is allowed | operational |
| U6 | A refused file is 422 with exactly the importer's message, no member name in it, nothing stored; empty, binary, unknown-header and header-only files are 422 | functional |
| U7 | `season` is required and must be an integer from 2000 to 2100 (else 422, nothing stored) | functional |
| U8 | A database failure (importer `RuntimeError`) is 500 with the fixed text above, nothing of the error leaks | operational |
| U9 | No member name reaches any log line on success or refusal, upload or reads | operational |
| S1 | Shares per game, per side: picks, share = picks/picked, mean confidence of that side's picks; counted by hand in the test | user-facing |
| S2 | A game nobody picked is listed with zero counts and null share and null mean (missing is missing) | user-facing |
| S3 | Games come in kickoff order (ties by id) with `kickoff_utc` shown | user-facing |
| S4 | A week with no games is `games: []`; `season` and `week` are required and bounded (422) | functional |
| S5 | The spread and the favoured side never change a share (swapping them in the file gives the same answer) | functional |
| S6 | The number of SQL statements for the shares route does not grow with the number of games (at most 3) | operational |
| T1 | Standings for a week: that week's points, running total of weeks up to it that season, stored rank or null; order as `queries.standings` | user-facing |
| T2 | A later weekly file adds the rank it owns and keeps the others (via the route) | functional |
| T3 | A week or season with no rows is `rows: []`; other seasons stay apart; `season` and `week` required and bounded (422) | functional |

Operational layer: U5, U8, U9, S6; the importer's own log-free behaviour is unchanged. A run-log row per import is carried (not in this step).

Gate: `bash docs/gauntlet/logs/step-16b-server-evidence/gate.sh <label>`: full pytest (a skipped test fails the gate), ruff on `nflpi tests migrations`, `alembic upgrade head / check` on an empty database, `npm run gen:api` with no drift (regenerated files committed).

First failing tests: `backend/tests/test_group_api.py`, red at `ImportError: cannot import name 'group' from 'nflpi.api'` (the intended reason: the router does not exist). Log `red-pytest.log`.
