"""Pre-game features. Every value here is known before kickoff."""

import math

import numpy as np
import pandas as pd

from nflpi.predictions.elo import EloParams, run_elo
from nflpi.predictions.market import devig_home_prob, novig_home_prob

BASE_FEATURES = ["elo_diff", "home_field", "home_qb_change", "away_qb_change"]
# Tested and dropped: rest_diff (no log-loss gain in the 2012-2025 walk-forward backtest).
BLEND_FEATURES = ["market_logit", *BASE_FEATURES]


def market_logit(df: pd.DataFrame, method: str) -> pd.Series:
    """Return clipped home market log-odds for the chosen margin method."""
    probs = pd.Series([
        devig_home_prob(h, a, method) if not (pd.isna(h) or pd.isna(a)) else np.nan
        for h, a in zip(df["home_ml"], df["away_ml"], strict=True)
    ], index=df.index, dtype=float).clip(0.01, 0.99)
    return np.log(probs / (1 - probs))


def team_game_epa(rows: list[dict]) -> pd.DataFrame:
    """Return each usable team's EPA per play minus its opponent's."""
    games: dict[str, list[tuple[int, str, float]]] = {}
    for i, row in enumerate(rows):
        values = [row[key] for key in ("passing_epa", "rushing_epa", "attempts", "sacks_suffered", "carries")]
        if any(value in ("", "NA") for value in values):
            continue
        passing, rushing, attempts, sacks, carries = map(float, values)
        if not all(math.isfinite(value) for value in (passing, rushing, attempts, sacks, carries)):
            continue
        plays = attempts + sacks + carries
        if plays == 0:
            continue
        games.setdefault(row["game_id"], []).append((i, row["team"], (passing + rushing) / plays))

    result = []
    for game_id, sides in games.items():
        if len(sides) != 2 or sides[0][1] == sides[1][1]:
            continue
        (first_i, first_team, first_epa), (second_i, second_team, second_epa) = sides
        result.extend(((first_i, game_id, first_team, first_epa - second_epa),
                       (second_i, game_id, second_team, second_epa - first_epa)))
    result.sort(key=lambda row: row[0])
    return pd.DataFrame([(game_id, team, net) for _, game_id, team, net in result],
                        columns=["game_id", "team", "net_epa"])


def offence_defence(rows: list[dict]) -> pd.DataFrame:
    """Return each team's offence rates and its opponent's offence rates."""
    games: dict[str, list[tuple[int, str, float, float, float]]] = {}
    for i, row in enumerate(rows):
        games.setdefault(row["game_id"], []).append((i, row["team"], row["plays"], row["epa"], row["success"]))

    result = []
    for game_id, sides in games.items():
        if len(sides) != 2 or sides[0][1] == sides[1][1]:
            continue
        try:
            (first_i, first_team, first_plays, first_epa, first_success) = sides[0]
            (second_i, second_team, second_plays, second_epa, second_success) = sides[1]
            first_plays, first_epa, first_success = map(float, (first_plays, first_epa, first_success))
            second_plays, second_epa, second_success = map(float, (second_plays, second_epa, second_success))
        except (TypeError, ValueError):
            continue
        if (first_plays <= 0 or second_plays <= 0 or
                not all(map(math.isfinite, (first_plays, first_epa, first_success,
                                            second_plays, second_epa, second_success)))):
            continue
        first_off_epa, second_off_epa = first_epa / first_plays, second_epa / second_plays
        first_off_sr, second_off_sr = first_success / first_plays, second_success / second_plays
        result.extend(((first_i, game_id, first_team, first_off_epa, second_off_epa, first_off_sr, second_off_sr),
                       (second_i, game_id, second_team, second_off_epa, first_off_epa, second_off_sr, first_off_sr)))
    result.sort(key=lambda row: row[0])
    return pd.DataFrame([row[1:] for row in result],
                        columns=["game_id", "team", "off_epa", "def_epa", "off_sr", "def_sr"])


def epa_diff(df: pd.DataFrame, epa: pd.DataFrame, half_life: float) -> pd.Series:
    """Return pregame EPA difference; kickoff rows must be ordered."""
    if not df["kickoff_utc"].is_monotonic_increasing:
        raise ValueError("kickoff_utc must be in non-decreasing order")
    decay = 0.5 ** (1 / half_life)
    by_game = {game_id: list(zip(group["team"], group["net_epa"], strict=True))
               for game_id, group in epa.groupby("game_id", sort=False)}
    ratings: dict[str, tuple[float, float]] = {}
    differences = []
    for row in df.itertuples():
        home = ratings.get(row.home_team)
        away = ratings.get(row.away_team)
        differences.append(home[0] / home[1] - away[0] / away[1] if home and away else np.nan)
        for team, net_epa in by_game.get(row.game_id, []):
            weighted, weight = ratings.get(team, (0.0, 0.0))
            ratings[team] = (weighted * decay + net_epa, weight * decay + 1)
    return pd.Series(differences, index=df.index, dtype=float)


def games_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    return df.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)


def qb_changes(df: pd.DataFrame) -> dict[str, list]:
    """Flag when a team's expected starter differs from its previous game's starter (same season)."""
    last: dict[str, tuple[int, str | None]] = {}
    cols: dict[str, list] = {"home_qb_change": [], "away_qb_change": [], "home_prev_qb": [], "away_prev_qb": []}
    for row in df.itertuples(index=False):
        for side, team, qb in (("home", row.home_team, row.home_qb), ("away", row.away_team, row.away_qb)):
            qb = qb if isinstance(qb, str) and qb else None
            prev = last.get(team)
            prev_qb = prev[1] if prev is not None and prev[0] == row.season else None
            cols[f"{side}_qb_change"].append(1.0 if qb and prev_qb and qb != prev_qb else 0.0)
            cols[f"{side}_prev_qb"].append(prev_qb)
            last[team] = (row.season, qb)
    return cols


def add_features(df: pd.DataFrame, elo: EloParams) -> pd.DataFrame:
    """df needs schedule columns plus home_ml/away_ml (may be NaN)."""
    out = run_elo(df, elo)
    out["elo_diff"] = (out["home_elo"] - out["away_elo"]) / 100
    out["home_field"] = (~out["neutral_site"].astype(bool)).astype(float)
    rest = (out["home_rest"].astype(float) - out["away_rest"].astype(float)).fillna(0) / 7
    out["rest_diff"] = rest.clip(-2, 2)
    for col, values in qb_changes(out).items():
        out[col] = values
    out["market_prob"] = [
        novig_home_prob(h, a) if not (pd.isna(h) or pd.isna(a)) else np.nan
        for h, a in zip(out["home_ml"], out["away_ml"], strict=True)
    ]
    p = out["market_prob"].clip(0.01, 0.99)
    out["market_logit"] = np.log(p / (1 - p))
    out["home_win"] = np.where(
        out["status"] == "final",
        np.where(
            out["home_score"] > out["away_score"], 1.0, np.where(out["home_score"] < out["away_score"], 0.0, np.nan)
        ),
        np.nan,
    )
    return out
