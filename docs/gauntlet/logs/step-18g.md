# Step 18g log: bench challengers from the brief (lane bench18g)

Lane lead: Phyllis (hive `worker-bench18g`, a temp). Mode: Gauntlet ONE_SHOT, tier T3 (it can say whether the model should change). Branch `lane/bench18g`, base `main` at `f1a072c`.
Owner brief `docs/model/OWNER_BRIEF_2026-10-13.md`, decision D68. Rules: PLAN section 3.1 (D18) and 3.6; AUDIT A11.
Evidence folder: `docs/gauntlet/logs/step-18g-evidence/`.

## In plain words

* **What this step does:** tests four ideas from the owner's brief against the live model, one at a time, on past seasons it has not been fitted on. The ideas: (1) a head-to-head chance from points scored and allowed (the "Pythagorean" formula); (2) a quarterback rating in place of the "quarterback changed" flag; (3) travel distance and time-zone change; (4) the 0-100 matchup score from step 18e.
* **What it ships:** nothing. Each idea gets a verdict that is a number with its interval, and a label: **football-only** (does not read the betting line) or **market-informed** (reads the line or a number made from it).
* **What it is not:** not a model change, not a new data source, not a change to the ship rule. A win is a finding for the owner, not a deployment.

## Checkpoint table

| CP | Name | State |
|---|---|---|
| 1 | Planning | done (this file, section 1) |
| 2 | Specification and first failing tests | done: section 2; red run `step-18g-evidence/red-1.log` (ImportError); commit `9ed7ce7` |
| 3 | Implementation | done: section 3 |
| 4 | Verification (tests, mutation sweep, real data) | done: sections 3 and 4 |
| 5 | Review (new critic on the final head) | done: section 5 |
| 6 | Landing record (lane-guard, done message) | done: section 5 |

## 1. PLANNING

