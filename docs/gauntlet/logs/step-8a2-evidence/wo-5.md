# CODEX WORK ORDER 5 — step 8a2, lane web: cleanup (/refactor, behaviour unchanged)

BUILD_RUNG and effort: see the hive message that carries this work order (try 1 of 2).

GOAL: simplify the code this step touched, with no change in behaviour and no test edited. Every test stays green; `npm run gen:api` produces no change.

BASELINE: worktree `/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-web`, branch `lane/web`, the commit named in the hive message.

ALLOWED SCOPE: `backend/nflpi/api/views.py`, `backend/nflpi/analytics/stars.py`, `apps/web/components/week/game-card.tsx`, `apps/web/components/game/star-players.tsx`, `apps/web/components/game/injuries.tsx`. Nothing else.

REQUIRED CHANGES
1. `views.summaries`: one star read per game. Call `stars.game_stars` only and build `StarsOut` from it: `out` is every star row whose status, lowercased, is in `stars.OUT_STATUSES`, clubs in the API order (away first), each club's rows in list order; `reports_seen` and `checked_at` come from the same result. Remove the `stars.stars_out` call, `star_qb_keys` and the `row | {...}` merge (each row already carries `qb_alert`). `analytics.stars.stars_out` itself stays as it is: its tests and step 8b use it.
2. `report_id` must not be needed outside `views.summaries`' ordering of `qb_alerts`; keep it only if that ordering uses it, in the shortest form (one set, one sort key).
3. One list of alert statuses: `_qb_alert` in `stars.py` and `ALERT_STATUSES` in `views.py` name the same three words. Keep one definition (in `stars.py`, a named constant) and import it in `views.py`. Do not touch `notify/push.py`.
4. Web: remove anything work order 4 left unused (`slotName` entries, imports, the `Chip` import in `game-card.tsx` if nothing else uses it there, props that are passed but could be a plain import without a circular import). If `statusTone` can be imported instead of passed as a prop without a circular import, import it; otherwise leave the prop.
5. Anything else you see in these five files that this step added and that is dead or said twice: remove it and name it in your reply. If you find nothing for an item, say "no change needed" with the reason.

PROOF (the coordinator reruns it): `cd backend && uvx ruff check nflpi tests`; `tests/test_api.py` and `tests/test_stars.py` (one file at a time); `npm run typecheck`; `npm run gen:api` leaves no change; browser `e2e/stars.spec.ts`.

CONSTRAINTS: /ponytail. Behaviour-preserving only: the API responses must be byte-for-byte what they were. No new file, dependency or abstraction. Do not build the web app, do not start a server or a browser, do not run the full suite. Do not commit; report the diff, item by item.
