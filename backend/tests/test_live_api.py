"""Step 15d (server side): GET /api/live, the one read the web polls while games are on."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from nflpi.api import live as live_api
from nflpi.api.main import app
from nflpi.ingestion.live import fetch, store
from nflpi.models import IngestionRun, LiveState, MarketQuote
from tests.test_live import seed_game

NOW = datetime(2026, 10, 13, 22, 0, tzinfo=UTC)  # 6:00 PM US Eastern, a Tuesday evening of a test season
FIELDS = {
    "game_id",
    "state",
    "home_team",
    "away_team",
    "home_score",
    "away_score",
    "period",
    "clock",
    "home_win_prob",
    "kalshi_home_prob",
    "updated_at",
}


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch):
    monkeypatch.setattr(live_api, "_now", lambda: NOW)


def game(session, key: str, kickoff: datetime, state: str | None, *, home="LA", away="BUF", **row):
    g = seed_game(session, away, home, kickoff, game_id=f"2026_05_{key}", status="scheduled")
    if state is not None:
        fields = (
            dict(
                home_score=10,
                away_score=7,
                period=2,
                clock="5:00",
                home_wp=0.6,
                tie_wp=0.0,
                last_play_id="9",
                fetched_at=NOW - timedelta(seconds=30),
            )
            | row
        )
        store.add_live_state(session, game_id=g.game_id, event_id="401", state=state, **fields)
        session.commit()
    return g


def confirm(session, source: str, at: datetime):
    store.mark_ok(session, source, at, timedelta(seconds=30))
    session.commit()


def quote(session, g, kind="live", prob=0.7, at=NOW - timedelta(seconds=40)):
    store.add_quote(
        session,
        game_id=g.game_id,
        source="kalshi",
        kind=kind,
        home_prob=prob,
        away_prob=None if prob is None else 1 - prob,
        raw_yes_bid=0.5,
        raw_yes_ask=0.6,
        overround=0.02,
        home_ml=None,
        away_ml=None,
        fetched_at=at,
        source_ts=at,
    )
    session.commit()


def body(client):
    response = client.get("/api/live")
    assert response.status_code == 200, response.text
    return response.json()


def ids(data) -> list[str]:
    return [g["game_id"] for g in data["games"]]


# ------------------------------------------------------------------------------------------- A1, A2


def test_the_route_needs_the_token():
    bare = TestClient(app)
    assert bare.get("/api/live").status_code == 401
    assert bare.get("/api/live", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert bare.get("/api/live", headers={"Authorization": "Bearer test-token"}).status_code == 200


def test_there_is_exactly_one_live_route_and_it_only_reads(client):
    paths = app.openapi()["paths"]
    assert set(paths["/api/live"]) == {"get"}
    assert [p for p in paths if p.startswith("/api/live")] == ["/api/live"]
    for verb in ("post", "put", "patch", "delete"):
        assert getattr(client, verb)("/api/live").status_code == 405


# ------------------------------------------------------------------------------------------- A3


def test_it_returns_games_in_progress_and_finished_today_and_no_others(session, client):
    game(session, "in", NOW - timedelta(hours=2), "in", home="LA")
    game(session, "lost", NOW - timedelta(hours=3), "lost", home="DAL", away="TB", home_wp=None)
    game(session, "post_today", datetime(2026, 10, 13, 17, 0, tzinfo=UTC), "post", home="WAS", away="NYG")
    game(session, "post_yesterday_et", datetime(2026, 10, 13, 3, 0, tzinfo=UTC), "post", home="MIA", away="NE")
    game(session, "post_old", datetime(2026, 10, 11, 17, 0, tzinfo=UTC), "post", home="DEN", away="SEA")
    game(session, "pre", NOW + timedelta(hours=1), "pre", home="KC", away="LV")
    game(session, "stuck", NOW - timedelta(hours=9), "in", home="GB", away="CHI")
    game(session, "never_seen", NOW - timedelta(hours=1), None, home="SF", away="ARI")
    data = body(client)
    assert ids(data) == ["2026_05_post_today", "2026_05_lost", "2026_05_in"]
    assert [g["state"] for g in data["games"]] == ["post", "lost", "in"]


def test_a_game_that_is_8_hours_old_is_still_shown_and_one_a_second_older_is_not(session, client):
    game(session, "edge", NOW - timedelta(hours=8), "in", home="LA")
    game(session, "past", NOW - timedelta(hours=8, seconds=1), "in", home="DAL", away="TB")
    assert ids(body(client)) == ["2026_05_edge"]


def test_a_game_that_runs_past_midnight_eastern_stays_in_the_reply(monkeypatch, session, client):
    late = datetime(2026, 10, 14, 4, 30, tzinfo=UTC)  # 12:30 AM Eastern on the 14th
    monkeypatch.setattr(live_api, "_now", lambda: late)
    game(
        session, "mnf", datetime(2026, 10, 14, 0, 15, tzinfo=UTC), "in", home="LA", away="BUF"
    )  # kicked off 8:15 PM ET
    game(session, "snf", datetime(2026, 10, 13, 23, 20, tzinfo=UTC), "lost", home="DAL", away="TB", home_wp=None)
    assert ids(body(client)) == ["2026_05_snf", "2026_05_mnf"]


def test_an_early_game_that_finished_today_is_still_listed_late_in_the_evening(monkeypatch, session, client):
    night = datetime(2026, 10, 14, 2, 0, tzinfo=UTC)  # 10:00 PM Eastern on the 13th
    monkeypatch.setattr(live_api, "_now", lambda: night)
    game(
        session, "early", datetime(2026, 10, 13, 17, 0, tzinfo=UTC), "post", home="WAS", away="NYG"
    )  # 1 PM ET, 9 h ago
    assert ids(body(client)) == ["2026_05_early"]


def test_the_reply_holds_at_most_20_games_in_kickoff_order(session, client):
    for i in range(25):
        game(session, f"g{i:02d}", NOW - timedelta(hours=2, minutes=i), "in", home="LA")
    data = body(client)
    assert len(data["games"]) == 20
    kickoffs = [g["game_id"] for g in data["games"]]
    assert kickoffs == sorted(kickoffs, reverse=True)  # earliest kickoff first = highest minute offset first
    assert kickoffs[0] == "2026_05_g24" and kickoffs[-1] == "2026_05_g05"


# ------------------------------------------------------------------------------------------- A4, A7


def test_a_game_carries_the_stored_numbers_and_only_the_named_fields(session, client):
    g = game(session, "a", NOW - timedelta(hours=1), "in", home="LA", away="BUF")
    row = body(client)["games"][0]
    assert set(row) == FIELDS
    assert row["game_id"] == g.game_id and row["state"] == "in"
    assert (row["home_team"], row["away_team"]) == ("LA", "BUF")
    assert (row["home_score"], row["away_score"], row["period"], row["clock"]) == (10, 7, 2, "5:00")
    assert row["home_win_prob"] == 0.6 and row["kalshi_home_prob"] is None
    stored = session.scalar(select(LiveState))
    assert datetime.fromisoformat(row["updated_at"]) == stored.fetched_at


@pytest.mark.parametrize("stored", [None, 0.0, 0.5, 1.0])
def test_win_probability_is_espns_number_and_a_missing_one_is_null_never_a_half(session, client, stored):
    game(session, "w", NOW - timedelta(hours=1), "in", home_wp=stored)
    assert body(client)["games"][0]["home_win_prob"] == stored


def test_a_lost_game_shows_its_last_numbers_and_no_probability(session, client):
    game(session, "l", NOW - timedelta(hours=1), "lost", home_wp=None, home_score=21, away_score=17)
    row = body(client)["games"][0]
    assert row["state"] == "lost" and (row["home_score"], row["away_score"]) == (21, 17)
    assert row["home_win_prob"] is None and row["kalshi_home_prob"] is None


def test_a_missing_score_period_or_clock_is_null_not_zero(session, client):
    game(session, "n", NOW - timedelta(hours=1), "in", home_score=None, away_score=None, period=None, clock=None)
    row = body(client)["games"][0]
    assert (row["home_score"], row["away_score"], row["period"], row["clock"]) == (None, None, None, None)


# ------------------------------------------------------------------------------------------- A5


def test_kalshi_shows_the_newest_live_quote_while_the_game_is_on_and_kalshi_was_heard_from_lately(session, client):
    g = game(session, "k", NOW - timedelta(hours=1), "in")
    quote(session, g, prob=0.4, at=NOW - timedelta(minutes=10))
    quote(session, g, prob=0.7, at=NOW - timedelta(minutes=5))
    confirm(session, "kalshi", NOW - timedelta(minutes=4, seconds=59))
    assert body(client)["games"][0]["kalshi_home_prob"] == 0.7


def test_kalshi_goes_null_when_the_last_good_kalshi_poll_is_over_5_minutes_old(session, client):
    g = game(session, "k", NOW - timedelta(hours=1), "in")
    quote(session, g)
    confirm(session, "kalshi", NOW - timedelta(minutes=5, seconds=1))
    assert body(client)["games"][0]["kalshi_home_prob"] is None


def test_kalshi_is_null_when_kalshi_was_never_heard_from(session, client):
    g = game(session, "k", NOW - timedelta(hours=1), "in")
    quote(session, g)
    assert body(client)["games"][0]["kalshi_home_prob"] is None


@pytest.mark.parametrize(
    ("age", "shown"),
    [
        (timedelta(minutes=14, seconds=59), True),
        (timedelta(minutes=15), True),
        (timedelta(minutes=15, seconds=1), False),
    ],
)
def test_a_quote_row_over_15_minutes_old_is_not_shown_even_if_kalshi_was_just_polled(session, client, age, shown):
    """An unchanged poll adds no row and a one-sided late-game market adds none either: the row's age bounds both."""
    g = game(session, "k", NOW - timedelta(hours=1), "in")
    quote(session, g, prob=0.7, at=NOW - age)
    confirm(session, "kalshi", NOW)
    assert body(client)["games"][0]["kalshi_home_prob"] == (0.7 if shown else None)


