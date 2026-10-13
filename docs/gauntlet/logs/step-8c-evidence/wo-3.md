CODEX WORK ORDER 3 (review fixes, lane news; the red tests in backend/tests/test_news.py are the spec, read them)

GOAL: make every failing test in backend/tests/test_news.py pass without breaking the rest. Five reviewers read HEAD e24590b; these are the confirmed defects.
BASELINE: branch lane/news HEAD (last commit adds the new tests). Currently 16 tests fail (see below). The other ~175 pass and must keep passing.
ALLOWED SCOPE: backend/nflpi/ingestion/news/fetch.py, parse.py, run.py, store.py. Nothing else. No new dependency. Do not commit.

REQUIREMENTS
fetch.py
 1. Robots: only an EXPLICIT refusal is a block. check_robots lets `Blocked` from fetch_guarded through unchanged (private address, 401/403/429, bad url) and raises Blocked("robots disallow") for a rule match. Any other trouble (timeout, DNS error, 5xx, redirect, wrong content type, oversize body, a status other than 200/404/410) is `FetchError("robots unavailable")`, NOT Blocked: the poll stops (fail closed, the feed is not requested) and the source is retried in the next 30-minute window instead of being stopped for 24 hours.
 2. fetch_guarded: 401 joins 403 and 429 as Blocked("status 401") (a login wall is a block). Other >= 400 stays FetchError (except 404/410 returned).
 3. `_validator` keeps a value only when it is plain printable ASCII (`value.isascii() and value.isprintable()`) and at most 256 chars. A hostile "é" ETag must never reach a header.
 4. is_public: also refuse IPv4-compatible `::/96`, 6to4 `2002::/16` and Teredo `2001::/32`, in addition to the NAT64 ranges already refused (keep the ipv4_mapped unwrap).
 5. Every request carries `Accept-Encoding: identity` (set after merging caller headers).
parse.py
 6. parse_feed: when the feed HAS entries (within the first 100) and every one of them was rejected for an empty title or an unusable link (none kept, none dropped merely for being older than 30 days) raise FeedError("no usable items"). A feed with zero entries still returns [] and a feed whose entries are all just old still returns [].
run.py
 7. When a good 200 answer carries neither an ETag nor a Last-Modified, DELETE the saved AppSetting validators row for that source if one exists (stale validators must not be re-sent). Validators are still saved only after a successful parse/store.
 8. In the FetchError/FeedError branch add `log.warning("news %s: %s", src.id, exc)` (no other change).
store.py
 9. `added += ... is not None` becomes `if ... is not None: added += 1` (do not add a bool to an int).

PROOF (you cannot reach the database): `bash docs/gauntlet/logs/step-8c-evidence/pure.sh` must end PURE OK; also `cd backend && .venv/bin/python -c "import nflpi.ingestion.news.run"`. The coordinator runs the database tests.
CONSTRAINTS (Ponytail): smallest diff, no new abstraction, ruff line 120, typed; touch only what the 9 items need (a separate cleanup pass follows, do NOT refactor or split functions now).
DO NOT: commit, push, install, use the network, edit tests.
RETURN: changed files, a 5-line summary, pure.sh result.
