# Implementation Reviewer, round 1 (fresh subagent, read-only), on `eed7c61..4657935`

Nothing was run; screenshots not opened. `audit.md` "Diagnostic Scan" applied. Paths under `apps/web/components/`.

| id | pass | severity | evidence | one-line fix | rule broken |
|---|---|---|---|---|---|
| 1 | code | Structural | `week/game-card.tsx:65-67`; `backend/nflpi/api/views.py:193` | Have the API mark the star (e.g. `StarStatus.in_qb_alert`) and filter on that flag. | No logic in the client; ST2 |
| 2 | code | Structural | `week/game-card.tsx:66` vs `:188` | Until the flag exists, match only against `qb_alerts.slice(0, 2)`. | Missing shown as missing |
| 3 | code | Structural | `week/game-card.tsx:200-217` | Show the no-list note beside the stars line and name the club from `no_list`. | Missing shown as missing; ST3 |
| 4 | I | Structural | `game/star-players.tsx:18,58`; `game/injuries.tsx:34` | Make star club names `h4` and give the full report its own `h3`. | Audit: heading hierarchy |
| 5 | code | Visual | `game/star-players.tsx:41-42` | Reuse the lowercasing `statusTone` from `injuries.tsx:9`. | DRY; pattern reuse |
| 6 | H | Visual | `game/star-players.tsx:43` | Drop `shrink-0`; add `max-w-[45%] break-words`. | Audit: overflow on narrow viewports |
| 7 | I | Visual | `week/game-card.tsx:204-208` | Prefix each star with `star.team`. | Clarity |
| 8 | I | Polish | `week/game-card.tsx:201-202` | Use `aria-labelledby` on the visible span; render the stars as `ul/li`. | Redundant label; list semantics |
| 9 | I | Polish | `game/star-players.tsx:44` | Replace the en dash with "Not known yet", or add an `sr-only` equivalent. | Status conveyed by text |
| 10 | code | Polish | `game/star-players.tsx:35-39` | Guard the detail line on `star.injury \|\| star.observed_at`. | All states implemented |
| 11 | code | Polish | `game/star-players.tsx:27` | Treat an empty `stars` array like no list. | All states implemented |
| 12 | code | Polish | `week/game-card.tsx:37`, `:69-72`; `game/injuries.tsx:9,72` | One `statusTone` and one `latest()` helper. | DRY |
| 13 | code | Polish | `week/game-card.tsx:204` | Key by `${team}-${slot}-${rank}`. | Stable React keys |
| 14 | tokens | Polish | `game/star-players.tsx:20,32,36,43` | Use one of `text-label` / `text-xs` (both 12px) throughout the file. | Audit: inconsistent tokens |
| 15 | code | Polish | `game/star-players.tsx:19` | Write `club?.stars_week != null`. | KISS |

Notes from the reviewer:

* 1: the alert text carries the injury report's spelling and the star carries the star list's spelling (contract item B3 exists because those differ), so the QB shows twice whenever they do. The alert text is also not cleaned of control characters, while the star name is.
* 2: the filter checks every alert, but only the first two are displayed. A star QB named in a third alert disappears from both lines.
* 3: when one club has stars out and the other has no list, the no-list note is suppressed, so the missing list reads as "nobody out". When the note shows, it does not say which club.
* 4: "Star players" and the injury-list club names are sibling `h3`s, the star club names are `<p>`, and the full report has no heading.
* 5: exact-case comparison (`=== "Out"`); "OUT" would lose its chip; Questionable is plain text here but a chip in the list below.
* 10: a status with no injury and no `observed_at` renders an empty `<p>`. 11: a list week with no stars renders an empty labelled `<ul>`.
* No hard-coded colours, radii or sizes; every class resolves to a theme token. No interactive elements in the diff.

**Single largest problem:** finding 1, with 2 as its side effect: the card decides what to hide by parsing a display sentence and comparing two names the backend knows are spelled differently. Minimal robust fix: `views.py` sets a boolean on the star from the matched report row; the card filters on the flag.
