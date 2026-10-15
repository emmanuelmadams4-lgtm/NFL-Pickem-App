"""Train the active model and write insert-only prediction snapshots.

Policy: weights are fit once per season on completed past seasons. Elo keeps
moving week to week from final results. A new prediction row is written only
when the inputs change; earlier rows are never edited.
"""

import hashlib
import json
import logging
import zlib
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nflpi.ai import run_checker
from nflpi.analytics import run_check
from nflpi.analytics.backtest import elo_frames, run_backtest, tune_elo
from nflpi.analytics.manifest import run_record
from nflpi.analytics.metrics import EARLY_WEEK_END, UPSET_GAP, pick_label, uncertainty_grade, upset_watch
from nflpi.analytics.sim_backtest import BASE_SEED, N_SIMULATIONS, WINDOW
from nflpi.api.schemas import SimulationOut
from nflpi.config import get_settings
from nflpi.ingestion.service import freshness
from nflpi.models import AppSetting, BacktestRun, Game, MarketSnapshot, ModelVersion, Prediction, utcnow
from nflpi.picks import home_spread_from_nflverse
from nflpi.predictions import fresh_line
from nflpi.predictions.elo import EloParams
from nflpi.predictions.events import ChangeEvent
from nflpi.predictions.features import BASE_FEATURES, BLEND_FEATURES, add_features
from nflpi.predictions.market import novig_home_prob
from nflpi.predictions.model import LogitModel
from nflpi.predictions.scores import STATS_FEATURES, ScoreModel, add_score_features
from nflpi.sim import DEFAULT_DISTRIBUTION, SimParams, TeamFeatures, simulate_game

MODEL_KIND = "blend-elo-qb"
log = logging.getLogger(__name__)
SIM_LABEL = "Score simulator, football-only inputs: not shown to beat the betting market or the win model"
MAX_EXPECTED_POINTS = 100
_SIM_ARRAYS = ("residual_a", "residual_b", "ot_increments")
REPO_ROOT = Path(__file__).resolve().parents[3]
CHANGE_WORDS = {
    "elo_diff": "team ratings after new results",
    "market_logit": "betting line",
    "market_source": "betting line",
    "market_seen_at": "betting line",
    "home_qb": "starting QB",
    "away_qb": "starting QB",
    "simulation": "score simulation",
    "simulation_check": "score simulation check",
    "home_rest": "rest days",
    "away_rest": "rest days",
}


def load_frame(session: Session, now: datetime | None = None) -> pd.DataFrame:
    now = now or utcnow()
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
    games = list(session.execute(q))
    upcoming = [g.game_id for g, _ in games if g.kickoff_utc > now]
    quotes = fresh_line.pregame_quotes(session, upcoming, now)
    previous: dict[str, Prediction] = {}
    if upcoming:
        latest_prediction = (
            select(Prediction.game_id, func.max(Prediction.id).label("pid"))
            .where(Prediction.game_id.in_(upcoming))
            .group_by(Prediction.game_id)
            .subquery()
        )
        previous = {
            prediction.game_id: prediction
            for prediction in session.scalars(
                select(Prediction).join(latest_prediction, Prediction.id == latest_prediction.c.pid)
            )
        }
    rows = []
    for g, m in games:
        row = {
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
                "spread_line": m.spread_line if m and m.spread_line is not None else np.nan,
                "total_line": m.total_line if m and m.total_line is not None else np.nan,
                "market_kind": m.kind if m else None,
                "market_observed_at": m.observed_at if m else None,
        }
        if g.game_id in upcoming:
            nflverse = fresh_line.Line(
                novig_home_prob(m.home_moneyline, m.away_moneyline) if m else None,
                "nflverse", m.observed_at if m else None,
            )
            old = previous.get(g.game_id)
            old_features = old.features if old else {}
            old_seen = old_features.get("market_seen_at")
            prior = fresh_line.Line(
                old_features.get("market_prob"), old_features.get("market_source", "nflverse"),
                datetime.fromisoformat(old_seen) if old_seen else None,
            ) if old else None
            chosen, refused = fresh_line.choose_line(
                nflverse, quotes.get(g.game_id, []), prior, now=now, kickoff=g.kickoff_utc,
            )
            if refused is not None:
                log.warning(
                    "fresh line sanity refusal for %s: nflverse=%s quote=%s source=%s",
                    g.game_id, nflverse.prob, refused.home_prob, refused.source,
                )
            if chosen.source != "nflverse" and chosen.prob is not None:
                row["home_ml"], row["away_ml"] = fresh_line.fair_moneylines(chosen.prob)
                row["market_source"] = chosen.source
                row["market_seen_at"] = chosen.seen_at.isoformat() if chosen.seen_at else None
        rows.append(row)
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
    frames = elo_frames(df)
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


