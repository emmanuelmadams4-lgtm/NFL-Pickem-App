# Step 10 (server half): passkey sign-in (WebAuthn)

Lane `passkey`, branch `lane/passkey`, base main `b73038e`. Coordinator: Creed (hive temp `worker-passkey`).
Mode: Gauntlet Loop ONE_SHOT, one session. Tier **T3** (the app's sign-in). Lands only after the owner's sign-off, through god.

## 1. PLANNING

* **What this builds (owner's words):** sign in with Face ID / Touch ID instead of pasting the app token. **What it
  replaces:** nothing; the app token stays as the backup way in (D33). **What it is not:** no screen (lane web builds
  the sign-in screen and the browser test on this contract), no email, no password, no user accounts.
* **Roadmap:** PLAN.md row 10, "Passkey sign-in (D33) | T3 | WebAuthn passkey, token stays as backup; needs HTTPS |
  Security review, e2e with a virtual authenticator | Owner sign-off". The e2e half is lane web's.
* **Prior decisions read:** OWNER_DECISIONS D33 and its notes (`docs/gauntlet/OWNER_DECISIONS_2026-10-12.md:179-190`);
  CLAUDE.md Security section; lanes.md section "Lane passkey" (OWNS and grants).
* **Pre-flight.** Problem: the only way in is a long token the owner must paste on each device. Why now: the app is
  served over HTTPS on the tailnet (step 5), which passkeys need. Scope: server routes, tables, one change in
  `require_token`; cut: screens, cookies, accounts. Success signal: the owner signs in on his iPhone with Face ID
  (checked by lane web's browser test and then on the real phone). Reversibility: two-way (clear two settings and
  the feature is off; the migration has a downgrade).
* **Assumptions.** validated: all four router mounts go through `require_token(authorization)` (`api/main.py:37-47,
  378-382`; `api/group.py:22-28` calls it directly), so one change covers them. validated: the web client sends
  `Authorization: Bearer` (`packages/shared/src/client.ts:63`). validated: `webauthn 3.0.1` API (inspected in a
  throwaway environment). assumed: one uvicorn process (in-process rate window). assumed: the tailnet host name is
  stable (D33 note: a new name means registering again).
* **Instrumentation.** Log events for registered / sign-in ok / refused (reason word) / removed; a push alert on
  every add and remove; `notifications` rows of kind `passkey`. Guardrail: the whole existing suite stays green.
* **Deployment reach.** Nothing is deployed by this lane. Passkeys stay off until `PASSKEY_RP_ID` and
  `PASSKEY_ORIGINS` are set on the server. Real-device check is PENDING (lane web + owner's iPhone).
* **Tools.** `JEVGREP: not-ready` (`jg doctor`: Jev connection check failed through OpenRouter), so discovery used
  `grep`/direct reads of the five files the dispatch named; Jev decisions unavailable for the same reason, so the
  dispatch's routing stands (Sonnet builds, `ecc:code-reviewer` critic). `HEADROOM: not-routed`. Skills: gauntlet-loop
  (loaded), /ponytail rules inlined in every work order, TDD (tests first, below), harness-engineering N/A (feature
  code), Design Gauntlet N/A (no screen).
* **Build provider.** `codex exec` tried once with the default model, 2026-10-13 17:20 UTC: `The 'gpt-6.1-sol' model
  is not supported when using Codex with a ChatGPT account.` (`step-10-server-evidence/codex-probe.log`). So
  `IMPLEMENTATION_PROVIDER: CLAUDE (limit hit)`, `BUILD_RUNG: sonnet`. Claude builds every work order in this step.
* **EFFORT:** PLANNING/SPECIFICATION high (auth); IMPLEMENTATION coordinator low, builder Sonnet; VERIFICATION high.

## 2. SPECIFICATION (frozen)

* **Design:** `step-10-server-evidence/design.md` (sections 1-13). Reviewed by Dwight before any production code:
  **PASS to build, no CRITICAL, no HIGH; five MEDIUM (R1-R5) required and folded in**
  (`step-10-server-evidence/dwight-design-review.md`). Library agreed: `webauthn>=3.0.1` (py_webauthn, BSD-3-Clause);
  it pulls `pyOpenSSL` (certificate-chain checks for attestation formats we do not request), `cbor2` (decoding the
  authenticator's data), `pyasn1`/`pyasn1-modules` and `cryptography` (already locked through pywebpush).
* **Gate:** `step-10-server-evidence/gate.sh <label> full` = full `pytest -q`, `ruff check nflpi tests migrations`,
  alembic on a fresh scratch database (upgrade head, check, downgrade one, upgrade), `npm run gen:api` with no drift.
  Twice on the final commit, plus a mutation pass (each security rule broken once, each caught).
* **Public test seam:** the HTTP routes through the real app, the three table names, and four names frozen for
  tests: `nflpi.auth.throttle.reset/LIMIT`, `nflpi.auth.passkeys.MAX_PASSKEYS/MAX_LIVE_CHALLENGES`,
  `nflpi.auth.sessions.session_factory`.
* **Frozen clauses, all in `backend/tests/test_passkey.py`** (42 tests, 60 cases; the passkey is the software
  authenticator in `backend/tests/fixtures/passkey/authenticator.py`, which makes real keys and signatures):

| Clause | Rule | Test (prefix `test_`) |
|---|---|---|
| P1 | Settings unset, half set or unsafe: every passkey route 503 "not configured"; token routes unchanged; clearing them ends sessions with no database call | `p1_*` (4) |
| P2 | A stranger cannot start or finish a registration, list, remove or sign out | `p2_*` |
| P3 | Register; replies never carry the key or credential id; no duplicate; label rules | `p3_*` (4) |
| P4 | Sign-in gives a session (`pks_`, 30 days, no-store) that opens all four router mounts | `p4_*` (2) |
| P5 | A challenge works once, also after a failed finish | `p5_*` (3) |
| P6 | A challenge expires after 5 minutes | `p6_*` |
| P7 P8 P11 | Origin, relying-party id and user verification are checked | `p7_p8_p9_p11_*`, `p7_p8_p11_*` |
| P9 | A tampered finish, another key, or a challenge of the other kind fails | `p7_p8_p9_p11_*`, `p9_*` (2) |
| P10 | A sign count that does not go up is refused; a higher one is stored; zero keeps working | `p10_*` (2) |
| P12 | Only the session's hash is stored; expired and signed-out sessions refused; header only | `p12_*` (4) |
| P13 | Removing a passkey ends its sessions; the last one gone, the app token still works | `p13_*` |
| P14 | Every sign-in failure answers the same; begin looks the same with and without a passkey | `p14_*` (2) |
| P15 | Nothing secret in any log record | `p15_*` |
| P16 | One rate window over the public routes (refused before any row or body); challenge cap; 64 KB body; 10 passkeys | `p16_*` (4) |
| P17 | The existing suite stays green with no test edited (one granted migration-list line) | gate + `git diff b73038e -- backend/tests` |
| P18 | Migration: upgrade, check, downgrade one, upgrade | gate (alembic) + `test_hardening.py` list line |
| P19 | App token check unchanged; a plain wrong token costs no database call; 503 when no app token | `p19_*` (3) |
| P20 | Relying party and origin come from settings, never the request | `p20_*` |
| R1 | Only the app token can add a passkey; a session gets 403 and creates nothing | `r1_*` |
| R2 | Adding and removing a passkey alerts the owner; a failed alert undoes nothing | `r2_*` (3) |
| R3 | A challenge is matched by its bytes, not its spelling | `r3_*` |
| R4 | A database failure in the session check is a 503, not a 401 | `p19_r4_*` |
| R5 | The challenge cap is per kind | `p16_r5_*` |

* **Red for the intended reason** (single file, own scratch database): `9 failed, 51 errors`: 51 x `ModuleNotFoundError:
  No module named 'nflpi.auth'`, 9 x route answers 404 where the clause expects 503/200. Log:
  `~/.claude/plans/nfl-pickem-lanes/logs/passkey/red-1.log`. Lint of the test files: clean.
* **Done by outcome.** functional: the table above. user-facing: PENDING, lane web's browser test with a virtual
  authenticator and the owner's iPhone. operational: log events, push alert on add/remove, 503 texts.
* **Starting rung:** `BUILD_RUNG: sonnet (try 1 of 2)`. Reason: Codex refused (above); the spec, the tests and the
  library calls are settled, so the build is wiring.
