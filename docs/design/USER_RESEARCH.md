# User research — NFL Pick'em Intelligence

2026-10-11. One user (the owner), so this is a self-study, not a recruited one. Everything under "Known" comes from repo documents. Everything under "Assumed" is unverified and marked so. Nothing here was observed.

## Method

| Method | Why it fits one user | When |
|---|---|---|
| Owner interview (guide below) | Answers what no document does | Once, 20 min, before step 2 lands |
| Diary from data the app already stores | Picks have timestamps; predictions are insert-only. No new tracking needed to see when he picks and how often he overrides | After week 6 and week 8 |
| Usability walk-through against ESPN | The owner-set bar is "can I make this pick fast and with confidence" | When the ESPN screenshots arrive |

Surveys, card sorts and A/B tests need many users and are out.

## Known (from `CLAUDE.md` and `docs/gauntlet/PLAN.md`)

* He picks every game weekly by gut and memory, 14 to 16 picks, each locking at kickoff.
* He wants to beat the market (66.6%) and reach the league leader (about 69%).
* He uses a desktop and an iPhone. The phone app is a PWA.
* He wants alerts for pick flips, QB news and unpicked kickoffs.
* The reference he chose is the ESPN iPhone app.

## Jobs to be done

1. **Decide.** When the week opens, show me who should win each game and how much to trust it, so I can pick all of them in one sitting.
2. **Re-decide.** When news breaks close to kickoff, tell me which pick changed and why, so I only revisit the games that moved.
3. **Don't miss.** Before a game locks, make sure I have a pick in.
4. **Learn.** After the week, show me where I beat or trailed the model and the market, so I know whether my overrides help.
5. **Trust.** Let me see the evidence and its age, so I know when the app is guessing.

## Weekly journey (assumed until the interview confirms it)

| When | He is | Needs from the screen | Surface |
|---|---|---|---|
| Tue to Wed | Doing the first pass at a desk | Whole slate at once, sortable, picks in one tap | Week board, desktop |
| Thu evening | Checking one game before kickoff | That game first, lock time visible | Week board, phone |
| Sat to Sun morning | Reacting to injury and QB news | What changed since his pick; attention filter | Alerts, Week board, Matchup |
| Minutes before 1:00 PM ET Sunday | In a hurry, maybe on poor signal | Unpicked games only; works offline; lock countdown | Week board, phone |
| Mon to Tue | Reviewing | Me vs model vs market, per week and season | Results |

## Design implications

| Finding | Implication for the design system |
|---|---|
| Sixteen decisions in one sitting | A dense, scannable row per game. Typography and alignment carry hierarchy, not boxes |
| Picks lock at kickoff | Time to lock is always visible on an open game. Locked rows look different from open ones without color alone |
| Probability is not confidence | Win probability and uncertainty get different visual forms (a bar and number vs a text chip) and never merge |
| Late changes happen on the phone | Pick buttons are thumb-reachable, 48px tall, with clear selected and queued-offline states |
| He overrides the model | "My pick differs from the model" is a first-class state, shown neutrally (it is not an error) |
| Trust depends on freshness | Every data block shows its age. Stale sources that feed the model get a loud banner; others get a quiet note |
| He compares himself to three things | Me, model and market each keep one fixed color everywhere |

## Owner interview guide (20 min)

1. Walk me through last week's picks. When did you make them, and on which device?
2. How many did you change after first picking? What made you change?
3. When the app's pick and your gut disagree, what do you want to see before deciding?
4. What does "high uncertainty" make you do differently, if anything?
5. Which alert would you act on within a minute? Which would annoy you?
6. On the phone, what is the one thing you open the app to do?
7. How does your Yahoo league score a tie? Do you want a "submitted in Yahoo" mark per pick?
8. Show me the ESPN screens you like. What exactly is good about them?

## Open questions (block nothing; answers refine `design.md`)

* Yahoo tie rule and the "submitted in Yahoo" mark (question 7).
* ESPN reference screenshots (question 8).
* Does he pick the whole slate at once or game by game? This decides whether the phone needs a "next unpicked game" flow.
