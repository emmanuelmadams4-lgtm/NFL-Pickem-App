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
| D7 | Backup, wipe, restore: picks, predictions, games counts match; restore keeps a safety copy (also when the database has no games) and leaves no scratch or old database; restore works when the database is missing; a non-dump, an empty gzip, a broken dump and a truncated dump are refused with the data intact and the app and worker running; a restore sent SIGTERM after the app stopped exits non-zero, starts the app and worker again by itself, explains why, and leaves the live data and `backups/` untouched; two backups started together are both good with no half files; a backup with the database stopped, of a database with no games, or into a copy folder without the `.pickem-backups` marker (or missing) exits non-zero; `BACKUP_COPY_DIR` makes an identical off-host copy | operational |
| D8 | Rotating `APP_ACCESS_TOKEN`: old token 401, new token 200 | operational |

Red evidence: `step-5-evidence/d-red.log` ("app ports ['8000'] do not follow 18000"), then after review `d-red-2.log` (D7: "restore.sh did not keep a safety copy"). Both right reasons.
Gate changes after the freeze: (1) environment: the pinned `playwright-core` wanted a Chromium build that is not installed, so D5 failed on launch; the script falls back to the newest installed headless shell. (2) After the first critic's FAIL the coordinator added the D7 cases above, a `127.0.0.1` bind check, a non-empty logo URL check, an ERR trap, a pre-run clean-up of a leftover project, `--rmi local` on clean-up and `python3 -E`. (3) A count comparison that failed on macOS `wc -l` padding was fixed. One of these does loosen a check, on purpose: D3 now accepts a stale outside weather feed as long as everything else is healthy (the output says so). The rest only tighten.

