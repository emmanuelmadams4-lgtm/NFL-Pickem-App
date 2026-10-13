# Step 18c: game-score simulator (lane sim)

Owner brief: `docs/model/OWNER_BRIEF_2026-10-13.md` section 7 (also 6, 10), read as D68 says. Tier T2. Base `c55827f` (main later moved to `589aa3b`, docs only). Coordinator: Stanley (worker-sim). Builders: subagents (see CLIMBS).

## 1. PLANNING

* **Step goal / done-when.** `simulate_game(team_a_features, team_b_features, n_simulations=10_000, *, ...)` in `backend/nflpi/sim/`, with every parameter learned on past seasons only, and a walk-forward bench (`analytics/sim_backtest.py`) that calls it for every game, picks the default distribution on 2012 to 2021, then does ONE confirm run on 2022 to 2025. `docs/model/SIMULATOR.md` written. Gate green twice, new critic PASS, lane guard clean.
* **Tier T2.** Pre-flight: *Problem* the pick sheet has win probabilities but no score distribution, so spread, total and tie questions (brief 7) cannot be answered. *Why now* owner decision D68 (step 18). *Scope* a game-score sampler plus bench; NOT a play-by-play engine, NOT wired into the live pipeline (SEAM). *Success metric* honest, out-of-sample numbers for score error, interval coverage and cover/over calibration; no claim of an edge unless a paired interval excludes zero. *Reversibility* two-way (new package, no migration, no route, no dependency).
* **Prior decisions relied on.** D18 ship rule (tune 2012-2021, confirm 2022-2025), D68, `CLAUDE.md` "Model validation requirements" (walk-forward by season only; never invent data).
* **Owner direction check (lesson 1).** Builds: a function that, given two teams' expected points, returns thousands of possible final scores and the odds read off them (win, tie, cover, over). Replaces: nothing. Is not: a live feature yet, a play-by-play model, or a source of picks.
* **Assumptions.** validated: expected points exist (`predictions/scores.py`: `ScoreModel`, `implied_score`); the cached nflverse `games.csv` has final scores, `overtime`, closing `spread_line` and `total_line` for 1999-2025; numpy 2.5.4 and pandas 3.0.6 are installed; scipy is not a declared dependency (not used). assumed: regulation scores can be recovered from final scores for overtime games as `min(home, away)` (only the OT winner scores in sudden death; wrong when both teams score in 2012+ modified overtime, rare; labelled). unknown: none that changes the design.
* **Discovery.** `jg` not used (no behavioural unknowns: the two modules to reuse were read directly); `/graft` N/A (no graft index for this worktree; direct reads of `scores.py`, `score_backtest.py`, `backtest.py`, `metrics.py`).
* **Skills.** `/tdd` (tests first, one clause = one test), `/ponytail` (numpy only, no abstraction without need; builder briefs carry it), `harness-engineering` N/A (no autonomous runner), Design Gauntlet N/A, security review N/A (no auth, input, DB, file, network or crypto code added: the bench reads a local CSV through the existing `nflverse` parser).
* **Effort.** EFFORT: PLANNING/SPECIFICATION high; builds low (subagents); VERIFICATION high.

## 2. SPECIFICATION (frozen before any production code)

### 2.1 What "features" are

`TeamFeatures(expected_points: float)`: one team's expected final points in THIS game, finite, 0 < x <= 100. Nothing else per team. The game-level knowledge is in `SimParams` (learned spread-of-outcomes parameters, below) passed as `params=`. `team_a` is the home team in the bench; `neutral_site` only labels the result (the venue effect is already inside the expected points).

Expected points come from existing code, in two variants always reported separately (brief 6):
* **football_only** = `ScoreModel` with `STATS_FEATURES`, fit on the 10 seasons before the game's season. No market number.
* **market_informed** = `implied_score(spread_line, total_line)`, i.e. the closing line's own score. **A market-informed simulator priced at the market's own line sits near 50 percent on cover and over by construction; it is not an independent discovery.** It is reported as the reference, not as an edge.

