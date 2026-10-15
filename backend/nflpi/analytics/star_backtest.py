"""Walk-forward bench for prior-season stars missing from a game."""

import pandas as pd

from nflpi.analytics.backtest import _market_games, _predict_or_blend, _train_rows, elo_frames, predict_season
from nflpi.ingestion.nflverse import STAR_STATS
from nflpi.predictions.features import BLEND_FEATURES
from nflpi.predictions.model import LogitModel

STAR_LIMITS = {"qb": 32, "off": 64, "def": 64}
REPORT_OUT = frozenset({"out", "doubtful"})
ROSTER_OUT = frozenset({"RES", "PUP", "SUS"})
ROSTER_FIRST_SEASON = 2016
MIN_FIT_SEASONS = 3
STAR_VARIANTS = {
    "p_star_count": ["star_out_diff"],
    "p_star_weighted": ["star_out_w_diff"],
    "p_star_count_qb": ["star_out_diff", "qb_out_diff"],
    "p_star_weighted_qb": ["star_out_w_diff", "qb_out_diff"],
    "p_star_res_count": ["star_res_diff"],
    "p_star_res_weighted": ["star_res_w_diff"],
}
OFFENSE_POINTS = {"rushing_yards": 0.1, "receiving_yards": 0.1, "rushing_tds": 6,
                  "receiving_tds": 6, "receptions": 0.5}
DEFENSE_POINTS = {"def_tackles_solo": 1, "def_tackles_with_assist": 1, "def_tackle_assists": 0.5,
                  "def_sacks": 6, "def_qb_hits": 2, "def_tackles_for_loss": 2, "def_interceptions": 6,
                  "def_pass_defended": 3, "def_fumbles_forced": 4, "def_tds": 6, "def_safeties": 2}


def _score(totals: dict[str, float], points: dict[str, float]) -> float:
    return sum(totals[name] * value for name, value in points.items())


def league_stars(stats: list[dict]) -> dict[int, dict[str, tuple[str, float]]]:
    """Rank each season's regular-season players by their production."""
    stars: dict[int, dict[str, tuple[str, float]]] = {
        row["season"]: {} for row in stats if row["season_type"] == "REG"
    }
    players: dict[int, dict[str, dict]] = {}
    for row in stats:
        if row["season_type"] != "REG":
            continue
        season, pid = row["season"], row["player_id"]
        player = players.setdefault(season, {}).setdefault(
            pid, {"week": -1, "position": None, "totals": dict.fromkeys(STAR_STATS, 0.0)}
        )
        if row["week"] > player["week"]:
            player["week"], player["position"] = row["week"], row["position"]
        for name in STAR_STATS:
            player["totals"][name] += row[name]
    for season, season_players in players.items():
        groups: dict[str, list[tuple[str, float]]] = {group: [] for group in STAR_LIMITS}
        for pid, player in season_players.items():
            totals = player["totals"]
            off, defense = _score(totals, OFFENSE_POINTS), _score(totals, DEFENSE_POINTS)
            group = "qb" if player["position"] == "QB" else "off" if off >= defense else "def"
            score = totals["attempts"] if group == "qb" else off if group == "off" else defense
            if score > 0:
                groups[group].append((pid, score))
        for group, ranked in groups.items():
            chosen = sorted(ranked, key=lambda item: (-item[1], item[0]))[:STAR_LIMITS[group]]
            mean = sum(score for _, score in chosen) / len(chosen) if chosen else 0.0
            stars[season].update({pid: (group, score / mean) for pid, score in chosen})
    return stars


def _report_index(reports: list[dict]) -> tuple[dict[tuple, list[dict]], set[tuple]]:
    indexed: dict[tuple, list[dict]] = {}
    weeks: set[tuple] = set()
    for row in reports:
        season_week = (row["season"], row["week"])
        weeks.add(season_week)
        indexed.setdefault((*season_week, row["team"]), []).append(row)
    return indexed, weeks


def _roster_index(roster: list[dict]) -> tuple[dict[tuple, set[str]], set[tuple]]:
    indexed: dict[tuple, set[str]] = {}
    weeks: set[tuple] = set()
    for row in roster:
        season_week = (row["season"], row["week"])
        weeks.add(season_week)
        if row["status"] in ROSTER_OUT:
            indexed.setdefault((*season_week, row["team"]), set()).add(row["player_id"])
    return indexed, weeks


def _club_out(reports: list[dict], kickoff: object) -> set[str]:
    return {row["player_id"] for row in reports if (row["status"] or "").lower() in REPORT_OUT
            and (row["modified"] is None or row["modified"] < kickoff)}


def _counts(ids: set[str], stars: dict[str, tuple[str, float]]) -> tuple[float, float, float]:
    found = [stars[pid] for pid in sorted(ids) if pid in stars]
    return (float(sum(group != "qb" for group, _ in found)),
            float(sum(weight for group, weight in found if group != "qb")),
            float(sum(group == "qb" for group, _ in found)))


def star_out_features(
    df: pd.DataFrame, stats: list[dict], reports: list[dict], roster: list[dict] | None = None
) -> pd.DataFrame:
    """Count prior-season stars unavailable to each side before kickoff."""
    columns = ["star_out_diff", "star_out_w_diff", "qb_out_diff"]
    if roster is not None:
        columns += ["star_res_diff", "star_res_w_diff"]
    stars_by_season = league_stars(stats)
    report_rows, report_weeks = _report_index(reports)
    roster_rows, roster_weeks = _roster_index(roster) if roster is not None else ({}, set())
    values = []
    for game in df[["season", "week", "kickoff_utc", "home_team", "away_team"]].itertuples(index=False):
        season_week = (game.season, game.week)
        stars = stars_by_season.get(game.season - 1)
        if stars is None or season_week not in report_weeks:
            values.append([float("nan")] * len(columns))
            continue
        home_key, away_key = (*season_week, game.home_team), (*season_week, game.away_team)
        home = _club_out(report_rows.get(home_key, []), game.kickoff_utc)
        away = _club_out(report_rows.get(away_key, []), game.kickoff_utc)
        result = [h - a for h, a in zip(_counts(home, stars), _counts(away, stars), strict=True)]
        if roster is not None:
            if game.season < ROSTER_FIRST_SEASON or season_week not in roster_weeks:
                result += [float("nan"), float("nan")]
            else:
                reserve_home = _counts(home | roster_rows.get(home_key, set()), stars)
                reserve_away = _counts(away | roster_rows.get(away_key, set()), stars)
                result += [h - a for h, a in zip(reserve_home[:2], reserve_away[:2], strict=True)]
        values.append(result)
    return pd.DataFrame(values, columns=columns, index=df.index, dtype=float)


def star_preds(df: pd.DataFrame, seasons: list[int], inputs: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """Score six star inputs against the walk-forward blend."""
    frames = {params: frame.assign(**inputs)
              for params, frame in elo_frames(df).items()}
    by_season = []
    for season in seasons:
        test = predict_season(frames, season, window)
        _, train = _train_rows(frames, season, window)
        train = train.dropna(subset=["market_logit"])
        for name, extra in STAR_VARIANTS.items():
            rows = train.dropna(subset=extra)
            if rows["season"].nunique() < MIN_FIT_SEASONS:
                test[name] = test["p_blend"]
            else:
                model = LogitModel.fit(rows, [*BLEND_FEATURES, *extra])
                test[name] = _predict_or_blend(model, test)
        by_season.append(test)
    return _market_games(by_season)
