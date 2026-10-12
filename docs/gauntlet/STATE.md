# STATE — NFL Pick'em Intelligence gauntlet

> Location note: this state file lives in the repo and is committed at every checkpoint. Since 2026-10-11 the work runs on the owner's Mac at `/Users/emmanueladams/Projects/NFL-Pickem-App` (the plan was written in a cloud sandbox). Logs: `~/.claude/plans/nfl-pickem-intelligence-logs/`.

## STATUS

* **Goal:** one private app (desktop web + iPhone PWA) for weekly NFL Pick'em: evidence-based picks that match/beat the market, honest uncertainty, alerts, accuracy tracking. See [PLAN.md](PLAN.md).
* **Overall step:** **step 1 of 8 — Safe backend + CI + first landing**, in progress (ONE_SHOT session started 2026-10-11). Step log: `docs/gauntlet/logs/step-1.md`.
* **DONE THIS STEP:** `223d169` red tests; `4fe9701` WO-A; `b582630` WO-B; `b08d179` explicit migration; `1794a56` WO-C; `c1ba844` WO-D; `68bb90c` WO-E (review fixes + cleanup). PLANNING, SPECIFICATION, IMPLEMENTATION, CLEANUP done. Coordinator validation green on `68bb90c`: 47 tests passed twice, ruff, alembic check, backtest, gen:api, typecheck, web build; live checks O2 O3 O4 O6 O7 pass. Evidence copied into `docs/gauntlet/logs/step-1-evidence/`.
* **RESUMING AT:** LANDING for step 1, last mile. CI was green on the first push (backend, web, docker). The owner's current-week decision is built and committed locally (48 tests pass, ruff clean) and a fresh critic is reviewing that one commit. NEXT: on critic PASS, `git push`, confirm CI green again (`gh pr checks 1`), then mark step 1 DONE, write the step 2 ONE_SHOT handoff into `## 0`, republish the progress page in place. On critic FAIL: fix through the build ladder, new critic. Step 2 picks up the first critic's A7 follow-ups (expose `time_tbd` in the API and UI; skip TBD/postponed in weather ingest and backfill).
* **OWNER DECISION 2026-10-11 (in chat):** "once the Monday night football game ends jump to the next week; each week is Thursday-Monday." So the current week stays on a week until its last game is FINAL, then moves to the next. Today's code (`engine.current_week`) moves when the last game KICKS OFF: fix it. Rule to build: if a game has kicked off, is not final, not postponed, not time_tbd, and kicked off within the last 12 hours, the current week is that game's week; otherwise the week of the next upcoming kickoff; an old never-scored game must still not pin the week (A9). Reversibility: two-way. Revisit trigger: owner asks. STATUS: built and committed 2026-10-11 (red test first, Codex work order F).
* **OWNER REQUEST 2026-10-11:** finish the remaining steps in the cloud. The cloud sandbox has no Codex, Jev, jg or Docker: there `IMPLEMENTATION_PROVIDER: CLAUDE (limit hit: Codex not installed)`, Sonnet/Opus subagents build, the coordinator verifies. Gates that need the owner's Mac, iPhone or keys (step 3 deploy and install, step 5 real alert, step 6 go-live) stay `PENDING` with a checklist for him; never mark them PASS from the cloud. New UI work follows `design.md` and `PRODUCT.md` at the repo root (Design Gauntlet applies from step 2).
* **STRIKES:** none. **CONTINUATIONS:** 0.
* **JEVGREP:** ready. **HEADROOM:** not-routed (desktop app).
* **Phase:** ONE_SHOT, checkpoint VERIFICATION.
* **Done:** backend (data pipeline, model, backtest, API, AI layer, Web Push) committed locally, unreviewed; plan; structure review (18 findings); blindspot review (12 findings); progress page.
* **Pre-gauntlet web build:** finished. Coordinator re-ran `tsc` + `next build` (pass) and inspected screens; findings C1–C5 in PLAN.md. It is input to steps 2 and 4, where it gets a frozen gate and a fresh critic. Not verified until then.
* **Container restart (2026-10-11):** code and commits survived; the dev API server and the local Docker daemon/Postgres container were lost. Step 1 restarts them (`dockerd &`, then `docker compose up -d db` or a fresh `postgres:17-alpine` container, `alembic upgrade head`, `jobs bootstrap`).
* **Repo:** `/Users/emmanueladams/Projects/NFL-Pickem-App`, branch `claude/nfl-pickem-intelligence`, base `origin/main` = `83a9ae4`. Pushed 2026-10-11 after a container restart (durability, owner-approved). **Draft PR #1**: https://github.com/emmanuelmadams4-lgtm/NFL-Pickem-App/pull/1 (watched by this session). No CI yet (step 1 adds it).
* **Provider ledger:** `CODEX_AVAILABLE: yes` (codex-cli 0.156.1, `gpt-6-luna` probe OK 2026-10-11) → `IMPLEMENTATION_PROVIDER: CODEX`. `CODEX_POLICY: CODEX_FIRST`. Jev: available. `CLIMBS: none`. Fable / gpt-6-astra: never without the owner's yes in chat.
* **Progress page:** https://claude.ai/artifact/6U5zCcvZijcXVMuH6Hbnvd, source `docs/gauntlet/progress.html`. Republish in place only.
* **Review reports:** `~/.claude/plans/nfl-pickem-intelligence-reviews/` and summaries in `docs/gauntlet/STRUCTURE_REVIEW.md`, PLAN.md § Blindspot review.
* **Waiting on owner:** ESPN iPhone screenshots (scores list + a game's Matchup Predictor), needed by steps 2 and 4 for the visual verdict only.

## User constraints (carry every handoff)

* Lean: smallest thing that truly works; no over-engineering; no extra tests beyond the gate.
* Never fake data, progress or results. Done = ran and verified with proof.
* Picks lock at kickoff; predictions insert-only; no invented values (CLAUDE.md rules).
* API keys and the VAPID private key server-side only; never commit `.env`.
* Consent: push the feature branch + update the draft PR after a step verifies = **yes (2026-10-11)**. Merge to `main`, deploy, real paid AI calls, key creation = ask first.
* Phone app = PWA only (no Expo, no Android build).
* Report in plain 4th-grade words; results first.

## Owner decisions

See PLAN.md § Owner decisions (each has reversibility + revisit trigger).

## 0. Next handoff

```text
GAUNTLET_MODE: DIRECT_COORDINATOR
GAUNTLET_PHASE: ONE_SHOT
STATE FILE: /Users/emmanueladams/Projects/NFL-Pickem-App/docs/gauntlet/STATE.md

This is a Gauntlet Loop handoff for a fresh session. Before doing substantive work, load/re-read the
gauntlet-loop skill, then read the STATE FILE (STATUS, "## 0. Next handoff", user constraints, owner
decisions). The mode and phase markers are authoritative. If the STATE FILE disagrees with this
handoff, stop and report the mismatch before acting. Do not generate another generic Gauntlet prompt.
Do not restart completed phases. Do not rely on prior conversation context. Before emitting the next
handoff, update the STATE FILE's STATUS and "## 0. Next handoff".

OVERALL STEP: step 1 of 8 — Safe backend + CI + first landing (T3)
GOAL: the backend is safe to rely on this season, and CI proves it on every push.
SCOPE + FROZEN GATE: docs/gauntlet/PLAN.md, roadmap row 1 (findings S1–S6, S8–S10, S13, S15, S16, S18,
  B1, B2, B7, B8-QB-flag; details in docs/gauntlet/STRUCTURE_REVIEW.md and PLAN.md § Blindspot review).
BASELINE: branch claude/nfl-pickem-intelligence (draft PR #1); backend tests 23/23 green at dbad5f9.
  Docker daemon is down after a container restart: start `dockerd`, then a postgres:17-alpine
  container `nflpi-db` (user/pass/db nflpi, port 5432); `cd backend && uv run pytest`.
CHECKPOINTS: PLANNING → SPECIFICATION (freeze criteria, first failing test) → IMPLEMENTATION (one
  red→green slice at a time, minimum diff) → CLEANUP (scope-locked refactor of touched code) →
  VERIFICATION (fresh Opus subagent critic re-runs the gate on the committed HEAD) → LANDING (push
  branch, open/update the draft PR, CI green). Record each in docs/gauntlet/logs/step-1.md.
DONE WHEN: every gate item in PLAN row 1 is green with its own numbers, critic PASS, pushed, CI green.
STOP WHEN: three straight failures of the same command (escalate), or a one-way door needs the owner.
OPEN OWNER QUESTIONS: none for step 1.
IMPLEMENTATION_PROVIDER: CLAUDE (limit hit: Codex not installed)
CODEX_POLICY: CODEX_FIRST
BUILD_RUNG: opus (try 1 of 2)   — JEV: unavailable; coordinator picked opus (multi-file, concurrency, migrations)
CLIMBS: none
STRIKES: none
PROGRESS PAGE: https://claude.ai/artifact/6U5zCcvZijcXVMuH6Hbnvd (source docs/gauntlet/progress.html)
REQUIRED SKILLS: /graft, /tdd, /ponytail, /refactor and harness-engineering are not installed here —
  apply their behavioral rules and say so in the step log. claude-api skill before touching ai/.
CONSTRAINTS: see STATE FILE § User constraints. Do not touch apps/web in this step except CI wiring.
```
