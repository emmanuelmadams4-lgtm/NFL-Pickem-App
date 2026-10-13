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


### Clarification after review (before the final run; no number moved)

L1 as first written did not say what a season with playoff rows only gets. Ruling: **a season with no regular-season row has no list** (F1 then makes its games missing, not zero). Real nflverse seasons all have regular-season rows, so this changes no result. Pinned by one more assertion in the existing "unknown stays missing" test (`red-2.log`: `assert 2021 not in {2021: {}}`), fixed in work order 2.

## 3. IMPLEMENTATION

Provider: Codex, one bounded work order at a time, prompt on stdin. The coordinator wrote the spec, the tests and the runner script (`star_out.py`), read every diff and reran the proof itself each time.

| Work order | Model, effort | JEV | Result | Commit |
|---|---|---|---|---|
| WO-1 the bench module (`wo-1.md`) | gpt-6-sol, medium, try 1 | `model:starb:wo-1` -> sol 0.71, effort high 0.44: unsure. I took Jev's model lean (sol) at the ladder's table effort (medium), since a mutation sweep and a critic check the result, instead of paying for an advisor call on a model pick | 11 of 11 new tests and the 34 model tests passed, first try. One new file, in scope (`green-1.log`) | `49246fb` |
| WO-2 one review fix and cleanup (`wo-2.md`) | gpt-6-luna, low, try 1 | not asked: four named line-level changes, checked by the tests and by rerunning the bench | 45 passed; one file, 10 lines; every stored number identical after it (`green-2.log`) | `79c3739` |

CLIMBS: none. STRIKES: none. No Codex limit was hit. EFFORT: coordinator session setting unchanged.

### What the real data says

Run: `cd backend && uv run python ../docs/gauntlet/logs/step-8b-evidence/star_out.py`, against live nflverse files, 2026-10-13. Stored: `run-1.json` (first and only scoring run of the first code, commit `9e8f9b5`) and `final.json` (the final code, commit `79c3739`). The two agree on all 168 result numbers, to the last digit. Walk-forward, window 10 seasons, 3,649 regular-season games with a closing line, 2012 to 2025; tune 2,565 games; confirm 1,084 games in 72 season-weeks. Run time: 45 to 66 seconds (46 files downloaded: the schedule, 18 seasons of player stats, 17 of injury reports, 10 of rosters).

**Baseline check (operational layer):** market 66.57%, log loss 0.6094; blend 66.46%, 0.6107. On the confirm seasons: market 67.80%, 0.6082; blend 67.53%, 0.6095. Equal to step 14's stored numbers; the script stops if they ever differ.

Gain = how much lower the candidate's log loss is than the blend's (positive is better). Interval = paired bootstrap, 95%, game by game (this is the rule). "By week" = the same interval when whole season-weeks are resampled (shown beside it, never decides).

### Verdict table

**Read this first: the confirm set is 1,084 games. It cannot show a gain under about 0.001 log loss (here the interval is about 0.002 wide each side). Every "No" below means "no gain this test can see", not "proven useless".**

| Candidate | Chosen on 2012 to 2021 | Gain on 2022 to 2025 | Interval (the rule) | Interval by week | Accuracy change | Ships |
|---|---|---|---|---|---|---|
| A. Stars out on the official injury report | count of stars out (`p_star_count`) | +0.00016 | -0.00190 to +0.00203 | -0.00150 to +0.00174 | -0.18 points (2 fewer right picks of 1,084) | **No** |
| B. The same plus reserve lists (2016 on) | weighted (`p_star_res_weighted`) | +0.00063 | -0.00140 to +0.00273 | -0.00138 to +0.00268 | -0.09 points (1 fewer right pick) | **No** |

**In plain words:** knowing which of last season's stars are out does not beat the current model, so **the live model does not change**. Both intervals include zero and both candidates picked slightly fewer winners. The gains seen (+0.00016 and +0.00063) are far below the smallest gain this test can detect (about 0.001), and a tenth to a third of the interval's own half-width (0.0020). Two candidates were each looked at once on the confirm seasons; had one passed, there would have been about a one in ten chance of that happening by luck. Neither passed. The simplest reading: the closing betting line already carries who is out.

Limits to keep in mind (none of them changes the verdict): a "star" here is one of last season's top producers league wide, so rookies, players who missed last season and offensive linemen can never be stars; "out" is Out or Doubtful on the report (plus reserve lists in candidate B), never Questionable, never a game-day scratch; report rows carry no time in 2009 and in 2025, so for one of the four confirm seasons (2025) the rule "not changed after kickoff" could not be checked and rests on the league rule that the game status is issued before the game.

### Every variant tried (tune seasons, 2,565 games)

