# CODEX WORK ORDER 6 — step 7, lane alerts: Settings shows the device the app just re-sent

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: make `apps/web/e2e/alerts.spec.ts` test A1c pass and keep every other browser test green.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit named in the hive message.

ALLOWED SCOPE: `apps/web/lib/push.ts` (`keepPushSubscription` only) and `apps/web/components/pwa.tsx` (`PushKeepAlive` only).

PROBLEM: on open, `PushKeepAlive` re-sends this device's subscription. The meta query was read before that, so Settings keeps saying "0 devices are subscribed on the server." beside "Alerts on" until something else re-reads meta. A false statement on the screen he checks.

REQUIREMENT: `keepPushSubscription` reports whether it sent a subscription to the server (resolves `true` after a successful `pushSubscribe`, `false` in every other case, failures included; it still never throws). When it did, `PushKeepAlive` re-reads meta once (`qc.invalidateQueries({ queryKey: keys.meta })`). It still runs once per app open: the re-read must not start it again.

FAILING EVIDENCE: `docs/gauntlet/logs/step-7-evidence/red-wo6.log` (red 3 runs of 3: "1 device is subscribed on the server." never appears).

PROOF (the coordinator reruns it with the full gate): `npm run typecheck`.

CONSTRAINTS: smallest correct diff; no other file; do not edit tests; do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): the changed lines, the proof command with its exit code, any blocker.
