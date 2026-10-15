# Step 8g web: news on the game page — step log (lane web)

GAUNTLET_MODE: DIRECT_COORDINATOR · GAUNTLET_PHASE: ONE_SHOT · coordinator Jim · builder Ryan (Codex) · integrator god.
Worktree `.claude/worktrees/lane-web`, branch `lane/web`, fast-forwarded to origin/main `f12bb90` (2026-10-15; the
`res:git-integrate` lock call failed on my shell quoting, the merge was a clean fast-forward of my own lane). Coord task #36.

## 1. PLANNING

**In the owner's words.** The game page gets a short "News" list: the latest few headlines about either team, each with
where it came from and how old it is, and a link to the story when the link is safe. No news shows one plain sentence.

**Goal (god d6b47e).** The game page shows that game's latest news from `GET /api/news?game_id=...`, per the ROUTE
CONTRACT in `docs/gauntlet/logs/step-8g-server.md` (read, not re-derived), including Dwight's screen notes L5, L6, L10, N1.

**What the API serves (contract, `api-types.ts` on `f12bb90`).** `NewsOut {game_id, items: NewsItemOut[]}`, at most 5,
newest first; `NewsItemOut {title (<=200, plain text, no < or >), source ("ESPN"|"CBS Sports"), published_at|null,
url|null (null = unsafe link), tags (coach|injury|playcaller|trade)}`. `items: []` when there is no news, also when every
feed is blocked or the worker is off. 401/404/422 as usual. The typed client has no `news` function yet (lane web adds
it to `packages/shared/src/client.ts`, our file).

**Done when.** The spec below holds in `apps/web/e2e/news8g.spec.ts` on a fresh build; typecheck 0; Dwight PASS; a fresh
critic PASS; lane-guard clean apart from the new files god adds to lane web; the full suite on PR CI (D71).

**Tier T2** (new user-facing behaviour, no API change). Prior decisions: D71 (PR CI is the full gate); CLAUDE.md (missing
stays missing; no prediction logic in the client); the contract's screen notes. The 18j lesson: a new field read on a
screen must survive an old cached reply. News is a new query with its own key, so an old cache simply has no entry.

**Pre-flight.** (1) Problem: news is fetched since 8g server but the owner cannot see it. (2) Why now: the route landed.
(3) Scope: one section on the game page; cut: the stale badge (needs `ingestion_runs` freshness in schemas/views;
carried), news on the week board, any summary. (4) Success signal: the owner reads a game's headlines on the iPhone
(qualitative). (5) Reversibility: two-way (UI only).

**Assumptions.** validated: shape and nullability (contract and generated types); the e2e seed holds no news rows
(`tests/e2e_seed.py` has none), so the real reply for a seeded game is `items: []`. assumed: five one-line titles fit at
320 px when wrapped (design critic checks). unknown: none.

**Instrumentation.** None: UI only. N/A.

**Skills.** grep pinned the seams: `useGame`/`keys` (`lib/queries.ts`, `client.ts`), `SECTIONS` (`game-view.tsx`),
`Section`/`Chip`/`ErrorState` (`ui.tsx`), `ago` (`format.ts`). `/jevgrep`: N/A, no behavioural question open. TDD:
Playwright at the page, as 18j. `/ponytail` in every work order. Design Gauntlet: applies. `harness-engineering`: N/A.

**Test data.** Tests either use the real reply (empty for the seed) or rewrite `/api/news` in the browser with a reply
typed `components["schemas"]["NewsOut"]`. Made-up headlines, no real names, no real feed fetch.

## 2. SPECIFICATION (frozen before production code)

Game page, a "News" section `id="news"`, tab "News" in the Sections row after "Injuries", data from
`GET /api/news?game_id=<id>` (client `api.news(gameId)`, query key `["news", gameId]`):
- N1 With items: one list entry per item in the API's order. Each shows the title as text, then the source, the age
  from `published_at` ("3h ago") and the tags as chips. When `published_at` is null, no age is shown (never "never").
- N2 A link only when safe: when `url` is set and starts with `https://`, the title is a link to exactly that url, with
  `target="_blank"` and `rel="noopener noreferrer"`. When `url` is null (or anything else, such as `javascript:`), the
  title is plain text and the item has no link at all.
- N3 Text only: a title holding a literal `&lt;b&gt;` shows those characters; no element is created from it.
- N4 No items: the section says "No news for this game yet." and shows no list (the real server reply for the seed).
- N5 The request fails: the section shows "Could not load news" and the rest of the game page still works.
- N6 No serious or critical axe finding in `#news`; no sideways scroll at 393 px and 320 px with five long titles.

Gate: `apps/web/e2e/news8g.spec.ts` (new) on a fresh build, typecheck 0; PR CI runs the full suite (D71).

**Red (`s8g-red-1`, fresh build of `9981e74`): 5/5 fail for the intended reason**: `locator('#news')` not found. In
N4 the real server checks before the page passed (`/api/news` 200, `items: []`). Before-screenshots: the game page on
`f12bb90` is the 18j `after2-game-*` set (same main; no change since), `~/.claude/plans/nfl-pickem-lanes-logs/step-18j/`.

## 3. IMPLEMENTATION
- WO1 (`evidence/wo-1.md`, try 1): Ryan reported at 03:57 UTC. The diff kept to the 4 allowed files and
  matched the order. Typecheck 0. `s8g-green-1` (fresh build of news8g and phone-layout): **18 passed**. Committed `91da4a9`.
- Design Gauntlet: after-screenshots at 393 and 1280 (`~/.claude/plans/nfl-pickem-lanes-logs/step-8g-web/after-*`). A fresh
  design critic reviewed them; report and triage in `evidence/reviews/design-1.md`. 1 MUST (link colour) and 2 SHOULDs
  taken. Tests first: `s8g-red-2`, N1 fails on the link class. WO2.
