# Design critic 1 — Alerts section of Settings (fresh Sonnet subagent, read-only, 393px dark and light)

Reviewed commit `b201bb4`, screenshots `../shots/after-alerts-*.png`, brief in `step-7.md`, `design.md`, `alerts.tsx`. It said it did not measure button heights or contrast ratios.

**VERDICT: FAIL** (Structural findings)

| # | Grade | Finding | Coordinator's ruling |
|---|---|---|---|
| 1 | Structural | A refusal ("Not delivered. …") is plain grey, the same as a success; the owner can miss that the test failed. | **Accepted.** Work order 3b: a result that is not a full delivery uses the `text-bad` token. Red test first. |
| 2 | Structural | The result sits under "N devices are subscribed on the server", so it reads as a footnote of the count. | **Accepted.** Work order 3b: the result goes directly under the buttons, above the count. Red test first. |
| 3 | Structural | The refusal names a host and a raw status ("fcm.googleapis.com", "(403)"); drop the host, say what to do. | **Rejected, with reason.** The roadmap row asks for the push service's status on screen, and the host says which push service (Apple or Google) refused. The sentence before it is already plain words from the server ("Push service rejected the alert."). What to do differs by status, so one fixed instruction would be wrong for some. |
| 4 | Structural | The "delivered" screenshot shows the result while the button still spins, and the busy button wraps to its own row. | **Accepted in part.** Real: the button stays busy while the device count is re-read after the result is shown. Work order 3b: do not hold the button busy for that. Red test first. The wrap of a busy button for the length of one request is left. |
| 5 | Visual | The result is `text-sm`, the count `text-xs`. | Left: the result is the more important line. |
| 6 | Polish | "0 devices are subscribed" beside "Alerts on" in the first screenshot. | Real, short-lived: the count on screen is from before the app re-sent its subscription on open. Deferred (noted in the step log). |
| 7 | Polish | The off-state screenshot is a crop. | Evidence only; retaken with the after-fix screenshots. |

Passing, in its words: buttons about 44px tall, the two buttons sit in one row at 393px, both themes legible, "Alerts on" and "Alerts off" distinct, the reminder copy plain and true.
