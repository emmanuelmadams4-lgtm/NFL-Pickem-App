"""Step 18k: the maths check report and the Claude PASS/FAIL gate on each simulation run (PLAN section 5, D74).

Claude is always a fake here. The check can only block a run; it never edits a number.
"""

import copy
import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from nflpi.ai import run_checker
from nflpi.ai.providers import AIError
from nflpi.analytics import run_check
from nflpi.analytics.manifest import run_record
from nflpi.config import get_settings
from nflpi.models import AppSetting, MarketSnapshot, Prediction
from nflpi.predictions import engine
from tests.test_wiring import CURRENT, N, latest, synthetic_params, upcoming


def now():
    """The fixture's market lines are stamped with the real clock, so a run 'at' a fixed past date fails the cutoff."""
    return datetime.now(UTC)


class FakeClaude:
    name, model = "claude", "fake"

    def __init__(self, reply="PASS"):
        self.reply, self.calls = reply, []

    def complete(self, system, user, json_schema=None, max_tokens=16000):
        self.calls.append((system, user))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


@pytest.fixture
def claude(monkeypatch):
    fake = FakeClaude()
    monkeypatch.setattr(run_checker, "get_provider", lambda name: fake)
    return fake


def good_sim(**over):
    sim = {
        "n_simulations": N, "home_win": 0.6, "away_win": 0.38, "tie": 0.02, "home_points": 24.0, "away_points": 21.0,
        "expected_margin": 3.01, "expected_total": 45.02, "margin_80": [-14.0, 20.0], "total_80": [30.0, 60.0],
        "home_spread": -3.0, "total": 45.0, "home_cover": 0.5, "away_cover": 0.45, "spread_push": 0.05,
        "over": 0.5, "under": 0.45, "total_push": 0.05,
    }
    return sim | over


def present(**over):
    inputs = {name: {"present": True, "observed_before_cutoff": None} for name in run_check.INPUTS}
    inputs["elo_diff"]["observed_before_cutoff"] = True
    inputs["market_logit"]["observed_before_cutoff"] = True
    return inputs | over


def check(sim=None, inputs=None, spread_line=3.0):
    return run_check.check_game("g1", good_sim() if sim is None else sim, inputs or present(), spread_line)


# 1 the report is maths only: each check fails on its own ----------------------------------------------------------

def test_a_clean_game_passes_every_check():
    entry = check()
    assert entry["ok"] and entry["problems"] == [] and entry["n_simulations"] == N


@pytest.mark.parametrize("sim, word", [
    (good_sim(n_simulations=9_999), "n_simulations"),
    (good_sim(home_win=0.7), "win+tie+loss"),
    (good_sim(home_cover=0.6), "cover+push"),
    (good_sim(over=0.6), "over+push"),
    (good_sim(home_spread=3.0), "spread sign"),
    (good_sim(expected_margin=9.0), "mean margin"),
    (good_sim(expected_total=60.0), "mean total"),
])
def test_each_broken_number_is_named(sim, word):
    entry = check(sim)
    assert not entry["ok"] and any(word in p for p in entry["problems"])


def test_a_mean_inside_sampling_error_is_fine():
    assert check(good_sim(expected_margin=3.2))["ok"]


def test_overtime_may_lift_the_total_a_little_but_nothing_else_may_move_it():
    assert check(good_sim(expected_total=45.4))["ok"]  # overtime adds points on top of the expected points
    assert not check(good_sim(expected_total=46.5))["ok"]
    assert not check(good_sim(expected_total=44.0))["ok"]  # overtime never takes points away


def test_a_missing_line_leaves_cover_and_total_fields_missing_not_failed():
    sim = good_sim(home_spread=None, total=None, home_cover=None, away_cover=None, spread_push=None, over=None,
                   under=None, total_push=None)
    entry = check(sim, spread_line=None)
    assert entry["ok"] and entry["sums"]["cover_push"] is None and entry["sums"]["over_push"] is None


def test_a_cover_chance_without_a_line_fails():
    assert not check(good_sim(home_spread=None), spread_line=None)["ok"]


def test_missing_inputs_are_marked_and_an_input_seen_after_the_cutoff_fails():
    inputs = present(market_logit={"present": False, "observed_before_cutoff": None})
    entry = check(inputs=inputs)
    assert entry["ok"] and entry["inputs"]["market_logit"]["status"] == "missing"
    assert set(entry["inputs"]) == set(run_check.INPUTS)
    late = present(market_logit={"present": True, "observed_before_cutoff": False})
    assert any("market_logit" in p for p in check(inputs=late)["problems"])


