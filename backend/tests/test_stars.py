"""Step 8a: star players (five per club) and which of them are out.

Every expected number in the hand-made cases is counted by hand in the comments.
The recorded case reads real nflverse files from tests/fixtures/stars (no network); its expected rows come from
docs/gauntlet/logs/step-8a-evidence/s8a-handcount.py, an independent count that shares no code with the app.
"""

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from nflpi.analytics.stars import stars_out
from sqlalchemy import func, select

from nflpi.ingestion import nflverse, service
from nflpi.models import Game, IngestionRun, InjuryReport, TeamStar

FIXTURES = Path(__file__).parent / "fixtures" / "stars"
SEASON = 2023
NOW = datetime(2023, 9, 20, 12, tzinfo=UTC)
STAT_COLS = [
    "attempts",
    "rushing_yards",
    "rushing_tds",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "def_tackles_solo",
    "def_tackles_with_assist",
    "def_tackle_assists",
    "def_tackles_for_loss",
    "def_fumbles_forced",
    "def_sacks",
    "def_qb_hits",
    "def_interceptions",
    "def_pass_defended",
    "def_tds",
    "def_safeties",
]


def snap(week: int, team: str, pfr: str, name: str, pos: str, off: int = 0, de: int = 0, season: int = SEASON) -> dict:
    """One row shaped like snap_counts_<season>.csv (every value a string, as csv gives it)."""
    return {
        "game_id": f"{season}_{week:02d}_AAA_BBB",
        "pfr_game_id": "x",
        "season": str(season),
        "game_type": "REG",
        "week": str(week),
        "player": name,
        "pfr_player_id": pfr,
        "position": pos,
        "team": team,
        "opponent": "BBB",
        "offense_snaps": str(off),
        "offense_pct": "0",
        "defense_snaps": str(de),
        "defense_pct": "0",
        "st_snaps": "0",
        "st_pct": "0",
    }


def stat(week: int, team: str, gsis: str, name: str, pos: str, season: int = SEASON, **nums) -> dict:
    """One row shaped like stats_player_week_<season>.csv, with only the columns the star rule reads."""
    unknown = set(nums) - set(STAT_COLS)
    assert not unknown, unknown
    return (
        {
            "player_id": gsis,
            "player_name": name,
            "player_display_name": name,
            "position": pos,
            "position_group": pos,
            "season": str(season),
            "week": str(week),
            "season_type": "REG",
            "team": team,
            "opponent_team": "BBB",
        }
        | {c: "0" for c in STAT_COLS}
        | {k: str(v) for k, v in nums.items()}
    )


