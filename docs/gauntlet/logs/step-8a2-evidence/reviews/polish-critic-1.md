# Polish critic (fresh subagent, read-only), on `after2-*.png` and `eed7c61..989cac2`

Applied `polish.md` section 4. Crops at all three widths; J2 and J3 read at tablet and phone only.

| id | severity | evidence | fix | decision |
|---|---|---|---|---|
| J1 | Polish | Board, BUF cards: 8 px between players against 4 px inside one, so the second "BUF" reads as part of the first entry | `game-card.tsx`: wrapper `gap-x-2` to `gap-x-3` | Accepted (WO-6) |
| J2 | Polish | Game NE_KC: "Not on injury report" sits about 2 px above the name's baseline | `star-players.tsx`: `leading-5` on the plain-text status | Accepted (WO-6) |
| J3 | Polish | Game MIA_LV: "No injury report yet this week" and "No star list yet" look like captions | `star-players.tsx`: `text-subtle` to `text-text-2` on both | Accepted (WO-6) |
| J4 | Polish | Inferred from code: under 375 px the status of the long name could drop alone onto a line | `game-card.tsx`: position and status in one `whitespace-nowrap` span | Accepted (WO-6) |

No finding on contrast (4.8:1 and 5.3:1), the small-text token, borders, spacing, or the long name at 393 px.

**polish verdict: ship**
