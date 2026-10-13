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
* 400 `{"detail": "bad content-length"}` — the Content-Length header is not a number.
* 413 `{"detail": "file is too large"}` — Content-Length above the cap, or the streamed body passes the cap; the importer is not called and nothing is decoded. The cap is `nflpi.group.importer.MAX_BYTES`, read at request time (exactly the cap is allowed).
* 422 `{"detail": "<the importer's own GroupImportError message>"}` (a string, no cell text, no member name); or FastAPI's 422 for a bad `season`.
* 422 `{"detail": "no games for this season"}` — a file for a season with no games at all (a weekly file carries no season, so this stops a file posted under a wrong year from writing rows; a wrong year that has games is not caught: the screen shows the season and the web lead should make the owner confirm it).
* 500 `{"detail": "group import failed: database error"}` when the importer raises `GroupDatabaseError` (a `RuntimeError` subclass added to `importer.py`); nothing else is turned into a database error.
* `rows` for a weekly file is members times weeks in the file.
* 401 / 503: the shared token check.

`GET /api/group/standings?season=&week=` → 200 `{"season": int, "week": int, "weeks_counted": [int], "rows": [{"member": str, "points": int, "total": int, "rank": int | null}]}`, rows in `queries.standings` order; empty `rows` when none.

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
| U10 | A weekly file for a season with no games is 422 "no games for this season", nothing stored (added after Dwight's code review D1) | functional |
| U11 | A Content-Length that is not a number is 400 (L6) | functional |
| U9 | No member name reaches any log line on success or refusal, upload or reads | operational |
| S1 | Shares per game, per side: picks, share = picks/picked, mean confidence of that side's picks; counted by hand in the test | user-facing |
| S2 | A game nobody picked is listed with zero counts and null share and null mean (missing is missing) | user-facing |
| S3 | Games come in kickoff order (ties by id) with `kickoff_utc` shown | user-facing |
| S4 | A week with no games is `games: []`; `season` and `week` are required and bounded (422) | functional |
| S5 | The spread and the favoured side never change a share (swapping them in the file gives the same answer) | functional |
| S6 | The number of SQL statements for the shares route does not grow with the number of games (at most 3) | operational |
| T1 | Standings for a week: that week's points, running total of weeks up to it that season, stored rank or null; order as `queries.standings` | user-facing |
| T4 | `weeks_counted` lists the weeks (up to the asked week) that have stored rows, so the screen can show which weeks a total adds up (D3, D4) | user-facing |
| T2 | A later weekly file adds the rank it owns and keeps the others (via the route) | functional |
| T3 | A week or season with no rows is `rows: []`; other seasons stay apart; `season` and `week` required and bounded (422) | functional |

Operational layer: U5, U8, U9, S6; the importer's own log-free behaviour is unchanged. A run-log row per import is carried (not in this step).

Gate: `bash docs/gauntlet/logs/step-16b-server-evidence/gate.sh <label>`: full pytest (a skipped test fails the gate), ruff on `nflpi tests migrations`, `alembic upgrade head / check` on an empty database, `npm run gen:api` with no drift (regenerated files committed).

First failing tests: `backend/tests/test_group_api.py`, red at `ImportError: cannot import name 'group' from 'nflpi.api'` (the intended reason: the router does not exist). Log `red-pytest.log`.

## 3. IMPLEMENTATION
Provider: Codex built WO-1; Claude (Sonnet subagent) built WO-2 because Codex's workspace ran out of credits at about 09:00 UTC (god's notice 09:01Z). Coordinator reran every proof. CLIMBS: none. STRIKES: none.