### 2.2 Conventions

M = a_score - b_score. Quoted spread `h` for team A: A covers when M + h > 0; push when M + h == 0. (nflverse `spread_line` is positive when home is favoured, so the bench uses `h = -spread_line`.) Total: over when a+b > total, under when <, push when equal. Scores are `int64`, >= 0. A "win" is a strictly higher final score; ties are reported separately; the home win probability for comparing with a classifier is `p_a_win + p_tie / 2` (labelled).

### 2.3 Distributions (regulation scores; overtime is a separate step, 2.4)

| name | what | learned from past seasons |
|---|---|---|
| `poisson` | independent Poisson(mu_a), Poisson(mu_b). Baseline. | nothing |
| `paired_residual` | team score = stochastic_round(mu) + a past (a-residual, b-residual) pair, where residual = regulation score - round(expected points); clipped at 0. Keeps dependence, tails and the lumpiness of football scores. | the residual pairs |
| `bivariate_normal` | discretised: round(N(mu, Sigma)), sd_i = sqrt(phi_i * mu_i), correlation rho; clipped at 0. | phi_a, phi_b, rho |
| `shared_gamma_poisson` | overdispersed counts: Poisson(mu_i * g_i), g_i = (S + E_i)/(k_s + k_e) with gamma S, E_i: variance mu + v mu^2 per team, shared factor v_s makes the two scores correlated. | v, v_s (method of moments) |

### 2.4 Overtime and ties

