"""Step 18g mutation sweep: break each frozen clause in bench_18g.py one way at a time; a test must fail.

Run from backend/ (needs DATABASE_URL and the gate lock):  uv run python ../docs/gauntlet/logs/step-18g-evidence/mutate.py
Prints CAUGHT or SURVIVED per mutant; the file is restored after each one and at the end.
"""

import subprocess
import sys
from pathlib import Path

TARGET = Path("nflpi/analytics/bench_18g.py")
M = [  # (clause, old text, new text)
    ("P1", "PYTH_EXPONENT = 2.37", "PYTH_EXPONENT = 2.0"),
    ("P1", "PYTH_HALF_LIVES = (4, 8, 16)", "PYTH_HALF_LIVES = (4, 8, 12)"),
    ("P1", "PYTH_CLIP = 0.01", "PYTH_CLIP = 0.05"),
    ("P1", "decay = 0.5 ** (1 / half_life)\n    ratings: dict[str, tuple[float, float]] = {}\n    values = []",
     "decay = 0.5 ** (1 / (2 * half_life))\n    ratings: dict[str, tuple[float, float]] = {}\n    values = []"),
    ("P1", "_log_odds(*home) - _log_odds(*away) if home and away", "_log_odds(*home) + _log_odds(*away) if home and away"),
    ("P1", "if home and away else np.nan", "if home or away else np.nan"),
    ("P1", "ratings[team] = (pf * decay + float(scored), pa * decay + float(allowed))",
     "ratings[team] = (pf * decay + float(allowed), pa * decay + float(scored))"),
    ("P2", "if _missing(row.home_score) or _missing(row.away_score):\n            continue\n        for team, scored",
     "if _missing(row.home_score) or _missing(row.away_score):\n            pass\n        for team, scored"),
    ("P1", 'if not df["kickoff_utc"].is_monotonic_increasing:', 'if False:'),
    ("P3", 'fallback = MARKET_FALLBACK if kind == "blend" else BASE_FALLBACK',
     "fallback = MARKET_FALLBACK"),
    ("P3", "_, train = backtest._train_rows(frames, season, window)\n        for column",
     "_, train = backtest._train_rows(frames, season, window + 1)\n        for column"),
    ("P3", "[*(BLEND_FEATURES if kind == \"blend\" else BASE_FEATURES), \"pyth_diff\"]",
     "[*(BLEND_FEATURES if kind == \"blend\" else BASE_FEATURES)[:-1], \"pyth_diff\"]"),
    ("Q1", 'if row.get("position") != "QB":', 'if False:'),
    ("Q1", "plays = attempts + sacks + carries", "plays = attempts + carries"),
    ("Q1", "pass_epa + rush_epa, plays", "pass_epa, plays"),
    ("Q1", "if plays <= 0:", "if plays < 0:"),
    ("Q1", "return number if math.isfinite(number) else None", "return number"),
    ("Q2", "QB_HALF_LIVES = (8, 16, 32)", "QB_HALF_LIVES = (8, 16, 24)"),
    ("Q2", "QB_SHRINK = 150.0", "QB_SHRINK = 100.0"),
    ("Q2", "QB_SCALE = 50.0", "QB_SCALE = 25.0"),
    ("Q2", "return epa / (plays + QB_SHRINK)", "return epa / plays if plays else 0.0"),
    ("Q2", "QB_SCALE * (rate(row.home_qb_id) - rate(row.away_qb_id))", "QB_SCALE * (rate(row.home_qb_id) + rate(row.away_qb_id))"),
    ("Q2", "if _missing(row.home_qb_id) or _missing(row.away_qb_id):", "if _missing(row.home_qb_id):"),
    ("Q2", "ratings[player] = (old_epa * decay + float(epa), old_plays * decay + float(plays))",
     "ratings[player] = (old_epa + float(epa), old_plays + float(plays))"),
    ("Q3", '"blend": ["market_logit", "elo_diff", "home_field", "qb_diff"]', '"blend": ["market_logit", "elo_diff", "home_field", "home_qb_change", "qb_diff"]'),
    ("Q3", '"base": ["elo_diff", "home_field", "qb_diff"]', '"base": ["elo_diff", "qb_diff"]'),
    ("T1", "EARTH_RADIUS_KM = 6371.0", "EARTH_RADIUS_KM = 3959.0"),
    ("T1", "KM_PER_UNIT = 1000.0", "KM_PER_UNIT = 100.0"),
    ("T2", 'TRAVEL_VARIANTS = {"travel": ["travel_km_diff"], "tz": ["tz_diff"], "both": ["travel_km_diff", "tz_diff"]}',
     'TRAVEL_VARIANTS = {"travel": ["travel_km_diff"], "tz": ["tz_diff"], "both": ["travel_km_diff"]}'),
    ("T2", '"PHO00": ', '"PHO00X": '),
    ("T3", "if bool(row.neutral_site) or _missing(row.stadium_id):", "if _missing(row.stadium_id):"),
    ("T3", "sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]", "sorted(c.items(), key=lambda kv: (kv[1], kv[0]))[0][0]"),
    ("T3", "(row.season, row.home_team), Counter()", "(0, row.home_team), Counter()"),
    ("T3", "_offset_hours(zones[stadium], kickoff) - _offset_hours(zones[venue], kickoff)",
     "_offset_hours(zones[venue], kickoff) - _offset_hours(zones[stadium], kickoff)"),
    ("T3", "kickoff.astimezone(ZoneInfo(zone)).utcoffset().total_seconds() / 3600",
     "ZoneInfo(zone).utcoffset(datetime(2022, 1, 1)).total_seconds() / 3600"),
    ("T3", "if bool(row.neutral_site)\n            else (0.0, 0.0)", "if False\n            else (0.0, 0.0)"),
    ("T3", "rows.append(((away[0] - home[0]) / KM_PER_UNIT, away[1] - home[1]))", "rows.append(((home[0] - away[0]) / KM_PER_UNIT, away[1] - home[1]))"),
    ("T3", "rows.append((np.nan, np.nan))", "rows.append((0.0, 0.0))"),
    ("T3", "if venue is None or venue not in coords or venue not in zones:\n        return np.nan, np.nan",
     "if venue is None or venue not in coords or venue not in zones:\n        return 0.0, 0.0"),
    ("T4", '*extra], {})', '*extra][:-1], {})'),
    ("M1", "/ MATCHUP_PERCENT\n        test[\"p_match_market\"]", "/ 50.0\n        test[\"p_match_market\"]"),
    ("M1", "matchup_score(test, include_market=True)", "matchup_score(test, include_market=False)"),
    ("M2", "diff = np.abs(refit - test[\"p_blend\"].to_numpy())", "diff = refit - test[\"p_blend\"].to_numpy()"),
    ("E1", 'raise ValueError("tune and confirm seasons must not overlap")', "pass"),
    ("E1", 'key=lambda v: v["tune"]["log_loss_gain"])["variant"]', 'key=lambda v: -v["tune"]["log_loss_gain"])["variant"]'),
    ("E1", '"gap": tune_gain - confirm_gain', '"gap": confirm_gain - tune_gain'),
    ("E1", "rows[baseline].to_numpy()", 'rows["p_blend"].to_numpy()'),
    ("E1", "result = gain(confirm_rows, chosen, confirm_groups)", "result = gain(confirm_rows, chosen, None)"),
    ("E2", '"_blend_" in column or column == "p_match_market"', '"_blend_" in column'),
    ("E2", 'if "_base_" in column or column == "p_match_football":', 'if "_base_" in column:'),
    ("E2", 'if game and group:', 'if game or group:'),
    ("E2", 'return "does not ship" if not game and not group else "needs the owner"', 'return "does not ship"'),
]


def passes() -> bool:
    out = subprocess.run(["uv", "run", "pytest", "-x", "-q", "tests/test_bench_18g.py"], capture_output=True, text=True)
    return out.returncode == 0


def main() -> int:
    original = TARGET.read_text()
    survived = 0
    try:
        for clause, old, new in M:
            if original.count(old) != 1:
                print(f"SKIPPED  {clause}  (text not found once): {old[:60]!r}")
                survived += 1
                continue
            TARGET.write_text(original.replace(old, new))
            caught = not passes()
            survived += not caught
            print(f"{'CAUGHT  ' if caught else 'SURVIVED'} {clause}  {old[:60]!r} -> {new[:40]!r}", flush=True)
    finally:
        TARGET.write_text(original)
    print(f"{len(M) - survived} of {len(M)} caught")
    return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
