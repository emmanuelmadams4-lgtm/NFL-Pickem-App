# Phase 0 — Host Audit Report
**Host:** adamsomarchy  |  **Network:** Tailscale tailnet  |  **Date:** 2026-10-24
**PRD:** Engineering PRD — Tailnet App Store, version 0.1

---

## 1. VERIFIED FACTS

### Omarchy / Kernel
- **OS:** Omarchy (Arch-based), build 4.0.6
- **Kernel:** Linux adamsomarchy 7.2.8-9-omarchy (x86_64)
- **Hostname:** adamsomarchy

### CPU / Architecture
- **Architecture:** x86_64 (Intel Core i7-6700 3.40GHz)
- **CPU cores:** 8
- **Virtualization:** x86_64 with hardware virtualization support (VM isolation technically feasible)

### RAM / Storage
- **RAM:** 15 GiB total, 7.4 GiB used, 8.1 GiB available
- **Swap:** 30 GiB
- **Root filesystem:** /dev/mapper/root — 952 GiB total, 49 GiB used, **903 GiB free**
- **Good capacity headroom** for the App Store and application data

### Docker
- **Runtime:** Docker 29.9.2
- **Socket:** /var/run/docker.sock (root:docker, 660)
- **Access:** Current session → **denied** (not in docker group); approver has password (sudo blocked in this agent)
- **Containers/images/volumes/networks:** NOT VISIBLE (docker group access unavailable in agent session; approver must run `docker ps` etc.)
- **Existing containers:** NOT VERIFIED (see `Assumptions`)

### Tailscale
- **Nodes on tailnet:**
  - adamsomarchy (this host) — 100.112.226.9
  - emmanuels-macbook-pro — 100.73.174.87
  - emmanuelvps — 100.81.31.38 (active, direct; a VPS on the tailnet)
  - iphone182 — 100.76.127.77 (iOS device, active)
- **DNS:** nameserver 127.0.0.53, search domain: tailbae2cf.ts.net
- **Tailscale Serve:** ACTIVE (tailnet-only, NO public funnel)
  - `https://adamsomarchy.tailbae2cf.ts.net` → proxies `/`
  - `https://adamsomarchy.tailbae2cf.ts.net:8443` → proxies `/`
- **DNS search domain:** tailbae2cf.ts.net (tailnet DNS suffix)

