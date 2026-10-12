# Fresh critic, round 2 (commit a223eaa) — condensed by the coordinator
Gate on a223eaa: ALL PASS D0-D8 (about 4.5 minutes); live containers' IDs, start times and restart counts identical before and after; no gate leftovers. Scripts: `bash -n` and `shellcheck` clean. No data-loss defect found in backup.sh or restore.sh (checked Ctrl-C, full disk, docker not running, db down, unwritable backups/, spaces in paths, newer-Postgres dumps, old-schema dumps, old 8-line-script backups).
VERDICT: FAIL
1. BLOCKING DEPLOY.md §2 step 10 and §3 step 2 told the owner to run section 1 twice; the second `cp .env.example .env` overwrites the database password and the app cannot log in.
2. ADVISORY scheduled backup lines had no BACKUP_COPY_DIR.
3. ADVISORY no runbook steps for a leftover `nflpi_old`.
4. ADVISORY safety copy taken while app and worker still write (restore.sh lines 114 vs 133).
5. ADVISORY an interrupt between the two RENAMEs prints the wrong message.
6. ADVISORY pg_terminate_backend does not wait for connections to close.
7. ADVISORY gate never reaches the swap-rollback and health-timeout paths; the worker restart is not checked; PASS line said 3 bad files, gate refuses 4.
8. ADVISORY DEPLOY.md overclaimed what was tested; IPHONE_PWA.md unlabelled.
9. ADVISORY smaller runbook errors (file name pattern without PID, no editor named, Task Scheduler fields, pre-restore files never pruned).
10. ADVISORY step-5.md claims without evidence on disk.
