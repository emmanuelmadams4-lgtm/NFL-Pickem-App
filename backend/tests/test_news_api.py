"""Step 8g (server side): GET /api/news, the latest news for one game.

Clauses R1 to R9 are frozen in docs/gauntlet/logs/step-8g-server.md section 2b.
News text is untrusted input: every test that seeds a hostile string checks what comes back.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from nflpi.api.main import app
from nflpi.models import IngestionRun, NewsItem
from tests.test_live import seed_game

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
GAME = "2026_05_BUF_MIA"
ITEM_KEYS = {"title", "source", "published_at", "url", "tags"}
_counter = [0]


@pytest.fixture
def game(session):
    return seed_game(session, "BUF", "MIA", NOW + timedelta(days=2), game_id=GAME, status="scheduled")


def news(
    session, title="Bills win", teams=("BUF",), *, source="espn", url=None, published="auto", fetched=None, tags=()
):
    _counter[0] += 1
    n = _counter[0]
    if published == "auto":
        published = NOW - timedelta(minutes=n)
    row = NewsItem(
        source=source,
        title=title,
        title_sha256=hashlib.sha256(f"{title}{n}".encode()).hexdigest(),
        url_canonical=url if url is not None else f"https://www.espn.com/nfl/story/_/id/{n}",
        published_at=published,
        fetched_at=fetched or NOW,
        extract="x",
        team_ids=list(teams),
        player_ids=[],
        tags=list(tags),
    )
    session.add(row)
    session.commit()
    return row


def get(client, game_id=GAME):
    return client.get("/api/news", params={"game_id": game_id})


def items(client, game_id=GAME) -> list[dict]:
    response = get(client, game_id)
    assert response.status_code == 200, response.text
    return response.json()["items"]


# ---------------------------------------------------------------- R1


def test_r1_the_route_needs_the_token(session, game):
    news(session)
    bare = TestClient(app)
    for headers in ({}, {"Authorization": "Bearer wrong"}, {"Authorization": ""}):
        response = bare.get("/api/news", params={"game_id": GAME}, headers=headers)
        assert response.status_code == 401 and "items" not in response.json()
    ok = bare.get("/api/news", params={"game_id": GAME}, headers={"Authorization": "Bearer test-token"})
    assert ok.status_code == 200


def test_r1_a_bad_game_id_without_a_token_is_still_401_not_422():
    assert TestClient(app).get("/api/news", params={"game_id": "a b"}).status_code == 401


# ---------------------------------------------------------------- R2


def test_r2_the_reply_has_exactly_the_frozen_keys(session, game, client):
    news(session, "Bills win", ("BUF",), tags=("injury",))
    body = get(client).json()
    assert set(body) == {"game_id", "items"} and body["game_id"] == GAME
    (one,) = body["items"]
    assert set(one) == ITEM_KEYS
    assert one["title"] == "Bills win" and one["source"] == "ESPN" and one["tags"] == ["injury"]
    assert one["url"].startswith("https://www.espn.com/nfl/story/")
    assert datetime.fromisoformat(one["published_at"]).utcoffset() is not None


def test_r2_the_source_is_the_display_name_for_each_feed(session, game, client):
    news(session, "from espn", source="espn")
    news(session, "from cbs", source="cbs", url="https://www.cbssports.com/nfl/news/x/")
    assert {i["title"]: i["source"] for i in items(client)} == {"from espn": "ESPN", "from cbs": "CBS Sports"}


def test_r2_a_missing_date_stays_null_and_is_never_invented(session, game, client):
    news(session, "undated", published=None)
    assert items(client)[0]["published_at"] is None


def test_r2_only_the_four_known_tags_come_back_sorted(session, game, client):
    news(session, tags=("trade", "<b>", "x" * 500, "injury", "coach", "playcaller", "other"))
    assert items(client)[0]["tags"] == ["coach", "injury", "playcaller", "trade"]


# ---------------------------------------------------------------- R3


def test_r3_items_for_either_team_of_the_game_come_back_and_no_others(session, game, client):
    news(session, "home only", ("MIA",))
    news(session, "away only", ("BUF",))
    news(session, "both", ("MIA", "BUF"))
    news(session, "neither", [])
    news(session, "other teams", ("NYJ", "NE"))
    news(session, "other plus home", ("NYJ", "MIA"))
    assert {i["title"] for i in items(client)} == {"home only", "away only", "both", "other plus home"}


def test_r3_a_team_name_inside_another_abbreviation_does_not_match(session, game, client):
    news(session, "substring", ("BUFF", "MIAMI", "XBUF"))
    assert items(client) == []


def test_r3_items_from_a_source_that_is_not_in_the_allowlist_are_not_returned(session, game, client):
    news(session, "from nowhere", source="evil", url="https://www.espn.com/x")
    news(session, "from espn", source="espn")
    assert [i["title"] for i in items(client)] == ["from espn"]


# ---------------------------------------------------------------- R4


def test_r4_at_most_five_newest_first(session, game, client):
    for k in range(8):
        news(session, f"item {k}", published=NOW - timedelta(hours=k))
    assert [i["title"] for i in items(client)] == [f"item {k}" for k in range(5)]


def test_r4_items_of_other_teams_never_use_up_the_five_places(session, game, client):
    for k in range(6):
        news(session, f"other {k}", ("NYJ",), published=NOW - timedelta(minutes=k))
    for k in range(5):
        news(session, f"ours {k}", ("MIA",), published=NOW - timedelta(days=1 + k))
    assert [i["title"] for i in items(client)] == [f"ours {k}" for k in range(5)]


def test_r4_undated_items_come_after_every_dated_one_then_by_our_fetch_time(session, game, client):
    news(session, "undated old", published=None, fetched=NOW - timedelta(hours=5))
    news(session, "undated new", published=None, fetched=NOW - timedelta(hours=1))
    news(session, "dated a", published=NOW - timedelta(days=3))
    news(session, "dated b", published=NOW - timedelta(days=9))
    assert [i["title"] for i in items(client)] == ["dated a", "dated b", "undated new", "undated old"]


def test_r4_a_tie_is_broken_by_fetch_time_then_by_the_higher_id(session, game, client):
    same = NOW - timedelta(hours=1)
    news(session, "first stored", published=same, fetched=NOW - timedelta(minutes=9))
    news(session, "fetched later", published=same, fetched=NOW - timedelta(minutes=2))
    news(session, "stored last", published=same, fetched=NOW - timedelta(minutes=9))
    assert [i["title"] for i in items(client)] == ["fetched later", "stored last", "first stored"]


def test_r4_no_news_is_a_normal_empty_reply(session, game, client):
    response = get(client)
    assert response.status_code == 200 and response.json() == {"game_id": GAME, "items": []}


# ---------------------------------------------------------------- R5


def test_r5_an_unknown_game_is_404_with_a_fixed_message(session, client):
    response = get(client, "2026_99_XXX_YYY")
    assert response.status_code == 404 and response.json() == {"detail": "Game not found"}


@pytest.mark.parametrize("bad", ["", "x" * 33, "a b", "a;b", "../x", "é", "a'b", "<b>", "a\nb", "2026_05_BUF_MIA\n"])
def test_r5_a_malformed_game_id_is_422_and_is_not_echoed(session, client, bad):
    response = get(client, bad)
    assert response.status_code == 422
    assert bad.strip() == "" or bad not in response.text


def test_r5_the_422_is_a_fixed_message_without_the_value(session, client):
    for bad in ("<script>alert(1)</script>", "x" * 40, "ok\n"):
        response = get(client, bad)
        assert response.status_code == 422
        assert response.json() == {"detail": "game_id must be 1 to 32 letters, digits, - or _"}


def test_r5_a_missing_game_id_is_the_same_fixed_422(client):
    response = client.get("/api/news")
    assert response.status_code == 422 and response.json() == {
        "detail": "game_id must be 1 to 32 letters, digits, - or _"
    }


def test_r5_a_game_id_of_exactly_thirty_two_characters_is_accepted(session, client):
    seed_game(session, "BUF", "MIA", NOW, game_id="2026_05_" + "A" * 24, status="scheduled")
    assert get(client, "2026_05_" + "A" * 24).status_code == 200


# ---------------------------------------------------------------- R6


@pytest.mark.parametrize(
    "hostile",
    [
        "<b>Hi</b> there <script>alert(1)</script>",
        "Bears > Lions & <3 <img src=x onerror=alert(1)>",
        "double &lt;script&gt; encoded",
        "&lt;script&gt;x&lt;/script&gt;",
        "&#60;img src=x onerror=1&#62; and &amp;lt;b&amp;gt;",
        "&#x3c;script&#x3e;x",
        "tag<​script>x</script>",
        "ok‮evil\x1b\x07 text",
    ],
)
def test_r6_no_markup_characters_or_control_characters_come_back(session, game, client, hostile):
    news(session, hostile)
    (one,) = items(client)
    assert one["title"]
    for text in (one["title"], one["source"], *one["tags"]):
        assert "<" not in text and ">" not in text
        assert not any(ord(c) < 32 or c in "‮​" for c in text)


def test_r6_the_title_is_cut_at_two_hundred_and_whitespace_is_collapsed(session, game, client):
    news(session, "  Word   " + "w" * 191)
    (one,) = items(client)
    assert len(one["title"]) <= 200 and "  " not in one["title"] and one["title"] == one["title"].strip()


def test_r6_the_reply_is_json_not_html(session, game, client):
    news(session, "<script>alert(1)</script>")
    response = get(client)
    assert response.headers["content-type"].startswith("application/json")
    assert "<script" not in response.text


# ---------------------------------------------------------------- R7

GOOD = "https://www.espn.com/nfl/story/_/id/9"


@pytest.mark.parametrize(
    "stored",
    [
        "http://www.espn.com/nfl/story/_/id/9",
        "https://evil.example/nfl",
        "https://espn.com.evil.example/nfl",
        "https://evilespn.com/nfl",
        "https://www.espn.com@evil.example/nfl",
        "https://user:pw@www.espn.com/nfl",
        "https://www.espn.com:8443/nfl",
        "https://www.espn.com\\@evil.example/nfl",
        "https://www.espn.com./nfl",
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "//www.espn.com/nfl",
        "https://www.espn.com/a b",
        "https://www.espn.com/a\x07b",
        "",
        "https://www.cbssports.com/nfl/news/x/",  # another allowlisted host, but not this item's own source
    ],
)
def test_r7_an_unsafe_link_comes_back_null_but_the_item_still_does(session, game, client, stored):
    news(session, "kept anyway", url=stored)
    (one,) = items(client)
    assert one["title"] == "kept anyway" and one["url"] is None


def test_r7_a_safe_link_comes_back_canonical_without_trackers_or_fragment(session, game, client):
    news(session, "good", url=GOOD + "?utm_source=x&id=2#frag")
    assert items(client)[0]["url"] == GOOD + "?id=2"


def test_r7_a_subdomain_of_the_items_own_host_is_fine_and_an_exact_host_too(session, game, client):
    news(session, "sub", url="https://a.b.espn.com/x")
    news(session, "bare", url="https://espn.com/y")
    assert {i["title"]: i["url"] for i in items(client)} == {"sub": "https://a.b.espn.com/x", "bare": "https://espn.com/y"}


# ---------------------------------------------------------------- R8, R9


def test_r8_the_route_writes_nothing_and_makes_no_network_call(session, game, client, monkeypatch):
    news(session)

    def boom(*a, **k):
        raise AssertionError("no network from /api/news")

    monkeypatch.setattr(httpx.Client, "send", boom)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", boom)
    rows = lambda: (  # noqa: E731
        session.scalar(select(func.count()).select_from(NewsItem)),
        session.scalar(select(func.count()).select_from(IngestionRun)),
    )
    before = rows()
    assert get(client).status_code == 200
    session.expire_all()
    assert rows() == before


def test_r8_only_get_is_allowed(client):
    for verb in ("post", "put", "delete", "patch"):
        assert getattr(client, verb)("/api/news", params={"game_id": GAME}).status_code == 405


def test_r9_the_contract_names_the_route_and_its_reply_models():
    spec = app.openapi()
    op = spec["paths"]["/api/news"]["get"]
    assert op["responses"]["200"]["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/NewsOut"}
    schemas = spec["components"]["schemas"]
    assert set(schemas["NewsOut"]["properties"]) == {"game_id", "items"}
    assert set(schemas["NewsItemOut"]["properties"]) == ITEM_KEYS
    assert json.dumps(spec).count("/api/news") == 1
