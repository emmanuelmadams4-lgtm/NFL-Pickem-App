import json
from datetime import timedelta

from sqlalchemy import func, select

from nflpi.ai import research
from nflpi.api import schemas as s
from nflpi.models import AIReport, Game, PushSubscription
from nflpi.notify import push
from nflpi.predictions.engine import ChangeEvent
from tests.conftest import CURRENT


def test_auth_is_required(loaded, client):
    assert client.get("/api/health").status_code == 200
    bare = client.get("/api/meta", headers={"Authorization": ""})
    assert bare.status_code == 401
    assert client.get("/api/meta", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/meta").status_code == 200


def test_week_and_game_contracts(loaded, client):
    meta = client.get("/api/meta").json()
    assert (meta["current_season"], meta["current_week"]) == (CURRENT, 4)
    week = s.WeekOut.model_validate(client.get(f"/api/weeks/{CURRENT}/4").json())
    assert week.summary.games_total == 3 and all(g.prediction for g in week.games)
    gid = week.games[0].game_id
    detail = s.GameDetail.model_validate(client.get(f"/api/games/{gid}").json())
    assert detail.prediction_history and detail.market_history
    assert abs(detail.prediction.home_win_prob + detail.prediction.away_win_prob - 1) < 1e-9
    assert client.get("/api/games/nope").status_code == 404


def test_picks_lock_at_kickoff_and_csv_round_trip(loaded, client):
    future = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 4)).first()
    past = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 1)).first()
    assert client.put(f"/api/picks/{future.game_id}", json={"team": future.home_team}).status_code == 200
    assert client.put(f"/api/picks/{future.game_id}", json={"team": "XXX"}).status_code == 422
    assert client.put(f"/api/picks/{past.game_id}", json={"team": past.home_team}).status_code == 409

    csv_body = f"game_id,my_pick\n{past.game_id},{past.home_team}\nbad_id,BUF\n"
    res = client.post("/api/picks/import", content=csv_body).json()
    assert res == {"imported": 1, "skipped": ["bad_id"]}
    exported = client.get(f"/api/picks/export.csv?season={CURRENT}").text
    assert f"{future.game_id}" in exported and future.home_team in exported

    perf = s.PerformanceOut.model_validate(client.get(f"/api/performance/{CURRENT}").json())
    assert perf.me.total == 1  # only the finished, picked game counts
    assert perf.home.total == 9


class FakeProvider:
    name, model = "claude", "fake-model"

    def __init__(self, replies):
        self.replies = list(replies)

    def complete(self, system, user, json_schema=None, max_tokens=4000):
        assert "Evidence pack" in user
        return self.replies.pop(0)


def _report(pack, **over):
    p = pack["prediction"]
    body = {
        "game_id": pack["game"]["game_id"],
        "recommended_winner": p["pick"],
        "statistical_win_probability": p["pick_win_probability"],
        "headline": "Edge to the favorite",
        "supporting_factors": ["Higher Elo"],
        "opposing_factors": [],
        "injury_impact": "None listed",
        "rest_and_schedule": "Even rest",
        "weather_impact": "Mild",
        "market_view": "Agrees",
        "key_uncertainties": [],
        "what_would_change_the_pick": ["QB news"],
        "data_quality_warnings": [],
        "sources": ["prediction", "form.home"],
    }
    return json.dumps(body | over)


def test_ai_report_validates_and_retries(loaded):
    gid = loaded.scalars(select(Game.game_id).where(Game.season == CURRENT, Game.week == 4)).first()
    pack = research.evidence_pack(loaded, gid)
    bad = _report(pack, statistical_win_probability=0.99)
    out = research.generate_report(loaded, gid, provider=FakeProvider(["not json", bad, _report(pack)]))
    assert out.status == "ok" and out.report.recommended_winner == pack["prediction"]["pick"]

    fail = research.generate_report(loaded, gid, provider=FakeProvider([bad, bad, bad]))
    assert fail.status == "failed" and "statistical_win_probability" in fail.error
    assert loaded.scalar(select(AIReport).where(AIReport.status == "failed")) is not None


def test_ai_without_keys_returns_clear_error(loaded, client):
    gid = loaded.scalars(select(Game.game_id).where(Game.season == CURRENT, Game.week == 4)).first()
    r = client.post(f"/api/games/{gid}/ask", json={"question": "Who wins?", "provider": "jev"})
    assert r.status_code == 503 and "OPENROUTER_API_KEY" in r.json()["detail"]


