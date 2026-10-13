# Step 18b: odds, settlement and expected-value maths (lane odds)

Owner brief `docs/model/OWNER_BRIEF_2026-10-13.md` section 8 (formulas) and section 12 (tests); owner decision D68. Base `c55827f`, branch `lane/odds`. Tier T2 (new behaviour, nothing user-facing yet). One-way doors: none (new package, nothing imports it).

## 1. PLANNING
- Step goal: new package `backend/nflpi/betting/` (pure functions, standard library only, one exception type `BettingError`); no database, route, config change, migration, network call or dependency. Wiring is wave 2.
- Done when: every frozen clause below has a test that fails when the clause is broken; gate green; critic PASS; lane-guard OK.
- Pre-flight: problem = the model platform needs correct odds, settlement and value maths before any betting-value output; why now = wave 1 of step 18; scope = maths only, no data layer; success metric = the clause tests plus mutation sweep; reversibility = two-way (delete the package).
- Assumptions: validated: `predictions/market.py` (read only) gives the multiplicative no-vig; assumed: American prices with 0 < |A| < 100 are not quotable (rejected; the brief only names A = 0); assumed: a spread snapshot's `line` is the HOME spread on both sides.
- Skills: `/graft`/`/jevgrep` N/A (new package, one file read); `/tdd` used (tests first); `/ponytail` in the work order; Design Gauntlet N/A; harness-engineering N/A (no runner).
- Codex: `codex exec -m gpt-6-luna` tried once; refused with `Your workspace is out of credits`. Build moved to a Claude Sonnet subagent (Build Ladder rule 5).
- EFFORT: SPECIFICATION high (money maths); IMPLEMENTATION low (sonnet); VERIFICATION high.

## 2. SPECIFICATION (frozen clauses, each with a test)
| # | Clause (brief section 8) | Test file |
|---|---|---|
| C1 | American to decimal: A>0 gives 1+A/100, A<0 gives 1+100/abs(A); A=0 invalid | odds |
| C2 | invalid prices rejected (NaN, inf, bool, text, decimal <= 1, 0<abs(A)<100) | odds |
| C3 | raw implied probability q = 1/decimal; same numbers as `predictions/market.py` `implied_prob` | odds |
| C4 | proportional no-vig p_i = q_i / sum(q) | odds |
| C5 | no-vig only inside one complete set: same game, book, time, market and line; mixed sets rejected, not averaged | odds |
| C6 | two-way and three-way moneyline; three-way without the draw price is unavailable (None), not a two-way guess | odds |
| C7 | stale odds rejected by a maximum age (equal to the maximum is fresh; future-dated rejected) | odds |
| C8 | settlement: spread M+h>0 win, =0 push; total over/under/equal push; two-way tie push, three-way tie pays the draw | settle |
| C9 | conditional probability when pushes are refunded: P(win)/(P(win)+P(loss)) | edge |
| C10 | four numbers separately: fair-market probability edge, price edge, EV per unit, signed point difference | edge |
| C11 | EV = P(win)(d-1) - P(loss); a refunded push adds zero | edge |
| C12 | edge keeps its sign (never the absolute difference) | edge |
| C13 | missing opposing price: fair edge is None (never 0), EV still computed | edge |

Generated-input checks (plain seeded loops, no new test dependency): no-vig sums to 1 (2000 sets), price round trips (American and decimal), EV zero at break-even (2000 cases with and without a push), home and away never both win (exhaustive spread and total loops), agreement with `devig_home_prob` on 1000 generated moneyline pairs. End to end: EV equals the probability-weighted realised profit on a small offline score distribution, for 12 selections across moneyline, spread and total.

Choices recorded: fair-market edge compares the model's conditional win probability with the no-vig probability (brief: "where pushes are refunded, compare probabilities conditional on a non-push result"); point difference is signed from the selection's side (spread home: forecast margin + h; away is the negative; over: forecast total - L; under: L - forecast total).

First failing test: commit `dd71b65`, `ModuleNotFoundError: No module named 'nflpi.betting'` (red for the right reason: the package does not exist).

## 3. IMPLEMENTATION
- `56f37de`: package built by a Sonnet subagent from a bounded work order (files: odds.py 55 lines, snapshot.py 101, settle.py 57, edge.py 124). Coordinator reran the proof itself: 245 passed. The builder did not commit and did not touch tests.
- Lint: six ruff findings in my own test files fixed by me (line length, `zip(strict=)`); not the builder's.

## 4. CLEANUP
`51d44ae` (scope-locked `/refactor` equivalent, via the same builder): one `decimal_price` helper replaces two copies of the "decimal > 1" check; one `_side` helper replaces two copies of the win/loss/push flip; `evaluate` reuses `price_edge`. Tests 245 passed before and after.

## 5. VERIFICATION
- Mutation sweep (stdlib `mutate.py`, 128 mutation sites, 142 s, lock `res:gate-c`): 122 killed, 6 survivors. 4 equivalent (strict zip, `margin > 0` after a zero check, `a > 0` after the |A|>=100 check, twice). 2 real gaps killed by new tests `test_one_point_margin_decides_a_moneyline` and `test_edge_result_is_immutable` (`6ad76fa`, confirmed by hand mutation). See `step-18b-evidence/mutation-summary.md`.
- lane-guard: `OK` (output below).
- GATE_PLACEHOLDER

## 6. LANDING
Not done by this lane: god lands it. No push, no PR.
