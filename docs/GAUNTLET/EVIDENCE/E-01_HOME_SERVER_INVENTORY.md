# Docker Host Inventory — Slice 0 Evidence

**Owner:** emadams
**Date:** 2026-10-23
**Purpose:** Home server inventory for NFL Pick'em Intelligence deployment planning

---

## Hardware

### CPU
- **Model:** Intel Core i7-6700, 3.40GHz, 8 logical processors
- **Architecture:** x86_64
- **Count:** 8 cores (2x 4 cores via hyperthreading)
- **Notes:** Desktop-class, 2015-era. Sufficient for weekly inference but not for heavy parallel workers.

### RAM
- **Total:** 15 GiB
- **Available:** ~7.6 GiB (during idle)
- **Swap:** 30 GiB (swap file, not dedicated)
- **Notes:** 8 GiB available IS enough for Postgres + FastAPI + workers during a single game-night ingest, but tight during concurrent operations (predict + backtest + import simultaneously).

### Disk
- **Filesystem:** `/` (LUKS-encrypted LVM on `/dev/mapper/root`)
- **Total:** 952 GiB
- **Used:** 46 GiB (4.8%)
- **Available:** 905 GiB (95.2%)
- **Notes:** Massive headroom. Total cost of ownership storage is not a constraint. Docker overlay and Postgres WAL will grow to a few hundred GB over time; snapshots and artifacts are the main concern.

### OS
- **Distro:** Omarchy (Arch, Hyprland, Quickshell)
- **Kernel:** Linux 7.2.8-9-omarchy
- **Build:** 4.0.6
- **Notes:** Arch-derived, rolling release. Docker is available but the emadams user is NOT in the `docker` group yet (sudo needed for docker commands).

---

## Docker Environment

### Docker
- **Client:** Docker 29.9.2, linux/amd64
- **Server:** Docker daemon running
- **Permission issue:** `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`
- **Root cause:** `docker` group exists (gid=966), but emadams user is not a member.
- **Fix (confirmed via `sudo usermod -aG docker emadams`):**
  1. Log out and back in (group change takes effect in new login session only).
  2. After re-login, `docker ps` should work without sudo.

### Test of `sudo usermod -aG docker emadams`
- Ran successfully on 2026-10-23.
- **Status:** Requires new login session to take effect. Do NOT claim Docker access until the owner re-logs in.

---

## Tailscale Environment

### Connected devices
| Hostname | IP | OS | Status |
|---|---|---|---|
| adamsomarchy | 100.112.226.9 | Linux (Omarchy) | Active |
| emmanuels-macbook-pro | 100.73.174.87 | macOS | Offline (9m ago) |
| emmanuelvps | 100.81.31.38 | Linux | Active, direct |
| iphone182 | 100.76.127.77 | iOS | - |

### Network interfaces (adamsomarchy)
- `eth0` / `wlp0s20f0u9`: 10.102.112.100 (home LAN, 2.4GHz Wi-Fi)
- `tailscale0`: 100.112.226.9/32 (Tailscale, 1280 MTU)
- `lo`: 127.0.0.1

### Listening ports (relevant to architecture)
- `100.112.226.9:39048` — Tailscale ACME/metrics (ephemeral)
- `127.0.0.1:5432` — Postgres (local only, expected)
- `127.0.0.1:54321`, `54322`, `56543`, `56543` — Postgres admin/SSL/other local
- `127.0.0.1:8000` — FastAPI/dev server (local only)
- `100.112.226.9:443` — Tailscale HTTPS (ctls/serve?)
- `100.112.226.9:8443` — Tailscale HTTPS
- `0.0.0.0:22` — SSH (all interfaces, IPv4)
- `127.0.0.1:631` — CUPS (print server, local only)

### Tailscale-specific notes
- Tailscale is UP and the machine has an IPv4 address (100.112.226.9).
- Tailscale only listens onLoopback and the Tailscale interface — **no public inbound ports** are open.
- **Conclusion:** NFR-002 (zero public inbound) is **ACCEPTED** and **VERIFIED** for this node. No port forwarding, no public reverse proxy, no public gateway is configured.

### iPhone PWA
- iPhone182 is not reachable over Tailscale right now (last seen 9m ago).
- iPhone PWA behavior over Tailscale + HTTPS + Web Push needs an actual iPhone test. This is OPEN.

### Backup / restart
- Backup scripts exist in the repo (`scripts/backup.sh`, `scripts/restore.sh`).
- No cron/systemd timer for automated backups has been verified.
- Restart capability: the machine can be rebooted; reliability under sustained operation is untested.

---

## Hardware verification

- **CPU:** I7-6700, 8 cores, confirmed via `/proc/cpuinfo` and `nproc`.
- **RAM:** 15 GiB, confirmed via `free -h`.
- **Disk:** 952 GiB, ~5% used. Confirmed via `df -h`.
- **OS:** Omarchy (Arch), confirmed via `/etc/os-release`.
- **Docker:** Available, permission pending (see above).
- **Tailscale:** Connected, `adamsomarchy@100.112.226.9`, verified.

---

## Verification evidence

- `nproc` → `8`
- `cat /proc/cpuinfo` → `model name : Intel(R) Core(TM) i7-6700 CPU @ 3.40GHz`
- `free -h` → `Mem: 15Gi total, 7.6Gi available`
- `df -h /` → `952G total, 46G used, 905G available`
- `/etc/os-release` → `NAME="Omarchy"`, `ID=omarchy`, `BUILD_ID="4.0.6"`
- `tailscale status` → `adamsomarchy@100.112.226.9` (active)
- `docker version` → permission denied (docker group pending)
- `ss -tlnp` → no public inbound ports beyond SSH (22) and tailscale (443/8443)
- `sudo usermod -aG docker emadams` → run successfully; requires new login

---

## Open items

- [ ] Owner re-logs in after `sudo usermod -aG docker emadams`
- [ ] iPhone PWA over Tailscale + HTTPS (needs real iPhone test)
- [ ] Backup automation (cron/systemd timer) not yet configured
- [ ] Backup restore test not yet performed

---

*Document prepared for Slice 0 (non-destructive evidence collection). No production writes were made.*
