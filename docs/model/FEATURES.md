# Feature dictionary (step 18e)

This file lists every input the model uses today and every candidate that has been tested or planned. It was checked against the code on main at commit 4cd599b. If a thing is not in that code, the table says "not built". Nothing here changes a prediction.

## How to read it

* **Known at** is the earliest moment the value can be computed. The rule is the as-of rule: a value may be used for a prediction only if `observed_at <= cutoff`, where the cutoff is the moment the pick is made. The helper for this rule is meant to live in `backend/nflpi/data/asof.py`. That package is **not built** on this branch, so today the rule is kept by hand: results and ratings obey it (AUDIT A3, tested), the live loader takes the newest line and quarterback name with no time filter (A7, `predictions/engine.py:52-63`).
* **Live vs backtest** says whether the live path and the backtest see the value at the same moment. Two known gaps: the backtest uses the closing line, a live pick uses the last line we saw (A6); the backtest has one quarterback name per game, the name of the man who started, while a live pick has a name for the coming week only (A8). How much either costs is not measured.
* **Spread sign rule (A13).** nflverse `spread_line` is positive when the home team is favoured. The owner brief writes the home spread `h` so that a favourite has a negative `h`. So `h = -spread_line`. The conversion must happen in one named function, `home_spread_from_nflverse`. That function is **not built** on this branch. Today `predictions/scores.py:19-24` uses the nflverse sign directly, and no model input uses the spread.
* **Terms.** EPA = expected points added (how many points a play is worth compared with the average play from the same spot). "No-vig" = a probability with the bookmaker's margin removed. Elo = a rating that moves after each result.
* All model inputs are in `BASE_FEATURES` and `BLEND_FEATURES` (`predictions/features.py:11-13`) and are built in `add_features` (`features.py:115-137`).

## Table 1. Model inputs (today)

Which inputs the production recommendation uses: the **stats + market blend** (CLAUDE.md, decision 2026-10-11). `engine.py:239-241`: if the game has a market line, the blend model (`market_logit` + the four stats inputs) is used; if it has no line, the stats-only model (the four stats inputs) is used. Fitted in `engine.py:108-109`. Model kind `blend-elo-qb` (`engine.py:27`).

| Name | Definition | Source field(s) | Known at (live / backtest) | Fallback when missing | Status | Where |
|---|---|---|---|---|---|---|
| `elo_diff` | (home Elo minus away Elo) divided by 100, both ratings taken before the game. Elo starts at 1505, moves by K times a margin multiplier times (result minus expected), and each team is pulled one third back to 1505 at the start of each season. K and home edge are chosen on training seasons only. | `games`: teams, season, kickoff, status, scores, neutral site (loaded by `load_frame`) | After the previous game's final score. Same on both paths; results cannot leak (A3). | No fallback needed: a new team starts at 1505. A tie counts as 0.5. | Model input (both models) | `features.py:118`; `elo.py:28-58`, defaults `elo.py:14-18` |
| `home_field` | 1 if the game is not at a neutral site, else 0. | `games.neutral_site` (nflverse `location == "Neutral"`) | When the schedule is published. Same on both paths. | `neutral_site` defaults to false, so a missing value counts as a home game. | Model input (both models) | `features.py:119`; `ingestion/nflverse.py:159` |
| `home_qb_change` | 1 if the home team's quarterback differs from its previous game's quarterback in the same season, else 0. | `games.home_qb` (nflverse `home_qb_name`) | **Differs.** Backtest: the name of the man who started, known for every game (A8). Live: the name on the newest download, present for the coming week only. | 0 when either name is blank or there is no earlier game in the season. A blank is never read as a change. | Model input (both models) | `features.py:100-112, 122-123`; `nflverse.py:167-168` |
| `away_qb_change` | Same, for the away team. | `games.away_qb` | Same as above | Same as above | Model input (both models) | same lines |
| `market_logit` | Natural log of p / (1 - p), where p is the no-vig home win probability from the two moneylines (multiplicative method), clipped to 1%-99%. | `market_snapshots.home_moneyline`, `away_moneyline` (nflverse schedule file); newest row per game | **Differs.** Backtest: closing line. Live: newest stored line, stamped with our own download time (A6, A7). nflverse has lines for the coming two weeks only. | NaN. The blend is not used for that game; the stats-only model is (`engine.py:239-241`). Rows with NaN are dropped from the blend fit (`model.py:21`, `engine.py:109`). | Model input (blend only) | `features.py:124-129`; `market.py:8-18`; `engine.py:52-63, 83-84` |

