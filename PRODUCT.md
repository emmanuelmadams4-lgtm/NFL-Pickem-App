# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One user: Emmanuel, the owner. He plays a weekly Yahoo Pick'em league and picks the straight-up winner of every NFL game (14 to 16 a week). He uses the app on a desktop browser and on his iPhone as a Home Screen web app. There are no other audiences and no plan for any.

## Product Purpose

Give an evidence-based pick for every game, show how sure the model is and why, and track his accuracy against the model, the betting market and the league leader. Success is his season pick accuracy on the Results screen, measured against the market (66.6% long-run) and the league leader (about 69%).

## Positioning

Win probability and uncertainty are separate numbers and are always shown separately. Every prediction is insert-only and timestamped, so the app can show what it said before kickoff and never rewrites history. Nothing is invented: missing data is shown as missing.

## Operating Context

* Weekly cycle. Lines and injury reports move from Tuesday to Sunday morning. Picks lock at each game's kickoff: Thursday night, Sunday 1:00 / 4:05 / 4:25 / 8:20 PM ET, Monday night, plus occasional London and Saturday games.
* He enters the picks in Yahoo himself. The app does not submit to Yahoo.
* Desktop for the weekly review. iPhone for late changes, often over Tailscale and sometimes offline.
* Alerts arrive by Web Push: pick flips, QB news, unpicked games near kickoff.
* Data comes from nflverse (schedules, lines, injuries, projected QBs) and Open-Meteo (weather). The reference for look and use is the ESPN iPhone app (NFL scores list and Matchup Predictor).

## Capabilities and Constraints

* Screens: sign-in, Week board, Matchup, Results (performance), Backtest, Settings.
* The client renders what the API returns. It holds no prediction logic.
* Terms with fixed meaning: **win probability**, **uncertainty** (low / moderate / high), **upset watch**, **backfill** (computed after the fact with pre-game inputs, always labeled), **live** (a pre-kickoff snapshot), **stale** (a source that failed to refresh).
* The recommendation for a game is its last snapshot before kickoff.
* Banned words in product copy: "lock", "guaranteed", and anything that implies certainty.
* PWA only. No native app, no App Store, no Android build.
* Undecided: how the Yahoo league scores ties; whether to add a "submitted in Yahoo" mark per pick.

## Brand Commitments

* Name: NFL Pick'em Intelligence. Short name in the app bar: "Pick'em Intel".
* Voice: plain, specific, calm. States what the evidence says and what is missing. No hype.
* Team logos from the API (`logo_url`, nflverse's ESPN links), cached for offline use (owner decision D38, 2026-10-12, replaces "no logos"). When a logo cannot load, the team shows its abbreviation in a team-color mark; never an empty ring.

## Evidence on Hand

* Real backtest, 2012 to 2025: market 66.6%, stats 64.5%, blend 66.5% (`CLAUDE.md`, `docs/gauntlet/PLAN.md`).
* Current screenshots of every screen in both themes: `docs/screenshots/`.
* Team colors come from the API (`apps/web/lib/team.ts` picks a readable one per theme).
* Research notes and open questions: `docs/design/USER_RESEARCH.md`.
* Absent, do not fabricate: the ESPN reference screenshots (owner to send), any observed-usage data, any second user's needs.

## Product Principles

1. Evidence before opinion. Every number has a source and an age.
2. Probability and uncertainty are different things and never share one visual.
3. Missing stays missing. A gap is shown as a gap, with the reason when known.
4. The fastest path is the pick. From opening the app to a saved pick is one tap per game.
5. The record is honest. Backfilled results are never mixed into the live headline.

## Accessibility & Inclusion

WCAG 2.2 AA. Meaning never rests on color alone (chips carry text, results carry a mark and a word). 44pt minimum touch targets on the phone. Reduced motion is honored. Text scales with the system setting. English only, times in the device's local zone.
