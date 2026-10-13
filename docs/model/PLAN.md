# Step 18 plan: what exists, what is missing, and how the rest is cut

Step 18a, lane `audit`, 2026-10-13. It reads the owner's brief (`docs/model/OWNER_BRIEF_2026-10-13.md`, cited as "brief §N") against the code on main at `589aa3b`, under owner decision D68. Companion files: `docs/model/AUDIT.md` (findings, cited here as A1 to A12) and `docs/model/REPOS.md`.

**In one line:** the win model and its test bench are sound and already cover most of brief §6, §10 and §12; what is missing is everything about spreads, totals and betting value (§3, §7, §8, §9), a point-in-time data layer with a feature dictionary (§4, §5), and a single evaluation report with saved run records (§10, §11). Seven lane-sized steps follow, 18d to 18j.

Words used below. **Bench:** the walk-forward backtest, which tests each season with a model fitted only on earlier seasons. **Blend:** today's live model, the stats model plus the betting line. **Cover:** a side beats the point spread. **Push:** the result lands exactly on the line and the bet is refunded. **Seam:** a file owned by another lane or by the integrator.

## 1. Gap table (brief §3 to §12)

HAVE = on main, with the file. PARTIAL = some of it. MISSING = nothing on main. "18b" and "18c" are being built now and are taken as given.

### §3 Prediction task and pick rules
| Requirement | State | Where, or what is missing |
|---|---|---|
| Straight-up pick from the win probability | HAVE | `backend/nflpi/predictions/engine.py:243` (home if 50% or more); recommendation = last snapshot before kickoff, `predictions/sheet.py:104-110` |
| The pool's tie rule | PARTIAL | Tied games are left out of fitting and scoring (`predictions/features.py:130-136`); no tie rule is modelled or configurable |
| Against-the-spread pick with push rules | MISSING | No cover probability anywhere (18c gives the probability, 18b the settlement, 18d the pick) |
| Confidence-pool weights, unique, by expected points | HAVE | `predictions/sheet.py:89-101` sorts by win probability and hands out unique points; for additive scoring that order is the expected-points optimum. Step 14c is testing the order |
| Betting-value analysis at a quoted price | MISSING | 18b (maths), 18i (ratings) |
| Mode is configurable, default straight-up, labelled | MISSING | One mode only today |
| A pick for every game, with an uncertainty warning instead of "no bet" | HAVE | `engine.py:238-256`: a game with no line still gets a pick from the stats model and the reason "No betting line yet" |
| NFL-specific, with interfaces other sports could use | PARTIAL | NFL only; no sport-neutral interface, and none is planned until a second sport is asked for |

### §4 Data layer
| Requirement | State | Where, or what is missing |
|---|---|---|
| pandas, NumPy, scikit-learn | HAVE | `backend/pyproject.toml` |
| Locally cached Parquet | MISSING | Files are downloaded as CSV on every run; the database is the store (`ingestion/nflverse.py:57-78`) |
| NFL season identifiers, not calendar years | HAVE | `ingestion/nflverse.py:141` reads nflverse's `season` |
| Settings: target season, as-of time, decision time, training window, feature windows, freshness, seeds, pick rules | PARTIAL | `config.py`: `train_window_seasons`, `first_season`, four `stale_hours_*`; `refresh_predictions(now=…)`. No as-of time for the data itself (A7), no target-season, seed or pick-rule setting |
| "All eligible information by the cutoff" | PARTIAL | True for results and ratings (A3, tested). Not enforceable for lines and quarterbacks in history (A6, A8) |
| Provenance, ingestion time, when-usable time | PARTIAL | `ingestion_runs`; `market_snapshots.observed_at`; `injury_reports.observed_at`; `weather_forecasts.observed_at`; `qb_observations` (since 2026-10-13). Nothing before our own first run |
| Coverage audit per feed, and the 2026 state | HAVE (this file) | Section 4 below |
| Forecast weather, not realized weather | PARTIAL | `ingestion/weather.py` stores forecasts with their time; `games.temp_f`/`wind_mph` from nflverse are realized values for finished games. Neither is a model input today |
| Schema validation, team-ID mapping, duplicate detection, missingness, season-transition checks, caching, repeat-safe updates | PARTIAL | Team mapping `nflverse.py:53`; repeat-safe upsert `ingestion/service.py:52-72`; star-file checks `service.py:211-243`. No schema check on `games.csv`, no duplicate-game check, no cache |
| A labelled synthetic fixture | HAVE | `backend/tests/conftest.py:1` ("realistic, made-up fixture games") |

