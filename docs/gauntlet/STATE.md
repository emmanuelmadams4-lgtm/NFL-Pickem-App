# STATE — NFL Pick'em Intelligence gauntlet

> Location note: this state file lives in the repo and is committed at every checkpoint. Since 2026-10-11 the work runs on the owner's Mac at `/Users/emmanueladams/Projects/NFL-Pickem-App` (the plan was written in a cloud sandbox). Logs: `~/.claude/plans/nfl-pickem-intelligence-logs/`.

## STATUS

* **Goal:** one private app (desktop web + iPhone PWA) for weekly NFL Pick'em: evidence-based picks that match/beat the market, honest uncertainty, alerts, accuracy tracking, a model that gets better over time (D18). See [PLAN.md](PLAN.md) and the owner's decisions D1–D41 in [OWNER_DECISIONS_2026-10-12.md](OWNER_DECISIONS_2026-10-12.md).
* **Overall step:** **step 2 of 8 DONE** (2026-10-12, cloud session; objective critic PASS twice, CI on the pushed head recorded in `logs/step-2.md` § 6). The roadmap is re-planned at the next PLANNING to fold D1–D41 (new steps: restyle, pick sheet, star players, trends, passkey; see the decisions file's roadmap section), so "of 8" changes there.
* **Next:** the **restyle step** (owner D39 look, D40 layout, D41 logo) with frozen carry-overs R1–R7 from step 2 (`logs/step-2.md` § 5, round 3), then the pick sheet (D15). Owner's chosen build order: restyle first so the pick sheet is built once in the new look.
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
STATE FILE, docs/gauntlet/OWNER_DECISIONS_2026-10-12.md and docs/gauntlet/logs/step-2.md (§ 5 round 3, § 6).
If they disagree with this handoff, stop and report. Do not restart steps 1-2.

OVERALL STEP: restyle step (inserted by owner decisions D39-D41), after step 2 of 8. PLANNING first folds
  D1-D41 into PLAN.md (new roadmap, renumbered), then rewrites design.md to D39/D40 before any code.
GOAL: the app looks and is laid out like reference 06 (docs/design/references/06-concept-dark-lime.jpg) with
  the app's own information; the owner's lime P is the app icon (docs/design/brand/app-icon/).
GATE: R1-R7 (logs/step-2.md § 5 round 3) + existing E1-E14 and W1-W5 stay green + new browser checks for the
  card layout, tab bar and icons + axe 0 serious/critical + fresh design critic, blind side by side with
  reference 06 at 393x852 and 1440x900 (the image is in the repo now).
BASELINE: branch claude/nfl-pickem-intelligence at the step 2 landing commit (logs/step-2.md § 6).
  Gate commands: cd backend && uv run pytest -q && uvx ruff check nflpi tests migrations;
  npm run gen:api (no drift) && npm run typecheck && npm run e2e.
DONE WHEN: gate green with its own numbers, objective critic PASS, design critic PASS, pushed, CI green.
STOP WHEN: three straight failures of the same command, or a one-way door needs the owner.
OPEN OWNER QUESTIONS: none blocking (team logos in dark mode use ESPN's 500-dark variant with fallback).
IMPLEMENTATION_PROVIDER: CODEX on the owner's Mac; in a cloud sandbox CLAUDE (limit hit: Codex not installed)
CODEX_POLICY: CODEX_FIRST
BUILD_RUNG: decide per work order (Jev on the Mac, coordinator in the cloud); try 1 of 2
CLIMBS: none
STRIKES: none
PROGRESS PAGE: https://claude.ai/artifact/6U5zCcvZijcXVMuH6Hbnvd (source docs/gauntlet/progress.html); republish in place
CONSTRAINTS: STATE FILE § User constraints. 21st.dev: adapt, never paste whole; 2 code retrievals a day.
```
