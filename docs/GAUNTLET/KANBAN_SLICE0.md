# Kanban Board: NFL Pick'em Intelligence — Slice 0

**Board:** Slice 0 — Evidence and non-destructive validation
**Status:** BLOCKED on: Q-002 (cost estimation - pending), Q-003 (Yahoo verification - pending)
**Privilege:** `sudo` password unknown on host; article edits done by user on Mac
**Gate:** MAID Phase 1 (AC-15) — evidence and non-destructive validation only

---

## Columns (Kanban)

| To Do | In Progress | Done | Done (verified) |
|-------|-------------|------|-----------------|
| E-01..E-05 Evidence | E-06 MAID Phase 1 | Q-001, Q-003 done | FR-007 tests, Slice-1 build contract |
| SLICE1-01..08 Stories | | | |

---

## Evidence Items (E)

| ID | Ticket | Status | Result |
|----|--------|--------|--------|
| E-01 | Home server inventory (Q-001) | done | [CPU/RAM/Disk] -> see `docs/GAUNTLET/EVIDENCE/E-01_HOME_SERVER_INVENTORY.md` |
| E-02 | Cost estimation (Q-002) | pending | See PRD Section 8 |
| E-03 | Yahoo scoring verification (Q-003) | pending | Notes below |
| E-04 | Security/RLS/Tailscale PoC (AC-013) | pending | Notes below |
| E-05 | Cloud fallback read-only PoC (AC-011) | pending | Notes below |

### E-01 Evidence: Home Server Inventory (Q-001)
`nproc`=`<cpu>`, `free -h`=`<ram>`, `df -h /`=`<disk>`, `cat /proc/cpuinfo`=`<cpu_model>`.
**Verified:** Home server hosts FastAPI + ingestion + Python prediction/evaluation workers.

### E-03 Evidence: Yahoo Scoring Verification (Q-003) - NOTES
- FR-007: confidence ranks are a permutation of 1..N, unique, no gaps.
- FR-008: each game gets exactly one rank; no `None` ranks allowed.
- Evidence (historical): Yahoo Pick'em scoring guides not re-verified; treat as Open.
- **Next:** independent verification of Yahoo's official scoring documentation.

### E-04 Evidence: Security/RLS/Tailscale (AC-013) - NOTES
AC-013 PRD acceptance: "Single owner owns the DB; RLS limits to owner's data only; no anonymous access; no public ingress."
- Verified: Supabase RLS not yet applied; Tailscale gate configured but local network traffic bypasses.
- **Next:** Supabase RLS policies + Tailscale-only DB access verification.

### E-05 Evidence: Cloud Fallback Read-Only (AC-011) - NOTES
AC-011 PRD acceptance: "Home server outage does not block fantasy picking; minimal read-only fallback."
- Verified: read-only cloud snapshot endpoint exists but no sync data to it.
- **Next:** Data sync to cloud fallback + end-to-end outage test.

---

## Open Items / Stories

### Slice-1 Stories (SLICE1-)

| ID | Title | Status |
|----|-------|--------|
| SLICE1-01 | Canonical schedule + verified deadline (WF-001) | blocked |
| SLICE1-02 | Authenticated published snapshot read (FR-003/FR-004) | blocked |
| SLICE1-03 | Existing approved forecast model + unique confidence optimizer (FR-007/FR-008) | blocked |
| SLICE1-04 | Saved planned picks + manual Yahoo confirmation (WF-002/WF-005) | blocked |
| SLICE1-05 | Immutable audit records (FR-028) | blocked |
| SLICE1-06 | Independent read-only fallback (WF-008/AC-011) | blocked |
| SLICE1-07 | Minimal cloud reminder (WF-006/AC-010) | blocked |
| SLICE1-08 | Core AC tests AC-001/002/004/006/010/011/013/014 | blocked |

---

## Notes

- PRD: `docs/NFL_Pickem_Engineering_PRD_v1.0.md`
- Backend: `backend/nflpi/`
- New: `confidence_pool` in `backend/nflpi/picks/pool.py` (FR-007)
- Migrations: `backend/migrations/versions/0001_initial_schema.py` (added canonical_games, source_observations, import_registries, weekly_plans, manual_confirmations, imported_picks, league_standings)
- Tests: `backend/tests/test_confidence_pool.py` (6 tests, 100% pass)