def test_push_subscribe_alerts_and_reminders_are_deduplicated(loaded, client, monkeypatch):
    sent = []
    monkeypatch.setattr(push, "_send", lambda session, title, body, url, **kw: sent.append((title, url)) or 1)
    sub = {"endpoint": "https://web.push.apple.com/abc123", "keys": {"p256dh": "B" * 87, "auth": "a" * 22}}
    assert client.post("/api/push/subscribe", json=sub).status_code == 204
    assert client.post("/api/push/subscribe", json=sub).status_code == 204  # idempotent
    assert loaded.scalar(select(func.count()).select_from(PushSubscription)) == 1

    gid = loaded.scalars(select(Game.game_id).where(Game.season == CURRENT, Game.week == 4)).first()
    ev = ChangeEvent(gid, 0.6, 0.4, "BUF", "MIA", "QB out")
    assert push.alert_prediction_changes(loaded, [ev]) == 1
    assert push.alert_prediction_changes(loaded, [ev]) == 0
    assert sent[0][0].startswith("Pick flipped") and sent[0][1] == f"/game/?id={gid}"

    # Game-day reminder (D19): off at 0, then one per game day inside the window, whether or not he has picked.
    upcoming = select(Game.kickoff_utc).where(Game.status == "scheduled").order_by(Game.kickoff_utc)
    first = loaded.scalars(upcoming).first()
    soon = first - timedelta(minutes=30)
    assert client.put("/api/settings", json={"reminder_minutes": 0}).json()["reminder_minutes"] == 0
    assert push.send_kickoff_reminders(loaded, soon) == 0
    assert client.put("/api/settings", json={"reminder_minutes": 60}).json()["reminder_minutes"] == 60
    assert push.send_kickoff_reminders(loaded, soon) == 1 and push.send_kickoff_reminders(loaded, soon) == 0
    assert sent[-1][0].startswith("Game") and sent[-1][1] == "/sheet/"
    assert client.request("DELETE", "/api/push/subscribe", params={"endpoint": sub["endpoint"]}).status_code == 204
    assert loaded.scalar(select(func.count()).select_from(PushSubscription)) == 0


def test_vapid_keys_have_web_push_shape():
    public, private = push.generate_vapid_keys()
    assert len(public) == 87 and len(private) == 43  # 65-byte point, 32-byte scalar, base64url


# Step 8a2: star players and who is out, on the week board and the game view


def _seed_stars(session, game) -> None:
    from nflpi.models import InjuryReport, TeamStar

    def star(team, week, slot, rank, pid, player, position):
        return TeamStar(
            season=game.season, week=week, team=team, slot=slot, rank=rank, player_id=pid, player=player,
            position=position, snaps=1, production=1.0, score=1.0, source="test", computed_at=game.kickoff_utc,
        )  # fmt: skip

    def report(team, pid, player, status, hours):
        return InjuryReport(
            season=game.season, week=game.week, team=team, player_id=pid, player=player, position=None,
            report_status=status, practice_status=None, injury="Knee", source="nflverse",
            observed_at=game.kickoff_utc - timedelta(hours=hours),
        )  # fmt: skip

    home, away = game.home.abbr, game.away.abbr
    session.add_all(
        [
            star(home, game.week, "qb", 1, "00-001", "Pat Passer", "QB"),
            star(home, game.week, "off", 1, "00-003", "Ron\x07 Run‮ner", "RB"),  # a bell and a text-direction mark
            star(home, game.week, "off", 2, "00-004", "Cal Catch", "WR"),
            star(home, game.week, "def", 1, "00-009", "Cory Corner", "CB"),
            star(home, game.week, "def", 2, "00-008", "Russ Rush", "DE"),
            star(away, game.week - 1, "qb", 1, "00-041", "Stay Put", "QB"),  # the away club's list is a week older
            report(home, "00-003", "Ron Runner", "Out", 30),
            report(home, "00-004", "Cal Catch", "Questionable", 6),
            report(away, "00-041", "Stay Put", "Doubtful", 5),
            report(away, "00-777", "Not A Star", "Out", 5),
        ]
    )
    session.commit()


