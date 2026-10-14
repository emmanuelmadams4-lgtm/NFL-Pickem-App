# Step 18i: odds history and value ratings (lane value)

Base main `f1a072c`. Branch `lane/value`. Owner brief sections 8 and 9, decision D68. PLAN section 2 row 18i, section 3.4.

## Spec (frozen before tests)

Public functions: `nflpi.value.save_prices`, `nflpi.value.load_snapshots`, `nflpi.value.rate_price`, `nflpi.value.max_price_age`; `oddsapi.odds_url(key, *, extra_markets=False)`; `oddsapi.Book.prices`.

| # | Clause |
|---|--------|
| V1 | Table `book_prices` (model `BookPrice`, migration `0009`, down `0008`): one row per price a book showed for one selection at one time: `game_id` (games), `sportsbook`, `market_type` (`moneyline`, `spread`, `total`), `selection` (`home`, `away`, `over`, `under`), `line` (null for moneyline; spread line is the HOME spread, book sign: negative when home is favoured), `price` (American), `observed_at` (the book's own time), `fetched_at`. Unique on game, book, market type, selection, observed time. Insert-only. |
| V2 | `save_prices(session, game_id, sportsbook, observed_at, fetched_at, quotes)` checks every quote through `betting.MarketSnapshot` (bad market, selection, line or price raises `BettingError`, nothing is written) and rejects `observed_at` later than `fetched_at`. It inserts new rows and returns how many; a row whose key is already stored is skipped and never updated. |
| V3 | `load_snapshots(session, game_id, market_type, *, as_of)` returns, per book and selection, the newest stored price observed at or before `as_of`, as `MarketSnapshot`s. A price observed after `as_of` is never returned. |
| V4 | `odds_url(key)` asks for `markets=h2h` only (unchanged, one credit). `odds_url(key, extra_markets=True)` asks for `h2h,spreads,totals`. The caller passes the flag; the setting that would turn it on is not added until the owner says yes to the credits. |
| V5 | A parsed `Book` keeps its head-to-head fields unchanged and gains `prices`: the moneyline pair plus, when present and valid, a spread pair (home and away points finite, opposite, absolute value at most 60, valid prices) and a total pair (`Over` and `Under` with the same finite point in (0, 150], valid prices). A malformed spread or total market is dropped; the book and its moneyline stay. |
| V6 | Setting `value_max_price_age_minutes` (default 30, must be above 0). `max_price_age()` returns it as a `timedelta`. |
| V7 | `rate_price(snapshot, probs, *, now, max_age=None, qb_missing=False)` goes through `nflpi.picks.betting_advice` (not rebuilt): a stale or future price gives `NO_BET` (`STALE_PRICE`); expected value at or below 0 gives `NO_BET` (`NONPOSITIVE_EV`). `max_age=None` uses the setting. |
| V8 | No rubric is passed, so with no validation history every rating with positive value is `UNRATED` (`NO_VALIDATION_HISTORY`), never stars, until PLAN section 3.4 can be met. |
| V9 | No price is shown as still available: the rating carries the book, the price, `observed_at` and its age at `now`, and a note saying when the price was seen and that it may no longer be offered. No field or text claims the price is available, current or live. |
| V11 | `run.py` odds job (now lane value's file, god 14:09): each matched book's `prices` go to `save_prices` with sides as our game has them (Odds API home not our home: home and away swap, spread line negates; totals unchanged), `observed_at` = the book's time capped at `now`, `fetched_at` = `now`. The request stays `odds_url(key)` (h2h only); the credit-low guard and the `market_quotes` rows are unchanged. |
| V10 | Zero real Odds API calls: `nflpi.value` does no network I/O; tests use recorded-shape fixtures in `backend/tests/fixtures/value/`. No automated wagering. |

## Seams for the integrator
- A config switch for `extra_markets` waits for the owner's yes to triple credits.

## Evidence
- Commits: `894a496` spec + red tests, `d42f02a` implementation (Sonnet builder, lead fixed two parser edge cases and wired `run.py`), `4a308de` V9 test + sweep.
- `tests/test_value.py`: 62 passed. With test_live, test_live_worker, test_live_api, test_hardening, test_picks, test_betting_odds: 731 passed. Ruff clean.
- Mutation sweep (`step-18i-evidence/mutate.py`, log `mutation-sweep.log`): 34/34 killed, at least one per clause V1-V11.
- Migration on a scratch database: upgrade to 0009, downgrade to 0008 (table gone), upgrade again: OK.
- Lane-guard against origin/main: only the four granted seams (models.py append, migration 0009, config.py one setting, test_hardening.py one line).
- Critic (ecc:python-reviewer, fresh, no transcript) on `4a308de`: **PASS**. Three LOW notes, none acted on: no guard around `_save_book_prices` in the odds job (no raising path found), pick'em spread may store -0.0, `fetched_at` checked after quote validation (nothing written either way).
- Zero real Odds API calls; the job still asks for h2h only.

## Integrator review fix (finisher Kelly, 2026-10-14)
Integrator review on `455da03`: FAIL, two findings, both fixed and nothing else changed.
- HIGH, spread line convention. `betting.MarketSnapshot` keeps the HOME spread on both selections (`settle_spread(selection, home_line, ...)`, `no_vig_probabilities` needs one shared line). `oddsapi._spread_prices` stored the away selection with its own point (+3.5 when home is -3.5). Now both selections carry the book's home point. `run._save_book_prices` unchanged: on a flipped book it swaps the selection and negates the line, which now gives our home line on both rows. Tests at the old convention corrected (V1 `ALL`, V3, V5, V11 flipped rows: our home LV is +9.5 on both). New red-first tests: a parsed and stored away spread row, loaded by `load_snapshots`, settles `win` for a home win by 3 at -3.5 and the pair passes `no_vig_probabilities`; the same through the run.py flipped path (KC at LV, our home LV +9.5).
- MEDIUM, odds run safety. `_odds_job` now runs `_save_book_prices` inside `session.begin_nested()`; an exception logs a warning with `safe_error` and the run goes on, so the moneyline `market_quotes` rows are kept. Test (two cases): a malformed book price (no spread line on a flipped book) and a failing SQL statement; both leave the moneyline quote stored, the job `ok` and no book price row.
- Evidence: `test_value.py` + `test_live.py` 370 passed; ruff check and format clean on changed files. Mutation sweep re-run with the moved V5 and V11 lines plus two new V11 mutations (savepoint removed, catch narrowed): 36/36 killed (`mutation-sweep.log`).
- Critic (ecc:python-reviewer, fresh) on `6fd39d0`: **PASS**, spread convention checked against `betting/snapshot.py` and `betting/settle.py`; four LOW notes (broad `except Exception`, Python-error case relies on the flipped game, no skip count, test count unverified by critic).

### Dwight's security review of 455da03 (PASS with fixes): V1, V2, V3, V5
- V1: `oddsapi._pair` skips outcomes whose name is not a string (a list or object name raised TypeError out of `parse_events` and lost the poll). Test: list, dict and null names drop that market only.
- V2: `run.BOOK_CLOCK_SKEW` = 2 minutes. A book whose last update is further ahead of our clock is refused (it would re-insert the same price on every poll) and counted as dropped. The V11 test now polls at 15:04, so booktwo (15:05) stays inside the skew and is capped at now. Test: at 15:02 booktwo is refused, bookone saved, moneyline quote kept, job ok.
- V3: savepoint as above; the odds job logs `oddsapi book prices: N saved, M dropped` every run (asserted in the V2 test).
- V5: `config._HIDDEN_REPR_FIELDS` adds `odds_api_key` and `database_url` (config.py grant widened to that tuple by god). Test: repr of Settings shows neither.
- Not done here (carried): Dwight's V4, per-market last update and alternate lines, a precondition for switching spreads and totals on.
- Evidence: `test_value.py` + `test_live.py` + `test_hardening.py` 400 passed; ruff check and format clean on changed files; mutation sweep 42/42 killed (new mutations for skew, its size, the drop count, the name check and each hidden field).
- Critic (ecc:python-reviewer, fresh) on `67be3fc`: **PASS**; spread convention checked against `betting/snapshot.py` and `betting/settle.py`; savepoint and V1, V2, V3, V5 confirmed; four LOW notes, none acted on (broad except, skew refusal logged as a warning, duplicate names caught by the length check, no exact 2-minute boundary test).
