"""Coverage report per feed. Reads tables handed in, or public nflverse files through an injected fetch function.

Never opens the live database; writes no files. ``python -m nflpi.data.coverage --seasons 2026`` fetches the public
files and prints a markdown table to stdout.
"""

import argparse
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

import pandas as pd

from nflpi.data.asof import AsofTables
from nflpi.ingestion import nflverse

Fetch = Callable[[str], list[dict[str, str]]]
SCHEDULE_PATH = "schedules/games.csv"
MISSING_TOKENS = ("NA", "")


@dataclass(frozen=True)
class FeedCoverage:
    name: str
    rows: int
    seasons: list[int]
    rows_per_season: dict[int, int]
    latest: str | None
    missing: dict[str, float]
    notes: list[str] = field(default_factory=list)


def _iso(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def coverage_for(
    name: str,
    df: pd.DataFrame,
    key_columns: list[str],
    time_column: str | None = None,
    season_column: str = "season",
) -> FeedCoverage:
    notes: list[str] = []
    rows_per_season: dict[int, int] = {}
    if season_column in df.columns:
        seasons = pd.to_numeric(df[season_column], errors="coerce").dropna().astype(int)
        rows_per_season = {int(s): int(n) for s, n in seasons.value_counts().sort_index().items()}
    latest = None
    if time_column and time_column in df.columns and len(df):
        latest = _iso(pd.to_datetime(df[time_column], utc=True).max())
    missing: dict[str, float] = {}
    for c in key_columns:
        if c not in df.columns:
            missing[c] = 1.0
            notes.append(f"column {c} is absent")
            continue
        blank = df[c].isna() | (df[c].astype(object) == "")
        missing[c] = float(blank.mean()) if len(df) else 0.0
    return FeedCoverage(name, len(df), sorted(rows_per_season), rows_per_season, latest, missing, notes)


def _with_season(df: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "game_id" not in df.columns or "season" not in games.columns:
        return df
    return df.assign(season=df["game_id"].map(games.set_index("game_id")["season"]))


def report_from_tables(tables: AsofTables) -> dict[str, FeedCoverage]:
    games = tables.games
    return {
        "games": coverage_for("games", games, ["home_score", "home_qb", "temp_f"], "kickoff_utc"),
        "lines": coverage_for(
            "lines",
            _with_season(tables.snapshots, games),
            ["home_moneyline", "spread_line", "total_line"],
            "observed_at",
        ),
        "quarterbacks": coverage_for(
            "quarterbacks", _with_season(tables.qb_observations, games), ["qb"], "observed_at"
        ),
        "injuries": coverage_for("injuries", tables.injuries, ["player_id", "report_status"], "observed_at"),
        "weather": coverage_for(
            "weather", _with_season(tables.weather, games), ["temp_f", "wind_mph", "precip_prob"], "observed_at"
        ),
    }


def _frame(rows: list[dict[str, str]]) -> pd.DataFrame:
    return pd.DataFrame(rows).replace(list(MISSING_TOKENS), pd.NA)


def _schedule_coverage(fetch: Fetch, seasons: list[int]) -> FeedCoverage:
    try:
        df = _frame(fetch(SCHEDULE_PATH))
    except Exception as exc:  # recorded in the feed's notes, never raised
        return FeedCoverage("schedule", 0, [], {}, None, {}, [f"fetch failed ({SCHEDULE_PATH}): {exc}"])
    df = df[pd.to_numeric(df["season"], errors="coerce").isin(seasons)]
    cov = coverage_for("schedule", df, ["home_score", "home_moneyline", "home_qb_name", "away_qb_name"], "gameday")
    notes = list(cov.notes)
    for s in cov.seasons:
        part = df[pd.to_numeric(df["season"], errors="coerce") == s]
        done = part[part["home_score"].notna()]
        qb = part["home_qb_name"].notna() & part["away_qb_name"].notna()
        last = done["gameday"].max() if len(done) else None
        notes.append(
            f"{s}: {len(part)} games, {len(done)} finished, last finished kickoff date {last}, "
            f"{int(part['home_moneyline'].notna().sum())} with a moneyline, {int(qb.sum())} with both quarterback names"
        )
    return FeedCoverage(cov.name, cov.rows, cov.seasons, cov.rows_per_season, cov.latest, cov.missing, notes)


def _per_season_coverage(name: str, template: str, fetch: Fetch, seasons: list[int], keys: list[str]) -> FeedCoverage:
    frames, notes = [], []
    for s in seasons:
        path = template.format(season=s)
        try:
            frames.append(_frame(fetch(path)).assign(season=s))
        except Exception as exc:  # recorded in the feed's notes, never raised
            notes.append(f"{s}: fetch failed ({path}): {exc}")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    cov = coverage_for(name, df, keys if len(df) else [])
    return FeedCoverage(
        cov.name, cov.rows, cov.seasons, cov.rows_per_season, cov.latest, cov.missing, cov.notes + notes
    )


def report_from_nflverse(seasons: Iterable[int], fetch: Fetch = nflverse.fetch_csv) -> dict[str, FeedCoverage]:
    wanted = sorted(set(seasons))
    return {
        "schedule": _schedule_coverage(fetch, wanted),
        "injuries": _per_season_coverage(
            "injuries", "injuries/injuries_{season}.csv", fetch, wanted, ["gsis_id", "report_status", "team"]
        ),
        "team_stats": _per_season_coverage(
            "team_stats", "stats_team/stats_team_week_{season}.csv", fetch, wanted, ["team", "week"]
        ),
    }


def render_markdown(report: dict[str, FeedCoverage], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        "| Feed | Rows | Seasons | Latest | Missing (key columns) | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for key, cov in report.items():
        seasons = f"{cov.seasons[0]}-{cov.seasons[-1]}" if cov.seasons else "none"
        missing = ", ".join(f"{c} {f:.0%}" for c, f in cov.missing.items()) or "n/a"
        notes = "<br>".join(cov.notes).replace("|", "/") or ""
        lines.append(f"| {cov.name or key} | {cov.rows} | {seasons} | {cov.latest or 'n/a'} | {missing} | {notes} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Print the nflverse feed coverage as markdown.")
    parser.add_argument("--seasons", type=int, nargs="+", required=True)
    args = parser.parse_args(argv)
    print(render_markdown(report_from_nflverse(args.seasons), f"nflverse coverage {args.seasons}"))


if __name__ == "__main__":
    main()
