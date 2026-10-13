from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from nflpi.ingestion import nflverse, service, weather
from nflpi.models import Game, IngestionRun, MarketSnapshot
from nflpi.predictions.market import implied_prob, novig_home_prob
from tests.conftest import CURRENT, schedule_rows, team_rows


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


# --- Head coaches: nflverse games.csv carries last season's coach for some clubs (BUF still McDermott in 2026). ---
# The current season's names come from ESPN's season coach list instead (defect, owner 2026-10-13).

@pytest.fixture(autouse=True)
def _fresh_coach_cache():
    service._COACH_CACHE.clear()


ESPN_HOST = "sports.core.api.espn.com"
ESPN_TEAMS = {"2": "BUF", "13": "LV", "14": "LAR", "28": "WSH", "22": "ARI"}


def espn_get(coaches: dict[str, list[str]]):
    """Fake of the ESPN calls: team list, a team's coach list, one coach. Keyed by ESPN abbreviation."""
    ids = {abbr: tid for tid, abbr in ESPN_TEAMS.items()}

    def get(url: str) -> dict:
        if url.endswith("/teams"):
            teams = [{"team": {"id": t, "abbreviation": a}} for t, a in ESPN_TEAMS.items() if a in coaches]
            return {"sports": [{"leagues": [{"teams": teams}]}]}
        if url.endswith("/coaches?lang=en"):
            tid = url.split("/teams/")[1].split("/")[0]
            abbr = next(a for a, i in ids.items() if i == tid)
            refs = [f"http://{ESPN_HOST}/v2/x/coaches/{abbr}/{n}?lang=en" for n in range(len(coaches[abbr]))]
            return {"items": [{"$ref": ref} for ref in refs]}
        abbr, n = url.split("/coaches/")[1].split("?")[0].split("/")
        first, last = coaches[abbr][int(n)].split(" ", 1)
        return {"firstName": first, "lastName": last}

    return get


def test_head_coaches_come_back_under_our_club_codes_and_skip_clubs_with_two_listed():
    coaches = {
        "BUF": ["Joe Brady"],
        "LV": ["Klint Kubiak"],
        "LAR": ["Sean McVay"],
        "WSH": ["Dan Quinn"],
        "ARI": ["A One", "B Two"],  # two listed: interim or unclear
    }
    got = nflverse.fetch_head_coaches(2026, get=espn_get(coaches))
    assert got == {"BUF": "Joe Brady", "LV": "Klint Kubiak", "LA": "Sean McVay", "WAS": "Dan Quinn"}


def test_current_season_coaches_are_replaced_and_other_seasons_are_left_alone(session):
    rows = schedule_rows()
    assert service.ingest_schedules(session, rows, head_coaches={"BUF": "Joe Brady"}).status == "ok"
    current = session.scalars(select(Game).where(Game.season == CURRENT)).all()
    old = session.scalars(select(Game).where(Game.season < CURRENT)).all()
    assert any(g.home_team == "BUF" for g in current) and any(g.away_team == "BUF" for g in current)
    for g in current:  # finished and future games alike
        assert (g.home_coach == "Joe Brady") == (g.home_team == "BUF")
        assert (g.away_coach == "Joe Brady") == (g.away_team == "BUF")
        if g.home_team != "BUF":
            assert g.home_coach == f"{g.home_team} Coach"
    assert all(g.home_coach == f"{g.home_team} Coach" and g.away_coach == f"{g.away_team} Coach" for g in old)
    run = session.scalars(select(IngestionRun).where(IngestionRun.dataset == "head_coaches")).one()
    assert run.status == "ok" and run.source == "espn" and run.rows > 0


def test_a_second_schedule_load_does_not_bring_the_stale_name_back(session):
    rows = schedule_rows()
    service.ingest_schedules(session, rows, head_coaches={"BUF": "Joe Brady"})
    service.ingest_schedules(session, rows, head_coaches={"BUF": "Joe Brady"})
    names = {g.home_coach for g in session.scalars(select(Game).where(Game.season == CURRENT, Game.home_team == "BUF"))}
    assert names == {"Joe Brady"}


def test_a_failed_coach_feed_keeps_the_feed_names_and_is_logged(session, monkeypatch):
    def down(url):
        raise RuntimeError("espn down")

    service.ingest_schedules(session, schedule_rows())
    monkeypatch.setattr(nflverse, "fetch_json", down)
    run = service.ingest_head_coaches(session)
    assert run.status == "failed" and "espn down" in run.error
    assert session.scalar(select(Game.home_coach).where(Game.season == CURRENT, Game.home_team == "BUF")) == "BUF Coach"


