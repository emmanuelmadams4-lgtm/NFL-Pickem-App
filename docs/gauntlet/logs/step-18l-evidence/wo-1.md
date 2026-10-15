# CODEX WORK ORDER 1 — step 18l: value ratings in the game reply and on the game page

Try 1 of 2. Baseline: branch `lane/web` at `9e22441` (red committed).

GOAL: make `backend/tests/test_value_api.py` (A1-A7) and `apps/web/e2e/value18l.spec.ts` (W1-W6) pass. Spec:
`docs/gauntlet/logs/step-18l.md` §2. Read both test files first.

ALLOWED FILES (nothing else):
- `backend/nflpi/api/schemas.py`: ADD `ValueRatingOut` and `GameDetail.value_ratings: list[ValueRatingOut] = []`. No other change.
- `backend/nflpi/api/readmodels.py`: ADD the fill code (one small helper + one line in `game_detail`). No other change.
- `packages/shared/openapi.json`, `packages/shared/src/api-types.ts`: only via `npm run gen:api` (never by hand).
- `apps/web/components/game/value.tsx` (new), `apps/web/components/game/game-view.tsx` (one SECTIONS entry + the section).
`backend/nflpi/value/**` and `nflpi/picks/**` are READ-ONLY.

REQUIRED BEHAVIOUR, API:
- `ValueRatingOut`: market_type Literal["moneyline","spread","total"], selection str, sportsbook str, line float|None,
  price float, observed_at datetime, status Literal["RATED","UNRATED","NO_BET"], stars int|None, expected_value float,
  reasons list[str], note str.
- Fill: `now = now_utc()` (the module function, so tests can patch it). Empty list when there is no prediction or
  `now >= g.kickoff_utc`. Use the newest prediction (`last`). For each market in ("moneyline","spread","total"):
  `value.load_snapshots(session, game_id, market, as_of=now)`; for each snapshot build `SettlementProbs` and call
  `value.rate_price(snapshot, probs, now=now)`:
  - moneyline: home win = last.home_win_prob, push 0, loss = 1 - win; away the mirror.
  - spread: only when `sim = last.features.get("simulation")` exists and `snapshot.line == sim["home_spread"]`;
    home = (home_cover, spread_push, away_cover), away = (away_cover, spread_push, home_cover).
  - total: only when sim exists and `snapshot.line == sim["total"]`; over = (over, total_push, under), under the mirror.
  - A snapshot that does not qualify is left out. Also skip when any needed chance is None.
  - Map ValueRating -> ValueRatingOut: status/stars/expected_value/reasons from `.advice`, the rest from the rating.

REQUIRED BEHAVIOUR, WEB (`value.tsx`, `ValueSection({ game })`, modelled on `simulation.tsx` / `news.tsx`):
- `<Section id="value" title="Value">`; first a line "Ratings are not yet shown to beat the market." (text-sm text-subtle).
- `const ratings = game.value_ratings ?? [];` (an old cached reply has no key). Empty -> "No book prices to rate for this game."
- Else a `ul`, one `li` per rating: market (moneyline "Win", spread "Spread", total "Total"); side: moneyline home/away
  -> team abbr; spread home -> `${home.abbr} ${signed(line)}`, away -> `${away.abbr} ${signed(-line)}` (e.g. -3.5 / +3.5);
  total -> "Over 47.5" / "Under 47.5"; price signed ("+120", "-140"); the book; status: UNRATED "Unrated", NO_BET
  "No bet", RATED `${stars} of 5 stars`; "Expected value " + signed whole percent ("+32%", "-10%"); reasons in words:
  STALE_PRICE "price too old to rate", NONPOSITIVE_EV "no value at this price", NO_VALIDATION_HISTORY "not yet shown to
  beat the market", QB_MISSING "starting quarterback unknown", BELOW_FIRST_THRESHOLD "value below the first star", any
  other code shown as is; then the server `note` word for word (text-xs text-subtle). Text only, never HTML.
- Never write the word "available". Use the app's existing tokens and components (Section, Chip if useful); no new CSS.
- `game-view.tsx`: `{ id: "value", label: "Value" }` after simulator, and `<ValueSection game={game} />` after the
  simulator section.

PROOF: `cd backend && DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15436/nflpi_test APP_ACCESS_TOKEN=test-token uv run pytest tests/test_value_api.py tests/test_value.py -q`,
`uvx ruff check nflpi tests`, `npm run gen:api && npm run typecheck`. The coordinator reruns these and the browser specs.
CONSTRAINTS: /ponytail: smallest diff, no new dependency, no migration, no odds call, no test edits. Do not commit.
Send the hive report as soon as the edit is done.
