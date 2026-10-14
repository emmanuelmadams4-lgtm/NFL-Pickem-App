# Mutation sweep, step 18b (stdlib script mutate.py, 128 sites, 142 s, lock res:gate-c)
First run: 122 killed, 6 survivors. After the sweep:
- snapshot.py `zip(..., strict=True)` -> False: equivalent (both lists always have equal length).
- settle.py `(margin > 0)` -> `>=`: equivalent (margin == 0 returns earlier).
- odds.py `a > 0` -> `>= 0` and `> 1`: equivalent (a is never in -100 < a < 100 after the validity check).
- settle.py `margin > 0` -> `margin > 1` (survived): killed by new test_one_point_margin_decides_a_moneyline (confirmed by hand mutation).
- edge.py `Edge` frozen=True -> False (survived): killed by new test_edge_result_is_immutable (confirmed by hand mutation).
Raw output: mutation-run.txt
