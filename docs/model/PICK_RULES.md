# Pick rules (step 18d)

Owner brief `docs/model/OWNER_BRIEF_2026-10-13.md` sections 3 and 9; decisions D68, D70. Package `backend/nflpi/picks/`. Pure functions: no database, route, migration, network call or dependency. Nothing imports it yet (wiring is step 18h).

## What it does
Four pick modes kept apart, plus a separate betting-advice answer:

| Mode | Question answered | Needs |
|---|---|---|
| `straight_up` | Who wins the game? | win and tie chances |
| `ats` | Who covers the pool spread? | home spread `h`, cover and push chances |
| `totals` | Over or under the total? | total, over and under and push chances |
| `confidence_pool` | Which unique weight goes on which game? | win and tie chances |

**Default mode is `straight_up`, labelled as an assumption** (`PickSet.mode_assumed = True`, label "Assumed: straight-up pick'em (pool rules unavailable)"). Passing a mode explicitly clears the flag.

**Every mode returns exactly one pick per input game, in input order, whatever the data.** Missing data gives a pick with a warning and a stated `basis`, never a gap and never `NO_BET`.

**Betting advice is a different function with a different input** (a price and settlement chances). It cannot see, change or remove a pick.

## Conventions
- **Spread sign (audit A13).** Functions take the brief's HOME spread `h`: home covers when `margin + h > 0`, pushes at 0, where margin is home score minus away score. nflverse `spread_line` has the opposite sign. The ONE place that converts is `home_spread_from_nflverse(spread_line)`, which returns `-spread_line`. Nothing else in the package converts.
- **Settlement is reused**, not rewritten: `nflpi.betting.settle` (`settle_moneyline`, `settle_spread`, `settle_total`), `SettlementProbs`, `expected_value`, `ensure_fresh`.
- **No simulator import.** Inputs are plain probabilities, so a simulator result, the stored win model or a test can feed them. The simulator's cover and over chances are labelled "not shown to beat a coin flip"; every ATS and totals pick carries the warning `NOT_SHOWN_TO_BEAT_COIN_FLIP` and no value rating is derived from them.
- Nothing is invented: a missing input stays `None` and produces a warning and a labelled fallback.

## Public API
```
PicksError(ValueError)

GameInputs(game_id, p_home_win, p_away_win, p_tie=0.0, home_spread=None, total=None,
           p_home_cover=None, p_away_cover=None, p_spread_push=None,
           p_over=None, p_under=None, p_total_push=None,
           expected_margin=None, expected_total=None,
           qb_missing=False, stale_inputs=False, market_home_win=None)       # frozen, validated
Pick(game_id, mode, selection, probability, expected_points, basis, line, warnings, weight=None)
PickSet(mode, mode_assumed, label, picks, warnings, expected_points)
Advice(status, stars, expected_value, reasons, provisional)
Rubric(ev_thresholds, validated=False, provisional=True)

home_spread_from_nflverse(spread_line) -> float
pick_straight_up(games, *, tie_rule="half", tie_break="first", close_band=0.05, disagree_band=0.15, mode_assumed=False) -> PickSet
pick_ats(games, *, push_rule="no_points", tie_break="first", close_band=0.05, ...) -> PickSet
pick_totals(games, *, push_rule="no_points", tie_break="first", close_band=0.05, ...) -> PickSet
confidence_pool(games, *, weights=None, tie_rule="game_id", win_tie_rule="half", ...) -> PickSet
make_picks(games, mode=None, **options) -> PickSet          # mode None = straight_up, assumed
grade_pick(pick, home_score, away_score) -> "win" | "loss" | "push"
pick_points(result, push_rule="no_points") -> float
betting_advice(snapshot, probs, *, now, max_age, rubric=None, qb_missing=False) -> Advice
```
`selection` is `home` or `away` (straight-up, ats, pool) and `over` or `under` (totals). `tie_break` `first` means home or over, `second` means away or under.

