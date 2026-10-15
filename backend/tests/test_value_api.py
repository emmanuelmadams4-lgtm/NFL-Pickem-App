"""Step 18l: the 18i value rating per book price in the game reply. Clauses A1-A6 in docs/gauntlet/logs/step-18l.md."""

from datetime import UTC, datetime, timedelta

import pytest

from nflpi import value
from nflpi.api import readmodels
from nflpi.models import Game, ModelVersion, Prediction

NOW = datetime(2026, 10, 17, 15, 0, tzinfo=UTC)
KICKOFF = datetime(2026, 10, 18, 17, 0, tzinfo=UTC)
GAME = "2026_07_MIA_BUF"
HOME_WIN = 0.60
SIM = {  # made-up simulator output at its own lines: home spread -3.5, total 47.5
    "source": "football_only", "distribution": "empirical", "n_simulations": 10000, "home_points": 25.1,
    "away_points": 22.4, "home_win": 0.58, "away_win": 0.41, "tie": 0.01, "expected_margin": 2.7,
    "expected_total": 47.5, "margin_80": [-10.0, 15.0], "total_80": [34.0, 61.0],
    "home_spread": -3.5, "total": 47.5, "home_cover": 0.55, "away_cover": 0.42, "spread_push": 0.03,
    "over": 0.52, "under": 0.48, "total_push": 0.0, "label": "Score simulator (test)",
}


@pytest.fixture
def at_now(monkeypatch):
    monkeypatch.setattr(readmodels, "now_utc", lambda: NOW)


def seed(session, *, sim: dict | None = SIM, prediction: bool = True, kickoff: datetime = KICKOFF) -> None:
    session.add(Game(game_id=GAME, season=2026, week=7, game_type="REG", kickoff_utc=kickoff, weekday="Sunday",
                     away_team="MIA", home_team="BUF", status="scheduled", source="test"))
    session.flush()
    if prediction:
        mv = ModelVersion(name="test-model", kind="logistic", params={}, trained_through_season=2025)
        session.add(mv)
        session.flush()
        session.add(Prediction(game_id=GAME, model_version_id=mv.id, home_win_prob=HOME_WIN, pick="BUF",
                               features={"simulation": sim} if sim else {}, factors=[], uncertainty="moderate",
                               inputs_hash="h" * 64))
    session.flush()


def prices(session, quotes: list[tuple], *, seen: datetime = NOW - timedelta(minutes=5), book: str = "bookone"):
    value.save_prices(session, GAME, book, seen, seen,
                      [{"market_type": m, "selection": sel, "line": line, "price": p} for m, sel, line, p in quotes])
    session.commit()


def ratings(session) -> dict[tuple[str, str], object]:
    detail = readmodels.game_detail(session, GAME)
    return {(r.market_type, r.selection): r for r in detail.value_ratings}


def test_a1_stale_price_is_no_bet_and_never_shown_as_available(session, at_now):
    seed(session)
    prices(session, [("moneyline", "home", None, 120), ("moneyline", "away", None, -140)],
           seen=NOW - timedelta(minutes=31))
    r = ratings(session)[("moneyline", "home")]
    assert r.status == "NO_BET"
    assert "STALE_PRICE" in r.reasons
    assert r.stars is None
    assert "may no longer be offered" in r.note
    assert r.observed_at == NOW - timedelta(minutes=31)


def test_a2_nonpositive_expected_value_is_no_bet(session, at_now):
    seed(session)
    prices(session, [("moneyline", "home", None, -400), ("moneyline", "away", None, 300)])
    r = ratings(session)[("moneyline", "home")]
    assert r.status == "NO_BET"
    assert r.reasons == ["NONPOSITIVE_EV"]
    assert r.expected_value <= 0


