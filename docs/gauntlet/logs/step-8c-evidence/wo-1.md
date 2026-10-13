CODEX WORK ORDER 1 (lane news, step 8c/8d: guarded fetcher + feed parser + table)

GOAL:
Make the pure (no database) part of backend/tests/test_news.py pass: allowlist, guarded fetch, robots, feed parsing. Also add the table, the migration and one setting so the test module imports.

BASELINE: branch lane/news, HEAD 01c2ee8 (tests red: `ImportError: cannot import name 'fetch'`). Read the whole of backend/tests/test_news.py first: it is the specification, every test is a frozen clause. Design reviewed by security: docs/gauntlet/logs/step-8c-evidence/design.md (its reviewer's six required changes D1-D6 are in the tests).

ALLOWED SCOPE (create/edit only these):
- backend/nflpi/ingestion/news/__init__.py (empty docstring)
- backend/nflpi/ingestion/news/sources.py, fetch.py, parse.py
- backend/nflpi/ingestion/news/match.py, store.py, run.py: create each as a ONE-LINE docstring-only placeholder (work order 2 fills them in)
- backend/nflpi/models.py: APPEND class NewsItem at the very end, change nothing above, add no import (use the already imported JSON, Integer, String, DateTime, Index, UniqueConstraint, Mapped, mapped_column, utcnow)
- backend/migrations/versions/0004_news_items.py
- backend/nflpi/config.py: add ONE new line `news_contact: str = ""` in its own `# News` group at the end of the class
Touch nothing else. No new dependency (feedparser is already added). Do not run git commit.

INTERFACES (names and signatures are fixed by the tests):

sources.py
  @dataclass(frozen=True) Source(id: str, url: str, host: str, link_suffixes: tuple[str, ...])
  SOURCES = (espn, cbs) in that order:
    espn: https://www.espn.com/espn/rss/nfl/news   host www.espn.com        suffixes ("espn.com",)
    cbs:  https://www.cbssports.com/rss/headlines/nfl/  host www.cbssports.com  suffixes ("cbssports.com",)

fetch.py  (httpx + stdlib only)
  Constants: TIMEOUT_S = 10, DEADLINE_S = 20, MAX_FEED_BYTES = 2_000_000, MAX_ROBOTS_BYTES = 512_000, MAX_REDIRECTS = 3, MAX_VALIDATOR_LEN = 256
  class FetchError(Exception); class Blocked(FetchError)
  @dataclass(frozen=True) FetchResult(status: int, body: bytes, etag: str | None, last_modified: str | None)
  user_agent() -> str: "NFLPickemIntel/1.0 (private single-user app)"; when get_settings().news_contact is non-empty AND has no control character
      (any Unicode category C*, incl CR/LF) it becomes "NFLPickemIntel/1.0 (private single-user app; contact: <contact>)". A contact with a control char is ignored whole. Never logged.
  default_resolver(host) -> list[str]: socket.getaddrinfo(host, 443, type=SOCK_STREAM), unique addresses in order.
  build_client(transport) -> httpx.Client with trust_env=False, follow_redirects=False, timeout=TIMEOUT_S, verify left at its default (ON), no cookies kept (a new client per fetch_guarded call), transport passed through (None = real).
  is_public(address: str) -> bool: ipaddress; unwrap .ipv4_mapped first; False for NAT64 64:ff9b::/96 and 64:ff9b:1::/48; otherwise `ip.is_global and not ip.is_multicast` (use is_global, NOT "not is_private": 100.64.0.0/10 is not private but not global).
  fetch_guarded(url, *, host, resolver=default_resolver, transport=None, headers=None, max_bytes=MAX_FEED_BYTES, content_types=("xml",), max_redirects=MAX_REDIRECTS, clock=time.monotonic) -> FetchResult
     * Every hop (first request and each redirect): urlsplit; scheme must be https; hostname must equal `host` exactly (case-insensitive); no userinfo; port None or 443; else raise Blocked BEFORE any DNS lookup.
     * Resolve with resolver(hostname) (OSError/UnicodeError -> FetchError; empty list -> FetchError). If ANY address is not is_public -> Blocked. Use ONE address (the first) and connect to that: request URL = https://<ip>/<path>?<query> (bracket IPv6), header Host = hostname, request extension {"sni_hostname": hostname}. Headers: User-Agent = user_agent(), Host, plus `headers`.
     * Redirects (301, 302, 303, 307, 308 with Location): more than max_redirects hops -> FetchError("too many redirects"); resolve Location with urljoin against the HOSTNAME url (never the IP url), then validate it as above (off-host / http / userinfo / bad port -> Blocked). max_redirects=0 means any redirect fails (raise FetchError).
     * Stream the body with iter_bytes(); count DECODED bytes; more than max_bytes -> FetchError("too large"). After every chunk and before every hop check clock() against start + DEADLINE_S -> FetchError("deadline exceeded").
     * httpx errors (httpx.HTTPError, ssl errors, OSError) -> FetchError with a fixed short message (exception class name only; never the URL or server text).
     * Status: 403 and 429 -> Blocked("status 403"/"status 429"). Other >= 400 except 404 and 410 -> FetchError("status N"). 404/410/304 and 2xx are returned as FetchResult (body b"" for 304/404/410). Content-Type is checked only for a 200: its lower-cased media type must contain one of `content_types` substrings, else FetchError("content type").
     * etag / last_modified in the result come from the Etag / Last-Modified response headers, kept only if <= MAX_VALIDATOR_LEN chars and free of control characters (any Unicode category C*), otherwise None.
     * Error and Blocked messages are fixed short strings (<= 40 chars), never server text.
  check_robots(source, *, resolver=default_resolver, transport=None) -> None: fetch https://<host>/robots.txt with fetch_guarded(host=source.host, content_types=("text/plain",), max_bytes=MAX_ROBOTS_BYTES, max_redirects=0). ANY FetchError/Blocked -> raise Blocked("robots unavailable"). Status 404 or 410 -> allowed. Status 200 -> urllib.robotparser.RobotFileParser(), `.parse(body.decode("utf-8","replace").splitlines())` ONLY (never read(), set_url() or anything that calls urlopen), `can_fetch("NFLPickemIntel", source.url)` false -> Blocked("robots disallow"). Any other status -> Blocked("robots unavailable").
  fetch_feed(source, *, resolver=default_resolver, transport=None, validators=None) -> FetchResult: check_robots first; then fetch_guarded(source.url, host=source.host, content_types=("xml",), headers=conditional) where validators {"etag":..., "last_modified":...} become If-None-Match / If-Modified-Since only when valid by the same rule as above. Result status must be 200 or 304, else FetchError("status N").

parse.py  (feedparser + stdlib only)
  class FeedError(Exception)
  @dataclass(frozen=True) Item(title: str, url: str, published_at: datetime | None, extract: str)
  clean_text(raw: str, limit: int) -> str: strip tags with stdlib html.parser.HTMLParser(convert_charrefs=True) (text data only; drop everything inside script/style); then turn ALL whitespace into single spaces (str.split/join) BEFORE removing every character whose unicodedata.category starts with "C"; collapse spaces again; strip; cut to `limit` characters; strip.
  canonical_url(link: str | None, suffixes: tuple[str, ...]) -> str | None: return None unless: link is non-empty, has no whitespace, control char or backslash; scheme https; hostname is ASCII, lower-cased, equals a suffix or ends with "." + suffix (dot boundary: evilespn.com fails), has NO trailing dot; no userinfo; NO explicit port at all. Drop the fragment; drop query params whose key (lower) starts with "utm_" or is fbclid, gclid, ocid (keep the others in order); percent-encode non-ASCII path/query characters (quote, keep "/%:@!$&'()*+,;=-._~?" safe); empty path -> "/". Result longer than 2048 -> None.
  parse_feed(body: bytes, source: Source, now: datetime) -> list[Item]:
     * Parse with feedparser.parse(io.BytesIO(body)) ONLY. NEVER pass bytes or a str directly: feedparser would try to open it as a file path or a URL.
     * If there are no entries and (parsed.bozo or not parsed.get("version")) -> raise FeedError("not a feed"). A well-formed feed with zero entries returns [].
     * Read at most the first 100 entries. Per entry: title = clean_text(title, 200); url = canonical_url(link, source.link_suffixes); extract = clean_text(summary, 300) (summary only; never content, enclosures, images or stylesheet links); skip the entry (not the feed) when title or url is empty.
     * published_at = the entry's published_parsed (else updated_parsed) as a timezone-aware UTC datetime, else None; later than now + 1 day -> None (never invented, never trusted); earlier than now - 30 days -> skip the entry.

models.py  class NewsItem(Base), __tablename__ = "news_items":
  id Integer pk autoincrement; source String(32); title String(200); title_sha256 String(64); url_canonical String(2048);
  published_at DateTime(timezone=True) nullable; fetched_at DateTime(timezone=True); extract String(300) (not null); team_ids JSON; player_ids JSON; tags JSON (lists of strings, not null);
  __table_args__ = (UniqueConstraint("url_canonical", name="uq_news_url"), UniqueConstraint("source", "title_sha256", name="uq_news_source_title"), Index("ix_news_fetched", "fetched_at"))

0004_news_items.py: same style as backend/migrations/versions/0003_team_stars.py (explicit sa tables, op.create_table, revision "0004", down_revision "0003", downgrade drops the index and table). It must match the model exactly (`alembic check` is part of the gate). No metadata/create_all.

PROOF (no database; you cannot reach it):
  bash docs/gauntlet/logs/step-8c-evidence/pure.sh      -> must end with "PURE OK"
  (It runs the test file without conftest; tests that need the database error with "fixture 'session' not found" and are checked later by the coordinator.)
  Do NOT use `uv run` (its cache is outside your sandbox); the script uses backend/.venv/bin/python.

CONSTRAINTS (Ponytail: smallest correct diff):
- stdlib + httpx + feedparser only. No new dependency, no abstraction a test does not need, no config for a constant.
- Python 3.12 style, typed, ruff line length 120, match surrounding code (see backend/nflpi/ingestion/weather.py, service.py).
- Do not edit backend/tests/**, docs, or any file outside ALLOWED SCOPE. Do not weaken or skip a test.
- Never fetch anything from a URL found inside a feed. No network use.

DO NOT: commit, push, install packages, touch .env, run anything that opens a network connection.

RETURN: changed files, a 5-line summary, the last lines of pure.sh output, any blocker.
