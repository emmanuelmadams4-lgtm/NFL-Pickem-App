Changed: [fetch.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/fetch.py), [parse.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/parse.py), [run.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/run.py), [store.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/store.py).

- Robots refusals remain blocks; other robots failures stop this poll for retry.
- Fetches block 401, reject the added IPv6 ranges, and request identity encoding.
- Validators now require printable ASCII; feeds with only unusable entries raise `FeedError`.
- Successful 200 responses clear stale validators; fetch and feed errors log a warning.
- Store counts inserted rows with an explicit integer increment.

**Proof:** Import passed. `pure.sh` did **not** reach `PURE OK`: 132 passed, 55 had the expected missing database fixture, and 2 failed while the tests constructed non-ASCII `httpx.Response` headers, before the changed code ran. I left tests and dependencies untouched. No commit was made.