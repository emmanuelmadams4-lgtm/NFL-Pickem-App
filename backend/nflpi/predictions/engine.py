"""Train the active model and write insert-only prediction snapshots.

Policy: weights are fit once per season on completed past seasons. Elo keeps
moving week to week from final results. A new prediction row is written only
when the inputs change; earlier rows are never edited.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nflpi.analytics.backtest import _elo_frames, run_backtest, tune_elo
from nflpi.config import get_settings
from nflpi.ingestion.service import freshness
from nflpi.models import BacktestRun, Game, InjuryReport, MarketSnapshot, ModelVersion, Prediction
from nflpi.predictions.elo import EloParams
from nflpi.predictions.features import BASE_FEATURES, BLEND_FEATURES, add_features
from nflpi.predictions.model import LogitModel

MODEL_KIND = "blend-elo-qb"
UPSET_MIN_PROB = 0.40
UPSET_MIN_GAP = 0.08
DISAGREE_GAP = 0.10
CHANGE_WORDS = {
    "elo_diff": "team ratings after new results",
    "market_logit": "betting line",
    "home_qb": "starting QB",
    "away_qb": "starting QB",
    "home_rest": "rest days",
    "away_rest": "rest days",
}


@dataclass
class ChangeEvent:
    game_id: str
    old_prob: float
    new_prob: float
    old_pick: str
    new_pick: str
    note: str


def load_frame(session: Session) -> pd.DataFrame:
    latest = (
        select(MarketSnapshot.game_id, func.max(MarketSnapshot.id).label("mid"))
        .group_by(MarketSnapshot.game_id)
        .subquery()
    )
    q = (
        select(Game, MarketSnapshot)
        .outerjoin(latest, latest.c.game_id == Game.game_id)
        .outerjoin(MarketSnapshot, MarketSnapshot.id == latest.c.mid)
        .where(Game.season >= get_settings().first_season)
    )
    rows = []
    for g, m in session.execute(q):
        rows.append(
            {
                "game_id": g.game_id,
                "season": g.season,
                "week": g.week,
                "game_type": g.game_type,
                "kickoff_utc": g.kickoff_utc,
                "home_team": g.home_team,
                "away_team": g.away_team,
                "home_score": g.home_score,
                "away_score": g.away_score,
                "status": g.status,
                "neutral_site": g.neutral_site,
                "home_rest": g.home_rest,
                "away_rest": g.away_rest,
                "home_qb": g.home_qb,
                "away_qb": g.away_qb,
                "home_ml": m.home_moneyline if m else np.nan,
                "away_ml": m.away_moneyline if m else np.nan,
                "market_kind": m.kind if m else None,
                "market_observed_at": m.observed_at if m else None,
            }
        )
    df = pd.DataFrame(rows)
    df["home_score"] = df["home_score"].astype("float")
    df["away_score"] = df["away_score"].astype("float")
    return df.sort_values(["kickoff_utc", "game_id"]).reset_index(drop=True)


def active_model(session: Session) -> ModelVersion | None:
    return session.scalars(select(ModelVersion).where(ModelVersion.is_active).order_by(ModelVersion.id.desc())).first()


def train(session: Session, through_season: int) -> ModelVersion:
    """Fit on the window ending at `through_season`, backtest, and activate."""
    settings = get_settings()
    df = load_frame(session)
    seasons = list(range(through_season - settings.train_window_seasons + 1, through_season + 1))
    frames = _elo_frames(df)
    elo = tune_elo(frames, seasons)
    f = frames[elo]
    train_rows = f[f["season"].isin(seasons) & f["home_win"].notna()]
    base = LogitModel.fit(train_rows, BASE_FEATURES)
    blend = LogitModel.fit(train_rows.dropna(subset=["market_logit"]), BLEND_FEATURES)

    params = {"elo": elo.as_dict(), "base": base.as_dict(), "blend": blend.as_dict(), "train_seasons": seasons}
    name = f"{MODEL_KIND}-v1-through-{through_season}-{_hash(params)[:12]}"
    mv = session.scalars(select(ModelVersion).where(ModelVersion.name == name)).first()
    if mv is None:
        test_seasons = list(range(max(settings.first_season + settings.train_window_seasons, 2012), through_season + 1))
        results = run_backtest(df, test_seasons, settings.train_window_seasons)
        session.add(
            BacktestRun(config={"seasons": test_seasons, "window": settings.train_window_seasons}, results=results)
        )
        mv = ModelVersion(
            name=name,
            kind=MODEL_KIND,
            params=params,
            trained_through_season=through_season,
            metrics={m["model"]: m for m in results["models"]},
        )
    for other in session.scalars(select(ModelVersion).where(ModelVersion.is_active)):
        other.is_active = False
    mv.is_active = True
    session.add(mv)
    session.commit()
    return mv


def current_week(session: Session) -> tuple[int, int]:
    upcoming = session.execute(
        select(Game.season, Game.week)
        .where(
            Game.status == "scheduled",
            Game.time_tbd.is_(False),
            Game.kickoff_utc > datetime.now(UTC),
        )
        .order_by(Game.kickoff_utc, Game.game_id)
        .limit(1)
    ).first()
    if upcoming is not None:
        return int(upcoming.season), int(upcoming.week)
    latest = session.execute(
        select(Game.season, Game.week).order_by(Game.season.desc(), Game.week.desc()).limit(1)
    ).first()
    if latest is None:
        raise RuntimeError("no games loaded")
    return int(latest.season), int(latest.week)


def _qb_injuries(session: Session, season: int) -> dict[tuple[int, str], list[InjuryReport]]:
    """Latest status of each QB on the injury report, keyed by (week, team)."""
    latest: dict[tuple[int, str, str], InjuryReport] = {}
    for r in session.scalars(
        select(InjuryReport)
        .where(InjuryReport.season == season, InjuryReport.position == "QB")
        .order_by(InjuryReport.id)
    ):
        latest[(r.week, r.team, r.player_id or r.player)] = r
    out: dict[tuple[int, str], list[InjuryReport]] = {}
    for (week, team, _), r in latest.items():
        if r.report_status in ("Out", "Doubtful", "Questionable"):
            out.setdefault((week, team), []).append(r)
    return out


def _factors(row: pd.Series, model: LogitModel, used_market: bool) -> list[dict]:
    home, away = row["home_team"], row["away_team"]
    contrib = model.contributions(row)
    labels = {
        "market_logit": ("Betting market", f"Line implies {row['market_prob']:.0%} for {home}" if used_market else ""),
        "elo_diff": ("Team strength (Elo)", f"{home} {row['home_elo']:.0f} vs {away} {row['away_elo']:.0f}"),
        "home_field": ("Home field", f"{home} at home"),
        "home_qb_change": ("QB change", f"{row['home_qb']} starts for {home} (last game: {row['home_prev_qb']})"),
        "away_qb_change": ("QB change", f"{row['away_qb']} starts for {away} (last game: {row['away_prev_qb']})"),
    }
    out = []
    for feat, weight in contrib.items():
        if abs(weight) < 1e-3:
            continue
        label, detail = labels[feat]
        out.append(
            {
                "key": feat,
                "label": label,
                "detail": detail,
                "favors": home if weight > 0 else away,
                "weight": round(weight, 4),
            }
        )
    return sorted(out, key=lambda x: -abs(x["weight"]))


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _clean(v: object) -> object:
    if isinstance(v, (float, np.floating)):
        return None if np.isnan(v) else round(float(v), 4)
    if isinstance(v, np.integer):
        return int(v)
    return v


def refresh_predictions(
    session: Session, now: datetime | None = None, game_ids: list[str] | None = None, kind: str = "live"
) -> list[ChangeEvent]:
    """Predict the current and next week (or the given games). Returns alert-worthy changes."""
    now = now or datetime.now(UTC)
    settings = get_settings()
    mv = active_model(session)
    if mv is None:
        raise RuntimeError("no active model; run `python -m nflpi.jobs train` first")
    p = mv.params
    base, blend = LogitModel.from_dict(p["base"]), LogitModel.from_dict(p["blend"])
    f = add_features(load_frame(session), EloParams(**p["elo"]))

    season, week = current_week(session)
    if game_ids is not None:
        targets = f[f["game_id"].isin(game_ids)]
    else:
        targets = f[(f["season"] == season) & f["week"].isin([week, week + 1]) & (f["status"] != "final")]
        targets = targets[pd.to_datetime(targets["kickoff_utc"], utc=True) > now]

    fresh = freshness(session, now)
    stale = [d["dataset"] for d in fresh if d["stale"] and d["dataset"] in ("schedules", "injuries")]
    if kind != "live":
        stale = []
    qb_inj = _qb_injuries(session, season)
    finals = f[f["status"] == "final"]

    events: list[ChangeEvent] = []
    for _, row in targets.iterrows():
        base_p = base.predict_one(row)
        has_market = not pd.isna(row["market_logit"])
        model = blend if has_market else base
        prob = model.predict_one(row)
        home, away = row["home_team"], row["away_team"]
        pick = home if prob >= 0.5 else away
        market_p = None if not has_market else float(row["market_prob"])

        before = finals[(finals["season"] == row["season"]) & (finals["kickoff_utc"] < row["kickoff_utc"])]
        played = pd.concat([before["home_team"], before["away_team"]]).value_counts()
        reasons = []
        for side, team in (("home", home), ("away", away)):
            if row[f"{side}_qb_change"]:
                reasons.append(f"QB change for {team}")
            for inj in qb_inj.get((int(row["week"]), team), []) if row["season"] == season else []:
                reasons.append(f"{team} QB {inj.player} listed {inj.report_status}")
            if played.get(team, 0) < 3:
                reasons.append(f"Early season: {team} has played {played.get(team, 0)} games")
        if not has_market:
            reasons.append("No betting line yet")
        elif abs(base_p - market_p) >= DISAGREE_GAP:
            reasons.append(f"Stats model and market differ by {abs(base_p - market_p):.0%}")
        reasons += [f"{d} data is stale" for d in stale]
        uncertainty = "low" if not reasons else "moderate" if len(reasons) == 1 else "high"

        upset = []
        if has_market:
            dog = away if market_p >= 0.5 else home
            dog_stats_p = 1 - base_p if dog == away else base_p
            if (base_p >= 0.5) != (market_p >= 0.5):
                upset.append(f"Stats model picks {dog}, the market underdog")
            elif dog_stats_p >= UPSET_MIN_PROB:
                upset.append(f"Stats model gives underdog {dog} {dog_stats_p:.0%}")
            if abs(base_p - market_p) >= UPSET_MIN_GAP:
                upset.append(f"Stats {base_p:.0%} vs market {market_p:.0%} for {home}")

        features = {
            c: _clean(row[c])
            for c in [*BLEND_FEATURES, "home_elo", "away_elo", "market_prob", "home_rest", "away_rest"]
        }
        features["stats_only_prob"] = round(base_p, 4)
        features["used_market"] = has_market
        features["market_kind"] = row["market_kind"]
        features["upset_flags"] = upset
        for col in ("home_qb", "away_qb", "home_prev_qb", "away_prev_qb"):
            features[col] = row[col]
        features = {k: _clean(v) for k, v in features.items()}
        h = _hash({"mv": mv.id, "f": features, "u": reasons})

        prev = session.scalars(
            select(Prediction).where(Prediction.game_id == row["game_id"]).order_by(Prediction.id.desc()).limit(1)
        ).first()
        if prev and prev.inputs_hash == h:
            continue
        note = None
        if prev:
            changed = {CHANGE_WORDS.get(k, "") for k in features if prev.features.get(k) != features[k]} - {""}
            what = ", ".join(sorted(changed)) or ("model version" if prev.model_version_id != mv.id else "risk flags")
            note = f"Changed: {what}. {home} win chance {prev.home_win_prob:.0%} → {prob:.0%}."
            moved = abs(prob - prev.home_win_prob)
            if prev.pick != pick or moved >= settings.alert_move_threshold:
                events.append(ChangeEvent(row["game_id"], prev.home_win_prob, prob, prev.pick, pick, note))
        session.add(
            Prediction(
                game_id=row["game_id"],
                model_version_id=mv.id,
                created_at=now,
                kind=kind,
                home_win_prob=round(prob, 4),
                pick=pick,
                features=features,
                factors=_factors(row, model, has_market),
                uncertainty=uncertainty,
                uncertainty_reasons=reasons,
                market_home_prob=market_p,
                inputs_hash=h,
                data_freshness={
                    d["dataset"]: d["last_success"].isoformat() if d["last_success"] else None for d in fresh
                },
                change_note=note,
            )
        )
    session.commit()
    return events


def backfill_season(session: Session, season: int, now: datetime | None = None) -> int:
    """Predict started games of a season that never got a live prediction (labeled 'backfill').

    Valid only when the active model was trained on earlier seasons: Elo and QB
    inputs are pre-game, and the market input is the closing line.
    """
    mv = active_model(session)
    if mv is None or mv.trained_through_season >= season:
        raise RuntimeError("backfill needs a model trained on seasons before the target season")
    now = now or datetime.now(UTC)
    have = set(session.scalars(select(Prediction.game_id)))
    started = select(Game.game_id).where(Game.season == season, (Game.status == "final") | (Game.kickoff_utc <= now))
    ids = [g for g in session.scalars(started) if g not in have]
    refresh_predictions(session, now=now, game_ids=ids, kind="backfill")
    return len(ids)
