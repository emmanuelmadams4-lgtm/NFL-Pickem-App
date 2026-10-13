# Review fan-out, round 1 (HEAD e24590b, read-only subagents, none ran the gate)

Five reviewers: ecc:code-reviewer, ecc:security-reviewer, ecc:silent-failure-hunter, ecc:python-reviewer, ecc:pr-test-analyzer. No CRITICAL from any. Verdicts and what was done:

| # | Finding (reviewer) | Severity | Decision |
|---|---|---|---|
| 1 | Any robots trouble (timeout, 5xx, redirect, HTML) became `Blocked` = 24 h stop (code, python, silent, security-adjacent) | MEDIUM | FIXED in WO-3: only an explicit refusal (401/403/429/disallow/private address) is a block; trouble is a plain error retried next window. Design amended; Dwight told. |
| 2 | A hostile non-ASCII ETag crashes every later poll of that source (`UnicodeEncodeError`, outside the try) (security) | MEDIUM | FIXED in WO-3: validators must be printable ASCII. Tests: café, bidi char, 257 chars; 256 plain chars kept |
| 3 | `::/96`, 6to4 `2002::/16`, Teredo `2001::/32` pass `is_global` on Python 3.13 (security) | LOW | FIXED in WO-3 + tests |
| 4 | Gzip bomb can inflate one chunk before the cap check (security) | LOW | FIXED in WO-3: `Accept-Encoding: identity` + test |
| 5 | A feed whose every entry is rejected (domain moved) is recorded ok with 0 rows and its ETag saved, so it stays silent forever (silent-failure) | HIGH | FIXED in WO-3: all entries unusable (not merely old) raises `FeedError`, validators not saved. Tests |
| 6 | Stale validators stay when a good answer carries none (code, silent) | LOW | FIXED in WO-3 + test |
| 7 | `fetch_guarded` ~85 lines / 5 levels; `run_news` ~70 lines; `sources` parameter shadows the module; untyped callables; magic numbers (python, code) | HIGH (style) | FIXED in CLEANUP WO-4 (all functions < 50 lines, no behaviour change, 189 tests identical) |
| 8 | `added += bool` (python) | LOW | FIXED in WO-3 |
| 9 | Test survivors (pr-test-analyzer): deadline value, client timeout, URL control chars and backslash, Location checks, missing Location, IPv6 bracket pinning, default_resolver, validator length edges, 30-minute edge and newest-run ordering, validators on bad feed, generic exception path, style tags, tracker case, future-date edge, leading word boundary | mixed | FIXED: 22 tests added before WO-3 (13 were red for the intended reason) |
| 10 | Misnamed test (40 vs 100 characters) | LOW | Renamed |
| 11 | DB work outside the per-source try: a dropped DB connection mid-poll can raise out of `run_news` (silent-failure) | HIGH as stated, LOW in practice | CARRIED: with the database down nothing can be recorded anyway; the poll runs inside the worker that owns the session |
| 12 | Empty `teams`/`team_stars` at poll time stores items untagged and a later poll never re-tags them (silent-failure) | MEDIUM | CARRIED to wave 5: the worker must ingest teams and stars before news. Items are never tied wrongly, only untied |
| 13 | Undated items still in a feed are pruned at 30 days and re-inserted with a new id (code, silent) | MEDIUM | CARRIED: harmless for display; wave 5 should not alert on `id` order alone |
| 14 | A traded star's club is the club of his newest star row; in the offseason that is last season's (code) | MEDIUM | CARRIED: a tie says "mentions", not "plays for now"; recorded in the hand check |
| 15 | One row that violates a column limit would fail the whole batch (code) | MEDIUM | CARRIED: titles/extracts/urls are cut or rejected before insert, so unreachable today |
| 16 | Two titles identical within one source are one story (`uq_news_source_title`) (silent) | LOW | CARRIED: as specified in the plan (unique on url + title hash) |
| 17 | `blocked:` is a text prefix in `ingestion_runs.error` (code, silent) | LOW | CARRIED: ingestion_runs is another lane's table |
| 18 | `getaddrinfo` has no timeout; robots not re-checked on a same-host redirect target; no cross-process poll lock; `*.espn.com` subdomain links accepted (security, silent) | LOW | CARRIED (also Dwight's L3) |
| 19 | prune inside a source's run deletes across sources (silent) | MEDIUM | CARRIED: it is the 30-day retention the plan asks for (rows older than 30 days by our own fetch time) |