def handmade() -> tuple[list[dict], list[dict], list[dict]]:
    """Season 2023, weeks 1 and 2. Returns (snap rows, stat rows, player id rows)."""
    players = [
        {"pfr_id": pfr, "gsis_id": gsis, "display_name": ""}
        for pfr, gsis in [
            ("PatQ01", "00-001"),
            ("BacQ01", "00-002"),
            ("RunR01", "00-003"),
            ("CatW01", "00-004"),
            ("TigT01", "00-005"),
            ("TacT01", "00-006"),
            ("MikL01", "00-007"),
            ("RusD01", "00-008"),
            ("CorC01", "00-009"),
            ("WidW01", "00-020"),
            ("ZedG01", "00-021"),
            ("TwoW01", "00-030"),
            ("TraG01", "00-040"),
            ("StaP01", "00-041"),
            ("", "00-777"),  # a player with no pfr id maps nothing
        ]
    ]
    snaps, stats = [], []
    for week in (1, 2):
        snaps += [
            snap(week, "KC", "PatQ01", "Pat Passer", "QB", off=60),
            snap(week, "KC", "RunR01", "Ron Runner", "RB", off=30),
            snap(week, "KC", "CatW01", "Cal Catch", "WR", off=50),
            snap(week, "KC", "TigT01", "Ty Tight", "TE", off=40),
            snap(week, "KC", "TacT01", "Tom Tackle", "T", off=60),
            snap(week, "KC", "MikL01", "Mike Backer", "LB", de=60),
            snap(week, "KC", "RusD01", "Russ Rush", "DE", de=40),
            snap(week, "KC", "CorC01", "Cory Corner", "CB", de=60),
            snap(week, "NYJ", "StaP01", "Stay Put", "WR", off=40),
        ]
    snaps += [
        snap(1, "KC", "BacQ01", "Bo Backup", "QB", off=5),
        # LV: no quarterback and no defender on file. One row still carries the old Oakland code.
        snap(1, "OAK", "WidW01", "Will Wide", "WR", off=50),
        snap(1, "LV", "AblT01", "Able Tackle", "T", off=60),  # AblT01 is not in the player id file
        snap(1, "LV", "ZedG01", "Zed Guard", "G", off=60),
        snap(1, "NE", "TwoW01", "Two Way", "CB", off=20, de=100),
        snap(1, "NYJ", "TraG01", "Trade Guy", "WR", off=50),
        snap(2, "MIA", "TraG01", "Trade Guy", "WR", off=10),  # traded after week 1
        snap(1, "KC", "CatW01", "Cal Catch", "WR", off=999, season=2022),  # another season: never counted
    ]
    stats += [
        # week 1
        stat(1, "KC", "00-001", "Pat Passer", "QB", attempts=30, rushing_yards=50, rushing_tds=1),
        stat(1, "KC", "00-003", "Ron Runner", "RB", rushing_yards=100, rushing_tds=1, receptions=2),
        stat(1, "KC", "00-004", "Cal Catch", "WR", receiving_yards=80, receptions=5),
        stat(1, "KC", "00-005", "Ty Tight", "TE", receiving_yards=30, receptions=3)
        | {"def_sacks": "NA", "rushing_yards": ""},
        stat(
            1, "KC", "00-007", "Mike Backer", "LB", def_tackles_solo=5, def_tackles_with_assist=1, def_tackle_assists=2
        ),
        stat(
            1,
            "KC",
            "00-008",
            "Russ Rush",
            "DE",
            def_tackles_solo=1,
            def_sacks=1.5,
            def_qb_hits=2,
            def_tackles_for_loss=1,
        ),
        stat(1, "KC", "00-009", "Cory Corner", "CB", def_tackles_solo=2, def_pass_defended=1),
        stat(1, "LV", "00-020", "Will Wide", "WR", receiving_yards=40, receptions=4),
        stat(1, "NE", "00-030", "Two Way", "CB", receiving_yards=10, receptions=1, def_tackles_solo=3),
        stat(1, "NYJ", "00-040", "Trade Guy", "WR", receiving_yards=150, receiving_tds=2),
        stat(1, "NYJ", "00-041", "Stay Put", "WR", receiving_yards=20, receptions=2),
        stat(1, "KC", "", "", "", rushing_yards=500),  # nflverse team rows have no player id: skipped
        stat(1, "KC", "00-004", "Cal Catch", "WR", season=2022, receiving_yards=900, receiving_tds=9),  # another season
        # week 2
        stat(2, "KC", "00-001", "Pat Passer", "QB", attempts=30),
        stat(2, "KC", "00-003", "Ron Runner", "RB", rushing_yards=100, receptions=2),
        stat(2, "KC", "00-004", "Cal Catch", "WR", receiving_yards=60, receptions=5),
        stat(2, "KC", "00-005", "Ty Tight", "TE", receiving_yards=20, receptions=2),
        stat(
            2, "KC", "00-007", "Mike Backer", "LB", def_tackles_solo=5, def_tackles_with_assist=1, def_tackle_assists=2
        ),
        stat(2, "KC", "00-008", "Russ Rush", "DE", def_tackles_solo=1, def_sacks=0.5, def_qb_hits=1),
        stat(2, "KC", "00-009", "Cory Corner", "CB", def_tackles_solo=2, def_interceptions=2, def_pass_defended=2),
        stat(2, "MIA", "00-040", "Trade Guy", "WR", receiving_yards=10),
        stat(2, "NYJ", "00-041", "Stay Put", "WR", receiving_yards=30, receptions=3),
    ]
    return snaps, stats, players