A sixth stored field, `rest_diff`, is built by `add_features` (`features.py:120-121`) but is not in either input list. See Table 2.

## Table 2. Bench candidates (not model inputs)

"Bench" means tested walk-forward by season in `analytics/backtest.py`. A candidate ships only if it improves walk-forward log loss and passes the paired-bootstrap rule (PLAN section 3.1). None of these changes a pick today.

| Name | Definition | Source field(s) | Known at (live / backtest) | Fallback when missing | Status | Where |
|---|---|---|---|---|---|---|
| `rest_diff` | (home rest days minus away rest days) / 7, clipped to -2..2. | `games.home_rest`, `away_rest` (nflverse) | When the schedule is published. Same on both paths. | Missing rest counts as 0 (`fillna(0)`). | **Dropped**: no log-loss gain in the 2012-2025 walk-forward test. Column still built, not used. | `features.py:12, 120-121` |
| `epa_diff` (net EPA per play, half-life rating) | For each game and team: (passing EPA + rushing EPA) / (pass attempts + sacks taken + carries), minus the opponent's same number. A team's rating is the decayed average of these over its earlier games, with half-life 4, 8 or 16 games. The feature is home rating minus away rating. | nflverse `stats_team/stats_team_week_<season>.csv`: `passing_epa`, `rushing_epa`, `attempts`, `sacks_suffered`, `carries`. Downloaded by the bench; **no table or loader in the app** (PLAN section 4). | After the team's previous game; the rating is read before the game's own row is added. Not a live input: nothing loads this file. | NaN when either team has no earlier rated game. Rows with a blank or non-finite value, or without exactly two sides, are skipped. | **Bench**, tested in step 14, did not ship | `features.py:25-49, 76-92`; `backtest.py:30, 130-150` |
| Offence EPA, defence EPA (`off_epa`, `def_epa`) | Team's EPA per play on offence; the opponent's EPA per play (what this team's defence allowed). Each rated with the same half-life method, then scaled by 10 and fed as home-minus-away differences. | nflverse play-by-play, summed per team per game: `plays`, `epa` | After the previous game. Not a live input (no loader). | NaN as above; games with non-positive or non-finite plays are skipped. | **Bench**, tested in step 14b, did not ship | `features.py:52-73`; `backtest.py:31-33, 153-177` |
| Success rate (`off_sr`, `def_sr`) | Share of a team's plays that were successful (nflverse's definition); same for the opponent. Scaled by 20. | play-by-play: `success`, `plays` | As above | As above | **Bench**, step 14b, did not ship | `features.py:52-73`; `backtest.py:33, 160-177` |
| Explosive-play rate | Share of plays gaining a large amount of yardage. | play-by-play | n/a | n/a | Step 14c: **on lane branch, not on main**. Nothing in the code on main (no `explosive` anywhere). | not on this branch |
| Stars out (`star_out_diff`, weighted and quarterback variants) | Count (or weighted count) of the previous season's top players listed Out or Doubtful before kickoff, home minus away. | nflverse player stats, injury reports (`injury_reports.observed_at`), weekly rosters | Our injury rows carry our own download time only; no past-season status history before our first run. | NaN when the season's reports or the earlier-season stars are missing. | **Bench**, step 8b, did not ship. Separate from the live "stars" display (`team_stars`, `analytics/stars.py`), which is not a model input (A12). | `analytics/star_backtest.py:15-21, 100-131`; `models.py:114` |
| Pythagorean head-to-head (points-based) | Win expectation from points scored and allowed, applied to the two teams. | would need game scores | n/a | n/a | **Not built** (planned for 18g) | none |
| Quarterback rating | A rating of the quarterback's play. | would need a player-game table | n/a | n/a | **Not built**. The app has no player-game table. | none |
| Travel and time zone | Distance and time-zone change between the two venues (estimates, not itineraries). | would need stadium coordinates for every team | n/a | n/a | **Not built**. Coordinates exist only inside the weather adapter (`ingestion/weather.py:15`) and nothing computes distance or time zone. | none |
| Forecast weather | Temperature, wind, gusts, rain chance and amount at kickoff hour. | Open-Meteo, table `weather_forecasts` (`temp_f`, `wind_mph`, `gust_mph`, `precip_prob`, `precip_in`, `observed_at`) | Fetched for games in the next 7 days and stamped with fetch time. Live only. No forecasts exist for past games, so it cannot enter a strict backtest. | NaN. Only outdoor, open or retractable-roof stadiums are fetched (`weather.py:needs_forecast`). | **Data exists, not a model input.** nflverse `games.temp_f`/`wind_mph` for finished games are the weather that happened, not a forecast. | `models.py:133-145`; `ingestion/weather.py`; `ingestion/service.py:293` |
| Line age | Hours between the last line we saw before kickoff and kickoff. | `market_snapshots.observed_at`, `games.kickoff_utc` | Computed per game after the fact, from snapshot rows seen before kickoff only. Live log only; no history before our first run. | None when no line was seen before kickoff. | **Report only** (step 13a), not a model input | `analytics/timing.py:54-92` |
| 0-100 matchup score | See the next section. | `elo_diff`, `market_logit` | Same as those inputs | NaN with no Elo | **Not built.** Specification only; the code on main has no matchup score (the word "matchup" in the code is the push-message and label text). | none |

