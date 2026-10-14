"""Mutation sweep for step 18k: each edit breaks one rule; test_run_check.py must fail for each."""
import pathlib
import subprocess
import sys

B = pathlib.Path("backend")
MUTATIONS = [
    ("M1 simulation count not enforced", "nflpi/analytics/run_check.py", "if n != N_SIMULATIONS:", "if n < 0:"),
    ("M2 spread sign not checked", "nflpi/analytics/run_check.py", "    if not sign_ok:", "    if False:"),
    ("M3 lowercase verdict accepted", "nflpi/analytics/run_check.py", "(text or \"\").strip().splitlines()", "(text or \"\").strip().upper().splitlines()"),
    ("M4 every run passes", "nflpi/predictions/engine.py", "if verdict.status == \"PASS\":", "if True:"),
    ("M5 failed run not marked", "nflpi/predictions/engine.py", "    return kept, marks", "    return kept, {}"),
    ("M6 failed run is used", "nflpi/predictions/engine.py", "    return kept, marks", "    return simulations, marks"),
    ("M7 stored verdict ignored", "nflpi/ai/run_checker.py", "if stored and stored.get(\"hash\") == digest:", "if False:"),
    ("M8 no-verdict retried every run", "nflpi/ai/run_checker.py", "if now - datetime.fromisoformat(stored[\"at\"]) < RETRY_AFTER:", "if False:"),
    ("M9 probability sums unchecked", "nflpi/analytics/run_check.py", "PROB_TOL = 1e-3", "PROB_TOL = 1e3"),
    ("M10 PASS may argue with itself", "nflpi/analytics/run_check.py", "any(ln.startswith(\"FAIL\") for ln in rest)", "False"),
    ("M11 input seen after cutoff ignored", "nflpi/analytics/run_check.py", "m[\"observed_before_cutoff\"] is False", "m[\"observed_before_cutoff\"] is None"),
    ("M12 overtime allowance unbounded", "nflpi/analytics/run_check.py", "OVERTIME_TOTAL_ALLOWANCE = 0.5", "OVERTIME_TOTAL_ALLOWANCE = 50"),
]
survived = []
for name, path, old, new in MUTATIONS:
    f = B / path
    src = f.read_text()
    assert src.count(old) == 1, (name, src.count(old))
    f.write_text(src.replace(old, new))
    try:
        r = subprocess.run(["uv", "run", "pytest", "tests/test_run_check.py", "-q", "-x", "-p", "no:cacheprovider"],
                           cwd=B, capture_output=True, text=True)
    finally:
        f.write_text(src)
    killed = r.returncode != 0
    print(("KILLED  " if killed else "SURVIVED"), name)
    if not killed:
        survived.append(name)
print(f"{len(MUTATIONS) - len(survived)}/{len(MUTATIONS)} killed")
sys.exit(1 if survived else 0)
