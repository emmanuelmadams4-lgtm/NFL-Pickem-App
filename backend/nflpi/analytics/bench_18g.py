"""Step 18g candidates: Pythagorean head-to-head, quarterback rating, travel and time zone, matchup score."""

import math
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from functools import cache
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from nflpi.analytics import backtest
from nflpi.analytics.metrics import paired_gain
from nflpi.ingestion.weather import STADIUMS
from nflpi.predictions.features import BASE_FEATURES, BLEND_FEATURES
from nflpi.predictions.model import LogitModel

PYTH_EXPONENT = 2.37
PYTH_HALF_LIVES = (4, 8, 16)
PYTH_CLIP = 0.01
QB_HALF_LIVES = (8, 16, 32)
QB_SHRINK = 150.0
QB_SCALE = 50.0
EARTH_RADIUS_KM = 6371.0
KM_PER_UNIT = 1000.0
MARKET_FALLBACK = "p_blend"
BASE_FALLBACK = "p_logistic"
MATCHUP_PERCENT = 100.0
MATCHUP_CLIP = 1e-3

EXTRA_COORDS: dict[str, tuple[float, float]] = {
    "OAK00": (37.75, -122.20),
    "NYC00": (40.81, -74.07),
    "ATL00": (33.76, -84.40),
    "SDG00": (32.78, -117.12),
    "STL00": (38.63, -90.19),
    "SFO00": (37.71, -122.39),
    "MIN00": (44.97, -93.26),
    "DAL99": (32.85, -96.91),
    "IND99": (39.76, -86.16),
    "PHO99": (33.43, -111.93),
    "LAX99": (34.01, -118.29),
    "LAX97": (33.86, -118.26),
    "MIN98": (44.98, -93.22),
    "CHI99": (40.10, -88.24),
    "PHI99": (39.90, -75.17),
    "BUF01": (43.64, -79.39),
    "BRG00": (30.41, -91.18),
    "SAN00": (29.42, -98.49),
    "LON01": (51.46, -0.34),
    "FRA00": (50.07, 8.65),
}
STADIUM_COORDS: dict[str, tuple[float, float]] = {**STADIUMS, **EXTRA_COORDS}

_NY, _CHI, _LA = "America/New_York", "America/Chicago", "America/Los_Angeles"
_IND, _PHX, _LON, _BER = "America/Indiana/Indianapolis", "America/Phoenix", "Europe/London", "Europe/Berlin"
STADIUM_ZONES: dict[str, str] = {
    "ATL97": _NY,
    "BAL00": _NY,
    "BOS00": _NY,
    "BUF00": _NY,
    "CAR00": _NY,
    "CHI98": _CHI,
    "CIN00": _NY,
    "CLE00": _NY,
    "DAL00": _CHI,
    "DEN00": "America/Denver",
    "DET00": "America/Detroit",
    "GNB00": _CHI,
    "HOU00": _CHI,
    "IND00": _IND,
    "JAX00": _NY,
    "KAN00": _CHI,
    "LAX01": _LA,
    "MIA00": _NY,
    "MIN01": _CHI,
    "NAS00": _CHI,
    "NOR00": _CHI,
    "NYC01": _NY,
    "PHI00": _NY,
    "PHO00": _PHX,
    "PIT00": _NY,
    "SEA00": _LA,
    "SFO01": _LA,
    "TAM00": _NY,
    "VEG00": _LA,
    "WAS00": _NY,
    "LON00": _LON,
    "LON02": _LON,
    "GER00": _BER,
    "MUN01": _BER,
    "MEX00": "America/Mexico_City",
    "MAD01": "Europe/Madrid",
    "MEL00": "Australia/Melbourne",
    "PAR00": "Europe/Paris",
    "RIO00": "America/Sao_Paulo",
    "SAO00": "America/Sao_Paulo",
    "OAK00": _LA,
    "NYC00": _NY,
    "ATL00": _NY,
    "SDG00": _LA,
    "STL00": _CHI,
    "SFO00": _LA,
    "MIN00": _CHI,
    "DAL99": _CHI,
    "IND99": _IND,
    "PHO99": _PHX,
    "LAX99": _LA,
    "LAX97": _LA,
    "MIN98": _CHI,
    "CHI99": _CHI,
    "PHI99": _NY,
    "BUF01": "America/Toronto",
    "BRG00": _CHI,
    "SAN00": _CHI,
    "LON01": _LON,
    "FRA00": _BER,
}
TRAVEL_VARIANTS = {"travel": ["travel_km_diff"], "tz": ["tz_diff"], "both": ["travel_km_diff", "tz_diff"]}


def _check_order(df: pd.DataFrame) -> None:
    if not df["kickoff_utc"].is_monotonic_increasing:
        raise ValueError("kickoff_utc must be in non-decreasing order")


