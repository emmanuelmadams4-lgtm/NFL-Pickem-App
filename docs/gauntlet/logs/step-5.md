# Step 5 of 14: Deploy and operate

Session: owner's Mac, 2026-10-12, lane `deploy` (own worktree, branch `lane/deploy`, base `0bb10c2`), run beside step 4.
Coordinator: Claude. Builder: Codex `gpt-6-sol` at medium (Jev: sol 0.92, medium 0.86; `JEV: model:deploy:wo1 -> sol, medium`).
Independence of the two lanes: `JEV: independent:sheet+deploy -> interface_coupling 0.05, shared_state 0.05`, lane-guard overlap `OK`.

## 1. PLANNING
* **In the owner's words:** make the app run from a clean copy, keep running on his old Windows PC, back up and restore, and change the token. It replaces the loose `docker compose` notes and the 8-line backup script. It is not: passkeys (step 10), the iPhone offline work (step 6), or alerts (step 7).
* **Tier:** T2. Reversibility: two-way (files only). Decisions relied on: D42 (always-on home = the PC, Tailscale, no cloud).
* **Skills:** `/jevgrep`, `/graft`: N/A (file homes known: compose, Dockerfile, scripts). `tdd`: the gate script is the red test (written by the coordinator, not the builder). `ponytail`: in the work order. Design Gauntlet: N/A (no UI). `harness-engineering`: N/A.
* **Pre-flight:** Problem: the app lives on a laptop that sleeps; one bad disk loses all picks. Why now: week 6 and the PC decision (D42). Scope: compose ports/restart, backup, restore, runbook, install order; cut: PowerShell scripts (the PC uses WSL 2), a second proxy. Success metric: restore returns the same counts; a clean clone reaches health ok. Reversibility: two-way.
* **Assumptions:** the Mac can stand in for the PC for everything except Windows power/boot settings (validated: Docker 28.3.2 here); Windows steps are written from vendor docs and marked UNVERIFIED (`docs/DEPLOY.md` § 2).

## 2. SPECIFICATION
Gate: `scripts/deploy-check.sh` (+ `scripts/deploy-check-sw.mjs`), committed red in `21403ad` before any fix. It clones committed HEAD, uses project `nflpi-deploycheck`, ports 18000/15432 and its own volume, and never touches the live stack.

| # | Criterion | Layer |
|---|---|---|
| D1 | Compose ports follow `APP_PORT`/`DB_PORT`; every service `restart: unless-stopped`; `.env` git-ignored; backup/restore scripts and runbook exist; iPhone doc says install first, then sign in | operational |
| D2 | Clean clone `up -d --build`: database ok, worker heartbeat fresh | operational |
| D3 | `bootstrap` then health `ok` | operational |
| D4 | Page 200, manifest, `sw.js` JavaScript and not cacheable | user-facing |
| D5 | No `http://` redirect behind an https proxy; service worker registers inside the manifest scope | user-facing |
| D6 | 32 of 32 team logos return 200 from the server's network | user-facing |
| D7 | Backup, wipe, restore: picks, predictions, games counts match; restore keeps a safety copy (also when the database has no games); restore works when the database is missing; a restore killed with SIGTERM after the app stopped can be recovered with `docker compose up -d` with the data unchanged; no scratch or old database is left after a restore; a missing `BACKUP_COPY_DIR` is an error and is not created; a non-dump, an empty gzip, a broken dump and a truncated dump are refused with the data intact and the app running; two backups started together are both good with no half files; a backup with the database stopped, or of a database with no games, exits non-zero and changes nothing in `backups/`; restore recovers from an emptied database; `BACKUP_COPY_DIR` makes an identical off-host copy | operational |
| D8 | Rotating `APP_ACCESS_TOKEN`: old token 401, new token 200 | operational |

Red evidence: `step-5-evidence/d-red.log` ("app ports ['8000'] do not follow 18000"), then after review `d-red-2.log` (D7: "restore.sh did not keep a safety copy"). Both right reasons.
Gate changes after the freeze: (1) environment: the pinned `playwright-core` wanted a Chromium build that is not installed, so D5 failed on launch; the script falls back to the newest installed headless shell. (2) After the first critic's FAIL the coordinator added the D7 cases above, a `127.0.0.1` bind check, a non-empty logo URL check, an ERR trap, a pre-run clean-up of a leftover project, `--rmi local` on clean-up and `python3 -E`. (3) A count comparison that failed on macOS `wc -l` padding was fixed. None of these loosen a check.

