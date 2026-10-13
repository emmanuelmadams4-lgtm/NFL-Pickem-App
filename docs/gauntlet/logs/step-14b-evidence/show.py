"""Print one stage's stored result as short lines. Usage: uv run python show.py <stage>"""
import json
import sys
from pathlib import Path

d = json.loads((Path(__file__).parent / f"run-{sys.argv[1]}.json").read_text())
r5 = lambda xs: [round(x, 5) for x in xs]  # noqa: E731
print({k: d[k] for k in ("games", "confirm_games", "confirm_clusters", "seconds")}, d.get("scored_games_missing"))
print("baseline", {m: (round(v["accuracy"], 4), round(v["log_loss"], 4)) for m, v in d["baseline"].items()},
      "confirm", {m: (round(v["accuracy"], 4), round(v["log_loss"], 4)) for m, v in d["baseline_confirm"].items()})
for c in d["candidates"]:
    for v in c["variants"]:
        t = v["tune"]
        print("  tune", v["variant"], f"{t['log_loss_gain']:+.5f}", r5(t["log_loss_gain_ci"]),
              "cluster", r5(t["log_loss_gain_ci_cluster"]), "acc", f"{t['accuracy_diff']:+.4f}")
    r = c["confirm"]
    print(c["candidate"], "chosen", c["chosen"], "confirm", f"{r['log_loss_gain']:+.5f}", r5(r["log_loss_gain_ci"]),
          "cluster", r5(r["log_loss_gain_ci_cluster"]), "acc", f"{r['accuracy_diff']:+.4f}", r5(r["accuracy_diff_ci"]),
          "ships", r["ships"], "ships_cluster", r["ships_cluster"], "signal", c["signal"])
