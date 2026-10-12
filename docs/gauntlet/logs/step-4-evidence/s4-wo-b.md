# Work order S4-B: pick sheet on screen (make apps/web/e2e/sheet.spec.ts pass, keep every other e2e green)

You are the builder. Repo /Users/emmanueladams/Projects/NFL-Pickem-App, branch claude/step-4-pick-sheet.
Read first: CLAUDE.md, design.md section 0 (the look: binding) and sections 8-12, apps/web/AGENTS.md,
apps/web/e2e/sheet.spec.ts (the frozen gate: DO NOT edit it or any other spec), docs/gauntlet/logs/step-4.md
sections 1-3, apps/web/components/week/game-card.tsx, week/week-board.tsx, pick-buttons.tsx,
performance/performance-view.tsx, app-shell.tsx, ui.tsx, lib/queries.ts, lib/sync.ts, lib/clock.ts,
packages/shared/src (client, keys, format).

Style: /ponytail. Smallest correct diff; reuse `Chip`, `cx`, existing tokens and classes; no new dependency, no new
colour, no new font size under 11px. Follow the line style of game-card.tsx (one JSX attribute cluster per line,
lines under ~170 chars). No prediction or ranking logic in the client: render what the API returns
(`game.sheet`). Do not touch backend/, scripts/, docs/. Do not commit.

## 0. Contract
Run `npm run gen:api` from the repo root first (regenerates packages/shared/openapi.json and src/api-types.ts;
never hand-edit them). Add to the shared client: `setPoints(gameId, points)` (PUT /picks/{id}/points -> Week),
`clearPoints(gameId)` (DELETE -> Week), `scorecard(season)`, `setRank(season, week, {rank, leader_points})`, and
query keys in the same style as the existing ones.

## 1. Words (fixed product terms, exactly these)
"Easy pick", "Tough matchup", "Coin flip" for sheet.label easy_pick / tough_matchup / coin_flip.
Never "lock" as a noun for a pick, never "guaranteed". "Points" for confidence points.

## 2. Game card (components/week/game-card.tsx, + one small new component file for the points control)
* Replace the `strengthLabel(prob)` line under the win-chance bar with the label: an element with
  `data-testid="pick-label"` whose text is exactly the label words, followed (outside that element) by its
  measured hit rate in small text-2: "won 77% of the time, 2012-2025" from `sheet.label_hit_rate`. No label = omit.
  Then delete `strengthLabel` if nothing else uses it (grep first).
* New row between the status chips and the pick pills: "Points".
  - Open game with `sheet.my_points`: a native `<select>` with accessible name
    `Points for {away.abbr} at {home.abbr}`, options 1..N where N = number of games on the board whose
    `sheet.my_points` is not null (pass N down from the board), value = my_points. Height 48px on the phone,
    40px from `lg`, `rounded-control`, `border-border-strong`, `bg-elevated`; the chosen number also shown large in
    the display face next to the word "Points" so the number reads at a glance. It must sit above the card link
    (`relative z-10`) like the pick pills.
  - On change: call setPoints; on success write the returned week into the query cache for that week
    (`queryClient.setQueryData(keys.week(season, week), week)`), so both swapped cards update at once. On error:
    the existing toast with `errorMessage`, and the select returns to the server value. No offline queue for
    points in this step: when offline the toast says the change needs a connection.
  - `sheet.points_by === "user"`: show the words "Your number" and "App says {app_points}" (text, not colour
    alone) and a text button "Use the app's number" (accessible name exactly that) that calls clearPoints and
    writes the returned week to the cache.
  - Locked (use the existing `useLocked(game)`): the select is `disabled`, shown with the Lock icon, 60% ink.
  - No `my_points` (postponed, no prediction, or an old game): no Points row.