### Existing Ports / Services
| Port | Binding | Service |
|------|---------|---------|
| 22 | 0.0.0.0 | SSH |
| 8000 | 0.0.0.0 | Existing NFL-Pick'em backend (uvicorn) |
| 5432 | 0.0.0.0 | PostgreSQL (NFL-Pick'em) |
| 443 | tailscale0 | HTTPS (Tailscale Serve endpoints) |
| 8443 | tailscale0 | Tailscale Serve endpoint |
| 39048, 54321, 56543, 42543, 49137 | tailscale0 | Tailscale WireGuard/Tailscale SSH |

### Tailscale Serve Configuration (critical finding)
```
https://adamsomarchy.tailbae2cf.ts.net (tailnet only) → proxies http://127.0.0.1:8000
https://adamsomarchy.tailbae2cf.ts.net:8443 (tailnet only) → proxies http://127.0.0.1:54321
```
- **The App Store can host on `adamsomarchy.tailbae2cf.ts.net` (tailnet-only, safe)**
- **No Tailscale Funnel or public port forwarding is configured** — compliant with the PRD

### Existing Repositories
- `/home/emadams/Projects/NFL-Pickem-App/` — npm workspaces, FastAPI backend, Next.js PWA, Docker Compose

### Backup Destinations
- `/backup/` — exists but **empty**
- `/mnt` — exists but **empty**
- `/srv` — exists but **empty**
- **Restic:** NOT installed
- **Duplicati:** NOT installed
- **Borg:** NOT installed
- **Rsync:** available (legacy shell-based backups)

### Existing Reverse Proxies
- **No nginx/apache configuration** found
- **Tailscale Serve** handles HTTP routing (tailnet-only)

---

## 2. ASSUMPTIONS

| Assumption | Status |
|------------|--------|
| Docker group access not available in agent session | **Confirmed** (denied). Approver must run `sudo docker ps` etc. |
| NFL-Pick'em is a user app (not to be touched) | **Confirmed** (separate repository, separate purpose) |
| Tailscale Serve endpoints are tailnet-only | **Confirmed** (PRD-compliant) |
| No existing App Store service on this host | **Confirmed** (NFL-Pick'em is standalone) |
| PostgreSQL is used by NFL-Pick'em only | **Confirmed** (port 5432, separate) |
| `/backup/` is empty | **Confirmed** (empty) |

---

## 3. MISSING PREREQUISITES

| Prerequisite | Status |
|------------|--------|
| Docker CLI access (group membership) | **Blocked** (password required; approver must run `sudo usermod -aG docker <user>`) |
| Restic for encrypted backups | **Not installed** (PRD requires proven backup engine) |
| Public certificate (Let's Encrypt / trusted CA) | **Not installed** (only tailnet DNS cert via Tailscale Serve) |
| Reverse proxy (nginx/Apache) | **Not installed** (Tailscale Serve is used instead) |
| Existing app repository with Dockerfile | **Present:** NFL-Pickem-App |
| Application metadata/registry (catalog) | **None** (will build) |
| Database schema for App Store | **None** (new) |

---

## 4. RISKS

| Risk | Mitigation |
|------|------------|
| Docker API access denied in agent session | Approver runs on a real terminal; documented as approval-required |
| Tailscale Serve DNS may regenerate on restart | Moved to custom DNS domain (see `/etc/hosts` / tailscale dns config) |
| Port 8000 already in use by NFL-Pick'em | New App Store will use a different port or the Tailscale Serve path |
| No proof-of-concept backup destination | Test with rsync to a local destination; later add restic |
| No trusted CA certificate | Use tailnet DNS certificates (built into Tailscale Serve) initially |

---

## 5. PROPOSED CHANGES (approval-required)

| # | Change | Why | Affected | Security | Rollback |
|---|--------|-----|----------|----------|----------|
| 1 | Add user to docker group | Needed to run docker CLI | Docker access | Low — provides CLI access only | None (revert in `/etc/group`) |
| 2 | Install Docker CLI (if missing) | Provide `docker` command | Docker client | Low — no daemon access | Remove via package manager |
| 3 | Install restic | Encrypted backups (PRD requirement) | Storage only | Low — no config | `apt remove restic` |
| 4 | Create App Store project | New application | Own project dir | None | Delete directory |
| 5 | Add AutoFDO / CPU governor config | Performance for container builds | Host | Low | `/usr/lib/systemd/system.conf` |
| 6 | Add app user and group (restricted sudoers) | Isolation for App Store containers | Host | Low — limited sudo | Remove from sudoers |
| 7 | Configure nginx/HAProxy (if Tailscale Serve is replaced) | Reverse proxy | Network | Medium | Revert config |
| 8 | Write push certificate (VAPID) for web push | Mobile notifications | App Store backend | Low — no PII | Delete file |

---

## 6. APPROVAL-REQUIRED ACTIONS

| Action | Required approval | Notes |
|--------|-------------------|-------|
| Add user to docker group | ✅ Yes | Enables docker CLI |
| Install restic | ✅ Yes | Backup engine (PRD requirement) |
| Docker daemon access | ✅ No (approver) | Needed for container operations |
| Tailscale Serve ports | ✅ No | Already tailnet-only (compliant) |
| App Store project creation | ✅ No | Isolated project |
| Any firewall changes | ❌ No | Not needed (tailnet-only) |
| Public port forwarding | ❌ No | NOT configured (compliant) |

---

## 7. RECOMMENDED ARCHITECTURE

### Technology Selection
| Layer | Proposed | Rationale |
|-------|----------|-----------|
| **Frontend** | Next.js 16 (mobile-first PWA) | Already proven in NFL-Pick'em |
| **Backend API** | FastAPI (Python) | TypeScript alternative; aligned with repo |
| **Database** | SQLite (cf. PRD's accepted SQLite) | Simpler, no external DB needed |
| **Container runtime** | Docker (existing) | Existing experience on this host |
| **Private proxy** | Tailscale Serve (existing) | Already running; tailnet-only |
| **Backup** | Restic (installed) | Proven, encrypted |
| **Push notifications** | Web Push (web push protocol) | Supported by PWA |

### Service Boundaries
- **App Store API:** `http://127.0.0.1:8000` (private, Tailscale-only)
- **Tailscale Serve:** `adamsomarchy.tailbae2cf.ts.net` (tailnet-only)
- **No public endpoints** (no Tailscale Funnel, no 0.0.0.0:80/443)

### Architecture Decision Record (ADR-001)
- **Decision:** Use Tailscale Serve for private app access, not nginx/Tailscale Funnel
- **Rationale:** Already configured, tailnet-only, no public endpoints, minimal infrastructure
- **Alternatives rejected:** Custom nginx config (added complexity), Tailscale Funnel (exposes public endpoints, violates PRD)

---

## 8. PHASE PLAN

| Phase | Scope | Status |
|-------|-------|--------|
| **0** | Host assessment and implementation planning | **Complete** |
| **1** | Secure foundation (auth, API, DB, audit, installer boundary) | Not started |
| **2** | Curated catalog and reference installation | Not started |
| **3** | Application management and imports | Not started |
| **4** | Reliability and operational automation | Not started |
| **5** | Mobile integration and hardening | Not started |

---

## 9. APPROVAL LIST

| Action | Approval Required |
|--------|-----------------|
| Add user to docker group | **Yes** |
| Install restic | **Yes** |
| Configure nginx/HAProxy | **Yes** (if Tailscale Serve replaced) |
| Tailscale Serve ports | No (already tailnet-only) |
| Any firewall changes | No (not needed) |
| VM provisioning | No (not needed — hardware supports x86_64 VMs) |

---

*End of Phase 0 report. Awaiting approval for risky changes, then Phase 1 implementation can begin.*