## Frozen clauses (each has a test and a mutation)
| # | Clause |
|---|---|
| P1 | `GameInputs` rejects: empty id; a probability outside [0, 1] or not finite; win + win + tie not summing to 1 (1e-9); cover, push set given partly or not summing to 1; over, under, push likewise; cover or over chances without the line they belong to (`home_spread` / `total`); a non-finite line |
| P2 | Straight-up picks the side with the larger share; share = win chance + half the tie chance under `tie_rule="half"`, win chance alone under `"loss"` |
| P3 | Exactly equal shares go to `tie_break` and add `EXACT_TIE_BREAK` |
| P4 | Straight-up pick's `probability` is the chosen share; `expected_points` equals it |
| P5 | Warnings: `CLOSE_CALL` when the chosen share is below 0.5 + `close_band`; `QB_MISSING`; `STALE_INPUTS`; `MODEL_DISAGREES_WITH_MARKET` when `market_home_win` is given and differs from `p_home_win` by `disagree_band` or more |
| P6 | ATS picks the side with the larger expected points: cover chance + (0.5 if `push_rule="half"` else 0) times push chance; equal goes to `tie_break` |
| P7 | ATS pick records the spread `h` as `line` and has `basis="model"` |
| P8 | No cover chances but `expected_margin` and `home_spread` given: pick by `margin + h` (above 0 home, below 0 away, 0 to `tie_break`), `basis="margin_fallback"`, warning `NO_COVER_MODEL` |
| P9 | No cover chances and no margin: fall back to the straight-up pick, `basis="straight_up_fallback"`, warnings `NO_COVER_MODEL` and, if `home_spread` is None, `NO_SPREAD` |
| P10 | Totals mirror P6 to P8 with over and under, `expected_total` against `total`, warning `NO_TOTAL_MODEL`; with neither chances nor expected total the pick is `tie_break`'s side, `basis="default"`; line recorded |
| P11 | Every ATS and totals pick carries `NOT_SHOWN_TO_BEAT_COIN_FLIP` |
| P12 | Every mode returns one pick per game, same order, for any mix of present and missing data; duplicate game ids raise `PicksError`; an empty list returns an empty set |
| P13 | `make_picks` with no mode is straight-up with `mode_assumed=True` and the assumption label; an explicit mode is not flagged; an unknown mode raises |
| P14 | Pool weights are unique; default `1..n`; custom weights must be `n` unique positive integers |
| P15 | Pool gives the largest weight to the largest straight-up share (maximizes expected points for additive scoring); expected points = sum of weight times share; a worked example equals the brute-force best over all permutations |
| P16 | Pool ties in share are ordered by `tie_rule`: `game_id` (ascending text) or `input_order`; same input twice gives identical weights |
| P17 | `grade_pick` uses `nflpi.betting.settle`: a spread pick pushes when `margin + h == 0`, a total pushes when the sum equals the line, a straight-up tie is a push; a pick without a line cannot grade ATS or totals (`PicksError`) |
| P18 | `pick_points`: win 1, loss 0, push 0 (`no_points`) or 0.5 (`half`) |
| P19 | `home_spread_from_nflverse(-3.0) == 3.0`; the conversion is not repeated anywhere else in the package |
| P20 | Advice: a stale or future price gives `NO_BET` (`STALE_PRICE`); expected value at or below 0 gives `NO_BET` (`NONPOSITIVE_EV`); both win over every other reason |
| P21 | Positive expected value with no rubric, or a rubric not `validated`, gives `UNRATED` with `NO_VALIDATION_HISTORY` and `stars=None` (D70) |
| P22 | Positive expected value with a validated rubric: stars = how many of the five increasing thresholds the value reaches; zero thresholds reached gives `UNRATED` (`BELOW_FIRST_THRESHOLD`); otherwise `RATED` with `provisional` from the rubric |
| P23 | `qb_missing` with positive expected value gives `UNRATED` (`QB_MISSING`), never `RATED` |
| P24 | `Rubric` rejects thresholds that are not exactly five, positive, finite and strictly increasing |
| P25 | Advice cannot remove a pick: `make_picks` output is identical whatever `betting_advice` returns (advice takes no picks and picks take no advice) |

## Not done here
- Sheet ordering with the AI tie-break evidence (`predictions/sheet.py`, `TIE_BAND`) is untouched; the pool function is the pure-probability ordering only. Merging them is a step 18h seam.
- Opponent-aware pool strategy (needs payout and opponent assumptions, brief section 3).
- Value stars stay `UNRATED` until the app has its own timestamped price history (D70).