### §5 Features
| Requirement | State | Where, or what is missing |
|---|---|---|
| One documented game-level table, home/away orientation | PARTIAL | `predictions/features.py:115-137` builds it (5 model inputs); not documented as a table |
| Only pre-cutoff information; sorted and shifted | HAVE | A3, tested in `tests/test_model_audit.py` and `tests/test_model.py` |
| Team efficiency (EPA, success rate, explosive plays, turnovers, red zone, pace) | PARTIAL | Bench only: `features.py:25-92` (net EPA per play, offence/defence EPA, success rate), tested in steps 14 and 14b, none shipped. Explosive-play rate is in step 14c. The rest is missing |
| Recency and opponent strength | PARTIAL | Elo is opponent-adjusted (`predictions/elo.py`); half-life EPA ratings on the bench |
| Situational: home, neutral, rest, short week, bye, travel, time zone, weather | PARTIAL | Home and neutral in the model; rest tested and dropped (`features.py:12`); travel, time zone and weather missing |
| Personnel: quarterback identity, quarterback rating, injury impact | PARTIAL | Quarterback-changed flags in the model; stars-out tested in step 8b, did not ship; no quarterback rating |
| Shrinkage and early-season handling | PARTIAL | Elo pulls one third back to the mean each season (`elo.py:17`); weeks 1 to 4 raise the uncertainty grade (`analytics/metrics.py:8`) |
| Nothing EPA-based is called DVOA | HAVE | No such name in the code |
| 0-100 matchup score with its formula | MISSING | 18e |
| Feature dictionary | MISSING | 18e |

### §6 Baselines
| Requirement | State | Where, or what is missing |
|---|---|---|
| Rating baseline, regularized logistic regression, market baseline | HAVE | `analytics/backtest.py:40-48` (home, elo, logistic, market, blend) |
| Margin and total regressions | PARTIAL | `predictions/scores.py:75` `ScoreModel` and `analytics/score_backtest.py` (step 9: did not beat the line-implied score). Step 14c tests a margin model |
| Gradient-boosted challenger | PARTIAL | Step 14c (lane modelc), not on main |
| Same games and cutoffs for every model | HAVE | `backtest.py:325-326` |
| Football-only and market-informed kept apart and labelled | HAVE | `logistic` against `blend`, labels at `backtest.py:42-48` |
| Chronological fit, calibration and test | HAVE | A5 (tested); `backtest.calibrated` fits on earlier seasons only |
| Reliability, Brier score, log loss | PARTIAL | `metrics.calibration` (five buckets), `brier`, `log_loss`. A decile table is in AUDIT A4; no plot |
| Simplest model preferred; fancy models optional | HAVE | A logistic regression on five inputs |

### §7 Simulator
| Requirement | State | Where, or what is missing |
|---|---|---|
| `simulate_game(...)` with win, tie, cover, push, over/under, intervals | MISSING | 18c, in flight (`backend/nflpi/sim/**`) |
| Wired into the prediction pipeline | MISSING | 18h (a seam: `predictions/engine.py`) |
| Classifier against simulator cross-check | MISSING | 18f |

### §8 Odds, settlement, edge
| Requirement | State | Where, or what is missing |
|---|---|---|
| American odds to implied probability, margin removed | HAVE | `predictions/market.py:8-48` (five methods) |
| Decimal odds, invalid-price rejection, settlement with pushes, edge and expected value | MISSING | 18b, in flight (`backend/nflpi/betting/**`) |
| Timestamped snapshots: game, book, time, market, selection, line, format, price | PARTIAL | `market_snapshots` (nflverse line, our own time, no book, no spread or total price); `market_quotes` (step 15: Kalshi and The Odds API, win market only) |
| Stale-odds rejection | MISSING | 18i |

