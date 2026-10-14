# CODEX WORK ORDER 4 — step 10 web half: a removed passkey must not come back from the saved cache

Try 1 of 2. Baseline: branch `lane/web`, the commit named in the hive message.

FAILING EVIDENCE (run `s10-green-3`, 13 passed, 1 failed): `e2e/passkey.spec.ts:266` "K12 design fixes …": after
the passkey is deleted and Settings is opened again, the section still shows the removed row ("Cancel me … Remove")
instead of "Passkey sign-in is switched off on the server." The server log shows no `GET /api/passkey` from the page
after the reload. Cause: the list is restored from the saved offline cache (`lib/persist.ts`) and the app-wide
`staleTime: 60_000` (`components/providers.tsx`) treats it as fresh, so it is not asked for again. A passkey removed
on another device stays listed for up to a minute; pressing Remove then gives a 404.

ALLOWED FILE: `apps/web/components/passkey/passkeys-section.tsx` only.
REQUIRED: the passkey list is fetched again every time the section opens (the saved copy may show until the answer
arrives, as other screens do offline). One option on the list query, as `use-passkeys-enabled.ts` already does for
health. Nothing else.
PROOF: `npm run typecheck`; the coordinator reruns `e2e/passkey.spec.ts` on a fresh build.
CONSTRAINTS: /ponytail. No test edits. typecheck only. Do not commit.
