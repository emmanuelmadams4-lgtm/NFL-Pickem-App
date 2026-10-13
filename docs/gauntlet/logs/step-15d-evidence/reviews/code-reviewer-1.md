# ecc:code-reviewer, round 1, on 7ecebaa..5e70a10 (saved from its final message; verdict WARNING: one HIGH)
1. HIGH api/live.py:54-57 candidate floor `max(today_start, now-LIVE_AGE)`: an `in` game past midnight Eastern vanishes mid-play (contradicts A3). Fix: `min`/8 h bound for in/lost, Eastern-day test only for post. -> FIXED a912883 (2 tests).
2. MED api/live.py:55,65-66 the same bound also drops `post` games of today more than 8 h old (a 1 PM final is gone by 10 PM). -> FIXED with the same change.
3. MED live_worker.py:103-120 sources run one after another; a slow Kalshi/Odds run (up to ~85 s) delays the next ESPN poll, which could push the gap past 120 s. -> CARRIED (needs hung quote sources; `stale` shows it).
4. LOW live_worker.py:66-72,95,108-116 `now` is the step's start, so reservations and `next_kalshi` use a time up to 85 s old. -> CARRIED.
5. LOW worker window 5 h vs route 8 h: a delayed game stays `in` with frozen numbers for up to 3 h. -> FIXED: worker window 8 h.
Checked, no defect: sweep predicate, `with_deadline` closure, Eastern-date conversion across DST, Kalshi row/poll age checks, token dependency.
