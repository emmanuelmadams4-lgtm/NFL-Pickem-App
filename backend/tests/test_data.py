from datetime import UTC, datetime

from sqlalchemy import func, select

from nflpi.ingestion import nflverse, service, weather
from nflpi.models import Game, IngestionRun, MarketSnapshot
from nflpi.predictions.market import implied_prob, novig_home_prob
from tests.conftest import schedule_rows, team_rows


def test_franchise_codes_are_normalized():
    assert nflverse.franchise("OAK") == "LV"
    assert nflverse.franchise("SD") == "LAC"
    assert nflverse.franchise("STL") == "LA"
    assert nflverse.franchise("BUF") == "BUF"


def test_kickoff_is_converted_from_eastern_to_utc():
    assert nflverse.kickoff_utc("2026-09-13", "13:00") == datetime(2026, 9, 13, 17, 0, tzinfo=UTC)  # EDT
    assert nflverse.kickoff_utc("2026-12-13", "13:00") == datetime(2026, 12, 13, 18, 0, tzinfo=UTC)  # EST


def test_parse_games_handles_missing_values():
    row = schedule_rows()[-1] | {"home_moneyline": "", "away_moneyline": "NA", "home_rest": "", "temp": ""}
    g = nflverse.parse_games([row], 2000)[0]
    assert g["status"] == "scheduled" and g["home_score"] is None
    assert g["_home_ml"] is None and g["_away_ml"] is None and g["home_rest"] is None and g["temp_f"] is None


def test_injury_parsing_skips_empty_rows_and_maps_teams():
    rows = [
        {
            "season": "2026",
            "game_type": "REG",
            "team": "OAK",
            "week": "5",
            "gsis_id": "00-1",
            "position": "QB",
            "full_name": "A Passer",
            "report_primary_injury": "Knee",
            "practice_primary_injury": "",
            "report_status": "Out",
            "practice_status": "Did Not Participate In Practice",
        },
        {
            "season": "2026",
            "game_type": "REG",
            "team": "BUF",
            "week": "5",
            "gsis_id": "00-2",
            "position": "WR",
            "full_name": "B Runner",
            "report_primary_injury": "",
            "practice_primary_injury": "",
            "report_status": "",
            "practice_status": "",
        },
    ]
    out = nflverse.parse_injuries(rows, datetime.now(UTC))
    assert len(out) == 1 and out[0]["team"] == "LV" and out[0]["report_status"] == "Out"


def test_novig_probabilities_sum_to_one():
    assert abs(implied_prob(-150) - 0.6) < 1e-9 and abs(implied_prob(130) - 100 / 230) < 1e-9
    p = novig_home_prob(-150, 130)
    assert 0.5 < p < 0.6
    assert novig_home_prob(None, 130) is None


def test_schedule_ingest_is_idempotent_and_tracks_line_moves(session):
    rows = schedule_rows()
    assert service.ingest_schedules(session, rows).status == "ok"
    n_games = session.scalar(select(func.count(Game.game_id)))
    n_snaps = session.scalar(select(func.count(MarketSnapshot.id)))
    service.ingest_schedules(session, rows)  # same data again: nothing new
    assert session.scalar(select(func.count(Game.game_id))) == n_games
    assert session.scalar(select(func.count(MarketSnapshot.id))) == n_snaps

    moved = [r | {"home_moneyline": "-400"} if r["game_id"] == rows[-1]["game_id"] else r for r in rows]
    service.ingest_schedules(session, moved)
    snaps = session.scalars(select(MarketSnapshot).where(MarketSnapshot.game_id == rows[-1]["game_id"])).all()
    assert [s.home_moneyline for s in snaps] == [float(rows[-1]["home_moneyline"]), -400.0]


def test_failed_download_keeps_old_data_and_is_logged(session, monkeypatch):
    service.ingest_schedules(session, schedule_rows())
    before = session.scalar(select(func.count(Game.game_id)))

    def boom(path):
        raise RuntimeError("nflverse down")

    monkeypatch.setattr(nflverse, "fetch_csv", boom)
    run = service.ingest_schedules(session)
    assert run.status == "failed" and "nflverse down" in run.error
    assert session.scalar(select(func.count(Game.game_id))) == before
    fresh = {f["dataset"]: f for f in service.freshness(session)}
    assert fresh["schedules"]["last_success"] is not None and fresh["teams"]["stale"]


def test_teams_load_only_current_franchises(session):
    service.ingest_schedules(session, schedule_rows())
    rows = team_rows() + [team_rows()[0] | {"team_abbr": "OAK"}]
    assert service.ingest_teams(session, rows).rows == 6
    assert session.scalar(select(func.count(IngestionRun.id))) == 2


def test_weather_picks_the_kickoff_hour():
    payload = {
        "hourly": {
            "time": ["2026-10-18T17:00", "2026-10-18T18:00"],
            "temperature_2m": [50, 52],
            "wind_speed_10m": [10, 14],
            "wind_gusts_10m": [20, 25],
            "precipitation_probability": [10, 40],
            "precipitation": [0, 0.1],
        }
    }
    wx = weather.pick_kickoff_hour(payload, datetime(2026, 10, 18, 18, 0, tzinfo=UTC))
    assert wx == {"temp_f": 52, "wind_mph": 14, "gust_mph": 25, "precip_prob": 40, "precip_in": 0.1}
    assert weather.pick_kickoff_hour(payload, datetime(2026, 10, 20, 18, 0, tzinfo=UTC)) is None
    assert not weather.needs_forecast("dome", "DET00") and weather.needs_forecast("closed", "DAL00")
