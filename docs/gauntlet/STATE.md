# STATE — NFL Pick'em Intelligence gauntlet

> Location note: this state file lives in the repo and is committed at every checkpoint. Since 2026-10-11 the work runs on the owner's Mac at `/Users/emmanueladams/Projects/NFL-Pickem-App` (the plan was written in a cloud sandbox). Logs: `~/.claude/plans/nfl-pickem-intelligence-logs/`.

## STATUS

* **Goal:** one private app (desktop web + iPhone PWA) for weekly NFL Pick'em: evidence-based picks that match/beat the market, honest uncertainty, alerts, accuracy tracking, a model that gets better over time (D18). See [PLAN.md](PLAN.md) and the owner's decisions D1–D41 in [OWNER_DECISIONS_2026-10-12.md](OWNER_DECISIONS_2026-10-12.md).
* **Overall step:** **step 5 of 14 DONE** (2026-10-12). Step 4, pick sheet, merged as PR #2 (`2b00b53`; record in `logs/step-4.md`). Step 5, deploy and operate, merged as PR #3 (`d01d0f8`; full gate D0-D8 ALL PASS on `0926d9f`, record and known limits in `logs/step-5.md`). Step 12, Trends, merged out of order as PR #4 (`00b952b`, 2026-10-12; record and carried items in `logs/step-12.md`). Step 6, iPhone PWA, merged as PR #5 (`d514885`, 2026-10-13 00:10 UTC; head `cede804`, four fresh-critic rounds, record and follow-ups in `logs/step-6.md`). **7 of 14 steps landed** (1 to 6 and 12). Live app on the owner's Mac rebuilt from `d514885` on 2026-10-13 00:16 UTC with his yes (HAG-15), backup taken first; his iPhone check of step 6 is PENDING.
* **Next:** **step 7, alerts** (lane `alerts`, Jim; alert threshold 0.07, D47; first the two step 6 follow-ups: Dwight R7 = Angela F-3, and Angela F6). Second lane: **step 8a, stars and who is out from nflverse** once the step 8 rows are laned (plan in `step8-scrape-plan.md`, D51 to D53). Lanes `pwa` and `trends` LANDED; their launchers below are history, do not rerun them. Lane map: `/Users/emmanueladams/.claude/plans/nfl-pickem-lanes/lanes.md`. `lane-guard overlap` OK; `JEV: independent:pwa+trends -> interface_coupling 0.03, shared_state 0.05` (independent). Then step 7 (needs step 6). Steps 8, 10, 11 and 13 wait on the owner or on week 6 (PLAN.md).
* **Phase:** lanes starting. Each lane is one `DIRECT_COORDINATOR / ONE_SHOT` session with its own STATE FILE `lane-<name>.md` in the plan folder.
* **STRIKES:** none. **CONTINUATIONS:** 0.
* **Repo:** base `main` = `origin/main` (step 12 merge `00b952b` plus this docs commit). Lane worktrees `.claude/worktrees/lane-<name>`, branches `lane/<name>`. **Integrator: Michael (hive agent `god`) since 2026-10-12, owner's yes on hive card HAG-1**; before that the owner's session "Work tree parallelization strategy". Only the integrator writes this file, PLAN.md, the progress page, `lanes.md`, `main` and the seam files. `coord` is initialised in this repo: claim your task and `coord lock` your paths; `res:e2e` before any run that starts a server or browser. JEVGREP: unavailable from the integrator's sandbox (network refused 2026-10-12); grep used instead.
* **Provider ledger:** cloud sandbox: Codex not installed → `IMPLEMENTATION_PROVIDER: CLAUDE (limit hit)`; Jev unavailable (no key here). On the owner's Mac: Codex and Jev available. Fable / gpt-6-astra: never without the owner's yes in chat.
* **21st.dev:** connected; search and theme CSS free; component code 2 retrievals a day on the free tier (`docs/design/COMPONENT_SOURCES.md`).
* **Progress page:** https://claude.ai/artifact/6U5zCcvZijcXVMuH6Hbnvd, source `docs/gauntlet/progress.html`. Republish in place only.
* **Waiting on owner:** nothing blocking. Open items in the decisions file (line freshness measured in week 6; Claude sign-in terms read as allowed with OpenRouter fallback, D32/Q10).

