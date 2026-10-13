# ecc:silent-failure-hunter on 26a8598 (read-only, fresh subagent). Findings and what the coordinator did.
1 HIGH whole-source parse failure (every item fails per-item validation) is recorded as ok, rows=0; freshness looks healthy. -> FIXED (R7): a reply of 3 or more items where none is usable fails the run (backoff, old rows kept). Fewer than 3 stay plain skips.
2 HIGH final session.commit() outside the try: a DB error leaves the run "running" and no back-off -> tight retry loop. -> FIXED (R2), red test first.
3 HIGH an event that vanishes from the scoreboard (or has an unknown state) never gets a closing row; the last stored "in" row stays. -> NOT CHANGED here (no invented data). Carried to step 15d API: a stored "in" row whose fetched_at is older than ~2 minutes must be shown as stale; the plan already specifies that.
4 MEDIUM failed summary -> null win probability row. -> same as code-reviewer 4: by design, carried.
5 MEDIUM mark_ok(credits_left=None) erased a known count. -> FIXED (R4).
6 MEDIUM Odds wrapper hid "status 401/429". -> FIXED in WO-4 (wrapper removed; fixed words reach ingestion_runs and source_status).
7 MEDIUM illiquid / old quotes carry no marker. -> empty-side case FIXED (R5); wide spreads are stored with the raw bid and ask so the display decides (plan: over 10 cents = "no price"); source_ts null means unknown. Carried to the API step.
8 MEDIUM Kalshi page cap, no signal. -> FIXED (R8) as a warning.
9 LOW skip paths (no key, credits low, backoff) leave no ingestion_runs row. -> by design: nothing was attempted. Documented in the log.
10 LOW orientation flip with absent tie; finished_at = start time. -> flip: honest null, carried; finished_at uses the injected `now` so tests are deterministic, durations are not recorded. Carried.
