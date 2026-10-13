# Step 8c-8f,8h design for security review (Toby, lane news, 2026-10-13)
Backend only. Module `backend/nflpi/ingestion/news/` (sources, fetch, parse, match, store, run). No API, worker, web or AI-pack code (8g). Nothing the feed says is ever fetched, run or sent to a model.

## Allowlist (code constant `sources.py`, not user input, not env)
| id | feed URL | exact host | item link must be https and end in |
|---|---|---|---|
| espn | https://www.espn.com/espn/rss/nfl/news | www.espn.com | espn.com |
| cbs | https://www.cbssports.com/rss/headlines/nfl/ | www.cbssports.com | cbssports.com |
Left out on purpose: Pro Football Talk (feed 301s to www.nbcsports.com, off host; robots.txt 301s too, so it fails two guards); Yahoo, NFL.com, team sites, Google News, AP, PFR, Athletic, Reddit/X (terms, robots deny, 403, paywall; see step8-scrape-plan.md). Adding a source = one row.

## Fetch guards (`fetch.py`, one function, every request incl. robots.txt)
1. https only, port 443, no userinfo, host must equal the source host exactly.
2. Resolve DNS; refuse the request if ANY address is not globally routable (private, loopback, link-local, metadata 169.254.*, multicast, reserved, unspecified, IPv6 mapped/ULA). Connect to the checked IP (URL = IP, `Host` header + TLS SNI/verify = hostname), so a second DNS answer cannot swap the address (rebinding).
3. `follow_redirects=False`; manual loop, max 3 hops, each hop re-validated by 1-2 and must stay on the same exact host.
4. 10 s connect/read timeout, 20 s wall clock for the whole fetch, 2 MB cap counted on DECODED bytes while streaming (gzip bomb safe), robots body cap 512 KB.
5. Content-Type must be xml/rss/atom/text for the feed and text/plain for robots; anything else is a failure.
6. UA `NFLPickemIntel/1.0 (private single-user app)` + optional contact from env `NEWS_CONTACT`; never rotated, no proxies, no headers imitating a browser.
7. robots.txt fetched through the same function before every feed fetch, parsed with `urllib.robotparser`: 200 text/plain = parse and obey; 404/410 = allowed; 401/403, 5xx, timeout, redirect, non-text/plain = DENY (fail closed). Disallow = source blocked.
8. Conditional GET (If-None-Match / If-Modified-Since), validators kept in `app_settings`; 304 = ok, 0 new rows.
9. Rate: at most 1 poll per source per 30 min (from `ingestion_runs`).
10. Feed bytes go to `feedparser.parse(bytes)` only (never a string/URL, so feedparser cannot fetch). Max 100 entries read per poll.

## Untrusted text (`parse.py`)
Title <= 200 chars, extract <= 300 chars (feed summary only, no article page is ever fetched, no body stored). Tags removed with stdlib `html.parser` (script/style content dropped), entities decoded, then every Unicode category C* char removed (control, bidi override, zero-width, private-use, unpaired surrogate), whitespace collapsed. Item link: https only, host in the source's suffix list, no userinfo, fragment and tracking params dropped, <= 2048 chars; else the item is skipped. Never followed. Dates: feed value or NULL (never invented); more than 1 day in the future = NULL; older than 30 days = skipped.

## Tie, dedupe, store, failure
- Team match: exact word-boundary on the 32 `teams.name` and `teams.nick`, case-insensitive. Player match: exact full name from `team_stars` (names cleaned the same way), only when it maps to one player_id; a player adds his club. Keywords tag injury / trade / coach / playcaller. No match = stored untagged.
- Table `news_items` (migration 0004): source, title, title_sha1, url_canonical, published_at, fetched_at, extract, team_ids[], player_ids[], tags[]. Unique url_canonical and unique (source, title_sha1); `INSERT .. ON CONFLICT DO NOTHING`; rows older than 30 days deleted after a successful poll. All values bound parameters (SQLAlchemy), no string SQL.
- Failure: per source one `ingestion_runs` row (dataset `news:<id>`). Blocked = 403, 429, robots deny, off-host redirect, private address -> failed, error starts `blocked:`, that source is skipped for 24 h, never retried in a loop, UA never changed. Timeout/5xx/oversize/bad XML -> failed, next normal window. One source failing never stops another or touches stored rows. App works with zero news.
- Tests: recorded fixtures only, httpx MockTransport + injected resolver; no network in pytest. One real feed per source recorded by hand into `tests/fixtures/news/`.

## Questions for you
1. Is pinning the connection to the checked IP enough, or do you want a second resolve-after-connect check? 2. Is fail-closed robots (HTML/redirect/5xx = deny) what you want? 3. Anything missing in the guard list?
