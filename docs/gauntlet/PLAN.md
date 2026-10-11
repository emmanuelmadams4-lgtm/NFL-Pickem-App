# Gauntlet plan — NFL Pick'em Intelligence

Plan for the gauntlet-loop. Planned on Opus, 2026-10-11. Steps are numbered; progress is always `step N of 8`.

## Goal and done-when

Emmanuel uses one private app every week of the 2026 season, on desktop and on his iPhone (Home Screen PWA). It gives an evidence-based pick for every game that matches or beats the betting market. It shows how sure it is and why, alerts him to flips, QB news and unpicked kickoffs, and tracks his accuracy against the model, the market and the league leader (about 69%).

Done when: steps 1–7 are landed. Step 8 (model upgrade) ships only if it beats the current model in the walk-forward test.

Deadline pressure: week 6 starts Thursday 2026-10-15 (SEA @ DEN). Steps are ordered so a usable, deployed app exists as early as possible; the backend refactor waits.

## Product Mode pre-flight (whole goal)

1. **Problem**: Emmanuel picks every NFL game weekly by gut and memory. He has no quick, honest view of who should win, why, or how sure to be.
2. **Why now**: the 2026 season is in week 5. Each week costs 14–16 picks, and picks lock at kickoff.
3. **Scope**: one backend plus one web app that is also the iPhone PWA. **Cut**: native apps, Android build, Yahoo auto-submit, multi-user, paid data feeds. The EPA model is optional (step 8).
4. **Success metric**: Emmanuel's season pick accuracy, shown on Results, against the league leader (69%) and the market (66.6% long-run). Secondary: model blend accuracy against the market, with a 95% interval.
5. **Reversibility**: mostly two-way (app code). One-way: DB schema and migrations, and the API contract the web app depends on (single user, so low cost).

## The bar

| Part | Bar | How it's judged |
|---|---|---|
| Model (objective) | Betting market closing line, walk-forward 2012–2025: **66.6% accuracy, log loss 0.609** | `jobs train` backtest. The recommendation model must stay within the market's 95% interval. A new model replaces it only if the paired-bootstrap log-loss gain excludes 0 |
| Look and use (subjective) | **ESPN iPhone app**: NFL scores list and a game's Matchup Predictor. Owner sends the screenshots | Fresh critic, blind side-by-side at 393×852, names a winner and the largest gap. Ours must win on "can I make this pick fast and with confidence" |
| PWA and flows (objective) | Executable | Playwright e2e on the production export, axe-core 0 serious/critical, valid manifest, service worker controls the page, offline reload renders with banner |
| Operations (objective) | Executable | `/api/health` ok, ingestion runs logged, freshness visible, cold start from an empty DB to predictions |

**Waiting on owner**: ESPN screenshots (2–3 iPhone screens). Visual comparisons in steps 2–3 are `PENDING` until they arrive. Everything else proceeds.

## Owner decisions (don't re-ask)

| Date | Decision | Reversibility | Revisit trigger |
|---|---|---|---|
| 2026-10-11 | Phone app = PWA of the web app. No Expo/native, no App Store, no Android build | two-way | A must-have feature can't work in an iOS Home Screen web app |
| 2026-10-11 | Push the feature branch and open a draft PR after verification | two-way | none |
| 2026-10-11 | Design bar = ESPN iPhone app screens | two-way | Owner names a better reference |
| 2026-10-11 | Recommendation = stats + market blend (ties market; stats-only is 2.1 pts worse). JEV: unavailable, decided on backtest evidence | two-way | Step 8 model beats it |
| 2026-10-11 | Claude model for reports `claude-sonnet-5-5` (cheapest capable) | two-way | Reports fail validation often, or owner asks |

## Harness (harness-engineering skill not installed here; behavioral equivalent)