## User constraints (carry every handoff)

* Lean: smallest thing that truly works; no over-engineering; no extra tests beyond the gate.
* Never fake data, progress or results. Done = ran and verified with proof.
* Picks lock at kickoff; predictions insert-only; no invented values (CLAUDE.md rules).
* API keys and the VAPID private key server-side only; never commit `.env`.
* Consent: push the feature branch + update the draft PR after a step verifies = **yes (2026-10-11)**. **Standing yes to land (owner, 2026-10-12, HAG-8, D44):** push, PR and merge to `main` without asking when the full gate is green on the committed HEAD, the security review has no CRITICAL, a brand new critic passed, `lane-guard check` is clean, and the full gate is green on `main` after the merge. Deploy, real paid AI calls, key creation, deleting, spending, gpt-6-astra or Fable, scope changes, force pushes = ask first.
* Phone app = PWA only (no Expo, no Android build).
* Report in plain 4th-grade words; results first.

## Owner decisions

See PLAN.md § Owner decisions (each has reversibility + revisit trigger).

## 0. Next handoff

Two lane launchers. Each goes to its own session; do not run both in one.

```text
GAUNTLET_MODE: DIRECT_COORDINATOR
GAUNTLET_PHASE: ONE_SHOT
GAUNTLET_LANE: pwa
STATE FILE: /Users/emmanueladams/.claude/plans/nfl-pickem-lanes/lane-pwa.md
LANE MAP: /Users/emmanueladams/.claude/plans/nfl-pickem-lanes/lanes.md   (read only for you)
WORKTREE: /Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-pwa   BRANCH: lane/pwa   BASE: main, branched at 9d41cb0
OVERALL STEP: step 6 of 14, iPhone PWA (PLAN.md row 6; carried polish in logs/step-3.md section 5 rounds 3-4 and logs/step-4.md line 222)
OWNS / NEEDS: as lanes.md, lane pwa. NEEDS none.
Gate: PLAN.md row 6, plus cd backend && uv run pytest -q && uvx ruff check nflpi tests migrations; npm run gen:api (no drift) && npm run typecheck && npm run web:build && npm run e2e
Done when: gate green with its own numbers, fresh objective critic PASS, design critic PASS, lane-guard check clean. Stop when: three straight failures of one command, or a one-way door needs the owner.
Rules: claim the lane first; edit only OWNS; seams go to the integrator; every Jev question through decide.sh; lane-guard check before landing; push, PR and merge need the owner's yes through the integrator. The markers are authoritative.
IMPLEMENTATION_PROVIDER: CODEX   CODEX_POLICY: CODEX_FIRST   BUILD_RUNG: per work order through decide.sh (try 1 of 2)   CLIMBS: none   STRIKES: none
PROGRESS PAGE: https://claude.ai/artifact/6U5zCcvZijcXVMuH6Hbnvd (integrator republishes; lanes never do)
```

```text
GAUNTLET_MODE: DIRECT_COORDINATOR
GAUNTLET_PHASE: ONE_SHOT
GAUNTLET_LANE: trends
STATE FILE: /Users/emmanueladams/.claude/plans/nfl-pickem-lanes/lane-trends.md
LANE MAP: /Users/emmanueladams/.claude/plans/nfl-pickem-lanes/lanes.md   (read only for you)
WORKTREE: /Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-trends   BRANCH: lane/trends   BASE: main, branched at 9d41cb0
OVERALL STEP: step 12 of 14, Trends (PLAN.md row 12; D30, Q3-Q5 in OWNER_DECISIONS_2026-10-12.md)
OWNS / NEEDS: as lanes.md, lane trends. NEEDS none.
Gate: PLAN.md row 12 (hand-checked counts on known examples; never moves the pick unless it wins walk-forward), plus cd backend && uv run pytest -q && uvx ruff check nflpi tests migrations; npm run gen:api shows no drift
Done when: gate green with its own numbers, fresh critic PASS, lane-guard check clean. Stop when: three straight failures of one command, or a one-way door needs the owner.
Rules: as lane pwa.
IMPLEMENTATION_PROVIDER: CODEX   CODEX_POLICY: CODEX_FIRST   BUILD_RUNG: per work order through decide.sh (try 1 of 2)   CLIMBS: none   STRIKES: none
```
