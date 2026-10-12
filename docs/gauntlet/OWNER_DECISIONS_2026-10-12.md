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
| D19 | Owner, his words: "I would like a 1 hour reminder right before kickoff. On Thursday and on Sunday." then "I would like all of the reminders to be 1 hour before kickoff of the first game." Replaces the "cut the reminder" half of D6. Rule: on every day that has a game, one alert one hour before that day's first kickoff (Eastern day). Sent whether or not he has picked; opens the week's sheet. | two-way | he asks for per-game or per-slate reminders |

D19 notes (coordinator's reading): "all" = every game day, so Thursday, Sunday, Monday, and
Saturday or holiday games get the same single reminder. A 9:30 AM ET London game means one alert
at 8:30 AM and none before the 1:00 PM slate. Today's code reminds per game and only for games
with no pick (`notify/push.py`, `send_kickoff_reminders`); D11 makes every game have a pick, so
that rule would never fire and is replaced by this per-day rule. Games with no kickoff time yet
(`time_tbd`) never trigger a reminder.
| D20 | Owner, his words: "if there are any drastic changes right before kickoff of any other games, send me a reminder." For every game, not only a day's first: an alert when something drastic changes before that game's kickoff. Confirms the "alerts when a suggestion changes" half of D6. | two-way | alerts are too many or too few in a real week |

D20 notes (coordinator's reading). "Drastic" = any of: the suggested winner flips; the game's
label changes (easy pick / tough matchup / coin flip, D2); a team's starting QB changes; the win
chance moves by the existing threshold (`settings.alert_move_threshold`, used at
`predictions/engine.py:286`). Flip and big-move alerts already exist (`notify/push.py`,
`alert_prediction_changes`); label change is new and needs D2 built first. One alert per game per
change, never after kickoff, never for a locked game. These fire at the D9 refreshes (daily, 90
and 15 minutes before kickoff), so the limit in "Open" item 1 applies: with the free line source a
late change may not be seen. OPEN (owner): the threshold in points of win chance.

How D18 is met without breaking the validation rules in `CLAUDE.md` (coordinator's reading):

* Team ratings already move after every game. That keeps the model current; it does not raise its ceiling.
* The ceiling rises only by a better model: a challenger (new input or method) is tested walk-forward on past seasons and replaces the current one only if it wins with a 95% interval that excludes zero. Roadmap step 8 (play-by-play efficiency ratings) is the first challenger and is no longer "optional". Next candidates: a fresher line source, a starting-QB adjustment.
* The Results screen shows the live model's winners-correct by week and season beside the market's, so "getting better" is a measured line, not a claim.
* Bar: the market picks about 66.6%, the league leader about 69%. No promise of a number.
* His picks still never train the model (D7).

## Star players (second grill, 8 questions, 2026-10-12)

Owner, his words: "a teams star player as well it's not always the QB but the QB and star
offensive and defensive players".

| # | Decision | Door | Revisit when |
|---|---|---|---|
| D21 | A star is decided automatically from this season's playing time and production, re-ranked weekly. No award lists, no hand-kept list. | two-way | the list misses names he considers obvious |
| D22 | Per team: the QB + top 2 on offense + top 2 on defense (5 per team, 160 league-wide). | two-way | too many or too few alerts |
| D23 | Alert triggers on a star: Out or Doubtful (and game-day inactive); injured reserve, suspension or trade; Questionable; return after missing games. | two-way | Questionable proves to be noise |
| D24 | A star out is shown and alerted now. Whether it moves the suggested winner is tested as a model challenger on 2012-2025 (D18 rule) and enters the model only if it wins. No untested adjustment. | two-way | the challenger result |
| D25 | Delivery: one morning summary of that day's star changes; in the last 90 minutes before a game, a new change to that game is its own immediate alert. | two-way | - |
| D26 | Add ESPN's free public (unofficial) feed as a second source for injuries, inactives and roster moves. Fall back to nflverse; label each item's source and age. | two-way | the feed breaks or its terms forbid this use |
| D27 | On the game row: a short "who's out" line, stars only, with its age. Full list on the game screen. The label never changes because of an injury (D2 stays measured win chance). | two-way | - |
| D28 | The win-chance move that counts as drastic stays 10 points (`alert_move_threshold = 0.10`). | two-way | - |

Star-player notes (coordinator's reading, facts checked in the repo and database):

* Today `injury_reports` holds player, position, report and practice status from nflverse (1,413
  rows through 2026 week 5: 309 Out, 267 Questionable, 25 Doubtful). There is no snap, production
  or transaction data, so D21 and the IR/trade trigger in D23 need new ingestion.
* "Production" needs one stated formula per side before it is built (for example offense = share
  of team scrimmage yards and snaps; defense = snaps plus sacks, tackles for loss, passes
  defended). Offensive linemen have no box-score production; with "top 2 on offense" they will
  rarely qualify. OPEN: accept that, or rank linemen by snaps alone.
* ESPN's feed is unofficial: check its terms of use before building on it, never present it as
  official, and keep the app working when it is down.
* Honest limit: with about 160 stars and Questionable included, the morning summary will often
  list 10 or more items midweek.

## Quick chat (2026-10-12)

| # | Decision | Door | Revisit when |
|---|---|---|---|
| D29 | Owner, his words: "include a quick chat area hooked up to the jev and Claude sdk so I can ask it questions and clarification on why it picked it." A chat area where he asks why the app picked a team, answered by Claude or Jev (his choice). Fits D16: it only runs when he asks. | two-way | - |

D29 notes (coordinator's reading, checked in the repo). Most of this exists and is reused, not rebuilt:

* Built: `POST /api/games/{game_id}/ask` -> `ai/research.py:answer_question`; Claude through the
  Anthropic SDK and Jev through OpenRouter (`ai/providers.py`); answers come only from the game's
  evidence pack, are capped per day, and are stored in `ai_reports` (kind `answer`). The web game
  screen has the box with a Claude/Jev picker (`apps/web/components/game/ask.tsx`).
* Missing for a "chat": (1) follow-up questions, each call is one question with no memory of the
  last; (2) the evidence pack does not yet hold the label, points, star list or what changed since
  his pick, because those are not built; (3) no way to ask about the whole week ("which games are
  my riskiest?"), it is per game only; (4) never run against a real key (owner go-live step).
* Smallest build: show the game's earlier questions and answers as a thread and send the last few
  turns with each new question; add the new fields to the evidence pack as they land. A week-level
  chat is a second, optional piece.
* Rule kept: answers explain the model's numbers; they never invent a fact that is not in the
  pack, and say what is missing instead. No "lock", no "guaranteed".

## Matchup trends (2026-10-12)

| # | Decision | Door | Revisit when |
|---|---|---|---|
| D30 | Owner, his words: "matchups as well like a key player, qb, offensive coordinator has secret trends against a certain team ... and key trends like the jags never lost in London or the browns never lost on Tuesday night". The app surfaces matchup and situation trends for each game. | two-way | - |

D30 notes (coordinator's reading, checked against the database: 6,576 final games, 2002-2026).

* Can be computed today from `games` (teams, scores, `home_qb`/`away_qb`, `home_coach`/`away_coach`,
  `stadium`, `weekday`, `neutral_site`, `div_game`, rest days): team vs team, starting QB vs a team,
  head coach vs a team or vs another coach, record at a stadium or in London, by weekday or kickoff
  slot, off a bye or short week, in division.
* Needs new data: offensive and defensive coordinators (not in nflverse; no free clean source
  known), and non-QB player game logs for "player X vs team Y".
* Every trend is shown as a record with its sample size and years, never as a claim. Checked
  examples: Jaguars in London are 8-6 over 14 games, not unbeaten. Browns on Tuesday: 0 games in
  the data; only 5 Tuesday games exist at all.
* Rule kept (`CLAUDE.md`, D18): a trend moves the suggested winner only if it wins a walk-forward
  test. Most small-sample trends will not; they stay context on the game screen and in the chat's
  evidence pack (D29). A floor on sample size (proposal: 8 games) keeps 2-0 "trends" off the row.
* OPEN (owner): the sample-size floor; whether coordinators are worth a hand-kept table.

## AI keys (2026-10-12)

| # | Decision | Door | Revisit when |
|---|---|---|---|
| D31 | Owner, his words: "We don't need anthropic keys we have the anthropic sdk and the openrouter key on this device anyway". No separate Anthropic key. The OpenRouter key already on the owner's Mac powers the AI features. | two-way | OpenRouter cost or limits become a problem |

D31 notes (coordinator's reading, checked on the Mac 2026-10-12, values never printed):

* `OPENROUTER_API_KEY` is set in the owner's shell (`~/.zshenv`). `ANTHROPIC_API_KEY` is not set
  anywhere. The repo has no `.env`, only `.env.example`.
* The Anthropic SDK is a library, not a login: `ai/providers.py:ClaudeProvider` cannot call Claude
  without `ANTHROPIC_API_KEY`. So "Claude" must go through OpenRouter, which serves Claude models
  on the same key. Change needed: when no Anthropic key is set, build the "claude" provider as an
  `OpenRouterProvider` with a Claude model id. Small, in `get_provider` and `available`.
* Jev risk, untested: Jev returns choices, scores and yes/no probabilities, not prose. The owner's
  own helper (`~/.claude/bin/jev.sh`) calls OpenRouter's decisions endpoint, while the app's
  provider posts a chat completion to the Jev model. A written "why this pick" answer from Jev may
  not work as built. To check in the first live call; likely Jev's role in the chat becomes a
  structured second opinion (agree / disagree, how sure) beside Claude's written answer.
* Still owner-gated: the first real paid call, and putting the key into the server's `.env`
  (the coordinator does not copy keys).
| D32 | Owner, his words: "lets do a Claude code login so I don't have to use an api key I want to use the sdk". Claude is reached through the Claude Agent SDK using his Claude Code sign-in, not an Anthropic API key and not OpenRouter. Replaces the "Claude through OpenRouter" part of D31. OpenRouter stays for Jev. | two-way | sign-in use is disallowed for this, or subscription limits get in the way |

D32 notes (coordinator's reading, checked on the Mac 2026-10-12):

* Claude Code CLI 2.1.278 is installed (`~/.local/bin/claude`) and has `claude auth login` and
  `claude setup-token` ("long-lived authentication token"). `claude auth status` says
  `loggedIn: false`: the desktop app's sign-in is separate from the CLI's. The owner must sign in
  himself; the coordinator cannot.
* Build: a third provider in `ai/providers.py` that calls the Claude Agent SDK (Python package
  `claude-agent-sdk`, which runs the `claude` CLI) with no tools, one turn, the same system prompt
  and JSON-schema check as today. New dependency, justified by this decision.
* Where it runs. On the Mac outside Docker it uses the CLI's sign-in directly. Inside the Docker
  `app` image it needs the CLI installed in the image plus the token from `claude setup-token`
  passed as an environment variable. That token is a secret like a key: server `.env` only, never
  committed, never in web code.
* Limits to state honestly: calls count against his Claude plan's usage limits, not a per-call
  bill; a spawned CLI is slower than a direct API call (seconds); if the sign-in expires the AI
  features stop until he signs in again, and the app must say so plainly.
* OPEN (owner to confirm, coordinator has not verified): that his plan's terms allow using the
  sign-in for his own private app. Single user, not offered to anyone else.

## What this does to the roadmap (coordinator's proposal, not yet in PLAN.md)

* New step right after the desktop web app: **Pick sheet** = label (D2), points with re-rank and
  swap (D3, D10), auto picks (D11), copy sheet (D12), rank entry and scorecard (D7, D13).
  Needs a schema change (points, label and source on picks; the app's sheet per snapshot) and a
  backtest table for the label cuts.
* Alerts step: drop the kickoff reminder work that is not built yet; keep flip and QB alerts (D6).
* Go-live step: AI is tap-only (D16).
* New later step: tiebreaker scores for two games (D5), gated on a backtest.
* Alerts step grows: per-day reminder (D19), drastic-change alerts incl. label change (D20), star
  list + star alerts + morning summary + ESPN source (D21-D27). Likely two steps, not one.
* Model challengers, in order: play-by-play efficiency (old step 8), stars missing (D24),
  matchup and situation trends (D30).
* New step: trends panel on the game screen + trends in the chat evidence pack (D30).

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
