"""Run ingestion jobs. Each run is logged; a failed run keeps old data in place."""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, case, delete, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nflpi.analytics.stars import rank_stars
from nflpi.config import get_settings
from nflpi.ingestion import nflverse, weather
from nflpi.models import Game, IngestionRun, InjuryReport, MarketSnapshot, Team, TeamStar, WeatherForecast
from nflpi.predictions.market import novig_home_prob

log = logging.getLogger(__name__)

STALE_HOURS = {
    "schedules": lambda s: s.stale_hours_schedules,
    "teams": lambda s: 24 * 30,
    "injuries": lambda s: s.stale_hours_injuries,
    "weather": lambda s: s.stale_hours_weather,
}


def run_logged(session: Session, source: str, dataset: str, job: Callable[[], int]) -> IngestionRun:
    run = IngestionRun(source=source, dataset=dataset, status="running")
    session.add(run)
    session.commit()
    try:
        run.rows = job()
        run.status = "ok"
    except Exception as exc:  # noqa: BLE001 - every failure is recorded, then surfaced
        session.rollback()
        run.status = "failed"
        run.error = str(exc)[:2000]
        log.exception("ingestion %s/%s failed", source, dataset)
    run.finished_at = datetime.now(UTC)
    session.add(run)
    session.commit()
    return run


def upsert_games(session: Session, games: list[dict], observed_at: datetime) -> int:
    """Upsert schedule rows and record a market snapshot when the line changed."""
    if not games:
        return 0
    rows = [{k: v for k, v in g.items() if not k.startswith("_")} | {"updated_at": observed_at} for g in games]
    for start in range(0, len(rows), 1000):
        chunk = rows[start : start + 1000]
        stmt = insert(Game).values(chunk)
        update = {c: stmt.excluded[c] for c in chunk[0] if c != "game_id"}
        update["status"] = case(
            (
                and_(
                    Game.status == "postponed",
                    stmt.excluded.status == "scheduled",
                    Game.kickoff_utc == stmt.excluded.kickoff_utc,
                ),
                Game.status,
            ),
            else_=stmt.excluded.status,
        )
        session.execute(stmt.on_conflict_do_update(index_elements=["game_id"], set_=update))

    latest = {
        m.game_id: m
        for m in session.scalars(
            select(MarketSnapshot).where(
                MarketSnapshot.id.in_(select(func.max(MarketSnapshot.id)).group_by(MarketSnapshot.game_id))
            )
        )
    }
    new_snaps = []
    for g in games:
        line = (g["_home_ml"], g["_away_ml"], g["_spread"], g["_total"])
        if all(v is None for v in line):
            continue
        prev = latest.get(g["game_id"])
        kind = "closing" if g["status"] == "final" else "latest"
        if prev and (prev.home_moneyline, prev.away_moneyline, prev.spread_line, prev.total_line) == line:
            if prev.kind != kind:
                prev.kind = kind
            continue
        new_snaps.append(
            MarketSnapshot(
                game_id=g["game_id"],
                observed_at=observed_at,
                source=nflverse.SOURCE,
                kind=kind,
                home_moneyline=line[0],
                away_moneyline=line[1],
                spread_line=line[2],
                total_line=line[3],
                home_prob_novig=novig_home_prob(line[0], line[1]),
            )
        )
    session.add_all(new_snaps)
    session.commit()
    return len(rows)


def ingest_schedules(
    session: Session,
    rows: list[dict[str, str]] | None = None,
    head_coaches: dict[str, str] | None = None,
) -> IngestionRun:
    settings = get_settings()

    def job() -> int:
        data = rows if rows is not None else nflverse.fetch_csv("schedules/games.csv")
        games = nflverse.parse_games(data, settings.first_season)
        return upsert_games(session, games, datetime.now(UTC))

    run = run_logged(session, nflverse.SOURCE, "schedules", job)
    if rows is None or head_coaches is not None:
        ingest_head_coaches(session, head_coaches)
    return run


def ingest_head_coaches(session: Session, coaches: dict[str, str] | None = None) -> IngestionRun:
    def job() -> int:
        season = session.scalar(select(func.max(Game.season)))
        if season is None:
            raise RuntimeError("no games loaded")
        current_coaches = coaches if coaches is not None else nflverse.fetch_head_coaches(season)
        changed = 0
        for abbr, name in current_coaches.items():
            for side in ("home", "away"):
                result = session.execute(
                    update(Game)
                    .where(
                        Game.season == season,
                        getattr(Game, f"{side}_team") == abbr,
                        getattr(Game, f"{side}_coach").is_distinct_from(name),
                    )
                    .values(**{f"{side}_coach": name})
                )
                changed += result.rowcount or 0
        session.commit()
        return changed

    return run_logged(session, "espn", "head_coaches", job)


def ingest_teams(session: Session, rows: list[dict[str, str]] | None = None) -> IngestionRun:
    def job() -> int:
        data = rows if rows is not None else nflverse.fetch_csv("teams/teams_colors_logos.csv")
        season = session.scalar(select(func.max(Game.season)))
        current = set(session.scalars(select(Game.home_team).where(Game.season == season)))
        teams = nflverse.parse_teams(data, current)
        if not teams:
            raise RuntimeError("no current teams matched; load schedules first")
        stmt = insert(Team).values(teams)
        session.execute(
            stmt.on_conflict_do_update(
                index_elements=["abbr"], set_={c: stmt.excluded[c] for c in teams[0] if c != "abbr"}
            )
        )
        session.commit()
        return len(teams)

    return run_logged(session, nflverse.SOURCE, "teams", job)


