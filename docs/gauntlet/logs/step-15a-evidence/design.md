# Step 15a-d,g design (lane live) — for security review before code

Worktree `.claude/worktrees/lane-live`, base main `53b1c89`. Backend only; new tables only; no worker loop, route, schema or web.
Sources: odds-live-plan.md Parts 1-4 (owner yes on all five picks, 2026-10-13; "Kalshi is fine"; D55).

## Hosts (exact equality, https, port 443/none, no userinfo, redirects OFF, never follow a URL found in a reply)
| Host | Used for | Key |
|---|---|---|
| `site.api.espn.com` | `/apis/site/v2/sports/football/nfl/scoreboard`, `/summary?event=<digits>` | none |
| `external-api.kalshi.com` | `/trade-api/v2/markets?series_ticker=KXNFLGAME&status=open&limit=200` (+ `cursor`, max 3 pages) | none |
| `api.the-odds-api.com` | `/v4/sports/americanfootball_nfl/odds?regions=us&markets=h2h&oddsFormat=american&apiKey=…` | `ODDS_API_KEY` (server `.env`, config.py) |
`sports.core.api.espn.com` is NOT used (no `$ref` is followed). No robots.txt check: these are JSON APIs, not pages; ESPN's robots for site.api answers "Access Denied" (Kevin) and the owner accepted the ESPN term risk in D55.

## Fetch guard (one module, `ingestion/live/fetch.py`, adapted from lane news `fetch.py` after Dwight D1-D6/N2)
Allowlist of the three hosts only. DNS resolved once, every address must be `is_global` (ipv4_mapped unwrapped, NAT64/6to4/Teredo refused), request goes to the pinned IP with Host + SNI = hostname. `trust_env=False`, `follow_redirects=False` (any 3xx = failure, never followed). 10 s timeout, 20 s total deadline, 2 MB body cap read in chunks, `Accept-Encoding: identity`, content-type must contain `json`. getaddrinfo run in a worker thread with a 5 s timeout (news N2). 401/403/429 = `Blocked`. Errors carry only the exception class name or the status code, never a URL, header, or body text.
Key handling: the Odds API takes the key only as a query parameter. So: key read from settings only inside the Odds adapter; the `httpx` and `httpcore` loggers are set to WARNING in the fetch module (httpx logs full request URLs at INFO); no URL is stored in `ingestion_runs.error` or logged by us (host + path only); a test asserts the key text appears in no log record, no run row, and no stored row. Empty key = adapter returns "no key set" and does nothing (no network).

