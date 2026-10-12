"""Step 2 backend criteria W1-W3 (docs/gauntlet/logs/step-2.md)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from nflpi.ingestion import service, weather
from nflpi.models import Game, Prediction
from nflpi.predictions import engine
from tests.conftest import CURRENT, schedule_rows, team_rows


def test_w1_time_tbd_is_in_the_api_contract(loaded, client):
    tbd = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4).order_by(Game.game_id)).first()
    tbd.time_tbd = True
    loaded.commit()

    games = {g["game_id"]: g for g in client.get(f"/api/weeks/{CURRENT}/4").json()["games"]}
    assert games.pop(tbd.game_id)["time_tbd"] is True
    assert games and all(g["time_tbd"] is False for g in games.values())
    assert client.get(f"/api/games/{tbd.game_id}").json()["time_tbd"] is True


def test_w2_weather_ingest_skips_games_with_no_kickoff_time(loaded, monkeypatch):
    week4 = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4).order_by(Game.game_id)).all()
    week4[0].time_tbd = True
    loaded.commit()
    asked = []
    monkeypatch.setattr(weather, "needs_forecast", lambda roof, stadium_id: True)
    monkeypatch.setattr(weather, "fetch_forecast", lambda stadium_id, kickoff: asked.append(kickoff))

    assert service.ingest_weather(loaded).status == "ok"
    assert sorted(asked) == sorted(g.kickoff_utc for g in week4[1:])


def test_w2_backfill_skips_tbd_and_postponed_games(session):
    service.ingest_schedules(session, schedule_rows())
    service.ingest_teams(session, team_rows())
    engine.train(session, through_season=CURRENT - 1)
    tbd, postponed, played = session.scalars(
        select(Game).where(Game.season == CURRENT, Game.week == 4).order_by(Game.game_id)
    ).all()
    past = datetime.now(UTC) - timedelta(days=1)
    tbd.kickoff_utc, tbd.time_tbd = past, True
    postponed.kickoff_utc, postponed.status = past, "postponed"
    played.kickoff_utc = past
    session.commit()

    engine.backfill_season(session, CURRENT)
    backfilled = set(session.scalars(select(Prediction.game_id).where(Prediction.kind == "backfill")))
    assert played.game_id in backfilled
    assert tbd.game_id not in backfilled and postponed.game_id not in backfilled


def test_w3_results_headline_counts_live_predictions_only(loaded, client):
    engine.backfill_season(loaded, CURRENT)
    perf = client.get(f"/api/performance/{CURRENT}").json()
    backfill = perf["model_backfill"]
    assert perf["model"]["total"] == 0  # every graded game so far was predicted after the fact
    assert backfill["total"] == perf["model_backfill_games"] > 0
    assert sum(w["model_backfill_total"] for w in perf["weeks"]) == backfill["total"]

    live = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)).first()
    live.status, live.home_score, live.away_score = "final", 30, 10  # its live snapshot predates kickoff
    loaded.commit()
    perf = client.get(f"/api/performance/{CURRENT}").json()
    pick = loaded.scalars(select(Prediction.pick).where(Prediction.game_id == live.game_id)).first()
    assert perf["model"]["total"] == 1
    assert perf["model"]["correct"] == int(pick == live.home_team)
    assert perf["model_backfill"] == backfill


def test_w3b_weekly_figures_and_calibration_keep_live_and_backfill_apart(loaded, client):
    engine.backfill_season(loaded, CURRENT)
    perf = client.get(f"/api/performance/{CURRENT}").json()
    weeks = perf["weeks"]
    assert sum(w["model_live_total"] for w in weeks) == perf["model"]["total"] == 0
    assert sum(w["model_backfill_total"] for w in weeks) == perf["model_backfill"]["total"] > 0
    assert sum(w["model_backfill_correct"] for w in weeks) == perf["model_backfill"]["correct"]
    assert sum(b["n"] for b in perf["calibration"]) == 0  # calibration is live-only
    assert sum(b["n"] for b in perf["calibration_backfill"]) == perf["model_backfill"]["total"]

    live = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)).first()
    live.status, live.home_score, live.away_score = "final", 30, 10
    loaded.commit()
    perf = client.get(f"/api/performance/{CURRENT}").json()
    week4 = next(w for w in perf["weeks"] if w["week"] == 4)
    assert (week4["model_live_total"], week4["model_live_correct"]) == (1, perf["model"]["correct"])
    assert sum(b["n"] for b in perf["calibration"]) == 1


def test_w4_week_summary_model_figures_count_live_predictions_only(loaded, client):
    engine.backfill_season(loaded, CURRENT)
    summary = client.get(f"/api/weeks/{CURRENT}/1").json()["summary"]
    assert (summary["model_graded"], summary["model_correct"], summary["model_accuracy"]) == (0, 0, None)

    live = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)).first()
    live.status, live.home_score, live.away_score = "final", 30, 10
    loaded.commit()
    summary = client.get(f"/api/weeks/{CURRENT}/4").json()["summary"]
    assert summary["model_graded"] == 1


def test_w5_no_api_field_mixes_live_and_backfill(loaded, client):
    engine.backfill_season(loaded, CURRENT)
    perf = client.get(f"/api/performance/{CURRENT}").json()
    assert "model_first" not in perf
    mixed = {"model_correct", "model_total", "model_first_correct", "model_first_total"}
    assert all(not mixed & w.keys() for w in perf["weeks"])
