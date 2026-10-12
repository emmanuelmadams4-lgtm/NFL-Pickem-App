"""Evidence-grounded matchup reports and Q&A.

The AI gets one evidence pack built from our database and nothing else.
It explains the model's numbers; it cannot change them. Every report is
validated, retried a limited number of times, and saved even when it fails.
"""

import json
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from nflpi.ai.providers import AIError, AIProvider, get_provider
from nflpi.analytics.trends import MIN_GAMES, game_trends
from nflpi.api import schemas as s
from nflpi.api.views import ai_report_out, game_detail
from nflpi.config import get_settings
from nflpi.models import AIReport, AppSetting, BacktestRun

SYSTEM = """You are an NFL analyst writing for one person making weekly Pick'em picks.
Use ONLY the evidence pack you are given. Do not add injuries, stats, quotes, news or
numbers that are not in it. If something important is missing, say so in
data_quality_warnings. The win probability comes from a statistical model in the pack;
repeat it exactly and never invent a different one. Never call a game a lock or guaranteed.
Trends are historical records for context; quote their sample size and seasons, and never let them change the pick.
Write short, plain sentences."""

REPORT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "game_id",
        "recommended_winner",
        "statistical_win_probability",
        "headline",
        "supporting_factors",
        "opposing_factors",
        "injury_impact",
        "rest_and_schedule",
        "weather_impact",
        "market_view",
        "key_uncertainties",
        "what_would_change_the_pick",
        "data_quality_warnings",
        "sources",
    ],
    "properties": {
        "game_id": {"type": "string"},
        "recommended_winner": {"type": "string", "description": "Team abbreviation of the model's pick"},
        "statistical_win_probability": {"type": "number", "description": "Model win probability of the pick, 0-1"},
        "headline": {"type": "string"},
        "supporting_factors": {"type": "array", "items": {"type": "string"}},
        "opposing_factors": {"type": "array", "items": {"type": "string"}},
        "injury_impact": {"type": "string"},
        "rest_and_schedule": {"type": "string"},
        "weather_impact": {"type": "string"},
        "market_view": {"type": "string"},
        "key_uncertainties": {"type": "array", "items": {"type": "string"}},
        "what_would_change_the_pick": {"type": "array", "items": {"type": "string"}},
        "data_quality_warnings": {"type": "array", "items": {"type": "string"}},
        "sources": {"type": "array", "items": {"type": "string"}, "description": "Evidence pack keys used"},
    },
}
AI_CAP_LOCK_KEY: int = 0x4149434150


def evidence_pack(session: Session, game_id: str) -> dict:
    d = game_detail(session, game_id)
    if d is None:
        raise AIError(f"unknown game {game_id}")
    p = d.prediction
    bt = session.scalars(select(BacktestRun).order_by(BacktestRun.id.desc()).limit(1)).first()
    pack = {
        "game": {
            "game_id": d.game_id,
            "season": d.season,
            "week": d.week,
            "kickoff_utc": d.kickoff_utc.isoformat(),
            "weekday": d.weekday,
            "away": d.away.name,
            "home": d.home.name,
            "away_abbr": d.away.abbr,
            "home_abbr": d.home.abbr,
            "stadium": d.stadium,
            "roof": d.roof,
            "surface": d.surface,
            "neutral_site": d.neutral_site,
            "division_game": d.div_game,
            "status": d.status,
        },
        "prediction": None
        if p is None
        else {
            "pick": p.pick,
            "pick_win_probability": round(max(p.home_win_prob, p.away_win_prob), 3),
            "home_win_probability": p.home_win_prob,
            "stats_only_home_probability": p.stats_only_home_prob,
            "uncertainty": p.uncertainty,
            "uncertainty_reasons": p.uncertainty_reasons,
            "model_version": p.model_version,
            "created_at": p.created_at.isoformat(),
            "upset_flags": p.upset_flags,
        },
        "model_factors": [] if p is None else [f.model_dump() for f in p.factors],
        "market": None if not d.market_history else d.market_history[-1].model_dump(mode="json"),
        "market_history": [m.model_dump(mode="json") for m in d.market_history[-6:]],
        "form": {"home": d.home_form.model_dump(), "away": d.away_form.model_dump()},
        "injuries": [i.model_dump(mode="json") for i in d.injuries if i.report_status],
        "weather": d.weather.model_dump(mode="json") if d.weather else None,
        "recent_meetings": [m.model_dump() for m in d.meetings],
        "trends": {
            "min_games": MIN_GAMES,
            "note": (
                f"These historical records are for context only, are not model inputs, and did not change the pick. "
                f"Records with fewer than {MIN_GAMES} games are left out. "
                "'last_5_seasons' means the five finished seasons before this game's season. "
                "Regular season and playoff games both count. QB and coach records are matched by name, "
                "and an upcoming game's QB is a projection."
            ),
            "records": game_trends(session, game_id),
        },
        "data_freshness": p.data_freshness if p else {},
        "model_track_record": None
        if bt is None
        else {
            "backtest_seasons": bt.results["seasons"],
            "accuracy": {m["model"]: round(m["accuracy"], 3) for m in bt.results["models"]},
            "note": "Head-to-head history and rest days showed no proven predictive value in testing.",
        },
    }
    return pack


