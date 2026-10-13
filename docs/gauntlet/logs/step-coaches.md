# Step coaches: wrong head coach names (defect, owner 2026-10-13)

Lane `coaches`, branch `lane/coaches`, base `d88d74e`, coord task #14, tier T1. Coordinator Creed (hive `worker-coaches`).
Owner's words: "some of the team news and coaching rosters are wrong like sean micdermot is not the coach of the bills".

## 1. PLANNING

* **Where every coach name comes from.** One place only: `games.home_coach` / `games.away_coach`, loaded from nflverse `games.csv` by `ingestion/nflverse.py::parse_games` and `service.py::upsert_games`. `views.py` (game screen, "Head coach" row) and `analytics/trends.py` (`coach_vs_team`) read those columns. No hard-coded name list exists anywhere (grep of `backend`, `apps`, `packages`). `analytics/play_callers.py` is an empty table (no feed exists; nothing wrong is shown). No coordinator or staff names are stored or shown anywhere, so there is nothing else to correct.
* **Which are wrong.** The nflverse 2026 rows carry last season's coach for clubs that changed, and one typo, even on games already played (week 1 to 4 show McDermott for BUF). Hand check of all 32 against ESPN's 2026 season coach list and Wikipedia's "List of current NFL head coaches" (full table: `step-coaches-evidence/check32-2026-10-13.md`, produced by `check32.py`):

| Club | nflverse feed says | Actual 2026 head coach | Sources (read 2026-10-13) |
|---|---|---|---|
| BUF | Sean McDermott | Joe Brady | Bills release (McDermott relieved Jan 19, 2026): https://www.buffalobills.com/news/buffalo-bills-announce-sean-mcdermott-has-been-relieved-of-his-duties-as-head-coach ; https://www.buffalobills.com/news/joe-brady-agrees-to-terms-to-be-the-next-buffalo-bills-head-coach |
| ATL | Raheem Morris | Kevin Stefanski | https://www.espn.com/nfl/story/_/id/47646376/matt-ryan-atlanta-falcons-hire-kevin-stefanski-new-coach |
| ARI | Jonathan Gannon | Mike LaFleur | https://www.azcardinals.com/news/cardinals-choose-mike-lafleur-as-new-head-coach-2026 |
| LV | "Klint Kubliak" (typo) | Klint Kubiak | AP via https://lasvegassun.com/news/2026/feb/09/raiders-officially-hire-klint-kubiak-as-head-coach/ , https://www.kold.com/2026/02/10/las-vegas-raiders-confirm-klint-kubiak-head-coach-silver-black |

  The other 28 clubs match in all three places (ESPN, Wikipedia, nflverse). Wikipedia list: https://en.wikipedia.org/wiki/List_of_current_NFL_head_coaches . ESPN feed: `https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/teams/{id}/coaches`.
