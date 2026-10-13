# Owner brief: model platform (step 18)

The owner gave this brief in chat on 2026-10-13 at about 18:10 UTC with the words: "OK the model is not good enoguh I want to enhance it with this prompt". It is kept word for word below. Owner decision D68 in `docs/gauntlet/OWNER_DECISIONS_2026-10-12.md` records how it is read. Lanes cite it by section number (1 to 13).

---

You are a senior machine-learning engineer, NFL quantitative analyst, and open-source Python maintainer.

Rebuild and improve my existing NFL pick’em system into an auditable, reproducible, open-source forecasting platform. The system should support straight-up picks, against-the-spread picks, totals, and optional betting-value analysis using historical data and available 2026-season data.

Build an independent system with capabilities such as matchup analysis, probabilistic forecasting, and Monte Carlo simulation. Do not claim to reproduce SportsLine’s proprietary algorithms or performance.

Your goal is measurable out-of-sample improvement—not simply adding more models, features, repositories, or simulations.

Work in my existing repository when available. Otherwise, create a runnable standalone project with clearly documented integration points.

# 1. Start by diagnosing the existing system

Before replacing the model, inspect the available code, datasets, configuration, saved models, prediction logs, and evaluation results.

Determine:
- What the system predicts and how picks are selected.
- Whether training and inference use identical feature definitions.
- Whether rolling features, preprocessing, injury information, or market lines leak future information.
- Whether probabilities are calibrated.
- Whether the evaluation uses chronological splits and realistic prediction cutoffs.
- Whether the model beats simple baselines on the same games.

Separate verified findings from hypotheses. Do not invent explanations for poor performance without evidence.

Preserve useful infrastructure, public interfaces, and existing functionality. Avoid an unnecessary wholesale rewrite.

If the current repository or results are unavailable, state that limitation and proceed with a standalone implementation. Do not claim to have diagnosed code you have not inspected.

# 2. Audit and selectively incorporate these repositories

Use these repositories as implementation references and potential dependencies:

1. https://github.com/nflverse/nflreadpy
   Evaluate as the primary NFL data-access layer.

2. https://github.com/BlairCurrey/nfl-analytics
   Evaluate for pipeline organization, spread modeling, CLI workflows, automation, and model artifact management.

3. https://github.com/jamesjholee/nfl-predictions
   Evaluate for modular data processing, feature engineering, and baseline model implementations.

4. https://github.com/ethan-dinh/NFL-Prediction
   Evaluate for ensemble modeling and probability-calibration approaches.

5. https://github.com/varnsen-net/nfl-modeling
   Evaluate for advanced feature engineering and modeling approaches.

6. https://github.com/23ccozad/nfl-4th-down-ml-model
   Evaluate for fourth-down decision modeling and situational football analysis.

Supporting references:
- https://github.com/nflverse
- https://opensourcefootball.com/

Treat the descriptions above as proposed areas to investigate, not verified claims about current repository contents.

For each repository, verify its availability, license, relevant functionality, dependency requirements, and compatibility with this project. Record the exact commit or release inspected.

Produce a compact integration table:
repository | verified capabilities | license | proposed use | adopt/adapt/defer/reject | reason

Do not copy incompatible code, treat an unlicensed repository as freely reusable, or combine entire projects indiscriminately. Maintain attribution where required.

Prefer a small, coherent implementation over a collection of unrelated model pipelines. Keep advanced architectures optional until they demonstrate measurable benefit.

If repository inspection is unavailable, mark it unverified and avoid inventing APIs, capabilities, or successful integrations.

# 3. Define the prediction task and pick’em rules

Keep these objectives separate:

STRAIGHT-UP PICK’EM:
Choose the team with the highest calibrated probability of winning under the pool’s tie rules.

ATS PICK’EM:
Choose the side with the highest probability of covering the specified pool spread. Apply the pool’s push rules.

CONFIDENCE POOLS:
Assign unique confidence weights according to the pool’s scoring system. Optimize expected points for additive scoring; do not confuse these weights with betting-value stars. More complex pool-winning strategies require explicit opponent and payout assumptions.

BETTING-VALUE ANALYSIS:
Evaluate a particular wager at a particular available price. A likely winner is not automatically a valuable bet.

Make the mode configurable. Default to straight-up NFL pick’em when pool rules are unavailable, and label that assumption.

If the pool requires a pick for every game, provide a pick with an uncertainty warning rather than using “NO BET” as a missing pick. Betting recommendations may abstain independently.

Use an NFL-specific implementation initially, with interfaces that could support other sports later. Do not apply NFL features or scoring assumptions to other sports without sport-specific models.

