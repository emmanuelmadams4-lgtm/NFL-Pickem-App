# CODEX WORK ORDER 1 — step 8g web: news on the game page

Try 1 of 2. Baseline: branch `lane/web`, the commit named in the hive message (red tests `9981e74`).

GOAL: the game page shows that game's latest news from `GET /api/news?game_id=<id>`. Spec N1-N6 in
`docs/gauntlet/logs/step-8g-web.md` §2; the tests are `apps/web/e2e/news8g.spec.ts` (read both). The API contract is the
"ROUTE CONTRACT" section of `docs/gauntlet/logs/step-8g-server.md`; the types `NewsOut`/`NewsItemOut` already exist in
`packages/shared/src/api-types.ts` (do not edit that file).

ALLOWED FILES:
- `packages/shared/src/client.ts`: `export type News = S["NewsOut"];`, a client method
  `news: (gameId: string) => call<News>(`/news?game_id=${encodeURIComponent(gameId)}`)`, and `news: (gameId: string) => ["news", gameId] as const` in `keys`.
- `apps/web/lib/queries.ts`: `useNews(gameId)` like `useGame` (same `enabled`, no refetch interval needed).
- `apps/web/components/game/news.tsx` (new): `NewsSection({ game })`.
- `apps/web/components/game/game-view.tsx`: `{ id: "news", label: "News" }` in `SECTIONS` right after "injuries", and
  `<NewsSection game={game} />` right after `<Injuries game={game} />`.

REQUIRED BEHAVIOUR (`NewsSection`):
- `<Section id="news" title="News">`, matching the other sections (see `simulation.tsx`, `history.tsx`).
- Loading: a `Skeleton`. Error with no data: `ErrorState` titled "Could not load news" with a retry.
- `items.length === 0`: `<p className="text-sm text-text-2">No news for this game yet.</p>`, and no list.
- Otherwise a `<ul>` with one `<li>` per item, in the API's order. Title as React text (never `dangerouslySetInnerHTML`).
  If `url` starts with `https://`, the title is `<a href={url} target="_blank" rel="noopener noreferrer">`; otherwise plain
  text with no link. Below it: the source; then `ago(published_at)` from `@nflpi/shared` only when `published_at` is not
  null; then each tag as a `Chip`.
- Must fit at 320 px with long titles (wrap; no sideways scroll), and no serious axe finding.

PROOF: `npm run typecheck`. The coordinator reruns `e2e/news8g.spec.ts` and `e2e/phone-layout.spec.ts` on a fresh build.
CONSTRAINTS: /ponytail (smallest working diff, no new dependency, no abstraction). No backend files, no `api-types.ts`,
no test edits. typecheck only. Do not commit. Send the hive report as soon as the edit is done.
