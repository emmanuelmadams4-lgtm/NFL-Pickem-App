# CODEX WORK ORDER 5 — step 10 web half, CLEANUP (scope-locked /refactor)

Try 1 of 2. Baseline: branch `lane/web`, the commit named in the hive message. Behaviour must not change: every
test in `apps/web/e2e/passkey.spec.ts` stays green, all texts stay word for word.

ALLOWED FILES (nothing else): `apps/web/components/passkey/browser.ts`, `apps/web/components/sign-in.tsx`.

REQUIRED
1. `browser.ts`: drop the private `unsupported` plus the `passkeyUnsupported = unsupported` alias; export one
   constant `passkeyUnsupported` and use it inside the file.
2. `browser.ts`: `createPasskey` and `getPasskey` repeat the same "no credential or no `toJSON` → throw, else
   return `toJSON()`" tail. Move that tail into one small private function both call.
3. `sign-in.tsx`: the "Could not reach the API… Check that the server is running." text is built twice (passkey
   and token paths). Build it once (a module constant) and use it in both places.

Nothing else: no renames of exported functions, no new files, no style changes.

PROOF: `npm run typecheck`; the coordinator reruns `e2e/passkey.spec.ts` on a fresh build.
CONSTRAINTS: /ponytail. No test edits. typecheck only: no build, no server, no browser, no pytest. Do not commit.
Report per item: done, or "no change needed" with the reason.
