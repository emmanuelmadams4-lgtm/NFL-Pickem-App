import subprocess, sys, os
env = dict(os.environ, DATABASE_URL="postgresql+psycopg://nflpi:nflpi@localhost:15445/nflpi_test")
G, Q = "nflpi/api/group.py", "nflpi/group/queries.py"
M = [
 (G, "int(content_length) > cap", "int(content_length) >= cap"),
 (G, "len(data) + len(chunk) > cap", "len(data) > cap"),
 (G, "len(data) + len(chunk) > cap", "len(data) + len(chunk) > cap + 1"),
 (G, "cap = importer.MAX_BYTES", "cap = 1_000_000"),
 (G, "Query(ge=2000, le=2100)", "Query(ge=1999, le=2100)"),
 (G, "Query(ge=2000, le=2100)", "Query(ge=2000, le=2101)"),
 (G, "Query(ge=1, le=22)", "Query(ge=0, le=22)"),
 (G, "Query(ge=1, le=22)", "Query(ge=1, le=23)"),
 (G, "raise HTTPException(422, str(exc)) from None", "raise HTTPException(422, 'bad file') from None"),
 (G, '"group import failed: database error"', '"group import failed"'),
 (G, "    except RuntimeError:\n        raise HTTPException(500, \"group import failed: database error\") from None\n", ""),
 (G, "dependencies=[Depends(_token)]", "dependencies=[]"),
 (G, "require_token(authorization)", "pass"),
 (G, "await run_in_threadpool(_import_file, season, data)", "_import_file(season, data)"),
 (Q, ".order_by(Game.kickoff_utc, Game.game_id)", ".order_by(Game.game_id)"),
 (Q, "Game.season == season, Game.week == week", "Game.week == week"),
 (Q, "Game.season == season, Game.week == week", "Game.season == season"),
 (Q, '"share": count / picked if picked else None', '"share": count / max(picked, 1)'),
 (Q, "GroupPick.game_id.in_(game_ids)", "GroupPick.game_id.is_not(None)"),
 (Q, '"avg_confidence": sum(confidence) / len(confidence) if confidence else None', '"avg_confidence": sum(confidence) / len(confidence) if confidence else 0'),
 (Q, '"members": len(picks), "picked": picked,\n                     "away"', '"members": picked, "picked": picked,\n                     "away"'),
]
survived = []
for f, old, new in M:
    src = open(f).read()
    assert src.count(old) >= 1, (f, old)
    open(f, "w").write(src.replace(old, new, 1))
    try:
        r = subprocess.run(["uv", "run", "pytest", "-q", "-x", "tests/test_group_api.py"], env=env, capture_output=True, text=True)
    finally:
        open(f, "w").write(src)
    ok = r.returncode != 0
    print("KILLED " if ok else "SURVIVED", f, old[:60].replace("\n", " "), flush=True)
    if not ok: survived.append((f, old))
print("survivors:", len(survived))
