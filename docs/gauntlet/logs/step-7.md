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

### After the cleanup: work order 6, one old test made steady, design critic 2

* **Work order 6** (`wo-6.md`; gpt-6-sol, medium, try 1). `keepPushSubscription` now answers whether it sent the subscription, and `PushKeepAlive` re-reads the meta answer when it did. 9 changed lines in `pwa.tsx`, 10 in `lib/push.ts`. Commit `7ff58fa`. It runs once per open (a `ran` flag), so the re-read cannot start the re-send again; checked in the code. Cleanup look at this diff after the fact: no change needed, it is the smallest form.
* **`gate.sh wo6`**: pytest 126, ruff, no API drift, typecheck green; browser tests 99 passed, **1 failed: E4**, a step 2 test of the kickoff lock, not touched by this step. Cause: it fast-forwarded the page's clock past kickoff and lost a race against the page's own load on a busy machine. **An existing test changed** (`apps/web/e2e/step2.spec.ts`, commit `72df0b5`): it now stops the clock one second before kickoff (`page.clock.pauseAt`) and steps over it. Same thing checked (the pick locks at kickoff), no timing guess. 15 of 15 runs after.
* **Design critic 2** (new fresh Sonnet subagent; `reviews/design-critic-2.md`, screenshots `shots/after-alerts-*.png`): its verdict was FAIL. I accepted none of its findings as a defect of this step and wrote the reason for each in that file, so the final critic and the review check can overrule me. Its Critical ("Alerts off" beside "1 device is subscribed") came from my screenshot script deleting the server's row behind the app's back; the count on screen was the app's saved answer (meta stays fresh for 5 minutes; read in the code, not rerun in a browser). The line itself is from before this step and counts every device, not this one. **Follow-up noted, not built:** say "other device" or hide the count when this device is off. Critic 1's three accepted findings are fixed and pinned by test A4.

## 5. VERIFICATION

Final gate on `e3b049d` (the last commit that changes code, tests or screenshots; later commits are this log and review files only).

| Run | pytest | ruff | API drift | typecheck | Browser tests | Result |
|---|---|---|---|---|---|---|
| `final-a` | 126 passed | clean | none | 0 | 99 passed, **1 failed (E11 light)**, 2 skipped, 18.7 min | **RED: the Mac went to sleep** |
| `final-b` | 126 passed | clean | none | 0 | **100 passed**, 2 skipped, 3.4 min | green |
| `final-c` | 126 passed | clean | none | 0 | **100 passed**, 2 skipped, 6.2 min | green |

`final-a` is not a product failure and not a flaky test: the Mac went into low-power sleep at 21:43:05 and woke at 21:57:49 local time (`pmset -g log`: "Entering Sleep state due to 'Low Power Sleep' ... Charge:1%"), 14.7 minutes, in the middle of E11 light, which then took 14.9 minutes and lost its page. `caffeinate -i` stops idle sleep, not a sleep forced by an empty battery. The machine was on mains power for `final-b` and `final-c`. Logs: `step-7-evidence/final-{a,b,c}-*.log`.

Lane guard on `e3b049d`: `python3 ~/.claude/bin/lane-guard.py check ~/.claude/plans/nfl-pickem-lanes/lanes.md alerts 696c64f --repo .` printed `OK`.

### Review round 1: security PASS, fresh critic FAIL

Commit names in sections 1 to 5 above are from before the branch was moved onto the new main `d88d74e` (step 8a landed under it; the integrator asked for it; no conflict). The same commits now have new names; `git log d88d74e..lane/alerts` lists them in the same order.

* **Security review (Dwight, read-only, at the old `6e777ae`): PASS, no CRITICAL, no HIGH**; 5 MEDIUM, 6 LOW; step 6 follow-up R7 confirmed fixed by P23.
* **Fresh critic (Angela, new, three gate runs `critic5-angela-{a,b,c}`): FAIL.** Runs a and c green (126 / 100 passed), run b red on E4. Blocking: B1 the gate went red; B2 a second reminder on the same game day once the first game is final (she reproduced it); B3 the step 6 follow-up fix in `sync.ts` threw away other games' stored picks when the retry was refused too. She upheld my design rulings except critic 2's point 3 in part (a forgotten device should be told what to do), and found my proof for point 6 wrong (the accessibility test never renders the "Alerts off" chip).
* **Integrator's rulings:** all three blockers stand; E4: find the cause, no wider timeout; also fix the exact 7 point move and record-before-send; a third FAIL goes to him.

