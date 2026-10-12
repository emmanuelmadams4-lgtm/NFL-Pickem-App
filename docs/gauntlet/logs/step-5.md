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
| D7 | Backup, wipe, restore: picks, predictions, games counts match; a backup with the database stopped exits non-zero and leaves no file; `BACKUP_COPY_DIR` makes an off-host copy | operational |
| D8 | Rotating `APP_ACCESS_TOKEN`: old token 401, new token 200 | operational |

Red evidence: `step-5-evidence/d-red.log` ("app ports ['8000'] do not follow 18000"), right reason.
Gate amendment after the freeze (environment, not the check): the pinned `playwright-core` wanted a Chromium build that is not installed, so D5 failed on launch. The script now falls back to the newest installed headless shell. Nothing it asserts changed.

## 3. IMPLEMENTATION
* WO-1 (Codex `gpt-6-sol`, medium, try 1 of 2): `docker-compose.yml`, `.env.example`, `scripts/backup.sh`, `scripts/restore.sh`. First try passed; no climb, no correction.
* Coordinator wrote `docs/DEPLOY.md` and the `docs/IPHONE_PWA.md` order change (docs, not code).
* Coordinator review of the Codex diff: in scope; `bash -n` and `shellcheck` clean; backup writes a `.part`, checks gzip and removes it on any failure; restore refuses without `--yes`.
* Commits: `21403ad` red gate, red evidence, `d03051f` deploy files, `3d110b1` gate environment fix.

## 4. CLEANUP
Scope-locked read of the touched files with `/ponytail` in mind. No change needed: backup.sh is 39 lines with no helpers, restore.sh 21, compose diff is 3 lines. `/refactor` found nothing to remove; the one extra loop in backup.sh (waits a second if the file name exists) is kept because two backups in one second would overwrite each other.

## 5. VERIFICATION
Gate on committed HEAD `3d110b1`: ALL PASS D0-D8 (`step-5-evidence/d-green.log`). Counts after restore equal before: `1,93,6771` (picks, predictions, games). Live stack checked untouched afterwards (`nfl-pickem-app-*` up, ports 8000/5432 unchanged). lane-guard check: see § 6.
Fresh critic and Jev verdict: recorded below when run.

## 6. LANDING
Recorded below when done.

## Not proven here
* The Windows 11 PC steps (`docs/DEPLOY.md` § 2) are written, not run. Owner check PENDING.
* Real TLS: tested with forwarded headers and localhost (a secure context); the real https address comes from Tailscale Serve on the owner's machine. Owner iPhone install check PENDING.
