Changed files:

- [fetch.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/fetch.py)
- [parse.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/parse.py)
- [run.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/run.py)
- [store.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/store.py)
- [match.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/match.py)

Summary:

1. Split fetch validation, body reading, and response handling while keeping guard order and messages.
2. Added resolver and clock types to fetch APIs.
3. Split news polling into due checks and per-source polling; removed the redundant final `session.add(run)`.
4. Named parsing limits and typed `_published`; updated the store and match module descriptions.
5. Proof passed: `PURE OK` (134 passed, 55 expected database-fixture errors), imports succeeded, and changed functions stay under 50 lines with no lines over 120 columns.