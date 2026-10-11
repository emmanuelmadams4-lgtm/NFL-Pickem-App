# NFL Pick'em Intelligence

Private decision support for weekly NFL Pick'em. One backend, one model, two apps: desktop web and iPhone/Android.

* Real data: nflverse schedules, results, betting lines, injury reports, team info. Open-Meteo forecasts.
* Model: Elo + QB-change + market blend, tested walk-forward on 2012 to 2025 (3,649 games).
* Every prediction is saved as a snapshot. Nothing is overwritten.
* Claude and Jev (OpenRouter) explain the evidence. They never make up the probability.

Read first: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (plan, data sources, model, honest results) and [docs/MOBILE_DEPLOYMENT.md](docs/MOBILE_DEPLOYMENT.md) (getting it on your phone).

## Run it (Docker)

```bash
cp .env.example .env          # set APP_ACCESS_TOKEN and POSTGRES_PASSWORD (match DATABASE_URL)
docker compose up -d --build  # db + app (API + web on :8000) + worker (refresh loop)
docker compose exec app python -m nflpi.jobs bootstrap   # first load: ~1 minute
```

Open http://localhost:8000 and paste your access token.
The worker keeps data and predictions fresh: every 4 hours most days, hourly in the last 2 days before a game, every 20 minutes in the last 6 hours.

Backups: `./scripts/backup.sh` (keeps the last 14 in `backups/`).

## Develop

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22+, Docker.

```bash
docker compose up -d db                      # Postgres on localhost:5432
cd backend && uv sync
echo "APP_ACCESS_TOKEN=dev-token" > .env
uv run alembic upgrade head
uv run python -m nflpi.jobs bootstrap        # load data, train, predict
uv run uvicorn nflpi.api.main:app --reload   # API on :8000

cd .. && npm install
npm run web:dev                              # web on :3000
npm run mobile                               # Expo dev server (scan with Expo Go or a dev build)
npm run gen:api                              # after changing backend/nflpi/api/schemas.py
```

## Test

```bash
cd backend && uv run pytest          # needs the db container; uses a separate nflpi_test database
uvx ruff check nflpi tests
cd .. && npm run typecheck
```

## Jobs

| Command | What it does |
|---|---|
| `python -m nflpi.jobs bootstrap` | Ingest, train, backfill this season, predict |
| `python -m nflpi.jobs ingest` | Schedules, lines, teams, injuries, weather |
| `python -m nflpi.jobs train` | Refit on past seasons + run the backtest |
| `python -m nflpi.jobs predict` | New snapshots for this week and next; push alerts on flips |
| `python -m nflpi.jobs loop` | The worker |

## Security

Single user. Every `/api` route except `/api/health` needs `Authorization: Bearer <APP_ACCESS_TOKEN>`. AI and push keys live only in the server's `.env`. Don't expose port 8000 to the internet without HTTPS; Tailscale is the easy private option (see the mobile guide).
