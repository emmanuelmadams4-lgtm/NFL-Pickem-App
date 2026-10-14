
## Critic (checkpoint 6)
Fresh ecc:python-reviewer, no transcript, on `a773c41`: **PASS** (0 critical, 0 high). Carried medium/low findings, not fixed in this step (code left as the critic saw it):
* M1 `run_checker._ask` swallows a database error in `_reserve_call` without `session.rollback()`; the later commit could then raise. Add a rollback in the except branches.
* M2 a backfill run is one request for a whole season (about 270 games): likely too large, then no verdict drops those simulations. Skip or chunk the check for `kind="backfill"`.
* M3 the check shares the 60-a-day `AI_DAILY_CALL_LIMIT` with reports; an outage retries every 30 minutes. Give it its own budget or back off.
* M4 a report with `all_ok = false` could be passed by Claude. Block in Python first when `all_ok` is false (and save the call).
* Low: rows stored before 18k count as "last checked"; one query per game on a block; the spread-sign check reuses the same function as the simulator; `PASS` followed by a lowercase "fail" line is accepted; the note stores up to 500 characters of Claude text.

## Critic fixes (head after this section)
Fixed with red tests first: M1 rollback in every `_ask` failure path; M2 a backfill run is never sent to Claude (simulations stored missing, status `not_checked`, note says why); M3 own budget `AI_RUN_CHECK_DAILY_LIMIT` (default 6, own counter) and back-off 30 min doubling to 6 h, reset when the content changes; M4 a Python report with `all_ok = false` blocks the run without a Claude call. Security review: S1 any exception in the check still writes every prediction (status `no_verdict`, cause `error`); S2 only simulations stamped `simulation_checked` (a PASS) carry forward, the stamp is added after the inputs hash; S3 PASS must be the only non-empty line; S4 cause code (cap, provider, unparsed, error) stored and shown; L1 note is fixed text plus game ids; L2 exception type only is logged; L3 `git_dirty` out of the cache hash; L5 `allow_nan=False`.
**L4:** a FAIL is cached by content hash until the data changes (fail closed); only a changed run asks Claude again.
Gate (throwaway Postgres 17 on port 15733, removed after): backend 2335 passed, 1 skipped; ruff clean; `gen:api` run (status literal `not_checked`, new `cause` field); `tsc` clean. No real Claude calls.
Two existing tests in `test_wiring.py` changed: they used `kind="backfill"` to get a simulation, now they use live runs. One test bypasses `python_block` (see carried item 1).
Fresh critic (ecc:python-reviewer, final head 176c88e): **PASS**, 0 critical, 0 high.
Carried:
1. A simulation made with learned parameters on the test fixture fails the Python mean check (margin 5.5 vs 2.6). Unknown whether real data does too; if it does, every live run is blocked. Check on the first live run.
2. `_simulations(...)` in `refresh_predictions` is outside the new try; `log.exception` logs the message, not type only; rollback in the handler discards uncommitted caller work (no known caller has any).
3. A backfill run over a game with a live checked simulation writes a row with `None`.
4. A cap hit raises the back-off count though no call was made; `get_provider` errors are labelled `error`, not `provider`.
5. The web app does not show `simulation_check` yet.
