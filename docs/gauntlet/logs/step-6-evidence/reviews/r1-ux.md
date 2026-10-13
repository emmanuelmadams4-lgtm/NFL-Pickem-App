# UX critic, round 1 (on `7611d89`) — DESIGN VERDICT: FAIL

Fresh subagent, read-only, given the screenshots, the diff, design.md and the brief.

| id | severity | evidence | fix |
|---|---|---|---|
| U1 | Critical | `after-week-full-393.png` (y≈869): ", next kickoff" is dark ink on the dark card and unreadable. `game-card.tsx` uses `text-accent-ink/75` on the dark body. | Use `text-text-2`. |
| U2 | Structural | `after-week-393.png`: previous/next week arrows are faint borderless chevrons; before they were bordered 44x40 buttons. `pickers.tsx` sets `hidden w-9 … lg:inline-flex` on top of Button's own `inline-flex`, yet they still render, at 36px. | Restore the bordered 44px buttons on the phone, or remove them for real. |
| U3 | Structural | `after-week-393.png` vs `before-week-393.png`: "Yahoo sheet" and "Updated …" are gone from the first screen. `week-board.tsx` puts them at the end of the `no-scrollbar` chip row, after "Sort by", with no edge fade. | Put Yahoo sheet beside the week picker and "Updated" in the subtitle line. |
| U4 | Structural | `pwa.tsx` `PickSync`: `.catch(() => {})` swallows any non-network flush error (e.g. 500). The 15 s retry runs only while unreachable, so the pick stays "Waiting to sync" with no message. | Toast "Pick not saved yet. Will retry." and retry while the queue is non-empty. |
| U5 | Visual | `pwa.tsx:93`: the banner always says "showing data from …". With the week not cached it sits above "Could not load this week", and with no timestamp it says "an earlier session". | Say "showing saved data" only when data exists; otherwise "nothing saved for this week". |
| U6 | Visual | `toast.tsx`: the update toast never expires and has no dismiss; it sits full-width above the tab bar over the cards. `role="status"` items inside an `aria-live` container can announce twice. | Add a 44px "Later" button; keep one live region. |
| U7 | Visual | `pwa.tsx:92`: the banner's `role="status"` node mounts already filled, so VoiceOver may not announce it. | Keep the region mounted and swap its text. |
| U8 | Visual | `after-week-320.png`: at 320x568 the first screen ends at the card's team row, with no recommendation or pick button. | Drop the kicker and merge the subtitle into the picker row at 320. |
| U9 | Polish | `sync.ts:174-175`: "1 offline pick synced" also fires after a Tailscale outage, when the phone was never offline. | "1 waiting pick saved." |
| U10 | Polish | `after-settings-393.png`: "Not protected…" gives no next step. `settings-view.tsx`: "This browser does not say." also shows while the request is pending. | Add "Add to Home Screen to keep it."; show "Checking…" while pending. |
| U11 | Polish | `after-week-full-393.png`: "Counts as X, the model's pick, unless you tap a team." repeats on all four cards; "Coin flip · Coin flips have won…" doubles the label. | Shorten; drop the repeated noun. |
| U12 | Polish | `providers.tsx`: the full-screen state says "Cannot reach the API" plus a raw error; the banner says "Can't reach the server". | Use one wording. |
| U13 | Polish | `pick-buttons.tsx`: the "Waiting to sync" chip is 11px. | Use `text-label`. |

**Largest problem:** U2 and U3 together. The density gain came from demoting week navigation and the Yahoo sheet link.

On the unreachable-server journey the pick queues, shows the chip, and syncs with one toast when the server returns. No dead end or double message; the only silent failure is U4.