def ingest(session, season: int = SEASON, data=None) -> IngestionRun:
    snaps, stats, players = data or handmade()
    return service.ingest_stars(session, season, snaps=snaps, stats=stats, players=players)


def stars(session, week: int, team: str, season: int = SEASON) -> list[tuple]:
    """(slot, rank, player, gsis id, position, snaps, production, score) in qb, off, def order."""
    order = {"qb": 0, "off": 1, "def": 2}
    rows = session.scalars(
        select(TeamStar).where(TeamStar.season == season, TeamStar.week == week, TeamStar.team == team)
    ).all()
    rows.sort(key=lambda r: (order[r.slot], r.rank))
    return [
        (r.slot, r.rank, r.player, r.player_id, r.position, r.snaps, round(r.production, 2), round(r.score, 2))
        for r in rows
    ]


def recorded(name: str) -> list[dict]:
    with open(FIXTURES / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _game(session, season: int, week: int, away: str, home: str) -> str:
    game_id = f"{season}_{week:02d}_{away}_{home}"
    session.add(
        Game(
            game_id=game_id,
            season=season,
            week=week,
            game_type="REG",
            kickoff_utc=NOW + timedelta(days=3),
            weekday="Sunday",
            away_team=away,
            home_team=home,
            status="scheduled",
            source="test",
        )
    )
    session.commit()
    return game_id


def _injury(
    session, week: int, team: str, player_id: str | None, player: str, status: str | None, hours_ago: float, **over
):
    row = {
        "season": SEASON,
        "week": week,
        "team": team,
        "player_id": player_id,
        "player": player,
        "position": None,
        "report_status": status,
        "practice_status": None,
        "injury": "Knee",
        "source": "nflverse",
        "observed_at": NOW - timedelta(hours=hours_ago),
    }
    session.add(InjuryReport(**(row | over)))
    session.commit()


# S1-S3, S13: the quarterback, top two on offence, top two on defence


def test_five_stars_per_club_ranked_from_snaps_and_production(session):
    run = ingest(session)
    assert (run.status, run.source, run.dataset) == ("ok", "nflverse", "stars")
    # Stars for week 3 use weeks 1 and 2.
    # Quarterback: Pat 120 offence snaps (Bo 5). Stored: snaps 120, production = 60 pass attempts, score = snaps.
    # Offence, score = 0.1 x offence snaps + (rush + receiving yards) / 10 + 6 x touchdowns + 0.5 x catches:
    #   Ron Runner 0.1 x 60 + 200/10 + 6 x 1 + 0.5 x 4 = 6 + 28 = 34.0
    #   Cal Catch  0.1 x 100 + 140/10 + 0.5 x 10       = 10 + 19 = 29.0
    #   Ty Tight   0.1 x 80 + 50/10 + 0.5 x 5          = 8 + 7.5 = 15.5 ("NA" and blank count as 0)
    #   Tom Tackle 0.1 x 120                           = 12.0 (a lineman: snaps only, so he misses the cut)
    #   Pat Passer ran for 50 yards and a touchdown but is a quarterback: never in the offence slots.
    # Defence, score = 0.05 x defence snaps + tackles + 0.5 x assists + 6 x sacks + 2 x QB hits + 2 x tackles for loss
    #                  + 6 x interceptions + 3 x passes defended (+ 4 x forced fumbles + 6 x TDs + 2 x safeties):
    #   Cory Corner 0.05 x 120 + 4 + 6 x 2 + 3 x 3          = 6 + 25 = 31.0
    #   Russ Rush   0.05 x 80 + 2 + 6 x 2 + 2 x 3 + 2 x 1   = 4 + 22 = 26.0
    #   Mike Backer 0.05 x 120 + (10 + 2) + 0.5 x 4         = 6 + 14 = 20.0
    assert stars(session, 3, "KC") == [
        ("qb", 1, "Pat Passer", "00-001", "QB", 120, 60.0, 120.0),
        ("off", 1, "Ron Runner", "00-003", "RB", 60, 28.0, 34.0),
        ("off", 2, "Cal Catch", "00-004", "WR", 100, 19.0, 29.0),
        ("def", 1, "Cory Corner", "00-009", "CB", 120, 25.0, 31.0),
        ("def", 2, "Russ Rush", "00-008", "DE", 80, 22.0, 26.0),
    ]


# S4: only earlier weeks of the same season count


def test_stars_for_a_week_use_only_earlier_weeks_of_that_season(session):
    ingest(session)
    # Stars for week 2 use week 1 only:
    #   Ron Runner 3 + 10 + 6 + 1 = 20.0; Cal Catch 5 + 8 + 2.5 = 15.5 (his 2022 rows are another season)
    #   Russ Rush 2 + 1 + 9 + 4 + 2 = 18.0; Mike Backer 3 + 6 + 1 = 10.0; Cory Corner 3 + 2 + 3 = 8.0
    assert stars(session, 2, "KC") == [
        ("qb", 1, "Pat Passer", "00-001", "QB", 60, 30.0, 60.0),
        ("off", 1, "Ron Runner", "00-003", "RB", 30, 17.0, 20.0),
        ("off", 2, "Cal Catch", "00-004", "WR", 50, 10.5, 15.5),
        ("def", 1, "Russ Rush", "00-008", "DE", 40, 16.0, 18.0),
        ("def", 2, "Mike Backer", "00-007", "LB", 60, 7.0, 10.0),
    ]
    # Nothing is known before a club's first game, and the last list is for the week after the last data week.
    weeks = set(session.scalars(select(TeamStar.week).where(TeamStar.season == SEASON)))
    assert weeks == {2, 3}
    assert session.scalar(select(func.count()).select_from(TeamStar).where(TeamStar.season != SEASON)) == 0


# S2, S6, S7, S13: linemen, players without an id, old club codes, ties


def test_a_lineman_makes_the_list_only_when_too_few_others_produce(session):
    ingest(session)
    # LV after week 1: Will Wide 0.1 x 50 + 40/10 + 0.5 x 4 = 11.0 (his snaps are filed under OAK, his stats under LV).
    # Able Tackle and Zed Guard both 0.1 x 60 = 6.0: the tie goes to the name first in A-Z order.
    # Able Tackle has no id in the player file: he is still ranked, with no id. No quarterback or defender is on file.
    assert stars(session, 2, "LV") == [
        ("off", 1, "Will Wide", "00-020", "WR", 50, 6.0, 11.0),
        ("off", 2, "Able Tackle", None, "T", 60, 0.0, 6.0),
    ]
    assert stars(session, 2, "OAK") == []


# S14: a player who plays both ways holds one slot


def test_a_two_way_player_is_ranked_once_on_his_stronger_side(session):
    ingest(session)
    # Two Way: offence 0.1 x 20 + 10/10 + 0.5 = 3.5; defence 0.05 x 100 + 3 = 8.0. Defence wins; no offence row.
    assert stars(session, 2, "NE") == [("def", 1, "Two Way", "00-030", "CB", 100, 3.0, 8.0)]


# S5: a traded player belongs to the club of his latest game


def test_a_traded_player_counts_only_for_his_latest_club(session):
    ingest(session)
    # After week 1 Trade Guy is a Jet: 0.1 x 50 + 150/10 + 6 x 2 = 32.0. Stay Put 0.1 x 40 + 2 + 1 = 7.0.
    assert stars(session, 2, "NYJ") == [
        ("off", 1, "Trade Guy", "00-040", "WR", 50, 27.0, 32.0),
        ("off", 2, "Stay Put", "00-041", "WR", 40, 3.0, 7.0),
    ]
    assert stars(session, 2, "MIA") == []
    # In week 2 he played for Miami: gone from the Jets list. In Miami only his Miami numbers count: 0.1 x 10 + 1 = 2.0.
    assert stars(session, 3, "NYJ") == [("off", 1, "Stay Put", "00-041", "WR", 80, 7.5, 15.5)]
    assert stars(session, 3, "MIA") == [("off", 1, "Trade Guy", "00-040", "WR", 10, 1.0, 2.0)]


# S8: a second run replaces the season and leaves other seasons alone


def test_rerun_replaces_the_season_and_keeps_other_seasons(session):
    old = (
        [snap(1, "KC", "PatQ01", "Pat Passer", "QB", off=40, season=2022)],
        [stat(1, "KC", "00-001", "Pat Passer", "QB", season=2022, attempts=20)],
        [{"pfr_id": "PatQ01", "gsis_id": "00-001", "display_name": ""}],
    )
    assert ingest(session, 2022, old).status == "ok"
    first = ingest(session)
    # KC 5 + 5, LV 2 + 2, NE 1 + 1, NYJ 2 + 1, MIA 0 + 1 = 20 rows for weeks 2 and 3.
    assert first.rows == 20
    second = ingest(session)
    assert (second.status, second.rows) == ("ok", 20)
    assert session.scalar(select(func.count()).select_from(TeamStar).where(TeamStar.season == SEASON)) == 20
    assert stars(session, 2, "KC", season=2022) == [("qb", 1, "Pat Passer", "00-001", "QB", 40, 20.0, 40.0)]


# S9, S15: a bad file fails the run loudly and the old list stays


def _without(rows: list[dict], column: str) -> list[dict]:
    return [{k: v for k, v in r.items() if k != column} for r in rows]


@pytest.mark.parametrize(
    "case",
    [
        "missing_snap_column",
        "missing_stat_column",
        "negative_snaps",
        "snaps_not_a_number",
        "empty_files",
        "id_too_long",
    ],
)
def test_a_bad_file_fails_the_run_and_keeps_the_old_stars(session, case):
    ingest(session)
    before = stars(session, 3, "KC")
    snaps, stats, players = handmade()
    if case == "missing_snap_column":
        snaps = _without(snaps, "offense_snaps")
    elif case == "missing_stat_column":
        stats = _without(stats, "def_sacks")
    elif case == "negative_snaps":
        snaps[0] = snaps[0] | {"offense_snaps": "-4"}
    elif case == "snaps_not_a_number":
        snaps[0] = snaps[0] | {"defense_snaps": "lots"}
    elif case == "empty_files":
        snaps, stats = [], []
    elif case == "id_too_long":
        stats[1] = stats[1] | {"player_id": "x" * 40}
    run = service.ingest_stars(session, SEASON, snaps=snaps, stats=stats, players=players)
    assert run.status == "failed"
    assert run.error
    assert stars(session, 3, "KC") == before
    assert session.scalar(select(func.count()).select_from(TeamStar)) == 20


def test_a_failed_download_keeps_the_old_stars(session, monkeypatch):
    ingest(session)

    def boom(path):
        raise RuntimeError("nflverse download failed")

    monkeypatch.setattr(nflverse, "fetch_csv", boom)
    run = service.ingest_stars(session, SEASON)
    assert (run.status, run.dataset) == ("failed", "stars")
    assert session.scalar(select(func.count()).select_from(TeamStar)) == 20


def test_ingest_downloads_the_three_nflverse_files(session, monkeypatch):
    files = {
        "snap_counts/snap_counts_2026.csv": recorded("snap_counts_2026.csv"),
        "stats_player/stats_player_week_2026.csv": recorded("stats_player_week_2026.csv"),
        "players/players.csv": recorded("players.csv"),
    }
    asked = []

    def fake(path):
        asked.append(path)
        return files[path]

    monkeypatch.setattr(nflverse, "fetch_csv", fake)
    run = service.ingest_stars(session, 2026)
    assert run.status == "ok", run.error
    assert sorted(asked) == sorted(files)


# Recorded real files: the app's stars equal the independent count


def test_recorded_2026_files_give_the_hand_counted_stars(session):
    run = service.ingest_stars(
        session,
        2026,
        snaps=recorded("snap_counts_2026.csv"),
        stats=recorded("stats_player_week_2026.csv"),
        players=recorded("players.csv"),
    )
    assert run.status == "ok", run.error
    # Stars for week 6 (weeks 1 to 5 played), from s8a-handcount.py on the same files.
    assert stars(session, 6, "KC", season=2026) == [
        ("qb", 1, "Patrick Mahomes", "00-0033873", "QB", 261, 128.0, 261.0),
        ("off", 1, "Kenneth Walker III", "00-0038134", "RB", 196, 104.1, 123.7),
        ("off", 2, "Travis Kelce", "00-0030506", "TE", 208, 44.6, 65.4),
        ("def", 1, "George Karlaftis III", "00-0037192", "DE", 234, 46.5, 58.2),
        ("def", 2, "Nick Bolton", "00-0036621", "LB", 273, 38.5, 52.15),
    ]
    assert stars(session, 6, "BUF", season=2026) == [
        ("qb", 1, "Josh Allen", "00-0034857", "QB", 257, 119.0, 257.0),
        ("off", 1, "James Cook", "00-0037248", "RB", 176, 65.5, 83.1),
        ("off", 2, "Dalton Kincaid", "00-0038933", "TE", 170, 40.5, 57.5),
        ("def", 1, "Gregory Rousseau", "00-0036914", "LB", 224, 121.5, 132.7),
        ("def", 2, "Deone Walker", "00-0040710", "DL", 202, 41.0, 51.1),
    ]
    assert stars(session, 6, "DET", season=2026) == [
        ("qb", 1, "Jared Goff", "00-0033106", "QB", 341, 191.0, 341.0),
        ("off", 1, "Jahmyr Gibbs", "00-0039139", "RB", 264, 142.2, 168.6),
        ("off", 2, "Amon-Ra St. Brown", "00-0036963", "WR", 304, 85.7, 116.1),
        ("def", 1, "Aidan Hutchinson", "00-0037236", "DE", 338, 67.5, 84.4),
        ("def", 2, "Derrick Barnes", "00-0036964", "LB", 313, 66.0, 81.65),
    ]
    # Earlier in the season the list was different: after two weeks Nohl Williams led the Chiefs defence.
    assert stars(session, 3, "KC", season=2026)[3][:3] == ("def", 1, "Nohl Williams")
    weeks = set(session.scalars(select(TeamStar.week).where(TeamStar.season == 2026)))
    assert weeks == {2, 3, 4, 5, 6}


# S10-S12: which stars are out for a game


def test_stars_out_lists_stars_whose_latest_report_is_out_or_doubtful(session):
    ingest(session)
    game_id = _game(session, SEASON, 3, "NYJ", "KC")
    _injury(session, 3, "KC", "00-009", "Cory Corner", "Out", 30, position="CB")  # a star, out
    _injury(session, 3, "KC", "00-003", "Ron Runner", "Out", 50)  # a star: out first ...
    _injury(session, 3, "KC", "00-003", "Ron Runner", "Questionable", 5)  # ... then upgraded: not listed
    _injury(session, 3, "KC", "00-004", "Cal Catch", "Questionable", 4)  # a star, only questionable
    _injury(session, 3, "KC", "00-006", "Tom Tackle", "Out", 4)  # out, but not a star
    _injury(session, 2, "KC", "00-001", "Pat Passer", "Out", 200)  # last week's report: not this game
    _injury(session, 3, "KC", "00-008", "Russ Rush", None, 4, practice_status="Limited")  # practice note only
    _injury(session, 3, "NYJ", "00-041", "Stay Put", "Doubtful", 2, injury="Ankle")  # a star, doubtful
    session.add(
        IngestionRun(source="nflverse", dataset="injuries", status="ok", finished_at=NOW - timedelta(hours=1), rows=1)
    )
    session.add(IngestionRun(source="nflverse", dataset="injuries", status="failed", finished_at=NOW, error="boom"))
    session.commit()

    result = stars_out(session, game_id, now=NOW)

    assert {k: result[k] for k in ("game_id", "season", "week", "stars_week")} == {
        "game_id": game_id,
        "season": SEASON,
        "week": 3,
        "stars_week": 3,
    }
    assert result["checked_at"] == NOW - timedelta(hours=1)  # the last good injury refresh, not the failed one
    # Away club first, then home; inside a club: quarterback, offence, defence.
    assert result["out"] == [
        {
            "team": "NYJ",
            "player": "Stay Put",
            "player_id": "00-041",
            "position": "WR",
            "slot": "off",
            "rank": 1,
            "status": "Doubtful",
            "injury": "Ankle",
            "observed_at": NOW - timedelta(hours=2),
            "age_hours": 2.0,
            "source": "nflverse",
        },
        {
            "team": "KC",
            "player": "Cory Corner",
            "player_id": "00-009",
            "position": "CB",
            "slot": "def",
            "rank": 1,
            "status": "Out",
            "injury": "Knee",
            "observed_at": NOW - timedelta(hours=30),
            "age_hours": 30.0,
            "source": "nflverse",
        },
    ]


def test_stars_out_matches_by_name_when_either_side_has_no_id(session):
    ingest(session)
    game_id = _game(session, SEASON, 2, "LV", "NE")
    _injury(session, 2, "LV", "00-099", "Able Tackle", "Out", 3)  # the star has no id: matched by name and club
    _injury(session, 2, "NE", None, "Two Way", "Doubtful", 6)  # the report has no id: matched by name and club
    _injury(session, 2, "LV", "00-555", "Will Wide", "Out", 3)  # same name, different id: a different person
    result = stars_out(session, game_id, now=NOW)
    assert [(r["team"], r["player"], r["player_id"], r["status"]) for r in result["out"]] == [
        ("LV", "Able Tackle", None, "Out"),
        ("NE", "Two Way", "00-030", "Doubtful"),
    ]
    assert result["checked_at"] is None  # injuries were never refreshed: shown as missing, not guessed


def test_stars_out_uses_the_latest_earlier_list_and_says_which(session):
    ingest(session)
    later = _game(session, SEASON, 5, "NYJ", "KC")  # no list for week 5: the week 3 list is the newest
    _injury(session, 5, "KC", "00-009", "Cory Corner", "Out", 1)
    result = stars_out(session, later, now=NOW)
    assert result["stars_week"] == 3
    assert [r["player"] for r in result["out"]] == ["Cory Corner"]

    opener = _game(session, SEASON, 1, "NYJ", "KC")  # week 1: no list exists yet, and a later list is never used
    _injury(session, 1, "KC", "00-009", "Cory Corner", "Out", 1)
    assert stars_out(session, opener, now=NOW) | {"checked_at": None} == {
        "game_id": opener,
        "season": SEASON,
        "week": 1,
        "stars_week": None,
        "checked_at": None,
        "out": [],
    }


def test_stars_out_rejects_an_unknown_game(session):
    with pytest.raises(LookupError):
        stars_out(session, "2023_99_NOPE_NOPE", now=NOW)