* **Locked**: data-integrity rules in CLAUDE.md (insert-only predictions, nothing invented, picks lock at kickoff), the walk-forward backtest protocol, consent gates, server-only secrets, each step's frozen gate.
* **Editable**: `backend/nflpi/**`, `backend/tests/**`, `apps/web/**`, `packages/shared/src/{client,format}.ts`, docs. `packages/shared/src/api-types.ts` changes only via `npm run gen:api`.
* **Append-only**: `predictions`, `ingestion_runs`, `notifications`, `ai_reports`, git history on the branch, `docs/gauntlet/logs/`.
* **Human-controlled**: push, PR, merge, deploy, API keys, VAPID subject, Tailscale, the ESPN screenshots, on-device iPhone checks, real AI calls that cost money.
* **Feedback**: pytest, ruff, tsc, next build, Playwright e2e + offline test, backtest report, fresh critic, CI on the PR.
* **Recovery**: a failed ingestion keeps old data and is logged; the worker retries in 15 min; alembic up/down; a commit per checkpoint; a CONTINUE_COORDINATOR handoff when context runs short.

## Environment facts (this cloud sandbox)

* Codex: **not installed**, so Codex's limit is hit. Claude builds on the matching rung: Sonnet (rung 1), Opus (rung 2). Fable only with the owner's yes.
* Jev: **unavailable** (no `~/.claude/bin/jev.sh`, no `OPENROUTER_API_KEY`). Routing is decided by the coordinator and recorded as `JEV: unavailable`. `llm-council` is used only for owner-decision forks and three-strike escalations.
* `/graft`, `/tdd`, `/ponytail`, `/refactor`, `harness-engineering`: **not installed**. Behavioral equivalents are applied and named in each step log.
* ECC roster agents (`ecc:*`): **not installed**. Nearest equivalents: `Plan` (Opus) for architect/planner/critic, `Explore` for code-explorer, `general-purpose` for builders.
* No outside websites reachable except GitHub/npm/PyPI. Docker Hub is rate-limited here (image builds may be `PENDING` to the owner's machine). No Apple device: on-device checks are `PENDING` for the owner.

## Roadmap

Order decision (2026-10-11): blindspot review B-order adopted. Usable deployed app first, refactor later. JEV: unavailable; the coordinator decided on the Thursday deadline (two-way door; revisit if step 1 slips past Wednesday).

| # | Step | Tier | Scope (finding IDs: S = structure review, B = blindspot review) | Gate (must be green) | Likely rung | Waits on |
|---|---|---|---|---|---|---|
| 1 | **Safe backend + CI + first landing** | T3 | S1 Docker/lockfile · S2 advisory lock · S3 insert-only model versions · S4 CSV pick lock · S5+B2 reliable reminders (mark sent only after a successful send, retry until kickoff, TTL = time to kickoff, Urgency high, 5-min reminder tick with no network ingest) · S6 localhost bind + proxy headers · S8 Cache-Control · S13 AI cap + max_tokens · S15 current week by next kickoff · S16 squash migrations (no DB exists outside the sandbox, confirmed) + worker skips alembic · S18 mobile leftovers · B1 worker heartbeat in `/api/health` · B7 `time_tbd` (no invented 13:00), reminder key includes kickoff, postponed status · B8 "QB not yet projected" flag · S9 migration test + focused tests · S10 GitHub Actions CI | `uv run pytest` green incl. new tests (DST 2026-11-01 13:00 ET → 18:00Z, London 09:30 ET, TBD time, rescheduled kickoff, postponed game, failed send retried, zero subscriptions stays unsent, CSV lock, retrain → new version, last-snapshot-before-kickoff, 410 + network error) · `uvx ruff check` · `alembic upgrade head` + `alembic check` on an empty DB · cold-start bootstrap to live predictions · stopped worker → health degraded · CI green on the PR (pytest, ruff, typecheck, `gen:api` drift, `docker build`) | Opus (Codex limit hit) | — |
| 2 | **Desktop web app** | T2 | Verify and fix the pre-built `apps/web` (sign-in, week board, one-tap picks, matchup, results, backtest, settings) · B3 lock from `kickoff_utc` + a ticking clock, server clock override for tests · B9 Results headline = live predictions only, backfill shown separately · ask owner: Yahoo tie rule, add "submitted in Yahoo" mark | Committed Playwright e2e on the production export served by FastAPI, with a fixed test clock (sign in, sort, pick and clear, lock past kickoff, matchup sections, results, CSV round trip) · `tsc` · `next build` · axe 0 serious/critical · fresh critic, blind side-by-side vs ESPN | Sonnet | ESPN screenshots (visual verdict only) |
| 3 | **Deploy and operate** | T2 | Docker image, compose from a clean clone, Tailscale Serve HTTPS runbook (Funnel off, host never sleeps) · S11 + B10 backups with pipefail, off-host copy, `.env`/VAPID key stored safely, restore steps · token rotation runbook (B5) · IPHONE_PWA.md: install first, then sign in inside the app (B5) · then the **owner's first iPhone install check** | Clean clone → `docker compose up -d --build` → health ok (worker heartbeat fresh) → bootstrap → web loads · B12 behind a TLS-terminating proxy: SW registers, manifest scope right, no `Location: http://` · backup → restore → pick and prediction counts match | Sonnet | Docker Hub here (else CI `docker build` + owner's machine); owner install check `PENDING` |
| 4 | **iPhone PWA** | T2 | Phone layouts, manifest + icons, S17 one offline layer (SW = shell + static), persisted query cache, offline picks queue · B4 "can't reach server — Tailscale on?" (reachability by last successful call, 5 s timeout) · B5 `navigator.storage.persist()` shown in Settings · B11 build ID in `sw.js`, `reg.update()` on `visibilitychange`, reload toast · install hint | Playwright at 393×852: manifest valid; SW controls the page; offline reload shows data + banner; `/api/**` aborted and delayed 30 s while online → cached data + banner within 6 s, picks stay queued; past-kickoff while offline → buttons disabled; build A → build B activates; all tabs open offline with no ChunkLoadError; emulated standalone with empty storage → sign-in card works · blind compare vs ESPN | Sonnet → Opus | ESPN screenshots; on-device check `PENDING` (owner) |
| 5 | **Alerts end to end** | T2 | Alerts + reminder settings UI, SW push display · B6 re-send the subscription on every open, resubscribe on key mismatch, `POST /api/push/test` + "Send test alert" showing the push service status · build `scripts/smoke.sh` for step 6 | pywebpush → local mock push service (valid VAPID JWT, aes128gcm body) · Chromium CDP `ServiceWorker.deliverPushMessage` shows the notification and opens the game · server row deleted → next open re-creates it | Opus | Real iPhone alert `PENDING` (owner) |
| 6 | **Owner go-live** | T1 | Owner adds keys (Anthropic, OpenRouter, VAPID), installs on the iPhone, runs `scripts/smoke.sh` | Smoke output + owner screenshots, every check PASS on the owner's server: live AI report, live Jev answer, test alert on the iPhone, live weather | Sonnet | Owner: keys, server, phone |
| 7 | **Backend layering, speed, data-timing instrumentation** | T1 | S7 import cycles and layers · S14 query shape · S12 backtest label + hindsight-QB caveat · B8 log first-seen/last-changed for line, QB and injury; show line age at the final pregame snapshot; after week 6, report median line age and blank-QB count | Same test suite green · no cross-package private imports (grep gate) · Week endpoint prediction queries ≤ 3 (query-count test) · backtest numbers unchanged · week-6 timing report written | Sonnet | Week 6 played |
| 8 | **Model upgrade (optional)** | T3 | EPA-per-play team ratings from nflverse play-by-play · B9 tuning protocol: tune on 2012–2021, confirm once on 2022–2025, log every variant tried | Paired-bootstrap log-loss gain vs the current blend on 2022–2025 excludes 0; else record it and keep the blend | Opus | — |

Every step runs as one `DIRECT_COORDINATOR / ONE_SHOT` session with the six checkpoints (PLANNING → SPECIFICATION → IMPLEMENTATION → CLEANUP → VERIFICATION → LANDING) and a fresh subagent critic before landing. Landing = commit, push the feature branch, update the draft PR, CI green (consent given 2026-10-11). Merge to `main` and any deploy still need the owner's yes.

## Structure review

See [STRUCTURE_REVIEW.md](STRUCTURE_REVIEW.md) (independent Opus architect, 2026-10-11). Findings are assigned to the steps above.

## Blindspot review

Fresh Opus architect, 2026-10-11. Twelve findings (B1–B12), all assigned above; the order was changed to its recommendation. Summary: worker liveness (B1), reminder delivery (B2), client-side lock (B3), server-unreachable state (B4), token storage on iPhone (B5), push subscription drift (B6), invented kickoff times / DST / TBD (B7), live data timing and leakage (B8), honest Results headline (B9), backups and the VAPID key (B10), service worker updates (B11), real HTTPS path test (B12).
