# Kanban Board: NFL Pick'em Intelligence

**Board:** Slice 0 — Evidence and non-destructive validation
**Status:** BLOCKED on: Q-001 (home server inventory - done), Q-002 (cost estimation), Q-003 (Yahoo verification)
**Privileges:** No production writes, no purchases, no migrations, no deployments. Only evidence collection.

## Columns
- [ ] TODO
- [ ] IN_PROGRESS
- [ ] BLOCKED
- [ ] DONE
- [ ] DONE_WITH_DEPENDENCIES

## Columns detail

### TODO
- E-02 — Cost estimation (Q-002)
- E-03 — Yahoo scoring verification (Q-003)
- E-06 — MAID Phase 1 (AC-15)
- E-07 — Build handoff contract (Slice 1 gate)

### IN_PROGRESS
- E-01 — Home server inventory (Q-001) [COMPLETED]

### BLOCKED
- E-04 — Security/RLS/Tailscale proof of concept (AC-013)
- E-05 — Cloud fallback read-only proof of concept (AC-011)
- SLICE1-01 — Canonical schedule + verified deadline (WF-001)
- SLICE1-02 — Authenticated published snapshot read (FR-003/FR-004)
- SLICE1-03 — Existing approved forecast model + unique confidence optimizer (FR-007/FR-008)
- SLICE1-04 — Saved planned picks + manual Yahoo confirmation (WF-002/WF-005)
- SLICE1-05 — Immutable audit records (FR-028)
- SLICE1-06 — Independent read-only fallback (WF-008/AC-011)
- SLICE1-07 — Minimal cloud reminder (WF-006/AC-010)
- SLICE1-08 — Core acceptance tests AC-001/002/004/006/010/011/013/014

### DONE
- E-01 — Home server inventory (Q-001) [COMPLETED]

## Tickets

### E-01 (DONE) — Home server inventory (Q-001)
**Story:** As the owner, I need a documented hardware/software/network assessment of the home server before any architecture claims.
- [x] E-01a — CPU/RAM/disk/OS specs (nproc=8, i7-6700, 15GiB RAM, 952GiB disk, Arch/Omarchy)
- [x] E-01b — Verify Tailscale connectivity (active, 100.112.226.9, no public ports)
- [x] E-01c — Verify Docker availability (available, user not in docker group - pending re-login)
- [x] E-01d — Verify backup/restart capability (backup.sh/restore.sh exist, no cron verified)
- [x] E-01e — Update docs/GAUNTLET/EVIDENCE/E-01_HOME_SERVER_INVENTORY.md
- [x] E-01f — Verify: command ran, output recorded

### E-02 (TODO) — Cost estimation (Q-002)
**Story:** As the owner, I need an itemized recurring cost estimate below $50/month before any spending.

### E-03 (TODO) — Yahoo scoring verification (Q-003)
**Story:** As the owner, I need confirmed Yahoo league scoring rules before building the confidence optimizer.

### E-04 (BLOCKED) — Security/RLS/Tailscale proof of concept (AC-013)
**Story:** As the owner, I need confirmed that private auth works end-to-end using safe test data.

### E-05 (BLOCKED) — Cloud fallback read-only proof of concept (AC-011)
**Story:** As the owner, I need confirmed that read-only published data is accessible when home server is down.

### E-06 (TODO) — MAID Phase 1 (AC-15)
**Story:** As the owner, I need a team-size and role proposal before any cleanup.

### E-07 (TODO) — Build handoff contract (Slice 1 gate)
**Story:** As the builder, I need a clear handoff contract to start Slice 1 after Slice 0.

### SLICE1-01 (BLOCKED) — Canonical schedule + verified deadline (WF-001)
**Story:** As the owner, I need a verified weekly schedule and deadline before any prediction runs.

### SLICE1-02 (BLOCKED) — Authenticated published snapshot read (FR-003/FR-004)
**Story:** As the owner, I need an authenticated cloud read path that returns last-valid snapshot with staleness badge.

### SLICE1-03 (BLOCKED) — Existing approved forecast model + unique confidence optimizer (FR-007/FR-008)
**Story:** As the owner, I need the existing approved model computing unique 1..N confidence values.

### SLICE1-04 (BLOCKED) — Saved planned picks + manual Yahoo confirmation (WF-002/WF-005)
**Story:** As the owner, I need planned, confirmed, and actual picks kept separately in immutable records.

### SLICE1-05 (BLOCKED) — Immutable audit records (FR-028)
**Story:** As the owner, I need complete change/audit history for all mutations.

### SLICE1-06 (BLOCKED) — Independent read-only fallback (WF-008/AC-011)
**Story:** As the owner, I need cloud reads to work when home server is powered off.

### SLICE1-07 (BLOCKED) — Minimal cloud reminder (WF-006/AC-010)
**Story:** As the owner, I need the cloud reminder to work when home server is down.

### SLICE1-08 (BLOCKED) — Core acceptance tests AC-001/002/004/006/010/011/013/014
**Story:** As the owner, I need the 8 core acceptance criteria verified before Slice 1 delivers.

---

## Workflow
1. E-01 (done) → E-02 → E-03 (all evidence)
2. E-04 → E-05 (proof of concepts)
3. E-06 → E-07 (deliverables)
4. Handoff to Slice 1 after owner approval
