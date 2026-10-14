
## Critic (checkpoint 6)
Fresh ecc:python-reviewer, no transcript, on `a773c41`: **PASS** (0 critical, 0 high). Carried medium/low findings, not fixed in this step (code left as the critic saw it):
* M1 `run_checker._ask` swallows a database error in `_reserve_call` without `session.rollback()`; the later commit could then raise. Add a rollback in the except branches.
* M2 a backfill run is one request for a whole season (about 270 games): likely too large, then no verdict drops those simulations. Skip or chunk the check for `kind="backfill"`.
* M3 the check shares the 60-a-day `AI_DAILY_CALL_LIMIT` with reports; an outage retries every 30 minutes. Give it its own budget or back off.
* M4 a report with `all_ok = false` could be passed by Claude. Block in Python first when `all_ok` is false (and save the call).
* Low: rows stored before 18k count as "last checked"; one query per game on a block; the spread-sign check reuses the same function as the simulator; `PASS` followed by a lowercase "fail" line is accepted; the note stores up to 500 characters of Claude text.