def test_a_simulation_without_the_rating_input_fails():
    inputs = present(elo_diff={"present": False, "observed_before_cutoff": None})
    assert not check(inputs=inputs)["ok"]


def test_a_game_without_a_simulation_is_listed_and_does_not_fail_the_run():
    report = run_check.build_report({"g1": check(), "g2": run_check.check_game("g2", None, present(), 3.0)})
    assert report["all_ok"] and report["n_simulated"] == 1 and report["games"][1]["has_simulation"] is False


# 2 the reply is parsed strictly ------------------------------------------------------------------------------------

@pytest.mark.parametrize("text, status", [
    ("PASS", "PASS"), ("PASS\nAll 12 games are consistent.", "PASS"), ("  PASS \n", "PASS"),
    ("FAIL\n- g1: spread sign flipped", "FAIL"), ("FAIL", "FAIL"),
])
def test_a_verdict_is_read_from_the_first_line(text, status):
    assert run_check.parse_verdict(text).status == status


@pytest.mark.parametrize("text", [
    "", "pass", "Pass", "PASSED", "PASS.", "The run looks fine. PASS", "I think PASS", "```PASS```", "FAILED",
    "PASS\nFAIL: g1 is wrong", "maybe", '{"verdict": "PASS"}',
])
def test_anything_else_is_no_verdict(text):
    assert run_check.parse_verdict(text).status is None


def test_fail_reasons_are_kept_short():
    verdict = run_check.parse_verdict("FAIL\n" + "x" * 5_000)
    assert verdict.status == "FAIL" and len(" ".join(verdict.reasons)) <= run_check.REASON_MAX


# 3 the run record carries the simulation count and inputs used per game ----------------------------------------------

def test_run_record_lists_simulations_and_inputs_per_game(tmp_path):
    games = {"g1": {"n_simulations": N, "inputs_used": ["elo_diff"]}}
    kwargs = dict(model="m", label="l", seed=1, seed_note=None, cutoff_rule="r", latest_kickoff=None, n_games=1,
                  seasons=[2026], uses_closing_line=False, data_files={}, repo_root=tmp_path)
    assert run_record(**kwargs, games=games)["games"] == games
    assert "games" not in run_record(**kwargs)  # older callers keep a byte-identical record


# 4 the gate in the live path ----------------------------------------------------------------------------------------

def simulate(session, now=None):
    engine.save_sim_params(session, CURRENT, synthetic_params())
    engine.refresh_predictions(session, now=now)


def change_run(session):
    """New total lines change every simulation and no win probability, pick or confidence point."""
    for g in upcoming(session):
        last = session.scalars(select(MarketSnapshot).where(MarketSnapshot.game_id == g.game_id)
                               .order_by(MarketSnapshot.id.desc())).first()
        session.add(MarketSnapshot(
            game_id=g.game_id, observed_at=last.observed_at + timedelta(microseconds=1), source=last.source,
            kind=last.kind,
            home_moneyline=last.home_moneyline, away_moneyline=last.away_moneyline, spread_line=last.spread_line,
            total_line=last.total_line + 1, home_prob_novig=last.home_prob_novig))
    session.commit()


def sims(session):
    return {g.game_id: latest(session, g.game_id).features["simulation"] for g in upcoming(session)}


def test_a_pass_stores_the_run_and_marks_nothing(loaded, claude):
    simulate(loaded)
    assert len(claude.calls) == 1  # one request covers the whole run
    assert all(s and s["n_simulations"] == N for s in sims(loaded).values())
    assert all("simulation_check" not in latest(loaded, g.game_id).features for g in upcoming(loaded))


def test_the_request_holds_the_record_and_report_and_nothing_secret(loaded, claude):
    simulate(loaded)
    system, user = claude.calls[0]
    body = json.loads(user[user.index("{"):])
    assert len(body["report"]["games"]) == len(upcoming(loaded)) and body["report"]["all_ok"]
    game = body["report"]["games"][0]
    assert game["n_simulations"] == N and set(game["inputs"]) == set(run_check.INPUTS)
    assert body["record"]["games"][game["game_id"]]["n_simulations"] == N
    assert "elo_diff" in body["record"]["games"][game["game_id"]]["inputs_used"]
    assert "PASS" in system and "FAIL" in system and "data" in system.lower()
    assert "token" not in user.lower() and "api_key" not in user.lower()