| Finding | Red test first | Fix | Proof |
|---|---|---|---|
| B2 second reminder | `test_n2_no_second_reminder_once_the_days_first_game_is_over` | work order 7 (`wo-7.md`; gpt-6-sol, medium; **two tries**) | backend 203 passed (`wo7-pytest.log`) |
| Security S1a: any `https://` address could be stored, so a leaked token could make the server call private addresses | 10 refused and 4 accepted addresses, `test_s1a_*` | work order 7: only the four real push services, no port, no user info | same |
| Security S2: a failed send logged too little | `test_s2_*` | work order 7: the exception's class name, never the address | same |
| Critic S4: an exact 7 point move gave no alert (0.57 − 0.50 is 0.0699… in floating point) | `test_n1_an_exact_seven_point_move_*`, `test_n1_a_six_and_a_half_point_move_*` | work order 7: the difference is rounded to 4 places | same |
| Security S3 / critic S1: an alert was recorded as sent before it was sent | `test_n3_an_alert_that_reached_no_device_is_not_recorded_as_sent` | work order 7, try 2: recorded only when a device got it, as reminders already did | same |
| Design critic 2 point 3, as ruled by the critic | `test_n6_a_device_the_push_service_forgot_is_told_what_to_do` | work order 7: "…Turn alerts off and on again." | same |
| B3 pick queue | P23b (`red-wo8.log`) | work order 8 (`wo-8.md`; gpt-6-sol, high, try 1): a refused write drops only the stale copy of the changed game | P22, P23, P23b green (`red-wo8b.log`) |
| Integrator's condition on B3's last resort | P23c (`red-wo8b.log`) | work order 8b (`wo-8b.md`; gpt-6-luna, medium, try 1): a clear notice on screen | see section 5, round 2 |
| Critic S5: my A3 re-send had no cap | none (a test change) | at most two re-sends, each written on the test report | alerts file 10 times: 90 of 90 (`alerts-loop2.log`, load 15) |

Work order 7 try 1 failed through **my** spec, not the builder: I wrote "whatever their status", and a postponed game became the day's first. An existing test caught it (`test_postponed_game_keeps_its_status_and_gets_no_reminder_or_pick_lock`). Try 2 excludes postponed games.

**The integrator's ruling on B3's last resort (2026-10-13):** when storage refuses every write and still holds an older pick for the same game, the stored queue is removed, because sending a wrong pick is worse than losing the waiting ones; accepted on the condition that he is told on screen (work order 8b, test P23c).

