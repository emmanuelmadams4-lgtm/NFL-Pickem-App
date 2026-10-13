CODEX WORK ORDER 2b (narrow correction, lane news; my spec was wrong, not your code)

GOAL: in backend/nflpi/ingestion/news/store.py make store_items return the true number of NEW rows.
FAILING EVIDENCE: `result.rowcount` is -1 for the single-row `insert(...).values(...).on_conflict_do_nothing()` on this driver (psycopg 3), so store_items returns a negative number (tests expect 1, 2, 100; observed -1, -2, -100).
ALLOWED SCOPE: backend/nflpi/ingestion/news/store.py only (only the line that counts the inserted rows, and only what that needs).
REQUIREMENT: add `.returning(NewsItem.id)` to the statement and count a row as new when the executed result yields a row (e.g. `session.execute(stmt).first() is not None`); a conflict (do nothing) yields no row. Keep one commit at the end as today. Leave prune() alone (its rowcount for DELETE is correct).
PROOF: `bash docs/gauntlet/logs/step-8c-evidence/pure.sh` still ends "PURE OK". You cannot reach the database; the coordinator runs the rest.
CONSTRAINTS: smallest diff, nothing else touched. DO NOT commit, push, install, use the network.
RETURN: the changed lines.
