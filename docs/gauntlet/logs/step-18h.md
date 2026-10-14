# Step 18h: wire the simulator and the pick rules into the live path (lane wire18h)

Lead: Toby (temp worker-wire18h). Base origin/main `b5ee53f`. Branch `lane/wire18h`. Plan: `docs/model/PLAN.md` section 2 row 18h and section 5 (D74).

## Objective
1. `refresh_predictions` stores the simulator's margin, total, cover and push chances beside the win probability, insert-only.
2. The API and the pick sheet expose the pick mode (straight-up default, labelled assumed).
3. D74: no AI tie-break in the confidence order; ties go to win chance, then game id.
4. One nflverse spread conversion: `nflpi.data.asof.home_spread_from_nflverse`.

## Design decisions
* **No migration, no `models.py` change.** The simulation is stored as `features["simulation"]` on the insert-only prediction row, so it is part of `inputs_hash`: a new row only when the simulation changes; old rows are never edited. Rows written before this step have no key and read as null.
* **Simulator parameters come from `jobs train`, not from the database.** The games table has no overtime flag, and `learn_params` needs it. `jobs train` fetches nflverse `games.csv` (the same file the schedule ingest reads), learns football-only parameters for the season it predicts with the 18c bench (`build_table`, `learn_for_season`) and saves them in `app_settings` (`sim_params_<season>`). No parameters means `simulation` is null: missing stays missing. A failed fetch never stops the win model training.
* **Expected points** come from the football-only `ScoreModel` fit on the ten seasons before the game's season, as the bench does (EloParams() default, `STATS_FEATURES`). Seed `crc32(game_id) ^ BASE_SEED` (the bench's), default distribution `paired_residual`, playoff games never tie.
* **Pick mode** is a setting (`PICK_MODE`: unset, `straight_up` or `confidence_pool`; both pick the straight-up winner, which is all the sheet shows). Unset gives straight-up with the PICK_RULES assumption label. `ats` and `totals` are refused until the screens can show them (18j).
* **Spread conversion.** `picks/rules.py` and `analytics/sim_backtest.py` now import the asof function. `predictions/` and `api/` may not import `nflpi.data` (`test_data_layer`), so the engine takes the function through `nflpi.picks`.
* `TIE_BAND` stays in `sheet.py` only because the step 14c bench (`analytics/model_c.py`) imports it.

## Checkpoints
| # | Checkpoint | Evidence | Result |
|---|---|---|---|
| 1 | Spec + red tests | `step-18h-evidence/red-tests.log` | 19 new tests red, 199 existing green |
