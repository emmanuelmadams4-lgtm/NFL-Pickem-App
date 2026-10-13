# Step 8b log: the star-out challenger (lane starb)

Lane coordinator: Kevin (hive `worker-starb`). Mode: Gauntlet ONE_SHOT, tier T2. Branch `lane/starb`, base `main` at `a71e112`.
Evidence folder: `docs/gauntlet/logs/step-8b-evidence/`. Gate: `bash docs/gauntlet/logs/step-8b-evidence/gate.sh <label>`.

## In plain words

* **What this step builds:** nothing for the screen. It asks one question on the test bench of steps 14 and 14b: does knowing which star players are out before kickoff make the win chance better? It replays 2012 to 2025 and says "ships" or "does not ship".
* **What it replaces:** nothing, unless it wins. A winner is committed here as a tested change with its proof; using it in the live app is a seam for the integrator (this lane may not touch the engine, the worker, the API or the web app).
* **What it is not:** not the "who is out" line on the game card (step 8a2), not a new data source for the app, not a change to the ship rule.

Words used below. **Log loss:** a score for probabilities, lower is better. **Gain:** how much lower an idea's log loss is than today's model (positive is better). **Blend:** today's model, the stats model plus the closing betting line. **Star:** one of last season's most productive players (rule in section 2). **Injury report:** the club's official weekly list with a game status (Out, Doubtful, Questionable). **Reserve list:** injured reserve and similar lists; a player on one cannot play that week. **Tune seasons:** 2012 to 2021, where a variant may be chosen. **Confirm seasons:** 2022 to 2025, looked at once per candidate, never used to choose.

## 1. PLANNING

