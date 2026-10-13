# Design critic reports, step 16b web (fresh general-purpose sonnet subagents, read-only, no build transcript)

Only made-up names appear anywhere in the screens they judged.

## Round 1: UX architect, on the brief and the frozen spec, before any code
Verdict: 3 blockers, 6 advisories, 3 nits. All 3 blockers accepted and the spec amended before any code was written (step log § 2, "Amendments").
* B1 no clause for loading or a failed fetch (an error could read as "no data") -> clause L1 + check.
* B2 no rule against a late reply for an earlier week replacing the current one -> clause L2 + check.
* B3 a wrong-year upload looks like a success and cannot be noticed -> confirm line "Saving to the {season} season", a "Show the {season} season" link after saving into another season, clause U1b + checks.
* Advisories taken: exact-match counts in P1, one message for a week nobody picked (P3b), a 32-member and long-name phone check (R2), "spread" checked on the whole body (X1b), double tap sends once, same file can be chosen again, season options come from `meta.seasons`.
* Advisories carried, not built: collapsing standings to a top ten; showing the file kind before saving (the server cannot tell without saving); "x of 32" wording; picks above standings.

## Round 1: anti-slop + polish + implementation critic, on the built screen (22 screenshots)
Verdict: "not yet": 1 rule violation, 3 STRUCTURAL; otherwise ties or beats the Results page on the phone for hierarchy and spacing; no AI-generic tells; tokens only; accessibility semantics good.
* FIXED (work orders 4 and 5, gpt-6-luna): `font-bold` on the season line -> `font-semibold` (design.md allows 400/500/600); the share bar removed (a bar beside a percent reads like the model's win probability, design.md § 2 rule 2); missing app pick now carries the words "not available" for screen readers, and a missing rank is explained under the table; the upload error moved above the buttons with a one-line hint under it (the server's text stays verbatim: clause E1); success link given a 44px tap target; table capped at `max-w-xl` on wide screens.
* CARRIED (advisory, not mapped to a frozen clause): "Model pick" wording vs the owner's "app's own pick" (the spec fixes "App pick:"); labels on the three numbers of a side row (the spec fixes the strings); repeated "Week 3, 2023" notes; upload section above the data; per-game cards as one grouped list; `h-11 lg:h-9` repeated on three buttons (a Button size prop is lane web's file); skeleton `role=status`; cards as `ul/li`; the app footer sentence about probabilities appears on this page (shared footer, lane web's file).
