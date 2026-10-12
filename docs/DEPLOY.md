# Running Pick'em Intel at home

One computer at home runs three containers (`db`, `app`, `worker`) from `docker-compose.yml`. Your phone and laptop reach it through Tailscale, so it is never on the public internet. Your always-on computer is the old Windows 11 PC (decision D42). Until it is set up, the Mac runs the app.

`scripts/deploy-check.sh` ran these on the Mac from a clean copy: the install, bootstrap, the https-proxy checks, backup, restore (including refusing bad files and a restore killed partway), and token rotation. It did not test the Windows PC, real Tailscale HTTPS, an iPhone, a scheduled backup, a reboot, updating an existing install, moving between two computers, or Docker Desktop on Windows passing port 8000 to Tailscale. Anything marked **UNVERIFIED** is written from the vendors' docs and has not been run on your PC yet. Tell me what you see and I will fix the page.

Commands run in a terminal on the server. On Windows, the Docker, git and script commands run in the **Ubuntu (WSL 2) terminal**, and the `tailscale` commands run in **Windows PowerShell**, because Tailscale is a Windows app (UNVERIFIED). The scripts need bash.

## 1. First install (any computer)

```bash
git clone https://github.com/emmanuelmadams4-lgtm/NFL-Pickem-App.git
cd NFL-Pickem-App
cp .env.example .env
```

Edit `.env` (for example `nano .env`):

* `POSTGRES_PASSWORD`: choose it **once** and never change it. The database only reads it the first time it is created; if it later differs from the password inside `DATABASE_URL`, the app cannot log in. Make one with `python3 -c "import secrets; print(secrets.token_urlsafe(24))"`. Put the same value inside `DATABASE_URL`. Use this command and not a password you made up: characters like `@ / : # %` break the address.
* `APP_ACCESS_TOKEN`: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
* Keys for the AI and alerts are optional and can wait.

```bash
docker compose up -d --build
docker compose exec app python -m nflpi.jobs bootstrap   # loads data, trains, predicts (takes a while)
curl http://127.0.0.1:8000/api/health                    # "status":"ok" and a fresh worker_heartbeat
```

To prove an install works from a clean copy, commit your changes and run `./scripts/deploy-check.sh`. It needs `node`, `npm ci` and a Playwright Chromium on the machine you run it from, and a few minutes. It uses its own project name and ports (18000 and 15432), so it never touches a running app. You do not need it to run the app.

## 2. Set up the Windows 11 PC (UNVERIFIED)

Goal: the PC starts by itself after a power cut and keeps the app running. Do these in order.