def test_a_coach_link_to_another_host_is_never_fetched_and_a_name_too_long_for_the_column_is_skipped():
    calls = []
    inner = espn_get({"BUF": ["Joe Brady"], "LV": ["Klint Kubiak"], "LAR": ["Too " + "L" * 65]})

    def get(url: str) -> dict:
        calls.append(url)
        if "/coaches/BUF/" in url:
            return inner(url)
        if url.endswith("/teams/2/coaches?lang=en"):
            return {"items": [{"$ref": "https://evil.test/coaches/BUF/0?lang=en"}]}
        return inner(url)

    got = nflverse.fetch_head_coaches(2026, get=get)
    assert got == {"LV": "Klint Kubiak"}  # BUF: foreign link skipped; LA: 65 characters skipped
    assert not any("evil.test" in u for u in calls)


# --- Dwight's review (security C1 to C3, function C4, C7, L1 to L3) ---


def test_only_a_plain_https_espn_link_is_followed():
    calls = []
    inner = espn_get({"BUF": ["Joe Brady"], "LV": ["Klint Kubiak"]})
    bad_links = {
        "2": f"https://{ESPN_HOST}@evil.test/coaches/BUF/0?lang=en",  # userinfo: the host is evil.test
        "13": f"https://{ESPN_HOST}:8000/coaches/LV/0?lang=en",  # another port
    }

    def get(url: str) -> dict:
        calls.append(url)
        for tid, link in bad_links.items():
            if url.endswith(f"/teams/{tid}/coaches?lang=en"):
                return {"items": [{"$ref": link}]}
        return inner(url)

    with pytest.raises(RuntimeError, match="no head coaches"):
        nflverse.fetch_head_coaches(2026, get=get)
    assert all(u.startswith("https://site.api.espn.com") or u.endswith("coaches?lang=en") for u in calls)


def test_a_team_id_that_is_not_digits_is_skipped_and_names_are_cleaned():
    messy = {"BUF": ["Joe  Brady​"], "LV": ["Klint Kubiak"]}
    inner = espn_get(messy)

    def get(url: str) -> dict:
        data = inner(url)
        if url.endswith("/teams"):
            data["sports"][0]["leagues"][0]["teams"][1]["team"]["id"] = "13/../x"
        if "/coaches/BUF/" in url:
            return {"firstName": "Joe", "lastName": " Brady​  "}
        return data

    assert nflverse.fetch_head_coaches(2026, get=get) == {"BUF": "Joe Brady"}  # LV skipped: id is not digits


def test_a_coach_name_that_is_not_text_is_skipped():
    inner = espn_get({"BUF": ["Joe Brady"], "LV": ["Klint Kubiak"]})

    def get(url: str) -> dict:
        if "/coaches/LV/" in url:
            return {"firstName": {"x": 1}, "lastName": 7}
        return inner(url)

    assert nflverse.fetch_head_coaches(2026, get=get) == {"BUF": "Joe Brady"}


def test_espn_calls_send_a_user_agent_and_do_not_follow_redirects(monkeypatch):
    seen = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    def fake_get(url, **kwargs):
        seen.update(kwargs)
        return Resp()

    monkeypatch.setattr(nflverse.httpx, "get", fake_get)
    nflverse.fetch_json("https://site.api.espn.com/x")
    assert seen["follow_redirects"] is False and "nflpi" in seen["headers"]["User-Agent"]


def test_too_few_clubs_fails_the_run_and_keeps_the_feed_names(session, monkeypatch):
    service.ingest_schedules(session, schedule_rows())
    monkeypatch.setattr(nflverse, "fetch_head_coaches", lambda season: {"BUF": "Joe Brady"})
    run = service.ingest_head_coaches(session)
    assert run.status == "failed" and "1 of" in run.error
    assert session.scalar(select(Game.home_coach).where(Game.season == CURRENT, Game.home_team == "BUF")) == "BUF Coach"


def test_the_coach_feed_is_fetched_at_most_once_in_the_cache_window(session, monkeypatch):
    service.ingest_schedules(session, schedule_rows())
    calls = []

    def fetch(season):
        calls.append(season)
        return {f"T{i}": f"Coach {i}" for i in range(32)} | {"BUF": "Joe Brady"}

    monkeypatch.setattr(nflverse, "fetch_head_coaches", fetch)
    assert service.ingest_head_coaches(session).status == "ok"
    service.ingest_schedules(session, schedule_rows(), head_coaches=None)  # a plain reload: no new fetch, names stay
    assert service.ingest_head_coaches(session).status == "ok"
    assert calls == [CURRENT]
