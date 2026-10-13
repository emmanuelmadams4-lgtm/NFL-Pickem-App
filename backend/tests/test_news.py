"""Step 8c-8f,8h: news from allowlisted public feeds.

No test touches the network. Requests go to an httpx MockTransport and DNS is an injected function. The two
recorded real feeds and their robots.txt files (tests/fixtures/news) were fetched by hand on 2026-10-13.
"""

import gzip
import hashlib
import socket
import ssl
import unicodedata
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from nflpi.ingestion.news import fetch, match, parse, run, sources, store
from nflpi.models import AppSetting, IngestionRun, NewsItem, Team, TeamStar

FIXTURES = Path(__file__).parent / "fixtures" / "news"
RECORDED_AT = datetime(2026, 10, 13, 4, 0, tzinfo=UTC)  # just after the newest item in the recorded feeds
PUBLIC_IP = "93.184.216.34"
XML = {"content-type": "text/xml; charset=UTF-8"}
TEXT = {"content-type": "text/plain"}
ESPN, CBS = sources.SOURCES[0], sources.SOURCES[1]


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
            return httpx.Response(404, headers=TEXT, content=b"")
        return route(request) if callable(route) else route

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)

    def paths(self) -> list[str]:
        return [f"{r.headers['host']}{r.url.path}" for r in self.requests]


def feed_xml(*items: str) -> bytes:
    body = "".join(items)
    return f'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>{body}</channel></rss>'.encode()


def item(title="Bills win", link="https://www.espn.com/nfl/story/_/id/1", desc="Short.", date=None) -> str:
    date = date or RECORDED_AT.strftime("%a, %d %b %Y %H:%M:%S GMT")
    link_tag = f"<link>{link}</link>" if link is not None else ""
    return f"<item><title>{title}</title>{link_tag}<description>{desc}</description><pubDate>{date}</pubDate></item>"


def web_for(source, feed: bytes, robots: bytes = b"User-agent: *\nDisallow: /private/\n", **extra) -> Web:
    url = httpx.URL(source.url)
    routes = {
        (source.host, "/robots.txt"): httpx.Response(200, headers=TEXT, content=robots),
        (source.host, url.path): httpx.Response(200, headers=XML, content=feed),
    }
    routes.update(extra)
    return Web(routes)


def both_webs(feed_a: bytes, feed_b: bytes) -> Web:
    a, b = web_for(ESPN, feed_a), web_for(CBS, feed_b)
    return Web({**a.routes, **b.routes})


def guarded(url: str, web: Web, **kw) -> fetch.FetchResult:
    return fetch.fetch_guarded(
        url,
        host=kw.pop("host", "www.espn.com"),
        resolver=kw.pop("resolver", public_dns),
        transport=web.transport,
        content_types=("xml",),
        **kw,
    )


# ---------------------------------------------------------------- allowlist (8c)


def test_the_allowlist_is_https_feeds_on_exact_hosts():
    assert {s.id for s in sources.SOURCES} == {"espn", "cbs"}
    for s in sources.SOURCES:
        url = httpx.URL(s.url)
        assert url.scheme == "https" and url.host == s.host and url.port is None
        assert s.link_suffixes and all(s.host.endswith(x) for x in s.link_suffixes)


# ---------------------------------------------------------------- guards (8c)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.espn.com/x",
        "https://evil.example/x",
        "https://www.espn.com.evil.example/x",
        "https://user:pw@www.espn.com/x",
        "https://www.espn.com:8443/x",
        "file:///etc/passwd",
    ],
)
def test_a_url_that_is_not_https_on_the_exact_host_is_refused_before_any_lookup(url):
    web, looked_up = Web({}), []
    with pytest.raises(fetch.Blocked):
        guarded(url, web, resolver=lambda h: looked_up.append(h) or [PUBLIC_IP])
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
        ["64:ff9b::1"],  # NAT64: Python calls it global, we do not
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
        guarded("https://www.espn.com/feed", web, resolver=lambda h: addresses)
    assert web.requests == []


@pytest.mark.parametrize("resolver", [lambda h: [], lambda h: (_ for _ in ()).throw(socket.gaierror("nope"))])
def test_a_host_that_does_not_resolve_is_a_fetch_error_and_nothing_is_sent(resolver):
    web = Web({})
    with pytest.raises(fetch.FetchError):
        guarded("https://www.espn.com/feed", web, resolver=resolver)
    assert web.requests == []


def test_when_several_public_addresses_come_back_one_checked_address_is_used():
    web = Web({("www.espn.com", "/feed"): httpx.Response(200, headers=XML, content=feed_xml())})
    guarded("https://www.espn.com/feed", web, resolver=lambda h: [PUBLIC_IP, "93.184.216.35"])
    assert [r.url.host for r in web.requests] == [PUBLIC_IP]


