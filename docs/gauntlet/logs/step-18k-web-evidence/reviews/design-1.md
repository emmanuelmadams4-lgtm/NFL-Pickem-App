# Design critic 1: step 18k web, on `7340ec2` (fresh read-only subagent; screenshots `after-*` in `~/.claude/plans/nfl-pickem-lanes-logs/step-18k-web/`)

1. MUST spacing: in "no verdict" (393, 1280) the notice touches "No simulation for this game yet." (`simulation.tsx:44`: `mb-4` only when `sim`).
2. SHOULD consistency: a hand-built box where `ui.tsx` `Notice` (design.md:152) exists; corners `rounded-card` vs `rounded-ctl`, padding, heading colour `text-text` vs `text-warn`. Use `<Notice tone="warn" title=… className="mb-4">`.
3. COULD hierarchy: reads as a caveat already (warn, role note); item 2's warn heading adds the semantic colour.
4. COULD order: keep as built (label in header, notice, then "Shown only…").
5. Accessibility: no change; contrast fine; `role="note"` right.

## Triage (Jim)
Taken: 1 and 2 (the shared `Notice` is less code and matches the app). 3 comes with 2. 4 and 5: no change.
Test first: C6 asserts the notice is the shared Notice (`rounded-ctl`) and a gap of at least 8 px under it; `s18kw-red-2` fails on the class. WO2.