| Commit | What | Builder | Proof (coordinator's rerun) |
|---|---|---|---|
| `4f4d302`, `73ac0e6` | Spec, red tests (`red-pytest.log`: ImportError, no `nflpi.api.group`), gate script | coordinator | red for the intended reason |
| `e2e2047` | WO-1: `api/group.py`, `week_shares`, the two main.py lines | `gpt-6-sol` xhigh, try 1 (`JEV: model:groupwire:wo-1 -> sol 0.98, effort xhigh 0.96`) | `test_group_api.py` + `test_group.py` 178 passed; diff read: only the 3 allowed files |
| `34e1c96`, later test commits | lint fix; tests for per-chunk stream cut, season check, off-loop import; mutation sweep (`mutate-1.log`: 21 mutations, 16 killed first time, 4 killed after new tests, 1 equivalent) | coordinator | 44 passed |
| `0fa36ae` | Red 2: Dwight's code review items D1, D2, D3/D4, L6 as failing tests (`red2-pytest.log`) | coordinator | ImportError `GroupDatabaseError` |

**Design review (Dwight, required):** PASS at `4f4d302`, no CRITICAL or HIGH. G1 (never declare the body as a parameter) and G2 (threadpool, session opened after the body) were put into WO-1 and are in the code. **Code review (Dwight, with `ecc:security-reviewer` and `ecc:silent-failure-hunter`):** PASS on security at `34e1c96`, no CRITICAL, no HIGH security; four MEDIUM data-integrity items: D1 taken (route-level season guard, clause U10), D2 taken (`GroupDatabaseError`), D3/D4 taken in part (`weeks_counted`, clause T4; a member with no row that week is still left out of that week, carried), L6 taken (U11). Carried: L5 (a rollback that itself fails escapes the importer's catches), L7 (no body-read timeout, no rate limit, no run-log row per import), a wrong year that has games is not caught by the server.
| `de3d4e9` | Review fixes: `GroupDatabaseError`, route-level season guard, `weeks_counted`, bad content-length | Claude Sonnet subagent (WO-2; Codex out of credits since about 09:00 UTC) | all tests green; diff read |
| `7d52b22` (rebased: `5b13a32`) | WO-3: season-guard select wrapped, `SQLAlchemyError` becomes `GroupDatabaseError` (Dwight LOW N1); new test `test_u8_a_database_failure_in_the_season_guard_is_500`, red first (`OperationalError` escaped), green after | Claude Sonnet subagent (Codex tried once: model `gpt-6.1-sol` not supported on this account) | 48 passed in `test_group_api.py`, ruff clean |

Work orders built by Claude: WO-2 and WO-3 (Sonnet). WO-1 by Codex. The coordinator wrote no production code.

## 4. CLEANUP
Behaviour-preserving cleanup pass: none needed. The router is 126 lines, one function per route, no duplicated block, no dead code found in `api/group.py`, `queries.week_shares`, `queries.standing_weeks` or the new `GroupDatabaseError`. The mutation sweep (`step-16b-server-evidence/mutate-1.log`: 21 mutations, 16 killed first time, 4 killed after new tests, 1 equivalent) stands: the code under it did not change except WO-3 (one guarded select, covered by the new test). Carried, not fixed here: L5 (a failed rollback escapes the importer's catches), L7 (no read timeout, no rate limit, no run-log row per import), a member with no row in a week is left out of that week's standings, a wrong year that has games is not caught by the server (the screen shows the season; the web lead makes the owner confirm).

## 5. VERIFICATION
* Rebase: `main` moved to `6feb74b` / `98ec875` (livewire, step 15d) during the lane. Rebased the 9 lane commits onto it. One conflict, `api/main.py` (both sides add an import and an `include_router` line), kept both; `packages/shared/openapi.json` and `api-types.ts` were not hand-merged: regenerated with `npm run gen:api` after the rebase and committed (`a4948fb`).
* Gate on `a4948fb`, run twice (`gate.sh a`, `gate.sh b`, logs `step-16b-server-evidence/a-*.log`, `b-*.log`): pytest 1062 passed, 0 skipped (a: 107 s, b: 106 s); ruff `nflpi tests migrations` clean; `alembic upgrade head / check / downgrade base / upgrade head / check` on an empty database clean; `npm run gen:api` no drift. Both runs identical.
* Test database `nflpi-lane-group-db` on 15445; the live app, ports 8000/5432 and the PC were not touched.
* Privacy: no real member name in any file, log or message; `research/group-data/` never opened.

## 6. LANDING
ROUTE CONTRACT (for the web lead). All routes need `Authorization: Bearer <APP_ACCESS_TOKEN>` (401 without or wrong, 503 if the server has no token set; the same check as every `/api` route). `season` is an integer 2000 to 2100, `week` an integer 1 to 22; a bad value is FastAPI's own 422.

| Route | Input | 200 reply | Error replies |
|---|---|---|---|
| `POST /api/group/import?season=<year>` | body = the raw CSV bytes (send the `File` itself as `fetch` body, NOT a `FormData`), any content type | `{"season": int, "kind": "picks" or "standings", "rows": int}` (`rows` for a weekly file = members times weeks in the file) | 400 `{"detail":"bad content-length"}`; 413 `{"detail":"file is too large"}` (cap 1,000,000 bytes, exactly the cap is allowed); 422 `{"detail": "<importer message>"}` (a string, no cell text, no name; empty, binary, unknown-header, header-only files); 422 `{"detail":"no games for this season"}` (a season with no games at all); 422 FastAPI list form for a bad/missing `season`; 500 `{"detail":"group import failed: database error"}`; 401/503 |
| `GET /api/group/standings?season=&week=` | both required | `{"season": int, "week": int, "weeks_counted": [int], "rows": [{"member": str, "points": int, "total": int, "rank": int or null}]}`; `rows: []` when nothing stored; `weeks_counted` = weeks up to the asked week that have stored rows (so the screen can say which weeks a total adds up) | 422 (bad/missing query); 401/503 |
| `GET /api/group/shares?season=&week=` | both required | `{"season","week","games":[{"game_id","away_team","home_team","kickoff_utc","members": int,"picked": int,"away":{"team","picks": int,"share": float or null,"avg_confidence": float or null},"home":{same}}]}`; every game of the week listed, in kickoff order (ties by id); zero picks gives `share` and `avg_confidence` null; `games: []` for a week with no games | 422; 401/503 |

Notes for the screen: a wrong year that has games is NOT caught by the server (show the season in the confirm step); a 422 import message is safe to show as is. The web lead consumes these through the regenerated `@nflpi/shared` types (`api-types.ts`); `client.ts` helpers are theirs.
Seam lines used: `api/main.py` one import line and one `include_router(group_api.router)` line (the router carries its own token dependency). No change to `schemas.py`, `views.py`, `client.ts` or `apps/web`.
