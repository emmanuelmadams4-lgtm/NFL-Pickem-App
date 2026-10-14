"""Step 18h: the simulator and the pick mode in the live path (docs/model/PLAN.md row 18h, owner decision D74)."""

import zlib
from dataclasses import replace

import numpy as np
import pytest
from sqlalchemy import func, select, update

from nflpi import jobs
from nflpi.analytics.sim_backtest import BASE_SEED
from nflpi.api import schemas as s
from nflpi.config import Settings, get_settings
from nflpi.ingestion import nflverse, service
from nflpi.models import AppSetting, Game, MarketSnapshot, Prediction
from nflpi.picks.rules import ASSUMED_LABEL
from nflpi.predictions import engine
from nflpi.predictions.elo import EloParams
from nflpi.predictions.scores import STATS_FEATURES, ScoreModel, add_score_features
from nflpi.sim import TeamFeatures, learn_params, simulate_game
from nflpi.sim import params as sim_params
from tests.conftest import CURRENT, schedule_rows, team_rows

N = 10_000


def synthetic_params(season: int = CURRENT):
    """Learned from 300 made-up games: 40 went to overtime, 10 of those stayed tied."""
    rng = np.random.default_rng(7)
    mu_a, mu_b = rng.uniform(18, 28, 300), rng.uniform(16, 26, 300)
    a, b = rng.poisson(mu_a), rng.poisson(mu_b)
    overtime = np.zeros(300, dtype=int)
    overtime[:40] = 1
    b[:10] = a[:10]
    b[10:40] = a[10:40] + 3
    return learn_params(mu_a, mu_b, a, b, overtime, np.full(300, season - 1), season)


def upcoming(session) -> list[Game]:
    return session.scalars(select(Game).where(Game.season == CURRENT, Game.status != "final")
                           .order_by(Game.kickoff_utc, Game.game_id)).all()


def latest(session, game_id: str) -> Prediction:
    return session.scalars(select(Prediction).where(Prediction.game_id == game_id)
                           .order_by(Prediction.id.desc())).first()


def count(session) -> int:
    return session.scalar(select(func.count()).select_from(Prediction))


def simulated(session) -> None:
    engine.save_sim_params(session, CURRENT, synthetic_params())
    engine.refresh_predictions(session)


# W1 the simulation is stored beside the win probability --------------------------------------------------------------

def test_simulation_is_stored_beside_the_unchanged_win_probability(loaded):
    before = {g.game_id: latest(loaded, g.game_id).home_win_prob for g in upcoming(loaded)}
    simulated(loaded)
    for gid, prob in before.items():
        p = latest(loaded, gid)
        sim = p.features["simulation"]
        assert p.home_win_prob == prob  # the win model still decides the pick
        assert (sim["source"], sim["distribution"], sim["n_simulations"]) == ("football_only", "paired_residual", N)
        assert sim["home_win"] + sim["away_win"] + sim["tie"] == pytest.approx(1, abs=1e-3)
        assert (sim["home_spread"], sim["total"]) == (-3.0, 45.5)  # nflverse spread_line 3: home favoured by 3
        assert sim["home_cover"] + sim["away_cover"] + sim["spread_push"] == pytest.approx(1, abs=1e-3)
        assert sim["over"] + sim["under"] + sim["total_push"] == pytest.approx(1, abs=1e-3)
        assert sim["margin_80"][0] <= sim["expected_margin"] <= sim["margin_80"][1]
        assert sim["total_80"][0] <= sim["expected_total"] <= sim["total_80"][1]
        assert sim["label"]


# W2 bench and live agree: the stored numbers are the simulator on the stored, walk-forward inputs ---------------------

