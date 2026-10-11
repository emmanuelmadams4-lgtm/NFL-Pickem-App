# Gauntlet plan — NFL Pick'em Intelligence

Approved plan for the gauntlet-loop. Planned on Opus, 2026-10-11. Steps are numbered; progress is always `step N of 7`.

## Goal and done-when

Emmanuel uses one private app every week of the 2026 season, on desktop and on his iPhone (Home Screen PWA). It gives an evidence-based pick for every game that matches or beats the betting market. It shows how sure it is and why, alerts him to flips, QB news and unpicked kickoffs, and tracks his accuracy against the model, the market and the league leader (about 69%).

Done when: steps 1–6 are landed. Step 7 (model upgrade) ships only if it beats the current model in the walk-forward test.

## Product Mode pre-flight (whole goal)

1. **Problem**: Emmanuel picks every NFL game weekly by gut and memory. He has no quick, honest view of who should win, why, or how sure to be.
2. **Why now**: the 2026 season is in week 5. Each week costs 14–16 picks, and picks lock at kickoff.
3. **Scope**: one backend plus one web app that is also the iPhone PWA. **Cut**: native apps, Android build, Yahoo auto-submit, multi-user, paid data feeds. The EPA model is optional (step 7).
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
| 2026-10-11 | Recommendation = stats + market blend (ties market; stats-only is 2.1 pts worse). JEV: unavailable, decided on backtest evidence | two-way | Step 7 model beats it |
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

| # | Step | Tier | Gate (must be green) | Likely rung | Waits on |
|---|---|---|---|---|---|
| 1 | **Backend hardening + first landing.** Fix the architecture review's backend and deploy findings. Add CI (GitHub Actions: Postgres, pytest, ruff, web typecheck + build). Prune Expo from the lockfile. Push + draft PR | T3 | `uv run pytest` green · `uvx ruff check` clean · alembic `upgrade head` and `downgrade base` on an empty DB · cold-start `jobs bootstrap` to live predictions · CI green on the PR | Opus (Codex limit hit) | — |
| 2 | **Desktop web app.** Verify and fix the pre-built `apps/web`: token gate, week board, one-tap picks, matchup, results, backtest, settings | T2 | Committed Playwright e2e on the production export served by FastAPI (sign in, sort, pick and clear, matchup sections, results, CSV round trip) · `tsc` · `next build` · axe 0 serious · fresh critic | Sonnet | ESPN screenshots for the visual verdict |
| 3 | **iPhone PWA.** Phone layouts, manifest and icons, service worker, offline cache, offline picks queue, install hint | T2 | Playwright at 393×852: manifest valid, SW controls the page, offline reload shows data and banner, offline pick queued then synced · blind compare against ESPN screens | Sonnet → Opus | ESPN screenshots; on-device install check `PENDING` (owner) |
| 4 | **Alerts end to end.** Settings UI for alerts and reminders, SW push display, server send | T2 | pywebpush sends to a local mock push service (valid VAPID JWT and aes128gcm body) · Chromium CDP `ServiceWorker.deliverPushMessage` shows the notification and opens the game · reminder and dedupe tests | Opus | Real iPhone alert `PENDING` (owner) |
| 5 | **Deploy and operate.** Docker image, compose from a clean clone, Tailscale Serve HTTPS, backups, health and logs | T2 | Clean clone → `docker compose up -d --build` → health ok → bootstrap → web loads at :8000 → backup file written | Sonnet | Docker Hub access (else `PENDING` on owner's machine) |
| 6 | **Owner go-live.** Owner adds keys (Anthropic, OpenRouter, VAPID), installs on iPhone, and runs `scripts/smoke.sh` for a live AI report, live push and live weather | T1 | Smoke script output and owner screenshots, every check PASS on the owner's server | Sonnet | Owner: keys, server, phone |
| 7 | **Model upgrade (optional).** EPA-per-play team ratings from nflverse play-by-play as new features | T3 | Walk-forward 2012–2025: paired-bootstrap log-loss gain vs the current blend excludes 0. If not, record it and keep the blend | Opus | — |

Every step runs as one `DIRECT_COORDINATOR / ONE_SHOT` session with the six checkpoints (PLANNING → SPECIFICATION → IMPLEMENTATION → CLEANUP → VERIFICATION → LANDING) and a fresh subagent critic before landing. Landing = commit, push the feature branch, update the draft PR, CI green (consent given 2026-10-11). Merge to `main` and any deploy still need the owner's yes.

## Structure review

See [STRUCTURE_REVIEW.md](STRUCTURE_REVIEW.md) (independent Opus architect, 2026-10-11). Findings are assigned to the steps above.
