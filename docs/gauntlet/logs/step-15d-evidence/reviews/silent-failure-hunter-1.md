# ecc:silent-failure-hunter, round 1, on 7ecebaa..5e70a10 (saved from its final message)
1. HIGH api/live.py:54-57 in-progress game vanishes after midnight ET (same as code-reviewer #1). -> FIXED a912883.
2. HIGH live_worker.py:66-74 + run.py:218-223 a deadline-cut or failed summary is counted as a summary failure, the run is `ok`, and the `in` row is stored with `home_wp` null; stale stays false. Suggested: fail the run or carry the old value. -> CARRIED by decision: failing the run would back ESPN off 15 min (worse); carrying forward breaks "missing stays missing"; Dwight H2 accepted null = "no probability right now". Contract note for the web.
3. MED live_worker.py:54-58,103 a `post` row with no final probability is never retried (window closes). -> FIXED: such a game stays in the window until the summary is stored (test).
4. MED live_worker.py:77-83 only the class name is logged, at warning every 5 s on a repeating fault. -> CARRIED (rate limit later; class-only is Dwight's requirement).
5. MED live_worker.py:77-83 `session.rollback()` inside the handler could itself raise and skip the other sources for one wake. -> CARRIED (next wake recovers; run_forever catches).
6. MED live_worker.py:149-162 no supervision of the thread. -> CARRIED (stale is the signal; start is logged).
7. LOW api/live.py:102-104 a flat Kalshi price older than 15 min is null even when Kalshi confirmed it. -> CARRIED (Dwight's own H5 condition; stated in the contract).
Not ranked: the sweep runs at start only; `StepResult.results` is unused by the loop.