def _missing(value) -> bool:
    return value is None or bool(pd.isna(value))


# ---- Pythagorean head-to-head ----


def _log_odds(pf: float, pa: float) -> float:
    """Pythagorean win share clipped to 0.01..0.99, as log-odds."""
    high, low = pf**PYTH_EXPONENT, pa**PYTH_EXPONENT
    share = 0.5 if high + low == 0 else high / (high + low)
    share = min(max(share, PYTH_CLIP), 1 - PYTH_CLIP)
    return math.log(share / (1 - share))


def pythag_diff(df: pd.DataFrame, half_life: float) -> pd.Series:
    """Home minus away Pythagorean log-odds from earlier games only; kickoff rows must be ordered."""
    _check_order(df)
    decay = 0.5 ** (1 / half_life)
    ratings: dict[str, tuple[float, float]] = {}
    values = []
    for row in df.itertuples():
        home, away = ratings.get(row.home_team), ratings.get(row.away_team)
        values.append(_log_odds(*home) - _log_odds(*away) if home and away else np.nan)
        if _missing(row.home_score) or _missing(row.away_score):
            continue
        for team, scored, allowed in (
            (row.home_team, row.home_score, row.away_score),
            (row.away_team, row.away_score, row.home_score),
        ):
            pf, pa = ratings.get(team, (0.0, 0.0))
            ratings[team] = (pf * decay + float(scored), pa * decay + float(allowed))
    return pd.Series(values, index=df.index, dtype=float)


def pythag_column(kind: str, half_life: int) -> str:
    """Name of one Pythagorean variant's prediction column."""
    return f"p_pyth_{kind}_{half_life}"


# ---- shared walk-forward machinery ----


def variant_preds(train: pd.DataFrame, test: pd.DataFrame, features: list[str], fallback_col: str) -> pd.Series:
    """Fit on train, predict test; a game missing an input keeps the named baseline's number."""
    model = LogitModel.fit(train, features)
    return pd.Series(model.predict(test), index=test.index).fillna(test[fallback_col])


Variant = tuple[str, str, list[str], dict[str, str]]  # (column, kind, features, feature -> frame column)


def _walk(
    df: pd.DataFrame,
    seasons: list[int],
    window: int,
    cols: dict[str, pd.Series],
    variants: Callable[[], list[Variant]],
) -> pd.DataFrame:
    frames = {params: frame.assign(**cols) for params, frame in backtest._elo_frames(df).items()}
    by_season = []
    for season in seasons:
        test = backtest.predict_season(frames, season, window)
        _, train = backtest._train_rows(frames, season, window)
        for column, kind, features, source in variants():
            fit_rows = train.dropna(subset=["market_logit"]) if kind == "blend" else train
            fallback = MARKET_FALLBACK if kind == "blend" else BASE_FALLBACK
            test[column] = variant_preds(
                fit_rows.assign(**{f: fit_rows[c] for f, c in source.items()}),
                test.assign(**{f: test[c] for f, c in source.items()}),
                features,
                fallback,
            )
        by_season.append(test)
    return backtest._market_games(by_season)


def pythag_preds(df: pd.DataFrame, seasons: list[int], window: int = 10) -> pd.DataFrame:
    """Score held-out seasons with Pythagorean head-to-head added to the blend and to the stats model."""
    cols = {f"pyth_diff_{h}": pythag_diff(df, h) for h in PYTH_HALF_LIVES}

    def variants() -> list[Variant]:
        return [
            (
                pythag_column(kind, h),
                kind,
                [*(BLEND_FEATURES if kind == "blend" else BASE_FEATURES), "pyth_diff"],
                {"pyth_diff": f"pyth_diff_{h}"},
            )
            for kind in ("blend", "base")
            for h in PYTH_HALF_LIVES
        ]

    return _walk(df, seasons, window, cols, variants)


# ---- quarterback rating ----


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def qb_games(rows: list[dict]) -> pd.DataFrame:
    """Quarterback game lines (EPA, plays) from nflverse player-week rows."""
    out = []
    for row in rows:
        if row.get("position") != "QB":
            continue
        parts = [_number(row.get(k)) for k in ("passing_epa", "rushing_epa", "attempts", "sacks_suffered", "carries")]
        if any(p is None for p in parts):
            continue
        pass_epa, rush_epa, attempts, sacks, carries = parts
        plays = attempts + sacks + carries
        if plays <= 0:
            continue
        out.append((row["game_id"], row["player_id"], pass_epa + rush_epa, plays))
    return pd.DataFrame(out, columns=["game_id", "player_id", "epa", "plays"])