def test_a_pregame_quote_is_never_shown_as_live(session, client):
    g = game(session, "k", NOW - timedelta(hours=1), "in")
    quote(session, g, kind="pregame")
    confirm(session, "kalshi", NOW)
    assert body(client)["games"][0]["kalshi_home_prob"] is None


def test_a_finished_game_shows_no_kalshi_number(session, client):
    g = game(session, "k", datetime(2026, 10, 13, 17, 0, tzinfo=UTC), "post")
    quote(session, g)
    confirm(session, "kalshi", NOW)
    assert body(client)["games"][0]["kalshi_home_prob"] is None


def test_a_newest_quote_without_a_price_is_null_not_the_older_price(session, client):
    g = game(session, "k", NOW - timedelta(hours=1), "in")
    quote(session, g, prob=0.7, at=NOW - timedelta(minutes=10))
    quote(session, g, prob=None, at=NOW - timedelta(minutes=5))
    confirm(session, "kalshi", NOW)
    assert body(client)["games"][0]["kalshi_home_prob"] is None


def test_quotes_from_other_sources_are_not_kalshi(session, client):
    g = game(session, "k", NOW - timedelta(hours=1), "in")
    store.add_quote(
        session,
        game_id=g.game_id,
        source="oddsapi",
        kind="live",
        home_prob=0.9,
        away_prob=0.1,
        raw_yes_bid=None,
        raw_yes_ask=None,
        overround=None,
        home_ml=-200,
        away_ml=170,
        fetched_at=NOW,
        source_ts=None,
    )
    session.commit()
    confirm(session, "kalshi", NOW)
    assert body(client)["games"][0]["kalshi_home_prob"] is None


