# Step 1 of 8 — Safe backend + CI + first landing (T3)

Session started 2026-10-11 on the owner's Mac (`/Users/emmanueladams/Projects/NFL-Pickem-App`), coordinator on Opus 5.5. `DIRECT_COORDINATOR / ONE_SHOT`.
Logs: `~/.claude/plans/nfl-pickem-intelligence-logs/` (prefix `s1-`). Reviews: `~/.claude/plans/nfl-pickem-intelligence-reviews/`.

## What this step builds, in plain words

* **Builds:** the server stops making silent mistakes (two refreshes at once, a retrain rewriting history, a CSV import changing a locked pick, a reminder that never arrives), and every push to GitHub runs the checks by itself.
* **Replaces:** nothing you can see. Same screens.
* **Is not:** new screens, the design system rollout, or the model upgrade.

## 1. PLANNING

* Step, base, branch: PLAN.md roadmap row 1. Branch `claude/nfl-pickem-intelligence`, draft PR #1. HEAD at start `a107074` (design docs commit on top of `1e18ba4`).
* Baseline (ran): `uv run pytest` 23 passed, exit 0 (`s1-baseline-pytest-1e18ba4.log`). `uvx ruff check nflpi tests` exit 0. Postgres 17 via `docker compose up -d db`.
* Environment changed since PLAN (the plan was written in a cloud sandbox): Codex is installed and answered a probe on `gpt-6-luna` (`s1-codex-probe.log`), `jev.sh` and `OPENROUTER_API_KEY` exist, `jg` 0.8.0 and `graft` are installed. So `IMPLEMENTATION_PROVIDER: CODEX`, `CODEX_POLICY: CODEX_FIRST`. The state file's old path `/home/user/...` is replaced by the local path.
* `JEVGREP: ready` (`jg doctor` exit 0). `HEADROOM: not-routed` (desktop app routing unsupported; not a blocker).
* Context window 650000 (set). Plan usage 8% of the 5-hour limit, 2% weekly.
* Prior decisions read: PLAN.md § Owner decisions, STATE.md § User constraints, CLAUDE.md § Decisions.
* Skills: `/jevgrep` ran (`s1-planning-jg-refresh-worker.log`; pinned `nflpi/jobs.py` `cycle`/`loop`, `nflpi/api/main.py` `refresh`, `nflpi/notify/push.py` `_send`/`send_kickoff_reminders`). `/graft` for exact lookups. `harness-engineering`: surfaces already recorded in PLAN.md § Harness, unchanged. Design Gauntlet: N/A (no UI in this step). TDD: no project `tdd` skill; `/tdd` rules applied. `claude-api` skill: before the `ai/` edit (S13).

### Product Mode (T3)

1. **Problem:** the backend can double-write snapshots, rewrite a model version, overwrite a locked pick and miss a reminder, and nothing checks it on push.
2. **Why now:** week 6 kicks off Thursday 2026-10-15. Picks made on a wrong or silent backend cannot be fixed afterwards.
3. **Scope:** PLAN row 1. Cut: S7, S11, S12, S14, S17 (later steps), all `apps/web` work except CI wiring and regenerated API types.
4. **Success metric:** every gate item below green with its own numbers; upset flag on ≤ 25% of 2012–2025 games; CI green on the PR.
5. **Reversibility:** two-way, except the migration squash and schema changes. No database with data exists (the sandbox DB was lost; the local volume was created empty today), so the squash costs nothing. API changes are additive.

Assumptions: Codex available (validated). Baseline green (validated). No data DB anywhere (validated locally; sandbox per STATE). nflverse and Docker Hub reachable from this Mac (assumed; checked at the cold-start gate). GitHub Actions enabled on the repo (unknown; does not change the design, checked at LANDING).

Instrumentation shipped in this step: worker heartbeat in `/api/health`, `ingestion_runs`, CI on every push. Read by: the Settings freshness block (exists) and the PR checks.

## 2. SPECIFICATION — frozen acceptance criteria

Functional (pytest in `backend/tests/`, real Postgres):

