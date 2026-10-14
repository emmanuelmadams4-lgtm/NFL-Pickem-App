"""Input checks for the data layer. Every failure raises DataCheckError naming the check, the column and examples."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import pandas as pd

KNOWN_TEAMS = frozenset(
    "ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB "
    "TEN WAS".split()
)
GAME_COLUMNS = (
    "game_id", "season", "week", "game_type", "kickoff_utc", "home_team", "away_team", "home_score", "away_score",
    "status", "neutral_site",
)  # fmt: skip
SNAPSHOT_COLUMNS = ("game_id", "observed_at", "kind", "home_moneyline", "away_moneyline", "spread_line", "total_line")
WEEK_RANGE = (1, 22)
MAX_PICKEM_MONEYLINE = 125
MIN_MONEYLINE_MAGNITUDE = 100
MAX_EXAMPLES = 5


class DataCheckError(ValueError):
    """A named input check failed."""


@dataclass(frozen=True)
class MissingCount:
    n_missing: int
    n_rows: int
    fraction: float


@dataclass(frozen=True)
class CheckReport:
    rows: int
    seasons: list[int]
    missing: dict[str, MissingCount]
    season_boundaries: dict[int, tuple[str, str]] = field(default_factory=dict)


def _fail(check: str, detail: str, examples: Iterable = ()) -> DataCheckError:
    shown = list(examples)[:MAX_EXAMPLES]
    suffix = f"; examples: {shown}" if shown else ""
    return DataCheckError(f"{check}: {detail}{suffix}")


def require_columns(df: pd.DataFrame, required: Sequence[str], name: str) -> None:
    absent = [c for c in required if c not in df.columns]
    if absent:
        raise _fail("require_columns", f"{name} is missing required column(s) {absent}")


def check_teams(df: pd.DataFrame, known: frozenset[str] = KNOWN_TEAMS) -> None:
    for col in ("home_team", "away_team"):
        bad = sorted({str(v) for v in df[col] if v not in known})
        if bad:
            raise _fail("check_teams", f"column {col} has unknown team code(s)", bad)
    tied = df["home_team"] == df["away_team"]
    if tied.any():
        examples = df.loc[tied, "game_id" if "game_id" in df.columns else "home_team"].tolist()
        raise _fail("check_teams", "home_team equals away_team", examples)


def check_duplicate_games(df: pd.DataFrame) -> None:
    dup_ids = df.loc[df["game_id"].duplicated(keep=False), "game_id"].unique().tolist()
    if dup_ids:
        raise _fail("check_duplicate_games", "duplicate game_id", dup_ids)
    keys = ["season", "week", "home_team", "away_team"]
    twice = df[df.duplicated(keys, keep=False)]
    if not twice.empty:
        raise _fail("check_duplicate_games", f"same {keys} appears twice", twice["game_id"].tolist())


def _is_tz_aware(series: pd.Series) -> bool:
    if isinstance(series.dtype, pd.DatetimeTZDtype):
        return True
    if series.dtype.kind == "M":
        return False
    return bool(len(series)) and all(getattr(v, "tzinfo", None) is not None for v in series)


def check_seasons(df: pd.DataFrame) -> dict[int, tuple[str, str]]:
    """Validate season/week/kickoff_utc; return {season: (first kickoff, last kickoff)} ISO strings."""
    season = pd.to_numeric(df["season"], errors="coerce")
    bad = df.loc[season.isna() | (season % 1 != 0), "season"]
    if not bad.empty:
        raise _fail("check_seasons", "season must be int-like", bad.tolist())
    week = pd.to_numeric(df["week"], errors="coerce")
    low, high = WEEK_RANGE
    off = df.loc[week.isna() | (week < low) | (week > high), "week"]
    if not off.empty:
        raise _fail("check_seasons", f"week must be within {low}..{high}", off.tolist())
    if not _is_tz_aware(df["kickoff_utc"]):
        raise _fail("check_seasons", "kickoff_utc must be tz-aware", df["kickoff_utc"].head(MAX_EXAMPLES).tolist())
    kick = pd.to_datetime(df["kickoff_utc"], utc=True)
    spans = kick.groupby(season.astype(int)).agg(["min", "max"]).sort_index()
    bounds = {int(s): (r["min"].isoformat(), r["max"].isoformat()) for s, r in spans.iterrows()}
    previous_end = None
    for s, row in spans.iterrows():
        if previous_end is not None and row["min"] < previous_end[1]:
            raise _fail(
                "check_seasons",
                f"overlapping seasons: {s} starts {row['min'].isoformat()} before {previous_end[0]} ends "
                f"{previous_end[1].isoformat()}; boundaries {bounds}",
            )
        previous_end = (s, row["max"])
    return bounds


def check_scores_and_status(df: pd.DataFrame) -> None:
    """Scores are non-negative; a final game has both scores; a scheduled game has none."""
    scores = {c: pd.to_numeric(df[c], errors="coerce") for c in ("home_score", "away_score")}
    for col, values in scores.items():
        if (values < 0).any():
            raise _fail("check_games", f"{col} has negative score(s)", df.loc[values < 0, "game_id"].tolist())
    status = df["status"].astype(str).str.strip().str.lower()
    missing = scores["home_score"].isna() | scores["away_score"].isna()
    final_blank = (status == "final") & missing
    if final_blank.any():
        raise _fail("check_games", "status final with a missing score", df.loc[final_blank, "game_id"].tolist())
    scheduled_scored = (status == "scheduled") & ~(scores["home_score"].isna() & scores["away_score"].isna())
    if scheduled_scored.any():
        raise _fail("check_games", "status scheduled with a score", df.loc[scheduled_scored, "game_id"].tolist())


def missing_counts(df: pd.DataFrame, columns: Sequence[str] | None = None) -> dict[str, MissingCount]:
    """Count NaN, None and '' per column. Data, not errors."""
    n = len(df)
    out = {}
    for c in columns if columns is not None else list(df.columns):
        col = df[c]
        blank = col.isna() | (col.astype(object) == "")
        count = int(blank.sum())
        out[c] = MissingCount(count, n, count / n if n else 0.0)
    return out


def check_games(df: pd.DataFrame, known: frozenset[str] = KNOWN_TEAMS) -> CheckReport:
    require_columns(df, GAME_COLUMNS, "games")
    check_teams(df, known)
    check_duplicate_games(df)
    check_scores_and_status(df)
    bounds = check_seasons(df)
    seasons = sorted(bounds)
    return CheckReport(
        rows=len(df), seasons=seasons, missing=missing_counts(df, GAME_COLUMNS), season_boundaries=bounds
    )


def check_snapshots(df: pd.DataFrame) -> None:
    require_columns(df, SNAPSHOT_COLUMNS, "snapshots")
    if not _is_tz_aware(df["observed_at"]) and len(df):
        raise _fail("check_snapshots", "observed_at must be tz-aware", df["observed_at"].head(MAX_EXAMPLES).tolist())
    for col in ("home_moneyline", "away_moneyline"):
        ml = pd.to_numeric(df[col], errors="coerce")
        small = df.loc[ml.notna() & (ml.abs() < MIN_MONEYLINE_MAGNITUDE), col]
        if not small.empty:
            raise _fail(
                "check_snapshots", f"{col} must be missing or |ml| >= {MIN_MONEYLINE_MAGNITUDE}", small.tolist()
            )
    home = pd.to_numeric(df["home_moneyline"], errors="coerce")
    away = pd.to_numeric(df["away_moneyline"], errors="coerce")
    # A pick'em can be -110/-110; two underdogs or two heavy favourites are not a market.
    both = home.notna() & away.notna()
    same_sign = both & (((home > 0) & (away > 0)) | ((home < -MAX_PICKEM_MONEYLINE) & (away < -MAX_PICKEM_MONEYLINE)))
    if same_sign.any():
        raise _fail(
            "check_snapshots", "home and away moneyline have the same sign", df.loc[same_sign, "game_id"].tolist()
        )
    keys = ["game_id", "observed_at", "kind"]
    dup = df[df.duplicated(keys, keep=False)]
    if not dup.empty:
        raise _fail("check_snapshots", f"duplicate {keys}", dup["game_id"].tolist())
