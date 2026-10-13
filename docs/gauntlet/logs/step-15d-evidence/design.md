# Step 15d (server side): design for review (lane livewire)

Server only. Reads `step-15a.md` ("carried to the wiring step"). Adds `backend/nflpi/live_worker.py`, `backend/nflpi/api/live.py`, tests, and seam lines (`api/main.py` 2 lines, `jobs.py` <= 10 lines, regenerated `openapi.json` and `api-types.ts`). No migration, no screen, no new dependency, no new setting.

## Worker (`live_worker.py`)
It runs in its OWN daemon thread started from `jobs.loop` (one call). A hung source can therefore never stall the main loop (the 300 s tick and the refresh cycle). Each wake (5 s) opens its own session, never shares one with the main loop.

* **W1 in play.** A game is "in play" at `now` when `kickoff <= now < kickoff + 8 h` (was 5 h; changed after review: a weather delay can pass 5 h, and the API shows a game for 8 h) and its newest `live_states` row is not `post`, or is `post` with `home_wp` still null (the final summary is retried until stored). A "window" is the same test with `kickoff <= now + lead`.
* **W2 no game, no call.** With no game in play and none inside a quote window, a wake makes ZERO fetches of any source and writes nothing.
* **W3 ESPN.** While a game is in play, every wake calls `refresh_live_games` (the adapter spaces real fetches 30 s apart and skips quietly inside the gap). Over a 3 h game: 300 to 360 real scoreboard fetches.
* **W4 quotes (frozen schedule).** Kalshi: only inside a 2 h lead window or in play; the worker spaces its attempts 120 s apart (adapter floor 60 s). Odds API: only inside a 24 h lead window or in play; spaced 6 h apart (adapter floor 6 h). The next-due time is set after every attempt, whatever the result.
* **W5 Odds budget.** Worst case 4 calls a day = 124 a month at 1 credit each, against 500 credits and a hard stop below 50. Proved by a 31-day simulation with a game every day: calls <= 124 and the fake credit header never below 376; and a header of 49 stops all calls for 35 days (adapter rule, exercised through the worker).
* **W6 run deadline (carried S4).** Every source run gets a `get` wrapper that raises `FetchError("deadline")` for any fetch started after the run's deadline (ESPN 45 s, quotes 45 s). One run is then at most deadline + one fetch (<= 20 s by the fetch guard), not 17 fetches.
* **W7 killed run (carried I8).** If the process dies inside a run: the `ingestion_runs` row stays `running` (decided: it is real evidence), the source stays reserved (`blocked_until` committed BEFORE the fetch, 15a L14) so a restart does not refetch at once, and no half-written `live_states` or quote exists (nothing was committed). On start the worker marks `running` rows of the live sources older than 10 min as `failed`, error `interrupted`, and touches nothing else (fresh rows, other sources, `ok` rows).
* **W8 isolation.** An exception in one source, or in the window queries, is logged by class name only (no message: an exception text can carry a URL or key) and never stops the other sources or the thread.
* **W9 jobs.py.** `loop()` starts the thread; the function returns immediately; the thread is a daemon.

## API (`api/live.py`, one route)
`GET /api/live`, no query, no body, mounted in `main.py` with the same token dependency as the `api` router (`include_router(..., dependencies=[Depends(require_token)])`, because importing `require_token` from main into the router file would be a circular import).

* **A1** no / wrong token: 401 (same dependency). **A2** exactly one route, GET only.
* **A3 which games.** Newest `live_states` row per game; returned when state is `in` or `lost` and kickoff is within 8 h, or `post` and the kickoff day (US Eastern) is today (Eastern). `pre` games, old finished games and a stuck `in` older than 8 h are not returned. Ordered by kickoff then game id; **at most 20 games** (the reply size is bounded).
* **A4** per game: `game_id, state, home_team, away_team, home_score, away_score, period, clock, home_win_prob, kalshi_home_prob, updated_at`. `home_win_prob` is ESPN's number as stored; a null stays null, **never 0.5** (a stored 0.0 or 0.5 is ESPN's own and is passed through).
* **A5 Kalshi.** `kalshi_home_prob` = newest `kalshi` quote of kind `live` (its `home_prob`, null stays null), only when the game state is `in`, `last_confirmed('kalshi')` is at most 5 min old AND the quote row itself is at most 15 min old (an unchanged poll adds no row, so row time is not freshness: same lesson as 15a I2). Otherwise null. A `pregame` quote is never shown as live.
* **A6 stale.** Reply-level `stale` = at least one returned game is `in` or `lost` AND `last_confirmed('espn_live')` is missing or MORE than 120 s old (exactly 120 s is not stale). Changed after Dwight's K3: once every game is final the worker stops calling, so an old poll then is expected and must not raise a false alarm. Reply also carries `last_confirmed_at`. `updated_at` per game is when that game's numbers last changed.
* **A7** a `lost` game is returned with its last numbers and `home_win_prob` null.
* **A8 read only.** The route writes nothing and makes no network call; the reply holds no key, URL or error text.

## Security notes for Dwight
Auth: unchanged dependency. Input: none (no parameters). DB: ORM only. External calls: all through the 15a fetch guard (hosts, DNS pin, caps). Log: class names only. Reply: bounded, validated strings only (15a stores only fullmatch-checked strings).

## Dwight's design review (PASS to build, H1-H5) and how each is folded in
* H1 restart test (a new worker object at now+1 min, no second Odds call): added, `test_a_restarted_worker_cannot_spend...`.
* H2 a skipped or failed summary stores `home_win_prob` null: decided NOT to carry the old value forward (missing stays missing, 15a rule). Contract for the web: `home_win_prob: null` on a game in play means "no probability right now"; the next good poll (about 30 s) restores it. One fetch is up to about 40 s worst case (DNS 5 s + connect 10 s + 20 s body), so one run is at most about 85 s; still bounded.
* H3 sweep matches source AND dataset (espn/live_scores, kalshi/market_quotes, oddsapi/market_quotes): test with a running `head_coaches` row.
* H4 DEBUG-on-every-logger test through the real fetch path; jobs.py never touches the http loggers.
* H5 `kalshi_home_prob` also needs the quote ROW to be at most 15 min old (A5 amended).
* H6 (owner yes for Kalshi/Odds): recorded as D59 in OWNER_DECISIONS_2026-10-12.md ("Kalshi is fine", Odds key supplied); no new setting. For god.
* LOW: first ESPN back-off stays 15 min (15a rule); the thread logs "live worker started"; the API reads the newest row only for games in the kickoff window.

## Review round 1 (ecc:code-reviewer, ecc:silent-failure-hunter) and what was done
Fixed with red tests first: (1) the API candidate floor was `max(today_start, now-8h)` (Codex deviated from the work order, which said `min`): an `in` game past midnight Eastern vanished, and an early final vanished by 10 PM; now `min`, two tests. (2) worker window 5 h -> 8 h to match the API. (3) a `post` row with null `home_wp` stays in the window so the summary is retried (silent-failure #3).
Carried, with reasons (see step-15d.md): null `home_win_prob` after a failed or deadline-cut summary is kept as null (project rule: missing stays missing; Dwight H2 accepted either); log rate limit; `rollback` inside the failure handler; no thread supervision; ESPN gap while a slow quote source runs; schedule times use the step's start time; quote row older than 15 min is null even if unchanged (Dwight H5).
