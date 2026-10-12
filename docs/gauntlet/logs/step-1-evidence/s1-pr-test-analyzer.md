# ecc:pr-test-analyzer on c1ba844 — VERDICT: warn
Pinned: A1, A2, A3, A4, A7, A8, A9, A10, A11, A12, A13 yes. Weak: A5 ("until kickoff" and mixed success/failure subscriptions untested), A6 (TICK_SECONDS is a constant check; loop() not exercised), A14 (test still pinned 9/12 while the rule is 12; the 12-point case sat on a rounding boundary).
Changes made by the coordinator: A14 re-pinned to 11 (no flag) and 14 (flag), renamed to twelve_point. A5 "until kickoff" left untested by choice (lean suite; behavior already holds via the kickoff > now filter).
