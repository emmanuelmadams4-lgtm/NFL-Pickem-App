# Step 18i part 2: spread and total prices on, honest price times, second Odds API key (lane value)

Base main `b5ee53f`. Branch `lane/value2`. Owner card HAG-74 (spread and total prices, yes) and the second key. Carries Dwight's V4 and V6 from `step-18i.md`. PLAN section 3.4 unchanged: ratings stay UNRATED.

## Spec (frozen before the tests)

| # | Clause |
|---|--------|
| P1 | The `book_prices` unique key becomes game, book, market type, selection, observed time, **line, price** (migration `0010`, down `0009`, `NULLS NOT DISTINCT` so a moneyline row, whose line is null, still dedupes). An alternate line, or a changed price under an unchanged time, is a new row; an identical row is still skipped, never updated. Downgrade keeps the first stored row of each old key. |
| P2 | `load_snapshots` returns, per book, the newest **complete pair** (both sides, one observed time, one line). A side seen at another time or on another line than its partner is never paired; a lone side is never returned. At one time with several lines, the most recently fetched pair wins. |
| P3 | Each stored price carries its **market's own `last_update`** (`Price.observed_at`), never the book's (the Odds API docs mark the bookmaker-level `last_update` deprecated and describe the market-level one as the last time odds were seen for that market). A market with no valid time stores no price (the book's time is not a stand-in). `Book.updated` is only the book's own field, or the newest market time when the field is absent; a malformed book time stays a skip. `run._save_book_prices` saves per market time, capped at now; a market whose clock is more than 2 minutes ahead drops the book's prices (savepoint, win-market quote kept). |
| P4 (V6) | A book with no usable win-market price keeps its spread and total prices (`home_ml`/`away_ml` are `None`; no `market_quotes` row is made for it). A book with no usable market at all is still skipped and counted. A second h2h market is ignored. |
| P5 | Setting `odds_extra_markets` (env `ODDS_EXTRA_MARKETS`), default ON: the odds job asks `odds_url(key, extra_markets=True)`, `h2h,spreads,totals`, 3 credits per request. OFF gives today's h2h-only request. |
| P6 | Setting `odds_api_key_fallback` (env `ODDS_API_KEY_FALLBACK`), default empty, hidden from the settings repr; one empty line in `.env.example`. The job uses the first key. When the reply is HTTP 401 (see below) it retries that run once with the fallback key and logs `oddsapi key slot primary|fallback ...` with the `x-requests-remaining` header, never a key value. No fallback, a malformed one, or one equal to the first: today's behaviour. The fallback failing too fails the run with the real reply. |

## Out-of-credits reply, from the public docs (no call made)

Read from `the-odds-api.com/liveapi/guides/v4/api-error-codes.html` and the v4 guide on 2026-10-14 (page fetch only, never the API):
- `OUT_OF_USAGE_CREDITS`: "The usage credit limit of the subscription has been reached for the month." The docs page does not print its HTTP status. Our fetcher (`fetch.fetch_json`) raises `Blocked("status 401")` for 401 and keeps neither body nor headers, so the job treats **401** as the out-of-credits signal. Retrying a 401 `INVALID_KEY` with the second key is harmless (one extra free call).
- `EXCEEDED_FREQ_LIMIT`: HTTP **429**, "the request was rate-limited", a burst limit of 30 calls per second. A second key does not cure it, so **429 never switches keys** (this is narrower than the dispatch text, which listed 401 or 429; the body that would tell them apart is not exposed by the fetcher, and 429 is documented as the rate limit).
- `x-requests-remaining`: credits left until the quota resets. A 200 reply with 0 left is a good reply: it is used, not re-fetched. With no fallback the existing "fewer than 50 credits" 35 day stop applies as before. With a fallback the stop is not set; the next run's first key answers 401 (free) and the run goes on to the fallback.
- Market-level `last_update`: documented in the v4 guide ("The market-level last_update field shows the last time our system saw odds for that market").

Alternate lines: the request asks the three featured markets only, so each book returns one line per market (`alternate_spreads` / `alternate_totals` are separate market keys we never ask for). The parser still takes a 2-outcome market only. The key and `load_snapshots` now keep and sort out alternates if they are ever stored.

## Spread sign check (against `betting/snapshot.py` and `settle.py`)
Unchanged and re-tested: both stored selections carry the HOME spread; a book whose home is our away swaps the sides and negates the spread line, totals unchanged. `test_v5_stored_away_spread_settles_on_home_line` and `test_v11_flipped_book_spread_pair_settles_on_our_home_line` still pass; the stored pair of a flipped book settles and passes `no_vig_probabilities`.

## Seams for the integrator
- `backend/tests/test_live.py`: one small autouse fixture (sets `ODDS_EXTRA_MARKETS=false` for that file) so its h2h-only request tests keep pinning the old request. The default is ON, so without it about 40 of its tests fail on the URL. test_live.py belongs to lane livegrade.
- `backend/tests/test_hardening.py` asserts the text `op.create_table` in every migration; `0010` only rebuilds a constraint, so it carries that text in a comment. If the assertion should allow constraint-only migrations, that is a one-line change to the test.
- Granted by the lane note: `config.py` (2 settings, one hidden tuple entry), `models.py` (the key), `.env.example` (one line), migration `0010`, the `test_hardening.py` list line (the formatter wraps the list to one name per line).

## Evidence
- `test_value.py`, `test_live.py`, `test_hardening.py`, `test_live_worker.py`, `test_live_api.py`, `test_picks.py`, `test_betting_odds.py`: 772 passed on `2a40aca`; after the critic fix, value + live + live_worker: 440 passed. Ruff clean on changed files.
- Mutation sweep `step-18i-part2-evidence/mutate.py`, log `mutation-sweep.log`: 39/39 killed, one or more per clause P1 to P6 (a first run had six survivors; tests were added for each and the sweep re-run).
- Migration on a scratch database: `step-18i-part2-evidence/migration.txt` (upgrade, duplicate refused including a null line, downgrade dedupes, upgrade again).
- Zero real Odds API calls: every test uses the recorded-shape fixture `fixtures/value/odds_api_all_markets.json` (now with market-level `last_update`, one market 30 s older than its book) or a fake `get`.
- No key or token value in code, tests, logs or messages (the tests use `a*32` and `b*32`).
- Build: lead wrote the code directly (small, tightly coupled change; no Codex or subagent builder).

## Six checkpoints
| # | Checkpoint | Result |
|---|-----------|--------|
| 1 | Spec frozen before tests | this table |
| 2 | Red first, then green | tests rewritten against the old code failed (key, pairing, URL, `Price` shape), then passed |
| 3 | One mutation per rule clause | 39/39 killed |
| 4 | Own tests and lint | ruff check and format clean on changed files |
| 5 | Fresh critic, no transcript | ecc:python-reviewer on `2a40aca`: **PASS**, 0 HIGH, 2 MEDIUM, 3 LOW. Fixed: a 35 day credits-low stop set before a fallback key was added is now lifted (test added); dead `credits[1]` removed. Not changed: per-slot credit tracking (MEDIUM 2, intended: the 401 is the switch signal); the migration test is a text check, the real up/down run is in `migration.txt`. |
| 6 | Lane-guard | flags only the granted seams (`.env.example`, `config.py`, `models.py`, `test_hardening.py`, migration `0010`) and `tests/test_live.py` (not granted; see Seams) |

## Security fixes (Dwight, PR #37, 2026-10-14)
| Finding | Fix | Commits |
|---------|-----|---------|
| W1 credit reserve unknown with two keys | Key choice rests on the `x-requests-remaining` header, kept per slot in `source_status` rows `oddsapi:primary` / `oddsapi:fallback` (`credits_left`, `last_ok_at`; no new column or migration). A slot whose last count is under 50 is skipped while another is usable; the last usable slot under 50 sets the 35 day stop; a skipped slot is asked again 35 days after its low count. One key behaves as before (an older single-key count on the `oddsapi` row counts as the primary's). | tests `6f9704b`, fix `457995f` |
| W2 dead primary invisible | Run detail: `primary answered; N credits left`, or `primary refused (401), on fallback; N credits left`. The same switch text is kept on the `oddsapi` status; both failing gives `Blocked: both keys refused (401)`. | `6f9704b`, `457995f` |
| W3 401 assumption | The 401 is only a second signal now; the header decides. A spent primary (count under 50) costs no refused call on later polls. | `6f9704b`, `457995f` |
| W4, W7 | Unchanged (LOW, accepted). W8 accepted by the integrator. | n/a |
| W5 h2h with no time still priced | `_book` takes an h2h market only with its own time: no time, no `home_ml`/`away_ml`, no `market_quotes` row, no `book_prices` row. | `6f9704b`, `457995f` |
| W6 raw header in log | Log carries `_credits_header` (parsed count or None). | `6f9704b`, `457995f` |

Tests: new or changed in `test_value.py`, committed red first (`6f9704b`; the first run failed on the old code), then green. Fresh critic (ecc:python-reviewer, no transcript) first said FAIL with 3 MEDIUM logic bugs, all fixed with tests: a legacy single-key count is copied to the primary slot; the stop ends when the earliest low slot is due; slot counts are committed so a later failure keeps them. Left as is: slot state is also shown only on the slot rows and the returned detail (LOW). `test_value.py`, `test_live.py`, `test_hardening.py`: 446 passed; ruff check clean. No real Odds API call, no key value anywhere.

## Critic fixes (PR #37, head 7641cf8 onward)

| Finding | Fix | Commit |
|---|---|---|
| M3 `_stop_until` could return a past time (primary low day 0, refused on day 36, fallback answers 20) | Only due times later than now are kept; test `test_critic_m3_a_stop_never_ends_in_the_past` | see git log |
| M1 stop not asserted | After the last usable slot goes under 50 the `oddsapi` row must have `last_error == "credits low"` and `blocked_until` = earliest due (mutation check: removing `mark_stopped` fails it) | |
| M2 legacy copy branch never reached | Test seeds `oddsapi` (20 left) with no `oddsapi:primary` row and asserts the copy and the skip | |
| M5 key leak | Parametrised over ok, switch, both-refused, zero-credit: no key value in run detail, `oddsapi*` rows or `IngestionRun.error`; both-refused also checks each slot's `last_error` | |
| LOW `_answer_note` | Uses `REFUSED` | |

Gate: test_value, test_live, test_hardening 453 passed; ruff clean (throwaway Postgres on port 15999, removed). Fresh critic (ecc:python-reviewer): items 1, 2, 3, 5 PASS; item 4 PASS WITH CAVEATS (vacuous `detail` clause, run log unchecked, conditional assert), all three fixed afterwards in test code only. Carried: other LOWs; `ruff format` nit at an older test.

## LANDING

**Landed 2026-10-14.** Critic fixes M1/M2/M3/M5 by a finisher (head `7250391`; 453 tests passed; fresh critic PASS on items 1, 2, 3 and 5; the later test-only commit reviewed by the integrator). Pull request #37: CI 9 of 9 green on `7250391` (D71). Merged as `ef68bab` at 15:28 UTC.

**Deployed:** deploy 11 to the owner's PC at `400677b`, 15:35 UTC (D73): migration `0010` applied with the worker stopped, row counts unchanged. **Second key:** the key the owner pasted is the one already set as `ODDS_API_KEY`, so `ODDS_API_KEY_FALLBACK` is left unset; the switch works once a different key is added.
