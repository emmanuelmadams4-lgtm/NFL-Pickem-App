# Data coverage report (step 18e)

Produced by `python -m nflpi.data.coverage --seasons 2026` (`backend/nflpi/data/coverage.py`) on 2026-10-14, from the **public nflverse release files only**. The live database was not opened. The same module reads the app's tables from a session you give it (`report_from_tables`); it was run on synthetic fixtures in tests, never on live data.

## nflverse files, season 2026

| Feed | Rows | Seasons | Missing (key columns) | Notes |
|---|---|---|---|---|
| schedule (`schedules/games.csv`) | 272 | 2026 | home_score 71%, home_moneyline 61%, home_qb_name 66%, away_qb_name 66% | 79 finished, last finished kickoff date 2026-10-12, 107 with a moneyline, 93 with both quarterback names |
| injuries (`injuries/injuries_2026.csv`) | 1,428 | 2026 | gsis_id 0%, report_status 58%, team 0% | no per-row clock in the file |
| team stats (`stats_team/stats_team_week_2026.csv`) | 158 | 2026 | team 0%, week 0% | weeks 1 to 5 |

"Latest" in the raw output for the schedule is the last scheduled kickoff of the season (2027-01-10), not the last result. Read the notes column for the last finished game.

## Agreement with `docs/model/PLAN.md` section 4 (checked 2026-10-13)

| Claim in PLAN section 4 | This report (2026-10-14) | Agrees? |
|---|---|---|
| 272 regular-season games, 79 finished, last finished 2026-10-12 | 272, 79, 2026-10-12 | Yes |
| Lines: 79 finished games plus the 28 of weeks 6 and 7 | 107 games with a moneyline (79 + 28) | Yes |
| Quarterback names: 79 finished plus the 14 of week 6 | 93 games with both names (79 + 14) | Yes |
| Team stats: weeks 1 to 5, 158 team rows | 158 rows | Yes |
| Injuries: 1,413 rows, weeks 1 to 5 | 1,428 rows | Differs by 15: the file was updated after the 2026-10-13 check. Not a disagreement about coverage |

## What this report cannot show
* The tables feeds (`games`, `lines`, `quarterbacks`, `injuries`, `weather`) need a database session; none was read here. PLAN's statements on weather forecasts and `market_quotes` stay "not checked" for that reason.
* Play-by-play is not in the report (no loader in the app; the report reads only the three files above).
* Nothing here says a feed is *correct*, only how much of it is present.
