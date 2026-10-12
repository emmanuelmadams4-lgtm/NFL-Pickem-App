# STATE — NFL Pick'em Intelligence gauntlet

> Location note: this state file lives in the repo and is committed at every checkpoint. Since 2026-10-11 the work runs on the owner's Mac at `/Users/emmanueladams/Projects/NFL-Pickem-App` (the plan was written in a cloud sandbox). Logs: `~/.claude/plans/nfl-pickem-intelligence-logs/`.

## STATUS

* **Goal:** one private app (desktop web + iPhone PWA) for weekly NFL Pick'em: evidence-based picks that match/beat the market, honest uncertainty, alerts, accuracy tracking. See [PLAN.md](PLAN.md).
* **Overall step:** **step 1 of 8 DONE** (2026-10-11; pushed `91d7987`, CI green, critic PASS twice). Next: **step 2 of 8 — Desktop web app**. Step log: `docs/gauntlet/logs/step-1.md`.
* **Phase:** between steps. Next session: `DIRECT_COORDINATOR / ONE_SHOT`, step 2.
* **DONE THIS STEP:** n/a (step 2 not started).
* **RESUMING AT:** first, republish the progress page in place with "step 2 of 8" (it was not updated at the end of step 1). Then step 2 PLANNING.
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
STATE FILE: /Users/emmanueladams/Projects/NFL-Pickem-App/docs/gauntlet/STATE.md  (in a cloud checkout: docs/gauntlet/STATE.md at the repo root)

This is a Gauntlet Loop handoff for a fresh session. Load/re-read the gauntlet-loop skill, then read the
STATE FILE. Do not re-plan. Do not restart step 1. Execute only step 2.

OVERALL STEP: step 2 of 8 — Desktop web app (T2). Scope and frozen gate: docs/gauntlet/PLAN.md roadmap row 2
  (C3, C4, B3, B9, verify and fix the pre-built apps/web).
ALSO IN SCOPE (carried from step 1, see docs/gauntlet/logs/step-1.md):
  - expose `time_tbd` in the API contract and show "time TBD" in the UI; skip TBD/postponed games in weather
    ingest and backfill (critic finding on A7);
  - Design Gauntlet applies: PRODUCT.md and design.md at the repo root are the source of truth; land the
    `proposed` tokens (docs/design/design-tokens.json) and fix the audit findings in design.md section 15.
BASELINE: branch claude/nfl-pickem-intelligence at 91d7987 (draft PR #1, CI green). Backend: 48 tests pass,
  ruff clean. Gate commands: cd backend && uv run pytest -q && uvx ruff check nflpi tests migrations;
  npm run gen:api (no drift) && npm run typecheck && npm run web:build; plus row 2's Playwright e2e and axe.
DONE WHEN: every gate item in PLAN row 2 is green with its own numbers, design critic and fresh critic PASS,
  pushed, CI green.
STOP WHEN: three straight failures of the same command, or a one-way door needs the owner.
OPEN OWNER QUESTIONS: Yahoo tie rule; add a "submitted in Yahoo" mark?; ESPN reference screenshots (visual
  verdict stays PENDING until they arrive).
IMPLEMENTATION_PROVIDER: CODEX on the owner's Mac (Codex works there; launch with
  -c sandbox_workspace_write.network_access=true). In a cloud sandbox: CLAUDE (limit hit: Codex not installed).
CODEX_POLICY: CODEX_FIRST
BUILD_RUNG: decide per work order with Jev (Mac) or the advisor (cloud); try 1 of 2
CLIMBS: none
STRIKES: none
PROGRESS PAGE: https://claude.ai/artifact/6U5zCcvZijcXVMuH6Hbnvd (source docs/gauntlet/progress.html); republish
  in place, it still shows step 1.
CONSTRAINTS: STATE FILE § User constraints. Owner-only gates (deploy, real iPhone, keys) stay PENDING.
```