### §9 Confidence, value ratings, abstention
| Requirement | State | Where, or what is missing |
|---|---|---|
| Forecast probability and uncertainty | HAVE | `Prediction.home_win_prob`, `uncertainty`, `uncertainty_reasons` |
| Pool confidence weight | HAVE | `predictions/sheet.py` |
| 1 to 5 value stars, `UNRATED`, `NO_BET` | MISSING | 18i. Note: `analytics/stars.py` is about star **players**, a different thing |
| Warnings for a missing quarterback, stale data, disagreement | PARTIAL | `analytics/metrics.py:21-38`: missing line, quarterback change, stats-market gap, early season, stale data. Not: out-of-range inputs, unsupported markets |
| No automated betting | HAVE | None exists; D68 keeps it out |

### §10 Evaluation
| Requirement | State | Where, or what is missing |
|---|---|---|
| Expanding or rolling-origin backtest with a decision time per game | PARTIAL | Walk-forward by season: HAVE. A decision time per game: MISSING in history (A6) |
| A final period kept untouched | PARTIAL | 2022 to 2025 has been scored nine times (A11). Untouched: 2026 games from now on |
| Live-logged against rebuilt forecasts | HAVE | `Prediction.kind` = `live` or `backfill` (`engine.py:329-347`) |
| Accuracy, log loss, Brier, calibration, by season, favourites/underdogs, confidence bands | HAVE | `backtest.run_backtest` |
| Pick'em points under the pool rules | PARTIAL | Weekly ranks and trends exist for his own picks (`analytics/trends.py`); no bench number for confidence points (step 14c) |
| Margin and total error; interval coverage | PARTIAL | `score_backtest.summary` (error); coverage missing |
| Against-the-spread and totals outcomes with pushes; fixed-stake returns | MISSING | 18f, and only as far as the odds history allows (section 3.4) |
| Intervals that respect grouping | HAVE | `metrics.bootstrap_ci(clusters=…)`, by week |
| Closing line only as a labelled benchmark | HAVE | `backtest.py:5-6`, labels at `:46-47` |
| Ablations | PARTIAL | Quarterback flags (`backtest.py:41`); nine ideas in steps 14, 14b, 8b |
| Tracking of what was tried | PARTIAL | The step logs; no single register of looks at the confirm seasons (A11) |
| Champion stays unless predeclared criteria are met | HAVE for the win model (D18) | Cover and totals: section 3 below |

### §11 Project shape
| Requirement | State | Where, or what is missing |
|---|---|---|
| Clear modules | PARTIAL | `ingestion/`, `predictions/`, `analytics/`, `api/`, `jobs.py`; `betting/` and `sim/` are coming; no `picks/`, no reporting module |
| Typed, pinned, no credentials in the repository | HAVE | `backend/uv.lock`; keys only in the server `.env` |
| Model record: training cutoff, feature list, parameters, evaluation summary | PARTIAL | `model_versions` (`engine.py:111-126`). Missing: data manifest, code revision, package versions, seed, calibration record |
| Scheduled and manual refresh, retrain, predict | HAVE | `jobs.py` (`bootstrap`, `ingest`, `train`, `predict`, `backfill`, `loop`, `backtest`) |
| No retrain because a price moved | HAVE | Weights are fitted once a season (A5, tested); a price change writes a new prediction row only |
| CSV and JSON outputs with the full prediction record | PARTIAL | JSON through the API; `GET /api/picks/export.csv` for picks. No export of the full record (cutoff, model version, market snapshot, push chance, edge, warnings) |
| Unavailable is not zero | HAVE | Nulls throughout (project rule) |

### §12 Tests
| Requirement | State | Where, or what is missing |
|---|---|---|
| Rolling features exclude the current game; cutoffs; chronological splits; fits on training data only | HAVE | `tests/test_model.py`, `tests/test_model_audit.py` |
| Team IDs, duplicate games, season transitions | PARTIAL | Season carry-over is tested for Elo and quarterbacks; no duplicate-game test |
| Missing and stale inputs | HAVE | `tests/test_model.py`, `tests/test_data.py` |
| Odds conversion and margin removal | HAVE | `tests/test_model.py` (devig tests) |
| Spread signs, settlement, expected value with pushes | MISSING | 18b |
| Probability normalization, valid and seeded simulated scores | MISSING | 18c |
| Required picks against betting abstention | MISSING | 18d |
| One end-to-end test on an offline fixture | HAVE | The `loaded` fixture: ingest, train, predict, backfill (`tests/conftest.py`) |

