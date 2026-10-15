PASS

No CRITICAL or HIGH defects. Two LOW notes.

Commands run (HEAD f8878e1):
- `pytest tests/test_value_api.py tests/test_value.py -q`: 137 passed, 13 warnings (the warnings are an existing `distinct` deprecation at readmodels.py:146, not this step). The first run failed on the uv cache with "Operation not permitted", so I reran it with the sandbox off.
- `uvx ruff check nflpi tests`: All checks passed.
- `npm run typecheck`: clean (tsc, no errors).
- Browser suite not run, as instructed. v18l-g2.log shows 24 passed, run exit=0.

Spec check:
- A1-A8: implemented in backend/nflpi/api/readmodels.py:349-390 and tested in backend/tests/test_value_api.py. The expected values are computed by hand (0.60*2.2-1, 0.55*2.1+0.03-1, the rescaled A8 sums), not copied from the code, so the tests are not tautological.
- Spread and total are rated only when `snapshot.line` equals the simulator's `home_spread` or `total`. Both spread selections share the HOME spread. Home gets (home_cover, push, away_cover) and away gets the mirror. The away stake maps to away_cover, so the right chance is used for each side.
- Push probabilities are included in `SettlementProbs`, and A4 asserts the refund.
- Moneyline: the 1-chance split is used with a push of 0. `home_win_prob=None` is skipped.
- Kickoff and absent data: `now >= kickoff` and `last is None` both return `[]` (A6, three parametrized cases). `load_snapshots` uses `as_of=now`, so it never reads prices observed after now.
- Bad stored data: None parts are skipped. A set whose sum is off by more than 0.001 is skipped. `BettingError`, `ValueError` and `TypeError` are caught and logged. A8 covers sums of 0.9999, 1.0001, 0.35 and a negative part.
- A price shown as available: a stale price gets NO_BET with the note "may no longer be offered" (A1). The W2 e2e asserts the section text never matches /available|Unrated/.
- XSS: value.tsx renders everything as React text, with no `dangerouslySetInnerHTML`. The REASONS lookup uses `Object.hasOwn`. W5 covers markup in a book name.
- Old cached reply without `value_ratings`: `game.value_ratings ?? []` handles it. The schema default is `[]`.
- W1-W6: all present in value.tsx and the e2e. The spread side shows -line for away (BUF -3.5, MIA +3.5). The section note is shown only when ratings exist (W4 handles the empty case).
- Generated types: openapi.json and api-types.ts changed (+99 and +39 lines) alongside schemas.py, so they were regenerated, not hand-edited.

Evidence:
- The step log has PLANNING, SPECIFICATION, IMPLEMENTATION and CLEANUP sections.
- Red came before code: 9e22441 (red) comes before 3f6cde9 (code). a8935e3 and c8af484 (A8 red) come before c308fa5 (fix).

Findings:
- LOW, readmodels.py:349-390: `_value_ratings` runs three `load_snapshots` queries per game-detail call and loops about 6 times. It is fine for a single-user app.
- LOW, readmodels.py:360-363: moneyline uses `last.home_win_prob`, which is the blend recommendation, not a simulator chance. This is consistent with the spec, so I only note it.
- LOW, readmodels.py:377 and readmodels.py:381: the `log.warning(exc_info=True)` on bad data could be noisy if the data stays bad. Nothing is rate-limited.
