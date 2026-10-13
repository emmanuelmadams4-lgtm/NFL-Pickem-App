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
| P17 | The existing suite stays green with no test edited (one granted migration-list line) | gate + `git diff <base> -- backend/tests` |
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

**Amended after review (before the critic), each with its test:** P1 now says the four ceremony routes answer 503
when unset; list, remove and sign-out keep working with the app token (`p1_the_owner_can_remove_a_passkey_while_
passkeys_are_off`). Added clauses from Dwight's code review: C1 a silent add or remove is still recorded and warned
(`r2_with_no_device_*`, `r2_a_failed_alert_*`), C3 a session refused for unset settings is logged
(`p1_clearing_the_settings_*`), C9 a wildcard or dotless relying party is not configured (`p1_half_set_*`). Added on
the test reviewer's advice: `p16_the_rate_window_slides`, `p5_a_failed_registration_finish_*`,
`p5_finishes_racing_on_one_challenge_*`. The first mutation sweep (56 mutants, `mutation-516ba39.log`) left three
alive, all test gaps and no code defect; closed with a wildcard relying party that has dots, a declared length over the
cap with a small body (`p16_a_declared_length_over_the_cap_*`), and the unknown passkey's id in the P15 secret list.
The file now has 48 tests, 69 cases.

## 3. IMPLEMENTATION

Provider: **Claude, Sonnet subagent** (Codex refused the model, section 1). The coordinator wrote the spec, the tests
and the software authenticator, and wrote no production code. Every proof below was rerun by the coordinator.

