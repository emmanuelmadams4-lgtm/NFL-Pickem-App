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

    # Kickoff reminders: off by default, then one per unpicked game inside the window.
    game = loaded.get(Game, gid)
    assert push.send_kickoff_reminders(loaded, game.kickoff_utc - timedelta(minutes=30)) == 0
    assert client.put("/api/settings", json={"reminder_minutes": 60}).json()["reminder_minutes"] == 60
    soon = game.kickoff_utc - timedelta(minutes=30)
    n = push.send_kickoff_reminders(loaded, soon)
    assert n >= 1 and push.send_kickoff_reminders(loaded, soon) == 0
    assert any(t.startswith("No pick yet") for t, _ in sent)
    assert client.request("DELETE", "/api/push/subscribe", params={"endpoint": sub["endpoint"]}).status_code == 204
    assert loaded.scalar(select(func.count()).select_from(PushSubscription)) == 0


def test_vapid_keys_have_web_push_shape():
    public, private = push.generate_vapid_keys()
    assert len(public) == 87 and len(private) == 43  # 65-byte point, 32-byte scalar, base64url
