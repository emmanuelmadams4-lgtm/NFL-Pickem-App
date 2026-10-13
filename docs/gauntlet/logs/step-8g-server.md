# Step 8g (server side) of 14: the news reaches the app (worker schedule + GET /api/news)

Session: owner's Mac, 2026-10-13, lane `newswire` (worktree `.claude/worktrees/lane-newswire`, branch `lane/newswire`, base `main@92adfbc`). Coordinator: Claude (hive temp "Toby"). Coord task #21. State file `~/.claude/plans/nfl-pickem-lanes/lane-newswire.md`. Evidence folder: `docs/gauntlet/logs/step-8g-server-evidence/`.

## 1. PLANNING
* **Goal:** the news that step 8c landed (`run_news`, table `news_items`) now reaches the app. (1) The worker polls the two feeds on a slow schedule and prunes old rows. (2) One token-protected route, `GET /api/news?game_id=...`, returns at most 5 latest items tied to either team of that game. **Server only: no screen, no migration, no AI evidence pack (lane sdk), no star alerts (8i).**
* **Roadmap rows:** `docs/gauntlet/step8-scrape-plan.md` Part 3, 8g (API `news` on game detail: latest 5, title, source, age, link out; the pack part belongs to lane sdk) and 8h (failure: a block stops the source 24 h, the app works with zero news). Lane goal and OWNS: `lanes.md`, lane newswire, plus the "Wire lanes" seam grant.
* **Tier:** T2 (external text is untrusted input and is returned to a client). Reversibility: two-way (two new files, 2 lines in `api/main.py`, at most 10 in `jobs.py`; no table or column changes).
* **Decisions relied on:** D51 (free), D52, D53 (public pages only: no login, paywall or anti-bot workaround, never a changed user agent or proxy; a 403, 429 or robots deny stops that source, as the landed code does). Step 8c's "Carried to wave 5 and 8g".
* **Pattern followed (not reinvented):** `live_worker.py` (a daemon thread started by `jobs.loop`, a sweep of stale `running` rows, every failure logged by class name only) and `api/live.py` (`APIRouter(prefix="/api")`, token check added at `include_router`).
* **Carried items taken or carried (from step 8c "Carried to wave 5 and 8g" and Dwight's advisories):**
  * *Teams and stars before `run_news`:* TAKEN for teams (the worker skips a run while the `teams` table is empty and says so in the log: the API ties by team). Stars: CARRIED with a reason: a star-less run still ties every item by team and tags it; star ties are an extra. Not blocking the news on the star feed.
  * *Prune:* TAKEN. `run_news` prunes only after a good poll or a 304; the worker prunes on every wake, so an all-blocked week still empties old rows.
  * *A4 (parse costs about 4 s CPU per feed):* TAKEN: the poll runs in its own thread with a deadline, off the main loop.
  * *A1, A2 (an item dropped or emptied without being counted):* CARRIED: cosmetic counters inside the landed parser; no effect on what the API returns.
  * *The AI pack, `<news_item>` wrapping, render rules:* NOT this step (lane sdk, lane web).
  * *Short nicknames such as "Jags" as aliases:* CARRIED to the owner (a miss, never a wrong tie).
* **Skills:** `/jevgrep` N/A: the seams were answered by reading `run.py`, `live_worker.py`, `api/live.py`, `jobs.py` (named symbols). Design Gauntlet N/A (no UI). Parallel lanes: `lane-guard check` at VERIFICATION.
* **Security design review first (required):** Dwight (hive `dwight-mv5mkpow`), design review sent 12:0x Z, replied **PASS to build, no CRITICAL, no HIGH, four MEDIUM** (M1 to M4) and six LOW (L1 to L6). Every one is folded into section 2 and a test below, nothing carried but L4 (a feed can date its own items up to a day ahead; accepted: two allowlisted sources) and L6 (a note to the screen, in the ROUTE CONTRACT).
  * **M1** `team_ids` is JSON, not JSONB: the filter casts to JSONB with a bound value, never string formatting (R3).
  * **M2** `clean_text` decodes one layer of entities, so the order is clean_text FIRST, strip `<` and `>` LAST, nothing decodes after (R6; tests for `&lt;script&gt;` and `&#60;img ...&#62;` stored rows).
  * **M3** FastAPI's own 422 echoes the rejected value, so `game_id` is a plain optional string checked by hand with `re.fullmatch` and answered with a fixed 422 message (R5).
  * **M4** the polling thread opens and closes its own session; the run deadline is 180 s (2 sources x (robots 20 s + feed 20 s + DNS 5 s) is 90 s, plus parse CPU and a redirect); a skipped wake logs a warning; the stale-run sweep runs on every wake (W7, W9).
  * **L1** every row-dropping filter and the order sit in the SQL before `LIMIT 5`. **L2** the wake is 600 s. **L3** the link is `canonical_url`'s output. **L5** `game_id` is echoed from the games row.

## 2. SPECIFICATION (frozen before production code)
Files: `backend/tests/test_news_worker.py`, `backend/tests/test_news_api.py` (red first). Public seams: `news_worker.news_step`, `news_worker.run_with_deadline`, `news_worker.run_forever`, `news_worker.start`, `news_worker.sweep_stale_runs`; router `news_api.router` (`GET /api/news`).

### 2a. Worker clauses (W)
* **W1 (a step polls and stores).** `news_step(session, now, ...)` calls `run_news` once with the sources it is given, and stores the recorded items, tied by team.
* **W2 (never more often than every 30 minutes).** Driven by the real `run_forever` loop on a fake clock for 3 hours, once with the real wake and once with the wake forced down to 1 second, each source is requested at most once per 30 minutes and never twice within 30 minutes. The guarantee comes from `run_news`; the schedule must not defeat it (the step passes the real `now` and never resets the history).
* **W3 (a blocked source stays quiet 24 hours).** A source answering 403 is requested once, not again for 24 hours, while the other source keeps its 30 minute rhythm. The worker never changes how it asks (same user agent, no proxy).
* **W4 (every source blocked).** `news_step` returns without raising; every run is `failed` with `blocked:`; old rows are still pruned.
* **W5 (prune every wake).** A row fetched 31 days ago is gone after a step, a row fetched 29 days ago stays; true when the step polls nothing (not due) and when everything is blocked.
* **W6 (teams first).** With an empty `teams` table a step makes no request and writes no `ingestion_runs` row.
* **W7 (a deadline).** `run_with_deadline(fn, seconds)` returns by the deadline when `fn` hangs, reports it did not finish, and the caller is not blocked. While the abandoned run is alive no second run starts (one run in flight at most); each skipped wake logs a warning. The step runs on a session the thread opens itself. The run deadline is 180 s and the wake 600 s.
* **W8 (the loop survives).** A step that raises (any exception) is logged by exception class name only (never the message) and the loop wakes again; `stop` ends the loop.
* **W9 (stale `running` rows).** At start-up and on every wake `running` rows of dataset `news:*` older than 10 minutes become `failed` / `interrupted`; younger ones and every other dataset are untouched.
* **W10 (wiring).** `jobs.loop` starts the news thread exactly once, after the live thread; `jobs.py` calls into `news_worker.py` and holds none of the logic.

### 2b. Route clauses (R) — `GET /api/news?game_id=<id>`
* **R1 (token).** No token or a wrong token: 401, nothing else in the body. Right token: 200.
* **R2 (reply shape, frozen).**
  ```
  200 {"game_id": str, "items": [ {"title": str(<=200), "source": str, "published_at": datetime|null, "url": str|null, "tags": [str]} ]}
  ```
  Exactly these keys, nothing more (no ids, no extract, no player ids). `source` is the display name (`ESPN`, `CBS Sports`), not the id. `published_at` is null when the feed gave none (never invented). `tags` are only from `injury|trade|coach|playcaller`, sorted, each stored tag outside that set dropped.
* **R3 (which items).** Items whose `team_ids` (JSON column, cast to JSONB with bound values) contain the game's home team or away team; items tied to neither, or to other teams only, are not returned. Items from a source id that is not in `sources.SOURCES` are not returned.
* **R4 (at most 5, newest first).** Order: `published_at` newest first, items with no date after all dated ones, then `fetched_at` newest, then `id` highest. All filtering and the order are in the SQL before `LIMIT 5` (other teams' items never use up a place). 0 items is `{"game_id": ..., "items": []}` with 200.
* **R5 (unknown or malformed game).** An unknown `game_id`: 404 with a fixed message. A missing, empty, longer than 32, or non `[A-Za-z0-9_-]` `game_id` (checked by hand with `re.fullmatch`, a trailing newline fails): 422 `{"detail": "game_id must be 1 to 32 letters, digits, - or _"}`, the same text for every case. No stack trace, no echo of the value.
* **R6 (plain strings only).** Order: `clean_text` first, then `<` and `>` removed last. No returned string holds `<` or `>` (also for stored `&lt;script&gt;`, `&#60;img&#62;` and `&#x3c;`); a stored title like `<b>Hi</b><script>x</script>` comes back with no markup characters. Titles are cut at 200, control characters and bidi marks are gone, whitespace is collapsed.
* **R7 (a link is returned only if safe).** `url` is the stored link only when it is `https`, has no user info, no port, no backslash or control character, and its host is the item's own source host or a subdomain of it (a host of the allowlist in `sources.py`, dot boundary: `espn.com.evil.com` and `evilespn.com` fail), else `null`. The item itself is still returned. Never a `javascript:`, `data:` or `http:` link. Max 2048 characters.
* **R8 (read only).** The route writes nothing and makes no network call.
* **R9 (contract).** `npm run gen:api` shows no drift after the router is included; the route is in `openapi.json` with response model `NewsOut`.

### 2c. Operational layer
Every poll stays an `ingestion_runs` row (`news:<id>`), as 8c landed; a block shows as `error = "blocked: ..."`; the freshness view reading those rows is lane web's/views' file (a SEAM question for the screen, not this step).

### 2d. Gate
```
cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@127.0.0.1:15441/nflpi_test uv run pytest -q \
 && uvx ruff check nflpi tests migrations && uv run alembic check ; cd .. && npm run gen:api (no drift)
```
Baseline on `main@92adfbc`: recorded in section 3.

## 3. IMPLEMENTATION
`IMPLEMENTATION_PROVIDER: Claude (Sonnet subagents), because Codex refused.` `codex exec` was tried (twice: the first call had no stdin; the second reached the service): `The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account`; nothing was built by it. `CLIMBS: none. STRIKES: none.` No Fable, no astra, no Opus builder. Builders never critic.

| WO | What | Builder | Result |
|---|---|---|---|
| WO-1 `wo-1.md` | `news_worker.py`, 2 lines in `jobs.py` | Sonnet subagent (try 1) | Written to the order; its sandbox blocked `uv`, so I ran the proof: 19 of 21 passed; both failures were mistakes in MY tests (a `json <> json` comparison; an off-by-one in the sweep count), fixed in the tests: 21 passed |
| WO-2 `wo-2.md` | `api/news.py`, `Source.name`, 2 lines in `api/main.py` | Sonnet subagent (try 1) | Written to the order; I ran the proof: 59 of 59 passed on the first run. One addition by the builder: an item whose source id is unknown is skipped (the SQL already excludes them) |

* **Diff read by me** against the order: only the allowed files; `jobs.py` +2 lines (limit 10); `main.py` +2 lines (limit: one import and one include); no `schemas.py`, `views.py`, `client.ts` or `apps/web` touched. The model of Dwight's M1 (JSONB cast with bound values), M2 (clean_text first, `<`/`>` last), M3 (plain `str | None`, `re.fullmatch`, fixed 422), M4 (the thread opens its own session) are all visible in the code.
* **Count:** the gate shows 1142 passed; 80 of them are new (21 worker, 59 route), so the suite before this step was 1062 by subtraction (the baseline was not run on its own).
* **Proof run of the first full gate** (`g0`, deleted after use because the alembic line was wrong: `alembic check` on the test database, which pytest builds with `create_all`, says "not up to date"; the gate now checks on a fresh scratch database, upgrade head then check, the way step 8c did): `1142 passed in 243 s`, ruff clean, `gen:api` regenerated `openapi.json` and `api-types.ts` (+140 and +88 lines, only the new route and two models). Committed.
* **Hand check (real network, once each):** see section 5.

## 4. CLEANUP
Scope-locked `/refactor` read of the three production files this step wrote or changed (`news_worker.py` 115 lines, `api/news.py` 90, the `Source` change). One simplification: the nested `try/except: pass` around `session.rollback()` in the worker's `step()` is gone (the `with` block closes the session, which rolls back); no behaviour change, 21 worker tests and ruff re-run. No change needed: `api/news.py` (one route, one query, named constants, functions under 25 lines), `sources.py` (a defaulted field, no duplication). Left alone on purpose: a row whose title is empty after cleaning is dropped after `LIMIT 5`, so such a reply could hold fewer than 5 (the stored title was already cleaned at ingest, so this needs a hostile row written outside `run_news`; advisory, carried).

## Review round (between IMPLEMENTATION and CLEANUP)
Dwight's code review at `feeff66` (his own read plus `ecc:security-reviewer` and `ecc:silent-failure-hunter`): **PASS on security, no CRITICAL; 3 MEDIUM** (C1 the sweep and a still-live abandoned run overwrote each other; C2 a run that never ends stopped news with only a repeated warning; C3 a session that fails to open escaped the thread's error handler) and LOW advice (L1 to L10). Four red tests first (`a2838b5`), then **WO-3** (`wo-3.md`, Sonnet subagent, try 1): `8c7f5ee`. My own test for C1 first seeded the stale row before the start-up sweep (it was marked by that legitimate sweep): a mistake in my test, fixed so the row is written from inside the live run; I then broke the guard to see the test go red (1 failed), and restored the builder's change (I briefly reverted it with a `git checkout` by mistake and re-applied the same inspected diff by hand; the result is the committed file). Dwight's delta read at `8c7f5ee`: **PASS, no CRITICAL, HIGH or MEDIUM left**; new LOW N1 (a run stuck for good keeps its `running` row; honest, see the contract). Carried with reasons: L1 (prune runs only inside a completed step; while no step completes no new row enters, so the table cannot grow), L2, L3 and L4 (need a row written outside `run_news`), L9, and L5, L6, L10 as seam notes in the ROUTE CONTRACT.
`main` moved from `92adfbc` to `6658036` (steps 8b, 17) during this round; rebased cleanly (no conflicts, hashes changed: Dwight's `feeff66`/`8c7f5ee` are now `c96e64a` and its parents, same content), then `gen:api` showed no drift.

## 5. VERIFICATION
* **Hand check, real network, each feed ONCE through the landed guarded fetch (robots included), 10 s apart** (`handcheck_8g.py`, `handcheck-8g.log`, scratch database, dropped after): `espn [('ok', 27, None)]`, `cbs [('ok', 36, None)]`, 63 items stored, ties BUF 16, LA 16, SF 6; then `GET /api/news` for a made-up game between the two top-tied teams returned 200 with five items, titles clean, links `https://www.espn.com/...` / `https://www.cbssports.com/...`, newest first. Nothing else touched the network.
* **The gate, run twice in a row on `c96e64a`** (`res:gate-b` held; `gate.sh`, `h1-*`, `h2-*`): `pytest 1190 passed` (194 s, then 160 s; machine load 13 and 9.6 at start), `ruff All checks passed!`, `alembic No new upgrade operations detected.` (fresh scratch database: upgrade head, then check), `gen:api` no drift. (The first runs, `g1`/`g2` on `feeff66`, were also green twice: 1142 passed; they were before the review fixes and the rebase and do not count for HEAD.)
* **Lane guard** (`lane-guard.log`, base `6658036`), as printed: `OUT OF LANE: backend/nflpi/api/main.py, backend/nflpi/jobs.py, packages/shared/openapi.json, packages/shared/src/api-types.ts` (4 problems). These are exactly the granted seam edits of the Wire-lanes paragraph in `lanes.md` (2 lines in `main.py`, 3 lines changed in `jobs.py` against a limit of 10, the regenerated contract files); nothing else is out of lane.
* **Dwight (security):** design PASS (4 MEDIUM folded in before code); code PASS at `feeff66` (no CRITICAL; C1 to C3 fixed); delta PASS at `8c7f5ee` (no CRITICAL, HIGH or MEDIUM left). See the review round above.
* **Fresh critic** (new `ecc:code-reviewer`, no build transcript, own gate run on HEAD `12a5e15`, `res:gate-b` held): **PASS**. `1190 passed in 117 s`, ruff clean, alembic `No new upgrade operations detected.` (scratch database), `gen:api` 0 drift. Mutations, each caught by the one matching test: W2 (a fresh later `now` each step) red; W3 (`BLOCK_HOURS` 24 to 1) red; R3 (home team only) red; R6 (strip before clean) red; R7 (any allowlisted host) red. No FAIL finding. Advisories: no `red-worker.log` (worker red-first rests on commit order and the first-run numbers in section 3); the "80 new tests" count in section 3 is loose (the files hold 25 and 59 now); the checkout slip noted above; no rate limit on the route; a stuck run keeps its `running` row (N1).

## 6. LANDING
Not done by this lane. The integrator lands (no push, PR or merge here). Nothing was deployed; nothing touched the live app. What changes when it lands: the running worker starts a second background thread (`news-worker`) that asks ESPN and CBS for their public NFL feeds at most once per 30 minutes each, and the API gains one read-only route. No migration (the table landed with step 8c).

## ROUTE CONTRACT (for the web lead)
All routes need `Authorization: Bearer <token>` like every `/api` route (401 otherwise).

**`GET /api/news?game_id=<game_id>`**
* Query: `game_id` (string; the app's game id, 1 to 32 characters of letters, digits, `-` and `_`). It is declared optional in the OpenAPI file on purpose (so FastAPI cannot echo a bad value); the server answers 422 when it is missing.
* 200 reply (`NewsOut`): `{"game_id": str, "items": [NewsItemOut]}`, at most 5 items, newest first (dated items first by `published_at`; undated after them). `NewsItemOut` = `{"title": str (<= 200, plain text, never HTML, no `<` or `>`), "source": str ("ESPN" or "CBS Sports"), "published_at": ISO datetime | null, "url": str | null, "tags": [str]}`. `tags` is any of `coach`, `injury`, `playcaller`, `trade`, sorted. `items` is `[]` when there is no news (also when every feed is blocked or the worker is off): the screen must work with zero.
* 401 missing/wrong token. 404 `{"detail": "Game not found"}` (unknown game id). 422 `{"detail": "game_id must be 1 to 32 letters, digits, - or _"}` (missing or malformed; the value is never echoed). 405 for any method but GET.
* Typed client: `NewsOut` and `NewsItemOut` are in `packages/shared/src/api-types.ts` (regenerated); lane web adds the fetch function to `client.ts` (not done here, not this lane's file).

**Notes for the screen (Dwight L5, L6, L10, N1):**
1. Render `title` and `source` as TEXT only (React text nodes; never `dangerouslySetInnerHTML`). A feed that double-encodes can leave a literal `&lt;` as text.
2. `url` is `null` for an unsafe link: then show no link at all (never guess one). Otherwise render `rel="noopener noreferrer"`, opened by the user only, and show the age from `published_at`.
3. An empty list cannot tell "no news" from "feeds blocked / worker stopped". For a "stale" badge the screen needs freshness from `ingestion_runs` (datasets `news:espn`, `news:cbs`; a block shows `error` starting `blocked:`), which is a `views.py`/`schemas.py` change in lane web's files (SEAM: not done here). A run stuck for good keeps its `running` row until the worker restarts (the error log says so every 10 minutes).
4. No rate limit on the route (one token, one user, read only, no network); an app-wide item for god.

## Final re-gate after the last move of main
`main` moved once more (`b387f33`, two docs files only). The branch was put on it again (the code diff against main is byte-identical to the one the critic passed: `cmp` showed no difference). The gate, run twice in a row on the final tree (`k1-summary.txt`, `k2-summary.txt`): `pytest 1190 passed` (161 s, then 150 s), ruff clean, alembic `No new upgrade operations detected.` (scratch database), `gen:api` 0 drift, both runs. The critic's verdict (on `12a5e15`, same code) is therefore not repeated.
