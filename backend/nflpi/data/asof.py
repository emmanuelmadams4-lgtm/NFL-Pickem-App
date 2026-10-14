"""As-of frame builder: one cutoff in, only what was known at that moment out.

Rule: a row is visible when ``observed_at <= cutoff`` (inclusive). A game result is known only when
``kickoff_utc + RESULT_LAG <= cutoff``. The schedule itself is public ahead of time, so every game row is kept, but
scores, status and realized weather of games not yet decided are blanked. Quarterback names of unplayed games come
only from observations (the games-table name is the after-the-fact value, audit A8). Missing stays missing.

All datetimes are UTC and tz-aware; a naive cutoff raises ValueError. Inputs are never edited.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from nflpi.models import Game, InjuryReport, MarketSnapshot, QbObservation, WeatherForecast

RESULT_LAG = timedelta(hours=4)
SIDES = ("home", "away")
LINE_COLUMNS = ["home_moneyline", "away_moneyline", "spread_line", "total_line", "home_prob_novig", "kind"]
GAME_COLUMNS = [
    "game_id", "season", "week", "game_type", "kickoff_utc", "home_team", "away_team", "home_score", "away_score",
    "status", "neutral_site", "home_qb", "away_qb", "temp_f", "wind_mph",
]  # fmt: skip
WEATHER_COLUMNS = ["temp_f", "wind_mph", "precip_prob"]
_REALIZED = ["home_score", "away_score", "temp_f", "wind_mph"]


@dataclass(frozen=True)
class AsofTables:
    games: pd.DataFrame
    snapshots: pd.DataFrame
    qb_observations: pd.DataFrame
    injuries: pd.DataFrame
    weather: pd.DataFrame


def _require_aware(cutoff: datetime) -> None:
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("cutoff must be tz-aware (UTC); got a naive datetime")


def home_spread_from_nflverse(spread_line):
    """Owner-brief home spread h from nflverse spread_line. The ONLY place the sign is flipped (audit A13).

    nflverse: a positive spread_line means the home side is favoured. Owner brief: the home side covers when
    margin + h > 0, so a favourite has a negative h. None and NaN stay NaN.
    """
    if spread_line is None:
        return np.nan
    spread = pd.to_numeric(spread_line, errors="coerce")
    return -spread


def _prep(df: pd.DataFrame, columns: list[str], times: tuple[str, ...] = ("observed_at",)) -> pd.DataFrame:
    """Copy with the expected columns present (NaN when absent) and time columns as UTC datetimes."""
    out = df.copy()
    for c in [*columns, *times]:
        if c not in out.columns:
            out[c] = np.nan
    for t in times:
        out[t] = pd.to_datetime(out[t], utc=True)
    return out


def _latest(df: pd.DataFrame, keys: list[str], cutoff: datetime) -> pd.DataFrame:
    """Newest row per key with observed_at <= cutoff; ties on observed_at go to the highest id."""
    seen = df[df["observed_at"] <= cutoff]
    order = ["observed_at", "id"] if "id" in seen.columns else ["observed_at"]
    return seen.sort_values(order, kind="stable").groupby(keys, sort=False, dropna=False).tail(1).reset_index(drop=True)


def _result_known(games: pd.DataFrame, cutoff: datetime) -> pd.Series:
    return (pd.to_datetime(games["kickoff_utc"], utc=True) + RESULT_LAG) <= cutoff


def asof_games(games: pd.DataFrame, cutoff: datetime) -> pd.DataFrame:
    _require_aware(cutoff)
    out = _prep(games, GAME_COLUMNS, times=("kickoff_utc",))
    hidden = ~_result_known(out, cutoff)
    for c in _REALIZED:
        out[c] = out[c].astype(float)
        out.loc[hidden, c] = np.nan
    out["status"] = out["status"].astype(object)
    out.loc[hidden, "status"] = "scheduled"
    return out


def asof_lines(snapshots: pd.DataFrame, cutoff: datetime) -> pd.DataFrame:
    _require_aware(cutoff)
    out = _latest(_prep(snapshots, ["game_id", *LINE_COLUMNS]), ["game_id"], cutoff)
    out["line_age_hours"] = (cutoff - out["observed_at"]).dt.total_seconds() / 3600
    out["home_spread"] = home_spread_from_nflverse(out["spread_line"])
    return out


def asof_qbs(observations: pd.DataFrame, cutoff: datetime) -> pd.DataFrame:
    _require_aware(cutoff)
    latest = _latest(_prep(observations, ["game_id", "side", "qb"]), ["game_id", "side"], cutoff)
    return latest[["game_id", "side", "qb", "observed_at"]].reset_index(drop=True)


def asof_injuries(injuries: pd.DataFrame, cutoff: datetime) -> pd.DataFrame:
    _require_aware(cutoff)
    prepared = _prep(injuries, ["season", "week", "team", "player_id", "player", "report_status"])
    prepared["_player_key"] = prepared["player_id"].fillna(prepared["player"])
    latest = _latest(prepared, ["season", "week", "team", "_player_key"], cutoff)
    return latest.drop(columns="_player_key")


def asof_weather(forecasts: pd.DataFrame, cutoff: datetime) -> pd.DataFrame:
    _require_aware(cutoff)
    return _latest(_prep(forecasts, ["game_id", *WEATHER_COLUMNS]), ["game_id"], cutoff)


def _qb_columns(frame: pd.DataFrame, qbs: pd.DataFrame, known: pd.Series, games_names: pd.DataFrame) -> pd.DataFrame:
    for side in SIDES:
        seen = qbs[qbs["side"] == side].set_index("game_id")
        observed = frame["game_id"].map(seen["qb"]) if len(seen) else pd.Series(np.nan, index=frame.index, dtype=object)
        stamp = frame["game_id"].map(seen["observed_at"]) if len(seen) else pd.Series(pd.NaT, index=frame.index)
        frame[f"{side}_qb"] = observed.where(~known, games_names[f"{side}_qb"])
        frame[f"{side}_qb_observed_at"] = pd.to_datetime(stamp, utc=True).where(~known, pd.NaT)
    return frame


def _out_counts(frame: pd.DataFrame, injuries: pd.DataFrame) -> pd.DataFrame:
    out_rows = injuries[injuries["report_status"] == "Out"]
    counts = out_rows.groupby(["season", "week", "team"]).size()
    for side in SIDES:
        keys = pd.MultiIndex.from_arrays([frame["season"], frame["week"], frame[f"{side}_team"]])
        frame[f"{side}_out_count"] = counts.reindex(keys).fillna(0).astype(int).to_numpy()
    return frame


def build_asof_frame(tables: AsofTables, cutoff: datetime) -> pd.DataFrame:
    """One row per game, sorted by kickoff then id, with everything known at ``cutoff``."""
    _require_aware(cutoff)
    games = _prep(tables.games, GAME_COLUMNS, times=("kickoff_utc",))
    known = _result_known(games, cutoff)
    frame = asof_games(tables.games, cutoff)

    lines = asof_lines(tables.snapshots, cutoff)
    lines = lines[["game_id", *LINE_COLUMNS, "observed_at", "line_age_hours", "home_spread"]]
    frame = frame.merge(lines.rename(columns={"observed_at": "line_observed_at"}), on="game_id", how="left")

    weather = asof_weather(tables.weather, cutoff)[["game_id", *WEATHER_COLUMNS, "observed_at"]]
    weather = weather.rename(
        columns={"temp_f": "fcst_temp_f", "wind_mph": "fcst_wind_mph", "precip_prob": "fcst_precip_prob"}
    )
    frame = frame.merge(weather.rename(columns={"observed_at": "fcst_observed_at"}), on="game_id", how="left")

    frame = _qb_columns(frame, asof_qbs(tables.qb_observations, cutoff), known.to_numpy(), games.reset_index(drop=True))
    frame = _out_counts(frame, asof_injuries(tables.injuries, cutoff))
    return frame.sort_values(["kickoff_utc", "game_id"], kind="stable").reset_index(drop=True)


def _table_frame(session: Session, model) -> pd.DataFrame:
    columns = [c.key for c in model.__table__.columns]
    rows = session.execute(select(*[getattr(model, c) for c in columns])).all()
    return pd.DataFrame(rows, columns=columns)


def load_tables(session: Session) -> AsofTables:
    """Read-only snapshot of the five tables the as-of frame needs."""
    return AsofTables(
        games=_table_frame(session, Game),
        snapshots=_table_frame(session, MarketSnapshot),
        qb_observations=_table_frame(session, QbObservation),
        injuries=_table_frame(session, InjuryReport),
        weather=_table_frame(session, WeatherForecast),
    )


def asof_frame_from_db(session: Session, cutoff: datetime) -> pd.DataFrame:
    return build_asof_frame(load_tables(session), cutoff)