Distributions sample the REGULATION score. If regulation is tied: regular season: with learned probability `ot_tie_frac` the game stays tied; otherwise a side picked 50/50 (labelled assumption) gains a learned overtime increment (drawn from past non-tied overtime games' winning margins). Playoffs (`playoff=True`): `ot_tie_frac` is 0, so no ties, ever. The overtime rule era follows the season: `ot_era(season)` is `sudden_death_15` before 2012, `modified_15` for 2012-2016, `modified_10` from 2017. `learn_params` uses only same-era overtime games when it has at least 30, else all training overtime games and sets `ot_era_fallback=True`. Regulation score of a past overtime game = `min(home, away)` for both teams (approximation, labelled).

### 2.5 Learning rule (no future data)

`learn_params` is a pure function of the rows it is given. In the bench, for test season S the rows are seasons `max(2004, S-10) .. S-1` only, with expected points that were themselves produced walk-forward (each training season's expected points come from a model fit on its own prior 10 seasons). Needs >= 200 usable games, else ValueError.

### 2.6 Bench (frozen before the tune run)

* Eligible games (identical for every variant): regular season, final, both scores, a closing spread and total, finite expected points in both sources. Seasons 2012-2025.
* **Default-distribution rule.** On tuning seasons 2012-2021 only: for every game and both sources, `CRPS(margin) + CRPS(total)` of the simulated samples against the actual margin and total (sample-based CRPS, lower is better); average over games and over both sources; the distribution with the lowest pooled mean is `DEFAULT_DISTRIBUTION`. Ties go to the earlier row of the table in 2.3. No confirm season is read to make this choice. Per-source winners and bootstrap intervals are reported but do not change the rule.
* **ONE confirm run** on 2022-2025, all 8 variants (4 distributions x 2 sources), refusing to run twice (writes its result file with exclusive create). Reported per variant: margin and total MAE and RMSE of the simulated mean; interval coverage at 50, 80, 95 percent for margin and total; cover and over calibration against the closing spread and total (reliability table with 10 bins, Brier, Brier of a flat 0.5, pushes excluded); simulated vs real tie rate; simulated vs real rate of |margin| = 3 and = 7; gap between `p_a_win + p_tie/2` and the live blend's win probability (mean absolute gap, max, count above 0.10, with the largest gaps listed); log loss and accuracy of the simulator's win probability next to the blend's and the market's on the same games, with a paired-bootstrap 95 percent interval of the log-loss gain (D18 reads it: a gain claim needs an interval that excludes zero and accuracy not lower).
* Seed per game = fixed base seed combined with the game id (same random numbers for every variant), 10,000 simulations.
* The bench calls `simulate_game` for every game and variant; there is no second code path.

### 2.7 Frozen clauses, one test each

`tests/test_sim.py`: C1 output validity (int, >=0, sizes; win/tie, cover/push, over/under/push each sum to 1). C2 spread convention (covers when M+h>0; zero spread with tie is a push; half-point spread never pushes). C3 total convention. C4 same seed same output, different seed different. C5 speed: median of 20 runs of 10,000 simulations < 100 ms for every distribution. C6 distribution moments: Poisson mean and variance equal mu; paired_residual mean equals mu; gamma-Poisson variance equals mu + v mu^2 and score correlation matches v_s; bivariate_normal correlation matches rho; all within sampling tolerance. C7 `learn_params` returns the moment values from known synthetic data (recovers a planted dispersion and correlation) and is invariant to row order. C8 playoffs never tie; zero `ot_tie_frac` never ties; regulation ties resolve to increments from the pool; non-tied regulation games are untouched. C9 `ot_era` boundaries and the same-era / fallback choice in `learn_params`. C10 predictive intervals nested, contain the median, hold at least their level of the samples. C11 sampling error equals sqrt(p(1-p)/n) and carries the "sampling error only" label; the margin mean error is sd/sqrt(n). C12 input validation (bad n, bad expected points, unknown distribution, non-poisson without params, non-finite spread or total). C13 `neutral_site` does not change the samples and is recorded. C14 `TeamFeatures` is immutable. C15 regulation recovery of overtime games (`min`).

`tests/test_sim_backtest.py`: B1 sample CRPS equals a hand-computed value; default rule picks the lowest pooled mean and breaks ties to the earlier row. B2 the tune run gives the same result when every row of season >= 2022 is deleted or scrambled. B3 walk-forward window: parameters for season S are identical when results of seasons >= S are scrambled, and use only `max(2004, S-10) .. S-1`. B4 eligible games identical for every variant. B5 the bench calls `simulate_game` once per game and variant (spy). B6 `h = -spread_line`. B7 metric helpers (coverage, reliability table, Brier vs 0.5, key-number and tie rates, win-probability gap) against hand-built examples. B8 the confirm run refuses to run twice (existing result file). B9 a small synthetic end-to-end run produces the report keys and finite numbers.

Gate (each run, twice on the final commit): `cd backend && DATABASE_URL=<scratch 15446> uv run pytest -q && uvx ruff check nflpi tests migrations && uv run alembic check` (fresh scratch database, `upgrade head` first) and `npm run gen:api` shows no drift. No migration, route or dependency.

## 3. Build record
(filled in as the build proceeds)

### Build record

* Codex probe (once, default model): `ERROR: {"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account."}}`. CLIMBS: none possible; IMPLEMENTATION_PROVIDER: CLAUDE (limit hit: Codex refuses on this account), BUILD_RUNG: sonnet subagent builders (try 1 of 2). Builders never write tests and never certify.
* Red: `tests/test_sim.py` fails at collection, `ModuleNotFoundError: No module named 'nflpi.sim.game'` (module absent = intended reason). Commit `e2efcf9`.
* `tests/test_sim_backtest.py` written (B1 to B9) and committed before the bench is built.
* IMPLEMENTATION WO1 (sonnet builder, try 1 of 2): `backend/nflpi/sim/` (5 files, 288 lines). First run 50 of 51 tests; the one failure was a bug in my own test (`assert_allclose` on a string field), fixed by me, 51 passed, ruff clean. Commit `e9786c1`.
* WO2 (sonnet builder, try 1 of 2): `analytics/sim_backtest.py` (331 lines). 65 passed (both files, 14.7 s, run by me), ruff clean. Commit `99422cb`. Builder notes: `build_table` skips a season whose training fit fails; `confirm` deletes its result file only if the run itself raises before finishing (so one failed run does not block a rerun; a completed run can never be overwritten).
* Database note: the lane test DB password is `test` (container env), not the one in the work order; still the lane DB on 15446, never the default URL.
