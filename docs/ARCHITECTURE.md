# NFL Pick'em Intelligence: Architecture and Roadmap

Private, single-user decision support for weekly Yahoo Pick'em picks.
One backend, one database, one prediction engine. Two clients: a desktop web app and an iOS/Android app.

---

## 0. Honest feasibility check (run on real data, 2026-10-11)

Picking the betting-market favorite in every regular-season game:

| Span | Games | Favorite won |
|---|---|---|
| 2010 to 2025 (16 seasons) | 4,161 | **66.6%** |
| Best single season (2013) | 255 | 71.8% |
| Worst single season (2015) | 256 | 61.7% |
| Home team, same span | | 55.4% |

Source: nflverse `games.csv` closing moneylines. Ties excluded; 21 even lines counted as away favorite.

What this means:

* The market has never hit 80% over a season in this span. 80 to 85% is a stretch goal, not a plan.
* Your league leader at about 69% is already at or above the market.
* The real job: match the market's accuracy using information we can trust, then find the few games a week where the evidence says the market is wrong. Every claim of "better" must clear a confidence interval in the backtest.

---

## 1. Final technology architecture

```
                 ┌──────────────┐        ┌──────────────┐
                 │  Web (Next)  │        │ Mobile (Expo)│
                 │  desktop     │        │ iOS/Android  │
                 └──────┬───────┘        └──────┬───────┘
                        │  same typed client     │
                        │  (@nflpi/shared)       │
                        └──────────┬─────────────┘
                                   │ HTTPS + bearer token
                     ┌─────────────▼──────────────┐
                     │  FastAPI  (backend/nflpi)  │
                     │  api · ingestion ·         │
                     │  predictions · analytics · │
                     │  ai · notify · jobs        │
                     └──┬──────────┬──────────┬───┘
                        │          │          │
                 PostgreSQL   nflverse,   Claude API, OpenRouter (Jev),
                              Open-Meteo  Expo Push service
```

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, Alembic | Matches the stats stack; Pydantic schemas are the one source of truth for the API contract |
| Database | PostgreSQL 17 | Versioned predictions, indexed history |
| Models | pandas, NumPy, scikit-learn | Elo + logistic regression first. Gradient boosting only if the backtest proves it helps |
| Jobs | One `worker` process with a simple schedule loop | No Celery, no Redis. Refresh gets faster as kickoff gets closer |
| Web | Next.js (static export), React, Tailwind, TanStack Query, Recharts | Built into static files and served by FastAPI, so production is one app container |
| Mobile | React Native, Expo SDK 57, expo-router, TanStack Query + persisted cache | Native feel, one codebase for iOS and Android, offline cache |
| Shared | `packages/shared`: TS types generated from FastAPI's OpenAPI, one fetch client, shared formatters | Web and mobile can't drift from the backend |
| AI | Provider interface: Anthropic SDK (Claude) and OpenRouter (Jev) | Keys live only on the server |
| Push | Expo Push service called from the backend | No Firebase/APNs code to maintain |
| Deploy | Docker Compose: `db`, `app`, `worker` | Runs on a home computer or one small server |

Changes from the suggested layout, on purpose:

* `services/{api,ingestion,predictions,ai,analytics}` became **one Python package** (`backend/nflpi/`) with those same folders. Same separation, one install, one deploy, no cross-service glue.
* shadcn/ui and TanStack Table are skipped for now. The week view sorts 16 rows; a hand-built table is smaller. Add them if the UI needs them.
* `seasons`, `weeks`, `feature_snapshots` are not separate tables. Season and week live on `games`. Every prediction row stores its exact feature values, which is the feature snapshot.

## 2. Is Rust justified?

No. The biggest compute job is a 16-season backtest: about 4,300 games, a few seconds in NumPy. Nothing here is CPU bound, latency critical, or security critical enough to pay for a second language. Revisit only if a profiled hot path takes more than 10 seconds and NumPy can't fix it.

## 3. Data providers

| Provider | What we use | History | Refresh | Auth / limits | License / terms | Cost | Verdict |
|---|---|---|---|---|---|---|---|
| **nflverse** (`nflverse-data` GitHub releases) | Schedules, results, closing and latest moneylines/spreads, rest days, roof, surface, starting QBs, coaches, team colors/logos, official injury reports | Schedules 1999+, injuries 2009+ | Several times a day in season (automated GitHub Actions) | None; plain file download | Mostly CC-BY 4.0 (FTN charting is CC-BY-SA) | Free | **Primary source** |
| **Open-Meteo** | Forecast weather at outdoor stadiums | Forecast + historical archive | Hourly models | No key; under 10,000 calls/day, non-commercial | CC-BY 4.0, non-commercial | Free | **Weather** |
| The Odds API | Live multi-book moneylines, if nflverse lines lag | Current + paid history | Near real time | API key; free tier about 500 credits/month | Commercial ToS | Free tier, then about $30/mo | Optional later |
| Yahoo Fantasy Sports API | League data | n/a | n/a | OAuth | Yahoo ToS | Free | **Not usable for Pick'em** (see §13 note) |
| ESPN site APIs | n/a | | | Undocumented | No published terms | | **Not used**: unofficial |
| Sportradar / SportsDataIO | Official feeds | Deep | Real time | Key | Commercial license | Hundreds per month and up | Not needed for one user |