# 4. Build a versioned, as-of-aware data layer

Use pandas, NumPy, and scikit-learn and/or XGBoost for core modeling. Use Polars where a verified data source or performance requirement justifies it.

Prefer structured, documented data sources and locally cached Parquet files over fragile scraping.

Support available, relevant historical seasons and the 2026 NFL season. Use NFL season identifiers rather than assuming calendar-year filters identify a season correctly.

Configure:
- target_season, initially 2026;
- as_of_utc;
- prediction lead time or explicit decision timestamp;
- historical training window;
- feature windows and decay parameters;
- data-freshness thresholds;
- random seeds;
- pick’em rules and market settlement rules.

“Use all data” means all eligible information available by the prediction cutoff—not every column or every observation.

Track source provenance, ingestion time, and information-availability timestamps where available. Distinguish when an event happened from when its information became usable.

Audit source coverage separately for:
- schedules, results, and venues;
- play-by-play and team statistics;
- rosters and quarterback information;
- injuries and player availability;
- weather forecasts;
- market odds and line snapshots.

Do not assume one provider supplies all of these.

For 2026, report the latest available date, games covered, incomplete feeds, and missing features. Do not fabricate current games, injuries, lines, or results.

Use weather forecasts available before the prediction cutoff, not realized game weather. Apply the same principle to injury reports, starters, and lineup changes.

If historical information-availability timestamps do not exist, disclose that the affected feature cannot support a fully point-in-time-verified backtest. Exclude it from the strict backtest or report it separately.

Add schema validation, team-ID normalization, duplicate detection, missingness checks, season-transition checks, caching, and idempotent incremental updates.

Provide a clearly labeled synthetic fixture for offline tests. Never present synthetic data as real NFL or 2026 evidence.

# 5. Engineer football features without leakage

Create one documented game-level feature table with a consistent home/away orientation.

Every feature must use only information available before the game’s prediction cutoff. Sort games chronologically and shift rolling calculations before joining them to prediction rows.

Candidate features should include:

TEAM EFFICIENCY:
Offensive and defensive EPA per play, passing and rushing EPA, success rate, yards per play, explosive-play rate, sacks or pressure proxies where supported, turnover rates, red-zone efficiency, and pace.

RECENCY AND OPPONENT STRENGTH:
Multiple rolling windows, exponentially weighted averages, season-to-date estimates, sample sizes, and opponent-adjusted offensive and defensive ratings.

SITUATIONAL CONTEXT:
Home-field advantage, neutral-site status, rest days, short weeks, bye weeks, venue-based travel-distance proxies, time-zone changes, and weather/roof information available at the cutoff.

PERSONNEL:
Quarterback identity and expected availability, quarterback performance estimates, and defensible injury-impact features when source coverage supports them.

Treat venue-based travel distances as estimates, not verified team itineraries.

Use shrinkage or regularization for unstable and small-sample features. Handle early-season uncertainty explicitly rather than treating one game as a reliable estimate of team strength.

Do not label an EPA-derived feature “DVOA.” Include DVOA only through an explicitly available, appropriately licensed source, and document its definition separately.

MATCHUP SCORE:
Build a transparent 0–100 matchup score comparing one team’s offense with its opponent’s defense, plus the reverse matchup.

Specify the formula, feature directions, normalization method, missing-data behavior, and any weights. Fit normalization and learned weights using training data only.

A matchup score is a summary index—not a win probability. Retain its underlying features and test whether the summary adds predictive value.

Produce a feature dictionary with definitions, source fields, availability rules, transformations, and fallback behavior.

# 6. Establish baselines before advanced models

Implement and compare:
- A simple historical or rating-based baseline.
- Regularized logistic regression for game outcomes.
- Simple margin and total regressions.
- Gradient-boosted challengers using XGBoost or a suitable scikit-learn implementation.
- A market-implied baseline when appropriate timestamped odds exist.

Compare models on identical eligible games and prediction cutoffs.

Maintain separate experiments for:
1. A football-data-only model.
2. A market-informed model that uses lines available at the decision timestamp.

Do not present a model that consumes market prices as an independent discovery of the same market information.

Use chronological training, validation, calibration, and test periods. Fit imputers, scalers, encoders, feature selection, hyperparameters, and calibration only on permitted training-side data.

If the dataset contains two team-perspective rows per game, keep both rows in the same fold.

Evaluate probability calibration using reliability plots, Brier score, and log loss. Select calibration methods using time-respecting validation; do not fit them on the final test set.

Prefer the simplest model that performs reliably. Transformers, deep ensembles, and fourth-down modules are optional challengers, not prerequisites.

