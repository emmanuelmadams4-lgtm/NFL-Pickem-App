Changed files: [fetch.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/fetch.py) and [parse.py](/Users/emmanueladams/Projects/NFL-Pickem-App/.claude/worktrees/lane-news/backend/nflpi/ingestion/news/parse.py). I did not edit tests or commit.

**Five-line summary**

- DNS lookup now times out after `RESOLVE_TIMEOUT_S` without waiting for a hung lookup.
- Fetch rejects compressed replies before reading the body.
- Text cleaning cuts raw input at 10 times the output limit before parsing.
- Text cleaning avoids flushing an unfinished tag into the result after a cut.
- Feedparser handled the hostile sample in about 0.13 seconds, so I kept its HTML sanitizing on.

**Proof:** `pure.sh` ended `PURE OK`. The 11 selected code tests passed. The exact `-k "dns or compressed or hostile"` command also selected one database test; `--noconftest` left it without its `session` fixture. Ruff passed on both changed files. The requested `uvx` command could not start because its cache was blocked; the local Ruff binary found one existing import-order error in the unchanged test file.