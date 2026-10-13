"""Step 16a hand check (criterion H1): the owner's two real group files against an independent count.

Run from backend/, on the lane's own database, never the live one:
  DATABASE_URL=postgresql+psycopg://nflpi:nflpi@localhost:15445/nflpi_hand \
    uv run python ../docs/gauntlet/logs/step-16a-evidence/s16a-handcheck.py <games.csv> <picks.csv> <weekly.csv>

Part A uses the app: real 2026 schedule in, both files imported, rows read back.
Part B shares no code with the app: it reads the same three files with the csv module and counts on its own.
The real files hold real member names, so nothing here prints a name: members are shown as M01, M02, ...
"""

import csv
import os
import sys
from collections import defaultdict

SEASON = 2026
# Part B's own code table (written by hand from the 32 codes in the file; the app's rule is upper case + franchise()).
CODES = {"Ari": "ARI", "Atl": "ATL", "Bal": "BAL", "Buf": "BUF", "Car": "CAR", "Chi": "CHI", "Cin": "CIN",
         "Cle": "CLE", "Dal": "DAL", "Den": "DEN", "Det": "DET", "GB": "GB", "Hou": "HOU", "Ind": "IND",
         "Jax": "JAX", "KC": "KC", "LAC": "LAC", "LAR": "LA", "LV": "LV", "Mia": "MIA", "Min": "MIN", "NE": "NE",
         "NO": "NO", "NYG": "NYG", "NYJ": "NYJ", "Phi": "PHI", "Pit": "PIT", "SF": "SF", "Sea": "SEA", "TB": "TB",
         "Ten": "TEN", "Was": "WAS"}


def read(path: str) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def app_side(games_rows, picks_path, weekly_path):
    assert ":15445/" in os.environ["DATABASE_URL"], "lane database only"
    from sqlalchemy import select

    from nflpi.db import Base, get_engine, session_factory
    from nflpi.group.importer import import_group_csv
    from nflpi.group.queries import game_shares, standings
    from nflpi.ingestion import service
    from nflpi.models import Game, GroupPick, GroupStanding

    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with session_factory()() as s:
        run = service.ingest_schedules(s, games_rows)
        assert run.status == "ok", run.error
        results = [import_group_csv(s, SEASON, open(p, "rb").read()) for p in (picks_path, weekly_path)]
        again = [import_group_csv(s, SEASON, open(p, "rb").read()) for p in (picks_path, weekly_path)]
        picks = {(p.game_id, p.member): (p.picked_team, p.confidence) for p in s.scalars(select(GroupPick))}
        stand = {(r.season, r.week, r.member): (r.points, r.rank) for r in s.scalars(select(GroupStanding))}
        game_ids = [g.game_id for g in s.scalars(select(Game).where(Game.season == SEASON, Game.week <= 5))]
        shares = {gid: game_shares(s, gid) for gid in game_ids}
        tables = {w: standings(s, SEASON, w) for w in range(1, 6)}
    return results, again, picks, stand, shares, tables


