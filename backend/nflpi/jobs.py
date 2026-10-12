"""Command line jobs and the background refresh loop.

python -m nflpi.jobs bootstrap      # first run: load data, train, predict, backfill
python -m nflpi.jobs ingest         # schedules, lines, teams, injuries, weather
python -m nflpi.jobs train          # fit on seasons before the current one
python -m nflpi.jobs predict        # refresh current + next week
python -m nflpi.jobs loop           # worker: refresh on a game-aware schedule
python -m nflpi.jobs vapid          # print a new Web Push key pair for .env
"""

import argparse
import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from nflpi.db import REFRESH_LOCK_KEY, get_engine, session_factory
from nflpi.ingestion import service
from nflpi.models import AppSetting, Game, ModelVersion
from nflpi.notify import push
from nflpi.predictions import engine

log = logging.getLogger("nflpi.jobs")
TICK_SECONDS = 300
HEARTBEAT_STALE_SECONDS = 2 * TICK_SECONDS
HEARTBEAT_KEY = "worker_heartbeat"


def ingest(session, weather: bool = True) -> dict:
    out = {"schedules": service.ingest_schedules(session).status, "teams": service.ingest_teams(session).status}
    season, week = engine.current_week(session)
    run, changed = service.ingest_injuries(session, season)
    out["injuries"] = run.status
    if weather:
        out["weather"] = service.ingest_weather(session).status
    out["qb_alerts"] = push.alert_injuries(session, changed, season, week)
    return out


def train(session) -> ModelVersion:
    season, _ = engine.current_week(session)
    return engine.train(session, through_season=season - 1)


def predict(session) -> int:
    events = engine.refresh_predictions(session)
    return push.alert_prediction_changes(session, events)


def next_interval(session, now: datetime) -> timedelta:
    """Refresh faster as kickoff gets closer."""
    nxt = session.scalar(select(Game.kickoff_utc).where(Game.kickoff_utc > now).order_by(Game.kickoff_utc).limit(1))
    if nxt is None:
        return timedelta(hours=12)
    until = nxt - now
    if until < timedelta(hours=6):
        return timedelta(minutes=20)
    if until < timedelta(days=2):
        return timedelta(hours=1)
    return timedelta(hours=4)


def tick(session: Session, now: datetime) -> None:
    """Send due reminders and record that the worker is alive."""
    log.info("kickoff reminders sent: %s", push.send_kickoff_reminders(session, now))
    row = session.get(AppSetting, HEARTBEAT_KEY)
    if row is None:
        session.add(AppSetting(key=HEARTBEAT_KEY, value={"at": now.isoformat()}))
    else:
        row.value = {"at": now.isoformat()}
    session.commit()


def cycle(session) -> None:
    """One refresh: ingest, (re)train once per season, then predict and alert."""
    try:
        log.info("kickoff reminders sent: %s", push.send_kickoff_reminders(session, datetime.now(UTC)))
    except Exception:  # noqa: BLE001 - reminders must not stop the refresh
        log.exception("kickoff reminders failed")
        session.rollback()
    with get_engine().connect() as lock_conn:
        acquired = lock_conn.scalar(text("select pg_try_advisory_lock(:k)"), {"k": REFRESH_LOCK_KEY})
        try:
            if acquired:
                log.info("ingest %s", ingest(session))
                season, _ = engine.current_week(session)
                mv = engine.active_model(session)
                if mv is None or mv.trained_through_season < season - 1:
                    train(session)
                    log.info("backfilled %s games", engine.backfill_season(session, season))
                log.info("prediction alerts sent: %s", predict(session))
        finally:
            if acquired:
                lock_conn.execute(text("select pg_advisory_unlock(:k)"), {"k": REFRESH_LOCK_KEY})


def loop() -> None:
    next_refresh = 0.0
    while True:
        with session_factory()() as session:
            try:
                tick(session, datetime.now(UTC))
            except Exception:  # noqa: BLE001 - keep the worker alive
                log.exception("worker tick failed")
                session.rollback()
            if time.monotonic() >= next_refresh:
                try:
                    cycle(session)
                    wait = next_interval(session, datetime.now(UTC))
                except Exception:  # noqa: BLE001 - keep the worker alive; errors are logged and in ingestion_runs
                    log.exception("refresh cycle failed")
                    session.rollback()
                    wait = timedelta(minutes=15)
                next_refresh = time.monotonic() + wait.total_seconds()
                log.info("next refresh in %s", wait)
        time.sleep(TICK_SECONDS)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["bootstrap", "ingest", "train", "predict", "backfill", "loop", "vapid"])
    parser.add_argument("--no-weather", action="store_true")
    args = parser.parse_args()
    if args.command == "loop":
        return loop()
    if args.command == "vapid":
        public, private = push.generate_vapid_keys()
        print(f"VAPID_PUBLIC_KEY={public}\nVAPID_PRIVATE_KEY={private}")
        return None
    with session_factory()() as session:
        if args.command == "bootstrap":
            return cycle(session)
        if args.command == "ingest":
            print("ingest:", ingest(session, weather=not args.no_weather))
        if args.command == "train":
            mv = train(session)
            print("trained:", mv.name, {k: round(v["accuracy"], 4) for k, v in mv.metrics.items()})
        if args.command == "backfill":
            season, _ = engine.current_week(session)
            print("backfilled:", engine.backfill_season(session, season))
        if args.command == "predict":
            print("prediction alerts:", predict(session))


if __name__ == "__main__":
    main()