def ingest_injuries(
    session: Session, season: int, rows: list[dict[str, str]] | None = None
) -> tuple[IngestionRun, list[InjuryReport]]:
    """Insert a row only when a player's status changed. Returns the changed rows."""
    changed: list[InjuryReport] = []

    def job() -> int:
        data = rows if rows is not None else nflverse.fetch_csv(f"injuries/injuries_{season}.csv")
        now = datetime.now(UTC)
        incoming = nflverse.parse_injuries(data, now)
        current = {}
        for r in session.scalars(select(InjuryReport).where(InjuryReport.season == season).order_by(InjuryReport.id)):
            current[(r.week, r.team, r.player_id or r.player)] = (r.report_status, r.practice_status)
        for r in incoming:
            key = (r["week"], r["team"], r["player_id"] or r["player"])
            if current.get(key) != (r["report_status"], r["practice_status"]):
                changed.append(InjuryReport(**r))
        session.add_all(changed)
        session.commit()
        return len(changed)

    return run_logged(session, nflverse.SOURCE, "injuries", job), changed


def _parse_star_file(rows: list[dict[str, str]], parser: Callable, name: str, *args) -> object:
    try:
        return parser(rows, *args)
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{name}: {exc!r}") from exc


def _check_star_file_pairs(parsed_snaps: list[dict], parsed_stats: list[dict]) -> None:
    snap_pairs = {(row["week"], row["team"]) for row in parsed_snaps}
    stat_pairs = {(row["week"], row["team"]) for row in parsed_stats}
    if snap_pairs - stat_pairs:
        week, club = min(snap_pairs - stat_pairs)
        raise RuntimeError(f"stats_player_week lacks ({week}, {club})")
    if stat_pairs - snap_pairs:
        week, club = min(stat_pairs - snap_pairs)
        raise RuntimeError(f"snap_counts lacks ({week}, {club})")


def _check_stars_against_stored(session: Session, season: int, ranked: list[dict]) -> None:
    last_week = max(row["week"] for row in ranked)
    stored_week = session.scalar(select(func.max(TeamStar.week)).where(TeamStar.season == season))
    if stored_week is not None and last_week < stored_week:
        raise RuntimeError("new stars end before stored stars")
    stored_clubs = session.scalar(
        select(func.count(func.distinct(TeamStar.team))).where(
            TeamStar.season == season,
            TeamStar.week == last_week,
        )
    )
    new_clubs = {row["team"] for row in ranked if row["week"] == last_week}
    if len(new_clubs) < stored_clubs:
        raise RuntimeError("new stars have fewer clubs than stored stars")


def ingest_stars(
    session: Session,
    season: int,
    snaps: list[dict[str, str]] | None = None,
    stats: list[dict[str, str]] | None = None,
    players: list[dict[str, str]] | None = None,
) -> IngestionRun:
    def job() -> int:
        snap_rows = snaps if snaps is not None else nflverse.fetch_csv(f"snap_counts/snap_counts_{season}.csv")
        stat_rows = stats if stats is not None else nflverse.fetch_csv(f"stats_player/stats_player_week_{season}.csv")
        player_rows = players if players is not None else nflverse.fetch_csv("players/players.csv")
        parsed_snaps = _parse_star_file(snap_rows, nflverse.parse_star_snaps, "snap_counts", season)
        parsed_stats = _parse_star_file(stat_rows, nflverse.parse_star_stats, "stats_player_week", season)
        ids = _parse_star_file(player_rows, nflverse.parse_star_players, "players")
        if not parsed_snaps or not parsed_stats or not ids:
            raise RuntimeError("incomplete star files; keeping existing season")
        _check_star_file_pairs(parsed_snaps, parsed_stats)
        ranked = rank_stars(season, parsed_snaps, parsed_stats, ids, datetime.now(UTC))
        if not ranked:
            raise RuntimeError("no stars ranked; keeping existing season")
        _check_stars_against_stored(session, season, ranked)
        session.execute(delete(TeamStar).where(TeamStar.season == season))
        session.add_all(TeamStar(**row) for row in ranked)
        session.commit()
        return len(ranked)

    return run_logged(session, nflverse.SOURCE, "stars", job)


def ingest_weather(session: Session, now: datetime | None = None) -> IngestionRun:
    now = now or datetime.now(UTC)

    def job() -> int:
        upcoming = session.scalars(
            select(Game).where(
                Game.status == "scheduled",
                Game.time_tbd.is_(False),
                Game.kickoff_utc > now,
                Game.kickoff_utc < now + timedelta(days=7),
            )
        ).all()
        saved = 0
        for g in upcoming:
            if not weather.needs_forecast(g.roof, g.stadium_id):
                continue
            wx = weather.fetch_forecast(g.stadium_id, g.kickoff_utc)
            if wx is None:
                continue
            session.add(WeatherForecast(game_id=g.game_id, observed_at=now, source=weather.SOURCE, **wx))
            saved += 1
        session.commit()
        return saved

    return run_logged(session, weather.SOURCE, "weather", job)


def freshness(session: Session, now: datetime | None = None) -> list[dict]:
    """Last good refresh per dataset, plus whether it is stale."""
    settings = get_settings()
    now = now or datetime.now(UTC)
    out = []
    for dataset, hours in STALE_HOURS.items():
        ok = session.scalar(
            select(func.max(IngestionRun.finished_at)).where(
                IngestionRun.dataset == dataset, IngestionRun.status == "ok"
            )
        )
        last = session.scalars(
            select(IngestionRun).where(IngestionRun.dataset == dataset).order_by(IngestionRun.id.desc()).limit(1)
        ).first()
        age = (now - ok).total_seconds() / 3600 if ok else None
        out.append(
            {
                "dataset": dataset,
                "last_success": ok,
                "age_hours": round(age, 2) if age is not None else None,
                "stale": age is None or age > hours(settings),
                "last_error": last.error if last and last.status == "failed" else None,
            }
        )
    return out
