# CLAUDE.md — NFL Pick'em Intelligence

## Purpose
Private, single-user decision support for weekly Yahoo Pick'em: pick the straight-up winner of every NFL game. Evidence first. Never "lock" or "guaranteed". Win probability and uncertainty are different things and are shown separately.

## Architecture
* `backend/nflpi/` — one Python package (FastAPI, SQLAlchemy 2, Alembic, pandas, scikit-learn)
  * `ingestion/` nflverse + Open-Meteo adapters, run log, freshness
  * `predictions/` Elo, features, logistic model, engine (snapshots, change tracking, upset flags)
  * `analytics/` metrics, walk-forward backtest
  * `ai/` provider interface (Claude via Anthropic SDK, Jev via OpenRouter chat API), evidence pack, validated reports
  * `notify/` Web Push alerts + kickoff reminders (deduped, VAPID)
  * `api/` schemas (the contract), views (read models), main (routes, auth, static web)
  * `jobs.py` CLI + worker loop
* `packages/shared/` — TS types generated from the API's OpenAPI + one fetch client + shared formatters/sorting, imported as `@nflpi/shared`.
* `apps/web/` — Next.js static export, served by FastAPI in production. Also the iPhone app: PWA (manifest, `public/sw.js`, persisted query cache, offline picks queue, Web Push).
* Postgres 17. Docker Compose: `db`, `app`, `worker`.

## Conventions
* Match surrounding code. Small modules, typed, no new dependency without a reason.
* API change = edit `api/schemas.py`, then `npm run gen:api`. Never hand-edit `packages/shared/src/api-types.ts`.
* Python: ruff (line 120). TS: strict.
* No prediction logic in the client. It renders what the API returns.

## Commands
```bash
docker compose up -d db
cd backend && uv sync && uv run alembic upgrade head
uv run python -m nflpi.jobs bootstrap      # ingest, train, backfill, predict
uv run uvicorn nflpi.api.main:app --reload
uv run pytest && uvx ruff check nflpi tests
cd .. && npm install && npm run typecheck && npm run web:build
npm run web:dev
```

## Security
* Every `/api` route except `/api/health` requires `Authorization: Bearer $APP_ACCESS_TOKEN` (constant-time compare).
* Anthropic/OpenRouter keys and the VAPID private key only in the server `.env`. Never in web code. Never commit `.env`.
* AI calls are capped per day (`AI_DAILY_CALL_LIMIT`).

## Data integrity rules
* Never invent data. Missing stays missing (null) and is shown as missing.
* A failed ingestion keeps old data and is logged in `ingestion_runs`; freshness shows it.
* Predictions are insert-only. A new row only when the inputs hash changes. Earlier rows are never edited.
* The recommendation for a game is its last snapshot before kickoff. Picks lock at kickoff (CSV import may backfill past picks).
* `kind = backfill` predictions were computed after the fact with pre-game inputs (closing line). Always labeled.
* nflverse future starting QBs are projections; market lines for upcoming games are our own snapshots.

## Model validation requirements
* Walk-forward by season only. Fit (Elo settings, weights, home rate) on seasons before the test season.
* No post-game stats, no future injury status, closing line only as benchmark/blend (labeled).
* Every new feature must show a walk-forward log-loss gain (see `ablations`) or it is dropped. Rest days were dropped this way.
* "Better than X" needs a paired-bootstrap 95% interval that excludes zero.
* Weights refit once per season (`jobs train`); Elo moves weekly from results. No ad-hoc changes after a loss.

## Status (2026-10-11)
- [x] Phase 1 Architecture + research (docs/ARCHITECTURE.md, docs/IPHONE_PWA.md)
- [x] Phase 2 Foundation (FastAPI, Postgres, Alembic, auth, health, tests, Compose)
- [x] Phase 3 Data pipeline (schedules, lines, teams, injuries; weather adapter untested live here: host blocked in build sandbox)
- [x] Phase 4 Prediction engine + backtest (2012–2025: market 66.6%, stats 64.5%, blend 66.5%)
- [x] Phase 5 AI layer (validated reports + Q&A; live calls need keys)
- [x] Gauntlet step 1: safe backend + CI (2026-10-11; 48 tests, CI green on draft PR #1)
- [ ] Phase 6 Web dashboard (in progress)
- [ ] Phase 7 Performance tracking UI (in progress)
- [ ] Phase 8 iPhone PWA (in progress)
- [x] Phase 9 Alerts backend (Web Push + kickoff reminders); device test pending
- [ ] Live check with real ANTHROPIC/OPENROUTER keys
- [ ] Alerts on a real iPhone (needs HTTPS via Tailscale Serve + VAPID keys)
- [ ] EPA features from nflverse play-by-play (next model upgrade; must beat blend in walk-forward)

## Decisions (don't re-ask)
* 2026-10-11 — Phone app = PWA of the web app (owner). No Expo/native, no App Store/TestFlight, no Android build.
* 2026-10-11 — Push the feature branch + open draft PRs after verification (owner said yes).
* 2026-10-11 — Recommendation model = stats + market blend (ties market in backtest; stats-only is 2.1 pts worse).
* 2026-10-11 — Claude default model `claude-sonnet-5-5` (cheapest capable); Opus via `ANTHROPIC_MODEL`.
* 2026-10-12 — The model must get better over time at choosing winners (owner). Gauntlet step 8 is required: each idea is tested walk-forward first and ships only if it wins. No changes after a single loss.
* 2026-10-12 — Team logos are shown (owner, D37), from the API's `logo_url`, cached offline, team-color fallback. Owner decisions D1-D37: `docs/gauntlet/OWNER_DECISIONS_2026-10-12.md`.
