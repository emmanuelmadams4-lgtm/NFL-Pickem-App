**The news fetcher, parser, table, migration, and setting are in place.** I did not commit or make network calls.

Changed files: [news package](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news), [models.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/models.py), [config.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/config.py), [0004_news_items.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/migrations/versions/0004_news_items.py).

- Added the fixed ESPN and CBS allowlist.
- Added pinned-IP fetches, redirect checks, size limits, deadlines, and robots checks.
- Added feed parsing with clean text, safe links, dates, and a 100-item limit.
- Added `NewsItem`, its matching migration, `news_contact`, and the requested placeholders.
- Verified syntax and schema fields; 105 pure tests passed, and I checked the nine blocked cases directly with mock responses.

**Blocker:** `pure.sh` did not print `PURE OK`. Nine tests fail before calling the code because they pass tuple keys through `**kwargs` (`TypeError: keywords must be strings`). The 45 `session` fixture errors are expected by the script. The test file is outside the allowed edit scope.

Last lines of `pure.sh`:

```text
ERROR tests/test_news.py::test_keyword_tags[Star placed on injured reserve-tags0]
ERROR tests/test_news.py::test_keyword_tags[Starter ruled out vs. Dolphins-tags1]
ERROR tests/test_news.py::test_keyword_tags[QB questionable with ankle injury-tags2]
ERROR tests/test_news.py::test_keyword_tags[Team trades receiver for a pick-tags3]
ERROR tests/test_news.py::test_keyword_tags[Traded: a star changes teams-tags4]
```