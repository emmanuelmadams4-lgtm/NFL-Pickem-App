"""Step 18i: odds history and value ratings. Clauses V1-V10 in docs/gauntlet/logs/step-18i.md."""

import ast
import copy
import json
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from nflpi import value
from nflpi.betting.edge import SettlementProbs
from nflpi.betting.odds import BettingError
from nflpi.betting.snapshot import MarketSnapshot
from nflpi.config import Settings, get_settings
from nflpi.ingestion.live import oddsapi
from nflpi.models import BookPrice, Game

FIXTURES = Path(__file__).parent / "fixtures" / "value"
KEY = "a" * 32
T0 = datetime(2026, 10, 17, 15, 0, tzinfo=UTC)
GAME = "2026_07_MIA_BUF"


def recorded() -> list:
    return json.loads((FIXTURES / "odds_api_all_markets.json").read_text())


def game(session, game_id: str = GAME) -> str:
    session.add(
        Game(
            game_id=game_id,
            season=2026,
            week=7,
            game_type="REG",
            kickoff_utc=datetime(2026, 10, 18, 17, 0, tzinfo=UTC),
            weekday="Sunday",
            away_team="MIA",
            home_team="BUF",
            status="scheduled",
            source="test",
        )
    )
    session.flush()
    return game_id


def q(market_type: str, selection: str, line: float | None, price: float) -> dict:
    return {"market_type": market_type, "selection": selection, "line": line, "price": price}


ALL = [
    q("moneyline", "home", None, -180),
    q("moneyline", "away", None, 155),
    q("spread", "home", -3.5, -110),
    q("spread", "away", -3.5, -110),  # spread line is the HOME spread on both selections
    q("total", "over", 47.5, -105),
    q("total", "under", 47.5, -115),
]


def rows(session) -> list[BookPrice]:
    return list(session.scalars(select(BookPrice).order_by(BookPrice.id)))


def snap(price: float = 150, observed_at: datetime = T0, market_type: str = "moneyline", selection: str = "home"):
    line = None if market_type == "moneyline" else -3.5
    return MarketSnapshot(GAME, "bookone", observed_at, market_type, selection, line, "american", price)


EVEN = SettlementProbs(win=0.5, push=0.0, loss=0.5)


# V1 the table
def test_v1_table_columns_and_unique_key():
    table = BookPrice.__table__
    assert table.name == "book_prices"
    assert {c.name for c in table.columns} == {
        "id",
        "game_id",
        "sportsbook",
        "market_type",
        "selection",
        "line",
        "price",
        "observed_at",
        "fetched_at",
    }
    assert table.c.line.nullable and not table.c.price.nullable and not table.c.observed_at.nullable
    assert [fk.target_fullname for fk in table.c.game_id.foreign_keys] == ["games.game_id"]
    uniques = [
        {c.name for c in con.columns} for con in table.constraints if con.__class__.__name__ == "UniqueConstraint"
    ]
    assert {"game_id", "sportsbook", "market_type", "selection", "observed_at"} in uniques


def test_v1_migration_0009_follows_0008_and_matches_model():
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0009_book_prices.py"
    tree = ast.parse(path.read_text())
    assigns = {
        n.targets[0].id: n.value.value
        for n in tree.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)
    }
    assert assigns["revision"] == "0009" and assigns["down_revision"] == "0008"
    text = path.read_text()
    for column in ("game_id", "sportsbook", "market_type", "selection", "line", "price", "observed_at", "fetched_at"):
        assert f'"{column}"' in text
    assert 'drop_table("book_prices")' in text


# V2 save_prices
def test_v2_saves_all_three_markets_with_times(session):
    g = game(session)
    fetched = T0 + timedelta(minutes=2)
    assert value.save_prices(session, g, "bookone", T0, fetched, ALL) == 6
    stored = rows(session)
    assert [(r.market_type, r.selection, r.line, r.price) for r in stored] == [
        (x["market_type"], x["selection"], x["line"], x["price"]) for x in ALL
    ]
    assert all(r.observed_at == T0 and r.fetched_at == fetched and r.sportsbook == "bookone" for r in stored)