## 2. The remaining work, cut into lanes

Rules for every step below: new files wherever possible so lanes do not touch; no model change without the promotion criteria of section 3; nothing fitted on 2026 data. "Needs" lists what must have landed first.

| Step | Goal | Files it would own | Needs | Gate that proves it |
|---|---|---|---|---|
| **18d Pick rules** | Four modes kept apart (brief §3, §9): straight-up, against-the-spread, totals, confidence pool. Each returns a pick for every game plus warnings; betting advice is a separate answer that may say `NO_BET`. Default mode straight-up, labelled as an assumption. Pure functions, no database | `backend/nflpi/picks/**` (new), `backend/tests/test_picks.py`, `docs/model/PICK_RULES.md` | 18b, 18c | Tests: every game gets a pick in every mode; a push follows the brief's spread convention; `NO_BET` never removes a required pick; confidence weights are unique and maximize expected points on a worked example; one mutation per clause |
| **18e Data layer and feature dictionary** | An as-of frame builder (one cutoff time in, only rows observed before it out), validation (columns, team codes, duplicate games, season change, missing counts), a coverage report per feed, and `FEATURES.md` (every input: definition, source field, when it is known, fallback). The 0-100 matchup score is defined here as a **bench candidate**, not a model input | `backend/nflpi/data/**` (new), `backend/tests/test_data_layer.py`, `docs/model/FEATURES.md`, `docs/model/DATA_COVERAGE.md` | nothing (reads `ingestion/` and the tables). `nflreadpy` only if it loads play-by-play, and then by D68's dependency route | Tests: a row observed after the cutoff never appears; a duplicate game or unknown team code is refused with a clear error; the coverage report on the real files matches section 4 of this plan |
| **18f Evaluation report, run records, exports** | One report (brief §10) from the bench: sample sizes and exclusions; accuracy, log loss, Brier, decile reliability; margin and total error; interval coverage and cover/over rates from the simulator; simulator against classifier; by season and confidence band. A run record per model (code revision, lock-file hash, data hashes, seed, cutoff: the pattern noted in REPOS.md). CSV and JSON export of the full prediction record | `backend/nflpi/analytics/report.py`, `backend/nflpi/analytics/manifest.py`, `backend/nflpi/export.py` (all new), `backend/tests/test_report.py`, `docs/model/EVALUATION.md` | 18b, 18c, 18d. CLI lines in `jobs.py` are a seam (ask the integrator, at most 10 lines) | The report's win-model numbers equal the stored bench numbers (3,649 games, market 0.6094, blend 0.6107); every number has its sample size; a missing value prints as missing; rerun gives the same file |
| **18g Bench challengers from the brief** | Test, one at a time and under D18: a points-based (Pythagorean) head-to-head chance, a quarterback rating in place of the changed flag, travel and time-zone, the matchup score from 18e. Football-only and market-informed labelled | `backend/nflpi/analytics/bench_18g.py` (new), `backend/tests/test_bench_18g.py`, `docs/gauntlet/logs/step-18g*` | Step 14c landed (it owns `backtest.py` and `features.py`, which this reads); 18e for the matchup score; the owner's answer to section 3.5 | D18, unchanged. Each idea is logged as won or lost; the register of confirm looks (A11) is updated |
| **18h Wiring (seams)** | Put the simulator and the pick rules into the live path: `refresh_predictions` stores the simulated margin, total, cover and push chances beside the win probability; the API and the pick sheet expose the mode | Seams: `predictions/engine.py`, `predictions/sheet.py`, `api/schemas.py`, `api/views.py`, generated types; one migration if the prediction row grows | 14c, 18c, 18d landed; the integrator's grant for each seam | Existing insert-only and no-leak tests stay green; `tests/test_model_audit.py` stays green (bench and live still agree); `npm run gen:api` shows the intended change only |
| **18i Odds history and value ratings** | Store book prices with their time for spread and total as well as the win market; reject stale prices by a setting; the 1 to 5 star rubric with `UNRATED` and `NO_BET` (brief §9). Ratings are `UNRATED` until section 3.4 can be met | `backend/nflpi/value/**` (new), `backend/tests/test_value.py`; seams: `models.py` (append one table), one migration, `ingestion/live/oddsapi.py` | 18b, 18d; the owner's yes for any odds source that costs credits | Tests: a stale price is refused; a nonpositive expected value gives `NO_BET`; with no validation history every rating is `UNRATED`; no price is ever shown as still available |
| **18j Screens** | Show the spread, total and value outputs in the web app, with "not yet shown to beat the market" wording where section 3 has not been met | `apps/web/**` (lane web, Jim) | 18h | Lane web's design and browser gate |

