# Security review 1: step 18j web (Dwight `dwight-mv5mkpow`, 2026-10-14, on `b4ba105`)

PASS for step 18j web: git diff origin/main...b4ba105 in lane-web. There are no findings at CRITICAL, HIGH or MEDIUM.

WHAT I CHECKED
- I read the production diff myself: game-view.tsx, simulation.tsx (new) and week-board.tsx.
- I also checked the test e2e/sim18j.spec.ts for the token it uses and the routes it intercepts.
- I did not run the two ecc agents, because this change is UI only and has no new surface. Nothing was run and no server was started.

RESULT
- Injection or XSS (a script getting into the page): none. sim.label, the pick-mode label, team abbreviations and numbers are all rendered as React text. I found no dangerouslySetInnerHTML, innerHTML, href built from data, or eval.
- No new routes, auth, storage, fetch calls or dependencies. The section reads game.prediction.simulation from the existing authenticated /api/games/<id> query.
- The test sets a fixed fake token ("e2e-token") in localStorage and intercepts /api/games/<id> in the browser only. It holds no real secret and does not touch ports 8000 or 5432.
- Data integrity: a null simulation shows "No simulation for this game yet". A null spread or total shows "No spread/total yet". The page says the simulator "does not change the pick". This matches "missing stays missing" in CLAUDE.md.

ADVICE (LOW, not blocking)
- A1, ordering with step 18k: once 18k lands, PredictionOut.simulation_check (failed / no_verdict / not_checked, with a note) says when the simulation shown is a carried-forward older one, or that this run's simulation was blocked. This section does not render simulation_check. After 18k, the owner would see an older checked simulation with no sign that the run was blocked. Add simulation_check.note to this section when 18k lands. It maps to CLAUDE.md "always labeled".
- A2, simulation.tsx:111: the total line is shown as the raw number ({sim.total}), while the spread goes through spreadText. This is cosmetic only.

## Triage (Jim)

- A1: carried. It is already the planned 18k follow-up (god 5f9ef8): when 18k lands, sync main, gen:api, show the run-check state with its cause on the game.
- A2: not taken. `{sim.total}` prints the server's line as is (45.5, 45); a total has no sign or Pick'em case, so spreadText does not apply.
