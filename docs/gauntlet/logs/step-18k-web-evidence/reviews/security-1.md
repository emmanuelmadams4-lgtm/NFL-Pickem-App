# Security review 1: step 18k web (Dwight `dwight-mv5mkpow`, 2026-10-15, on `5d8046b`, apps/ diff from 4ee29d4)

PASS for step 18k web: git diff 4ee29d4..HEAD -- apps/ (HEAD 5d8046b) in lane-web. There are no findings at CRITICAL, HIGH or MEDIUM.

WHAT I CHECKED
- I read the simulation.tsx change myself, plus the shared Notice in components/ui.tsx at lines 322-336.
- I did not run the two ecc agents. The change is UI only with no new surface. Nothing was run and no server was started.

RESULT
- XSS (a script getting into the page): none. The status heading comes from a fixed map. check.note and the cause are rendered as React text inside Notice, which renders children as plain React nodes with no innerHTML.
- The note is fixed server text plus game ids from our own report, and Claude's free text is not served (18k L1). break-words handles a long note.
- No new routes, fetch calls, storage or dependencies. The data comes from the existing authenticated game query.
- The test check18k.spec.ts rewrites /api/games/<id> in the browser only.
- This closes my 18j advice A1: a carried-forward or blocked simulation is now labelled.

ADVICE (LOW, not blocking)
- A1, simulation.tsx CHECK_CAUSES[check.cause] ?? check.cause: this is a plain-object lookup. A cause such as "constructor" or "toString" would return an Object.prototype function instead of falling back to the raw code. React would then drop it or warn, and the cause line would be empty. It cannot happen today, because the server sends only cap, provider, unparsed and error (cause is a plain str in the API, my 18k N3). To fix it, use Object.hasOwn(CHECK_CAUSES, cause), or a Map.
- A2: CHECK_HEADINGS[check.status] with a status this client does not know gives a Notice with no title. That fails soft, and the note still shows.

## Triage (Jim)

- A1: not taken. The server sends only cap, provider, unparsed and error (18k S4), and the worst case is an empty cause line. Carried as a one-line hardening if the cause set ever grows.
- A2: not taken. It fails soft and the note still explains the state; the status is a closed Literal on the server.
