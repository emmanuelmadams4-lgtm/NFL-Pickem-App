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
from nflpi.models import BookPrice, Game, MarketQuote, SourceStatus

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
    assert {"game_id", "sportsbook", "market_type", "selection", "observed_at", "line", "price"} in uniques


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
    assert value.save_prices(session, g, "bookone", T0, T0 + timedelta(minutes=5), ALL[:2]) == 0
    assert [(r.price, r.fetched_at) for r in rows(session)] == [(-180, T0), (155, T0)]


def test_v2_changed_price_under_an_unchanged_time_is_kept(session):
    g = game(session)
    value.save_prices(session, g, "bookone", T0, T0, ALL[:2])
    changed = [q("moneyline", "home", None, -200), q("moneyline", "away", None, 170)]
    assert value.save_prices(session, g, "bookone", T0, T0 + timedelta(minutes=5), changed) == 2
    assert sorted((r.price, r.fetched_at) for r in rows(session)) == [
        (-200, T0 + timedelta(minutes=5)),
        (-180, T0),
        (155, T0),
        (170, T0 + timedelta(minutes=5)),
    ]


def test_v2_alternate_line_under_an_unchanged_time_is_kept(session):
    g = game(session)
    alt = [q("spread", "home", -7.0, 150), q("spread", "away", -7.0, -170)]
    value.save_prices(session, g, "bookone", T0, T0, ALL[2:4])
    assert value.save_prices(session, g, "bookone", T0, T0, alt) == 2
    assert {r.line for r in rows(session)} == {-3.5, -7.0}


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
def pair(book_price_home: float, book_price_away: float):
    return [q("moneyline", "home", None, book_price_home), q("moneyline", "away", None, book_price_away)]


def test_v3_newest_complete_pair_at_or_before_as_of_per_book(session):
    g = game(session)
    t1, t2 = T0 + timedelta(hours=1), T0 + timedelta(hours=2)
    value.save_prices(session, g, "bookone", T0, T0, pair(-180, 155))
    value.save_prices(session, g, "bookone", t1, t1, pair(-200, 170))
    value.save_prices(session, g, "booktwo", T0, T0, pair(-170, 150))
    value.save_prices(session, g, "bookone", t2, t2, pair(-250, 200))

    got = value.load_snapshots(session, g, "moneyline", as_of=t1)
    assert all(isinstance(s, MarketSnapshot) for s in got)
    assert [(s.sportsbook, s.selection, s.price, s.observed_at) for s in got] == [
        ("bookone", "home", -200, t1),
        ("bookone", "away", 170, t1),
        ("booktwo", "home", -170, T0),
        ("booktwo", "away", 150, T0),
    ]
    assert value.load_snapshots(session, g, "moneyline", as_of=T0 - timedelta(seconds=1)) == []


def test_v3_never_pairs_two_sides_seen_at_different_times(session):
    g = game(session)
    t1 = T0 + timedelta(hours=1)
    value.save_prices(session, g, "bookone", T0, T0, pair(-180, 155))
    value.save_prices(session, g, "bookone", t1, t1, [q("moneyline", "home", None, -200)])  # away not seen at t1
    got = value.load_snapshots(session, g, "moneyline", as_of=t1)
    assert {(s.selection, s.price, s.observed_at) for s in got} == {("home", -180, T0), ("away", 155, T0)}


def test_v3_a_lone_side_is_never_returned(session):
    g = game(session)
    value.save_prices(session, g, "bookone", T0, T0, [q("moneyline", "home", None, -180)])
    value.save_prices(session, g, "booktwo", T0, T0, pair(-170, 150))
    assert {s.sportsbook for s in value.load_snapshots(session, g, "moneyline", as_of=T0)} == {"booktwo"}


def test_v3_never_pairs_two_sides_on_different_lines(session):
    g = game(session)
    value.save_prices(session, g, "bookone", T0, T0, [q("spread", "home", -3.5, -110), q("spread", "away", -3.5, -110)])
    value.save_prices(session, g, "bookone", T0, T0, [q("spread", "home", -7.0, 150)])  # alternate, no partner
    got = value.load_snapshots(session, g, "spread", as_of=T0)
    assert sorted((s.selection, s.line) for s in got) == [("away", -3.5), ("home", -3.5)]


