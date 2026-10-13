"""Step 16b (server): the group routes, through the real app. Every member name here is made up.

Criterion ids (R.., U.., S.., T..) are the frozen list in docs/gauntlet/logs/step-16b-server.md section 2.
"""

import logging
from datetime import UTC, datetime

import pytest
from sqlalchemy import event, select

from nflpi.api import group as group_api
from nflpi.db import get_engine
from nflpi.group import importer
from nflpi.models import Game, GroupPick, GroupStanding

SEASON = 2023
HEADER = "Week,Team,Game,Favored,Spread,Underdog,Pick,Side,Confidence,Week_Total_Pts"
NAMES = ("Ann A", "Bo's Picks", "Cy!!")
# (season, week, away, home). Week 1 has three games; the 2022 game and the week 2 game must never show up.
GAMES = [(2023, 1, "MIA", "BUF"), (2023, 1, "NYJ", "NE"), (2023, 1, "LV", "KC"), (2023, 2, "KC", "LA"),
         (2022, 1, "MIA", "BUF")]
PICK_ROWS = [  # hand counts in the S tests below
    "1,Ann A,1,Buf,3.5,Mia,Buf,Favorite,3,5",
    "1,Ann A,2,NE,1.5,NYJ,NYJ,Underdog,1,5",
    "1,Bo's Picks,1,Buf,3.5,Mia,Mia,Underdog,1,0",
    "1,Bo's Picks,2,NE,1.5,NYJ,,none,,0",
    "1,Cy!!,1,Buf,3.5,Mia,Buf,Favorite,2,7",
    "1,Cy!!,2,NE,1.5,NYJ,NYJ,Underdog,3,7",
]
PICKS = ("\r\n".join([HEADER, *PICK_ROWS, ""])).encode()
STANDINGS = b"Rank,Team,Wk1,Wk2,Total_Pts\r\n1,Ann A,6,3,9\r\n2,Bo's Picks,5,3,8\r\n3,Cy!!,2,1,3\r\n"
WEEK1_STANDINGS = b"Rank,Team,Wk1,Total_Pts\r\n1,Ann A,6,6\r\n2,Bo's Picks,5,5\r\n3,Cy!!,2,2\r\n"


@pytest.fixture
def games(session):
    for index, (season, week, away, home) in enumerate(GAMES):  # earlier in the list kicks off later
        session.add(Game(game_id=f"{season}_{week:02d}_{away}_{home}", season=season, week=week, game_type="REG",
                         kickoff_utc=datetime(season, 9, 10 + week, 20 - index, tzinfo=UTC), weekday="Sunday",
                         away_team=away, home_team=home, status="final", source="test"))
    session.commit()
    return session


def upload(client, data=PICKS, season=SEASON, **kwargs):
    return client.post(f"/api/group/import?season={season}", content=data, **kwargs)


def stored(session):
    session.expire_all()
    picks = {(p.game_id, p.member): (p.picked_team, p.confidence) for p in session.scalars(select(GroupPick))}
    points = {(s.season, s.week, s.member): (s.points, s.rank) for s in session.scalars(select(GroupStanding))}
    return picks, points


# ---------------------------------------------------------------- R: access
ROUTES = [("post", "/api/group/import?season=2023"), ("get", "/api/group/standings?season=2023&week=1"),
          ("get", "/api/group/shares?season=2023&week=1")]


@pytest.mark.parametrize(("method", "path"), ROUTES)
@pytest.mark.parametrize("auth", [None, "Bearer wrong", "Basic test-token"])
def test_r1_every_route_needs_the_token(client, method, path, auth):
    client.headers.pop("Authorization")
    if auth:
        client.headers["Authorization"] = auth
    assert getattr(client, method)(path).status_code == 401


def test_r1_an_unauthorised_upload_is_never_read(client, games, monkeypatch):
    monkeypatch.setattr(group_api, "import_group_csv", lambda *a: pytest.fail("importer called without a token"))
    client.headers.pop("Authorization")
    assert upload(client).status_code == 401
    assert stored(games) == ({}, {})


# ---------------------------------------------------------------- U: upload
def test_u1_a_picks_file_is_stored_and_counted(client, games):
    reply = upload(client)
    assert reply.status_code == 200
    assert reply.json() == {"season": SEASON, "kind": "picks", "rows": 6}
    picks, _ = stored(games)
    assert picks[("2023_01_MIA_BUF", "Ann A")] == ("BUF", 3)
    assert picks[("2023_01_NYJ_NE", "Bo's Picks")] == (None, None)
    assert len(picks) == 6


def test_u2_a_weekly_file_is_stored_and_counted(client, games):
    reply = upload(client, STANDINGS)
    assert reply.status_code == 200
    assert reply.json() == {"season": SEASON, "kind": "standings", "rows": 6}
    _, points = stored(games)
    assert points[(SEASON, 2, "Ann A")] == (3, 1)  # rank only on the file's last week
    assert points[(SEASON, 1, "Ann A")] == (6, None)


