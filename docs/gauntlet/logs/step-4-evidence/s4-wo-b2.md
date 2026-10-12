# Work order S4-B2: narrow correction, the scorecard table on the phone

Repo /Users/emmanueladams/Projects/NFL-Pickem-App, branch claude/step-4-pick-sheet. Edit only
apps/web/components/performance/scorecard.tsx (and performance-view.tsx only if the wrapper there is the cause).
Do NOT edit specs. Do not commit. /ponytail: smallest diff.

Failing browser checks (coordinator ran them; you cannot launch a browser in your sandbox):
1. restyle.spec.ts F1 (320px) and sheet.spec.ts U4b (375px): `/performance/` scrolls sideways. At 320px
   `document.documentElement.scrollWidth` is 665. The scorecard table (`min-w-[660px]`) must scroll inside its own
   container, never widen the page. The `overflow-x-auto` wrapper is not containing it: an ancestor (grid or flex
   item, the `Section`, or the `form`/`fieldset`) lets its min-content width grow. Fix with `min-w-0` on the
   right ancestors and/or `w-full` + `overflow-x-auto` on the wrapper. A `fieldset` has `min-inline-size:
   min-content` by default: give it `min-w-0` too.
2. restyle.spec.ts G5 (phone, dark and light): axe `scrollable-region-focusable` on that wrapper. A scrollable
   region must be reachable by keyboard: add `tabIndex={0}`, `role="region"` and
   `aria-label="Scorecard table, scrolls sideways"` to the scroll wrapper, with the app's visible focus ring.

Proof: npm run typecheck && npm run web:build (paste tails). Say plainly that you could not run the browser.
