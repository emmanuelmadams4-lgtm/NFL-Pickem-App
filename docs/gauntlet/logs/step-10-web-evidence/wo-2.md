# CODEX WORK ORDER 2 — step 10 web half: a second passkey on one device, and the lint line

Try 1 of 2. Baseline: worktree lane-web, branch `lane/web`, the commit named in the hive message.

ALLOWED FILES: `apps/web/components/passkey/passkeys-section.tsx`, `apps/web/components/passkey/browser.ts`, `backend/nflpi/api/main.py` (the one line only).

REQUIRED
1. Adding a passkey from a device that already holds one for this app: the browser refuses with `InvalidStateError` (the server sends the stored ids as `exclude_credentials`). Today the section shows the browser's own English sentence. Show "This device already has a passkey for this app." instead, and add nothing. Failing test: `e2e/passkey.spec.ts:237` "K5 a second passkey from the same device is refused in plain words" (red: `s10-red-2b`). Treat only `InvalidStateError` this way; other errors keep their current handling.
2. `uvx ruff check nflpi tests` → `nflpi/api/main.py:61:121 E501 Line too long (124 > 120)`. Wrap it so ruff passes; no other change in that file.

PROOF (the coordinator reruns): `npm run typecheck`; ruff; `e2e/passkey.spec.ts`.
CONSTRAINTS: /ponytail. No test edits. typecheck only; no build, server, browser, pytest; no commit. Report per item.
