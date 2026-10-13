# Step 15 (backend half) of 17: Live scores, live win probability and market quotes (new tables, adapters, no wiring)

Session: owner's Mac, 2026-10-13 (night, US Eastern), lane `live` (worktree `.claude/worktrees/lane-live`, branch `lane/live`, base `main@53b1c89`), run beside lanes alerts, news, model, scores, group.
Coordinator: Claude (hive temp "Pam", dispatched by the integrator). Builder: Codex. Lane claim `claims/live`, coord task #15.
Evidence folder: `docs/gauntlet/logs/step-15a-evidence/` (design.md, gate.sh and its logs, baseline, hand checks, reviews/).
Rows covered from `docs/gauntlet/PLAN.md` row 15 and `research/odds-live-plan.md` Part 3: **15a** insert-only quote table, **15b** Kalshi adapter, **15c** Odds API adapter, **15d** ESPN live state (server side only), **15g** per-source failure handling. NOT in this step: worker loop (`jobs.py`), API routes and schemas, web, the model candidate (15e), in-game grading (15f).

KNOWN LIMIT (read first): no NFL game is in progress until Thursday 2026-10-15 (SEA @ DEN). Everything "live" here was built and tested against real finished-game replies plus in-progress replies **made by hand** from them (state, period, clock, score and win probability edited). **"Checked against a real live game": PENDING, 2026-10-15** (first Thursday kickoff 8:15 PM ET; then Sunday 2026-10-18). Behaviour not seen live: how fast ESPN's win probability updates, whether it can lag or vanish, whether Kalshi game markets stay priced during play.

## 1. PLANNING
* **In the owner's words (D55, 2026-10-13):** "can we also add realtime scores please for each game until the game ends if the game is going on". His yes on hive card HAG-40 to all five picks of the odds plan Part 4 (Kalshi quotes, Odds API key, ESPN win probability next to the market, display only). 2026-10-13: "Kalshi is fine" (he read Kalshi's Developer Agreement) and he supplied a free Odds API key.
* **What this step builds / replaces / is not:** builds the server half of live scores and market prices (three new tables, three guarded adapters, one function the worker will call, one query the API will call). Replaces nothing (final scores still come from nflverse; the games table is untouched). It is not visible to the owner yet: no route, no screen, no worker call.
* **Roadmap:** PLAN.md row 15 after step 7. **Tier:** T2. Reversibility: two-way (three new tables with a clean downgrade; nothing existing changes).
* **Decisions relied on:** D55; HAG-40 picks; `CLAUDE.md` data rules (never invent data, insert-only, failed ingestion keeps old data); the plan's untrusted-input guard list; picks lock at kickoff and nothing here can change a locked pick (display and grading only).
* **Pre-flight:** Problem: the owner cannot see a game's score or who is winning while it is on, nor what the market thinks. Why now: week 6 starts Thursday 2026-10-15. Scope: smallest backend that stores and serves live state and quotes safely; cut: UI, polling loop, model use of quotes. Success signal: after the first live Thursday, `live_states` rows exist for the game and the last row equals ESPN's final score and win probability. Reversibility: two-way.
* **Assumptions:** `validated` ESPN scoreboard and summary shapes (recorded 2026-10-13, 15 finished games, 3 summaries incl. a 27-27 tie and an OT game); `validated` Kalshi `KXNFLGAME` shape (56 markets, 28 events) and Odds API `h2h/us` shape (14 events, 9 books, header `x-requests-remaining`); `assumed` ESPN/Kalshi behaviour during play (see KNOWN LIMIT); `assumed` the owner's key has 500 credits/month (header said 499 after the first call).
* **Skills:** `/jevgrep`, `/graft`: used by reading `ingestion/nflverse.py fetch_head_coaches` and lane news' `fetch.py` directly (named in the dispatch); `jg` not run (`JEVGREP: not-checked`). `/tdd`: first failing tests written before any production file. `/ponytail`: stated in every work order. `harness-engineering`: N/A (no runner or approval boundary; the worker wiring is a later step). Design Gauntlet: N/A (no UI).
* **Tools:** `codex-cli 0.156.1`. Codex's sandbox cannot reach Postgres or the network, so every proof was rerun by the coordinator (Gauntlet lesson 6).
* **Test database:** own container `nflpi-lane-live-db`, `127.0.0.1:15447`, no volume. The live stack (5432, 8000, `nfl-pickem-app-*`) was never touched.
* **Baseline at `53b1c89`** (pytest on the lane DB): 183 passed, exit 0 (`step-15a-evidence/baseline-pytest.log`). (I did not check that `coord lock res:gate` was granted before this one run; the later gate runs do.)
* **Real network use (all recorded):** ESPN: 1 scoreboard + 3 summaries to record fixtures, then 1 scoreboard + 3 summaries (adapter) + 3 summaries/1 scoreboard (independent re-fetch) in the hand check. Kalshi: 1 call to record + 1 in the hand check. **Odds API: 2 of the 3 allowed calls** (1 to record the fixture, 1 in the end-to-end hand check; 499 credits left after the first, about 498 after the second). Key never printed, logged or committed; `gate.sh keyscan` greps every file for it.
* EFFORT: PLANNING and SPECIFICATION high; IMPLEMENTATION low (Codex builds; the coordinator only dispatches and reruns); CLEANUP low; VERIFICATION high.