**Order.** Wave 2, side by side on files that do not touch: 18d (after 18b and 18c land), 18e (can start now), 18i's storage half (can start once 18b lands). Then 18f. 18g and 18h wait for step 14c, because lane modelc owns the model and bench files. 18j is last.

**Not planned, and why.** A transformer or deep ensemble (brief §6 calls them optional; nothing on the bench suggests a gain). A fourth-down module (REPOS.md: the named repository has no pregame signal). A second sport.

## 3. Promotion criteria, written before any test

These are set now, before 18c's simulator or any cover or totals model has been scored on the confirm seasons.

### 3.1 Win probability: D18, unchanged
A challenger replaces the live blend only if, with its variant chosen on 2012 to 2021 and scored once on 2022 to 2025 against the blend on the same games, the paired-bootstrap 95% interval of the log-loss gain has its low end above zero **and** its accuracy is not lower (`analytics/metrics.py:109-136`, `ships`). The week-clustered interval is reported beside it and does not change the verdict.

### 3.2 Cover probability (against the spread): proposed
* **Question judged:** does the home side cover the nflverse closing spread? Pushes are left out and counted.
* **Baseline to beat:** 50% for every game. There is no cover model today, and a closing spread is built to split outcomes evenly, so a coin flip is the honest champion.
* **Rule:** variant chosen on 2012 to 2021, scored once on 2022 to 2025. It is **published as a rated probability** only if the paired-bootstrap 95% interval of its log-loss gain over the 50% baseline has its low end above zero, by game and by week, **and** its share of correct cover picks is not below 50%.
* **If it fails:** the simulator's cover chance may still be shown, labelled "not shown to beat a coin flip against the closing spread", and it drives no value rating.
* **What the test can see:** about 1,084 games. A true 52.4% (the break-even at -110 prices) is 1.6 standard errors from 50% at that size, so this test cannot confirm an edge that small. A "No" will mean "no gain this test can see".

### 3.3 Totals (over/under): proposed
The same rule with "the game goes over the nflverse closing total", baseline 50%, pushes left out and counted.