def save_sim_params(session: Session, season: int, params: SimParams) -> None:
    value = {k: [int(x) for x in v] if k in _SIM_ARRAYS else v for k, v in asdict(params).items()}
    key = f"sim_params_{season}"
    row = session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    session.commit()


def load_sim_params(session: Session, season: int) -> SimParams | None:
    row = session.get(AppSetting, f"sim_params_{season}")
    if row is None:
        return None
    try:
        return SimParams(**{k: np.array(v, dtype=np.int64) if k in _SIM_ARRAYS else v for k, v in row.value.items()})
    except Exception:  # the simulator is optional: a bad stored row means no simulation, never no predictions
        log.exception("stored simulator parameters for season %s are unusable", season)
        return None


def _finite(v: object) -> bool:
    return v is not None and bool(np.isfinite(v))


def _score_model(frame: pd.DataFrame, season: int) -> ScoreModel | None:
    """Football-only expected points fit on the WINDOW seasons before `season` (walk-forward, as the 18c bench)."""
    try:
        return ScoreModel.fit(frame[frame["season"].between(season - WINDOW, season - 1)], STATS_FEATURES)
    except ValueError:
        return None
    except Exception:  # the simulator is optional
        log.exception("score model fit failed for season %s", season)
        return None


def _simulation(row: pd.Series, params: SimParams, model: ScoreModel | None, frame: pd.DataFrame) -> dict | None:
    """The score simulation for one game, or None when the inputs are missing (never guessed)."""
    if model is None:  # no score model also covers a season without parameters: none is fitted for it
        return None
    home, away = (float(x[0]) for x in model.predict(frame[frame["game_id"] == row["game_id"]]))
    if not all(_finite(x) and 0 < x <= MAX_EXPECTED_POINTS for x in (home, away)):
        return None
    spread = float(home_spread_from_nflverse(row["spread_line"])) if _finite(row["spread_line"]) else None
    total = float(row["total_line"]) if _finite(row["total_line"]) and row["total_line"] > 0 else None
    res = simulate_game(
        TeamFeatures(home), TeamFeatures(away), N_SIMULATIONS, params=params,
        seed=zlib.crc32(row["game_id"].encode()) ^ BASE_SEED, spread=spread, total=total,
        neutral_site=bool(row["neutral_site"]), distribution=DEFAULT_DISTRIBUTION, playoff=row["game_type"] != "REG",
    )
    out = {
        "source": "football_only", "distribution": res.distribution, "n_simulations": res.n,
        "home_points": home, "away_points": away, "home_win": res.p_a_win, "away_win": res.p_b_win,
        "tie": res.p_tie, "expected_margin": res.expected_margin, "expected_total": res.expected_total,
        "margin_80": list(res.margin_intervals[0.8]), "total_80": list(res.total_intervals[0.8]),
        "home_spread": spread, "total": total, "home_cover": res.p_a_cover, "away_cover": res.p_b_cover,
        "spread_push": res.p_spread_push, "over": res.p_over, "under": res.p_under, "total_push": res.p_total_push,
    }
    out = {k: [_clean(x) for x in v] if isinstance(v, list) else _clean(v) for k, v in out.items()}
    out |= {"label": SIM_LABEL}
    try:  # what the API cannot serve (a NaN turned null) is never stored: it would 500 the week
        SimulationOut.model_validate(out)
    except ValidationError:
        log.error("simulation for %s fails the API contract; stored as missing", row["game_id"], exc_info=True)
        return None
    return out


def _safe_simulation(row: pd.Series, params: SimParams, model: ScoreModel | None, frame: pd.DataFrame) -> dict | None:
    try:
        return _simulation(row, params, model, frame)
    except Exception:  # the simulator is optional: one game's failure must not stop any prediction
        log.exception("simulation failed for %s; stored as missing", row["game_id"])
        return None