def test_a3_positive_value_without_validation_history_is_unrated(session, at_now):
    seed(session)
    prices(session, [("moneyline", "home", None, 120), ("moneyline", "away", None, -140)])
    got = ratings(session)
    home = got[("moneyline", "home")]
    assert home.status == "UNRATED"
    assert "NO_VALIDATION_HISTORY" in home.reasons
    assert home.stars is None
    assert home.expected_value == pytest.approx(HOME_WIN * 2.2 - 1)  # +120 pays 2.2 per unit staked
    assert (home.sportsbook, home.price, home.line) == ("bookone", 120, None)
    assert got[("moneyline", "away")].status == "NO_BET"  # 0.40 at -140 loses value
    assert all(r.status != "RATED" for r in got.values())


def test_a4_spread_and_total_rated_only_at_the_simulated_line(session, at_now):
    seed(session)
    prices(session, [("spread", "home", -3.5, 110), ("spread", "away", -3.5, -130),
                     ("total", "over", 47.5, 105), ("total", "under", 47.5, -125)])
    prices(session, [("spread", "home", -6.5, 150), ("spread", "away", -6.5, -170),
                     ("total", "over", 51.5, 150), ("total", "under", 51.5, -170)], book="booktwo")
    detail = readmodels.game_detail(session, GAME)
    assert {(r.sportsbook, r.market_type, r.selection) for r in detail.value_ratings} == {
        ("bookone", "spread", "home"), ("bookone", "spread", "away"),
        ("bookone", "total", "over"), ("bookone", "total", "under"),
    }
    home = next(r for r in detail.value_ratings if (r.market_type, r.selection) == ("spread", "home"))
    assert home.line == -3.5
    assert home.expected_value == pytest.approx(0.55 * 2.1 + 0.03 - 1)  # a push refunds the stake


def test_a5_no_simulation_rates_only_the_win_market(session, at_now):
    seed(session, sim=None)
    prices(session, [("moneyline", "home", None, 120), ("moneyline", "away", None, -140),
                     ("spread", "home", -3.5, 110), ("spread", "away", -3.5, -130)])
    assert {m for m, _ in ratings(session)} == {"moneyline"}


@pytest.mark.parametrize("case", ["no prediction", "kicked off", "no prices"])
def test_a6_empty_list_when_nothing_can_be_rated(session, at_now, case):
    seed(session, prediction=case != "no prediction", kickoff=NOW - timedelta(minutes=1) if case == "kicked off"
         else KICKOFF)
    if case != "no prices":
        prices(session, [("moneyline", "home", None, 120), ("moneyline", "away", None, -140)])
    assert readmodels.game_detail(session, GAME).value_ratings == []


def test_a7_game_route_serves_the_ratings(session, at_now, client):
    seed(session)
    prices(session, [("moneyline", "home", None, 120), ("moneyline", "away", None, -140)])
    body = client.get(f"/api/games/{GAME}").json()
    assert {(r["market_type"], r["selection"], r["status"]) for r in body["value_ratings"]} == {
        ("moneyline", "home", "UNRATED"), ("moneyline", "away", "NO_BET"),
    }


@pytest.mark.parametrize(("cover", "rated"), [(0.5499, True), (0.5501, True), (0.45, False), (-0.1, False)])
def test_a8_stored_chances_rounded_or_broken_never_fail_the_game_reply(session, at_now, cover, rated):
    # the engine stores simulator chances rounded to 4 places, so a set may sum to 0.9999 or 1.0001
    seed(session, sim=SIM | {"home_cover": cover})
    prices(session, [("moneyline", "home", None, 120), ("moneyline", "away", None, -140),
                     ("spread", "home", -3.5, 110), ("spread", "away", -3.5, -130)])
    got = ratings(session)
    assert ("moneyline", "home") in got
    assert (("spread", "home") in got) is rated
    if rated:
        total = cover + 0.03 + 0.42
        assert got[("spread", "home")].expected_value == pytest.approx(cover / total * 2.1 + 0.03 / total - 1)
