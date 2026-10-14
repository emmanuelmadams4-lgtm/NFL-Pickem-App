# Step 18d: pick rules (lane picks)

Owner brief `docs/model/OWNER_BRIEF_2026-10-13.md` sections 3 and 9; decisions D68, D70, D71. Base `e4f7a44` (main after PR #30), branch `lane/picks`. Tier T2 (new behaviour, nothing user-facing; nothing imports the package). One-way doors: none.

## Checkpoints
| # | Checkpoint | Result |
|---|---|---|
| 1 | Plan: modes, inputs, boundaries | Done. Plain-probability inputs (`GameInputs`), so no `nflpi.sim` import is needed and the simulator, win model or a test can feed it. Reuse of `nflpi.betting` settlement, `SettlementProbs`, `expected_value`, `ensure_fresh`. Codex tried: `codex exec` fails in this sandbox (`Operation not permitted`), so builders are Claude Sonnet subagents (Build Ladder rule 5). |
| 2 | Specification frozen | `docs/model/PICK_RULES.md`, clauses P1 to P25, commit `c6099bc`. |
| 3 | Tests first, red | `backend/tests/test_picks.py` by a separate Sonnet tester; red: `ImportError: cannot import name 'Advice' from 'nflpi.picks'` (package absent). Commit `e2eddba`. |
| 4 | Implementation, green | `backend/nflpi/picks/` (types 130, rules 187, pool 36, advice 44, init 32 lines) by a separate Sonnet implementer. 151 of 152 first run; the one failure was a wrong expectation in my test (P16 used the home chance of a game whose chosen side is away); expectation fixed, not the code. 152 passed. ruff clean. Commit `665f93b`. |
| 5 | Mutation sweep: one mutation per clause | `evidence/mutate.py`: 37 source mutations across P1 to P24 (P25 holds by construction: advice takes no picks), 37 killed, 0 survived (`evidence/mutation-run1.txt`). |
| 6 | Critic (fresh, no transcript), lane-guard, done | See section below. |

## Deviations and choices
- `GameInputs.p_home_win` / `p_away_win` default to NaN (rejected by validation) so an empty construction raises `PicksError`, not `TypeError`.
- Fallback picks (no cover or over chances) carry `probability = None` and `expected_points = None`; nothing is invented. Totals fallback uses `basis="margin_fallback"`, same name as ATS.
- `pick_ats` / `pick_totals` take only `push_rule` and `tie_break`; the close-call and disagreement bands describe win chances.
- Pool: largest share gets the largest weight; ties in share by `game_id` (default) or `input_order`.
- Value stars: `UNRATED` unless a `validated` rubric is passed (D70); `NO_BET` for a stale price or nonpositive expected value; a missing quarterback caps at `UNRATED`.
- Gate (D71): own test file plus ruff locally; the full gate is the CI of the pull request.
- Sandbox: `uv` and `git fetch` needed the sandbox off; the `.git/config` update for the branch rename was denied (the branch ref itself is renamed).

## Critic (checkpoint 6)
Fresh `ecc:python-reviewer`, no transcript, on head `93fe57b`, ran only `tests/test_picks.py` (152 passed) and ruff (clean). **Verdict: PASS**, no CRITICAL, HIGH or MEDIUM. LOW, left as is and recorded: `make_picks(games, "ats", close_band=...)` raises `TypeError` (the ATS and totals functions take no band options); `home_spread_from_nflverse` does not validate its input (a non-number raises `TypeError`, NaN is rejected later by `GameInputs`, `0.0` gives `-0.0`); numpy integer weights are refused; `zip(strict=False)` in the rubric check is intentional.