| Work order | What | Commit | Coordinator's own proof |
|---|---|---|---|
| 1 (`step-10-server-evidence/wo-1.md`), try 1 | `nflpi/auth/{throttle,sessions,passkeys}.py`, `api/passkey.py`, migration 0008, three models, two settings, 4 changed lines in `require_token` | `d4bf199` | 60 of 60 cases passed, ruff clean |
| 1, try 2 (narrow correction after the coordinator's read of the diff) | a body nested too deep (RecursionError became a 500), credential id shape, id range on DELETE, alert commit | `d4bf199` | red first: `red-2.log` 2 failed; then 60 passed |
| 2 (review fix + cleanup, section 4) | list, remove, sign-out without the settings; type hints | `098e0b0` | red first: `red-3.log` 2 failed; then 64 passed |
| 3 (Dwight's C1, C3, C4, C5, C9) | record and warn a silent add; log a refusal for unset settings; two race guards; relying-party shape | `098e0b0` | 67 passed (`green-2.log`), ruff clean |

Diff check after each return: `git status`, the full diff read by the coordinator, scope = the files the work order
allowed, no test edited by the builder, no untracked stray file.

**Review fan-out at `d4bf199`** (read-only, tier large): `step-10-server-evidence/reviews.md`.
`ecc:python-reviewer`: no CRITICAL, no HIGH. `ecc:pr-test-analyzer`: no vacuous test, three weak spots, all closed
with new tests. **Dwight (security, with `ecc:security-reviewer` and `ecc:silent-failure-hunter`): PASS on security
at `d4bf199`, C1 to fix; fixed in `098e0b0`** (`dwight-code-review.md`; how each finding was handled: design.md
section 15).

AGENTS: Sonnet general-purpose subagent (builder); `ecc:python-reviewer`, `ecc:pr-test-analyzer` (fan-out);
`ecc:security-reviewer` and `ecc:silent-failure-hunter` run by Dwight, not run twice; `ecc:code-reviewer` is the
fresh critic (section 6); `ecc:planner`/`ecc:architect`/`ecc:code-explorer` not used (the dispatch fixed the plan and
named the five files to read); `ecc:build-error-resolver` not needed (no build break).

## 4. CLEANUP

Scope-locked `/refactor` pass on the code this step added (work order 2, part B; behaviour unchanged, proof rerun:
64 passed before work order 3):
* `_begin`'s `make_options` typed as `Callable[[Session, PasskeyConfig], dict[str, Any]]`.
* Bare `dict` annotations in `api/passkey.py` and `auth/passkeys.py` became `dict[str, Any]`.
* A comment on the check-then-insert passkey count (owner-only route).
* The unused `cfg` dependency left three routes (this one is also the P1 fix).
* No dead code, unused import or duplicated block found in the new files: no further change needed.

Left as is, with the reason: `sessions.accepts` raises `HTTPException` (keeps `require_token` inside its 10-line
grant); the lazy import of `require_token` in `api/passkey.py` (same pattern as `api/group.py`; the grant is one import
line in `main.py`); raw SQL for writes (every time comes from the database clock in the statement that uses it).

## Seam asks for the integrator (no edit made by this lane)

* `nflpi/notify/push.py` has no public "send one alert" function; `api/passkey.py` calls `push._send` and
  `push._record`. A public wrapper there would be cleaner.
* `api/group.py` carries its own `_token` wrapper; it delegates to `require_token`, so it accepts a passkey session
  with no change. `live.py` and `news.py` carry no check of their own (mounted with the dependency in `main.py`).
* `config._HIDDEN_REPR_FIELDS`: nothing to add; the two passkey settings are not secret.
* Operator notes (docs/DEPLOY.md is not this lane's): set `PASSKEY_RP_ID` and `PASSKEY_ORIGINS` to the tailnet host
  name; after changing the app token or restoring a backup, open the passkey list and remove any you do not know.

## ROUTE CONTRACT (for lane web)

All under `/api/passkey`. JSON in, JSON out. Errors are `{"detail": "<text>"}`. Types are in
`packages/shared/src/api-types.ts` (replies only; the two finish bodies are untyped on purpose).

**Holding and sending the session.** Sign-in finish returns `{"session": "pks_...", "expires_at": "<UTC ISO>"}`. Keep
`session` exactly where the app token is kept today and send it the same way: `Authorization: Bearer <session>` on
every `/api` call. It lasts 30 days from sign-in and is not extended by use; `expires_at` tells you when to ask for
Face ID again. Never put it in a URL or a cookie. A 401 `Missing or wrong access token` means it is gone (expired,
signed out, passkey removed, or passkeys switched off): drop it and show sign-in. A 503 `Sign-in is temporarily
unavailable` means the server could not check it: KEEP it and retry.

| Route | Who may call | Body | Success | Errors |
|---|---|---|---|---|
| `POST /register/begin` | app token only | none | 200: creation options, pass to `PublicKeyCredential.parseCreationOptionsFromJSON` | 401 no sign-in; 403 `Adding a passkey needs the app token` (signed in with a passkey session: ask for the token, do NOT sign out); 429; 503 `Passkey sign-in is not configured` |
| `POST /register/finish` | app token only | `{"credential": <credential.toJSON()>, "label": "<1-64 printable characters, optional>"}` | 201 `{id, label, created_at}` | 400 `Passkey registration failed` (start again from begin); 401; 403; 409 `Passkey limit reached (10). Remove one first.`; 413; 422 `Label must be 1 to 64 printable characters`; 503 |
| `POST /signin/begin` | anyone | none | 200: request options (no `allowCredentials`), pass to `parseRequestOptionsFromJSON` | 429 `Too many attempts, try again in a minute`; 503 not configured (hide the passkey button) |
| `POST /signin/finish` | anyone | `<credential.toJSON()>` itself | 200 `{session, expires_at}`, `Cache-Control: no-store` | 401 `Passkey sign-in failed` (every failure, same text; start again from begin); 413; 429; 503 |
| `GET /api/passkey` | token or session | none | 200 `{"passkeys": [{id, label, created_at, last_used_at}]}`, oldest first | 401 |
| `DELETE /{id}` | token or session | none | 204; that passkey's sessions end at once | 401; 404 `Passkey not found`; 422 bad id |
| `POST /signout` | token or session | none | 204; the presented session is revoked (with the app token: nothing to revoke) | 401 |

Rules for the screen: a challenge works once and for 5 minutes, so call begin right before the browser prompt and
never retry a finish; ask for a platform passkey (the options already require Face ID / Touch ID and a discoverable
passkey); render `label` as plain text; list, remove and sign-out work even when passkeys are not configured; the
server refuses the 11th passkey. Only the mock proves nothing here: lane web's browser test with a virtual
authenticator is the first end-to-end proof, the owner's iPhone the second.

## 5. Evidence

Commits (after the branch was moved onto main `11cc401`): `3c81c72` spec, red · `a818128` implementation ·
`edcd32f` review fixes and cleanup (**last production change**) · `14b013b` tests for the three mutation gaps ·
`def9ce7` gate commit (docs and scripts after `14b013b`). Raw logs: `~/.claude/plans/nfl-pickem-lanes/logs/passkey/`.

| Evidence | Result | Log |
|---|---|---|
| Baseline, main `b73038e` (throwaway copy) | 1292 passed, 1 failed only because the copy had no repo-root `.env.example`: 1293 tests | `baseline-b73038e.log` |
| Red (spec, before any production code) | 9 failed, 51 errors: `No module named 'nflpi.auth'`, routes 404 | `red-1.log` |
| Red for each later fix | 2 failed each time, then green | `red-2.log`, `red-3.log`, `green-1..3.log` |
| Gate run 1 (before the first move onto a newer main, `098e0b0`) | 1360 passed in 1007 s; ruff clean; alembic clean; API types no drift | `gate-1-098e0b0.log` |
| Mutation sweep 1 (`516ba39`) | 56 mutants, **3 survived** (test gaps: wildcard relying party with dots, content-length cap, unknown passkey id in a log); tests added in `14b013b`, no production change | `mutation-516ba39.log` |
| **Mutation sweep 2** (`60c7da1` = `531a001` before the last move; same lane code) | **56 mutants, 0 survived, 0 not applied**; each mutant run against its own clause's tests | `mutation-60c7da1.log` |
| Critic's own gate run (`60c7da1`) | 1408 passed in 249 s; ruff clean; alembic clean; no drift | `critic-60c7da1.log` |
| **Gate run A on `def9ce7`** | **1456 passed in 306 s; ruff clean; alembic up, check, down one, up clean; API types no drift; exit 0** | `gate-A-def9ce7.log` |
| **Gate run B on `def9ce7`** (same commit, separate hold of the slot) | **1456 passed in 235 s; all four parts clean; exit 0** | `gate-B-def9ce7.log` |
| P17 | `git diff 11cc401 def9ce7 --stat -- backend/tests`: two new files and one line in `test_hardening.py` | critic.md |

Suite size: main had 1293 tests at `b73038e`, 1339 at `c55827f`, 1387 at `11cc401` (other lanes landed); this lane
adds 69 cases each time (1360 at first with 67, then 1408, then 1456).

**Lane guard** (`lane-guard.py check lanes.md passkey 11cc401`): 10 lines, every one a file the lane was GRANTED in
the note above its `lanes.md` section, none outside the grants:
`.env.example` (add-only settings) · `backend/migrations/versions/0008_passkeys.py` (the one migration) ·
`backend/nflpi/api/main.py` (one import, one include_router, +3/-1 in `require_token`) · `backend/nflpi/config.py`
(add-only) · `backend/nflpi/models.py` (append-only) · `backend/pyproject.toml` and `backend/uv.lock` (the one
dependency) · `backend/tests/test_hardening.py` (the migration-list line) · `packages/shared/openapi.json` and
`packages/shared/src/api-types.ts` (regenerated, never hand-edited).

## 6. VERIFICATION

* **Security review (Dwight, hive agent `dwight-mv5mkpow`):** design **PASS to build** with R1-R5 (all folded in
  before code); code **PASS on security** at `d4bf199` with both ecc agents, C1 to fix; delta **PASS** at `098e0b0`,
  "nothing CRITICAL, HIGH or MEDIUM is open". The later commits changed tests and scripts only, no production line.
* **Fresh critic** (`ecc:code-reviewer`, no build transcript, `60c7da1`): **PASS**; all 28 clauses covered, grants
  kept, sections 1-4 evidenced (`step-10-server-evidence/critic.md`). One critic round; no FAIL.
* **Coordinator's validation on the commit to land (`def9ce7`):** gate runs A and B above, both exit 0.
* **Moves onto a newer main:** twice (`b73038e` to `c55827f` at 18:20 UTC, then to `11cc401` at 18:58 UTC), both
  clean, under `res:git-integrate`; `uv lock` and `npm run gen:api` rerun each time with no change; the migration
  stayed `0008` on `0007` (no other migration landed). The critic and sweep 2 ran before the second move; the gate
  ran twice after it.
* **JEV (Job 4):** `passed` scored 0.78, inside the grey zone, so the advisor ruled.
  **ADVISOR: opus "did the review truly pass?" -> PASS for the server scope only.** It asked for these to be said
  plainly: the browser test and the real-iPhone check are PENDING, not passed; the critic's verdict and sweep 2 are
  on `60c7da1`, and `def9ce7` was gated twice but not swept again (no passkey line differs between the two); the last
  move onto main brought one unrelated change into a file this lane also edits (`backend/nflpi/config.py`: a `Field`
  import and a `star_summary_hour` setting from lane staralerts; it combined cleanly and the gate ran after it);
  Dwight did not see the later tests-only commits.
* **Done by outcome.** functional: PASS (table above). user-facing: **PENDING**, lane web's browser test with a
  virtual authenticator, then the owner's iPhone. operational: log events, the alert on add and remove, 503 texts,
  all under test; a real push to a real device is PENDING with step 11.

**Carried, advisory (none tied to a clause):** one shared rate window, so a flood on the tailnet keeps passkey
sign-in at 429 for as long as it lasts (owner decision 8); the two caps are check-then-insert; a database error on a
non-auth passkey route is a 500; a session may remove a passkey (owner decision 12); restored settings revive
sessions under 30 days old (decision 5); Dwight N1 one warning line per refused session while passkeys are off; N2 no
notifications row if the push sender itself raises (the change is still logged); private push functions (seam);
synced passkeys always report sign count 0, so clone detection only works for authenticators that count.

**Mistake to record:** at about 18:39 and 18:57 UTC the coordinator stopped its own gate script with a process match
that was too wide (any `evidence/gate.sh`) and at 18:57 it also signalled lane web's `step-15-web-evidence/gate.sh
g4`. Jim was told at once (hive inform). No file, database or lock of another lane was touched.

## 7. LANDING

Not done by this lane. Tier T3: god asks the owner to sign off, then lands. Nothing was pushed, no pull request
opened, nothing deployed. Passkeys stay off until `PASSKEY_RP_ID` and `PASSKEY_ORIGINS` are set on the server.

**Decisions for the owner (each two-way):**
1. A passkey session lasts 30 days from sign-in and is not extended by use.
2. The session is kept on the device where the app token is kept today and sent the same way.
3. Up to 10 passkeys, one per device.
4. Adding a passkey needs the app token; a passkey sign-in alone cannot add another passkey.
5. Removing a passkey signs that device out at once; a passkey sign-in may remove a passkey.
6. Every add and every removal sends an alert to your devices and is kept on record.
7. Face ID / Touch ID is required on every passkey sign-in.
8. Clearing the two passkey settings switches passkey sign-in off at once (sessions stop working; they work again if
   the settings come back within their 30 days, so remove a passkey to end its sessions for good). The app token is
   never affected.
9. A passkey is tied to the app's host name; a new host name means registering again.
10. Someone on your tailnet could make passkey sign-in refuse for as long as they keep flooding it; the app token
    still works.
11. After changing the app token or restoring a backup, open the passkey list and remove any you do not know.
12. New library: `webauthn` (py_webauthn, BSD licence), agreed by the security reviewer.