## 3. IMPLEMENTATION
* WO-1 (Codex `gpt-6-sol`, medium, try 1): compose ports/password, `.env.example`, first `backup.sh` and `restore.sh`. Passed the first, weaker gate on try 1.
* Review rounds then found data-loss paths the gate did not test. The gate was the weak part, not the builder, so no ladder try was spent. Each time the coordinator added the missing cases to the gate first and saw them fail (`d-red.log`, `d-red-2.log`, `d-red-3.log`, `d-red-4.log`), then Codex fixed the scripts:
  * WO-2 (`gpt-6-sol`, xhigh, try 1; `JEV: model:deploy:wo2 -> astra 0.48 (unsure), effort xhigh 0.95`; advisor (Sonnet) -> sol; astra needs the owner's yes and was not asked): restore loads a scratch database while the app runs, saves a safety copy, swaps names, restarts and polls health; backup verifies the dump and never self-deletes.
  * WO-3 (`gpt-6-sol`, xhigh, try 1; `JEV: model:deploy:wo3b -> sol 0.55 (unsure), xhigh 0.93`): stop the app before the safety copy and always keep one; INT/TERM/HUP traps; restore with the database missing; real database names after an interrupted swap; rotation by name; `start_period` on the app healthcheck.
  * WO-4 (`gpt-6-sol`, medium, try 1; `JEV: model:deploy:wo4 -> sol 0.76, medium 0.60`, both unsure and both agreeing with the rung in use): marker file for the copy folder, a finished backup is never deleted by the cleanup trap, a dated message on failure, refuse dumps that create or switch databases, `psql -1 -f -`, cleanup ignores further signals, post-swap failures print their real cause.
  * WO-5 (`gpt-6-sol`, high, try 1; `JEV: model:deploy:wo5 -> sol 0.41, medium 0.31`, unsure, no advisor asked: same rung and size class as WO-3/4): when a restore is killed during the swap, the exit handler reads the database names and restarts the app by itself if they show the swap never started (drops the scratch copy) or finished (keeps `nflpi_old`); otherwise it prints the names and the recovery pointer as before. Found by `d-red-5.log`: the kill landed in the swap, the app was left stopped.
* Coordinator wrote the gate, `docs/DEPLOY.md` and the `docs/IPHONE_PWA.md` order change (docs and tests, not application code).
* Coordinator review of each Codex diff: in scope, `bash -n` and `shellcheck` clean (`lint.log`). restore.sh is long because each failure point has its own recovery; this was accepted over a shorter script that can leave the app down or lose data.

## 4. CLEANUP
Scope-locked read of the touched files with `/ponytail` in mind. No helper scripts or config files were added; the extra branches in restore.sh each map to a data-loss state a reviewer found. No further simplification without removing a recovery path.

## 5. VERIFICATION
Four review rounds, each with a new fresh critic and a new silent-failure reviewer, none seeing the earlier rounds' reasoning (condensed reports: `critic-1-report.md`, `silent-failure-1-report.md`, `critic-2-report.md`, `silent-failure-2-report.md`, `critic-3-report.md`, `silent-failure-3-report.md`).
* Round 1 (`57b2b65`): gate green, critic FAIL. BLOCKING: restore dropped the live database before proving the file was a dump; no safety copy; app left stopped; backup could save an empty database and rotate real ones out; the Mac-to-PC steps lost picks.
* Round 2 (`a223eaa`): gate green, critic FAIL. BLOCKING: the runbook had the owner run section 1 twice, overwriting the database password; the safety copy was taken while the app still wrote and was skipped when games was empty; a restore killed by SIGTERM left the app stopped silently.
* Round 3 (`3bb0ada`): gate green, critic FAIL on one runbook blocker (`backups/` does not exist on a fresh PC clone, so the move's restore is refused); the silent-failure reviewer found the kill-a-restore check could pass without a kill happening.
* Fixes: runbook (section 1 once, `backups/` folder, recovery table for each database state, off-computer marker file), gate (the kill must happen and be seen, live data differs from the file, the exit handler must restart the app by itself, `backups/` untouched, marker file, `unset BACKUP_COPY_DIR`, docker errors are not read as "not running"), WO-4.
* Round 4 (`1022a27`, after WO-5): gate ALL PASS in the critic's own run, critic VERDICT PASS with no blocking findings (`critic-4-report.md`). Its advisories are in Known limits. The silent-failure reviewer also returned no blocking findings (`silent-failure-4-report.md`); its advisories (exit-handler race with an orphaned psql, SIGHUP stopping the handler, a half swap after SIGKILL, no lock between two restores, no flush before the off-host `cmp`, rotation by name with no long-term tier) are in Known limits below or in the report. The runbook table was extended for the missing database states.

Gate evidence: `d-green.log` (final), `killed-restore-run.log` (the real output of a restore killed with SIGTERM: the handler restarts app and worker and prints "live data was not replaced; restart requested"). Counts after restore equal before: `1,93,6771`. D3 tolerates only the outside weather feed being stale (it printed `health ok` in the final runs); an earlier run (log not kept) showed `weather` stale and failed D3 before this tolerance existed; the first strict kill failure's output was also not kept, only the second (`d-red-5.log`). The strict kill check then failed twice. The first time looked like slowness; the second run printed the real cause (`d-red-5.log`): the gate's slow polling let the kill land inside the database swap. The gate now watches the app container directly and kills about 85 ms after its stop, and is written to accept either survivable outcome (swap not started, swap finished) while rejecting a half state (but see Known limits: its message check does not recognise the swap-finished text); WO-5 made the handler restart the app in both. Three consecutive full runs have not been needed; the final run and the critic's own run are the evidence.

## 6. LANDING
Jev review verdict: `JEV: review:step5 -> passed 0.34` (grey zone). Advisor (Sonnet): `VERDICT: PASS`, with two log corrections (the WO-5 swap branches have no green run on disk, stated in Known limits; D3's weather tolerance, stated in § 2). The decision log is `step-5-evidence/jev-decisions.jsonl`.
Push, PR, CI and merge are recorded below when done.

## Known limits (not proven or not fixed here)
* Gate: the killed-restore message check (`restart requested|live data`) does not match the two swap-finished messages, so if a kill ever lands after the swap on a slow machine the gate fails on a correct run (it fails safe; it cannot give a false PASS). The WO-5 swap branches have no green run on disk; `killed-restore-run.log` shows only the before-swap path.
* The two database renames in the swap are separate statements (not one transaction), so an interrupt can leave one done. The handler reads the names after 3 seconds and restarts only in clearly safe states; an orphaned `psql` still running after that wait can leave "only `nflpi_old`" (the runbook table has that row now). The handler stops at its first failed command (for example an `echo` to a closed terminal), so the app may stay stopped; `docker compose up -d` recovers.
* Also not fixed, from the round-4 silent-failure report: a closed terminal window can stop the exit handler at its first failed `echo` (recovery: `docker compose up -d`); a SIGKILL or Docker quit between the two renames leaves a half swap (the runbook table covers it); no lock between two restores or a restore and a backup; the off-host copy is compared from the page cache, not flushed; rotation keeps by file name and has no weekly tier, so a database that lost picks but still has games would back up and push older good copies out after 14 nights (keep an occasional older copy off the computer).
* The Dockerfile (outside this step) does not handle SIGTERM in the app and worker, so every `docker compose stop` waits 10 s and force-kills them.
* The Mac-to-PC move needs the same code version on both computers; the runbook says so (step 0 of section 3).
* The Windows 11 PC steps (`docs/DEPLOY.md` §§ 2, 3, 4), the recovery table for interrupted swaps and the Mac-to-PC move are written, not run. Owner check PENDING.
* Real TLS: tested with forwarded headers on localhost (a secure context); the real https address comes from Tailscale Serve on the owner's machine. Owner iPhone install check PENDING.
* "Restarts by itself" is a config check plus the killed-restore test; no reboot is simulated, and Docker does not restart an unhealthy (not exited) container.
* The gate kills a restore only after the app stops (SIGTERM to the process). It does not test Ctrl-C or a closed terminal to the whole process group, a kill during the swap, or SIGKILL.
* No lock stops two restores, or a backup during a restore; `docs/DEPLOY.md` says not to run them together.
* Backups guard against an empty games table only. A wiped picks table would still back up; keep older off-computer copies for that case. A clock that runs behind makes name-ordered rotation keep the wrong files (the new file is always kept).
* The gate builds with a warm Docker layer cache, depends on outside logo hosts (D6), and compares row counts of three tables in D7.
* `POSTGRES_PASSWORD=change-me` in `.env.example` is accepted by the required-value check; the runbook tells the owner to generate one.
