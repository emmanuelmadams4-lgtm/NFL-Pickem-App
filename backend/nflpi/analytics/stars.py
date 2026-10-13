"""Rank weekly club stars and find those with current injury reports."""

from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nflpi.ingestion import nflverse
from nflpi.models import Game, IngestionRun, InjuryReport, TeamStar

OFF_SNAP_WEIGHT = 0.1
DEF_SNAP_WEIGHT = 0.05
YARDS_DIVISOR = 10
TOUCHDOWN_POINTS = 6
SACK_POINTS = 6
INTERCEPTION_POINTS = 6
RECEPTION_POINTS = 0.5
ASSIST_POINTS = 0.5
HIT_POINTS = 2
LOSS_POINTS = 2
PASS_DEFENDED_POINTS = 3
FUMBLE_POINTS = 4
SAFETY_POINTS = 2
SIDE_LIMIT = 2
OUT_STATUSES = {"out", "doubtful"}
SLOT_ORDER = {"qb": 0, "off": 1, "def": 2}


def _production(rows: list[dict]) -> tuple[float, float, float]:
    totals = {name: sum(row[name] for row in rows) for name in nflverse.STAR_STATS}
    off = (
        (totals["rushing_yards"] + totals["receiving_yards"]) / YARDS_DIVISOR
        + TOUCHDOWN_POINTS * (totals["rushing_tds"] + totals["receiving_tds"])
        + RECEPTION_POINTS * totals["receptions"]
    )
    de = (
        totals["def_tackles_solo"]
        + totals["def_tackles_with_assist"]
        + ASSIST_POINTS * totals["def_tackle_assists"]
        + SACK_POINTS * totals["def_sacks"]
        + HIT_POINTS * totals["def_qb_hits"]
        + LOSS_POINTS * totals["def_tackles_for_loss"]
        + INTERCEPTION_POINTS * totals["def_interceptions"]
        + PASS_DEFENDED_POINTS * totals["def_pass_defended"]
        + FUMBLE_POINTS * totals["def_fumbles_forced"]
        + TOUCHDOWN_POINTS * totals["def_tds"]
        + SAFETY_POINTS * totals["def_safeties"]
    )
    return off, de, totals["attempts"]


def _candidate(player_id: str | None, history: list[tuple[str, dict]], week: int) -> dict | None:
    prior = [(kind, row) for kind, row in history if row["week"] < week]
    if not prior:
        return None
    latest = max(prior, key=lambda item: item[1]["week"])[1]
    team = latest["team"]
    snaps = [row for kind, row in prior if kind == "snap" and row["team"] == team]
    stats = [row for kind, row in prior if kind == "stat" and row["team"] == team]
    named = max(snaps or stats, key=lambda row: row["week"])
    off_snaps = sum(row["offense_snaps"] for row in snaps)
    def_snaps = sum(row["defense_snaps"] for row in snaps)
    off_prod, def_prod, attempts = _production(stats)
    return {
        "team": team,
        "player_id": player_id,
        "player": named["player"],
        "position": named["position"],
        "off_snaps": off_snaps,
        "def_snaps": def_snaps,
        "off_prod": off_prod,
        "def_prod": def_prod,
        "attempts": attempts,
        "off_score": OFF_SNAP_WEIGHT * off_snaps + off_prod,
        "def_score": DEF_SNAP_WEIGHT * def_snaps + def_prod,
    }


def _row(
    slot: str,
    rank: int,
    player: dict,
    snaps: int,
    production: float,
    score: float,
) -> dict:
    return dict(
        team=player["team"],
        slot=slot,
        rank=rank,
        player_id=player["player_id"],
        player=player["player"],
        position=player["position"],
        snaps=snaps,
        production=production,
        score=score,
    )


def _rank_club(candidates: list[dict]) -> list[dict]:
    rows = []
    qbs = [p for p in candidates if p["position"] == "QB" and (p["off_snaps"] or p["attempts"])]
    if qbs:
        qb = sorted(qbs, key=lambda p: (-p["off_snaps"], -p["attempts"], p["player"]))[0]
        rows.append(_row("qb", 1, qb, qb["off_snaps"], qb["attempts"], float(qb["off_snaps"])))
    for slot in ("off", "def"):
        pool = [
            p for p in candidates if p["position"] != "QB" and (slot == "off") == (p["off_score"] >= p["def_score"])
        ]
        pool.sort(key=lambda p: (-p[f"{slot}_score"], p["player"]))
        for rank, player in enumerate(pool[:SIDE_LIMIT], 1):
            score = player[f"{slot}_score"]
            if score > 0:
                rows.append(
                    _row(
                        slot,
                        rank,
                        player,
                        player[f"{slot}_snaps"],
                        player[f"{slot}_prod"],
                        score,
                    )
                )
    return rows


