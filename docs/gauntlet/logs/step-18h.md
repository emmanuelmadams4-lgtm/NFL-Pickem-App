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
| 1 | Spec + red tests (`319baf2`) | `step-18h-evidence/red-tests.log` | 19 new tests red, 199 existing green |
| 2 | Build green (`bd99ff7`; Sonnet builder, Codex refused the model for this account) | `green-tests.log` | 382 related tests pass; ruff clean |
| 3 | `npm run gen:api` + typecheck (`666d2de`) | `gen-api.diff` | additions only: `SimulationOut`, `PickModeOut`, `PredictionOut.simulation`, `WeekOut.pick_mode`; `tsc --noEmit` clean |
| 4 | Mutation sweep, one per rule clause (`3bb62d6`) | `mutate.py`, `mutation.log`, `mutation-2.log` | 15/15 killed (M7 and M15 first survived; tests added, one redundant guard removed) |
| 5 | Full backend run (res:gate-b) + critic ecc:python-reviewer, no transcript, on `3bb62d6` | `full-pytest.log` | 2207 passed, 1 skipped; critic PASS (0 critical, 0 high) |
| 6 | Lane-guard vs origin/main | `lane-guard.log` | 10 files flagged, every one inside the written grants (below) |
| 7 | Security fixes after Dwight's review (see below) | `tests/test_wiring.py` | red first (5 failing), then green: `test_wiring` + `test_sheet` + `test_api` 68 passed |

## Security fixes
| Finding | Fix | Commits |
|---|---|---|
| X1 (medium) one bad stored row or one failing game stopped all predictions | `load_sim_params` returns None and logs on any error; each game's simulation and the score-model fit run guarded, log the game id, store None | red `998e09f`, fix `f4b7796` |
| X4 (low) a NaN could make the week endpoint answer 500 | each simulation is validated with the API's `SimulationOut` before storing; stored as None if it fails | `998e09f`, `f4b7796` |
| X5 (low) pick-mode label implied two orders | label ends with "Both pick modes use the same order: win chance, then game id" | `998e09f`, `f4b7796` |

X2, X3, X6 stay as they are (carried to the integrator).

## Lane-guard flags, each inside the lanes.md grant
`predictions/sheet.py` (seam grant, D74); `config.py` (add-only, one setting); `picks/rules.py` and `analytics/sim_backtest.py` (the one spread function each); `packages/shared/openapi.json`, `api-types.ts` (generated); `tests/test_sheet.py`, `test_picks.py`, `test_sim_backtest.py`, `test_model_c.py` (tests of the Jev tie-break or the spread functions; `test_model_c.py` only drops the removed evidence argument from one `order` call). The guard reads only the OWNS line.

## Critic advisories (not fixed; for the integrator)
1. MEDIUM: if the nflverse fetch fails during `jobs train`, the season's simulations are null with only a log line; no freshness record shows it.
2. LOW: `_score_model` catches only `ValueError`; another fit error would stop `refresh_predictions`.
3. LOW: `refresh_predictions` rebuilds the score frame each call (cost); the bench never simulates playoffs, the live path sets `playoff`; the first refresh after parameters are saved writes one new row per upcoming game (insert-only, as designed; alerts only on pick, move or label change).
4. LOW: the no-leak test checks the game's own score, not later games' scores (the season window excludes them).
* Also: `analytics/` and `jobs.py` may not contain `nflpi.data` (`test_data_layer`), so `sim_backtest.py` imports the asof function through `nflpi.picks`, as the engine does. Old `jev_tiebreak_*` rows in `app_settings` are now unused.

