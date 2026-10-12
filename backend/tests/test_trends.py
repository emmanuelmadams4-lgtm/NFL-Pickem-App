"""Step 12: matchup and situation trends. Every expected number below is counted by hand from the rows in the test."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from nflpi.ai import research
from nflpi.analytics.trends import MIN_GAMES, game_trends
from nflpi.models import Game, Prediction
from tests.conftest import CURRENT

_n = 0


def _game(session, season: int, away: str, home: str, away_score: int | None, home_score: int | None, **over) -> str:
    """One game. Kickoffs inside a season follow insertion order, one day apart."""
    global _n
    _n += 1
    row = {
        "game_id": f"{season}_t{_n:03d}_{away}_{home}",
        "season": season,
        "week": 1,
        "game_type": "REG",
        "kickoff_utc": datetime(season, 9, 1, 17, tzinfo=UTC) + timedelta(days=_n),
        "weekday": "Sunday",
        "away_team": away,
        "home_team": home,
        "away_score": away_score,
        "home_score": home_score,
        "status": "scheduled" if home_score is None else "final",
        "source": "test",
    }
    session.add(Game(**(row | over)))
    session.commit()
    return row["game_id"]


def _find(rows: list[dict], **match) -> dict | None:
    hits = [r for r in rows if all(r[k] == v for k, v in match.items())]
    assert len(hits) <= 1, hits
    return hits[0] if hits else None


def _record(row: dict | None) -> tuple | None:
    if row is None:
        return None
    return (row["wins"], row["losses"], row["ties"], row["games"], row["first_season"], row["last_season"])


def test_team_vs_team_record_counts_wins_losses_ties_from_each_side(session):
    # MIA at BUF or BUF at MIA, one a season 2015-2023. (away, home, away score, home score)
    for season, away, home, a, h in [
        (2015, "MIA", "BUF", 20, 27),  # BUF win
        (2016, "BUF", "MIA", 31, 10),  # BUF win
        (2017, "MIA", "BUF", 17, 17),  # tie
        (2018, "BUF", "MIA", 21, 14),  # BUF win
        (2019, "MIA", "BUF", 30, 13),  # MIA win
        (2020, "BUF", "MIA", 24, 3),  # BUF win
        (2021, "MIA", "BUF", 28, 21),  # MIA win
        (2022, "BUF", "MIA", 35, 7),  # BUF win
        (2023, "MIA", "BUF", 20, 23),  # BUF win
    ]:
        _game(session, season, away, home, a, h)
    target = _game(session, 2024, "MIA", "BUF", None, None)

    rows = game_trends(session, target)

    buf = _find(rows, kind="team_vs_team", team="BUF", window="all")
    mia = _find(rows, kind="team_vs_team", team="MIA", window="all")
    assert _record(buf) == (6, 2, 1, 9, 2015, 2023)
    assert _record(mia) == (2, 6, 1, 9, 2015, 2023)
    assert buf["context"] == "MIA" and mia["context"] == "BUF" and buf["person"] is None
    # 2019-2023 holds only 5 of these games: under the floor, so no last-5 row.
    assert _find(rows, kind="team_vs_team", team="BUF", window="last_5_seasons") is None
    # Not a neutral-site game: no site rows at all.
    assert [r for r in rows if r["kind"] == "team_at_site"] == []


def test_weekday_record_and_last_five_finished_seasons_window(session):
    # BUF on Thursday. W = BUF win, L = BUF loss. BUF is always home here.
    thursday = [
        (2018, "NE", 10, 20),  # W
        (2019, "NYJ", 7, 14),  # W
        (2019, "KC", 30, 20),  # L
        (2020, "NE", 3, 6),  # W
        (2020, "NYJ", 0, 9),  # W
        (2021, "KC", 21, 20),  # L
        (2021, "NE", 13, 17),  # W
        (2022, "NYJ", 10, 24),  # W
        (2022, "KC", 14, 28),  # W
        (2023, "NE", 27, 24),  # L
        (2024, "NYJ", 6, 9),  # W, earlier in the target's own season
    ]
    for season, opp, a, h in thursday:
        _game(session, season, opp, "BUF", a, h, weekday="Thursday")
    _game(session, 2022, "NE", "BUF", 40, 0, weekday="Sunday")  # not a Thursday: never counted
    target = _game(session, 2024, "LV", "BUF", None, None, weekday="Thursday")

    rows = game_trends(session, target)

    every = _find(rows, kind="team_on_weekday", team="BUF", window="all")
    last5 = _find(rows, kind="team_on_weekday", team="BUF", window="last_5_seasons")
    assert _record(every) == (8, 3, 0, 11, 2018, 2024)
    # The five finished seasons before 2024 are 2019-2023: 9 games, 6 wins, 3 losses.
    assert _record(last5) == (6, 3, 0, 9, 2019, 2023)
    assert every["context"] == "Thursday"
    assert _find(rows, kind="team_on_weekday", team="LV", window="all") is None


def test_records_under_eight_games_are_left_out(session):
    assert MIN_GAMES == 8
    for season in range(2017, 2024):  # 7 Monday games for NE
        _game(session, season, "NYJ", "NE", 10, 20, weekday="Monday")
    target = _game(session, 2024, "KC", "NE", None, None, weekday="Monday")
    assert _find(game_trends(session, target), kind="team_on_weekday", team="NE", window="all") is None

    _game(session, 2016, "NYJ", "NE", 10, 20, weekday="Monday")  # the 8th
    row = _find(game_trends(session, target), kind="team_on_weekday", team="NE", window="all")
    assert _record(row) == (8, 0, 0, 8, 2016, 2023)


def test_only_finished_games_before_kickoff_count(session):
    for season in range(2016, 2024):  # 8 KC wins over LV
        _game(session, season, "LV", "KC", 10, 30)
    target = _game(session, 2024, "LV", "KC", 31, 0)  # the game itself is final: KC lost it
    _game(session, 2024, "KC", "LV", 0, 31)  # played after the target: KC lost it too
    _game(session, 2023, "KC", "LV", None, None)  # never played

    row = _find(game_trends(session, target), kind="team_vs_team", team="KC", window="all")

    assert _record(row) == (8, 0, 0, 8, 2016, 2023)


def test_qb_and_coach_records_follow_the_person_and_skip_a_missing_name(session):
    allen = {"home_qb": "Josh Allen", "home_coach": "Sean McDermott"}
    # 8 Allen starts for BUF against MIA under McDermott: 6 wins, 2 losses.
    for season, a, h in [
        (2018, 10, 20),
        (2019, 10, 20),
        (2019, 30, 20),  # loss
        (2020, 10, 20),
        (2021, 10, 20),
        (2022, 24, 20),  # loss
        (2022, 10, 20),
        (2023, 10, 20),
    ]:
        _game(session, season, "MIA", "BUF", a, h, **allen)
    # One Allen start against MIA for another team and coach: a win for him, not for BUF or McDermott.
    _game(session, 2017, "NE", "MIA", 27, 3, away_qb="Josh Allen", away_coach="Someone Else")
    # Two BUF losses to MIA with another QB and coach: team record only.
    _game(session, 2016, "MIA", "BUF", 30, 0, home_qb="Other Guy", home_coach="Old Coach")
    _game(session, 2017, "MIA", "BUF", 30, 0, home_qb="Other Guy", home_coach="Old Coach")
    target = _game(session, 2024, "MIA", "BUF", None, None, **allen)  # MIA's QB and coach are not known

    rows = game_trends(session, target)

    qb = _find(rows, kind="qb_vs_team", team="BUF", window="all")
    coach = _find(rows, kind="coach_vs_team", team="BUF", window="all")
    assert _record(qb) == (7, 2, 0, 9, 2017, 2023)
    assert (qb["person"], qb["context"]) == ("Josh Allen", "MIA")
    assert _record(coach) == (6, 2, 0, 8, 2018, 2023)
    assert (coach["person"], coach["context"]) == ("Sean McDermott", "MIA")
    assert _record(_find(rows, kind="team_vs_team", team="BUF", window="all")) == (6, 4, 0, 10, 2016, 2023)
    # Missing stays missing: no QB or coach rows for the side whose names are unknown.
    assert [r for r in rows if r["team"] == "MIA" and r["kind"] in ("qb_vs_team", "coach_vs_team")] == []


def test_stadium_record_uses_the_stadium_id_across_a_rename(session):
    home = [("NE", 10, 20), ("NYJ", 10, 20), ("KC", 30, 20), ("NE", 10, 20)]  # W W L W, twice over
    for i, (opp, a, h) in enumerate(home * 2):
        name = "New Era Field" if i < 4 else "Highmark Stadium"
        _game(session, 2016 + i, opp, "BUF", a, h, stadium_id="BUF00", stadium=name)
    _game(session, 2020, "BUF", "NE", 0, 40, stadium_id="BOS00", stadium="Gillette Stadium")  # elsewhere
    target = _game(session, 2024, "LV", "BUF", None, None, stadium_id="BUF00", stadium="Highmark Stadium")

    row = _find(game_trends(session, target), kind="team_at_stadium", team="BUF", window="all")

    assert _record(row) == (6, 2, 0, 8, 2016, 2023)
    assert row["context"] == "Highmark Stadium"


def test_neutral_site_record_groups_one_city_by_stadium_id_prefix_or_name(session):
    london = {"neutral_site": True}
    # Jaguars at Wembley: W W L W L
    for season, a, h in [(2015, 10, 20), (2016, 10, 20), (2017, 30, 20), (2018, 10, 20), (2019, 30, 20)]:
        _game(session, season, "IND", "JAX", a, h, stadium_id="LON00", stadium="Wembley Stadium", **london)
    _game(session, 2020, "IND", "JAX", 10, 20, stadium_id="LON01", stadium="Twickenham Stadium", **london)  # W
    _game(session, 2021, "IND", "JAX", 30, 20, stadium_id="LON02", stadium="Tottenham Stadium", **london)  # L
    # The real schedule file has a London game filed under the Jaguars' own stadium id. It still counts.
    _game(session, 2022, "IND", "JAX", 10, 20, stadium_id="JAX00", stadium="Tottenham Hotspur Stadium", **london)  # W
    # Real home games in Jacksonville and another club's London game: never part of the Jaguars' London record.
    _game(session, 2022, "IND", "JAX", 40, 0, stadium_id="JAX00", stadium="EverBank Stadium")
    _game(session, 2023, "IND", "JAX", 40, 0, stadium_id="JAX00", stadium="EverBank Stadium")
    _game(session, 2023, "NE", "LA", 10, 20, stadium_id="LON00", stadium="Wembley Stadium", **london)
    target = _game(
        session, 2024, "LA", "JAX", None, None, stadium_id="LON02", stadium="Tottenham Hotspur Stadium", **london
    )

    rows = game_trends(session, target)

    site = _find(rows, kind="team_at_site", team="JAX", window="all")
    assert _record(site) == (5, 3, 0, 8, 2015, 2022)
    assert site["context"] == "Tottenham Hotspur Stadium, Tottenham Stadium, Twickenham Stadium, Wembley Stadium"
    assert _find(rows, kind="team_at_site", team="LA", window="all") is None  # 1 game
    assert _find(rows, kind="team_at_stadium", team="JAX", window="all") is None  # 1 game filed under LON02


def test_unknown_game_is_an_error(session):
    with pytest.raises(LookupError):
        game_trends(session, "no-such-game")


def test_trends_reach_the_evidence_pack_and_never_touch_predictions(loaded):
    gid = loaded.scalars(select(Game.game_id).where(Game.season == CURRENT, Game.week == 4)).first()
    before = loaded.scalar(select(func.count()).select_from(Prediction))

    pack = research.evidence_pack(loaded, gid)

    trends = pack["trends"]
    assert trends["min_games"] == 8
    assert isinstance(trends["note"], str) and trends["note"]
    assert trends["records"] == game_trends(loaded, gid)
    assert trends["records"], "the fixture seasons give every team more than 8 games at its stadium"
    for r in trends["records"]:
        assert r["games"] >= 8 and r["wins"] + r["losses"] + r["ties"] == r["games"]
        assert r["last_season"] <= CURRENT
    assert loaded.scalar(select(func.count()).select_from(Prediction)) == before
    # Trends are context only: nothing in the prediction code may read them.
    predictions = Path(__file__).resolve().parents[1] / "nflpi" / "predictions"
    assert [p.name for p in predictions.rglob("*.py") if "trends" in p.read_text()] == []
