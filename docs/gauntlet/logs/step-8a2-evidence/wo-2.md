# CODEX WORK ORDER 2 — step 8a2, lane web: stars on the row and the game screen

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: make `apps/web/e2e/stars.spec.ts` ST1 to ST7 green and the two new `no_list` assertions in `backend/tests/test_api.py` green, without changing any test, and keep every other test green. ST8 (Settings freshness rows) and `test_freshness_lists_the_star_list_and_the_head_coaches` stay red: they need a file outside this lane.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message. Spec: `docs/gauntlet/logs/step-8a2.md` section 2 (criteria ST1 to ST7, "Spec amendment after the freeze"), and the decisions in `step-8a2-evidence/reviews/ux-architect-spec.md`. Read `apps/web/AGENTS.md` first: this Next.js version differs from the one you know.

ALLOWED SCOPE: `apps/web/components/week/game-card.tsx`, `apps/web/components/game/injuries.tsx`, at most one new component file under `apps/web/components/game/` if `injuries.tsx` would pass about 150 lines, `apps/web/components/freshness.tsx` (item 5 only), `backend/nflpi/api/schemas.py` and `backend/nflpi/api/views.py` (item 1 only), the generated `packages/shared/openapi.json` and `packages/shared/src/api-types.ts` (`npm run gen:api`), and `packages/shared/src/index.ts` only if a new type must be re-exported. Nothing else: no test file, no `globals.css`, no new dependency, no new token.

REQUIRED BEHAVIOUR
1. **API: `StarsOut.no_list: list[str]`**: the clubs of this game that have no star list (their `stars_week` is None), away club first. `stars_out` in `analytics/stars.py` already knows each club's list; if you need it there, that file is NOT in scope: derive it in `views.py` from what the star functions already return, or tell me if that is impossible.
2. **Row (ST1, ST2, ST3)** in `game-card.tsx`, for games whose `status` is `scheduled` only:
   * At least one star to show: a `role="group"` with `aria-label="Stars out"` on its own full-width line directly under the flags row (the one with Upset watch and the QB alerts) and above "What changed" and the pick buttons. Visible label text "Stars out". Then up to three stars in the API's order: name, position (small, subtle), status chip (same `Chip` tones as the QB alert: Out = bad, Doubtful = warn). Then "+N more" when more are hidden. Then "latest seen {ago(newest observed_at of the stars shown)}".
   * A star is left out when a `game.qb_alerts` entry already names him (an entry reads `"{team} QB {player}: {status}"`); "+N more" counts only stars that would otherwise be shown.
   * No star to show: when `stars_out.no_list` is not empty, the quiet text "No star list yet"; else when `stars_out.reports_seen` is 0, the quiet text "Injury report not in yet"; else nothing at all.
   * Plain text. No new link, button, tooltip or icon. It must sit above the card's link layer the way the flags row does only if it needs to be selectable; do not block the card link.
   * A long name truncates or wraps inside the card; the page never scrolls sideways at 393 px.
3. **Game screen (ST4, ST5, ST6)** in the Injuries section (`injuries.tsx`), above the existing per-club injury lists, under an `h3` "Star players":
   * Two clubs side by side from `md`, stacked on the phone, away first: logo and club name as the existing `TeamInjuries` head does.
   * A club with a list: a `ul` with `aria-label="{club name} star players"`, five `li` in the API's order. Each row: a slot word (QB, Offense, Defense), the name, the position, then on the right his status: a `Chip` for Out (bad) and Doubtful (warn), plain text for any other status, or the quiet text "Not on injury report" when `status` is null. A row with a status also shows the injury and "seen {ago(observed_at)}" on a second line.
   * When `game.stars_out.reports_seen` is 0: no row says "Not on injury report" (show an en dash instead) and the block says "No injury report yet this week".
   * A club whose `stars_week` is lower than `game.week`: "Star list from week {stars_week}" under its name. A club with `stars_week` null: "No star list yet" in the dashed empty-state box the section already uses, and no list.
   * Two short notes under the heading, in the section's existing note style: "A star being out does not change the pick." and "Ages count from when this app first saw the status."
   * The existing "Report as of ..." note and the per-club injury lists stay exactly as they are.
4. **ST7**: no serious or critical axe issue, dark and light. Colour is never the only signal: every status is also a word.
5. **Freshness label** (`freshness.tsx`): show a dataset name with underscores as spaces ("head coaches"). `MODEL_INPUTS` stays as it is: `stars` and `head_coaches` must never turn the top-bar indicator amber.

DESIGN (source: `design.md` — rules inlined because Codex cannot load design skills)
REGISTER: product   USER GOAL: see at a glance which games have a star out; the primary action stays "tap a team to pick".
REUSE: `Chip`, `Section`, `TeamLogo`, `ago`, the `statusTone` already in each file; tokens only from `apps/web/app/globals.css` (`text-text`, `text-text-2`, `text-subtle`, `text-label`, `border-border`, `rounded-ctl`); no new UI or animation dependency.
STATES: per the list above (loading is the page's existing skeleton).
A11Y: semantic lists and headings, visible focus unchanged, no new interactive element.
MOTION: none.
DON'T: lime anywhere in this feature (lime means "me") · a red or amber border, tint or icon on the card or near the pick buttons · a card inside a card · a new pill for the label · gradient, glow, glass · one-off hex or px values · lines longer than about 160 characters of JSX (match `injuries.tsx`).
CHANGES, in order: API field → row line → game-screen block → freshness label.

PROOF (the coordinator reruns all of it; you cannot bind a port or reach the test database, so say so): `npm run gen:api`, `npm run typecheck`, `cd backend && uvx ruff check nflpi tests migrations`. Do NOT run `npm run web:build`, `npm run e2e` or anything that writes `apps/web/out`: the coordinator still needs the old build for the "before" screenshots and runs the build himself.

CONSTRAINTS: smallest diff that does each item (Ponytail); match the surrounding code; no test edits; do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): per item the changed files and lines; the proof commands with exit codes; anything you could not run; any blocker.
