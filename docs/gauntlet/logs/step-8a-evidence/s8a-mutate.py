"""Step 8a: each mutation below must make tests/test_stars.py fail. Run on a copy, never the worktree."""
import os, pathlib, shutil, subprocess, sys

work, copy, project = map(pathlib.Path, sys.argv[1:4])
MUTATIONS = [
    ("S11 slot order reversed", "nflpi/analytics/stars.py", 'SLOT_ORDER = {"qb": 0, "off": 1, "def": 2}', 'SLOT_ORDER = {"qb": 2, "off": 1, "def": 0}'),
    ("S11 rank dropped from the sort", "nflpi/analytics/stars.py", "SLOT_ORDER[star.slot], star.rank))", "SLOT_ORDER[star.slot]))"),
    ("S24 stats-has-pair-snaps-lack branch off", "nflpi/ingestion/service.py", "if stat_pairs - snap_pairs:", "if False:"),
    ("S26 AttributeError not wrapped", "nflpi/ingestion/service.py", "except (AttributeError, KeyError, TypeError, ValueError)", "except (KeyError, TypeError, ValueError)"),
    ("S21 any name match joins", "nflpi/analytics/stars.py", "if len(matches) == 1:", "if len(matches) >= 1:"),
    ("S25 only NA counts as blank", "nflpi/ingestion/nflverse.py", 'row[name] not in ("", "NA")', 'row[name] != "NA"'),
    ("S22 quarterback needs snaps", "nflpi/analytics/stars.py", '(p["off_snaps"] or p["attempts"])', 'p["off_snaps"]'),
    ("name cut removed (stats)", "nflpi/ingestion/nflverse.py", 'row["player_display_name"].strip()[:64]', 'row["player_display_name"].strip()'),
    ("name cut removed (snaps)", "nflpi/ingestion/nflverse.py", 'row["player"].strip()[:64]', 'row["player"].strip()'),
    # critic 3
    ("S10 reports of any season", "nflpi/analytics/stars.py", "            InjuryReport.season == game.season,\n", ""),
    ("S13 star list of any season", "nflpi/analytics/stars.py", "TeamStar.season == game.season, TeamStar.week <= game.week, ", "TeamStar.week <= game.week, "),
    ("S12 name matched across clubs", "nflpi/analytics/stars.py", "if report.team == star.team\n            and (", "if ("),
    ("S11 checked_at is the oldest good run", "nflpi/analytics/stars.py", "select(func.max(IngestionRun.finished_at))", "select(func.min(IngestionRun.finished_at))"),
    ("S1 quarterback name tiebreak dropped", "nflpi/analytics/stars.py", '(-p["off_snaps"], -p["attempts"], p["player"])', '(-p["off_snaps"], -p["attempts"])'),
    ("S14 side name tiebreak dropped", "nflpi/analytics/stars.py", '(-p[f"{slot}_score"], p["player"])', '(-p[f"{slot}_score"],)'),
    ("S19 defence snaps unbounded", "nflpi/ingestion/nflverse.py", "if not 0 <= off <= MAX_STAR_SNAP_COUNT or not 0 <= de <= MAX_STAR_SNAP_COUNT:", "if not 0 <= off <= MAX_STAR_SNAP_COUNT:"),
    ("S19 week 0 allowed", "nflpi/ingestion/nflverse.py", "MIN_STAR_WEEK = 1", "MIN_STAR_WEEK = 0"),
    ("S19 week 23 allowed", "nflpi/ingestion/nflverse.py", "MAX_STAR_WEEK = 22", "MAX_STAR_WEEK = 23"),
    ("S19 week 22 refused", "nflpi/ingestion/nflverse.py", "MAX_STAR_WEEK = 22", "MAX_STAR_WEEK = 21"),
    ("S23 reports of every club counted", "nflpi/analytics/stars.py", "            InjuryReport.team.in_((game.away_team, game.home_team)),\n", ""),
    ("S9 not-a-number stat accepted", "nflpi/ingestion/nflverse.py", "if not math.isfinite(number) or abs(number) > MAX_STAR_STAT_ABS:", "if abs(number) > MAX_STAR_STAT_ABS:"),
    ("S9 large negative stat accepted", "nflpi/ingestion/nflverse.py", "abs(number) > MAX_STAR_STAT_ABS:", "number > MAX_STAR_STAT_ABS:"),
    ("S19 300 snaps refused", "nflpi/ingestion/nflverse.py", "MAX_STAR_SNAP_COUNT = 300", "MAX_STAR_SNAP_COUNT = 299"),
    ("S19 301 snaps allowed", "nflpi/ingestion/nflverse.py", "MAX_STAR_SNAP_COUNT = 300", "MAX_STAR_SNAP_COUNT = 301"),
    ("S19 a stat of 1000 refused", "nflpi/ingestion/nflverse.py", "MAX_STAR_STAT_ABS = 1000", "MAX_STAR_STAT_ABS = 999"),
    ("S19 a stat of 1001 allowed", "nflpi/ingestion/nflverse.py", "MAX_STAR_STAT_ABS = 1000", "MAX_STAR_STAT_ABS = 1001"),
    ("S19 five-letter club allowed", "nflpi/ingestion/nflverse.py", "MAX_STAR_CLUB_LENGTH = 4", "MAX_STAR_CLUB_LENGTH = 5"),
    ("S6 players with no id keyed by club", "nflpi/analytics/stars.py", '("pfr", row["pfr_id"] or row["player"])', '("pfr", row["team"])'),
]
DB = "postgresql+psycopg://nflpi:nflpi@localhost:15438/nflpi_test"  # the lane's own database, never the default
survived = 0
for label, rel, old, new in [("no mutation (control)", "", "", "")] + MUTATIONS:
    shutil.rmtree(copy, ignore_errors=True)
    copy.mkdir(parents=True)
    for d in ("nflpi", "tests"):
        shutil.copytree(work / d, copy / d)
    if rel:
        text = (copy / rel).read_text()
        assert text.count(old) == 1, (label, text.count(old))
        (copy / rel).write_text(text.replace(old, new))
    run = subprocess.run(
        ["uv", "run", "--project", str(project), "pytest", "-q", "-p", "no:cacheprovider", "tests/test_stars.py"],
        cwd=copy, env={**os.environ, "PYTHONPATH": str(copy), "DATABASE_URL": DB}, capture_output=True, text=True,
    )
    tail = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr.strip()[-200:]
    killed = run.returncode != 0
    if rel and not killed:
        survived += 1
    print(f"{'control' if not rel else 'KILLED' if killed else 'SURVIVED'}: {label}: {tail}")
print(f"{len(MUTATIONS)} mutations, {survived} survived")
sys.exit(1 if survived else 0)
