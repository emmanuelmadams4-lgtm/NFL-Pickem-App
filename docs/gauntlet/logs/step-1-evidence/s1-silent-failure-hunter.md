# ecc:silent-failure-hunter on c1ba844 — VERDICT: warn
1. MEDIUM notify/push.py _send: only WebPushException/RequestException caught; one malformed subscription aborts all reminders and the heartbeat. -> test added (red), WO-E F1, F2
2. MEDIUM push.py reminders: send then record, commit at end; a crash on a later game can resend; with several subscriptions one success marks it done. carried (single user, one or two devices); partial via F1
3. MEDIUM advisory lock on pooled connection; unlock failure leaks the lock; skip branch logs nothing. -> WO-E F5
4. MEDIUM pick lock bypass: a final game with time_tbd stays editable. -> test added (red), WO-E F4
5. LOW ai/research.py _reserve_call on a retry raises outside try; failed row not saved. -> WO-E F8
6. LOW jobs.loop: rollback can raise if DB is down; long cycle shows false degraded; reminders only every 5 min. -> WO-E F3 (cycle in a thread)
7. LOW health: malformed heartbeat -> 500. -> WO-E F7