def test_stored_simulation_is_the_simulator_on_walk_forward_expected_points(loaded):
    simulated(loaded)
    frame = add_score_features(engine.load_frame(loaded), EloParams())
    model = ScoreModel.fit(frame[frame["season"].between(CURRENT - 10, CURRENT - 1)], STATS_FEATURES)
    for g in upcoming(loaded):
        sim = latest(loaded, g.game_id).features["simulation"]
        home, away = model.predict(frame[frame["game_id"] == g.game_id])
        assert (sim["home_points"], sim["away_points"]) == pytest.approx((home[0], away[0]), abs=1e-3)
        res = simulate_game(TeamFeatures(home[0]), TeamFeatures(away[0]), N, params=synthetic_params(),
                            seed=zlib.crc32(g.game_id.encode()) ^ BASE_SEED, spread=-3.0, total=45.5)
        assert sim["home_win"] == pytest.approx(res.p_a_win, abs=1e-3)
        assert sim["tie"] == pytest.approx(res.p_tie, abs=1e-3)
        assert sim["home_cover"] == pytest.approx(res.p_a_cover, abs=1e-3)
        assert sim["spread_push"] == pytest.approx(res.p_spread_push, abs=1e-3)
        assert sim["over"] == pytest.approx(res.p_over, abs=1e-3)
        assert sim["expected_margin"] == pytest.approx(res.expected_margin, abs=1e-3)
        assert sim["expected_total"] == pytest.approx(res.expected_total, abs=1e-3)


# W3 missing stays missing -------------------------------------------------------------------------------------------

def test_without_learned_parameters_the_simulation_is_missing_not_guessed(loaded, client):
    assert all(latest(loaded, g.game_id).features["simulation"] is None for g in upcoming(loaded))
    week = s.WeekOut.model_validate(client.get(f"/api/weeks/{CURRENT}/4").json())
    assert all(g.prediction and g.prediction.simulation is None for g in week.games)


def test_a_game_without_a_line_gets_win_chances_but_no_cover_or_total_chances(loaded):
    gid = upcoming(loaded)[0].game_id
    no_line = update(MarketSnapshot).where(MarketSnapshot.game_id == gid).values(spread_line=None, total_line=None)
    loaded.execute(no_line)
    loaded.commit()
    simulated(loaded)
    sim = latest(loaded, gid).features["simulation"]
    assert sim["home_win"] > 0 and sim["home_spread"] is None and sim["total"] is None
    assert [sim[k] for k in ("home_cover", "away_cover", "spread_push", "over", "under", "total_push")] == [None] * 6


def test_a_season_without_parameters_gets_no_simulation_when_another_season_has_them(loaded):
    engine.save_sim_params(loaded, CURRENT, synthetic_params())
    past = loaded.scalars(select(Game).where(Game.season == CURRENT - 1)).first().game_id
    now = upcoming(loaded)[0].game_id
    engine.refresh_predictions(loaded, game_ids=[past, now], kind="backfill")
    assert latest(loaded, past).features["simulation"] is None
    assert latest(loaded, now).features["simulation"] is not None


# W4 insert-only ------------------------------------------------------------------------------------------------------

def test_adding_parameters_inserts_one_new_row_per_game_and_never_edits_old_rows(loaded):
    old = {p.id: (p.inputs_hash, dict(p.features), p.home_win_prob) for p in loaded.scalars(select(Prediction))}
    simulated(loaded)
    engine.refresh_predictions(loaded)  # same inputs again: nothing new
    loaded.expire_all()
    assert count(loaded) == len(old) + len(upcoming(loaded))
    assert {p.id: (p.inputs_hash, p.features, p.home_win_prob)
            for p in loaded.scalars(select(Prediction).where(Prediction.id.in_(old)))} == old


# W5 no leak: a game's own result never reaches its simulation -------------------------------------------------------

def test_a_games_own_result_does_not_reach_its_simulation(loaded):
    engine.save_sim_params(loaded, CURRENT, synthetic_params())
    game = loaded.scalars(select(Game).where(Game.season == CURRENT, Game.week == 3)).first()
    engine.refresh_predictions(loaded, game_ids=[game.game_id], kind="backfill")
    first = latest(loaded, game.game_id)
    game.home_score, game.away_score = game.away_score + 40, 0
    loaded.commit()
    engine.refresh_predictions(loaded, game_ids=[game.game_id], kind="backfill")
    assert latest(loaded, game.game_id).id == first.id and first.features["simulation"] is not None