| Candidate | Variant | Tune gain | Tune interval | Tune accuracy | Chosen |
|---|---|---|---|---|---|
| A | `p_star_count`: count of stars out | +0.00003 | -0.00101 to +0.00106 | 0.00 points | yes |
| A | `p_star_weighted`: weighted by last season's production | -0.00005 | -0.00105 to +0.00100 | -0.04 points | no |
| A | `p_star_count_qb`: count, plus quarterback stars out as its own input | -0.00031 | -0.00168 to +0.00101 | -0.31 points | no |
| A | `p_star_weighted_qb`: weighted, plus quarterback stars out | -0.00038 | -0.00176 to +0.00097 | -0.43 points | no |
| B | `p_star_res_count`: count, report plus reserve lists | -0.00118 | -0.00269 to +0.00018 | +0.27 points | no |
| B | `p_star_res_weighted`: weighted, report plus reserve lists | -0.00097 | -0.00216 to +0.00013 | +0.35 points | yes (the less bad of two) |

That is every variant: six, frozen before the first run. Nothing else was run on the confirm seasons, and nothing was added after a result.

### Notes

* **The input points the right way and is small.** One fit on the tune seasons only (diagnostic, `tune_only_weights`) gives each extra star out a weight of about -0.076 on the home side's log-odds: roughly 1.9 points of win chance at an even game, on top of what the line says. With the reserve lists the weight is -0.052 (count variant; the weighted variant carried to the confirm seasons has -0.035). The quarterback input adds -0.042 and made every variant worse: the model's quarterback-change flag and the line already cover it.
* **Candidate A learned from 2009 on.** For 2012 it had 3 seasons to learn from, 10 from 2019. No scored game lacked a report input (0 missing). 1,068 of 3,649 scored games had a non-zero count (about 29%).
* **Candidate B is the blend until 2019.** Reserve lists are usable from 2016, a fit needs 3 seasons, so 1,784 tune games (2012 to 2018) equal the blend exactly and its tune numbers come from 2019 to 2021 only (781 games). It was worse than the blend there and the less bad variant was carried to the confirm seasons as the protocol says. On the confirm seasons it learned from 6 to 9 seasons.
* **Joins checked on every run** (reviewer findings H1, H2, M1): every season's Out or Doubtful rows match stars (98 to 178 per season, 9% to 16% of rows); every club code in the report and roster files is one the schedule has; 8 of 7,298 scored club-games had no report row that week (read as nobody out); every season file holds weeks 1 to 17; no injury row lacks a player id (383 stat rows and 140 roster rows do: club totals and unnamed entries, skipped).
* **The reserve check on the files the run used** (all weeks, `RES`, `PUP` and `SUS` together): 2016: 20 of 4,678 reserve player-weeks had a stat line that week (0.43%); 2017: 2; 2019: 9; every other season 0. The control: 59% to 71% of active player-weeks have a stat line, so the zeros are not a failed join. The run stops at 1%.
* **Report times:** 6 Out or Doubtful rows are dated at or after kickoff and are dropped. 1,003 of 1,008 such rows in 2009 and all 1,502 in 2025 have no time.

### Review round 1 (on `9e8f9b5`, before cleanup)

| Reviewer | Verdict | Report |
|---|---|---|
| `ecc:code-reviewer` | APPROVE. No leak found, no CRITICAL, no HIGH. 3 MEDIUM, 5 LOW | `~/.claude/plans/nfl-pickem-lanes-reviews/s8b-r1-code-reviewer.md` |
| `ecc:silent-failure-hunter` | No leak reported. 2 HIGH (both in the runner script), 6 MEDIUM, 4 LOW | `~/.claude/plans/nfl-pickem-lanes-reviews/s8b-r1-silent-failure-hunter.md` |

Neither reviewer could run the tests (their sandbox could not write the uv cache); the coordinator's own runs are the test evidence.

Rulings:

* **Accepted, fixed in the runner (coordinator's file):** a season file missing any of weeks 1 to 17 stops the run (a cut-short download can no longer pass quietly); a club code the schedule does not have stops the run; a season whose report rows match no star stops the run; the reserve check must cover every roster season and has a positive control; the JSON now carries rows per season and file kind, rows skipped for no player id, report rows with no time per season, the status values seen, and the per-season join table.
* **Accepted, fixed in WO-2 (frozen clause F1):** a season with playoff rows only got an empty star list, which read as "nobody out" instead of unknown. Red test first (`red-2.log`).
* **Accepted, fixed in WO-2:** weighted sums are added in a fixed order (they were added in set order, which could move the last digit between runs).
* **Accepted as a finding, said in the verdict (M4):** 2025 report rows have no time.
* **Kept as built:** blank stat cells count as 0 (nflverse leaves a stat blank when a player has none of it; a non-number stops the run); the runner counts "kept the blend's number" by exact equality (a fitted number equal to the blend's to the last digit does not happen; the counts match the rule exactly: 1,784 = the seven seasons 2012 to 2018); no flag columns added.
* **Carried, advisory:** a report status with stray spaces would not count (the values seen are exactly Out, Doubtful, Questionable, Probable, Note and blank); a quarterback whose last row has a blank position leaves the quarterback group; a season with a single training row counts as a season for the three-season rule; the runner script itself has no tests (its checks stop the run instead); Elo settings are tuned twice per season (cost only).

AGENTS: `ecc:code-reviewer`, `ecc:silent-failure-hunter` ran. `ecc:security-reviewer` and Dwight not run: no auth, user input, database query, file write or new network path; the runner downloads from the same nflverse host through the app's existing download function and reads one committed JSON file. `ecc:python-reviewer`, `ecc:pr-test-analyzer` not run: standard-size work item. `ecc:planner`, `ecc:architect`, `ecc:code-explorer` not run: the plan and the seam files came with the dispatch. `ecc:mle-reviewer` is the fresh critic (section 5).

## 4. CLEANUP

Explicit scope-locked refactor pass on the touched code (`/refactor` rules: behaviour unchanged, touched functions only), done by Codex in work order 2 (`wo-2.md`, gpt-6-luna), commit `79c3739`.

* **Simplified:** the reserve columns are computed with the same home-minus-away `zip` as the report columns (they used index numbers `(0, 1)` on an unlabelled tuple); the input columns are attached with `frame.assign(**inputs)` (was a dict built column by column); `_counts` walks the ids in sorted order.
* **No change needed:** `league_stars` (one pass to sum, one to rank), the two index helpers, `_club_out`, `star_preds` (the same shape as step 14b's `split_preds`, reusing its four helpers). No existing module was touched.
* **Proof after the edit:** `tests/test_star_backtest.py` and `tests/test_model.py` 45 passed (`green-2.log`); ruff clean; the bench rerun on the final code (`final.json`) and compared with the first run key by key: identical in all 168 result numbers.
* **Remaining findings, classified:** all advisory, listed under "Carried" above.
* **Mutation sweep** (`s8b-mutate.py`, `mutate.log`): 79 mutants of `star_backtest.py`; 77 caught on the first complete run, 2 survived: L2 (a tie between offence and defence score must go to offence) and F7 (the away side's reserve count must also include its own report). Both were real gaps, not equivalent mutants. One assertion each added to the existing tests (commit after `79c3739`); each of the two mutants re-applied by hand now fails a test (79 of 79 caught).
* **Rebase:** the branch was rebased on `main` e51ac48 (no conflicts; this lane's files are disjoint from the step 15 changes).

## 5. VERIFICATION

Fresh critic `ecc:mle-reviewer` (no build transcript), run on `f172d4b`: **PASS**. Its three first checks all passed:

1. No future data: PASS. Five hand-made leaks (`season - 1` to `season`; `_train_rows(..., season + 1, ...)`; kickoff guard replaced by `True`; the previous week's report indexed under this week; `predict_season` window + 1) each failed a named test.
2. Confirm seasons never used for tuning: PASS. In `final.json` and `run-1.json` each candidate's `chosen` is the variant with the largest tune gain; `backtest.evaluate` chooses it and raises if tune and confirm overlap; the six scored variants equal the protocol.
3. Reported numbers equal the stored files: PASS. Every cell of both tables was compared with `final.json`; `run-1.json` and `final.json` agree on all result keys.

Critic's gate on `f172d4b`: pytest 957 passed; ruff All checks passed; alembic No new upgrade operations detected; gen:api no drift. X1: `git diff --stat main..HEAD -- backend` shows only the two new files. Every clause L1 to L3, F1 to F7, P1 to P4 and X1 is pinned by a caught mutant; F8 and P5 are pinned indirectly (named tests). The critic ran 8 of its own mutants, all caught.

Advisories carried (none open against a clause): the log's header and Baseline still name the old base a71e112 (history; the branch was rebased onto e51ac48); the protocol says stats files 2008 to 2024 while the runner loads 2008 to 2025 (no 2026 game is scored); 2025 report rows have no time (disclosed); the runner script has no tests (it stops on bad input). One wording fix made from the critic's list: the -0.052 weight is the count variant, the weighted reserve variant is -0.035.

**Jev job 4** ("did the review truly pass?"): 0.78. That is between 0.1 and 0.8, so by the rule the advisor decides; the coordinator did not spend an advisor call and passes the decision to the integrator, with every gate green and the critic PASS.

## 6. LANDING

Branch `lane/starb`, rebased on main e51ac48, not pushed. Files: `backend/nflpi/analytics/star_backtest.py`, `backend/tests/test_star_backtest.py`, `docs/gauntlet/logs/step-8b*`. `lane-guard check` against `lanes.md`: OK. No seam change needed: nothing ships, so `engine.py` is unchanged. Security review not required (no auth, user input, database query, file write or new network path). The gate runs twice on the final commit (see the done message for the numbers).