## 3. IMPLEMENTATION
* WO-1 (Codex `gpt-6-sol`, medium, try 1 of 2): `docker-compose.yml`, `.env.example`, `scripts/backup.sh`, `scripts/restore.sh`. Passed the first gate on try 1.
* The first critic and the silent-failure reviewer then found data-loss paths the gate did not test (below). The gate was the weak part, not the builder, so no ladder try was spent.
* WO-2 (Codex `gpt-6-sol`, xhigh, try 1 of 2; `JEV: model:deploy:wo2 -> astra 0.48 (unsure), effort xhigh 0.95`; advisor (Sonnet) -> sol; astra needs the owner's yes and was not asked): `scripts/backup.sh`, `scripts/restore.sh`, app healthcheck in `docker-compose.yml`. Restore now validates the file, loads a scratch database while the app runs, saves `pre-restore-*` safety copy, swaps database names, restarts the app and polls health, and restarts the app if anything fails before the swap. Backup verifies the dump trailer and a games row, never deletes the file it just wrote, uses unique names, and copies off-host through a temp name plus `cmp`.
* Coordinator also wrote `docs/DEPLOY.md` and the `docs/IPHONE_PWA.md` order change (docs, not code), then revised DEPLOY.md after review.
* Coordinator review of each Codex diff: in scope, `bash -n` and `shellcheck` clean (`step-5-evidence/lint.log`). restore.sh is long because each failure point has its own recovery; this was accepted over a shorter script that can leave the app down.

## 4. CLEANUP
Scope-locked read of the touched files with `/ponytail` in mind. No further change: no helper scripts or config files were added, and the extra branches in restore.sh each map to a data-loss state a reviewer found.

## 5. VERIFICATION
Round 1 (commit `57b2b65`): the gate was ALL PASS (`critic-1-gate-run.log`) but the fresh critic returned FAIL, and the silent-failure reviewer found the same two restore problems. Blocking: (1) restore dropped the live database before proving the file was a real backup, took no safety copy, and left the app stopped on failure; (2) the Mac-to-PC steps lost picks made after the backup and contradicted themselves about the VAPID keys. Also blocking from the second reviewer: backup could save an empty database and rotate real backups out. All fixed above; the Windows/WSL contradictions, the off-host copy and the other advisories were fixed in the same pass (the ones not fixed are listed under "Known limits").
Round 2 (commit `a223eaa`): gate ALL PASS but the fresh critic returned FAIL again (`critic-2-report.md`): BLOCKING, the runbook had the owner run section 1 twice, which overwrites the database password after the database exists. The silent-failure reviewer (`silent-failure-2-report.md`) found two more data-safety holes: the safety copy was taken while the app still wrote and was skipped when the games table was empty (BLOCKING), and a restore killed by SIGTERM/SIGHUP left the app stopped and printed nothing, plus smaller items. Fixed: runbook (section 1 once; password never changes; `nflpi_old` recovery steps; scheduled backups with `BACKUP_COPY_DIR`; labels), gate cases (red: `d-red-3.log`), and WO-3 (Codex `gpt-6-sol` xhigh, try 1; `JEV: model:deploy:wo3b -> sol 0.55 (unsure; sol is also the rung that wrote the scripts), xhigh 0.93`): stop writers before the safety copy, always keep one, INT/TERM/HUP traps, missing-database restore, real database names after an interrupted swap, backup rotation by name, copy directory must exist, `start_period` on the app healthcheck.
Round 3 (commit `84a28ed` and docs after it): gate ALL PASS D0-D8 with the new cases, `d-green.log`.
Previous round 2 line follows for history (commit `c0d9e56`): gate ALL PASS, counts after restore equal before (`1,93,6771`), `step-5-evidence/d-green.log`. lane-guard overlap and check: `lane-guard.log` (OK, OK). Live stack: `live-stack.log` (the three `nfl-pickem-app-*` containers up; the gate's own images and volume are removed). Fresh critic round 2 and Jev verdict: recorded below when run.

## 6. LANDING
Recorded below when done.

## Known limits (not proven or not fixed here)
* The Windows 11 PC steps (`docs/DEPLOY.md` §§ 2, 3, 4) are written, not run. Owner check PENDING.
* Real TLS: tested with forwarded headers on localhost (a secure context); the real https address comes from Tailscale Serve on the owner's machine. Owner iPhone install check PENDING.
* "Restarts by itself" is a config check only; no process is killed and no reboot is simulated.
* The gate builds with a warm Docker layer cache, depends on outside logo hosts (D6), and compares row counts of three tables in D7.
* A backup started while a restore is running is not blocked; DEPLOY.md says not to.
* The app healthcheck now needs the database, but Docker does not restart an unhealthy container by itself.