A fourth-down module must use pregame-available tendencies or legitimately simulated game states. It must not introduce actual future in-game decisions into pregame forecasts.

# 7. Build a validated Monte Carlo game simulator

Provide this public function, allowing additional keyword-only arguments when necessary:

simulate_game(team_a_features, team_b_features, n_simulations=10_000)

Integrate it into the prediction pipeline rather than leaving it as an isolated demonstration.

The simulator must return score samples and derived probabilities for:
- each team winning;
- regulation/final ties where relevant;
- each side covering a specified spread;
- spread pushes;
- over, under, and total pushes;
- expected margin and total;
- useful predictive intervals.

Use reproducible random-number generation and vectorized computation where practical.

Start with a defensible baseline distribution, then evaluate alternatives such as overdispersed count models, shared-factor score models, paired residual sampling, or drive-level simulation.

An independent Poisson model may be a baseline, but do not assume it adequately captures football score distributions, score dependence, tails, or ties.

Learn distribution parameters from historical training data. Do not assign arbitrary scoring rates or variance multipliers without validation.

Ensure simulated scores are nonnegative and internally consistent. Handle score discreteness, dependence, overtime, and season-appropriate rules explicitly.

Call the implementation a game-score simulation unless it actually models play-by-play state transitions. Do not market a score sampler as a play-by-play engine.

Cross-check direct classifier probabilities against simulation-derived probabilities. Document the source of each published probability and investigate material inconsistencies.

Distinguish Monte Carlo error from model uncertainty. For independent simulated event indicators, report sampling standard error where useful:

SE = sqrt(p × (1 − p) / n_simulations)

Do not present this as the model’s total uncertainty.

Increasing simulation count reduces sampling noise; it does not repair biased predictions, missing information, leakage, or poor calibration.

# 8. Implement correct odds, settlement, and edge calculations

Accept timestamped market snapshots with:
game ID, sportsbook, observed time, market type, selection, line, odds format, and price.

Support American and decimal odds. Reject invalid prices and mismatched market pairs.

For American odds A:
- If A > 0: decimal_odds = 1 + A / 100
- If A < 0: decimal_odds = 1 + 100 / abs(A)
- A = 0 is invalid.

Raw implied probability:
q = 1 / decimal_odds

For a complete set of mutually exclusive, exhaustive outcomes from the same market snapshot, calculate a transparent proportional no-vig baseline:

p_market_i = q_i / sum(q)

Do not mix sportsbooks, timestamps, or different lines to construct a supposedly coherent no-vig market.

Where pushes or ties are refunded, compare probabilities conditional on a non-push result:

p_model_conditional = P(win) / [P(win) + P(loss)]

Handle two-way and three-way moneyline markets according to their actual settlement rules.

Report these separately:
- Fair-market probability edge = model probability − no-vig market probability.
- Price edge = model conditional win probability − quoted break-even probability.
- Expected value per unit staked.
- Signed point difference between the forecast and quoted spread or total.

For a wager with decimal odds d:

EV = P(win) × (d − 1) − P(loss)

A refunded push contributes zero profit.

Do not use the absolute difference as “edge”: a negative difference is evidence against that selection.

Do not compare a probability percentage with a spread measured in points. ATS and totals betting value must come from cover/over/under probabilities at the offered price, not just a mean-score difference.

Use this explicit spread convention:

M = home_score − away_score
h = quoted home spread

Home covers when M + h > 0.
Home pushes when M + h = 0.

For a total L:

Over wins when home_score + away_score > L.
Under wins when home_score + away_score < L.
Equality is a push.

If opposing prices are unavailable, report that no-vig comparison is unavailable. EV may still be calculated for a quoted selection when its settlement probabilities are available.

Reject stale odds according to configuration. Do not imply a historical quoted price is still available.

# 9. Separate confidence, value ratings, and abstention

Expose three distinct concepts:
1. Forecast probability and uncertainty.
2. Pick’em confidence or pool confidence weight.
3. Betting-value star rating.

Implement a documented, configurable 1–5-star rubric for eligible betting-value signals.

The rubric should account for estimated EV, calibration quality, model uncertainty, supporting sample size, and data freshness. Select thresholds using training/validation evidence and freeze them before final evaluation.

Do not use “edge greater than 5% means five stars” as an unsupported universal rule.

When evidence is insufficient to validate the rubric, return UNRATED or explicitly label the ratings provisional. Stars are not guaranteed win rates.

Return NO_BET for nonpositive estimated EV or failed reliability checks. This must not suppress mandatory pick’em selections.