def rank_stars(
    season: int, snaps: list[dict], stats: list[dict], players: dict[str, str], computed_at: datetime
) -> list[dict]:
    history = defaultdict(list)
    name_ids = defaultdict(set)
    for row in stats:
        name_ids[(row["team"], row["player"])].add(row["player_id"])
    for row in snaps:
        player_id = players.get(row["pfr_id"])
        if not player_id:
            matches = name_ids[(row["team"], row["player"])]
            if len(matches) == 1:
                player_id = next(iter(matches))
        key = ("gsis", player_id) if player_id else ("pfr", row["pfr_id"] or row["player"])
        history[key].append(("snap", row))
    for row in stats:
        history[("gsis", row["player_id"])].append(("stat", row))
    last_week = max((row["week"] for row in snaps + stats), default=0)
    ranked = []
    for week in range(2, last_week + 2):
        clubs = defaultdict(list)
        for (kind, player_id), rows in history.items():
            candidate = _candidate(player_id if kind == "gsis" else None, rows, week)
            if candidate:
                clubs[candidate["team"]].append(candidate)
        for candidates in clubs.values():
            ranked.extend(
                row
                | {
                    "season": season,
                    "week": week,
                    "source": nflverse.SOURCE,
                    "computed_at": computed_at,
                }
                for row in _rank_club(candidates)
            )
    return ranked


def _current_reports(session: Session, game: Game) -> list[InjuryReport]:
    reports = session.scalars(
        select(InjuryReport)
        .where(
            InjuryReport.season == game.season,
            InjuryReport.week == game.week,
            InjuryReport.team.in_((game.away_team, game.home_team)),
        )
        .order_by(InjuryReport.id)
    ).all()
    current = {}
    for report in reports:
        current[(report.team, report.player_id or report.player)] = report
    return list(current.values())


def _star_report(star: TeamStar, reports: list[InjuryReport]) -> InjuryReport | None:
    return max(
        (
            report
            for report in reports
            if report.team == star.team
            and (
                report.player_id == star.player_id
                if report.player_id and star.player_id
                else _normal_name(report.player) == _normal_name(star.player)
            )
        ),
        key=lambda report: report.id,
        default=None,
    )


def _normal_name(name: str) -> str:
    words = name.lower().replace(".", "").replace("'", "").replace("’", "").split()
    if words and words[-1] in {"jr", "sr", "ii", "iii", "iv", "v"}:
        words.pop()
    return " ".join(words)


def _listed_star(star: TeamStar, report: InjuryReport, now: datetime) -> dict:
    return dict(
        team=star.team,
        player=star.player,
        player_id=star.player_id,
        position=star.position,
        slot=star.slot,
        rank=star.rank,
        status=report.report_status,
        injury=report.injury,
        observed_at=report.observed_at,
        source=report.source,
        age_hours=round((now - report.observed_at).total_seconds() / 3600, 1),
    )


def _game_star_data(
    session: Session, game_id: str
) -> tuple[Game, list[tuple[str, int | None, list[TeamStar]]], list[InjuryReport], datetime | None]:
    game = session.get(Game, game_id)
    if game is None:
        raise LookupError(game_id)
    lists = []
    for team in (game.away_team, game.home_team):
        week = session.scalar(
            select(func.max(TeamStar.week)).where(
                TeamStar.season == game.season, TeamStar.week <= game.week, TeamStar.team == team
            )
        )
        rows = session.scalars(
            select(TeamStar).where(TeamStar.season == game.season, TeamStar.week == week, TeamStar.team == team)
        ).all() if week is not None else []
        rows.sort(key=lambda star: (SLOT_ORDER[star.slot], star.rank))
        lists.append((team, week, rows))
    checked_at = session.scalar(
        select(func.max(IngestionRun.finished_at)).where(
            IngestionRun.dataset == "injuries", IngestionRun.status == "ok"
        )
    )
    return game, lists, _current_reports(session, game), checked_at


def game_stars(session: Session, game_id: str, now: datetime | None = None) -> dict:
    """List each club's current stars and their newest game-status report."""
    now = now or datetime.now(UTC)
    game, lists, reports, checked_at = _game_star_data(session, game_id)
    teams = []
    for team, week, stars in lists:
        rows = []
        for star in stars:
            report = _star_report(star, reports)
            status = report.report_status if report and report.report_status else None
            rows.append(dict(
                team=team, player=star.player, position=star.position, slot=star.slot, rank=star.rank,
                status=status, injury=report.injury if status else None,
                observed_at=report.observed_at if status else None,
                age_hours=round((now - report.observed_at).total_seconds() / 3600, 1) if status else None,
            ))
        teams.append(dict(team=team, stars_week=week, stars=rows))
    return dict(game_id=game_id, season=game.season, week=game.week, reports_seen=len(reports),
                checked_at=checked_at, teams=teams)


def stars_out(session: Session, game_id: str, now: datetime | None = None) -> dict:
    """Find out and doubtful stars for a game's latest star list.
    `out` lists stars whose newest report says Out or Doubtful.
    `reports_seen` 0 means the week has no report yet; empty `out` means not known, not nobody is out.
    `age_hours` starts at `observed_at`, when this app first saw that status; `stars_week` is the list used.
    """
    now = now or datetime.now(UTC)
    game, lists, reports, checked_at = _game_star_data(session, game_id)
    stars_week = max((week for _, week, _ in lists if week is not None), default=None)
    result = dict(
        game_id=game_id,
        season=game.season,
        week=game.week,
        stars_week=stars_week,
        checked_at=checked_at,
        reports_seen=len(reports),
        out=[],
    )
    for _, _, stars in lists:
        for star in stars:
            report = _star_report(star, reports)
            if report is not None and (report.report_status or "").lower() in OUT_STATUSES:
                result["out"].append(_listed_star(star, report, now))
    return result