def test_an_unchanged_run_reuses_the_stored_verdict(loaded, claude):
    simulate(loaded)
    engine.refresh_predictions(loaded, now=now() + timedelta(days=1))
    assert len(claude.calls) == 1


def test_a_changed_run_is_checked_again(loaded, claude):
    simulate(loaded)
    change_run(loaded)
    engine.refresh_predictions(loaded)
    assert len(claude.calls) == 2


def test_a_fail_keeps_the_last_checked_run_and_says_so(loaded, claude):
    simulate(loaded)
    kept = sims(loaded)
    wins = {g.game_id: (latest(loaded, g.game_id).pick, latest(loaded, g.game_id).home_win_prob)
            for g in upcoming(loaded)}
    claude.reply = "FAIL\n- g1: spread sign flipped"
    change_run(loaded)
    engine.refresh_predictions(loaded)
    for g in upcoming(loaded):
        p = latest(loaded, g.game_id)
        assert p.features["simulation"] == kept[g.game_id]  # the last checked run, not the failed one
        assert p.features["simulation_check"]["status"] == "failed"
        assert "spread sign flipped" in p.features["simulation_check"]["note"]
        assert (p.pick, p.home_win_prob) == wins[g.game_id]  # the check never touches the picks


@pytest.mark.parametrize("reply", ["maybe?", "", AIError("Claude is not configured")])
def test_no_verdict_blocks_the_run_like_a_fail(loaded, claude, reply):
    simulate(loaded)
    kept = sims(loaded)
    claude.reply = reply
    change_run(loaded)
    engine.refresh_predictions(loaded)
    p = latest(loaded, upcoming(loaded)[0].game_id)
    assert p.features["simulation"] == kept[p.game_id] and p.features["simulation_check"]["status"] == "no_verdict"


def test_a_first_run_that_fails_has_no_simulation_but_keeps_every_pick(loaded, claude):
    claude.reply = "FAIL\n- n_simulations is 9999"
    simulate(loaded)
    for g in upcoming(loaded):
        p = latest(loaded, g.game_id)
        assert p.features["simulation"] is None and p.features["simulation_check"]["status"] == "failed"
        assert p.pick and 0 < p.home_win_prob < 1


def test_without_a_claude_setup_the_simulation_is_not_used(loaded, monkeypatch):
    def refuse(name):
        raise AIError("Claude is not configured")

    monkeypatch.setattr(run_checker, "get_provider", refuse)
    simulate(loaded)
    assert all(v is None for v in sims(loaded).values())


def test_no_verdict_is_retried_after_a_pause_not_on_every_run(loaded, claude):
    claude.reply = AIError("down")
    simulate(loaded, now=now())
    engine.refresh_predictions(loaded, now=now() + timedelta(minutes=5))
    assert len(claude.calls) == 1
    engine.refresh_predictions(loaded, now=now() + run_checker.RETRY_AFTER + timedelta(minutes=1))
    assert len(claude.calls) == 2


def test_a_recovered_check_clears_the_mark(loaded, claude):
    claude.reply = "FAIL\n- bad"
    simulate(loaded)
    claude.reply = "PASS"
    change_run(loaded)
    engine.refresh_predictions(loaded)
    p = latest(loaded, upcoming(loaded)[0].game_id)
    assert p.features["simulation"] and "simulation_check" not in p.features


def test_no_simulations_means_no_claude_call(loaded, claude):
    engine.refresh_predictions(loaded)
    assert claude.calls == []


def test_the_verdict_is_stored_by_content_hash(loaded, claude):
    simulate(loaded)
    row = loaded.get(AppSetting, run_checker.SETTING_KEY)
    assert row.value["verdict"] == "PASS" and len(row.value["hash"]) == 64


def test_the_api_says_the_check_blocked_the_run(loaded, claude, client):
    claude.reply = "FAIL\n- bad"
    simulate(loaded)
    game = upcoming(loaded)[0]
    pred = client.get(f"/api/games/{game.game_id}").json()["prediction"]
    assert pred["simulation"] is None and pred["simulation_check"]["status"] == "failed"
    assert latest(loaded, game.game_id).id == pred["id"]
    assert loaded.scalars(select(Prediction).where(Prediction.game_id == game.game_id)).first()


def test_the_check_report_is_deterministic():
    a = run_check.build_report({"g1": check()})
    assert a == run_check.build_report({"g1": copy.deepcopy(check())})
    assert run_check.content_hash({"r": 1}, a, {"g1": good_sim()}) == run_check.content_hash(
        {"r": 1}, a, {"g1": good_sim()})
    assert run_check.content_hash({"r": 1}, a, {"g1": good_sim()}) != run_check.content_hash(
        {"r": 1}, a, {"g1": good_sim(home_win=0.61)})