**B1, the red gate (E4).** The cause is the machine, not the test and not the page. Evidence `e4-compare.log`: the committed E4 and a rewrite of mine that fakes only the date, 15 runs each, interleaved, at load average 30 to 40: 6 of 15 and 8 of 15 passed, and 14 of the 16 failures are the plain wait for the board (`step2.spec.ts:53`, 5 s), before any clock code. At load 62 the test server did not start within 180 s. The load came mostly from another project's crash-looping containers, which the integrator stopped with the owner's yes, plus six lanes running tests. My first explanation (the test clock also drives the data library's timers) was **wrong**; I restored the committed test. Rule since then (integrator): one machine-wide lock `res:gate` for any full test run, the load is recorded beside each run, no wider timeouts.

**Mistakes of mine in this round, for the record:** (1) eight CPU-load processes I started for an E4 loop were not stopped by my script and ran about 30 minutes (`e4-loop.log` is from that run; it proves nothing about E4); an alerts loop that ran under them was thrown away. (2) One P23 run tested a web build from before the change, because the test server does not rebuild; rerun after a build. (3) One short P22/P23 run started although my `res:gate` lock had been refused (a chaining error in my command); its result was thrown away.

**Numbers in section 3 without a saved log** (the critic is right): "2 of 6 runs", "1 of 10 still red" and "15 of 15" for E4 were read off my terminal and not kept. `alerts-loop.log` (20 of 20) is kept. The E4 "15 of 15" is also overtaken by `e4-compare.log`.

**Carried, not built in this step, with the reason:**
* A cap on stored devices (security S1b): with the allowlist only real push services can be stored; one user, a handful of devices.
* Two worker processes in the same minute could both send a reminder (critic S2): needs a database constraint or lock; today one worker runs.
* On a server key change the old subscription is removed before the new one exists; if the new one then fails, alerts stay off until he opens Settings (security S4, critic S3). A browser cannot hold both, so the order cannot be swapped. On the real iPhone checklist.
* A dropped alert is retried only if the same change is reported again; the prediction engine reports a change once. A real retry needs a queue (models and a migration: lane stars' files).
* Security lows S5 to S10 and the critic's lows (address in the unsubscribe query string, token in `curl`'s arguments in `smoke.sh`, "Delivered to 2 devices" counts all devices, both QBs changing names one team, the "Alerts off" chip has no accessibility check).

### Security delta on round 1's fixes (Dwight, read-only, at `585e3f5`): NOT passed, one finding

* **S1a still open (MEDIUM).** `https://evil.com\.push.apple.com/x` passed the host check (`urlsplit` reads the host as ending in `.push.apple.com`) while the sending library (`urllib3`) would connect to `evil.com`. My ten refused addresses had no backslash case. Red tests added (three backslash addresses, a tab, a trailing newline; and for every accepted address, the sender's parser must name the same host as the check): `red-wo9.log`, 6 failed. Work order 9 (`wo-9.md`; gpt-6-sol, medium).
* S2 and S3 confirmed fixed. No rate limit on the test route: accepted by him (token, one user). Redirects left on: accepted once the host check holds (LOW).
* His F1 (a missed alert is not logged, and there is no retry): the log line is in work order 9 (red test `test_n3_an_alert_that_reached_no_device_says_so_in_the_log`). **There is no retry**: a prediction or injury alert that reached no device is written to the log and dropped, because the change is reported once.
* Not built, with the reason: his send-time check of stored rows (point 2): the tests' stand-in push service lives on `127.0.0.1` and `push.example.test`, which that check would refuse, and rows from before the check can only have been stored by the token holder; on the real iPhone checklist: turn alerts off and on once after go-live. F2 (a database error while recording would undo earlier records in the same pass) and F3 (if the phone also refuses to remove the stored queue, the old copy stays, and the stronger notice can be replaced by the weaker one): no failing test written; carried.

The gate runs `r2-a`, `r2-b` that had started on `585e3f5` were stopped when this arrived (r2-a had reached: pytest 203 passed, ruff, no drift, typecheck 0; browser tests not finished). They do not count.

### Security delta 2 (Dwight, read-only, at `baef330`): PASS

S1a closed: 271,232 crafted addresses, none accepted that would send to a host outside the four services. No CRITICAL, HIGH or MEDIUM security finding open. The send-time check is not a condition. For the owner's go-live list: remove any stored subscription whose address fails the new check, or turn alerts off and on once. His lows (use `%r` for the key in the "reached 0 devices" log line; redirects left on; empty host labels) are carried, not built.

### Gate round 2 on `baef330` (interim: main moved under it)

| Run | Load before | pytest | ruff | drift | typecheck | browser |
|---|---|---|---|---|---|---|
| `r2-a` | 5.83 | 211 passed | clean | none | 0 | 102 passed, 2 skipped |
| `r2-b` | 6.91 | 211 passed | clean | none | 0 | **5 failed**, 97 passed, 2 skipped |

**r2-b, the cause.** P20 hung on its first click and its cleanup never ran, so P22, P23, P23b and P23c failed after it. The saved trace of P20 shows the server answering `GET /api/weeks/2023/4` at 04:39:57Z with `my_pick: "LV"` for `2023_04_MIA_LV`, while this run's server log has no write of that pick after the last delete (line 2697). So another process wrote to the shared test database during my run. My coordination lease had expired while I waited on the background run (the coord log notes it at 04:40), which released `res:gate` and `res:e2e`; session s35 held `res:gate` right after. I did not see the other writer directly: this is the most likely cause, not a proven one. No timeout was changed. Fix on my side: the gate script now renews the lease every 45 seconds and re-checks both locks after each run (`gate-r3.sh` in the session scratchpad).

Main then moved to `53b1c89` (coach fix). The lane was moved onto it with no conflict; lane-guard against `53b1c89`: OK. Gate round 3 (`r3-a`, `r3-b`) runs on that HEAD.

### Gate round 3 on `41aa9bb` (lane on main `53b1c89`), locks held and re-checked after each run

| Run | Load before | pytest | ruff | drift | typecheck | browser |
|---|---|---|---|---|---|---|
| `r3-a` | 4.85 | 222 passed | clean | none | 0 | 102 passed, 2 skipped |
| `r3-b` | 4.52 | 222 passed | clean | none | 0 | 102 passed, 2 skipped |

Lane-guard against `53b1c89`: OK. CLEANUP for the round 2 code (work orders 7, 8, 8b, 9): diffs read again after the fixes; no change needed (each is the smallest change for its red test; the one shared pattern, send then record, already reads the same in the three callers).