## 2. SPECIFICATION
Public seam (names pinned by `backend/tests/test_live.py`):
* `nflpi.ingestion.live.fetch.fetch_json(url, resolver, transport, clock) -> JsonResult(status, data, headers)`; `FetchError`, `Blocked`.
* `nflpi.ingestion.live.run.refresh_live_games(session, get, now)` (**the one function for the worker**), `refresh_kalshi_quotes`, `refresh_odds_quotes(..., api_key)`, each returning `RefreshResult(source, status ok|failed|skipped, inserted, skipped, detail)`.
* `nflpi.ingestion.live.store.live_states_for(session, game_ids) -> {game_id: LiveState}` (**the one query for the API**: newest row per game).
* Models `LiveState` (`live_states`), `MarketQuote` (`market_quotes`), `SourceStatus` (`source_status`); migration `0006`; setting `odds_api_key`.

Gate: `backend/tests/test_live.py` (267 cases), then `bash docs/gauntlet/logs/step-15a-evidence/gate.sh <label>`: full pytest (a skipped test is a failure), ruff, the migration up/check/down/up/check on an empty database, `npm run gen:api` with no drift, and a scan that the real Odds key appears in no file.

| # | Criterion | Layer |
|---|---|---|
| L1 | The games table and every existing column are unchanged; three new tables exist with the planned columns; the migration upgrades and downgrades cleanly | functional |
| L2 | Fetch guard: only the three exact hosts over https; DNS resolved once, every answer must be public (private, loopback, link-local, NAT64, 6to4, Teredo, CGNAT refused), IPv4 preferred, request pinned to the checked address with Host and SNI; no proxy from the environment; redirects never followed; 10 s timeout, 20 s deadline, 2 MB cap; compressed replies refused; JSON only; hung DNS cut at 5 s in a daemon thread | operational |
| L3 | Errors carry only a class name or a fixed word/status; never a URL, header, query or reply text; `httpx`/`httpcore` do not log URLs | operational |
| L4 | ESPN: three recorded finished games store final score, last win probability (including 27-27 → 0.5), play id; re-poll inserts nothing; summary fetched only for games `in`, or just ended; at most 16 per poll; links in replies are never fetched | functional |
| L5 | ESPN orientation: scores follow team codes, win probability flips when ESPN's home is our away; unmatched or ambiguous events are skipped and counted | functional |
| L6 | Strict parsing: bad score, period, clock, win probability become null; bad state, event id (non-ASCII digits, trailing newline), team skip the event; every stored reply-derived string passes a fullmatch pattern | functional |
| L7 | A refresh never writes `games`; `live_states_for` returns the newest row per requested game only | functional |
| L8 | Kalshi: markets grouped per event, ticker parsed against the known code set (unique parse), both teams required; home probability = mid(home)/(mid(home)+mid(away)), overround kept, raw bid/ask of the home team stored; JAC→JAX, LAR→LA; kind pregame/live by kickoff; an empty book side (0/1) has no price; paging at most 3 pages | functional |
| L9 | Odds API: one call per run; one quote per book per matched game, outcomes matched by club name, no-vig via the existing `novig_home_prob`; no key (or a key failing `[A-Za-z0-9]{16,64}`) → nothing happens and it says so; credits header parsed strictly; fewer than 50 credits left → stop for 35 days, then one call refreshes the count; a missing header never erases the last known count | functional |
| L10 | The key appears in no log record (DEBUG), no `ingestion_runs`, `source_status` or stored row, and no exception text or cause, on ok, 401, timeout and bad-JSON paths | operational |
| L11 | Per-source failure handling: any failure or block → that source only backs off 15 min doubling to 24 h (never overflows); after a success it waits its minimum interval (ESPN 30 s, Kalshi 60 s, Odds 6 h); one attempt per call, no retry; old rows kept; every attempt is one `ingestion_runs` row; inside a back-off nothing is fetched or logged; a database error at commit still ends the run failed with a back-off | operational |
| L12 | A reply of 3 or more items where none is usable is a format change: the run fails and backs off (not "ok, 0 rows"); fewer stay plain skips | operational |
| L13 | Quotes are only matched to games kicking off within 3 days before now or later | functional |
| L14 | The next allowed time is committed under a row lock BEFORE the fetch (a crash loop or a second process cannot spend credits); source times are bounded to 2000 to 2100 and can never raise; a moneyline above 100,000 or a swapped-orientation probability outside 0..1 is not stored; the API key cannot reach a log even if the http loggers are turned up | operational |
| L15 | A reply with 3 or more usable events and no matching game, or 3 or more live/finished events with no readable score, fails the run; a one-sided Kalshi book (no bid or no ask) has no price; quote dedupe includes `kind`; source times keep real past values (an old line looks old) | operational |
| L16 | `store.last_confirmed(source)` = last good poll (the API step's staleness clock, since an unchanged poll adds no row); a game stored as `in` that is missing from a good scoreboard reply gets one `lost` row with its last numbers (never for finished games, never on a failed poll) | operational |

Decisions (each two-way): a **live_states history table** (insert-only, one row per change) instead of one mutable row, so step 15f can grade the series; **`source_status`** table for back-off and credits (credits cannot live in `ingestion_runs`, whose columns may not change); **Odds floor 6 h not 24 h** (Dwight suggested 24 h; plan budget 3 calls a day Wed to Sun; 6 h is at most 4 calls a day, about 120 credits of 500 a month); **no robots.txt check** for these three API hosts (Dwight agreed); spread and total columns of PLAN row 15a **left out** (nothing fetches them; add with the spreads market).
* `JEV: model:live:wo1 -> sol (0.80) effort xhigh (0.95)`; `wo2 -> sol (0.89), effort unsure (0.25)`; `wo3 -> sol (0.92), effort unsure (0.59)`; `wo5 -> sol (0.98)`. Where Jev was unsure on effort the coordinator took high (WO-2, WO-5) and xhigh (WO-3), because the code parses untrusted data. Model route was `advisor` for WO-1 to 3 (confidence below 0.8 on one key) but the pick was the same as the only workable choice (luna 0.02; astra needs the owner).
* **Security design review before any code:** Dwight, PASS with E1 to E8 (key leaks through exception text, key format and `urlencode`, fullmatch with `[0-9]`, stored strings from replies, strict types, minimum intervals, credits header, safe logging) and L1 to L6; each has its own test (`design.md` bottom). Asked god to record the owner's yes for Kalshi/Odds/ESPN terms in the repo (not found by Dwight).
* Red: the first run failed at collection with `ModuleNotFoundError: No module named 'nflpi.ingestion.live'` (right reason: the package did not exist). Spec commit `da3882c` (fixtures, design, first 100 cases), later cases added per work order before each build.

## 3. IMPLEMENTATION
| Work order | Rung (Jev/coordinator) | Commit | Proof |
|---|---|---|---|
| WO-1a guarded JSON fetch (ported from lane news `fetch.py`, plus encoding, resolve timeout, daemon thread, IPv4 first) | gpt-6-sol xhigh, try 1 | `d31acd9` | fetch tests green |
| WO-1b three tables, migration `0006`, `ODDS_API_KEY` setting, `.env.example` line, hardening list line | gpt-6-luna low, try 1 | `d31acd9` | table tests + `test_hardening -k migration` green |
| WO-2 ESPN parser, insert-only store, runner with back-off | gpt-6-sol high, try 1 | `1753e4c` | all ESPN, failure, query, hardening tests green |
| WO-3 Kalshi and Odds adapters | gpt-6-sol xhigh, try 1 | `26a8598` | 254 of 255 green; the one red was my test (the fixture is 7 days old) and I fixed the test |
| WO-5 review fixes R1-R9 | gpt-6-sol high, try 1 | `cb6710c` (with WO-6) | 265 of 267, then WO-6 |
| WO-6 restore the "no item is an object" shape rule | gpt-6-luna low, try 1 | `cb6710c` | 267 passed |
| WO-7 security review fixes S1-S3, S5, S6, S8, I1-I7 (reserve-before-fetch, `times.py`, key log filter, no-match and format-change failures, `last_confirmed`, one-sided books) | gpt-6-sol xhigh, try 1 | `d6cbdc7` | 296 of 299 green; the 3 reds were my tests (wrong constant for a fixture time; two tests that needed games near their `now`), fixed in the test file |
| WO-8 `lost` row for a game that drops off a good scoreboard reply (Dwight's second half of I2) | gpt-6-sol high, try 1 | `ee3d841` (after the move onto main) | 299 passed |
| Moved the branch onto main `a9ed486` (step 7 landed), as the integrator asked: clean, no conflicts | coordinator (`res:git-integrate` held, taken as the hook's session id) | hashes below this point are the moved ones | |
| Migration renamed `0006` to `0004`, `down_revision` stays `0003`, hardening list `0001, 0002, 0003, 0004` (integrator's ruling: numbers taken at landing time; main has 0001-0003) | coordinator, mechanical (3 lines) | `baee3a4` | |
* CLIMBS: none. STRIKES: none. Codex never ran astra or Fable. Every proof was rerun by the coordinator on the lane DB; Codex's own sandbox could not reach Postgres or the network.
* **Review fan-out at IMPLEMENTATION exit** (standard tier): `ecc:code-reviewer` and `ecc:silent-failure-hunter` on `26a8598`, reports in `step-15a-evidence/reviews/` (21 findings; 12 fixed with red tests first, the rest carried with the reason). `ecc:security-reviewer`: replaced by Dwight's full security review (he runs the same agents). AGENTS: ecc:code-reviewer, ecc:silent-failure-hunter, Dwight (security), Angela (general review); ecc:pr-test-analyzer not used (large tier only).
* **Mistake caught and undone:** running `ruff format` over the whole `nflpi` folder reformatted seven other lanes' files; I reverted those seven with `git checkout` before any commit (`git diff --stat` shows only lane files). Lesson: format only own paths.

## 4. CLEANUP
`/refactor` pass, scope-locked to files this lane wrote (WO-4, `76731c7`, luna medium; plus the cleanup items inside WO-5):
* `_odds_job` lost a catch-all wrapper that hid "status 401/429" behind "request failed" (the fixed status words now reach the run row);
* both quote jobs load only games kicking off within 3 days before now (was every game ever; one helper `_quote_candidates`);
* `safe_error` precedence made explicit; unreachable `total == 0` branch removed; duplicated back-off check removed from `refresh_odds_quotes`; parameter `run_source` renamed `ingestion_source` (it shadowed its function).
* **No change needed, with reasons:** `run.py` is about 410 lines holding three source pipelines (under the 800-line ceiling; splitting is carried); two `mark_ok` calls for the Odds source are kept (the second only adds the credit count, which is known after the job); `fetch.py` duplicates lane news' `fetch.py` on purpose (Dwight L3: merge into one module after both lanes land).
* Re-ran affected proof after every edit: 267 passed, ruff clean.

## 4b. Second review round (Dwight, security, at `cb6710c`)
Dwight (hive `dwight-mv5mkpow`, with his two ecc agents): **PASS on security, no CRITICAL or HIGH**; E1-E8 all met; fetch guard met. Conditions for wiring and what was done (each fix has a red test first, commit `33ca5c3`, built in WO-7/WO-8):

| # | Finding | Result |
|---|---|---|
| S1 MED | `blocked_until` written only after the job (crash loop or two processes spend credits) | FIXED: committed under `SELECT ... FOR UPDATE` before the fetch |
| S2 MED | `OverflowError` from odd dates fails the whole refresh | FIXED: one `times.parse_utc`, year 2000-2100, catches Overflow |
| S3 LOW | http loggers WARNING only at import | FIXED: logging filter drops any record containing `apiKey=` |
| S4 LOW | no per-run deadline (up to 17 fetches) | CARRIED to the worker step (it must wrap a run deadline) |
| S5, S6 LOW | swapped probability outside 0..1; moneyline 1e300 | FIXED |
| S7 LOW | migration number | DONE by the integrator's ruling (0004) |
| S8 LOW | quote growth; `live_states_for` loaded every row | query FIXED (newest row per game in SQL); retention CARRIED (rows are written only on change) |
| I1 | all-unmatched reply recorded ok | FIXED (3+ usable events and no match fails; counts logged) |
| I2 | unchanged poll leaves no new row, so `fetched_at` is not "last confirmed" | FIXED two ways: `last_confirmed(source)` for a stopped clock; a `lost` row when a game vanishes from a good reply. **API step rule: staleness = `last_confirmed("espn_live")` older than 2 minutes, not `LiveState.fetched_at`** |
| I3-I7 | credits-low stop invisible; failed summaries uncounted; int scores read as missing; old source time hidden; one-sided book | FIXED (logs, reason stored, 3+ no-score events fail, past times kept, one-sided = no price) |
| I8 LOW | no guard against a score going backwards; `kind` from the clock only; a Blocked summary backs off all of ESPN; a killed run stays `running` | CARRIED to the worker/API step |

Dwight did not exercise the TLS name check; the hand-check logs did (certificate verified against the hostname through the pinned address, real ESPN, Kalshi and Odds API replies).

## 5. VERIFICATION
(filled in after the final gate runs; see below)