Rules built into the code:

* Each provider is an adapter. A failed run keeps the old data and marks that dataset stale. Nothing is filled in with made-up values.
* Every row keeps its source and when we saw it. Every dataset shows its last good refresh.

Gaps to say out loud:

* nflverse's starting QB for future games is a projection. It becomes the real starter once the game is played. The model treats it as "expected starter" before kickoff.
* nflverse lines for upcoming games change as the week goes on. We save a snapshot each time we pull, so line movement is our own record, not a provider feed.
* Historical injury reports exist (2009+) but "what we knew on Wednesday" is not cleanly recoverable. Injuries are shown and flagged. They are not a numeric model input until we can backtest them without leakage.

## 4. Database schema

```
teams(abbr PK, name, nick, conference, division, color, color2, logo_url)
games(game_id PK, season, week, game_type, kickoff_utc, weekday,
      away_team FK, home_team FK, away_score, home_score, status,
      location, neutral_site, div_game, roof, surface, stadium, stadium_id,
      away_rest, home_rest, away_qb, home_qb, away_coach, home_coach,
      temp_f, wind_mph, source, updated_at)
      idx (season, week), idx (kickoff_utc)
market_snapshots(id PK, game_id FK, observed_at, source, kind[latest|closing],
      home_moneyline, away_moneyline, spread_line, total_line,
      home_prob_novig)                      uniq (game_id, source, observed_at)
injury_reports(id PK, season, week, team FK, player_id, player, position,
      report_status, practice_status, injury, source, observed_at)
      idx (season, week, team)
weather_forecasts(id PK, game_id FK, observed_at, temp_f, wind_mph,
      gust_mph, precip_prob, precip_in, source)
model_versions(id PK, name, kind, params JSON, trained_through_season,
      metrics JSON, created_at, is_active)
predictions(id PK, game_id FK, model_version_id FK, created_at,
      home_win_prob, pick, features JSON, factors JSON, uncertainty,
      market_home_prob, inputs_hash, data_freshness JSON,
      is_final_pregame)                     idx (game_id, created_at)
user_picks(game_id PK FK, picked_team, picked_at, source[app|csv])
ai_reports(id PK, game_id FK, prediction_id FK, provider, model,
      created_at, status, report JSON, error, usage JSON)
ingestion_runs(id PK, source, dataset, started_at, finished_at,
      status, rows, error)
backtest_runs(id PK, created_at, config JSON, results JSON)
push_devices(token PK, platform, created_at, last_seen)
notifications(id PK, kind, game_id, dedupe_key UNIQUE, sent_at, payload JSON)
```

Rules: predictions are insert-only. A new prediction is written only when the inputs hash changes. Results come from `games`, so "was this pick right" is always computed, never stored twice.

Deferred tables (add in the phase that needs them): `players`, `team_game_statistics`, `player_game_statistics` (from nflverse play-by-play, for EPA features), `roster_status`.

## 5. Prediction methodology

The AI never makes a probability. The numbers come from here.

