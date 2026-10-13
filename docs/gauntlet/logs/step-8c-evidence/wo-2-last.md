Changed: [match.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/match.py), [store.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/store.py), [run.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/run.py).

1. Team and full player names now tie stories to IDs; shared player names are ignored.
2. Story tags follow the specified word patterns.
3. Storage deduplicates by the database constraints and prunes by fetch date.
4. Polling tracks each source’s retry window, validators, and failures separately.
5. Imports and `git diff --check` pass; database tests remain for the coordinator.

`pure.sh`: **PURE OK** (114 passed; 45 database errors in this environment). I found no issue in `fetch.py` or `parse.py`. No commit was made.