def test_v3_a_changed_price_under_an_unchanged_time_wins_by_fetch_order(session):
    g = game(session)
    later = T0 + timedelta(minutes=5)
    value.save_prices(session, g, "bookone", T0, T0, pair(-180, 155))
    value.save_prices(session, g, "bookone", T0, later, [q("moneyline", "home", None, -200)])  # only home moved
    got = {s.selection: s.price for s in value.load_snapshots(session, g, "moneyline", as_of=later)}
    assert got == {"home": -200, "away": 155}


def test_v3_alternate_lines_at_one_time_the_latest_fetch_wins(session):
    g = game(session)
    value.save_prices(session, g, "bookone", T0, T0, [q("spread", "home", -3.5, -110), q("spread", "away", -3.5, -110)])
    later = T0 + timedelta(minutes=5)
    value.save_prices(
        session, g, "bookone", T0, later, [q("spread", "home", -7.0, 150), q("spread", "away", -7.0, -170)]
    )
    assert {s.line for s in value.load_snapshots(session, g, "spread", as_of=later)} == {-7.0}


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


def test_v4_setting_turns_extra_markets_on_by_default():
    assert Settings().odds_extra_markets is True
    assert Settings(odds_extra_markets=False).odds_extra_markets is False


# V5 parsing
def core(book: oddsapi.Book) -> list[tuple]:
    """Prices without their time: (market_type, selection, line, price)."""
    return [p[:4] for p in book.prices]


def by_key(event: oddsapi.Event) -> dict[str, oddsapi.Book]:
    return {b.key: b for b in event.books}