### 3.4 Point forecasts (margin, total): the step 9 rule, kept
A margin or total forecast replaces the line-implied number only if its error is lower with a paired-bootstrap interval that excludes zero (`analytics/score_backtest.py`, step 9's stricter rule). Step 9's two candidates did not pass.

### 3.5 What cannot be judged without a history of timestamped odds
1. **Any claim of betting value, expected value or return at an entry price.** The files hold one line per past game (nflverse's, treated as the close), not what was on offer at decision time, and no history of prices by book.
2. **Beating the closing line** (the usual test of a bettor's skill): it needs the price taken and the close, both timestamped.
3. **The live blend's true accuracy.** It is fitted and scored on closing lines but predicts from an earlier line (AUDIT A6). How much that costs cannot be measured from history.
4. **The star thresholds** (brief §9: "select thresholds using training/validation evidence"). With no history every rating is `UNRATED`.
5. **A stale-price threshold** and any book-against-book comparison.

What starts the history: `market_snapshots` (our own timestamps since deploy), the line-age report of step 13a, `market_quotes` (step 15), and 18i. The earliest honest verdict on any of the five is after one full season of our own snapshots: the 2026 regular season is 272 games.

### 3.6 One decision the owner should make (through the integrator)
2022 to 2025 has now been scored nine times for the win model (AUDIT A11). The proposal: keep D18 as the rule, **and** name the 2026 games from 2026-10-15 on, with predictions logged live before kickoff, as the untouched final period of brief §10. Nothing is tuned on them; they are read once, after the season. The cost: no verdict from them until January 2027. The alternative, to keep reusing 2022 to 2025, costs nothing now but makes each further "win" on it less believable. This is a two-way door. Until he answers, D18 stands as it is.

## 4. 2026 data coverage (brief §4), as of 2026-10-13

Checked from the public nflverse release files on 2026-10-13 at about 18:50 UTC (`docs/gauntlet/logs/step-18a-evidence/audit-numbers.json`, keys `season_2026` and `feeds`, and `feeds-extra.txt`). The app keeps no local copy of these files: it downloads them on each run and stores what it parses in its database. The live database was **not** opened by this lane, so "what the app has" below is what the code loads, not a count of live rows. Nothing here is made up: a blank means not checked.

| Feed | What the app loads today | Latest the public file covers | Missing |
|---|---|---|---|
| **Schedule, results, venues** | `games` table from `schedules/games.csv` (`ingestion/service.py:112-128`): teams, kickoff, score, neutral site, roof, surface, stadium, rest days | File updated 2026-10-13 18:46 UTC. 2026: 272 regular-season games, 79 finished, weeks 1 to 5, last finished game 2026-10-12; next game 2026-10-15. No playoff games listed yet | Travel distance and time-zone change: stadium coordinates exist only inside the weather adapter (`ingestion/weather.py:15`) and nothing computes either. A check for duplicate games or unknown team codes |
| **Play-by-play and team statistics** | **Nothing in the app.** Bench scripts download `stats_team/stats_team_week_<season>.csv` and play-by-play when a step needs them | `stats_team_week_2026.csv`: weeks 1 to 5, 158 team rows. `play_by_play_2026` updated 2026-10-13 16:56 UTC | No table, no loader, no cache in the app. Any EPA, success-rate or explosive-play input needs 18e first |
| **Rosters and quarterbacks** | `games.home_qb` / `away_qb` from the schedule file; `qb_observations` (when each name was first seen, since 2026-10-13); `team_stars` from snap counts, player stats and the players file | Quarterback names: all 79 finished 2026 games; of the 193 unplayed games only the 14 of week 6. `roster_weekly_2026` and `depth_charts_2026` exist (updated 2026-10-13) but the app does not load them | Projected starters beyond the coming week. A record of who was expected before each **past** game (AUDIT A8). Weekly rosters and depth charts |
| **Injuries** | `injury_reports` from `injuries/injuries_<season>.csv`, a row when a player's status changes, with our own download time (`ingestion/service.py:187-208`) | `injuries_2026.csv`: 1,413 rows, weeks 1 to 5, file updated 2026-10-13 14:57 UTC. No week 6 rows yet. No row carries a `date_modified` value, so our own download time is the only clock | When each status became public, for past seasons. Not a model input (step 8b tested stars-out: no gain) |
| **Weather** | `weather_forecasts` from Open-Meteo, each with the time it was fetched (`ingestion/weather.py`); `games.temp_f` / `wind_mph` from nflverse, which for finished games is the weather that happened | Not checked (live database; `CLAUDE.md` records the adapter as untested live) | Forecasts as they stood before **past** games: none exist, so weather cannot enter a strict backtest (brief §4 says to disclose this). Not a model input today |
| **Odds** | `market_snapshots`: the moneyline, spread and total in the nflverse schedule file, a new row when they change, with our download time. `market_quotes` (step 15): Kalshi and The Odds API, win market only | nflverse carries lines for the 28 games of weeks 6 and 7 and no later week; all 79 finished games have a line. The file also has spread and total **prices** (`home_spread_odds`, `over_odds`) that the app does not read. The Odds API and Kalshi: not checked, zero calls made | Any history of what the line was before a past game's close. Prices by book. Spread and total prices in our own tables. See section 3.5 |

**Features that cannot be built for 2026 today:** anything from play-by-play (no loader), a quarterback rating (no player-game table), travel and time zone (nothing computes them), and weather as a tested input (no forecast history).