def _simulations(session: Session, targets: pd.DataFrame) -> dict[str, dict | None]:
    """One simulation per target game; None for a season with no learned parameters."""
    if targets.empty:
        return {}
    params = {s: load_sim_params(session, s) for s in {int(s) for s in targets["season"]}}
    if not any(params.values()):
        return dict.fromkeys(targets["game_id"])
    try:
        frame = add_score_features(load_frame(session), EloParams())
    except Exception:  # the simulator is optional
        log.exception("score features failed; no simulations this run")
        return dict.fromkeys(targets["game_id"])
    models = {s: _score_model(frame, s) for s, p in params.items() if p is not None}
    return {
        row["game_id"]: _safe_simulation(row, params[int(row["season"])], models.get(int(row["season"])), frame)
        for _, row in targets.iterrows()
    }


def _last_simulation(session: Session, game_id: str) -> dict | None:
    """The simulation on the game's newest stored prediction, only if it carries the checked stamp (a PASS)."""
    prev = session.scalars(
        select(Prediction).where(Prediction.game_id == game_id).order_by(Prediction.id.desc()).limit(1)
    ).first()
    return prev.features.get("simulation") if prev and prev.features.get("simulation_checked") else None


def _check_run(
    session: Session, targets: pd.DataFrame, frame: pd.DataFrame, simulations: dict[str, dict | None],
    now: datetime, kind: str,
) -> tuple[dict[str, dict | None], dict[str, dict]]:
    """Gate the run's simulations behind the Claude check (step 18k, D74).

    PASS: the run is used as is. FAIL or no verdict: the run is not used; every game keeps its last checked
    simulation and gets a note saying so. The win model, the pick and the confidence points are not read here.
    """
    if not any(simulations.values()):
        return simulations, {}
    if kind == "backfill":  # one request for a whole season is too large; its simulations are stored as missing
        note = "A backfill run is not sent to the run check, so it has no simulation."
        return ({gid: None for gid in simulations},
                {gid: {"status": "not_checked", "note": note} for gid, sim in simulations.items() if sim})
    final_later = (frame["status"] == "final") & (pd.to_datetime(frame["kickoff_utc"], utc=True) > now)
    results_ok = None if kind != "live" else not bool(final_later.any())  # a backfill is labeled after-the-fact
    entries, per_game = {}, {}
    for _, row in targets.iterrows():
        gid, sim = row["game_id"], simulations[row["game_id"]]
        inputs = run_check.game_inputs(row, now, results_ok)
        spread_line = float(row["spread_line"]) if _finite(row["spread_line"]) else None
        entries[gid] = run_check.check_game(gid, sim, inputs, spread_line)
        per_game[gid] = {"n_simulations": sim["n_simulations"] if sim else None,
                         "inputs_used": [name for name, m in inputs.items() if m["present"]] if sim else []}
    record = run_record(
        MODEL_KIND, label=SIM_LABEL, seed=BASE_SEED, seed_note="each game: crc32(game_id) xor seed",
        cutoff_rule=run_check.CUTOFF_RULE,
        latest_kickoff=pd.to_datetime(targets["kickoff_utc"], utc=True).max().isoformat(),
        n_games=len(targets), seasons=sorted({int(s) for s in targets["season"]}),
        uses_closing_line=bool((targets["market_kind"] == "closing").any()), data_files={}, repo_root=REPO_ROOT,
        games=per_game,
    )
    verdict = run_checker.verdict_for(session, record, run_check.build_report(entries), simulations, now)
    if verdict.status == "PASS":
        return simulations, {}
    return _blocked(session, simulations, verdict.status, verdict.games, verdict.cause)