def test_the_client_ignores_proxy_environment_and_keeps_certificate_checks(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    client = fetch.build_client(None)
    assert client.trust_env is False and client.follow_redirects is False
    assert client._transport._pool._ssl_context.verify_mode == ssl.CERT_REQUIRED  # verify is on
    client.close()


def test_the_connection_goes_to_the_checked_address_with_the_real_name_as_host_and_sni():
    web = Web({("www.espn.com", "/feed"): httpx.Response(200, headers=XML, content=feed_xml())})
    guarded("https://www.espn.com/feed", web)
    (req,) = web.requests
    assert req.url.host == PUBLIC_IP and req.url.scheme == "https"
    assert req.headers["host"] == "www.espn.com"
    assert req.extensions["sni_hostname"] == "www.espn.com"


def test_redirects_on_the_same_host_are_followed_up_to_three_hops():
    def hop(n):
        return lambda r: httpx.Response(301, headers={"location": f"/h{n}"})

    routes = {("www.espn.com", "/feed"): hop(1), ("www.espn.com", "/h1"): hop(2), ("www.espn.com", "/h2"): hop(3)}
    routes[("www.espn.com", "/h3")] = httpx.Response(200, headers=XML, content=feed_xml())
    assert guarded("https://www.espn.com/feed", Web(routes)).status == 200
    routes[("www.espn.com", "/h3")] = hop(4)  # a fourth hop is one too many
    with pytest.raises(fetch.FetchError):
        guarded("https://www.espn.com/feed", Web(routes))


@pytest.mark.parametrize(
    "location",
    ["https://www.nbcsports.com/x", "http://www.espn.com/x", "https://www.espn.com.evil.example/x", "//evil.example/x"],
)
def test_a_redirect_off_the_host_or_to_http_is_refused_and_never_followed(location):
    web = Web({("www.espn.com", "/feed"): httpx.Response(301, headers={"location": location})})
    with pytest.raises(fetch.Blocked):
        guarded("https://www.espn.com/feed", web)
    assert web.paths() == ["www.espn.com/feed"]


def test_every_hop_is_resolved_and_checked_again():
    calls = []

    def dns(host):
        calls.append(host)
        return [PUBLIC_IP] if len(calls) == 1 else ["127.0.0.1"]

    web = Web({("www.espn.com", "/feed"): httpx.Response(302, headers={"location": "/next"})})
    with pytest.raises(fetch.Blocked):
        guarded("https://www.espn.com/feed", web, resolver=dns)
    assert len(calls) == 2 and web.paths() == ["www.espn.com/feed"]


def test_a_body_over_the_cap_is_refused_even_when_it_is_compressed():
    big = Web({("www.espn.com", "/feed"): httpx.Response(200, headers=XML, content=b"x" * 3_000_000)})
    with pytest.raises(fetch.FetchError):
        guarded("https://www.espn.com/feed", big)
    bomb = gzip.compress(b"0" * 20_000_000)
    assert len(bomb) < fetch.MAX_FEED_BYTES  # small on the wire, huge once decoded
    web = Web(
        {("www.espn.com", "/feed"): httpx.Response(200, headers=XML | {"content-encoding": "gzip"}, content=bomb)}
    )
    with pytest.raises(fetch.FetchError):
        guarded("https://www.espn.com/feed", web)


def test_a_body_at_the_cap_is_accepted():
    body = b"x" * fetch.MAX_FEED_BYTES
    web = Web({("www.espn.com", "/feed"): httpx.Response(200, headers=XML, content=body)})
    assert guarded("https://www.espn.com/feed", web).body == body


def test_a_slow_response_hits_the_wall_clock_deadline():
    now = [0.0]

    def slow():
        def chunks():
            for _ in range(5):
                now[0] += 10  # each chunk takes ten fake seconds
                yield b"<rss>"

        return httpx.Response(200, headers=XML, content=chunks())

    web = Web({("www.espn.com", "/feed"): lambda r: slow()})
    with pytest.raises(fetch.FetchError, match="deadline"):
        guarded("https://www.espn.com/feed", web, clock=lambda: now[0])


@pytest.mark.parametrize("exc", [httpx.ReadTimeout("slow"), httpx.ConnectError("down"), httpx.RemoteProtocolError("x")])
def test_network_errors_are_fetch_errors(exc):
    def boom(request):
        raise exc

    with pytest.raises(fetch.FetchError):
        fetch.fetch_guarded(
            "https://www.espn.com/feed",
            host="www.espn.com",
            resolver=public_dns,
            transport=httpx.MockTransport(boom),
            content_types=("xml",),
        )


def test_the_timeout_is_ten_seconds():
    assert fetch.TIMEOUT_S == 10 and fetch.MAX_FEED_BYTES == 2_000_000 and fetch.MAX_REDIRECTS == 3


@pytest.mark.parametrize("ctype", ["text/html", "application/json", "image/png", ""])
def test_a_feed_with_the_wrong_content_type_is_a_fetch_error(ctype):
    web = Web({("www.espn.com", "/feed"): httpx.Response(200, headers={"content-type": ctype}, content=b"<rss/>")})
    with pytest.raises(fetch.FetchError):
        guarded("https://www.espn.com/feed", web)


@pytest.mark.parametrize(
    "ctype", ["application/rss+xml", "application/atom+xml; charset=utf-8", "application/xml", "text/xml"]
)
def test_feed_content_types_are_accepted(ctype):
    web = Web({("www.espn.com", "/feed"): httpx.Response(200, headers={"content-type": ctype}, content=b"<rss/>")})
    assert guarded("https://www.espn.com/feed", web).status == 200


@pytest.mark.parametrize("status", [403, 429])
def test_403_and_429_are_blocked(status):
    web = Web({("www.espn.com", "/feed"): httpx.Response(status)})
    with pytest.raises(fetch.Blocked):
        guarded("https://www.espn.com/feed", web)


@pytest.mark.parametrize("status", [500, 502, 503, 400, 401])
def test_other_failures_are_fetch_errors_not_blocks(status):
    web = Web({("www.espn.com", "/feed"): httpx.Response(status)})
    with pytest.raises(fetch.FetchError) as caught:
        guarded("https://www.espn.com/feed", web)
    assert not isinstance(caught.value, fetch.Blocked)


def test_the_user_agent_names_the_app_and_adds_the_contact_when_set(monkeypatch):
    from nflpi.config import get_settings

    web = Web({("www.espn.com", "/feed"): httpx.Response(200, headers=XML, content=feed_xml())})
    guarded("https://www.espn.com/feed", web)
    assert web.requests[0].headers["user-agent"] == fetch.user_agent()
    assert "NFLPickemIntel/1.0" in fetch.user_agent() and "@" not in fetch.user_agent()
    monkeypatch.setenv("NEWS_CONTACT", "owner@example.test")
    get_settings.cache_clear()
    try:
        assert fetch.user_agent().endswith("owner@example.test)") or "owner@example.test" in fetch.user_agent()
        monkeypatch.setenv("NEWS_CONTACT", "a@b.test\r\nX-Evil: 1")
        get_settings.cache_clear()
        assert "\r" not in fetch.user_agent() and "\n" not in fetch.user_agent() and "X-Evil" not in fetch.user_agent()
    finally:
        monkeypatch.delenv("NEWS_CONTACT")
        get_settings.cache_clear()


# ---------------------------------------------------------------- robots (8c)


def feed_through_robots(robots: httpx.Response | None, **kw) -> tuple[Web, fetch.FetchResult | None, Exception | None]:
    routes = {(ESPN.host, httpx.URL(ESPN.url).path): httpx.Response(200, headers=XML, content=feed_xml())}
    if robots is not None:
        routes[(ESPN.host, "/robots.txt")] = robots
    web = Web(routes)
    try:
        return web, fetch.fetch_feed(ESPN, resolver=public_dns, transport=web.transport, **kw), None
    except Exception as exc:  # noqa: BLE001 - the test inspects it
        return web, None, exc


def test_robots_is_read_before_every_fetch_and_obeyed():
    deny = httpx.Response(200, headers=TEXT, content=b"User-agent: *\nDisallow: /espn/\n")
    web, result, exc = feed_through_robots(deny)
    assert isinstance(exc, fetch.Blocked) and "robots" in str(exc)
    assert web.paths() == ["www.espn.com/robots.txt"]  # the feed itself is never requested
    web, result, exc = feed_through_robots(httpx.Response(200, headers=TEXT, content=b"User-agent: *\nDisallow: /x/\n"))
    assert exc is None and web.paths() == ["www.espn.com/robots.txt", "www.espn.com/espn/rss/nfl/news"]


def test_robots_that_names_our_agent_is_obeyed():
    body = b"User-agent: NFLPickemIntel\nDisallow: /\n\nUser-agent: *\nDisallow:\n"
    _, _, exc = feed_through_robots(httpx.Response(200, headers=TEXT, content=body))
    assert isinstance(exc, fetch.Blocked)


@pytest.mark.parametrize("status", [404, 410])
def test_missing_robots_means_allowed(status):
    _, result, exc = feed_through_robots(httpx.Response(status, headers=TEXT))
    assert exc is None and result.status == 200


@pytest.mark.parametrize(
    "robots",
    [
        httpx.Response(401),
        httpx.Response(403),
        httpx.Response(500),
        httpx.Response(503),
        httpx.Response(200, headers={"content-type": "text/html"}, content=b"<html>not rules</html>"),
        httpx.Response(200, headers=TEXT, content=b"x" * (fetch.MAX_ROBOTS_BYTES + 1)),
        httpx.Response(301, headers={"location": "https://www.nbcsports.com/robots.txt"}),
        httpx.Response(301, headers={"location": "/other-robots.txt"}),
    ],
    ids=["401", "403", "500", "503", "html", "oversize", "redirect-off-host", "redirect-same-host"],
)
def test_robots_that_cannot_be_trusted_means_denied(robots):
    web, _, exc = feed_through_robots(robots)
    assert isinstance(exc, fetch.Blocked)
    assert "www.espn.com/espn/rss/nfl/news" not in web.paths()


def test_robots_rules_are_parsed_from_text_never_read_by_urllib(monkeypatch):
    import urllib.request

    def forbidden(*a, **k):
        raise AssertionError("urllib must not be used")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    _, result, exc = feed_through_robots(httpx.Response(200, headers=TEXT, content=b"User-agent: *\nDisallow: /x/\n"))
    assert exc is None and result.status == 200


def test_robots_unreachable_means_denied():
    def boom(request):
        raise httpx.ConnectError("down")

    with pytest.raises(fetch.Blocked):
        fetch.fetch_feed(ESPN, resolver=public_dns, transport=httpx.MockTransport(boom))


@pytest.mark.parametrize("status", [204, 206, 404, 410])
def test_only_200_and_304_count_as_a_good_feed_answer(status):
    web = web_for(ESPN, b"", **{(ESPN.host, "/espn/rss/nfl/news"): httpx.Response(status, headers=XML)})
    with pytest.raises(fetch.FetchError):
        fetch.fetch_feed(ESPN, resolver=public_dns, transport=web.transport)


def test_the_recorded_real_robots_files_allow_our_two_feeds():
    for source in sources.SOURCES:
        robots = (FIXTURES / f"{source.id}_robots.txt").read_bytes()
        web = web_for(source, (FIXTURES / f"{source.id}.xml").read_bytes(), robots=robots)
        result = fetch.fetch_feed(source, resolver=public_dns, transport=web.transport)
        assert result.status == 200 and len(result.body) > 1000


def test_validators_are_sent_and_a_304_is_a_clean_empty_result():
    seen = {}

    def not_modified(request):
        seen.update(request.headers)
        return httpx.Response(304)

    web = web_for(ESPN, b"", **{(ESPN.host, "/espn/rss/nfl/news"): not_modified})
    result = fetch.fetch_feed(
        ESPN,
        resolver=public_dns,
        transport=web.transport,
        validators={"etag": 'W/"abc"', "last_modified": "Wed, 01 Jan 2025 00:00:00 GMT"},
    )
    assert result.status == 304 and result.body == b""
    assert seen["if-none-match"] == 'W/"abc"' and seen["if-modified-since"] == "Wed, 01 Jan 2025 00:00:00 GMT"


@pytest.mark.parametrize("bad", ["x" * 300, "ab\x00c", "a\x07b"])
def test_validators_that_are_long_or_have_control_characters_are_never_saved_or_sent(bad):
    headers = XML | {"etag": bad, "last-modified": bad}
    web = web_for(
        ESPN, b"", **{(ESPN.host, "/espn/rss/nfl/news"): httpx.Response(200, headers=headers, content=feed_xml())}
    )
    result = fetch.fetch_feed(ESPN, resolver=public_dns, transport=web.transport)
    assert result.etag is None and result.last_modified is None
    sent = web_for(ESPN, feed_xml())
    fetch.fetch_feed(
        ESPN, resolver=public_dns, transport=sent.transport, validators={"etag": bad, "last_modified": bad}
    )
    assert "if-none-match" not in sent.requests[-1].headers and "if-modified-since" not in sent.requests[-1].headers


def test_the_result_carries_the_new_validators():
    headers = XML | {"etag": '"v2"', "last-modified": "Tue, 02 Jan 2025 00:00:00 GMT"}
    web = web_for(
        ESPN, b"", **{(ESPN.host, "/espn/rss/nfl/news"): httpx.Response(200, headers=headers, content=feed_xml())}
    )
    result = fetch.fetch_feed(ESPN, resolver=public_dns, transport=web.transport)
    assert result.etag == '"v2"' and result.last_modified == "Tue, 02 Jan 2025 00:00:00 GMT"


# ---------------------------------------------------------------- extract (8d)


def one(feed: bytes, source=ESPN, now=RECORDED_AT) -> list[parse.Item]:
    return parse.parse_feed(feed, source, now)


def test_tags_scripts_and_entities_become_plain_text():
    desc = "&lt;p&gt;Hello &lt;b&gt;Buffalo&lt;/b&gt;&lt;script&gt;alert(1)&lt;/script&gt; &amp;amp; co&lt;/p&gt;"
    (got,) = one(feed_xml(item(desc=desc)))
    assert got.extract == "Hello Buffalo & co" and "alert" not in got.extract and "<" not in got.extract


def test_control_bidi_zero_width_and_private_use_characters_are_removed_everywhere():
    nasty = "Bills‮​ win\x07\x1b[31m big⁦"
    (got,) = one(feed_xml(item(title=nasty, desc=f"Josh​ Allen {nasty}")))
    for text in (got.title, got.extract):
        assert not any(unicodedata.category(c).startswith("C") for c in text), text
    assert got.title.startswith("Bills win") and "Josh Allen" in got.extract


def test_whitespace_is_collapsed_and_lengths_are_capped():
    (got,) = one(feed_xml(item(title="A\n\n  B\t C" + "x" * 500, desc="word " * 200)))
    assert got.title.startswith("A B C") and len(got.title) <= 200
    (glued,) = one(feed_xml(item(title="Bills&#10;win&#9;big")))
    assert glued.title == "Bills win big"
    assert len(got.extract) <= 300 and "  " not in got.extract


def test_clean_text_is_the_one_cleaner():
    assert parse.clean_text("a‮b\x00c", 10) == "abc"
    assert len(parse.clean_text("é" * 50, 10)) == 10


@pytest.mark.parametrize(
    "link",
    [
        "javascript:alert(1)",
        "data:text/html,hi",
        "http://www.espn.com/nfl/story/1",
        "https://evil.example/nfl",
        "https://notespn.com/nfl",
        "https://evilespn.com/nfl",
        "https://www.espn.com./nfl",
        "https://www.espn.com:8443/nfl",
        "https://www.espn.com:443/nfl",
        "https://www.espn.com\\@evil.example/nfl",
        "https://www.espn.com/a b",
        "https://www.espn.com/a\\b",
        "https://www.\u0435spn.com/nfl",
        "https://www.espn.com.evil.example/nfl",
        "https://user:pw@www.espn.com/nfl",
        "https://www.espn.com/" + "a" * 2100,
        "",
        None,
    ],
)
def test_an_item_with_an_unsafe_or_foreign_link_is_skipped_not_fatal(link):
    got = one(feed_xml(item(title="bad", link=link), item(title="good")))
    assert [i.title for i in got] == ["good"]


def test_links_are_canonical_https_without_trackers_or_fragments():
    link = "https://WWW.ESPN.com/nfl/story?id=1&utm_source=x&fbclid=y&gclid=z&ocid=q&keep=2#frag"
    (got,) = one(feed_xml(item(link=link.replace("&", "&amp;"))))
    assert got.url == "https://www.espn.com/nfl/story?id=1&keep=2"
    assert parse.canonical_url("https://a.espn.com/x", ("espn.com",)) == "https://a.espn.com/x"
    assert parse.canonical_url("https://www.espn.com/é", ("espn.com",)) == "https://www.espn.com/%C3%A9"


def test_a_missing_date_stays_missing_and_a_future_date_is_dropped_not_trusted():
    fresh = RECORDED_AT.strftime("%a, %d %b %Y %H:%M:%S GMT")
    future = (RECORDED_AT + timedelta(days=3)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    nodate = "<item><title>no date</title><link>https://www.espn.com/a</link></item>"
    got = {
        i.title: i for i in one(feed_xml(item(title="fresh", date=fresh), item(title="future", date=future), nodate))
    }
    assert got["fresh"].published_at == RECORDED_AT and got["fresh"].published_at.tzinfo is not None
    assert got["future"].published_at is None and got["no date"].published_at is None


def test_items_older_than_thirty_days_are_skipped():
    old = (RECORDED_AT - timedelta(days=31)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert [i.title for i in one(feed_xml(item(title="old", date=old), item(title="new")))] == ["new"]


def test_at_most_one_hundred_entries_are_read():
    many = [item(title=f"t{n}", link=f"https://www.espn.com/{n}") for n in range(150)]
    assert len(one(feed_xml(*many))) == 100


@pytest.mark.parametrize("body", [b"", b"<html><body>not a feed</body></html>", b"\x00\x01\x02", b"{}"])
def test_a_body_that_is_not_a_feed_raises(body):
    with pytest.raises(parse.FeedError):
        one(body)


def test_a_feed_body_that_is_only_a_file_path_is_never_opened(tmp_path):
    secret = tmp_path / "secret.xml"
    secret.write_text(feed_xml(item(title="FROM A LOCAL FILE")).decode())
    with pytest.raises(parse.FeedError):
        one(str(secret).encode())


def test_a_real_feed_with_no_entries_is_just_empty():
    assert one(feed_xml()) == []


@pytest.mark.parametrize("source", sources.SOURCES, ids=lambda s: s.id)
def test_the_recorded_real_feeds_parse_to_clean_items(source):
    items = one((FIXTURES / f"{source.id}.xml").read_bytes(), source)
    assert len(items) >= 5
    for it in items:
        assert it.title and it.url.startswith("https://") and httpx.URL(it.url).host.endswith(source.link_suffixes)
        assert len(it.title) <= 200 and len(it.extract) <= 300 and "<" not in it.title + it.extract
        assert not any(unicodedata.category(c).startswith("C") for c in it.title + it.extract)


# ---------------------------------------------------------------- tie to team and player (8e)


def seed_names(session):
    session.add_all(
        Team(abbr=a, name=n, nick=k, conference="AFC", division="d", color="#000", color2="#000", logo_url="x")
        for a, n, k in [
            ("BUF", "Buffalo Bills", "Bills"),
            ("NYJ", "New York Jets", "Jets"),
            ("NYG", "New York Giants", "Giants"),
            ("MIA", "Miami Dolphins", "Dolphins"),
        ]
    )

    def star(season, week, team, rank, pid, name):
        return TeamStar(
            season=season, week=week, team=team, slot="off", rank=rank, player_id=pid, player=name, position="QB",
            snaps=100, production=1.0, score=1.0, source="t", computed_at=RECORDED_AT,
        )  # fmt: skip

    session.add_all(
        [
            star(2026, 5, "BUF", 1, "00-A", "Josh Allen"),
            star(2026, 5, "NYJ", 1, "00-B", "Garrett Wilson"),
            star(2026, 5, "MIA", 1, "00-C", "Tyreek Hill"),
            star(2026, 5, "NYG", 1, "00-D", "Josh Allen"),  # same name, other player: ambiguous
            star(2026, 4, "NYJ", 2, "00-E", "Old Season Guy"),
            star(2026, 5, "MIA", 2, "00-F", "Patrick​ Surtain II"),  # a control character in the stored name
            star(2025, 17, "BUF", 1, "00-G", "Last Year Guy"),  # an earlier season is not today's roster
            star(2026, 5, "BUF", 2, None, "Nameless Id"),  # no id: cannot be tied
        ]
    )
    session.commit()
    return match.load_names(session)


def tie(session_names, title, extract=""):
    return match.tie(title, extract, session_names)


def test_teams_match_on_whole_names_and_nicknames_ignoring_case(session):
    names = seed_names(session)
    assert tie(names, "Bills beat Jets in OT").team_ids == ["BUF", "NYJ"]
    assert tie(names, "BUFFALO BILLS rally").team_ids == ["BUF"]
    assert tie(names, "the Jets' secondary", "Giants next").team_ids == ["NYG", "NYJ"]
    for miss in [
        "Billsboro mayor",
        "Jetsons reboot",
        "Giantsville",
        "Bill Belichick",
        "New York is loud",
        "Miami heat",
    ]:
        assert tie(names, miss).team_ids == [], miss


def test_a_player_matches_on_his_full_name_and_brings_his_club(session):
    names = seed_names(session)
    got = tie(names, "Garrett Wilson limited", "")
    assert got.player_ids == ["00-B"] and got.team_ids == ["NYJ"]
    assert tie(names, "Tyreek Hill is back").player_ids == ["00-C"]
    assert tie(names, "Wilson limited").player_ids == [] and tie(names, "Garrett only").player_ids == []


def test_a_name_shared_by_two_players_is_never_guessed(session):
    names = seed_names(session)
    assert tie(names, "Josh Allen throws three scores").player_ids == []


def test_only_the_newest_season_with_an_id_counts_and_names_are_cleaned_like_headlines(session):
    names = seed_names(session)
    assert tie(names, "Last Year Guy retires").player_ids == []
    assert tie(names, "Nameless Id plays").player_ids == []
    assert tie(names, "Patrick Surtain II is out").player_ids == ["00-F"]
    assert tie(names, "Old Season Guy plays").player_ids == [
        "00-E"
    ]  # an earlier week of the newest season still counts


def test_player_match_runs_over_title_and_extract(session):
    names = seed_names(session)
    assert tie(names, "Big news", "Tyreek Hill signs a deal").player_ids == ["00-C"]


def test_with_no_stars_loaded_teams_still_match_and_players_do_not(session):
    session.add(
        Team(
            abbr="BUF",
            name="Buffalo Bills",
            nick="Bills",
            conference="AFC",
            division="d",
            color="x",
            color2="x",
            logo_url="x",
        )
    )
    session.commit()
    names = match.load_names(session)
    assert tie(names, "Josh Allen and the Bills") == match.Tie(team_ids=["BUF"], player_ids=[], tags=[])


@pytest.mark.parametrize(
    "text,tags",
    [
        ("Star placed on injured reserve", ["injury"]),
        ("Starter ruled out vs. Dolphins", ["injury"]),
        ("QB questionable with ankle injury", ["injury"]),
        ("Team trades receiver for a pick", ["trade"]),
        ("Traded: a star changes teams", ["trade"]),
        ("Head coach fired after loss", ["coach"]),
        ("Club hires new defensive coordinator", ["coach"]),
        ("New play-caller named", ["playcaller"]),
        ("Who is calling plays now? New play caller", ["playcaller"]),
        ("Bills win again", []),
        ("A tradeoff on the line", []),
        ("Uninjured and happy", []),
    ],
)
def test_keyword_tags(session, text, tags):
    assert tie(seed_names(session), text).tags == tags


# ---------------------------------------------------------------- dedupe and store (8f)


def make_items(*titles: str) -> list[parse.Item]:
    return [
        parse.Item(
            title=t,
            url=f"https://www.espn.com/{hashlib.sha256(t.encode()).hexdigest()[:8]}",
            published_at=RECORDED_AT,
            extract="e",
        )
        for t in titles
    ]


def rows(session) -> list[NewsItem]:
    return list(session.scalars(select(NewsItem).order_by(NewsItem.id)))


def test_new_items_are_stored_with_their_ties_and_a_title_hash(session):
    names = seed_names(session)
    assert store.store_items(session, "espn", make_items("Bills beat Jets", "Nothing here"), names, RECORDED_AT) == 2
    first, second = rows(session)
    assert first.source == "espn" and first.team_ids == ["BUF", "NYJ"] and first.player_ids == []
    assert first.title_sha256 == hashlib.sha256(b"Bills beat Jets").hexdigest()
    assert first.fetched_at == RECORDED_AT and first.extract == "e" and first.tags == []
    assert second.team_ids == [] and second.player_ids == []


def test_storing_the_same_items_again_adds_nothing(session):
    names = seed_names(session)
    items = make_items("Bills beat Jets", "Other")
    assert store.store_items(session, "espn", items, names, RECORDED_AT) == 2
    assert store.store_items(session, "espn", items, names, RECORDED_AT + timedelta(minutes=40)) == 0
    assert len(rows(session)) == 2


def test_the_same_headline_under_a_new_url_is_one_story_per_source_but_two_sources_keep_theirs(session):
    names = seed_names(session)
    store.store_items(session, "espn", make_items("Same headline"), names, RECORDED_AT)
    moved = [parse.Item(title="Same headline", url="https://www.espn.com/moved", published_at=None, extract="")]
    assert store.store_items(session, "espn", moved, names, RECORDED_AT) == 0
    other = [parse.Item(title="Same headline", url="https://www.cbssports.com/x", published_at=None, extract="")]
    assert store.store_items(session, "cbs", other, names, RECORDED_AT) == 1
    assert [r.source for r in rows(session)] == ["espn", "cbs"]


def test_the_database_itself_refuses_a_duplicate_url(session):
    session.add(
        NewsItem(
            source="espn",
            title="a",
            title_sha256="1" * 64,
            url_canonical="https://www.espn.com/a",
            fetched_at=RECORDED_AT,
            extract="",
            team_ids=[],
            player_ids=[],
            tags=[],
        )
    )
    session.commit()
    session.add(
        NewsItem(
            source="cbs",
            title="b",
            title_sha256="2" * 64,
            url_canonical="https://www.espn.com/a",
            fetched_at=RECORDED_AT,
            extract="",
            team_ids=[],
            player_ids=[],
            tags=[],
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_news_is_pruned_thirty_days_after_we_fetched_it(session):
    names = seed_names(session)
    now = RECORDED_AT
    store.store_items(session, "espn", make_items("fetched long ago"), names, now - timedelta(days=31))
    store.store_items(session, "espn", make_items("fetched recently"), names, now - timedelta(days=29))
    assert store.prune(session, now) == 1
    assert [r.title for r in rows(session)] == ["fetched recently"]


# ---------------------------------------------------------------- the run: failure handling (8h)


def runs(session, dataset=None) -> list[IngestionRun]:
    q = select(IngestionRun).order_by(IngestionRun.id)
    if dataset:
        q = q.where(IngestionRun.dataset == dataset)
    return list(session.scalars(q))


def go(session, web: Web, now=RECORDED_AT, **kw):
    return run.run_news(session, now=now, resolver=public_dns, transport=web.transport, **kw)


def real_web() -> Web:
    a, b = (
        web_for(s, (FIXTURES / f"{s.id}.xml").read_bytes(), (FIXTURES / f"{s.id}_robots.txt").read_bytes())
        for s in sources.SOURCES
    )
    return Web({**a.routes, **b.routes})


def test_a_poll_stores_both_recorded_feeds_and_logs_one_run_each(session):
    seed_names(session)
    made = go(session, real_web())
    assert [(r.source, r.dataset, r.status) for r in made] == [("espn", "news:espn", "ok"), ("cbs", "news:cbs", "ok")]
    stored = rows(session)
    assert {r.source for r in stored} == {"espn", "cbs"}
    assert sum(r.rows for r in made) == len(stored) >= 10
    assert all(r.started_at == RECORDED_AT and r.finished_at is not None for r in made)


def test_a_second_poll_inside_thirty_minutes_sends_nothing_and_logs_nothing(session):
    seed_names(session)
    web = real_web()
    go(session, web)
    sent = len(web.requests)
    assert go(session, web, now=RECORDED_AT + timedelta(minutes=29)) == []
    assert len(web.requests) == sent and len(runs(session)) == 2


@pytest.mark.parametrize("status", ["running", "failed"])
def test_a_running_or_failed_row_inside_the_window_also_holds_the_next_poll_back(session, status):
    session.add(
        IngestionRun(source="espn", dataset="news:espn", started_at=RECORDED_AT - timedelta(minutes=5), status=status)
    )
    session.commit()
    web = web_for(ESPN, feed_xml(item()))
    assert go(session, web, sources=(ESPN,)) == [] and web.requests == []


def test_a_poll_after_thirty_minutes_is_idempotent_and_uses_the_saved_validators(session):
    seed_names(session)
    headers = XML | {"etag": '"v1"'}
    feed = feed_xml(item(title="Bills win", link="https://www.espn.com/a"))
    seen = []

    def serve(request):
        seen.append(request.headers.get("if-none-match"))
        return (
            httpx.Response(304)
            if request.headers.get("if-none-match")
            else httpx.Response(200, headers=headers, content=feed)
        )

    web = web_for(ESPN, feed, **{(ESPN.host, "/espn/rss/nfl/news"): serve})
    (first,) = go(session, web, sources=(ESPN,))
    assert first.rows == 1 and session.get(AppSetting, "news:espn:validators").value["etag"] == '"v1"'
    (second,) = go(session, web, now=RECORDED_AT + timedelta(minutes=31), sources=(ESPN,))
    assert seen == [None, '"v1"'] and second.status == "ok" and second.rows == 0 and len(rows(session)) == 1


def test_items_are_tied_to_teams_and_stars_when_stored(session):
    seed_names(session)
    feed = feed_xml(
        item(title="Garrett Wilson hurt as Jets lose to Bills", link="https://www.espn.com/a", desc="ruled out")
    )
    go(session, web_for(ESPN, feed), sources=(ESPN,))
    (got,) = rows(session)
    assert got.team_ids == ["BUF", "NYJ"] and got.player_ids == ["00-B"] and got.tags == ["injury"]


def test_at_most_one_hundred_items_are_stored_per_poll(session):
    many = [item(title=f"t{n}", link=f"https://www.espn.com/{n}") for n in range(150)]
    (made,) = go(session, web_for(ESPN, feed_xml(*many)), sources=(ESPN,))
    assert made.rows == 100 == len(rows(session))


@pytest.mark.parametrize("status", [403, 429])
def test_a_block_stops_that_source_for_24_hours_and_never_retries_in_a_loop(session, status):
    web = web_for(ESPN, b"", **{(ESPN.host, "/espn/rss/nfl/news"): httpx.Response(status)})
    (made,) = go(session, web, sources=(ESPN,))
    assert made.status == "failed" and made.error.startswith("blocked:")
    sent = len(web.requests)
    assert go(session, web, now=RECORDED_AT + timedelta(hours=23), sources=(ESPN,)) == []
    assert len(web.requests) == sent  # not one request in 23 hours, and no new run row
    again = go(session, web, now=RECORDED_AT + timedelta(hours=25), sources=(ESPN,))
    assert len(web.requests) > sent and again[0].error.startswith("blocked:")


def test_run_errors_hold_at_most_forty_characters_of_what_the_server_said(session):
    long_location = "https://www.nbcsports.com/" + "y" * 200
    web = web_for(
        ESPN, b"", **{(ESPN.host, "/espn/rss/nfl/news"): httpx.Response(301, headers={"location": long_location})}
    )
    (made,) = go(session, web, sources=(ESPN,))
    assert "yyyyy" * 9 not in made.error and len(made.error) <= 100


def test_nothing_else_the_feed_names_is_ever_fetched(session):
    extras = (
        "<enclosure url='https://www.espn.com/a.mp3' length='1' type='audio/mpeg'/>"
        "<image><url>https://www.espn.com/i.png</url></image>"
    )
    feed = feed_xml(item().replace("</item>", extras + "</item>")).replace(
        b"<rss", b'<?xml-stylesheet href="https://www.espn.com/s.xsl"?><rss', 1
    )
    web = web_for(ESPN, feed)
    go(session, web, sources=(ESPN,))
    assert web.paths() == ["www.espn.com/robots.txt", "www.espn.com/espn/rss/nfl/news"]


def test_a_block_changes_nothing_about_how_we_ask(session):
    web = web_for(ESPN, b"", **{(ESPN.host, "/espn/rss/nfl/news"): httpx.Response(403)})
    go(session, web, sources=(ESPN,))
    go(session, web, now=RECORDED_AT + timedelta(hours=25), sources=(ESPN,))
    agents = {r.headers["user-agent"] for r in web.requests}
    assert agents == {fetch.user_agent()}


@pytest.mark.parametrize(
    "web_factory,dns",
    [
        (lambda: web_for(ESPN, feed_xml(), robots=b"User-agent: *\nDisallow: /\n"), public_dns),
        (
            lambda: Web(
                {
                    (ESPN.host, "/robots.txt"): httpx.Response(200, headers=TEXT, content=b""),
                    (ESPN.host, "/espn/rss/nfl/news"): httpx.Response(
                        301, headers={"location": "https://www.nbcsports.com/x"}
                    ),
                }
            ),
            public_dns,
        ),
        (lambda: web_for(ESPN, feed_xml()), lambda h: ["10.1.2.3"]),
    ],
    ids=["robots-deny", "redirect-off-host", "private-address"],
)
def test_robots_deny_off_host_redirect_and_private_address_are_all_blocks(session, web_factory, dns):
    (made,) = run.run_news(session, now=RECORDED_AT, resolver=dns, transport=web_factory().transport, sources=(ESPN,))
    assert made.status == "failed" and made.error.startswith("blocked:")
    assert (
        run.run_news(
            session,
            now=RECORDED_AT + timedelta(hours=2),
            resolver=dns,
            transport=web_factory().transport,
            sources=(ESPN,),
        )
        == []
    )


@pytest.mark.parametrize("status", [500, 503])
def test_a_server_error_fails_the_run_but_is_not_a_block_and_retries_next_window(session, status):
    web = web_for(ESPN, b"", **{(ESPN.host, "/espn/rss/nfl/news"): httpx.Response(status)})
    (made,) = go(session, web, sources=(ESPN,))
    assert made.status == "failed" and not made.error.startswith("blocked:")
    assert go(session, web, now=RECORDED_AT + timedelta(minutes=10), sources=(ESPN,)) == []
    (retry,) = go(session, web, now=RECORDED_AT + timedelta(minutes=31), sources=(ESPN,))
    assert retry.status == "failed"


def test_one_failing_source_never_stops_the_other_or_touches_old_rows(session):
    names = seed_names(session)
    store.store_items(session, "espn", make_items("Yesterday's story"), names, RECORDED_AT - timedelta(hours=20))

    def timeout(request):
        raise httpx.ReadTimeout("slow")

    good = web_for(CBS, feed_xml(item(title="Bills win", link="https://www.cbssports.com/a")))
    web = Web(
        {
            **good.routes,
            (ESPN.host, "/robots.txt"): httpx.Response(200, headers=TEXT, content=b""),
            (ESPN.host, "/espn/rss/nfl/news"): timeout,
        }
    )
    made = go(session, web)
    assert {r.source: r.status for r in made} == {"espn": "failed", "cbs": "ok"}
    assert sorted(r.source for r in rows(session)) == ["cbs", "espn"]  # yesterday's espn row is still there


def test_a_page_that_is_not_a_feed_fails_the_run_and_keeps_old_data(session):
    names = seed_names(session)
    store.store_items(session, "espn", make_items("Old"), names, RECORDED_AT - timedelta(hours=5))
    web = web_for(ESPN, b"<html><body>Please enable JavaScript</body></html>")
    (made,) = go(session, web, sources=(ESPN,))
    assert made.status == "failed" and not made.error.startswith("blocked:") and len(rows(session)) == 1


def test_pruning_runs_after_a_good_poll_only(session):
    names = seed_names(session)
    old = [
        parse.Item(
            title="ancient",
            url="https://www.espn.com/ancient",
            published_at=RECORDED_AT - timedelta(days=45),
            extract="",
        )
    ]
    store.store_items(session, "espn", old, names, RECORDED_AT - timedelta(days=45))
    bad = web_for(ESPN, b"", **{(ESPN.host, "/espn/rss/nfl/news"): httpx.Response(500)})
    go(session, bad, sources=(ESPN,))
    assert len(rows(session)) == 1
    go(session, web_for(ESPN, feed_xml(item())), now=RECORDED_AT + timedelta(minutes=31), sources=(ESPN,))
    assert [r.title for r in rows(session)] == ["Bills win"]


def test_with_every_source_down_the_poll_returns_failed_runs_and_never_raises(session):
    def down(request):
        raise httpx.ConnectError("no network")

    made = run.run_news(session, now=RECORDED_AT, resolver=public_dns, transport=httpx.MockTransport(down))
    assert [r.status for r in made] == ["failed", "failed"] and rows(session) == []


def test_a_bad_dns_answer_for_one_source_does_not_stop_the_other(session):
    web = real_web()

    def dns(host):
        if host == ESPN.host:
            raise socket.gaierror("no such host")
        return [PUBLIC_IP]

    made = run.run_news(session, now=RECORDED_AT, resolver=dns, transport=web.transport)
    assert {r.source: r.status for r in made} == {"espn": "failed", "cbs": "ok"}