def test_v2_duplicate_is_skipped_never_updated(session):
    g = game(session)
    value.save_prices(session, g, "bookone", T0, T0, ALL[:2])
    changed = [q("moneyline", "home", None, -200), q("moneyline", "away", None, 170)]
    assert value.save_prices(session, g, "bookone", T0, T0 + timedelta(minutes=5), changed) == 0
    assert [(r.price, r.fetched_at) for r in rows(session)] == [(-180, T0), (155, T0)]
    later = T0 + timedelta(minutes=10)
    assert value.save_prices(session, g, "bookone", later, later, changed) == 2
    assert len(rows(session)) == 4


@pytest.mark.parametrize(
    "bad",
    [
        q("parlay", "home", None, -110),
        q("spread", "over", -3.5, -110),
        q("spread", "home", None, -110),
        q("moneyline", "home", -3.5, -110),
        q("moneyline", "home", None, 50),
        q("total", "over", float("nan"), -110),
    ],
)
def test_v2_bad_quote_raises_and_writes_nothing(session, bad):
    g = game(session)
    with pytest.raises(BettingError):
        value.save_prices(session, g, "bookone", T0, T0, [ALL[0], bad])
    assert rows(session) == []


def test_v2_observed_after_fetch_is_refused(session):
    g = game(session)
    with pytest.raises(BettingError):
        value.save_prices(session, g, "bookone", T0 + timedelta(seconds=1), T0, ALL)
    assert rows(session) == []


def test_v2_naive_times_are_refused(session):
    g = game(session)
    with pytest.raises(BettingError):
        value.save_prices(session, g, "bookone", T0.replace(tzinfo=None), T0, ALL)
    with pytest.raises(BettingError):
        value.save_prices(session, g, "bookone", T0, T0.replace(tzinfo=None), ALL)


# V3 load_snapshots
def test_v3_newest_at_or_before_as_of_per_book_and_selection(session):
    g = game(session)
    t1, t2 = T0 + timedelta(hours=1), T0 + timedelta(hours=2)
    value.save_prices(session, g, "bookone", T0, T0, ALL[:2])
    value.save_prices(session, g, "bookone", t1, t1, [q("moneyline", "home", None, -200)])
    value.save_prices(session, g, "booktwo", T0, T0, [q("moneyline", "home", None, -170)])
    value.save_prices(session, g, "bookone", t2, t2, [q("moneyline", "home", None, -250)])

    got = value.load_snapshots(session, g, "moneyline", as_of=t1)
    assert all(isinstance(s, MarketSnapshot) for s in got)
    assert sorted((s.sportsbook, s.selection, s.price, s.observed_at) for s in got) == [
        ("bookone", "away", 155, T0),
        ("bookone", "home", -200, t1),
        ("booktwo", "home", -170, T0),
    ]
    assert all(s.observed_at <= t1 for s in got)
    assert value.load_snapshots(session, g, "moneyline", as_of=T0 - timedelta(seconds=1)) == []


def test_v3_filters_market_and_keeps_line(session):
    g = game(session)
    value.save_prices(session, g, "bookone", T0, T0, ALL)
    spreads = value.load_snapshots(session, g, "spread", as_of=T0)
    assert sorted((s.selection, s.line) for s in spreads) == [("away", -3.5), ("home", -3.5)]
    assert {s.market_type for s in spreads} == {"spread"}


# V4 the request
def test_v4_default_request_is_h2h_only():
    assert "markets=h2h&" in oddsapi.odds_url(KEY)
    assert "spreads" not in oddsapi.odds_url(KEY) and "totals" not in oddsapi.odds_url(KEY)
    assert oddsapi.odds_url(KEY, extra_markets=False) == oddsapi.odds_url(KEY)


def test_v4_extra_markets_only_when_asked():
    url = oddsapi.odds_url(KEY, extra_markets=True)
    assert "markets=h2h%2Cspreads%2Ctotals&" in url
    with pytest.raises(ValueError):
        oddsapi.odds_url("short", extra_markets=True)


