# Design critic (UX + visual), round 2 (on `d0d7b9e`) — DESIGN VERDICT: PASS

Fresh subagent, read-only, given the after screenshots, the diff, design.md and the brief. No build history.

| id | severity | evidence | fix |
|---|---|---|---|
| C1 | Visual (copy, false statement) | `after-week-393`, summary strip, 4th cell (y≈320-345): "Model – No live picks". The cards below show a model pick on every game and `after-game-open-393` (y≈670) tags it "Live". Shortened from "No live picks graded" in `apps/web/components/week/kpi-strip.tsx:44`. | Change `phoneSub` to "None graded" for both the Me and Model cells. |
| C2 | Visual | `after-week-393`, chip row (y≈172-214): "Needs attention (4)" is dimmed from x≈335, so the count reads as disabled. The mask in `week-board.tsx:118` fades the last 15% of the row. | Fade only the last ~24px. |
| C3 | Visual | `after-week-full-320`, every card footer: Points select sits alone on a row with empty space to its right, and the pick buttons wrap below, adding about 55px per card. | Lower `min-w-36` on `PickButtons` in `game-card.tsx` so they share one row at 320. |
| C4 | Visual | `after-week-320`: the first card starts at y≈465 under the tab bar, so no recommendation or pick button is on the first screen. The Yahoo sheet pill takes its own row (y≈175-218). | At 320, keep the pill in the title row with `px-2.5` and no wrap. |
| C5 | Visual | `after-week-393`, title row: the Yahoo sheet pill (y≈122-162) is bottom-aligned to the subtitle, so it floats between title and subtitle and sits about 8px above the chip row. | Centre it on the title (`items-center`) or align its baseline to the subtitle. |
| C6 | Visual | `apps/web/components/toast.tsx:34,54-65`: the "New version ready." toast never times out and its only control is Reload, so it stays above the tab bar until he reloads. | Add a "Later" dismiss button. |
| C7 | Polish | `apps/web/lib/sync.ts:167`: "Pick not saved yet. Will retry." names no game. `apps/web/components/ui.tsx:13,15` says "the API" where the banner in `pwa.tsx:100` says "the server". | Name the matchup; use "server" everywhere. |
| C8 | Polish | `apps/web/components/settings/settings-view.tsx:327-328` and `after-settings-393` (y≈630-685): "Not protected…" offers no next step, and "This browser does not say." is vague. | Add "Add to Home Screen to protect it."; reword to "Can't tell on this browser." |
| C9 | Polish | `after-week-393`, summary strip: the two-line sub-labels at `leading-3` are tight, and the Final and Yours cells leave uneven empty space beside them. | Use `leading-4`, or one-line labels as in C1. |

Checked with no finding:
- ", next kickoff": now the same grey as the date and readable (`after-week-full-320`, y≈990).
- Lime: only on the selected chip, the active tab, the next-kickoff header and the Reload text.
- Control heights: chips, selects, week arrows and the Yahoo pill are all 44px.
- State copy: the offline and server-unreachable banners, the "Waiting to sync" chip, and the "N waiting pick(s) saved" and "locked at kickoff" toasts are plain and fire once per event.

**Largest problem:** C1. The first screen says the model has "No live picks" while every card shows one. Graded Visual because it does not block picking, but it is a false statement about the data.

Stop rule: no Critical or Structural finding open.
