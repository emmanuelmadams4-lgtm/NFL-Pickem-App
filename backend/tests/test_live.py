"""Step 15a-d,g: live scores, market quotes and the guarded fetch behind them.

No test touches the network. Requests go to an httpx MockTransport and DNS is an injected function. The recorded
real replies (tests/fixtures/live) were fetched by hand on 2026-10-13. No game was in progress then, so every
in-progress reply here is hand-made from a recorded finished one.
"""

import copy
import json
import socket
import ssl
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import inspect, select

from nflpi.config import Settings
from nflpi.db import get_engine
from nflpi.ingestion.live import espn, fetch, kalshi, oddsapi, run, store
from nflpi.models import Game, IngestionRun, LiveState, MarketQuote, SourceStatus
from nflpi.predictions.market import implied_prob, novig_home_prob

FIXTURES = Path(__file__).parent / "fixtures" / "live"
PUBLIC_IP = "93.184.216.34"
JSON = {"content-type": "application/json; charset=utf-8"}
ESPN_HOST = "site.api.espn.com"
URL = f"https://{ESPN_HOST}/apis/site/v2/sports/football/nfl/scoreboard"


def public_dns(host: str) -> list[str]:
    return [PUBLIC_IP]


class Web:
    """A fake internet: routes[(host, path)] is a Response or a callable(request) -> Response."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        route = self.routes.get((request.headers["host"], request.url.path))
        if route is None:
            return httpx.Response(404, headers=JSON, content=b"{}")
        return route(request) if callable(route) else route

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def paths(self) -> list[str]:
        return [f"{r.headers['host']}{r.url.path}" for r in self.requests]


def ok(body: bytes = b'{"a": 1}', **headers) -> httpx.Response:
    return httpx.Response(200, headers=JSON | headers, content=body)


def one(response, host: str = ESPN_HOST, path: str = "/apis/site/v2/sports/football/nfl/scoreboard") -> Web:
    return Web({(host, path): response})


def get(url: str, web: Web, **kw) -> fetch.JsonResult:
    return fetch.fetch_json(url, resolver=kw.pop("resolver", public_dns), transport=web.transport, **kw)


# ---------------------------------------------------------------- the guarded fetch (15a, 15g)


def test_only_three_exact_hosts_are_on_the_allowlist():
    assert fetch.ALLOWED_HOSTS == frozenset({"site.api.espn.com", "external-api.kalshi.com", "api.the-odds-api.com"})


@pytest.mark.parametrize(
    "url",
    [
        "http://site.api.espn.com/x",
        "https://evil.example/x",
        "https://site.api.espn.com.evil.example/x",
        "https://sports.core.api.espn.com/v2/x",  # a real ESPN host, but not on our list
        "https://user:pw@site.api.espn.com/x",
        "https://site.api.espn.com:8443/x",
        "file:///etc/passwd",
        "https://site.api.espn.com/a\\b",
        "https://site.api.espn.com/a\x01b",
        "https://site.api.espn.com/a\tb",
        "https://site.api.espn.com:443@evil.example/x",
    ],
)
def test_a_url_that_is_not_https_on_an_allowed_host_is_refused_before_any_lookup(url):
    web, looked_up = Web({}), []
    with pytest.raises(fetch.Blocked):
        get(url, web, resolver=lambda h: looked_up.append(h) or [PUBLIC_IP])
    assert web.requests == [] and looked_up == []


@pytest.mark.parametrize(
    "addresses",
    [
        ["10.0.0.5"],
        ["192.168.1.1"],
        ["172.16.0.9"],
        ["127.0.0.1"],
        ["169.254.169.254"],
        ["0.0.0.0"],
        ["100.64.0.1"],
        ["224.0.0.1"],
        ["::1"],
        ["64:ff9b::1"],
        ["64:ff9b:1::1"],
        ["::7f00:1"],
        ["2002:7f00:1::1"],
        ["2001:0:4136:e378:8000:63bf:3fff:fdd2"],
        ["::ffff:100.64.0.1"],
        ["fd00::1"],
        ["fe80::1"],
        ["::ffff:10.0.0.1"],
        [PUBLIC_IP, "127.0.0.1"],  # one bad answer among good ones is enough
    ],
)
def test_a_host_that_resolves_to_any_private_address_is_refused(addresses):
    web = Web({})
    with pytest.raises(fetch.Blocked):
        get(URL, web, resolver=lambda h: addresses)
    assert web.requests == []


@pytest.mark.parametrize("resolver", [lambda h: [], lambda h: (_ for _ in ()).throw(socket.gaierror("nope"))])
def test_a_host_that_does_not_resolve_is_a_fetch_error_and_nothing_is_sent(resolver):
    web = Web({})
    with pytest.raises(fetch.FetchError):
        get(URL, web, resolver=resolver)
    assert web.requests == []


def test_the_connection_goes_to_the_checked_address_with_the_real_name_as_host_and_sni():
    web = one(ok())
    get(URL, web, resolver=lambda h: [PUBLIC_IP, "93.184.216.35"])
    (req,) = web.requests
    assert req.url.host == PUBLIC_IP and req.url.scheme == "https"
    assert req.headers["host"] == ESPN_HOST and req.extensions["sni_hostname"] == ESPN_HOST
    assert req.headers["accept-encoding"] == "identity"


def test_a_public_ipv6_answer_is_pinned():
    web = one(ok())
    get(URL, web, resolver=lambda h: ["2606:4700:4700::1111"])
    assert web.requests[0].url.host == "2606:4700:4700::1111"


def test_the_client_ignores_proxy_environment_keeps_certificate_checks_and_never_redirects(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    client = fetch.build_client(None)
    assert client.trust_env is False and client.follow_redirects is False
    assert client._transport._pool._ssl_context.verify_mode == ssl.CERT_REQUIRED
    client.close()


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("location", ["/elsewhere", "https://site.api.espn.com/other", "https://evil.example/x"])
def test_a_redirect_is_a_failure_and_is_never_followed(status, location):
    web = one(httpx.Response(status, headers={"location": location}))
    with pytest.raises(fetch.FetchError):
        get(URL, web)
    assert len(web.requests) == 1


def test_a_failure_message_never_repeats_the_server_or_the_url():
    web = one(httpx.Response(302, headers={"location": "https://evil.example/leak?token=abc"}))
    with pytest.raises(fetch.FetchError) as caught:
        get(URL + "?apiKey=SECRET123", web)
    assert "evil.example" not in str(caught.value) and "SECRET123" not in str(caught.value)


def test_a_body_over_the_cap_is_refused():
    web = one(ok(b"x" * 3_000_000))
    with pytest.raises(fetch.FetchError):
        get(URL, web)


def test_a_body_at_the_cap_is_read():
    body = b'"' + b"x" * (fetch.MAX_BODY_BYTES - 2) + b'"'
    assert get(URL, one(ok(body))).data == "x" * (fetch.MAX_BODY_BYTES - 2)


@pytest.mark.parametrize("encoding", ["gzip", "br", "deflate", "gzip, identity"])
def test_a_reply_that_is_compressed_anyway_is_refused_before_it_is_decoded(encoding):
    web = one(ok(b"x", **{"content-encoding": encoding}))
    with pytest.raises(fetch.FetchError, match="encoding"):
        get(URL, web)


def test_a_slow_response_hits_the_wall_clock_deadline():
    now = [0.0]

    def slow():
        def chunks():
            for _ in range(5):
                now[0] += 10
                yield b" "

        return httpx.Response(200, headers=JSON, content=chunks())

    with pytest.raises(fetch.FetchError, match="deadline"):
        get(URL, one(lambda r: slow()), clock=lambda: now[0])


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("slow"), httpx.ConnectError("down"), httpx.RemoteProtocolError("x")])
def test_network_errors_are_fetch_errors(exc):
    def boom(request):
        raise exc

    with pytest.raises(fetch.FetchError):
        fetch.fetch_json(URL, resolver=public_dns, transport=httpx.MockTransport(boom))


def test_the_limits_are_ten_seconds_twenty_seconds_and_two_megabytes():
    assert fetch.TIMEOUT_S == 10 and fetch.DEADLINE_S == 20 and fetch.MAX_BODY_BYTES == 2_000_000
    client = fetch.build_client(None)
    assert client.timeout == httpx.Timeout(10)
    client.close()


def test_a_hung_dns_lookup_is_cut_off_after_the_resolve_timeout(monkeypatch):
    def hang(host, port, **kw):
        time.sleep(2)
        return []

    monkeypatch.setattr(socket, "getaddrinfo", hang)
    monkeypatch.setattr(fetch, "RESOLVE_TIMEOUT_S", 0.2)
    started = time.perf_counter()
    with pytest.raises(OSError):
        fetch.default_resolver(ESPN_HOST)
    assert time.perf_counter() - started < 1.5


def test_default_resolver_asks_for_port_443_and_returns_each_address_once(monkeypatch):
    asked = []

    def fake(host, port, **kw):
        asked.append((host, port))
        return [(2, 1, 6, "", (a, 443)) for a in ["93.184.216.34", "93.184.216.34", "93.184.216.35"]]

    monkeypatch.setattr(socket, "getaddrinfo", fake)
    assert fetch.default_resolver(ESPN_HOST) == ["93.184.216.34", "93.184.216.35"]
    assert asked == [(ESPN_HOST, 443)]


@pytest.mark.parametrize("ctype", ["text/html", "text/plain", "image/png", ""])
def test_a_reply_that_is_not_json_by_content_type_is_a_fetch_error(ctype):
    web = one(httpx.Response(200, headers={"content-type": ctype}, content=b"{}"))
    with pytest.raises(fetch.FetchError):
        get(URL, web)


@pytest.mark.parametrize("body", [b"", b"not json", b"{", b"\xff\xfe"])
def test_a_body_that_is_not_json_is_a_fetch_error(body):
    with pytest.raises(fetch.FetchError):
        get(URL, one(ok(body)))


@pytest.mark.parametrize("status", [401, 403, 429])
def test_401_403_and_429_are_blocked(status):
    with pytest.raises(fetch.Blocked):
        get(URL, one(httpx.Response(status)))


@pytest.mark.parametrize("status", [400, 404, 500, 502, 503])
def test_other_failures_are_fetch_errors_not_blocks(status):
    with pytest.raises(fetch.FetchError) as caught:
        get(URL, one(httpx.Response(status)))
    assert not isinstance(caught.value, fetch.Blocked)


def test_the_result_carries_status_data_and_only_the_credit_headers():
    web = one(ok(b'{"k": [1, 2]}', **{"x-requests-remaining": "499", "x-requests-last": "1", "set-cookie": "a=b"}))
    result = get(URL, web)
    assert result.status == 200 and result.data == {"k": [1, 2]}
    assert result.headers == {"x-requests-remaining": "499", "x-requests-last": "1"}


def test_the_user_agent_names_the_app_and_nothing_personal():
    web = one(ok())
    get(URL, web)
    assert web.requests[0].headers["user-agent"].startswith("NFLPickemIntel/")


def test_the_http_client_libraries_do_not_log_request_urls_at_info():
    import logging

    for name in ("httpx", "httpcore"):
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING


# ---------------------------------------------------------------- tables and settings (15a)

GAMES_COLUMNS_ON_MAIN = {
    "game_id", "season", "week", "game_type", "kickoff_utc", "time_tbd", "weekday", "away_team", "home_team",
    "away_score", "home_score", "status", "neutral_site", "div_game", "roof", "surface", "stadium", "stadium_id",
    "away_rest", "home_rest", "away_qb", "home_qb", "away_coach", "home_coach", "temp_f", "wind_mph", "source",
    "updated_at",
}  # fmt: skip


def test_the_games_table_is_untouched():
    assert {c.name for c in Game.__table__.columns} == GAMES_COLUMNS_ON_MAIN


def test_the_three_new_tables_have_the_planned_columns(session):
    tables = inspect(get_engine())
    cols = {name: {c["name"] for c in tables.get_columns(name)} for name in tables.get_table_names()}
    assert cols["market_quotes"] == {
        "id", "game_id", "source", "kind", "home_prob", "away_prob", "raw_yes_bid", "raw_yes_ask", "overround",
        "home_ml", "away_ml", "fetched_at", "source_ts",
    }  # fmt: skip
    assert cols["live_states"] == {
        "id", "game_id", "espn_event_id", "fetched_at", "state", "home_score", "away_score", "period", "clock",
        "home_wp", "tie_wp", "last_play_id",
    }  # fmt: skip
    assert cols["source_status"] == {
        "source", "consecutive_failures", "blocked_until", "last_ok_at", "last_error", "credits_left", "updated_at",
    }  # fmt: skip
    assert MarketQuote.__tablename__ == "market_quotes" and LiveState.__tablename__ == "live_states"
    assert SourceStatus.__tablename__ == "source_status"


def test_quotes_and_live_states_belong_to_a_real_game(session):
    fks = {t: {fk["referred_table"] for fk in inspect(get_engine()).get_foreign_keys(t)} for t in
           ("market_quotes", "live_states")}  # fmt: skip
    assert fks == {"market_quotes": {"games"}, "live_states": {"games"}}


def test_the_odds_api_key_is_a_setting_that_defaults_to_empty():
    assert Settings(_env_file=None).odds_api_key == ""
    example = (Path(__file__).parents[2] / ".env.example").read_text().splitlines()
    assert "ODDS_API_KEY=" in example


# ---------------------------------------------------------------- ESPN live state (15d, server side)

NOW = datetime(2026, 10, 13, 6, 30, tzinfo=UTC)


def recorded(name: str):
    return json.loads((FIXTURES / name).read_text())


def seed_game(session, away: str, home: str, kickoff: datetime, **kw) -> Game:
    game = Game(
        game_id=kw.pop("game_id", f"2026_05_{away}_{home}"),
        season=2026,
        week=kw.pop("week", 5),
        game_type="REG",
        kickoff_utc=kickoff,
        weekday="Sunday",
        away_team=away,
        home_team=home,
        status=kw.pop("status", "final"),
        source="nflverse",
        **kw,
    )
    session.add(game)
    session.commit()
    return game


def seed_recorded_games(session) -> dict[str, Game]:
    return {
        "buf_la": seed_game(
            session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), away_score=37, home_score=34
        ),
        "tb_dal": seed_game(
            session, "TB", "DAL", datetime(2026, 10, 9, 0, 15, tzinfo=UTC), away_score=24, home_score=16
        ),
        "nyg_was": seed_game(
            session, "NYG", "WAS", datetime(2026, 10, 11, 17, 0, tzinfo=UTC), away_score=27, home_score=27
        ),
    }


SUMMARIES = {
    "401872994": "espn_summary_buf_lar.json",
    "401872980": "espn_summary_tb_dal.json",
    "401872988": "espn_summary_nyg_wsh.json",
}


def recorded_routes() -> dict:
    routes = {espn.SCOREBOARD_URL: recorded("espn_scoreboard_final.json")}
    routes |= {espn.summary_url(i): recorded(f) for i, f in SUMMARIES.items()}
    return routes


def fake_get(routes: dict):
    """get(url) -> JsonResult from routes[url]; an Exception value is raised; a missing url fails the test."""
    calls: list[str] = []

    def get(url: str) -> fetch.JsonResult:
        calls.append(url)
        reply = routes[url]
        if isinstance(reply, Exception):
            raise reply
        return fetch.JsonResult(200, copy.deepcopy(reply), {})

    get.calls = calls
    return get


def live_rows(session) -> list[LiveState]:
    return list(session.scalars(select(LiveState).order_by(LiveState.id)))


def in_progress(event_id: str = "401872994", *, home="34", away="30", period=4, clock="2:05", wp=0.62):
    """The recorded BUF @ LAR scoreboard and summary, edited to look like a game in progress."""
    board = recorded("espn_scoreboard_final.json")
    event = next(e for e in board["events"] if e["id"] == event_id)
    board["events"] = [event]
    for status in (event["status"], event["competitions"][0]["status"]):
        status.update(period=period, displayClock=clock, clock=0.0)
        status["type"].update(name="STATUS_IN_PROGRESS", state="in", completed=False, description="In Progress")
    for team in event["competitions"][0]["competitors"]:
        team["score"] = home if team["homeAway"] == "home" else away
    summary = recorded(SUMMARIES[event_id])
    summary["winprobability"] = summary["winprobability"][:50]
    summary["winprobability"][-1].update(homeWinPercentage=wp, tiePercentage=0.0, playId="4018729940777")
    return {espn.SCOREBOARD_URL: board, espn.summary_url(event_id): summary}


def test_the_urls_are_exact_espn_hosts_and_the_event_id_is_digits_only():
    assert espn.SCOREBOARD_URL == "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    assert (
        espn.summary_url("401872994")
        == "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=401872994"
    )
    for bad in ("", "12a", "1" * 13, "../x", "1&x=2", "٣٤", "123\n", "123 "):
        with pytest.raises(ValueError):
            espn.summary_url(bad)


def test_three_finished_games_store_their_score_and_last_win_probability_as_espn_shows_them(session):
    games = seed_recorded_games(session)
    result = run.refresh_live_games(session, get=fake_get(recorded_routes()), now=NOW)
    assert (result.source, result.status, result.inserted, result.skipped) == ("espn_live", "ok", 3, 0)
    by_game = {r.game_id: r for r in live_rows(session)}
    buf = by_game[games["buf_la"].game_id]
    assert (buf.state, buf.home_score, buf.away_score, buf.home_wp, buf.tie_wp) == ("post", 34, 37, 0.0, 0.0)
    assert (buf.last_play_id, buf.espn_event_id, buf.fetched_at) == ("4018729944992", "401872994", NOW)
    tb = by_game[games["tb_dal"].game_id]
    assert (tb.state, tb.home_score, tb.away_score, tb.home_wp) == ("post", 16, 24, 0.0)
    assert tb.last_play_id == "4018729804255"
    tie = by_game[games["nyg_was"].game_id]  # NYG @ WSH ended 27-27: ESPN's last win probability is 0.5
    assert (tie.state, tie.home_score, tie.away_score, tie.home_wp) == ("post", 27, 27, 0.5)


def test_a_second_refresh_with_nothing_new_inserts_nothing_and_fetches_only_the_scoreboard(session):
    seed_recorded_games(session)
    run.refresh_live_games(session, get=fake_get(recorded_routes()), now=NOW)
    again = fake_get(recorded_routes())
    result = run.refresh_live_games(session, get=again, now=NOW + timedelta(seconds=30))
    assert result.inserted == 0 and len(live_rows(session)) == 3
    assert again.calls == [espn.SCOREBOARD_URL]  # a game already stored as final needs no summary


def test_a_refresh_never_writes_the_games_table(session):
    games = seed_recorded_games(session)
    before = {g.game_id: (g.status, g.home_score, g.away_score, g.updated_at) for g in games.values()}
    run.refresh_live_games(session, get=fake_get(recorded_routes()), now=NOW)
    session.expire_all()
    after = {g.game_id: (g.status, g.home_score, g.away_score, g.updated_at) for g in session.scalars(select(Game))}
    assert after == before


def test_a_game_in_progress_stores_score_period_clock_and_the_live_win_probability(session):
    game = seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    get = fake_get(in_progress())
    result = run.refresh_live_games(session, get=get, now=NOW)
    (row,) = live_rows(session)
    assert result.inserted == 1 and row.game_id == game.game_id
    assert (row.state, row.home_score, row.away_score, row.period, row.clock) == ("in", 34, 30, 4, "2:05")
    assert (row.home_wp, row.tie_wp, row.last_play_id) == (0.62, 0.0, "4018729940777")
    assert get.calls == [espn.SCOREBOARD_URL, espn.summary_url("401872994")]


def test_a_new_clock_or_score_adds_a_row_and_an_unchanged_poll_adds_none(session):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    run.refresh_live_games(session, get=fake_get(in_progress()), now=NOW)
    run.refresh_live_games(session, get=fake_get(in_progress()), now=NOW + timedelta(seconds=30))
    assert len(live_rows(session)) == 1
    run.refresh_live_games(session, get=fake_get(in_progress(clock="1:58")), now=NOW + timedelta(seconds=60))
    run.refresh_live_games(session, get=fake_get(in_progress(clock="1:58", home="37")), now=NOW + timedelta(seconds=90))
    run.refresh_live_games(
        session, get=fake_get(in_progress(clock="1:58", home="37", wp=0.8)), now=NOW + timedelta(seconds=120)
    )
    assert [(r.clock, r.home_score, r.home_wp) for r in live_rows(session)] == [
        ("2:05", 34, 0.62), ("1:58", 34, 0.62), ("1:58", 37, 0.62), ("1:58", 37, 0.8),
    ]  # fmt: skip


def test_a_game_that_has_not_started_is_stored_as_pre_with_no_summary_fetch(session):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    routes = in_progress()
    for status in (routes[espn.SCOREBOARD_URL]["events"][0]["status"],
                   routes[espn.SCOREBOARD_URL]["events"][0]["competitions"][0]["status"]):  # fmt: skip
        status["type"].update(name="STATUS_SCHEDULED", state="pre", description="Scheduled")
    for team in routes[espn.SCOREBOARD_URL]["events"][0]["competitions"][0]["competitors"]:
        team["score"] = "0"
    get = fake_get(routes)
    run.refresh_live_games(session, get=get, now=NOW)
    (row,) = live_rows(session)
    assert row.state == "pre" and row.home_wp is None
    assert get.calls == [espn.SCOREBOARD_URL]


def test_a_summary_is_fetched_when_the_final_win_probability_is_not_stored_yet(session):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    run.refresh_live_games(session, get=fake_get(in_progress()), now=NOW)  # last stored state: in
    get = fake_get(recorded_routes())
    run.refresh_live_games(session, get=get, now=NOW + timedelta(minutes=1))
    assert espn.summary_url("401872994") in get.calls  # the game just ended: capture the final probability
    assert live_rows(session)[-1].state == "post"


def test_scores_follow_team_codes_not_espns_home_label_and_the_win_probability_flips(session):
    game = seed_game(
        session, "LA", "BUF", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled"
    )  # neutral site
    run.refresh_live_games(session, get=fake_get(in_progress(wp=0.62)), now=NOW)  # ESPN calls LA the home team
    (row,) = live_rows(session)
    assert row.game_id == game.game_id
    assert (row.home_score, row.away_score) == (30, 34)  # BUF is our home team and has 30 in this edit
    assert row.home_wp == pytest.approx(0.38)


def test_an_event_with_no_game_in_our_table_is_skipped_and_counted_not_guessed(session):
    games = seed_recorded_games(session)
    session.delete(games["tb_dal"])
    session.commit()
    result = run.refresh_live_games(session, get=fake_get(recorded_routes()), now=NOW)
    assert (result.inserted, result.skipped) == (2, 1)


def test_the_same_teams_on_another_day_do_not_match(session):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 20, 0, 15, tzinfo=UTC), status="scheduled")
    assert run.refresh_live_games(session, get=fake_get(in_progress()), now=NOW).skipped == 1
    assert live_rows(session) == []


def test_espn_codes_map_to_ours_and_every_nfl_club_is_known():
    assert espn.TEAM_CODES["WSH"] == "WAS" and espn.TEAM_CODES["LAR"] == "LA"
    assert len(set(espn.TEAM_CODES.values())) == 32


@pytest.mark.parametrize(
    ("field", "value"),
    [("score", "9999"), ("score", "-3"), ("score", "x"), ("score", None), ("score", True)],
)
def test_a_bad_score_becomes_null_never_a_guess(session, field, value):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    routes = in_progress()
    for team in routes[espn.SCOREBOARD_URL]["events"][0]["competitions"][0]["competitors"]:
        team[field] = value
    run.refresh_live_games(session, get=fake_get(routes), now=NOW)
    (row,) = live_rows(session)
    assert row.home_score is None and row.away_score is None and row.state == "in"


@pytest.mark.parametrize("clock", ["banana", "99:99:99", "", "1:2", "12:345", "<b>1:00</b>", None, 7])
def test_a_bad_clock_becomes_null(session, clock):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    run.refresh_live_games(session, get=fake_get(in_progress(clock=clock)), now=NOW)
    assert live_rows(session)[0].clock is None


@pytest.mark.parametrize("period", [0, 11, -1, "4", 4.5, None, True])
def test_a_bad_period_becomes_null(session, period):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    run.refresh_live_games(session, get=fake_get(in_progress(period=period)), now=NOW)
    assert live_rows(session)[0].period is None


@pytest.mark.parametrize("wp", [1.7, -0.1, float("nan"), float("inf"), "0.5", None, True])
def test_a_bad_win_probability_becomes_null_and_the_row_is_still_stored(session, wp):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    run.refresh_live_games(session, get=fake_get(in_progress(wp=wp)), now=NOW)
    (row,) = live_rows(session)
    assert row.home_wp is None and row.state == "in" and row.home_score == 34


@pytest.mark.parametrize("state", ["weird", "", None, 3, "IN"])
def test_an_unknown_state_skips_the_event(session, state):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    routes = in_progress()
    routes[espn.SCOREBOARD_URL]["events"][0]["status"]["type"]["state"] = state
    routes[espn.SCOREBOARD_URL]["events"][0]["competitions"][0]["status"]["type"]["state"] = state
    result = run.refresh_live_games(session, get=fake_get(routes), now=NOW)
    assert result.skipped == 1 and live_rows(session) == []


@pytest.mark.parametrize(
    "event_id", ["../../etc/passwd", "1&event=2", "12a", "", None, 401872994, "٣٤٥", "401872994\n"]
)
def test_an_event_id_that_is_not_digits_is_never_put_in_a_url(session, event_id):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    routes = in_progress()
    routes[espn.SCOREBOARD_URL]["events"][0]["id"] = event_id
    get = fake_get(routes)
    result = run.refresh_live_games(session, get=get, now=NOW)
    assert result.skipped == 1 and get.calls == [espn.SCOREBOARD_URL]


def test_a_link_inside_a_reply_is_never_fetched(session):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    routes = in_progress()
    event = routes[espn.SCOREBOARD_URL]["events"][0]
    event["links"] = [{"$ref": "http://169.254.169.254/latest/meta-data"}]
    event["competitions"][0]["$ref"] = "https://evil.example/x"
    get = fake_get(routes)
    run.refresh_live_games(session, get=get, now=NOW)
    assert get.calls == [espn.SCOREBOARD_URL, espn.summary_url("401872994")]


def test_a_malformed_scoreboard_fails_the_run_and_keeps_every_old_row(session):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    run.refresh_live_games(session, get=fake_get(in_progress()), now=NOW)
    for bad in ([], {"events": "nope"}, {"events": [None, 3, "x"]} | {"filler": "x"}, {"events": [{}] * 41}):
        result = run.refresh_live_games(session, get=fake_get({espn.SCOREBOARD_URL: bad}), now=NOW + timedelta(days=9))
        session.query(SourceStatus).update({"blocked_until": None})  # let the next bad shape through
        session.commit()
        assert result.status == "failed"
    assert len(live_rows(session)) == 1


def test_at_most_sixteen_summaries_are_fetched_in_one_refresh(session):
    board = recorded("espn_scoreboard_final.json")
    template = board["events"][0]
    events = []
    for i in range(30):
        e = copy.deepcopy(template)
        e["id"] = str(401880000 + i)
        for status in (e["status"], e["competitions"][0]["status"]):
            status["type"].update(state="in", completed=False)
        events.append(e)
    board["events"] = events[:40]
    get = fake_get(
        {espn.SCOREBOARD_URL: board} | {espn.summary_url(e["id"]): recorded(SUMMARIES["401872994"]) for e in events}
    )
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    run.refresh_live_games(session, get=get, now=NOW)
    assert len([c for c in get.calls if "summary" in c]) <= 16


def test_one_summary_that_fails_leaves_that_game_without_a_probability_and_the_run_ok(session):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    routes = in_progress()
    routes[espn.summary_url("401872994")] = fetch.FetchError("status 500")
    result = run.refresh_live_games(session, get=fake_get(routes), now=NOW)
    (row,) = live_rows(session)
    assert result.status == "ok" and row.home_wp is None and row.home_score == 34


def test_a_blocked_summary_stops_the_source_but_keeps_what_the_scoreboard_gave(session):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    routes = in_progress()
    routes[espn.summary_url("401872994")] = fetch.Blocked("status 429")
    result = run.refresh_live_games(session, get=fake_get(routes), now=NOW)
    status = session.get(SourceStatus, "espn_live")
    assert result.status == "failed" and len(live_rows(session)) == 1 and live_rows(session)[0].home_wp is None
    assert status.consecutive_failures == 1 and status.blocked_until == NOW + timedelta(minutes=15)


# ---------------------------------------------------------------- failure behaviour (15g)


def test_every_refresh_logs_one_ingestion_run_and_a_status_row(session):
    seed_recorded_games(session)
    run.refresh_live_games(session, get=fake_get(recorded_routes()), now=NOW)
    (log,) = session.scalars(select(IngestionRun)).all()
    assert (log.source, log.dataset, log.status, log.rows, log.error) == ("espn", "live_scores", "ok", 3, None)
    status = session.get(SourceStatus, "espn_live")
    assert (status.consecutive_failures, status.blocked_until, status.last_error) == (
        0,
        NOW + timedelta(seconds=30),
        None,
    )
    assert status.last_ok_at == NOW


@pytest.mark.parametrize("exc", [fetch.FetchError("status 500"), fetch.Blocked("status 403")])
def test_a_failed_scoreboard_keeps_old_rows_logs_the_run_and_backs_off_fifteen_minutes(session, exc):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    run.refresh_live_games(session, get=fake_get(in_progress()), now=NOW)
    result = run.refresh_live_games(session, get=fake_get({espn.SCOREBOARD_URL: exc}), now=NOW + timedelta(hours=1))
    assert result.status == "failed" and len(live_rows(session)) == 1
    log = session.scalars(select(IngestionRun).order_by(IngestionRun.id.desc())).first()
    assert log.status == "failed" and log.error == f"{type(exc).__name__}: {exc}"
    status = session.get(SourceStatus, "espn_live")
    assert status.consecutive_failures == 1 and status.blocked_until == NOW + timedelta(hours=1, minutes=15)
    assert status.last_error == f"{type(exc).__name__}: {exc}"


def test_inside_the_backoff_window_nothing_is_fetched_and_nothing_is_logged(session):
    boom = fake_get({espn.SCOREBOARD_URL: fetch.FetchError("status 500")})
    run.refresh_live_games(session, get=boom, now=NOW)
    quiet = fake_get({})
    result = run.refresh_live_games(session, get=quiet, now=NOW + timedelta(minutes=14, seconds=59))
    assert result.status == "skipped" and quiet.calls == []
    assert len(session.scalars(select(IngestionRun)).all()) == 1


def test_backoff_doubles_with_each_straight_failure_to_a_day_and_one_success_resets_it(session):
    seed_recorded_games(session)
    when, waits = NOW, []
    for _ in range(9):
        run.refresh_live_games(session, get=fake_get({espn.SCOREBOARD_URL: fetch.FetchError("x")}), now=when)
        status = session.get(SourceStatus, "espn_live")
        waits.append(status.blocked_until - when)
        when = status.blocked_until
    assert waits[:3] == [timedelta(minutes=15), timedelta(minutes=30), timedelta(hours=1)]
    assert waits[-1] == timedelta(hours=24) and max(waits) == timedelta(hours=24)
    run.refresh_live_games(session, get=fake_get(recorded_routes()), now=when)
    status = session.get(SourceStatus, "espn_live")
    assert (status.consecutive_failures, status.blocked_until, status.last_ok_at) == (
        0, when + timedelta(seconds=30), when
    )  # fmt: skip


def test_one_refresh_makes_one_attempt_and_never_retries(session):
    get = fake_get({espn.SCOREBOARD_URL: fetch.FetchError("status 500")})
    run.refresh_live_games(session, get=get, now=NOW)
    assert get.calls == [espn.SCOREBOARD_URL]


def test_a_failure_message_is_the_error_class_and_text_we_raised_and_never_a_url(session):
    get = fake_get({espn.SCOREBOARD_URL: RuntimeError(f"boom {espn.SCOREBOARD_URL}?apiKey=SECRET")})
    run.refresh_live_games(session, get=get, now=NOW)
    log = session.scalars(select(IngestionRun)).one()
    status = session.get(SourceStatus, "espn_live")
    assert "http" not in (log.error or "") and "SECRET" not in (log.error or "")
    assert "http" not in (status.last_error or "") and "SECRET" not in (status.last_error or "")


# ---------------------------------------------------------------- the query the API will call (15d)


def test_live_states_for_returns_the_newest_row_per_requested_game_only(session):
    games = seed_recorded_games(session)
    seed_game(session, "SEA", "DEN", datetime(2026, 10, 16, 0, 15, tzinfo=UTC), status="scheduled")
    run.refresh_live_games(session, get=fake_get(recorded_routes()), now=NOW)
    ids = [g.game_id for g in games.values()]
    session.add_all([  # a later row for one game wins; newest is by id, which is insert order
        LiveState(game_id=ids[0], espn_event_id="401872994", fetched_at=NOW + timedelta(minutes=5), state="post",
                  home_score=34, away_score=37, home_wp=0.0, tie_wp=0.0, period=5, clock="0:00"),
    ])  # fmt: skip
    session.commit()
    states = store.live_states_for(session, [ids[0], ids[1], "2026_05_SEA_DEN", "no_such_game"])
    assert set(states) == {ids[0], ids[1]}
    assert states[ids[0]].period == 5 and states[ids[1]].home_score == 16
    assert store.live_states_for(session, []) == {}


# ---------------------------------------------------------------- hardening from the design security review


def test_a_source_is_not_called_again_before_its_minimum_interval_after_a_success(session):
    seed_recorded_games(session)
    run.refresh_live_games(session, get=fake_get(recorded_routes()), now=NOW)
    quiet = fake_get({})
    early = run.refresh_live_games(session, get=quiet, now=NOW + timedelta(seconds=29))
    assert early.status == "skipped" and quiet.calls == []
    assert (
        run.refresh_live_games(session, get=fake_get(recorded_routes()), now=NOW + timedelta(seconds=30)).status == "ok"
    )
    assert (run.ESPN_MIN_INTERVAL, run.KALSHI_MIN_INTERVAL, run.ODDS_MIN_INTERVAL) == (
        timedelta(seconds=30), timedelta(seconds=60), timedelta(hours=6),
    )  # fmt: skip


def test_a_bad_json_body_of_any_shape_is_a_fetch_error_never_a_crash():
    deep = b"[" * 200_000 + b"]" * 200_000  # RecursionError in the json module
    long_int = b'{"a": ' + b"1" * 6000 + b"}"  # ValueError: int digit limit
    for body in (deep, long_int):
        with pytest.raises(fetch.FetchError):
            get(URL, one(ok(body)))


def test_an_ipv4_answer_is_preferred_when_both_families_come_back():
    web = one(ok())
    get(URL, web, resolver=lambda h: ["2606:4700:4700::1111", PUBLIC_IP])
    assert web.requests[0].url.host == PUBLIC_IP


def test_a_hung_lookup_leaves_only_a_daemon_thread_behind(monkeypatch):
    import threading

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: time.sleep(0.8) or [])
    monkeypatch.setattr(fetch, "RESOLVE_TIMEOUT_S", 0.1)
    with pytest.raises(OSError):
        fetch.default_resolver(ESPN_HOST)
    lingering = [t for t in threading.enumerate() if t.name == "nflpi-resolve"]
    assert lingering and all(t.daemon for t in lingering)


def test_a_book_name_play_id_and_source_time_from_a_reply_must_pass_their_own_pattern(session):
    seed_game(session, "BUF", "LA", datetime(2026, 10, 13, 0, 15, tzinfo=UTC), status="scheduled")
    routes = in_progress()
    summary = routes[espn.summary_url("401872994")]
    summary["winprobability"][-1]["playId"] = "12\n<script>"
    run.refresh_live_games(session, get=fake_get(routes), now=NOW)
    (row,) = live_rows(session)
    assert row.last_play_id is None and row.home_wp == 0.62


def test_an_unmatched_event_is_logged_only_in_a_safe_form(session, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    routes = in_progress()
    routes[espn.SCOREBOARD_URL]["events"][0]["id"] = "9" * 12  # no game for it
    routes[espn.SCOREBOARD_URL]["events"].append(
        copy.deepcopy(routes[espn.SCOREBOARD_URL]["events"][0]) | {"id": "123\n\x1b[31mINJECT"}
    )
    run.refresh_live_games(session, get=fake_get(routes), now=NOW)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "\x1b" not in text and "INJECT" not in text and len(text) < 2000


def test_the_configured_odds_key_is_in_no_fixture_and_no_doc(monkeypatch):
    key = Settings().odds_api_key or ""
    root = Path(__file__).parents[2]
    files = [*FIXTURES.glob("*"), *root.glob("docs/**/*.md")]
    assert key == "" or not any(key in f.read_text(errors="ignore") for f in files)


# ---------------------------------------------------------------- Kalshi market quotes (15b)

KNOW = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)
FOUR_GAMES = [  # away, home, kickoff: the four games both the recorded Kalshi and Odds API replies contain
    ("SEA", "DEN", datetime(2026, 10, 16, 0, 15, tzinfo=UTC)),
    ("HOU", "JAX", datetime(2026, 10, 18, 13, 30, tzinfo=UTC)),
    ("ARI", "LA", datetime(2026, 10, 18, 20, 5, tzinfo=UTC)),
    ("BUF", "LV", datetime(2026, 10, 18, 20, 25, tzinfo=UTC)),
]


def seed_four(session) -> dict[str, Game]:
    return {f"{a}_{h}": seed_game(session, a, h, k, status="scheduled") for a, h, k in FOUR_GAMES}


def quote_rows(session, source: str | None = None) -> list[MarketQuote]:
    stmt = select(MarketQuote).order_by(MarketQuote.id)
    if source:
        stmt = stmt.where(MarketQuote.source == source)
    return list(session.scalars(stmt))


def kalshi_routes(data=None) -> dict:
    return {kalshi.markets_url(): data if data is not None else recorded("kalshi_markets.json")}


def test_the_kalshi_url_is_the_exact_open_nfl_game_series_and_a_cursor_is_encoded():
    assert kalshi.markets_url() == (
        "https://external-api.kalshi.com/trade-api/v2/markets?series_ticker=KXNFLGAME&status=open&limit=200"
    )
    assert kalshi.markets_url("abc_DEF-12=").endswith("&cursor=abc_DEF-12%3D")
    for bad in ("", "a b", "a&b=1", "x" * 201, "ab\n", "٣"):
        with pytest.raises(ValueError):
            kalshi.markets_url(bad)


def test_kalshi_codes_map_to_ours_and_all_32_clubs_are_known():
    assert kalshi.TEAM_CODES["JAC"] == "JAX" and kalshi.TEAM_CODES["LAR"] == "LA"
    assert len(kalshi.TEAM_CODES) == 32 and len(set(kalshi.TEAM_CODES.values())) == 32


def test_the_recorded_kalshi_markets_become_one_normalised_quote_per_game(session):
    games = seed_four(session)
    get = fake_get(kalshi_routes())
    result = run.refresh_kalshi_quotes(session, get=get, now=KNOW)
    assert (result.source, result.status, result.inserted, result.skipped) == ("kalshi", "ok", 4, 0)
    assert get.calls == [kalshi.markets_url()]
    rows = {r.game_id: r for r in quote_rows(session)}
    den = rows[games["SEA_DEN"].game_id]  # SEA 0.59/0.60 and DEN 0.40/0.41: mids 0.595 and 0.405 sum to 1
    assert (den.source, den.kind, den.fetched_at) == ("kalshi", "pregame", KNOW)
    assert den.home_prob == pytest.approx(0.405) and den.away_prob == pytest.approx(0.595)
    assert (den.raw_yes_bid, den.raw_yes_ask) == (0.40, 0.41) and den.overround == pytest.approx(0.0)
    assert den.home_ml is None and den.away_ml is None
    lv = rows[games["BUF_LV"].game_id]  # LV 0.31/0.32 and BUF 0.69/0.70: mids 0.315 + 0.695 = 1.01
    assert lv.home_prob == pytest.approx(0.315 / 1.01) and lv.away_prob == pytest.approx(0.695 / 1.01)
    assert lv.overround == pytest.approx(0.01) and (lv.raw_yes_bid, lv.raw_yes_ask) == (0.31, 0.32)
    assert lv.home_prob + lv.away_prob == pytest.approx(1.0)


def test_kalshi_team_codes_that_differ_from_ours_still_match(session):
    games = seed_four(session)  # Kalshi says LAR and JAC, we say LA and JAX
    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=KNOW)
    by_game = {r.game_id: r for r in quote_rows(session)}
    assert by_game[games["ARI_LA"].game_id].home_prob == pytest.approx(0.845)
    assert by_game[games["HOU_JAX"].game_id].home_prob == pytest.approx(0.57)


def test_kalshi_is_pregame_before_kickoff_and_live_after_and_an_old_source_time_becomes_null(session):
    games = seed_four(session)
    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=datetime(2026, 10, 16, 1, 0, tzinfo=UTC))
    rows = {r.game_id: r for r in quote_rows(session)}
    assert rows[games["SEA_DEN"].game_id].kind == "live" and rows[games["BUF_LV"].game_id].kind == "pregame"
    assert rows[games["SEA_DEN"].game_id].source_ts is None  # the recorded time is over seven days old by then


def test_a_kalshi_quote_has_a_source_time_inside_the_window(session):
    seed_four(session)
    now = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)  # the recorded markets were last updated on 2026-10-06
    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=now)
    times = [r.source_ts for r in quote_rows(session)]
    assert all(t is not None and now - timedelta(days=7) <= t <= now + timedelta(days=1) for t in times)
    assert {t.isoformat() for t in times} <= {"2026-10-06T04:05:00.760741+00:00", "2026-10-06T04:06:00.764221+00:00"}


def test_an_unchanged_kalshi_quote_adds_no_row_and_a_changed_price_adds_one(session):
    seed_four(session)
    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=KNOW)
    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=KNOW + timedelta(minutes=2))
    assert len(quote_rows(session)) == 4
    moved = recorded("kalshi_markets.json")
    next(m for m in moved["markets"] if m["ticker"].endswith("SEADEN-DEN"))["yes_ask_dollars"] = "0.4300"
    result = run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes(moved)), now=KNOW + timedelta(minutes=4))
    assert result.inserted == 1 and len(quote_rows(session)) == 5
    assert quote_rows(session)[-1].raw_yes_ask == 0.43


def test_a_kalshi_event_with_no_game_is_skipped_and_counted_not_guessed(session):
    games = seed_four(session)
    session.delete(games["BUF_LV"])
    session.commit()
    result = run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=KNOW)
    assert (result.inserted, result.skipped) == (3, 1)


def _edit(fn):
    data = recorded("kalshi_markets.json")
    fn(data["markets"])
    return data


@pytest.mark.parametrize(
    "edit",
    [
        lambda ms: ms.remove(next(m for m in ms if m["ticker"].endswith("SEADEN-SEA"))),  # only one team priced
        lambda ms: ms.append(copy.deepcopy(next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")))),  # twice
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(status="closed"),
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(yes_bid_dollars="0.9000"),  # >ask
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(yes_ask_dollars="1.2000"),
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(yes_ask_dollars="nan"),
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(yes_ask_dollars=None),
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(yes_bid_dollars=0.59),
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(yes_ask_dollars="0.6000\n"),
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(yes_ask_dollars="٠.٦"),
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(
            event_ticker="KXNFLGAME-26OCT15SEA"
        ),
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(
            ticker="KXNFLGAME-26OCT15SEADEN-XXX"
        ),
        lambda ms: next(m for m in ms if m["ticker"].endswith("SEADEN-SEA")).update(ticker=None),
    ],
)
def test_a_kalshi_event_that_cannot_be_priced_cleanly_is_skipped_and_the_rest_are_stored(session, edit):
    games = seed_four(session)
    result = run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes(_edit(edit))), now=KNOW)
    stored = {r.game_id for r in quote_rows(session)}
    assert games["SEA_DEN"].game_id not in stored and len(stored) == 3 and result.skipped >= 1


def test_kalshi_pages_are_followed_with_the_cursor_up_to_three_pages(session):
    seed_four(session)
    full = recorded("kalshi_markets.json")
    a, b, c, d = (full["markets"][i : i + 2] for i in (0, 2, 4, 6))
    routes = {
        kalshi.markets_url(): {"cursor": "p2", "markets": a},
        kalshi.markets_url("p2"): {"cursor": "p3", "markets": b},
        kalshi.markets_url("p3"): {"cursor": "p4", "markets": c},
        kalshi.markets_url("p4"): {"cursor": "", "markets": d},
    }
    get = fake_get(routes)
    run.refresh_kalshi_quotes(session, get=get, now=KNOW)
    assert get.calls == [kalshi.markets_url(), kalshi.markets_url("p2"), kalshi.markets_url("p3")]  # page 4 never asked
    assert len(quote_rows(session)) == 3  # the BUF/LV pair is on the page we did not read


@pytest.mark.parametrize("cursor", ["p1", "a b", "x" * 201, "p&q=1", "", None, 5])
def test_a_repeated_empty_or_bad_cursor_ends_the_paging(session, cursor):
    seed_four(session)
    full = recorded("kalshi_markets.json")
    routes = {kalshi.markets_url(): {"cursor": cursor, "markets": full["markets"]}}
    get = fake_get(routes | {kalshi.markets_url("p1"): {"cursor": "p1", "markets": []}})
    run.refresh_kalshi_quotes(session, get=get, now=KNOW)
    assert len(get.calls) <= 2 and len(quote_rows(session)) == 4


@pytest.mark.parametrize(
    "bad", [[], "x", {"markets": "no"}, {"markets": [None, 1]} | {"x": 1}, {"markets": [{}] * 501}]
)
def test_a_malformed_kalshi_reply_fails_the_run_and_keeps_old_rows(session, bad):
    seed_four(session)
    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=KNOW)
    result = run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes(bad)), now=KNOW + timedelta(minutes=5))
    assert result.status == "failed" and len(quote_rows(session)) == 4


def test_kalshi_logs_a_run_keeps_its_own_status_and_waits_a_minute(session):
    seed_four(session)
    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=KNOW)
    (log,) = session.scalars(select(IngestionRun)).all()
    assert (log.source, log.dataset, log.status, log.rows) == ("kalshi", "market_quotes", "ok", 4)
    assert session.get(SourceStatus, "kalshi").blocked_until == KNOW + timedelta(seconds=60)
    quiet = fake_get({})
    assert run.refresh_kalshi_quotes(session, get=quiet, now=KNOW + timedelta(seconds=59)).status == "skipped"
    assert quiet.calls == []


def test_a_kalshi_block_stops_that_source_only_and_never_retries(session):
    seed_four(session)
    get = fake_get({kalshi.markets_url(): fetch.Blocked("status 429")})
    result = run.refresh_kalshi_quotes(session, get=get, now=KNOW)
    assert result.status == "failed" and get.calls == [kalshi.markets_url()] and quote_rows(session) == []
    status = session.get(SourceStatus, "kalshi")
    assert (status.consecutive_failures, status.blocked_until) == (1, KNOW + timedelta(minutes=15))
    assert session.get(SourceStatus, "espn_live") is None  # the other sources carry on


def test_the_sources_back_off_independently(session):
    seed_recorded_games(session)
    run.refresh_kalshi_quotes(session, get=fake_get({kalshi.markets_url(): fetch.FetchError("status 500")}), now=KNOW)
    assert run.refresh_live_games(session, get=fake_get(recorded_routes()), now=KNOW).status == "ok"


# ---------------------------------------------------------------- The Odds API quotes (15c)

KEY = "Zk9QmW3xTt7LpR2vYc8N"  # a made-up key: letters and digits, long enough to pass the format check
ODDS_HOST = "api.the-odds-api.com"
ODDS_PATH = "/v4/sports/americanfootball_nfl/odds"
ODDS_NOW = datetime(2026, 10, 13, 7, 0, tzinfo=UTC)


def odds_routes(data=None, headers: dict | None = None) -> dict:
    return {
        oddsapi.odds_url(KEY): (data if data is not None else recorded("odds_api_h2h.json")),
        "_headers": headers if headers is not None else recorded("odds_api_headers.json"),
    }


def odds_get(routes: dict):
    calls: list[str] = []

    def get(url: str) -> fetch.JsonResult:
        calls.append(url)
        reply = routes[url]
        if isinstance(reply, Exception):
            raise reply
        return fetch.JsonResult(200, copy.deepcopy(reply), dict(routes.get("_headers", {})))

    get.calls = calls
    return get


def refresh_odds(session, routes=None, *, now=ODDS_NOW, key=KEY):
    get = odds_get(routes or odds_routes())
    return run.refresh_odds_quotes(session, get=get, now=now, api_key=key), get


def test_the_odds_url_asks_for_us_h2h_american_odds_in_one_call_and_encodes_the_key():
    url = oddsapi.odds_url(KEY)
    assert url.startswith("https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds?")
    from urllib.parse import parse_qs, urlsplit

    assert parse_qs(urlsplit(url).query) == {
        "regions": ["us"], "markets": ["h2h"], "oddsFormat": ["american"], "apiKey": [KEY],
    }  # fmt: skip


@pytest.mark.parametrize(
    "key",
    [
        "",
        None,
        "short",
        "has space abcdefghijkl",
        "abcdefghijklmnop&x=1",
        "abc\ndefghijklmnop",
        "a" * 65,
        "key-with-dash-1234567",
    ],
)
def test_with_no_usable_key_the_odds_adapter_does_nothing_and_says_so(session, key):
    get = odds_get({})
    result = run.refresh_odds_quotes(session, get=get, now=ODDS_NOW, api_key=key)
    assert (result.source, result.status, result.detail) == ("oddsapi", "skipped", "ODDS_API_KEY is not set")
    assert get.calls == [] and session.scalars(select(IngestionRun)).all() == [] and quote_rows(session) == []
    with pytest.raises(ValueError):
        oddsapi.odds_url(key or "")


def test_the_key_comes_from_the_setting_when_none_is_passed(session, monkeypatch):
    from nflpi.config import get_settings

    monkeypatch.setenv("ODDS_API_KEY", KEY)
    get_settings.cache_clear()
    try:
        get = odds_get(odds_routes())
        assert run.refresh_odds_quotes(session, get=get, now=ODDS_NOW).status == "ok"
        assert get.calls == [oddsapi.odds_url(KEY)]
    finally:
        monkeypatch.delenv("ODDS_API_KEY")
        get_settings.cache_clear()


def test_every_team_name_is_known_once():
    assert len(oddsapi.TEAM_NAMES) == 32 and len(set(oddsapi.TEAM_NAMES.values())) == 32
    assert oddsapi.TEAM_NAMES["Los Angeles Rams"] == "LA" and oddsapi.TEAM_NAMES["Washington Commanders"] == "WAS"


def test_one_call_stores_one_quote_per_book_per_matched_game(session):
    games = seed_four(session)
    result, get = refresh_odds(session)
    assert get.calls == [oddsapi.odds_url(KEY)]  # one call
    assert (result.source, result.status, result.inserted) == ("oddsapi", "ok", 9 + 9 + 4 + 4)
    assert result.skipped == 10  # ten events in the reply have no game in our table
    den = [r for r in quote_rows(session) if r.game_id == games["SEA_DEN"].game_id]
    assert len(den) == 9 and {r.source for r in den} >= {"oddsapi:draftkings", "oddsapi:fanduel", "oddsapi:bovada"}
    dk = next(r for r in den if r.source == "oddsapi:draftkings")
    assert (dk.home_ml, dk.away_ml, dk.kind) == (130, -155, "pregame")  # outcomes are matched by name, not position
    assert dk.home_prob == pytest.approx(novig_home_prob(130, -155))
    assert dk.away_prob == pytest.approx(1 - novig_home_prob(130, -155))
    assert dk.overround == pytest.approx(implied_prob(130) + implied_prob(-155) - 1)
    assert dk.source_ts == datetime(2026, 10, 13, 6, 20, 27, tzinfo=UTC) and dk.fetched_at == ODDS_NOW
    assert dk.raw_yes_bid is None and dk.raw_yes_ask is None


def test_an_unchanged_book_line_adds_no_row_and_a_moved_line_adds_one(session):
    seed_four(session)
    refresh_odds(session)
    later = ODDS_NOW + timedelta(hours=6)
    again, _ = refresh_odds(session, now=later)
    assert again.inserted == 0 and len(quote_rows(session)) == 26
    moved = recorded("odds_api_h2h.json")
    moved[0]["bookmakers"][0]["markets"][0]["outcomes"][0]["price"] = 125
    result, _ = refresh_odds(session, odds_routes(moved), now=later + timedelta(hours=6))
    assert result.inserted == 1 and len(quote_rows(session)) == 27


def test_a_moneyline_that_is_not_a_real_american_price_skips_that_book_only(session):
    seed_four(session)
    bad = recorded("odds_api_h2h.json")
    outcomes = [b["markets"][0]["outcomes"] for b in bad[0]["bookmakers"][:5]]
    outcomes[0][0]["price"] = 50  # |x| < 100
    outcomes[1][0]["price"] = float("nan")
    outcomes[2][0]["price"] = True
    outcomes[3][0]["price"] = "130"
    outcomes[4][0]["price"] = None
    result, _ = refresh_odds(session, odds_routes(bad))
    assert result.inserted == 26 - 5


@pytest.mark.parametrize(
    "book_key", ["DraftKings", "draft kings", "a" * 33, "", None, 7, "x\n", "bet<b>", "../x", "dk-1"]
)
def test_a_book_name_must_be_a_short_lowercase_word_or_the_book_is_skipped(session, book_key):
    seed_four(session)
    bad = recorded("odds_api_h2h.json")
    bad[0]["bookmakers"][0]["key"] = book_key
    result, _ = refresh_odds(session, odds_routes(bad))
    assert result.inserted == 25 and all(r.source.startswith("oddsapi:") for r in quote_rows(session))
    assert all(len(r.source) <= 32 for r in quote_rows(session))


@pytest.mark.parametrize(
    "edit",
    [
        lambda e: e.update(home_team="Denver Broncos II"),
        lambda e: e.update(away_team="Denver Broncos"),  # both outcomes the same club
        lambda e: e.update(commence_time="2026-10-30T00:15:00Z"),  # same teams, another day
        lambda e: e.update(commence_time="not a time"),
        lambda e: e.update(commence_time=None),
        lambda e: e.update(home_team=None),
    ],
)
def test_an_odds_event_that_does_not_match_one_game_is_skipped_never_guessed(session, edit):
    seed_four(session)
    bad = recorded("odds_api_h2h.json")
    edit(bad[0])
    result, _ = refresh_odds(session, odds_routes(bad))
    assert result.inserted == 26 - 9 and result.skipped == 11


def test_outcomes_that_are_not_exactly_the_two_clubs_skip_that_book(session):
    seed_four(session)
    bad = recorded("odds_api_h2h.json")
    bad[0]["bookmakers"][0]["markets"][0]["outcomes"].append({"name": "Draw", "price": 300})
    bad[0]["bookmakers"][1]["markets"][0]["outcomes"][0]["name"] = "Seattle Seahawks"  # same club twice
    result, _ = refresh_odds(session, odds_routes(bad))
    assert result.inserted == 24


def test_credits_left_is_saved_and_the_next_call_waits_six_hours(session):
    seed_four(session)
    refresh_odds(session)
    status = session.get(SourceStatus, "oddsapi")
    assert status.credits_left == 499 and status.blocked_until == ODDS_NOW + timedelta(hours=6)
    assert status.consecutive_failures == 0 and status.last_ok_at == ODDS_NOW
    quiet = odds_get({})
    early = run.refresh_odds_quotes(session, get=quiet, now=ODDS_NOW + timedelta(hours=5, minutes=59), api_key=KEY)
    assert early.status == "skipped" and quiet.calls == []


@pytest.mark.parametrize("header", ["abc", "-5", "1000001", "٣٥٠", "12.5", "", " 300", "300\n", "1" * 8])
def test_a_credit_header_that_is_not_a_plain_small_number_is_unknown_and_the_floor_still_holds(session, header):
    seed_four(session)
    refresh_odds(session, odds_routes(headers={"x-requests-remaining": header}))
    status = session.get(SourceStatus, "oddsapi")
    assert status.credits_left is None and status.blocked_until == ODDS_NOW + timedelta(hours=6)


def test_a_missing_credit_header_is_unknown_too(session):
    seed_four(session)
    refresh_odds(session, odds_routes(headers={}))
    assert session.get(SourceStatus, "oddsapi").credits_left is None


def test_fewer_than_fifty_credits_left_stops_the_source_for_thirty_five_days_after_this_call(session):
    seed_four(session)
    result, _ = refresh_odds(session, odds_routes(headers={"x-requests-remaining": "49"}))
    status = session.get(SourceStatus, "oddsapi")
    assert result.status == "ok" and len(quote_rows(session)) == 26  # this reply was paid for: keep it
    assert status.credits_left == 49 and status.blocked_until == ODDS_NOW + timedelta(days=35)
    quiet = odds_get({})
    stopped = run.refresh_odds_quotes(session, get=quiet, now=ODDS_NOW + timedelta(days=30), api_key=KEY)
    assert stopped.status == "skipped" and quiet.calls == []


@pytest.mark.parametrize(("left", "calls"), [(49, 0), (50, 1), (None, 1), (500, 1)])
def test_the_stored_credit_count_is_checked_before_every_call(session, left, calls):
    seed_four(session)
    session.add(SourceStatus(source="oddsapi", consecutive_failures=0, credits_left=left, updated_at=ODDS_NOW))
    session.commit()
    result, get = refresh_odds(session)
    assert len(get.calls) == calls and (result.status == "skipped") == (calls == 0)
    if calls == 0:
        assert "credit" in result.detail and session.scalars(select(IngestionRun)).all() == []


def test_an_odds_block_stops_the_source_and_makes_exactly_one_call(session):
    seed_four(session)
    result, get = refresh_odds(session, {oddsapi.odds_url(KEY): fetch.Blocked("status 429")})
    status = session.get(SourceStatus, "oddsapi")
    assert result.status == "failed" and len(get.calls) == 1
    assert status.consecutive_failures == 1 and status.blocked_until >= ODDS_NOW + timedelta(minutes=15)


def test_a_malformed_odds_reply_fails_the_run_and_keeps_old_rows(session):
    seed_four(session)
    refresh_odds(session)
    for bad in ({}, "x", [None, 3], [{}] * 101, [{"bookmakers": "no"}]):
        session.query(SourceStatus).update({"blocked_until": None})
        session.commit()
        result, _ = refresh_odds(session, odds_routes(bad), now=ODDS_NOW + timedelta(days=1))
        assert result.status == "failed" or bad == [{"bookmakers": "no"}]
    assert len(quote_rows(session)) == 26


def test_the_odds_run_is_logged_with_its_own_dataset(session):
    seed_four(session)
    refresh_odds(session)
    (log,) = session.scalars(select(IngestionRun)).all()
    assert (log.source, log.dataset, log.status, log.rows, log.error) == ("oddsapi", "market_quotes", "ok", 26, None)


# ---------------------------------------------------------------- the key never leaves the request (E1, E2)


def _odds_web(kind: str) -> Web:
    def route(request: httpx.Request) -> httpx.Response:
        if kind == "timeout":
            raise httpx.ReadTimeout(f"timed out: {request.url}")
        if kind == "401":
            return httpx.Response(401, headers=JSON, content=b'{"message": "bad key %s"}' % KEY.encode())
        if kind == "badjson":
            return ok(b"{" + KEY.encode())
        return ok(json.dumps(recorded("odds_api_h2h.json")).encode(), **{"x-requests-remaining": "480"})

    return Web({(ODDS_HOST, ODDS_PATH): route})


def _everything_stored(session) -> str:
    parts = []
    for model in (IngestionRun, SourceStatus, MarketQuote):
        for row in session.scalars(select(model)):
            parts.append(repr({c.name: getattr(row, c.name) for c in model.__table__.columns}))
    return "\n".join(parts)


@pytest.mark.parametrize("kind", ["ok", "401", "timeout", "badjson"])
def test_the_key_appears_in_no_log_no_row_and_no_error_on_any_path(session, caplog, kind):
    import functools
    import logging

    caplog.set_level(logging.DEBUG)
    seed_four(session)
    web = _odds_web(kind)
    get = functools.partial(fetch.fetch_json, resolver=public_dns, transport=web.transport)
    result = run.refresh_odds_quotes(session, get=get, now=ODDS_NOW, api_key=KEY)
    assert any(KEY in str(r.url) for r in web.requests)  # the key really was sent, so the checks below mean something
    assert result.status == ("ok" if kind == "ok" else "failed")
    logged = "\n".join(
        " ".join([r.getMessage(), str(r.args), r.exc_text or "", str(r.exc_info), r.name]) for r in caplog.records
    )
    assert KEY not in logged and KEY not in result.detail and KEY not in repr(result)
    assert KEY not in _everything_stored(session)


@pytest.mark.parametrize("kind", ["401", "timeout", "badjson"])
def test_a_fetch_error_and_its_cause_never_carry_the_key(kind):
    web = _odds_web(kind)
    with pytest.raises(fetch.FetchError) as caught:
        fetch.fetch_json(oddsapi.odds_url(KEY), resolver=public_dns, transport=web.transport)
    err = caught.value
    assert KEY not in repr(err) and KEY not in str(err) and err.__cause__ is None
    assert "".join(__import__("traceback").format_exception(err)).count(KEY) == 0


def test_the_http_client_does_not_log_the_key_at_info(session, caplog):
    import functools
    import logging

    caplog.set_level(logging.INFO)
    seed_four(session)
    web = _odds_web("ok")
    run.refresh_odds_quotes(
        session,
        get=functools.partial(fetch.fetch_json, resolver=public_dns, transport=web.transport),
        now=ODDS_NOW,
        api_key=KEY,
    )
    assert KEY not in "\n".join(r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------- cleanup: only games near now are matched for quotes


def test_quotes_match_only_games_that_kick_off_within_three_days_before_now_or_later(session):
    old = seed_game(session, "SEA", "DEN", datetime(2026, 10, 16, 0, 15, tzinfo=UTC), status="final")
    far_future = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)  # three days after the last kickoff in the recorded replies
    kalshi_result = run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=far_future)
    odds_result, _ = refresh_odds(session, now=far_future)
    assert quote_rows(session) == [] and kalshi_result.skipped >= 1 and odds_result.skipped >= 1
    session.query(SourceStatus).update({"blocked_until": None})  # the far run set a wait; this is a separate case
    session.commit()
    near = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)  # two days after kickoff: still matched
    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=near)
    assert {r.game_id for r in quote_rows(session)} == {old.game_id}


# ---------------------------------------------------------------- fixes from the review fan-out (R1-R9)


def test_a_very_long_run_of_failures_still_backs_off_exactly_a_day_and_never_raises(session):
    session.add(SourceStatus(source="espn_live", consecutive_failures=60, updated_at=NOW))
    session.commit()
    result = run.refresh_live_games(session, get=fake_get({espn.SCOREBOARD_URL: fetch.FetchError("x")}), now=NOW)
    status = session.get(SourceStatus, "espn_live")
    assert result.status == "failed" and status.consecutive_failures == 61
    assert status.blocked_until == NOW + timedelta(hours=24)


def test_a_database_error_while_saving_ends_the_run_failed_with_a_back_off_and_no_rows(session, monkeypatch):
    seed_four(session)

    def bad_quote(session, **values):
        session.add(MarketQuote(**{**values, "kind": "x" * 20}))  # too long for the column: fails on flush
        return True

    monkeypatch.setattr(store, "add_quote", bad_quote)
    result = run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=KNOW)
    (log,) = session.scalars(select(IngestionRun)).all()
    status = session.get(SourceStatus, "kalshi")
    assert result.status == "failed" and log.status == "failed" and log.finished_at is not None
    assert status.consecutive_failures == 1 and status.blocked_until == KNOW + timedelta(minutes=15)
    assert quote_rows(session) == []


def test_after_the_thirty_five_day_stop_one_call_is_allowed_so_the_credit_count_can_refresh(session):
    seed_four(session)
    session.add(
        SourceStatus(
            source="oddsapi", consecutive_failures=0, credits_left=10, last_ok_at=ODDS_NOW,
            blocked_until=ODDS_NOW + timedelta(days=35), updated_at=ODDS_NOW,
        )
    )  # fmt: skip
    session.commit()
    stopped, get = refresh_odds(session, now=ODDS_NOW + timedelta(days=34))
    assert stopped.status == "skipped" and get.calls == []
    resumed, get = refresh_odds(session, now=ODDS_NOW + timedelta(days=36))
    assert resumed.status == "ok" and len(get.calls) == 1
    assert session.get(SourceStatus, "oddsapi").credits_left == 499


def test_a_credit_header_that_goes_missing_does_not_erase_the_last_known_count(session):
    seed_four(session)
    refresh_odds(session)
    assert session.get(SourceStatus, "oddsapi").credits_left == 499
    refresh_odds(session, odds_routes(headers={}), now=ODDS_NOW + timedelta(hours=7))
    assert session.get(SourceStatus, "oddsapi").credits_left == 499


@pytest.mark.parametrize(("bid", "ask"), [("0.0000", "1.0000"), ("0.00", "1.00"), ("0", "1")])
def test_a_kalshi_market_with_an_empty_book_side_has_no_price_and_the_event_is_skipped(session, bid, ask):
    games = seed_four(session)

    def edit(markets):
        next(m for m in markets if m["ticker"].endswith("SEADEN-SEA")).update(yes_bid_dollars=bid, yes_ask_dollars=ask)

    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes(_edit(edit))), now=KNOW)
    assert games["SEA_DEN"].game_id not in {r.game_id for r in quote_rows(session)} and len(quote_rows(session)) == 3


def test_a_kalshi_quote_with_the_same_prices_across_kickoff_adds_one_live_row(session):
    games = seed_four(session)
    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=KNOW)
    after_kickoff = datetime(2026, 10, 16, 0, 20, tzinfo=UTC)
    run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes()), now=after_kickoff)
    rows = [r for r in quote_rows(session) if r.game_id == games["SEA_DEN"].game_id]
    assert [r.kind for r in rows] == ["pregame", "live"]


def test_a_reply_where_every_item_of_three_or_more_is_unusable_is_a_format_change_not_noise(session):
    seed_recorded_games(session)
    seed_four(session)
    board = recorded("espn_scoreboard_final.json")
    for event in board["events"]:
        event["date"] = "yesterday"
    kal = recorded("kalshi_markets.json")
    for market in kal["markets"]:
        market["yes_bid_dollars"] = 0.5  # numbers instead of strings
    odds = recorded("odds_api_h2h.json")
    for event in odds:
        event["home_team"] = "The Home Team"
    assert run.refresh_live_games(session, get=fake_get({espn.SCOREBOARD_URL: board}), now=NOW).status == "failed"
    assert run.refresh_kalshi_quotes(session, get=fake_get(kalshi_routes(kal)), now=KNOW).status == "failed"
    assert refresh_odds(session, odds_routes(odds))[0].status == "failed"
    assert live_rows(session) == [] and quote_rows(session) == []
    for source in ("espn_live", "kalshi", "oddsapi"):
        assert session.get(SourceStatus, source).consecutive_failures == 1


def test_one_or_two_unusable_items_in_a_reply_are_just_noise(session):
    seed_recorded_games(session)
    board = recorded("espn_scoreboard_final.json")
    board["events"][0]["date"] = "yesterday"
    board["events"][1]["date"] = "yesterday"
    result = run.refresh_live_games(session, get=fake_get(recorded_routes() | {espn.SCOREBOARD_URL: board}), now=NOW)
    assert result.status == "ok" and result.skipped >= 2


def test_more_kalshi_pages_than_we_read_are_logged_not_silent(session, caplog):
    import logging

    caplog.set_level(logging.WARNING)
    seed_four(session)
    full = recorded("kalshi_markets.json")["markets"]
    routes = {
        kalshi.markets_url(): {"cursor": "p2", "markets": full[:2]},
        kalshi.markets_url("p2"): {"cursor": "p3", "markets": full[2:4]},
        kalshi.markets_url("p3"): {"cursor": "p4", "markets": full[4:6]},
    }
    run.refresh_kalshi_quotes(session, get=fake_get(routes), now=KNOW)
    assert any("more pages" in r.getMessage() for r in caplog.records)
