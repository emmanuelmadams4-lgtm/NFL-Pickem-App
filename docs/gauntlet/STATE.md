# STATE — NFL Pick'em Intelligence gauntlet

> Location note: this state file lives in the repo and is committed at every checkpoint. Since 2026-10-11 the work runs on the owner's Mac at `/Users/emmanueladams/Projects/NFL-Pickem-App` (the plan was written in a cloud sandbox). Logs: `~/.claude/plans/nfl-pickem-intelligence-logs/`.

## STATUS

* **Goal:** one private app (desktop web + iPhone PWA) for weekly NFL Pick'em: evidence-based picks that match/beat the market, honest uncertainty, alerts, accuracy tracking. See [PLAN.md](PLAN.md).
* **Overall step:** **step 1 of 8 — Safe backend + CI + first landing**, in progress (ONE_SHOT session started 2026-10-11). Step log: `docs/gauntlet/logs/step-1.md`.
* **DONE THIS STEP:** `a107074` design docs; `3c8c499` PLANNING + frozen criteria; `223d169` red tests; `4fe9701` WO-A; `b582630` WO-B; `b08d179` explicit migration (A12 green). Suite: 36 passed / 10 red (C, D).
* **RESUMING AT:** IMPLEMENTATION: Codex WO-C is running (`s1-wo-c.md`, gpt-6-sol high, try 1 of 2; last message `s1-wo-c-last.md`). When it ends: read the diff, rerun pytest/ruff/alembic check (scratch DB via `docker exec nfl-pickem-app-db-1 psql`)/gen:api/typecheck, commit. Then WO-D (`s1-wo-d.md`, sol high). Launch Codex with `-c sandbox_workspace_write.network_access=true`. Never re-dispatch a running Codex job.
* **STRIKES:** none. **CONTINUATIONS:** 0.
* **JEVGREP:** ready. **HEADROOM:** not-routed (desktop app).
* **Phase:** ONE_SHOT, checkpoint SPECIFICATION.
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