# W6 playoff games never end tied ----------------------------------------------------------------------------------

def test_playoff_games_never_end_tied_and_regular_season_games_can(loaded):
    games = upcoming(loaded)
    games[0].game_type = "WC"
    loaded.commit()
    simulated(loaded)
    assert latest(loaded, games[0].game_id).features["simulation"]["tie"] == 0
    assert latest(loaded, games[1].game_id).features["simulation"]["tie"] > 0


# W7 `jobs train` learns the parameters for the season it predicts -------------------------------------------------

def _overtime_rows() -> list[dict]:
    rows = schedule_rows()
    for i, row in enumerate(rows):
        row["overtime"] = "1" if row["home_score"] and i % 7 == 0 else "0"
    return rows


def test_train_learns_and_saves_simulator_parameters_for_the_season_it_predicts(session, monkeypatch):
    monkeypatch.setattr(sim_params, "MIN_TRAIN_GAMES", 10)  # the fixture has five past seasons of 15 games
    monkeypatch.setattr(nflverse, "fetch_csv", lambda path: _overtime_rows())
    service.ingest_schedules(session, schedule_rows())
    service.ingest_teams(session, team_rows())
    jobs.train(session)
    params = engine.load_sim_params(session, CURRENT)
    assert params is not None and params.n_train > 10 and params.ot_era == "modified_10"
    assert engine.load_sim_params(session, CURRENT - 1) is None
    engine.refresh_predictions(session)
    assert all(latest(session, g.game_id).features["simulation"] for g in upcoming(session))


def test_train_still_trains_the_win_model_when_the_simulator_cannot_learn(session, monkeypatch):
    def offline(path):
        raise OSError("no network")

    monkeypatch.setattr(nflverse, "fetch_csv", offline)
    service.ingest_schedules(session, schedule_rows())
    service.ingest_teams(session, team_rows())
    assert jobs.train(session).is_active
    assert engine.load_sim_params(session, CURRENT) is None


def test_saved_parameters_round_trip_exactly(session):
    params = synthetic_params()
    engine.save_sim_params(session, CURRENT, replace(params, n_train=1, ot_era="older"))
    engine.save_sim_params(session, CURRENT, params)  # a retrain replaces the season's parameters
    back = engine.load_sim_params(session, CURRENT)
    for field in ("residual_a", "residual_b", "ot_increments"):
        assert np.array_equal(getattr(back, field), getattr(params, field))
    for field in ("phi_a", "phi_b", "rho", "v", "v_shared", "ot_tie_frac", "ot_era", "ot_era_fallback", "n_train"):
        assert getattr(back, field) == getattr(params, field)


# W8 the API exposes the simulation and the pick mode ------------------------------------------------------------------

def test_api_exposes_the_stored_simulation(loaded, client):
    simulated(loaded)
    gid = upcoming(loaded)[0].game_id
    detail = s.GameDetail.model_validate(client.get(f"/api/games/{gid}").json())
    assert detail.prediction.simulation.model_dump() == latest(loaded, gid).features["simulation"]


def test_pick_mode_is_straight_up_and_labelled_assumed_by_default(loaded, client):
    week = s.WeekOut.model_validate(client.get(f"/api/weeks/{CURRENT}/4").json())
    assert week.pick_mode.mode == "straight_up" and week.pick_mode.assumed
    assert week.pick_mode.label.startswith(ASSUMED_LABEL)


def test_a_configured_pick_mode_is_shown_and_not_labelled_assumed(loaded, client, monkeypatch):
    monkeypatch.setenv("PICK_MODE", "confidence_pool")
    get_settings.cache_clear()
    try:
        week = s.WeekOut.model_validate(client.get(f"/api/weeks/{CURRENT}/4").json())
    finally:
        monkeypatch.delenv("PICK_MODE")
        get_settings.cache_clear()
    assert (week.pick_mode.mode, week.pick_mode.assumed) == ("confidence_pool", False)
    assert week.pick_mode.label.startswith("Confidence pool")


# X5 the label says both modes use one order ---------------------------------------------------------------------------

