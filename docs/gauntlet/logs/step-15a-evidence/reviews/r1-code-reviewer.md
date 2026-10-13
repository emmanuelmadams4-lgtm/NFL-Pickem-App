# ecc:code-reviewer on 26a8598 (read-only, fresh subagent). Findings and what the coordinator did.
1 HIGH store.py:151 backoff exponent overflows after ~38 straight failures (timedelta OverflowError inside the except path; backoff silently off). -> FIXED in WO-5 (R1), red test first.
2 MEDIUM run.py:374 Odds credit gate never lifts after the 35-day stop (stored credits_left < 50 read forever). -> FIXED (R3), red test first.
3 MEDIUM Kalshi bid 0 / ask 1 gives mid 0.5 = an invented probability. -> FIXED (R5): a market with bid 0 and ask 1 is unusable.
4 MEDIUM failed/skipped summary fetch writes a null win-probability row (row churn). -> NOT CHANGED, by design: "missing stays missing" (CLAUDE.md data rule); the score still updates; the cost is one extra row. Carried (advisory): step 15d API must treat a null home_wp as "no probability right now".
5 MEDIUM flipped orientation loses home_wp when tie_wp is absent. -> NOT CHANGED: a probability with no tie value cannot be flipped honestly; null is the honest answer (same row rule as 4). Carried.
6 MEDIUM Kalshi paging stops at 3 pages with no signal. -> FIXED (R8): a fixed-text warning is logged. (An NFL week has about 32 open markets; 600 would be 300 games.)
7 LOW kind change pregame->live not recorded when prices equal. -> FIXED (R6): kind is part of the change test.
8 LOW run row stays "running" if the process dies. -> same as the existing run_logged; R2 closes the commit-failure path. Carried (process kill).
9 LOW dead code (`total == 0`), duplicated blocked check, mark_ok twice. -> FIXED (R9/R3/R4).
10 LOW parameter `run_source` shadows its function; run.py 392 lines. -> parameter renamed (R9); split not done (under the 800-line ceiling; carried).
11 LOW migration down_revision "0003" hard-coded. -> known: the integrator re-points at landing (comment in the file, in the log and in the done message).
Not issues (reviewer checked): orientation maths, safe_error precedence, Eastern-date matching, _source_time bounds.
