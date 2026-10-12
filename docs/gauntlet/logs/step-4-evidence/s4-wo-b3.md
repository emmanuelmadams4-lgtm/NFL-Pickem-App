# Work order S4-B3: one-class fix in apps/web/components/performance/scorecard.tsx

Repo /Users/emmanueladams/Projects/NFL-Pickem-App. Edit only that file. Do not commit. Do not edit specs.

Cause found by the coordinator with a browser probe at 375px: the page still scrolls sideways on /performance/
because the `sr-only` spans inside the table (`Missing`) are `position: absolute`; their containing block is
outside the `overflow-x-auto` wrapper, so they escape its clipping and widen the page (one sits at x=665).
Fix: add `relative` to the scroll wrapper div (the one with role="region") so it becomes their containing block.
Nothing else.

Proof: npm run typecheck (paste the tail).
