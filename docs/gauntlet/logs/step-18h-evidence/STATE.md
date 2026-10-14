# Lane wire18h state (restart file)

Branch lane/wire18h, base origin/main b5ee53f. Test DB: DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15442/nflpi_wire18h (never 5432: live stack). uv/git need sandbox off.

## Design (decided 2026-10-14)
1. Simulator in the live path, NO migration, NO models.py change: stored as `features["simulation"]` on the insert-only
   Prediction row (so it is part of inputs_hash; a new row only when the simulation changes).
   - SimParams cannot be learned from the DB (the games table has no overtime flag). `jobs train` fetches nflverse
     games.csv, learns params with the 18c bench (`build_table` + `learn_for_season(.., "football_only")`) for the
     season being predicted, and saves them in AppSetting `sim_params_<season>`. No params -> `simulation` is null.
   - Expected points: football-only ScoreModel (STATS_FEATURES) fit on the ten seasons before the game's season,
     EloParams() as the bench. Spread = home_spread_from_nflverse(latest spread_line); total = latest total_line.
   - seed = crc32(game_id) ^ BASE_SEED; DEFAULT_DISTRIBUTION; playoff = game_type != "REG"; n = 10,000.
2. Pick mode: config `pick_mode` (None | straight_up | confidence_pool; both pick the straight-up winner). WeekOut.pick_mode
   = {mode, assumed, label} from nflpi.picks.make_picks([], mode). None -> straight_up, assumed.
3. D74: sheet.order(games) sorts by (-prob, game_id); Jev code removed from sheet.py and jobs.predict. TIE_BAND kept
   (model_c imports it).
4. Spread: picks/rules.py re-exports nflpi.data.asof.home_spread_from_nflverse; sim_backtest.quoted_home_spread removed,
   calls go to home_spread_from_nflverse. predictions/ and api/ may not import nflpi.data (test_data_layer), so the
   engine imports it through nflpi.picks.

## Checkpoints
- [x] 1 spec + red tests committed
- [x] 2 build green
- [x] 3 gen:api
- [x] 4 mutation sweep
- [x] 5 critic PASS
- [x] 6 lane-guard + done
