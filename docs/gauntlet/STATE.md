# STATE — NFL Pick'em Intelligence gauntlet

> Location note: this state file lives in the repo and is committed at every checkpoint. Since 2026-10-11 the work runs on the owner's Mac at `/Users/emmanueladams/Projects/NFL-Pickem-App` (the plan was written in a cloud sandbox). Logs: `~/.claude/plans/nfl-pickem-intelligence-logs/`.

## STATUS

* **Goal:** one private app (desktop web + iPhone PWA) for weekly NFL Pick'em: evidence-based picks that match/beat the market, honest uncertainty, alerts, accuracy tracking, a model that gets better over time (D18). See [PLAN.md](PLAN.md) and the owner's decisions D1–D41 in [OWNER_DECISIONS_2026-10-12.md](OWNER_DECISIONS_2026-10-12.md).
* **Overall step:** **step 3 of 14 DONE** (2026-10-12, cloud session; restyle to reference 06, D39–D41). Objective critic PASS and design critic PASS on round 4 (`logs/step-3.md` § 5); CI 8/8 green on `3cd9964`. Roadmap is 14 steps (PLAN.md).
* **Next:** **step 4, Pick sheet** (D1–D3, D7, D10–D14; PLAN.md row 4). PLANNING also rewrites design.md §§ 5/7/8 (still describe the old blue system). Polish carried to step 6 is listed in `logs/step-3.md` § 5 rounds 3–4.
* **Phase:** between steps. Next session: `DIRECT_COORDINATOR / ONE_SHOT`.
* **STRIKES:** none. **CONTINUATIONS:** 0.
* **Repo:** branch `claude/nfl-pickem-intelligence`, draft PR #1, base `main` `83a9ae4`. Two Claude sessions write to this branch (cloud: code; owner's Mac: decisions and research, docs only); merge, never rebase or force.
* **Provider ledger:** cloud sandbox: Codex not installed → `IMPLEMENTATION_PROVIDER: CLAUDE (limit hit)`; Jev unavailable (no key here). On the owner's Mac: Codex and Jev available. Fable / gpt-6-astra: never without the owner's yes in chat.
* **21st.dev:** connected; search and theme CSS free; component code 2 retrievals a day on the free tier (`docs/design/COMPONENT_SOURCES.md`).
* **Progress page:** https://claude.ai/artifact/6U5zCcvZijcXVMuH6Hbnvd, source `docs/gauntlet/progress.html`. Republish in place only.
* **Waiting on owner:** nothing blocking. Open items in the decisions file (line freshness measured in week 6; Claude sign-in terms read as allowed with OpenRouter fallback, D32/Q10).

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
STATE FILE: docs/gauntlet/STATE.md (repo root of the checkout; on the owner's Mac /Users/emmanueladams/Projects/NFL-Pickem-App/docs/gauntlet/STATE.md)

This is a Gauntlet Loop handoff for a fresh session. Load/re-read the gauntlet-loop skill, then read the
STATE FILE, docs/gauntlet/PLAN.md (row 4), docs/gauntlet/OWNER_DECISIONS_2026-10-12.md and
docs/gauntlet/logs/step-3.md (§ 5 rounds 3-4, § 6).
If they disagree with this handoff, stop and report. Do not restart steps 1-3.

OVERALL STEP: step 4 of 14, Pick sheet (D1-D3, D7, D10-D14).
GOAL: labels (coin flip / tough matchup / easy pick, cuts from the backtest with hit rates), points 1-N with
  re-rank and swap, auto pick at kickoff marked `auto`, copy-to-Yahoo sheet, weekly rank entry, scorecard of
  the owner's changes vs the app's sheet. Built in the step 3 look (design.md § 0). PLANNING first rewrites
  design.md §§ 5/7/8 (still the old blue system).
GATE: pytest for labels/points/auto picks · backtest table for the label cuts · e2e for re-rank, swap, lock,
  copy sheet · existing W/E/S/R/F/G checks stay green · axe 0 serious/critical · fresh objective + design critics.
BASELINE: branch claude/nfl-pickem-intelligence at the step 3 landing commit (logs/step-3.md § 6).
  Gate commands: cd backend && uv run pytest -q && uvx ruff check nflpi tests migrations;
  npm run gen:api (no drift) && npm run typecheck && npm run web:build && npm run e2e (from the repo root;
  e2e serves the built export, so rebuild first).
DONE WHEN: gate green with its own numbers, objective critic PASS, design critic PASS, pushed, CI green.
STOP WHEN: three straight failures of the same command, or a one-way door needs the owner.
OPEN OWNER QUESTIONS: none blocking.
IMPLEMENTATION_PROVIDER: CODEX on the owner's Mac; in a cloud sandbox CLAUDE (limit hit: Codex not installed)
CODEX_POLICY: CODEX_FIRST
BUILD_RUNG: decide per work order (Jev on the Mac, coordinator in the cloud); try 1 of 2
CLIMBS: none
STRIKES: none
PROGRESS PAGE: https://claude.ai/artifact/6U5zCcvZijcXVMuH6Hbnvd (source docs/gauntlet/progress.html); republish in place
CONSTRAINTS: STATE FILE § User constraints. 21st.dev: adapt, never paste whole; 2 code retrievals a day.
```