* **Step:** 18g, lane map "Lane bench18g". Needs: 14c (landed, PR #29), 18e (PR #31, for the matchup score only).
* **Files this lane may edit** (`lanes.md`): `analytics/bench_18g.py`, `tests/test_bench_18g.py`, this log, `step-18g-evidence/**`. It reads `backtest.py`, `model_c.py`, `features.py`, `metrics.py`, `ingestion/weather.py`, `nflpi.data`; it edits none of them.
* **One-way doors:** none. Reversibility: two-way. Deployment reach: none.
* **Prior decisions relied on:** D18 (ship rule), D68, D70, D72 (no game from 2026-10-15 on is scored: the bench ends at the 2025 season, so none is), CLAUDE.md "Model validation requirements".
* **The model to beat:** the walk-forward `p_blend` of `analytics/backtest.py`, window 10 seasons, baseline equal to step 14's stored numbers (market 0.6094, blend 0.6107, 3,649 games; confirm 1,084 games). The stats-only model `p_logistic` is the second baseline for football-only ideas.

### Assumptions

| Assumption | State |
|---|---|
| 2022 to 2025 has been scored fifteen times for the win model (nine in AUDIT A11, six in step 14c). This step adds eight looks (one per candidate below), so twenty-three. At 95% two-sided, a pass by luck is about 1 in 40 per look; across 23 looks about 1 in 2 that at least one passes by chance (the looks are correlated, so this is rough) with no real effect | stated in every verdict. A narrow pass is "needs the owner" |
| The bench has the starting quarterback of every past game (schedule file); a live pick has it for the coming week only (AUDIT A8). The quarterback rating is therefore scored on the same footing as the flag it replaces, and the gap is not sized here | stated |
| Points for and against, and quarterback performance, come only from games that kicked off earlier; a team plays once per week so an earlier game is always finished | tested (no-leak clauses) |
| Stadium coordinates are the city-level pairs of `ingestion/weather.py` plus 20 older stadium codes added here (same precision, entered by hand); time zones are IANA names per stadium. A game whose stadium is unknown has no travel feature and keeps the blend's number | stated; coverage printed |
| Matchup score = `nflpi.data.matchup.matchup_score`, a fixed formula, nothing fitted. Used as a **probability** (score / 100), because as a **blend input** it is a straight-line rescale of inputs the blend already has (`elo_diff`, `market_logit`) and cannot add information; the run prints that check | stated; the check is run |
| `stats_player_week_<season>.csv` gives per-player passing and rushing EPA per game (`passing_epa`, `rushing_epa`, `attempts`, `sacks_suffered`, `carries`), 2002 on, keyed by `game_id` and `player_id`; the schedule file gives `home_qb_id` / `away_qb_id` | checked 2026-10-14 |

### Skills and tools

| Skill | Use |
|---|---|
| `/ponytail` | smallest correct diff, plain functions, no new dependency (stdlib `zoneinfo`, `math`) |
| `/tdd` | no project skill; failing tests first, written by the lead (section 2) |
| Builder | Codex once (refused on this account earlier today); else a Sonnet subagent; never Opus; never the critic |
| Critic | one new `ecc:python-reviewer`, no transcript, final committed head, own test file only |
| Design Gauntlet, Parallel Lanes | N/A (no screen); lane claimed, own worktree, state file `lane-bench18g.md` (claims directory is not writable from this sandbox: noted) |

EFFORT: PLANNING and SPECIFICATION high (session setting, not changed).

## 2. SPECIFICATION

Public seam: `nflpi.analytics.bench_18g` (new file). Built on the step 14 bench (`backtest._elo_frames`, `_train_rows`, `predict_season`), `LogitModel`, `metrics.paired_gain`. No existing file is edited.

### Frozen acceptance criteria (functional layer)

| ID | Clause |
|---|---|
| P1 | `PYTH_EXPONENT = 2.37`, `PYTH_HALF_LIVES = (4, 8, 16)`. `pythag_diff(df, half_life)`: for each team the points for (PF) and against (PA) from its earlier games, each earlier game decayed by 0.5^(1/half_life) per game of that team; team log-odds = exponent x ln(PF / PA) (the Pythagorean win share, clipped to 0.01..0.99); value = home log-odds minus away log-odds (the head-to-head "log5" odds). Missing until both teams have a past game. Kickoffs out of order raise `ValueError` |
| P2 | A game's own score and later games never move its value; a game with no score adds nothing; swapping home and away negates the value |
| P3 | `pythag_preds(df, seasons, window)` carries the bench's `p_blend` and `p_logistic` and, for each half-life, `p_pyth_blend_<h>` (blend inputs plus `pyth_diff`, **market-informed**) and `p_pyth_base_<h>` (stats-model inputs plus `pyth_diff`, **football-only**). Fitted on the `window` seasons before the test season only. A game without a value keeps `p_blend` (blend variants) or `p_logistic` (base variants) |
| Q1 | `qb_games(rows)`: from nflverse player-week rows, quarterbacks only; plays = attempts + sacks suffered + carries, epa = passing EPA + rushing EPA; a row with a missing or non-finite number, or no plays, is left out |
| Q2 | `QB_HALF_LIVES = (8, 16, 32)`, `QB_SHRINK = 150`, `QB_SCALE = 50`. `qb_diff(df, qb_games, half_life)`: a quarterback's rating = decayed sum of EPA / (decayed sum of plays + 150), decay per game of that quarterback (his games follow him across teams); a quarterback with no past rates 0; value = 50 x (home starter minus away starter). Any starter id missing gives a missing value. A game's own numbers and later games never move its value; a relief quarterback who threw is rated next time |
| Q3 | `qb_preds(df, seasons, qb_games, window)`: `p_qb_blend_<h>` = [market_logit, elo_diff, home_field, qb_diff] (the two change flags are **replaced**, **market-informed**); `p_qb_base_<h>` = [elo_diff, home_field, qb_diff] (**football-only**). Window and fallback as P3 |
| T1 | `great_circle_km(a, b)` haversine between (lat, lon) pairs, earth radius 6371 km |
| T2 | `STADIUM_COORDS` holds every pair of `ingestion/weather.py` unchanged plus 20 older codes entered by hand; `STADIUM_ZONES` gives an IANA zone for every key. `TRAVEL_VARIANTS = {travel: [travel_km_diff], tz: [tz_diff], both: [both]}` |
| T3 | `travel_features(df, coords, zones)`: a team's home venue = the stadium it uses most at home (not neutral) in that season. The away team travels from its home venue to the game's stadium; the home team travels only at a neutral site, from its own venue. `travel_km_diff` = (away km minus home km) / 1000. A team's time shift = the stadium's UTC offset at kickoff minus the team's home UTC offset at kickoff (hours, east is positive; daylight saving handled by `zoneinfo`); `tz_diff` = away shift minus home shift. An unknown stadium or home venue gives missing, never zero |
| T4 | `travel_preds(df, seasons, window)`: `p_travel_blend_<v>` (**market-informed**) and `p_travel_base_<v>` (**football-only**) for v in travel, tz, both. Window and fallback as P3 |
| M1 | `matchup_preds(df, seasons, window)`: `p_match_football` = `matchup_score(frame, include_market=False) / 100` and `p_match_market` = the same with the market, on the season's test frame (Elo settings chosen on the window). Nothing is fitted for them |
| M2 | `matchup_input_gap(df, seasons, window)`: the largest difference between `p_blend` and the blend refitted with the football matchup log-odds as an extra input; small, because that input is a straight-line rescale of `elo_diff` |
| E1 | `evaluate_vs(preds, candidates, tune, confirm, baseline, cluster)`: like `backtest.evaluate` but against any baseline column; the variant is chosen on the tune seasons only; one confirm gain with the game-level and cluster intervals; every variant's tune gain, confirm gain (descriptive) and `gap`; overlapping seasons raise `ValueError` |
| E2 | `label(column)` gives "football-only" or "market-informed" from the column name; an unknown column raises. `verdict(result)`: "ships" when both intervals pass, "does not ship" when neither does, "needs the owner" when they disagree |
| X1 | Nothing existing changes; every existing test stays green and unedited |

User-facing layer: N/A (no screen). The owner-facing output is this log's verdict table. Operational layer: `step-18g-evidence/run.py <stage>` runs from a clean checkout against live nflverse files, prints JSON with `allow_nan=False`, fails loudly on a download error, and stops if the baseline differs from step 14's stored numbers (market 0.6094, blend 0.6107, 3,649 games, confirm 1,084).

### Protocol, frozen before any result was seen

* Baseline `p_blend`; football-only ideas also against `p_logistic` (the live stats-only model). Tune 2012 to 2021; confirm 2022 to 2025; window 10. Data: nflverse `schedules/games.csv`, `stats_player/stats_player_week_<season>.csv` (2002 on, for ratings), history seasons 2008 to 2011 scored for nothing.
* **Ship rule, unchanged (D18):** the low end of the game-level paired-bootstrap 95% interval of the confirm log-loss gain above 0, and accuracy not lower. The season-week cluster interval is printed beside it; a split is "needs the owner". An idea "beats the blend" only against `p_blend`; "improves the stats model" is the same rule against `p_logistic` and replaces nothing.
* Per candidate: every variant scored on tune; the variant with the largest tune gain is the only one scored on confirm; the other variants' confirm gains are printed with the gap and decide nothing. No variant is added after a result is seen. A losing candidate is logged as lost.
* **Eight candidates, one confirm look each:** `pythag_market`, `pythag_football`, `qb_market`, `qb_football`, `travel_market`, `travel_football`, `matchup_football`, `matchup_market`. Order: pythag, qb, travel, matchup. Total looks at 2022 to 2025 after this step: 15 + 8 = 23 (AUDIT A11 and step 14c).
* **Power limit, said in every verdict:** the confirm set is 1,084 games; the half-width of each confirm interval (printed per run) is the smallest gain that test could see.
* Seasons before 2012 are history only. No 2026 game is read for any number (D72).

### First failing tests

`backend/tests/test_bench_18g.py`, written by the lead before any production code. The matchup tests skip until `nflpi.data` is in the tree (they run after the rebase on PR #31).

## 3. IMPLEMENTATION

Provider: `codex exec` was tried once and refused (`The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account`, `step-18g-evidence/codex-try.log`). One bounded work order went to a Sonnet subagent (never Opus, never the critic) with the spec, the tests and the 14c pattern; it wrote `bench_18g.py` (492 lines) and reported 35 of 37 tests green. The two failures were **errors in my own tests**, not in the code: (1) a swap test whose second game had a team with no past (the value is correctly missing); (2) a travel test with the wrong sign for the away side. I corrected the tests. After the rebase on PR #31 (`nflpi.data` present) all matchup tests ran: 37 passed, ruff clean. D74 (no AI in any feature or verdict) holds: every number is arithmetic on past results; no model call exists in the file.

Mutation sweep (`mutate.py`, gate lock held): the first run caught 49 of 54. Of the five survivors, one was a no-op edit I wrote (dropped), one is equivalent (blend variants fit on `train` with or without dropping rows that lack a line: `LogitModel.fit` drops rows with a missing input itself; dropped from the list), and three exposed real test gaps, each closed by a stronger test: the training window must be exactly the seasons before the test season; a quarterback line with a non-finite number is left out; the matchup gap counts a refit that is lower as well as higher. Second run: **52 of 52 caught** (`mutate.log`). Tests: `tests/test_bench_18g.py` 38 passed.

## 4. What the real data says

Run: `bash step-18g-evidence/locked-stage.sh <stage>` (gate lock), then `summ.py`. Live nflverse files, 2026-10-14, one stage once, in the order pythag, qb, travel, matchup. Walk-forward, window 10, 3,649 games with a closing line (2012 to 2025), tune 2012 to 2021 (2,565 games), confirm 2022 to 2025 (1,084 games, 72 season-weeks). **Baseline check passed on every run** (market 66.57% and log loss 0.6094; blend 66.46% and 0.6107; confirm blend 67.53% and 0.6095): the runner stops otherwise. No 2026 game is read (D72). One travel run stopped on a call bug in the runner (a missing argument) before printing any score; it was fixed and rerun; no look was taken from the failed run. Raw files: `run-<stage>.json`, `verdicts.txt`.

Gain = how much lower the idea's log loss is than the baseline's (positive is better). Interval = paired bootstrap 95%, game by game (the rule); the week-clustered interval is beside it. Football-only ideas were chosen against the stats-only model `p_logistic` and also scored against the live blend. **Power limit: the confirm interval half-widths printed in each run (about 0.0005 for the blend variants, 0.003 for football-only Pythagorean, 0.009 for football-only quarterback) are the smallest gain each test could separate from zero; "does not ship" means no gain this test can see.**

| Idea | Label | Chosen on tune | Baseline | Confirm gain (95% interval) | Accuracy change | Verdict |
|---|---|---|---|---|---|---|
| Pythagorean, in the blend | market-informed | half-life 8 games | blend | -0.00056 (-0.00107 to -0.00001) | -0.09 pts | does not ship |
| Pythagorean, in the stats model | football-only | half-life 8 | stats model | -0.00023 (-0.00343 to +0.00303) | +0.46 pts | does not ship (no gain this test can see); vs the blend -0.02382 (-0.03399 to -0.01259) |
| Quarterback rating replacing the change flags, in the blend | market-informed | half-life 32 games | blend | -0.00187 (-0.00533 to +0.00183) | +0.37 pts | does not ship |
| Quarterback rating, in the stats model | football-only | half-life 32 | stats model | -0.00029 (-0.00947 to +0.00945) | +1.11 pts | does not ship; vs the blend -0.02389 (-0.03432 to -0.01346) |
| Travel and time zone, in the blend | market-informed | time-zone shift only | blend | -0.00067 (-0.00133 to -0.00003) | -0.09 pts | does not ship |
| Travel and time zone, in the stats model | football-only | time-zone shift only | stats model | -0.00109 (-0.00226 to +0.00006) | -0.28 pts | does not ship; vs the blend -0.02468 |
| Matchup score (football) | football-only | the one formula | stats model | -0.00829 (-0.01687 to +0.00008) | +0.83 pts | does not ship; vs the blend -0.03188 |
| Matchup score (with the line) | market-informed | the one formula | blend | -0.00863 (-0.01503 to -0.00221) | -0.65 pts | does not ship |

Reading it plainly:

* **All eight lose. Nothing ships; no change to the model is proposed.** None of the eight confirm intervals has a low end above zero. Against the blend, only the matchup score with the line is below zero on both intervals; Pythagorean and travel in the blend are below zero by a hair on the game-level interval (upper ends -0.00001 and -0.00003) and cross zero on the week-clustered one, so they are "no gain", not proven harm, and across 23 looks even that is weak. The football-only ideas are far behind the blend (0.024 to 0.032 log loss, intervals wholly below zero), which is what dropping the line costs.
* **Tune gains did not survive.** Both football-only quarterback and Pythagorean variants had positive tune gains (+0.0057 quarterback, +0.0014 Pythagorean) that turned to about zero on confirm (gap +0.006 and +0.002): the pattern of a gain that was fitted noise. The half-life-8 Pythagorean variant that looked best on tune is the one that failed; the half-life-4 one scored +0.00085 on confirm, but confirm chooses nothing (descriptive).
* **Quarterback rating:** the gap between the quarterback rating and the old flag is not distinguishable from zero in either direction (interval half-widths about 0.004 in the blend and 0.009 without the line). 179 games of the 2002-onward frame (all game types and seasons, not only the 3,649 scored) have no starter id; where one is missing the quarterback value is missing and the baseline's number is kept. The bench has the starter of every past game while a live pick has it for the coming week only (AUDIT A8), so even a gain here would have been an upper bound.
* **Travel:** all 3,649 scored games had a distance and a time-zone shift (no unknown stadium). The distance variant is slightly positive on confirm (+0.00013 in the blend) but was not chosen on tune, and is far inside the noise.
* **Matchup score:** a fixed formula of the Elo gap (and the line) cannot beat the fitted model it is a rescaled copy of; as a blend input it changes predictions by at most 0.0022 in probability (`input_gap`), so a test of it as an input could not have told anything new.
* **Looks used:** eight new, so 23 at 2022 to 2025 for the win model (AUDIT A11's nine, step 14c's six, these eight). With no real effect, roughly even odds that some look passes by chance across 23 looks at 95% (the looks are correlated, so this is rough); none did. A11 should now read twenty-three looks; the register is updated here, not in `AUDIT.md` (not this lane's file).
* **What this does not show:** it does not show that these ideas are worthless in general, only that none adds to a model that already reads the closing line, on the games this test can see. Football-only versions were never going to beat the market-informed blend (0.024 log loss behind); the stats-model comparison asks only whether the idea helps a model with no line, and it does not.

## 5. Review and landing

Critic: one new `ecc:python-reviewer` with no transcript, on head `bb47c7b`, own test file only (38 passed). **Verdict PASS**: no CRITICAL or HIGH finding. It found no leakage, hand-worked three examples (Pythagorean with decay, quarterback shrink, daylight-saving shift) against the code, spot-checked eight clauses for a failing test, and matched every table number to the run files. Three MEDIUM findings were overstatements in this log (the single 0.001 power figure, "measurably worse" for two game-level-only intervals, the 179-game count's scope); all three are corrected above in a documentation-only commit. Kept as known LOW points, no code change after the critic: a missing `neutral_site` flag would be read as neutral (`bool(nan)`; the schedule file always sets it); `travel_preds` computes the features twice; the home venue uses the whole season's schedule, which is known before the season. X1 (no existing file changed) is checked by lane-guard.

Lane-guard (`check ... bench18g origin/main`): OK. Against the local `main` ref it lists picks files, because the local ref predates PR #32; they are not this lane's.
