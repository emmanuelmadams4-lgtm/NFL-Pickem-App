"""Train the active model and write insert-only prediction snapshots.

Policy: weights are fit once per season on completed past seasons. Elo keeps
moving week to week from final results. A new prediction row is written only
when the inputs change; earlier rows are never edited.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nflpi.analytics.backtest import _elo_frames, run_backtest, tune_elo
from nflpi.analytics.metrics import EARLY_WEEK_END, UPSET_GAP, pick_label, uncertainty_grade, upset_watch
from nflpi.config import get_settings
from nflpi.ingestion.service import freshness
from nflpi.models import BacktestRun, Game, MarketSnapshot, ModelVersion, Prediction
from nflpi.predictions.elo import EloParams
from nflpi.predictions.features import BASE_FEATURES, BLEND_FEATURES, add_features
from nflpi.predictions.model import LogitModel

MODEL_KIND = "blend-elo-qb"
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
    old_label: str | None = None
    new_label: str | None = None
    qb_team: str | None = None
    qb_name: str | None = None


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


LIVE_GAME_WINDOW_HOURS = 12  # A game ends well within this window; data refresh marks it final.


def current_week(session: Session) -> tuple[int, int]:
    now = datetime.now(UTC)
    live = session.execute(
        select(Game.season, Game.week)
        .where(
            Game.status.not_in(("final", "postponed")),
            Game.time_tbd.is_(False),
            Game.kickoff_utc <= now,
            Game.kickoff_utc >= now - timedelta(hours=LIVE_GAME_WINDOW_HOURS),
        )
        .order_by(Game.kickoff_utc, Game.game_id)
        .limit(1)
    ).first()
    if live is not None:
        return int(live.season), int(live.week)
    upcoming = session.execute(
        select(Game.season, Game.week)
        .where(
            Game.status == "scheduled",
            Game.time_tbd.is_(False),
            Game.kickoff_utc > now,
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
    events: list[ChangeEvent] = []
    for _, row in targets.iterrows():
        base_p = base.predict_one(row)
        has_market = not pd.isna(row["market_logit"])
        model = blend if has_market else base
        prob = model.predict_one(row)
        home, away = row["home_team"], row["away_team"]
        pick = home if prob >= 0.5 else away
        market_p = None if not has_market else float(row["market_prob"])

        gap = abs(base_p - market_p) if has_market else None
        qb_teams = [team for side, team in (("home", home), ("away", away)) if row[f"{side}_qb_change"]]
        uncertainty, reason_keys = uncertainty_grade(gap, bool(qb_teams), row["week"] <= EARLY_WEEK_END, bool(stale))
        reason_text = {
            "missing_market": "No betting line yet",
            "early_season": f"Early season: week {row['week']}",
            "disagreement": f"Stats model and market differ by {gap:.0%}" if gap is not None else "",
            "qb_change": f"QB change for {', '.join(qb_teams)}",
            "stale": f"{', '.join(stale)} data is stale",
        }
        reasons = [reason_text[key] for key in reason_keys]

        upset = []
        if upset_watch(base_p, market_p):
            dog = away if market_p >= 0.5 else home
            if market_p != 0.5 and (base_p >= 0.5) != (market_p >= 0.5):
                upset.append(f"Stats model picks {dog}, the market underdog")
            if gap >= UPSET_GAP:
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
            old_label = pick_label(max(prev.home_win_prob, 1 - prev.home_win_prob))
            new_label = pick_label(max(prob, 1 - prob))
            qb_team = next(
                (team for col, team in (("home_qb", home), ("away_qb", away))
                 if features.get(col) and features.get(col) != prev.features.get(col)),
                None,
            )
            qb_name = features.get("home_qb" if qb_team == home else "away_qb") if qb_team else None
            if prev.pick != pick or moved >= settings.alert_move_threshold or old_label != new_label or qb_team:
                events.append(ChangeEvent(
                    row["game_id"], prev.home_win_prob, prob, prev.pick, pick, note,
                    old_label, new_label, qb_team, qb_name if isinstance(qb_name, str) else None,
                ))
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
    started = select(Game.game_id).where(
        Game.season == season,
        (Game.status == "final")
        | ((Game.kickoff_utc <= now) & Game.time_tbd.is_(False) & (Game.status != "postponed")),
    )
    ids = [g for g in session.scalars(started) if g not in have]
    refresh_predictions(session, now=now, game_ids=ids, kind="backfill")
    return len(ids)