def test_pick_mode_label_says_both_modes_use_the_same_order(loaded, client):
    week = s.WeekOut.model_validate(client.get(f"/api/weeks/{CURRENT}/4").json())
    assert "same order" in week.pick_mode.label and "win chance, then game id" in week.pick_mode.label


def test_pick_modes_the_sheet_cannot_show_are_refused():
    with pytest.raises(ValueError):
        Settings(pick_mode="ats")


# X1 the simulator is optional: no simulator fault stops prediction rows --------------------------------------------

def all_games_have_rows(session) -> bool:
    return all(latest(session, g.game_id) is not None for g in upcoming(session))


def test_a_malformed_stored_parameter_row_gives_no_simulation_but_all_predictions(loaded):
    loaded.add(AppSetting(key=f"sim_params_{CURRENT}", value={"unexpected": 1}))
    loaded.commit()
    assert engine.load_sim_params(loaded, CURRENT) is None
    engine.refresh_predictions(loaded)
    assert all_games_have_rows(loaded)
    assert all(latest(loaded, g.game_id).features["simulation"] is None for g in upcoming(loaded))


def test_one_game_whose_simulation_raises_is_stored_as_none_and_the_rest_survive(loaded, monkeypatch):
    engine.save_sim_params(loaded, CURRENT, synthetic_params())
    bad = upcoming(loaded)[0].game_id
    real = engine.simulate_game

    def flaky(*a, seed=None, **kw):
        if seed == zlib.crc32(bad.encode()) ^ BASE_SEED:
            raise RuntimeError("boom")
        return real(*a, seed=seed, **kw)

    monkeypatch.setattr(engine, "simulate_game", flaky)
    engine.refresh_predictions(loaded)
    assert all_games_have_rows(loaded)
    assert latest(loaded, bad).features["simulation"] is None
    assert all(latest(loaded, g.game_id).features["simulation"] is not None for g in upcoming(loaded)[1:])


def test_a_score_model_fit_that_raises_still_writes_every_prediction(loaded, monkeypatch):
    engine.save_sim_params(loaded, CURRENT, synthetic_params())

    def broken(*a, **kw):
        raise RuntimeError("fit failed")

    monkeypatch.setattr(engine.ScoreModel, "fit", broken)
    engine.refresh_predictions(loaded)
    assert all_games_have_rows(loaded)
    assert all(latest(loaded, g.game_id).features["simulation"] is None for g in upcoming(loaded))


# X4 a simulation the API could not serve is never stored ---------------------------------------------------------

def test_a_nan_simulation_is_stored_as_none_and_the_week_still_answers(loaded, client, monkeypatch):
    engine.save_sim_params(loaded, CURRENT, synthetic_params())
    real = engine.simulate_game
    monkeypatch.setattr(engine, "simulate_game",
                        lambda *a, **kw: replace(real(*a, **kw), p_a_win=float("nan")))
    engine.refresh_predictions(loaded)
    assert all(latest(loaded, g.game_id).features["simulation"] is None for g in upcoming(loaded))
    assert client.get(f"/api/weeks/{CURRENT}/4").status_code == 200


def test_a_score_frame_that_cannot_be_built_still_writes_every_prediction(loaded, monkeypatch):
    engine.save_sim_params(loaded, CURRENT, synthetic_params())

    def broken(*a, **kw):
        raise RuntimeError("frame failed")

    monkeypatch.setattr(engine, "add_score_features", broken)
    engine.refresh_predictions(loaded)
    assert all_games_have_rows(loaded)
    assert all(latest(loaded, g.game_id).features["simulation"] is None for g in upcoming(loaded))


# Step 18k: the run check gates every stored simulation; these tests use a Claude that always says PASS ----------------

@pytest.fixture(autouse=True)
def _claude_passes(monkeypatch):
    from nflpi.ai import run_checker

    class AlwaysPass:
        name, model = "claude", "fake"

        def complete(self, system, user, json_schema=None, max_tokens=16000):
            return "PASS"

    monkeypatch.setattr(run_checker, "get_provider", lambda name: AlwaysPass())