## The 0-100 matchup score (bench candidate only)

Status: a specification for 18e. Nothing on main computes it. It is a summary index, **not a probability claim**, not a model input, and it changes no prediction.

* `z_elo = (ln(10) / 4) * elo_diff`, where `elo_diff` is (home Elo - away Elo) / 100. This is the Elo win-odds formula (400 Elo points = a factor of 10 in odds) written as log-odds, so it needs no fitted constant.
* `z_market = market_logit` (clipped log-odds of the no-vig home probability, as in Table 1).
* `z` = the mean of the components that are available. Elo is always available. The market component is used only in the market-informed variant, and only when the game has a line.
* `score = 100 / (1 + exp(-z))`.
* 50 means an even matchup. Above 50 favours the home side. Below 50 favours the away side.
* If there is no Elo (`elo_diff` is NaN) the score is NaN. It is never filled in.
* No fitted constant and no learned weight: the components are averaged with equal weight.
* **Football-only variant:** Elo only (`z = z_elo`). Label it "football-only".
* **Market-informed variant:** Elo and market (`z` = mean of `z_elo` and `z_market`). Label it "market-informed". It inherits the closing-line gap in A6 on the backtest.
* The score is a scale for reading a matchup, not a chance of winning. Do not show it as a percentage chance.
* Before it could ever be used as an input, step 18g must test it under D18: it must beat the current blend on walk-forward log loss, with a paired-bootstrap 95% interval that excludes zero. The underlying inputs are kept so the test can compare the score with its parts.

## Naming rule

Nothing EPA-based is called DVOA anywhere. Our EPA and success-rate ratings are our own, built from nflverse data. They are not Football Outsiders' DVOA, which is a different measure from a different source. Use "EPA rating" or "success-rate rating".
