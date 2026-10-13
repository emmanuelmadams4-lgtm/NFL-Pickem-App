# Reader report: nflreadpy

Read-only inspection by a subagent on 2026-10-13 (nothing in the repository was run, imported or installed). The coordinator checked the commit and the license against the clone; other claims are the reader's, cited to files in that clone.

1. COMMIT: `e7e87b2ef626b8672279db25432b1554ee13348a 2026-09-09T19:52:39Z`

2. LICENSE: `LICENSE.md`, first line "MIT License". `pyproject.toml:8` says `license = "MIT"`, and the classifier at line 20 is "OSI Approved :: MIT License".

3. VERIFIED CAPABILITIES (all paths under `src/nflreadpy/`)
- Public loaders are exported in `__init__.py:18-37`. I read the dataset path in each loader file.

| Function | Dataset path read |
|---|---|
| `load_schedules` | `schedules/games` (`load_schedules.py:30`) |
| `load_injuries` | `injuries/injuries_{season}` (`load_injuries.py:49`) |
| `load_snap_counts` | `snap_counts/snap_counts_{season}` (`:49`) |
| `load_player_stats` / `load_team_stats` | `stats_{player\|team}/stats_{...}_{level}_{season}` (`load_stats.py:51`) |
| `load_players` | `players/players` (`:30`) |
| `load_teams` | `teams/teams_colors_logos` (`:22`) |
| `load_pbp` | `pbp/play_by_play_{season}` (`:46`) |
| `load_rosters` | read, but I did not capture its path string |
| `load_rosters_weekly` | `weekly_rosters/roster_weekly_{season}` (`:49`) |
| `load_participation` | `pbp_participation/pbp_participation_{season}` (`:55`) |
| `load_nextgen_stats` | `nextgen_stats/ngs_{stat_type}` (`:57`) |
| `load_officials` | `officials/officials` (`:30`) |
| `load_draft_picks` | `draft_picks/draft_picks` (`:33`) |
| `load_combine` | `combine/combine` (`:31`) |
| `load_contracts` | `contracts/historical_contracts` (`:25`) |
| `load_trades` | `trades/trades` (`:24`) |

- Other loaders: `load_depth_charts`, `load_ftn_charting`, `load_pfr_advstats`, and the ffverse loaders (`load_ff_playerids`, `load_ff_rankings`, `load_ff_opportunity`). The ffverse ones read from dynastyprocess and ffopportunity.
- Download: `requests.Session().get(url, timeout, stream=True)` (`downloader.py:25,66`). It has no retry logic.
- Base URL is the `nflverse-data` GitHub releases download path (`downloader.py:17-22`). Other bases are espnscrapeR-data, dynastyprocess and ffopportunity.
- Default format is `.parquet` (`downloader.py:36-48,105`). CSV is used only when a loader asks for it.
- Return type is a Polars DataFrame (`downloader.py:50,107`). The README says to call `.to_pandas()` for pandas, and the `pandas` extra is optional (`pyproject.toml:37-39`).
- Cache modes are memory (the default), filesystem and off (`config.py:13-24,67`). Filesystem writes Parquet (`cache.py:~158`). The default TTL is 86400 s (`config.py:79-83`).
- Env vars: `NFLREADPY_CACHE`, `_CACHE_DIR`, `_CACHE_DURATION`, `_VERBOSE`, `_TIMEOUT` (default 30 s) and `_USER_AGENT` (`config.py:45-52`).
- `schedules/games` is downloaded in full, then filtered by season in memory (`load_schedules.py:30-40`).
- Seasons are validated, with a 2009 lower bound for injuries (`load_injuries.py:42`).

4. DEPENDENCIES (`pyproject.toml:33-40`)
- Python `>=3.10`.
- Six runtime dependencies: `requests>=2.33.0`, `polars>=0.20.0`, `platformdirs>=3.0.0`, `tqdm>=4.64.0`, `pydantic>=2.0.0`, `pydantic-settings>=2.0.0`.
- Optional extra: `pandas>=1.5.0`.
- pyarrow is not a dependency.
- Polars is the one large wheel. The rest are small, and our app already has pydantic, pydantic-settings and requests.

5. NOT FOUND
- Odds history and as-of snapshots: grepping `src` for odds, moneyline, spread_line, weather and temp found no code. The only hit was a config description.
- Weather forecasts: none.
- No retry or backoff in the downloader.
- No ESPN scoreboard or coach loaders.
- It does not return plain dicts.
- No per-asset freshness or ETag check. Staleness is controlled only by the TTL.

6. COMPARISON
- Our `fetch_csv(path)` and `_fetch` (`nflverse.py:57-78`) could be replaced for these requests (callers at `service.py` lines 120, 169, 194, 253-255, and `jobs.py:67`):

| Our request | nflreadpy equivalent |
|---|---|
| `schedules/games.csv` | `load_schedules` |
| `teams/teams_colors_logos.csv` | `load_teams` |
| `injuries/injuries_{season}.csv` | `load_injuries` |
| `snap_counts/snap_counts_{season}.csv` | `load_snap_counts` |
| `stats_player/stats_player_week_{season}.csv` | `load_player_stats` (week level assumed from the path pattern) |
| `players/players.csv` | `load_players` |
| `stats_team/stats_team_week_{season}.csv` (step-14 and 14b logs) | `load_team_stats` |
| `pbp/play_by_play_{season}.csv.gz` (`ideas.py:56`) | `load_pbp` |

- Not replaceable: `fetch_json`, `fetch_head_coaches` and the ESPN URLs (`nflverse.py:26-27,81-116`).
- The parsers (`parse_games`, `parse_teams`, `parse_injuries` and so on) also stay. They do franchise mapping, kickoff UTC conversion and validation. They expect `list[dict[str, str]]`, with `""` or `"NA"` for missing values (`_num` and `_int`, `nflverse.py:119-124`). nflreadpy returns typed Polars data with nulls, so each call would need `.to_dicts()` or an adapter, and the parsers' string handling would need changing.
- Columns: both read the same nflverse release files, but nflreadpy renames none of them. `parse_games` reads `home_moneyline`, `spread_line`, `total_line`, `home_qb_name`, `temp`, `wind` and others (`nflverse.py:138-180`). Matching names are UNVERIFIED because I did not read the file schemas. Behavior differs in one place: `load_schedules` nulls `roof` values outside dome, outdoors, closed or open (`load_schedules.py:43-50`).
- Our `backend/pyproject.toml` has pandas>=3.0, requests, httpx, pydantic and pydantic-settings. polars and pyarrow are not dependencies. Adopting nflreadpy adds polars, platformdirs and tqdm.
- Caveat: nflreadpy would not preserve our own retry/backoff or the `nflverse_base` setting. It would also add a GitHub-releases dependency on `.parquet` rather than `.csv`.

7. FRESHNESS
- `README.md:141-142` and `docs/index.md:76` only point to the external nflreadr "nflverse_data_schedule" page for update times. The repo states no cadence itself. The default local cache is 24 h (`config.py:79`).