def test_v4_no_setting_turns_extra_markets_on():
    assert not any("market" in name for name in Settings.model_fields)


# V5 parsing
def by_key(event: oddsapi.Event) -> dict[str, oddsapi.Book]:
    return {b.key: b for b in event.books}


def test_v5_all_markets_parsed():
    events, skipped = oddsapi.parse_events(recorded())
    assert skipped == 0
    one = by_key(events[0])["bookone"]
    assert (one.home_ml, one.away_ml) == (-180, 155)
    assert sorted(one.prices) == sorted(
        [
            ("moneyline", "away", None, 155),
            ("moneyline", "home", None, -180),
            ("spread", "away", -3.5, -110),
            ("spread", "home", -3.5, -110),
            ("total", "over", 47.5, -105),
            ("total", "under", 47.5, -115),
        ]
    )


def test_v5_inconsistent_spread_and_total_dropped_moneyline_kept():
    events, skipped = oddsapi.parse_events(recorded())
    two = by_key(events[0])["booktwo"]
    assert skipped == 0
    assert (two.home_ml, two.away_ml) == (-190, 160)
    assert sorted(two.prices) == [("moneyline", "away", None, 160), ("moneyline", "home", None, -190)]


def test_v5_missing_total_market_is_fine():
    events, _ = oddsapi.parse_events(recorded())
    kc = events[1].books[0]
    assert {p[0] for p in kc.prices} == {"moneyline", "spread"}
    assert ("spread", "home", -9.5, -110) in kc.prices


def _first_book_with(market: str, mutate) -> oddsapi.Book:
    data = recorded()
    m = next(x for x in data[0]["bookmakers"][0]["markets"] if x["key"] == market)
    mutate(m["outcomes"])
    events, _ = oddsapi.parse_events(data)
    return events[0].books[0]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda o: o[0].update(point=float("inf")),
        lambda o: o[0].update(point="3.5"),
        lambda o: (o[0].update(point=-61), o[1].update(point=61)),
        lambda o: o[0].update(price=50),
        lambda o: o[0].update(price=True),
        lambda o: o[0].update(name="Seattle Seahawks"),
        lambda o: o.pop(),
        lambda o: o.append({"name": "Buffalo Bills", "price": -110, "point": -3.5}),
        lambda o: o[0].pop("point"),
        lambda o: (o[0].update(point=-(10**400)), o[1].update(point=10**400)),
    ],
)
def test_v5_bad_spread_dropped(mutate):
    book = _first_book_with("spreads", mutate)
    assert book.home_ml == -180
    assert not any(p[0] == "spread" for p in book.prices)
    assert any(p[0] == "total" for p in book.prices)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda o: (o[0].update(point=0), o[1].update(point=0)),
        lambda o: (o[0].update(point=151), o[1].update(point=151)),
        lambda o: o[0].update(name="over"),
        lambda o: o[1].update(name="Over"),
        lambda o: o[1].update(price=None),
        lambda o: o[0].update(point=None),
        lambda o: (o[0].update(point=1), o[1].update(point=True)),
        lambda o: (o[0].update(point=10**400), o[1].update(point=10**400)),
    ],
)
def test_v5_bad_total_dropped(mutate):
    book = _first_book_with("totals", mutate)
    assert not any(p[0] == "total" for p in book.prices)
    assert any(p[0] == "spread" for p in book.prices)


def test_v5_total_upper_bound_inclusive():
    book = _first_book_with("totals", lambda o: (o[0].update(point=150), o[1].update(point=150)))
    assert ("total", "over", 150, -105) in book.prices


def test_v5_spread_bound_inclusive_and_pickem():
    book = _first_book_with("spreads", lambda o: (o[0].update(point=-60), o[1].update(point=60)))
    assert ("spread", "home", -60, -110) in book.prices
    book = _first_book_with("spreads", lambda o: (o[0].update(point=0), o[1].update(point=0)))
    assert ("spread", "home", 0, -110) in book.prices