def qb_diff(df: pd.DataFrame, log: pd.DataFrame, half_life: float) -> pd.Series:
    """Scaled home minus away starter rating from earlier games only; kickoff rows must be ordered."""
    _check_order(df)
    decay = 0.5 ** (1 / half_life)
    by_game = {
        gid: list(zip(g["player_id"], g["epa"], g["plays"], strict=True))
        for gid, g in log.groupby("game_id", sort=False)
    }
    ratings: dict[str, tuple[float, float]] = {}

    def rate(player: str) -> float:
        epa, plays = ratings.get(player, (0.0, 0.0))
        return epa / (plays + QB_SHRINK)

    values = []
    for row in df.itertuples():
        if _missing(row.home_qb_id) or _missing(row.away_qb_id):
            values.append(np.nan)
        else:
            values.append(QB_SCALE * (rate(row.home_qb_id) - rate(row.away_qb_id)))
        for player, epa, plays in by_game.get(row.game_id, []):
            old_epa, old_plays = ratings.get(player, (0.0, 0.0))
            ratings[player] = (old_epa * decay + float(epa), old_plays * decay + float(plays))
    return pd.Series(values, index=df.index, dtype=float)


def qb_column(kind: str, half_life: int) -> str:
    """Name of one quarterback variant's prediction column."""
    return f"p_qb_{kind}_{half_life}"