def _blocked(
    session: Session, simulations: dict[str, dict | None], status: str | None, games: tuple[str, ...] = (),
    cause: str | None = None,
) -> tuple[dict[str, dict | None], dict[str, dict]]:
    """A FAIL or no verdict: every game keeps its last checked simulation and gets a fixed-text note."""
    kept = {gid: _last_simulation(session, gid) for gid in simulations}
    failed = status == "FAIL"
    head = "The run check failed" if failed else f"The run check gave no verdict ({cause or 'error'})"
    if failed and games:
        head += f" for {', '.join(games)}"
    marks = {}
    for gid in simulations:
        if simulations[gid] is None and kept[gid] is None:
            continue
        tail = "showing the last checked simulation" if kept[gid] else "no checked simulation yet"
        marks[gid] = {"status": "failed" if failed else "no_verdict", "note": f"{head}. This run is not used; {tail}.",
                      **({} if failed else {"cause": cause or "error"})}
    return kept, marks


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
    f = add_features(load_frame(session, now), EloParams(**p["elo"]))

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
    simulations = _simulations(session, targets)
    try:
        simulations, sim_marks = _check_run(session, targets, f, simulations, now, kind)
    except Exception:  # noqa: BLE001 - the check must never stop the win model, picks and points from being written
        log.exception("run check failed; predictions are written without the new simulations")
        session.rollback()
        simulations, sim_marks = _blocked(session, simulations, None, cause="error")
    target_weeks = {(int(row["season"]), int(row["week"])) for _, row in targets.iterrows()}
    weekly_old: dict[tuple[int, int], dict[str, float]] = {key: {} for key in target_weeks}
    if target_weeks:
        latest_week_prediction = (
            select(Prediction.game_id, func.max(Prediction.id).label("pid"))
            .group_by(Prediction.game_id)
            .subquery()
        )
        for game, prediction in session.execute(
            select(Game, Prediction)
            .join(latest_week_prediction, latest_week_prediction.c.game_id == Game.game_id)
            .join(Prediction, Prediction.id == latest_week_prediction.c.pid)
            .where(Game.season.in_({season for season, _ in target_weeks}))
            .where(Game.week.in_({week for _, week in target_weeks}))
        ):
            key = (game.season, game.week)
            if key in weekly_old:
                weekly_old[key][game.game_id] = prediction.home_win_prob
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
        if isinstance(row.get("market_source"), str):
            features["market_source"] = row["market_source"]
            features["market_seen_at"] = row["market_seen_at"]
        features["upset_flags"] = upset
        for col in ("home_qb", "away_qb", "home_prev_qb", "away_prev_qb"):
            features[col] = row[col]
        features = {k: _clean(v) for k, v in features.items()}
        features["simulation"] = simulations[row["game_id"]]
        if row["game_id"] in sim_marks:  # absent means the run passed its check
            features["simulation_check"] = sim_marks[row["game_id"]]
        h = _hash({"mv": mv.id, "f": features, "u": reasons})
        if features["simulation"] is not None:
            features["simulation_checked"] = True  # after the hash: a stamp alone never writes a new row

        prev = session.scalars(
            select(Prediction).where(Prediction.game_id == row["game_id"]).order_by(Prediction.id.desc()).limit(1)
        ).first()
        if prev and prev.inputs_hash == h:
            continue
        note = None
        if prev:
            changed_keys = {
                key for key in features.keys() | prev.features.keys()
                if prev.features.get(key) != features.get(key)
            }
            changed = {CHANGE_WORDS.get(k, "") for k in changed_keys} - {""}
            what = ", ".join(sorted(changed)) or ("model version" if prev.model_version_id != mv.id else "risk flags")
            note = f"Changed: {what}. {home} win chance {prev.home_win_prob:.0%} → {prob:.0%}."
            moved = round(abs(prob - prev.home_win_prob), 4)
            old_label = pick_label(max(prev.home_win_prob, 1 - prev.home_win_prob))
            new_label = pick_label(max(prob, 1 - prob))
            qb_team = qb_name = None
            for col, team in (("home_qb", home), ("away_qb", away)):
                old_starter = prev.features.get(col)
                new_starter = features.get(col)
                if old_starter and new_starter and new_starter != old_starter:
                    qb_team = team
                    qb_name = new_starter if isinstance(new_starter, str) else None
                    break
            line_keys = {
                "market_prob", "market_logit", "market_source", "market_seen_at",
                "used_market", "market_kind", "upset_flags",
            }
            line_only = bool(changed_keys) and changed_keys <= line_keys and prev.model_version_id == mv.id
            if line_only:
                old_probs = weekly_old[(int(row["season"]), int(row["week"]))]
                old_probs.setdefault(row["game_id"], prev.home_win_prob)
                alert = prev.pick != pick or fresh_line.rank_changed(
                    old_probs, old_probs | {row["game_id"]: prob}, row["game_id"],
                )
            else:
                alert = prev.pick != pick or moved >= settings.alert_move_threshold or old_label != new_label or qb_team
            if alert:
                events.append(ChangeEvent(
                    row["game_id"], prev.home_win_prob, prob, prev.pick, pick, note,
                    old_label, new_label, qb_team, qb_name,
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
