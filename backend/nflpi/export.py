"""Full prediction record of the bench as CSV and JSON, plus the NaN-free JSON helper the report shares.

Rows are sorted by kickoff then game id, key order is fixed, a missing value is an empty CSV cell and JSON null.
"""

import csv
import io
import json
import math

import numpy as np
import pandas as pd

from nflpi.analytics.score_backtest import PRED_COLS
from nflpi.betting.settle import settle_spread, settle_total
from nflpi.data.asof import home_spread_from_nflverse

LINE_KIND = "closing, benchmark only"
SIM_SOURCES = ("football_only", "market_informed")
SIM_METRICS = ("mean_margin", "mean_total", "p_win_half", "p_tie", "p_cover_nopush", "p_over_nopush")
SIM_COLUMNS = [f"sim_{source}_{metric}" for source in SIM_SOURCES for metric in SIM_METRICS]
CONFIDENCE_BANDS = (("50-60%", 0.5, 0.6), ("60-70%", 0.6, 0.7), ("70%+", 0.7, 1.0))
KICKOFF_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
INT_COLUMNS = {"season", "week", "home_win", "home_score", "away_score", "margin", "total"}
PROB_COLUMNS = ["p_home", "p_elo", "p_logistic", "p_market", "p_blend"]
PREDICTION_COLUMNS = [
    "game_id", "season", "week", "kickoff_utc", "home_team", "away_team", "home_win", "home_score", "away_score",
    "margin", "total", "spread_line", "home_spread", "total_line", *PROB_COLUMNS, "blend_pick",
    "blend_confidence_band", *PRED_COLS, "cover_result", "over_result", "line_kind", *SIM_COLUMNS,
]
_SPREAD_WORDS = {"win": "home_cover", "loss": "away_cover", "push": "push"}
_TOTAL_WORDS = {"win": "over", "loss": "under", "push": "push"}


def to_native(obj):
    """Plain JSON types only: numpy scalars unwrapped, NaN and infinity become None, keys become strings."""
    if isinstance(obj, dict):
        return {str(k): to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_native(v) for v in obj]
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        value = float(obj)
        return value if math.isfinite(value) else None
    return obj


def confidence_band(prob: float) -> str | None:
    """Band of the picked side's probability; None when the probability is missing."""
    if prob is None or pd.isna(prob):
        return None
    picked = max(prob, 1 - prob)
    return next(label for label, lo, hi in CONFIDENCE_BANDS if lo <= picked < hi or (hi == 1.0 and picked <= hi))


def _settled(settle, words: dict[str, str], selection: str, line, home_score, away_score) -> str | None:
    if any(pd.isna(v) for v in (line, home_score, away_score)):
        return None
    return words[settle(selection, line, int(home_score), int(away_score))]


def closing_results(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Spread and total outcomes against the closing lines; the home spread is the one sign flip."""
    home_spread = home_spread_from_nflverse(frame["spread_line"])
    cover = [
        _settled(settle_spread, _SPREAD_WORDS, "home", h, hs, aws)
        for h, hs, aws in zip(home_spread, frame["home_score"], frame["away_score"], strict=True)
    ]
    over = [
        _settled(settle_total, _TOTAL_WORDS, "over", line, hs, aws)
        for line, hs, aws in zip(frame["total_line"], frame["home_score"], frame["away_score"], strict=True)
    ]
    return pd.Series(cover, index=frame.index, dtype=object), pd.Series(over, index=frame.index, dtype=object)


def sim_wide(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per game from the long simulator table (one distribution per source)."""
    wide = pd.DataFrame({"game_id": rows["game_id"].drop_duplicates().to_numpy()})
    for source in SIM_SOURCES:
        part = rows.loc[rows["source"] == source, ["game_id", *SIM_METRICS]]
        wide = wide.merge(part.rename(columns={m: f"sim_{source}_{m}" for m in SIM_METRICS}), on="game_id", how="left")
    return wide


def prediction_record(record: pd.DataFrame, score_preds: pd.DataFrame, sim_rows: pd.DataFrame | None = None
                      ) -> pd.DataFrame:
    """sim_rows is the wide per-game simulator table (game_id plus SIM_COLUMNS), as sim_wide builds it."""
    df = record.merge(score_preds[["game_id", *PRED_COLS]], on="game_id", how="left")
    df = df.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)
    df["kickoff_utc"] = pd.to_datetime(df["kickoff_utc"], utc=True).dt.strftime(KICKOFF_FORMAT)
    df["margin"], df["total"] = df["home_score"] - df["away_score"], df["home_score"] + df["away_score"]
    df["home_spread"] = home_spread_from_nflverse(df["spread_line"])
    df["blend_pick"] = np.where(df["p_blend"].isna(), None, np.where(df["p_blend"] > 0.5, "home", "away"))
    df["blend_confidence_band"] = [confidence_band(p) for p in df["p_blend"]]
    df["cover_result"], df["over_result"] = closing_results(df)
    df["line_kind"] = LINE_KIND
    wide = sim_rows if sim_rows is not None else pd.DataFrame({"game_id": df["game_id"]})
    df = df.merge(wide.reindex(columns=["game_id", *SIM_COLUMNS]), on="game_id", how="left")
    return df[PREDICTION_COLUMNS]


def _cell(column: str, value):
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    value = to_native(value)
    if column in INT_COLUMNS and isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _rows(df: pd.DataFrame) -> list[dict]:
    return [{c: _cell(c, v) for c, v in zip(PREDICTION_COLUMNS, row, strict=True)}
            for row in df[PREDICTION_COLUMNS].itertuples(index=False, name=None)]


def to_csv_text(df: pd.DataFrame) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(PREDICTION_COLUMNS)
    writer.writerows([["" if v is None else v for v in row.values()] for row in _rows(df)])
    return out.getvalue()


def to_json_text(df: pd.DataFrame) -> str:
    return json.dumps(_rows(df), indent=1, allow_nan=False) + "\n"
