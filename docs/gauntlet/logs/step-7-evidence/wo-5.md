# CODEX WORK ORDER 5 — step 7, lane alerts: CLEANUP (scope-locked refactor of the code this step touched)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: simpler code, same behaviour. Every test stays green and no test changes. If one of the three items below would change behaviour or does not come out simpler, leave it and say why: "no change, because …" is a valid result.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-alerts`, branch `lane/alerts`, the commit named in the hive message.

ALLOWED SCOPE: `backend/nflpi/notify/push.py` (`_send` only), `backend/nflpi/predictions/engine.py` (the `qb_team` / `qb_name` lines in `refresh_predictions` only), `apps/web/components/settings/alerts.tsx` (`sendTest` only), `apps/web/lib/push.ts` (only to receive the function from item 3).

ITEMS
1. `push._send`: the block `if results is not None: results.append({...})` is written four times. Work out one outcome per device (`ok`, `status`, `error`) in the `try`/`except` branches and append it once after them. Same log lines, same deletes on 404 and 410, same return value, same result dictionaries in the same order.
2. `engine.refresh_predictions`: `qb_team` is found by a generator and `qb_name` is then looked up again from `qb_team`, with an `isinstance` check at the call. Find the side and its new starter in one step, so the name is never looked up twice. Same rule: the previous snapshot named a starter for that side and the new one names a different one; home side first.
3. `alerts.tsx` `sendTest`: the words for a reply are built inline with a nested conditional. Move them to one pure function, `testAlertWords(result: PushTestOut): { text: string; problem: boolean }`, in `apps/web/lib/push.ts`, and call it. Same words, same `problem` rule.

NOT IN SCOPE: anything else, however tempting. No renames outside these lines, no new file, no new dependency, no test edits, no comments that only restate the code.

PROOF (the coordinator reruns all of it with the full gate): `cd backend && uvx ruff check nflpi tests migrations` (or your cached ruff) and `npm run typecheck`.

CONSTRAINTS: behaviour-preserving; smallest diff that does each item; never log or return a full subscription endpoint or a key; do not commit.

RETURN (reply to Jim, `jim-mv5mje0k`): per item, "done" with the changed lines or "no change, because …"; the proof commands with exit codes; any blocker.