def test_v5_all_markets_parsed():
    events, skipped = oddsapi.parse_events(recorded())
    assert skipped == 0
    one = by_key(events[0])["bookone"]
    assert (one.home_ml, one.away_ml) == (-180, 155)
    assert sorted(core(one)) == sorted(
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
    assert sorted(core(two)) == [("moneyline", "away", None, 160), ("moneyline", "home", None, -190)]


def test_v5_missing_total_market_is_fine():
    events, _ = oddsapi.parse_events(recorded())
    kc = events[1].books[0]
    assert {p[0] for p in core(kc)} == {"moneyline", "spread"}
    assert ("spread", "home", -9.5, -110) in core(kc)


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
    assert ("total", "over", 150, -105) in core(book)


def test_v5_spread_bound_inclusive_and_pickem():
    book = _first_book_with("spreads", lambda o: (o[0].update(point=-60), o[1].update(point=60)))
    assert ("spread", "home", -60, -110) in core(book)
    book = _first_book_with("spreads", lambda o: (o[0].update(point=0), o[1].update(point=0)))
    assert ("spread", "home", 0, -110) in core(book)


def test_v5_h2h_only_reply_unchanged():
    data = recorded()
    for event in data:
        for book in event["bookmakers"]:
            book["markets"] = [m for m in book["markets"] if m["key"] == "h2h"]
    events, skipped = oddsapi.parse_events(data)
    assert skipped == 0
    assert all({p[0] for p in b.prices} == {"moneyline"} for e in events for b in e.books)


def test_v6_book_without_h2h_keeps_its_spread_and_total_prices():
    data = recorded()
    data[0]["bookmakers"][0]["markets"] = [m for m in data[0]["bookmakers"][0]["markets"] if m["key"] != "h2h"]
    events, skipped = oddsapi.parse_events(data)
    one = by_key(events[0])["bookone"]
    assert skipped == 0 and (one.home_ml, one.away_ml) == (None, None)
    assert {p[0] for p in one.prices} == {"spread", "total"}


def test_v6_book_with_a_bad_h2h_price_keeps_its_spread_and_total_prices():
    book = _first_book_with("h2h", lambda o: o[0].update(price=50))
    assert book.home_ml is None and {p[0] for p in book.prices} == {"spread", "total"}


def test_v6_book_with_no_usable_market_is_skipped():
    data = recorded()
    data[1]["bookmakers"][0]["markets"] = [{"key": "h2h", "last_update": "2026-10-17T15:00:00Z", "outcomes": []}]
    events, skipped = oddsapi.parse_events(data)
    assert skipped == 1 and events[1].books == []


def test_v4_each_price_carries_its_markets_own_time_not_the_books():
    one = by_key(oddsapi.parse_events(recorded())[0][0])["bookone"]
    assert one.updated == T0  # the book's own field is only a fallback now
    times = {p.market_type: p.observed_at for p in one.prices}
    assert times == {"moneyline": T0, "spread": T0, "total": T0 - timedelta(seconds=30)}


def test_v4_a_market_with_no_time_stores_no_price_and_the_book_time_is_no_stand_in():
    data = recorded()
    for m in data[0]["bookmakers"][0]["markets"]:
        if m["key"] == "totals":
            del m["last_update"]
    one = by_key(oddsapi.parse_events(data)[0][0])["bookone"]
    assert {p.market_type for p in one.prices} == {"moneyline", "spread"}


def test_v4_a_book_without_its_own_time_takes_the_newest_market_time():
    data = recorded()
    del data[0]["bookmakers"][0]["last_update"]
    assert by_key(oddsapi.parse_events(data)[0][0])["bookone"].updated == T0
    data[0]["bookmakers"][0]["last_update"] = "garbage"
    assert [b.key for b in oddsapi.parse_events(data)[0][0].books] == ["booktwo"]  # malformed stays a skip


def test_v5_prices_save_through_value(session):
    g = game(session)
    events, _ = oddsapi.parse_events(recorded())
    one = by_key(events[0])["bookone"]
    quotes = [dict(zip(("market_type", "selection", "line", "price"), p, strict=True)) for p in core(one)]
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
    game(session, "2026_07_MIA_BUF")
    session.add(
        Game(
            game_id="2026_07_KC_LV", season=2026, week=7, game_type="REG",
            kickoff_utc=datetime(2026, 10, 18, 20, 25, tzinfo=UTC), weekday="Sunday",
            away_team="KC", home_team="LV", status="scheduled", source="test",
        )
    )  # fmt: skip
    session.commit()
    now = T0 + timedelta(minutes=4)  # booktwo's clock (15:05) is 1 minute ahead: kept, capped at now
    calls: list[str] = []

    def get(url: str) -> fetch.JsonResult:
        calls.append(url)
        return fetch.JsonResult(200, recorded(), {"x-requests-remaining": "480"})

    result = run.refresh_odds_quotes(session, get=get, now=now, api_key=KEY)
    assert result.status == "ok" and calls == [oddsapi.odds_url(KEY, extra_markets=True)]
    assert session.scalar(select(MarketQuote.id).limit(1)) is not None

    got = {(r.game_id, r.sportsbook, r.market_type, r.selection, r.line, r.price, r.observed_at) for r in rows(session)}
    assert ("2026_07_MIA_BUF", "bookone", "spread", "home", -3.5, -110, T0) in got
    assert (
        "2026_07_MIA_BUF",
        "bookone",
        "total",
        "under",
        47.5,
        -115,
        T0 - timedelta(seconds=30),
    ) in got  # the totals market's own time
    assert ("2026_07_MIA_BUF", "booktwo", "moneyline", "home", None, -190, now) in got  # capped at now
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
    kc_lv(session)
    parse = oddsapi.parse_events
    if db_error:  # a failed statement must not poison the odds run's transaction
        monkeypatch.setattr(run, "save_prices", lambda s, *a: s.execute(text("select 1/0")))

    def bad_prices(data):
        events, skipped = parse(data)
        for event in events:
            event.books[:] = [
                replace(b, prices=(oddsapi.Price("spread", "home", None, -110, T0),)) for b in event.books
            ]
        return events, skipped

    if not db_error:
        monkeypatch.setattr(oddsapi, "parse_events", bad_prices)
    assert run.refresh_odds_quotes(session, get=odds_get, now=T0, api_key=KEY).status == "ok"
    assert session.scalar(select(MarketQuote.id).where(MarketQuote.game_id == "2026_07_KC_LV").limit(1)) is not None
    assert rows(session) == []


# Dwight V1: an outcome name that is not a string drops that market, never the poll
@pytest.mark.parametrize("name", [["Buffalo Bills"], {"a": 1}, None])
def test_v5_non_string_outcome_name_drops_market_only(name):
    book = _first_book_with("spreads", lambda o: o[0].update(name=name))
    assert book.home_ml == -180
    assert not any(p[0] == "spread" for p in book.prices)
    assert any(p[0] == "total" for p in book.prices)


# Dwight V2 + V3: a book clock too far ahead of ours is refused, counted and logged
def test_v11_book_clock_ahead_refused_and_counted(session, caplog):
    from nflpi.ingestion.live import run
    game(session)
    session.commit()
    now = T0 + timedelta(minutes=2)  # booktwo says 15:05: 3 minutes ahead, over the 2 minute skew
    assert run.BOOK_CLOCK_SKEW == timedelta(minutes=2)
    with caplog.at_level("INFO", logger="nflpi.ingestion.live.run"):
        assert run.refresh_odds_quotes(session, get=odds_get, now=now, api_key=KEY).status == "ok"
    assert {r.sportsbook for r in rows(session)} == {"bookone"}
    assert session.scalar(select(MarketQuote.id).where(MarketQuote.game_id == GAME).limit(1)) is not None
    assert "oddsapi book prices: 6 saved, 2 dropped" in caplog.text


# Dwight V5: settings repr hides the Odds API key and the database URL
def test_v5_settings_repr_hides_odds_key_and_database_url():
    shown = repr(Settings(odds_api_key="k" * 32, database_url="postgresql+psycopg://u:sekretpw@h/db"))
    assert "k" * 32 not in shown and "sekretpw" not in shown


# ---- step 18i part 2: the settings, the request, the second key -------------------------------------------------
from nflpi.ingestion.live import fetch, run  # noqa: E402

KEY2 = "b" * 32


def test_p2_extra_markets_on_by_default_and_asked_in_one_request(session):
    kc_lv(session)
    calls: list[str] = []

    def get(url: str) -> fetch.JsonResult:
        calls.append(url)
        return fetch.JsonResult(200, recorded(), {"x-requests-remaining": "480"})

    assert run.refresh_odds_quotes(session, get=get, now=T0, api_key=KEY).status == "ok"
    assert len(calls) == 1 and "markets=h2h%2Cspreads%2Ctotals" in calls[0]


def test_p2_setting_off_asks_for_win_market_only(session, monkeypatch):
    kc_lv(session)
    monkeypatch.setattr(get_settings(), "odds_extra_markets", False)
    calls: list[str] = []

    def get(url: str) -> fetch.JsonResult:
        calls.append(url)
        return fetch.JsonResult(200, recorded(), {})

    run.refresh_odds_quotes(session, get=get, now=T0, api_key=KEY)
    assert calls == [oddsapi.odds_url(KEY)]


def test_p2_a_book_without_a_win_price_keeps_its_spread_and_total_rows_in_the_job(session):
    game(session)
    session.commit()
    data = recorded()
    data[0]["bookmakers"][0]["markets"] = [m for m in data[0]["bookmakers"][0]["markets"] if m["key"] != "h2h"]

    def get(url: str) -> fetch.JsonResult:
        return fetch.JsonResult(200, data, {})

    assert run.refresh_odds_quotes(session, get=get, now=T0 + timedelta(minutes=4), api_key=KEY).status == "ok"
    assert {(r.sportsbook, r.market_type) for r in rows(session) if r.sportsbook == "bookone"} == {
        ("bookone", "spread"),
        ("bookone", "total"),
    }
    sources = set(session.scalars(select(MarketQuote.source)))
    assert "oddsapi:bookone" not in sources and "oddsapi:booktwo" in sources


def test_p2_a_changed_price_under_the_same_market_time_is_stored_by_the_job(session):
    game(session)
    session.commit()
    first, second = recorded(), recorded()
    second[0]["bookmakers"][0]["markets"][1]["outcomes"][0]["price"] = -125  # spread moved, time did not
    for n, data in enumerate((first, second)):
        get = lambda url, d=data: fetch.JsonResult(200, d, {})  # noqa: E731
        run.refresh_odds_quotes(session, get=get, now=T0 + timedelta(minutes=1, hours=7 * n), api_key=KEY)
    prices = sorted(r.price for r in rows(session) if r.sportsbook == "bookone" and r.market_type == "spread")
    assert prices == [-125, -110, -110]


def test_p2_settings_fallback_key_default_empty_and_hidden():
    assert Settings().odds_api_key_fallback == ""
    shown = repr(Settings(odds_api_key_fallback="z" * 32))
    assert "z" * 32 not in shown and "odds_api_key_fallback" not in shown


def test_p2_env_example_has_one_empty_fallback_line():
    lines = (Path(__file__).parents[2] / ".env.example").read_text().splitlines()
    assert lines.count("ODDS_API_KEY_FALLBACK=") == 1
    assert sum(1 for line in lines if line.startswith("ODDS_API_KEY_FALLBACK")) == 1


def _keys_seen(session, replies: list, *, fallback: str | None = KEY2, now=T0):
    seen: list[str] = []

    def get(url: str) -> fetch.JsonResult:
        seen.append(url)
        reply = replies[min(len(seen), len(replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply

    result = run.refresh_odds_quotes(session, get=get, now=now, api_key=KEY, fallback_key=fallback)
    return result, seen


def _ok(remaining: str = "480") -> fetch.JsonResult:
    return fetch.JsonResult(200, recorded(), {"x-requests-remaining": remaining})


def test_p2_out_of_credits_retries_once_with_the_fallback_key_and_logs_the_slot(session, caplog):
    kc_lv(session)
    with caplog.at_level("INFO", logger="nflpi.ingestion.live.run"):
        result, seen = _keys_seen(session, [fetch.Blocked("status 401"), _ok("333")])
    assert result.status == "ok" and len(seen) == 2
    assert result.detail == "primary refused (401), on fallback; 333 credits left"  # W2
    assert f"apiKey={KEY}" in seen[0] and f"apiKey={KEY2}" in seen[1]
    assert "key slot primary refused (401)" in caplog.text
    assert "key slot fallback used, credits remaining: 333" in caplog.text
    assert KEY not in caplog.text and KEY2 not in caplog.text


def test_p2_without_a_fallback_an_out_of_credits_reply_fails_as_before(session):
    kc_lv(session)
    result, seen = _keys_seen(session, [fetch.Blocked("status 401")], fallback="")
    assert result.status == "failed" and len(seen) == 1


def test_p2_fallback_out_of_credits_too_fails_after_one_retry(session):
    kc_lv(session)
    result, seen = _keys_seen(session, [fetch.Blocked("status 401"), fetch.Blocked("status 401")])
    assert result.status == "failed" and len(seen) == 2
    assert result.detail == "Blocked: both keys refused (401)"  # W2: two refusals are not one bad key


def test_p2_a_rate_limit_429_never_switches_keys(session):
    kc_lv(session)
    result, seen = _keys_seen(session, [fetch.Blocked("status 429"), _ok()])
    assert result.status == "failed" and len(seen) == 1


def test_p2_a_good_primary_never_touches_the_fallback(session, caplog):
    kc_lv(session)
    with caplog.at_level("INFO", logger="nflpi.ingestion.live.run"):
        result, seen = _keys_seen(session, [_ok("400")])
    assert result.status == "ok" and len(seen) == 1 and f"apiKey={KEY2}" not in seen[0]
    assert "key slot primary used, credits remaining: 400" in caplog.text


def test_p2_a_fallback_equal_to_the_primary_or_malformed_is_ignored(session):
    kc_lv(session)
    for n, spare in enumerate((KEY, "short", None)):
        result, seen = _keys_seen(session, [fetch.Blocked("status 401")], fallback=spare, now=T0 + timedelta(days=n))
        assert result.status == "failed" and len(seen) == 1


def test_p2_zero_credits_left_does_not_stop_the_source_when_a_fallback_is_set(session):
    kc_lv(session)
    result, seen = _keys_seen(session, [_ok("0")])
    assert result.status == "ok" and len(seen) == 1
    later = T0 + timedelta(hours=7)  # W1: the primary's last count is under 50, so only the fallback is asked
    result, seen = _keys_seen(session, [_ok("300")], now=later)
    assert result.status == "ok" and len(seen) == 1 and f"apiKey={KEY2}" in seen[0]


def test_p2_zero_credits_left_still_stops_the_source_with_no_fallback(session):
    kc_lv(session)
    result, _ = _keys_seen(session, [_ok("0")], fallback="")
    assert result.status == "ok"
    result, seen = _keys_seen(session, [_ok("300")], fallback="", now=T0 + timedelta(hours=7))
    assert result.status == "skipped" and seen == []


def test_p2_fallback_setting_is_read_when_no_key_is_passed(session, monkeypatch):
    kc_lv(session)
    monkeypatch.setattr(get_settings(), "odds_api_key_fallback", KEY2)
    seen: list[str] = []

    def get(url: str) -> fetch.JsonResult:
        seen.append(url)
        if len(seen) == 1:
            raise fetch.Blocked("status 401")
        return _ok()

    assert run.refresh_odds_quotes(session, get=get, now=T0, api_key=KEY).status == "ok" and len(seen) == 2


def test_p2_migration_0010_follows_0009_and_grows_the_key():
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0010_book_prices_key.py"
    text = path.read_text()
    tree = ast.parse(text)
    assigns = {
        n.targets[0].id: n.value.value
        for n in tree.body
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)
    }
    assert assigns["revision"] == "0010" and assigns["down_revision"] == "0009"
    assert '[*OLD, "line", "price"]' in text and "postgresql_nulls_not_distinct=True" in text


def test_p2_total_pair_loads_as_over_and_under(session):
    g = game(session)
    value.save_prices(session, g, "bookone", T0, T0, ALL[4:])
    got = value.load_snapshots(session, g, "total", as_of=T0)
    assert [(s.selection, s.line, s.price) for s in got] == [("over", 47.5, -105), ("under", 47.5, -115)]


def test_p2_h2h_market_without_a_time_stores_no_win_price_at_all():
    data = recorded()
    del data[0]["bookmakers"][0]["markets"][0]["last_update"]
    one = by_key(oddsapi.parse_events(data)[0][0])["bookone"]
    assert (one.home_ml, one.away_ml) == (None, None)  # W5: no time, no price, no market_quotes row
    assert {p.market_type for p in one.prices} == {"spread", "total"}


def test_p2_a_second_h2h_market_is_ignored():
    data = recorded()
    markets = data[0]["bookmakers"][0]["markets"]
    second = copy.deepcopy(markets[0])
    second["outcomes"][0]["price"], second["outcomes"][1]["price"] = -999, 999
    markets.append(second)
    one = by_key(oddsapi.parse_events(data)[0][0])["bookone"]
    assert (one.home_ml, one.away_ml) == (-180, 155)
    assert [p.price for p in one.prices if p.market_type == "moneyline"] == [-180, 155]


def test_p2_adding_a_fallback_lifts_an_earlier_credits_low_stop(session):
    kc_lv(session)
    result, _ = _keys_seen(session, [_ok("0")], fallback="")  # single key: stopped for 35 days
    assert result.status == "ok"
    result, seen = _keys_seen(session, [_ok("300")], now=T0 + timedelta(hours=7))
    assert result.status == "ok" and len(seen) == 1 and f"apiKey={KEY2}" in seen[0]


# --- Security fixes W1 to W6 (Dwight, PR #37)
def _slot(session, name: str):
    return session.get(SourceStatus, f"oddsapi:{name}", populate_existing=True)


def test_w1_a_slot_under_50_is_skipped_while_the_other_is_usable(session):
    kc_lv(session)
    result, seen = _keys_seen(session, [_ok("30")])  # primary answers with 30 left: no stop, a spare is usable
    assert result.status == "ok" and len(seen) == 1
    assert _slot(session, "primary").credits_left == 30
    result, seen = _keys_seen(session, [_ok("300")], now=T0 + timedelta(hours=7))
    assert result.status == "ok" and len(seen) == 1 and f"apiKey={KEY2}" in seen[0]
    assert _slot(session, "fallback").credits_left == 300 and _slot(session, "primary").credits_left == 30


def test_w1_the_last_usable_slot_under_50_sets_the_35_day_stop(session):
    kc_lv(session)
    _keys_seen(session, [_ok("30")])  # primary low
    result, _ = _keys_seen(session, [_ok("40")], now=T0 + timedelta(hours=7))  # fallback low too
    assert result.status == "ok"
    result, seen = _keys_seen(session, [_ok("300")], now=T0 + timedelta(days=34))
    assert result.status == "skipped" and seen == [] and result.detail == "credits low"
    result, seen = _keys_seen(session, [_ok("300")], now=T0 + timedelta(days=35, hours=8))
    assert result.status == "ok" and f"apiKey={KEY}" in seen[0]  # credits reset monthly: primary asked again


def test_w1_a_skipped_slot_is_tried_again_35_days_after_its_low_count(session):
    kc_lv(session)
    _keys_seen(session, [_ok("30")])
    for hours in (7, 14):
        _keys_seen(session, [_ok("300")], now=T0 + timedelta(hours=hours))
    result, seen = _keys_seen(session, [_ok("450")], now=T0 + timedelta(days=35, minutes=1))
    assert result.status == "ok" and f"apiKey={KEY}" in seen[0]


def test_w1_a_single_key_is_exactly_as_before(session):
    kc_lv(session)
    result, seen = _keys_seen(session, [_ok("49")], fallback="")
    assert result.status == "ok"
    result, seen = _keys_seen(session, [_ok("300")], fallback="", now=T0 + timedelta(days=34))
    assert result.status == "skipped" and seen == []
    result, seen = _keys_seen(session, [_ok("300")], fallback="", now=T0 + timedelta(days=36))
    assert result.status == "ok" and len(seen) == 1


def test_w1_a_401_is_still_a_second_signal_when_the_header_said_nothing(session):
    kc_lv(session)
    reply = fetch.JsonResult(200, recorded(), {})  # no x-requests-remaining header
    _keys_seen(session, [reply])
    result, seen = _keys_seen(session, [fetch.Blocked("status 401"), _ok("200")], now=T0 + timedelta(hours=7))
    assert result.status == "ok" and len(seen) == 2


def test_w2_the_run_says_which_slot_answered_and_its_count(session):
    kc_lv(session)
    result, _ = _keys_seen(session, [_ok("480")])
    assert result.detail == "primary answered; 480 credits left"


def test_w2_a_switch_is_kept_on_the_source_status(session):
    kc_lv(session)
    _keys_seen(session, [fetch.Blocked("status 401"), _ok("333")])
    main = session.get(SourceStatus, "oddsapi", populate_existing=True)
    assert main.last_error == "primary refused (401), on fallback" and main.credits_left == 333
    assert _slot(session, "primary").last_error == "refused (401)"
    assert _slot(session, "fallback").credits_left == 333


def test_w2_both_keys_refused_is_said_on_the_run_and_the_status(session):
    kc_lv(session)
    result, _ = _keys_seen(session, [fetch.Blocked("status 401"), fetch.Blocked("status 401")])
    assert result.status == "failed" and result.detail == "Blocked: both keys refused (401)"
    assert session.get(SourceStatus, "oddsapi", populate_existing=True).last_error == (
        "Blocked: both keys refused (401)"
    )


def test_w3_the_key_choice_rests_on_the_header_not_on_a_status_code(session):
    kc_lv(session)
    _keys_seen(session, [_ok("0")])  # primary is spent but the API never printed a 401 for it
    result, seen = _keys_seen(session, [_ok("300")], now=T0 + timedelta(hours=7))
    assert len(seen) == 1 and f"apiKey={KEY2}" in seen[0]  # no refused call to the spent key


def test_w5_a_book_with_no_h2h_time_stores_no_market_quote(session):
    kc_lv(session)
    data = recorded()
    for event in data:
        del event["bookmakers"][0]["markets"][0]["last_update"]
    result = run.refresh_odds_quotes(
        session, get=lambda url: fetch.JsonResult(200, data, {}), now=T0, api_key=KEY, fallback_key=""
    )
    assert result.status == "ok"
    assert session.scalars(select(MarketQuote).where(MarketQuote.source == "oddsapi:bookone")).first() is None


def test_w6_the_log_carries_the_parsed_count_never_the_raw_header(session, caplog):
    kc_lv(session)
    reply = fetch.JsonResult(200, recorded(), {"x-requests-remaining": "12\nforged line"})
    with caplog.at_level("INFO", logger="nflpi.ingestion.live.run"):
        _keys_seen(session, [reply], fallback="")
    assert "forged" not in caplog.text and "credits remaining: None" in caplog.text