| ID | Finding | Criterion |
|---|---|---|
| A1 | S2 | Ingest + predict run under one Postgres advisory lock in both `/api/refresh` and the worker cycle. While another connection holds it, `/api/refresh` answers `started: false` and the cycle does no ingest or predict |
| A2 | S3 | Training again for the same season with different params inserts a new `ModelVersion`; the earlier row is unchanged. The next prediction refresh writes a new snapshot under the new version |
| A3 | S4 | CSV import for a game past kickoff never changes an existing pick; it inserts only when no pick exists |
| A4 | S9 | The recommendation for a game is its last snapshot before kickoff, even when later snapshots exist |
| A5 | S5, B2 | A reminder is recorded as sent only after at least one successful push. A failed send (HTTP error or network error) is retried on the next tick until kickoff. Zero subscriptions leaves it unsent. `webpush` gets `timeout=10`, TTL = seconds to kickoff, `Urgency: high`. HTTP 404/410 deletes the subscription; a network error does not |
| A6 | S5, B2 | Reminders run on their own tick (at most 5 minutes apart) with no network ingest, and an ingest failure cannot skip them |
| A7 | B7 | A game with no kickoff time is stored with `time_tbd` true and no invented clock time. 2026-11-01 13:00 ET → 18:00Z. A London 09:30 ET kickoff converts with the right offset. A rescheduled kickoff reminds again (reminder key includes kickoff). A postponed game gets no reminder and no pick lock from a stale time |
| A8 | B8 | An upcoming game with no projected starting QB carries a "QB not yet projected" flag in the API |
| A9 | S15 | Current week = the week of the next upcoming kickoff. An old unfinished (cancelled) game does not pin it |
| A10 | B1 | The worker writes a heartbeat every tick. `/api/health` (still public, still HTTP 200) reports `degraded` when the heartbeat is missing or stale and `ok` when fresh |
| A11 | S13 | The AI daily cap counts attempts, including failed ones. `max_tokens` is at least 16000 |
| A12 | S9, S16 | On an empty database `alembic upgrade head` succeeds and `alembic check` reports no drift. There is one initial migration |
| A13 | S8 | HTML, `sw.js` and the manifest are served `Cache-Control: no-cache`; `/_next/static/*` is `immutable` |
| A14 | C1 | Upset watch fires only when the stats model picks the market underdog or differs from the market by 10 points or more |

Signals (walk-forward backtest, real data, numbers recorded):

| ID | Criterion |
|---|---|
| G1 (C1) | Upset flag on ≤ 25% of 2012–2025 games; flagged underdogs' win rate reported |
| G2 (C2) | Accuracy falls from low → moderate → high uncertainty. If not, regrade until it does |

Operational (commands, each with its log):

| ID | Finding | Criterion |
|---|---|---|
| O1 | S1 | `docker build .` succeeds. No `apps/mobile`, expo or react-native in Dockerfile, .dockerignore, package.json, package-lock.json |
| O2 | S6 | Compose publishes the app on `127.0.0.1:8000`; uvicorn runs with `--proxy-headers --forwarded-allow-ips="*"` |
| O3 | S16 | The worker command does not run alembic |
| O4 | S18 | No mobile leftovers in CLAUDE.md, .env.example, CORS default, schema/client comments |
| O5 | S10 | One GitHub Actions workflow: pytest on Postgres, ruff, typecheck, `gen:api` drift, `docker build`. Green on the PR |
| O6 | — | Cold start: empty DB → `alembic upgrade head` → `jobs bootstrap` → live predictions exist |
| O7 | B1 | With the worker stopped, `/api/health` reports `degraded` on a running stack |

User-facing layer: `npm run gen:api` leaves no drift, `npm run typecheck` and `npm run web:build` pass, so the web app still compiles against the changed contract.

Gate command: `cd backend && uv run pytest && uvx ruff check nflpi tests && uv run alembic check`, plus O1–O7 and G1–G2.

### Red evidence (SPECIFICATION done)

