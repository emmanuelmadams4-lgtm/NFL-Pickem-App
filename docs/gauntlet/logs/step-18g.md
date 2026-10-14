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
| 2 | Specification and first failing tests | |
| 3 | Implementation | |
| 4 | Verification (tests, mutation sweep, real data) | |
| 5 | Review (new critic on the final head) | |
| 6 | Landing record (lane-guard, done message) | |

## 1. PLANNING

* **Step:** 18g, lane map "Lane bench18g". Needs: 14c (landed, PR #29), 18e (PR #31, for the matchup score only).
* **Files this lane may edit** (`lanes.md`): `analytics/bench_18g.py`, `tests/test_bench_18g.py`, this log, `step-18g-evidence/**`. It reads `backtest.py`, `model_c.py`, `features.py`, `metrics.py`, `ingestion/weather.py`, `nflpi.data`; it edits none of them.
* **One-way doors:** none. Reversibility: two-way. Deployment reach: none.
* **Prior decisions relied on:** D18 (ship rule), D68, D70, D72 (no game from 2026-10-15 on is scored: the bench ends at the 2025 season, so none is), CLAUDE.md "Model validation requirements".
* **The model to beat:** the walk-forward `p_blend` of `analytics/backtest.py`, window 10 seasons, baseline equal to step 14's stored numbers (market 0.6094, blend 0.6107, 3,649 games; confirm 1,084 games). The stats-only model `p_logistic` is the second baseline for football-only ideas.

### Assumptions

| Assumption | State |
|---|---|
| 2022 to 2025 has been scored fifteen times for the win model (nine in AUDIT A11, six in step 14c). This step adds eight looks (one per candidate below), so twenty-three. At 95% two-sided, a pass by luck is about 1 in 40 per look; across 23 looks about 1 in 2 that at least one passes by chance with no real effect | stated in every verdict. A narrow pass is "needs the owner" |
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
* **Power limit, said in every verdict:** the confirm set is 1,084 games; it cannot show a gain under about 0.001 log loss.
* Seasons before 2012 are history only. No 2026 game is read for any number (D72).

### First failing tests

`backend/tests/test_bench_18g.py`, written by the lead before any production code. The matchup tests skip until `nflpi.data` is in the tree (they run after the rebase on PR #31).