def _check(report: s.MatchupReport, pack: dict) -> list[str]:
    errors = []
    pred = pack["prediction"]
    if pred:
        if report.recommended_winner != pred["pick"]:
            errors.append(f"recommended_winner must be {pred['pick']} (the model's pick)")
        if abs(report.statistical_win_probability - pred["pick_win_probability"]) > 0.006:
            errors.append(f"statistical_win_probability must be {pred['pick_win_probability']}")
    unknown = [src for src in report.sources if src.split(".")[0] not in pack]
    if unknown:
        errors.append(f"sources must be evidence pack keys; unknown: {unknown}")
    return errors


def _reserve_call(session: Session) -> None:
    """Count a provider attempt before making it, including failed attempts."""
    key = f"ai_attempts_{datetime.now(UTC).date().isoformat()}"
    session.execute(text("select pg_advisory_xact_lock(:k)"), {"k": AI_CAP_LOCK_KEY})
    row = session.get(AppSetting, key, populate_existing=True)
    count = row.value["v"] if row else 0
    if count >= get_settings().ai_daily_call_limit:
        session.rollback()
        raise AIError("Daily AI call limit reached (AI_DAILY_CALL_LIMIT)")
    if row is None:
        session.add(AppSetting(key=key, value={"v": 1}))
    else:
        row.value = {"v": count + 1}
    session.commit()


def generate_report(
    session: Session, game_id: str, provider_name: str = "claude", provider: AIProvider | None = None
) -> s.AIReportOut:
    pack = evidence_pack(session, game_id)
    pred_id = None
    if pack["prediction"]:
        detail = game_detail(session, game_id)
        pred_id = detail.prediction.id if detail and detail.prediction else None
    provider = provider or get_provider(provider_name)
    user = "Evidence pack (JSON):\n" + json.dumps(pack, default=str) + "\n\nWrite the matchup report."
    error = "no attempt"
    cap_error: AIError | None = None
    for _ in range(get_settings().ai_max_retries + 1):
        reserved = False
        try:
            _reserve_call(session)
            reserved = True
            response = provider.complete(SYSTEM, user, REPORT_SCHEMA, max_tokens=16000)
            report = s.MatchupReport.model_validate_json(response)
            problems = _check(report, pack)
            if not problems:
                row = AIReport(
                    game_id=game_id,
                    prediction_id=pred_id,
                    provider=provider.name,
                    model=provider.model,
                    status="ok",
                    report=report.model_dump(),
                )
                session.add(row)
                session.commit()
                return ai_report_out(row)
            error = "; ".join(problems)
        except ValidationError as exc:
            error = f"invalid report format: {exc.errors()[:3]}"
        except AIError as exc:
            error = str(exc)
            if not reserved:
                cap_error = exc
            break
        user += f"\n\nYour previous answer was rejected: {error}. Fix it and answer again."
    row = AIReport(
        game_id=game_id,
        prediction_id=pred_id,
        provider=provider.name,
        model=provider.model,
        status="failed",
        error=error[:2000],
    )
    session.add(row)
    session.commit()
    if cap_error is not None:
        raise cap_error
    return ai_report_out(row)


def answer_question(
    session: Session, game_id: str, question: str, provider_name: str = "claude", provider: AIProvider | None = None
) -> s.AskOut:
    pack = evidence_pack(session, game_id)
    provider = provider or get_provider(provider_name)
    user = (
        "Evidence pack (JSON):\n"
        + json.dumps(pack, default=str)
        + f"\n\nQuestion: {question}\n\nAnswer in under 150 words. If the pack can't answer it, say what is missing."
    )
    _reserve_call(session)
    answer = provider.complete(SYSTEM, user, None, max_tokens=16000)
    row = AIReport(
        game_id=game_id,
        kind="answer",
        provider=provider.name,
        model=provider.model,
        status="ok",
        question=question,
        report={"answer": answer},
    )
    session.add(row)
    session.commit()
    return s.AskOut(answer=answer, provider=provider.name, model=provider.model, created_at=row.created_at)
