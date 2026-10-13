"""Hand check: every club's 2026 head coach, ESPN (the feed the fix uses) against the nflverse games.csv.
Run: python3 check32.py <games.csv>   Prints one markdown row per club."""
import csv, json, sys, time, urllib.request
from collections import defaultdict

def get(url, tries=4):
    for i in range(tries):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "nflpi-check"}), timeout=30))
        except Exception:  # noqa: BLE001 - retry any transport error
            if i == tries - 1:
                raise
            time.sleep(2 ** i)

OURS = {"LAR": "LA", "WSH": "WAS"}
teams = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams")["sports"][0]["leagues"][0]["teams"]
feed = defaultdict(set)
for r in csv.DictReader(open(sys.argv[1])):
    if r["season"] == "2026":
        for s in ("home", "away"):
            feed[r[s + "_team"]].add(r[s + "_coach"])
print("| club | ESPN 2026 head coach | nflverse games.csv 2026 | same |\n|---|---|---|---|")
for t in sorted(teams, key=lambda t: OURS.get(t["team"]["abbreviation"], t["team"]["abbreviation"])):
    tid, abbr = t["team"]["id"], OURS.get(t["team"]["abbreviation"], t["team"]["abbreviation"])
    items = get(f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/teams/{tid}/coaches?lang=en")["items"]
    c = get(items[0]["$ref"].replace("http://", "https://"))
    name = f'{c["firstName"]} {c["lastName"]}'
    print(f"| {abbr} | {name} ({len(items)} listed) | {', '.join(sorted(feed[abbr]))} | {'yes' if feed[abbr] == {name} else 'NO'} |")