1. **Elo ratings** (one per team). Updated after every final game with a margin-of-victory multiplier. One-third regression to 1505 between seasons. Home edge and K are tuned only on seasons before the test season.
2. **Feature set** (all known before kickoff; each one had to earn its place in the backtest):
   * `elo_diff` (home minus away, per 100 Elo points)
   * `home_field` (0 at neutral sites; the model learns the home edge from recent seasons)
   * `home_qb_change`, `away_qb_change` (expected starter differs from the team's last starter this season). Kept: improves log loss.
   * `market_logit` (no-vig line) only in the **blend** model, used when a line exists
   * Tested and dropped: `rest_diff` (no gain). Division game, weather and head-to-head are shown as context, not model inputs.
3. **Logistic regression** on those features gives the home win probability.
4. **Calibration**: reliability buckets, Brier score, log loss.
5. **Output per game**: home/away win probability, pick, model version, timestamp, the feature values, the top factors for and against (coefficient × value), data freshness, and an **uncertainty grade** that is separate from the probability:
   * Low: no flags
   * Moderate: one flag
   * High: two or more flags. Flags: QB change, QB on the injury report, stats model vs market 10+ points apart, no line yet, stale data, under 3 games played

The word "lock" or "guaranteed" never appears.

**Upset watch**: a game is flagged when the market underdog has at least a 40% model chance, or the model and market pick different teams, or they differ by 8+ points. The flag shows both numbers and the reasons. No made-up "upset score".

**Change tracking**: a new snapshot is written only when inputs change. It stores which inputs changed (QB, line, Elo after a result) and the move. A push goes out if the pick flips or the probability moves 10+ points.

## 6. Backtesting strategy

* Walk-forward by season: to test season S, tune and fit on seasons before S only. Elo runs forward in time and only sees finished games.
* Seasons 2012 to 2025 tested (2002 to 2011 used only for the first training window).
* No leakage: no post-game stats, no closing line in the base model, no future injury status, scalers fit on train only.
* Metrics: accuracy, Brier, log loss, calibration by 10-point bucket, accuracy by season, favorites vs underdogs, vs the home baseline and the market.
* 95% intervals by bootstrap. "Model beats market" is only claimed if the paired-bootstrap interval for the accuracy gap sits above zero.
* Your own picks are scored the same way once you enter them.

### Results (run 2026-10-11, 3,649 regular-season games, 2012 to 2025)

| Model | Accuracy | 95% CI | Brier | Log loss |
|---|---|---|---|---|
| Always pick home | 55.4% | 53.7 to 56.9 | 0.247 | 0.688 |
| Elo only | 64.1% | 62.5 to 65.6 | 0.221 | 0.632 |
| Stats model (Elo + QB + home) | 64.5% | 62.9 to 66.0 | 0.220 | 0.629 |
| Betting market (closing line) | 66.6% | 65.1 to 68.1 | 0.211 | 0.609 |
| **Blend (stats + market)** | **66.5%** | 64.9 to 67.9 | 0.212 | 0.611 |

* Stats model vs market: −2.1 points, 95% CI −3.4 to −0.8. A real gap: the market knows more.
* Blend vs market: −0.1 points, CI −0.5 to +0.4. No proven difference. The blend is what the app recommends.
* Calibration is good: blend picks rated 70 to 80% (avg 74.6%) won 76.3% of the time; 60 to 70% (avg 64.7%) won 63.5%.
* When the stats model picked the market underdog (549 games), it was right 43.2% of the time. When the blend did (72 games), 47.2%. Upset flags mean "look closer", not "pick the dog".
* 2026 so far (through week 5 Sunday): see the Backtest and Performance pages; numbers update every run.

What would move the needle next: EPA-per-play team ratings from nflverse play-by-play (must beat the blend in this same test before it ships), and reading line movement between Wednesday and kickoff.

## 7. Claude / Jev integration

```
nflpi/ai/
  providers.py   AIProvider protocol → ClaudeProvider (Anthropic SDK), OpenRouterProvider (Jev)
  research.py    evidence pack, report generation + validation + retries, Q&A
nflpi/api/schemas.py  MatchupReport (Pydantic): the validated output contract
```

Flow per matchup (on demand, when you press "Generate"): load stats, injuries, market, weather and the model's prediction from our DB → send that evidence pack (and nothing else) to Claude or Jev → Claude uses structured outputs (JSON schema); Jev gets the schema in its prompt → validate against `MatchupReport` and check the pick and probability match the model and every source is a pack key → retry up to 2 times with the error, else save as failed with the reason → save with timestamp, provider, model and the prediction it explains.

* The AI explains; it cannot set or change a probability.
* Second opinion: generate the report with the other provider and compare. Two models agreeing is never called validation.
* Jev is `typesafe/jev-1.13` on OpenRouter, called in your setup by `~/.claude/bin/jev.sh` (not in this repo). This app uses OpenRouter's documented chat completions endpoint with the model id in config. No Jev-specific endpoint is invented. If Jev only answers its own question format, set `OPENROUTER_MODEL` to a chat model.
* Claude model: `claude-sonnet-5-5` by default (cheapest capable for grounded summaries; set `ANTHROPIC_MODEL=claude-opus-5-5` for deeper write-ups). Server-side refusal fallback is on.
* Spend controls: daily cap on AI calls (`AI_DAILY_CALL_LIMIT`, default 60). Reports are only made when asked; the latest one is shown until you make a new one.

## 8. Sitemap

**Web (desktop)**

| Route | Purpose |
|---|---|
| `/` | Week board: summary bar, sortable game table, one-click picks |
| `/game?id=` | Matchup: overview, factors, injuries, schedule/rest, weather, market, AI report, ask a question, prediction history |
| `/performance` | Weekly and season accuracy, you vs model vs market vs home, calibration chart |
| `/backtest` | Model comparison across seasons with intervals |
| `/settings` | Access token, CSV import/export, data freshness |

**Mobile (tabs)**

| Tab | Screens |
|---|---|
| Picks | Week board (cards), pull to refresh, one-tap pick, offline banner |
| Matchup (pushed) | Same sections as web, plus Ask Claude / Ask Jev |
| Results | Weekly and season accuracy, history |
| Settings | Server URL, token, notifications, download week for offline, last refresh |

## 9. Phased plan (desktop + mobile)

| Phase | Scope | Done when |
|---|---|---|
| 1. Architecture and research | This document, provider check, deploy research | Written and reviewed |
| 2. Foundation | Monorepo, FastAPI, Postgres, Alembic, token auth, health, tests, Compose | `pytest` green, `/api/health` up on Postgres |
| 3. Data pipeline | nflverse schedules, lines, teams, injuries; Open-Meteo weather; run log and staleness | Real 2026 data loaded, reruns are safe |
| 4. Prediction engine | Elo, logistic, baselines, backtest, calibration, snapshots, change tracking, upset flags | Backtest report with intervals, predictions for the current week |
| 5. AI | Claude + OpenRouter providers, validated reports, Q&A | Report validates in tests; live call works once keys are set |
| 6. Web dashboard | Week board, matchup, picks, history | Click-through works against real data |
| 7. Performance | Results, accuracy, calibration, CSV | Numbers match a hand check |
| 8. Mobile M1 | Expo app: picks board, matchup, one-tap picks, results, offline cache | Runs in Expo Go and on device; typecheck green |
| 9. Mobile M2 | Push: server alerts (flip, big move, QB status), local deadline reminders | Push arrives on a dev build |
| 10. Mobile M3 | AI assistant screen, "download week", polish | Ask works; airplane mode shows saved data with refresh time |
| 11. Hardening | Tests, backups, failure drills, docs | Fresh-clone setup works from README |

Mobile phases run after the API they need exists. Nothing in mobile changes backend behavior; it only adds endpoints (`/api/devices`, `/api/games/{id}/ask`).

## 10. Costs (monthly, estimates)

| Item | Cost |
|---|---|
| nflverse, Open-Meteo | $0 |
| Hosting: your own computer + Tailscale (private network to your phone) | $0 |
| Or: one small cloud server | about $5 to $12 |
| Claude API (Sonnet 5.5, $2/$10 per million tokens): about 16 reports a week at roughly 1 to 2 cents each, plus questions | about $1 to $5 a month; daily cap in config |
| OpenRouter (Jev second opinion) | depends on Jev pricing; capped in config |
| Apple Developer Program (needed for push and long-lived installs) | $99 per year |
| Android sideload | $0 |
| Expo push service, EAS free plan | $0 |

## 11. Risks and open items

| Risk | Impact | Plan |
|---|---|---|
| 80 to 85% is above anything the market has done | Disappointment | Track vs market weekly with intervals; aim to beat 66.6% |
| nflverse is community-run | Data delay | Staleness banners; optional Odds API adapter |
| Projected QB is wrong | Bad pick | Uncertainty flag, injury report shown, alert on QB status change |
| Yahoo has no Pick'em API | Manual entry | One-tap picks in app + CSV import/export |
| Jev's own endpoint is unknown here | Second opinion may not work | Uses OpenRouter chat API; swap model id in config |
| Phone must reach the server | App can't load new data away from home | Tailscale (private) or a small server with token auth; offline cache always works |
| No API keys in this build environment | AI and push not live-tested here | Fake providers in tests; live check is a 2-minute step after keys are set |

## 12. Smallest real MVP

1. Load real nflverse schedules, results and lines.
2. Elo + logistic model with a walk-forward backtest against the market.
3. Predictions for the current week with factors and uncertainty.
4. Week board and matchup page on web and phone.
5. One-tap picks and accuracy tracking.

AI reports, push and weather come right after, on the same backbone.

---

## 13. Yahoo Pick'em integration

Yahoo's Fantasy Sports API covers fantasy football, baseball, basketball and hockey leagues. Pick'em games are not in its documented resources, so no reading of league picks or standings is possible through it. No scraping. The app supports manual one-tap picks and CSV import/export. Revisit if Yahoo documents Pick'em access.

## 14. Mobile delivery (personal use)

See [MOBILE_DEPLOYMENT.md](MOBILE_DEPLOYMENT.md).
