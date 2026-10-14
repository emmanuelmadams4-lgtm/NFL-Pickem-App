"""Mutation sweep for step 18d: apply one source change per clause, expect test_picks.py to fail, restore.

Run from the repo root: python3 docs/gauntlet/logs/step-18d-evidence/mutate.py
"""
import pathlib
import subprocess
import sys

P = "backend/nflpi/picks/"
MUTATIONS = [  # (clause, file, old, new)
    ("P2 half tie share", "rules.py", "p_tie / 2 if", "p_tie if"),
    ("P2 larger share", "rules.py", 'side = "home" if home > away else "away"', 'side = "home" if home < away else "away"'),
    ("P3 exact tie break", "rules.py", 'warns.append("EXACT_TIE_BREAK")', "pass"),
    ("P4 share is probability", "rules.py", 'Pick(g.game_id, "straight_up", side, share, share,', 'Pick(g.game_id, "straight_up", side, share, 1 - share,'),
    ("P5 close call boundary", "rules.py", "share < 0.5 + close_band", "share <= 0.5 + close_band"),
    ("P5 qb flag", "rules.py", '"QB_MISSING",) if g.qb_missing', '"QB_MISSING",) if not g.qb_missing'),
    ("P5 disagree boundary", "rules.py", ">= disagree_band", "> disagree_band"),
    ("P6 push bonus half", "rules.py", "bonus = 0.5 * push if", "bonus = push if"),
    ("P6 ats larger", "rules.py", "pick_first = a > b or", "pick_first = a < b or"),
    ("P6 equal goes to tie_break", "rules.py", "(a == b and _first(tie_break))", "(a == b and not _first(tie_break))"),
    ("P7 line recorded", "rules.py", "g.home_spread, push_rule, tie_break, chances, value", "None, push_rule, tie_break, chances, value"),
    ("P8 fallback margin sign", "rules.py", "g.expected_margin + g.home_spread", "g.expected_margin - g.home_spread"),
    ("P8 zero margin", "rules.py", "(value == 0 and _first(tie_break))", "(value == 0 and not _first(tie_break))"),
    ("P9 no spread warning", "rules.py", '(("NO_SPREAD",) if g.home_spread is None else ())', "()"),
    ("P10 total fallback sign", "rules.py", "g.expected_total - g.total", "g.total - g.expected_total"),
    ("P10 default side", "rules.py", 'side = "over" if _first(tie_break) else "under"', 'side = "under" if _first(tie_break) else "over"'),
    ("P11 coin flip warning", "rules.py", "flags = _flags(g) + (COIN_FLIP,)", "flags = _flags(g)"),
    ("P12 duplicate ids", "rules.py", "if len(set(ids)) != len(ids):", "if False:"),
    ("P13 assumed flag", "rules.py", "mode_assumed=True, **options", "mode_assumed=False, **options"),
    ("P13 unknown mode", "rules.py", "if mode not in modes:", "if False:"),
    ("P14 unique weights", "pool.py", "or len(set(weights)) != n", "or False"),
    ("P14 default weights", "pool.py", "list(range(n, 0, -1))", "list(range(n + 1, 1, -1))"),
    ("P15 share order", "pool.py", "key=lambda i: (-chosen[i][1],", "key=lambda i: (chosen[i][1],"),
    ("P15 expected points", "pool.py", "weight[i] * share", "share"),
    ("P16 game id order", "pool.py", 'ids[i] if tie_rule == "game_id" else ""', '""'),
    ("P17 spread settle", "rules.py", "settle = settle_spread if pick.mode == \"ats\" else settle_total", "settle = settle_total if pick.mode == \"ats\" else settle_spread"),
    ("P17 no line", "rules.py", "if pick.line is None:", "if False:"),
    ("P18 half push", "rules.py", "return 0.5", "return 1.0"),
    ("P19 nflverse sign", "rules.py", "return -spread_line", "return spread_line"),
    ("P20 stale price", "advice.py", 'reasons.append("STALE_PRICE")', "pass"),
    ("P20 ev boundary", "advice.py", "if ev <= 0:", "if ev < 0:"),
    ("P21 validation", "advice.py", "if rubric is None or not rubric.validated:", "if rubric is None:"),
    ("P22 star count", "advice.py", "sum(ev >= t for t", "sum(ev > t for t"),
    ("P22 below first", "advice.py", "if stars == 0:", "if stars < 0:"),
    ("P23 qb missing", "advice.py", "    if qb_missing:", "    if False:"),
    ("P24 rubric strictly increasing", "types.py", "any(a >= b for a, b", "any(a > b for a, b"),
    ("P1 probability bound", "types.py", "if not 0 <= p <= 1:", "if not 0 <= p < 1:"),
]


def run() -> int:
    return subprocess.run(["uv", "run", "pytest", "tests/test_picks.py", "-q", "-x", "-p", "no:cacheprovider"],
                          cwd="backend", capture_output=True, text=True).returncode


def main() -> int:
    survived, killed, skipped = [], 0, []
    for clause, name, old, new in MUTATIONS:
        if old is None:
            skipped.append(clause)
            continue
        path = pathlib.Path(P + name)
        src = path.read_text()
        if src.count(old) != 1:
            skipped.append(f"{clause} (pattern count {src.count(old)})")
            continue
        path.write_text(src.replace(old, new))
        try:
            code = run()
        finally:
            path.write_text(src)
        if code == 0:
            survived.append(clause)
        else:
            killed += 1
        print(("KILLED  " if code else "SURVIVED"), clause, flush=True)
    print(f"killed {killed}, survived {len(survived)}, skipped {len(skipped)}")
    for s in survived:
        print("  survived:", s)
    for s in skipped:
        print("  skipped:", s)
    return 1 if survived or skipped else 0


sys.exit(main())