def test_u3_the_same_file_twice_changes_nothing(client, games):
    for data in (PICKS, STANDINGS):
        first = upload(client, data)
        before = stored(games)
        second = upload(client, data)
        assert second.status_code == 200
        assert second.json() == first.json()
        assert stored(games) == before


def test_u4_the_file_is_taken_as_raw_bytes_whatever_its_content_type(client, games):
    for content_type in ("text/csv", "application/octet-stream", "multipart/form-data"):
        assert upload(client, headers={"Content-Type": content_type}).status_code == 200


def test_u5_a_file_over_the_cap_is_refused_413_before_it_is_read(client, games, monkeypatch):
    monkeypatch.setattr(group_api, "import_group_csv", lambda *a: pytest.fail("importer called on a big file"))
    reply = upload(client, b"x" * (importer.MAX_BYTES + 1))
    assert reply.status_code == 413
    assert reply.json() == {"detail": "file is too large"}
    assert stored(games) == ({}, {})


def test_u5_the_cap_holds_without_a_content_length(client, games, monkeypatch):
    monkeypatch.setattr(group_api, "import_group_csv", lambda *a: pytest.fail("importer called on a big file"))

    def chunks():
        for _ in range(11):
            yield b"x" * 100_000

    reply = upload(client, chunks())  # a generator is sent chunked: no Content-Length header
    assert reply.status_code == 413


def test_u5_the_cap_is_read_from_the_importer_at_request_time(client, games, monkeypatch):
    monkeypatch.setattr(importer, "MAX_BYTES", len(PICKS) - 1)
    assert upload(client).status_code == 413
    monkeypatch.setattr(importer, "MAX_BYTES", len(PICKS))
    assert upload(client).status_code == 200  # exactly the cap is allowed


def test_u6_a_bad_file_is_422_with_the_importers_own_message_and_writes_nothing(client, games):
    bad = PICKS.replace(b"Favorite,3,5", b"Sideways,3,5")
    with pytest.raises(importer.GroupImportError) as expected:
        importer.import_group_csv(games, SEASON, bad)
    games.rollback()
    reply = upload(client, bad)
    assert reply.status_code == 422
    assert reply.json() == {"detail": str(expected.value)}
    assert reply.json()["detail"].startswith("line 2: ")
    assert not any(name in reply.text for name in NAMES)
    assert stored(games) == ({}, {})


@pytest.mark.parametrize("data", [b"", b"\xff\xfe\x00", b"not,a,group,file\r\n1,2,3,4\r\n", HEADER.encode()])
def test_u6_empty_binary_unknown_and_headers_only_files_are_422(client, games, data):
    reply = upload(client, data)
    assert reply.status_code == 422
    assert isinstance(reply.json()["detail"], str)


@pytest.mark.parametrize("season", ["", "abc", "1999", "2101", "2023.5", "-2023"])
def test_u7_the_season_must_be_a_year_between_2000_and_2100(client, games, season):
    assert upload(client, season=season).status_code == 422
    assert stored(games) == ({}, {})


def test_u7_a_422_never_echoes_the_file(client, games):
    for path in ("/api/group/import?season=abc", "/api/group/import"):
        reply = client.post(path, content=PICKS)
        assert reply.status_code == 422
        assert not any(name in reply.text for name in NAMES)


def test_u7_a_missing_season_is_422(client, games):
    assert client.post("/api/group/import", content=PICKS).status_code == 422


def test_u8_a_database_failure_is_500_and_leaks_nothing(client, games, monkeypatch):
    def broken(*args):
        raise RuntimeError("group import: database error (OperationalError)")

    monkeypatch.setattr(group_api, "import_group_csv", broken)
    reply = upload(client)
    assert reply.status_code == 500
    assert reply.json() == {"detail": "group import failed: database error"}


def test_u9_no_member_name_reaches_the_log(client, games, caplog):
    with caplog.at_level(logging.DEBUG):
        upload(client)
        upload(client, PICKS.replace(b"Favorite,3,5", b"Sideways,3,5"))
        client.get(f"/api/group/shares?season={SEASON}&week=1")
        client.get(f"/api/group/standings?season={SEASON}&week=1")
    assert not any(name in caplog.text for name in NAMES)


# ---------------------------------------------------------------- S: shares
def test_s1_shares_per_game_counted_by_hand(client, games):
    upload(client)
    reply = client.get(f"/api/group/shares?season={SEASON}&week=1")
    assert reply.status_code == 200
    body = reply.json()
    assert body["season"] == SEASON and body["week"] == 1
    by_id = {g["game_id"]: g for g in body["games"]}
    assert set(by_id) == {"2023_01_MIA_BUF", "2023_01_NYJ_NE", "2023_01_LV_KC"}  # no other week, no other season
    one = by_id["2023_01_MIA_BUF"]  # Ann BUF 3, Bo MIA 1, Cy BUF 2
    assert (one["away_team"], one["home_team"], one["members"], one["picked"]) == ("MIA", "BUF", 3, 3)
    assert one["away"] == {"team": "MIA", "picks": 1, "share": 1 / 3, "avg_confidence": 1.0}
    assert one["home"] == {"team": "BUF", "picks": 2, "share": 2 / 3, "avg_confidence": 2.5}
    two = by_id["2023_01_NYJ_NE"]  # Ann NYJ 1, Bo no pick, Cy NYJ 3
    assert (two["members"], two["picked"]) == (3, 2)
    assert two["away"] == {"team": "NYJ", "picks": 2, "share": 1.0, "avg_confidence": 2.0}
    assert two["home"] == {"team": "NE", "picks": 0, "share": 0.0, "avg_confidence": None}