* **Direction check (owner's words).** Builds: the head coach shown on a game, and used for "record under this coach", is correct and stays correct as clubs change coaches. Replaces: trusting nflverse alone for the current season. Not: coordinator or play-caller data (no feed, table stays empty), API or web changes, and "team news" (the news lane).
* **Product Mode (T1).** Assumptions: `validated` the wrong names are in the feed (rows above, played games included); `validated` ESPN lists one coach for each of the 32 clubs for 2026; `assumed` ESPN's name spelling equals nflverse's for returning coaches (true for all 28 matching clubs today); `assumed` a club that fires a coach mid-season lists two coaches on ESPN. Reversibility: two-way. Revisit trigger: ESPN changes the endpoint or the check script shows a mismatch.
* **Prior decisions read.** `docs/gauntlet/STATE.md` constraints, step-12 log (coach and play-caller records are name-matched; play-caller table ships empty by owner decision HAG-9, revisit when the owner says so). CLAUDE.md data rules: missing stays missing; a failed ingestion keeps old data and is logged.
* **Seams.** The word "team news" and coaching rosters shown in the web: none stored, nothing to fix here. SEAM report for god (not done by this lane): `freshness()` has a fixed dataset list in `ingestion/service.py` (mine) feeding `/api` freshness (not mine); I did not add `head_coaches` to it so the API shape is unchanged. If the owner wants a stale-coaches banner, that is wave 5.
* Skills: `/jevgrep` not used (small repo, exact lookups with grep; recorded). `/graft` N/A (not installed in this session; grep used). No Design Gauntlet (no UI).

## 2. SPECIFICATION (frozen)

| ID | Clause | Test (`backend/tests/test_data.py`) |
|---|---|---|
| C1 | `fetch_head_coaches(season)` returns club code to full name from ESPN's team list and per-team season coach list, mapping ESPN codes to ours (LAR to LA, WSH to WAS), and skips a club that does not list exactly one coach | `test_head_coaches_come_back_under_our_club_codes_and_skip_clubs_with_two_listed` |
| C2 | After a schedule load, every game of the newest season (played or not) has the ESPN coach for that club; other clubs and older seasons keep the feed names; an `ingestion_runs` row (source `espn`, dataset `head_coaches`) is `ok` with a row count | `test_current_season_coaches_are_replaced_and_other_seasons_are_left_alone` |
| C3 | A second schedule load (which rewrites names from nflverse) does not bring the stale name back | `test_a_second_schedule_load_does_not_bring_the_stale_name_back` |
| C4 | A failed ESPN call is logged as a failed run and the feed names stay; the schedule load itself is unaffected | `test_a_failed_coach_feed_keeps_the_feed_names_and_is_logged` |

* Offline schedule loads (tests, `rows` passed) do not call ESPN unless `head_coaches` is passed.
* Operational layer: the run is visible in `ingestion_runs` (source `espn`). User-facing layer: hand check below (the real feed gives Joe Brady for BUF).
* Red: commit `948c610`, `step-coaches-evidence/red-1.log`: `AttributeError: module 'nflpi.ingestion.nflverse' has no attribute 'fetch_head_coaches'` (the intended reason).
* Gate: `cd backend && uv run pytest -q && uvx ruff check nflpi tests migrations && uv run alembic check`; `npm run gen:api` no drift (no API change in this lane); hand check `check32.py`. Test database: own container `nflpi-lane-coaches-db`, `127.0.0.1:15443`.

## 3. IMPLEMENTATION

* Provider Codex, `gpt-6-luna`, no climbs (`CLIMBS: none`), 3 work orders + 1 cleanup order, each with two tries available, none needed. Codex cannot reach the database or PyPI from its sandbox (expected), so the coordinator reran every proof. EFFORT: spec and review `high` (coordinator), luna `low`, work order 4 `medium` (many clauses). Jev/`decide.sh` was not called: all picks are the Build Ladder default rung for known call sites, recorded here as the reason.
* WO-1 `549f18d`: `fetch_head_coaches`, `ingest_head_coaches`, overlay after each schedule load. Coordinator fixed two faults of its own tests (C4's test loaded no games; four lines over 120 columns).
* Dwight's security review (`dwight-mv5mkpow`, at `f2290d4`): no CRITICAL, no HIGH; three MEDIUM security (C1 link host, C2 name cleaning, C3 id digits) and functional points C4 to C7, L1 to L4. Red tests first (`f2290d4`, `41ab752`, then `step "review findings"` commit), then WO-3 `209a23d` (host pin, 64 limit) and WO-4 `dff233b`:

| Finding | Outcome |
|---|---|
| C1 link host | fixed: https scheme, exact host `sports.core.api.espn.com`, no userinfo, port none or 443, ESPN calls do not follow redirects; tests `plain_https`, `another_host` |
| C2 names | fixed: both parts must be text, control characters dropped, spaces collapsed, at most 64; tests `not_text`, `not_digits` (cleaning) |
| C3 team id | fixed: digits only |
| C4 skipped clubs | fixed as a floor: fewer than 30 clubs fails the run and keeps the feed names (`too_few`); a club with 0 or 2 coaches is skipped |
| C5 `jobs.py` reports ok when ESPN failed | NOT done: `jobs.py` is not this lane's. SEAM for god: `ingest_schedules` returns the schedules run, the head-coach run is its own row in `ingestion_runs` (source `espn`). If god wants it in the job exit code, wave 5 reads `ingestion_runs` |
| C6 finished games rewritten | kept on purpose and stated: nflverse carries the old name into already played 2026 games (BUF weeks 1 to 4), so the rewrite is the fix; a mid-season replacement lists two coaches on ESPN and is skipped (feed names stay). Needs god's confirmation (Dwight asked) |
| C7 load | fixed: 6 hour in-process cache (`at_most_once`), User-Agent sent |
| L1 L2 L3 | fixed: error text shows host and path only; first 40 clubs read; shape errors name the club. L4 (`max(season)` can be next year after the new schedule is published): not done, noted |

* Delta sent to Dwight for a second look (outbox `dwight-delta.json`).

## 4. CLEANUP

* Round 1, `/refactor` scope-locked to `ingest_head_coaches`: side loop over `"home"`/`"away"` instead of a column identity test (WO-2, luna low). Round 2, after the review fixes: `fetch_head_coaches` had grown past 40 lines with deep nesting, so `_is_espn_link` and `_clean_name` were extracted (WO-5 `5d07b32`, behaviour identical, `test_data.py` + `test_trends.py` 36 passed). Nothing else touched.

## 5. VERIFICATION

* Commit under test `5d07b32`. Machine rule from god: `res:gate` held by this lane for the full runs (coord lock taken, released after).
* Gate run 1 and run 2 back to back (`step-coaches-evidence/gate-run1.log`, `gate-run2.log`): `183 passed in 50.34s`, `183 passed in 48.36s`; `uvx ruff check nflpi tests migrations`: `All checks passed!` both; `alembic upgrade head` on a scratch database then `alembic check`: `No new upgrade operations detected.` both (the test database is built with `create_all`, so `alembic check` needs its own migrated database, `nflpi_alembic`). `npm run gen:api`: no diff in `packages/` or `apps/` (`gen-api.log`). The red-to-green history is in the commits (`948c610` red, `549f18d` green).
* Hand check (the scope named it), `handcheck-live-fetch.log`: the real nflverse download and the real ESPN feed through the new code into a scratch database: `schedules ok 842`, `head_coaches ok 68` (4 clubs x 17 games), BUF `{'Joe Brady'}`, ATL `{'Kevin Stefanski'}`, ARI `{'Mike LaFleur'}`, LV `{'Klint Kubiak'}`, and 2025 BUF stays `{'Sean McDermott'}` (past seasons untouched). Production path with no injected names: `ok 0` (nothing left to change).
* `lane-guard.py check lanes.md coaches d88d74e`: `OK` (`lane-guard.log`).
* **Fresh critic** (`ecc:code-reviewer`, no build transcript, HEAD `a21d941`): reran the gate itself under `res:gate`: `183 passed in 48.41s`, ruff `All checks passed!`. C1 to C4 and every hardening clause PASS, each with a named test that fails when the clause is broken; evidence log complete; file scope holds. **VERDICT: PASS.** Advisory, carried: cache expiry untested; real fetch path covered only by the live hand check; `max(season)` can be next year (L4); `jobs.py` blind to `head_coaches` (C5); exact 64/65 length boundary untested.
* **Dwight** (security, `dwight-mv5mkpow`) at `5d07b32`: **PASS**, no CRITICAL, HIGH or MEDIUM security finding. Carried LOW/MEDIUM advice, not built: S1 `_fetch` error text still carries `last_error` (for a redirect, httpx puts the Location in it); S2 `isdigit()` accepts Unicode digits (add `isascii()`); S3 invisible non-control characters in names pass; F1 skipped clubs leave no trace when 30 or 31 clubs return; F2 a cached run is logged `ok` like a fresh fetch; F3 a real coach change can show up to 6 hours late; F4 no back-off after an ESPN failure (retries on every schedule load). Any of these needs a new small step and a new critic.
* **Jev Job 4** not run: it is a paid OpenRouter call and this session may not make one. Pass rests on green gates twice, the critic PASS and Dwight PASS.

## 6. LANDING

Not done by this lane (no push, PR, merge or deploy). God lands it.

## Carried / for god

1. C5: `jobs.py` and the API freshness list know nothing about the `head_coaches` dataset. Not added to `STALE_HOURS`, so the API shape is unchanged. Failed ESPN runs are visible only in `ingestion_runs`.
2. C6: finished games of the season are rewritten (see above). Confirm with the owner.
3. The web "Head coach" row (`apps/web/components/game/team-compare.tsx`) and `api/views.py` read `games.*_coach` unchanged; no edit there was needed, the names are fixed at the source.
4. Play callers: still no feed and the table is empty (owner decision HAG-9); nothing wrong is shown. Coordinators and other staff are not stored anywhere in the app. If the owner wants those, it needs a feed or a sourced table first: a new step.
5. "Team news" is the news lane (8c), not this defect.
6. Wikipedia and ESPN both listed one coach per club on 2026-10-13; re-run `check32.py` before the next season starts.