* Tests: `backend/tests/test_hardening.py`, written by a fresh Opus spec author (not the builder), one extra A7 case added by the coordinator. `uv run pytest -q` → **22 failed, 24 passed**, exit 1 (`s1-spec-red-pytest-final.log`). Each failure is a missing behavior or a missing new name, checked per test. `ruff` clean.
* A4 cannot be red: `views.summaries` already picks the last snapshot before kickoff. The test stands as a regression guard. The DST and London conversions in A7 also already work; they are pinned in the same test as the TBD row.
* A7 clarified before any production code: a game with `time_tbd` is stored at the start of its game day in US Eastern (no made-up clock time), and it is **not locked and not reminded** until it has a real time.
* New contract names the builder must use: `nflpi.db.REFRESH_LOCK_KEY` (single-bigint `pg_try_advisory_lock`), `nflpi.jobs.tick(session, now)`, `jobs.TICK_SECONDS` (≤ 300), `jobs.HEARTBEAT_STALE_SECONDS`, `Game.time_tbd`, `Game.status == "postponed"` survives re-ingest, `GameSummary.qb_not_projected`.
* Not pinned by tests (builder follows the criterion's words): how a game becomes postponed (nflverse has no status column), and the reminder's stop at kickoff (already holds).
* Rungs. `JEV: model/effort` → WO-A luna 0.43 / medium 0.87; WO-B sol 0.97 / high 0.53; WO-C sol 0.97 / high 0.89; WO-D sol 0.58 / medium 0.65. Unsure picks went to the advisor: `ADVISOR: sonnet` → A luna, B high, D sol high. `EFFORT:` coordinator high for PLANNING/SPECIFICATION.

## 3. IMPLEMENTATION

Provider: Codex (`CODEX_POLICY: CODEX_FIRST`). Work orders live in the logs folder (`s1-wo-*.md`), each with its Codex log and last message. Codex's sandbox cannot reach Postgres or PyPI by default, so from work order B on it runs with `sandbox_workspace_write.network_access=true`; the coordinator still reruns every proof.

| WO | Scope | Rung | Commit | Proof rerun by the coordinator |
|---|---|---|---|---|
| A | S1, S6, S8 (A13), S10, S16 (A12), S18 | gpt-6-luna medium, try 1 | `4fe9701` | `npm ci` exit 0 (147 packages) · `alembic upgrade head` + `alembic check` exit 0, "No new upgrade operations detected" · pytest with CI's `DATABASE_URL`: 20 failed, 26 passed (A12 and A13 now green; the 20 belong to B, C, D) · ruff exit 0 · `npm run gen:api` no drift · `npm run typecheck` exit 0 · `docker build .` exit 0, image 796MB · logs `s1-woa-*.log` |
| B | A1, A2, A3, A7, A8, A9 (A4 guard) | gpt-6-sol high, try 1 | `b582630` | pytest 10 failed, 36 passed (the 10 belong to C and D) · ruff exit 0 · `npm run gen:api` regenerated (new `qb_not_projected`, `postponed`) · `npm run typecheck` exit 0 · full diff read by the coordinator · logs `s1-wob-*.log` |
| A, correction | A12 again | gpt-6-luna high, try 2 of 2 | `b08d179` | explicit migration, 14 `op.create_table`, no `create_all` · scratch DB: `alembic upgrade head` exit 0 (14 tables + alembic_version), `alembic check` exit 0 "No new upgrade operations detected", `alembic downgrade base` exit 0 (only alembic_version left) · pytest 10 failed, 36 passed · ruff incl. migrations exit 0 · logs `s1-woa2-*.log`. Note: the coordinator's first two runs of these three alembic commands failed on its own shell quoting (no scratch DB was created) and the commit was made before the third, correct run; that run was on the unchanged committed files and passed. |

WO-A defect found while reviewing WO-B: the squashed migration called `Base.metadata.create_all`, so it tracked the live models and `alembic check` could never fail. The coordinator had not opened that file in the WO-A review (coordinator miss). A12's test now also requires explicit `op.create_table` and no `create_all`/`metadata` (red, committed), and Codex got a narrow correction (`s1-wo-a2.md`). `CLIMBS:` none; effort raised luna medium → high for try 2 (try rule).

Carried observation (unmapped, not a gate item): `current_week` now follows the next kickoff, as the plan asked. During the last game of a week (Monday night) the default week therefore moves to the next week once that game kicks off. Owner question for step 2, where the Week board is verified.

WO-A review note: Codex removed `EXPOSE 8000` from the Dockerfile because the coordinator's own grep (`expo`, case-insensitive) matched it. The gate was wrong, not the line: restored, and O1's grep is now `apps/mobile|react-native|"expo|expo-`.

## 4. CLEANUP

## 5. VERIFICATION

## 6. LANDING
