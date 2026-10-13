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
* **Security design review first (required):** this section and section 2 go to Dwight before any code.

## 2. SPECIFICATION (frozen before production code)
Files: `backend/tests/test_news_worker.py`, `backend/tests/test_news_api.py` (red first). Public seams: `news_worker.news_step`, `news_worker.run_with_deadline`, `news_worker.run_forever`, `news_worker.start`, `news_worker.sweep_stale_runs`; router `news_api.router` (`GET /api/news`).

### 2a. Worker clauses (W)
* **W1 (a step polls and stores).** `news_step(session, now, ...)` calls `run_news` once with the sources it is given, and stores the recorded items, tied by team.
* **W2 (never more often than every 30 minutes).** Driven by the real `run_forever` loop on a fake clock for 3 hours, once with the real wake and once with the wake forced down to 1 second, each source is requested at most once per 30 minutes and never twice within 30 minutes. The guarantee comes from `run_news`; the schedule must not defeat it (the step passes the real `now` and never resets the history).
* **W3 (a blocked source stays quiet 24 hours).** A source answering 403 is requested once, not again for 24 hours, while the other source keeps its 30 minute rhythm. The worker never changes how it asks (same user agent, no proxy).
* **W4 (every source blocked).** `news_step` returns without raising; every run is `failed` with `blocked:`; old rows are still pruned.
* **W5 (prune every wake).** A row fetched 31 days ago is gone after a step, a row fetched 29 days ago stays; true when the step polls nothing (not due) and when everything is blocked.
* **W6 (teams first).** With an empty `teams` table a step makes no request and writes no `ingestion_runs` row.
* **W7 (a deadline).** `run_with_deadline(fn, seconds)` returns by the deadline when `fn` hangs, reports it did not finish, and the caller is not blocked. While the abandoned run is alive no second run starts (one run in flight at most).
* **W8 (the loop survives).** A step that raises (any exception) is logged by exception class name only (never the message) and the loop wakes again; `stop` ends the loop.
* **W9 (stale `running` rows).** At start-up `running` rows of dataset `news:*` older than 10 minutes become `failed` / `interrupted`; younger ones and every other dataset are untouched.
* **W10 (wiring).** `jobs.loop` starts the news thread exactly once, after the live thread; `jobs.py` calls into `news_worker.py` and holds none of the logic.

### 2b. Route clauses (R) — `GET /api/news?game_id=<id>`
* **R1 (token).** No token or a wrong token: 401, nothing else in the body. Right token: 200.
* **R2 (reply shape, frozen).**
  ```
  200 {"game_id": str, "items": [ {"title": str(<=200), "source": str, "published_at": datetime|null, "url": str|null, "tags": [str]} ]}
  ```
  Exactly these keys, nothing more (no ids, no extract, no player ids). `source` is the display name (`ESPN`, `CBS Sports`), not the id. `published_at` is null when the feed gave none (never invented). `tags` are only from `injury|trade|coach|playcaller`, sorted, each stored tag outside that set dropped.
* **R3 (which items).** Items whose `team_ids` contain the game's home team or away team; items tied to neither, or to other teams only, are not returned. Items from a source id that is not in `sources.SOURCES` are not returned.
* **R4 (at most 5, newest first).** Order: `published_at` newest first, items with no date after all dated ones, then `fetched_at` newest, then `id` highest. 0 items is `{"game_id": ..., "items": []}` with 200.
* **R5 (unknown or malformed game).** An unknown `game_id`: 404 with a fixed message. A missing, empty, longer than 32, or non `[A-Za-z0-9_-]` `game_id`: 422. No stack trace, no echo of the value.
* **R6 (plain strings only).** No returned string holds `<` or `>`; a stored title like `<b>Hi</b><script>x</script>` comes back with no markup characters. Titles are cut at 200, control characters and bidi marks are gone, whitespace is collapsed.
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
