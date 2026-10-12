# Owner design references (received 2026-10-12)

The image files sit next to this note on the owner's Mac only. They are screenshots of other
companies' apps, and this repository is public, so they are git-ignored. This note is the
committed record. A session without the files (cloud) works from the descriptions and marks the
blind side-by-side verdict PENDING.

## Owner statement, 2026-10-12 (his words)

> I only want to predict winners and scores based on history and keep a database of who I
> picked so we can learn and get better over time

Reading (coordinator's, not yet confirmed by the owner):

* Core = a predicted winner and a predicted score per game, a stored record of his picks, and a
  review of how picks and the model did. Everything else is secondary.
* **Predicted scores are new.** No step in `docs/gauntlet/PLAN.md` builds them.
* "Only" may mean cut AI reports, alerts and weather. OPEN: owner has not said which.
* "Based on history" may mean drop the betting line. OPEN. The backtest says stats alone are
  2.1 points worse than the blend (64.5% vs 66.5%).

## What each image shows

| File | Source | What to take |
|---|---|---|
| `01-espn-picks-top.png` | ESPN Pick'em, "Create an Entry", dark | One game per row, two wide pill buttons side by side (away left, home right). Each pill: logo on a team-tinted left third, abbreviation, then record and moneyline in small grey. Sticky bottom bar: "Submit Your Picks" and "0/14 Picks Made" with a progress bar. A full-width ad breaks the list (do not copy that). |
| `02-espn-picks-tiebreaker.png` | same | After the last game: a "TIEBREAKER · MON 10/19 · LOCKS @ 8:15 PM" block asking for total points in the Monday game. Lock time is stated next to the thing that locks. |
| `03-yahoo-my-picks.png` | Yahoo Pro Football Pick'em, "My Picks", light | Week stepper at top. Per game: "Away @ Home", final score, **a confidence number (15, 8, 3, 9, 11)**, two team buttons, the picked one tinted green (right) or red (wrong) with a check or cross between them, and a bar under the row with the share of the league on each side. |
| `04-yahoo-tiebreakers.png` | same | An open pick is tinted blue. **Tie breakers: a predicted score for each team in two games**, plus "who will score the MOST points this week" and "the LEAST". |
| `05-concept-light-match-list.jpg` | Dribbble concept (soccer) | Card per match: date and venue, crest - score - crest, two quiet actions. Detail screen with tabs and a split bar. |
| `06-concept-dark-lime.jpg` | Dribbble concept (soccer) | Near-black with one loud accent, big condensed display type, floating pill tab bar, segmented control at the bottom of a detail screen, win-share tiles. |

## What this changes

1. **His Yahoo league is a confidence-points league with score tiebreakers** (images 03 and 04).
   The app today gives a winner and a win probability only. To fill in Yahoo he also needs:
   a confidence rank (1 to N, highest on the surest game), a predicted score for both teams, and
   the most/least-points teams. None is in the plan. OPEN: confirm the league still runs this way.
2. Pick row: the two-pill row in image 01 matches `design.md` (pick pills, 48px on the phone).
   Add what ESPN shows and we do not: record under the team, and a sticky "N of M picked" bar.
3. Results: image 03 is the model for the review screen (right/wrong per pick, without colour alone).
4. Images 05 and 06 agree with `design.md` (dark first, one accent, floating pill tab bar).
   Nothing to change; do not add the photo backgrounds or the lime.
