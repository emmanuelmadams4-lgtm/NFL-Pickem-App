"""Step 18h mutation sweep: apply one mutation, run the lane tests, restore. A mutation must make a test fail."""
import subprocess
import sys
from pathlib import Path

B = Path(__file__).resolve().parents[4] / "backend"
TESTS = ["tests/test_wiring.py", "tests/test_sheet.py", "tests/test_sim_backtest.py", "tests/test_picks.py"]
M = [
    ("M1 order ties by id", "nflpi/predictions/sheet.py", "(-g.prob, g.game_id)", "(-g.prob, -ord(g.game_id[0]))"),
    ("M2 simulation inside the hash", "nflpi/predictions/engine.py",
     '        features["simulation"] = simulations[row["game_id"]]\n        h = _hash({"mv": mv.id, "f": features, "u": reasons})',
     '        h = _hash({"mv": mv.id, "f": features, "u": reasons})\n        features["simulation"] = simulations[row["game_id"]]'),
    ("M3 bench seed", "nflpi/predictions/engine.py", ".encode()) ^ BASE_SEED", ".encode())"),
    ("M4 spread sign", "nflpi/predictions/engine.py", "float(home_spread_from_nflverse(row[\"spread_line\"]))",
     "float(-home_spread_from_nflverse(row[\"spread_line\"]))"),
    ("M5 playoff never ties", "nflpi/predictions/engine.py", 'playoff=row["game_type"] != "REG"', "playoff=False"),
    ("M6 walk-forward window", "nflpi/predictions/engine.py", "between(season - WINDOW, season - 1)",
     "between(season - WINDOW, season)"),
    ("M7 no params, no simulation", "nflpi/predictions/engine.py",
     "models = {s: _score_model(frame, s) for s, p in params.items() if p is not None}",
     "models = {s: _score_model(frame, s) for s, p in params.items()}"),
    ("M8 load_frame spread", "nflpi/predictions/engine.py",
     '"spread_line": m.spread_line if m and m.spread_line is not None else np.nan', '"spread_line": np.nan'),
    ("M9 train survives a failed fetch", "nflpi/jobs.py", "except Exception:  # noqa: BLE001 - the simulator", "except ValueError:  # the simulator"),
    ("M10 train learns the predicted season", "nflpi/jobs.py",
     "engine.save_sim_params(session, season,", "engine.save_sim_params(session, season - 1,"),
    ("M11 configured pick mode", "nflpi/api/views.py", "make_picks([], mode=get_settings().pick_mode)",
     "make_picks([], mode=None)"),
    ("M12 refuse ats", "nflpi/config.py", 'Literal["straight_up", "confidence_pool"]',
     'Literal["straight_up", "confidence_pool", "ats"]'),
    ("M13 one bench conversion", "nflpi/analytics/sim_backtest.py",
     "from nflpi.picks import home_spread_from_nflverse",
     "from nflpi.picks import home_spread_from_nflverse as _h\n\n\ndef home_spread_from_nflverse(x):\n    return _h(x)"),
    ("M14 api maps simulation", "nflpi/api/views.py", 'simulation=p.features.get("simulation")', "simulation=None"),
    ("M15 save upsert", "nflpi/predictions/engine.py", "        row.value = value\n    session.commit()",
     "        pass\n    session.commit()"),
]
only = set(sys.argv[1:])
for name, rel, old, new in M:
    if only and name.split()[0] not in only:
        continue
    path = B / rel
    src = path.read_text()
    assert src.count(old) == 1, (name, src.count(old))
    path.write_text(src.replace(old, new))
    try:
        r = subprocess.run(["uv", "run", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS], cwd=B,
                           capture_output=True, text=True, check=False)
    finally:
        path.write_text(src)
    print(f"{name}: {'KILLED' if r.returncode else 'SURVIVED'}", flush=True)
