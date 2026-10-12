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
| C | A5, A6, A10, A11 | gpt-6-sol high, try 1; correction xhigh, try 2 of 2 | `1794a56` | pytest 1 failed, 45 passed (the 1 is A14, owned by D) · ruff exit 0 · gen:api + typecheck exit 0 · full diff read · logs `s1-woc-*.log` |
| D | A14, G1, G2 | gpt-6-sol high, try 1 | not committed | Codex's real-data report (`s1-wo-d-last.md`): headline unchanged (market 66.57%, stats 64.51%, blend 66.46%, 3649 games) · A14 green, suite 46/46 · **G1 not met**: the worded rule (underdog pick or 10-point gap) flags 30.64% (1118/3649); flagged underdogs won 36.66% · G2 met on paper (low 79.11% / moderate 63.53% / high 55.00%; untouched 2022-2025 78.25 / 65.10 / 58.74) but by the wrong means, see below |
| D, revised spec | A14, G1, G2 | gpt-6-sol high, try 1 of the revised spec | `c1ba844` | backtest rerun by the coordinator on real nflverse data (`s1-wod2-backtest.log`), numbers identical to Codex's: headline unchanged (market 66.57%, stats 64.51%, blend 66.46%, 3649 games) · **G1 met**: gap raised to 12 points (chosen on 2012-2021: 24.44%), 2022-2025 24.35%, overall **24.42%** (891/3649); flagged underdogs won 38.06% (338/888) vs 31.85% unflagged · **G2 met**: blend accuracy low 68.73% (1500) / moderate 66.93% (1019) / high 63.01% (1130); train 68.16 / 66.11 / 63.05; 2022-2025 70.07 / 68.92 / 62.91; each grade ≥ 27% of games; within probability bands accuracy does not rise from low to high in 3 of 3 bands overall (55.56→51.96, 64.50→62.40, 81.76→75.56) · pytest 46 passed · ruff exit 0 · gen:api no drift · variants log `s1-wod2-variants.txt` (80 grade variants) |

Honest limits on G2, recorded not hidden: 80 grade variants were measured on 2012-2021, so the chosen rule is the best of many; Codex also looked at 2022-2025 results for other candidates while developing, so that period is not wholly unseen; the low-versus-moderate gap (1.8 points overall) is small, the low-versus-high gap (5.7 points) is about three standard errors. The label is honest about direction, not a precise measure. QB injury listings no longer appear in the uncertainty reasons (they cannot be tested walk-forward); they still show as QB alert chips.

WO-A defect found while reviewing WO-B: the squashed migration called `Base.metadata.create_all`, so it tracked the live models and `alembic check` could never fail. The coordinator had not opened that file in the WO-A review (coordinator miss). A12's test now also requires explicit `op.create_table` and no `create_all`/`metadata` (red, committed), and Codex got a narrow correction (`s1-wo-a2.md`). `CLIMBS:` none; effort raised luna medium → high for try 2 (try rule).

WO-C review: try 1 kept an old four-argument test fake working by catching `TypeError` and reading its message inside `send_kickoff_reminders`. Rejected: the coordinator updated the fake in `tests/test_api.py` (`**kw`) and Codex deleted the fallback (try 2). The AI cap now counts attempts per UTC day in `app_settings` (`ai_attempts_<date>`); "daily" read as a UTC calendar day. `claude-api` skill was not loaded: the `ai/` change is one constant (`max_tokens` 16000, call stays non-streaming) and the live call is checked at step 6.

Carried observations from WO-C (unmapped, not gate items): the heartbeat is written by `tick`, so a refresh cycle longer than 10 minutes (first bootstrap, yearly retrain) shows `degraded` until the next tick; one `ai_attempts_<date>` row per day accumulates in `app_settings`.

WO-D review, two spec faults (the coordinator's, not the builder's, so no rung climb):
1. G1: the plan's gate (≤ 25%) and the plan's suggested rule (10-point gap) conflict on real data. `JEV: tighten the rule or relax the gate → tighten_rule (0.98)`. Revised: keep both conditions, raise the gap to the smallest whole number ≥ 10 that gives ≤ 25% on 2012-2021, report 2022-2025 untouched. A14's middle case will be re-pinned to the chosen gap by the coordinator.
2. G2: Codex graded uncertainty by how close the pick is to 50% (the coordinator's work order had offered that as an example). That passes "accuracy falls from low to high" trivially and breaks the binding rule in CLAUDE.md and PRODUCT.md that win probability and uncertainty are different things. No Jev call: a logged decision governs. Revised: the grade may use only reliability inputs (stats-vs-market disagreement, QB change, early season counted once, missing line; stale data live), never the probability's distance from 50%. Added evidence gate: within pick-probability bands, accuracy must not rise from low to high in at least two of three bands. If no such rule separates, Codex stops and reports; the question then goes to the owner.
Work order: `s1-wo-d2.md`.

Carried observation (unmapped, not a gate item): `current_week` now follows the next kickoff, as the plan asked. During the last game of a week (Monday night) the default week therefore moves to the next week once that game kicks off. Owner question for step 2, where the Week board is verified.

WO-A review note: Codex removed `EXPOSE 8000` from the Dockerfile because the coordinator's own grep (`expo`, case-insensitive) matched it. The gate was wrong, not the line: restored, and O1's grep is now `apps/mobile|react-native|"expo|expo-`.

## 4. CLEANUP

## 5. VERIFICATION

## 6. LANDING
