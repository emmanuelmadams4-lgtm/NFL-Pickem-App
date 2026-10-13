# Fresh critic, round 2 — step 8a2 on `20b82cf` (code at `88037c5`)

Fresh subagent, no build transcript. VERDICT: **FAIL** (one major, in a test).

Its own gate run (`critic-b-*.log`): pytest 1081 passed, ruff clean, gen:api no drift, typecheck exit 0, browser 119 passed (2 skipped: the screenshot spec, as in every run). Load before: 11.52 19.55 16.23 (the script waited about ten minutes for the 1-minute figure to drop under 12). Lane-guard: the one granted finding, nothing else. It confirmed critic 1's F1 is fixed, scope is clean, no prediction logic in the client, missing shown as missing, no feed text in an attribute, all cited logs exist.

| # | Severity | Finding | Decision (coordinator) |
|---|---|---|---|
| 1 | MAJOR | `stars.spec.ts` ST3: the "Injury report not in yet" assertion sat inside `if (next)` and the fixture has no such week 5 game, so it never ran; the silent state (report in, lists present, no star out) had no check either. | Accepted. Mine (my test). New tests ST3b and ST3c replace the API's stars block for one game (the pattern `phone-layout.spec.ts` already uses) and check both states at both widths, unconditionally. The dead `if (next)` block is gone. The server side of "nothing known yet" is in `test_api.py` (`out == []`, `reports_seen == 0`). |
| 2 | MINOR | The worker's `try/except` around the star refresh was not tested: the test made it return "failed", never raise. | Accepted: the test now also makes it raise and checks the round goes on. The guard stays (a star refresh must never stop the injuries and alerts round). |
| 3 | MINOR | Red for work orders 9 and 10 was by reading, no failing-run log. | True, said in the log. The test commits precede the fix commits. |
| 4 | MINOR | ST1 checks position, status, count, age with `toContainText` only. | Not changed: ST2 does the geometry checks on the stress card at both widths; ST1's name is checked for clipping. |
| 5 | MINOR | The bare age "3h ago". | Not changed: decided in design critic 2 item 6. |
| 6 | MINOR | `game_stars` runs once per game in `summaries` and again in `game_detail`. | Carried to step 13 (speed), as before. |
| 7 | NIT | Indent of the inner group div; `no_list.length > 0` written twice. | Not changed: a production edit for a nit would cost a new build and review round; carried to the next step that touches the card (step 15). |
| 8 | NIT | Stale comment in `e2e_seed.py`. | Fixed (my file). |
| 9 | NIT | `views.py` imports `stars` and `ALERT_STATUSES` from one module. | Not changed. |
| 10 | NIT | `aria-label` built from the team name. | Not a fault: no player or feed text reaches an attribute. |

Could not verify (its list): who built and who reviewed (hive messages only), recorded load figures, the top of the phone game screen under the sticky header in the full-page shot (ST4 asserts it at 393 px), light theme by eye (ST7 runs axe in both), a live nflverse refresh.