# 5 critic fixes (M1-M4) ---------------------------------------------------------------------------------------------


def test_a_python_failed_report_blocks_the_run_without_asking_claude(loaded, claude, monkeypatch):
    real = run_check.check_game
    monkeypatch.setattr(run_check, "check_game", lambda gid, sim, inputs, line: real(
        gid, dict(sim, n_simulations=9_999) if sim else sim, inputs, line))
    engine.save_sim_params(loaded, CURRENT, synthetic_params())
    engine.refresh_predictions(loaded)  # Claude would say PASS; Python blocked first
    assert claude.calls == []
    p = latest(loaded, upcoming(loaded)[0].game_id)
    assert p.features["simulation"] is None and p.features["simulation_check"]["status"] == "failed"
    assert "n_simulations" in p.features["simulation_check"]["note"]


def test_a_database_error_in_the_budget_step_leaves_the_session_usable(loaded, claude, monkeypatch):
    def boom(session):
        session.execute(text("select * from table_that_does_not_exist"))

    monkeypatch.setattr(run_checker, "_reserve_check_call", boom)
    simulate(loaded)  # would raise "transaction is aborted" later without the rollback
    p = latest(loaded, upcoming(loaded)[0].game_id)
    assert p.features["simulation"] is None and p.features["simulation_check"]["status"] == "no_verdict"
    assert loaded.scalars(select(Prediction)).first()


def test_a_backfill_run_is_not_sent_to_claude_and_says_why(loaded, claude):
    engine.save_sim_params(loaded, CURRENT, synthetic_params())
    engine.refresh_predictions(loaded, kind="backfill")
    assert claude.calls == []
    p = latest(loaded, upcoming(loaded)[0].game_id)
    assert p.features["simulation"] is None
    assert p.features["simulation_check"]["status"] == "not_checked"
    assert "backfill" in p.features["simulation_check"]["note"]


def test_the_check_has_its_own_daily_budget_apart_from_reports(loaded, claude, monkeypatch):
    monkeypatch.setenv("AI_RUN_CHECK_DAILY_LIMIT", "1")
    get_settings.cache_clear()
    try:
        simulate(loaded)
        change_run(loaded)
        engine.refresh_predictions(loaded)  # second changed run: the check budget is spent
        assert len(claude.calls) == 1
        p = latest(loaded, upcoming(loaded)[0].game_id)
        assert p.features["simulation_check"]["status"] == "no_verdict"
        monkeypatch.setenv("AI_DAILY_CALL_LIMIT", "0")  # and a spent report budget does not touch the check
        get_settings.cache_clear()
        monkeypatch.setenv("AI_RUN_CHECK_DAILY_LIMIT", "5")
        get_settings.cache_clear()
        engine.refresh_predictions(loaded, now=now() + timedelta(hours=7))
        assert len(claude.calls) == 2
    finally:
        get_settings.cache_clear()


def test_a_check_does_not_use_the_report_counter(loaded, claude):
    simulate(loaded)
    keys = [r.key for r in loaded.scalars(select(AppSetting)) if "attempts" in r.key]
    assert keys and all(not k.startswith("ai_attempts_") for k in keys)


def test_repeated_failures_back_off_longer_each_time(loaded, claude):
    claude.reply = AIError("down")
    simulate(loaded, now=now())
    engine.refresh_predictions(loaded, now=now() + run_checker.RETRY_AFTER + timedelta(minutes=1))
    assert len(claude.calls) == 2  # first retry after the base pause
    engine.refresh_predictions(loaded, now=now() + 2 * run_checker.RETRY_AFTER + timedelta(minutes=2))
    assert len(claude.calls) == 2  # second failure doubles the pause
    engine.refresh_predictions(loaded, now=now() + 5 * run_checker.RETRY_AFTER)
    assert len(claude.calls) == 3


def test_the_api_serves_a_backfill_run_that_was_not_checked(loaded, claude, client):
    engine.save_sim_params(loaded, CURRENT, synthetic_params())
    engine.refresh_predictions(loaded, kind="backfill")
    game = upcoming(loaded)[0]
    pred = client.get(f"/api/games/{game.game_id}").json()["prediction"]
    assert pred["simulation"] is None and pred["simulation_check"]["status"] == "not_checked"
