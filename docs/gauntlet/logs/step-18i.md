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
| V10 | Zero real Odds API calls: `nflpi.value` does no network I/O; tests use recorded-shape fixtures in `backend/tests/fixtures/value/`. No automated wagering. |

## Seams for the integrator (not edited by this lane)
- `ingestion/live/run.py` `_odds_job`: call `value.save_prices` for each matched book's `prices` (game side mapped as `_save_odds` does). Left to the integrator; run.py is not lane value's file.
- A config switch for `extra_markets` waits for the owner's yes to triple credits.