def test_v5_h2h_only_reply_unchanged():
    data = recorded()
    for event in data:
        for book in event["bookmakers"]:
            book["markets"] = [m for m in book["markets"] if m["key"] == "h2h"]
    events, skipped = oddsapi.parse_events(data)
    assert skipped == 0
    assert all({p[0] for p in b.prices} == {"moneyline"} for e in events for b in e.books)


def test_v5_book_without_h2h_still_dropped():
    data = recorded()
    data[0]["bookmakers"][0]["markets"] = [m for m in data[0]["bookmakers"][0]["markets"] if m["key"] != "h2h"]
    events, skipped = oddsapi.parse_events(data)
    assert skipped == 1 and [b.key for b in events[0].books] == ["booktwo"]


def test_v5_prices_save_through_value(session):
    g = game(session)
    events, _ = oddsapi.parse_events(recorded())
    one = by_key(events[0])["bookone"]
    quotes = [dict(zip(("market_type", "selection", "line", "price"), p, strict=True)) for p in one.prices]
    assert value.save_prices(session, g, one.key, one.updated, one.updated, quotes) == 6


# V6 the setting
def test_v6_setting_default_and_validation():
    assert Settings.model_fields["value_max_price_age_minutes"].default == 30
    assert value.max_price_age() == timedelta(minutes=get_settings().value_max_price_age_minutes)
    with pytest.raises(ValueError):
        Settings(value_max_price_age_minutes=0)


# V7 rating through betting_advice
def test_v7_stale_price_is_no_bet():
    r = value.rate_price(snap(), EVEN, now=T0 + timedelta(minutes=31), max_age=timedelta(minutes=30))
    assert (r.advice.status, r.advice.reasons) == ("NO_BET", ("STALE_PRICE",))
    edge = value.rate_price(snap(), EVEN, now=T0 + timedelta(minutes=30), max_age=timedelta(minutes=30))
    assert edge.advice.status == "UNRATED"


def test_v7_future_price_is_no_bet():
    r = value.rate_price(snap(), EVEN, now=T0 - timedelta(seconds=1), max_age=timedelta(minutes=30))
    assert r.advice.status == "NO_BET" and "STALE_PRICE" in r.advice.reasons


def test_v7_nonpositive_ev_is_no_bet():
    r = value.rate_price(snap(price=-110), EVEN, now=T0, max_age=timedelta(minutes=30))
    assert (r.advice.status, r.advice.reasons) == ("NO_BET", ("NONPOSITIVE_EV",))
    zero = value.rate_price(snap(price=100), EVEN, now=T0, max_age=timedelta(minutes=30))
    assert zero.advice.status == "NO_BET" and zero.advice.expected_value == 0


def test_v7_default_max_age_is_the_setting():
    minutes = get_settings().value_max_price_age_minutes
    assert value.rate_price(snap(), EVEN, now=T0 + timedelta(minutes=minutes)).advice.status == "UNRATED"
    late = value.rate_price(snap(), EVEN, now=T0 + timedelta(minutes=minutes, seconds=1))
    assert late.advice.status == "NO_BET"


def test_v7_goes_through_picks_betting_advice(monkeypatch):
    import nflpi.picks

    seen = {}

    def fake(snapshot, probs, **kw):
        seen.update(kw)
        return nflpi.picks.Advice("UNRATED", None, 0.25, ("NO_VALIDATION_HISTORY",), True)

    monkeypatch.setattr(value.rate, "betting_advice", fake)
    r = value.rate_price(snap(), EVEN, now=T0, max_age=timedelta(minutes=5), qb_missing=True)
    assert r.advice.expected_value == 0.25
    assert seen["max_age"] == timedelta(minutes=5) and seen["qb_missing"] is True and seen.get("rubric") is None


