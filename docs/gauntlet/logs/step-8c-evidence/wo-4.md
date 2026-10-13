CODEX WORK ORDER 4 (CLEANUP: behaviour-preserving refactor of the code touched in this step)

GOAL: apply a scope-locked /refactor pass. NO behaviour change: all 189 tests in backend/tests/test_news.py must give exactly the same results (you can only run the no-database ones; the coordinator runs the rest).
ALLOWED SCOPE: backend/nflpi/ingestion/news/fetch.py, parse.py, run.py, store.py, match.py only. Do not edit tests, models, migration, config. Do not commit.

THE CLEANUPS (and nothing else):
 1. fetch.py: fetch_guarded is ~85 lines with 5 levels of nesting. Split it so every function is under 50 lines and nesting is at most 3 levels: e.g. `_pin(url, host, resolver) -> tuple[str, str]` (validate url, resolve, check every address, return hostname and the IP url) and `_read_body(response, max_bytes, clock, deadline) -> bytes` (stream with the byte cap and the deadline check). Same exceptions, same messages, same order of checks.
 2. fetch.py: annotate `resolver: Callable[[str], list[str]]`, `clock: Callable[[], float]` on fetch_guarded, check_robots, fetch_feed (import Callable from collections.abc).
 3. run.py: run_news is ~70 lines. Split into `_is_due(session, dataset, now) -> bool` and `_poll(session, src, names, now, resolver, transport) -> IngestionRun` (the per-source body). Same behaviour. Stop shadowing the module: `from nflpi.ingestion.news.sources import SOURCES, Source`, keep the keyword parameter NAME `sources` (tests pass `sources=`), typed `Sequence[Source]`, default SOURCES. Remove the redundant `session.add(run)` before the final commit only if it is provably redundant (run is already persistent). Annotate resolver/transport.
 4. parse.py: name the magic numbers as module constants: MAX_ENTRIES = 100, KEEP_DAYS = 30, MAX_URL = 2048, TITLE_MAX = 200, EXTRACT_MAX = 300, FUTURE_SLACK = timedelta(days=1); use them. Annotate `_published(entry: Mapping[str, Any], ...)`.
 5. store.py and match.py: the first-line docstrings mention "step 8e/8f"; say what the module does instead.
PROOF: `bash docs/gauntlet/logs/step-8c-evidence/pure.sh` ends PURE OK and `cd backend && .venv/bin/python -c "import nflpi.ingestion.news.run, nflpi.ingestion.news.fetch"`. The coordinator reruns everything.
CONSTRAINTS (Ponytail): smallest diff that achieves the five items; no new abstraction beyond the named helpers; ruff line 120; keep every guard exactly as is.
DO NOT: commit, push, install, use the network, change messages or error text, reorder security checks.
RETURN: changed files and a 5-line summary.
