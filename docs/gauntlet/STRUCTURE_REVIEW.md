# Structure review (2026-10-11)

Independent read-only architect review on Opus. It stands in for `ecc:architect`, which isn't installed here. Reviewed commit `dbad5f9` plus the in-progress `apps/web`.

**Verdict:** the structure is sound and right-sized. That means one package, one database, a worker loop with no Celery, insert-only snapshots, an OpenAPI-generated contract, and the PWA served from the same origin. Nothing is seriously over-built; the only real cut is the doubled offline cache (S17). The deploy path is broken today (S1) and there's no CI to catch it. The weak spots are data integrity under concurrency and retraining (S2–S4) and worker robustness for reminders and push (S5). Fix S1–S6 before relying on it this season.

| ID | Severity | Problem (evidence) | Smallest fix | Step |
|---|---|---|---|---|
| S1 | blocker | Dockerfile, .dockerignore and package-lock still reference the deleted `apps/mobile` (31 expo + 20 react-native packages), so the image build breaks | Drop the mobile lines, regenerate the lockfile, drop Expo-only `overrides` | 1 |
| S2 | should-fix | `/api/refresh` uses an in-process thread lock while the worker container runs the same ingest/predict, so duplicate snapshots and rows are possible | `pg_try_advisory_lock` around ingest+predict in both paths | 1 |
| S3 | should-fix | Retraining the same season mutates an existing `ModelVersion`; the hash ignores params, so no new snapshot is written | Model versions are insert-only (params hash in name) | 1 |
| S4 | should-fix | CSV import overwrites locked picks after the result is known, inflating "my accuracy" | Past kickoff: insert only when no pick exists; add a test | 1 |
| S5 | should-fix | Reminders run last (skipped on any earlier error), `webpush` has no timeout, network errors aren't caught, and a 20-min cadence skips reminders under 25 min | Reminders first in their own try; `timeout=10`; catch `RequestException`; minimum 30 min | 1 |
| S6 | should-fix | Compose publishes `8000` on all interfaces (plain-HTTP token on the LAN); there are no proxy headers behind Tailscale Serve | Bind `127.0.0.1:8000`; uvicorn `--proxy-headers --forwarded-allow-ips="*"` | 1 |
| S7 | should-fix | Import cycles and wrong layers: engine imports a private `_elo_frames` from analytics; `train()` lives in predictions; notify pulls pandas in for a dataclass; ai imports api.views | Elo grid public in `elo.py`; `train` moves to analytics; `ChangeEvent` gets its own tiny module; `api/views` → `readmodels.py` | 2 |
| S8 | should-fix | Static mount sends no Cache-Control, so stale HTML can point at deleted chunks after a deploy | Middleware: `no-cache` for HTML/sw.js/manifest, `immutable` for `/_next/static/` | 4 |
| S9 | should-fix | Tests use `create_all`, never the migrations. Missing tests: last-snapshot-before-kickoff, retrain → new version, CSV lock, push 410/network error | One `alembic upgrade head` + `alembic check` test; the 4 focused tests | 1 |
| S10 | should-fix | No CI | One workflow: pytest on Postgres, ruff, typecheck, `gen:api` drift check, `docker build` | 1 |
| S11 | should-fix | `backup.sh` has no pipefail, so a failed dump still rotates good backups away; no schedule | bash + `set -euo pipefail`, reject empty dumps, document cron + restore | 6 |
| S12 | should-fix | Backtest label still says "+ rest"; the QB feature is tested on actual starters but used live on projected starters (an optimistic gain) | Fix the label; state the caveat on the Backtest page and in ARCHITECTURE | 2 |
| S13 | nice | AI daily cap counts rows, not attempts (~3x calls); `max_tokens` 4000/1500 risks cut-offs with thinking on | Count attempts; `max_tokens` ~16000 | 1 |
| S14 | nice | The Week board runs full-season `performance()`; predictions are filtered per game (quadratic); latest-by-game loads full history | Group once; `DISTINCT ON`; season accuracy only from `/performance` | 2 |
| S15 | nice | Current week = lowest week with an unfinished game, so a cancelled, never-scored game pins it forever | Use the week of the next upcoming kickoff | 1 |
| S16 | nice | Migration 0001 creates `push_devices` and 0003 drops it (branch never pushed, so squash is cheap); app and worker both run alembic on boot (race) | Squash to one initial migration; worker waits for a healthy app and skips alembic | 1 |
| S17 | nice | Two offline layers: the SW caches `/api/*` and React Query persists to localStorage | Keep the persisted query cache; SW caches the shell and static files only | 4 |
| S18 | nice | Leftover mobile references (CLAUDE.md, .env.example, `:8081` CORS default, schema/client comments) | Remove | 1 |
