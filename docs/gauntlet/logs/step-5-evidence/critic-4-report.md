# Fresh critic, round 4 (commit 1022a27) — condensed by the coordinator
Gate on 1022a27: ALL PASS D0-D8 (about 4 m 46 s), counts 1,93,6771; live containers' IDs and start times identical before and after; no gate leftovers. `bash -n`/shellcheck clean. No path found where backup.sh or restore.sh can lose the only copy of data; every DROP targets nflpi_restore or nflpi_old-after-health-with-a-verified-safety-copy.
VERDICT: PASS (no BLOCKING findings). ADVISORY:
1. The killed-restore check's message regex (`restart requested|live data`) does not match the two "swap finished" messages ("the restored data is live..."), so if a kill ever lands after the swap the gate fails on a correct run (it fails safe, never a false PASS); the step log wrongly said the gate accepts that outcome.
2. No green run has exercised the WO-5 swap branches; killed-restore-run.log shows only the pre-swap path.
3. The two RENAMEs run in autocommit; a leftover psql inside the container can still rename after the handler's 3 s wait, giving an "nflpi_old only" state the recovery table did not list.
4. The handler stops at its first failed command (bash 3.2 `set -e` in an EXIT trap), for example an echo to a closed terminal, so the app may stay stopped; DEPLOY.md says to run `docker compose up -d`.
5. Missing-database restore interrupted mid-rename lands in "uncertain" with no matching table row.
6. The move needs the same code version on both computers (the Mac runs the step 4 branch with migration 0002).
7-10. Gate weaknesses (scratch left by a killed restore is dropped before it is checked; safety copy never restored; keyword greps), step-log claims without evidence, runbook details (Task Scheduler quoting, USB mount in WSL, "PC does not have them until step 5"), Dockerfile PID 1 does not handle SIGTERM so each stop waits 10 s.
