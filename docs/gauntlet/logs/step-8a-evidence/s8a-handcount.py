"""Independent count of the five stars per club, straight from the nflverse CSV files.

Shares no code with nflpi. Written by the coordinator before the build, as the bar the app must match.
Usage: python3 -I s8a-handcount.py <snap_counts.csv> <stats_player_week.csv> <players.csv> <week> <TEAM,TEAM,...>
Prints one line per star: team|slot|rank|player|gsis id|position|snaps|production|score
"""

import csv
import sys

snaps_file, stats_file, players_file, week, teams = sys.argv[1:6]
week = int(week)
OLD = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA"}


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(v):
    return float(v) if v not in ("", "NA") else 0.0


gsis = {r["pfr_id"]: r["gsis_id"] for r in rows(players_file) if r["pfr_id"] and r["gsis_id"]}
people = {}  # (player key, team) -> totals from weeks before `week`


def person(key, team):
    return people.setdefault(
        (key, team), {"id": None, "name": "", "pos": "", "snap_week": 0, "off": 0, "def": 0, "offp": 0.0, "defp": 0.0, "att": 0.0, "last": 0}
    )


for r in rows(snaps_file):
    w = int(r["week"])
    if w >= week:
        continue
    gid = gsis.get(r["pfr_player_id"])
    p = person(gid or "pfr:" + r["pfr_player_id"], OLD.get(r["team"], r["team"]))
    p["id"] = gid
    if w >= p["snap_week"]:
        p["snap_week"], p["name"], p["pos"] = w, r["player"].strip(), r["position"]
    p["off"] += int(float(r["offense_snaps"]))
    p["def"] += int(float(r["defense_snaps"]))
    p["last"] = max(p["last"], w)

for r in rows(stats_file):
    w = int(r["week"])
    if w >= week or not r["player_id"]:
        continue
    p = person(r["player_id"], OLD.get(r["team"], r["team"]))
    p["id"] = r["player_id"]
    if not p["snap_week"]:
        p["name"], p["pos"] = r["player_display_name"].strip(), r["position"]
    p["last"] = max(p["last"], w)
    p["att"] += num(r["attempts"])
    p["offp"] += (num(r["rushing_yards"]) + num(r["receiving_yards"])) / 10
    p["offp"] += 6 * (num(r["rushing_tds"]) + num(r["receiving_tds"])) + 0.5 * num(r["receptions"])
    p["defp"] += num(r["def_tackles_solo"]) + num(r["def_tackles_with_assist"]) + 0.5 * num(r["def_tackle_assists"])
    p["defp"] += 6 * num(r["def_sacks"]) + 2 * num(r["def_qb_hits"]) + 2 * num(r["def_tackles_for_loss"])
    p["defp"] += 6 * num(r["def_interceptions"]) + 3 * num(r["def_pass_defended"]) + 4 * num(r["def_fumbles_forced"])
    p["defp"] += 6 * num(r["def_tds"]) + 2 * num(r["def_safeties"])

latest_team = {}
for (key, team), p in people.items():
    if key not in latest_team or p["last"] > people[(key, latest_team[key])]["last"]:
        latest_team[key] = team

for team in teams.split(","):
    mine = [p for (key, t), p in people.items() if t == team and latest_team[key] == team]
    qbs = sorted((p for p in mine if p["pos"] == "QB"), key=lambda p: (-p["off"], -p["att"], p["name"]))
    off, de = [], []
    for p in mine:
        if p["pos"] == "QB":
            continue
        o, d = 0.1 * p["off"] + p["offp"], 0.05 * p["def"] + p["defp"]
        if max(o, d) <= 0:
            continue
        (off if o >= d else de).append((o if o >= d else d, p))
    for slot, ranked in (("off", off), ("def", de)):
        ranked.sort(key=lambda x: (-x[0], x[1]["name"]))
    for p in qbs[:1]:
        print(f"{team}|qb|1|{p['name']}|{p['id']}|{p['pos']}|{p['off']}|{p['att']:.2f}|{float(p['off']):.2f}")
    for slot, ranked, snap_key, prod_key in (("off", off, "off", "offp"), ("def", de, "def", "defp")):
        for i, (score, p) in enumerate(ranked[:2], 1):
            print(f"{team}|{slot}|{i}|{p['name']}|{p['id']}|{p['pos']}|{p[snap_key]}|{p[prod_key]:.2f}|{score:.2f}")
