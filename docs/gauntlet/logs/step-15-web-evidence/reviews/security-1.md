# Security review (Dwight) — step 15 web at `6296c54`, diff from main `a1fd984`

Hive message `2026-10-13T18-01-24-672Z-6c5521`. VERDICT: **PASS**. Nothing critical, nothing high in his rating. He read the whole production diff and ran two ECC reviewers on the commit through git only; nothing was executed.

The five checks asked for, all met: (1) `clock` reaches the screen only as text children; no attribute, URL, class, style or raw HTML takes a live field; club codes come from the game; rows are matched by exact `game_id`. (2) A 401 from `/api/live` reaches the app's sign-out handler; no token in a URL, key or error text. (3) Live replies are kept out of the saved cache; nothing touches the pick queue, a pick or a prediction. (4) Polling: only with a started game on screen, 30 s or 120 s, not in the background, no retry, about two requests a minute at most. (5) No package or lock change, no secret, no outside host in `live.spec.ts`.

| # | Sev | Finding | Decision (coordinator) |
|---|---|---|---|
| F1 | MEDIUM | A failed or still-loading first `/api/live` reads "Started · No live score right now", the same words as a feed with no row. | Not changed: decided before the build (spec review finding 1). The words are true in both cases, and the app's offline banner covers a dead connection. Carried to the integrator as a known limit. |
| F2 | MEDIUM | A held ended row shows with no age until the week says final, and before the stale test; the Map is not cleared on sign-out. | Not changed: the row says the game ended with that score, which stays true when the feed dies; scores are public and a reload clears the Map (`ponytail:` note with its ceiling in `queries.ts`). Carried. |
| F3 | LOW (one reviewer: HIGH) | Any state other than `post` and `lost` falls through to "Live". | Not changed: the server types `state` as `in`, `post`, `lost` and the generated client type is that union, so the check would be dead code to the compiler. Carried: if 15d ever adds a state, `cardLiveState` must be revisited (the type change will flag it). |
| F4 | LOW | With no model pick and no pick of mine the chance line names the home club. | Not changed: decided in the spec review (finding 17). |
| F5 | LOW | Probabilities and scores are not range-checked on the client. | Not changed: the server's schema is the boundary. |
| F6 | LOW | A game left `scheduled` after its kickoff counts as started for good (poll every 30 s while that week is on screen). | Not changed: the same rule locks picks today (`isLocked`). Carried. |
| F7 | LOW | `clock` has no length limit on the client. | Server's (15d). Carried. |

Not verified by him: the browser suite and the gate, the server relay beyond the row type, `live.spec.ts` beyond a scan for hosts and tokens, the `test_api.py` addition.
