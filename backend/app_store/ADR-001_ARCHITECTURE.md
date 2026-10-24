# Architecture Decision Record (ADR) — App Store v0.1

## ADR-001: Service platform choice
**Decision:** FastAPI (Python) + SQLite + Docker containers + Tailscale Serve
**Rationale:** PRD permits SQLite. Single-user private app. No external DB needed. FastAPI
  matches existing codebase. No microservices, no message broker, no external DB.
**Alternatives rejected:** PostgreSQL (external DB, adds complexity); Go (no TypeScript);
  Kubernetes (over-engineered for single-user).
**Accepted requirements preserved:** Tailscale-only access, one-user RLS, no public endpoints.

## ADR-002: Private access via Tailscale Serve
**Decision:** Tailscale Serve provides private app access. No nginx, no public ports.
**Rationale:** Already configured on the host. `https://adamsomarchy.tailbae2cf.ts.net` →
  `http://127.0.0.1:8000`. Tailnet-only (no Funnel). No public inbound endpoints.

## ADR-003: Database
**Decision:** SQLite (cf. PRD's accepted SQLite). App Store uses its own SQLite database
  alongside the Pick'em PostgreSQL. Separate schema, separate ownership.

## ADR-004: Authentication
**Decision:** Passkeys (WebAuthn) for user auth. API access via `APP_ACCESS_TOKEN`.
**Rationale:** Passkeys support enrolled authenticator on phone; no passwords to share.
**Alternatives rejected:** Username/password (password sharing violates constraint);
  OAuth (no external identity needed for single-user).

## ADR-005: Installer engine
**Decision:** Durable job engine (operation ID + idempotency key + durable checkpoints).
**Rationale:** PRD requires classified bounded retries and safe compensating operations.
**Files:** `backend/app_store/installer.py`

## ADR-006: Backup engine
**Decision:** Restic (after install via package manager). Independent encrypted backups.
**Rationale:** PRD requires proven backup engine. Restic is the standard for encrypted
  backups. Test restoration is required before marking complete.

## ADR-007: Push notifications (Web Push)
**Decision:** `pywebpush` library. VAPID keys in `.env`. Push via public service worker.
**Rationale:** PRD requires "supported mobile push notifications". Web Push is the standard
  PWA mechanism.

## ADR-008: App catalog
**Decision:** Static JSON catalog + import from GitHub URL. No arbitrary shell execution.
**Rationale:** PRD requires curated catalog. Import reviewed Docker/GitHub apps. Verified
  package + manifest version validation.

## ADR-009: Container isolation
**Decision:** Docker containers with `--network none` by default + capability drop.
**Rationale:** PRD requires: standard container must not control Docker daemon; high-risk
  apps isolated in separate VMs when technically supported. Hardware supports x86_64 VMs.

## ADR-010: Secrets management
**Decision:** Per-app credentials injected via Docker secrets/volume mounts.
**Rationale:** PRD requires "encrypted per-application credentials" and "secure application
  secret injection".

## ADR-011: Health & resources
**Decision:** `docker stats` for resource monitoring. Per-app health endpoint.
**Rationale:** PRD requires resource enforcement and health monitoring.

## ADR-012: Backup destination
**Decision:** `/backup/` (local) + optional restic remote (s3/rsync). Backward compatible.
**Rationale:** PRD requires "consistent application-aware database backups" + "versioned
  snapshots" + "destination availability checks".

---

## Technology stack (accepted by PRD)

| Layer | Technology | Reason |
|-------|-----------|--------|
| Frontend | Next.js 16 | Mobile-first PWA |
| Backend API | FastAPI (Python) | Already in repo |
| Database | SQLite | PRD-approved |
| Container runtime | Docker | Already installed |
| Private proxy | Tailscale Serve | Already configured |
| Backup | Restic | PRD-required |
| Push | pywebpush | PRD-required |
| Auth | WebAuthn | PRD-required |

## Security boundaries

1. Tailscale-only access (no public)
2. Passkey-backed authorization (op passkey approval)
3. Restricted installer boundary (no arbitrary shell)
4. No Docker socket exposed
5. No arbitrary code execution from import
6. Standard containers: `--network none` + capability drop
7. High-risk apps: separate VM when supported
8. Encrypted per-app credentials
9. Audit logging

## Liability boundaries

- No push notifications when home server is offline (planned).
- No arbitrary iOS apps silently installed (iOS requires App Store or enterprise).
- No "guaranteed"/"locked" picks (pick'em domain rule from PRD context).
- No deletion of unrelated resources on failed install.
- No rollback of DB migrations without backup.