* **Step:** `docs/gauntlet/step8-scrape-plan.md` Part 3 row 8b (gate: paired-bootstrap 95% excludes 0), tier T2. Depends on step 14 (PR #9) and step 14b (PR #13), both landed. `NEEDS: (none)` in `lanes.md`.
* **Scope (god's dispatch, 2026-10-13):** per team and game, how many of its stars are out, and one weighted form; the quarterback counted apart; tested walk-forward 2012 to 2025 under step 14's ship rule; at most 6 variants, frozen before any run; every variant logged.
* **Out:** `predictions/engine.py`, `jobs.py`, the API, the web app, the shared package, `analytics/stars.py` (read only; lane web is editing it), any migration, any change to the ship rule.
* **Done when:** each candidate has a walk-forward verdict on real nflverse data with every variant logged; each frozen clause has a test that fails when it is broken; the gate is green twice on the final commit; a new critic passes; lane guard is clean.
* **Files this lane may edit:** `analytics/star_backtest.py` (new), `tests/test_star_backtest.py` (new), `predictions/{model,features,elo,market}.py`, `analytics/{backtest,metrics}.py`, `tests/test_model.py`, this log and its evidence folder. Only the two new files and the log are touched.
* **One-way doors:** none. No schema, no API contract, no live model change. Reversibility: two-way.
* **Deployment reach:** none. Nothing here runs in the live app.
* **Prior decisions relied on:** CLAUDE.md "Model validation requirements"; owner decision 2026-10-12 (each idea tested first, ships only if it wins); D24 (a star being out never moves a pick until it wins walk-forward: this step is that test); step 14 and 14b logs (the bench, the rule, what already lost); step 8a log (how the app picks stars today).

### Product Mode pre-flight

1. **Problem:** the owner sees "star X is out" and cannot tell whether that should move a pick, or whether the betting line already carries it.
2. **Why now:** the bench landed today (steps 14, 14b), and step 8a2 is about to put stars on the screen.
3. **Scope:** two candidates, six variants, on public nflverse files. Cut: practice notes, Questionable, game-day inactive lists, snap counts, depth charts, news feeds, live wiring.
4. **Success metric:** confirm-season log-loss gain over the blend with a paired-bootstrap 95% interval; accuracy as the guard.
5. **Reversibility:** two-way.

### Checked at the source (nflverse release files, 2026-10-13, before the spec was frozen; no game result was read)

| Question | Found |
|---|---|
| How far back does the official injury report go? | `injuries/injuries_<season>.csv` exists for 2009 to 2025; 2008 answers 404. One row per player and week, with `report_status` (Out, Doubtful, Questionable, Probable until 2015) and the league player id on every row |
| Is the report dated? | `date_modified` is filled from 2010 to 2024 (blank on all but 17 rows of 2009; the column is gone in 2025). Of 16,716 dated regular-season Out or Doubtful rows, 6 are dated at or after that team's kickoff. Those rows are dropped by rule F3 |
| Is the weekly roster status a pregame fact? | **Not before 2016.** In `weekly_rosters/roster_weekly_<season>.csv` for 2008 to 2015, about half of the player-weeks marked `RES` (reserve) have a stat line in that same week (2015: 1,391 of 2,512): the file carries a later status back onto earlier weeks. That is future data. From 2016 it is a pregame state: 18 of 4,115 in 2016, then 2, 0, 5, 0, 0, 0, 0, 0, 0 for 2017 to 2025. So roster status is used from 2016 only (rule F7), and the runner re-checks this share on every run |
| Player stats | `stats_player/stats_player_week_<season>.csv` exists back to 2001 at least, offence and defence in one file, with `season_type` |
| Snap counts | Start in 2013 (step 8a log). The app's own star rule uses snaps, so it cannot be replayed from 2012 with enough earlier seasons to learn from. The bench rule below uses production only and says so |

### Assumptions

| Assumption | State |
|---|---|
| The model to beat is the walk-forward `p_blend` of `analytics/backtest.py`, window 10 seasons; baseline must equal step 14's stored numbers (market 0.6094, blend 0.6107 on 3,649 games; confirm 1,084 games) | validated by the runner on every run (it stops if they differ) |
| A game status on the official report is issued before the game (league rule). Where a row carries a date at or after kickoff it is dropped; an undated row (2009, 2025) is kept | assumed for undated rows; stated in the verdict |
| A star list from last season's production, league wide, is a fair stand-in for "star": it exists in week 1 and does not lose a star who got hurt early. Rookies, players who missed last season and offensive linemen can never be stars under it | assumed; frozen before any result |
| A reserve-list status in the 2016+ roster files is public before kickoff (roster moves are published by the league the day before a game at the latest) | validated by the same-week check above; game-day inactive lists (`INA`) are left out on purpose, they are too close to "who played" |
| A fit drops training rows that lack the input, so the report candidate learns from 2009 on (3 seasons for 2012, 10 from 2019) and the reserve candidate from 2016 on (first fitted season 2019) | stated; the confirm seasons have a full window for the report candidate and 6 to 9 seasons for the reserve candidate |
| Two confirm looks at 95% each: about a one in ten chance that at least one passes by luck if neither is real | stated in the verdict |

Interpretations weighed (two-way, decided by the coordinator inside the dispatch's own choice "prior season, or season to date; freeze which"): **prior season** over season to date, because season to date has no list in week 1 and drops a star once he has missed a few games, which is exactly the case under test. Rejected: the app's own five-per-club rule (needs snap counts, 2013+; and the bench must not call `stars.py`). If a candidate ships, the seam note says the live path needs this bench rule, not the screen's rule.

### Instrumentation

North star: confirm-season log-loss gain against the blend. Baseline: the blend's numbers from the same run. Read by `star_out.py`, which prints one JSON. Guardrail: accuracy must not drop. Check date: this step.

### Skills and tools

| Skill | Use |
|---|---|
| `/jevgrep` | `jg 0.8.0`. Question: "Where are star players or injury report statuses used as inputs to a win probability model?" Ranked `predictions/engine.py`, `features.py`, `analytics/backtest.py`, `stars.py`; the source shown confirms the model reads only the quarterback-change flags: no star or injury input exists today. `JEVGREP: ready` |
| `/graft` | N/A: the seam files were named in the dispatch and read whole |
| `/tdd` | No project `tdd` skill. Failing tests first, written by the coordinator (section 2) |
| `/ponytail` | In the work order: smallest correct diff, no new dependency, plain functions, one new module |
| `harness-engineering` | N/A: no runner service, evaluator or approval boundary is created |
| Design Gauntlet | N/A: no user interface |
| Parallel Lanes | Lane claimed (`claims/starb`), own worktree, own state file, coord task #18 |

EFFORT: PLANNING and SPECIFICATION high (session setting, not changed).

## 2. SPECIFICATION

Public seam (one new module, `nflpi.analytics.star_backtest`; nothing existing changes):

* `league_stars(stats) -> {season: {player_id: (group, weight)}}`
* `star_out_features(df, stats, reports, roster=None) -> DataFrame` (one row per game of `df`, same index)
* `star_preds(df, seasons, inputs, window=10) -> DataFrame` (the bench's scored games plus one column per variant)
* constants `STAR_LIMITS`, `REPORT_OUT`, `ROSTER_OUT`, `ROSTER_FIRST_SEASON`, `MIN_FIT_SEASONS`, `STAR_VARIANTS`

Row shapes (plain dicts; the runner builds them from the nflverse files):
`stats`: `season, week, season_type, player_id, position` plus the 17 numbers of `nflverse.STAR_STATS`. `reports`: `season, week, team, player_id, status, modified` (a datetime with a time zone, or `None`). `roster`: `season, week, team, player_id, status`. `df`: needs `season, week, kickoff_utc, home_team, away_team` and nothing else.

### Frozen acceptance criteria (functional layer)

| ID | Clause |
|---|---|
| L1 | `league_stars` makes one list per season in `stats`, from that season's rows with `season_type == "REG"` only, summed per player. |
| L2 | Groups. A player is a quarterback when his row with the highest week says `QB`; his score is pass attempts. Any other player has an offence score = (rushing + receiving yards) / 10 + 6 x (rushing + receiving touchdowns) + 0.5 x receptions and a defence score = solo tackles + tackles with assist + 0.5 x assists + 6 x sacks + 2 x QB hits + 2 x tackles for loss + 6 x interceptions + 3 x passes defended + 4 x forced fumbles + 6 x defensive touchdowns + 2 x safeties, and belongs to the side where his score is higher (offence on a tie). These are the point values of step 8a (S2, S3) without the snap term, copied here on purpose; the bench does not call `stars.py`. |
| L3 | Stars are the top 32 quarterbacks, top 64 on offence and top 64 on defence by score (`STAR_LIMITS`), score above 0 only, ties to the lower player id. A star's weight is his score divided by the mean score of that season's stars in his group. |
| F1 | A game of season S uses the star list of season S - 1 and no other season. No list for S - 1: every column is missing for that game. |
| F2 | A club's stars out for a game are the stars with a report row of the same season, week and club whose status is Out or Doubtful (`REPORT_OUT`, any letter case). Not Questionable, Probable or blank; not another week, season or club; a player counts once. |
| F3 | A report row whose `modified` time is at or after the game's kickoff is not used. A row with no time is used. |
| F4 | Quarterbacks are counted apart: `qb_out_diff` counts quarterback stars only; `star_out_diff` and `star_out_w_diff` never include a quarterback. |
| F5 | Every column is home minus away. `star_out_diff` is the number of stars out; `star_out_w_diff` is the sum of their weights. |
| F6 | Unknown stays missing. A season and week with no report row at all (any club, any status) gives missing values; a week that has rows gives 0 for a club with no star out. |
| F7 | With `roster`, two more columns, `star_res_diff` and `star_res_w_diff`: the same count and weighted sum over the non-quarterback stars who are out on the report or have a roster row of the same season, week and club with status `RES`, `PUP` or `SUS` (`ROSTER_OUT`); a player on both counts once. `INA`, `ACT` and every other status are not used. Missing when the report columns are missing, when the season is before `ROSTER_FIRST_SEASON` (2016), or when that season and week has no roster row at all. Without `roster` the two columns are absent. |
| F8 | No column reads a game result, a starter, or anything from the game itself: the output is the same from a frame holding only `season, week, kickoff_utc, home_team, away_team`, and does not move when scores, same-season stats, or later weeks' reports and rosters change. |
| P1 | `star_preds` scores the same games as the step 14 bench (regular season, finished, with a price) for the seasons asked, and carries the same `p_blend`. |
| P2 | Six variants (`STAR_VARIANTS`), each the blend's inputs plus: `p_star_count` (`star_out_diff`), `p_star_weighted` (`star_out_w_diff`), `p_star_count_qb` (`star_out_diff`, `qb_out_diff`), `p_star_weighted_qb` (`star_out_w_diff`, `qb_out_diff`), `p_star_res_count` (`star_res_diff`), `p_star_res_weighted` (`star_res_w_diff`). |
| P3 | Every fit uses only rows of the `window` seasons before the test season that have a price and every input of the variant. |
| P4 | When those rows cover fewer than 3 seasons (`MIN_FIT_SEASONS`), nothing is fitted and the season keeps the blend's number. A test game missing an input keeps the blend's number. A number is never invented. |
| P5 | No variant's number for a game moves when the result of a game in that week or later changes. |
| X1 | Nothing existing changes: no edit to any existing module or test. |

User-facing layer: N/A (no screen). The owner-facing output is this log's verdict table.
Operational layer: `star_out.py` runs from a clean checkout against live nflverse files, prints JSON with `allow_nan=False`, fails loudly on a download error, stops if the baseline differs from step 14's stored numbers, and stops if the reserve check (share of reserve player-weeks with a stat line that same week) is 1% or more in any season it uses.

### Protocol, frozen before any result was seen

* Baseline `p_blend`; tune 2012 to 2021; confirm 2022 to 2025; window 10. Data: live nflverse `schedules/games.csv`, `stats_player/stats_player_week_<S>.csv` for 2008 to 2024, `injuries/injuries_<S>.csv` for 2009 to 2025, `weekly_rosters/roster_weekly_<S>.csv` for 2016 to 2025, all through the app's existing download function. Club codes through the app's `franchise()` map.
* **Ship rule, unchanged from step 14:** low end of the game-level paired-bootstrap 95% interval of the confirm log-loss gain above 0, and accuracy not lower. The season-week cluster interval is printed beside it and never decides.
* **Power limit, to be said in the verdict:** the confirm set is 1,084 games; it cannot show a gain under about 0.001 log loss.
* **Candidate A, `star_out_report`** (official report only): variants `p_star_count`, `p_star_weighted`, `p_star_count_qb`, `p_star_weighted_qb`.
* **Candidate B, `star_out_reserve`** (report plus reserve lists, 2016 on): variants `p_star_res_count`, `p_star_res_weighted`. For 2012 to 2018 it equals the blend by rule P4 (gain exactly 0), so it is in effect chosen on 2019 to 2021.
* For each candidate every variant is scored on the tune seasons and printed; the variant with the largest tune gain is scored once on the confirm seasons. Six variants, two confirm looks, nothing added after a result is seen. No follow-up idea is gated on these results. A losing candidate is logged as lost.
* Two confirm looks: if neither were real, the chance that at least one passes a 95% rule by luck is about one in ten. Said with the verdict.

### First failing tests

Eleven tests in `backend/tests/test_star_backtest.py`, written by the coordinator before any production code. Red for the intended reason, the module does not exist (`red-1.log`): `ImportError: cannot import name 'star_backtest' from 'nflpi.analytics'`.

### Baseline

`tests/test_model.py` on `a71e112`: 34 passed (`baseline-test_model.log`). The full gate on `main` at `a71e112` is the integrator's CI run (PR #13). The full gate runs here twice on the final commit.
