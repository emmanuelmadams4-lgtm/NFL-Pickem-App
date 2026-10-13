# Step 7 of 14 — Alerts end to end (T2), lane `alerts`

Coordinator: Jim (hive `jim-mv5mje0k`). Builder: Ryan (Codex dev, hive `ryan-mv5mjwq1`). Reviewers: Dwight (security), Angela (review and fresh critic).
Branch `lane/alerts`, base `main@696c64f`. State file: `~/.claude/plans/nfl-pickem-lanes/lane-alerts.md`. Evidence and logs: `docs/gauntlet/logs/step-7-evidence/`.
Dispatch: hive message `2026-10-13T00-18-07-540Z-dc6a88` (god). Owner's date: Thursday 2026-10-15.

## What this step builds, in plain words

* **Builds:** the alerts on his phone. One reminder on every game day, an hour before that day's first kickoff. An alert when something drastic changes for a game before it kicks off. A "Send test alert" button that says what the push service answered. The app keeps its alert subscription alive by itself.
* **First inside it:** the two follow-ups from step 6 (an older stored pick sent after the app is reopened; the offline banner's time).
* **Does not build:** star-player alerts and the morning summary (they need the star list, step 8). A real alert on his iPhone and the live keys: his go-live step, **PENDING**.

## 1. PLANNING

* **Roadmap row:** `docs/gauntlet/PLAN.md` row 7 (D19, D20, D25, D28), amended by D47 (threshold 0.07, replaces D28's 0.10).
* **Base and branch:** `lane/alerts` on `main@696c64f`, worktree `.claude/worktrees/lane-alerts`. Depends on step 6 (landed, PR #5).
* **Rigor tier:** T2 (new user-facing behaviour). No one-way door: no schema change planned, no new dependency.
* **Deployment reach:** local only. God pushes, opens the pull request, merges and rebuilds the live app. No VAPID key creation on the live app and no real push to his phone by me.
* **Validation that needs another environment:** a real alert on the owner's iPhone (needs HTTPS through Tailscale Serve and live VAPID keys): **PENDING**, owner's go-live (PLAN row 11).
* **Lane:** `lanes.md` gives lane alerts `apps/web/**, packages/shared/**, backend/nflpi/**, backend/tests/**, backend/migrations/**, scripts/smoke.sh, scripts/e2e-server.sh, design.md, docs/design/**, docs/IPHONE_PWA.md` and this log. The expected file list went to god (hive outbox `step7-files.json`) so he can narrow it and open step 8a.

### Pre-flight (Product Mode, T2)

1. **Problem:** he misses the pick deadline, or a late change to a game, because the app only tells him when he opens it.
2. **Why now:** the phone app landed in step 6; alerts are the reason it is installed.
3. **Scope:** the smallest set that delivers D19 and D20 and proves delivery without his phone. Cut: star alerts and morning summary (D25, step 8), per-alert on/off switches, an alert history screen, quiet hours.
4. **Success signal:** on a game day he gets exactly one reminder an hour before the first kickoff, and "Send test alert" shows "delivered". Measured locally by tests; on his phone at go-live.
5. **Reversibility:** two-way. Alerts can be turned off in Settings; the reminder has an Off value.

### Assumptions

| Assumption | State |
|---|---|
| "Every game day" uses the US Eastern calendar day (D19 notes). | validated (owner decision notes) |
| The reminder is on, at one hour, until he changes it. Today it is off until set. D19 is his request for it, so on is the default. | assumed (told to god in the scope message) |
| "Drastic" = winner flips, label changes, starting QB changes, or win chance moves 7 points (D20 notes, D47). | validated |
| Headless Chromium cannot get a real push subscription (no push service), so browser tests stand in a fake subscription and deliver the push through the browser's debug protocol. Real encryption and signing are proven server-side against a local mock push service. | assumed; checked in SPECIFICATION |
| No schema change: the `notifications`, `push_subscriptions` and `app_settings` tables already hold what is needed. | assumed; a need for one goes to god first |

### Skills

* `/graft`, `/jevgrep`: jevgrep's key check fails on this machine (memory note); discovery was by exact-symbol `grep` on `push`, `reminder`, `alert_` and reading the eight files they named (listed in the state file).
* Project `tdd` skill: none in the repo; `/tdd` rules apply. Public seams: the HTTP API, `push.send_kickoff_reminders`, `push.alert_prediction_changes`, `engine.refresh_predictions`, and the browser.
* `/ponytail`: in every work order.
* `harness-engineering`: N/A (no runner, evaluator or approval boundary changes).
* Design Gauntlet: applies to the Alerts section of Settings (one new button, one result line, reworded reminder). Brief and critic report in the evidence folder.
* Parallel Lanes: lane alerts; `lane-guard.py check` before landing.

### Baseline

`gate.sh baseline` on `696c64f` (logs `baseline-*.log`): pytest **115 passed** · ruff clean · gen:api no drift · typecheck 0 · e2e **89 passed, 2 failed, 2 skipped**. The 89 are main's own tests, all green; the 2 failures are P23 and P24, which I added to the tree while the run was in flight, so this run is also their red proof. The 2 skips are `shots.spec.ts` (screenshots only). `test_alerts.py` did not exist yet when pytest ran.

## 2. SPECIFICATION

Frozen before any production change. The gate is `docs/gauntlet/logs/step-7-evidence/gate.sh <label>`: pytest, ruff, `gen:api` with no drift, typecheck, `npm run e2e`. Green twice in a row to land.

### Acceptance criteria

**Step 6 follow-ups (browser, `apps/web/e2e/pwa.spec.ts`)**

* **P23** After the phone refused to store the pick queue and the newer pick was sent, reopening the app does not send an older stored pick. (Dwight R7, Angela F-3; also asserts a write was refused, Dwight R8.)
* **P24** The offline banner's "showing data from" is the age of the data on screen, not of the last server reply of any kind. (Angela F6.)

**Server (`backend/tests/test_alerts.py`)**

* **N1** A win-chance move of 7 points counts as drastic (`alert_move_threshold` default 0.07, D47).
* **N2** One reminder per game day, sent in the window that opens `reminder_minutes` before that Eastern day's first kickoff and closes at that kickoff. Sent whether or not he has picked. Not for a later game the same day. Not for a day whose games have no clock time. Opens `/sheet/`. Title `Games today: first kickoff 1:00 PM ET` (one game: `Game today: kickoff 8:15 PM ET`), body `2 games today. First: MIA @ BUF.` (one game: `1 game today: NYJ @ LV.`). Time to live = seconds to kickoff, urgency high. Recorded only once delivered, so a failed send is retried (kept from step 1). On at 60 minutes until he changes it; 0 is off.
* **N3** A starting QB change for a game is alerted even when the win chance barely moves: title `QB change: AWAY @ HOME`, body names the new QB.
* **N4** A label change (easy pick, tough matchup, coin flip) is alerted even when the win chance barely moves: title `Now a tough matchup: AWAY @ HOME` (`Now an easy pick`, `Now a coin flip`), body says `Was an easy pick` and so on.
* **N5** No change alert once the game has kicked off (`alert_prediction_changes(session, events, now=...)`), and nothing is recorded for it.
* **N6** `POST /api/push/test` (token required) sends `Test alert` to every subscribed device and returns `{configured, devices, delivered, results: [{host, ok, status, error}]}`: what the push service answered, per device, by host only (never the full endpoint, which is a secret address). A device the push service calls gone (404, 410) is dropped. Push not set up: `configured: false`, nothing sent.
* **N7** A real push leaves the server signed and encrypted: a local mock push service receives it with a valid VAPID token (ES256, signed by the server key, audience = the push service, not expired) and an `aes128gcm` body that only the phone's key can read.

**Browser (`apps/web/e2e/alerts.spec.ts`), written with work order 3**

* **A1** Opening the app with alerts on re-sends the subscription to the server; after the server's row is deleted, the next open re-creates it.
* **A2** When the server's public key differs from the one the device subscribed with, the app subscribes again with the new key and sends that.
* **A3** A push delivered to the service worker shows a notification with the alert's title and body; tapping it opens the game.
* **A4** Settings, Alerts: "Send test alert" shows the result in words ("Delivered to 1 device." or the push service's refusal). The reminder control reads as one reminder per game day.
* **A5** Accessibility: no serious or critical axe issue on Settings in dark and light; the result line is announced (`role="status"`).

**Operational**

* **O1** `scripts/smoke.sh <base-url>` checks health, the token, meta and (only with `--push`) the test alert, prints PASS or FAIL per check, exits non-zero on any FAIL. Run by me against the lane server only.
* **G** The whole gate is green twice in a row on the final commit; no existing test weakened. Tests that pinned the old per-game "No pick yet" rule are rewritten to the D19 rule and listed in this log.

### Instrumentation

Every alert is a row in `notifications` (kind, game, dedupe key, time, payload); failed sends are logged with the push service's status. The test alert returns the same status to the screen.

### Out of scope, with the reason

D25 star alerts and morning summary (need step 8's star list). Per-kind switches, alert history, quiet hours (not asked for). An allowlist of push-service hosts on subscribe: left to Dwight's review to rate.

### First failing tests (red for the intended reason)

* Browser, `red-wo1.log` (from the baseline run): **P23** fails at "the older stored pick was not sent on reopening" (expected `LV`, received `MIA`); **P24** fails with the banner reading "Offline · showing data from just now" where "5h ago" is expected.
* Server, `red-wo2.log`: **9 failed, 1 passed**. N1 `0.1 == 0.07`; N2 no reminder sent, and the default reads `None` not 60; N3 and N4 no change event; N5 `alert_prediction_changes()` takes no `now`; N6 and N7 `POST /api/push/test` answers 405. The one that passes is a guard (no reminder after the first kickoff or for a day with no clock time): it stays true on the old code because the reminder is off until set.

### Existing tests the D19 rule changes

`backend/tests/test_api.py::test_push_subscribe_alerts_and_reminders_are_deduplicated` and the reminder tests in `backend/tests/test_hardening.py` (A5, A6, A12) pin the old per-game "No pick yet" rule. They are rewritten to the D19 rule in work order 2 by me, not by the builder; what each one guards (time to live, urgency, retry after a failed send, a gone subscription, rescheduled kickoff, postponed, no clock time) is kept.

## 3. IMPLEMENTATION

Builder: Ryan (Codex). Each work order is a file in the evidence folder; I read the real diff, checked scope and reran the proof myself (Ryan cannot bind ports or reach the test database).

| Work order | What | Model, effort, try | Commit | My proof |
|---|---|---|---|---|
| 1 (`wo-1.md`) | Step 6 follow-ups: pick queue drops the older stored copy after a refused write (P23); offline banner shows the age of the data on screen (P24) | gpt-6-sol, high, try 1 (Jev `model:alerts:wo-1`: sol 1.0, high 1.0) | `30bb253` | `gate.sh wo1`: browser tests 91 passed, typecheck 0. Server tests 13 red on purpose (work order 2). |
| 2 (`wo-2.md`) | Server side: threshold 0.07 (N1), one reminder per game day (N2), QB and label change alerts (N3, N4), none after kickoff (N5), `POST /api/push/test` (N6, N7) | gpt-6-sol, high, try 1 | `6ce6d72` | `gate.sh wo2`: pytest 125 passed, ruff clean, typecheck 0, browser tests 93 passed; the 6 alerts browser tests red on purpose (work order 3). The gate's "no drift" line read FAIL because the generated API files were not committed yet; rerun after the commit: no drift. |
| 2b (`wo-2b.md`) | A first-named starter is not a QB change. Found by me reading work order 2's diff: my work order text allowed "no starter before, one named now", which would send one alert per game when the week's starters are first posted. Red test first (`red-wo2b.log`). | gpt-6-sol, medium, try 1 (Jev `model:alerts:wo-2b`: sol 0.97, medium 0.96) | `79ad694` | pytest 126 passed, ruff clean (`wo2b-pytest.log`). |
| 3 (`wo-3.md`) | Phone side: subscription re-sent on every open and re-made when the server's key changed (A1, A2), tap opens the game even when focus is refused (A3), "Send test alert" with the result in words and the reminder reworded (A4), accessibility (A5) | gpt-6-sol, high, try 1 (Jev `model:alerts:wo-3`: sol 0.99, high 0.98) | `b201bb4` | `gate.sh wo3`, all five stages green: pytest 126 passed, ruff clean, no API drift, typecheck 0, browser tests 99 passed, 2 skipped. |
| 4 (`wo-4.md`) | `scripts/smoke.sh`, the after-deploy check (O1) | gpt-6-luna, medium, try 1 (Jev split 0.61 to 0.39; Sonnet advisor: luna, medium, 0.72, having read the work order and the proof script) | `ad2336c` | `smoke-proof.sh` against the lane test server (`smoke-proof.log`): PASS. Right token exit 0 and five PASS lines; wrong token exit 1 with the later checks still run; `--push` with no device FAIL and exit 1; no token or no address exit 2; the token is never printed. |

Model choice for work order 2: Jev settled effort (high, 1.0) and split on the rung, so a Sonnet advisor answered: gpt-6-sol, no split, confidence 0.7 (it said it read the work order only). Work order 3: Jev `model:alerts:wo-3`, sol 0.99, high 0.98.

### Browser tests for alerts (`apps/web/e2e/alerts.spec.ts`, commit `16ca7cc`)

* Headless Chromium has no push service. The device's subscription is a stand-in kept in `localStorage` (the test replaces `getSubscription`, `subscribe` and `unsubscribe`); a push reaches the service worker through the browser's debug protocol (`ServiceWorker.deliverPushMessage`).
* Checked, not assumed: the default headless shell refuses notifications even when the test grants them (`Notification.permission` reads `denied`). The full browser in its new headless mode (`channel: "chromium"`) grants them and shows the notification. CI installs it already (`npx playwright install --with-deps chromium`). The spec uses that channel.
* Checked: a synthetic tap cannot focus a window (`InvalidAccessError: Not allowed to focus a window`), and today's handler stops there. The worker can still send the window to the link (`navigate` succeeded in a probe). So A3 asks that a refused focus does not stop the navigation; it is a real hardening, not only a test need.
* `scripts/e2e-server.sh` now makes a throwaway push key pair on every run (never stored), so the test server reports push as configured.
* Red proof, `red-wo3.log`: 6 failed, 2 passed. A1 no subscription sent on open; A2 the old key is kept; A3 the alert shows, the tap leaves the page on `/`; A4 "Game day reminder" not found; A5 (dark, light) no "Send test alert" button. The 2 that pass are guards (alerts off: nothing sent, no button).

### Design brief for the Alerts section (Design Gauntlet)

One existing section of Settings, no new screen. Added: one secondary button ("Send test alert") beside "Turn off alerts", shown only while alerts are on; one result line under it (`role="status"`, plain words, replaced by each new result). Reworded: "Kickoff reminder" becomes "Game day reminder" with the help text "One alert on each game day, before that day's first kickoff." Existing tokens and components only (`Button`, `Chip`, `Notice`, `text-subtle`, `text-bad`); no new colour, size or component, so `design.md` gets no durable change. The exact words are in `wo-3.md` section D and pinned by test A4.

### Notes from reading work order 2's diff (for the reviewers)

* `_send`'s last catch-all now logs a warning with the host only, where it logged the full traceback and the endpoint. Good for the secret address; the traceback is lost. For Dwight to rate.
* `POST /api/push/test` has no rate limit of its own (token required, single user). For Dwight to rate.
* The subscribe route accepts any `https://` address; an allowlist of push-service hosts is not built. For Dwight to rate.
* When both starters change in one refresh, the alert names the home side only. Accepted: one alert per game per change.

### Design review of the Alerts section

Screenshots at 393px, dark and light, of each state (alerts on, delivered, refused, off): `step-7-evidence/shots/after-alerts-*.png`, taken with a throwaway test file that is not in the repo. "Before" is step 6's `step-6-evidence/shots/after-settings-393.png`.

**Design critic 1** (fresh Sonnet subagent, read-only; `reviews/design-critic-1.md`): **FAIL**, on Structural findings. My rulings:

* Accepted, red test first (`red-wo3b.log`), work order 3b: a refusal looked the same as a success (now the `text-bad` token); the result sat under the device count (now directly under the buttons); the button stayed busy while the device count was re-read (now free when the result shows).
* Rejected, with the reason in the report: dropping the push service's host and status from a refusal. The roadmap row asks for the push service's status on screen.
* Deferred: for a moment after opening, Settings can show "0 devices are subscribed" beside "Alerts on", until the count is re-read.

### Work order 3b and two flaky tests of mine

Work order 3b (`wo-3b.md`; gpt-6-sol, medium, try 1; Jev sol 0.9, effort by a Sonnet advisor: medium 0.68) made the three accepted design fixes in `alerts.tsx`. Commit `070bf84`.

`gate.sh wo3b`: pytest 126, ruff, no API drift, typecheck green; **browser tests 98 passed, 1 failed: A3**. Not the builder's change. I reproduced it (2 of 6 runs of the alerts file) and found two races in my own test file:

* **A3.** The browser's debug channel drops a delivered push now and then, with no error and no worker event at all (seen with passive logging: registration and "activated, running" reported, push sent, then nothing). Waiting for "activated, running" did not cure it (1 of 10 still red). The test now sends the push again while nothing has been shown; the last check is exact, so a push that arrived twice would fail it. This is a limit of the test channel, not of the app: the worker's handler is never reached in a dropped run.
* **A1.** The test deleted the server's row while the app's re-send was still in flight, so the row came back before the check. It now waits for the server's answer to the re-send.
* Also seen: the stand-in tap (a made-up `notificationclick`) makes the worker log "Can not call waitUntil on a script constructed ExtendableEvent". The handler has already started its steps by then, so the window is still sent to the link. A real tap has no such limit. Said in a comment in the test.

Fix committed as `fa7a842`. Then the whole alerts file ran **20 times in a row: 20 of 20** (`alerts-loop.log`). Because a test went red in this step, the fresh critic is asked for three gate runs.

### A finding from retaking the screenshots (work order 6)

Design critic 1's point 6, which I had deferred as momentary, is not momentary: after the app re-sends its subscription on open, Settings keeps saying "0 devices are subscribed on the server." beside "Alerts on" until something else re-reads the count. A false statement on the screen he checks. Red test A1c (`red-wo6.log`, red 3 of 3), work order 6 (`wo-6.md`; gpt-6-sol, medium; Jev sol 0.98, effort by a Sonnet advisor: medium 0.8).

## 4. CLEANUP

Scope-locked refactor pass on the code this step touched, as work order 5 (`wo-5.md`; gpt-6-sol, high, try 1; Jev `model:alerts:wo-5`: sol 0.94, high 0.97). No behaviour change, no test changed. Commit `a4285a8`.

| Where | Simplification |
|---|---|
| `notify/push.py` `_send` | The block that records a device's result was written four times; each branch now sets one outcome and it is appended once. |
| `predictions/engine.py` `refresh_predictions` | The side whose starter changed and the new starter's name are found in one loop; the second lookup and the type check at the call are gone. |
| `settings/alerts.tsx`, `lib/push.ts` | The words for a test alert reply moved from a nested conditional inside the click handler to one pure function, `testAlertWords`. |

Looked at and left, with the reason: `send_kickoff_reminders` (one loop, reads top to bottom); `alert_prediction_changes` (four plain branches, one per kind of alert); `keepPushSubscription` (linear, early returns); `scripts/smoke.sh` (longer than it could be, but each check is one visible block and the proof pins every line); the test files (long by nature; no helper is duplicated between `alerts.spec.ts` and `pwa.spec.ts` beyond `workerControls`, three lines, not worth a shared module).

`gate.sh wo5` on the cleanup: pytest **126 passed** · ruff clean · no API drift · typecheck 0 · browser tests **99 passed, 1 failed on purpose** (A1c, work order 6), 2 skipped.
