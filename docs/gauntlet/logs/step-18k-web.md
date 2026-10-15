# Step 18k web: the simulation run check on the game page — step log (lane web)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · coordinator Jim · builder Ryan (Codex) · integrator god.
Worktree `.claude/worktrees/lane-web`, branch `lane/web`: 8g web head `4ee29d4` (PR #42) plus a merge of origin/main
`cd9094b` (18k) as `e571206`, under `res:git-integrate`; `npm run gen:api` shows no drift. Coord task #37.

## 1. PLANNING

**In the owner's words.** When the run check did not pass a game's score simulation, the Score simulator section says
so in plain words: the check failed, gave no verdict (and why), or was not run. It also says whether the numbers shown are
the last checked ones or whether there are none yet.

**Goal (god 3683c0, 9edd3b).** Show `PredictionOut.simulation_check` by the Score simulator section. "Not checked" or
"blocked" gets plain words and the cause; a blocked run shows the last checked simulation and says so. It ships as its
own PR after #42.

**What the API serves (`schemas.py` and `engine.py` on `cd9094b`).**
- `SimulationCheckOut {status: failed|no_verdict|not_checked, note: str, cause?: str|null}`.
- `simulation_check` is null when the run passed (`engine.py:469`).
- On a block, `simulation` is the game's last checked simulation or null (`_blocked`, `engine.py:381`). The `note` is
  fixed server text that ends "showing the last checked simulation" or "no checked simulation yet".
- `cause` is set only for `no_verdict`: one of `cap`, `provider`, `unparsed`, `error` (step-18k.md S4).
- `not_checked` is a backfill run, with the note "A backfill run is not sent to the run check, so it has no simulation."

**Done when.** The spec below holds in `apps/web/e2e/check18k.spec.ts` on a fresh build; typecheck 0; Dwight PASS; a
fresh critic PASS; PR CI runs the full suite (D71).

**Tier T2.** Prior decisions: D74 (the simulator never picks); CLAUDE.md (missing stays missing, always labelled); the 18j
lesson (an old cached game reply has no `simulation_check`, so it must read as "no notice").

**Pre-flight.** (1) Problem: after 18k a blocked run silently shows older numbers. (2) Why now: 18k landed. (3) Scope: a
short notice in the existing section; cut: any history of checks, any badge on the week board. (4) Success: the owner
can tell when the simulator numbers were not checked (qualitative). (5) Two-way door (UI only).

**Assumptions.** validated: the shape and the meaning (code read above). assumed: the cause codes read best as short
phrases (the design check covers it). unknown: none.

**Instrumentation.** N/A (UI only). **Skills.** grep and read of `engine.py` `_check_run`/`_blocked` and `views.py:105`
pinned the meaning; `/jevgrep` N/A; TDD with Playwright at the page; `/ponytail` in the work order; Design Gauntlet:
applies, as a small notice inside an existing section.

**Test data.** The real game reply with `simulation` and `simulation_check` replaced, typed against the wire types.
Made-up values; no names.

## 2. SPECIFICATION (frozen before production code)

Inside `#simulator`, above the numbers, when `simulation_check` is present, a notice:
- C1 `failed` with a kept simulation: the heading "Run check failed", then the server `note` word for word. The kept
  simulation's numbers still show below it.
- C2 `no_verdict`: the heading "Run check gave no verdict", the `note` word for word, and "Cause: <plain words>" with
  cap = "the daily check limit was reached", provider = "Claude could not be reached", unparsed = "the check's answer could
  not be read", error = "the check hit an error". With `simulation` null it still says
  "No simulation for this game yet."
- C3 `not_checked`: the heading "Not checked", and the `note` word for word.
- C4 `simulation_check` null or absent (a passed run, or an old cached reply): no notice; the section reads as in 18j.
- C5 No serious or critical axe finding in `#simulator` with a C2 notice; no sideways scroll at 320 px.

Gate: `e2e/check18k.spec.ts` and `e2e/sim18j.spec.ts` on a fresh build; typecheck 0; PR CI runs the full suite.

**Red (`s18kw-red-1`, fresh build of `745fee6`): 6 failed, 3 passed, as intended.** C1, C2 (all four causes) and C3
fail on their heading ("Run check failed", "Run check gave no verdict", "Not checked"). C4 (null, absent) and C5 pass
today: they guard what must not change.

## 3. IMPLEMENTATION
- WO1 (`evidence/wo-1.md`, try 1): Ryan reported at 04:12 UTC. The diff touched only `simulation.tsx` and matched
  the order. Typecheck 0. `s18kw-green-1` (fresh build of check18k and sim18j): **16 passed**. Committed `7340ec2`.
- Design Gauntlet: notice screenshots `after-{failed,noverdict}-{393,1280}.png`. A fresh design critic reviewed them
  (`evidence/reviews/design-1.md`): 1 MUST, the notice touches the next line when there is no simulation; 1 SHOULD,
  use the shared `Notice`. Both taken. Test first: C6 (`s18kw-red-2` fails on the class). WO2.