def test_week_board_says_which_stars_are_out_and_the_game_view_lists_all_of_them(loaded, client):
    before = s.WeekOut.model_validate(client.get(f"/api/weeks/{CURRENT}/4").json())
    game = before.games[0]
    assert (game.stars_out.out, game.stars_out.reports_seen) == ([], 0)  # nothing known yet: an empty line, said so
    assert game.stars_out.no_list == [game.away.abbr, game.home.abbr]  # neither club has a star list: said, away first

    _seed_stars(loaded, game)
    after = s.WeekOut.model_validate(client.get(f"/api/weeks/{CURRENT}/4").json())
    row = after.games[0]

    assert [(r.team, r.player, r.position, r.slot, r.status) for r in row.stars_out.out] == [
        (game.home.abbr, "Ron Runner", "RB", "off", "Out"),  # Out before Doubtful: the row names the first one
        (game.away.abbr, "Stay Put", "QB", "qb", "Doubtful"),  # control characters never reach the web (Ron Runner)
    ]
    assert row.stars_out.reports_seen == 4
    assert row.stars_out.no_list == []  # both clubs have a list now (the away club's is a week older)
    assert row.stars_out.out[0].observed_at == game.kickoff_utc - timedelta(hours=30)
    assert row.prediction == game.prediction and row.sheet == game.sheet  # a star out never moves the pick (D24)
    clubs = {game.away.abbr, game.home.abbr}
    for other in after.games[1:]:  # another game lists a star only when his club plays in it
        playing = {other.away.abbr, other.home.abbr}
        assert {r.team for r in other.stars_out.out} <= playing & clubs

    detail = s.GameDetail.model_validate(client.get(f"/api/games/{game.game_id}").json())
    away, home = detail.stars
    assert (away.team, away.stars_week, [r.player for r in away.stars]) == (game.away.abbr, game.week - 1, ["Stay Put"])
    assert (home.team, home.stars_week) == (game.home.abbr, game.week)
    assert [(r.slot, r.rank, r.player, r.status) for r in home.stars] == [
        ("qb", 1, "Pat Passer", None),
        ("off", 1, "Ron Runner", "Out"),
        ("off", 2, "Cal Catch", "Questionable"),
        ("def", 1, "Cory Corner", None),
        ("def", 2, "Russ Rush", None),
    ]
    assert [r.listed for r in home.stars] == [False, True, True, False, False]  # on this week's report or not
    assert detail.stars_out == row.stars_out


def test_a_star_quarterback_named_in_the_qb_alert_is_marked_by_the_api_whatever_the_spelling(loaded, client):
    from nflpi.models import InjuryReport

    game = s.WeekOut.model_validate(client.get(f"/api/weeks/{CURRENT}/4").json()).games[0]
    _seed_stars(loaded, game)

    def qb(pid, player, hours):
        return InjuryReport(
            season=game.season, week=game.week, team=game.home.abbr, player_id=pid, player=player, position="QB",
            report_status="Out", practice_status=None, injury="Ankle", source="nflverse",
            observed_at=game.kickoff_utc - timedelta(hours=hours),
        )  # fmt: skip

    # two backups first, then the star, whose name the injury report spells another way
    loaded.add_all([qb("00-801", "Backup One", 9), qb("00-802", "Backup Two", 8), qb("00-001", "Patrick Passer", 7)])
    loaded.commit()

    row = s.WeekOut.model_validate(client.get(f"/api/weeks/{CURRENT}/4").json()).games[0]
    marked = {r.player: r.qb_alert for r in row.stars_out.out}
    assert marked == {"Stay Put": False, "Pat Passer": True, "Ron Runner": False}  # Stay Put's report has no position
    # the web shows the first two alerts: the star's is one of them, so he is never hidden from both lines
    assert row.qb_alerts[0] == f"{game.home.abbr} QB Patrick Passer: Out" and len(row.qb_alerts) == 3
    detail = s.GameDetail.model_validate(client.get(f"/api/games/{game.game_id}").json())
    assert [r.qb_alert for r in detail.stars[1].stars] == [True, False, False, False, False]


def test_the_worker_refreshes_the_star_list_and_a_failure_does_not_stop_the_round(loaded, monkeypatch):
    from types import SimpleNamespace

    from nflpi import jobs
    from nflpi.ingestion import service

    seen = []
    ok = SimpleNamespace(status="ok")
    monkeypatch.setattr(service, "ingest_schedules", lambda session: ok)
    monkeypatch.setattr(service, "ingest_teams", lambda session: ok)
    monkeypatch.setattr(service, "ingest_injuries", lambda session, season: (ok, []))
    def stars(session, season):
        seen.append(season)
        return SimpleNamespace(status="failed")

    monkeypatch.setattr(service, "ingest_stars", stars)

    out = jobs.ingest(loaded, weather=False)

    assert seen == [CURRENT]  # this season's list, once per round
    assert out["stars"] == "failed" and out["injuries"] == "ok" and "qb_alerts" in out  # the round went on

    def broken(session, season):
        raise RuntimeError("no network")

    monkeypatch.setattr(service, "ingest_stars", broken)
    out = jobs.ingest(loaded, weather=False)
    assert out["stars"] == "failed" and out["injuries"] == "ok" and "qb_alerts" in out  # a crash: the same


def test_freshness_lists_the_star_list_and_the_head_coaches(loaded, client):
    from nflpi.ingestion.service import run_logged

    rows = {d["dataset"]: d for d in client.get("/api/freshness").json()}
    assert {"stars", "head_coaches"} <= set(rows)
    assert rows["stars"]["stale"] and rows["stars"]["last_success"] is None  # never refreshed: said, not hidden

    run_logged(loaded, "nflverse", "stars", lambda: 160)
    run_logged(loaded, "espn", "head_coaches", lambda: 32)
    rows = {d["dataset"]: d for d in client.get("/api/freshness").json()}
    assert not rows["stars"]["stale"] and not rows["head_coaches"]["stale"]