* Whose pick (one short line above the pick pills, text-label):
  - `pick_by === "app"` and not locked: "App pick: {app_pick}. Tap a team to make it yours."
  - `pick_by === "auto"`: a Chip "Auto pick" (it was the app's pick at kickoff).
  - `pick_by === "user"` / "csv": nothing extra (the lime pill already says it is his).
  The pick pills keep their behaviour: lime fill only for HIS pick (`game.my_pick` with pick_by user/csv). An
  untouched game shows no lime pill; the app's team is named in the line above. An auto pick after kickoff may
  show the picked pill as today.
* The existing "Differs from model" chip stays for a different winner. Points that differ are covered by
  "Your number / App says".

## 3. Week board (components/week/week-board.tsx)
* Compute N once and pass it to each card.
* In the page head, next to the filter chips row (not inside the chip group), a pill link "Copy to Yahoo"
  (accessible name exactly that) to `/sheet/` carrying the same season/week query string the shell uses.

## 4. Copy sheet page (new route apps/web/app/sheet/page.tsx + components/sheet/sheet-view.tsx)
* Same page head pattern as the other screens: kicker "Week {n}", title in the display face: "COPY SHEET".
* One line of help: "Enter these in Yahoo. Tiebreaker scores are not in the app yet."
* A list in kickoff order (then game_id) of every game with `sheet.my_points !== null`; each row
  `data-testid="sheet-row"`: day and kickoff time, "{AWAY} @ {HOME}", the winner (`data-testid="sheet-winner"`,
  text exactly the team abbreviation, with its TeamLogo beside it, logo outside the testid element), and the
  points (`data-testid="sheet-points"`, text exactly the number, display face). A locked row shows the Lock icon
  and the word "Locked". An "Auto pick"/"App pick" note in small text where pick_by is auto/app.
* A primary button "Copy as text": writes one line per row, exactly
  `{AWAY} @ {HOME}: {my_pick} {my_points}` joined with "\n", via `navigator.clipboard.writeText`, then shows
  "Copied" in an element with `role="status"` (and a plain error message if the clipboard call fails).
* Loading, empty ("No games with points this week") and error states, in the style of the other screens.
* The shell must treat `/sheet` as part of "Week" for the active nav item.

## 5. Results (components/performance/performance-view.tsx + one new component file)
* A `fieldset`/group with accessible name "Your Yahoo rank": label-above inputs "Week" (native select of the
  season's weeks 1..18, default the current week), "Your rank" (number, min 1), "Leader's points" (number, min 0,
  optional), and a button "Save rank". On save: setRank, then refetch the scorecard; inline error text under the
  field on a 422. Helper text: "From your Yahoo league's standings."
* A table with accessible name "Scorecard" (`<table aria-label="Scorecard">`), columns: Week, You, App, Max,
  Changed, Auto, Rank. One row per scorecard week labelled "Week {n}"; "You"/"App" are points; "Changed" reads
  like "2 (1 right, 1 wrong)"; rank shows as "4" with the leader's points in small text when present; missing
  values are an en dash with a reason available to screen readers, as elsewhere in the app. A totals row.
  Horizontal scroll inside its own container on the phone, never the page.
* Auto picks: the "Me" tally now excludes them (the API already does); add one small line
  "Auto picks: {correct} of {total}" using `performance.auto` when total > 0.

## 6. Accessibility and layout (gates in the spec)
0 serious/critical axe issues in dark and light on `/`, `/sheet/`, `/performance/`; no sideways scroll at 375px;
every new control reachable by keyboard with a visible focus ring; touch targets 44px+ on the phone; nothing
under 11px; states never by colour alone.

## Proof you must run and paste the tail of (from the repo root)
npm run gen:api && git status --short packages/shared   (shows the regenerated contract)
npm run typecheck
npm run web:build
If you can bind a port: npm run e2e   (all specs). If your sandbox cannot bind ports or reach Postgres, say so
plainly; the coordinator will run e2e. Never claim a pass you did not see.

## Report back
Files changed, command tails, anything in this order that is wrong or impossible, every simplification made on
purpose.
