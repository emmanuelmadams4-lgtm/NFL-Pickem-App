# Design review 1: Value section (step 18l)

MUST
1. Each rating is its own bordered card. design.md section 133 says "A game is never its own card"; rows divide with hairlines inside one group. News uses `<ul className="divide-y divide-border">` with `py-4 first:pt-0 last:pb-0`. Change `<ul>` and `<li>` to match; drop `rounded-card border p-3` and `space-y-3`.
2. Flat hierarchy: title, status and reasons are all 14px, and only the title is medium weight. Status is the answer and must scan first. Render it as `<Chip>` (neutral for Unrated/No bet, `accent` for n of 5 stars, never lime fill) on the same row as the market title (`flex flex-wrap items-center justify-between gap-x-3 gap-y-1`). Add the words "stars" or "No bet" to the chip text so it is not colour-only.
3. The same "not yet shown to beat the market" appears 1 + N times (section line plus each Unrated row). Keep the required line once, and render it with the shared `note` prop on `Section` (as other sections do) instead of a loose `<p>`. Per row, show it only as the reason, in `text-text-2`, prefixed "Why:" or placed beside the chip. Do not drop it from rows.

SHOULD
- Expected value is a number: `tabular-nums`, label in `text-subtle text-xs` ("Expected value"), value in `text-text`. A positive EV next to "No bet" (+32% on a stale total) reads as contradictory; put the reason directly after the status line, not after EV.
- Price line: make "bookone" `text-text-2` so the market and price lead.
- Note: keep `text-xs text-subtle` (5.3:1 on surface, OK). Do not place it on `elevated` (4.47:1).
- Empty state: copy is fine; use `text-text-2` only, and drop the disclaimer line when there are no rows (nothing is being rated).
- Replace the index key with a stable key (`rating_id` if the API has one).

NIT
- Reasons are lowercase fragments; capitalise the first letter of each joined string.
- Separator dots are read aloud; use `aria-hidden` spans like news.tsx.
- Use `leading-snug` on the note so it wraps cleanly at 393px.
