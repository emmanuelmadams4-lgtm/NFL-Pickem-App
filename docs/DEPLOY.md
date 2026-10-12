# Running Pick'em Intel at home

One computer at home runs three containers (`db`, `app`, `worker`) from `docker-compose.yml`. Your phone and laptop reach it through Tailscale, so it is never on the public internet. Your always-on computer is the old Windows 11 PC (decision D42). Until it is set up, the Mac runs the app.

The commands below run in a terminal on the server (on Windows: the WSL 2 Ubuntu terminal). The scripts need bash.

## 1. First install (any computer)

```bash
git clone https://github.com/emmanuelmadams4-lgtm/NFL-Pickem-App.git
cd NFL-Pickem-App
cp .env.example .env
```

Edit `.env`:

* `POSTGRES_PASSWORD`: a long random password. Use the same one inside `DATABASE_URL`.
* `APP_ACCESS_TOKEN`: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
* Keys for the AI and alerts are optional and can wait.

```bash
docker compose up -d --build
docker compose exec app python -m nflpi.jobs bootstrap   # loads data, trains, predicts (takes a while)
curl http://127.0.0.1:8000/api/health                    # "status":"ok" and a fresh worker_heartbeat
```

To prove the install works from a clean copy, run `./scripts/deploy-check.sh` from a clean git tree. It uses its own project name and ports (18000 and 15432), so it never touches a running app.

## 2. Set up the Windows 11 PC (UNVERIFIED: written from the vendors' docs, not yet run on your PC)

Goal: the PC starts by itself after a power cut and keeps the app running.

1. **Docker:** install Docker Desktop with the WSL 2 backend. In its settings turn on "Start Docker Desktop when you sign in to Windows" and, under Resources, WSL integration for your Ubuntu distro.
2. **Linux terminal:** install Ubuntu from the Microsoft Store (`wsl --install -d Ubuntu`). Clone the repo inside Ubuntu's own folders (`~/NFL-Pickem-App`), not under `C:\`. It is much faster.
3. **Never sleep:** Settings, System, Power. Set "Screen and sleep" to Never when plugged in.
4. **Power comes back:** in the PC's BIOS set "Restore on AC power loss" (the name varies) to Power On.
5. **Sign in by itself:** Docker Desktop starts after a Windows sign-in, so turn on automatic sign-in for your account (Microsoft's `netplwiz` tool, or the "Sign-in options" page). The PC lives at home, so this is a fair trade.
6. **Windows Update:** set Active hours so it restarts at night, not on a game day.
7. **Tailscale:** install it, sign in with the same account as your phone, and choose "Run unattended" so it runs before anyone signs in.
8. **HTTPS address:** `tailscale serve --bg 8000`. If it says Serve is not enabled, open the link it prints and enable it. Check `tailscale serve status`. Leave **Funnel off** (never run `tailscale funnel`); Funnel puts the app on the public internet.
9. Follow section 1, then add the phone with `docs/IPHONE_PWA.md`.

After a reboot test, all three containers should be back within a few minutes. Check with `docker compose ps` and the health URL.

## 3. Move from the Mac to the PC

The address changes when the computer changes, so the iPhone app is added again once. Passkeys (step 10) come after the move.

1. On the Mac: `./scripts/backup.sh`. Copy the new file in `backups/` to the PC (a USB stick or Tailscale file copy, not email).
2. On the PC: install (section 1) with its own new `POSTGRES_PASSWORD`. Copy only the keys you want to keep from the Mac's `.env` (access token, AI keys, VAPID keys). Keep the VAPID keys, or every phone has to subscribe again.
3. Restore (section 5).

## 4. Backups

Run a backup by hand: `./scripts/backup.sh`. It keeps the newest 14 in `backups/`, checks the file is a good gzip, and exits with an error (leaving no half file) if anything fails.

Copy it off the computer too. Point `BACKUP_COPY_DIR` at another disk or a folder that syncs to a cloud drive:

```bash
BACKUP_COPY_DIR=/mnt/d/pickem-backups ./scripts/backup.sh
```

Run it every night. On Windows use Task Scheduler with the action `wsl.exe -d Ubuntu -- bash -lc "cd ~/NFL-Pickem-App && BACKUP_COPY_DIR=/mnt/d/pickem-backups ./scripts/backup.sh"`. On the Mac use `cron` or `launchd`.

**Keep the secrets safe too.** `.env` is not in git and not in the database dump. Put a copy of `.env` (token, AI keys, VAPID private key) in your password manager. Without the VAPID private key, alerts stop until every phone subscribes again.

## 5. Restore

```bash
./scripts/restore.sh backups/nflpi-YYYYMMDD-HHMMSS.sql.gz --yes
```

This replaces everything in the database with the backup. It stops the app and worker, rebuilds the database, loads the file, and starts them again. Then check `curl http://127.0.0.1:8000/api/health`. Your picks and predictions are back as of the backup time.

## 6. Rotate the access token

Do this if the token leaked or a phone was lost.

1. Make a new token: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`.
2. Put it in `.env` as `APP_ACCESS_TOKEN`.
3. `docker compose up -d --force-recreate app worker`
4. The old token stops working at once. Sign in again on each device with the new one.

## 7. Update the app

```bash
git pull
docker compose up -d --build
```

Database changes run by themselves when the app starts. Take a backup first.