## What is stored (migration 0006, three NEW tables; no existing table or column changes)
- `live_states` (insert-only; a row only when a value changed): game_id FK, fetched_at, state (`pre|in|post`), home_score, away_score, period, clock (`m:ss` text), home_wp, tie_wp, last_play_id, espn_event_id. Final scores still come from nflverse; this table never writes `games`.
- `market_quotes` (insert-only; row only when the quote changed): game_id FK, source (`kalshi` | `oddsapi:<book>`), kind (`pregame|live`, by fetched_at vs kickoff), home_prob, away_prob (0..1, no-vig / normalized), raw_yes_bid, raw_yes_ask (home team's), overround, home_ml, away_ml, fetched_at, source_ts.
- `source_status` (one mutable row per source `espn_live|kalshi|oddsapi`): consecutive_failures, blocked_until, last_ok_at, last_error (class/status only), credits_left (Odds API header `x-requests-remaining`), updated_at. This is the backoff and credit memory. Every refresh also writes one `ingestion_runs` row (existing table) so freshness shows it.
Spread and total columns from PLAN row 15a are left out (nothing here fetches them; add with the spreads market).

## Untrusted-input rules on parse (strict; bad value = null + a count in the run, never a guess)
Pydantic models with `extra=ignore`, finite floats only, probabilities in [0,1], American odds |x| >= 100, scores int 0..200, period int 0..10, clock matches `^\d{1,2}:\d{2}$`, state in {pre,in,post}, ESPN event id `^\d{1,12}$` (we build the summary URL from it), list lengths capped (events <= 40, winprobability entries <= 2000, markets <= 500 over <= 3 pages, books <= 40). Response text (team names, titles, rules) is only ever compared with our own tables/constant maps and is never stored, logged or shown. No response text is passed to the AI. Oversized, non-JSON, or wrong-shaped reply = failed run, old rows untouched.
Matching: ESPN event -> our game by Eastern game date + team code set (constant alias maps WSH->WAS, LAR->LA); Kalshi event ticker `KXNFLGAME-<yy><MON><dd><away><home>` parsed against the known code set (JAC->JAX, LAR->LA); a split that is ambiguous or unknown = event skipped and counted; Odds API by full team name (constant map of 32) + commence date. Orientation: scores map by team code, not by ESPN `homeAway`; if ESPN's home is our away (neutral site), home_wp is flipped. Unmatched = logged (count + ticker/event id only) and skipped.

## Failure behaviour (15g)
401/403/429/redirect/robots-class/blocked-address = `Blocked`: that source stops for 15 min, doubling per consecutive failure to 24 h (`blocked_until`); any other failure also backs off the same way; success resets. While blocked, refresh does no network and writes no run. Never a retry loop inside one run (one attempt per source per call). Odds API: if `credits_left` < 50 (stored or just returned) the source does not call again for 35 days (ponytail: monthly reset day is unknown); one call per run; no live polling. The app works with all three sources off.

## Public surface for the worker/API (later steps)
`refresh_live_games(session, now=None, ...)`, `refresh_kalshi_quotes(...)`, `refresh_odds_quotes(...)`, `live_states_for(session, game_ids)` (latest row per game). Nothing is called from jobs.py or the API in this step.

## Questions for Dwight
1. Is dropping the robots check right for these three API hosts?
2. Is a query-string key acceptable given the logger + no-URL-in-errors mitigation?
3. Any host/guard missing for Kalshi pagination `cursor` (we append it only after `^[A-Za-z0-9_=-]{1,200}$`)?

## Dwight's reply (2026-10-13 06:24Z): PASS to build with E1-E8; folded in, one test each in `backend/tests/test_live.py`
- E1 key in exception text: errors are class name or status only and raised `from None`; no `log.exception` and no traceback for any source; test with a sentinel key on four paths (ok, 401, timeout, bad JSON) over caplog DEBUG, run rows, status rows, stored rows, `repr` of the error and its `__cause__`.
- E2 key must fullmatch `[A-Za-z0-9]{16,64}` else "no key set", no network; query built with `urlencode`.
- E3 every pattern uses `re.fullmatch` with `[0-9]` (never `\d`, never `$`). E4 book key `[a-z0-9_]{1,32}`, play id `[0-9]{1,20}`, source_ts parsed and refused outside [-7 d, +1 d] of fetch time.
- E5 strict types: ESPN scores are digit strings in the real reply (accepted, `[0-9]{1,3}`); bool/float/other types rejected; period/wp strict; any json error (RecursionError, int-digit limit) = failed run.
- E6 minimum interval after a success, stored in `source_status.blocked_until`: ESPN 30 s, Kalshi 60 s, Odds API 6 h (Dwight suggested 24 h; the plan's budget was 3 calls/day Wed-Sun, so 6 h = at most 4 calls/day, about 120 credits/month of 500); summaries per run cap 16.
- E7 credits header must fullmatch `[0-9]{1,7}` and be <= 1,000,000 else unknown (None); the 6 h floor is then the only spend limit and survives restarts (DB).
- E8 unmatched ids are logged only after passing their pattern, with `%r`, cut to 64 characters.
- L1 refuse any Content-Encoding but identity (done). L2 IPv4 preferred when pinning. L6 resolver thread is a daemon named `nflpi-resolve`. L3 duplicate of lane news `fetch.py`: carried to god (merge into one module after both land). L4 `live_states` grows one row per change, about 400 rows per game per 3.5 h at 30 s; no prune rule needed (about 120k rows per season). L5 migration number re-point at landing.
- Not recorded in the repo: the owner's yes for Kalshi / the Odds API key / ESPN terms (god's dispatch carries it: "Kalshi is fine", key supplied, D55). Asked god to record it.
