"""Step 16a: the owner's Yahoo group files (picks and weekly points), checked on the way in, and two questions.

Every member name here is made up. The two fixture files in tests/fixtures/group show the two shapes the owner
exports. Expected numbers are counted by hand in the comments. Criterion numbers (P.., N.., W.., Q..) are the
frozen list in docs/gauntlet/logs/step-16a.md section 2.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from nflpi.group import importer
from nflpi.group.importer import GroupImportError, import_group_csv
from nflpi.group.queries import game_shares, standings
from nflpi.models import Game, GroupPick, GroupStanding

FIXTURES = Path(__file__).parent / "fixtures" / "group"
PICKS = (FIXTURES / "picks_ok.csv").read_bytes()
STANDINGS = (FIXTURES / "standings_ok.csv").read_bytes()
SEASON = 2023
HEADER = "Week,Team,Game,Favored,Spread,Underdog,Pick,Side,Confidence,Week_Total_Pts"
ROW = "1,Ann A,1,Buf,3.5,Mia,Buf,Favorite,3,5"  # line 2 of picks_ok.csv
DEE = "Dee ’Q’"
# (season, week, away, home). The 2022 game makes sure another season is never matched.
GAMES = [(2023, 1, "MIA", "BUF"), (2023, 1, "NYJ", "NE"), (2023, 1, "LV", "KC"), (2023, 2, "KC", "LA"),
         (2023, 2, "BUF", "NE"), (2022, 3, "LV", "MIA")]


@pytest.fixture
def games(session):
    for season, week, away, home in GAMES:
        session.add(Game(game_id=f"{season}_{week:02d}_{away}_{home}", season=season, week=week, game_type="REG",
                         kickoff_utc=datetime(season, 9, 10, 17, tzinfo=UTC), weekday="Sunday", away_team=away,
                         home_team=home, status="final", source="test"))
    session.commit()
    return session


def picks(*rows: str, header: str = HEADER) -> bytes:
    return "\r\n".join([header, *rows, ""]).encode()


def edit(old: str, new: str, data: bytes = PICKS) -> bytes:
    assert old.encode() in data
    return data.replace(old.encode(), new.encode(), 1)


def stored_picks(session) -> dict:
    session.expire_all()
    return {(p.game_id, p.member): (p.picked_team, p.confidence) for p in session.scalars(select(GroupPick))}


def stored_standings(session) -> dict:
    session.expire_all()
    return {(s.season, s.week, s.member): (s.points, s.rank) for s in session.scalars(select(GroupStanding))}


def refused(session, data: bytes, match: str) -> str:
    """The file is refused with a message that matches, and nothing at all is written."""
    before = stored_picks(session), stored_standings(session)
    with pytest.raises(GroupImportError, match=match) as err:
        import_group_csv(session, SEASON, data)
    session.rollback()
    assert (stored_picks(session), stored_standings(session)) == before
    return str(err.value)


# Picks file -----------------------------------------------------------------------------------------------------


def test_p1_picks_file_stores_one_row_per_member_and_game(games):
    result = import_group_csv(games, SEASON, PICKS)
    assert (result.kind, result.rows) == ("picks", 20)
    rows = stored_picks(games)
    assert len(rows) == 20
    assert rows[("2023_01_MIA_BUF", "Ann A")] == ("BUF", 3)
    assert rows[("2023_01_NYJ_NE", "Ann A")] == ("NYJ", 1)  # an underdog pick stores the underdog's code
    assert rows[("2023_01_LV_KC", "Bo's Picks")] == ("KC", 1)
    assert rows[("2023_02_BUF_NE", "Cy!!")] == ("BUF", 2)
    assert all(game.startswith("2023_") for game, _ in rows)


def test_p2_yahoo_codes_map_to_app_codes_any_case_and_lar_is_la(games):
    import_group_csv(games, SEASON, PICKS)
    rows = stored_picks(games)
    assert rows[("2023_02_KC_LA", "Ann A")] == ("LA", 2)  # file says LAR; the app's code is LA
    assert rows[("2023_01_MIA_BUF", "Cy!!")] == ("MIA", 1)  # file says Mia
    games.execute(GroupPick.__table__.delete())
    games.commit()
    import_group_csv(games, SEASON, picks("1,Ann A,1,bUF,3.5,mia,BUF,Favorite,3,5"))
    assert stored_picks(games) == {("2023_01_MIA_BUF", "Ann A"): ("BUF", 3)}


def test_p3_a_row_with_no_pick_is_stored_as_missing(games):
    import_group_csv(games, SEASON, PICKS)
    rows = stored_picks(games)
    assert rows[("2023_01_MIA_BUF", DEE)] == (None, None)
    assert rows[("2023_02_KC_LA", "Cy!!")] == (None, None)


@pytest.mark.parametrize(("old", "new"), [
    ("1,Ann A,1,Buf,3.5,Mia,Buf", "1,Ann A,1,Buf,3.5,Dal,Buf"),  # no such matchup that week
    ("1,Ann A,1,Buf,3.5,Mia,Buf", "1,Ann A,1,Xyz,3.5,Mia,Mia"),  # not a team
    ("1,Ann A,1,Buf,3.5,Mia,Buf", "1,Ann A,1,Buf,3.5,Buf,Buf"),  # one team twice
    ("2,Ann A,2,Buf,10.0,NE,Buf", "1,Ann A,2,Buf,10.0,NE,Buf"),  # right matchup, wrong week
    ("1,Ann A,1,Buf,3.5,Mia,Buf", "1,Ann A,1, Buf,3.5,Mia,Buf"),  # codes are not trimmed
])
def test_p4_a_matchup_that_is_not_one_game_of_that_week_is_refused(games, old, new):
    assert refused(games, edit(old, new), "no game").startswith("line ")


def test_p4_games_of_another_season_never_match(games):
    row = "3,Ann A,1,Mia,3.5,LV,Mia,Favorite,3,5"  # LV at MIA is week 3 of 2022, not of 2023
    refused(games, picks(row), "line 2: .*no game")
    assert import_group_csv(games, 2022, picks(row)).rows == 1
    assert stored_picks(games) == {("2022_03_LV_MIA", "Ann A"): ("MIA", 3)}


@pytest.mark.parametrize(("old", "new", "match"), [
    ("Buf,Favorite,3", "Mia,Favorite,3", "pick"),  # Favorite but the pick is the underdog
    ("NYJ,Underdog,1", "NE,Underdog,1", "pick"),  # Underdog but the pick is the favorite
    ("Buf,Favorite,3", "KC,Favorite,3", "pick"),  # a team that is not in the game
    ("Buf,Favorite,3", "Buf,favorite,3", "side"),  # the three words are exact
    ("Buf,Favorite,3", "Buf,,3", "side"),
    ("Mia,,none,,5", "Mia,Buf,none,,5", "pick"),  # none with a pick
    ("Mia,,none,,5", "Mia,,none,2,5", "confidence"),  # none with a confidence
    ("Buf,Favorite,3", ",Favorite,3", "pick"),  # a side with no pick
    ("Buf,Favorite,3", "Buf,Favorite,", "confidence"),  # a pick with no confidence
])
def test_p5_pick_side_and_confidence_must_agree(games, old, new, match):
    refused(games, edit(old, new), match)


@pytest.mark.parametrize(("old", "new", "match"), [
    ("1,Ann A,1,Buf", "0,Ann A,1,Buf", "week"),
    ("1,Ann A,1,Buf", "23,Ann A,1,Buf", "week"),
    ("1,Ann A,1,Buf", "1,Ann A,0,Buf", "game"),
    ("1,Ann A,1,Buf", "1,Ann A,17,Buf", "game"),
    ("Buf,Favorite,3,5", "Buf,Favorite,0,5", "confidence"),
    ("Buf,Favorite,3,5", "Buf,Favorite,17,5", "confidence"),
    ("Buf,Favorite,3,5", "Buf,Favorite,3,137", "total"),
    ("Buf,3.5,Mia,Buf", "Buf,100,Mia,Buf", "spread"),
    ("Buf,3.5,Mia,Buf", "Buf,-3.5,Mia,Buf", "spread"),
    ("Buf,3.5,Mia,Buf", "Buf,3.55,Mia,Buf", "spread"),
    ("Buf,3.5,Mia,Buf", "Buf,3.,Mia,Buf", "spread"),
    ("Buf,3.5,Mia,Buf", "Buf,,Mia,Buf", "spread"),
    ("Buf,3.5,Mia,Buf", "Buf,nan,Mia,Buf", "spread"),
])
def test_p6_numbers_outside_their_bounds_are_refused(games, old, new, match):
    refused(games, edit(old, new), "line 2: .*" + match)


def test_p6_numbers_at_their_bounds_are_accepted(games):
    games.add(Game(game_id="2023_22_MIA_BUF", season=2023, week=22, game_type="SB", weekday="Sunday",
                   kickoff_utc=datetime(2024, 2, 11, 23, tzinfo=UTC), away_team="MIA", home_team="BUF",
                   status="scheduled", source="test"))
    games.commit()
    data = picks("22,Ann A,16,Buf,99.9,Mia,Buf,Favorite,16,136", "22,Cy!!,1,Buf,0,Mia,Mia,Underdog,1,0")
    assert import_group_csv(games, SEASON, data).rows == 2
    assert stored_picks(games) == {("2023_22_MIA_BUF", "Ann A"): ("BUF", 16), ("2023_22_MIA_BUF", "Cy!!"): ("MIA", 1)}


@pytest.mark.parametrize("bad", ["+1", "1.0", "1_0", " 1", "1 ", "١", "", "one", "0x1"])
def test_p7_a_whole_number_is_plain_digits_only(games, bad):
    refused(games, picks(f"{bad},Ann A,1,Buf,3.5,Mia,Buf,Favorite,3,5"), "week")
    refused(games, picks(f"1,Ann A,1,Buf,3.5,Mia,Buf,Favorite,{bad},5"), "confidence")
    refused(games, picks(f"1,Ann A,{bad},Buf,3.5,Mia,Buf,Favorite,3,5"), "game")
    refused(games, picks(f"1,Ann A,1,Buf,3.5,Mia,Buf,Favorite,3,{bad}"), "total")


def test_p8_one_row_per_member_and_game(games):
    message = refused(games, picks(ROW, ROW), "line 3: .*twice")
    assert "confidence" not in message
    # the same member after name cleaning is still the same member
    refused(games, picks(ROW, ROW.replace("Ann A", "Ann​  A")), "line 3: .*twice")


def test_p9_a_member_uses_each_confidence_number_once_a_week(games):
    message = refused(games, edit("1,Ann A,2,NE,1.5,NYJ,NYJ,Underdog,1,5", "1,Ann A,2,NE,1.5,NYJ,NYJ,Underdog,3,5"),
                      "line 3: .*confidence")
    assert "twice" not in message
    # the same number in another week, or for another member, is fine
    import_group_csv(games, SEASON, picks(ROW, "1,Cy!!,1,Buf,3.5,Mia,Buf,Favorite,3,5",
                                          "2,Ann A,2,Buf,10.0,NE,Buf,Favorite,3,3"))
    assert len(stored_picks(games)) == 3


def test_p10_spread_favored_and_underdog_never_change_what_is_stored(games):
    """The group scores straight winners with confidence points: the line and who is favored are context only."""
    import_group_csv(games, SEASON, PICKS)
    first = stored_picks(games)
    games.execute(GroupPick.__table__.delete())
    games.commit()
    flipped = []
    for line in PICKS.decode().splitlines()[1:]:
        week, team, _game, fav, _spread, dog, pick, side, conf, _total = line.split(",")
        side = {"Favorite": "Underdog", "Underdog": "Favorite", "none": "none"}[side]
        flipped.append(",".join([week, team, "16", dog, "13.5", fav, pick, side, conf, "0"]))
    import_group_csv(games, SEASON, picks(*flipped))
    assert stored_picks(games) == first
    assert {c.name for c in GroupPick.__table__.columns} == {"game_id", "member", "picked_team", "confidence",
                                                             "imported_at"}
    assert {c.name for c in GroupStanding.__table__.columns} == {"season", "week", "member", "points", "rank",
                                                                 "imported_at"}


# Untrusted input ------------------------------------------------------------------------------------------------


def test_n1_a_file_over_the_size_cap_is_refused_before_it_is_read(games, monkeypatch):
    assert importer.MAX_BYTES == 1_000_000
    monkeypatch.setattr(importer, "MAX_BYTES", len(PICKS))
    assert import_group_csv(games, SEASON, PICKS).rows == 20  # exactly at the cap is allowed
    monkeypatch.setattr(importer, "MAX_BYTES", len(PICKS) - 1)
    refused(games, PICKS, "too large")
    refused(games, b"\xff" * len(PICKS), "too large")  # the size is checked before the text is decoded


def test_n2_text_that_is_not_utf8_is_refused_and_a_byte_order_mark_is_fine(games):
    refused(games, PICKS.replace(b"Ann A", b"Ann \xff"), "UTF-8")
    assert import_group_csv(games, SEASON, b"\xef\xbb\xbf" + PICKS).rows == 20


@pytest.mark.parametrize("header", [
    HEADER + ",Extra",
    HEADER.replace(",Spread", ""),
    HEADER.replace("Week,Team", "Team,Week"),
    HEADER.lower(),
    HEADER.replace("Team", "Member"),
    "Rank,Team,Total_Pts",
    "Rank,Team,Wk2,Total_Pts",
    "Rank,Team,Wk1,Wk3,Total_Pts",
    "Rank,Team,Wk1,Wk1,Total_Pts",
    "Rank,Team,Wk01,Total_Pts",
    "Rank,Team,Wk1,Total_Pts,Extra",
    "Team,Rank,Wk1,Total_Pts",
    "Rank,Team," + ",".join(f"Wk{i}" for i in range(1, 24)) + ",Total_Pts",
    "",
])
def test_n3_only_the_two_exact_headers_are_accepted(games, header):
    refused(games, picks(ROW, header=header), "columns")


def test_n3_a_weekly_file_may_have_up_to_22_weeks(games):
    header = "Rank,Team," + ",".join(f"Wk{i}" for i in range(1, 23)) + ",Total_Pts"
    assert import_group_csv(games, SEASON, picks("1,Ann A," + "1," * 22 + "22", header=header)).rows == 22


@pytest.mark.parametrize("row", [ROW + ",9", ROW.rsplit(",", 1)[0], ""])
def test_n4_a_row_with_the_wrong_number_of_cells_is_refused_with_its_line(games, row):
    refused(games, picks(ROW.replace("Ann A", "Cy!!"), row), "line 3: .*cells")


def test_n4_a_file_with_no_rows_is_refused(games):
    refused(games, picks(), "no rows")
    refused(games, b"", "columns")
    refused(games, b"Rank,Team,Wk1,Total_Pts\r\n", "no rows")


@pytest.mark.parametrize(("raw", "clean"), [
    ("Al\x00ice\x1b[31m", "Alice[31m"),  # control characters
    ("Al‮ice​﻿", "Alice"),  # format characters: right-to-left override, zero width space, mark
    ("Alice\U000e0001", "Alice"),  # private use and tag characters
    ("  Al   ice   A ", "Al ice A"),  # outer spaces go, inner runs become one space
    ("<script>alert(1)</script>", "<script>alert(1)</script>"),  # stored as plain text, never changed
    ("=cmd|' /C calc'!A0", "=cmd|' /C calc'!A0"),
    ("x" * 64, "x" * 64),
])
def test_n5_names_are_cleaned_before_they_are_stored(games, raw, clean):
    import_group_csv(games, SEASON, picks(f'1,"{raw}",1,Buf,3.5,Mia,Buf,Favorite,3,5'))
    assert stored_picks(games) == {("2023_01_MIA_BUF", clean): ("BUF", 3)}
    import_group_csv(games, SEASON, picks(f'1,"{raw}",5,5', header="Rank,Team,Wk1,Total_Pts"))
    assert stored_standings(games) == {(SEASON, 1, clean): (5, 1)}


def test_n5_a_tab_or_line_break_inside_a_name_is_removed_not_kept_as_a_space(games):
    import_group_csv(games, SEASON, picks('1,"Al\tice\r\nA",1,Buf,3.5,Mia,Buf,Favorite,3,5'))
    assert list(stored_picks(games)) == [("2023_01_MIA_BUF", "AliceA")]


@pytest.mark.parametrize("raw", ["", "   ", "\x00​", "x" * 65])
def test_n6_a_name_that_is_empty_or_over_64_characters_after_cleaning_is_refused(games, raw):
    refused(games, picks(f'1,"{raw}",1,Buf,3.5,Mia,Buf,Favorite,3,5'), "line 2: .*name")
    refused(games, picks(f'1,"{raw}",5,5', header="Rank,Team,Wk1,Total_Pts"), "line 2: .*name")


def test_n7_a_bad_row_refuses_the_whole_file_and_keeps_what_was_stored(games):
    import_group_csv(games, SEASON, PICKS)
    import_group_csv(games, SEASON, STANDINGS)
    # only the last row is bad; an earlier, good row of the same file carries a change
    changed = edit("Buf,Favorite,3,5", "Mia,Underdog,3,5")
    last = f"2,{DEE},2,Buf,10.0,NE,Buf,Favorite,"
    refused(games, edit(last + "2,3", last + "99,3", changed), "line 21: .*confidence")
    assert stored_picks(games)[("2023_01_MIA_BUF", "Ann A")] == ("BUF", 3)
    refused(games, edit("1,Bo's Picks,6,3,9", "1,Bo's Picks,1,1,2", STANDINGS).replace(b"4,2,6", b"4,2,7"),
            "line 5: .*total")
    assert stored_standings(games)[(SEASON, 1, "Bo's Picks")] == (6, None)


def test_n8_an_error_names_the_line_and_never_echoes_a_long_value_or_a_member_name(games):
    assert issubclass(GroupImportError, ValueError)
    long_number = f"1,Zed Secret,1,Buf,3.5,Mia,Buf,Favorite,{'9' * 500},5"
    message = refused(games, picks(ROW.replace("Ann A", "Cy!!"), long_number), "line 3: ")
    assert "Zed Secret" not in message
    assert "9" * 41 not in message and "9" * 40 in message
    message = refused(games, picks(f"1,Zed Secret,1,{'Q' * 500},3.5,Mia,Buf,Favorite,3,5"), "line 2: ")
    assert "Zed Secret" not in message and "Q" * 41 not in message
    assert "NNN" not in refused(games, picks(f"1,{'N' * 65},1,Buf,3.5,Mia,Buf,Favorite,3,5"), "line 2: ")
    assert "NNN" not in refused(games, picks(ROW.replace("Ann A", "NNNN"), ROW.replace("Ann A", "NNNN")), "twice")
    weekly = picks("1,NNNN,5,5", "2,NNNN,4,4", header="Rank,Team,Wk1,Total_Pts")
    assert "NNN" not in refused(games, weekly, "line 3: .*twice")


def test_n9_importing_the_same_file_again_changes_nothing(games):
    import_group_csv(games, SEASON, PICKS)
    import_group_csv(games, SEASON, STANDINGS)
    first = stored_picks(games), stored_standings(games)
    assert (import_group_csv(games, SEASON, PICKS).rows, import_group_csv(games, SEASON, STANDINGS).rows) == (20, 8)
    assert (stored_picks(games), stored_standings(games)) == first
    assert (len(first[0]), len(first[1])) == (20, 8)


def test_n10_a_corrected_file_updates_the_row_in_place(games):
    import_group_csv(games, SEASON, PICKS)
    fixed = edit("1,Ann A,1,Buf,3.5,Mia,Buf,Favorite,3,5", "1,Ann A,1,Buf,3.5,Mia,Mia,Underdog,3,5")
    fixed = edit(f"1,{DEE},1,Buf,3.5,Mia,,none,,5", f"1,{DEE},1,Buf,3.5,Mia,Buf,Favorite,1,5", fixed)
    fixed = edit("2,Bo's Picks,1,LAR,2.5,KC,KC,Underdog,1,3", "2,Bo's Picks,1,LAR,2.5,KC,,none,,3", fixed)
    import_group_csv(games, SEASON, fixed)
    rows = stored_picks(games)
    assert len(rows) == 20
    assert rows[("2023_01_MIA_BUF", "Ann A")] == ("MIA", 3)
    assert rows[("2023_01_MIA_BUF", DEE)] == ("BUF", 1)
    assert rows[("2023_02_KC_LA", "Bo's Picks")] == (None, None)
    # a file with fewer rows leaves the other rows alone
    import_group_csv(games, SEASON, picks(ROW))
    assert len(stored_picks(games)) == 20 and stored_picks(games)[("2023_01_MIA_BUF", "Ann A")] == ("BUF", 3)


# Weekly points file ---------------------------------------------------------------------------------------------


def test_w1_weekly_file_stores_points_per_member_and_week_and_the_rank_on_the_last_week_only(games):
    result = import_group_csv(games, SEASON, STANDINGS)
    assert (result.kind, result.rows) == ("standings", 8)
    assert stored_standings(games) == {
        (SEASON, 1, "Bo's Picks"): (6, None), (SEASON, 2, "Bo's Picks"): (3, 1),
        (SEASON, 1, DEE): (5, None), (SEASON, 2, DEE): (3, 2),
        (SEASON, 1, "Ann A"): (5, None), (SEASON, 2, "Ann A"): (3, 3),
        (SEASON, 1, "Cy!!"): (4, None), (SEASON, 2, "Cy!!"): (2, 4),
    }


@pytest.mark.parametrize(("old", "new", "match"), [
    ("1,Bo's Picks,6,3,9", "1,Bo's Picks,6,3,10", "line 2: .*total"),  # the total is not the sum of the weeks
    ("1,Bo's Picks,6,3,9", "1,Bo's Picks,6,,6", "line 2: .*points"),  # a blank week
    ("1,Bo's Picks,6,3,9", "1,Bo's Picks,137,3,140", "line 2: .*points"),
    ("1,Bo's Picks,6,3,9", "1,Bo's Picks,-6,3,-3", "line 2: .*points"),
    ("1,Bo's Picks,6,3,9", "1,Bo's Picks,6,3,", "line 2: .*total"),
    ("1,Bo's Picks,6,3,9", "1,Bo's Picks,6,3,9.0", "line 2: .*total"),
    ("1,Bo's Picks,6,3,9", "0,Bo's Picks,6,3,9", "line 2: .*rank"),
    ("1,Bo's Picks,6,3,9", "10000,Bo's Picks,6,3,9", "line 2: .*rank"),
    ("1,Bo's Picks,6,3,9", "1.0,Bo's Picks,6,3,9", "line 2: .*rank"),
    ("3,Ann A,5,3,8", "3,Bo's Picks,5,3,8", "line 4: .*twice"),  # one member on two rows
])
def test_w2_weekly_rows_are_checked(games, old, new, match):
    refused(games, edit(old, new, STANDINGS), match)


def test_w2_weekly_numbers_at_their_bounds_are_accepted(games):
    import_group_csv(games, SEASON, picks("9999,Ann A,136,0,136", header="Rank,Team,Wk1,Wk2,Total_Pts"))
    assert stored_standings(games) == {(SEASON, 1, "Ann A"): (136, None), (SEASON, 2, "Ann A"): (0, 9999)}


def test_w3_a_later_file_keeps_the_rank_an_earlier_file_gave_a_week(games):
    import_group_csv(games, SEASON, STANDINGS)
    later = picks("1,Ann A,5,4,7,16", "2,Bo's Picks,6,3,2,11", header="Rank,Team,Wk1,Wk2,Wk3,Total_Pts")
    assert import_group_csv(games, SEASON, later).rows == 6
    rows = stored_standings(games)
    assert rows[(SEASON, 2, "Ann A")] == (4, 3)  # points corrected, week 2 rank kept
    assert rows[(SEASON, 2, "Bo's Picks")] == (3, 1)
    assert rows[(SEASON, 3, "Ann A")] == (7, 1) and rows[(SEASON, 3, "Bo's Picks")] == (2, 2)
    assert rows[(SEASON, 1, "Ann A")] == (5, None)
    assert len(rows) == 10  # the two members missing from the later file keep their rows
    # the same last week again replaces that week's rank
    import_group_csv(games, SEASON, picks("2,Ann A,5,4,7,16", header="Rank,Team,Wk1,Wk2,Wk3,Total_Pts"))
    assert stored_standings(games)[(SEASON, 3, "Ann A")] == (7, 2)


def test_w4_seasons_are_kept_apart(games):
    import_group_csv(games, SEASON, STANDINGS)
    import_group_csv(games, 2022, picks("1,Ann A,9,9", header="Rank,Team,Wk1,Total_Pts"))
    rows = stored_standings(games)
    assert rows[(2022, 1, "Ann A")] == (9, 1) and rows[(SEASON, 1, "Ann A")] == (5, None)


# Questions ------------------------------------------------------------------------------------------------------


def test_q1_game_shares_counts_each_side_and_averages_its_confidence(games):
    import_group_csv(games, SEASON, PICKS)
    # MIA at BUF: Ann BUF 3, Bo BUF 2, Cy MIA 1, Dee no pick. 4 members, 3 picked.
    assert game_shares(games, "2023_01_MIA_BUF") == {
        "game_id": "2023_01_MIA_BUF", "members": 4, "picked": 3,
        "away": {"team": "MIA", "picks": 1, "share": pytest.approx(1 / 3), "avg_confidence": pytest.approx(1.0)},
        "home": {"team": "BUF", "picks": 2, "share": pytest.approx(2 / 3), "avg_confidence": pytest.approx(2.5)},
    }
    # KC at LA: Ann LA 2, Dee LA 1, Bo KC 1, Cy no pick.
    shares = game_shares(games, "2023_02_KC_LA")
    assert (shares["members"], shares["picked"]) == (4, 3)
    assert shares["away"] == {"team": "KC", "picks": 1, "share": pytest.approx(1 / 3), "avg_confidence": 1.0}
    assert shares["home"] == {"team": "LA", "picks": 2, "share": pytest.approx(2 / 3), "avg_confidence": 1.5}


def test_q2_a_side_nobody_picked_and_a_game_nobody_picked_show_missing_not_zero(games):
    import_group_csv(games, SEASON, PICKS)
    # LV at KC: all four picked KC with 2, 1, 2, 3.
    shares = game_shares(games, "2023_01_LV_KC")
    assert shares["away"] == {"team": "LV", "picks": 0, "share": 0.0, "avg_confidence": None}
    assert shares["home"] == {"team": "KC", "picks": 4, "share": 1.0, "avg_confidence": 2.0}
    import_group_csv(games, 2022, picks("3,Ann A,1,Mia,3.5,LV,,none,,0"))
    assert game_shares(games, "2022_03_LV_MIA") == {
        "game_id": "2022_03_LV_MIA", "members": 1, "picked": 0,
        "away": {"team": "LV", "picks": 0, "share": None, "avg_confidence": None},
        "home": {"team": "MIA", "picks": 0, "share": None, "avg_confidence": None},
    }
    games.execute(GroupPick.__table__.delete())
    games.commit()
    assert game_shares(games, "2023_01_LV_KC")["members"] == 0
    assert game_shares(games, "2023_01_LV_KC")["home"] == {"team": "KC", "picks": 0, "share": None,
                                                           "avg_confidence": None}


def test_q3_game_shares_for_an_unknown_game_raises(games):
    with pytest.raises(LookupError):
        game_shares(games, "2023_09_XX_YY")


def test_q4_standings_for_a_week_give_points_running_total_and_rank(games):
    import_group_csv(games, SEASON, STANDINGS)
    import_group_csv(games, 2022, picks("1,Ann A,90,90", header="Rank,Team,Wk1,Total_Pts"))  # another season
    # Week 2: totals Bo 9, Dee 8, Ann 8, Cy 6. Dee and Ann tie on total: Yahoo's rank puts Dee first.
    assert standings(games, SEASON, 2) == [
        {"member": "Bo's Picks", "points": 3, "total": 9, "rank": 1},
        {"member": DEE, "points": 3, "total": 8, "rank": 2},
        {"member": "Ann A", "points": 3, "total": 8, "rank": 3},
        {"member": "Cy!!", "points": 2, "total": 6, "rank": 4},
    ]
    # Week 1 has no rank in the file: it stays missing, and a tie on total goes by name.
    assert standings(games, SEASON, 1) == [
        {"member": "Bo's Picks", "points": 6, "total": 6, "rank": None},
        {"member": "Ann A", "points": 5, "total": 5, "rank": None},
        {"member": DEE, "points": 5, "total": 5, "rank": None},
        {"member": "Cy!!", "points": 4, "total": 4, "rank": None},
    ]
    assert standings(games, SEASON, 3) == []
    assert standings(games, 2021, 1) == []


def test_q4_running_total_counts_only_weeks_up_to_the_asked_week(games):
    import_group_csv(games, SEASON, picks("1,Ann A,5,4,7,16", "2,Cy!!,9,1,1,11",
                                          header="Rank,Team,Wk1,Wk2,Wk3,Total_Pts"))
    assert standings(games, SEASON, 2) == [
        {"member": "Cy!!", "points": 1, "total": 10, "rank": None},
        {"member": "Ann A", "points": 4, "total": 9, "rank": None},
    ]
    assert [(r["member"], r["total"], r["rank"]) for r in standings(games, SEASON, 3)] == [("Ann A", 16, 1),
                                                                                           ("Cy!!", 11, 2)]
