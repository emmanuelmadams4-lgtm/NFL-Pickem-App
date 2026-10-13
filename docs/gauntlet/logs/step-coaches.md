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
| LV | "Klint Kubliak" (typo) | Klint Kubiak | https://www.nfl.com/news/klint-kubiak-confi... (Wikipedia ref), https://www.kold.com/2026/02/10/las-vegas-raiders-confirm-klint-kubiak-head-coach-silver-black |

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

* Provider Codex, `gpt-6-luna` low, try 1 of 2, no climbs (`BUILD_RUNG: gpt-6-luna`, `CLIMBS: none`). Work order 1 (`nflverse.py`, `service.py` only). Codex could not reach the database or PyPI from its sandbox (expected), so the coordinator reran every proof.
* Coordinator found two faults and fixed them before the commit: C4's test loaded no games first (my test bug, not Codex's: failed for "no games loaded" instead of the ESPN error), and four test lines over the 120-column ruff limit.
* Commit `549f18d`. Coach tests 3/3 green after the fix (the fourth, C1, was among them: `3 passed` in the `-k coach` selection plus the stale-name test in the full run).
* Jev/model pick: skipped `decide.sh` (Jev call not needed for one small order; luna low is the Build Ladder default for known call sites). Recorded here as the reason.

## 4. CLEANUP

* `/refactor` scope-locked to `ingest_head_coaches`: the inner loop had a `team_side is Game.home_team` conditional twice; rewritten to loop over `"home"` and `"away"` with `getattr`. Behaviour identical. Work order 2 to Codex luna low, commit `refactor: head coach overlay loops over side names`. No other simplification: `fetch_head_coaches` is 15 lines, one network helper shared with `fetch_csv`.

## 5. VERIFICATION

(filled below after the runs)

## 6. LANDING

Not done by this lane. God lands it. Nothing was pushed, deployed or merged. Wave 5 notes for god: none needed for correctness (the API already serves `games.home_coach`).
