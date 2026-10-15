# Fresh critic 1: step 8g web, on `2f23ba6` (read-only subagent, no transcript, 2026-10-15)

Verdict: **PASS**, no CRITICAL or HIGH. Gate: typecheck 0; `s8g-critic-1` (news8g on a fresh build) 5/5, 15.5 s.
N1-N6 and the contract's screen notes are met; the tests are real; the offline cache is safe (news is a new key, so
there is no old entry). Red-before-fix order holds (9981e74 < 91da4a9, 11a9a34 < 2f23ba6); cleanup is recorded; the
triage is reasonable.

## Findings and triage (Jim)
- MEDIUM, test flakiness `news8g.spec.ts:105`: the app retries a 500 twice (~3 s) and the check used the default 5 s.
  **Fixed (test only)**: `{ timeout: 15_000 }`. Rerun `s8g-green-3` (fresh build): 5/5.
- LOW: N2 is not tested with `http://` or `HTTPS://`. Not taken: the same `startsWith("https://")` branch as the
  `javascript:` case, which is tested; both fail safe.
- LOW: N5 "page still works" only checks `#market`. Not taken: it proves the page rendered past the failed section.
- LOW: the N3 `&lt;b&gt;` check is near-automatic in React. Kept as a regression guard.
- Missing: the screenshots were from before WO2. **Retaken** on `2f23ba6` as `final-*.png` (accent links and the "·" visible).
