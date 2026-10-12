# Owner decisions, 2026-10-12 (grill session, 18 questions)

Source: the owner's answers in chat. Each row is his choice. These override `PLAN.md`,
`PRODUCT.md` and `design.md` where they differ. Not yet folded into those files (a step 2
session is editing them); the next PLANNING checkpoint must do it.

## What the app is

> this app is supposed to only have me pick winners and if this is a tough matchup, easy pick,
> or coin flip game and how many points from 1-16, 16 being the most confident on each pick

| # | Decision | Door | Revisit when |
|---|---|---|---|
| D1 | The app suggests a winner, a label and points for every game. He can change any of them. Both the app's sheet and his are stored. | two-way | never asked |
| D2 | Label = three steps of the blend win chance: coin flip (favorite under about 55%), tough matchup (about 55 to 67%), easy pick (above about 67%). Exact cuts come from the 2012-2025 backtest and each label ships with its measured hit rate. | two-way | a label's hit rate overlaps its neighbour's |
| D3 | Points = 1 to N (N = games that week), each number once, highest on the surest pick. The range is one setting, so "16 down" is a one-line change. | two-way | owner checks Yahoo's bye-week rule |
| D4 | Suggestion uses history plus the betting line (the current blend). | two-way | a history-only model matches the blend in walk-forward |
| D5 | Predicted scores for two games only: Sunday night and Monday night (the Yahoo tiebreakers). No most/least-points team. Must be backtested before it ships. | two-way | league changes its tiebreakers |
| D6 | Keep: alerts when a suggestion changes, AI report per game, weather per game. Cut: the "no pick yet" reminder. | two-way | owner asks |
| D7 | "Self-learning" = team ratings learn from results (as now) and the app keeps a scorecard of his changes vs the app's sheet. His picks never train the model. | two-way | several seasons of his picks exist |
| D8 | News: no feed. The model gets the freshest inputs at each refresh (results, line, injuries, starting QBs). | two-way | owner asks for a feed |
| D9 | Refresh daily, plus 90 and 15 minutes before each kickoff. The suggestion at kickoff is the last one. | two-way | data source rate-limits |
| D10 | A locked game keeps its winner and points. Open games re-rank with the numbers left. A number he set by hand is left alone; the app says when it differs. Changing a number swaps it with the game that had it. | two-way | never asked |
| D11 | A game he never touches: the app's suggestion is saved as his pick at kickoff, marked `auto`, and scored apart from picks he made. | two-way | never asked |
| D12 | Yahoo entry: one "copy to Yahoo" sheet (winner, points, two tiebreaker scores). No "entered" button; what is saved at kickoff is taken as submitted. | two-way | he reports the record and Yahoo disagree |
| D13 | Headline measure: his rank in the league. He types rank (and the leader's points) each week. Points and winners-correct are shown under it. | two-way | he stops entering rank |
| D14 | Start at week 6. Old weeks may come later through the existing CSV import. | two-way | - |
| D15 | Build order: labels + points + copy sheet first, on the desktop site. Then phone install, change alerts, tiebreaker scores, weather, AI reports. No promise for Thursday. | two-way | - |
| D16 | AI report runs only when he taps "explain this game". No automatic calls. Daily cap stays. | two-way | - |
| D17 | Accent stays blue. Phone screens borrow the soft glow at the top from reference 07. | two-way | - |
| D18 | Owner goal, his words: "I want the model to get better over time by choosing the winners more often." The model's share of winners picked is a tracked number, and model improvement is ongoing work, not optional. | two-way | - |

How D18 is met without breaking the validation rules in `CLAUDE.md` (coordinator's reading):

* Team ratings already move after every game. That keeps the model current; it does not raise its ceiling.
* The ceiling rises only by a better model: a challenger (new input or method) is tested walk-forward on past seasons and replaces the current one only if it wins with a 95% interval that excludes zero. Roadmap step 8 (play-by-play efficiency ratings) is the first challenger and is no longer "optional". Next candidates: a fresher line source, a starting-QB adjustment.
* The Results screen shows the live model's winners-correct by week and season beside the market's, so "getting better" is a measured line, not a claim.
* Bar: the market picks about 66.6%, the league leader about 69%. No promise of a number.
* His picks still never train the model (D7).

## What this does to the roadmap (coordinator's proposal, not yet in PLAN.md)

* New step right after the desktop web app: **Pick sheet** = label (D2), points with re-rank and
  swap (D3, D10), auto picks (D11), copy sheet (D12), rank entry and scorecard (D7, D13).
  Needs a schema change (points, label and source on picks; the app's sheet per snapshot) and a
  backtest table for the label cuts.
* Alerts step: drop the kickoff reminder work that is not built yet; keep flip and QB alerts (D6).
* Go-live step: AI is tap-only (D16).
* New later step: tiebreaker scores for two games (D5), gated on a backtest.

## Open, and honest limits

1. **Line freshness (blocks the value of D9).** Lines come from the nflverse schedule file
   (`ingestion/nflverse.py`, `spread_line` / moneylines). That file is not updated minute by
   minute, so a refresh 15 minutes before kickoff may see the same line as the morning. A truly
   fresh line needs an odds source with an API key (owner creates keys). Roadmap step 7 was
   already going to measure this. Until measured, do not claim "latest line".
2. Trades and draft picks are not model inputs and have no tested effect; they reach the number
   only through the line and the starting-QB data.
3. Yahoo bye-week point range (D3) and whether a tied game scores zero: owner to check.
4. "Tough matchup" is a fixed product term now. `PRODUCT.md` terms and banned words need the
   three labels added; the existing uncertainty grade stays a separate thing.