Missing quarterback information, unsupported markets, stale prices, out-of-distribution inputs, or major model disagreement should trigger warnings, abstention, or reduced confidence under explicit rules.

Do not add automated wagering or claims of guaranteed profit.

# 10. Run realistic, leakage-resistant evaluation

Use rolling-origin or expanding-window backtests with a defined decision timestamp for every game.

Keep a final period untouched until model selection, feature choices, calibration, and rating thresholds are frozen.

Evaluate 2026 predictions only when they could genuinely have been produced before kickoff. Distinguish retrospectively reconstructed forecasts from predictions logged live.

Report:
- Sample sizes, exclusions, and source coverage.
- Straight-up accuracy and pick’em points under the selected rules.
- Log loss, Brier score, and probability calibration.
- Margin and total MAE/RMSE.
- Distribution or interval coverage.
- ATS and totals outcomes, including pushes.
- Fixed-stake betting returns where authentic timestamped odds exist.
- Uncertainty intervals that respect relevant grouping or time dependence.

Use closing lines only as an explicitly available-at-cutoff input or as a later evaluation benchmark. Never silently use them to evaluate an earlier entry decision.

Break down results by season, forecast-confidence group, favorites/underdogs, and relevant sample-size bands. Flag small samples.

Run ablations for matchup score, personnel features, situational features, opponent adjustment, market inputs, and advanced models.

Track experiment selection to reduce cherry-picking. Do not tune to the final test set or report only favorable subsets.

Treat short-run betting returns as noisy evidence, not proof of a durable advantage.

Compare against the existing model when available. Keep the current model as champion unless the challenger satisfies documented, predeclared promotion criteria.

If improvement is not established, say so and identify the most useful next experiment.

# 11. Deliver a maintainable Python project

Organize the implementation around clear modules:

- data ingestion, schemas, and quality checks;
- as-of feature generation;
- baselines, training, and calibration;
- simulation;
- odds conversion and settlement;
- pick’em rules and recommendation logic;
- backtesting and reporting;
- CLI and configuration;
- tests, fixtures, and documentation.

Use typed interfaces, meaningful exceptions, structured logging, and a compatible pinned dependency set.

Keep credentials out of source control. Save model artifacts with:
training cutoff, feature schema, data manifest, parameters, random seed, package versions, code revision, calibration artifact, and evaluation summary.

Provide configurable scheduled and manual workflows for refreshing data, rebuilding features, retraining when appropriate, and generating predictions.

Do not retrain merely because a market price changed. Separate model training, feature refresh, and price-based recommendation refresh.

Provide CSV and JSON outputs. A prediction record should include:
game, kickoff, prediction cutoff, source freshness, model version, selected team/side, calibrated probability, predicted score/margin/total, applicable market snapshot, push probability, edge, EV, confidence weight, star status, and warnings.

Clearly distinguish unavailable values from zero.

# 12. Test the failure modes that matter

Include automated tests for:
- Rolling features excluding the current game.
- Cutoff filtering and chronological splits.
- Preprocessing fitted only on training data.
- Team IDs, duplicate games, and season transitions.
- Missing and stale inputs.
- Odds conversion and no-vig normalization.
- Positive and negative spread conventions.
- Spread, total, and moneyline settlement.
- EV calculations including pushes.
- Probability normalization and valid simulated scores.
- Deterministic seeded simulations.
- Required pick’em selections versus betting abstention.

Include at least one end-to-end test using a small offline fixture.

Report which tests and commands you actually ran. Do not invent successful execution, model metrics, repository inspection, or live-data availability.

# 13. Execute in this order and return concrete deliverables

Prioritize a reliable vertical slice:
ingest → validate → build point-in-time features → train baseline → calibrate → simulate → score picks → backtest → export.

Then add complexity only where evaluation supports it.

Return:
1. A concise audit of the existing system, or an explicit statement that it was unavailable.
2. The repository verification and integration table.
3. The architecture and important modeling decisions.
4. Runnable implementation, not only pseudocode or an architectural plan.
5. Configuration and commands for setup, ingestion, training, backtesting, and 2026 prediction generation.
6. Tests and actual execution results.
7. An evaluation report separating observed performance from proposed improvements.
8. Remaining limitations and the next highest-value improvement.

When a workspace is available, create or modify the files directly. Otherwise, provide file-by-file code.

Do not leave TODOs in the core forecasting path and describe it as complete. External integrations blocked by unavailable access should fail explicitly and be labeled unverified; provide a working offline path instead.

Do not stop after a plan or ask for broad confirmation. Make reasonable defaults explicit, implement the smallest complete system first, and clearly distinguish completed work from blocked work.