1. **Ubuntu:** open PowerShell as administrator, run `wsl --install -d Ubuntu`, and restart when it asks. Open Ubuntu once to create your user.
2. **Docker:** install Docker Desktop with the WSL 2 backend. In its settings turn on "Start Docker Desktop when you sign in to Windows" and, under Resources, WSL integration for Ubuntu.
3. **Where the code lives:** clone the repo inside Ubuntu's own folders (`~/NFL-Pickem-App`), not under `C:\`. It is much faster.
4. **Never sleep:** Settings, System, Power. Set "Screen and sleep" to Never when plugged in.
5. **Power comes back:** in the PC's BIOS set "Restore on AC power loss" (the name varies) to Power On.
6. **Sign in by itself:** Docker Desktop starts only after a Windows sign-in, so after a power cut nothing runs until someone signs in. Turn on automatic sign-in for your account (Microsoft's `netplwiz` tool, or the "Sign-in options" page). The PC lives at home, so this is a fair trade.
7. **Windows Update:** set Active hours so it restarts at night, not on a game day.
8. **Tailscale:** install the Windows app, sign in with the same account as your phone, and choose "Run unattended" so it runs before anyone signs in.
9. **HTTPS address (PowerShell):** `tailscale serve --bg 8000`. If it says Serve is not enabled, open the link it prints and enable it. Check `tailscale serve status`. Leave **Funnel off** (never run `tailscale funnel`); Funnel puts the app on the public internet.
10. Do section 1 in Ubuntu **once**. If you are moving from the Mac, do section 3 instead of a separate section 1: it tells you where section 1 fits. Then add the phone with `docs/IPHONE_PWA.md`.

Test it once: restart the PC, sign in, wait a few minutes, then run `docker compose ps` and the health URL. All three containers should be back. The gate does not prove this part; it checks only that the restart setting is in the file.

## 3. Move from the Mac to the PC (UNVERIFIED on the PC side)

The address changes when the computer changes, so the iPhone app is added again once. Passkeys (step 10) come after the move. Do not make picks while you move: the Mac stops taking them at step 1, and the PC does not have them until step 5.

1. **On the Mac, stop the app and take the last backup** (from the repo folder):
   ```bash
   cd ~/Projects/NFL-Pickem-App
   docker compose stop app worker
   ./scripts/backup.sh
   ```
   The newest file in `backups/` has everything (`ls -t backups | head -1`). Copy it to the PC (a USB stick or a Tailscale file copy, not email). Inside Ubuntu a file on the Windows side is under `/mnt/c/Users/<your name>/`; put quotes around any path with a space in it.
2. **On the PC:** do section 1 once, up to and including `docker compose up -d --build`, with its own new `POSTGRES_PASSWORD`. Do not run `cp .env.example .env` a second time: it erases your password, and the database already uses it. Copy only the keys you want to keep from the Mac's `.env` (access token, AI keys, VAPID keys) by the same safe route as the backup (a password manager, section 4), not email. After the restore, `docker compose up -d --force-recreate app worker` makes them use the new `.env`. Skip the bootstrap; the restore brings the data.
3. **Restore** the file (section 5). A fresh clone has no `backups/` folder, so first make it and copy the file in, for example `mkdir -p backups && cp "/mnt/c/Users/<your name>/Downloads/<that file>" backups/`.
4. **On the iPhone:** delete the old Pick'em icon, add the new address to the Home Screen (`docs/IPHONE_PWA.md`), sign in, and turn alerts on again. Each phone subscribes again from the new address, with or without the same VAPID keys. Keep the same keys anyway so nothing else changes.
5. **When the PC looks right,** on the Mac run `docker compose down` so two servers never send alerts, remove its backup job (the `cron` line, if you made one), and run `tailscale serve reset`. Keep the backup file.

## 4. Backups

Run a backup by hand: `./scripts/backup.sh`. It keeps the newest 14 `nflpi-*.sql.gz` files in `backups/`. It saves nothing and exits with an error if the dump is incomplete, the database has no games, or anything fails. A failed run leaves no half file. A run whose only failure is the off-computer copy still keeps its good local backup. Do not run a backup while a restore is running.

Copy it **off the computer** too. A folder on the same PC does not count. Point `BACKUP_COPY_DIR` at a USB drive, another computer, or a folder that syncs to a cloud drive:

```bash
touch /path/to/other-place/.pickem-backups      # once
BACKUP_COPY_DIR=/path/to/other-place ./scripts/backup.sh
```

The folder must already exist and hold a marker file you create once: `touch /path/to/other-place/.pickem-backups` (with the drive plugged in). If the drive is unplugged, the folder or the marker is missing and the backup reports an error instead of quietly writing to the wrong place; the local backup is still saved. The copy is made under a temporary name, compared with the original, and only then renamed. The newest 14 are kept there too. `BACKUP_KEEP` (default 14) must be 2 or more.

Run it every night, and write the output to a file you can read (a failed backup is silent otherwise):

Replace `/path/to/other-place` with your real off-computer folder (with its marker file).

* **Windows (UNVERIFIED):** Task Scheduler, a daily task set to "Run only when user is logged on" (the PC signs in by itself, step 6 above). In the action, Program is `wsl.exe` and Arguments is `-d Ubuntu -- bash -lc "cd ~/NFL-Pickem-App && BACKUP_COPY_DIR=/path/to/other-place ./scripts/backup.sh >> ~/pickem-backup.log 2>&1"`.
* **Mac (UNVERIFIED as a scheduled job):** `cron` does not have `docker` on its PATH. Use a crontab line like `0 3 * * * cd ~/Projects/NFL-Pickem-App && PATH=/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin BACKUP_COPY_DIR=/path/to/other-place ./scripts/backup.sh >> ~/pickem-backup.log 2>&1`.

Once a week, look at the date of the newest file in `backups/` (`ls -t backups | head -3`) and the last lines of the log. `pre-restore-*` files (made by a restore) are never deleted by the script; remove old ones by hand. Hidden `.nflpi.*.part` files in `backups/` are left by a run that was killed (for example WSL shutting down) and are safe to delete.

**Keep the secrets safe too.** `.env` is not in git and not in the database dump. Put a copy of `.env` (token, AI keys, VAPID private key) in your password manager. Without the VAPID private key, alerts stop until every phone subscribes again.

## 5. Restore

```bash
ls -t backups | head                      # pick a file; names look like nflpi-20261012-031500-4242.sql.gz
./scripts/restore.sh backups/<that file> --yes
```

This replaces the data with the backup. It first checks the file is a complete backup with games in it and loads it into a scratch copy while the app keeps running. Then it stops the app and worker, saves the current data as `backups/pre-restore-<time>.sql.gz`, swaps the two, and starts the app again. If anything fails before the swap, the app is started again and nothing changes. If the window is closed or you press Ctrl-C partway, run `docker compose up -d`, then `curl http://127.0.0.1:8000/api/health`. After it prints `restored`, check the same URL. If the database `nflpi` itself is gone, the restore still works.

If the app is not running after a problem, `docker compose up -d` starts it.

**If a restore stops with a message about database names or `nflpi_old` (UNVERIFIED: these steps were written from the script's logic and were not run):** list the databases first:

```bash
docker compose exec db psql -U nflpi -d postgres -c '\l'
```

Look for `nflpi`, `nflpi_old` and `nflpi_restore`, then follow the row that matches:

| What you see | What it means | What to do |
|---|---|---|
| `nflpi` and `nflpi_restore`, no `nflpi_old` | The swap never started; your data is still in `nflpi`. | `docker compose up -d`. Remove the scratch copy: `docker compose exec -T db psql -U nflpi -d postgres -c 'DROP DATABASE nflpi_restore WITH (FORCE)'`. |
| `nflpi_old` and `nflpi_restore`, no `nflpi` | The swap stopped halfway. Your old data is in `nflpi_old`, the restored data is in `nflpi_restore`. | Pick which one you want live: `docker compose exec -T db psql -U nflpi -d postgres -c 'ALTER DATABASE nflpi_old RENAME TO nflpi'` for the old data (or `nflpi_restore` for the restored data), then `docker compose up -d`. |
| `nflpi` and `nflpi_old` | The swap finished. `nflpi` is the restored data; `nflpi_old` is what it replaced. | `docker compose up -d`, check health. When happy, remove the old copy: `docker compose exec -T db psql -U nflpi -d postgres -c 'DROP DATABASE nflpi_old WITH (FORCE)'`. A new restore is refused until `nflpi_old` is gone. |

**Undo a restore:** restore the `pre-restore-*` file the earlier restore made (after removing `nflpi_old` as above). One limit: a restore refuses any file whose database has no games, so if the data you replaced had no games, the safety copy cannot be restored this way; load it by hand with `gunzip -c backups/pre-restore-<time>.sql.gz | docker compose exec -T db psql -U nflpi -d <a new empty database>`.

Do not press Ctrl-C a second time while it is restarting the app. If you did, run `docker compose up -d`.

## 6. Rotate the access token

Do this if the token leaked or a phone was lost.

1. Make a new token: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Put it in `.env` as `APP_ACCESS_TOKEN`.
3. `docker compose up -d --force-recreate app worker`
4. The old token stops working at once. Sign in again on each device with the new one.

## 7. Update the app

Take a backup first (section 4), then:

```bash
git pull
docker compose up -d --build
```

Database changes run by themselves when the app starts.
