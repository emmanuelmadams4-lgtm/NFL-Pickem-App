# CODEX WORK ORDER 3 — step 18l: design critic MUSTs + Dwight's V1 and L1/L3

Try 1 of 2. Baseline: `lane/web` after WO2 is committed (commit named in the hive message).
Sources: `reviews/design-1.md` (design critic), Dwight's 18l reply (V1 MEDIUM, L1, L3).

ALLOWED FILES: `apps/web/components/game/value.tsx`.

API: none (Dwight V1 moved into WO2).

WEB (`value.tsx`), keep every test in `e2e/value18l.spec.ts` green (no test edits):
1. Rows, not cards (design.md: a game is never its own card): `<ul className="divide-y divide-border">`, each `li`
   `py-4 first:pt-0 last:pb-0 min-w-0 break-words` (as news.tsx). Drop `rounded-card border p-3` and `space-y-3`.
2. Title row `flex flex-wrap items-center justify-between gap-x-3 gap-y-1`: left the market, side and price
   (`font-medium text-text`) with the book in `text-text-2`; right the status as `<Chip>`: "Unrated" and "No bet"
   neutral, `${stars} of 5 stars` accent.
3. The disclaimer once, through `Section`'s `note` prop: "Ratings are not yet shown to beat the market." (drop the loose `<p>`).
4. Under the title: the reasons line first (text-sm text-text-2), then "Expected value" (text-xs text-subtle) with the
   figure `tabular-nums text-text`, then the note (`text-xs text-subtle leading-snug`).
5. Separator dots `<span aria-hidden="true">·</span>` as news.tsx does.
6. Reason lookup with `Object.hasOwn(REASONS, reason) ? REASONS[reason] : reason` (Dwight L3).
7. Empty state (Dwight L1, honest when prices exist at other lines): "No book prices to rate for this game. Spread and
   total prices are rated only at the simulator's line."
Never the word "available"; lower-case reason words stay as they are.

PROOF: typecheck; pytest test_value_api.py (with the DATABASE_URL on 15436); ruff. The coordinator runs the browser specs.
CONSTRAINTS: /ponytail; no test edits; do not commit; report when done.
