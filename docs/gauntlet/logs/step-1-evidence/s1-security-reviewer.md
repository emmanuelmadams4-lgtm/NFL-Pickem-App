# ecc:security-reviewer on c1ba844 — VERDICT: approve (nothing above LOW)
1. LOW api/main.py refresh + jobs.cycle: advisory unlock failure returns a still-locked pooled connection; fix invalidate() on failure. -> WO-E F5
2. LOW .github/workflows/ci.yml: no permissions block; actions pinned to mutable tags. -> WO-E F9 (permissions); SHA pinning carried
3. LOW Dockerfile --forwarded-allow-ips="*": acceptable while the port is bound to 127.0.0.1; a problem only if the bind changes. carried
4. LOW /api/health exposes worker_heartbeat timestamp (low value); malformed heartbeat -> 500 on a public route. -> WO-E F7
5. LOW ai/research.py daily cap resets at UTC midnight (up to 2x across midnight); max_tokens 16000 raises cost per call. carried
6. LOW cache middleware leaves /api responses without no-store (pre-existing). carried
Clean: CSV import refuses to overwrite locked picks; /settings cannot reset ai_attempts_* or worker_heartbeat.
