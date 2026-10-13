"""Step 8a: each mutation below must make tests/test_stars.py fail. Run on a copy, never the worktree."""
import pathlib, shutil, subprocess, sys

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
]
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
        cwd=copy, env={**__import__("os").environ, "PYTHONPATH": str(copy)}, capture_output=True, text=True,
    )
    tail = run.stdout.strip().splitlines()[-1] if run.stdout.strip() else run.stderr.strip()[-200:]
    killed = run.returncode != 0
    if rel and not killed:
        survived += 1
    print(f"{'control' if not rel else 'KILLED' if killed else 'SURVIVED'}: {label}: {tail}")
print(f"{len(MUTATIONS)} mutations, {survived} survived")
sys.exit(1 if survived else 0)
