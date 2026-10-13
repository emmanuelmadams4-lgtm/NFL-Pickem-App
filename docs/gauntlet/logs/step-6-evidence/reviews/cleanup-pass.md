# CLEANUP: scope-locked refactor pass (on `cfbef46`) — CHANGES RECOMMENDED (1)

Fresh read-only subagent. Scope: production code this step touched (`git diff 9d41cb0..cfbef46 -- apps/web packages/shared scripts`, tests excluded). Rule: behaviour-preserving only, no new abstractions or files.

| id | file | what to simplify | exact change | why it cannot change behaviour |
|---|---|---|---|---|
| R1 | `apps/web/lib/sync.ts`, `unqueueIfCurrent` and `flushPicks` (three places) | The `gameId in queue` test is redundant. | `if (!(gameId in queue) \|\| queue[gameId] !== team)` → `if (queue[gameId] !== team)` | Queue values are `string \| null`, written only by `queuePick` and read from JSON, so never `undefined`. A missing key reads as `undefined`, which never equals `team`. |

Leave as is:
- The `change_note.replace(/^Changed:\s*/i, "")` in `game-card.tsx` and `recommendation.tsx`: two one-line uses; sharing it needs a new export.
- Phone and desktop subtitle spans in `week-board.tsx`: the two texts differ on purpose; same pattern as `kpi-strip.tsx`.
- The literal `12px` in `scroll-padding-top` (`globals.css`): no token means "gap below the header"; the line above uses a bare `84px` too.
- `phoneSub: "None graded"` twice in `kpi-strip.tsx`: two short cell definitions.
- `API_TIMEOUT_MS` exported from `client.ts` but used only there: harmless, it is the public timeout setting.
- The extra class argument in `Segmented` (`ui.tsx`): taste only.
- `sw.js`, `stamp-sw.mjs`, `persist.ts`, the `pwa.tsx` update flow: no dead code, no debug output, no false comments. The removed API cache and `replay` helper have no remaining references.