# V8 UNRATED until section 3.4
@pytest.mark.parametrize("price", [101, 150, 300, 1000])
def test_v8_positive_value_is_never_starred(price):
    r = value.rate_price(snap(price=price), EVEN, now=T0, max_age=timedelta(minutes=30))
    assert r.advice.status == "UNRATED" and r.advice.stars is None
    assert r.advice.reasons == ("NO_VALIDATION_HISTORY",)


def test_v8_spread_and_total_ratings_unrated_too():
    for market, selection in (("spread", "home"), ("total", "over")):
        r = value.rate_price(snap(150, T0, market, selection), EVEN, now=T0, max_age=timedelta(minutes=30))
        assert r.advice.status == "UNRATED"


# V9 never shown as still available
def test_v9_rating_carries_time_and_age():
    now = T0 + timedelta(minutes=12)
    r = value.rate_price(snap(), EVEN, now=now, max_age=timedelta(minutes=30))
    assert (r.sportsbook, r.market_type, r.selection, r.line, r.price) == ("bookone", "moneyline", "home", None, 150)
    assert r.observed_at == T0 and r.age == timedelta(minutes=12)
    assert "2026-10-17 15:00 UTC" in r.note and "bookone" in r.note and "may no longer be offered" in r.note


def test_v9_note_time_is_utc_whatever_the_zone():
    eastern = timezone(timedelta(hours=-4))
    r = value.rate_price(snap(observed_at=T0.astimezone(eastern)), EVEN, now=T0, max_age=timedelta(minutes=30))
    assert "2026-10-17 15:00 UTC" in r.note and r.age == timedelta(0)


@pytest.mark.parametrize("minutes", [0, 12, 31])
def test_v9_no_field_or_text_claims_available(minutes):
    r = value.rate_price(snap(), EVEN, now=T0 + timedelta(minutes=minutes), max_age=timedelta(minutes=30))
    names = {f.name for f in fields(r)}
    assert not names & {"available", "is_available", "current", "live", "still_available"}
    text = r.note.lower()
    for claim in ("still available", "available now", "current price", "live price", "bet now"):
        assert claim not in text


