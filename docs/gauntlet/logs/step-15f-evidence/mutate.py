"""Break each grading rule once; every mutant must make tests/test_live_grade.py fail."""
import subprocess, sys, pathlib
F = pathlib.Path("backend/nflpi/analytics/live_grade.py")
MUTANTS = [
 ("G1 per-point instead of by time", "weights=weights))\n    log_loss", "weights=None))\n    log_loss"),
 ("G1 log loss unweighted", "game_log_loss(p, y), weights=weights", "game_log_loss(p, y), weights=None"),
 ("G1 no clip at window start", "max(point.at, start)", "point.at"),
 ("G1 no clip at window end", "min(points[i + 1].at, end) if i + 1 < len(points) else end", "points[i + 1].at if i + 1 < len(points) else end"),
 ("G2 window ends at last row not first post", 's.state == "post"), None)', 's.state != "in"), None)'),
 ("G2 lost treated as in_progress", '"in_progress" if states[-1].state == "in" else "incomplete"', '"in_progress"'),
 ("G2 later rows kept", "states = states[: states.index(last_row) + 1]", "pass"),
 ("G3 prediction after kickoff allowed", "p.created_at < game.kickoff_utc and", "True and"),
 ("G3 first not last prediction", "(before or backfill or [None])[-1]", "(before or backfill or [None])[0]"),
 ("G3 backfill beats real snapshot", "(before or backfill or [None])[-1]", "(backfill or before or [None])[-1]"),
 ("G3 backfill ignored", "(before or backfill or [None])[-1]", "(before or [None])[-1]"),
 ("G3 kind label dropped", "kind=chosen.kind if chosen is not None else None", "kind=None"),
 ("G4 outside 0..1 accepted", "0.0 <= value <= 1.0", "True"),
 ("G4 nonfinite accepted", "math.isfinite(value) and ", ""),
 ("G4 null espn row filled", 'if s.state == "in" else None', "if True else None"),
 ("G5 min points off", "MIN_POINTS = 3", "MIN_POINTS = 1"),
 ("G5 coverage off", "MIN_COVERAGE = 0.5", "MIN_COVERAGE = 0.0"),
 ("G6 tie graded", "if game.home_score == game.away_score:", "if False:"),
 ("G7 no live data", 'if first_in is None:', "if False:"),
 ("G8 period > 4 dropped", "s.home_wp if s.state", "(s.home_wp if (s.period or 0) <= 4 else None) if s.state"),
 ("G9 no clamp", "np.average(game_log_loss(p, y), weights=weights)", "np.average(-(y*np.log(np.maximum(p,1e-300))+(1-y)*np.log(np.maximum(1-p,1e-300))), weights=weights)"),
 ("G10 not-final graded", "if not final:", "if False:"),
 ("G11 averages weight by nothing: skip filter", 'x.forecasters[name].status == "scored"', "True"),
 ("G11 games_graded counts ties", 'x.status == "graded"', 'x.status != "in_progress"'),
 ("kalshi pregame kind used", 'MarketQuote.kind == "live"', 'MarketQuote.kind != "x"'),
 ("kalshi any source", 'MarketQuote.source == "kalshi"', 'MarketQuote.source != "x"'),
]
src = F.read_text()
bad = 0
for name, old, new in MUTANTS:
    assert src.count(old) >= 1, f"pattern missing: {name}"
    F.write_text(src.replace(old, new, 1))
    try:
        r = subprocess.run(["uv", "run", "pytest", "tests/test_live_grade.py", "-q", "-x", "-p", "no:cacheprovider"],
                           cwd="backend", capture_output=True, text=True)
    finally:
        F.write_text(src)
    caught = r.returncode != 0
    bad += not caught
    print(("CAUGHT  " if caught else "SURVIVED"), name, flush=True)
print("survivors:", bad)
# Survivors known EQUIVALENT (cannot change any output): "G2 later rows kept" (held_segments clips to the window
# end anyway) and "G4 nonfinite accepted" (0 <= nan <= 1 and 0 <= inf <= 1 are both False).
EQUIVALENT = 2
sys.exit(max(0, bad - EQUIVALENT))
