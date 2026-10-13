CODEX WORK ORDER 2 (lane news, step 8e/8f/8h: tie to teams and stars, dedupe and store, per-source failure handling)

GOAL:
Fill in match.py, store.py and run.py so the database-backed part of backend/tests/test_news.py passes. You cannot reach the database; the coordinator runs those tests. Write carefully against the tests.

BASELINE: branch lane/news. Work order 1 is committed: fetch.py, parse.py, sources.py, NewsItem model and migration 0004 exist (read them, reuse their names: fetch.fetch_feed, fetch.Blocked, fetch.FetchError, fetch.default_resolver, parse.parse_feed, parse.clean_text, parse.Item, parse.FeedError, sources.SOURCES, models.NewsItem). Read the whole of backend/tests/test_news.py first (from "tie to team and player" down): it is the specification.

ALLOWED SCOPE (edit only these; they exist as one-line placeholders):
- backend/nflpi/ingestion/news/match.py, store.py, run.py
Touch nothing else (not models.py, not fetch.py/parse.py: if you find a real bug there, say so in RETURN). No new dependency. Do not commit.

INTERFACES (fixed by the tests):

match.py
  @dataclass(frozen=True) Tie(team_ids: list[str], player_ids: list[str], tags: list[str])
  @dataclass(frozen=True) Names (opaque: compiled patterns and id maps; your design)
  load_names(session) -> Names
     * Teams: from table `teams`: phrases `name` ("Buffalo Bills") and `nick` ("Bills") -> abbr. City alone is NOT a phrase.
     * Players: from table `team_stars`, only rows of the NEWEST season present, only rows with a player_id. Clean each stored name with parse.clean_text(name, 64) (control characters and zero-width marks removed, whitespace collapsed) and match case-insensitively on the cleaned FULL name. A cleaned name that maps to more than one distinct player_id is dropped (never guessed). A player's club = the team of his row with the highest week.
     * Empty tables are fine (no teams / no players).
  tie(title: str, extract: str, names: Names) -> Tie
     * Search title and extract. Match phrases case-insensitively with word boundaries on both sides, using `(?<!\w)` + re.escape(phrase) + `(?!\w)` (so "Bills" matches in "Bills beat Jets" and "Jets'" but not in "Billsboro" or "Jetsons"). Prefer one combined alternation per kind, longest phrase first.
     * team_ids = sorted unique abbrs of matched teams plus the club of every matched player. player_ids = sorted unique matched ids.
     * tags: sorted list of: "injury" r"\binjur(?:y|ies|ed)\b|\bruled out\b|\bquestionable\b|\bdoubtful\b"; "trade" r"\btrad(?:e|es|ed|ing)\b"; "coach" r"\b(?:coach|coaches|coaching|coordinator|fired|fires|firing|hired|hires|hiring)\b"; "playcaller" r"\bplay[- ]?call(?:er|ers|ing)\b|\bcalling (?:the )?plays\b". All case-insensitive. "Uninjured", "tradeoff" must NOT match.

store.py
  KEEP_DAYS = 30
  store_items(session, source_id: str, items: list[parse.Item], names: match.Names, fetched_at: datetime) -> int
     * For each item: Tie from match.tie(item.title, item.extract, names); insert one NewsItem row (title_sha256 = hashlib.sha256(title.encode()).hexdigest()) with sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_nothing() (no target: either unique constraint). Execute row by row, sum result.rowcount (new rows only), commit once, return the count. Values are bound parameters; no string-built SQL.
  prune(session, now: datetime) -> int: delete rows whose fetched_at < now - KEEP_DAYS days (key on OUR fetched_at, not the feed's date); commit; return the deleted count.

run.py
  POLL_MINUTES = 30, BLOCK_HOURS = 24
  run_news(session, *, now: datetime | None = None, resolver=None, transport=None, sources=sources.SOURCES) -> list[IngestionRun]
     * now defaults to datetime.now(UTC). resolver defaults to fetch.default_resolver. Load names once with match.load_names.
     * Per source, in order, one after the other. A source is DUE unless its latest `ingestion_runs` row (dataset f"news:{id}", ANY status, including "running" and "failed", newest by started_at) is: (a) error starts with "blocked:" and started_at > now - 24 h, or (b) started_at > now - 30 min. A source that is not due is skipped: no request, no row, not in the returned list.
     * For a due source create IngestionRun(source=id, dataset=f"news:{id}", started_at=now, status="running"), commit, then:
         validators = AppSetting row key f"news:{id}:validators" (value {"etag": ..., "last_modified": ...}) if present;
         result = fetch.fetch_feed(src, resolver=..., transport=transport, validators=validators);
         status 304 -> rows 0, ok. Otherwise items = parse.parse_feed(result.body, src, now); n = store.store_items(session, id, items, names, now); save the new validators (session.merge an AppSetting; only when etag or last_modified is not None) ; store.prune(session, now); rows = n, status "ok".
         except fetch.Blocked as exc -> status "failed", error "blocked: " + the exception message;
         except (fetch.FetchError, parse.FeedError) as exc -> status "failed", error = the exception message;
         except Exception -> session.rollback(), log.exception, status "failed", error "unexpected: " + exception class name.
       In every failure case roll back first, keep stored rows untouched, set finished_at = datetime.now(UTC), and commit the run row. Error text is passed through parse.clean_text(text, 100) and is at most 100 characters.
     * One source failing never stops the next. run_news never raises for a source failure. Returns the IngestionRun rows it made, in source order.
  Style: like backend/nflpi/ingestion/service.py (run_logged); import nothing from service.py (another lane owns it).

PROOF: you cannot run them. Run `bash docs/gauntlet/logs/step-8c-evidence/pure.sh` (must still say PURE OK) and `cd backend && .venv/bin/python -c "import nflpi.ingestion.news.run, nflpi.ingestion.news.store, nflpi.ingestion.news.match"` (imports cleanly). The coordinator runs the database tests.

CONSTRAINTS (Ponytail): smallest correct diff; stdlib + sqlalchemy only; typed; ruff line 120; no abstraction a test does not need.
DO NOT: commit, push, install, touch tests/docs/other files, use the network, read .env.

RETURN: changed files, a 5-line summary, pure.sh result, anything in fetch.py/parse.py you believe is wrong.