# V10 no network, no wagering
def test_v10_value_package_has_no_network_or_wager_code():
    root = Path(value.__file__).parent
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        imported |= {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not any(
            m.split(".")[0] in {"httpx", "requests", "urllib", "socket", "http", "aiohttp"} for m in imported
        ), path
        assert not any("fetch" in m or "oddsapi" in m for m in imported), path
        assert "place_bet" not in path.read_text() and "wager" not in path.read_text().lower(), path


def test_v10_fixture_is_not_mutated_by_parse():
    data = recorded()
    before = copy.deepcopy(data)
    oddsapi.parse_events(data)
    assert data == before


# V11 the odds job stores every price, sides as our game has them
def test_v11_odds_job_saves_book_prices_with_our_sides(session):
    from nflpi.ingestion.live import fetch, run
    from nflpi.models import MarketQuote

    game(session, "2026_07_MIA_BUF")
    session.add(
        Game(
            game_id="2026_07_KC_LV", season=2026, week=7, game_type="REG",
            kickoff_utc=datetime(2026, 10, 18, 20, 25, tzinfo=UTC), weekday="Sunday",
            away_team="KC", home_team="LV", status="scheduled", source="test",
        )
    )  # fmt: skip
    session.commit()
    now = T0 + timedelta(minutes=2)
    calls: list[str] = []

    def get(url: str) -> fetch.JsonResult:
        calls.append(url)
        return fetch.JsonResult(200, recorded(), {"x-requests-remaining": "480"})

    result = run.refresh_odds_quotes(session, get=get, now=now, api_key=KEY)
    assert result.status == "ok" and calls == [oddsapi.odds_url(KEY)]
    assert session.scalar(select(MarketQuote.id).limit(1)) is not None

    got = {(r.game_id, r.sportsbook, r.market_type, r.selection, r.line, r.price, r.observed_at) for r in rows(session)}
    assert ("2026_07_MIA_BUF", "bookone", "spread", "home", -3.5, -110, T0) in got
    assert ("2026_07_MIA_BUF", "bookone", "total", "under", 47.5, -115, T0) in got
    assert ("2026_07_MIA_BUF", "booktwo", "moneyline", "home", None, -190, now) in got  # book time 15:05 capped at now
    assert ("2026_07_KC_LV", "bookone", "spread", "away", 9.5, -110, T0) in got  # their home KC is our away; LV +9.5
    assert ("2026_07_KC_LV", "bookone", "spread", "home", 9.5, -110, T0) in got
    assert ("2026_07_KC_LV", "bookone", "moneyline", "away", None, -400, T0) in got
    assert len(got) == 6 + 2 + 4
    assert all(r.fetched_at == now for r in rows(session))


# Integrator fix: spread line is the HOME spread on both stored selections (betting.snapshot)
def test_v5_stored_away_spread_settles_on_home_line(session):
    from nflpi.betting.settle import settle
    from nflpi.betting.snapshot import no_vig_probabilities

    g = game(session)
    one = by_key(oddsapi.parse_events(recorded())[0][0])["bookone"]
    value.save_prices(session, g, "bookone", T0, T0, [p._asdict() for p in one.prices])
    pair = {s.selection: s for s in value.load_snapshots(session, g, "spread", as_of=T0)}
    assert pair["away"].line == pair["home"].line == -3.5
    assert settle(pair["away"], 20, 17) == "win"  # home wins by 3 at -3.5: away covers
    assert settle(pair["home"], 20, 17) == "loss"
    assert set(no_vig_probabilities(list(pair.values()))) == {"home", "away"}


def kc_lv(session) -> None:
    session.add(
        Game(
            game_id="2026_07_KC_LV", season=2026, week=7, game_type="REG",
            kickoff_utc=datetime(2026, 10, 18, 20, 25, tzinfo=UTC), weekday="Sunday",
            away_team="KC", home_team="LV", status="scheduled", source="test",
        )
    )  # fmt: skip
    session.commit()


def odds_get(url: str):
    from nflpi.ingestion.live import fetch

    return fetch.JsonResult(200, recorded(), {"x-requests-remaining": "480"})


def test_v11_flipped_book_spread_pair_settles_on_our_home_line(session):
    from nflpi.betting.settle import settle
    from nflpi.betting.snapshot import no_vig_probabilities
    from nflpi.ingestion.live import run

    kc_lv(session)
    assert run.refresh_odds_quotes(session, get=odds_get, now=T0, api_key=KEY).status == "ok"
    pair = {s.selection: s for s in value.load_snapshots(session, "2026_07_KC_LV", "spread", as_of=T0)}
    assert pair["away"].line == pair["home"].line == 9.5  # our home LV +9.5
    assert settle(pair["home"], 10, 19) == "win"  # KC (our away) wins by 9: LV +9.5 covers
    assert settle(pair["away"], 10, 19) == "loss"
    assert set(no_vig_probabilities(list(pair.values()))) == {"home", "away"}


@pytest.mark.parametrize("db_error", [False, True])
def test_v11_bad_book_price_keeps_moneyline_quote_and_job_ok(session, monkeypatch, db_error):
    from sqlalchemy import text

    from nflpi.ingestion.live import run
    from nflpi.models import MarketQuote

    kc_lv(session)
    parse = oddsapi.parse_events
    if db_error:  # a failed statement must not poison the odds run's transaction
        monkeypatch.setattr(run, "save_prices", lambda s, *a: s.execute(text("select 1/0")))

    def bad_prices(data):
        events, skipped = parse(data)
        for event in events:
            event.books[:] = [replace(b, prices=(oddsapi.Price("spread", "home", None, -110),)) for b in event.books]
        return events, skipped

    if not db_error:
        monkeypatch.setattr(oddsapi, "parse_events", bad_prices)
    assert run.refresh_odds_quotes(session, get=odds_get, now=T0, api_key=KEY).status == "ok"
    assert session.scalar(select(MarketQuote.id).where(MarketQuote.game_id == "2026_07_KC_LV").limit(1)) is not None
    assert rows(session) == []
