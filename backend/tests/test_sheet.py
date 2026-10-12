"""Step 4 gate: the pick sheet (owner decisions D1-D3, D7, D10-D14, D43).

Every game gets the app's winner, a label and confidence points 1..N. The owner can change the winner and the
points. A game that has kicked off keeps what it had. Frozen criteria: docs/gauntlet/logs/step-4.md § 2.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from nflpi import jobs
from nflpi.analytics import metrics
from nflpi.ingestion import service
from nflpi.models import Game, UserPick
from nflpi.predictions import engine, sheet
from tests.conftest import CURRENT, schedule_rows
from tests.test_hardening import moneylines

EASTERN = ZoneInfo("America/New_York")
WEEK = 4  # three games, all in the future


def week(client, wk: int = WEEK) -> dict[str, dict]:
    return {g["game_id"]: g for g in client.get(f"/api/weeks/{CURRENT}/{wk}").json()["games"]}


def sheets(client, wk: int = WEEK) -> dict[str, dict]:
    return {gid: g["sheet"] for gid, g in week(client, wk).items()}


def by_points(client) -> list[str]:
    """Game ids from the most points to the fewest."""
    rows = sheets(client)
    return sorted(rows, key=lambda gid: -rows[gid]["my_points"])


class Schedule:
    """The fixture schedule with changes that stick across re-ingests."""

    def __init__(self, session) -> None:
        self.session, self.changed = session, {}

    def change(self, game_id: str, **fields: str) -> None:
        self.changed[game_id] = self.changed.get(game_id, {}) | fields
        service.ingest_schedules(self.session, [r | self.changed.get(r["game_id"], {}) for r in schedule_rows()])

    def kick_off(self, game_id: str) -> None:
        started = (datetime.now(UTC) - timedelta(hours=1)).astimezone(EASTERN)
        self.change(game_id, gameday=f"{started:%Y-%m-%d}", gametime=f"{started:%H:%M}", home_score="", away_score="")

    def finish(self, game_id: str, home: int, away: int) -> None:
        self.kick_off(game_id)
        self.change(game_id, home_score=str(home), away_score=str(away))


@pytest.fixture
def schedule(loaded) -> Schedule:
    return Schedule(loaded)


# S1 label ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prob", "label"),
    [(0.50, "coin_flip"), (0.549, "coin_flip"), (0.55, "tough_matchup"), (0.669, "tough_matchup"),
     (0.67, "easy_pick"), (0.99, "easy_pick")],
)
def test_label_is_three_steps_of_the_picks_win_chance(prob, label):
    assert metrics.pick_label(prob) == label


def test_backtest_reports_how_often_each_label_won(loaded, client):
    report = client.get("/api/backtest").json()
    assert [row["label"] for row in report["labels"]] == ["coin_flip", "tough_matchup", "easy_pick"]
    assert sum(row["games"] for row in report["labels"]) == report["games"]
    for row in report["labels"]:
        assert row["hit_rate"] is None or 0 <= row["hit_rate"] <= 1


# S2 the app's sheet -----------------------------------------------------------------------------------------------


def test_every_game_gets_a_label_and_points_one_to_n_by_win_chance(loaded, client):
    games = week(client)
    rows = {gid: g["sheet"] for gid, g in games.items()}
    assert sorted(r["app_points"] for r in rows.values()) == [1, 2, 3]
    chance = {gid: max(g["prediction"]["home_win_prob"], g["prediction"]["away_win_prob"]) for gid, g in games.items()}
    assert sorted(rows, key=lambda gid: rows[gid]["app_points"]) == sorted(rows, key=lambda gid: chance[gid])
    for gid, row in rows.items():
        assert row["app_pick"] == games[gid]["prediction"]["pick"]
        assert row["label"] == metrics.pick_label(chance[gid])
        assert row["label_hit_rate"] == metrics.LABEL_HIT_RATE[row["label"]]
        # Untouched: his sheet is the app's sheet.
        assert (row["my_pick"], row["my_points"]) == (row["app_pick"], row["app_points"])
        assert (row["pick_by"], row["points_by"], row["differs"]) == ("app", "app", False)


def test_picking_the_underdog_moves_that_game_to_the_fewest_points(loaded, client):
    top = by_points(client)[0]
    game = week(client)[top]
    underdog = game["home"]["abbr"] if game["sheet"]["app_pick"] == game["away"]["abbr"] else game["away"]["abbr"]

    assert client.put(f"/api/picks/{top}", json={"team": underdog}).status_code == 200

    row = sheets(client)[top]
    assert (row["my_pick"], row["pick_by"], row["differs"]) == (underdog, "user", True)
    assert row["my_points"] == 1  # his side has the lowest win chance on the sheet
    assert row["app_points"] == 3  # the app's own sheet did not move
    assert sorted(r["my_points"] for r in sheets(client).values()) == [1, 2, 3]


def test_postponed_game_gets_no_points_and_the_rest_use_one_to_n(loaded, client):
    off = by_points(client)[0]
    loaded.get(Game, off).status = "postponed"
    loaded.commit()

    rows = sheets(client)
    assert rows[off]["app_points"] is None and rows[off]["my_points"] is None
    assert sorted(r["my_points"] for gid, r in rows.items() if gid != off) == [1, 2]


# S3 his points ----------------------------------------------------------------------------------------------------


def test_setting_points_swaps_with_the_game_that_had_them(loaded, client):
    high, mid, low = by_points(client)

    res = client.put(f"/api/picks/{low}/points", json={"points": 3})

    assert res.status_code == 200
    rows = {g["game_id"]: g["sheet"] for g in res.json()["games"]}  # the reply is the week, already updated
    assert (rows[low]["my_points"], rows[high]["my_points"], rows[mid]["my_points"]) == (3, 1, 2)
    assert (rows[low]["points_by"], rows[high]["points_by"], rows[mid]["points_by"]) == ("user", "user", "app")
    assert rows[low]["differs"] and rows[high]["differs"] and not rows[mid]["differs"]
    assert rows[low]["app_points"] == 1  # the app still says what it would do


def test_hand_set_points_stay_when_the_apps_order_changes(loaded, client, schedule):
    high, mid, low = by_points(client)
    client.put(f"/api/picks/{mid}/points", json={"points": 2})  # same number, now his
    game = week(client)[low]
    favorite_is_home = game["sheet"]["app_pick"] == game["home"]["abbr"]

    schedule.change(low, **moneylines(0.97 if favorite_is_home else 0.03))  # the weakest pick becomes the surest
    engine.refresh_predictions(loaded)

    rows = sheets(client)
    assert (rows[low]["my_points"], rows[mid]["my_points"], rows[high]["my_points"]) == (3, 2, 1)
    assert rows[mid]["points_by"] == "user" and rows[mid]["app_points"] == 1 and rows[mid]["differs"]


def test_clearing_hand_set_points_gives_the_game_back_to_the_app(loaded, client):
    high, mid, low = by_points(client)
    client.put(f"/api/picks/{low}/points", json={"points": 3})

    assert client.delete(f"/api/picks/{low}/points").status_code == 200
    assert client.delete(f"/api/picks/{high}/points").status_code == 200

    assert by_points(client) == [high, mid, low]
    assert {r["points_by"] for r in sheets(client).values()} == {"app"}


@pytest.mark.parametrize("points", [0, 4, -1])
def test_points_outside_one_to_n_are_refused(loaded, client, points):
    game_id = by_points(client)[0]
    assert client.put(f"/api/picks/{game_id}/points", json={"points": points}).status_code == 422


# S4 lock ----------------------------------------------------------------------------------------------------------


def test_a_started_game_keeps_its_pick_and_points_and_the_open_games_rerank(loaded, client, schedule):
    high, mid, low = by_points(client)
    before = sheets(client)[mid]
    schedule.kick_off(mid)

    locked = week(client)[mid]
    assert locked["locked"] and locked["sheet"]["my_points"] == 2 and locked["sheet"]["app_points"] == 2

    game = week(client)[low]
    favorite_is_home = game["sheet"]["app_pick"] == game["home"]["abbr"]
    schedule.change(low, **moneylines(0.97 if favorite_is_home else 0.03))
    engine.refresh_predictions(loaded)

    rows = sheets(client)
    assert (rows[low]["my_points"], rows[mid]["my_points"], rows[high]["my_points"]) == (3, 2, 1)
    assert (rows[low]["app_points"], rows[mid]["app_points"], rows[high]["app_points"]) == (3, 2, 1)
    for field in ("app_pick", "my_pick", "label"):
        assert rows[mid][field] == before[field]


def test_points_cannot_move_onto_or_off_a_started_game(loaded, client, schedule):
    high, mid, low = by_points(client)
    schedule.kick_off(high)
    week(client)  # the started game is written down

    assert client.put(f"/api/picks/{high}/points", json={"points": 1}).status_code == 409
    # 3 belongs to the started game
    assert client.put(f"/api/picks/{low}/points", json={"points": 3}).status_code == 409
    assert client.delete(f"/api/picks/{high}/points").status_code == 409
    assert by_points(client) == [high, mid, low]


def test_a_game_he_never_touched_becomes_an_auto_pick_at_kickoff(loaded, client, schedule):
    high, mid, low = by_points(client)
    app = sheets(client)[high]
    schedule.kick_off(high)

    row = sheets(client)[high]
    assert (row["my_pick"], row["my_points"], row["pick_by"]) == (app["app_pick"], app["app_points"], "auto")
    assert not row["differs"]
    saved = loaded.get(UserPick, high)
    assert (saved.picked_team, saved.source) == (app["app_pick"], "auto")


def test_the_worker_tick_writes_down_started_games_without_anyone_opening_the_app(loaded, client, schedule):
    high = by_points(client)[0]
    schedule.kick_off(high)

    jobs.tick(loaded, datetime.now(UTC))

    assert loaded.get(UserPick, high).source == "auto"
    assert loaded.get(sheet.SheetEntry, high).my_points == 3


def test_his_own_pick_is_kept_at_kickoff_and_not_marked_auto(loaded, client, schedule):
    high = by_points(client)[0]
    team = sheets(client)[high]["app_pick"]
    client.put(f"/api/picks/{high}", json={"team": team})
    schedule.kick_off(high)

    row = sheets(client)[high]
    assert (row["my_pick"], row["pick_by"], row["points_by"]) == (team, "user", "app")
    assert loaded.get(UserPick, high).source == "app"


# S5 learning: auto picks apart, rank, scorecard -------------------------------------------------------------------


def test_auto_picks_are_scored_apart_from_his_own(loaded, client, schedule):
    high, mid, low = by_points(client)
    game = week(client)[mid]
    client.put(f"/api/picks/{mid}", json={"team": game["home"]["abbr"]})
    for game_id in (high, mid):
        schedule.kick_off(game_id)
    week(client)
    for game_id in (high, mid):
        schedule.finish(game_id, home=30, away=10)

    perf = client.get(f"/api/performance/{CURRENT}").json()
    row = next(w for w in perf["weeks"] if w["week"] == WEEK)
    assert (row["my_total"], row["my_correct"]) == (1, 1)  # only the game he picked himself
    assert row["auto_total"] == 1
    assert perf["auto"]["total"] == 1


def test_scorecard_compares_his_sheet_with_the_apps_and_shows_his_rank(loaded, client, schedule):
    high, mid, low = by_points(client)
    games = week(client)
    app = {gid: g["sheet"] for gid, g in games.items()}
    top = games[high]
    underdog = top["home"]["abbr"] if app[high]["app_pick"] == top["away"]["abbr"] else top["away"]["abbr"]
    client.put(f"/api/picks/{high}", json={"team": underdog})  # he goes against the app on its surest game
    mine = sheets(client)
    for game_id in games:
        schedule.kick_off(game_id)
    week(client)
    for game_id in games:
        schedule.finish(game_id, home=30, away=10)  # the home team wins every game
    assert client.put(f"/api/ranks/{CURRENT}/{WEEK}", json={"rank": 4, "leader_points": 61}).status_code == 204

    card = client.get(f"/api/scorecard/{CURRENT}").json()

    row = next(w for w in card["weeks"] if w["week"] == WEEK)
    home = {gid: g["home"]["abbr"] for gid, g in games.items()}
    assert row["games"] == 3 and row["max_points"] == 6
    assert row["my_points"] == sum(mine[g]["my_points"] for g in games if mine[g]["my_pick"] == home[g])
    assert row["app_points"] == sum(app[g]["app_points"] for g in games if app[g]["app_pick"] == home[g])
    assert row["changed"] == 1
    assert (row["changed_right"], row["changed_wrong"]) == ((1, 0) if underdog == home[high] else (0, 1))
    assert row["auto"] == 2
    assert (row["rank"], row["leader_points"]) == (4, 61)
    assert sum(r["games"] for r in card["by_label"]) == 3
    assert card["totals"]["my_points"] == row["my_points"]


def test_a_tied_game_scores_zero_for_both_sheets(loaded, client, schedule):
    games = week(client)
    for game_id in games:
        schedule.kick_off(game_id)
    week(client)
    for game_id in games:
        schedule.finish(game_id, home=20, away=20)

    row = next(w for w in client.get(f"/api/scorecard/{CURRENT}").json()["weeks"] if w["week"] == WEEK)
    assert (row["games"], row["my_points"], row["app_points"], row["my_correct"], row["app_correct"]) == (3, 0, 0, 0, 0)


@pytest.mark.parametrize("body", [{"rank": 0}, {"rank": 3, "leader_points": -1}, {}])
def test_rank_entry_refuses_bad_numbers(loaded, client, body):
    assert client.put(f"/api/ranks/{CURRENT}/{WEEK}", json=body).status_code == 422


# S6 Jev breaks near-ties (D43) ------------------------------------------------------------------------------------


def test_order_is_by_win_chance_and_jev_only_swaps_neighbours_that_are_nearly_equal():
    close = [sheet.Ranked("a", 0.704), sheet.Ranked("b", 0.700), sheet.Ranked("c", 0.600)]
    assert sheet.order(close, {}) == ["a", "b", "c"]  # no Jev answer: win chance decides

    strong_b = {"a": sheet.Evidence(score=1.0, confidence=0.9), "b": sheet.Evidence(score=2.0, confidence=0.9)}
    assert sheet.order(close, strong_b) == ["b", "a", "c"]  # 0.4 points apart and b's evidence is a level stronger

    unsure = {"a": sheet.Evidence(score=1.0, confidence=0.9), "b": sheet.Evidence(score=2.0, confidence=0.5)}
    assert sheet.order(close, unsure) == ["a", "b", "c"]  # Jev was not sure: no change

    strong_c = {"b": sheet.Evidence(score=0.0, confidence=0.9), "c": sheet.Evidence(score=3.0, confidence=0.9)}
    assert sheet.order(close, strong_c) == ["a", "b", "c"]  # ten points apart is not a near-tie


def test_jev_is_asked_once_per_change_and_never_blocks_the_sheet(loaded, client, monkeypatch):
    calls = []

    def decide(state, questions):
        calls.append(questions)
        return {key: {"type": "score", "score": 1.0, "confidence": 0.9} for key in questions}

    monkeypatch.setattr(sheet, "TIE_BAND", 1.0)  # every game counts as a near-tie in this test
    monkeypatch.setattr("nflpi.ai.jev.decide", decide)
    before = by_points(client)

    sheet.refresh_tiebreaks(loaded, CURRENT, WEEK)
    sheet.refresh_tiebreaks(loaded, CURRENT, WEEK)

    assert len(calls) == 1  # nothing changed between the two runs
    assert set(calls[0]) == set(before)  # one question per game, keyed by game id
    assert all(q["type"] == "score" and len(q["criteria"]) >= 3 for q in calls[0].values())
    assert by_points(client) == before  # equal evidence: order unchanged

    def down(state, questions):
        raise RuntimeError("Jev unavailable")

    monkeypatch.setattr("nflpi.ai.jev.decide", down)
    engine.refresh_predictions(loaded, now=datetime.now(UTC) + timedelta(minutes=1))
    sheet.refresh_tiebreaks(loaded, CURRENT, WEEK)  # must not raise
    assert sorted(r["my_points"] for r in sheets(client).values()) == [1, 2, 3]


def test_jev_is_not_asked_when_no_two_games_are_nearly_equal(loaded, client, monkeypatch):
    monkeypatch.setattr(sheet, "TIE_BAND", 0.0)
    monkeypatch.setattr("nflpi.ai.jev.decide", lambda state, questions: pytest.fail("Jev was asked"))
    sheet.refresh_tiebreaks(loaded, CURRENT, WEEK)