def main() -> int:
    games_path, picks_path, weekly_path = sys.argv[1:4]
    games_rows = [r for r in read(games_path) if r["season"] == str(SEASON)]
    results, again, picks, stand, shares, tables = app_side(games_rows, picks_path, weekly_path)

    # Part B: independent count ----------------------------------------------------------------------------------
    raw_picks, raw_weekly = read(picks_path), read(weekly_path)
    label = {name: f"M{i:02d}" for i, name in enumerate(sorted({r["Team"] for r in raw_picks + raw_weekly}), 1)}
    game_of, winner = {}, {}
    for g in games_rows:
        game_of[(int(g["week"]), frozenset((g["away_team"], g["home_team"])))] = g
        if g["home_score"] not in ("", "NA") and g["home_score"] != g["away_score"]:
            winner[g["game_id"]] = g["home_team"] if int(g["home_score"]) > int(g["away_score"]) else g["away_team"]
    want_picks, tally, earned = {}, defaultdict(lambda: defaultdict(list)), defaultdict(int)
    for r in raw_picks:
        g = game_of[(int(r["Week"]), frozenset((CODES[r["Favored"]], CODES[r["Underdog"]])))]
        pick = CODES[r["Pick"]] if r["Pick"] else None
        conf = int(r["Confidence"]) if r["Confidence"] else None
        want_picks[(g["game_id"], r["Team"])] = (pick, conf)
        tally[g["game_id"]][pick].append(conf)
        earned[(int(r["Week"]), r["Team"])] += conf if pick and winner.get(g["game_id"]) == pick else 0
    weeks = [c for c in raw_weekly[0] if c.startswith("Wk")]
    last = int(weeks[-1][2:])
    want_stand = {(SEASON, int(w[2:]), r["Team"]): (int(r[w]), int(r["Rank"]) if int(w[2:]) == last else None)
                  for r in raw_weekly for w in weeks}

    bad = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal bad
        bad += not ok
        print(f"{'PASS' if ok else 'FAIL'} {name} {detail}")

    check("import results", [(r.kind, r.rows) for r in results] == [("picks", len(raw_picks)),
                                                                   ("standings", len(raw_weekly) * len(weeks))],
          f"{[(r.kind, r.rows) for r in results]}")
    check("second import changes nothing", [(r.kind, r.rows) for r in again] == [(r.kind, r.rows) for r in results]
          and len(picks) == len(raw_picks) and len(stand) == len(raw_weekly) * len(weeks))
    diff = [k for k in want_picks.keys() | picks.keys() if want_picks.get(k) != picks.get(k)]
    check("stored picks equal the file", not diff, f"rows {len(picks)} of {len(want_picks)}, different {len(diff)}"
          + "".join(f" [{g} {label.get(m, '?')}]" for g, m in diff[:5]))
    none = sum(1 for v in picks.values() if v[0] is None)
    check("no-pick rows stored as missing", none == sum(1 for r in raw_picks if not r["Pick"]), f"{none}")
    diff = [k for k in want_stand.keys() | stand.keys() if want_stand.get(k) != stand.get(k)]
    check("stored weekly points and rank equal the file", not diff, f"rows {len(stand)}, different {len(diff)}")
    wrong = 0
    for gid, by_pick in tally.items():
        g = next(x for x in games_rows if x["game_id"] == gid)
        picked = sum(len(v) for k, v in by_pick.items() if k)
        for side, team in (("away", g["away_team"]), ("home", g["home_team"])):
            confs = by_pick.get(team, [])
            want = {"team": team, "picks": len(confs), "share": len(confs) / picked if picked else None,
                    "avg_confidence": sum(confs) / len(confs) if confs else None}
            got = shares[gid][side]
            same = got["team"] == want["team"] and got["picks"] == want["picks"] and all(
                (got[k] is None) == (want[k] is None) and (got[k] is None or abs(got[k] - want[k]) < 1e-9)
                for k in ("share", "avg_confidence"))
            wrong += not same
        wrong += shares[gid]["members"] != sum(len(v) for v in by_pick.values()) or shares[gid]["picked"] != picked
    check("game_shares equal an independent tally", wrong == 0 and len(tally) == len(shares),
          f"games {len(tally)} (app listed {len(shares)}), wrong sides {wrong}")
    miss = [(int(w[2:]), r["Team"]) for r in raw_weekly for w in weeks if earned[(int(w[2:]), r["Team"])] != int(r[w])]
    check("straight winners x confidence equals Yahoo's weekly points", not miss,
          f"member-weeks {len(raw_weekly) * len(weeks)}, different {len(miss)}"
          + "".join(f" [wk{w} {label[m]}: counted {earned[(w, m)]}]" for w, m in miss[:8]))
    file_total = [(w, r["Team"]) for r in raw_picks for w in [int(r["Week"])]
                  if int(r["Week_Total_Pts"]) != want_stand[(SEASON, w, r["Team"])][0]]
    check("picks file week totals equal the weekly file", not file_total, f"different rows {len(file_total)}")
    wrong = 0
    for w, rows in tables.items():
        running = {r["Team"]: sum(int(r[f"Wk{i}"]) for i in range(1, w + 1)) for r in raw_weekly}
        wrong += len(rows) != len(raw_weekly)
        wrong += [x["total"] for x in rows] != sorted(running.values(), reverse=True)
        wrong += any(x["total"] != running[x["member"]] or x["points"] != int(next(
            r for r in raw_weekly if r["Team"] == x["member"])[f"Wk{w}"]) for x in rows)
        if w == last:
            wrong += [x["rank"] for x in rows] != list(range(1, len(rows) + 1))
            by_rank = sorted(raw_weekly, key=lambda r: int(r["Rank"]))
            wrong += [x["member"] for x in rows] != [r["Team"] for r in by_rank]
        else:
            wrong += any(x["rank"] is not None for x in rows)
    check("standings() per week equal the file (totals, order, last-week rank = Yahoo's order)", wrong == 0,
          f"weeks {len(tables)}, members {len(raw_weekly)}, problems {wrong}")
    print(f"members {len(label)}, games with results {len(winner)}, weeks {weeks[0]}..{weeks[-1]}")
    print("HAND CHECK", "PASS" if not bad else f"FAIL ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