def test_s2_a_game_nobody_picked_is_there_with_missing_not_zero(client, games):
    upload(client)
    three = {g["game_id"]: g for g in client.get(f"/api/group/shares?season={SEASON}&week=1").json()["games"]}[
        "2023_01_LV_KC"]
    assert (three["members"], three["picked"]) == (0, 0)
    for side in ("away", "home"):
        assert three[side]["picks"] == 0 and three[side]["share"] is None and three[side]["avg_confidence"] is None


def test_s3_games_are_in_kickoff_order_with_the_kickoff_shown(client, games):
    body = client.get(f"/api/group/shares?season={SEASON}&week=1").json()
    assert [g["game_id"] for g in body["games"]] == ["2023_01_LV_KC", "2023_01_NYJ_NE", "2023_01_MIA_BUF"]
    assert [g["kickoff_utc"] for g in body["games"]] == [
        "2023-09-11T18:00:00Z", "2023-09-11T19:00:00Z", "2023-09-11T20:00:00Z"]


def test_s4_a_week_with_no_games_is_an_empty_list_and_bounds_are_checked(client, games):
    assert client.get(f"/api/group/shares?season={SEASON}&week=9").json() == {"season": SEASON, "week": 9, "games": []}
    for query in ("season=2023&week=0", "season=2023&week=23", "season=1999&week=1", "week=1", "season=2023",
                  "season=x&week=1"):
        assert client.get(f"/api/group/shares?{query}").status_code == 422


def test_s5_the_spread_and_the_favoured_side_are_never_used(client, games):
    upload(client)
    first = client.get(f"/api/group/shares?season={SEASON}&week=1").json()
    swapped = PICKS.replace(b"Buf,3.5,Mia,Buf,Favorite", b"Mia,9.5,Buf,Buf,Underdog")
    assert swapped != PICKS
    assert upload(client, swapped).status_code == 200
    assert client.get(f"/api/group/shares?season={SEASON}&week=1").json() == first


def test_s6_the_number_of_queries_does_not_grow_with_the_number_of_games(client, games):
    upload(client)
    counts = []
    for week_query in ("week=1", "week=2"):  # week 1 has three games, week 2 has one
        seen = []

        def count(conn, cursor, statement, *args, seen=seen):
            seen.append(statement)

        event.listen(get_engine(), "before_cursor_execute", count)
        try:
            assert client.get(f"/api/group/shares?season={SEASON}&{week_query}").status_code == 200
        finally:
            event.remove(get_engine(), "before_cursor_execute", count)
        counts.append(len(seen))
    assert counts[0] == counts[1] <= 3


# ---------------------------------------------------------------- T: standings
def test_t1_standings_for_a_week_with_running_totals(client, games):
    upload(client, STANDINGS)
    body = client.get(f"/api/group/standings?season={SEASON}&week=2").json()
    assert body == {"season": SEASON, "week": 2, "rows": [
        {"member": "Ann A", "points": 3, "total": 9, "rank": 1},
        {"member": "Bo's Picks", "points": 3, "total": 8, "rank": 2},
        {"member": "Cy!!", "points": 1, "total": 3, "rank": 3}]}
    first = client.get(f"/api/group/standings?season={SEASON}&week=1").json()
    assert [(r["member"], r["points"], r["total"], r["rank"]) for r in first["rows"]] == [
        ("Ann A", 6, 6, None), ("Bo's Picks", 5, 5, None), ("Cy!!", 2, 2, None)]  # no rank from a later file's week 1


def test_t2_a_later_file_adds_the_rank_it_owns_and_keeps_the_rest(client, games):
    upload(client, STANDINGS)
    upload(client, WEEK1_STANDINGS)  # ends at week 1: sets week 1 ranks, leaves week 2 alone
    one = client.get(f"/api/group/standings?season={SEASON}&week=1").json()["rows"]
    assert [r["rank"] for r in one] == [1, 2, 3]
    two = client.get(f"/api/group/standings?season={SEASON}&week=2").json()["rows"]
    assert [r["rank"] for r in two] == [1, 2, 3]


def test_t3_no_rows_is_an_empty_list_other_seasons_are_apart_and_bounds_are_checked(client, games):
    upload(client, STANDINGS)
    assert client.get("/api/group/standings?season=2022&week=1").json() == {"season": 2022, "week": 1, "rows": []}
    for query in ("season=2023&week=0", "season=2023&week=23", "season=2101&week=1", "week=1", "season=2023",
                  "season=2023&week=x"):
        assert client.get(f"/api/group/standings?{query}").status_code == 422
