Changed lines in [store.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/store.py:29):

```python
        ).returning(NewsItem.id)
        added += session.execute(stmt.on_conflict_do_nothing()).first() is not None
```

`pure.sh` ended with **PURE OK**. It reported 114 passed and 45 errors. No commit made.