def qb_preds(df: pd.DataFrame, seasons: list[int], log: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """Score held-out seasons with a quarterback rating replacing the two change flags."""
    cols = {f"qb_diff_{h}": qb_diff(df, log, h) for h in QB_HALF_LIVES}
    sets = {
        "blend": ["market_logit", "elo_diff", "home_field", "qb_diff"],
        "base": ["elo_diff", "home_field", "qb_diff"],
    }

    def variants() -> list[Variant]:
        return [
            (qb_column(kind, h), kind, sets[kind], {"qb_diff": f"qb_diff_{h}"})
            for kind in ("blend", "base")
            for h in QB_HALF_LIVES
        ]

    return _walk(df, seasons, window, cols, variants)


# ---- travel and time zone ----


def great_circle_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Haversine distance between two (lat, lon) pairs."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


@cache
def _offset_hours(zone: str, kickoff: datetime) -> float:
    return kickoff.astimezone(ZoneInfo(zone)).utcoffset().total_seconds() / 3600


def _home_venues(df: pd.DataFrame) -> dict[tuple[int, str], str]:
    """Per season and team, the stadium used most for home games that are not neutral."""
    counts: dict[tuple[int, str], Counter] = {}
    for row in df.itertuples():
        if bool(row.neutral_site) or _missing(row.stadium_id):
            continue
        counts.setdefault((row.season, row.home_team), Counter())[row.stadium_id] += 1
    return {key: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for key, c in counts.items()}


def _kickoff(value) -> datetime | None:
    if _missing(value):
        return None
    moment = pd.Timestamp(value).to_pydatetime()
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _trip(venue: str | None, stadium: str, kickoff: datetime, coords: dict, zones: dict) -> tuple[float, float]:
    """(km, time shift in hours) for a team travelling from its home venue to the stadium."""
    if venue is None or venue not in coords or venue not in zones:
        return np.nan, np.nan
    km = great_circle_km(coords[venue], coords[stadium])
    return km, _offset_hours(zones[stadium], kickoff) - _offset_hours(zones[venue], kickoff)


def travel_features(df: pd.DataFrame, coords: dict, zones: dict) -> pd.DataFrame:
    """Away-minus-home travel distance (thousand km) and time-zone shift (hours); missing when unknown."""
    venues = _home_venues(df)
    rows = []
    for row in df.itertuples():
        stadium, kickoff = row.stadium_id, _kickoff(row.kickoff_utc)
        if _missing(stadium) or stadium not in coords or stadium not in zones or kickoff is None:
            rows.append((np.nan, np.nan))
            continue
        away = _trip(venues.get((row.season, row.away_team)), stadium, kickoff, coords, zones)
        home = (
            _trip(venues.get((row.season, row.home_team)), stadium, kickoff, coords, zones)
            if bool(row.neutral_site)
            else (0.0, 0.0)
        )
        rows.append(((away[0] - home[0]) / KM_PER_UNIT, away[1] - home[1]))
    return pd.DataFrame(rows, index=df.index, columns=["travel_km_diff", "tz_diff"], dtype=float)


def travel_column(kind: str, variant: str) -> str:
    """Name of one travel variant's prediction column."""
    return f"p_travel_{kind}_{variant}"


def travel_preds(df: pd.DataFrame, seasons: list[int], window: int = 10) -> pd.DataFrame:
    """Score held-out seasons with travel distance and time-zone shift added to the blend and stats model."""
    cols = {c: travel_features(df, STADIUM_COORDS, STADIUM_ZONES)[c] for c in ("travel_km_diff", "tz_diff")}

    def variants() -> list[Variant]:
        return [
            (travel_column(kind, v), kind, [*(BLEND_FEATURES if kind == "blend" else BASE_FEATURES), *extra], {})
            for kind in ("blend", "base")
            for v, extra in TRAVEL_VARIANTS.items()
        ]

    return _walk(df, seasons, window, cols, variants)


# ---- matchup score ----


def matchup_preds(df: pd.DataFrame, seasons: list[int], window: int = 10) -> pd.DataFrame:
    """Score held-out seasons with the fixed matchup formula, with and without the market; nothing is fitted."""
    from nflpi.data.matchup import matchup_score

    frames = backtest._elo_frames(df)
    by_season = []
    for season in seasons:
        test = backtest.predict_season(frames, season, window)
        test["p_match_football"] = np.asarray(matchup_score(test, include_market=False), dtype=float) / MATCHUP_PERCENT
        test["p_match_market"] = np.asarray(matchup_score(test, include_market=True), dtype=float) / MATCHUP_PERCENT
        by_season.append(test)
    return backtest._market_games(by_season)


def matchup_input_gap(df: pd.DataFrame, seasons: list[int], window: int = 10) -> float:
    """Largest difference between the blend and the blend refitted with the football matchup log-odds added."""
    from nflpi.data.matchup import matchup_score

    def logit_of(frame: pd.DataFrame) -> pd.Series:
        p = np.asarray(matchup_score(frame, include_market=False), dtype=float) / MATCHUP_PERCENT
        p = np.clip(p, MATCHUP_CLIP, 1 - MATCHUP_CLIP)
        return pd.Series(np.log(p / (1 - p)), index=frame.index)

    frames = backtest._elo_frames(df)
    gap = 0.0
    for season in seasons:
        test = backtest.predict_season(frames, season, window)
        _, train = backtest._train_rows(frames, season, window)
        train = train.dropna(subset=["market_logit"]).assign(match_logit=lambda t: logit_of(t))
        test = test[test["market_logit"].notna()]
        model = LogitModel.fit(train, [*BLEND_FEATURES, "match_logit"])
        refit = model.predict(test.assign(match_logit=logit_of(test)))
        diff = np.abs(refit - test["p_blend"].to_numpy())
        if np.isfinite(diff).any():
            gap = max(gap, float(np.nanmax(diff)))
    return gap


# ---- judging ----


def evaluate_vs(
    preds: pd.DataFrame,
    candidates: dict[str, list[str]],
    tune: list[int],
    confirm: list[int],
    baseline: str = MARKET_FALLBACK,
    cluster: list[str] | None = None,
) -> list[dict]:
    """Choose each candidate's variant on tune seasons only and judge it once on confirm against any baseline."""
    if set(tune) & set(confirm):
        raise ValueError("tune and confirm seasons must not overlap")
    tune_rows = preds[preds["season"].isin(tune)]
    confirm_rows = preds[preds["season"].isin(confirm)]

    def clusters(rows: pd.DataFrame) -> np.ndarray | None:
        return rows.groupby(cluster, sort=True).ngroup().to_numpy() if cluster is not None else None

    def gain(rows: pd.DataFrame, column: str, groups: np.ndarray | None) -> dict:
        return paired_gain(
            rows[column].to_numpy(), rows[baseline].to_numpy(), rows["home_win"].to_numpy(), clusters=groups
        )

    tune_groups, confirm_groups = clusters(tune_rows), clusters(confirm_rows)
    out = []
    for name, columns in candidates.items():
        variants = [{"variant": c, "tune": gain(tune_rows, c, tune_groups)} for c in columns]
        chosen = max(variants, key=lambda v: v["tune"]["log_loss_gain"])["variant"]
        result = gain(confirm_rows, chosen, confirm_groups)
        all_variants = []
        for v in variants:
            confirm_gain = gain(confirm_rows, v["variant"], None)["log_loss_gain"]
            tune_gain = v["tune"]["log_loss_gain"]
            all_variants.append(
                {
                    "variant": v["variant"],
                    "tune_gain": tune_gain,
                    "confirm_gain": confirm_gain,
                    "gap": tune_gain - confirm_gain,
                }
            )
        out.append(
            {
                "candidate": name,
                "variants": variants,
                "chosen": chosen,
                "baseline": baseline,
                "confirm": result,
                "ships": result["ships"],
                "all_variants": all_variants,
            }
        )
    return out


def label(column: str) -> str:
    """Whether a prediction column uses the market, from its name."""
    if "_blend_" in column or column == "p_match_market":
        return "market-informed"
    if "_base_" in column or column == "p_match_football":
        return "football-only"
    raise ValueError(f"cannot label column: {column}")


def verdict(result: dict) -> str:
    """Ship rule: both intervals must pass; a split goes to the owner."""
    game = bool(result["ships"])
    group = bool(result.get("ships_cluster", game))
    if game and group:
        return "ships"
    return "does not ship" if not game and not group else "needs the owner"
