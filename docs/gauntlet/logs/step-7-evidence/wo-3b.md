# CODEX WORK ORDER 3b — step 7, lane alerts: the test alert result (design critic findings 1, 2, 4)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: make `apps/web/e2e/alerts.spec.ts` test A4 pass again (it is red on three new checks) and keep A4b, A5 and every other browser test green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit named in the hive message.

SOURCE: `docs/gauntlet/logs/step-7-evidence/reviews/design-critic-1.md`.

ALLOWED SCOPE: `apps/web/components/settings/alerts.tsx` only.

REQUIREMENT
1. The button is free as soon as the result shows. Today `sendTest` awaits `qc.invalidateQueries(...)`, so "Send test alert" stays busy (and disabled) while meta is re-read. Start the re-read without waiting for it.
2. A result that is not a full delivery reads as a problem: the line uses the `text-bad` token when the reply is "Not delivered…", "Delivered to X of N devices…" or "The server has no device to send to…". A full delivery ("Delivered to N device(s).") keeps `text-subtle`. Keep `role="status"` and the words exactly as they are. Hold what is needed in state as data (for example the text and whether it is a problem); do not work out the tone by matching on the sentence.
3. The result line sits directly under the row of buttons and above the line "N device(s) … subscribed on the server.", not below it. The `role="alert"` error line stays where it is.

FAILING EVIDENCE: `docs/gauntlet/logs/step-7-evidence/red-wo3b.log` (first failure: the button is still disabled after the result shows; the tone and order checks follow it in the same test).

PROOF (the coordinator reruns it): `npm run typecheck`. You cannot bind ports; the coordinator runs the gate.

CONSTRAINTS: smallest correct diff; existing tokens only (`text-bad`, `text-subtle`); no new component, colour or size; no other file; do not edit tests; do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): the changed lines, a three-line summary, the proof command with its exit code, any blocker.