# ------------------------------------------------------------------------------------------- A6


@pytest.mark.parametrize(
    ("age", "stale"),
    [
        (None, True),
        (timedelta(seconds=0), False),
        (timedelta(seconds=119), False),
        (timedelta(seconds=120), False),
        (timedelta(seconds=121), True),
        (timedelta(hours=3), True),
    ],
)
def test_stale_means_the_last_good_espn_poll_is_missing_or_more_than_two_minutes_old(session, client, age, stale):
    game(session, "s", NOW - timedelta(hours=1), "in")
    if age is not None:
        confirm(session, "espn_live", NOW - age)
    data = body(client)
    assert data["stale"] is stale
    if age is None:
        assert data["last_confirmed_at"] is None
    else:
        assert datetime.fromisoformat(data["last_confirmed_at"]) == NOW - age


def test_a_quiet_slate_is_an_empty_list_and_stale(session, client):
    data = body(client)
    assert data["games"] == [] and data["stale"] is True and data["last_confirmed_at"] is None


# ------------------------------------------------------------------------------------------- A8


def test_the_route_writes_nothing_and_makes_no_network_call(session, client, monkeypatch):
    game(session, "r", NOW - timedelta(hours=1), "in")
    confirm(session, "espn_live", NOW)

    def no_network(*a, **k):
        raise AssertionError("the route must not fetch")

    monkeypatch.setattr(fetch, "fetch_json", no_network)
    counts = lambda: tuple(  # noqa: E731
        session.scalar(select(func.count()).select_from(t)) for t in (LiveState, MarketQuote, IngestionRun)
    )
    before = counts()
    for _ in range(3):
        body(client)
    session.expire_all()
    assert counts() == before


def test_the_reply_carries_no_ids_from_the_source_and_no_text_beyond_the_named_fields(session, client):
    game(session, "x", NOW - timedelta(hours=1), "in")
    text = client.get("/api/live").text
    for banned in ("espn_event_id", "last_play_id", "tie_wp", "apiKey", "http"):
        assert banned not in text
