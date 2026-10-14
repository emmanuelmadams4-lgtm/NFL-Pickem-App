"""Print one line per variant and per candidate from run-<stage>.json files."""
import json, sys
for stage in sys.argv[1:]:
    d = json.load(open(f"run-{stage}.json"))
    print(f"== {stage}: games {d['games']}, confirm {d['confirm_games']}, seconds {d['seconds']}")
    for k in d:
        if k.startswith(("games_", "unknown", "quarterback", "input_gap")):
            print("  ", k, d[k])
    for c in d["candidates"]:
        print(f"  {c['candidate']} [{c['label']}] vs {c['baseline']}: chosen {c['chosen']}")
        for v in c["all_variants"]:
            print(f"     {v['variant']}: tune {v['tune_gain']:+.5f} confirm {v['confirm_gain']:+.5f} gap {v['gap']:+.5f}")
        r = c["confirm"]
        print(f"     CONFIRM gain {r['log_loss_gain']:+.5f} ci {r['log_loss_gain_ci'][0]:+.5f}..{r['log_loss_gain_ci'][1]:+.5f}"
              f" cluster {r['log_loss_gain_ci_cluster'][0]:+.5f}..{r['log_loss_gain_ci_cluster'][1]:+.5f}"
              f" acc {r['accuracy_diff']:+.4f} -> {c['verdict']}")
        if "confirm_vs_blend" in c:
            r = c["confirm_vs_blend"]
            print(f"     vs BLEND gain {r['log_loss_gain']:+.5f} ci {r['log_loss_gain_ci'][0]:+.5f}..{r['log_loss_gain_ci'][1]:+.5f}"
                  f" acc {r['accuracy_diff']:+.4f} -> {c['verdict_vs_blend']}")
